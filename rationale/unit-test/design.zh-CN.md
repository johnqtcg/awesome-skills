---
title: unit-test skill 设计解析
owner: awesome-skills maintainers
status: active
last_updated: 2026-03-27
applicable_versions: current repository version
---

# unit-test skill 解析

`unit-test` 是一套面向 Go 仓库的缺陷优先单元测试框架。它的核心设计思想是：**高质量单元测试的目标是先判断目标代码的风险等级，再围绕明确的缺陷假设设计高信号用例，用关键用例、边界清单、分层评分卡和 `-race` / coverage 证据把“这组测试为什么值得存在”说清楚。** 因此它把 Go 版本门禁、执行模式、缺陷优先工作流、高信号测试预算、边界检查清单、自动评分卡、基于性质的测试和报告真实性串成了一条固定流程。

## 1. 定义

`unit-test` 用于：

- 为 Go 代码新增、补强、修复单元测试
- 优先发现边界、映射、并发、上下文传播等真实缺陷
- 把测试组织成 table-driven + `t.Run` 的可维护结构
- 根据目标风险自动选择 `Light / Standard / Strict` 模式
- 在交付时同时给出 race、coverage、评分卡和剩余风险

它输出的不只是测试代码，还包括：

- 执行模式与选择理由
- 已测试目标与用例数量
- Go 版本与版本适配
- 边界检查清单
- coverage / race 结果
- 评分卡与最终 PASS/FAIL

其中 `Failure Hypothesis List`、`killer case` 详情和 JSON summary 主要出现在 `Standard / Strict` 模式；`Light` 模式会刻意缩减输出，只保留较轻量的边界检查与评分结果。

从设计上看，它更像一个“单元测试治理框架”，而不是一个只会补几个 `_test.go` 文件的提示词。

## 2. 背景与问题

这个 skill 要解决的，不是“模型不会写 Go 测试”，而是默认的单测生成很容易滑向几种低信号模式：

- 测得很多，但断言很弱
- 覆盖率很好看，但抓不住真实 bug
- 用例数量很多，却没有清晰的方法论

如果没有明确框架，常见问题通常集中在 8 类：

| 问题 | 典型后果 |
|------|----------|
| 只追覆盖率，不先想缺陷 | 路径看似都测了，但关键 bug 还是会漏掉 |
| 不区分目标风险 | 简单函数被过度设计，高风险并发代码却只写浅层 happy path |
| 没有关键用例 | 维护者不知道哪些断言是关键防线 |
| 边界清单不系统 | `nil`、空值、单元素、最后一个元素、context cancel 等容易漏 |
| 断言抗变异性弱 | 只断言 `err == nil`、`not nil`，字段错了也照样过 |
| 测试组织零散 | 一个目标堆很多独立 `TestXxx`，复用差、增量改动成本高 |
| 并发测试不确定 | 依赖 `time.Sleep`、不跑 `-race`、共享状态泄漏导致测试脆弱 |
| 输出不可审计 | 团队不知道为何选这个模式、为什么说测试“够了”、还有什么风险未覆盖 |

`unit-test` 的设计逻辑，就是先回答“这段代码风险有多高、最可能坏在哪、哪些断言是回归防线、覆盖率门槛是否合理、该用什么强度的测试流程”，再决定生成多少测试和如何组织它们。

## 3. 与常见替代方案的对比

先看它与几种常见做法的区别：

| 维度 | `unit-test` skill | 直接让模型“写单元测试” | 把单测当成覆盖率补洞任务 |
|------|-------------------|--------------------------|--------------------------|
| 缺陷假设驱动 | 强 | 弱 | 弱 |
| 模式选择 (`Light / Standard / Strict`) | 强 | 弱 | 弱 |
| 关键用例纪律 | 强 | 弱 | 弱 |
| 边界清单系统性 | 强 | 中 | 弱 |
| 并发 / `-race` 意识 | 强 | 中 | 弱 |
| 测试组织一致性 | 强 | 中 | 弱 |
| 质量评分与审计 | 强 | 弱 | 弱 |
| 覆盖率态度 | 强调高信号，不鼓励刷量 | 容易随手补 case | 容易为了数字堆低价值测试 |

