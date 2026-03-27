---
title: yt-dlp-downloader skill 设计解析
owner: awesome-skills maintainers
status: active
last_updated: 2026-03-27
applicable_versions: current repository version
---

# yt-dlp-downloader skill 解析

`yt-dlp-downloader` 是一套围绕 yt-dlp 下载命令生成与执行设计的探测优先下载框架。它的核心设计思想是：**高质量 yt-dlp 帮助的关键在于先判断用户到底要下载什么、哪些格式和字幕真实可用、是否会误触整条播放列表、当前环境能不能安全执行，以及在没有真正执行命令的情况下绝不能把推荐命令伪装成成功结果。** 因此它把范围分类、依赖检查、歧义消解、探测、认证安全、执行模式和执行真实性这 7 个门禁串成了一条固定流程。

## 1. 定义

`yt-dlp-downloader` 用于：

- 生成并在条件允许时执行 yt-dlp 下载命令
- 处理单视频、固定分辨率、播放列表、音频提取、字幕、认证内容、直播、SponsorBlock 等场景
- 用 probe 驱动格式与字幕决策，而不是硬猜 format ID 或语言代码
- 默认补上 archive、resume、no-overwrite、重试、输出路径截断等安全参数
- 用结构化执行报告说明命令是否真的运行、结果在哪里、下一步该怎么做

它输出的不只是最终命令，还包括：

- scenario
- inputs
- probe 决策或 probe 结果摘要
- final command
- execution status
- output location
- next step

从设计上看，它更像一个“下载命令治理框架”，而不是一个 yt-dlp 参数速查提示词。

## 2. 背景与问题

这个 skill 要解决的，不是“模型不会写 yt-dlp 命令”，而是默认的下载建议很容易出现几种高风险失真：

- 没探测就直接猜 format ID、字幕语言或分辨率选择器
- 用户明明只要单个视频，却因为 URL 带 `list=` 参数误下整条播放列表
- 命令从没执行，却被写得像已经下载成功

如果没有明确流程，常见问题通常集中在 8 类：

| 问题 | 典型后果 |
|------|----------|
| 不先做场景分类 | 播放列表、字幕、音频提取、SponsorBlock 的组合规则被混在一起 |
| 不先检查依赖 | 没有 `ffmpeg` 还推荐 merge / extract / embed 相关命令 |
| 不先解决歧义 | 不知道是整条 playlist 还是其中一个视频，不知道字幕语言要哪种 |
| 不做 probe | format ID、字幕可用性、playlist 规模全靠猜 |
| 缺少 auth 安全边界 | 把 cookies 描述成绕过付费墙或 DRM 的手段 |
| 缺少安全默认值 | 重复下载、长标题溢出、网络中断后无法续传 |
| 不诚实声明执行状态 | 用户以为已经下载成功，实际上只是推荐了一条命令 |
| 复杂组合请求无结构化报告 | 命令可以跑，但事后没人知道为什么用了这些 flag |

`yt-dlp-downloader` 的设计逻辑，就是先回答“当前是哪种下载场景、哪些参数还不清楚、哪些格式和字幕真实存在、是否需要认证、当前环境能否执行、如果不能执行应该怎样诚实降级”，再允许拼接最终命令。

## 3. 与常见替代方案的对比

先看它与几种常见做法的区别：

| 维度 | `yt-dlp-downloader` skill | 直接让模型“给我一条 yt-dlp 命令” | 凭经验手写一条常见命令 |
|------|---------------------------|-----------------------------------|--------------------------|
| 场景分类 | 强 | 弱 | 弱 |
| probe 纪律 | 强 | 弱 | 弱 |
| playlist 安全守卫 | 强 | 弱 | 弱 |
| safe defaults | 强 | 弱 | 弱 |
| auth 安全边界 | 强 | 中 | 弱 |
| honest degradation | 强 | 弱 | 弱 |
| 结构化报告 | 强 | 弱 | 弱 |
| 多场景叠加处理 | 强 | 中 | 弱 |

它的价值，不只是把命令“写得更完整”，而是把下载建议变成一个可审查、可复用、对失败更诚实的命令生成流程。

## 4. 核心设计逻辑

### 4.1 先做 范围分类

`yt-dlp-downloader` 的第一步不是直接写命令，而是先把请求归入一个 primary scenario：

- Single video
- Fixed resolution
- Playlist
- Audio extraction
- Subtitles
- Authenticated
- Live stream
- SponsorBlock

如果是复合请求，它要求先选一个 primary scenario，再叠加 secondary flags，并在 输出契约 的 Scenario 字段里明确写出组合关系。

