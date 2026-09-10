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

---

## 八、第 4 轮评审整改（2026-09-10）

一次外部评审对 skill 及其回归测试提出四条意见。改动前四条全部复现，其中三条能复现为可执行的事实，而非判断。

### 8.1 改动前的复现记录

| # | 实验 | 观测结果 | 判定 |
|---|------|---------|------|
| 1 | 保留合格示例其余内容，只把调用改成 `UndefinedFunction` | `SkipTest: go test exited 1 without running the test` | 成立——生成代码无法编译被归入环境问题 |
| 2 | 把 `json` 围栏内容替换成 `NOT JSON` | `grade() == (True, [])` | 成立——只检查围栏，从不解析块内内容 |
| 3 | 两包模块，`lib` 无 `_test.go`，用 `-coverpkg=./...` 运行 | 控制台 `covfix/lib coverage: 0.0% of statements`；合并 profile `lib.Add 100.0%` | 成立——SKILL.md 的排除规则建立在一个并不代表该包覆盖率的数字上 |
| 4 | 顺着工作流追踪 Removal Risk 语句 | 没有任何步骤要求真跑变异或删断言 | 成立——缺陷假设被用「已证结论」的语气强制写出 |

### 8.2 改了什么

| 意见 | 改动 | 守护 |
|------|------|------|
| 1 | `_GoRunner.run` 返回三态（`PASSED` / `FAILED` / `NO_RUN`）。正确源上的 `NO_RUN` 判为回答本身失败；变异源上的 `NO_RUN` 报为**无效变异**，绝不记为杀死。只有真实环境故障才跳过——`preflight()` 先证明工具链能编译。`go test` 的 `[no tests to run]`（退出 0，且打印在 `ok` 行上）同样归为 `NO_RUN`。 | `GraderSelfTest` 共 7 条，含评审的原实验 |
| 2 | `grade_json_summary` 解析该块并做交叉校验：必需字段（声明在 `meta.json`）、`summary.score` 与三档计数、`summary.pass` 与档位规则、`coverage.met` 与 `line_pct`/`gate`、`race.clean` 蕴含 `race.executed`、散文与 JSON 结论一致。档位阈值**从 `references/boundary-scorecard.md` 解析**，评分器不留第二份副本。 | `JsonSummaryContractTests` 共 14 条，不依赖 Go 工具链 |
| 3 | § Multi-Package Coverage 重写：门槛数字取自合并 profile；**「没有 `_test.go`」不是有效排除理由**（被同级包测试覆盖 → 计入门槛；确实未覆盖 → 报为覆盖缺口，与 PR-diff 规则一致）；有效排除按理由逐项列出。 | `CoverageScopeGuardTests` 共 5 条（按小节定界）+ `test_coverpkg_console_line_lies_while_the_profile_tells_the_truth`，它在真实两包模块上**执行 SKILL.md 里的原配方** |
| 4 | Removal Risk 语句必须带 `Verification: Verified`（已注入缺陷、观测并引用失败输出）或 `Verification: Unverified`（附原因）。工作流第 12 步改为「通过执行来验证」，`references/killer-case-patterns.md` § Verifying the Kill 给出配方，并列出「假杀」的三种表现。记分卡第 11 项计分对象是这个标签：诚实的 `Unverified` 仍算 PASS，**无标签**的断言算 FAIL。 | `KillerCaseVerificationGuardTests` 共 7 条 + 评分器的报告标记检查 |

测试套件 103 → 138 条，全绿。本轮每条新规则都做了变异验证——逐条改坏规则、要求对应测试失败：在绿色基线上**17/17 全部杀死**，且*跳过*计为存活而非杀死。

那次变异运行还抓出我自己两条有缺陷的测试：一条让 `SkipTest` 向上传播（unittest 把跳过记为绿色，于是这条守护无法发现它本该发现的回归），另一条因为 fixture 文件声明了不匹配的包名而走了构建错误分支，导致它本想覆盖的分支根本不可达。

### 8.3 关于第 4 条意见：证据支持什么、不支持什么

评审的实质判断成立，本报告有必要写明：§3 的 A/B 显示 without-skill 未通过的 13 条 assertion 全部属于**方法论层面**，核心路径覆盖完全一致（§3.4）。这支持「产出更可审查、组织更一致」，**不能**支撑「缺陷检出率更高」——本次评估没有任何实验测量过缺陷发现数。§5.1 的「价值地图」与 §6 的加权总分都应在这个边界内阅读。

本轮整改只在不新增实验就能收窄的那一处收窄了差距：killer case 的核心断言现在要么被执行并引用输出，要么被明确标注为未验证。这套纪律是否真能提高缺陷检出，仍是一个待答问题，需要一次植入缺陷的 A/B，无法从 §3 推导。

### 8.4 未重新测量的部分