它的价值，不只是让单测“更多”，而是把单测从一组零散 case 提升成一套可解释、可审计、可维护的缺陷防御体系。

## 4. 核心设计逻辑

### 4.1 先做模式选择 vs 先写 case

`unit-test` 在 工作流程 的第 0 步先要求选择 `Light / Standard / Strict`。这一步非常关键，因为它明确拒绝一种常见误区：所有单测都用同一套重型流程。

它根据以下因素自动分流：

- target 数量
- 是否涉及并发
- 依赖复杂度
- 分支复杂度
- 是否安全敏感
- 是否有 context / deadline 语义
- 是否存在集合变换或 property-based trigger

这层设计的意义在于：

- 简单纯函数可以走 `Light`，避免过度设计
- 普通业务逻辑走 `Standard`
- 并发、安全敏感、高风险路径自动提升到 `Strict`

它解决的是“测试流程强度和代码风险不匹配”的问题。没有这层，最常见的失真就是简单逻辑被重写出一大套形式化报告，而复杂代码却只拿到几条浅层 case。

### 4.2 把 Defect-First 工作流程 放在中心

`unit-test` 最关键的设计，不是 table-driven，也不是 coverage，而是 Defect-First 工作流程。对 `Standard / Strict` 模式，它要求在写测试前先列出 Failure Hypothesis List，至少覆盖：

- loop / index 风险
- collection transform 风险
- branching 风险
- concurrency 风险
- context / time 风险

这层设计非常重要，因为单元测试真正高价值的地方，不在“函数有哪些参数组合”，而在“这段代码最可能以什么方式坏掉”。而对低风险目标，`Light` 模式会刻意跳过这层较重的方法论，避免把简单单测写成沉重流程。

评估也直接证明了这一点：with-skill 与 without-skill 在核心功能路径覆盖上几乎没有差异，最大的差距恰恰在 Failure Hypothesis List、关键用例、边界检查清单等方法论层。也就是说，这个 skill 的增量主要不是“测更多”，而是“更系统地解释为什么要这样测”。

### 4.3 关键用例是硬约束

在 `Standard + Strict` 模式下，这个 skill 要求每个 test target 至少有 1 个关键用例，并且必须包含四个组成部分：

1. defect hypothesis
2. fault injection 或 boundary setup
3. critical assertion
4. removal risk statement

这层设计是整个 skill 最有辨识度的部分之一。普通边界用例和关键用例的区别在于：关键用例必须明确指向一个命名缺陷，并说明“如果这个断言被删除，哪种已知 bug 会逃逸”。

它解决的是一个非常现实的问题：很多测试文件随着时间会被重构、简化、删断言。如果没有 removal risk 这一层，后续维护者很难知道哪些断言是装饰性的，哪些是关键防线。评估里 without-skill 虽然经常也覆盖了相同路径，但没有这层解释，因此测试的回归防御边界不够清晰。

### 4.4 坚持 边界检查清单 vs “边写边想”

`unit-test` 把边界检查显式做成：

- `Light` 模式 5 项清单
- `Standard / Strict` 模式 12 项清单

覆盖内容包括：

- `nil`
- empty
- single element
- size / last-element boundary
- min/max boundary
- invalid format
- zero-value struct/default trap
- dependency error
- context cancellation
- concurrent/race behavior
- mapping completeness
- killer case 映射

这层设计非常务实，因为边界遗漏往往不是因为开发者不知道这些情况存在，而是因为它们在写测试时不会自然按固定顺序跳出来。清单化之后，测试质量就不再依赖即时记忆，而是有了可审查的最小基线。

评估也说明，without-skill 并不是没写边界 case，而是没有形成显式 checklist，因此团队无法快速判断哪些边界已经系统覆盖，哪些只是零散碰到。

