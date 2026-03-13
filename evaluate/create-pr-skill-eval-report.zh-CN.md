# create-pr Skill 评估报告

> 评估框架: [skill-creator](https://github.com/anthropics/skills/tree/main/skills/skill-creator)
> 评估日期: 2026-03-11
> 评估对象: `create-pr`

---

`create-pr` 是一个面向主分支提 PR 的结构化交付 skill，用于在提交前完成分支卫生检查、质量验证、安全扫描和 PR 内容生成，目标是产出可审阅、可追溯、可安全合并的高质量 PR。它最突出的三个亮点是：以 8 个强制 Gate 串起完整 preflight 流程，避免未验证变更直接进入评审；通过 `confirmed / likely / suspected` 三档置信度模型决定 draft 或 ready 状态，降低误判风险；同时提供固定章节的 PR Body 模板，把测试证据、风险说明和未覆盖项表达得更完整、更一致。

## 1. Skill 概述

`create-pr` 是一个结构化的 PR 创建 skill，定义了 8 个强制 Gate（A-H）、3 级置信度模型、非协商规则、以及包含 8 个必需章节的 PR Body 模板。其目标是确保每个 PR 在推送前经过完整的预检、质量验证、安全扫描和提交规范检查。

**核心组件**:

| 文件 | 行数 | 职责 |
|------|------|------|
| `SKILL.md` | 373 | 主技能定义（Gate 流程、规则、模板引用） |
| `references/pr-body-template.md` | 55 | PR Body 8 段式模板 |
| `references/create-pr-checklists.md` | 59 | 各阶段 Checklist |
| `references/create-pr-config.example.yaml` | 59 | 仓库级配置示例 |
| `scripts/create_pr.py` | 1449 | 一键执行脚本（Gate 运行 + PR 创建） |
| `scripts/tests/test_create_pr.py` | 276 | 脚本单元测试 |

---

## 2. 测试设计

### 2.1 场景定义

| # | 场景名称 | 分支 | 核心挑战 | 期望结果 |
|---|----------|------|----------|----------|
| 1 | 干净的功能特性 | `feat/add-word-count` | 小型 Go 变更，规范提交，所有检查应通过 | ready, confirmed |
| 2 | 糟糕的提交规范 | `quick-fix` | 非 CC 格式提交消息 + 不规范分支名 | draft, suspected |
| 3 | 安全敏感变更 | `fix/token-handling` | 代码中硬编码 `ghp_` GitHub Token | draft, suspected |

### 2.2 断言矩阵（34 项）

**场景 1 — 干净功能特性 (13 项)**

| ID | 断言 | With-Skill | Without-Skill |
|----|------|:----------:|:-------------:|
| A1 | 系统化运行所有 Gate A-G（带命令证据） | PASS | FAIL |
| A2 | Gate A: 检查 auth、remote、base branch | PASS | FAIL |
| A3 | Gate B: 检查分支命名规范 | PASS | FAIL |
| A4 | Gate C: 变更大小分类（≤400行 = normal） | PASS | FAIL |
| A5 | Gate D: 运行 tests + lint 并记录结果 | PASS | PARTIAL |
| A6 | Gate E: 对变更文件运行安全扫描 | PASS | FAIL |
| A7 | Gate F: 检查文档/兼容性 | PASS | PARTIAL |
| A8 | Gate G: 校验 Conventional Commits 格式 | PASS | FAIL |
| A9 | PR 标题遵循 CC 格式（≤50 字符） | PASS | PASS |
| A10 | PR Body 包含全部 8 个必需章节 | PASS | FAIL |
| A11 | 明确声明 Confidence Level | PASS | FAIL |
| A12 | 基于 Gate 结果做出 draft/ready 决策 | PASS | FAIL |
| A13 | 输出遵循 Output Contract | PASS | FAIL |

**场景 2 — 糟糕的提交规范 (10 项)**

| ID | 断言 | With-Skill | Without-Skill |
|----|------|:----------:|:-------------:|
| B1 | 系统化运行所有 Gate A-G | PASS | FAIL |
| B2 | Gate B: 警告分支命名不规范 | PASS | FAIL |
| B3 | Gate D: 运行 tests + lint | PASS | PARTIAL |
| B4 | Gate G: 标记非 CC 格式的提交消息 | PASS | PASS |
| B5 | PR 标题遵循 CC 格式 | PASS | PARTIAL |
| B6 | PR Body 包含全部 8 个必需章节 | PASS | FAIL |
| B7 | 明确声明 Confidence Level | PASS | FAIL |
| B8 | 基于 Gate 失败推荐 draft | PASS | PASS |
| B9 | 识别新函数缺少单元测试 | PASS | PASS |
| B10 | 输出遵循 Output Contract（结构化 Gate 判定） | PASS | FAIL |

**场景 3 — 安全敏感变更 (11 项)**

| ID | 断言 | With-Skill | Without-Skill |
|----|------|:----------:|:-------------:|
| C1 | 系统化运行所有 Gate A-G | PASS | FAIL |
| C2 | Gate E: 明确检测到硬编码 ghp_ Token | PASS | PASS |
| C3 | Gate E: 标记为阻塞性安全问题 | PASS | PASS |
| C4 | Confidence = suspected（多个 Gate 失败） | PASS | FAIL |
| C5 | 推荐 draft 状态 | PASS | PASS |
| C6 | PR 标题遵循 CC 格式 | PASS | PASS |
| C7 | PR Body 包含全部 8 个必需章节 | PASS | FAIL |
| C8 | Security Notes 章节具体指出 Token 问题 | PASS | PARTIAL |
| C9 | 输出包含结构化 Uncovered Risk List | PASS | FAIL |
| C10 | 明确建议不要推送/创建 PR 直到移除密钥 | PASS | PARTIAL |
| C11 | 输出遵循 Output Contract | PASS | FAIL |

---

## 3. 通过率对比

### 3.1 总体通过率

| 配置 | 通过 | 部分通过 | 失败 | 通过率 |
|------|------|---------|------|--------|
| **With Skill** | 34 | 0 | 0 | **100%** |
| **Without Skill** | 10 | 5 | 19 | **29%** (含 PARTIAL 按 0.5 计 = 37%) |

**通过率提升: +71 百分点**（含 PARTIAL 时 +63pp）

### 3.2 按场景通过率

| 场景 | With-Skill | Without-Skill | 差异 |
|------|:----------:|:-------------:|:----:|
| 1. 干净功能特性 | 13/13 (100%) | 2/13 (15%) | +85pp |
| 2. 糟糕的提交规范 | 10/10 (100%) | 3.5/10 (35%) | +65pp |
| 3. 安全敏感变更 | 11/11 (100%) | 4.5/11 (41%) | +59pp |

### 3.3 实质性维度（不依赖流程结构的核心能力）

为排除"流程断言偏差"，额外评估 12 项与流程无关的实质性检查：

| ID | 检查项 | With-Skill | Without-Skill |
|----|--------|:----------:|:-------------:|
| S1 | 场景 1: 运行测试并通过 | PASS | PASS |
| S2 | 场景 1: 运行 lint 检查 | PASS | FAIL |
| S3 | 场景 1: 安全扫描（rg/gosec/govulncheck） | PASS | FAIL |
| S4 | 场景 1: PR 标题 CC 格式 | PASS | PASS |
| S5 | 场景 2: 分支命名问题标记 | PASS | FAIL |
| S6 | 场景 2: 提交消息问题标记 | PASS | PASS |
| S7 | 场景 2: 缺少 GoDoc 标记 | PASS | PASS |
| S8 | 场景 2: 缺少测试标记 | PASS | PASS |
| S9 | 场景 3: 硬编码 Token 检测 | PASS | PASS |
| S10 | 场景 3: 标记为 draft/阻塞 | PASS | PASS |
| S11 | 场景 3: 多工具交叉验证 | PASS | FAIL |
| S12 | 全部: 结构化 PR Body | PASS | FAIL |

**实质性通过率**: With-Skill **12/12 (100%)** vs Without-Skill **7/12 (58%)**，提升 **+42pp**。

---

## 4. 关键差异分析

### 4.1 With-Skill 独有的行为（Baseline 完全缺失）

| 行为 | 影响 |
|------|------|
| **系统化 8-Gate 流程** | 每个 Gate 明确执行、带命令证据、判定 PASS/FAIL/SUPPRESSED |
| **Gate A: GitHub 认证预检** | 验证 `gh auth status`、`gh repo view`、分支保护规则 |
| **Gate B: 分支命名规范检查** | 自动检测 `quick-fix` 不符合 `type/short-description` 模式 |
| **Gate C: 变更风险分类** | 按行数分级（≤400/401-800/>800），标记高风险区域 |
| **Gate E: 多工具安全扫描** | `rg` 正则 + `gosec` + `govulncheck` 三重交叉验证 |
| **Confidence 置信度模型** | confirmed/likely/suspected 三级判定，直接关联 draft/ready |
| **Output Contract** | 结构化报告：Gate 结果 → Uncovered Risk → PR 元数据 → Next Actions |
| **PR Body 8 段式模板** | Problem, What Changed, Why, Risk/Rollback, Test Evidence, Security, Breaking Changes, Reviewer Checklist |

### 4.2 Baseline 能做到但质量较低的行为

| 行为 | With-Skill 质量 | Without-Skill 质量 |
|------|-----------------|-------------------|
| 安全问题检测 | 3 工具交叉验证，结构化报告 | 代码审查发现，但无工具证据 |
| 提交消息校验 | 精确格式检查 + 字符数计算 | 能识别问题但不计算长度 |
| 测试运行 | `make test` + `golangci-lint` + `go build` | 仅 `make test`（偶尔 `go vet`） |
| PR Body | 8 段完整结构 | 自由格式，缺少关键章节 |
| Draft/Ready 决策 | 基于 Gate 判定的形式化推理 | 基于直觉的主观判断 |

### 4.3 场景级关键发现

**场景 1（干净功能）**:
- With-Skill: 全部 7 个 Gate 通过，confidence = confirmed，推荐 ready。运行了 `gosec`、`govulncheck`、`golangci-lint` 等完整工具链。
- Without-Skill: 仅运行 `make test` + `go vet`，无安全扫描。错误地推荐 draft（基于 YAGNI 考虑而非 Gate 失败）。

**场景 2（糟糕提交）**:
- With-Skill: Gate B 警告分支命名，Gate D 检测 lint 失败（缺少 GoDoc），Gate G 检测非 CC 提交消息。confidence = suspected，推荐 draft。提供 6 步修复计划。
- Without-Skill: 识别了提交消息和 GoDoc 问题，但未检测分支命名问题，未运行 lint 工具，无结构化 Gate 判定。

**场景 3（安全敏感）**:
- With-Skill: Gate E 通过 `rg`/`gosec`/`golangci-lint` 三重检测到 `ghp_` Token，生成详细安全报告，包含 CWE 编号、严重级别、修复建议、Token 吊销步骤。明确阻止 push/create。
- Without-Skill: 通过代码审查发现 Token，正确标记为 CRITICAL，但无工具证据链，无 CWE 引用，修复建议不够具体。

---

## 5. Token 效费比分析

### 5.1 Skill 上下文 Token 成本

| 组件 | 行数 | 估算 Token 数 | 加载时机 |
|------|------|-------------|----------|
| `SKILL.md` | 373 | ~2,500 | 始终加载 |
| `pr-body-template.md` | 55 | ~400 | 按需引用 |
| `create-pr-checklists.md` | 59 | ~500 | 按需引用 |
| `create-pr-config.example.yaml` | 59 | ~350 | 按需引用 |
| **典型场景总计** | ~487 | **~3,400** | SKILL.md + template + checklists |

注：`scripts/create_pr.py`（1449 行，~10,000 tokens）仅在使用脚本模式时加载，不计入默认上下文。

### 5.2 效费比计算

| 指标 | 值 |
|------|------|
| 总体通过率提升 | +71pp（严格）/ +63pp（含 PARTIAL） |
| 实质性通过率提升 | +42pp |
| Skill 上下文成本 | ~3,400 tokens |
| **每 1% 通过率提升的 Token 成本（总体）** | **~48 tokens/1%** |
| **每 1% 通过率提升的 Token 成本（实质性）** | **~81 tokens/1%** |

### 5.3 与其他 Skill 效费比对比

| Skill | Token 成本 | 通过率提升 | Tokens/1% |
|-------|-----------|-----------|-----------|
| `git-commit` | ~1,150 | +22pp | ~51 |
| `go-makefile-writer` | ~1,960 (SKILL.md) / ~4,300 (full) | +31pp | ~63-139 |
| **`create-pr`** | **~3,400** | **+71pp** | **~48** |

`create-pr` 在 tokens/1% 指标上表现最优，主要因为其 **通过率差异极大**（+71pp）——Baseline 在 PR 创建场景中严重缺乏结构化流程，使得 skill 的边际价值极高。

### 5.4 Token 回报曲线分析

```
投入 Token 量与回报的映射关系:

~2,500 tokens (SKILL.md only):
  → 获得: Gate 流程、Non-Negotiables、Confidence 模型、Command Playbook
  → 预计覆盖: ~90% 的通过率提升

+400 tokens (pr-body-template.md):
  → 获得: 8 段式 PR Body 模板
  → 预计覆盖: +8% 的通过率提升（PR Body 结构断言）

+500 tokens (checklists):
  → 获得: 各阶段 Checklist
  → 预计覆盖: +2% 的通过率提升（边际价值较低）
```

SKILL.md 本身提供了约 90% 的价值，参考文件提供剩余 10%。

---

## 6. 综合评分

### 6.1 分维度评分

| 维度 | With Skill | Without Skill | 差值 |
|------|-----------|--------------|------|
| Gate 执行完整度（A-G 系统化 + 命令证据） | 5.0/5 | 1.5/5 | +3.5 |
| PR Body 结构化质量（8 段模板） | 5.0/5 | 2.0/5 | +3.0 |
| 安全扫描能力（多工具交叉验证） | 5.0/5 | 2.0/5 | +3.0 |
| Confidence/Draft 决策准确性 | 5.0/5 | 3.0/5 | +2.0 |
| Commit 规范合规检查 | 5.0/5 | 2.5/5 | +2.5 |
| 结构化输出报告（Output Contract） | 5.0/5 | 1.0/5 | +4.0 |
| **综合均值** | **5.0/5** | **2.0/5** | **+3.0** |

**维度得分说明**:

- **Gate 执行完整度**: With-Skill 在 3 个场景中均系统化运行 7 个 Gate，每个 Gate 附带精确命令和输出证据。Without-Skill 仅运行 `make test`（偶尔 `go vet`），无 auth 验证、分支命名检查、风险分类或安全扫描工具。
- **PR Body 结构化质量**: With-Skill 全部产出包含 8 个必需章节（Problem/Context、What Changed、Why、Risk/Rollback、Test Evidence、Security Notes、Breaking Changes、Reviewer Checklist）。Without-Skill 产出自由格式 Body，普遍缺少 Risk/Rollback、Security Notes、Breaking Changes 等关键章节。
- **安全扫描能力**: With-Skill 使用 `rg` 正则 + `gosec` + `govulncheck` 三重交叉验证。在场景 3 中，三个工具独立检测到 `ghp_` Token（含 CWE-798 编号）。Without-Skill 仅通过代码审查发现 Token，无工具证据链。
- **Confidence/Draft 决策**: With-Skill 3/3 场景决策正确（场景 1: confirmed→ready; 场景 2: suspected→draft; 场景 3: suspected→draft）。Without-Skill 场景 1 错误推荐 draft（基于 YAGNI 而非 Gate 结果），场景 2/3 推荐 draft（正确但缺乏形式化推理）。
- **Commit 规范合规**: With-Skill Gate G 精确验证 CC 格式、计算字符数、检查语气。在场景 2 中识别 3 项违规（缺少 type(scope):、过去时态、无结构化格式）。Without-Skill 场景 2 能识别问题但无字符计数和精确格式校验。
- **结构化输出报告**: With-Skill 严格遵循 Output Contract（Gate 判定 → Uncovered Risk → PR 元数据 → Next Actions）。Without-Skill 无结构化输出，无 Gate 判定摘要表。

### 6.2 加权总分

| 维度 | 权重 | 得分 | 理由 | 加权 |
|------|------|------|------|------|
| Assertion 通过率（delta） | 25% | 10.0/10 | +71pp（总体）/ +42pp（实质性），三个 skill 中最大差异 | 2.50 |
| Gate 执行完整度 | 20% | 10.0/10 | 3/3 场景全部 7 Gate 系统化执行 + 命令证据 | 2.00 |
| PR Body 结构化质量 | 15% | 10.0/10 | 3/3 场景全部 8 段完整 + 证据表格 | 1.50 |
| 安全扫描能力 | 15% | 9.5/10 | 三重工具验证优秀；可增加更多正则模式 | 1.43 |
| Token 效费比 | 15% | 7.5/10 | ~48 tok/1% 最优，但 ~30% 内容未使用（脚本、Monorepo、合并策略） | 1.13 |
| Confidence/Draft 决策准确性 | 10% | 10.0/10 | 3/3 场景决策正确，形式化推理清晰 | 1.00 |
| **加权总分** | **100%** | | | **9.55/10** |

### 6.3 与其他 Skill 综合评分对比

| Skill | 加权总分 | 通过率 delta | Tokens/1% | 最大优势维度 |
|-------|---------|-------------|-----------|-------------|
| **create-pr** | **9.55/10** | +71pp | ~48 | Gate 流程 (+3.5)、Output Contract (+4.0) |
| go-makefile-writer | 9.16/10 | +31pp | ~63 | CI 可复现性 (+3.0)、Output Contract (+4.0) |
| git-commit | — | +22pp | ~51 | — |

`create-pr` 获得三个 skill 中的 **最高综合评分**，主要因为：

1. **通过率差异极大**（+71pp）：PR 创建是 Baseline 模型最薄弱的领域
2. **分维度评分无短板**：6 个维度中 5 个获得满分，仅 Token 效费比因 ~30% 内容冗余未达满分
3. **Token 效费比最优**（~48 tok/1%）：尽管绝对 Token 量较大（~3,400），但因通过率差异极大，单位成本反而最低

**失分点**: Token 效费比维度（7.5/10）是唯一明显低于满分的项，主要原因：
- Bundled Script 段落（~500 tokens）占 SKILL.md 14% 但无 agent 使用
- Merge Strategy Guidance（~200 tokens）在非 Squash 场景无价值
- Monorepo Support（~80 tokens）对单模块仓库无用

---

## 7. 结论

`create-pr` skill 是本次评估中 **通过率差异最大** 的 skill（+71pp），同时在 tokens/1% 指标上也最优（~48 tokens/1%）。这表明 PR 创建是一个 Baseline 模型 **高度缺乏结构化能力** 的领域，skill 的边际价值极高。

**核心价值点**:
1. **8-Gate 强制流程**：确保安全扫描、lint、auth 等步骤不被跳过
2. **Confidence 模型**：将 draft/ready 决策从主观判断变为形式化推理
3. **多工具交叉验证**：Gate E 的 rg + gosec + govulncheck 三重检测在场景 3 中表现突出
4. **8 段式 PR Body**：标准化输出使 Reviewer 体验一致

**主要风险**: SKILL.md 中约 30% 的内容（脚本说明、Monorepo、合并策略）在典型场景中未被使用，可通过模块化精简进一步优化 token 效费比。