第二至七章**没有**为第 4 轮重跑。触发准确率（§2）、A/B assertion 通过率（§3）、分维度评分（§6.1）与加权总分（§6.2）描述的仍是 2026-03-11 那次评估。第 4 轮改的是 skill 文档与测试工装；要再次主张那些数字，需要一次新的 A/B——且评分标准需纳入 `Verification:` 一项。

---

## 九、第 5 轮评审整改（2026-09-10）

后续评审又发现三处缺陷，改动前全部复现。

### 9.1 改动前的复现记录

| # | 实验 | 观测结果 | 判定 |
|---|------|---------|------|
| 1a | 把合格示例的 `"critical_pass"` 改为字符串 `"three"` | `grade_json_summary` → `[]` | 成立——类型不对时一致性校验被静默跳过 |
| 1b | 覆盖率改成 `line_pct: 20`、`met: false`，保留 `13/13 PASS` | `grade_json_summary` → `[]` | 成立——覆盖率结果与最终判定之间没有约束 |
| 2 | 删掉示例的长度断言，保留 H1 变异 | 测试**仍然失败**，由 ID 断言抓住（`last ID = "2", want "3"`） | 成立——"能杀死变异" ≠ "该断言不可缺少"；示例自己强制写的那句话是**假的** |
| 3 | 拿 `good.md` 对照它自己的代码读 | 声称 5 个 case、覆盖 H1+H2；实际只有一个三元素输入、没有 nil／empty 用例，却给 `13/13 PASS` | 成立——评分器的正例本身在过度声明 |

### 9.2 改了什么

**意见 1 —— JSON 校验改为分阶段、有顺序地执行。** 先查类型（来自 `meta.json` 的 `json_field_types`，它同时就是必需字段清单，因此只有一份清单而不是两份需要互相同步），再查取值范围，最后查一致性。一致性检查现在无条件执行，类型错误再也无法关掉某条规则；`int` 会拒绝 `true`，因为 Python 里 `bool` 是 `int` 的子类。新增规则：各档总数必须等于记分卡的档位规模、`0 <= *_pass <= *_total`、百分比落在 `0..100`、`cases >= 1`，以及此前缺失的跨支柱约束——覆盖率门槛是 Critical 第 13 项，因此**已测量**的未达标（受限 N/A 只适用于*未测量*的情形）必须表现为一条 Critical 失败和整体 FAIL。`JsonSummaryContractTests` 新增 9 条变异测试。

**意见 2 —— 两种断言彻底分开，且差别由执行来证明。** 报告的强制项现在是 `Kill: Verified` / `Kill: Unverified`（已注入缺陷、观测到失败）。*断言不可缺少*是另一个实验：在缺陷仍然注入的前提下删掉指名的那条断言、看到测试**转为通过**才成立，且该声明是可选的；此前那句一律强制的"if this assertion is removed, the known bug can escape detection"已从它出现的全部 10 处撤除。`references/killer-case-patterns.md` § Verifying the Kill 现在给出两套流程和**各自不同的结论**，写明"删除后仍失败"是对不可缺少性的**反证**，并解释不可缺少性是**（断言，缺陷）配对**的属性：ID 断言对"顺序被打乱但长度不变"的缺陷不可缺少，长度断言对"元素被重复但身份不变"的缺陷不可缺少，而对丢尾缺陷两者都不是——这正是评审给出的那个例子。`test_behavioral_killer.test_removing_an_assertion_can_still_leave_the_mutation_caught` 用执行把这个事实钉住。

**意见 3 —— 示例被重写为与自身代码相符，并新增两项对照检查。** `good.md` 现在是一个 4 用例的 table-driven 测试（nil、空、单元素、三元素），报告 4 个 case，把 H1 与 H2 分别映射到真正覆盖它们的用例，附上支撑其记分卡的完整边界清单，记录 `Kill: Verified` 与观测到的失败输出，并诚实写明对 H1 **不能**做任何断言不可缺少性的声明及其理由。评分器现在用 `go test -v` 运行，因此 `_grade_report_matches_code` 能把 `sum(targets[].cases)` 与工具链实际执行的用例数对照，并要求 fixture 声明的每条假设都有一个真正跑过的用例（`required_case_patterns`）。

测试套件 140 → 153 条，全绿。`SKILL.md` 的行数预算由 500 提到 520，理由记录在测试里。

### 9.3 一般性教训

意见 1 与意见 3 是同一种缺陷在两个层次上的表现：检查看的是**形式**，而它所认证的主张关乎**内容**。一个 json 围栏不是一份 JSON 文档；一份能解析的文档不是一份自洽的报告；一份自洽的报告不是一份关于随它一起交付的代码的报告。这个 skill 每一轮加固都把某一条边界从形式往内容推进一步，而每一步都是由实验发现的，不是靠重读规则发现的。

意见 2 的性质不同：那条规则本身不成立，而不只是没被强制执行。它强制要求的一个主张，用它自己推荐的实验根本无法确立，而示例恰好演示了这个主张是假的。一条无法用自带流程验证的强制要求，最终只会被"声明"满足——实际发生的正是这件事。

---

## 十、第 6 轮评审整改（2026-09-10）

