---
title: tdd-workflow skill 设计解析
owner: awesome-skills maintainers
status: active
last_updated: 2026-03-27
applicable_versions: current repository version
---

# tdd-workflow skill 解析

`tdd-workflow` 是一套面向 Go 服务代码改动的实用 TDD 执行框架。它的核心设计思想是：**测试驱动开发的价值不在“先写几个测试文件”，而在于把 Red -> Green -> Refactor 变成可验证的工作证据，并在写测试前先说明要防什么缺陷、测试预算应该有多大、哪些高风险路径必须覆盖、以及当前结论还留下了哪些残余风险。** 因此它把缺陷假设门禁、关键用例门禁、覆盖率门禁、执行真实性门禁、并发确定性门禁、变更规模测试预算门禁、评分卡和输出契约串成了一条固定流程。

## 1. 定义

`tdd-workflow` 用于：

- 对新功能、缺陷修复、重构、API 改动和新模块实施实用 TDD
- 强制保留 `Red -> Green -> Refactor` 证据链
- 在写测试前先列缺陷假设，并映射到测试名
- 通过 killer case、覆盖率和风险路径门禁提升测试信噪比
- 对已有代码补测试时，用 characterization testing 规则保留 Red 证据

它输出的不只是测试代码，还包括：

- 变更文件
- 变更规模
- 缺陷假设到测试的映射
- 关键用例
- Red -> Green evidence
- coverage
- 评分卡
- 残余风险 / 后续事项

从设计上看，它更像一个“TDD 治理框架”，而不是一个单纯帮你生成 Go 单元测试的提示词。

## 2. 背景与问题

这个 skill 要解决的，不是“模型不会写 Go 测试”，而是测试生成任务很容易退化成几种常见伪 TDD：

- 先把实现写完，再补几个通过的测试
- 写了很多 case，但没人知道它们到底在防什么 bug
- 只追求行覆盖率，不区分高风险路径是否真的被命中

如果没有明确流程，常见问题通常集中在 8 类：

| 问题 | 典型后果 |
|------|----------|
| 没有 Red 证据 | 只能证明“现在能过”，不能证明测试真的能抓错 |
| 不列缺陷假设 | 测试和风险点脱节，容易漏 killer path |
| 不做 killer case | 高风险 bug 没有标靶测试 |
| 只看 line coverage | 关键风险路径未覆盖却误以为测试充分 |
| 不按改动规模分配测试预算 | 小改动测得过重，大改动测得过浅 |
| 重构阶段偷偷改行为 | 把行为变更伪装成 refactor |
| 对已有代码补测试时放弃 TDD 纪律 | characterization testing 与普通 test-after 混在一起 |
| 不输出结构化报告 | 评审者看不到 Red、coverage、残余风险是否真实成立 |

`tdd-workflow` 的设计逻辑，就是先把“这次改动要防哪些具体缺陷、每个缺陷由哪个测试承担、哪些 case 是 killer、测试预算该到什么深度、有没有真实 Red 证据、覆盖率是否覆盖到风险路径”讲清楚，再允许宣布这是一轮合格的 TDD 交付。

## 3. 与常见替代方案的对比

先看它与几种常见做法的区别：

| 维度 | `tdd-workflow` skill | 直接让模型“补单元测试” | 手工经验式写测试 |
|------|----------------------|--------------------------|------------------|
| Red -> Green 证据纪律 | 强 | 弱 | 中 |
| 缺陷假设驱动 | 强 | 弱 | 中 |
| Killer case 机制 | 强 | 弱 | 弱 |
| 覆盖率 + 风险路径双门禁 | 强 | 中 | 中 |
| 按改动规模控制测试预算 | 强 | 弱 | 弱 |
| Characterization testing 适配 | 强 | 弱 | 中 |
| 执行真实性声明 | 强 | 弱 | 中 |
| 结构化交付 | 强 | 弱 | 弱 |

它的价值，不只是让测试输出更像一份报告，而是把“会写测试”升级成“会交付可验证的 TDD 过程”。

## 4. 核心设计逻辑

### 4.1 先做 Change Size Classification

`tdd-workflow` 的第一步不是直接写测试，而是先把改动分成：

- `S`
- `M`
- `L`

并按文件数、LOC 和 critical path 数量确定测试预算。

这一步是整个 skill 的结构中轴，因为 TDD 最常见的失真之一，不是“没写测试”，而是测试深度和改动规模完全不匹配。skill 明确规定：

- `S` 改动通常控制在 3-6 个 case / method
- `M` 改动通常控制在 6-12 个 case / method
- `L` 改动则允许进入更广的 regression matrix

