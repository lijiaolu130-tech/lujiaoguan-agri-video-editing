#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_dy_list.py —— 抖音发布终验：管理页全量枚举 + 队列指纹差集

管理页（creator.douyin.com/creator-micro/content/manage）是无限滚动非分页，
DOM 向上爬卡片法会失效。唯一可靠法：**innerText 滚动累积**——
每轮 scrollTo 到底 + 把所有可滚容器拉满，抓 body.innerText，
文本长度连续 4 轮不变即到底；按「编辑作品」分段提取标题/日期/可见性。

拿标题前 8 字指纹与发布队列做差集：页面跳转成功≠服务端入库。

用法（需要带 playwright 的 python，通常是 homebrew python3）:
  python3 verify_dy_list.py --queue <队列.json> --date 2026年10月05日
      [--profile <chrome_profile目录>] [-o 差集.json]

队列 json 格式: 标题字符串数组，或 [{"title": ...}, ...]。
"""
import argparse
import json
import os
import re
import time

from playwright.sync_api import sync_playwright

DEFAULT_PROFILE = os.path.expanduser('~/douyin_chrome_profile')  # 或指向已有的 playwright persistent profile


def load_queue(path):
    q = json.load(open(path, encoding='utf-8'))
    if isinstance(q, dict):
        for k in ('titles', 'queue', 'items'):
            if k in q and isinstance(q[k], list):
                q = q[k]; break
    titles = []
    for it in q:
        if isinstance(it, str):
            titles.append(it)
        elif isinstance(it, dict):
            t = it.get('title') or it.get('name') or ''
            if t:
                titles.append(t)
    return titles


def main():
    ap = argparse.ArgumentParser(description='抖音管理页指纹差集终验')
    ap.add_argument('--queue', required=True, help='发布队列 json（标题数组或对象数组）')
    ap.add_argument('--date', default='', help='只统计该日期的卡片，如 2026年10月05日（留空=不限）')
    ap.add_argument('--profile', default=DEFAULT_PROFILE, help='chrome persistent profile 目录')
    ap.add_argument('-o', '--out', default='dy_verify_diff.json')
    ap.add_argument('--max-rounds', type=int, default=60)
    args = ap.parse_args()

    queue = load_queue(args.queue)
    date_re = re.compile(r'\d{4}年\d{2}月\d{2}日 \d{2}:\d{2}')
    seen = {}

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            args.profile, headless=False, viewport={'width': 1500, 'height': 950})
        pg = ctx.pages[0] if ctx.pages else ctx.new_page()
        pg.goto('https://creator.douyin.com/creator-micro/content/manage',
                wait_until='domcontentloaded', timeout=60000)
        time.sleep(10)
        last_len, stale = -1, 0
        for r in range(args.max_rounds):
            txt = pg.evaluate("()=>document.body?document.body.innerText:''") or ''
            # 每张卡以「编辑作品」结尾：可见性标记后的文案即标题
            for seg in txt.split('编辑作品'):
                m = date_re.search(seg)
                vis = '私密' if '私密' in seg else ('已发布' if '已发布' in seg else '?')
                parts = re.split(r'私密|已发布', seg)
                title = (parts[1] if len(parts) > 1 else '').strip().replace('\n', ' ')[:60]
                if title and m:
                    seen[(title[:30], m.group(0))] = {
                        'title': title, 'date': m.group(0), 'vis': vis}
            today = sum(1 for c in seen.values()
                        if not args.date or c['date'].startswith(args.date))
            print('round%d 文本%d 卡片%d 当日%d' % (r, len(txt), len(seen), today), flush=True)
            if len(txt) == last_len:
                stale += 1
                if stale >= 4:
                    break
            else:
                stale = 0
            last_len = len(txt)
            pg.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            try:
                pg.evaluate("""()=>{const els=[...document.querySelectorAll('div')].filter(
                    d=>d.scrollHeight>d.clientHeight+200&&d.clientHeight>300);
                    els.forEach(d=>d.scrollTop=d.scrollHeight)}""")
            except Exception:
                pass
            time.sleep(3)
        ctx.close()

    dump = json.dumps([c['title'] for c in seen.values()], ensure_ascii=False)
    hit = [t for t in queue if t[:8] in dump]
    miss = [t for t in queue if t[:8] not in dump]
    json.dump({'cards': list(seen.values()), 'hit': hit, 'miss': miss},
              open(args.out, 'w'), ensure_ascii=False, indent=1)
    print('=== 终验：命中 %d / %d ===' % (len(hit), len(queue)))
    for t in miss:
        print('  MISS:', t[:36])
    print('DIFF_DONE ->', args.out)


if __name__ == '__main__':
    main()
