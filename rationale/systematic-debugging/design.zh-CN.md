---
title: systematic-debugging skill 设计解析
owner: awesome-skills maintainers
status: active
last_updated: 2026-03-27
applicable_versions: current repository version
---

# systematic-debugging skill 解析

`systematic-debugging` 是一套把调试工作从“直觉修补”改造成“先找根因、再谈修复”的调查框架。它的核心设计思想是：**调试任务的目标是先分级、再收集证据、再形成单一假设、再做最小验证，最后才进入修复与验证，并把整个过程以可审查、可判定 PASS/FAIL 的报告形式交付出来。** 因此它把严重级别分诊、铁律、四个阶段、假设纪律、修复尝试门禁、评分卡和输出契约串成了一条强约束流程。

## 1. 定义

`systematic-debugging` 用于：

- 调试测试失败、线上异常、间歇性问题、性能回退、构建失败、第三方故障等技术问题
- 要求在永久修复前先完成根因调查
- 用显式假设、边界证据和数据流追踪来定位问题来源
- 在 P0 场景中先止血，再回到完整根因分析
- 用报告结构和评分标准约束调试质量

它输出的不只是修复建议，还包括：

- triage
- reproduction
- evidence collected
- hypothesis log
- root cause
- fix plan/change
- verification
- residual risk/follow-ups
- 评分卡

从设计上看，它更像一个“调试治理框架”，而不是一个只会根据错误信息直接给修复方案的提示词。

## 2. 背景与问题

这个 skill 要解决的，不是“模型不会修 bug”，而是调试任务天然容易被几种高风险冲动带偏：

- 看到症状就直接下手改
- 一次改多个地方，破坏归因
- 修复后不验证，只凭感觉宣布完成

如果没有流程约束，常见问题通常集中在 8 类：

| 问题 | 典型后果 |
|------|----------|
| 不先做根因调查 | 直接修症状，问题很快复发 |
| 不先确认复现 | 以为修好了，其实只是没再撞到 |
| 不查最近变更 | 错过最可能的触发因素 |
| 不看环境健康 | 把磁盘满、端口冲突、OOM 当代码 bug 修 |
| 不做边界证据收集 | 多组件系统里不知道究竟哪层坏了 |
| 不写显式假设 | 根因和猜测混在一起 |
| 一次尝试多个修复 | 无法知道究竟哪一个起作用 |
| 连续失败还不质疑架构 | 进入 Fix #4、Fix #5 的无效试错循环 |

`systematic-debugging` 的设计逻辑，就是先把“这个问题属于什么级别、该按什么策略调查、证据是否足够支持根因、修复是否真正经过验证”说清楚，再允许进入实现阶段。

## 3. 与常见替代方案的对比

先看它与几种常见做法的区别：

| 维度 | `systematic-debugging` skill | 直接让模型“修这个 bug” | 手工经验式调试 |
|------|------------------------------|--------------------------|----------------|
| 根因优先纪律 | 强 | 弱 | 中 |
| 显式阶段结构 | 强 | 弱 | 弱 |
| 假设与验证分离 | 强 | 弱 | 中 |
| 多边界证据收集 | 强 | 弱 | 中 |
| 抗冲动修补能力 | 强 | 弱 | 弱 |
| P0 止血与根因拆分 | 强 | 弱 | 中 |
| 调试报告可审查性 | 强 | 弱 | 弱 |
| PASS/FAIL 质量判定 | 强 | 弱 | 弱 |

它的价值，不只是让调试说明更像报告，而是把调试从一次性的“试试看”提升成带证据、带门槛、带复核的工程流程。

## 4. 核心设计逻辑

### 4.1 先做 严重级别分诊 vs 一上来分析代码

`systematic-debugging` 要求在进入四个 phase 之前先判定：

- `P0`
- `P1`
- `P2`

这一步非常关键，因为不同严重级别的调试目标并不相同。P0 首先是运营问题，要先止血；P1 要完整走四阶段流程；P2 则允许采用简化路径，通常以 Phase 1 + Phase 4 为主，并在根因已经很清楚时跳过 Pattern Analysis。skill 因此把“mitigate first, investigate second”写进 P0 协议，而不是把所有故障都当成同一类调试任务来处理。