这层设计非常关键，因为 yt-dlp 的很多错误不是单个 flag 写错，而是多个场景叠加时没有先确定主模板。例如“播放列表 + 720p + SponsorBlock + 中文字幕”不是 4 条独立需求并列罗列，而是要先从 Playlist 模板出发，再叠加分辨率、SponsorBlock、字幕相关规则。评估里最复杂场景恰恰说明了这点：skill 的优势不是基本语法，而是组合纪律。

### 4.2 依赖门禁 必须前置

在真正执行前，这个 skill 要求先检查：

- `yt-dlp --version`
- `ffmpeg -version`

并且明确指出 `ffmpeg` 在以下操作中是必需依赖：

- merge video + audio
- embed subtitles
- extract audio
- embed thumbnail
- `--merge-output-format`

它还补充了 `yt-dlp-ejs + JS runtime` 的 YouTube 支持要求，用来解释一些常见 extraction error。

这层设计很成熟，因为很多“命令看起来没问题”的失败，本质上不是参数问题，而是依赖环境问题。如果没有这道门，模型很容易把失败归因到 URL 或格式，而不是先确认依赖链是否完整。

### 4.3 歧义消解 Gate 要这么严格

`yt-dlp-downloader` 明确规定遇到以下情况必须 STOP and ASK：

- 没给 URL
- 批量或播放列表下载时输出目录不明确
- “good quality” 但分辨率偏好不清
- playlist URL 但用户没说是整条还是单个视频
- 需要字幕但没说语言
- 给了多个 URL 但没说是批量还是分别处理

这层设计非常重要，因为下载类任务看似简单，但“少问一句”经常会让命令完全跑偏。最典型的例子就是带 `list=` 的 YouTube watch URL：如果不先澄清，单视频意图会直接变成整条 playlist 下载。

### 4.4 Probe Gate 是整个 skill 的核心

这个 skill 最突出的设计，就是 Probe Gate。它明确规定：

- 想要特定分辨率 / codec / format 时先 `yt-dlp -F`
- 想知道字幕语言是否存在时先 `yt-dlp --list-subs`
- playlist 规模不清或过大时先 `--flat-playlist`
- auth / redirect 不确定时先 `--simulate --skip-download`

并且只在“公开、单视频、用户接受默认最佳质量”的简单场景下才允许跳过 probe。

这层设计是整个 skill 的方法论核心。评估里最稳定的 skill-only 差异之一就是 Probe decision compliance：with-skill `3/3`，without-skill `0/3`。这说明 skill 的真正增量不是“知道有哪些 yt-dlp 参数”，而是“知道什么时候不能靠经验猜参数”。

### 4.5 `--no-playlist` 是安全规则，而 `--yes-playlist` 是显式意图声明

`yt-dlp-downloader` 对 playlist 行为做了两层约束：

- 单视频 watch URL 默认加 `--no-playlist`，这是明确写进 `安全规则` 的安全守卫
- 用户明确要整条 playlist 时显式加 `--yes-playlist`，这是与之配套的显式意图声明规则

这层设计的意义非常直接，因为这是评估里风险最高的基础模型缺口之一。YouTube 的 watch URL 经常带 `&list=` 参数，不加 `--no-playlist` 时很容易误下载整个播放列表，造成大量时间、带宽和存储浪费。

也正因此，`--no-playlist` 不只是“一个推荐 flag”，而是 skill 的 Safety Rule；而 `--yes-playlist` 的作用，是在用户确实要整条播放列表时把这个意图显式写出来，避免默认行为含糊不清。

### 4.6 safe defaults 会被固定成一组默认 contract

这个 skill 的默认参数不是零散建议，而是一组固定默认值：

- `--download-archive`
- `--continue`
- `--no-overwrites`
- `--retries 10 --fragment-retries 10`
- `-o "<dir>/%(title).200s [%(id)s].%(ext)s"`

在 batch、troubleshooting、unstable network 场景下，它还建议把日志通过 `tee` 留存。

这层设计非常成熟，因为 yt-dlp 下载问题很多都不是“命令不能跑”，而是：

- 重跑时全部重复下载
- 网络中断后不能续传
- 长标题导致路径问题
- 批量任务失败后没有日志可追

评估里 `archive / retries / truncation` 是最稳定的 skill-only 优势之一，说明这些默认值带来的不是语法正确性，而是执行韧性。

### 4.7 Auth Safety Gate 要把“能做”和“该不该做”分开

这个 skill 支持 cookies 和浏览器会话，但同时给出非常明确的边界：