### 4.5 把覆盖率门禁做成“有范围、有理由”的策略

这个 skill 并没有把 coverage 简化成一句“统一 >= 80%”。它明确区分：

- logic-heavy package：默认 `>= 80%`
- infra / IO-heavy package：可以更低，但必须有明确理由

并且强调：

- 不能为了冲 coverage 去补低信号测试
- 即使 coverage 允许较低，边界清单纪律仍然保留
- 多包场景下要用 `-coverpkg=./...` 或分包 profile 做更准确测量

这层设计很成熟，因为它同时反对两种常见极端：

- 只看 coverage 数字，不看断言强度
- 因为覆盖率容易失真，就干脆不做 coverage gate

`unit-test` 的做法是把 coverage 留作质量门槛的一部分，但永远不让它替代 defect-first 设计。

### 4.6 强调断言的抗变异性

`unit-test` 一再要求断言要有抗变异性，同时跟随项目已有约定选择断言风格。它支持：

- `testify` 项目里用 `require` / `assert`
- `go-cmp` 项目里优先用 `cmp.Diff`
- stdlib-only 项目里用 `t.Fatalf` / `t.Errorf`
- 不能只写 `err == nil`、`not nil`
- 要断言业务字段，而不是存在性

这层设计解决的是低信号测试的核心问题。一个测试如果只是证明“返回了个对象”，那实现即使把字段交换、默认值写错、最后一个元素丢了，也可能继续通过。skill 真正强制的不是某个断言库，而是“必须使用足够强的断言表达业务正确性”。

参考文档 `bug-finding-techniques.md` 里的第一条就是 Mutation-Resistant Assertions，评估里也反复证明，skill 真正重视的是“哪一个具体字段出错时测试必须红”，而不是“有没有跑到这条路径”。

### 4.7 把测试组织标准写得这么具体

这个 skill 强制要求：

- 顶层命名按 target type 适配
- `t.Run` 分组与 test target 一一对应
- 用表驱动组织 case
- case name 要缺陷导向、可读
- 优先考虑 `t.Parallel()`，但前提是子测试独立

这层设计不仅是风格问题，更是维护成本问题。评估里 without-skill 经常会写出很多独立 `TestXxx` 函数，功能上未必差，但扩展新 case 的成本更高，setup 重复也更多。with-skill 统一采用 table-driven + `t.Run`，让后续增量测试更便宜。

### 4.8 对并发测试特别强调确定性控制

`unit-test` 明确要求：

- 运行 `go test -race`
- 并发场景不要依赖 `time.Sleep`
- 用 channel barrier、WaitGroup、channel sequencing 做确定性控制
- 在不安全条件下不要滥用 `t.Parallel()`

这层设计很关键，因为并发单测最大的风险不是“不会跑”，而是“偶尔才失败”或“本地绿、CI 红”。`references/concurrency-testing.md` 提供的做法，本质上是在把并发测试从“靠时间猜执行顺序”改造成“靠同步原语控制时序”。这也是为什么 `-race` 被设成硬要求，而不是可选优化。

### 4.9 支持 基于性质的测试，但不让它替代 table-driven

这个 skill 对 property-based testing 的态度很克制：

- `Light` 模式不适用
- `Standard` 模式可推荐
- `Strict` 模式在适配 pattern 时要求给出建议或实现

它只在 roundtrip、idempotency、preservation、commutativity、parse validity、monotonicity 等模式下建议使用，并明确说明：

- property-based test 验证 invariant
- table-driven test 验证具体边界和精确输出
- 关键用例仍然不能被 property-based test 取代

这层设计很成熟，因为它避免了另一种测试误区：一看到 invariants 就试图用随机输入替代全部手写 case。skill 的立场很清楚，property-based test 是补充广度，不是替代缺陷驱动和边界驱动。

### 4.10 Generated Code Exclusion 是必要规则

`unit-test` 明确排除：

- `*.pb.go`
- `*_gen.go`
- `wire_gen.go`
- `mock_*.go`
- `*_mock.go`
- 带 `Code generated ... DO NOT EDIT` 指令的文件

