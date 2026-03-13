# google-search Skill 评审报告

> 评估框架: [skill-creator](https://github.com/anthropics/skills/tree/main/skills/skill-creator)
> 评估日期: 2026-03-12
> 评估对象: `google-search`

---

`google-search` 是一个把“帮我搜一下”转成可验证搜索流程的 research/search skill，适合用于事实查询、错误调试、官方文档检索、技术比较以及需要来源支撑的公开信息搜集。它最突出的三个亮点是：先做问题分类、证据链定义和模式选择，把搜索从“找链接”提升为“找结论所需证据”；输出里会附带可信度、来源层级、预算状态和可复用查询，让搜索过程本身可复盘、可继续；同时强调执行完整性和降级声明，能明确区分“已验证结论”和“证据不足的部分结果”。

## 一、评估概览

本次评估从**实际任务表现**和 **Token 效费比**两个维度对 google-search skill 进行全面评审。设计 3 个递进复杂度的搜索场景（Quick 模式事实查询、Standard 模式错误调试、Deep 模式框架对比），每个场景分别运行 with-skill 和 without-skill 配置，共 3 场景 × 2 配置 = 6 次独立 subagent 运行，对照 27 条 assertion 进行评分。

| 维度 | With Skill | Without Skill | 差异 |
|------|-----------|--------------|------|
| **Assertion 通过率** | **27/27 (100%)** | 7/27 (25.9%) | **+74.1 百分点** |
| **Output Contract 8 字段全满** | 3/3 全对 | 0/3 | Skill 独有 |
| **Confidence + Source-tier 标签** | 3/3 全对 | 0/3 | Skill 独有 |
| **可复用搜索查询** | 3/3 全对 | 0/3 | Skill 独有 |
| **证据链状态追踪** | 3/3 全对 | 0/3 | Skill 独有 |
| **内容质量（答案正确性/深度）** | 3/3 全对 | 3/3 全对 | 无差异 |
| **Skill Token 开销（SKILL.md 单文件）** | ~3,100 tokens | 0 | — |
| **Skill Token 开销（含条件加载参考资料）** | ~6,400–7,800 tokens | 0 | — |
| **每 1% 通过率提升的 Token 成本** | ~42 tok（SKILL.md）/ ~99 tok（full） | — | — |

**关键发现：google-search skill 的核心价值是搜索纪律和报告规范，而非搜索内容质量。** 基础模型已具备出色的搜索和信息综合能力（答案正确性、来源覆盖、代码示例质量均优），但完全缺乏搜索过程的元数据记录（模式选择、预算控制、证据链追踪、降级声明、可信度标签、可复用查询）。Skill 填补的正是这一"搜索操作纪律"的空白。

---

## 二、测试方法

### 2.1 场景设计

| 场景 | 用户请求 | 预期模式 | Assertions |
|------|---------|---------|-----------|
| Eval 1: 事实查询 | "Go database/sql 包 MaxOpenConns 和 MaxIdleConns 默认值" | Quick | 9 |
| Eval 2: 错误调试 | "gRPC context deadline exceeded — works locally, fails in production" | Standard | 9 |
| Eval 3: 框架对比 | "Compare Gin/Echo/Fiber performance for high-traffic REST API 2026" | Deep | 9 |

### 2.2 执行方式

- With-skill 运行先读取 SKILL.md 及相关参考资料（query-patterns、programmer-search-patterns、source-evaluation 等）
- Without-skill 运行不读取任何 skill，按模型默认行为搜索
- 所有运行均可使用 WebSearch 和 WebFetch 工具
- 6 个 subagent 并行运行（with-skill 使用默认模型，without-skill 使用 fast 模型）

### 2.3 Skill 特征

google-search 是一个**多文件 skill**（1 个 SKILL.md + 6 个参考文件），条件加载设计。

| 文件 | 单词数 | 估算 Token | 加载条件 |
|------|--------|-----------|---------|
| **SKILL.md** | 2,085 | ~3,100 | 始终加载 |
| **references/query-patterns.md** | 1,191 | ~1,800 | 始终加载（查询构建） |
| **references/programmer-search-patterns.md** | 1,031 | ~1,500 | 程序员搜索类 |
| **references/source-evaluation.md** | 911 | ~1,400 | 来源评估/冲突处理 |
| **references/ai-search-and-termination.md** | 549 | ~800 | 终止/升级决策 |
| **references/high-conflict-topics.md** | 947 | ~1,400 | 高冲突主题 |
| **references/chinese-search-ecosystem.md** | 279 | ~400 | 中文/中国话题 |
| **SKILL.md 描述（always in context）** | ~60 | ~80 | 始终 |

**各场景实际加载量**：

| 场景 | 加载文件 | 估算 Token |
|------|---------|-----------|
| Eval 1 (Quick, programmer) | SKILL.md + query-patterns + programmer-search | ~6,400 |
| Eval 2 (Standard, programmer) | SKILL.md + query-patterns + programmer-search + source-evaluation | ~7,800 |
| Eval 3 (Deep, comparison) | SKILL.md + query-patterns + programmer-search + source-evaluation | ~7,800 |
| **平均** | | **~7,300** |

---

## 三、Assertion 通过率

### 3.1 总览

| 场景 | Assertions | With Skill | Without Skill | 差值 |
|------|-----------|-----------|--------------|------|
| Eval 1: 事实查询（Quick） | 9 | **9/9 (100%)** | 3/9 (33.3%) | +66.7% |
| Eval 2: 错误调试（Standard） | 9 | **9/9 (100%)** | 2/9 (22.2%) | +77.8% |
| Eval 3: 框架对比（Deep） | 9 | **9/9 (100%)** | 2/9 (22.2%) | +77.8% |
| **总计** | **27** | **27/27 (100%)** | **7/27 (25.9%)** | **+74.1%** |

### 3.2 逐项评分明细

#### Eval 1: Go database/sql 默认池大小（Quick 模式）

| # | Assertion | With Skill | Without Skill |
|---|-----------|:---------:|:------------:|
| A1 | 输出含 execution mode 标签 | ✅ "Quick" | ❌ |
| A2 | 输出含 degradation level | ✅ "Full" | ❌ |
| A3 | 结论直接回答问题 | ✅ | ✅ |
| A4 | 输出含可复用查询（≥2） | ✅（5 条） | ❌ |
| A5 | 至少 1 条查询用 `site:go.dev` | ✅ | ❌ |
| A6 | 结论引用官方来源 | ✅ go.dev, pkg.go.dev | ✅ go.dev, pkg.go.dev |
| A7 | 输出含证据链状态 | ✅ 显式表格 | ❌ |
| A8 | 结论含具体数值 | ✅ MaxOpenConns=0, MaxIdleConns=2 | ✅ |
| A9 | 关键数字含 confidence + source-tier 标签 | ✅ "High" + "Official" | ❌ |

#### Eval 2: gRPC context deadline exceeded（Standard 模式）

| # | Assertion | With Skill | Without Skill |
|---|-----------|:---------:|:------------:|
| B1 | 输出含 execution mode 标签 | ✅ "Standard" | ❌ |
| B2 | 输出含 degradation level | ✅ "Full" | ❌ |
| B3 | 结论含多个原因 | ✅（5 个结构化原因） | ✅（6 个原因） |
| B4 | 输出含可复用查询（≥3） | ✅（5 条） | ❌ |
| B5 | 至少 1 条查询定向 SO 或 GitHub | ✅ `site:github.com/grpc/grpc-go` | ❌ |
| B6 | 至少 1 条查询用引号精确匹配错误信息 | ✅ `"context deadline exceeded"` | ❌ |
| B7 | 来源含交叉验证（≥2 独立源） | ✅（6 个独立来源） | ✅（6 个参考来源） |
| B8 | 输出含证据链状态 | ✅ 显式表格 | ❌ |
| B9 | 输出含 source assessment | ✅ 可信度/时效/缺口/冲突/置信度论证 | ❌ |

#### Eval 3: Go HTTP 框架对比（Deep 模式）

| # | Assertion | With Skill | Without Skill |
|---|-----------|:---------:|:------------:|
| C1 | 输出含 execution mode 标签（Deep） | ✅ "Deep" | ❌ |
| C2 | 输出含 degradation level | ✅ "Partial"（诚实降级） | ❌ |
| C3 | 结论含推荐建议 | ✅ 决策树 + 框架定位 | ✅ 决策矩阵 + 推荐 |
| C4 | 输出含可复用查询（≥3） | ✅（5 条含 gap-closing） | ❌ |
| C5 | 关键数字含 confidence + source-tier 标签 | ✅（14 个数字全标注） | ❌ |
| C6 | ≥3 个独立来源 | ✅（5+ 来源含详细评估） | ✅（16 来源） |
| C7 | 来源含可信度评估 | ✅ Source Comparison Table（含 tier/credibility/gaps/recency/bias） | ❌ |
| C8 | 输出含证据链状态 | ✅ 显式链状态表 | ❌ |
| C9 | 对比覆盖 ≥3 框架含具体数据 | ✅ Gin/Echo/Fiber + RPS + 延迟 + 星数 | ✅ |

### 3.3 Without-Skill 失败的 20 条 Assertion 归类

| 失败类型 | 次数 | 说明 |
|---------|------|------|
| **缺少 Output Contract 元数据字段** | 6 | execution mode (3) + degradation level (3) |
| **缺少可复用搜索查询** | 3 | 3/3 场景均无 reusable queries 区段 |
| **缺少证据链状态追踪** | 3 | 3/3 场景均无 evidence chain status |
| **缺少 confidence + source-tier 标签** | 3 | 关键数字无双标签 |
| **缺少 source assessment** | 3 | 无可信度/bias/recency 评估 |
| **缺少搜索策略展示** | 2 | 无 site: 精确查询、无引号匹配 |

**注意**：与 deep-research 评估类似，所有 20 条失败都是**搜索纪律/报告格式**失败，不是内容质量失败。Without-skill 在答案正确性、来源覆盖、代码示例方面全部通过。

### 3.4 与 deep-research skill 的对比

| 指标 | google-search | deep-research |
|------|--------------|---------------|
| With-skill 通过率 | 100% | 100% |
| Without-skill 通过率 | **25.9%** | 33.3% |
| 差值 | **+74.1%** | +66.7% |
| 失败类型 | 搜索纪律 + 报告格式 | 报告格式 |

google-search 的 assertion delta 更大，因为它要求的不仅是报告模板（deep-research 的 7-section），还包括**搜索过程的元数据**（模式、预算、证据链、降级级别、可复用查询、精确查询策略）。基础模型连这些概念都不产出。

---

## 四、逐维度对比分析

### 4.1 Output Contract（8 字段）

| 字段 | With Skill 3/3 | Without Skill 产出 |
|------|---------------|-------------------|
| 1. Execution mode | ✅ Quick/Standard/Deep | ❌ 无模式概念 |
| 2. Degradation level | ✅ Full/Partial/Blocked | ❌ 无降级概念 |
| 3. Conclusion summary | ✅ | ✅（等效） |
| 4. Evidence chain status | ✅ 显式表格 | ❌ 无追踪 |
| 5. Key evidence | ✅ 结构化表格含贡献说明 | ⚠️ 有来源列表但无结构化评估 |
| 6. Source assessment | ✅ 可信度/偏见/时效/缺口/冲突 | ❌ 无评估 |
| 7. Key numbers + 双标签 | ✅ confidence + source-tier | ❌ 有数字但无标签 |
| 8. Reusable queries | ✅ 3-5 条含精确/扩展/填补策略 | ❌ 无 |

**实际价值**：
- **Degradation level** 在 Eval 3 中展现了最高价值——With-skill 诚实声明为 "Partial"（TechEmpower 数据来自第三方解读、无命名公司生产案例），而 Without-skill 直接给出结论不标注不确定性
- **Evidence chain status** 让读者能追踪 "哪些证据已满足、哪些缺失"，避免把片面数据当完整结论
- **Reusable queries** 赋予读者"继续搜索"的能力——5 条精心设计的 Google 查询比一个答案更有持久价值

### 4.2 搜索策略纪律

| 维度 | With Skill | Without Skill |
|------|-----------|--------------|
| 查询构建策略 | Primary + Precision + Expansion 三变体 | 直接搜索，无显式策略 |
| `site:` 域限定 | ✅ site:go.dev, site:github.com/grpc/grpc-go | 偶尔出现但非系统性 |
| 引号精确匹配 | ✅ `"context deadline exceeded"` | 未展示 |
| 查询预算控制 | ✅ Quick 2 / Standard 5 / Deep 8 | 无预算概念 |
| 查询历史记录 | ✅ Gate Execution Log | ❌ 无记录 |
| 搜索后续策略 | ✅ gap-closing 查询 | ❌ 无 |

### 4.3 Confidence + Source-Tier 标签

Eval 3 的 With-skill 输出为 14 个关键数字全部标注了双标签：

```
| Fiber real-world RPS | ~36,000 | May 2024 | Medium | Primary (independent benchmark) |
| Fiber JSON RPS (TechEmpower R23) | ~735,000 | March 2025 | Low | Third-party interpretation of Official |
```

区分了 "Medium confidence from Primary source" 和 "Low confidence from Third-party interpretation"，让读者知道 TechEmpower 数据经过第三方转述因此可信度降级。Without-skill 的 Eval 3 引用了 16 个来源和大量数字，但**没有任何数字标注可信度或来源层级**。

### 4.4 诚实降级（Honest Degradation）

Eval 3 的 With-skill 输出最能展现此机制：

> **Degradation Level: Partial** — Strong benchmark data and ecosystem analysis available. However: TechEmpower Round 23 Go-specific per-framework numbers could not be directly verified from TechEmpower's own site... Large-scale production experience reports... were not found from named companies with disclosed architectures.

这段降级声明明确告知读者两个具体不确定性，避免读者把对比结论当作完全确认的事实。Without-skill 的 Eval 3 同样没找到命名公司案例，但**没有声明这一局限**。

### 4.5 内容质量对比

| 维度 | With Skill | Without Skill | 差异 |
|------|-----------|--------------|------|
| 答案正确性 | 3/3 正确 | 3/3 正确 | 无差异 |
| 来源数量 | 2 / 6 / 5 | 4 / 6 / 16 | Without-skill 略多（Eval 3） |
| 代码示例 | 优秀（Eval 2 含 6 个代码块） | 优秀（Eval 2 含 5 个代码块） | 无显著差异 |
| 调试步骤（Eval 2） | 6 步结构化调试流程 | 5 步调试流程 | 相当 |
| 框架对比表格（Eval 3） | Source Comparison Table + Decision Tree | Decision Matrix + Star 评分 | 各有优势 |
| 生产建议 | 优秀 | 优秀 | 无显著差异 |

**关键结论：** 与 deep-research skill 的评估发现一致——基础模型在内容维度已经非常出色，Skill 的增量完全在**搜索纪律和报告元数据**上。

---

## 五、Token 效费比分析

### 5.1 Skill 体积

| 文件 | 估算 Token | 加载条件 |
|------|-----------|---------|
| SKILL.md | ~3,100 | 始终 |
| query-patterns.md | ~1,800 | 始终 |
| programmer-search-patterns.md | ~1,500 | 程序员搜索 |
| source-evaluation.md | ~1,400 | 来源评估 |
| ai-search-and-termination.md | ~800 | 终止决策 |
| high-conflict-topics.md | ~1,400 | 高冲突 |
| chinese-search-ecosystem.md | ~400 | 中文话题 |
| **最大加载量** | **~10,400** | 全部加载 |
| **典型加载量（程序员搜索）** | **~7,800** | SKILL + query + programmer + source-eval |
| **最小加载量（非程序员 Quick）** | **~4,900** | SKILL + query |

### 5.2 Token 换取的质量提升

| 指标 | 数值 |
|------|------|
| With-skill 通过率 | 100% (27/27) |
| Without-skill 通过率 | 25.9% (7/27) |
| 通过率提升 | +74.1 百分点 |
| 每修复 1 条 assertion 的 Token 成本（SKILL.md） | ~155 tok |
| 每修复 1 条 assertion 的 Token 成本（典型加载） | ~390 tok |
| 每 1% 通过率提升的 Token 成本（SKILL.md） | **~42 tok** |
| 每 1% 通过率提升的 Token 成本（典型加载） | **~105 tok** |

### 5.3 Token 分段效费比

| 模块 | 估算 Token | 关联 Assertion 差值 | 效费比 |
|------|-----------|-------------------|--------|
| **Output Contract（SKILL.md）** | ~300 | 6 条（mode 3 + degradation 3） | **极高** — 50 tok/assertion |
| **Confidence + Source-tier 规则** | ~200 | 3 条 | **极高** — 67 tok/assertion |
| **Reusable Queries 要求** | ~100 | 3 条 | **极高** — 33 tok/assertion |
| **Evidence Chain Gate（Gate 3）** | ~300 | 3 条 | **高** — 100 tok/assertion |
| **Source Assessment 要求** | ~150 | 3 条 | **高** — 50 tok/assertion |
| **query-patterns.md** | ~1,800 | 2 条（site: + 引号策略） | **中** — 900 tok/assertion |
| **programmer-search-patterns.md** | ~1,500 | 间接贡献（搜索质量） | **中** — 无直接 assertion |
| **source-evaluation.md** | ~1,400 | 间接贡献（评估质量） | **中** — 无直接 assertion |
| **Worked Examples（SKILL.md）** | ~500 | 0 条直接 | **低** |
| **Anti-Examples（SKILL.md）** | ~300 | 0 条直接 | **低** |
| **其他 Gates（1,2,4,5,6,7,8）** | ~450 | 间接贡献 | **中** |

### 5.4 高杠杆 vs 低杠杆指令

**高杠杆（~1,050 tokens → 18 条 assertion 差值）：**
- Output Contract 8 字段定义（~300 tok → 6 条）
- Confidence + Source-tier 双标签规则（~200 tok → 3 条）
- Reusable Queries 要求（~100 tok → 3 条）
- Evidence Chain Gate（~300 tok → 3 条）
- Source Assessment 要求（~150 tok → 3 条）

**中杠杆（~5,150 tokens → 2 条直接 + 间接贡献）：**
- query-patterns.md（~1,800 tok → 2 条 + 搜索质量间接）
- programmer-search-patterns.md（~1,500 tok → 间接）
- source-evaluation.md（~1,400 tok → 间接）
- 其他 Gates（~450 tok → 间接）

**低杠杆（~800 tokens → 0 条直接差值）：**
- Worked Examples（~500 tok）
- Anti-Examples（~300 tok）

### 5.5 与其他 Skill 的效费比对比

| 指标 | google-search | deep-research | yt-dlp-downloader | tdd-workflow | go-makefile-writer |
|------|--------------|---------------|-------------------|-------------|-------------------|
| SKILL.md Token | ~3,100 | ~1,350 | ~2,370 | ~2,100 | ~1,960 |
| 典型加载 Token | ~7,800 | ~1,350 | ~5,100 | ~3,600 | ~4,100 |
| 通过率提升 | **+74.1%** | +66.7% | +55.0% | +46.2% | +31.0% |
| 每 1% 的 Token（SKILL.md） | ~42 tok | **~20 tok** | ~43 tok | ~45 tok | ~63 tok |
| 每 1% 的 Token（典型加载） | ~105 tok | **~20 tok** | ~93 tok | ~78 tok | ~132 tok |

google-search 在**绝对通过率提升**上最高（+74.1%），但 SKILL.md 层面的单位效费比（~42 tok/1%）与 yt-dlp-downloader（~43）和 tdd-workflow（~45）相当。典型加载效费比（~105 tok/1%）因参考文件较多而偏高。

---

## 六、与基础模型能力的边界分析

### 6.1 基础模型已具备的能力（Skill 无增量）

| 能力 | 证据 |
|------|------|
| WebSearch 信息检索 | 3/3 场景均主动搜索并找到正确答案 |
| 官方来源优先 | Eval 1 自行定位 go.dev 和 pkg.go.dev |
| 错误信息搜索 | Eval 2 自行搜索 gRPC error 并找到 GitHub issues |
| 多来源综合 | Eval 3 引用 16 个来源进行框架对比 |
| 代码示例生成 | Eval 2 生成完整的调试代码片段 |
| 结构化对比表格 | Eval 3 生成决策矩阵和星级评分 |

### 6.2 基础模型的能力缺口（Skill 填补）

| 缺口 | 证据 | 风险等级 |
|------|------|---------|
| **无搜索模式/预算控制** | 3/3 场景无 Quick/Standard/Deep 概念 | **中** — 可能在简单问题上过度搜索或在复杂问题上不足 |
| **无降级声明** | 3/3 场景直接给结论不标注不确定性 | **高** — 读者把 Partial 当 Full |
| **无证据链追踪** | 3/3 场景不追踪"需要什么证据、找到了什么" | **高** — 无法评估结论可靠性 |
| **无 confidence + source-tier 双标签** | 3/3 场景数字无标签 | **高** — 第三方转述和官方一手数据等权展示 |
| **无可复用查询** | 3/3 场景不输出搜索查询 | **中** — 用户无法继续搜索 |
| **无来源可信度评估** | 3/3 场景不评估来源偏见/时效/缺口 | **中** — 竞品博客和官方文档等权引用 |
| **无搜索策略展示** | 搜索过程不透明 | **低** — 对最终答案无直接影响 |

**核心发现**：基础模型的"搜索结果→答案"能力很强，但"搜索过程可审计性"和"结论可信度标注"为零。google-search skill 的价值集中在后两者。

---

## 七、综合评分

### 7.1 分维度评分

| 维度 | With Skill | Without Skill | 差值 |
|------|-----------|--------------|------|
| Output Contract 合规 | 5.0/5 | 0.5/5 | +4.5 |
| 搜索纪律（模式/预算/策略） | 5.0/5 | 1.0/5 | +4.0 |
| Confidence + Source-tier | 5.0/5 | 0.5/5 | +4.5 |
| 诚实降级 | 5.0/5 | 1.0/5 | +4.0 |
| 可复用查询 | 5.0/5 | 0.0/5 | +5.0 |
| 内容质量（答案正确性/深度） | 5.0/5 | 4.5/5 | +0.5 |
| 来源数量/多样性 | 5.0/5 | 4.5/5 | +0.5 |
| **综合均值** | **5.0/5** | **1.71/5** | **+3.29** |

### 7.2 加权总分

| 维度 | 权重 | 得分 | 加权 |
|------|------|------|------|
| Assertion 通过率（delta） | 25% | 10/10 | 2.50 |
| Output Contract 合规 | 15% | 10/10 | 1.50 |
| 搜索纪律 + 诚实降级 | 15% | 10/10 | 1.50 |
| Confidence + Source-tier | 10% | 10/10 | 1.00 |
| 可复用查询 | 10% | 10/10 | 1.00 |
| Token 效费比 | 10% | 7.0/10 | 0.70 |
| 内容质量增量 | 10% | 2.0/10 | 0.20 |
| 来源数量/质量增量 | 5% | 2.0/10 | 0.10 |
| **加权总分** | | | **8.50/10** |

Token 效费比评分偏低（7.0/10）反映了参考文件较多导致典型加载量（~7,800 tok）较高的现实，尽管 SKILL.md 本身的效费比（~42 tok/1%）与同级 skill 相当。

---

## 八、评估材料

| 材料 | 路径 |
|------|------|
| Eval 1 with-skill 输出 | `/tmp/gsearch-eval/eval-1/with_skill/response.md` |
| Eval 1 without-skill 输出 | `/tmp/gsearch-eval/eval-1/without_skill/response.md` |
| Eval 2 with-skill 输出 | `/tmp/gsearch-eval/eval-2/with_skill/response.md` |
| Eval 2 without-skill 输出 | `/tmp/gsearch-eval/eval-2/without_skill/response.md` |
| Eval 3 with-skill 输出 | `/tmp/gsearch-eval/eval-3/with_skill/response.md` |
| Eval 3 without-skill 输出 | `/tmp/gsearch-eval/eval-3/without_skill/response.md` |
