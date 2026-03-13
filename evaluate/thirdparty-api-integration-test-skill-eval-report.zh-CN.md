# thirdparty-api-integration-test Skill 评审报告

> 评估框架: [skill-creator](https://github.com/anthropics/skills/tree/main/skills/skill-creator)
> 评估日期: 2026-03-11
> 评估对象: `thirdparty-api-integration-test`

---

`thirdparty-api-integration-test` 是一个为 Go 第三方 API 客户端编写和执行真实集成测试的 skill，适合验证供应商接口契约、排查外部调用故障，以及在真实运行时配置下做有边界的回归检查。它最突出的三个亮点是：先做严格的范围校验，能清楚区分第三方 API、内部 API 和单元测试，避免测试策略错配；对环境变量、运行时配置和生产环境访问有明确安全门禁，默认拒绝高风险执行路径；同时要求 build tag 隔离和结构化输出报告，使这类高成本测试更适合按需运行、结果也更容易沉淀。

## 一、评估概览

本次评估从**实际任务表现**和 **Token 效费比**两个维度对 thirdparty-api-integration-test skill 进行全面评审。设计 3 个场景（GitHub REST API 集成测试、OpenAI Responses API 集成测试、内部 webapp API 范围边界测试），每个场景分别运行 with-skill 和 without-skill 配置，共 3 场景 × 2 配置 = 6 次独立 subagent 运行，对照 36 条 assertion 进行评分。

| 维度 | With Skill | Without Skill | 差异 |
|------|-----------|--------------|------|
| **Assertion 通过率** | **36/36 (100%)** | 24/36 (66.7%) | **+33.3 百分点** |
| **Gate 环境变量隔离** | 3/3 全对 | 1/3 | 最大单项差异 |
| **Production Safety Gate** | 3/3 | 0/3 | Skill 独有 |
| **Build Tag 隔离** | 3/3 | 2/3 | Eval 2 without-skill 缺失 |
| **Output Contract 结构化报告** | 3/3 | 0/3 | Skill 独有 |
| **Scope 边界识别** | 4/4 | 0/4 | Skill 独有 |
| **Skill Token 开销（SKILL.md 单文件）** | ~680 tokens | 0 | — |
| **Skill Token 开销（含全部参考资料）** | ~1,660 tokens | 0 | — |
| **每 1% 通过率提升的 Token 成本** | ~20 tokens（SKILL.md only）/ ~50 tokens（full） | — | — |

---

## 二、测试方法

### 2.1 场景设计

| 场景 | 目标 | 核心考察点 | Assertions |
|------|------|-----------|-----------|
| Eval 1: GitHub REST client | `internal/github/rest_client.go`（5 个方法） | 标准第三方 API 集成测试：gate、安全门禁、断言质量 | 15 |
| Eval 2: OpenAI Responses API | `internal/converter/summary_openai.go`（Summarize 方法） | 付费 API 测试：API key 管理、i18n、超时边界 | 13 |
| Eval 3: Internal webapp (scope) | `internal/webapp/handler.go`（6 个 HTTP endpoint） | 范围边界识别：内部 API 不应套用第三方模式 | 8 |

### 2.2 执行方式

- With-skill 运行先读取 SKILL.md 及其引用的 4 个参考文件
- Without-skill 运行不读取任何 skill，按模型默认行为生成测试
- 所有运行在独立 subagent 中并行执行
- Eval 3 用于测试 skill 对内部 API 的范围识别能力

---

## 三、Assertion 通过率

### 3.1 总览

| 场景 | Assertions | With Skill | Without Skill | 差值 |
|------|-----------|-----------|--------------|------|
| Eval 1: GitHub REST | 15 | **15/15 (100%)** | 10/15 (66.7%) | +33.3% |
| Eval 2: OpenAI API | 13 | **13/13 (100%)** | 10/13 (76.9%) | +23.1% |
| Eval 3: Scope 边界 | 8 | **8/8 (100%)** | 4/8 (50.0%) | +50.0% |
| **总计** | **36** | **36/36 (100%)** | **24/36 (66.7%)** | **+33.3%** |

### 3.2 逐项 Assertion 详情

#### Eval 1: GitHub REST Client (15 assertions)

| # | Assertion | With | Without | 说明 |
|---|-----------|------|---------|------|
| A1 | `//go:build integration` build tag | ✅ | ✅ | |
| A2 | 独立 gate env var（GITHUB_INTEGRATION=1） | ✅ | ❌ | Without 仅用 GITHUB_TOKEN 作隐式 gate |
| A3 | Production safety gate（ENV=prod → skip） | ✅ | ❌ | Without 完全缺失 |
| A4 | GITHUB_TOKEN 从 env 读取 | ✅ | ✅ | |
| A5 | Actionable skip messages | ✅ | ✅ | |
| A6 | context.WithTimeout 包裹每个 API 调用 | ✅ | ✅ | |
| A7 | Protocol-level 断言（number match, non-nil） | ✅ | ✅ | |
| A8 | Business-level 断言（title, user, state 非空） | ✅ | ✅ | |
| A9 | 失败路径显式 error type/code 检查 | ✅ | ❌ | Without 仅 `err != nil`，无 `*statusError` 断言 |
| A10 | 使用 production code path（real client） | ✅ | ✅ | |
| A11 | No retry（或 bounded retry） | ✅ | ✅ | |
| A12 | 文件命名 `*_integration_test.go` | ✅ | ✅ | |
| A13 | Env var 验证（TrimSpace + ParseInt） | ✅ | ❌ | Without 无 TrimSpace |
| A14 | Test data lifecycle（稳定 fixtures, 可覆盖） | ✅ | ✅ | |
| A15 | Output Contract 结构化报告 | ✅ | ❌ | Without 仅普通摘要 |

#### Eval 2: OpenAI Responses API (13 assertions)

| # | Assertion | With | Without | 说明 |
|---|-----------|------|---------|------|
| B1 | `//go:build integration` build tag | ✅ | ❌ | Without 缺失 build tag，`go test ./...` 会触发 |
| B2 | 独立 gate env var | ✅ | ✅ | Both 使用了 gate |
| B3 | Production safety gate | ✅ | ❌ | Without 完全缺失 |
| B4 | OPENAI_API_KEY 从 env 读取 | ✅ | ✅ | |
| B5 | Actionable skip messages | ✅ | ✅ | |
| B6 | context.WithTimeout 包裹每个调用 | ✅ | ✅ | |
| B7 | Protocol-level 断言（Status == "ok"） | ✅ | ✅ | |
| B8 | Business-level 断言（Summary/Language/KeyDecisions） | ✅ | ✅ | |
| B9 | 失败路径测试（empty key, invalid key） | ✅ | ✅ | |
| B10 | 使用 production code path | ✅ | ✅ | |
| B11 | No retry（付费 API 默认不重试） | ✅ | ✅ | |
| B12 | Timeout 边界测试（expired context） | ✅ | ✅ | |
| B13 | Output Contract 结构化报告 | ✅ | ❌ | Without 仅普通摘要 |

#### Eval 3: Scope 边界测试 (8 assertions)

| # | Assertion | With | Without | 说明 |
|---|-----------|------|---------|------|
| C1 | 识别 target 为内部 API（非第三方） | ✅ | ❌ | Without 无 scope 概念 |
| C2 | 不应用 thirdparty 模式（build tag, gate） | ✅ | ✅ | |
| C3 | Report 标明 scope 判定 | ✅ | ❌ | Without 无 scope 分析 |
| C4 | 推荐正确 skill（$api-integration-test） | ✅ | ❌ | Without 无 skill 推荐概念 |
| C5 | 使用 httptest 模式 | ✅ | ✅ | |
| C6 | 未错误添加 THIRDPARTY_INTEGRATION gate | ✅ | ✅ | |
| C7 | 测试覆盖内部 endpoints | ✅ | ✅ | |
| C8 | 提供清晰的 scope 边界解释 | ✅ | ❌ | Without 无 scope 分析 |

### 3.3 Without-Skill 失败的 12 条 Assertion 归类

| 失败类型 | 次数 | 涉及 Eval | 说明 |
|---------|------|----------|------|
| **Production Safety Gate 缺失** | 2 | Eval 1, 2 | 均无 ENV=prod 保护，直接运行可能误触生产环境 |
| **Gate Env Var 缺失或隐式** | 1 | Eval 1 | 仅用 GITHUB_TOKEN 隐式 gate，无专用开关变量 |
| **Build Tag 缺失** | 1 | Eval 2 | `go test ./...` 会意外触发 OpenAI 集成测试 |
| **缺少结构化 Output Contract** | 2 | Eval 1, 2 | 无 gate vars、failure classification、missing prerequisites |
| **Error Type/Code 不精确** | 1 | Eval 1 | 404 路径仅 `err != nil`，未检查 `*statusError` |
| **Env Var 验证不规范** | 1 | Eval 1 | 无 TrimSpace，前后空格可导致误判 |
| **Scope 识别能力缺失** | 4 | Eval 3 | 无 scope 分析、无替代 skill 推荐 |

### 3.4 风险矩阵：Without-Skill 缺失项的实际影响

| 缺失项 | 风险等级 | 实际场景 |
|--------|---------|---------|
| Production Safety Gate | **高** | `ENV=prod` 时测试直接调用生产第三方 API，可能消耗配额、产生费用、触发限流 |
| Build Tag 缺失 | **高** | Eval 2 无 tag → `go test ./...` 调用 OpenAI API → 每次 CI 消耗 API 额度 |
| Gate Env Var 隐式 | **中** | 只要 GITHUB_TOKEN 存在就运行 → 开发者的 shell 通常已配置 token |
| Error Type 不精确 | **中** | 404 回归变成 500 时 `err != nil` 仍通过，无法区分错误类型变化 |
| Env Var 无 TrimSpace | **低** | 环境变量尾部空格导致 gate 判断错误（罕见但存在） |

---

## 四、逐维度对比分析

### 4.1 Gate 环境变量设计

这是**实用价值最高**的差异维度。

| 场景 | With Skill | Without Skill |
|------|-----------|--------------|
| GitHub REST | `GITHUB_INTEGRATION=1` + `GITHUB_TOKEN` 二级 gate | 仅 `GITHUB_TOKEN` 隐式 gate |
| OpenAI API | `OPENAI_INTEGRATION=1` + `OPENAI_API_KEY` 二级 gate | `ISSUE2MD_OPENAI_INTEGRATION=1` + `OPENAI_API_KEY` |

**分析**: With-skill 始终使用**显式二级 gate**（开关变量 + 凭证变量分离），Without-skill 在 Eval 1 中仅依赖凭证变量，这意味着开发者 shell 中已有 `GITHUB_TOKEN` 时，运行 `go test -tags=integration ./...` 会意外触发。

Skill 的模式 "Add explicit run gate env var, otherwise `t.Skip(...)`" 解决了这个安全设计问题。

### 4.2 Production Safety Gate

| 场景 | With Skill | Without Skill |
|------|-----------|--------------|
| Eval 1 | ✅ `ENV=prod → t.Skip` | ❌ 完全缺失 |
| Eval 2 | ✅ `ENV=prod → t.Skip` | ❌ 完全缺失 |

**分析**: 这是 **Skill 独有**的安全机制，Without-skill 在两个场景中均未实现。对于第三方 API 测试（尤其是付费的 OpenAI API），缺少生产保护可能导致：
- 测试在生产环境中意外执行
- 消耗真实 API 配额和费用
- 触发供应商限流策略

### 4.3 Build Tag 隔离

| 场景 | With Skill | Without Skill |
|------|-----------|--------------|
| Eval 1 | `//go:build integration` + `// +build integration` | `//go:build integration` |
| Eval 2 | `//go:build integration` + `// +build integration` | ❌ 无 build tag |

**分析**: Eval 2 的 Without-skill 输出完全**缺少 build tag**，这意味着 `go test ./...` 会编译并运行 OpenAI 集成测试。对付费 API 而言，这是一个严重问题——每次 CI 运行都可能产生 API 费用。

With-skill 始终输出双 build tag（新旧格式），确保向后兼容性。

### 4.4 错误断言精度

| 维度 | With Skill | Without Skill |
|------|-----------|--------------|
| Eval 1 404 路径 | `errors.As(err, &stErr)` + `stErr.StatusCode == 404` | `err != nil` |
| Eval 2 auth 失败 | `strings.Contains(err.Error(), "status 4")` | `strings.Contains(err.Error(), "status 4")` |

Skill 的规则 "For expected failure paths, assert explicit error type/code (not only `require.Error`)" 在 Eval 1 中产生了显著差异。With-skill 使用 `errors.As` 检查具体的 `*statusError` 类型和 404 状态码，而 Without-skill 仅检查 `err != nil`。

**实际价值**: 如果 GitHub API 的 404 响应格式发生变化（例如返回 403 而非 404），Without-skill 的测试会继续通过而掩盖问题。

### 4.5 Output Contract（结构化报告）

With-skill 在每次运行后产出包含以下内容的报告：

| 报告项 | Eval 1 | Eval 2 | Eval 3 |
|--------|--------|--------|--------|
| Integration target 详细信息 | ✅ | ✅ | ✅ |
| Gate variable 完整列表 | ✅（10 vars） | ✅（6 vars） | ✅（N/A） |
| Exact run commands | ✅ | ✅ | ✅ |
| Timeout / Retry policy | 30s / none | 30s / none | 10s / none |
| Result summary（pass/fail/skip） | ✅ | ✅ | ✅ |
| Failure classification | N/A | N/A | N/A |
| Missing prerequisites | ✅ | ✅ | ✅ |
| Checklist compliance | ✅ | ✅ | — |
| Scope determination | — | — | ✅ |

Without-skill 产出简洁的任务摘要，但无 gate variable 表格、无 failure classification 分类、无 missing prerequisites 列表。

### 4.6 Scope 边界识别（Eval 3）

这是本次评估中**最突出的差异化能力**。

With-skill 在 Eval 3 中：
1. 读取 `internal/webapp/handler.go` 后**主动识别**为内部 API
2. 明确声明 "OUT OF SCOPE for thirdparty-api-integration-test skill"
3. 提供**逐步 gate 评估表格**证明不适用
4. 推荐正确的 `$api-integration-test` skill
5. 仍然生成了**高质量的内部 API 测试**（httptest 模式）

Without-skill 直接生成了高质量的 webapp 测试（25 个测试函数，覆盖全部 endpoint），但**无任何 scope 分析**。

**分析**: Skill 的 scope 限定来自 SKILL.md 中的 "Validate external API integration end-to-end" 和 "Apply to any third-party API integration" 声明。虽然 SKILL.md **没有显式的 scope validation gate**（不像 `api-integration-test` 的 "Scope Validation Gate" 段落），agent 仍然能从上下文推断出范围边界。这说明 SKILL.md 的隐式 scope 定义足以引导 agent 做出正确判断。

---

## 五、Token 效费比分析

### 5.1 Skill 体积

| 文件 | 行数 | 单词 | 字节 | 估算 Token |
|------|------|------|------|-----------|
| **SKILL.md** | 80 | 482 | 3,699 | ~680 |
| references/common-integration-gate.md | 38 | 209 | 1,513 | ~370 |
| references/common-output-contract.md | 19 | 96 | 658 | ~150 |
| references/checklists.md | 31 | 184 | 1,397 | ~280 |
| references/vendor-examples.md | 99 | 326 | 3,094 | ~570 |
| **Description（始终在 context）** | — | ~30 | — | ~40 |
| **总计** | **267** | **1,327** | **10,361** | **~2,090** |

**典型加载场景:**

| 场景 | 读取文件 | 总 Token |
|------|---------|---------|
| 完整加载（所有参考） | SKILL.md + 4 references | ~2,050 |
| 标准加载（无 vendor 示例） | SKILL.md + gate + contract + checklists | ~1,480 |
| 最小加载 | SKILL.md | ~680 |

### 5.2 Token 换取的质量提升

| 指标 | 数值 |
|------|------|
| With-skill 通过率 | 100% (36/36) |
| Without-skill 通过率 | 66.7% (24/36) |
| 通过率提升 | +33.3 百分点 |
| 每修复 1 条 assertion 的 Token 成本 | ~57 tokens（SKILL.md only）/ ~171 tokens（full） |
| 每 1% 通过率提升的 Token 成本 | **~20 tokens（SKILL.md only）/ ~50 tokens（full）** |

### 5.3 与姊妹 Skill 效费比对比

| 指标 | thirdparty-api-integration-test | api-integration-test | go-makefile-writer | git-commit |
|------|------|------|------|------|
| SKILL.md Token | ~680 | ~1,800 | ~1,960 | ~1,120 |
| 总加载 Token | ~2,050 | ~2,850 | ~4,600 | ~1,120 |
| 通过率提升 | +33.3% | +36.8% | +31.0% | +22.7% |
| 每 1% 的 Token（SKILL.md） | **~20 tok** | ~49 tok | ~63 tok | ~51 tok |
| 每 1% 的 Token（full） | **~62 tok** | ~77 tok | ~149 tok | ~51 tok |

**分析**: thirdparty-api-integration-test 的 SKILL.md **Token 效费比为全系列最优**，仅 ~680 tokens 的 SKILL.md 就实现了 +33.3% 的通过率提升。这得益于：
1. SKILL.md 极度精简（80 行 vs api-integration-test 的 290 行）
2. 关键规则高度密集——13 条 Required Pattern 覆盖了全部核心差异
3. 参考资料设计合理——vendor-examples.md 提供了可直接复制的模板

### 5.4 Token 分段效费比

| 模块 | 估算 Token | 关联 Assertion 差值 | 效费比 |
|------|-----------|-------------------|--------|
| **Required Pattern §3-5（gate + prod safety + env validation）** | ~80 | 5 条（A2,A3,A13,B1,B3） | **极高** — 16 tok/assertion |
| **Required Pattern §12（explicit error type/code）** | ~20 | 1 条（A9） | **极高** — 20 tok/assertion |
| **Output Contract 指针** | ~15 | 2 条（A15,B13） | **极高** — 8 tok/assertion |
| **common-output-contract.md** | ~150 | 间接支撑 Output Contract 质量 | **高** |
| **Scope 定义（"Apply to any third-party API integration"）** | ~30 | 4 条（C1,C3,C4,C8） | **极高** — 8 tok/assertion |
| **common-integration-gate.md** | ~370 | 间接支撑 gate 设计一致性 | **高** |
| **checklists.md** | ~280 | 间接支撑测试质量完整性 | **中** |
| **vendor-examples.md** | ~570 | 间接支撑模板一致性（MCS/USS 模板） | **中** — 对 issue2md 项目无直接匹配 |

### 5.5 高杠杆 vs 低杠杆指令

**高杠杆（~145 tokens SKILL.md → 12 条 assertion 差值）:**
- Gate + prod safety + env validation 规则（80 tok → 5 条）
- Explicit error type/code 规则（20 tok → 1 条）
- Scope 定义（30 tok → 4 条）
- Output Contract 指针（15 tok → 2 条）

**中杠杆（~535 tokens SKILL.md → 间接贡献）:**
- Vendor-Specific Safety Additions（~150 tok）— 驱动 idempotent 偏好、rate-limit 意识
- Safety Rules 总结（~130 tok）— 强化安全约束
- Configuration Gate 指针（~25 tok）— 引导读取详细 gate 文档
- References 区（~230 tok）— 指向全部参考资料

**低杠杆（~570 tokens 参考资料 → 有限贡献）:**
- vendor-examples.md（~570 tok）— MCS/USS 模板对 issue2md 无直接映射

### 5.6 Token 效率评级

| 评级 | 结论 |
|------|------|
| **整体 ROI** | **优秀** — ~2,050 tokens 换取 +33.3% 通过率 |
| **SKILL.md 本身 ROI** | **卓越** — ~680 tokens 包含全部高杠杆规则，效费比全系列最优 |
| **高杠杆 Token 比例** | ~21%（145/680）直接贡献全部 12 条 assertion 差值 |
| **低杠杆 Token 比例** | vendor-examples.md 占总预算 27%，对当前项目无直接映射 |
| **参考资料效费比** | **高** — gate + contract 参考文件小而精，vendor-examples 偏大 |

---

## 六、与 Claude 基础模型能力的边界分析

### 6.1 基础模型已具备的能力（Skill 无增量）

| 能力 | 证据 |
|------|------|
| context.WithTimeout 包裹 API 调用 | 3/3 场景均正确 |
| Protocol-level 断言（number match, non-nil） | 3/3 场景正确 |
| Business-level 断言（non-empty fields） | 3/3 场景正确 |
| 文件命名 `*_integration_test.go` | 2/2 API 场景正确 |
| 使用 production code path（real client） | 3/3 场景正确 |
| No retry 默认策略 | 3/3 场景正确 |
| 基本 actionable skip messages | 3/3 场景正确 |
| httptest.NewServer 用于内部 API | 1/1 场景正确 |
| 稳定 fixture + 覆盖能力 | 2/2 API 场景正确 |

### 6.2 基础模型的能力缺口（Skill 填补）

| 缺口 | 证据 | 风险等级 |
|------|------|---------|
| **Production Safety Gate 缺失** | 2/2 API 场景无 ENV=prod 保护 | **高** — 生产环境误触发可消耗配额 |
| **Build Tag 不一致** | 1/2 API 场景缺失 build tag | **高** — `go test ./...` 触发付费 API |
| **Gate Env Var 隐式** | 1/2 场景仅用凭证作 gate | **中** — 凭证存在即触发 |
| **Error Type 不精确** | 1/2 场景仅 `err != nil` | **中** — 无法区分错误类型变化 |
| **Env Var 无 TrimSpace** | 1/2 场景无验证 | **低** — 尾部空格导致误判 |
| **无结构化 Output Report** | 2/2 场景无报告 | **中** — 缺少审计追溯 |
| **Scope 识别能力** | 1/1 场景无 scope 分析 | **低** — 仍生成了合适的测试 |

---

## 七、综合评分

### 7.1 分维度评分

| 维度 | With Skill | Without Skill | 差值 |
|------|-----------|--------------|------|
| Gate 与安全门禁 | 5.0/5 | 2.0/5 | +3.0 |
| Build Tag 隔离 | 5.0/5 | 3.5/5 | +1.5 |
| 断言质量（protocol + business + error） | 5.0/5 | 3.5/5 | +1.5 |
| Env Var 验证与 test data lifecycle | 5.0/5 | 4.0/5 | +1.0 |
| 结构化报告 | 5.0/5 | 1.0/5 | +4.0 |
| Scope 边界识别 | 5.0/5 | 1.0/5 | +4.0 |
| **综合均值** | **5.00/5** | **2.50/5** | **+2.50** |

### 7.2 加权总分

| 维度 | 权重 | 得分 | 加权 |
|------|------|------|------|
| Assertion 通过率（delta） | 25% | 9.5/10 | 2.38 |
| Gate 与安全门禁 | 20% | 10/10 | 2.00 |
| Build Tag 隔离与一致性 | 10% | 10/10 | 1.00 |
| 断言质量与错误精度 | 10% | 10/10 | 1.00 |
| 结构化报告（Output Contract） | 10% | 10/10 | 1.00 |
| Scope 边界识别 | 10% | 10/10 | 1.00 |
| Token 效费比 | 15% | 9.5/10 | 1.43 |
| **加权总分** | | | **9.81/10** |

---

## 八、评估材料

| 材料 | 路径 |
|------|------|
| Eval 1 with-skill 输出 | `/tmp/tp-integ-eval/eval-1/with_skill/` |
| Eval 1 without-skill 输出 | `/tmp/tp-integ-eval/eval-1/without_skill/` |
| Eval 2 with-skill 输出 | `/tmp/tp-integ-eval/eval-2/with_skill/` |
| Eval 2 without-skill 输出 | `/tmp/tp-integ-eval/eval-2/without_skill/` |
| Eval 3 with-skill 输出 | `/tmp/tp-integ-eval/eval-3/with_skill/` |
| Eval 3 without-skill 输出 | `/tmp/tp-integ-eval/eval-3/without_skill/` |
