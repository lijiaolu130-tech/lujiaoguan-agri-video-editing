# 陆教官农资自动剪辑 Skill

农资/种植类实拍短视频的从素材导入到发布上线完整 SOP 技能——果园、农场、农资店主实拍素材一键变可发布竖屏短视频。

## 覆盖流程

```
素材导入 → ASR 转写(方言自动转简体) → 确定性剪辑引擎 → 字幕烧录 → BGM 侧链混音
   → 全量自动化体检 → 验收师标准逐条挑错 → 返修手术 → 草稿箱发布与风控
```

- **确定性引擎**：SPECS 字典声明每条视频，同输入永远同输出，返修只改配置重跑
- **字幕规范**：卡级 ≤13 字、逐字高亮、错词替换表（长词优先）、孤立语气词不烧
- **BGM 混音**：实证最优参数（-29 LUFS 侧链闪避、人声 highpass、alimiter 防削波）
- **验收闭环**：ASR 语气词兜底扫描 + 抽帧目验 + 响度/规格/削波全量体检
- **返修三路线**：cue 级 fix 重渲 / 0.5s 气口外科剪除 / demucs 人声分离换 BGM
- **发布风控**：抖音当日配额硬顶、指纹差集发布验证、私密断言防误公开

内置 4 个实测脚本（`scripts/`）：`health_check.py`、`asr_filler_scan.py`、`bgm_swap_demucs.py`、`verify_dy_list.py`。全部参数取自 59 条量产成片的实战最优值。

## 安装（WorkBuddy / OpenClaw 兼容）

**方式一：WorkBuddy 客户端**
1. 下载本仓库 zip（Code → Download ZIP）
2. 客户端左侧「技能」→ 添加技能 → 上传技能 → 拖入 zip，自动完成配置

**方式二：手动安装（OpenClaw 兼容格式）**
```bash
git clone https://github.com/lijiaolu130-tech/lujiaoguan-agri-video-editing.git ~/.workbuddy/skills/lujiaoguan-agri-video-editing
```

## 环境依赖

- ffmpeg-full（homebrew 精简版无 ass/subtitles 滤镜）：`brew install ffmpeg-full`
- whisper.cpp：`brew install whisper-cpp` + ggml-small 模型
- demucs（可选，换 BGM 用）：`pip install demucs`
- playwright（可选，发布验证用）：`pip install playwright && playwright install chromium`

## 使用

装好后直接说：

- 「用陆教官农资自动剪辑剪这批素材」
- 「全量体检」「按返修单修」
- 「推到抖音/视频号草稿箱」（默认只存草稿，不公开发表）

## 目录结构

```
├── SKILL.md              # 全流程 SOP 主文档（八章 + 翻车清单）
├── references/
│   ├── engine.md         # 73 行确定性引擎可抄范本
│   ├── subs.md           # 字幕硬参数 + FIX_WORDS + 逐字高亮算法
│   └── release.md        # 发布红线 + 配额铁律 + 验证法
├── scripts/              # 4 个实测可跑的 Python 脚本
└── assets/               # 字体说明（需自带版权字体）
```

## 声明

本技能含农艺操作经验类内容，具体农事决策请以当地农技部门指导为准。作者：陆教官。
