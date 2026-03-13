# unit-test Skill 评审报告

> 评估框架: [skill-creator](https://github.com/anthropics/skills/tree/main/skills/skill-creator)
> 评估日期: 2026-03-11
> 评估对象: `unit-test`

---

`unit-test` 是一个面向 Go 仓库的单元测试生成与优化 skill，适合新增或补强逻辑测试、修复低信号测试，以及为并发、边界和映射类缺陷设计更有针对性的测试用例。它最突出的三个亮点是：触发准确率高，能稳定区分单测、benchmark、fuzz、集成测试等相邻任务；强调失败假设、Killer Case 和边界清单，把测试目标从“刷覆盖率”拉回“抓真实 bug”；同时坚持 table-driven、`t.Run`、race 检测和项目断言风格适配，让测试既规范又贴近现有代码库实践。

## 一、评估概览

本次评估从**触发准确率**和**实际任务表现**两个维度对 unit-test skill 进行全面评审。实际任务表现覆盖 3 个不同类型的 Go 并发/时间敏感目标代码，每个目标代码分别运行 with-skill 和 without-skill 配置，共 3 个场景 × 2 配置 = 6 次独立 subagent 运行，对照 34 条 assertion 进行评分。

| 维度 | With Skill | Without Skill | 差异 |
|------|-----------|--------------|------|
| **触发准确率** | 20/20 (100%) | — | Recall 10/10, Precision 10/10 |
| **Assertion 通过率** | **34/34 (100%)** | 21/34 (61.6%) | **+38.4 百分点** |
| **功能覆盖（核心路径）** | 全覆盖 | 全覆盖 | 无差异 |
| **方法论产出（假设列表/Killer Case/边界清单）** | **全覆盖** | **零覆盖** | **决定性差异** |
| **测试组织（table-driven + t.Run）** | 3/3 | 0/3 | Skill 一致执行 |

---

## 二、触发准确率

### 2.1 测试方法

设计 20 条测试查询（10 条应触发 / 10 条不应触发），覆盖中英文、多种单测场景和容易混淆的近似任务（benchmark、fuzz test、集成测试、E2E、CI 配置、mock 生成、文档写作、翻译、pprof 分析）。使用独立 subagent 模拟 Cursor 的 `<agent_skills>` 触发路径，每条查询做 3 轮独立判断，共 60 次判断。

> **关于 `run_eval.py` 失败说明**: skill-creator 提供的 `run_eval.py` 脚本在 Cursor IDE 内无法正常工作——`claude -p` 子进程因认证上下文丢失而静默失败（错误: "Your organization does not have access to Claude"），导致所有 60 次查询都返回 `triggered=false`，产出无意义的 0% Recall / 50% Accuracy。本报告的触发评估改用 Task subagent 模拟方法，每轮由全新上下文的独立 agent 评估。

### 2.2 结果

```
总准确率:  20/20 (100%)
Recall:    10/10 (100%) — 所有正例查询全部正确触发（3 轮一致）
Precision: 10/10 (100%) — 所有负例查询均正确排除（3 轮一致）
F1:        100%
总判断数:  60/60 (TP=30, FN=0, FP=0, TN=30)
```

### 2.3 正例查询（全部正确触发）

| # | 查询 | 判断 | 触发理由 |
|---|------|------|---------|
| 1 | 帮我给 service.go 写单元测试…并发下会出问题 | ✅ | "写单元测试" + 并发场景 |
| 2 | I need unit tests for jwt.go…expiry boundary…zero coverage | ✅ | unit test + coverage gate |
| 3 | 单测挂了，TestUserService_Create/duplicate_email… | ✅ | fix test + 测试排错 |
| 4 | handler_test.go 全是 TestXxx，想重构成 table-driven + t.Run | ✅ | table-driven + 补测试 |
| 5 | coverage 掉到 62% 了，CI 卡住了…针对性补几个测试 | ✅ | coverage gate + 补测试 |
| 6 | MapReduce 函数…空切片和单元素…能不能写几个测试验证 | ✅ | "verify this function works" |
| 7 | sync.Pool 包装器…想确认并发场景下没有 data race…用 -race 跑 | ✅ | -race + check for race conditions |
| 8 | 给 retry.go 加上 unit test…重试次数边界、context 取消 | ✅ | unit test + 边界场景 |
| 9 | 请帮我写测试验证 middleware chain 的执行顺序… | ✅ | "写测试" + 验证函数 |
| 10 | 帮我 review 一下 service_test.go 的测试质量…killer case | ✅ | review tests + 测试质量 |

### 2.4 负例查询（全部正确排除）

| # | 查询 | 判断 | 排除理由 |
|---|------|------|---------|
| 11 | 帮我写个 benchmark 对比 sync.Map… -benchmem | ✅ | benchmark，不是单测 |
| 12 | 需要写集成测试验证 UserRepository 和真实 MySQL… | ✅ | integration test，不是单测 |
| 13 | 给 json_parser.go 写个 fuzz test… go test -fuzz | ✅ | fuzz test，不是单测 |
| 14 | 帮我配置 GitHub Actions CI workflow… | ✅ | CI 配置，不是写测试 |
| 15 | 用 mockgen 给 UserStore 接口生成 mock 文件… | ✅ | mock generation，不是写测试 |
| 16 | 帮我写一个 E2E 测试…chromedp 或 playwright… | ✅ | E2E test，不是单测 |
| 17 | 压测 gRPC 接口…用 ghz 工具跑 10 秒… | ✅ | load test，不是单测 |
| 18 | 帮我写一篇关于 Go 测试策略的技术文档… | ✅ | 文档写作，不是写测试 |
| 19 | 帮我把 gocore/map/ 目录下的 markdown 翻译成英文… | ✅ | 翻译，完全无关 |
| 20 | 帮我分析一下 pprof 的 CPU profile 数据… | ✅ | 性能分析，不是写测试 |

### 2.5 结论

改进后的 Description 采用了四层策略来确保触发准确率：

1. **不可替代性信号** — "references/ with killer-case pattern templates"、"cannot be reproduced from memory"、"mandatory 13-check tiered scorecard" 让模型判断自身知识不足以替代 skill
2. **强命令语气** — "ALWAYS read this skill before writing, reviewing, or fixing ANY Go test file (_test.go)"
3. **广覆盖触发词** — 中英文 12 个关键词 + 4 种间接触发模式（verify、check for race conditions、improve test quality、coverage is too low）
4. **明确排除范围** — "Do NOT use for benchmarks, fuzz tests, integration tests, E2E tests, load tests, or mock generation" 有效隔离了 6 类相邻任务

---

## 三、实际任务表现

### 3.1 测试方法

选取仓库中 3 个无现有测试的 Go 代码文件，涵盖不同的测试难点：

| 场景 | 目标代码 | 测试难点 | Assertions 数 |
|------|---------|---------|-------------|
| Eval 1: resilience.Do | `designpattern/circuitbreaker/resilience/resilience.go` | 组合限流+熔断+重试，多组件交互、上下文传播、重试边界 | 11 |
| Eval 2: WorkerPool | `designpattern/bulkhead/pool/pool.go` | 并发 worker pool，goroutine 泄漏、double-Shutdown 安全、任务丢失 | 11 |
| Eval 3: Limiter | `designpattern/circuitbreaker/ratelimiter/ratelimiter.go` | 令牌桶限流器，时间敏感测试、并发竞争、浮点精度 | 12 |

每个场景各运行 1 个 with-skill + 1 个 without-skill subagent，共 6 次运行。

### 3.2 Assertion 通过率总览

| 场景 | Assertions | With Skill | Without Skill | 差值 |
|------|-----------|-----------|--------------|------|
| Eval 1: resilience.Do | 11 | **11/11 (100%)** | 7/11 (63.6%) | +36.4% |
| Eval 2: WorkerPool | 11 | **11/11 (100%)** | 6/11 (54.5%) | +45.5% |
| Eval 3: Limiter | 12 | **12/12 (100%)** | 8/12 (66.7%) | +33.3% |
| **总计** | **34** | **34/34 (100%)** | **21/34 (61.6%)** | **+38.4%** |

### 3.3 逐项对比: 哪些 Assertion 拉开了差距？

Without-skill 在所有 3 个场景中未通过的 13 条 assertion 可归类为 4 个方法论维度：

| 失败类型 | 次数 | 失败的 Assertion |
|---------|------|-----------------|
| **Failure Hypothesis List** | 3 | 3 个场景全部缺失——无正式的缺陷假设表 |
| **Killer Cases** | 3 | 3 个场景全部缺失——无以命名缺陷假设驱动的 killer case |
| **Table-driven + t.Run** | 3 | 3 个场景全部使用独立 TestXxx 函数，而非子测试组织 |
| **Boundary Checklist** | 4 | 3 个场景全部缺失 + Eval 2 额外缺失 goroutine leak 讨论 |

**关键观察**: Without-skill 的全部 13 条失败 assertion 都属于 **方法论层面**，不是功能覆盖层面。

### 3.4 功能覆盖对比

在「代码的哪些路径被测试到了」这个维度上，两者差异不大：

| 功能路径 | With Skill | Without Skill |
|---------|-----------|--------------|
| **Eval 1 核心路径** | | |
| 限流拒绝 (ErrRateLimited) | ✅ | ✅ |
| 熔断打开 (ErrBreakerOpen) | ✅ | ✅ |
| 上下文取消（backoff 期间） | ✅ | ✅ |
| 重试边界 (MaxRetries=0/1) | ✅ | ✅ |
| -race 通过 | ✅ | ✅ |
| **Eval 2 核心路径** | | |
| TrySubmit 队列满返回 false | ✅ | ✅ |
| Shutdown 排空任务 | ✅ | ✅ |
| Double-Shutdown 安全 | ✅ | ✅ |
| 并发 Submit 压力测试 | ✅ | ✅ |
| -race 通过 | ✅ | ✅ |
| **Eval 3 核心路径** | | |
| 初始突发容量 | ✅ | ✅ |
| 令牌耗尽 | ✅ | ✅ |
| 令牌补充 | ✅ | ✅ |
| 突发上限 | ✅ | ✅ |
| 并发 Allow() | ✅ | ✅ |
| -race 通过 | ✅ | ✅ |

**结论: 功能覆盖率两者一致。** Without-skill 并非测试了更少的代码路径，而是缺少了围绕这些路径的方法论框架。

---

## 四、Skill 差异化价值深度分析

### 4.1 Failure Hypothesis List（缺陷假设列表）

**With Skill**: 每个场景生成 7-9 个编号假设（H1-H9），按类别（Branching、Concurrency、Loop/index、Context/time）组织，每个假设映射到具体测试用例。

**Without Skill**: 无此产出。测试按功能区域组织（Rate Limiting、Success Paths、Retry Exhaustion），但没有正式的缺陷分析。

| 对比维度 | With Skill | Without Skill |
|---------|-----------|--------------|
| 假设数量 | Eval1: 9, Eval2: 7, Eval3: 9 | 0, 0, 0 |
| 缺陷→测试映射 | 每个假设标注 Covered By | 无 |
| 覆盖分析 | 可追溯哪些缺陷被测到了 | 只能看到哪些路径被跑了 |

**实际价值**: Failure Hypothesis List 的意义不在于「多写了一张表」，而在于它驱动了测试设计方向——**先思考「这段代码可能有什么 bug」，再据此设计测试**，而非「按函数签名铺覆盖率」。

### 4.2 Killer Cases（致命用例）

**With Skill**: 每个场景 3-4 个 killer case，每个包含：
- 链接的缺陷假设（如 KC1→H3）
- 故障注入描述
- 关键断言（带具体字段和值）
- **Removal Risk Statement**（"如果删除这个断言，什么 bug 会逃逸"）

示例（Eval 1 KC1）:

> **Linked hypothesis**: H3 — ErrBreakerOpen is retried instead of returned immediately
> **Critical assertion**: `backoffCalls == 0` — no retry backoff was triggered
> **Removal risk**: If removed, the known bug (ErrBreakerOpen not short-circuiting retries) can escape detection — 4 unnecessary backoff+retry cycles would occur.

**Without Skill**: 测试覆盖了同样的路径（如 TestDo_BreakerOpenStopsRetry），但没有 removal risk 分析。开发者无法判断哪个断言是「防止回归的关键」、哪个是「锦上添花」。

### 4.3 Boundary Checklist（边界清单）

**With Skill**: 标准 12 项清单，每项标注 Covered / N/A + 说明：

| # | Item | Status |
|---|------|--------|
| 1 | nil input | Covered — nil Limiter, nil Backoff |
| 2 | Empty value | N/A |
| 3 | Single element (len==1) | Covered — MaxRetries=1 |
| 4 | Size boundary (n=2, n=3, last) | Covered — MaxRetries=0,2,3,-1 |
| ... | ... | ... |

**Without Skill**: 无此产出。边界场景零散分布在各个测试函数中，缺少系统化的审计。

### 4.4 测试组织: table-driven vs 独立函数

| 维度 | With Skill | Without Skill |
|------|-----------|--------------|
| 组织方式 | t.Run 子测试（TestDo/12 subtests） | 17 个独立 TestXxx 函数 |
| Parallel | t.Parallel() | 无 |
| 命名规范 | 蛇形命名，动词+期望（`rate_limited_returns_ErrRateLimited`） | 帕斯卡命名（`TestDo_RateLimited`） |
| 可维护性 | 新增 case 只需加一行表项 | 新增 case 需要新函数 + setup 重复 |

### 4.5 Auto Scorecard（13 检查项记分卡）

With-skill 的输出包含结构化的 13 项记分卡（3 Critical + 5 Standard + 5 Hygiene），附通过/失败证据和层级汇总。Without-skill 无此产出。

### 4.6 额外发现

With-skill 运行发现了代码中的**真实洞察**，without-skill 未提及：

| 发现 | 场景 | 说明 |
|------|------|------|
| worker pool quit channel 死代码 | Eval 2 | worker 的 `select` 中 `quit` 分支在 `close(tasks)` + `range` 模式下永远不会触发 |
| `Tokens()` 状态变异风险 | Eval 3 | 读取 Tokens 值时内部调 `refill()` 改变了状态，查询操作有副作用 |
| 令牌分数阈值精度风险 | Eval 3 | 浮点运算中 `l.tokens >= 1` 的比较在 refill 后可能有精度问题 |

---

## 五、综合分析

### 5.1 Skill 的差异化价值地图

| 维度 | 贡献度 | 说明 |
|------|--------|------|
| **方法论框架** | ★★★★★ | Failure Hypothesis List + Killer Cases + Boundary Checklist 是 without-skill 完全不产出的能力 |
| **测试组织纪律** | ★★★★☆ | table-driven + t.Run + t.Parallel 一致执行，without-skill 全部未遵守 |
| **质量审计追溯** | ★★★★★ | 13-check Scorecard + Removal Risk Statement 提供了测试质量的可审计证据 |
| **缺陷发现能力** | ★★☆☆☆ | 代码洞察（死代码、副作用）是额外收益，但功能路径覆盖与 without-skill 一致 |
| **功能覆盖差异** | ★☆☆☆☆ | 核心路径两者均完整覆盖，无差异 |

### 5.2 Skill 的真实价值定位

```
Skill 不是用来「多测几条路径」的，而是用来「系统化思考为什么要测这条路径」的。
```

核心价值按重要性排序：

1. **缺陷假设驱动的测试设计** — 先列「可能的 bug」（H1-H9），再据此设计测试。without-skill 则是「按 API 签名遍历参数组合」。前者找 bug，后者铺覆盖率。
2. **Killer Case + Removal Risk** — 每个 killer case 回答「这个断言防止什么 bug 逃逸」。没有这层信息，后续维护者无法区分关键断言和冗余断言，容易在重构时误删。
3. **结构化质量审计** — 13-check Scorecard 提供可量化的质量判断（Critical 层全过 = 可合并），而非「看起来测得挺全」的主观判断。
4. **边界清单系统化** — 12 项标准清单确保不会遗漏 nil、空值、边界值、并发、上下文取消等场景，每项标注 Covered/N/A 提供审计痕迹。
5. **测试组织一致性** — table-driven + t.Run 不只是风格偏好，它影响测试的可维护性和新增 case 的成本。

### 5.3 Skill 的弱点

1. **功能覆盖无差异**: 在所有 3 个场景中，without-skill 覆盖了与 with-skill 完全相同的核心路径（限流、熔断、上下文取消、并发等）。Skill 的差异化完全在方法论层面，不在「测什么」层面。
2. **Without-skill 偶尔有更多测试用例**: Eval 1 中 without-skill 产出 17 个独立测试函数 vs with-skill 的 12 个子测试。数量更多并不等于质量更高，但说明 without-skill 并非「测得少」。
3. **方法论产出的实际价值取决于团队**: Failure Hypothesis List 和 Killer Cases 对资深开发者可能是「有帮助但非必要」的，对测试新手或 Code Review 场景价值更大。
4. **评估场景有限**: 仅评估了 3 个并发/设计模式场景，未涵盖数据库操作、HTTP handler、纯逻辑函数等更广的场景谱。

---

## 六、评分总结

### 6.1 分维度评分

| 维度 | With Skill | Without Skill | 差值 |
|------|-----------|--------------|------|
| 功能覆盖 | 5.0/5 | 5.0/5 | 0.0 |
| **方法论完整度** | **5.0/5** | **1.0/5** | **+4.0** |
| 测试组织 | 5.0/5 | 2.5/5 | +2.5 |
| 可追溯性（审计） | 5.0/5 | 1.0/5 | +4.0 |
| 代码洞察 | 4.0/5 | 3.0/5 | +1.0 |
| 可维护性 | 4.5/5 | 3.0/5 | +1.5 |
| **综合均值** | **4.75/5** | **2.58/5** | **+2.17** |

### 6.2 加权总分

| 维度 | 权重 | 得分 | 加权 |
|------|------|------|------|
| 触发准确率 | 25% | 10/10 | 2.50 |
| Assertion 通过率 (with/without delta) | 20% | 9.2/10 | 1.84 |
| 方法论产出（假设/Killer/清单） | 20% | 10/10 | 2.00 |
| 测试组织 & 可维护性 | 15% | 9.0/10 | 1.35 |
| 代码洞察附加值 | 10% | 7.0/10 | 0.70 |
| 功能覆盖差异（相对基线） | 10% | 5.0/10 | 0.50 |
| **加权总分** | | | **8.89/10** |

---

## 七、评估方法论

### 触发评估
- **方法**: Subagent 模拟触发判断（3 轮独立运行 × 20 条查询 = 60 次判断）
- **查询设计**: 10 正例（涵盖中英文、直接/间接触发模式）+ 10 负例（6 类相邻任务: benchmark/fuzz/integration/E2E/load/mock + CI/docs/translation/profiling）
- **评估环境**: Cursor IDE Task subagent（generalPurpose, fast model），每轮全新上下文
- **局限性**: 代理测试而非端到端真实触发; 未考虑 50+ 竞争 skill 的干扰

### 任务评估
- **方法**: 3 个场景 × 2 配置 = 6 个独立 subagent 运行
- **目标代码**: 均为仓库中无现有测试的真实 Go 代码（非人工构造）
- **Assertions**: 34 条，覆盖文件创建、方法论产出、功能路径、测试组织、race 安全、质量审计 6 个维度
- **评分**: 手工逐条对照 assertion 与 subagent 输出，记录 pass/fail + 证据
- **基线**: 相同提示词，不读取 SKILL.md

### 评估材料
- 触发评估查询: `unit-test-workspace/trigger-eval-set.json`
- 触发评估结果: `unit-test-workspace/trigger-eval-results.json`
- Eval 定义: `unit-test-workspace/evals/evals.json`
- 评分结果: `unit-test-workspace/iteration-1/{resilience-do,worker-pool,rate-limiter}/{with_skill,without_skill}/grading.json`
- Benchmark 汇总: `unit-test-workspace/iteration-1/benchmark.json`
- Description 改进报告: `unit-test-workspace/description-improvement-report.md`
- Eval Viewer: `unit-test-workspace/iteration-1/eval-review.html`
- 生成的测试代码: `unit-test-workspace/iteration-1/*/outputs/*_test.go`
- 生成的报告: `unit-test-workspace/iteration-1/*/outputs/report.md`
