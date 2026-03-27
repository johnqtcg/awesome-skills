# writing-plans Skill 评估报告

> 评估框架: [skill-creator](https://github.com/anthropics/skills/tree/main/skills/skill-creator)
> 评估日期: 2026-03-27
> 评估对象: `writing-plans`

---

`writing-plans` 是一个面向多步骤任务实施前置规划的结构化 skill，通过 4 个强制 Gate 串联需求澄清、适用性判断、路径发现、范围评估全流程，目标是产出路径已验证、风险已分级、接口已定义、可立即执行的高质量实施计划。它最突出的三个亮点是：以 4 个 Gate 构成的前置流程防止在未厘清需求的情况下写出「幽灵计划」；以 SKIP/Lite/Standard/Deep 四档执行模式按任务复杂度动态调整输出体量，避免文档过载；同时通过 `[Existing]/[New]/[Inferred]/[Speculative]` 四标签路径验证体系和 `[interface]/[test-assertion]/[command]` 代码块标注，将计划文档变为可验证、可执行的工程文档。

## 1. Skill 概述

`writing-plans` 是一个结构化的实施计划创建 skill，定义了 4 个强制 Gate、4 种执行模式、10 项反模式检查、以及覆盖 6 类变更类型的计划模板体系。其目标是确保每个计划在落笔前完成需求澄清、路径验证和风险分级。

**核心组件**:

| 文件 | 行数 | 职责 |
|------|------|------|
| `SKILL.md` | 301 | 主技能定义（4 Gate 流程、4 执行模式、Output Contract） |
| `references/requirements-clarity-gate.md` | 128 | Gate 1：5 维度需求清晰度检查规则 |
| `references/applicability-gate.md` | 51 | Gate 2：适用性决策树与模式选择 |
| `references/repo-discovery-protocol.md` | 80 | Gate 3：路径验证协议与 4 标签体系 |
| `references/golden-scenarios.md` | 157 | 6 类场景 GOOD/BAD 示例对照 |
| `references/reviewer-checklist.md` | 71 | B/N/SB 三层审查清单 |
| `references/anti-examples.md` | 104 | 10 类反模式（BAD/GOOD + WHY） |
| `references/plan-update-protocol.md` | 44 | 执行偏差分级与重规划阈值 |
| `references/plan-templates/feature.md` | 39 | 功能类计划模板 |
| `references/plan-templates/bugfix.md` | 31 | 缺陷修复模板 |
| `references/plan-templates/refactor.md` | 48 | 重构类模板 |
| `references/plan-templates/migration.md` | 44 | 迁移类模板 |
| `references/plan-templates/api-change.md` | 42 | API 变更模板 |
| `references/plan-templates/docs-only.md` | 45 | 文档变更模板（主要为 SKIP 路径） |
| 测试套件 (`test_skill_contract.py` + `test_golden_scenarios.py`) | 831 | 合约测试 + 黄金场景验证 |

---

## 2. 测试设计

### 2.1 场景定义

| # | 场景名称 | 核心挑战 | 期望结果 |
|---|----------|----------|----------|
| 1 | 清晰功能需求 | JWT 认证 Go API，5 个包跨越认证边界 | Standard 模式计划，全 Gate 通过，路径标注，接口代码块 |
| 2 | 模糊需求 | "让系统更快"，无范围/指标/目标 | Gate 1 STOP，提出澄清问题，不产生计划文档 |
| 3 | 文档变更 | 更新 README 添加 API 章节 | Gate 2 SKIP，简洁执行清单，无完整计划文档 |

**场景 1 测试 Prompt：**
> "I need to add JWT-based user authentication to our Go REST API. The API currently serves `/users` and `/products` endpoints. I want to add `/auth/login`, `/auth/register`, and `/auth/refresh` endpoints with middleware that protects existing routes."

**场景 2 测试 Prompt：**
> "Make the system faster. There are some performance issues we need to fix."

**场景 3 测试 Prompt：**
> "Update the README.md to add a section about the new API endpoints we just added. Just document what they do and show example curl commands."

### 2.2 断言矩阵（34 项）

**场景 1 — 清晰功能需求 (13 项)**

| ID | 断言 | With-Skill | Without-Skill |
|----|------|:----------:|:-------------:|
| A1 | 系统化运行所有 4 个 Gate（带命令证据） | PASS | FAIL |
| A2 | Gate 2 (Applicability) 选择 Standard 模式 | PASS | FAIL |
| A3 | Gate 3 (Repo Discovery) 为所有路径添加 [Existing]/[New] 标注 | PASS | FAIL |
| A4 | 使用 feature.md 模板结构（必需章节齐全） | PASS | FAIL |
| A5 | 代码块使用 [interface] 标签（非完整实现） | PASS | FAIL |
| A6 | 验证步骤使用 [command] 标签（精确命令） | PASS | FAIL |
| A7 | Quality Scorecard Critical 层全部通过（B: 6/6） | PASS | FAIL |
| A8 | 包含 Reviewer 审核循环（≥1 轮） | PASS | FAIL |
| A9 | 不包含完整函数实现（Anti-Pattern #2） | PASS | FAIL |
| A10 | 包含每任务回滚/风险评估 | PASS | PARTIAL |
| A11 | 计划文档结构符合 Output Contract | PASS | FAIL |
| A12 | 范围/风险分级明确（Gate 4 结果） | PASS | FAIL |
| A13 | 独立任务标注为可并行执行 | PASS | FAIL |

**场景 2 — 模糊需求 (10 项)**

| ID | 断言 | With-Skill | Without-Skill |
|----|------|:----------:|:-------------:|
| B1 | Gate 1 识别需求模糊性（多个 STOP 维度触发） | PASS | PARTIAL |
| B2 | 提出具体澄清问题（≥3 个） | PASS | PASS |
| B3 | 不跳过 Gate 1 直接生成计划文档 | PASS | PASS |
| B4 | 澄清问题覆盖目标/范围/约束维度 | PASS | PASS |
| B5 | 问题中包含具体维度（性能指标、组件范围、基线/目标） | PASS | PARTIAL |
| B6 | 明确说明为何需要澄清（而非猜测） | PASS | PASS |
| B7 | 未使用 [Speculative] 路径（无 Degraded Mode 滥用） | PASS | PASS |
| B8 | 没有产生计划文档正文 | PASS | PASS |
| B9 | 提供「澄清后继续」的路径说明 | PASS | PASS |
| B10 | 输出格式与 Gate 1 失败协议一致（STOP 声明） | PASS | FAIL |

**场景 3 — 文档变更 (11 项)**

| ID | 断言 | With-Skill | Without-Skill |
|----|------|:----------:|:-------------:|
| C1 | Gate 2 (Applicability) 正确选择 SKIP 模式 | PASS | PARTIAL |
| C2 | 明确声明 SKIP 理由（文档变更，无跨模块依赖） | PASS | PASS |
| C3 | 不产生完整 Standard/Deep 计划文档 | PASS | PASS |
| C4 | 建议直接执行（或给出执行清单） | PASS | PASS |
| C5 | 不运行 Gate 3 (Repo Discovery) 完整流程 | PASS | PASS |
| C6 | 没有虚构/未验证的文件路径或端点 | PASS | FAIL |
| C7 | 没有 Quality Scorecard 评估（SKIP 时不需要） | PASS | PASS |
| C8 | 没有 Reviewer 审核循环触发 | PASS | PASS |
| C9 | 输出简洁（决策部分清晰明了） | PARTIAL | FAIL |
| C10 | 与 docs-only.md 模板的 SKIP 信号一致 | PASS | FAIL |
| C11 | 输出遵循 Output Contract（SKIP 分支） | PASS | FAIL |

---

## 3. 通过率对比

### 3.1 总体通过率

| 配置 | 通过 | 部分通过 | 失败 | 通过率 |
|------|------|---------|------|--------|
| **With Skill** | 33 | 1 | 0 | **97%**（含 PARTIAL 按 0.5 计 = **98.5%**） |
| **Without Skill** | 13 | 4 | 17 | **38%**（含 PARTIAL 按 0.5 计 = **44%**） |

**通过率提升: +59pp**（含 PARTIAL 时 +54.5pp）

### 3.2 按场景通过率

| 场景 | With-Skill | Without-Skill | 差异 |
|------|:----------:|:-------------:|:----:|
| 1. 清晰功能需求 | 13/13 (100%) | 0.5/13 (4%) | +96pp |
| 2. 模糊需求 | 10/10 (100%) | 8/10 (80%) | +20pp |
| 3. 文档变更 | 10.5/11 (95%) | 6.5/11 (59%) | +36pp |

> **注**：场景 2 差异较小（+20pp），因为需求模糊时 Baseline 模型也倾向于自然地提出澄清问题。Skill 的额外价值在于：结构化 Gate 1 分析、精确匹配 D1-D5 维度的问题设计、以及规范化的 STOP 协议输出。

### 3.3 实质性维度（不依赖流程结构的核心能力）

为排除「流程断言偏差」，额外评估 12 项与流程无关的实质性检查：

| ID | 检查项 | With-Skill | Without-Skill |
|----|--------|:----------:|:-------------:|
| S1 | 场景 2: 正确识别需求模糊并拒绝直接规划 | PASS | PASS |
| S2 | 场景 3: 识别文档变更无需正式计划 | PASS | PARTIAL |
| S3 | 场景 1: 所有文件路径在写入计划前已验证 | PASS | FAIL |
| S4 | 场景 1: 每个任务包含独立回滚步骤 | PASS | FAIL |
| S5 | 场景 1: 计划只含接口定义，无完整函数体 | PASS | FAIL |
| S6 | 场景 1: 可并行任务被明确标注 | PASS | FAIL |
| S7 | 场景 1: 验证步骤包含可运行的精确命令 | PASS | PASS |
| S8 | 场景 1: 执行模式（SKIP/Lite/Standard/Deep）显式声明 | PASS | FAIL |
| S9 | 场景 1: 计划包含明确的范围内/范围外边界 | PASS | FAIL |
| S10 | 场景 1: 变更风险等级被明确分类 | PASS | FAIL |
| S11 | 场景 1: 计划通过审查清单（B/N/SB）验证 | PASS | FAIL |
| S12 | 场景 3: 无虚构路径或推测性端点写入输出 | PASS | FAIL |

**实质性通过率**: With-Skill **12/12 (100%)** vs Without-Skill **3/12 (25%)**，提升 **+75pp**（含 PARTIAL = 3.5/12 ≈ 29%，提升 **+71pp**）。

---

## 4. 关键差异分析

### 4.1 With-Skill 独有的行为（Baseline 完全缺失）

| 行为 | 影响 |
|------|------|
| **系统化 4-Gate 流程** | Gate 1 检查需求清晰度、Gate 2 选择模式、Gate 3 验证路径、Gate 4 分类风险，每步有明确输出 |
| **路径验证四标签体系** | [Existing]/[New]/[Inferred]/[Speculative] 确保计划文档中不出现幽灵路径 |
| **代码块语义标注** | [interface] 只含签名/结构体、[test-assertion] 含预期行为、[command] 含精确命令，防止实现代码渗入计划 |
| **SKIP/Lite/Standard/Deep 模式决策** | 按任务复杂度动态调整体量，文档变更不触发 Standard 计划，避免过度工程化 |
| **每任务回滚协议** | 每个任务块末尾有具体回滚步骤，非 checklist 末尾一句话 |
| **Reviewer 审查循环** | Standard 模式触发 1 轮 B/N/SB 三层审查，作为计划自检机制 |
| **Output Contract 规范输出** | 固定结构：Gate 判定 → 文件地图 → 任务块（含依赖/阻塞关系）→ 验证命令 |
| **Gate 1 STOP 协议** | 模糊需求时明确 STOP，说明 STOP 理由，给出「澄清后继续」的 pipeline |

### 4.2 Baseline 能做到但质量较低的行为

| 行为 | With-Skill 质量 | Without-Skill 质量 |
|------|-----------------|-------------------|
| 模糊需求识别 | Gate 1 系统化分析 4 个 STOP 触发维度，输出结构化 STOP 声明 | 自然语言识别，能提问但无维度框架 |
| 澄清问题设计 | 5 个针对 D1-D5 维度的精准问题 | 4 个问题，覆盖面类似但结构性弱 |
| 无需计划场景处理 | 正式 SKIP 决策 + 执行清单 + Gate 应用摘要表 | 直接写 README 内容（体量过大，无决策说明） |
| 命令包含 | [command] 标注 + 精确命令 + 预期输出说明 | 裸命令块，无预期输出 |
| 风险考量 | Gate 4 正式分级（Medium-High），每任务回滚 | 安全 checklist（8 项），但无风险等级和回滚 |

### 4.3 场景级关键发现

**场景 1（清晰功能）**：
- With-Skill: 全 4 Gate 通过，Standard 模式，580 行计划文档，文件地图含 10 条路径全部标注 [Existing]/[New]，6 个任务块含依赖图，Tasks 4/5 标注为可并行，Reviewer Loop B:6/6 + N:7/7 + SB:6/6。
- Without-Skill: 13 节计划，包含完整 Config struct 代码、完整 handler 逻辑、完整 token service 代码（违反 Anti-Pattern #2），无路径标注，无并行识别，无 rollback，无 Reviewer 循环。差异极大。

**场景 2（模糊需求）**：
- With-Skill: Gate 1 明确识别 4 个 STOP 触发条件，提出 5 个精准问题（含 p99 延迟示例、组件范围、基线目标、约束、现有 profiling 数据），说明「写计划会惯性发明问题」的理由，给出 4 步 pipeline（Gate 1 重跑 → 分类 → Discovery → 计划）。
- Without-Skill: 提了 4 个问题，质量相当，另外还主动给出了 pprof 使用指南和常见 Go 性能问题分类。两者最大区别在于：Without-Skill 没有 STOP 声明和 Gate 协议，不知道何时「转入规划」。

**场景 3（文档变更）**：
- With-Skill: Gate 2 决策树走完，决策表格列出 6 个信号均指向 SKIP，输出「无需正式计划，直接执行」+ 5 步执行清单 + Gate 应用摘要表，总计 72 行。
- Without-Skill: 识别无需计划（正确），但随即写了 ~200 行 README 内容，包括从处理器文件名推断的 10 个端点及其完整 curl 示例。输出内容对用户有价值，但核心问题是：推断端点路径（GET /users, POST /products 等）未经验证，属于虚构路径写入输出，违反路径卫生。

---

## 5. Token 效费比分析

### 5.1 Skill 上下文 Token 成本

| 组件 | 行数 | 估算 Token 数 | 加载时机 |
|------|------|-------------|----------|
| `SKILL.md` | 301 | ~2,200 | 始终加载 |
| `applicability-gate.md` | 51 | ~360 | Gate 2（绝大多数场景） |
| `repo-discovery-protocol.md` | 80 | ~560 | Gate 3（Standard/Deep） |
| `requirements-clarity-gate.md` | 128 | ~900 | Gate 1 模糊需求 |
| 计划模板（任一） | 31–48 | ~220–340 | 匹配场景类型时 |
| **典型 Standard 场景总计** | ~505 | **~3,390** | SKILL.md + Gate 2 + Gate 3 + 1 模板 |
| **典型 Gate 1 STOP 场景** | ~429 | **~3,100** | SKILL.md + Gate 1 文档 |
| **典型 SKIP 场景** | ~397 | **~2,875** | SKILL.md + Gate 2 + docs 模板 |
| **三场景加权平均** | ~444 | **~3,122** | — |

注：`golden-scenarios.md`（157行）、`reviewer-checklist.md`（71行）、`anti-examples.md`（104行）仅在 Reviewer 循环或参考时加载，不计入典型场景上下文。

### 5.2 效费比计算

| 指标 | 值 |
|------|------|
| 总体通过率提升（含 PARTIAL） | +54.5pp |
| 总体通过率提升（严格 PASS） | +59pp |
| 实质性通过率提升 | +75pp |
| Skill 上下文成本（典型场景） | ~3,100 tokens |
| **每 1% 通过率提升的 Token 成本（总体）** | **~57 tokens/1%** |
| **每 1% 通过率提升的 Token 成本（实质性）** | **~41 tokens/1%** |

### 5.3 与其他 Skill 效费比对比

| Skill | Token 成本 | 通过率提升 | Tokens/1% |
|-------|-----------|-----------|-----------|
| `git-commit` | ~1,150 | +22pp | ~51 |
| `go-makefile-writer` | ~3,960 (full) | +31pp | ~128 |
| `create-pr` | ~3,400 | +71pp | ~48 |
| **`writing-plans`** | **~3,100** | **+54.5pp** | **~57** |

`writing-plans` 在 tokens/1% 上略逊于 `create-pr`（~57 vs ~48），主要原因：场景 2（模糊需求）中 Baseline 也能自然地提出澄清问题，压低了场景 2 的差异（+20pp），拉低了整体效费比。从「实质性维度」看（+75pp），其效费比（~41 tokens/1%）则优于所有对比 Skill。

### 5.4 Token 回报曲线分析

```
投入 Token 量与回报的映射关系：

~2,200 tokens (SKILL.md only):
  → 获得：4-Gate 流程骨架、4 执行模式、路径标注规则、
           代码块标注、Output Contract、10 类反模式
  → 预计覆盖：~85% 的通过率提升

+360 tokens (applicability-gate.md):
  → 获得：决策树、7 类信号、「Looks Small But Isn't」模式
  → 预计覆盖：+8% 的提升（Gate 2 相关断言）

+560 tokens (repo-discovery-protocol.md):
  → 获得：5 步发现协议、标签定义、路径验证规则
  → 预计覆盖：+5% 的提升（路径标注断言）

+220-340 tokens (plan-template):
  → 获得：场景对应的模板结构和触发信号
  → 预计覆盖：+2% 的提升（模板合规断言）
```

SKILL.md 单独提供约 85% 的价值；适用性门 + 发现协议提供另外 13%；模板提供边际 2%。

---

## 6. 综合评分

### 6.1 分维度评分

| 维度 | With Skill | Without Skill | 差值 |
|------|-----------|--------------|------|
| Gate 执行完整度（4-Gate 系统化 + 命令证据） | 5.0/5 | 1.0/5 | +4.0 |
| 计划文档结构化质量（模板合规 + 路径标注 + 代码块标注） | 5.0/5 | 1.5/5 | +3.5 |
| 模式选择准确性（SKIP/Lite/Standard/Deep 正确判断） | 5.0/5 | 2.0/5 | +3.0 |
| 路径验证 + 反模式规避（路径标注 + 无幽灵路径 + 无完整实现） | 5.0/5 | 1.5/5 | +3.5 |
| 需求澄清质量（Gate 1 结构化 STOP vs 自然提问） | 5.0/5 | 4.0/5 | +1.0 |
| 结构化输出合规（Output Contract + SKIP 分支合规） | 5.0/5 | 1.5/5 | +3.5 |
| **综合均值** | **5.0/5** | **1.9/5** | **+3.1** |

**维度得分说明**:

- **Gate 执行完整度**: With-Skill 在 3 个场景中系统化运行 Gate（场景 2 Gate 1 STOP、场景 3 Gate 1+2 SKIP、场景 1 全 4 Gate），每 Gate 有明确输出和决策依据。Without-Skill 无 Gate 体系，最高得 1.0/5。
- **计划文档结构化质量**: With-Skill 场景 1 产出 580 行完整计划（文件地图、6 任务块、依赖图、每任务回滚、[interface]/[command] 代码块）。Without-Skill 产出 13 节非结构化计划（含完整实现代码，缺路径标注、模板章节、审查循环），得 1.5/5。
- **模式选择准确性**: With-Skill 三场景均选择正确模式（Standard/STOP/SKIP）。Without-Skill 场景 1 未声明模式，场景 3 直接写 README 内容而非 SKIP+清单，得 2.0/5。
- **路径验证 + 反模式规避**: With-Skill 场景 1 文件地图 10 条路径全部标注，场景 3 未写入推测端点。Without-Skill 场景 1 有完整实现代码（Anti-Pattern #2），场景 3 写入 10 个推断端点路径，得 1.5/5。
- **需求澄清质量**: 场景 2 中两者均能提出澄清问题，Baseline 甚至提供了 pprof 使用指南（额外价值）。差距主要在：Without-Skill 缺乏结构化 STOP 声明和后续 pipeline 说明，得 4.0/5。
- **结构化输出合规**: With-Skill 三个场景均有规范化输出（Gate 摘要表、决策树走读、Output Contract）。Without-Skill 无 Output Contract，得 1.5/5。

### 6.2 加权总分

| 维度 | 权重 | 得分 | 理由 | 加权 |
|------|------|------|------|------|
| Assertion 通过率（delta） | 25% | 9.5/10 | +54.5pp（总体）/ +75pp（实质性），低于 create-pr（+71pp）因 S2 差异小 | 2.375 |
| Gate 执行完整度 | 20% | 10.0/10 | 3/3 场景 Gate 系统化执行，每步有明确输出 | 2.00 |
| 计划文档结构化质量 | 15% | 10.0/10 | 路径标注、代码块标注、任务依赖图全部到位 | 1.50 |
| 模式选择准确性 | 15% | 10.0/10 | SKIP/STOP/Standard 三场景判断全部正确 | 1.50 |
| Token 效费比 | 15% | 7.5/10 | ~57 tok/1%（总体），场景 2 Baseline 表现良好压低了差异；实质性维度 ~41 tok/1% 是最优 | 1.125 |
| 路径验证 + 反模式规避 | 10% | 9.5/10 | 仅 C9（输出行数）为 PARTIAL（72 行 vs 建议 ≤15 行），但 SKIP 场景需展示 Gate 决策表，略超属合理 | 0.95 |
| **加权总分** | **100%** | | | **9.45/10** |

### 6.3 与其他 Skill 综合评分对比

| Skill | 加权总分 | 通过率 delta | Tokens/1% | 最大优势维度 |
|-------|---------|-------------|-----------|-------------|
| **create-pr** | **9.55/10** | +71pp | ~48 | Gate 流程 (+3.5)、Output Contract (+4.0) |
| **writing-plans** | **9.45/10** | +54.5pp | ~57 | Gate 执行 (+4.0)、路径验证 (+3.5) |
| go-makefile-writer | 9.16/10 | +31pp | ~128 | CI 可复现性 (+3.0) |

`writing-plans` 获得本次评估中第二高的综合评分（9.45/10），略低于 `create-pr`（9.55/10）。主要差距来源：

1. **通过率 delta 略小**（+54.5pp vs +71pp）：场景 2（模糊需求）Baseline 也表现良好，拉低了整体差异。
2. **Token 效费比略逊**（~57 tok/1% vs ~48 tok/1%）：同样因场景 2 差异小。

两个 Skill 的共同点是：**PR 创建** 和 **实施规划** 都是 Baseline 模型严重缺乏结构化能力的领域，skill 的边际价值都很高。

**失分点分析**:

- **Assertion 通过率（9.5/10）**：场景 2 中 Baseline 自然询问澄清问题的能力，使得该场景差异仅 +20pp。若评估加入「复杂功能 + 部分路径存在」的边界场景，差异会更显著。
- **Token 效费比（7.5/10）**：`golden-scenarios.md`（157行，~1,100 tokens）和 `plan-update-protocol.md`（44行，~310 tokens）在典型场景中未被加载，属于「按需但低频」的参考资源，不构成实际浪费。

---

## 7. 结论

`writing-plans` skill 在本次评估中展现出高度一致的 4-Gate 执行能力和精确的模式选择逻辑，**实质性通过率 100%（12/12）**，总体通过率 **98.5%**，与 Baseline（44%）相差 **+54.5pp**。

**核心价值点**:

1. **4-Gate 前置流程**：将「模糊需求直接下手写计划」（Anti-Pattern #10）阻止在 Gate 1；将「README 更新触发全 Standard 流程」（过度工程化）阻止在 Gate 2
2. **路径验证四标签体系**：[Existing]/[New]/[Inferred]/[Speculative] 让计划文档的每条路径都可追溯，消除幽灵路径
3. **代码块语义标注**：[interface]/[test-assertion]/[command] 三标签防止实现代码渗入计划（Anti-Pattern #2），保持计划的「接口级」精度
4. **动态模式选择**：SKIP 在文档变更、STOP 在需求模糊、Standard 在跨包功能变更——三场景的模式判断全部正确

**主要风险与优化空间**:

- **场景 2 差异收窄**（+20pp）：当需求明显模糊时，Baseline 也倾向于提问。Skill 的差异化价值在于「系统化 STOP 声明 + D1-D5 维度问题 + 后续 pipeline 说明」，但这些结构性价值在 Reviewer 评审时容易被忽视。
- **C9 行数约束过严**：SKIP 场景需展示 Gate 决策表（本质上是结构化证据），72 行输出属于必要体量，「≤15 行」的断言设计值得修订为「无完整计划文档正文」。
- **`golden-scenarios.md` 利用率低**：157 行参考文档在 3 个测试场景中均未被主动加载，建议在 SKILL.md 中为 Reviewer 循环阶段添加更明确的引用指引。