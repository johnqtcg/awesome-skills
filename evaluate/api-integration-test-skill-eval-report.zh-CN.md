# api-integration-test Skill 评审报告

> 评估框架: [skill-creator](https://github.com/anthropics/skills/tree/main/skills/skill-creator)
> 评估日期: 2026-03-11
> 评估对象: `api-integration-test`

---

`api-integration-test` 是一个面向 Go 内部 HTTP / gRPC API 的集成测试 skill，用于创建、维护和执行带门禁的真实配置集成测试，重点覆盖接口契约验证、故障排查和安全可控执行。它最突出的三个亮点是：先做严格的作用域判断，能明确区分内部 API、第三方 API 和单元测试场景；内置 Production Safety Gate 与配置完整性门禁，默认拒绝不安全或条件不足的执行路径；同时要求 build tag 隔离和结构化输出报告，使测试既便于安全接入 CI，也便于后续诊断和审计。

## 一、评估概览

本次评估从**实际任务表现**和 **Token 效费比**两个维度对 api-integration-test skill 进行全面评审。设计 3 个场景（内部 API 标准测试、第三方 API 作用域拒绝、综合模式升级），每个场景分别运行 with-skill 和 without-skill 配置，共 3 场景 × 2 配置 = 6 次独立 subagent 运行，对照 38 条 assertion 进行评分。

| 维度 | With Skill | Without Skill | 差异 |
|------|-----------|--------------|------|
| **Assertion 通过率** | **36/38 (94.7%)** | 22/38 (57.9%) | **+36.8 百分点** |
| **Production Safety Gate** | 3/3 全对 | 0/3 | Skill 独有 |
| **Build Tag 隔离** | 3/3 全对 | 0/3 | Skill 独有 |
| **Output Contract 结构化报告** | 3/3 全对 | 0/3 | Skill 独有 |
| **作用域识别能力** | ✅ 识别第三方 API | ❌ 无作用域意识 | Skill 独有 |
| **Skill Token 开销（SKILL.md 单文件）** | ~2,100 tokens | 0 | — |
| **Skill Token 开销（含全部参考资料）** | ~6,000 tokens | 0 | — |
| **典型加载开销** | ~3,500 tokens | 0 | — |
| **每 1% 通过率提升的 Token 成本** | ~57 tokens (SKILL.md) / ~95 tokens (典型) | — | — |

---

## 二、测试方法

### 2.1 场景设计

| 场景 | 目标 | 核心考察点 | Assertions |
|------|------|-----------|-----------|
| Eval 1: 内部 webapp API（Standard 模式） | `internal/webapp` HTTP 端点 | build tag、环境门禁、生产安全、协议+业务断言、Output Contract | 15 |
| Eval 2: 第三方 API 作用域拒绝 | `internal/github` REST 客户端 | 作用域验证门禁、重定向到正确 skill、是否生成测试代码 | 8 |
| Eval 3: 综合模式升级 | 已有集成测试 → Comprehensive | 并发安全、大载荷测试、超时策略、完整 Output Contract | 15 |

### 2.2 执行方式

- issue2md 项目源码作为所有场景的真实代码上下文
- With-skill 运行先读取 SKILL.md 及其引用的参考资料
- Without-skill 运行不读取任何 skill，按模型默认行为生成
- 所有运行在独立 subagent 中执行，输出保存到 `/tmp/api-integ-eval/`

### 2.3 issue2md 项目关键上下文

- **Go 版本**: 1.25.8
- **内部 API**: `internal/webapp`（5 个端点：`/`、`/convert`、`/openapi.json`、`/swagger`、`/swagger/index.html`）
- **第三方客户端**: `internal/github`（REST + GraphQL 调用 api.github.com）
- **已有集成测试**: `tests/integration/http/web_api_integration_test.go`（httptest.NewRecorder + fake fetcher）
- **门禁环境变量**: `ISSUE2MD_API_INTEGRATION=1`

---

## 三、Assertion 通过率

### 3.1 总览

| 场景 | Assertions | With Skill | Without Skill | 差值 |
|------|-----------|-----------|--------------|------|
| Eval 1: 内部 webapp API | 15 | **15/15 (100%)** | 11/15 (73.3%) | +26.7% |
| Eval 2: 第三方 API 作用域 | 8 | **6/8 (75%)** | 2/8 (25.0%) | +50.0% |
| Eval 3: 综合模式升级 | 15 | **15/15 (100%)** | 9/15 (60.0%) | +40.0% |
| **总计** | **38** | **36/38 (94.7%)** | **22/38 (57.9%)** | **+36.8%** |

### 3.2 Without-Skill 失败的 16 条 Assertion 归类

| 失败类型 | 次数 | 涉及 Eval | 说明 |
|---------|------|----------|------|
| **缺少 `//go:build integration` build tag** | 3 | Eval 1/2/3 | 测试会在 `go test ./...` 中编译和跳过，浪费编译时间 |
| **缺少 Production Safety Gate** | 3 | Eval 1/2/3 | 若 ENV=prod 且误设门禁变量，测试会在生产环境执行 |
| **缺少 Output Contract 结构化报告** | 3 | Eval 1/2/3 | 无执行模式、降级等级、变量清单的结构化输出 |
| **无作用域识别能力** | 3 | Eval 2 | 对第三方 API 直接生成测试，无任何 scope 判断 |
| **缺少 Execution Mode 声明** | 2 | Eval 1/3 | 无 Standard/Comprehensive 模式声明 |
| **缺少 context.WithTimeout 覆盖** | 1 | Eval 3 | 使用 `http.Post` 直接调用，无上下文超时 |
| **缺少 Quality Scorecard** | 1 | Eval 3 | 无预编写/代码质量检查清单 |

### 3.3 With-Skill 失败的 2 条 Assertion 分析

| Assertion | 场景 | 分析 |
|-----------|------|------|
| 作用域门禁未硬停止 | Eval 2 | Agent 识别了 GitHub API 是第三方，但以"评估任务"为由继续生成测试代码 |
| 未完全阻止测试代码生成 | Eval 2 | 虽然报告中明确标注了 Scope Note，但仍产出了完整的 `_integration_test.go` 文件 |

**根因分析**: Skill 的 Scope Validation Gate 描述为 "redirect to `$thirdparty-api-integration-test`, stop"，但缺乏 **硬停止机制**（类似 fuzzing-test skill 的 "If item 2 or 3 fails → stop, do not write tests"）。Agent 有充分的作用域意识但选择了 "best effort" 继续执行。

---

## 四、逐维度对比分析

### 4.1 Build Tag 隔离（`//go:build integration`）

这是 **3 个场景均失败** 的维度，影响最广。

| 场景 | With Skill | Without Skill |
|------|-----------|--------------|
| Eval 1 | `//go:build integration` + `// +build integration` | ❌ 无 build tag |
| Eval 2 | `//go:build integration` + `// +build integration` | ❌ 无 build tag |
| Eval 3 | `//go:build integration` + `// +build integration` | ❌ 无 build tag |

**实际价值**: 缺少 build tag 意味着:
- `go test ./...` 会编译集成测试文件及其依赖（即使最终 t.Skip）
- 增加 CI 编译时间
- 若测试引用了特殊依赖（如 service container 包），在无该依赖的环境会编译失败

### 4.2 Production Safety Gate

| 场景 | With Skill | Without Skill |
|------|-----------|--------------|
| Eval 1 | `ENV=prod` → `t.Skip` unless `INTEGRATION_ALLOW_PROD=1` | ❌ 无 |
| Eval 2 | `ENV=prod` → `t.Skip` unless `INTEGRATION_ALLOW_PROD=1` | ❌ 无 |
| Eval 3 | `ENV=prod` → `t.Skip` unless `INTEGRATION_ALLOW_PROD=1` | ❌ 无 |

**实际价值**: 这是**安全关键维度**。Without-skill 的测试在 `ISSUE2MD_API_INTEGRATION=1` 且 `ENV=production` 的环境中会执行，可能对生产服务发起请求。Skill 的双重门禁（gate + prod safety）提供纵深防御。

### 4.3 Output Contract（结构化报告）

With-skill 在每次运行后产出包含以下内容的报告：

| 报告项 | Eval 1 | Eval 2 | Eval 3 |
|--------|--------|--------|--------|
| Execution Mode | Standard | Standard | Comprehensive |
| Integration Target | 5 endpoints | 5 REST methods | 5 endpoints |
| Degradation Level | Full | Full | Full |
| Gate Variables 清单 | 3 vars | 8 vars | 3 vars |
| Exact Commands | ✅ | ✅ | ✅ |
| Timeout/Retry Policy | 15s/无 | 15s/无 | 30s/无 |
| Result Summary | 15 pass | 8 skip | 38 pass |
| Failure Classification | N/A | N/A | N/A |
| Quality Scorecard | ✅ 完整 | ✅ 完整 | ✅ 完整 |

Without-skill 产出简洁的文本摘要，无结构化字段。

### 4.4 作用域验证（Eval 2 特有）

| 维度 | With Skill | Without Skill |
|------|-----------|--------------|
| 识别 GitHub API 为第三方 | ✅（明确标注 Scope Note） | ❌ |
| 提及正确的替代 skill | ✅ (`$thirdparty-api-integration-test`) | ❌ |
| 硬停止，不生成测试代码 | ❌（以评估名义继续） | ❌（直接生成） |
| 作用域解释 | ✅（报告中详细说明） | ❌ |

**分析**: With-skill 的作用域意识远优于 baseline（3/4 vs 0/4 作用域相关 assertions），但未实现硬停止。Skill 的 Gate 1 指令 "redirect to `$thirdparty-api-integration-test`, stop" 在当前措辞下不够有约束力——agent 有足够的"理由"绕过它。

### 4.5 context.WithTimeout 覆盖

| 场景 | With Skill | Without Skill |
|------|-----------|--------------|
| Eval 1 | 每个 HTTP 调用均有 15s context | 通过 helper 5s context ✅ |
| Eval 2 | 每个 API 调用均有 15s context | 30s `http.Client.Timeout` ⚠️ |
| Eval 3 | 每个请求均有 30s context | `http.Post` 直接调用，无 context ❌ |

**分析**: Without-skill 在 Eval 3 中使用了 `http.Post` 和 `http.Get`，这些便捷函数不接受 context 参数。Skill 的模式要求 "Guard each external call with `context.WithTimeout`"，确保超时行为一致且可测试。

---

## 五、Skill 差异化能力

### 5.1 Skill 独有能力（Without-Skill 从未表现出的）

| 能力 | 描述 | 出现次数 |
|------|------|---------|
| **Build Tag 隔离** | `//go:build integration` 在文件顶部 | 3/3 |
| **Production Safety Gate** | `ENV=prod` → `t.Skip` 双重门禁 | 3/3 |
| **Output Contract** | 9 个必填字段的结构化报告 | 3/3 |
| **作用域验证** | 识别内部 vs 第三方 API，建议重定向 | 1/1 |
| **Quality Scorecard** | Pre-Authoring + Test Quality 双检查清单 | 3/3 |
| **Execution Mode 声明** | Smoke/Standard/Comprehensive 自动选择 | 3/3 |
| **Degradation Level** | Full/Scaffold/Blocked 降级判断 | 3/3 |

### 5.2 双方均表现良好的能力

| 能力 | With Skill | Without Skill |
|------|-----------|--------------|
| 环境变量门禁 | 3/3 | 3/3 |
| 协议级断言（HTTP status） | 3/3 | 3/3 |
| 业务级断言（响应内容） | 3/3 | 3/3 |
| 成功+失败路径覆盖 | 3/3 | 3/3 |
| 可操作的 Skip 消息 | 3/3 | 3/3 |
| 文件命名规范 | 3/3 | 3/3 |
| 运行命令提供 | 3/3 | 3/3 |

### 5.3 Skill 优势趋势：随提示信息密度变化

| 提示信息密度 | Eval | With-Skill 优势 |
|-------------|------|-----------------|
| 标准提示（中等信息） | Eval 1 | +26.7% |
| 作用域边界提示（高信息） | Eval 2 | +50.0% |
| 显式 Comprehensive 提示（高信息） | Eval 3 | +40.0% |

Skill 在**作用域边界判断**场景中优势最大（+50%），因为作用域验证是纯 skill 知识，模型默认不具备此判断力。

---

## 六、Token 效费比分析

### 6.1 Skill 文件 Token 预估

| 文件 | 行数 | 预估 Tokens |
|------|------|------------|
| `SKILL.md` | 336 | ~2,100 |
| `references/common-integration-gate.md` | 97 | ~600 |
| `references/common-output-contract.md` | 30 | ~200 |
| `references/checklists.md` | 98 | ~600 |
| `references/internal-api-patterns.md` | 415 | ~2,500 |
| **全量加载** | **976** | **~6,000** |

### 6.2 典型加载场景

Skill 的 Reference Loading Gate 规定按需加载参考资料：

| 场景 | 加载的文件 | Token 开销 |
|------|----------|-----------|
| HTTP 标准测试 | SKILL.md + gate + output + checklists + api-patterns | ~6,000 |
| 仅作用域判断（被拒绝） | SKILL.md + gate + output | ~2,900 |
| 结果报告 | SKILL.md + output | ~2,300 |
| **典型（标准 HTTP 测试）** | **全量** | **~6,000** |

**注意**: 当前 skill 的 Reference Loading Gate 设计导致大多数 HTTP 测试场景会加载全部参考资料（因为 `internal-api-patterns.md` 在 HTTP 场景中总是触发）。典型加载 ≈ 全量加载。

### 6.3 效费比计算

| 指标 | 值 |
|------|-----|
| With-Skill 通过率 | 94.7% |
| Without-Skill 通过率 | 57.9% |
| 提升幅度 | +36.8 百分点 |
| SKILL.md Token 成本 | ~2,100 |
| 全量加载 Token 成本 | ~6,000 |
| **每 1% 提升的 Token 成本（SKILL.md）** | **~57 tokens** |
| **每 1% 提升的 Token 成本（全量）** | **~163 tokens** |

### 6.4 与其他 Skill 的效费比对比

| Skill | 通过率提升 | SKILL.md Tokens | 每 1% 成本 |
|-------|----------|----------------|-----------|
| go-makefile-writer | +31.0% | ~1,960 | ~63 |
| **api-integration-test** | **+36.8%** | **~2,100** | **~57** |
| fuzzing-test | +54.3% | ~2,250 | ~41 |
| go-ci-workflow | +33.0% | ~1,500 | ~45 |

api-integration-test 的 SKILL.md-only 效费比（57 tokens/1%）处于合理范围。但全量加载效费比（163 tokens/1%）偏高，主要因为 `internal-api-patterns.md`（2,500 tokens）在几乎所有场景都会被加载。

---

## 七、综合评分

### 7.1 评分维度与权重

| 维度 | 权重 | 得分 | 加权分 |
|------|------|------|--------|
| 安全门禁（build tag + prod safety） | 25% | 10.0 | 2.50 |
| 测试代码质量（protocol + business 断言） | 20% | 9.5 | 1.90 |
| 作用域验证能力 | 15% | 7.5 | 1.13 |
| Output Contract 完整度 | 15% | 10.0 | 1.50 |
| Token 效费比 | 10% | 7.5 | 0.75 |
| 实际通过率提升 | 10% | 9.5 | 0.95 |
| Execution Mode 自动选择 | 5% | 9.0 | 0.45 |
| **加权总分** | **100%** | — | **9.18 / 10** |

### 7.2 分项说明

- **安全门禁 (10.0)**: 3/3 场景 build tag + prod safety gate 全对，这是 Without-Skill 完全缺失的维度
- **测试代码质量 (9.5)**: 协议+业务断言完整，context.WithTimeout 覆盖一致，-0.5 因为 Eval 1 的 httptest.NewServer 模式与 Eval 3 重复
- **作用域验证 (7.5)**: 识别了 GitHub API 为第三方并提供了详细说明，但未实现硬停止（-2.5）
- **Output Contract (10.0)**: 所有 9 个必填字段在 3 个场景中均完整输出
- **Token 效费比 (7.5)**: SKILL.md 效费比优秀（57 tokens/1%），但全量加载偏高（163 tokens/1%），主要因为 `internal-api-patterns.md` 体积大
- **通过率提升 (9.5)**: +36.8pp 是显著提升，尤其在安全维度
- **Mode 自动选择 (9.0)**: 正确选择了 Standard 和 Comprehensive 模式

---

## 八、逐 Eval 详细评分

### Eval 1: 内部 webapp API — Standard 模式

| # | Assertion | With Skill | Without Skill |
|---|-----------|:---:|:---:|
| 1 | `//go:build integration` build tag | ✅ | ❌ |
| 2 | Gate env var check (`ISSUE2MD_API_INTEGRATION=1`) | ✅ | ✅ |
| 3 | Production safety gate (`ENV=prod` → `t.Skip`) | ✅ | ❌ |
| 4 | `context.WithTimeout` on HTTP calls | ✅ | ✅ |
| 5 | Protocol-level assertion (HTTP status codes) | ✅ | ✅ |
| 6 | Business-level assertion (response content/fields) | ✅ | ✅ |
| 7 | Success path test case | ✅ | ✅ |
| 8 | Expected-failure path test case | ✅ | ✅ |
| 9 | Actionable skip messages | ✅ | ✅ |
| 10 | File naming `*_integration_test.go` | ✅ | ✅ |
| 11 | No hardcoded secrets/endpoints | ✅ | ✅ |
| 12 | Execution mode stated (Standard) | ✅ | ❌ |
| 13 | Degradation level stated (Full) | ✅ | ❌ |
| 14 | Output Contract with mandatory fields | ✅ | ❌ |
| 15 | Exact run command provided | ✅ | ✅ |
| | **合计** | **15/15** | **11/15** |

### Eval 2: 第三方 API 作用域拒绝

| # | Assertion | With Skill | Without Skill |
|---|-----------|:---:|:---:|
| 1 | 识别 GitHub API 为第三方 | ✅ | ❌ |
| 2 | 提及 `$thirdparty-api-integration-test` | ✅ | ❌ |
| 3 | 硬停止，不生成测试代码 | ❌ | ❌ |
| 4 | 提供明确的作用域解释 | ✅ | ❌ |
| 5 | Build tag `//go:build integration`（若生成测试） | ✅ | ❌ |
| 6 | Production safety gate（若生成测试） | ✅ | ❌ |
| 7 | `context.WithTimeout` on calls（若生成测试） | ✅ | ✅ |
| 8 | Actionable skip messages（若生成测试） | ✅ | ✅ |
| | **合计** | **6/8** | **2/8** |

### Eval 3: 综合模式升级 — Comprehensive

| # | Assertion | With Skill | Without Skill |
|---|-----------|:---:|:---:|
| 1 | `//go:build integration` build tag | ✅ | ❌ |
| 2 | Gate env var check | ✅ | ✅ |
| 3 | Production safety gate | ✅ | ❌ |
| 4 | Concurrent request safety test | ✅ | ✅ |
| 5 | Large payload test (1MB MaxBytesReader) | ✅ | ✅ |
| 6 | All error status codes (400, 401, 403, 404, 429, 502) | ✅ | ✅ |
| 7 | `context.WithTimeout` on all HTTP calls | ✅ | ❌ |
| 8 | Response header assertions | ✅ | ✅ |
| 9 | Protocol-level assertions | ✅ | ✅ |
| 10 | Business-level assertions | ✅ | ✅ |
| 11 | Execution mode stated (Comprehensive) | ✅ | ❌ |
| 12 | Timeout documented (30s) | ✅ | ❌ |
| 13 | Output Contract present | ✅ | ❌ |
| 14 | Run command with comprehensive timeout | ✅ | ✅ |
| 15 | Quality Scorecard | ✅ | ❌ |
| | **合计** | **15/15** | **9/15** |

---

## 九、总结

api-integration-test skill 以 ~2,100 tokens (SKILL.md) 的成本实现了 +36.8 百分点的通过率提升，在安全维度（build tag 隔离 + production safety gate）和结构化输出（Output Contract + Quality Scorecard）方面表现出完全的差异化优势。作用域验证能力是 skill 的独特价值——baseline 对第三方 API 毫无判断力，而 skill 能识别并给出重定向建议。

主要改进方向：强化 Scope Validation Gate 的硬停止语义（当前是"建议"而非"强制"），以及精简 `internal-api-patterns.md` 的体积以优化全量加载的效费比。
