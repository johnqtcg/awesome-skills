# systematic-debugging Skill 评审报告

> 评估框架: [skill-creator](https://github.com/anthropics/skills/tree/main/skills/skill-creator)
> 评估日期: 2026-03-11
> 评估对象: `systematic-debugging`

---

`systematic-debugging` 是一个强调“先找根因、再谈修复”的调试 skill，适合用于测试失败、线上异常、间歇性问题、性能回退和第三方集成故障等场景，核心目标是避免拍脑袋式修补。它最突出的三个亮点是：把调试过程拆成清晰 phase，并要求先完成调查再提出永久修复；强调显式假设、证据收集和调查步骤完整性，使调试报告更可验证、更少猜测；同时内置严重级别分流，既支持紧急故障下先止血，也坚持后续必须回到根因分析。

## 一、评估概览

本次评估从**实际任务表现**和 **Token 效费比**两个维度对 systematic-debugging skill 进行全面评审。设计 3 个递进复杂度的调试场景（Go 测试失败、多层错误映射 Bug、间歇性空结果），每个场景分别运行 with-skill 和 without-skill 配置，共 3 场景 × 2 配置 = 6 次独立 subagent 运行，对照 40 条 assertion 进行评分。

| 维度 | With Skill | Without Skill | 差异 |
|------|-----------|--------------|------|
| **Assertion 通过率** | **40/40 (100%)** | 29/40 (72.5%) | **+27.5 百分点** |
| **Phase 结构化** | 3/3 全对 | 0/3 | 最大单项差异 |
| **显式假设陈述** | 3/3 | 0/3 | Skill 独有 |
| **调查步骤完整性** | 3/3 | 0/3 | 至少缺 1 步 |
| **Skill Token 开销（SKILL.md）** | ~2,000 tokens | 0 | — |
| **Skill Token 开销（含参考资料）** | ~3,000 tokens | 0 | — |
| **每 1% 通过率提升的 Token 成本** | ~73 tokens（SKILL.md only）/ ~109 tokens（full） | — | — |

---

## 二、测试方法

### 2.1 场景设计

所有场景使用 issue2md 项目 (`/Users/john/issue2md`) 的真实代码构造调试任务。

| 场景 | 目标文件 | 核心考察点 | Assertions |
|------|---------|-----------|-----------|
| Eval 1: 测试失败 | `frontmatter.go` `yamlQuote` | 单函数 Bug：多行字符串破坏 YAML 输出 | 14 |
| Eval 2: 错误状态码 | `graphql_client.go` → `handler.go` | 多层调用链：GraphQL 错误未分类导致 502 | 13 |
| Eval 3: 间歇空摘要 | `summary_openai.go` | 间歇性 Bug：LLM 输出含尾逗号导致 JSON 校验失败 | 13 |

### 2.2 Assertion 设计原则

Assertion 聚焦于 **调试过程纪律**（process discipline），而非最终 Bug 修复质量。核心检查项：

| 维度 | 检查内容 | 覆盖 Assertions |
|------|---------|----------------|
| Phase 1 完整性 | 读错误信息、复现、查历史、追数据流、证据收集 | 15 |
| Phase 2 完整性 | 工作示例对比、差异分析 | 3 |
| Phase 3 完整性 | 显式假设陈述、最小测试 | 6 |
| Phase 4 完整性 | 失败测试、单一修复、验证、无附带改进 | 12 |
| 结构纪律 | Phase 顺序合规 | 3 |
| 抗冲动纪律 | 不跳过调查直接修复 | 1 |

### 2.3 执行方式

- With-skill 运行先读取 `SKILL.md` 及 `root-cause-tracing.md` 参考资料
- Without-skill 运行不读取任何 skill，按模型默认行为调试
- 所有运行在独立 subagent 中执行

---

## 三、Assertion 通过率

### 3.1 总览

| 场景 | Assertions | With Skill | Without Skill | 差值 |
|------|-----------|-----------|--------------|------|
| Eval 1: 测试失败 | 14 | **14/14 (100%)** | 9/14 (64.3%) | +35.7% |
| Eval 2: 多层 Bug | 13 | **13/13 (100%)** | 11/13 (84.6%) | +15.4% |
| Eval 3: 间歇性 Bug | 13 | **13/13 (100%)** | 9/13 (69.2%) | +30.8% |
| **总计** | **40** | **40/40 (100%)** | **29/40 (72.5%)** | **+27.5%** |

### 3.2 Without-Skill 失败的 11 条 Assertion 归类

| 失败类型 | 次数 | 涉及 Eval | 说明 |
|---------|------|----------|------|
| **Phase 结构化缺失** | 3 | 1/2/3 | 扁平结构（Symptom → Root Cause → Fix），无 Phase 1→2→3→4 |
| **显式假设缺失** | 3 | 1/2/3 | 从根因直接跳到修复，缺少 "I think X because Y" 的假设验证环节 |
| **复现尝试缺失** | 1 | 1 | 未说明如何触发 Bug、是否可靠复现 |
| **变更历史检查缺失** | 1 | 1 | 未查 git 历史或近期变更 |
| **工作示例对比缺失** | 1 | 1 | 未比较已有的正常工作用例 |
| **现有测试审查缺失** | 1 | 3 | 未检查现有测试覆盖了什么、遗漏了什么 |
| **修复验证缺失** | 1 | 3 | 提出修复但未演示实际运行测试确认 |

### 3.3 趋势：Skill 优势与场景特征的关系

| 场景特征 | With-Skill 优势 | 分析 |
|---------|----------------|------|
| Eval 1（简单、单点） | +35.7%（5 条失败） | 简单 Bug 最容易让人跳过调查；Skill 的 Iron Law 强制走全流程 |
| Eval 2（多层、复杂） | +15.4%（2 条失败） | 复杂场景天然需要分层分析，基础模型也会做较完整的调查 |
| Eval 3（间歇、隐蔽） | +30.8%（4 条失败） | 间歇 Bug 的"沉默失败"需要系统性证据收集；without-skill 缺少过程严谨性 |

**关键发现**: Skill 的最大价值在**简单 Bug 场景**（Eval 1: +35.7%）和**间歇 Bug 场景**（Eval 3: +30.8%）。这恰好对应了 skill 中 "When to Use — Use this ESPECIALLY when 'Just one quick fix' seems obvious" 的设计意图。

---

## 四、逐维度对比分析

### 4.1 Phase 结构化（最大差异维度）

这是 **所有 3 场景一致性最高的差异**：with-skill 全部采用 Phase 1→2→3→4 结构，without-skill 全部使用扁平结构。

| 维度 | With Skill | Without Skill |
|------|-----------|--------------|
| Phase 1: Root Cause Investigation | ✅ 3/3 独立章节，含子步骤 | ❌ 混合在 "Root Cause" 段中 |
| Phase 2: Pattern Analysis | ✅ 3/3 独立章节 | ❌ 0/3 完全缺失或隐含 |
| Phase 3: Hypothesis and Testing | ✅ 3/3 显式假设 | ❌ 0/3 完全缺失 |
| Phase 4: Implementation | ✅ 3/3 RED→GREEN→Verify | ⚠️ 2/3 有修复和测试但无验证流程 |

**分析**: 基础模型的默认调试范式是 **Root Cause → Fix → Test**，跳过了 Pattern Analysis 和 Hypothesis 两个关键中间步骤。Skill 的四阶段框架强制了额外的分析周期，这在 Eval 2 中尤为明显——with-skill 的 Phase 2 明确对比了 REST 和 GraphQL 的工作/破损路径，而 without-skill 虽然也做了类似对比，但是嵌入在根因分析中而非独立环节。

**实际价值**: 四阶段结构确保：
- 调查不会因为"看到了根因"就立即跳到修复（Phase 2 防护）
- 修复前有明确的可验证假设（Phase 3 防护）
- 修复后有红/绿验证循环（Phase 4 纪律）

### 4.2 显式假设陈述（Skill 独有）

| 场景 | With Skill 假设 | Without Skill |
|------|----------------|--------------|
| Eval 1 | "The root cause is that `yamlQuote` does not handle newline characters. Replacing `\r\n`, `\r`, and `\n` with spaces..." | 无假设，直接 "Fix Applied" |
| Eval 2 | "`queryRaw()` line 144-146 uses `fmt.Errorf` with `%s`, creating plain unclassified error..." | 无假设，直接 "Proposed Fix" |
| Eval 3 | "`normalizeSummaryJSON` does not strip trailing commas... `json.Valid()` returns false..." | 无假设，直接 "Proposed Fix" |

**分析**: Without-skill 在所有 3 场景中都跳过了显式假设环节。虽然根因描述中隐含了假设，但缺少 "I think X because Y" 的明确陈述意味着：
- 无法区分"确认的根因"和"猜测的根因"
- 无法设计最小化验证实验来排除替代解释
- 在复杂 Bug 中可能导致"修了症状而非根因"

Skill 的 Phase 3 规则 "Form Single Hypothesis — State clearly: 'I think X is the root cause because Y'" 有效消除了这个缺口。

### 4.3 调查完整性

With-skill 在 Phase 1 中执行的调查子步骤在 without-skill 中部分缺失：

| Phase 1 子步骤 | With Skill | Without Skill | 缺失场景 |
|---------------|-----------|--------------|---------|
| 读错误信息 | 3/3 | 3/3 | — |
| 复现确认 | 3/3 | 2/3 | Eval 1 |
| 查变更历史 | 3/3 | 2/3 | Eval 1 |
| 数据流追踪 | 3/3 | 3/3 | — |
| 证据收集（多组件） | 3/3 | 3/3 | — |
| 工作示例对比 | 3/3 | 2/3 | Eval 1 |
| 现有测试审查 | 3/3 | 2/3 | Eval 3 |

**分析**: 基础模型在**读错误信息**和**数据流追踪**方面表现强劲（3/3），但在**复现确认**、**变更历史**和**工作示例对比**上不一致。Eval 1（最简单的场景）缺失项最多，说明简单 Bug 更容易诱发调查步骤的省略。

### 4.4 Bug 修复质量对比

有趣的是，所有 6 个 agent 都成功识别了正确的根因并提出了等效的修复方案：

| 场景 | With Skill 修复 | Without Skill 修复 | 质量差异 |
|------|----------------|-------------------|---------|
| Eval 1 | `strings.NewReplacer` 替换换行 | `strings.NewReplacer` 替换换行 | 无差异 |
| Eval 2 | 添加 `Type` 字段 + `isGraphQLNotFoundError` + `%w` | 添加 `Type` 字段 + `isGraphQLNotFoundError` + `%w` | 无差异 |
| Eval 3 | `stripTrailingCommas()` 字符级解析 | `removeTrailingCommas()` 正则表达式 | 微小差异（实现方式不同，功能等价） |

**关键发现**: **基础模型的 Bug 修复能力本身已经很强**。Skill 的价值不在于提高修复质量，而在于**强制执行结构化过程**，确保：
- 修复前已充分理解问题（防止"症状修复"）
- 假设经过验证（防止"碰巧修对了"）
- 修复经过完整的红/绿验证循环

---

## 五、Token 效费比分析

### 5.1 Skill 体积

| 文件 | 行数 | 单词 | 估算 Token |
|------|------|------|-----------|
| **SKILL.md** | 296 | 1,504 | ~2,000 |
| root-cause-tracing.md | 169 | 739 | ~1,000 |
| defense-in-depth.md | 122 | 494 | ~650 |
| condition-based-waiting.md | 115 | 498 | ~650 |
| condition-based-waiting-example.ts | 158 | 667 | ~870 |
| find-polluter.sh | 63 | 214 | ~280 |
| test-*.md + test-academic.md | 209 | 1,221 | ~1,600 |
| CREATION-LOG.md | 119 | 612 | ~800 |
| **Description（始终在 context）** | — | ~15 | ~20 |

**评估中实际加载:**

| 配置 | 读取文件 | 总 Token |
|------|---------|---------|
| Eval 1/2/3 with-skill | SKILL.md + root-cause-tracing.md | ~3,000 |
| 仅 SKILL.md（最小加载） | SKILL.md | ~2,000 |
| 全部加载（极端情况） | 所有 .md + .sh + .ts | ~7,850 |

### 5.2 Token 换取的质量提升

| 指标 | 数值 |
|------|------|
| With-skill 通过率 | 100% (40/40) |
| Without-skill 通过率 | 72.5% (29/40) |
| 通过率提升 | +27.5 百分点 |
| 每修复 1 条 assertion 的 Token 成本 | ~182 tokens（SKILL.md only）/ ~273 tokens（full） |
| 每 1% 通过率提升的 Token 成本 | ~73 tokens（SKILL.md only）/ ~109 tokens（full） |

### 5.3 Token 分段效费比

将 SKILL.md 内容按功能模块拆分：

| 模块 | 估算 Token | 关联 Assertion 差值 | 效费比 |
|------|-----------|-------------------|--------|
| **Iron Law + Phase 顺序** | ~120 | 3 条（Phase 结构化） | **极高** — 40 tok/assertion |
| **Phase 3: Hypothesis 规则** | ~150 | 3 条（显式假设） | **极高** — 50 tok/assertion |
| **Phase 1: 5 步调查清单** | ~400 | 3 条（复现/历史/对比/测试审查） | **高** — 133 tok/assertion |
| **Phase 4: 实现纪律** | ~250 | 1 条（验证） | **中** — 250 tok/assertion |
| **Phase 2: Pattern Analysis** | ~150 | 1 条（工作示例对比） | **中** — 150 tok/assertion |
| **Red Flags 清单** | ~200 | 间接贡献（强化不跳步纪律） | **中** — 无直接 assertion |
| **Common Rationalizations 表** | ~150 | 间接贡献（抗"quick fix"诱惑） | **中** — 无直接 assertion |
| **"When to Use" 区块** | ~180 | 0 条（场景匹配已由评估设定） | **低** — 评估中无增量 |
| **Phase 4.5: 架构质疑** | ~200 | 0 条（评估未覆盖 3+ 次失败修复场景） | **低** — 未测试 |
| **Supporting Techniques 指针** | ~50 | 0 条（仅指针） | **低** — 信息密度低 |
| **root-cause-tracing.md** | ~1,000 | 间接贡献（Eval 2 多层追踪） | **中** — 辅助追踪但基础模型也会做 |

### 5.4 高杠杆 vs 低杠杆指令

**高杠杆（~670 tokens SKILL.md → 10 条 assertion 差值）:**
- Iron Law + Phase 顺序（120 tok → 3 条）
- Phase 3 Hypothesis 规则（150 tok → 3 条）
- Phase 1 五步调查清单（400 tok → 4 条）

**中杠杆（~750 tokens → 间接贡献）:**
- Phase 4 实现纪律（250 tok → 1 条直接 + 红/绿流程间接）
- Phase 2 Pattern Analysis（150 tok → 1 条）
- Red Flags + Rationalizations（350 tok → 抗冲动纪律间接）

**低杠杆（~430 tokens → 0 条差值）:**
- "When to Use" 区块（180 tok）— 场景匹配由评估设定
- Phase 4.5 架构质疑（200 tok）— 未测试
- Supporting Techniques 指针（50 tok）— 信息密度低

**参考资料（~1,000 tokens root-cause-tracing.md → 间接贡献）:**
- 辅助了 Eval 2 多层追踪的结构化，但基础模型在多层追踪方面本身表现良好

### 5.5 Token 效率评级

| 评级 | 结论 |
|------|------|
| **整体 ROI** | **优秀** — ~3,000 tokens 换取 +27.5% 通过率 |
| **SKILL.md 本身 ROI** | **优秀** — ~2,000 tokens 包含全部高杠杆规则 |
| **高杠杆 Token 比例** | ~34%（670/2,000）直接贡献 10/11 条 assertion 差值 |
| **低杠杆 Token 比例** | ~22%（430/2,000）在当前评估中无增量贡献 |
| **参考资料效费比** | **中等** — ~1,000 tokens root-cause-tracing.md 提供间接提升 |

### 5.6 与其他 Skill 的效费比对比

| 指标 | systematic-debugging | go-makefile-writer | security-review | google-search |
|------|---------------------|-------------------|-----------------|---------------|
| SKILL.md Token | ~2,000 | ~1,960 | ~3,700 | ~2,200 |
| 总加载 Token | ~3,000 | ~4,100-4,600 | ~5,000-9,600 | ~3,600 |
| 通过率提升 | +27.5% | +31.0% | +50.0% | +74.1% |
| 每 1% 的 Token（SKILL.md） | ~73 tok | ~63 tok | ~74 tok | ~30 tok |
| 每 1% 的 Token（full） | ~109 tok | ~149 tok | ~100-192 tok | ~49 tok |

systematic-debugging 的 SKILL.md 效费比（73 tok/1%）与 go-makefile-writer（63 tok/1%）和 security-review（74 tok/1%）处于同一区间，属于**高效率 skill**。

---

## 六、与基础模型能力的边界分析

### 6.1 基础模型已具备的能力（Skill 无增量）

| 能力 | 证据 |
|------|------|
| 准确读取错误信息 | 3/3 场景正确解析错误输出 |
| 数据流追踪（单层和多层） | 3/3 场景完整追踪到根因 |
| 正确识别根因 | 3/3 场景根因一致 |
| 编写等效修复代码 | 3/3 场景修复功能等价 |
| 编写 table-driven 测试 | 3/3 场景产出类似测试 |
| 多组件边界分析 | Eval 2 中详细分析了 5 层组件 |
| 间歇性 Bug 的症状→原因映射 | Eval 3 中正确解释了"为什么间歇" |

### 6.2 基础模型的能力缺口（Skill 填补）

| 缺口 | 证据 | 风险等级 |
|------|------|---------|
| **Phase 结构化缺失** | 3/3 场景使用扁平结构 | 高 — 无法区分调查、分析、验证、实现阶段 |
| **显式假设缺失** | 3/3 场景从根因直接跳到修复 | 高 — 对复杂 Bug 可能导致"碰巧修对" |
| **复现确认不一致** | 1/3 场景跳过 | 中 — 简单 Bug 更容易省略 |
| **变更历史检查不一致** | 1/3 场景跳过 | 低 — 特定场景依赖 |
| **工作示例对比缺失** | 1/3 场景跳过 | 中 — Pattern Analysis 是防止重复 Bug 的关键 |
| **现有测试审查不一致** | 1/3 场景跳过 | 中 — 遗漏可能导致测试覆盖盲区 |
| **修复验证不一致** | 1/3 场景跳过 | 高 — 未验证的修复可能引入新 Bug |

### 6.3 Skill 价值定位

systematic-debugging skill 的核心价值不在于**提升 Bug 修复能力**（基础模型已经很强），而在于**强制执行调试纪律**：

1. **防止跳步**：Iron Law + Phase 结构强制完成调查后才能修复
2. **显式假设验证**：Phase 3 确保修复基于验证过的假设而非直觉
3. **调查清单完整性**：Phase 1 的 5 步清单确保不遗漏关键调查步骤
4. **抗冲动机制**：Red Flags + Rationalizations 表在"简单 Bug"场景中特别有效

这类似于飞行检查清单——不是因为飞行员不知道怎么飞，而是确保不会因为"太简单"或"太急"而跳过关键步骤。

---

## 七、综合评分

### 7.1 分维度评分

| 维度 | With Skill | Without Skill | 差值 |
|------|-----------|--------------|------|
| Phase 结构化 | 5.0/5 | 1.0/5 | +4.0 |
| 假设验证纪律 | 5.0/5 | 1.0/5 | +4.0 |
| 调查完整性 | 5.0/5 | 3.5/5 | +1.5 |
| 修复质量 | 5.0/5 | 4.5/5 | +0.5 |
| 测试覆盖 | 5.0/5 | 4.0/5 | +1.0 |
| 验证纪律（红/绿循环） | 5.0/5 | 3.5/5 | +1.5 |
| **综合均值** | **5.0/5** | **2.92/5** | **+2.08** |

### 7.2 加权总分

| 维度 | 权重 | 得分 | 加权 |
|------|------|------|------|
| Assertion 通过率（delta） | 25% | 8.5/10 | 2.13 |
| Phase 结构化 | 20% | 10/10 | 2.00 |
| 假设验证纪律 | 15% | 10/10 | 1.50 |
| 调查完整性 | 15% | 9.0/10 | 1.35 |
| Token 效费比 | 15% | 8.5/10 | 1.28 |
| Bug 修复质量增量 | 10% | 5.0/10 | 0.50 |
| **加权总分** | | | **8.76/10** |

**Bug 修复质量增量得分较低（5.0/10）说明**: 基础模型的修复能力已经很强，skill 的贡献主要在过程纪律而非结果质量。

---

## 八、评估材料

| 材料 | 路径 |
|------|------|
| Eval 1 with-skill 输出 | `/tmp/debug-eval/eval-1/with_skill/response.md` |
| Eval 1 without-skill 输出 | `/tmp/debug-eval/eval-1/without_skill/response.md` |
| Eval 2 with-skill 输出 | `/tmp/debug-eval/eval-2/with_skill/response.md` |
| Eval 2 without-skill 输出 | `/tmp/debug-eval/eval-2/without_skill/response.md` |
| Eval 3 with-skill 输出 | `/tmp/debug-eval/eval-3/with_skill/response.md` |
| Eval 3 without-skill 输出 | `/tmp/debug-eval/eval-3/without_skill/response.md` |
| 目标代码 | `/Users/john/issue2md/internal/converter/` |
| 目标代码 | `/Users/john/issue2md/internal/github/` |
| 目标代码 | `/Users/john/issue2md/internal/webapp/` |
