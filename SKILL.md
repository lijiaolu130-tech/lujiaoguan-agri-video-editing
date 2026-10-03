---
name: lujiaoguan-agri-video-editing
display_name: 陆教官农资自动剪辑
display_name_en: Lu's Agri Video Auto-Editing
description: 农资/种植类实拍短视频从素材导入到发布上线的完整 SOP，覆盖转写、确定性剪辑引擎、字幕规范、BGM 混音、全量体检、返修手术、抖音/视频号草稿发布。触发词：剪视频、剪辑果园素材、出成片、修字幕、错别字、气口、口吃、换音乐、BGM、爆款配乐、抖音草稿、视频号草稿、成片体检、验收。
description_zh: 农资/种植实拍素材一键变可发布竖屏短视频：ASR 转写→确定性剪辑引擎→字幕烧录→BGM 侧链混音→全量自动化体检→验收返修→草稿箱发布，内置 4 个实测脚本，参数全部取自 59 条量产成片的实战最优值。
description_en: Turn farm and agricultural filming footage into publishable vertical short videos: ASR transcription, deterministic editing engine, subtitle burning, BGM sidechain mixing, automated health checks, rework surgery, and draft-box publishing with 4 battle-tested scripts.
category: media
version: 1.0.0
author: 陆教官
agent_created: true
---

# 陆教官农资自动剪辑 skills

农资/种植实拍素材 → 可发布竖屏短视频的确定性流水线。核心原则：**引擎确定化（同输入同输出）、验收闭环化（每条必验）、发布纪律化（草稿箱优先）**。

## 全流程地图

```
素材导入 → 转写(ASR) → 确定性剪辑引擎 → 字幕烧录 → BGM 混音
   → 全量体检 → 逐条验收 → 返修手术 → 入草稿箱 → (授权后)发布
```

每一步的完整参数与代码范本在 `references/`，可复用脚本在 `scripts/`。按需读取，不要一次全载入。

## 〇、环境准备（一次配好）

- **ffmpeg 必须用 ffmpeg-full**（homebrew 精简版无 ass/subtitles/drawtext 滤镜）：
  `/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg`
- **whisper.cpp**：`/opt/homebrew/bin/whisper-cli`，模型 `~/.cache/whisper.cpp/ggml-small.bin`（快）/ `ggml-medium.bin`（准）
- **Python 分工**：渲染引擎用系统 python3（stdlib 即可）；需要 cv2/opencc/playwright/demucs 的脚本用带依赖的 venv
- **字体**：中文标题用方正启功行楷类书法体；字幕用粗黑体（assets 需自带，字幕烧录要 `fontsdir`）
- 竖屏统一 **1080×1920**，H.264，AAC 48k

## 一、素材导入与转写

1. 素材按「项目目录/源文件名.MOV」存放，一个项目一个目录：`work/`（转写+中间产物）、`out/`（成片）、`fonts/`、`bgm/`
2. 全量转写用 whisper **词级 json**（`-oj -ojf`），方言素材**必须带简体 prompt**（`--prompt "以下是普通话的句子，请使用简体中文。"`），否则间歇性整段吐繁体导致字幕对齐失败
3. 转写 json 是全流水线的单一事实源：剪辑、字幕、返修全靠它，别用 srt 当源
4. 详见 `references/engine.md`

## 二、确定性剪辑引擎（核心范式）

用 SPECS 字典声明每条视频：保留哪些源区间（spans）、修哪些词（fix）、顶卡文案（title/sub/note）、花字步骤（steps）、补镜头（broll）。`prepare()` 产字幕+台账，`render()` 拼片+烧录+混音。**同输入永远同输出**，返修只改 SPECS 重跑。

五条铁律：
1. `assert not dest.exists()`（渲染幂等保护，旧产物先挪 `_旧版_<日期>/`，**永不删除**）
2. prepare 写文件用 `'x'` 模式 → 重跑前必须把旧 srt/ass/ledger/edit_packet 全部挪走（只挪 mp4 会崩）
3. 待核词（听不清/没听准）字幕进 Pending 黄色样式，台账标 `PENDING_TERM`，**不许静默出厂**
4. 修词走 **cue 级 fix 注入**（cue 必须完整落在 span 内），不要事后改切卡产物；跨刀口的 cue 会被整条丢弃——调 spans 前先查 cue 边界
5. 渲染前断言磁盘余量 >5GB

完整范本代码（73 行可抄的引擎）：`references/engine.md`

## 三、字幕规范（硬参数）

- 卡级 ≤13 字/行 ×最多 2 行（一句话拆两卡比长卡好）；竖屏 MarginV 155
- 错字必须走**替换表**（长词优先，防「骨抗门」被「骨抗」抢先命中）；切卡后才过替换表的陷阱见 `references/subs.md`
- 逐字高亮：token 字级时间戳钉到字上；对齐失配判据与补偿算法见 `references/subs.md`
- 孤立语气词（嗯/啊/哦独立成卡）一律不烧；句首起势「嗯，」从字幕删除（声音保留不影响）
- 无证据的听不清 → 字幕写「听不清，请网友翻译」，**禁止硬猜**

