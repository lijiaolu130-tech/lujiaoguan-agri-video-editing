#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""asr_filler_scan.py —— 成片 ASR 兜底扫描：找孤立语气词/句首起势词

用法:
  python3 asr_filler_scan.py <视频目录或文件...> [-o 报告.json]
      [--model ~/.cache/whisper.cpp/ggml-small.bin]
      [--ffmpeg /opt/homebrew/opt/ffmpeg-full/bin/ffmpeg]
      [--words 嗯,啊,哦,呃,唉,诶]

流程（每条）:
  1) ffmpeg 抽音轨 mono 16k wav → /tmp/asr_scan/
  2) whisper-cli -osrt（注意: txt 输出参数是 -otxt，写 -ot 会 stoi 崩溃）
  3) 解析 srt，找「整卡只有语气词」或「句首起势语气词+逗号」的 cue

⚠️ 命中≠实锤: ASR 听到「嗯」不代表字幕烧了「嗯」。
   命中项必须抽帧亲眼读烧录字幕再下刀:
   ffmpeg -ss <秒> -i <视频> -frames:v 1 -vf fps=1 out.jpg
   （抽帧用 fps= 滤镜，select 复合表达式会抓错帧）
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile

WHISPER = '/opt/homebrew/bin/whisper-cli'
CUE_RE = re.compile(r'(\d{2}:\d{2}:\d{2})[,.](\d{3}) --> (\d{2}:\d{2}:\d{2})')


def sh(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def ts2sec(hms):
    h, m, s = (int(x) for x in hms.split(':'))
    return h * 3600 + m * 60 + s


def scan_one(video, args):
    base = os.path.splitext(os.path.basename(video))[0]
    tmp = tempfile.mkdtemp(prefix='asr_scan_')
    wav = os.path.join(tmp, 'a.wav')
    r = sh([args.ffmpeg, '-y', '-v', 'error', '-i', video,
            '-vn', '-ac', '1', '-ar', '16000', '-c:a', 'pcm_s16le', wav])
    if r.returncode:
        return {'error': 'extract: ' + (r.stderr or '')[-200:]}
    r = sh([WHISPER, '-m', args.model, '-l', 'zh', '-osrt',
            '--prompt', '以下是普通话的句子，请使用简体中文。',
            '--max-len', str(args.max_len),
            '-of', os.path.join(tmp, 'a'), wav])
    srt = os.path.join(tmp, 'a.srt')
    if r.returncode or not os.path.exists(srt):
        return {'error': 'whisper: ' + (r.stderr or '')[-200:]}
    words = [w for w in args.words.split(',') if w]
    hits = []
    cues = []
    cur_ts = ''
    for line in open(srt, encoding='utf-8', errors='ignore'):
        line = line.strip()
        m = CUE_RE.search(line)
        if m:
            cur_ts = line
            continue
        if not line or line.isdigit():
            continue
        cues.append((cur_ts, line))
        text = re.sub(r'[，。！？,.!?]', '', line)
        for w in words:
            # 整卡只有语气词，或句首起势「嗯，xxx」
            if text == w or re.match(r'^%s[，,]' % w, line):
                hits.append([cur_ts, line, '%.1f' % ts2sec(m and m.group(1) or '00:00:00')])
                break
    return {'cues': len(cues), 'hits': hits, 'srt': srt}


def main():
    ap = argparse.ArgumentParser(description='成片 ASR 语气词兜底扫描')
    ap.add_argument('targets', nargs='+', help='视频目录或文件')
    ap.add_argument('-o', '--out', default='filler_scan.json')
    ap.add_argument('--model', default=os.path.expanduser(
        '~/.cache/whisper.cpp/ggml-small.bin'))
    ap.add_argument('--ffmpeg', default='/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg')
    ap.add_argument('--words', default='嗯,啊,哦,呃,唉,诶')
    ap.add_argument('--max-len', type=int, default=28,
                    help='whisper 分段最大字符数（默认 28，约 7s 一卡；越大卡越长越漏检）')
    args = ap.parse_args()

    videos = []
    for t in args.targets:
        if os.path.isdir(t):
            videos += sorted(os.path.join(t, f) for f in os.listdir(t)
                             if f.endswith(('.mp4', '.mov', '.MOV')))
        elif os.path.isfile(t):
            videos.append(t)
    if not videos:
        print('no videos found'); sys.exit(1)
    if not os.path.exists(args.model):
        print('model not found: %s' % args.model); sys.exit(1)

    report = {}
    for i, v in enumerate(videos, 1):
        print('[%d/%d] %s' % (i, len(videos), os.path.basename(v)), flush=True)
        report[os.path.basename(v)] = scan_one(v, args)
    json.dump(report, open(args.out, 'w'), ensure_ascii=False, indent=1)

    n_hit = sum(1 for r in report.values() if r.get('hits'))
    print('=== DONE %d 条，命中语气词 %d 条（详见 %s）===' % (len(report), n_hit, args.out))
    print('⚠️ 命中≠实锤，逐条抽帧读烧录字幕后再决定是否动刀！')


if __name__ == '__main__':
    main()
