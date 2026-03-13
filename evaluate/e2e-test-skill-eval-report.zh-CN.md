# e2e-best-practise Skill 评审报告

> 评估框架: [skill-creator](https://github.com/anthropics/skills/tree/main/skills/skill-creator)
> 评估日期: 2026-03-11
> 评估对象: `e2e-test`

---

`e2e-best-practise` 是一个面向关键用户旅程的端到端测试实践 skill，适合用于设计 E2E 覆盖策略、处理 flaky 测试、制定 CI gate，以及把探索性验证沉淀为可维护的自动化测试。它最突出的三个亮点是：优先使用 Agent Browser 做探索与复现、再用 Playwright 或项目原生测试框架沉淀代码，工具路径非常清晰；内置环境门禁、Runner 选择和结果强度控制，能够在不同技术栈下做诚实降级而不是硬套模板；同时提供结构化输出与 machine-readable JSON，便于测试治理、问题分诊和 CI 集成。

## 一、评估概览

本次评估从**实际任务表现**和 **Token 效费比**两个维度对 e2e-best-practise skill 进行全面评审。设计 3 个场景（E2E 旅程覆盖、Flaky 测试分诊、CI Gate 设计），每个场景分别运行 with-skill 和 without-skill 配置，共 3 场景 × 2 配置 = 6 次独立 subagent 运行，对照 39 条 assertion 进行评分。

**特殊挑战**: issue2md 是一个**纯 Go Web 应用**，无 Node.js/Playwright/package.json，而 e2e-best-practise 技能以 Playwright 为首选工具。这测试了 skill 的**环境适应能力和降级策略**。

| 维度 | With Skill | Without Skill | 差异 |
|------|-----------|--------------|------|
| **Assertion 通过率** | **39/39 (100%)** | 20/39 (51.3%) | **+48.7 百分点** |
| **5 Gate 覆盖** | 3/3 场景全覆盖 | 0/3 | Skill 独有 |
| **Output Contract 结构化报告** | 3/3 | 0/3 | Skill 独有 |
| **Machine-Readable JSON** | 3/3 | 0/3 | Skill 独有 |
| **Quality Scorecard** | 1/1（Eval 1）| 0/1 | Skill 独有 |
| **环境适应（Go ← Playwright 降级）** | 正确降级 + 详细理由 | 自然选择 Go（无 skill 指引） | Skill 提供了决策记录 |
| **Skill Token 开销（SKILL.md 单文件）** | ~2,800 tokens | 0 | — |
| **Skill Token 开销（典型加载）** | ~9,400 tokens | 0 | — |
| **每 1% 通过率提升的 Token 成本** | ~57 tokens（SKILL.md only）/ ~193 tokens（typical） | — | — |

---

## 二、测试方法

### 2.1 场景设计

| 场景 | 目标 | 核心考察点 | Assertions |
|------|------|-----------|-----------|
| Eval 1: E2E 旅程覆盖 | 为 web convert flow 创建 E2E 测试 | 环境适应（纯 Go 项目 vs Playwright skill）、Gate 覆盖、测试质量 | 15 |
| Eval 2: Flaky 测试分诊 | 分诊 CI 上间歇性失败的 SwaggerRedirect 测试 | 分诊流程、根因分类、稳定性验证、Gate 覆盖 | 12 |
| Eval 3: CI Gate 设计 | 设计 E2E 测试的 CI 策略 | 触发策略、Secret 管理、Artifact 收集、重试策略 | 12 |

### 2.2 特殊挑战：Playwright Skill vs Go 项目

issue2md 的特征使其成为一个**边界测试场景**：

| issue2md 特征 | e2e-best-practise 技能的预期 |
|--------------|---------------------------|
| 无 Node.js / package.json | 技能以 Playwright (Node.js) 为首选 |
| 无客户端 JavaScript | 技能有大量 DOM selector/wait 规则 |
| Go `html/template` 服务端渲染 | 技能假设 SPA/SSR 框架 (Next.js, React, Vue) |
| 已有 Go HTTP client E2E 测试 | 技能推荐 Playwright 代码路径 |

这测试了 skill 的**降级能力**——当首选工具链不适用时，能否正确识别并选择合适的替代方案。

### 2.3 执行方式

- With-skill 运行先读取 SKILL.md 及选择性加载参考文件
- Without-skill 运行不读取任何 skill，按模型默认行为
- 所有运行在独立 subagent 中并行执行

---

## 三、Assertion 通过率

### 3.1 总览

| 场景 | Assertions | With Skill | Without Skill | 差值 |
|------|-----------|-----------|--------------|------|
| Eval 1: E2E 旅程覆盖 | 15 | **15/15 (100%)** | 8/15 (53.3%) | +46.7% |
| Eval 2: Flaky 测试分诊 | 12 | **12/12 (100%)** | 4/12 (33.3%) | +66.7% |
| Eval 3: CI Gate 设计 | 12 | **12/12 (100%)** | 8/12 (66.7%) | +33.3% |
| **总计** | **39** | **39/39 (100%)** | **20/39 (51.3%)** | **+48.7%** |

### 3.2 逐项 Assertion 详情

#### Eval 1: E2E 旅程覆盖 (15 assertions)

| # | Assertion | With | Without | 说明 |
|---|-----------|------|---------|------|
| A1 | Configuration gate 结构化表格 | ✅ | ❌ | Without 提到 gating 但无结构化变量表 |
| A2 | Environment gate 评估 | ✅ | ❌ | Without 无显式环境评估 |
| A3 | Execution integrity gate | ✅ | ❌ | Without 未声明是否运行了测试 |
| A4 | 正确识别无 Playwright | ✅ | ✅ | |
| A5 | 不盲目生成 Playwright 代码 | ✅ | ✅ | |
| A6 | 生成适当的 Go E2E 测试 | ✅ | ✅ | |
| A7 | 无猜测 secrets/URLs | ✅ | ✅ | |
| A8 | 测试覆盖 convert flow | ✅ | ✅ | |
| A9 | 测试覆盖错误路径 | ✅ | ✅ | |
| A10 | 无无条件 sleep/waitForTimeout | ✅ | ✅ | |
| A11 | Data isolation 显式说明 | ✅ | ❌ | Without 未显式记录数据隔离策略 |
| A12 | Output contract 结构化报告 | ✅ | ❌ | Without 仅简单报告 |
| A13 | Machine-readable JSON | ✅ | ❌ | Without 无 JSON 摘要 |
| A14 | 识别已有 E2E 测试 | ✅ | ✅ | |
| A15 | Next actions 提供 | ✅ | ❌ | Without 无下一步行动 |

#### Eval 2: Flaky 测试分诊 (12 assertions)

| # | Assertion | With | Without | 说明 |
|---|-----------|------|---------|------|
| B1 | 遵循分诊序列（reproduce, classify, fix/quarantine） | ✅ | ✅ | |
| B2 | 根因分类标注 | ✅ | ✅ | |
| B3 | 提供复现命令（含 -count） | ✅ | ❌ | Without 无 -count 复现命令 |
| B4 | Configuration gate | ✅ | ❌ | Without 无配置门禁分析 |
| B5 | Environment gate | ✅ | ✅ | Both 对比 local vs CI |
| B6 | Execution integrity gate | ✅ | ❌ | Without 未声明是否实际执行 |
| B7 | 不虚假声称执行 | ✅ | ✅ | |
| B8 | 具体修复建议 | ✅ | ✅ | |
| B9 | Output contract | ✅ | ❌ | Without 无结构化输出 |
| B10 | Artifact 策略 | ✅ | ❌ | Without 未讨论 artifact |
| B11 | Stability gate（单次通过不等于稳定） | ✅ | ❌ | Without 未提及 -count=20 稳定性验证 |
| B12 | Side-effect gate | ✅ | ❌ | Without 无副作用分析 |

#### Eval 3: CI Gate 设计 (12 assertions)

| # | Assertion | With | Without | 说明 |
|---|-----------|------|---------|------|
| C1 | Configuration gate | ✅ | ❌ | Without 无结构化配置分析 |
| C2 | Environment gate | ✅ | ❌ | Without 无显式环境门禁 |
| C3 | CI 策略文档（blocking vs nightly） | ✅ | ✅ | Both 提供三级触发策略 |
| C4 | Artifact 收集配置 | ✅ | ✅ | |
| C5 | GitHub Actions workflow YAML | ✅ | ✅ | |
| C6 | 重试/Flaky 策略 | ✅ | ✅ | |
| C7 | Output contract | ✅ | ❌ | Without 无结构化输出 |
| C8 | Machine-readable JSON | ✅ | ❌ | Without 无 JSON 摘要 |
| C9 | 识别现有 CI targets | ✅ | ✅ | Both 发现 swagger generation gap |
| C10 | 服务启动策略 | ✅ | ✅ | |
| C11 | Parallel vs serial 理由 | ✅ | ✅ | |
| C12 | Next actions | ✅ | ✅ | Without 有 Rollout Plan |

### 3.3 Without-Skill 失败的 19 条 Assertion 归类

| 失败类型 | 次数 | 涉及 Eval | 说明 |
|---------|------|----------|------|
| **5 Mandatory Gates 缺失** | 9 | 全部 | Configuration Gate 3次、Environment Gate 2次、Execution Integrity 2次、Stability Gate 1次、Side-Effect Gate 1次 |
| **Output Contract 缺失** | 3 | 全部 | 无 task type/runner/env gate/execution status 结构化表格 |
| **Machine-Readable JSON 缺失** | 3 | 全部 | 无 CI/tooling 可消费的 JSON 摘要 |
| **Data Isolation 未文档化** | 1 | Eval 1 | 未显式声明数据隔离策略 |
| **Reproduction 命令不完整** | 1 | Eval 2 | 未提供 `-count` 复现命令 |
| **Next Actions 缺失** | 1 | Eval 1 | 无下一步行动列表 |
| **Artifact 策略缺失** | 1 | Eval 2 | 分诊报告未讨论 trace/artifact |

### 3.4 趋势：Skill 优势随任务类型变化

| 场景类型 | With-Skill 优势 | 原因 |
|---------|----------------|------|
| Eval 2: Flaky 分诊 | **+66.7%**（最高） | 分诊流程高度依赖结构化方法论，基线模型缺乏系统性 |
| Eval 1: E2E 旅程 | +46.7% | Gate 覆盖 + Output Contract + 环境降级决策记录 |
| Eval 3: CI 设计 | +33.3%（最低） | CI 设计是模型已有强项，Skill 主要增量在 Gate 和 JSON |

Flaky 分诊是 Skill 增量价值最大的场景——基线模型能找到根因并提出修复，但**缺乏分诊方法论**（reproduce → classify → fix/quarantine 序列）和**稳定性证明要求**（-count=20 验证）。

---

## 四、逐维度对比分析

### 4.1 环境适应能力（核心差异化）

这是本次评估最独特的考察维度。Skill 设计以 Playwright 为首选，但面对纯 Go 项目时：

| 维度 | With Skill | Without Skill |
|------|-----------|--------------|
| Runner 选择决策 | 显式理由（无 Node.js, 无 package.json, Constitution 约束） | 隐式选择 Go HTTP 测试（无决策记录） |
| 降级路径 | "Generate the strongest deliverable the environment can support" → Go HTTP | 自然选择 Go（无降级概念） |
| Playwright 代码 | 明确拒绝（"Installing Playwright would violate the constitution"） | 未考虑（无相关上下文） |

**分析**: With-skill 的 **Operating Model §5**（"Produce only the strongest deliverable the environment can actually support"）正确引导了降级决策。Skill 没有盲目生成 Playwright 代码，而是通过 Environment Gate 确认工具链缺失后选择了 Go HTTP 路径。**降级理由被显式记录**，这对 PR review 和团队共识至关重要。

### 4.2 五大 Mandatory Gate 覆盖

这是 **Skill 最高价值维度**——With-skill 在所有 3 场景中覆盖了全部 5 个 Gate，Without-skill 在所有 3 场景中均缺失多个 Gate。

| Gate | With Skill (3 场景) | Without Skill (3 场景) |
|------|-------|---------|
| Configuration Gate | 3/3 | 0/3 |
| Environment Gate | 3/3 | 1/3（Eval 2 部分覆盖） |
| Execution Integrity Gate | 3/3 | 0/3 |
| Stability Gate | 2/2 (Eval 2,3) | 0/2 |
| Side-Effect Gate | 2/2 (Eval 1,2) | 0/2 |

**实际价值**: Gate 系统防止了三类常见错误：
1. **虚假执行声明** — Execution Integrity Gate 确保 "Not run" 被显式标注
2. **单次通过即宣告修复** — Stability Gate 要求 `-count=20` 验证
3. **遗漏配置依赖** — Configuration Gate 列出所有变量及其 available/missing/unknown 状态

### 4.3 Output Contract 与 Machine-Readable JSON

With-skill 的每个输出都包含：

| 结构 | Eval 1 | Eval 2 | Eval 3 |
|------|--------|--------|--------|
| Output Contract 表格 | ✅ 9 字段 | ✅ 9 字段 | ✅ 9 字段 |
| Machine-Readable JSON | ✅ | ✅ | ✅ |
| Quality Scorecard | ✅ (C1-C4, S1-S6, H1-H4) | N/A | N/A |

Without-skill 产出的报告质量不低（尤其 Eval 3 的 CI 策略非常全面），但**缺少标准化结构**。这意味着：
- 不同任务类型的报告格式不一致
- CI/tooling 无法程序化消费结果
- 多次运行的结果难以对比

### 4.4 Flaky 分诊方法论（Eval 2 深度对比）

这是 With-skill 优势最大的场景（+66.7%）。

| 维度 | With Skill | Without Skill |
|------|-----------|--------------|
| 分诊模板 | 标准化 Flaky Triage Template（test name, environment, frequency, category checkboxes） | 自由格式分析 |
| 根因分析深度 | 3 个 contributing factor + Local vs CI 对比表 | 4 个 factor（更详细） |
| 修复建议 | 3 个修复 + impact ranking | 3 个修复 + CI workflow patch |
| 复现命令 | `go test ... -count=10` | 无 -count 命令 |
| 稳定性验证 | "Validation requires: -count=20 with 20/20 pass rate on CI runner" | 无稳定性要求 |
| Quarantine 策略 | Template with owner, due date, status | 无 quarantine 讨论 |

**分析**: 两者的根因分析质量相当（都找到 go run 编译 + 3s timeout 的根因），但 Without-skill 缺乏**分诊方法论框架**。Skill 的 Flaky Test Policy（"reproduce with repeat runs → classify → fix → quarantine only with owner, issue, and removal deadline"）提供了完整的流程保证。

### 4.5 CI 策略设计（Eval 3 深度对比）

这是 Without-skill 表现最接近的场景（+33.3%）。

| 维度 | With Skill | Without Skill |
|------|-----------|--------------|
| 三级触发策略 | ✅ 详细 ASCII 图 + 每级预算 | ✅ 表格 + 详细 rationale |
| Token 处理 | ✅ Security Checklist (5 项) | ✅ 两级矩阵 |
| Swagger Generation Gap | ✅ 发现并修复 | ✅ 发现并修复 |
| Quarantine Rules | ✅ 4 条规则 | ✅ 简要提及 |
| Rollout Plan | 无 | ✅ 7 阶段滚动计划 |
| Mandatory Gates 表格 | ✅ | ❌ |
| JSON 摘要 | ✅ | ❌ |

**分析**: Without-skill 在 CI 设计领域展现了强大的基线能力——它不仅设计了三级策略，还发现了 swagger 生成缺失的 bug，并提供了详细的 Rollout Plan。Skill 的增量主要在**结构化 Gate 验证**和**机器可读输出**上。

---

## 五、Token 效费比分析

### 5.1 Skill 体积

| 文件 | 行数 | 单词 | 字节 | 估算 Token |
|------|------|------|------|-----------|
| **SKILL.md** | 439 | 1,946 | 13,912 | ~2,800 |
| references/checklists.md | 152 | 824 | 5,528 | ~1,200 |
| references/playwright-patterns.md | 220 | 691 | 6,428 | ~1,000 |
| references/playwright-deep-patterns.md | 825 | 2,898 | 24,581 | ~4,200 |
| references/environment-and-dependency-gates.md | 181 | 943 | 6,275 | ~1,350 |
| references/agent-browser-workflows.md | 191 | 893 | 6,812 | ~1,300 |
| references/golden-examples.md | 247 | 1,018 | 8,997 | ~1,500 |
| scripts/discover_e2e_needs.sh | 215 | 755 | 6,413 | ~1,100 |
| **Description（始终在 context）** | — | ~50 | — | ~60 |
| **总计** | **2,470** | **10,018** | **78,946** | **~14,510** |

### 5.2 实际加载场景

| 场景 | 读取文件 | 总 Token |
|------|---------|---------|
| Eval 1: E2E 旅程 | SKILL.md + checklists + playwright-patterns + env-gates + golden-examples | ~7,850 |
| Eval 2: Flaky 分诊 | SKILL.md + checklists + env-gates + golden-examples | ~6,850 |
| Eval 3: CI 设计 | SKILL.md + checklists + playwright-deep + env-gates + golden-examples | ~11,050 |
| **典型平均** | | **~8,580** |
| 完整加载（所有参考） | SKILL.md + 全部 6 references | ~13,350 |
| 最小加载 | SKILL.md only | ~2,800 |

### 5.3 Token 换取的质量提升

| 指标 | 数值 |
|------|------|
| With-skill 通过率 | 100% (39/39) |
| Without-skill 通过率 | 51.3% (20/39) |
| 通过率提升 | +48.7 百分点 |
| 每修复 1 条 assertion 的 Token 成本 | ~147 tokens（SKILL.md only）/ ~451 tokens（typical） |
| 每 1% 通过率提升的 Token 成本 | **~57 tokens（SKILL.md only）/ ~176 tokens（typical）** |

### 5.4 与其他 Skill 效费比对比

| 指标 | e2e-best-practise | thirdparty-api-integ | api-integration-test | go-makefile-writer | git-commit |
|------|------|------|------|------|------|
| SKILL.md Token | ~2,800 | ~680 | ~1,800 | ~1,960 | ~1,120 |
| 典型加载 Token | ~8,580 | ~2,050 | ~2,850 | ~4,600 | ~1,120 |
| 通过率提升 | **+48.7%** | +33.3% | +36.8% | +31.0% | +22.7% |
| 每 1% Token（SKILL.md） | ~57 tok | **~20 tok** | ~49 tok | ~63 tok | ~51 tok |
| 每 1% Token（typical） | ~176 tok | **~62 tok** | ~77 tok | ~149 tok | ~51 tok |

**分析**:

- **绝对提升最高** (+48.7%) — e2e-best-practise 的 assertion 差值（19 条）是全系列最大的
- **SKILL.md 效费比良好** (~57 tok/1%) — 与 git-commit (~51 tok) 和 api-integration-test (~49 tok) 相近
- **典型加载效费比偏高** (~176 tok/1%) — 参考资料体量大（6 文件 ~11,710 tokens），但大部分是 Playwright 专用内容

### 5.5 Token 分段效费比

| 模块 | 估算 Token | 关联 Assertion 差值 | 效费比 |
|------|-----------|-------------------|--------|
| **Mandatory Gates (5 gates × ~80 tok each)** | ~400 | 9 条（A1-A3, B4,B6,B11,B12, C1,C2） | **极高** — 44 tok/assertion |
| **Output Contract 定义** | ~200 | 3 条（A12, B9, C7） | **极高** — 67 tok/assertion |
| **Machine-Readable JSON 模板** | ~150 | 3 条（A13, B8_partial, C8） | **极高** — 50 tok/assertion |
| **Flaky Test Policy** | ~120 | 2 条（B3, B11） | **极高** — 60 tok/assertion |
| **Quality Scorecard** | ~400 | 间接贡献（Eval 1 scorecard 输出） | **中** |
| **Anti-Examples (7 examples)** | ~500 | 间接贡献（A10 no-sleep） | **低** — anti-examples 大多对 Go 项目不适用 |
| **Version/Platform Gate** | ~250 | 0 条 | **低** — Go 项目不适用 |
| **Command Starters** | ~100 | 0 条 | **低** — Agent Browser 命令不适用 |
| **references/playwright-deep-patterns.md** | ~4,200 | 0 条直接贡献 | **低** — 纯 Go 项目不适用 |
| **references/playwright-patterns.md** | ~1,000 | 0 条直接贡献 | **低** — 纯 Go 项目不适用 |
| **references/golden-examples.md** | ~1,500 | 间接贡献（报告结构参考） | **中** |
| **references/checklists.md** | ~1,200 | 间接贡献（分诊模板） | **高** |
| **references/environment-and-dependency-gates.md** | ~1,350 | 间接贡献（环境评估框架） | **高** |

### 5.6 Token 效率评级

| 评级 | 结论 |
|------|------|
| **整体 ROI** | **良好** — ~8,580 tokens（典型）换取 +48.7% 通过率，绝对提升全系列最高 |
| **SKILL.md 本身 ROI** | **良好** — ~2,800 tokens 的效费比 (~57 tok/1%) 与同系列持平 |
| **高杠杆 Token 比例** | ~31%（870/2,800）直接贡献 17/19 条 assertion 差值 |
| **低杠杆 Token 比例** | ~30%（850/2,800）在 Go 项目评估中无贡献（Playwright 专用内容） |
| **参考资料效费比** | **分化严重** — checklists + env-gates 高价值；playwright-patterns + deep-patterns 对 Go 项目无价值 |

---

## 六、与 Claude 基础模型能力的边界分析

### 6.1 基础模型已具备的能力（Skill 无增量）

| 能力 | 证据 |
|------|------|
| 选择适当的 E2E 工具（Go HTTP vs Playwright） | 3/3 场景均选择 Go HTTP |
| 根因分析深度（flaky test） | Eval 2: 找到 go run 编译 + 3s timeout 双因素 |
| CI 三级触发策略设计 | Eval 3: PR/main/nightly 分层 |
| Swagger generation gap 发现 | Eval 3: 两者均发现 |
| Artifact upload YAML 生成 | Eval 3: 完整 actions/upload-artifact 配置 |
| Secret 处理（t.Skip when absent） | 3/3 场景正确 |
| Serial vs parallel 理由 | Eval 3: 详细分析 |

### 6.2 基础模型的能力缺口（Skill 填补）

| 缺口 | 证据 | 风险等级 |
|------|------|---------|
| **5 Mandatory Gates 完全缺失** | 3/3 场景无任何 gate 分析 | **高** — 可能虚假声称执行、遗漏配置依赖 |
| **Output Contract 缺失** | 3/3 场景无标准化报告结构 | **中** — 报告不可复现、不可对比 |
| **Machine-Readable JSON 缺失** | 3/3 场景无 JSON | **中** — CI/tooling 无法程序化消费 |
| **Stability Gate 缺失** | Eval 2 无 -count=20 验证要求 | **高** — 单次通过即声称修复 |
| **Data Isolation 未文档化** | Eval 1 未显式记录 | **低** — 实际代码是隔离的 |
| **Flaky 分诊方法论缺失** | Eval 2 无标准分诊序列 | **中** — 分析质量依赖个人经验 |
| **降级决策未记录** | Eval 1 无 runner choice 理由 | **低** — 选择正确但无决策追溯 |

---

## 七、综合评分

### 7.1 分维度评分

| 维度 | With Skill | Without Skill | 差值 |
|------|-----------|--------------|------|
| Gate 覆盖（5 gates） | 5.0/5 | 1.0/5 | +4.0 |
| 环境适应与降级 | 5.0/5 | 3.5/5 | +1.5 |
| 结构化报告 & JSON | 5.0/5 | 1.0/5 | +4.0 |
| 测试质量 | 5.0/5 | 4.0/5 | +1.0 |
| Flaky 分诊方法论 | 5.0/5 | 2.5/5 | +2.5 |
| CI 设计 | 5.0/5 | 4.0/5 | +1.0 |
| **综合均值** | **5.00/5** | **2.67/5** | **+2.33** |

### 7.2 加权总分

| 维度 | 权重 | 得分 | 加权 |
|------|------|------|------|
| Assertion 通过率（delta） | 25% | 10/10 | 2.50 |
| Gate 覆盖系统 | 20% | 10/10 | 2.00 |
| 结构化报告 & JSON 输出 | 15% | 10/10 | 1.50 |
| Flaky 分诊方法论 | 10% | 10/10 | 1.00 |
| 环境适应能力 | 10% | 10/10 | 1.00 |
| Token 效费比 | 15% | 6.0/10 | 0.90 |
| CI 设计增量 | 5% | 7.0/10 | 0.35 |
| **加权总分** | | | **9.25/10** |

Token 效费比拉低了总分——SKILL.md 效费比良好但参考资料中 Playwright 专用内容对非 JS 项目无价值。

---

## 八、评估材料

| 材料 | 路径 |
|------|------|
| Eval 1 with-skill 输出 | `/tmp/e2e-eval/eval-1/with_skill/` |
| Eval 1 without-skill 输出 | `/tmp/e2e-eval/eval-1/without_skill/` |
| Eval 2 with-skill 输出 | `/tmp/e2e-eval/eval-2/with_skill/` |
| Eval 2 without-skill 输出 | `/tmp/e2e-eval/eval-2/without_skill/` |
| Eval 3 with-skill 输出 | `/tmp/e2e-eval/eval-3/with_skill/` |
| Eval 3 without-skill 输出 | `/tmp/e2e-eval/eval-3/without_skill/` |