这层设计很有必要，因为生成代码通常应该由生成器自身或上层行为测试来覆盖。若不加排除，模型很容易在看起来“很好补覆盖率”的地方投入大量无效测试，造成维护噪音。这里的重点不是“生成代码永远不该测”，而是 skill 默认把它视为边界之外的低收益区域。

### 4.11 自动评分卡 和 报告真实性 要同时存在

`unit-test` 的输出不是一句“测试补好了”，而是至少要给出：

- mode
- version adaptation
- boundary checklist
- coverage / race 结果
- 13 项或 7 项评分卡
- 最终 PASS / FAIL

对于 `Standard / Strict` 模式，还要补充：

- hypothesis / killer case 映射
- 更完整的方法论输出
- JSON summary

同时它明确规定：没跑过 `-race` 和 coverage，就不能声称自己跑过；不能验证时必须给出精确命令。

这层设计的价值，在于把单元测试从“代码改动”升级成“可审计交付物”。团队拿到的不只是几个测试文件，而是知道：

- 为什么选这个模式
- 哪些缺陷已被覆盖（在 `Standard / Strict` 模式下尤为明确）
- 哪些 killer case 是关键防线（`Standard / Strict`）
- coverage / race 到底有没有达标
- 还剩哪些风险没测到

评估里最明显的优势，也正是这种方法论输出与审计追溯能力。

### 4.12 在 Description 上投入很多触发设计

与很多 skill 不同，`unit-test` 的评估把 trigger accuracy 单独做成了重要维度，而且达到了 `20/20`。这并不是附带结果，而是由 skill 的 Description 设计驱动的：

- 强 trigger 词覆盖
- 明确排除 benchmark / fuzz / integration / E2E / load / mock
- 强命令语气
- 强化“不可替代性信号”

这层设计很值得写进 rationale，因为它说明 `unit-test` 并不只是把规则写多，而是在认真解决“什么时候该触发自己、什么时候该让路给别的 skill”。

### 4.13 一个 killer case 有两个主张，需要两个实验

killer case 会做出两个读起来几乎一样、但要靠不同实验确立的主张：

| 主张 | 实验 | 结论 |
|------|------|------|
| **这个用例能抓住缺陷 D** | 注入 D，重跑 | 测试失败 ⇒ 成立 |
| **断言 A 才是抓住 D 的那一条** | 注入 D *并且*只删掉 A，重跑 | 测试转为通过 ⇒ 成立；仍然失败 ⇒ **被反证** |

这个 skill 最初强制的是第二个主张——每个 killer case 都必须写上"if this assertion is removed, the known bug can escape detection"——而它的工作流两个都不验证。由此产生了两个不同的缺陷。

*这句话按其写法是不可证伪的。* 一次全绿的测试运行，无法区分"这条断言会抓住该缺陷"和"不会"，所以这句话必须写、又无法核对，最终只会被"声明"稳定地满足。

*而且这条强制要求本身不成立。* 即便正确执行，注入缺陷也确立不了它。本仓库自己的示例证明了这一点：在丢尾变异生效的情况下，删掉它的长度断言后测试**仍然失败**，被最后一个元素的 ID 断言抓住。示例里那句强制语句对它自己的测试就是假的——`test_removing_an_assertion_can_still_leave_the_mutation_caught` 现在用执行把这一点钉住。

于是两个主张被分开。杀死检查是强制的，报告为 `Kill: Verified`（已注入缺陷、观测并引用失败）或 `Kill: Unverified`（附原因）。断言不可缺少性的声明是可选的，且只有在做过它自己的删除检查之后才允许写——参考文档还提醒：得到否定结果才是常态，因为一个好用例会同时断言基数*和*身份，而多数单一缺陷会同时触发两者。

背后的关键认识是：**不可缺少性是（断言，缺陷）配对的属性，不是断言的属性。** 对"顺序被打乱但长度不变"的缺陷，ID 断言不可缺少；对"元素被重复但身份不变"的缺陷，长度断言不可缺少；对丢尾缺陷，两者都不是。两条都要留着——只是别在没做过那个实验的情况下声称哪一条是承重的。