这层设计的价值在于，它把“先恢复服务”和“找出永久修复”拆成两个动作，避免在紧急故障里为了追求优雅根因而延误恢复，同时也避免把临时 mitigation 误当成真正修复。

### 4.2 `铁律` 要写得这么绝对

这个 skill 的铁律是：

```text
NO FIXES WITHOUT ROOT CAUSE INVESTIGATION FIRST
```

这不是风格偏好，而是整个 skill 的核心约束。它明确禁止：

- 先修再查
- 先堆多个改动再看结果
- 先提永久修复，再补调查

也正因为这条铁律，skill 才需要把 diagnostic instrumentation 单独豁免出来。临时日志、断点、probe script 不是 fix，而是观察手段。这样既保住了“先调查”的原则，也避免把必要的证据采集误当作违规实现。

### 4.3 四阶段结构是这个 skill 的骨架

`systematic-debugging` 把调试固定拆成：

1. Root Cause Investigation
2. Pattern Analysis
3. Hypothesis and Testing
4. Implementation

这四步不是文档结构美化，而是为了防止几种常见跳步：

- 从症状直接跳到修复
- 看完根因就不再做 working example 对比
- 还没形成单一假设就开始动代码
- 修完之后不跑显式验证

评估也非常清楚地说明了这点：without-skill 的默认结构更像 `Root Cause -> Fix -> Test`，而 with-skill 则能稳定给出 Phase 1→2→3→4 的完整分层。这说明 skill 的核心增量之一，不是更强的 bug 修复能力，而是更可靠的过程结构。

### 4.4 显式 Hypothesis 是关键设计 vs 写作要求

`systematic-debugging` 强制要求写出类似：

> I think X is the root cause because Y

并且一次只保留一个假设、一个最小测试。

这层设计特别重要，因为调试里最常见的失真不是完全没思路，而是把“当前最可能的解释”误当成“已经确认的根因”。显式假设迫使调试者回答：

- 我现在认为根因是什么
- 证据支持它的哪一部分
- 还有什么证据可能推翻它

这让 Phase 3 成为真正的科学方法步骤，而不是“把直觉写得更正式”。

### 4.5 强调“一次一个假设，一次一个最小改动”

这个 skill 明确禁止 bundled changes，并要求：

- one hypothesis at a time
- one minimal test per hypothesis
- one fix at a time

这是个很强的设计，因为调试失败最常见的来源之一，就是把多个可能原因一起改掉。这样即使问题暂时消失，也没人知道到底哪一项才是真正起作用的修复。skill 因此强制维护 attribution，使调试结果不仅“能过”，而且“知道为什么能过”。

### 4.6 Environment Health Check 被放进 Phase 1

`systematic-debugging` 在以下症状下会显式要求先查环境健康：

- 间歇性失败
- timeout
- works on my machine
- silent process death
- 没有明显代码原因

并给出 `df -h`、`lsof`、`dmesg`、`nslookup` 等系统命令。

这层设计很成熟，因为很多“看起来像代码 bug”的问题，其实是：

- 磁盘满
- OOM
- 端口冲突
- DNS/网络问题
- 文件描述符耗尽

skill 把环境检查前置，相当于明确承认：不是所有异常都应该先钻进代码里找答案。这个设计能显著减少在错误层级上浪费时间。

### 4.7 多组件系统必须做 Boundary 证据

对于 CI -> build -> signing 或 API -> service -> database 这样的多层系统，skill 明确要求：

- 在每个边界记录输入
- 在每个边界记录输出
- 验证环境和配置是否传播
- 用一次观测确定“断在了哪一层”

这层设计非常关键，因为多组件问题最容易出现的误判，就是在某一层看到错误后直接把这一层当根因。Boundary evidence 要求调试者先建立证据链，而不是凭借位置接近性下结论。评估里的多层错误映射场景，也正体现了这条规则的价值。

### 4.8 Phase 2 要保留 Pattern Analysis

很多人会问：既然 Phase 1 已经查根因了，为什么还要单独做 Pattern Analysis？

原因在于根因调查回答的是“哪里坏了”，而 Pattern Analysis 回答的是：