## 四、BGM 配乐

- 选曲用**特征对比法**：解码前 90s → RMS 包络 → 起音密度/起伏度/亮度三指标，选实证爆款曲（播放量+亮度双高），不凭感觉
- 混音链（验证过的最优值）：
  - 人声：`highpass=f=65~90, loudnorm=I=-16~-18:TP=-1.5~-2:LRA=9~11, alimiter=limit=0.84~0.95`
  - BGM：`loudnorm=I=-29:TP=-9` → `afade in 1s / out 2.6~3s` → `sidechaincompress=threshold=0.010~0.018:ratio=8:attack=12~60:release=350~1200`
  - 混合：`amix=inputs=2:duration=first:normalize=0`（人声必须 `asplit` 成侧链路+混合路两路，同一 label 喂两个滤镜会掉 11dB）
- **归一缓存陷阱**：`loudnorm` 后的 BGM 缓存 wav（如 `bgm/norm/xxx_m28.wav`）换曲时必须先挪走，否则缓存命中继续用旧曲
- 引擎已丢失的旧成片换 BGM → **demucs 人声分离重混**路线：`htdemucs --two-stems=vocals`（CPU 约 8 秒/条）→ 人声+新 BGM 侧链混音。范本 `scripts/bgm_swap_demucs.py`
- 中间一律 PCM 48k，最后一步才编 AAC

## 五、全量体检 + 逐条验收（验收师标准）

**每一批成片必须全量体检**（`scripts/health_check.py`）：1080×1920、AAC、无削波（peak<-0.1dBFS）、响度 -16~-24 LUFS、时长合理。全部自动化，几分钟跑完。

**逐条验收**（不只看字幕，还要看画面）：
1. ASR 兜底扫描（`scripts/asr_filler_scan.py`）找孤立语气词/长停顿 → **命中≠实锤，必须抽帧亲眼读**（ASR 听到「嗯」不代表字幕烧了「嗯」）
2. 抽帧用 `fps=N` 滤镜（不要用 select 复合表达式，会抓错帧）；OCR 报错≠字幕错，疑似项 crop 放大逐帧读
3. 硬指标：开头 8s 无花絮、占位符 0、无繁体、结尾字幕覆盖到最后一句
4. 问题定位要落到「文件+时间码+原文+应改为+依据」，修完抽帧闭环

## 六、返修手术（三条路线）

| 场景 | 路线 |
|---|---|
| 改词/删语气词（引擎在） | SPECS fix 注入或替换表 → 重渲（分钟级） |
| 剪除 0.5~1s 气口/废段 | trim+concat **音视频同剪**，音频 acrossfade=d=0.05 平滑 BGM 接口；切口处必须无字幕卡（抽帧确认） |
| 引擎已删的旧成片 | demucs 人声分离 → 换 BGM 重混（字幕跟着视频 copy，不动） |

旧版永远挪 `_旧版_<日期>/` 备份；台账记录每一条 src→dst。

## 七、发布通道与风控（红线）

1. **成片只进草稿箱/私密存货，禁点公开发表**；公开发布须用户当次明确授权 + 06:00–20:00 窗口 + 2 小时间隔，每天最多 8 条
2. **抖音当日配额 ~30 条是硬顶**：首轮即使 24 条/小时仍会超；超配额后当天 90 秒/7 分钟间隔补发**全部无效**（页面照常显示成功）。对策：一天 ≤30 条，到顶停手等次日
3. **「发布成功」必须事后验证**：枚举管理页列表（无限滚动，用 innerText 累积法），拿标题前 8 字指纹与队列做差集——页面跳转成功≠服务端入库
4. 私密可见范围控件：`label[data-checked]` 包 checkbox，**点 label 本体**，断言 `data-checked==='true'` 且「公开」为 false，不通过拒绝发布（无断言会误公开）
5. 多会话共用状态文件必须做**格式规范化**（dict/list 兼容），否则互相写崩
6. 详细操作与脚本：`references/release.md`

## 八、常见翻车清单（血泪教训速查）

- ffmpeg 用了无 ass 滤镜的精简版 → 字幕滤镜直接报错
- whisper 方言素材不带简体 prompt → 繁体混入 → 字幕对齐崩
- prepare 的 'x' 模式撞 FileExistsError → 只挪了 mp4 没挪字幕文件
- span 剪除把跨刀口 cue 整条丢掉 → 正常内容消失
- 换 BGM 忘清 loudnorm 缓存 → 新曲没进片
- 模块级裸跑渲染循环无 `__main__` 守卫 → import 副作用触发渲染/断言崩溃
- 共享 state 文件格式漂移（dict vs list）→ 判重失效重复发布
- ASR 命中语气词就动刀 → 其实字幕是干净的（先抽帧再下刀）
