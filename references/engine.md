# 确定性剪辑引擎范本（73 行，可直接抄）

设计目标：同输入永远同输出；返修=改 SPECS 重跑；人工只做「裁决」不做「重复劳动」。

## 1. 项目目录与转写

```
项目目录/
├── work/          # 转写 json + 中间产物
├── out/           # 成片（成片_XX_slug.mp4）
├── fonts/         # 字体
└── bgm/norm/      # BGM loudnorm 缓存（换曲先清空！）
```

转写命令（词级时间戳 + 简体强制）：

```bash
whisper-cli -m ~/.cache/whisper.cpp/ggml-small.bin -l zh \
  --prompt "以下是普通话的句子，请使用简体中文。" \
  -oj -ojf -of work/IMG_XXXX ~/Downloads/IMG_XXXX.MOV
```

⚠️ 方言素材不带 prompt 会间歇性吐繁体；`norm()` 只按汉字码点过滤，繁简码点不同 → 句子匹配失败 → 字幕排到音频之外。

## 2. SPECS 声明式剪辑单

```python
SPECS = {
 'bud': {
   'source': 'IMG_4851',                       # 转写 json 名（work/IMG_4851.json）
   'title': '释迦的芽点', 'sub': '枝叶之间找答案',
   'spans': [(24.04, 59.1), (70.74, 83.98)],   # 保留的源区间（秒）
   'note': '释迦果园实拍 · 操作经验待专业复核',  # 角标免责声明（全片显示）
   'fix': {18: '那芽点和叶子是在一块的'},        # cue 级修词：{源转写cue序号: 全文替换}
   'steps': [(2, '先观察芽点位置'), ...],        # 花字步骤条 (秒, 文案)
   'broll': [('IMG_4818.MOV', 47, 10)],         # 补镜头 (文件, 源起点, 成片位置)
 },
}
```

## 3. prepare()：转写 → 字幕 + 台账

```python
def prepare():
    for key, s in SPECS.items():
        trans = json.load(open(f"work/{s['source']}.json"))['transcription']
        rows, off = [], 0
        for j, (a, b) in enumerate(s['spans']):
            for i, r in enumerate(trans, 1):
                x, y = r['offsets']['from']/1000, r['offsets']['to']/1000
                if x >= a-.001 and y <= b+.001:
                    txt = s['fix'].get(i, r['text']).strip()
                    # ≤13 字断句 × 2 行一组，按字数比例铺时间
                    chunks = []
                    for p in re.split(r'(?<=[，。？])', txt):
                        ...
                    rows.append({'start': ..., 'end': ..., 'text': ...,
                                 'source_cue': i,
                                 'status': 'PENDING_TERM' if '待核' in txt else 'TEXT_REVIEW_ONLY'})
            off += b - a
        # 产出: {key}.srt / {key}.ass(待核词 Pending 黄样式) / {key}_ledger.json / edit_packet.json
        # ⚠️ 全部 open('x') —— 重跑前必须挪走旧文件（只挪 mp4 会 FileExistsError）
```

铁律：
- cue 必须**完整落在 span 内**才收录（`x>=a and y<=b`）——跨刀口 cue 整条丢弃，调 spans 前先核对 cue 边界，否则正常内容会消失
- fix 的键是**源转写 cue 序号**（从 ledger 的 `source_cue` 查）
- 待核词进 Pending 样式，不静默出厂

## 4. render()：拼片 + 烧录 + 混音

```python
def render(key):
    s = SPECS[key]; duration = sum(b-a for a, b in s['spans'])
    dest = OUT/f'{key}_review.mp4'
    assert not dest.exists()                      # 幂等保护
    assert shutil.disk_usage(OUT).free > 5*1024**3  # 磁盘余量
    # 多输入 -ss/-t 切 span → concat
    # 顶卡 gfx：title 黄 86px / sub 白 66px / note 角标 27px（0~4.5s）
    # 字幕烧录: subtitles=filename='{ass 全路径}':fontsdir='{字体目录}'
    # 音频链:
    #   [raw]  highpass=f=65,loudnorm=I=-18:TP=-2:LRA=9,aresample=48000,asplit=2[voice][key]
    #   [music] atrim=duration, loudnorm=I=-29:TP=-9:LRA=7, afade in 1s / out {duration-3} 3s
    #   [music][key] sidechaincompress=threshold=0.018:ratio=8:attack=12:release=350[ducked]
    #   [voice][ducked] amix=inputs=2:duration=first:normalize=0, alimiter=limit=0.84[a]
    # 编码: h264_videotoolbox -b:v 18M 60fps / aac 256k / +faststart
```

⚠️ 人声必须 `asplit=2` 成两路（一路喂侧链、一路进 amix）——同一 label 喂 sidechaincompress 和 amix 会被消费两次，人声实测掉 11dB（不报错、只是「听起来小一大截」）。

## 5. verify()：出厂前三道关

1. ffprobe：1080×1920 / 帧率 / 时长与 spans 之和 ±0.05s
2. 全解码（`-v error -i dest -f null -` 无 error 输出）
3. ledger 边界断言 + 字幕 gap 检测（>250ms 断档报警）+ 三帧 contact sheet 抽帧

状态恒 `REVIEW_NOT_FINAL`——审查版不冒充成品。
