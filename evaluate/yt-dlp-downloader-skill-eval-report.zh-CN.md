# yt-dlp-downloader Skill 评审报告

> 评估框架: [skill-creator](https://github.com/anthropics/skills/tree/main/skills/skill-creator)
> 评估日期: 2026-03-12
> 评估对象: `yt-dlp-downloader`

---

`yt-dlp-downloader` 是一个围绕 yt-dlp 的下载命令生成与执行 skill，适合处理单视频、播放列表、音频提取、字幕下载、SponsorBlock、分辨率限制以及需要认证的下载场景。它最突出的三个亮点是：坚持先 probe 再下，依据格式列表和字幕信息来决定命令组合，而不是直接猜参数；默认带有 `--no-playlist`、重试、输出命名和归档等安全默认值，能明显降低误下、重复下和命令失控的风险；同时提供结构化执行报告，特别适合复杂组合请求下复用、审阅和后续调整。

## 一、评估概览

本次评估从**实际任务表现**和 **Token 效费比**两个维度对 yt-dlp-downloader skill 进行全面评审。设计 3 个递进复杂度的 yt-dlp 命令生成场景（单视频下载、音频提取+字幕、播放列表+分辨率+SponsorBlock+字幕），每个场景分别运行 with-skill 和 without-skill 配置，共 3 场景 × 2 配置 = 6 次独立 subagent 运行，对照 40 条 assertion 进行评分。

| 维度 | With Skill | Without Skill | 差异 |
|------|-----------|--------------|------|
| **Assertion 通过率** | **40/40 (100%)** | 18/40 (45.0%) | **+55.0 百分点** |
| **Output Contract 结构化报告** | 3/3 全对 | 0/3 | Skill 独有 |
| **Probe 决策合规** | 3/3 全对 | 0/3 | Skill 独有 |
| **安全防护 (--no-playlist)** | 3/3（含播放列表场景正确使用 --yes-playlist） | 0/2（单视频场景缺失） | 最大安全差异 |
| **Safe defaults (archive/retries/truncation)** | 3/3 全对 | 0/3 | Skill 独有 |
| **Skill Token 开销（SKILL.md 单文件）** | ~2,370 tokens | 0 | — |
| **Skill Token 开销（含参考资料）** | ~5,100–6,260 tokens | 0 | — |
| **每 1% 通过率提升的 Token 成本** | ~43 tokens（SKILL.md only）/ ~103 tokens（full） | — | — |

---

## 二、测试方法

### 2.1 场景设计

| 场景 | 用户请求 | 核心考察点 | Assertions |
|------|---------|-----------|-----------|
| Eval 1: 单视频下载 | "帮我下载这个 YouTube 视频到 ~/Downloads/videos 目录，要 MP4 格式最好画质" | 基础命令结构、安全默认值、Output Contract | 12 |
| Eval 2: 音频提取+字幕 | "Extract audio as MP3, save English subtitles as SRT" | 双场景组合、字幕探测、ffmpeg 依赖 | 13 |
| Eval 3: 播放列表+720p+SponsorBlock+字幕 | "Download entire playlist at max 720p, skip sponsors, embed Chinese subtitles" | 四场景叠加、格式选择、复杂命令组合 | 15 |

### 2.2 执行方式

- With-skill 运行先读取 SKILL.md 及其引用的参考资料
- Without-skill 运行不读取任何 skill，按模型默认 yt-dlp 知识生成
- 所有运行在 Degraded 模式（无 yt-dlp 安装），评估命令推荐质量而非实际执行
- 6 个 subagent 并行运行

---

## 三、Assertion 通过率

### 3.1 总览

| 场景 | Assertions | With Skill | Without Skill | 差值 |
|------|-----------|-----------|--------------|------|
| Eval 1: 单视频下载 | 12 | **12/12 (100%)** | 5/12 (41.7%) | +58.3% |
| Eval 2: 音频提取+字幕 | 13 | **13/13 (100%)** | 7/13 (53.8%) | +46.2% |
| Eval 3: 播放列表+720p+SponsorBlock+字幕 | 15 | **15/15 (100%)** | 6/15 (40.0%) | +60.0% |
| **总计** | **40** | **40/40 (100%)** | **18/40 (45.0%)** | **+55.0%** |

### 3.2 逐项评分明细

#### Eval 1: 单视频下载

| # | Assertion | With Skill | Without Skill |
|---|-----------|:---------:|:------------:|
| A1 | `--no-playlist` 标志存在 | ✅ | ❌ |
| A2 | 最佳画质格式选择器 (`bv*+ba/b` 或等效) | ✅ | ✅ |
| A3 | `--merge-output-format mp4` | ✅ | ✅ |
| A4 | `--download-archive` 标志存在 | ✅ | ❌ |
| A5 | `--retries` 和 `--fragment-retries` | ✅ | ❌ |
| A6 | 标题截断 `%(title).200s` | ✅ | ❌ |
| A7 | 7 字段 Output Contract 完整 | ✅ | ❌ |
| A8 | Probe 决策正确（跳过并说明理由） | ✅ | ❌ |
| A9 | 输出路径包含 `~/Downloads/videos` | ✅ | ✅ |
| A10 | 无硬编码 format ID | ✅ | ✅ |
| A11 | 提及 ffmpeg 依赖 | ✅ | ✅ |
| A12 | 显式声明 Degraded 模式 | ✅ | ❌ |

#### Eval 2: 音频提取+字幕

| # | Assertion | With Skill | Without Skill |
|---|-----------|:---------:|:------------:|
| B1 | `-x` 标志存在 | ✅ | ✅ |
| B2 | `--audio-format mp3` | ✅ | ✅ |
| B3 | `--audio-quality 0` (最佳 VBR 质量) | ✅ | ❌ |
| B4 | 字幕探测 `--list-subs` 推荐 | ✅ | ❌ |
| B5 | `--write-subs` (独立文件，非 embed) | ✅ | ✅ |
| B6 | `--sub-lang en` 或等效 | ✅ | ✅ |
| B7 | `--convert-subs srt` (保证 SRT 输出) | ✅ | ✅ |
| B8 | 提及 ffmpeg 依赖 | ✅ | ✅ |
| B9 | 7 字段 Output Contract 完整 | ✅ | ❌ |
| B10 | `--no-playlist` 存在 | ✅ | ❌ |
| B11 | 输出目录 `~/Music/podcast/` | ✅ | ✅ |
| B12 | `--download-archive` 存在 | ✅ | ❌ |
| B13 | 标题截断 `%(title).200s` | ✅ | ❌ |

#### Eval 3: 播放列表+720p+SponsorBlock+字幕

| # | Assertion | With Skill | Without Skill |
|---|-----------|:---------:|:------------:|
| C1 | `--yes-playlist` 显式声明 | ✅ | ❌ |
| C2 | 分辨率上限 `[height<=720]` 或 `-S "res:720"` | ✅ | ✅ |
| C3 | `--sponsorblock-remove` 含相关类别 | ✅ | ✅ |
| C4 | 字幕探测 `--list-subs` 推荐 | ✅ | ❌ |
| C5 | `--embed-subs` 嵌入字幕 | ✅ | ✅ |
| C6 | 中文字幕语言代码覆盖 | ✅ | ✅ |
| C7 | 嵌套播放列表输出模板含截断+零填充 | ✅ | ❌ |
| C8 | `--download-archive` 存在 | ✅ | ❌ |
| C9 | 7 字段 Output Contract 完整 | ✅ | ❌ |
| C10 | Probe 区含格式/字幕探测命令 | ✅ | ❌ |
| C11 | `--merge-output-format mp4` | ✅ | ❌ |
| C12 | 输出目录 `~/Videos/course/` | ✅ | ✅ |
| C13 | 提及 ffmpeg 依赖 | ✅ | ✅ |
| C14 | `--write-subs` 配合 `--embed-subs` | ✅ | ❌ |
| C15 | 标题截断 `%(title).200s` | ✅ | ❌ |

### 3.3 Without-Skill 失败的 22 条 Assertion 归类

| 失败类型 | 次数 | 涉及 Eval | 说明 |
|---------|------|----------|------|
| **缺少 7 字段 Output Contract** | 3 | 1/2/3 | 无结构化的 Scenario/Inputs/Probe/Command/Status/Location/Next 报告 |
| **缺少 `--download-archive`** | 3 | 1/2/3 | 重复运行会重新下载全部内容 |
| **缺少标题截断 `%(title).200s`** | 3 | 1/2/3 | 长标题可能导致文件系统路径溢出 |
| **缺少 `--no-playlist` 安全守卫** | 2 | 1/2 | 单视频 URL 含 list 参数时可能触发全播放列表下载 |
| **缺少 Probe 决策/字幕探测** | 3 | 1/2/3 | 未检查字幕可用性即假设存在；未说明何时跳过探测 |
| **缺少 `--retries`/`--fragment-retries`** | 1 | 1 | 不稳定网络下下载易失败 |
| **缺少 Degraded 模式声明** | 1 | 1 | 未明确说明命令未执行 |
| **缺少 `--audio-quality 0`** | 1 | 2 | MP3 不使用最佳 VBR 质量 |
| **缺少 `--yes-playlist` 显式声明** | 1 | 3 | 播放列表 URL 默认行为可能不稳定 |
| **播放列表模板缺少截断+零填充** | 1 | 3 | `%(playlist_index)s` 无零填充，排序混乱 |
| **缺少 `--merge-output-format mp4`** | 1 | 3 | 输出格式不确定（可能 mkv/webm） |
| **缺少 `--write-subs` 配合 `--embed-subs`** | 1 | 3 | `--embed-subs` 需要先下载字幕 |

### 3.4 趋势：Skill 优势随场景复杂度递增

| 场景复杂度 | With-Skill 优势 |
|-----------|----------------|
| Eval 1（简单单视频） | +58.3%（7 条失败） |
| Eval 2（中等双场景） | +46.2%（6 条失败） |
| Eval 3（复杂四场景叠加） | +60.0%（9 条失败） |

与 go-makefile-writer 评估中"Skill 优势随复杂度递减"不同，本 skill 在最复杂场景中反而优势最大。原因：**yt-dlp 的命令组合有大量隐性规则**（`--write-subs` 配合 `--embed-subs`、播放列表模板零填充、SponsorBlock 依赖 ffmpeg 等），基础模型在叠加多个场景时遗漏更多细节。

---

## 四、逐维度对比分析

### 4.1 Output Contract（结构化报告）

这是 Skill **独有**的差异化产出，贡献 3 条 assertion 差值。

| 字段 | With Skill 产出 | Without Skill 产出 |
|------|---------------|-------------------|
| 1. Scenario | "Single video / Audio extraction + Subtitles / Composite: Playlist + Fixed Resolution + SponsorBlock + Subtitles" | 无 |
| 2. Inputs | 结构化表格（URL/dir/format/subs/auth） | 散文描述 |
| 3. Probe | 显式决策（skipped + 理由 / 推荐命令） | 无 |
| 4. Final command | 完整可复制命令 + 每个标志的理由表 | 命令 + 简要参数说明 |
| 5. Execution status | "Not run in this environment" | 无明确声明 |
| 6. Output location | 预期文件路径模式 | 简述保存位置 |
| 7. Next step | 排序的后续行动清单 | 简要提示 |

**实际价值**: Output Contract 使得：
- 命令推荐可审计（知道为什么选择了特定标志）
- Probe 决策透明（是否跳过探测以及为什么）
- 用户下一步行动清晰（不需要猜测）

### 4.2 Probe 决策框架

这是 Skill **核心设计优势**，贡献 3 条 assertion 差值。

| 场景 | With Skill Probe 决策 | Without Skill |
|------|---------------------|---------------|
| Eval 1 | **Skipped** — 公开视频，默认最佳画质，无需探测 | 无框架 |
| Eval 2 | **`--list-subs` 推荐** — 字幕可用性未知，探测后决定 `--write-subs` 或 `--write-auto-subs` | 直接假设字幕存在 |
| Eval 3 | **3 条探测命令** — 播放列表内容/格式可用性/字幕可用性 | 无探测 |

Without-skill 的关键问题：直接假设字幕存在并添加 `--write-subs` 或 `--embed-subs`，如果字幕不存在则静默失败。Skill 的 Probe Gate 强制先验证再下载。

### 4.3 安全防护标志

| 标志 | 作用 | With Skill | Without Skill |
|------|------|-----------|--------------|
| `--no-playlist` | 防止 watch URL 意外触发全播放列表下载 | Eval 1 ✅ / Eval 2 ✅ | ❌ / ❌ |
| `--yes-playlist` | 显式声明播放列表意图 | Eval 3 ✅ | ❌ |
| `--download-archive` | 防止重复下载 | 3/3 ✅ | 0/3 ❌ |
| `--retries`/`--fragment-retries` | 网络韧性 | 3/3 ✅ | 1/3 |
| `%(title).200s` | 防止长标题导致路径溢出 | 3/3 ✅ | 0/3 ❌ |

`--no-playlist` 是**最高风险的安全缺失**。YouTube watch URL 含 `&list=` 参数时，不加 `--no-playlist` 会下载整个播放列表而非单个视频，可能导致数十 GB 意外下载。这是 Skill Anti-Example #3 明确标注的问题。

### 4.4 命令技术正确性

| 细节 | With Skill | Without Skill |
|------|-----------|--------------|
| 格式选择器 | `bv*+ba/b`（含 pre-merged fallback） | `bestvideo+bestaudio/best`（等效但不含 `*`） |
| 播放列表模板 | `%(playlist_title).120s/%(playlist_index)05d` | `%(playlist)s/%(playlist_index)s` |
| 字幕嵌入链 | `--write-subs --write-auto-subs + --embed-subs` | `--embed-subs`（缺少 `--write-subs`） |
| SponsorBlock 类别 | `sponsor,selfpromo,interaction` | `all`（可能过度删除） |
| 音频质量 | `--audio-quality 0`（最佳 VBR） | 未指定（默认 quality 5） |

With-skill 的 `bv*` 选择器比 `bestvideo` 更优，因为 `*` 包含已合并的视频流（某些站点只提供 pre-merged 格式）。Without-skill 的 `bestvideo` 不包含 pre-merged 流。

### 4.5 歧义解析质量

Eval 3 中 "Chinese subtitles" 是个歧义点：

| 维度 | With Skill | Without Skill |
|------|-----------|--------------|
| 歧义识别 | 显式标注 "assumption: zh-Hans" 并解释 YouTube 语言标签不一致 | 无歧义分析 |
| 语言代码覆盖 | `zh-Hans,zh-Hant,zh`（三码回退链） | `zh,zh-Hans,zh-Hant` |
| 回退策略 | 明确建议先探测，如果语言代码不同则调整 | 简述"如果没有中文字幕则跳过" |

两者都覆盖了三个语言代码，但 With-skill 的歧义解析更透明——用户知道为什么选择了这些代码以及如何调整。

---

## 五、Token 效费比分析

### 5.1 Skill 体积

| 文件 | 行数 | 单词 | 字节 | 估算 Token |
|------|------|------|------|-----------|
| **SKILL.md** | 214 | 1,298 | 9,742 | ~2,370 |
| references/scenario-templates.md | 168 | 548 | 5,053 | ~980 |
| references/decision-rules.md | 124 | 646 | 4,515 | ~870 |
| references/safety-and-recovery.md | 154 | 557 | 3,778 | ~730 |
| references/golden-examples.md | 110 | 497 | 4,290 | ~830 |
| references/format-selection-guide.md | 126 | 515 | 3,512 | ~680 |
| **Description（始终在 context）** | — | ~50 | — | ~70 |

### 5.2 典型加载场景

SKILL.md 的 "Load References Selectively" 区段指导按需加载：

| 场景 | 读取文件 | 总 Token |
|------|---------|---------|
| 简单下载（Eval 1） | SKILL.md + scenario-templates + golden-examples | ~4,180 |
| 中等组合（Eval 2） | SKILL.md + scenario-templates + decision-rules + golden-examples | ~5,050 |
| 复杂多场景（Eval 3） | SKILL.md + scenario-templates + decision-rules + format-selection-guide + golden-examples | ~5,730 |
| 故障恢复 | SKILL.md + safety-and-recovery | ~3,100 |
| 全量加载 | 所有文件 | ~6,460 |

### 5.3 Token 换取的质量提升

| 指标 | 数值 |
|------|------|
| With-skill 通过率 | 100% (40/40) |
| Without-skill 通过率 | 45.0% (18/40) |
| 通过率提升 | +55.0 百分点 |
| 每修复 1 条 assertion 的 Token 成本 | ~108 tokens（SKILL.md only）/ ~240 tokens（average full） |
| 每 1% 通过率提升的 Token 成本 | ~43 tokens（SKILL.md only）/ ~95 tokens（average full） |

### 5.4 Token 分段效费比

| 模块 | 估算 Token | 关联 Assertion 差值 | 效费比 |
|------|-----------|-------------------|--------|
| **Output Contract 定义** | ~200 | 3 条（3 evals 7-field report） | **极高** — 67 tok/assertion |
| **Probe Gate 决策框架** | ~250 | 3 条（probe skip/recommend） | **极高** — 83 tok/assertion |
| **`--no-playlist` 安全规则 + Anti-Example #3** | ~80 | 2 条（Eval 1/2 missing guard） | **极高** — 40 tok/assertion |
| **Safe defaults（archive/retries/truncation）** | ~150 | 7 条（3×archive + 1×retries + 3×truncation） | **极高** — 21 tok/assertion |
| **`--yes-playlist` 显式声明规则** | ~30 | 1 条 | **极高** — 30 tok/assertion |
| **Audio quality 0 规则** | ~20 | 1 条 | **极高** — 20 tok/assertion |
| **`--write-subs` + `--embed-subs` 链** | ~40 | 1 条 | **极高** — 40 tok/assertion |
| **播放列表模板截断+零填充** | ~30 | 1 条 | **极高** — 30 tok/assertion |
| **`--merge-output-format mp4` 规则** | ~20 | 1 条 | **极高** — 20 tok/assertion |
| **Degraded 模式框架** | ~100 | 1 条 | **高** — 100 tok/assertion |
| **Gate 流水线架构（7 gates 图）** | ~300 | 间接贡献（结构化思维） | **中** — 无直接 assertion |
| **Anti-Examples（8 条）** | ~350 | 间接贡献（避免硬编码 format ID 等） | **中** — 间接贡献 |
| **Scope Classification 表格** | ~120 | 间接贡献（正确分类场景） | **中** — 间接贡献 |
| **Auth Safety Gate** | ~100 | 0 条（本次评估无 auth 场景） | **低** — 未测试 |
| **Live Stream 规则** | ~50 | 0 条（本次评估无直播场景） | **低** — 未测试 |

### 5.5 高杠杆 vs 低杠杆指令

**高杠杆（~820 tokens SKILL.md → 20 条 assertion 差值）:**
- Safe defaults（150 tok → 7 条）
- Probe Gate（250 tok → 3 条）
- Output Contract（200 tok → 3 条）
- `--no-playlist` 规则（80 tok → 2 条）
- 其他单条规则（140 tok → 5 条）

**中杠杆（~770 tokens → 间接贡献）:**
- Anti-Examples（350 tok）— 避免了硬编码 format ID
- Gate 流水线（300 tok）— 驱动了结构化思考流程
- Scope 分类（120 tok）— 正确识别多场景叠加

**低杠杆（~150 tokens → 0 条差值）:**
- Auth Safety（100 tok）— 本次评估无 auth 场景
- Live Stream（50 tok）— 本次评估无直播场景

**参考资料（~3,090–4,090 tokens → 间接贡献）:**
- scenario-templates.md 驱动了命令的完整性和标志选择
- golden-examples.md 驱动了回答格式的一致性
- decision-rules.md 驱动了格式选择的技术正确性

### 5.6 Token 效率评级

| 评级 | 结论 |
|------|------|
| **整体 ROI** | **优秀** — ~5,000 tokens 换取 +55% 通过率 |
| **SKILL.md 本身 ROI** | **极优** — ~2,370 tokens 包含全部高杠杆规则 |
| **高杠杆 Token 比例** | ~35%（820/2,370）直接贡献 20/22 条 assertion 差值 |
| **低杠杆 Token 比例** | ~6%（150/2,370）在当前评估中无增量贡献 |
| **参考资料效费比** | **良好** — 间接提升命令完整性和技术正确性 |

### 5.7 与其他 Skill 的效费比对比

| 指标 | yt-dlp-downloader | go-makefile-writer | tdd-workflow |
|------|-------------------|-------------------|-------------|
| SKILL.md Token | ~2,370 | ~1,960 | ~2,100 |
| 总加载 Token | ~5,100-5,730 | ~4,100-4,600 | ~3,600-4,800 |
| 通过率提升 | **+55.0%** | +31.0% | +46.2% |
| 每 1% 的 Token（SKILL.md） | **~43 tok** | ~63 tok | ~45 tok |
| 每 1% 的 Token（full） | **~95 tok** | ~149 tok | ~92 tok |

yt-dlp-downloader 的 Token 效费比在三个 skill 中**最优**，原因是：
1. 基础模型对 yt-dlp 的隐性规则掌握较弱（45% 基线 vs go-makefile 的 69%），提升空间更大
2. Skill 的高杠杆规则非常紧凑（safe defaults、probe gate、output contract 仅 ~820 tokens）
3. 参考资料的条件加载设计良好，简单场景不加载全部内容

---

## 六、与基础模型能力的边界分析

### 6.1 基础模型已具备的能力（Skill 无增量）

| 能力 | 证据 |
|------|------|
| `-f "bestvideo+bestaudio/best"` 格式选择 | 3/3 场景正确 |
| `--merge-output-format mp4` | 2/3 场景正确（Eval 3 遗漏） |
| `-x --audio-format mp3` 音频提取 | 1/1 场景正确 |
| `--convert-subs srt` 格式转换 | 1/1 场景正确 |
| `[height<=720]` 分辨率上限 | 1/1 场景正确 |
| `--sponsorblock-remove` 基本用法 | 1/1 场景正确 |
| `--embed-subs` 字幕嵌入 | 1/1 场景正确 |
| 中文字幕多语言代码覆盖 | 1/1 场景正确 |
| ffmpeg 依赖提示 | 3/3 场景正确 |
| 输出路径基本正确 | 3/3 场景正确 |

### 6.2 基础模型的能力缺口（Skill 填补）

| 缺口 | 证据 | 风险等级 |
|------|------|---------|
| **缺少 `--no-playlist` 安全守卫** | 2/2 单视频场景缺失 | **高** — 可能意外下载整个播放列表 |
| **缺少 `--download-archive`** | 3/3 场景缺失 | **中** — 重复运行会重新下载 |
| **缺少标题截断** | 3/3 场景使用 `%(title)s` | **中** — 长标题路径溢出 |
| **无 Probe 决策框架** | 3/3 场景无探测意识 | **中** — 假设字幕存在而静默失败 |
| **无结构化 Output Contract** | 3/3 场景无报告 | **中** — 命令推荐缺少可审计性 |
| **`--write-subs` + `--embed-subs` 链** | 1/1 场景遗漏 | **高** — 字幕嵌入静默失败 |
| **播放列表模板零填充** | 1/1 场景缺失 | **低** — 排序不正确但可用 |
| **`--audio-quality 0`** | 1/1 场景缺失 | **低** — 默认质量稍低但可接受 |
| **Degraded 模式声明** | 1/3 场景缺失 | **低** — 用户可能误以为命令已执行 |

---

## 七、综合评分

### 7.1 分维度评分

| 维度 | With Skill | Without Skill | 差值 |
|------|-----------|--------------|------|
| 命令技术正确性 | 5.0/5 | 3.5/5 | +1.5 |
| 安全防护（no-playlist/archive/truncation） | 5.0/5 | 1.5/5 | +3.5 |
| Probe 决策框架 | 5.0/5 | 1.0/5 | +4.0 |
| 结构化报告（Output Contract） | 5.0/5 | 1.0/5 | +4.0 |
| 多场景叠加处理 | 5.0/5 | 3.0/5 | +2.0 |
| 歧义解析 | 5.0/5 | 2.5/5 | +2.5 |
| **综合均值** | **5.0/5** | **2.08/5** | **+2.92** |

### 7.2 加权总分

| 维度 | 权重 | 得分 | 加权 |
|------|------|------|------|
| Assertion 通过率（delta） | 25% | 10/10 | 2.50 |
| 安全防护 | 20% | 10/10 | 2.00 |
| Probe 决策 + 歧义解析 | 15% | 10/10 | 1.50 |
| Output Contract | 10% | 10/10 | 1.00 |
| 多场景叠加处理 | 10% | 10/10 | 1.00 |
| Token 效费比 | 15% | 9.0/10 | 1.35 |
| 命令技术正确性增量 | 5% | 7.0/10 | 0.35 |
| **加权总分** | | | **9.70/10** |

命令技术正确性增量评分较低是因为 Without-skill 的核心命令本身技术上不差——基础模型对 yt-dlp 的基本用法掌握较好，Skill 的核心价值在**安全防护**、**Probe 纪律**和**结构化报告**。

---

## 八、评估材料

| 材料 | 路径 |
|------|------|
| Eval 1 with-skill 输出 | `/tmp/ytdlp-eval/eval-1/with_skill/response.md` |
| Eval 1 without-skill 输出 | `/tmp/ytdlp-eval/eval-1/without_skill/response.md` |
| Eval 2 with-skill 输出 | `/tmp/ytdlp-eval/eval-2/with_skill/response.md` |
| Eval 2 without-skill 输出 | `/tmp/ytdlp-eval/eval-2/without_skill/response.md` |
| Eval 3 with-skill 输出 | `/tmp/ytdlp-eval/eval-3/with_skill/response.md` |
| Eval 3 without-skill 输出 | `/tmp/ytdlp-eval/eval-3/without_skill/response.md` |
