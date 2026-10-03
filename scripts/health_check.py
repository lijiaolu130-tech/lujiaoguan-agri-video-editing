#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""health_check.py —— 成片全量体检：规格/时长/响度/削波

用法:
    python3 health_check.py <视频目录> [<视频目录> ...] [-o 报告.json]

检查项:
  1) 分辨率 = 1080x1920（竖屏标准，可用 --size 放宽）
  2) 音频流存在 (AAC)
  3) 响度 Integrated 在 [-24, -14] LUFS（可用 --lufs 调）
  4) 无削波: true peak < -0.1 dBFS
  5) 时长 > 3s
异常逐条打印，报告落 JSON。
"""
import argparse
import json
import os
import re
import subprocess

FF = os.environ.get('FF', '/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg')
FP = os.environ.get('FP', '/opt/homebrew/opt/ffmpeg-full/bin/ffprobe')


def probe(p):
    r = subprocess.run([FP, '-v', 'error', '-show_entries',
                        'stream=width,height,codec_name:format=duration',
                        '-of', 'json', p], capture_output=True, text=True)
    return json.loads(r.stdout)


def loudness(p):
    """整段响度。⚠️ ebur128 的 progress 段每 100ms 打一个 I 值，
    起始值恒为 -70 —— 必须取最后一段 'Integrated loudness:' 之后的 Summary 值。"""
    e = subprocess.run([FF, '-v', 'info', '-i', p, '-af', 'ebur128=peak=true',
                        '-f', 'null', '-'], capture_output=True, text=True)
    seg = e.stderr.rsplit('Integrated loudness:', 1)[-1]
    mi = re.search(r'I:\s*(-?[\d.]+) LUFS', seg)
    mp = re.search(r'Peak:\s*(-?[\d.]+) dBFS', seg)
    return (float(mi.group(1)) if mi else -99.0,
            float(mp.group(1)) if mp else -99.0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('dirs', nargs='+')
    ap.add_argument('-o', '--out', default='health_check_report.json')
    ap.add_argument('--size', default='1080x1920')
    ap.add_argument('--lufs', default='-24,-14')
    args = ap.parse_args()
    w_exp, h_exp = (int(x) for x in args.size.split('x'))
    lo, hi = (float(x) for x in args.lufs.split(','))

    res, bad = [], []
    for d in args.dirs:
        for f in sorted(os.listdir(d)):
            if not f.endswith('.mp4'):
                continue
            p = os.path.join(d, f)
            try:
                j = probe(p)
                v = [s for s in j['streams'] if s.get('codec_name') in ('h264', 'hevc')]
                a = [s for s in j['streams'] if s.get('codec_name') == 'aac']
                dur = float(j['format']['duration'])
                w, h = (v[0].get('width'), v[0].get('height')) if v else (-1, -1)
                lufs, peak = loudness(p)
            except Exception as e:
                res.append({'file': p, 'err': str(e)[:120]})
                bad.append({'file': p, 'why': 'probe_fail'})
                continue
            r = {'file': p, 'dur': round(dur, 1), 'w': w, 'h': h,
                 'aac': len(a), 'lufs': lufs, 'peak': peak}
            res.append(r)
            why = []
            if (w, h) != (w_exp, h_exp):
                why.append('size %sx%s' % (w, h))
            if len(a) < 1:
                why.append('no_aac')
            if not (lo <= lufs <= hi):
                why.append('lufs %.1f' % lufs)
            if peak > -0.1:
                why.append('clipping peak %.1f' % peak)
            if dur < 3:
                why.append('too_short')
            if why:
                r['why'] = ';'.join(why)
                bad.append(r)
                print('⚠ %s  %s' % (os.path.basename(p), r['why']), flush=True)
    json.dump(res, open(args.out, 'w'), ensure_ascii=False, indent=1)
    print('总计 %d，异常 %d，报告 → %s' % (len(res), len(bad), args.out))


if __name__ == '__main__':
    main()