如果超出预算，必须按 distinct logic paths 解释原因；如果是 auth、输入校验、SSRF guard、crypto 等安全敏感代码，还允许加倍预算，但要把安全理由写进输出契约。这让测试深度从“凭感觉多写点”变成了显式资源配置。

### 4.2 缺陷假设门禁 被放在写测试之前

这个 skill 强制先列具体 defect hypotheses，例如：

- boundary/index
- error propagation
- mapping loss
- concurrency/order/timing
- idempotency/retry

并要求每个 hypothesis 至少映射到一个 test case name。

这层设计非常关键，因为很多自动生成的测试虽然数量不少，但只是把 happy path、error path、boundary path 随机铺开，并没有真正回答“这组测试到底在防哪类 bug”。缺陷假设门禁 先确定风险模型，再生成 case，从而让测试具有理论来源，而不是只是一堆表面上完整的样例。

评估里这也是最鲜明的 skill-only 增量之一：without-skill 三个场景都能写出不少测试，但 0/3 提供了 hypothesis-to-test mapping；with-skill 则 3/3 全部具备。

### 4.3 “关键用例门禁”是这个 skill 的差异核心

`tdd-workflow` 不满足于“有边界测试”，而是要求每个 changed method / use-case 至少有一个 killer case，并且这个 killer case 必须：

1. 指向高风险 defect hypothesis
2. 带有明确 fault injection 或攻击输入
3. 带有关键断言
4. 在报告里被显式标记

这层设计的价值非常大，因为很多测试都能跑、也有覆盖率，但真正关键的失败模式没有任何一条测试专门盯住。评估里最典型的是 `IsPrivateIPLiteral` 场景：without-skill 虽然写了 36 个测试，但没有触碰 `::ffff:127.0.0.1` 这种 IPv4-mapped IPv6 SSRF bypass；with-skill 的 killer case 则直接把这类攻击路径钉住。这说明 skill 的增量不只是“更多测试”，而是“更能捕获高风险缺陷的测试”。

### 4.4 Red 证据必须被保留下来

`tdd-workflow` 的核心纪律之一，是不能只说自己做了 TDD，而要保留：

- Red evidence
- Green evidence
- Refactor 后持续 green 的证据

这不是格式要求，而是 TDD 合法性的核心。没有 Red，测试就可能只是事后证明实现现在能过；有了 Red，才能证明这条测试真的会在行为错误时失败。

也正因如此，skill 对 pre-existing code 专门设计了 characterization 路径：

- 如果是给已有实现补测试
- Red 证据可以通过 mutation 来展示
- 或者通过明确 defect hypothesis 来说明测试确实在守护真实风险

这层设计很成熟，因为它承认现实里并不是每次都能从“函数未定义”那种最纯粹的 Red 开始，但仍然坚持要给出可验证的 Red 替代证据，而不是直接把“测试先于本次修改写出”混同于完整 TDD。

### 4.5 覆盖率门禁 是“Line + Risk Path”双门禁

这个 skill 要求：

- changed package 默认 line coverage >= 80%
- 所有高风险 hypothesis / branch 必须被覆盖

这层设计非常关键，因为很多测试工作会落入一个常见陷阱：覆盖率数字很好看，但关键的风险路径根本没跑到。`tdd-workflow` 把 risk-path gate 放在 line coverage 旁边，实际上是在明确声明：coverage 只是底线，不是证明测试有效的充分条件。

这也解释了为什么它特别强调 killer cases、high-risk branches 和 security override。skill 真正在追求的不是“把数字做满”，而是“让高风险错误很难溜过去”。

### 4.6 Characterization Testing 要被正式纳入工作流

很多仓库里，目标函数已经存在但没有测试。这时如果死守最狭义的 TDD，会出现一个尴尬问题：代码早就存在，怎么证明 Red？

`tdd-workflow` 的答案不是放弃 TDD，而是把 characterization testing 纳入流程：

- 先用测试刻画当前行为
- 保持这些测试通过，形成安全网
- 再针对新变更写新的 failing test
- 然后实现变更

对于更难直接制造 Red 的场景，还允许 mutation-based Red evidence 或 hypothesis-based Red evidence。这个设计很重要，因为它让 skill 能覆盖真实仓库中的高频任务，而不只适用于“从零写一个新函数”的理想化场景。

### 4.7 并发确定性门禁 单独存在

对于并发敏感代码，skill 强制要求：

- 不用 `time.Sleep` 做同步
- 使用 channels / barriers / waitgroups / atomics 控制顺序
- 跑 `-race`

这是一个很有针对性的设计，因为并发测试最常见的伪稳定方式，就是用 sleep 把竞态问题掩盖掉。这样虽然测试“更绿了”，但并没有真正提高可验证性。把 determinism 独立成 gate，说明这个 skill 不接受“靠 timing 运气通过”的测试。