记分卡第 11 项计分的是杀死状态，不是执行结果：诚实的 `Unverified` 仍算 PASS，而无标签的杀死声明算 FAIL。惩罚一个跑不了 Go 的环境，只会教会模型谎报 `Verified`——那正是要关掉的失效模式，而不是它的加强版。

### 4.14 对形式的检查无法认证关于内容的主张

这个 skill 的评分器上出现过三处独立缺陷，其实是同一个错误在不同深度上的表现：

| 检查看的是 | 它认证的是 | 通过了的反例 |
|-----------|-----------|-------------|
| 存在一个 ```json 围栏 | "摘要是机器可读的" | 围栏里写着 `NOT JSON` |
| 文档能解析、字段齐全 | "摘要是自洽的" | `line_pct: 20`、`met: false`、`13/13 PASS` |
| 报告自洽 | "报告描述的是这套测试" | 一个三元素输入上声称"5 个 case、覆盖 H1+H2" |

每次修复都把边界从形式往内容推进一步，而每个缺口都是由实验发现的，不是靠重读规则发现的——这本身就是这个 skill 那条报告真实性条款的论据。

由此得出两条设计规则。**先校验类型再校验一致性，并且绝不用类型判断去守卫一致性规则**——一个 `isinstance` 守卫会把类型错误变成被跳过的检查，于是 `"critical_pass": "three"` 通过了。**把最终判定所依赖的支柱连起来**：覆盖率门槛是记分卡 Critical 第 13 项，因此一次已测量的覆盖率未达标必须表现为一条 Critical 失败与整体 FAIL。没有这条链接，每个字段都可以局部自洽，而最终判定是不可能的。

用来堵住第三行的内容级检查刻意保持狭窄：用 `go test -v` 跑生成的测试，把声称的用例数与工具链实际执行的用例数对照。这不是语义分析——它对照的是两个本来就必须一致的东西，而过度声明的报告通常正是在这里先破。

### 4.15 发现、运行、验证——三件不同的事

一个测试用例有三种状态，而粗糙的检查会把它们压成一种：

| 状态 | 证据 | 能支撑什么 |
|------|------|-----------|
| **已发现** | 用例存在且有名字 | 什么都不能 |
| **已运行** | `go test -v` 为它打印了一行 | 单独看什么都不能——`--- SKIP` 也会打印一行 |
| **已验证** | 它取得了 `PASS` 或 `FAIL` | 它的断言真的执行了 |

这个 skill 自己的测试工装把*已运行*压成了*已验证*：它把 `PASS`、`FAIL`、`SKIP` 一并收集，于是把两个子测试改成 `t.Skip()`——名字不变、数量不变——评分器照样报告它们的假设已覆盖。而实际上什么都没断言。

同一种混淆对 skill 的使用者同样开放，所以这条规则现在写在 Reporting Integrity 里、而不只是在评分器里：被跳过的用例在边界清单上被标成 `Covered` 是完全相同的错误；而给一个被跳过的 killer case 打上 `Kill: Verified` 更糟——它为一个没有运行的用例声明了执行结果。

一般形式是：**状态本身就是数据，丢掉它会把否定结果变成肯定结果。** 任何把"逐项结果集合"缩减成"名字集合"的检查都犯了这个错，不论那些项是测试用例、迁移的行，还是被 lint 的文件。

### 4.16 一条假设只有在你能说出变异时才是可检验的

Failure Hypothesis List 问的是"什么可能出错"。第 6 轮说明这本身还不够：一条假设可以被写在散文里、映射到用例、按名字匹配上——却依然描述着一个没有任何断言覆盖的行为。

示例里的 H2 承诺"nil／空 slice 得到空但**非 nil**的结果"。它的用例给了输入，断言了长度和元素。但 `len(nil) == 0`，所以把实现改成 `var out []string`——在契约承诺 `[]` 的地方返回 `null`——满足了全部断言。这条假设有输入场景，没有验证。

修法是一条有牙齿的规则：**对每条假设，说出什么样的实现改动会违反它。**

- 说不出来，就说明这条假设按当前写法不可检验。改写它直到能说出来——正是这个改写过程把含糊的假设变成可测的假设。
- 用例必须带一条"被指名的那个改动会打破"的断言。给到输入不等于验证。

在测试工装里这一点被做成了结构性的：每条假设自带一个变异，生成的测试必须逐条杀死。在此之前 fixture 维护着三份并行清单——措辞、必需用例、变异——而 H2 只出现在其中两份里。两份必须一致的清单会漂移，三份更糟。合并成"每条假设一个条目"之后，那个藏住 H2 缺口的遗漏就无法被表达出来了。

第二条教训关于答案的来源。非 nil 是否属于契约，是关于**契约**的问题，不是关于实现的问题：`make([]T, 0, n)` 今天恰好返回非 nil，并不构成承诺。契约写了就断言它；没写就收窄假设。一个断言得比契约承诺更多的示例，是在替被测代码发明需求——那正是被修的这个缺陷的镜像。

这个镜像需要它自己的守卫，而变异运行证明了这一点：把源码文档注释里那句非 nil 删掉，一切照样通过。于是每条假设现在带着两条方向相反的链接——一个**变异**（杀死它，假设即已被验证）和源码中的**契约证据**（匹配它，假设即是正当的）。只有前者的假设可能是被编造出来的需求；只有后者的假设是一句未经验证的承诺。两者都需要，且互不替代。

## 5. 这个设计解决了哪些具体问题

结合当前 `SKILL.md`、关键 references 和评估报告，可以把它解决的问题归纳为：

| 问题类型 | skill 中的对应设计 | 实际效果 |
|----------|-------------------|----------|
| 单测只追覆盖率 | Defect-First 工作流程 | 测试更像抓 bug，而不是刷路径 |
| 高低风险代码用同一套流程 | 执行模式 | 测试强度更匹配代码风险 |
| 关键断言容易在重构中丢失 | 关键用例 + Removal Risk | 回归防线更明确 |
| 边界场景漏测 | 边界检查清单 | 覆盖更系统 |
| 断言信号弱 | Mutation-Resistant Assertions | 更容易抓到字段、映射、状态错误 |
| 并发测试不稳定 | `-race` + deterministic concurrency patterns | 测试更可靠 |
| 组织方式零散 | table-driven + `t.Run` + target adaptation | 维护成本更低 |
| 测试完成度不可审计 | 评分卡 + 报告真实性 | 团队更容易判断是否可交付 |
| Killer case 的核心断言只被声明、从不核对 | 强制的 `Kill:` 状态（§4.13） | 杀死结果要么被执行并引用输出，要么被明确标注为假设 |
| 把"能杀死变异"读作"该断言不可缺少" | 两个主张、两个实验（§4.13） | 更强的那个主张改为可选，且必须做它自己的删除检查 |
| 把形式检查当作内容检查来信任 | 先类型再一致性、支柱互相链接、报告与运行对照（§4.14） | 看起来自洽却与自身代码矛盾的报告会被拒 |
| 把被跳过的用例读作覆盖 | 发现／运行／验证三态分开（§4.15） | `--- SKIP` 不再能标出 `Covered` 或 `Kill: Verified` |
| 假设陈述了一个没有断言覆盖的行为 | 每条假设都要指名变异（§4.16） | 指不出变异的假设要改写，而不是照发 |
| 读覆盖率数字时不带测量范围 | 合并 profile 规则 + 按理由排除（§4.14） | 已覆盖的代码不会被丢出门槛，真实缺口也买不到豁免 |

## 6. 主要亮点

### 6.1 它把单元测试从“覆盖率任务”改造成“缺陷发现流程”

这是整个 skill 最重要的亮点，也是评估里最核心的差异来源。

### 6.2 `Light / Standard / Strict` 让测试强度与风险匹配

不是所有代码都值得同样重的测试流程，这个 skill 把这种判断显式化了。

### 6.3 关键用例是非常有辨识度的设计

它要求每个 `Standard / Strict` 目标至少有一个能明确说明“这个断言删了，哪种 bug 会漏”的关键用例。

### 6.4 边界清单和评分卡让测试质量可审计

团队不需要再凭感觉判断“这组测试差不多够了”，而可以看到明确的检查结果。

### 6.5 它在并发与时间敏感代码上特别有针对性

channel barrier、error fan-in、panic recovery、`-race`、`t.Parallel()` 安全规则，说明它对 Go 单测的高风险区有专门设计。

### 6.6 当前版本的真正增量，在方法论和审计，而不是功能路径数量

评估已经说明：with-skill 和 without-skill 在核心功能路径覆盖上差异不大；真正的差距在 Failure Hypothesis List、关键用例、边界检查清单、测试组织和评分卡。这说明 `unit-test` 的核心价值是测试治理，而不是单纯“多生成一些测试”。

## 7. 什么时候适合用，什么时候不该硬用

| 场景 | 是否适合 | 原因 |
|------|----------|------|
| Go 逻辑代码补单测、补边界测试 | 非常适合 | 这是核心场景 |
| 并发、context、映射转换类 bug 风险较高的代码 | 非常适合 | Defect-First + `-race` 很有针对性 |
| 需要 review / 改造已有 `_test.go` 质量 | 非常适合 | 评分卡与关键用例规则很实用 |
| benchmark | 不适合 | 应交给 benchmark / 性能测试路径 |
| fuzz test | 不适合 | 应交给 fuzzing 流程 |
| integration / E2E / load test | 不适合 | 都超出单测范围 |
| mock 生成 | 不适合 | 这不是测试设计本身 |

## 8. 结论

`unit-test` 的真正亮点，不是它能更快写出 Go 测试，而是它把单元测试里最容易流于形式的部分系统化了：先按风险选择模式，再列缺陷假设，再为每个 target 设计关键用例，再用边界清单、抗变异断言、并发确定性控制、coverage / race 证据和分层评分卡约束最终交付物。

从设计上看，这个 skill 很清楚地体现了一条原则：**高质量单元测试的关键，不是把更多函数跑一遍，而是让测试能够解释自己要防什么 bug、为什么这些断言不能删、哪些边界已经系统覆盖、哪些风险还残留，以及这些结论是否真的被 `-race` 和 coverage 证据支撑。** 这也是它特别适合 Go 逻辑测试、并发敏感代码和测试质量改造场景的原因。

## 9. 文档维护

当以下内容发生变化时，这份文档应该同步更新：

- `skills/unit-test/SKILL.md` 中的硬性规则、执行模式、缺陷优先工作流程、覆盖率门禁、自动评分卡、基于性质的测试、报告真实性或输出预期发生变化。
- `skills/unit-test/references/killer-case-patterns.md`、`bug-finding-techniques.md`、`concurrency-testing.md` 或 `property-based-testing.md` 中的关键模式与示例发生变化。
- `evaluate/unit-test-skill-eval-report.md` 或 `evaluate/unit-test-skill-eval-report.zh-CN.md` 中支撑本文判断的核心结果发生变化。

建议按季度复查一次；如果 `unit-test` 的模式选择、关键用例纪律、评分卡结构或触发条件描述发生明显重构，则应立即复查。

## 10. 相关阅读

- `skills/unit-test/SKILL.md`
- `skills/unit-test/references/killer-case-patterns.md`
- `skills/unit-test/references/bug-finding-techniques.md`
- `skills/unit-test/references/concurrency-testing.md`
- `skills/unit-test/references/property-based-testing.md`
- `skills/unit-test/scripts/tests/COVERAGE.md`
- `evaluate/unit-test-skill-eval-report.md`
- `evaluate/unit-test-skill-eval-report.zh-CN.md`