- cookies 只能用于用户有权访问的内容
- 优先 `--cookies-from-browser`
- 绝不让用户把 cookies 内容粘贴到对话里
- 绝不把 cookies 描述成绕过 paywall / DRM / geo restriction 的手段

这层设计很关键，因为 yt-dlp 相关帮助天然容易滑向“技术上可行但不该帮助”的区域。`yt-dlp-downloader` 的做法是保留合法认证访问场景，同时把越界用途在规则层直接封死。

### 4.8 Execution 模式 和 Honest Degradation 要单独成层

`yt-dlp-downloader` 会根据环境自动进入：

- Full
- Degraded
- Blocked

并明确规定：

- Full：依赖齐全且命令真实执行，才能报告成功 / 失败细节
- Degraded：只提供推荐命令和假设，不能报告成功、文件大小、格式可用性
- Blocked：`yt-dlp` 未安装，或请求涉及 DRM / 未授权访问，必须说明 blocker；其他缺少的必需依赖（如当前请求需要 `ffmpeg`）则应作为该请求的具体阻塞项单独说明，并给出安装指引

这层设计特别重要，因为下载类帮助最容易出现一种“伪执行感”：模型给出了一条完整命令，用户就误以为事情已经完成。这个 skill 强制把“命令推荐”和“命令已执行”分开，避免了这种误导。

### 4.9 执行真实性门禁 是最后的诚实底线

这个 skill 明确要求：

- 真执行了，才报告 destination、success/failure、stderr/stdout 摘要
- 没执行，就必须写 `Not run in this environment`

这层设计非常关键，因为很多助手在 shell 不可用时仍会写出像“downloaded successfully”这样的句子。评估里 without-skill 就会漏掉 Degraded mode declaration，而 with-skill 会把“没运行”明确写成输出 contract 的一部分。这种设计让用户能区分：

- 命令本身看起来是否合理
- 命令是否真的已经跑过

### 4.10 作为另一条主轴的输出契约

`yt-dlp-downloader` 强制每次响应都带 7 个字段：

1. Scenario
2. Inputs
3. Probe
4. Final command
5. Execution status
6. Output location
7. Next step

这层设计的价值，不只是“回答更整齐”，而是把一条复杂下载命令拆成可审计的几部分：

- 这个命令是按什么场景模板选出来的
- 哪些输入是用户明确给的，哪些是假设
- probe 是跳过了还是执行了，为什么
- 如果失败，下一步应改哪里

评估里 输出契约 是明确的 skill-only 差异：with-skill `3/3`，without-skill `0/3`。

### 4.11 多场景叠加处理是高价值设计

yt-dlp 的真实使用里，用户很少只提一个条件，常见的是：

- playlist + resolution cap
- subtitles + embed
- audio extraction + subtitle save
- sponsorblock + mp4 output

`yt-dlp-downloader` 没把这些场景做成平铺罗列的 flag 清单，而是强调：

- 先定主场景模板
- 再叠加 secondary scenario 的规则
- 在报告里写清 composite relationship

这让复杂请求仍然有稳定结构，而不是在最后一步凭印象拼 flag。

### 4.12 真正的增量在流程治理，而不在基础命令语法

评估已经说明，baseline 模型本来就会不少 yt-dlp 基本用法，比如：

- `bestvideo+bestaudio/best`
- `--audio-format mp3`
- `[height<=720]`
- `--sponsorblock-remove`
- `--embed-subs`

真正的差距在于：

- 缺少 `--no-playlist`
- 缺少 `--download-archive`
- 缺少标题截断
- 没有 Probe framework
- 没有 输出契约
- 不知道 `--write-subs` 要和 `--embed-subs` 配合
- 不会诚实声明 Degraded mode

这说明 `yt-dlp-downloader` 的核心价值不是“让模型第一次学会 yt-dlp”，而是“让模型在真实下载任务里少踩高风险坑，并且把命令建议变成可解释、可追责、可复用的下载方案”。

## 5. 这个设计解决了哪些具体问题

结合当前 `SKILL.md`、关键 references 和评估报告，可以把它解决的问题归纳为：

| 问题类型 | skill 中的对应设计 | 实际效果 |
|----------|-------------------|----------|
| 场景混杂，模板选错 | 范围分类 | 命令结构更稳定 |
| 依赖缺失导致命令失效 | 依赖门禁 | 失败定位更准确 |
| 用户意图含糊 | 歧义消解 Gate | 误下载更少 |
| 没探测就猜格式或字幕 | Probe Gate | 参数选择更可靠 |
| 单视频误触整条 playlist | `--no-playlist` / `--yes-playlist` 规则 | 安全性更高 |
| 重跑、断点、路径问题 | Safe defaults | 执行韧性更强 |
| cookies 使用越界 | Auth Safety Gate | 安全边界更清晰 |
| 命令没跑却像跑过一样 | 执行真实性 + Honest Degradation | 报告更诚实 |