又两处缺口，改动前全部复现，且都是第 5 轮那条教训的变体：检查看的是形式，而主张关乎内容。

### 10.1 改动前的复现记录

| # | 实验 | 观测结果 | 判定 |
|---|------|---------|------|
| 1 | 让示例的 `nil input` 与 `empty slice` 子测试直接 `t.Skip()`，其余不动 | `grade()` → `(True, [])` | 成立——`executed_case_names` 把 PASS/FAIL/SKIP 一并收集，于是一个什么都没断言的用例成了"H2 已覆盖"的证据 |
| 2 | 把实现改为 `var out []string`（空输入返回 nil） | 示例四个用例仍全部 PASS | 成立——H2 承诺"空但**非 nil**"，而断言只检查长度和元素；`len(nil) == 0` |

### 10.2 改了什么

**"发现了"不等于"验证了"。** `executed_case_names` 改为 `test_case_results`，返回 用例名 → `PASS`/`FAIL`/`SKIP` 的映射，`verified_cases` 剔除跳过的用例。一条假设只能由**取得判定结果**的匹配用例来支撑；并且这个 fixture 是无环境依赖的纯函数，因此**任何**跳过都会被报告（`allow_skipped_cases: false`）。

**每条假设都自带一个变异。** "一个 fixture 只有一个变异"正是第 2 处缺口的结构性成因：H2 可以被陈述、被给到输入场景、被按名字匹配，却从未被验证，因为没有任何东西测试它承诺的行为。fixture 里三份并行清单（`hypothesis_keywords` / `required_case_patterns` / `mutation`）合并为一个 `hypotheses` 数组，每个条目自带措辞、必需用例与变异。生成的测试现在必须杀死**每一条**假设的变异。

**示例被修正——依据是契约，不是实现。** 对任何会被序列化的返回值，`[]` 与 `null` 是真实可观测的差别，因此非 nil 这条承诺被明确写进被测代码的文档注释，然后才被断言（`got == nil` 必须是独立的一条检查，因为 `len` 看不见它）。H2 由此成为第二个 killer case K2，并有它自己已执行的 kill。反过来说：如果契约**并没有**承诺非 nil，正确的做法是收窄 H2——示例不能替被测代码发明需求。

示例还有两个细节值得记录：报告里引用的失败行指向 `assertIDs(...)` 的调用处而不是断言所在行，因为 `t.Helper()` 会把归属改到调用方；以及示例的 killer case 计数由 1 改为 2，因为现在每条假设都有一个绑定缺陷、且已执行 kill 的用例。

**随后的变异运行发现反方向没有守卫。** 把 `sut.go` 文档注释里那句非 nil 删掉，示例照样通过——没有任何东西把 H2 的断言绑定到代码真的做出的承诺上，于是一个示例"发明需求"和"漏掉验证"一样容易。现在每条假设都要声明 `contract_evidence`（一个必须匹配被测源码的正则），`validate_fixture` 会在评分任何回答之前拒绝无根据的假设（或干脆没声明证据的假设）。这两项检查方向相反：变异证明假设**已被验证**，证据证明假设**是正当的**。

**这两条规则在 skill 本身也是缺的**，不只是评分器的 bug：一个被跳过的用例，同样会在边界清单上被标成 `Covered`。Reporting Integrity 现在写明 `--- SKIP` 是"发现"而非"验证"，并禁止据此写 `Kill: Verified`；Defect-First 工作流要求每条假设都要指出"什么样的实现改动会违反它"（"指不出来，说明这条假设按当前写法不可检验"），并写明"给到输入不等于验证"；`references/bug-finding-techniques.md` 记录了 slice、map 与 `[]byte` 上的 `len(nil) == 0` 陷阱，并把判断依据落在契约而不是当前实现上。

测试套件 154 → 166 条，全绿。

### 10.3 第 4–6 轮的共同形态

到目前为止每一处发现都是同一个形状：**被检查的东西比被主张的东西差一步。**

| 轮次 | 检查的是 | 主张的是 | 差距 |
|------|---------|---------|------|
| 4 | 存在一个 `json` 围栏 | 摘要可被消费 | 围栏里写着 `NOT JSON` |
| 4 | 控制台一行覆盖率 | 该包的覆盖率 | 那行描述的是缺失的测试二进制 |
| 5 | 文档能解析 | 报告自洽 | `20%` 覆盖率配 `13/13 PASS` |
| 5 | 报告自洽 | 它描述的是这套测试 | 声称 5 个 case，实际 1 个 |
| 6 | 用例存在且打印了一行 | 行为已被验证 | 该用例被跳过 |
| 6 | 输入场景已覆盖 | 承诺的行为成立 | `len(nil) == 0` |

每一轮都堵住一步，下一次评审就找到再下一步。可推广的规则是：**对每一个主张，先说出"如果它是假的，什么观测会不一样"，然后去检查那个观测**——这正是这个 skill 对 killer case 的要求，只是把它用在了自己的测试工装上。
