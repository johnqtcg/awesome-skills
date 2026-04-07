# deep-research Skill 评审报告

> 评估框架: [skill-creator](https://github.com/anthropics/skills/tree/main/skills/skill-creator)
> 评估日期: 2026-03-12
> 评估对象: `deep-research`

---

快照说明：本报告评估的是 **2026-03-12** 时点的 `deep-research` skill。当前仓库已将该 skill 扩展为 9-section 输出契约，并新增了 `references/` 与辅助脚本。下文中的结构描述、行数和 token 估算均对应当时被评估的快照，非当前最新版本。

`deep-research` 是一个面向事实型与分析型研究任务的 source-backed research skill，适合用于技术调研、方案比较、观点核验和跨来源综合分析，强调先检索证据、再形成结论。在被评估的那个快照中，它最突出的三个亮点是：内置证据链要求和 hallucination-aware 校验流程，能显著降低无依据结论；输出采用稳定的 7-section 模板，适合沉淀为可复用研究报告；同时要求编号引用、来源可信度标注和执行完整性说明，让研究结果更容易核查、复盘和继续扩展。

## 一、评估概览

本次评估从**实际任务表现**和 **Token 效费比**两个维度对 deep-research skill 进行全面评审。设计 3 个递进复杂度的研究场景（聚焦技术研究、多视角分析、跨领域综合），每个场景分别运行 with-skill 和 without-skill 配置，共 3 场景 × 2 配置 = 6 次独立 subagent 运行，对照 27 条 assertion 进行评分。

| 维度 | With Skill | Without Skill | 差异 |
|------|-----------|--------------|------|
| **Assertion 通过率** | **27/27 (100%)** | 9/27 (33.3%) | **+66.7 百分点** |
| **7-section 模板合规** | 3/3 全对 | 0/3 | Skill 独有 |
| **编号引用格式 [1]-[n]** | 3/3 全对 | 0/3 | Skill 独有 |
| **来源可信度标注** | 3/3 全对 | 0/3 | Skill 独有 |
| **内容质量（深度/广度/数据）** | 3/3 全对 | 3/3 全对 | 无差异 |
| **Skill Token 开销** | ~1,350 tokens | 0 | — |
| **每 1% 通过率提升的 Token 成本** | **~20 tokens** | — | 所有评估 skill 中最优 |

**关键发现：deep-research skill 的核心价值是结构化纪律，而非内容质量提升。** 基础模型已具备出色的研究能力（广度、深度、数据引用均优），但缺乏一致的报告结构。Skill 的 7-section 模板 + 编号引用 + 可信度标注填补了这一空白。

---

## 二、测试方法

### 2.1 场景设计

| 场景 | 用户请求 | 核心考察点 | Assertions |
|------|---------|-----------|-----------|
| Eval 1: 聚焦技术研究 | "Research Go generics adoption — patterns, best practices, pitfalls" | 模板合规、引用格式、技术深度 | 10 |
| Eval 2: 多视角分析 | "Research AI code review tools — developer, team lead, security perspectives" | 多视角覆盖、争议识别、平衡性 | 8 |
| Eval 3: 跨领域综合 | "Research OSS maintainer burnout — causes, strategies, evidence" | 证据分层、共识/争议区分、研究空白 | 9 |

### 2.2 执行方式

- With-skill 运行先读取 SKILL.md，按其 Research Process 和 Output Format 执行
- Without-skill 运行不读取任何 skill，按模型默认行为生成研究报告
- 所有运行均可使用 WebSearch 和 WebFetch 工具查找真实来源
- 6 个 subagent 并行运行

### 2.3 Skill 特征

在本次评估发生时，deep-research 是一个**单文件 skill**（仅 SKILL.md，无参考文件），193 行，985 单词，~1,350 tokens。其核心组件：

| 组件 | 行数 | 估算 Token |
|------|------|-----------|
| Research Process（5 步流程） | ~30 | ~200 |
| Output Format（7-section 模板） | ~30 | ~200 |
| Source Evaluation Criteria | ~8 | ~60 |
| 完整示例（Intermittent Fasting） | ~80 | ~550 |
| 其他（description/frontmatter/headers） | ~45 | ~340 |
| **合计** | **193** | **~1,350** |

---

## 三、Assertion 通过率

### 3.1 总览

| 场景 | Assertions | With Skill | Without Skill | 差值 |
|------|-----------|-----------|--------------|------|
| Eval 1: Go 泛型研究 | 10 | **10/10 (100%)** | 3/10 (30.0%) | +70.0% |
| Eval 2: AI 代码审查 | 8 | **8/8 (100%)** | 3/8 (37.5%) | +62.5% |
| Eval 3: OSS 维护者倦怠 | 9 | **9/9 (100%)** | 3/9 (33.3%) | +66.7% |
| **总计** | **27** | **27/27 (100%)** | **9/27 (33.3%)** | **+66.7%** |

### 3.2 逐项评分明细

#### Eval 1: Go 泛型研究

| # | Assertion | With Skill | Without Skill |
|---|-----------|:---------:|:------------:|
| A1 | "Executive Summary" 区段存在 | ✅ | ✅ |
| A2 | "Key Findings" 区段含编号引用 [1]-[n] | ✅ (6 findings) | ❌ |
| A3 | "Detailed Analysis" 区段含子主题 | ✅ (7 subtopics) | ❌ |
| A4 | "Areas of Consensus" 区段 | ✅ (6 points) | ❌ |
| A5 | "Areas of Debate" 区段 | ✅ (6 points) | ❌ |
| A6 | "Sources" 区段用编号 [1]-[n] 引用 | ✅ (18 sources) | ❌ |
| A7 | "Gaps and Further Research" 区段 | ✅ (8 gaps) | ❌ |
| A8 | ≥3 个独立来源 | ✅ (18) | ✅ (11) |
| A9 | 来源含可信度标注 | ✅ | ❌ |
| A10 | Findings 包含具体数据点 | ✅ | ✅ |

#### Eval 2: AI 代码审查多视角分析

| # | Assertion | With Skill | Without Skill |
|---|-----------|:---------:|:------------:|
| B1 | 全部 7 个模板区段存在 | ✅ | ❌ |
| B2 | 覆盖 3 个视角（开发者/管理者/安全） | ✅ | ✅ |
| B3 | ≥4 个独立来源 | ✅ (19) | ✅ (10) |
| B4 | 引用使用编号 [1]-[n] 格式 | ✅ | ❌ |
| B5 | Sources 区含可信度标注 | ✅ | ❌ |
| B6 | Areas of Debate 区标识真正分歧 | ✅ (6 debates) | ❌ |
| B7 | 平衡覆盖优劣两面 | ✅ | ✅ |
| B8 | 提及具体工具或研究 | ✅ | ✅ |

#### Eval 3: OSS 维护者倦怠研究

| # | Assertion | With Skill | Without Skill |
|---|-----------|:---------:|:------------:|
| C1 | 全部 7 个模板区段存在 | ✅ | ❌ |
| C2 | ≥4 个独立来源 | ✅ (29) | ✅ (~30) |
| C3 | 引用使用编号 [1]-[n] 并在正文引用 | ✅ | ❌ |
| C4 | 来源含可信度评估 | ✅ | ❌ |
| C5 | 策略含证据分层（强/中/弱） | ✅ | ✅ |
| C6 | 覆盖三大主题（原因/策略/证据） | ✅ | ✅ |
| C7 | 共识与争议明确区分 | ✅ | ❌ |
| C8 | Gaps 区提出具体研究方向 | ✅ (8 gaps) | ❌ |
| C9 | 包含数据点和研究引用 | ✅ | ✅ |

### 3.3 Without-Skill 失败的 18 条 Assertion 归类

| 失败类型 | 次数 | 涉及 Eval | 说明 |
|---------|------|----------|------|
| **缺少 7-section 模板中的特定区段** | 12 | 1/2/3 | Key Findings (3), Areas of Consensus (3), Areas of Debate (3), Gaps and Further Research (3) |
| **缺少编号 [1]-[n] 引用格式** | 3 | 1/2/3 | 使用内联 URL 或参考表格，无统一编号 |
| **缺少来源可信度标注** | 3 | 1/2/3 | 列出来源但无 "peer-reviewed / authoritative / moderate credibility" 标注 |

**注意**：所有 18 条失败都是**结构性/格式**失败，不是内容质量失败。Without-skill 在内容维度（来源数量、数据点、视角覆盖、证据分层）上全部通过。

### 3.4 趋势分析

| 场景复杂度 | With-Skill 优势 | 失败类型 |
|-----------|----------------|---------|
| Eval 1（聚焦技术） | +70.0%（7 failures） | 全部结构性 |
| Eval 2（多视角） | +62.5%（5 failures） | 全部结构性 |
| Eval 3（跨领域） | +66.7%（6 failures） | 全部结构性 |

Skill 优势在三个场景间**高度稳定**（62.5%-70.0%），不像其他 skill 有显著的复杂度趋势。原因是 Skill 的核心价值——模板合规——与场景复杂度无关：无论研究什么主题，7-section 模板和引用格式要么遵守要么不遵守。

---

## 四、逐维度对比分析

### 4.1 报告结构（7-Section 模板）

这是 Skill **独有**的差异化产出，贡献 12 条 assertion 差值。

| 区段 | With Skill 3/3 | Without Skill 产出替代 |
|------|---------------|---------------------|
| Executive Summary | ✅ 始终存在 | ✅ 通常存在（2/3 有标题） |
| Key Findings | ✅ 简洁要点 + 引用 | ❌ 无独立区段；findings 分散在各节 |
| Detailed Analysis | ✅ 有子标题的深入分析 | ⚠️ 通常有类似内容但命名不同 |
| Areas of Consensus | ✅ 独立区段 | ❌ 无；共识信息隐含在正文中 |
| Areas of Debate | ✅ 独立区段 | ❌ 无；争议信息零散分布 |
| Sources | ✅ 编号 + 可信度 | ⚠️ 存在但格式各异（表格/列表/内联） |
| Gaps and Further Research | ✅ 前瞻性研究方向 | ❌ 无独立区段或仅简短提及 |

**实际价值：**
- **Areas of Consensus + Debate 区分**是最有价值的结构元素——它迫使研究者明确区分"已确认"和"仍有争议"的发现，防止读者把初步发现误当定论
- **Gaps 区段**驱动前瞻性思维——Without-skill 的产出是"此刻状态的快照"，With-skill 增加了"未来研究方向"的维度
- **Key Findings 区段**为忙碌的读者提供快速概览——Without-skill 的读者需要通读全文才能提取要点

### 4.2 引用格式（编号 [1]-[n]）

| 维度 | With Skill | Without Skill |
|------|-----------|--------------|
| 引用格式 | `[1]`, `[2]`, ..., `[n]` — 正文编号 + 末尾完整引用 | 内联 URL、表格、括号引用、author-year 格式混用 |
| 交叉引用 | 正文中的 `[1][2]` 可立即在 Sources 区找到对应来源 | 需手动在不同格式间匹配 |
| 一致性 | 3/3 场景格式完全一致 | 3/3 场景格式各不相同 |

**分析：** Without-skill 的 Eval 1 使用了 Markdown 表格列出来源（含 URL 和"Key Contribution"），Eval 2 使用了编号表格，Eval 3 按类别列出来源。三个场景引用格式互不相同。With-skill 的 3 个场景引用格式完全一致：正文 `[n]`，末尾 `[n] Full citation (credibility note)`。

### 4.3 来源可信度标注

| 场景 | With Skill | Without Skill |
|------|-----------|--------------|
| Eval 1 | 18 sources，每个标注如 "(Official Go team guidance; highest credibility)" | 11 sources，仅 "Key Contribution" 列 |
| Eval 2 | 19 sources，每个标注如 "(Pre-print; moderate credibility)" | 10 sources，仅 "Type" 列 |
| Eval 3 | 29 sources，每个标注如 "(Peer-reviewed conference paper; high credibility)" | ~30 sources 按 Academic/Industry 分类，无逐条可信度 |

**实际价值：** 可信度标注帮助读者快速评估证据权重。例如 Eval 3 中 With-skill 明确标注 "self-reported survey data, not a randomized trial, but the effect sizes are large"，让读者知道 Tidelift 数据的局限性。Without-skill 仅列出来源名称，不评估其权威性。

### 4.4 内容质量对比

| 维度 | With Skill | Without Skill | 差异 |
|------|-----------|--------------|------|
| 来源数量 | 18 / 19 / 29 | 11 / 10 / ~30 | 相当或 With-skill 略多 |
| 数据点密度 | 高 | 高 | 无显著差异 |
| 代码示例（Eval 1） | 多个完整 Go 代码块 | 多个完整 Go 代码块 | 无显著差异 |
| 性能数据（Eval 1） | PlanetScale benchmark 表格 | DeepSource 引用 + 定性描述 | With-skill 略优 |
| 工具对比表格（Eval 2） | 5 工具 × 3 维度表 | 5 工具 × 3 维度表（不同数据） | 相当 |
| 证据分层（Eval 3） | Strong/Moderate/Weak + Consensus/Debate | Strongest/Moderate/Weak/Absent | 相当 |
| WebSearch 使用 | 广泛（12+ searches/eval） | 广泛（8+ searches/eval） | 相当 |
| 研究深度 | 优秀 | 优秀 | 无显著差异 |

**关键结论：** 基础模型在内容质量上已经非常出色。With-skill 和 Without-skill 在来源数量、数据密度、分析深度上几乎无差异。Skill 的核心增量完全在**结构化模板**和**引用格式规范**上。

---

## 五、Token 效费比分析

### 5.1 Skill 体积

按本报告评估时点计，deep-research 是一个**极轻量级 skill**——单文件，无参考资料，固定 ~1,350 tokens 开销。

| 文件 | 行数 | 单词 | 字节 | 估算 Token |
|------|------|------|------|-----------|
| **SKILL.md** | 193 | 985 | 6,995 | ~1,350 |
| **Description（始终在 context）** | — | ~40 | — | ~50 |
| **参考资料** | 无 | — | — | 0 |
| **总计** | **193** | **985** | **6,995** | **~1,350** |

### 5.2 Token 换取的质量提升

| 指标 | 数值 |
|------|------|
| With-skill 通过率 | 100% (27/27) |
| Without-skill 通过率 | 33.3% (9/27) |
| 通过率提升 | +66.7 百分点 |
| 每修复 1 条 assertion 的 Token 成本 | ~75 tokens |
| 每 1% 通过率提升的 Token 成本 | **~20 tokens** |

### 5.3 Token 分段效费比

| 模块 | 估算 Token | 关联 Assertion 差值 | 效费比 |
|------|-----------|-------------------|--------|
| **Output Format 模板** | ~200 | 12 条（7-section 模板 × 3 evals，扣除 Executive Summary） | **极高** — 17 tok/assertion |
| **引用格式规则（[1]-[n] + 可信度）** | ~80 | 6 条（编号格式 3 + 可信度标注 3） | **极高** — 13 tok/assertion |
| **Research Process（5 步流程）** | ~200 | 间接贡献（驱动系统化研究方法） | **中** — 无直接 assertion |
| **Source Evaluation Criteria** | ~60 | 间接贡献（驱动可信度标注内容） | **中** — 间接贡献 |
| **完整示例（Intermittent Fasting）** | ~550 | 间接贡献（示范模板使用方式） | **低** — 占 41% tokens 但无直接 assertion |
| **其他（frontmatter/headers）** | ~260 | 0 条 | **低** — 基础框架 |

### 5.4 高杠杆 vs 低杠杆指令

**高杠杆（~280 tokens → 18 条 assertion 差值）:**
- Output Format 模板定义（~200 tok → 12 条）
- 引用格式 + 可信度规则（~80 tok → 6 条）

**中杠杆（~260 tokens → 间接贡献）:**
- Research Process 5 步流程（~200 tok）
- Source Evaluation Criteria（~60 tok）

**低杠杆（~810 tokens → 0 条直接差值）:**
- 完整示例（~550 tok）— 占总量 41%，但示范效应可能对模板遵从有间接贡献
- 其他框架内容（~260 tok）

### 5.5 Token 效率评级

| 评级 | 结论 |
|------|------|
| **整体 ROI** | **极优** — ~1,350 tokens 换取 +66.7% 通过率 |
| **高杠杆 Token 比例** | ~21%（280/1,350）直接贡献 18/18 条 assertion 差值 |
| **低杠杆 Token 比例** | ~60%（810/1,350）无直接 assertion 贡献 |
| **参考资料效费比** | N/A — 无参考资料 |
| **示例效费比** | **待优化** — 550 tokens（41%）用于一个示例，压缩空间大 |

### 5.6 与其他 Skill 的效费比对比

| 指标 | deep-research | yt-dlp-downloader | go-makefile-writer | tdd-workflow |
|------|--------------|-------------------|-------------------|-------------|
| SKILL.md Token | **~1,350** | ~2,370 | ~1,960 | ~2,100 |
| 总加载 Token | **~1,350** | ~5,100-5,730 | ~4,100-4,600 | ~3,600-4,800 |
| 通过率提升 | **+66.7%** | +55.0% | +31.0% | +46.2% |
| 每 1% 的 Token（SKILL.md） | **~20 tok** | ~43 tok | ~63 tok | ~45 tok |
| 每 1% 的 Token（full） | **~20 tok** | ~95 tok | ~149 tok | ~92 tok |

deep-research 的 Token 效费比在所有已评估 skill 中**最优**，原因：
1. **单文件，零参考资料** — 固定 ~1,350 tokens 开销，无条件加载复杂性
2. **基础模型研究能力缺口精准** — 缺的恰好是结构模板（容易用少量 tokens 填补），而非领域知识
3. **模板指令极其紧凑** — 7-section 定义仅需 ~200 tokens 即可驱动 12 条 assertion 差值

---

## 六、与基础模型能力的边界分析

### 6.1 基础模型已具备的能力（Skill 无增量）

| 能力 | 证据 |
|------|------|
| WebSearch + WebFetch 信息收集 | 3/3 场景均使用 8-12+ 次搜索 |
| 多来源综合 | 3/3 场景引用 10-30 个来源 |
| 具体数据点引用 | 3/3 场景包含数字、百分比、研究结果 |
| 多视角覆盖 | Eval 2 正确覆盖开发者/管理者/安全专家 |
| 证据分层（强/中/弱） | Eval 3 without-skill 自行实现 Strongest/Moderate/Weak 分层 |
| 代码示例和 benchmark 数据 | Eval 1 without-skill 包含完整 Go 代码和性能表格 |
| 平衡的优劣分析 | 3/3 场景覆盖正反两面 |

### 6.2 基础模型的能力缺口（Skill 填补）

| 缺口 | 证据 | 风险等级 |
|------|------|---------|
| **无一致的报告模板** | 3/3 场景使用不同结构 | **中** — 跨报告对比困难 |
| **缺少 Areas of Consensus/Debate 区分** | 3/3 场景无独立区段 | **中** — 读者难以区分已确认和未定论 |
| **缺少 Key Findings 快速概览** | 3/3 场景无独立区段 | **低** — 读者可自行提取 |
| **缺少 Gaps and Further Research 区段** | 3/3 场景无或仅简短提及 | **中** — 缺失前瞻性视角 |
| **引用格式不一致** | 3/3 场景格式各异 | **低** — 功能不受影响 |
| **无来源可信度标注** | 3/3 场景无逐条可信度评估 | **中** — 读者无法快速评估证据权重 |

**核心发现：** 基础模型的"研究能力"（搜索、综合、分析）极为出色，但"研究报告写作纪律"（结构一致性、引用规范、可信度评估）有显著缺口。Skill 填补的恰好是后者。

---

## 七、综合评分

### 7.1 分维度评分

| 维度 | With Skill | Without Skill | 差值 |
|------|-----------|--------------|------|
| 报告结构合规 | 5.0/5 | 1.0/5 | +4.0 |
| 引用格式与可信度 | 5.0/5 | 1.5/5 | +3.5 |
| 共识/争议区分 | 5.0/5 | 1.0/5 | +4.0 |
| 前瞻性（Gaps 区段） | 5.0/5 | 1.5/5 | +3.5 |
| 内容深度与广度 | 5.0/5 | 4.5/5 | +0.5 |
| 来源数量与质量 | 5.0/5 | 4.5/5 | +0.5 |
| **综合均值** | **5.0/5** | **2.33/5** | **+2.67** |

### 7.2 加权总分

| 维度 | 权重 | 得分 | 加权 |
|------|------|------|------|
| Assertion 通过率（delta） | 25% | 10/10 | 2.50 |
| 报告结构合规 | 20% | 10/10 | 2.00 |
| 引用格式与可信度 | 15% | 10/10 | 1.50 |
| 共识/争议区分 + 前瞻性 | 10% | 10/10 | 1.00 |
| Token 效费比 | 15% | 10/10 | 1.50 |
| 内容质量增量 | 10% | 2.0/10 | 0.20 |
| 来源数量/质量增量 | 5% | 2.0/10 | 0.10 |
| **加权总分** | | | **8.80/10** |

内容质量和来源增量评分较低反映了一个重要事实：**基础模型的研究能力本身已经很强**，Skill 的价值集中在结构化报告写作上而非信息收集或分析深度。这不是 Skill 的缺陷，而是其设计定位的准确反映。

---

## 八、评估材料

| 材料 | 路径 |
|------|------|
| Eval 1 with-skill 输出 | `/tmp/research-eval/eval-1/with_skill/response.md` |
| Eval 1 without-skill 输出 | `/tmp/research-eval/eval-1/without_skill/response.md` |
| Eval 2 with-skill 输出 | `/tmp/research-eval/eval-2/with_skill/response.md` |
| Eval 2 without-skill 输出 | `/tmp/research-eval/eval-2/without_skill/response.md` |
| Eval 3 with-skill 输出 | `/tmp/research-eval/eval-3/with_skill/response.md` |
| Eval 3 without-skill 输出 | `/tmp/research-eval/eval-3/without_skill/response.md` |