## 6. 主要亮点

### 6.1 Probe-first 是整个 skill 最有辨识度的设计

它把“先看可用格式和字幕，再决定命令”变成硬流程，而不是经验建议。

### 6.2 playlist 安全守卫非常实用

`--no-playlist` / `--yes-playlist` 把 yt-dlp 最常见、代价最高的误操作前置拦住了。

### 6.3 safe defaults 不是装饰，而是执行可靠性的核心

archive、resume、retries、title truncation 共同解决了重复下载、网络波动、路径溢出等现实问题。

### 6.4 honest degradation 让命令推荐和真实执行严格分离

这让用户不会把“建议命令”误解成“已经下载完成”。

### 6.5 输出契约 让复杂命令变得可审查

尤其在多场景叠加时，Scenario / Probe / Next step 这些字段能显著提高可解释性。

### 6.6 当前版本的真正增量，在安全和流程，而不在基础语法

评估已经说明：baseline 的基础命令语法并不差；真正的提升来自 Probe 纪律、安全默认值、playlist guard、结构化报告和执行诚实度。这说明 `yt-dlp-downloader` 的核心价值是 command governance，而不是参数百科。

## 7. 什么时候适合用，什么时候不该硬用

| 场景 | 是否适合 | 原因 |
|------|----------|------|
| 单视频、播放列表、音频提取、字幕下载 | 非常适合 | 核心场景 |
| 复合请求（如 playlist + 720p + subtitles + SponsorBlock） | 非常适合 | 模板叠加能力强 |
| 需要认证但用户有合法访问权限 | 适合 | 有明确 auth safety 规则 |
| 没有 shell 或没装 yt-dlp 的环境 | 适合 | 可走 Degraded / Blocked |
| 想绕过 DRM、paywall、未授权访问限制 | 不适合 | 明确被 安全规则 拦截 |

## 8. 结论

`yt-dlp-downloader` 的真正亮点，不是它能把 yt-dlp 命令写得更长，而是它把下载帮助中最容易失真的部分系统化了：先分类场景，再检查依赖，再消解歧义，再用 probe 验证格式和字幕可用性，然后用 safe defaults、playlist guard、auth safety 和 honest degradation 去约束最终命令与执行报告。

从设计上看，这个 skill 很清楚地体现了一条原则：**高质量的 yt-dlp 帮助，关键不在于知道更多 flag，而在于知道什么时候必须先探测、什么时候必须先停下来问、什么时候必须拒绝越界请求，以及在没实际执行下载时绝不能把推荐命令写成已完成结果。** 这也是它特别适合真实下载、批量下载和复杂组合下载场景的原因。

## 9. 文档维护

当以下内容发生变化时，这份文档应该同步更新：

- `skills/yt-dlp-downloader/SKILL.md` 中的 7 个 Gate、Defaults、安全规则、Honest Degradation、输出契约 或 selective loading 规则发生变化。
- `skills/yt-dlp-downloader/references/scenario-templates.md`、`decision-rules.md`、`format-selection-guide.md`、`safety-and-recovery.md`、`anti-examples.md` 或 `golden-examples.md` 中的关键规则发生变化。
- `evaluate/yt-dlp-downloader-skill-eval-report.md` 或 `evaluate/yt-dlp-downloader-skill-eval-report.zh-CN.md` 中支撑本文判断的核心结果发生变化。

建议按季度复查一次；如果 `yt-dlp-downloader` 的 probe 规则、安全默认值、playlist guard 或 execution contract 有明显重构，则应立即复查。

## 10. 相关阅读

- `skills/yt-dlp-downloader/SKILL.md`
- `skills/yt-dlp-downloader/references/scenario-templates.md`
- `skills/yt-dlp-downloader/references/decision-rules.md`
- `skills/yt-dlp-downloader/references/format-selection-guide.md`
- `skills/yt-dlp-downloader/references/safety-and-recovery.md`
- `skills/yt-dlp-downloader/references/anti-examples.md`
- `skills/yt-dlp-downloader/references/golden-examples.md`
- `evaluate/yt-dlp-downloader-skill-eval-report.md`
- `evaluate/yt-dlp-downloader-skill-eval-report.zh-CN.md`