### 4.8 硬性规则要适配项目断言风格

`tdd-workflow` 并不把某一种测试库当成唯一正确答案，而是先看项目现有约定：

- 如果项目用 `testify`，按 `require` / `assert` 习惯走
- 如果项目只用标准库，就用 `t.Fatalf` / `t.Errorf`
- 如果项目用 `go-cmp`，允许 `cmp.Diff`

这层设计的价值在于，它把 TDD 的稳定核心定义在流程纪律上，而不是绑定到具体断言库。这能减少为了“看起来像 TDD”而引入不符合仓库习惯的新测试风格，也更符合真实工程协作。

### 4.9 强制限制 speculative production code

skill 明确规定：

- 不要写 failing tests 未要求的生产代码
- 不要在 Green 阶段顺手补 Update / Delete / helper abstraction

这层设计很重要，因为很多“测试先写、实现后写”的流程，最后还是会退化成一次性把整块生产代码铺开。表面上看像 test-first，实际上已经失去 TDD 的反馈回路。`tdd-workflow` 用这条规则把实现范围钉在当前 failing test 所要求的最小路径上。

### 4.10 Refactor Phase 要和行为变更彻底切开

这个 skill 明确规定：Refactor 阶段只能做结构优化，例如：

- extract method
- rename
- reduce nesting
- replace magic number

但如果 refactor 需要改测试，或者改变外部可观察行为，就必须重新开启新的 Red cycle。

这层设计的价值在于，它把“结构改良”和“行为变更”分成两套事件。否则很多人会在 refactor 阶段偷偷修语义、改错误类型、改接口表现，而测试又因为断言太弱没暴露出来。skill 通过这条边界，把 refactor 从“顺手做优化”重新定义回“安全重排”。

### 4.11 含过程证据的输出契约

`tdd-workflow` 要求最终输出包含：

- changed files
- change size
- defect hypotheses -> test mapping
- killer cases
- Red -> Green evidence
- coverage
- 评分卡
- residual risks / follow-ups

这层设计非常关键，因为 TDD 最容易被误解成一种“只要最后有测试文件就算做过”的个人习惯。输出契约 把过程证据显式化后，评审者就能检查：

- 这次到底是不是按 TDD 驱动的
- killer case 是什么
- Red 是否真实发生过
- line coverage 和 risk-path coverage 是否都过关
- 还有哪些边角情况因为 budget 未覆盖

也正因为如此，这个 skill 的交付物不是一组测试文件，而是一份可审查的 TDD 结果说明。

### 4.12 “评分卡”不是附属说明，而是质量门槛

`tdd-workflow` 把结果分成三层评分：

- Critical
- Standard
- Hygiene

其中：

- 没有 Red evidence、没有 killer case、没有 risk-path coverage，直接无法 overall PASS
- Standard 至少要过 4/5
- Hygiene 至少要过 3/4

这层设计的意义，在于把“测试写出来了”和“这是一轮合格的 TDD”区分开。评估里 without-skill 最大的问题也不是测试代码完全不行，而是缺少这套方法论证据和结构化质量门槛。

### 4.13 references 采用按场景选择性加载

`tdd-workflow` 的 references 不是一次全读，而是按场景加载：

- `boundary-checklist.md` 是 always-read 基础设施
- `api-3layer-template.md` 和 `fake-stub-template.md` 用于 API / service 层
- `tdd-workflow.md` 用于首次 TDD 或复杂重构
- `anti-examples.md` 用于 review 或生成阶段
- `golden-characterization-example.md` 用于已有代码补测试

这层结构很合理，因为 TDD 的核心纪律必须常驻，但具体策略会随任务类型变化。通过分层 references，skill 既能覆盖纯函数、三层服务、legacy characterization、并发场景，又不会每次都把全部上下文灌入模型。

## 5. 这个设计解决了哪些具体问题

结合当前 `SKILL.md`、关键 references 和评估报告，可以把它解决的问题归纳为：

| 问题类型 | skill 中的对应设计 | 实际效果 |
|----------|-------------------|----------|
| 测试先天缺乏风险模型 | 缺陷假设门禁 | 测试更有针对性 |
| 高风险路径没有标靶测试 | 关键用例门禁 | 更容易抓关键 defect |
| 只写通过测试，无法证明守护力 | Red -> Green evidence | 测试更可验证 |
| 覆盖率数字高但风险路径漏掉 | 覆盖率门禁 (line + risk-path) | 覆盖质量更真实 |
| 小改动写成大矩阵或大改动测得太浅 | 变更规模测试预算门禁 | 测试深度更匹配改动 |
| 并发测试靠 sleep 碰运气 | 并发确定性门禁 | 结果更稳定可信 |
| 旧代码补测试时 TDD 纪律失效 | Characterization rules | 兼顾现实约束与 TDD 证据 |
| 测试结果难以评审 | 输出契约 + 评分卡 | 更易复核与比较 |

