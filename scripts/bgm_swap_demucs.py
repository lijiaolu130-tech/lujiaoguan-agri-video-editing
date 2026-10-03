#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bgm_swap_demucs.py —— 引擎已删的旧成片换 BGM（demucs 人声分离重混）

从成片里干净分出人声，再混入新 BGM。字幕跟着视频流 copy，不动。
CPU 约 8 秒/条（htdemucs --two-stems=vocals）。

用法:
  python3 bgm_swap_demucs.py --src <成片目录或文件...> --bgm <新BGM.mp3> --out <输出目录>
      [--demucs-python <带demucs的python>] [--lufs -29]

依赖:
  - demucs 装在 venv 里（pip install demucs），用 --demucs-python 指定该解释器
  - ffmpeg-full: /opt/homebrew/opt/ffmpeg-full/bin/ffmpeg

混音链（已验证最优值）:
  人声: highpass=f=65
  BGM:  loudnorm=I=-29:TP=-9:LRA=7 → afade in 1s / out 3s（尾部 2.6s 起）
  侧链闪避: sidechaincompress=threshold=0.018:ratio=8:attack=12:release=350
  混合: amix inputs=2 duration=first normalize=0（人声必须 asplit 成两路）
"""
import argparse
import os
import subprocess
import sys
import tempfile

FF = '/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg'
FP = '/opt/homebrew/opt/ffmpeg-full/bin/ffprobe'


def sh(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def dur_of(p):
    r = sh([FP, '-v', 'error', '-show_entries', 'format=duration',
            '-of', 'csv=p=0', p])
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def swap(src, bgm, out_dir, py, lufs):
    name = os.path.basename(src)
    dest = os.path.join(out_dir, name)
    if os.path.exists(dest):
        print('  ✓ 已存在，跳过 %s' % name)
        return True
    tmp = tempfile.mkdtemp(prefix='demucs_')
    wav = os.path.join(tmp, 'audio.wav')
    voc = os.path.join(tmp, 'htdemucs', 'audio', 'vocals.wav')

    r = sh([FF, '-y', '-v', 'error', '-i', src, '-vn', '-ac', '1',
            '-ar', '44100', '-c:a', 'pcm_s16le', wav])
    if r.returncode:
        print('  ✗ 抽音轨失败', (r.stderr or '')[-200:]); return False
    r = subprocess.run([py, '-m', 'demucs', '-n', 'htdemucs',
                        '--two-stems=vocals', '-o', tmp, wav],
                       capture_output=True, text=True)
    if not os.path.exists(voc):
        print('  ✗ demucs 失败', (r.stderr or '')[-300:]); return False

    dur = dur_of(src)
    fo = max(0.5, dur - 2.6)
    fc = (
        "[1:a]highpass=f=65,aresample=48000[voice];"
        "[2:a]atrim=duration={dur:.2f},asetpts=PTS-STARTPTS,"
        "loudnorm=I={lufs}:TP=-9:LRA=7,aresample=48000,"
        "afade=t=in:d=1,afade=t=out:st={fo:.2f}:d=3[music];"
        "[voice]asplit=2[vmix][key];"
        "[music][key]sidechaincompress=threshold=0.018:ratio=8"
        ":attack=12:release=350[ducked];"
        "[vmix][ducked]amix=inputs=2:duration=first:normalize=0,"
        "alimiter=limit=0.84:level=0:latency=1[a]"
    ).format(dur=dur, fo=fo, lufs=lufs)
    r = sh([FF, '-y', '-v', 'error', '-i', src, '-i', voc,
            '-stream_loop', '-1', '-i', bgm,
            '-filter_complex', fc, '-map', '0:v', '-map', '[a]',
            '-c:v', 'copy', '-c:a', 'aac', '-b:a', '256k',
            '-ar', '48000', '-ac', '2', '-t', '%.2f' % dur,
            '-movflags', '+faststart', dest])
    if r.returncode or not os.path.exists(dest):
        print('  ✗ 混音失败', (r.stderr or '')[-200:]); return False
    print('  ✓ %s（%.1fs）' % (dest, dur_of(dest)))
    return True


def main():
    ap = argparse.ArgumentParser(description='demucs 人声分离换 BGM')
    ap.add_argument('--src', nargs='+', required=True, help='成片目录或文件')
    ap.add_argument('--bgm', required=True, help='新 BGM 音频文件')
    ap.add_argument('--out', required=True, help='输出目录（不要指向交付目录，验收后再部署）')
    ap.add_argument('--demucs-python', default=sys.executable,
                    help='装有 demucs 的 python 解释器路径')
    ap.add_argument('--lufs', default='-29', help='BGM 响度（默认 -29）')
    args = ap.parse_args()

    videos = []
    for t in args.src:
        if os.path.isdir(t):
            videos += sorted(os.path.join(t, f) for f in os.listdir(t)
                             if f.endswith(('.mp4', '.mov', '.MOV')))
        elif os.path.isfile(t):
            videos.append(t)
    if not videos:
        print('no videos found'); sys.exit(1)
    os.makedirs(args.out, exist_ok=True)

    ok = 0
    for v in videos:
        print('=== %s ===' % os.path.basename(v), flush=True)
        if swap(v, args.bgm, args.out, args.demucs_python, args.lufs):
            ok += 1
    print('DONE %d/%d' % (ok, len(videos)))


if __name__ == '__main__':
    main()