- 有没有相似但正常工作的代码
- 参考实现到底怎么写
- broken 和 working 的差异到底有哪些
- 当前组件还依赖哪些隐含前提

这是 skill 用来防止“看到一个 plausible root cause 就立刻改”的缓冲层。评估里 without-skill 在部分场景中会缺失 working example comparison，这说明这一步并不会稳定自然出现，因此保留成独立阶段仍然有价值。

### 4.9 “修复尝试门禁”要在三次失败后强制升级

这个 skill 明确规定：

- 3 个 hypothesis 或 3 个 fixes 失败后
- 必须停止
- 必须重新质疑 mental model 或 architecture
- 不允许无上限进入 Fix #4

这层设计非常有价值，因为很多调试失败并不是单次技术判断错了，而是整个问题被放进了错误的架构假设里。连续失败 3 次后继续小修小补，通常意味着问题不在“这一行逻辑写错了”，而在“这套结构是否本来就不适合”。skill 把这个升级点写死，避免试错无上限蔓延。

### 4.10 P0 协议要求“先止血，后调查”

P0 场景下，skill 要求：

1. 先执行 rollback / 功能开关切换 / failover / 定向 hotfix
2. 验证 mitigation 生效
3. 然后在 24 小时内启动完整根因调查

这层设计很重要，因为它解决了一个常见误解：先止血是不是等于跳过调试流程？skill 的答案是，不是。mitigation 是运维动作，permanent fix 才属于调试动作。两者分开后，既不会为了“严格流程”而耽误恢复，也不会为了“先救火”而永远不回到根因。

### 4.11 把调试报告质量也纳入强约束

`systematic-debugging` 不只管调试动作，还要求最终报告显式给出评分卡结论：

- Critical
- Standard
- Hygiene

并给出明确的 PASS/FAIL 规则。

这层设计非常强，因为很多调试结果表面上有：

- root cause
- fix
- test

但实际上：

- 根因还是症状
- 证据不足
- 假设日志缺失
- 验证语焉不详

评分卡的作用，就是把“报告看起来完整”和“报告足够可信”区分开来。它允许某次调试结果被明确判成 `FAIL`，而不是默认每份报告都算通过。也正因如此，这个 skill 的输出不仅是技术结论，也是质量可判定的调试产物。

### 4.12 固定顺序的输出契约

这个 skill 要求调试报告按固定顺序输出：

1. 问题分级
2. 复现
3. 已收集证据
4. 假设日志
5. 根因
6. 修复方案与改动
7. 验证
8. 剩余风险与后续动作
9. 评分卡

这层设计解决的是一个非常实际的问题：如果报告结构不固定，reviewer 很难快速判断：

- 是否先调查后修复
- 有没有显式假设
- 根因是不是源头
- 验证是否真实做过

固定顺序把这些判断变成可检查结构，而不是阅读者的主观印象。

### 4.13 references 采用按症状加载

`systematic-debugging` 的 references 不是一口气全读，而是按问题类型加载：

- 深栈问题读 `root-cause-tracing.md`
- 数据守卫问题读 `defense-in-depth.md`
- flaky / async / sleep 问题读 `condition-based-waiting.md`
- bug 类型不清时读 `bug-type-strategies.md`
- 写报告时读 `output-contract-template.md`
- 打分时读 `debugging-report-scorecard.md`

这种结构很合理，因为调试问题种类极多，但并不是每次都需要把所有调试技巧塞进上下文。skill 把核心纪律留在 `SKILL.md`，把专项技巧按症状触发，从而兼顾覆盖面和 token 成本。

## 5. 这个设计解决了哪些具体问题

结合当前 `SKILL.md`、关键 references 和评估报告，可以把它解决的问题归纳为：

| 问题类型 | skill 中的对应设计 | 实际效果 |
|----------|-------------------|----------|
| 看到 bug 就直接修 | 铁律 + 四阶段流程 | 强制先调查再修复 |
| 根因与猜测混淆 | 假设纪律 | 根因更可验证 |
| 多组件问题断层不明 | Boundary 证据 | 更快定位断点 |
| 环境问题被误当代码问题 | Environment Health Check | 降低错误排查方向 |
| 连续修补失去归因 | 单假设、单最小改动 | 提升 attribution |
| Fix #4 / #5 无限试错 | 修复尝试门禁 | 及时升级到架构层讨论 |
| 调试报告看似完整但不可信 | 输出契约 + 评分卡 | 更易评审与复核 |
| 紧急事故里先修补后遗忘根因 | P0 protocol | 同时兼顾恢复与根因分析 |