## 6. 主要亮点

### 6.1 它把 TDD 从“写测试顺序”提升成“过程证据体系”

真正的重点不是 tests-first 口号，而是证明 Red、Green、Refactor 都真的发生过。

### 6.2 缺陷假设 + 关键用例是最显著的结构亮点

这是 `tdd-workflow` 最有辨识度的设计：先定义要防哪类 bug，再指定哪条测试负责守住它。

### 6.3 它的覆盖率设计比“80% 就行”更成熟

line coverage 只是底线，risk-path coverage 才是防止关键缺陷漏过的核心。

### 6.4 它对已有代码补测试的适配非常实用

很多真实任务不是从零开发，而是给已有实现补测试。`tdd-workflow` 用 characterization testing 和 mutation/hypothesis-based Red 把这个现实场景纳入了 TDD 框架。

### 6.5 它把测试预算控制纳入设计

S/M/L 分类和安全敏感代码的预算加倍规则，让测试规模与风险匹配，而不是越多越好。

### 6.6 当前版本的真正增量，在方法论纪律而不在测试代码生成本身

评估已经说明：基础模型本来就会写 table-driven tests、stdlib assertions、边界测试，甚至有时 case 更多；真正的差距在 defect hypothesis、killer case、Red evidence、coverage report、change-size control 和 structured output。这说明 `tdd-workflow` 的核心价值是 TDD 治理，而不是单纯“更会写测试”。

## 7. 什么时候适合用，什么时候不该硬用

| 场景 | 是否适合 | 原因 |
|------|----------|------|
| 新功能、缺陷修复、API 改动 | 非常适合 | 这是它的核心使用场景 |
| 安全敏感逻辑测试 | 非常适合 | killer case 和 risk-path gate 很有价值 |
| 给已有代码补测试 | 非常适合 | characterization 路径非常实用 |
| 并发或时序敏感代码 | 非常适合 | determinism gate 能避免伪稳定测试 |
| 很小的纯函数修复 | 适合但可轻量执行 | 通常走 S-size 预算即可 |
| 只想快速补几条 smoke test | 不一定最优 | 它会显著提高过程要求 |

## 8. 结论

`tdd-workflow` 的真正亮点，不是它能替你生成更多测试，而是它把 TDD 里最容易被偷换概念的几件事制度化了：先定义缺陷假设，再安排 killer case，再保留 Red -> Green 证据，再检查覆盖率是否真正触达风险路径，最后把残余风险和评分结果一起交付出来。

从设计上看，这个 skill 很清楚地体现了一条原则：**高质量 TDD 的关键，不是测试文件写在实现之前这一件事本身，而是让每一条测试都知道自己在防什么、让每一轮 Green 都有前置 Red 作为证据、让每一次 refactor 都不偷偷改行为、并让整个过程能被别人复核。** 这也是它特别适合 Go 服务开发、缺陷修复、安全敏感逻辑测试和 legacy code 补测试场景的原因。

## 9. 文档维护

当以下内容发生变化时，这份文档应该同步更新：

- `skills/tdd-workflow/SKILL.md` 中的硬性规则、6 个强制门禁、工作流程、评分卡、输出契约或 characterization testing 规则发生变化。
- `skills/tdd-workflow/references/boundary-checklist.md`、`tdd-workflow.md`、`api-3layer-template.md`、`fake-stub-template.md`、`anti-examples.md` 或 `golden-characterization-example.md` 中的关键规则发生变化。
- `evaluate/tdd-workflow-skill-eval-report.md` 或 `evaluate/tdd-workflow-skill-eval-report.zh-CN.md` 中支撑本文判断的核心结果发生变化。

建议按季度复查一次；如果 `tdd-workflow` 的缺陷假设规则、关键用例规则、Red 证据定义、覆盖率门禁或改动规模预算有明显重构，则应立即复查。

## 10. 相关阅读

- `skills/tdd-workflow/SKILL.md`
- `skills/tdd-workflow/references/boundary-checklist.md`
- `skills/tdd-workflow/references/tdd-workflow.md`
- `skills/tdd-workflow/references/anti-examples.md`
- `skills/tdd-workflow/references/golden-characterization-example.md`
- `evaluate/tdd-workflow-skill-eval-report.md`
- `evaluate/tdd-workflow-skill-eval-report.zh-CN.md`