## 6. 主要亮点

### 6.1 它把调试从“修 bug”改造成“调查 bug”

这是整个 skill 最核心的升级。先收集证据，再允许修复。

### 6.2 四阶段结构是最显著的流程亮点

Phase 1→2→3→4 把调查、分析、假设和实现拆开，防止调试塌缩成“看一眼就改”。

### 6.3 显式假设机制非常关键

它强迫调试者把“我觉得是这个原因”变成可验证命题，而不是隐性直觉。

### 6.4 环境健康与边界证据让它对真实系统更有用

很多调试流程只盯代码；`systematic-debugging` 把操作系统、配置传播、多层边界一起纳入根因调查。

### 6.5 它对“调试冲动”有明确反制

Red flags、3 次失败后升级、P0 先止血后调查，这些都在直接对抗最常见的人类调试坏习惯。

### 6.6 当前版本的真正增量，在流程纪律而不在修复能力

评估已经说明：基础模型在读取错误、追数据流、识别根因、写修复代码方面本来就不弱；真正的差距在 phase structure、显式假设、调查完整性、验证纪律和报告可审查性。这说明 `systematic-debugging` 的核心价值是调试治理，而不是单纯“更会修 bug”。

## 7. 什么时候适合用，什么时候不该硬用

| 场景 | 是否适合 | 原因 |
|------|----------|------|
| 测试失败、构建失败、线上异常 | 非常适合 | 这是它的核心使用场景 |
| 多层调用链或多组件系统问题 | 非常适合 | boundary evidence 很有价值 |
| 间歇性 / flaky / race 问题 | 非常适合 | 假设纪律和证据采集很关键 |
| 时间压力很大、很想 quick fix | 非常适合 | 这正是它最想约束的场景 |
| 明显的一行拼写或编译错误 | 适合但可简化 | 通常可按 P2 简化路径处理 |

## 8. 结论

`systematic-debugging` 的真正亮点，不是它能给出更聪明的修复，而是它把调试里最容易失真的判断系统化了：先分级，再调查，再形成单一假设，再做最小验证，最后才进入实现，并且要求整个过程能被复盘、被评分、被另一个工程师复查。

从设计上看，这个 skill 很清楚地体现了一条原则：**高质量调试的关键，不是更快写出修复，而是更早知道自己到底理解了什么、证据来自哪里、假设有没有被验证、以及这次修复是不是建立在真正的根因之上。** 这也是它特别适合 bug 调试、故障调查和根因分析场景的原因。

## 9. 文档维护

当以下内容发生变化时，这份文档应该同步更新：

- `skills/systematic-debugging/SKILL.md` 中的严重级别分诊、铁律、四阶段流程、强制门禁、评分卡、输出契约或 P0 协议发生变化。
- `skills/systematic-debugging/references/root-cause-tracing.md`、`bug-type-strategies.md`、`defense-in-depth.md`、`condition-based-waiting.md`、`output-contract-template.md`、`debugging-report-scorecard.md` 或 `bad-good-debugging-reports.md` 中的关键规则发生变化。
- `evaluate/systematic-debugging-skill-eval-report.md` 或 `evaluate/systematic-debugging-skill-eval-report.zh-CN.md` 中支撑本文判断的核心结果发生变化。

建议按季度复查一次；如果 `systematic-debugging` 的阶段结构、假设纪律、P0 协议或评分卡 / 输出契约有明显重构，则应立即复查。

## 10. 相关阅读

- `skills/systematic-debugging/SKILL.md`
- `skills/systematic-debugging/references/root-cause-tracing.md`
- `skills/systematic-debugging/references/bug-type-strategies.md`
- `skills/systematic-debugging/references/output-contract-template.md`
- `skills/systematic-debugging/references/debugging-report-scorecard.md`
- `evaluate/systematic-debugging-skill-eval-report.md`
- `evaluate/systematic-debugging-skill-eval-report.zh-CN.md`
