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
- `skills/systematic-debugging/references/scope-and-severity.md`
- `skills/systematic-debugging/references/safety-and-authorization.md`
- `evaluate/systematic-debugging-skill-eval-report.md`
- `evaluate/systematic-debugging-skill-eval-report.zh-CN.md`

## 11. 2026-08-27 结构调整——针对外部评审的加固

一次外部评审在当时 500 行的 `SKILL.md` 中发现了七个具体缺陷，动手修改前逐一对照实际文件做了独立验证（遵循本仓库 `skill-quality-audit` 的做法——只重排结构而不复核事实，只会把原有错误包装得更像是对的）：

1. **规则冲突**：P2 严重级别行的"简化：Phase 1 + 4"快捷方式，与"必须依次完成每个阶段"以及 Critical 门禁 C1 无条件要求的"Phase 1-3 证据"直接矛盾——按 skill 自己给出的 P2 快捷方式走完，反而会自动让 C1 判 FAIL。
2. **缺少仅诊断模式**：skill 的触发描述包含"diagnosing, investigating"，但流程无条件强制进入 Phase 4（实施修复），当用户并未要求或授权修改代码时也没有任何机制可以止步于根因。
3. **规则过于机械**："三个假设被否决后，你很可能对系统的心智模型是错的"这句话被当作近乎必然的结论；而完整的九段报告 + Scorecard 对所有情况都是强制的，即便是 skill 自己的 `bug-type-strategies.md` 里明确说只需要"Phase 1 Step 1"就够了的简单情况。
4. **安全门禁不足**：`allowed-tools` 预先批准了 `git init`（在这个工作流里没有任何正当用途）和 `rm -rf node_modules`（破坏性操作，且未经确认）；P0 协议允许直接回滚、热修复或切流量，却没有授权、证据保全或回滚风险方面的要求。
5. **可验证的事实错误**："8 类 bug 分类"的说法对不上参考文件里实际的 6 个分类；把 `find-polluter.sh` 描述成"自动二分查找定位"，但该脚本其实是顺序线性扫描；脚本里 `|| true` 悄悄吞掉了退出码，导致"这个测试根本没跑起来"和"这个测试跑得很干净"在输出上无法区分；`defense-in-depth.md` 的"每一层都要加校验"与 Phase 4 的"只做一个最小改动，不要打包"之间存在未被说明的张力。
6. **测试偏浅**：66 个测试都是真实存在且全部通过的，但 golden scenario 的断言只检查 `SKILL.md` 加参考文件里是否*包含*某些字符串，并不检查模型拿到一个具体场景后*产出*的报告质量好不好——这一点 skill 自己的 `COVERAGE.md` 其实已经如实记录过。
7. **评估分数已过时**：`evaluate/systematic-debugging-skill-eval-report.md` 里的 8.76/10，是针对一个 296 行、只有 3 个场景的旧版本测出来的，报告原文自己也说这个提升主要在流程纪律而不在修复质量——它并不能代表（当时）已经 500 行的当前版本。

**对应的修复，顺序与上面一致：**

1–2. 新增了**范围与模式（Scope & Mode）**的判定（见 `references/scope-and-severity.md`）：仅诊断 / 诊断并修复 / P0 事故三种模式，每种都有明确的停止点和 Fix Plan 写法。C1 也改写为跟随所声明的模式/严重级别走，而不再是一条会被文档里明写的快捷方式违反的无条件门槛。
3. 重新表述了 Phase 3 里关于假设被否决的措辞——假设被否决是廉价且正常的过程，真正该触发"质疑架构"的信号被移到了 Phase 4 里**修复尝试**的失败（真正改了代码却没解决问题），这是分量明显更重的证据。报告的详略现在按严重级别/模式分档，并给出了明确的 N/A 计分约定（Scorecard 里不适用的项按"因不适用而通过"计分，但必须写明一句理由，不能悄悄判过、也不能完全免于说明）。
4. 从 `allowed-tools` 中移除了 `git init` 和 `rm -rf node_modules`（回退到正常的权限确认流程，不再被预先批准）；新增 `references/safety-and-authorization.md`，覆盖 `env` 的敏感信息脱敏、`tcpdump` 的载荷谨慎处理，以及 P0 场景下的授权、证据保全和回滚风险要求。
5. 修正了分类数量和算法描述，使其与实际文件一致；修复了 `find-polluter.sh`，让 runner 执行失败会被显示出来而不是被吞掉；在 `defense-in-depth.md` 里补充了一段调和说明——针对同一个已确认根因、跨多层加校验仍然算一次修复而不是打包，但和已确认根因无关的校验依然算打包。
6. 增加了一批针对性的一致性/变异测试，用来在上述每个问题回归时能被立刻捕获（分类数量交叉核对、"二分查找"说法的缺失校验、模式与 C1 的交叉引用、破坏性命令的排除校验），而不是在这一轮里就试图把基于关键词的 golden 测试全部替换成真实的 LLM-in-the-loop 评估——那需要复用评估报告自己的子代理方法论、并针对当前文件重新跑一遍，超出了这次一致性加固的范围，因此记录在 `COVERAGE.md` 的 Known Gaps 里作为后续工作，而不是悄悄暗示已经做完。
7. 在两份评估报告的开头都加了一条"已过时"的说明，而不是在没有重新跑评估的情况下编造一个新分数。

对 `SKILL.md` 本身的净效果：500 行 → 319 行，新增的模式判定和安全细节被下沉到两个新的参考文件（`scope-and-severity.md`、`safety-and-authorization.md`）而不是直接堆进主文件——这与本 skill 自己一贯的渐进式披露风格是一致的。词数/字节数是反方向变化的（2931 词 → 约 3100 词）——文件变得更容易浏览，但并没有变得更"小"，因为新增的模式判定、N/A 计分、安全门禁都是真实新增的区分，不是单纯的重排。行数减少是一次实实在在的可读性收益，但不是 token 成本上的收益，这份文档也不打算把两者混为一谈。

## 12. 2026-08-27 第二轮——补上契约、安全与验证方面的剩余缺口

第一轮改完之后，第二轮评审又发现了七个问题，同样是逐一重新核实之后才动手修：

1. **Scorecard 和 Output Contract 没同步**：第一轮给 `SKILL.md` 和新增的 `scope-and-severity.md` 加上了模式判定和 N/A 约定，却没有同步进 `references/debugging-report-scorecard.md` 本身（它的 C1/C4/H2 那几行还是旧的、不区分模式的措辞）。另外，与第一轮的改动无关，`output-contract-template.md` 里"以下任一情况即判 FAIL"的清单（覆盖缺少边界证据、断言未经验证这两条）一直没有和 Scorecard "Standard 只需 4/6"的门槛调和过——一份报告完全可能 S2 和 S4 同时不过（6 项里错 2 项），剩下几项刚好凑够 4/6，于是在明显缺边界证据、验证也不诚实的情况下，整体照样判 PASS。
2. **仅诊断模式自相矛盾**：`scope-and-severity.md`（第一轮新增）明确允许在仅诊断模式下描述一个打了标签、未落地的修复方案；`SKILL.md` 的 Output Contract 却说"仅诊断模式下不要 propose 实现层面的改动"——两处用同一个"propose"指代两件不同的事（描述 vs. 落地实现），读起来就是直接矛盾。另外，`output-contract-template.md` 的 Verification 一节无条件要求证明"原症状已经消失"，而这对一个根本没有落地修复的模式来说，从定义上就不可能做到。
3. **`find-polluter.sh` 对自动化系统来说依然不可靠**：第一轮加了一条人能看到的警告，用来提示某次测试运行失败了，但脚本在"每一次运行都失败"的情况下依然 `exit 0`（成功）——只看退出码的自动化调用方，会把"完全没跑成"读成"确认干净"。
4. **`allowed-tools` 和第一轮新增的安全 reference 各说各话**：`safety-and-authorization.md` 把清缓存类命令（`go clean`、`mvn clean`）归类为"会改变状态、需要说明理由"，但 `allowed-tools` 依然毫无摩擦地预先批准它们，读起来像是自相矛盾（其实不算——它们风险低、可恢复，跟 `rm -rf`/`git init`不一样——但文档从来没这么说清楚过）。另外，`env` 的脱敏规则被表述成"展示之前"要做的事，但实际的敏感信息泄露发生在命令执行的那一刻、进入工具输出的时候——报告里的脱敏改不了这件已经发生的事，真正管用的防线是从一开始就少 dump。
5. **`defense-in-depth.md` 示例里有一个真的 bug**：`normalized.startsWith(tmpDir)` 是经典的路径前缀判断缺陷——`/tmp-evil` 作为字符串能通过 `startsWith('/tmp')` 检查，但它明明不在 `/tmp` 里面。另外，文档"为什么要多层"和"关键洞见"两节把第 4 层（调试日志）也算进"让 bug 结构性不可能发生"的功劳里，但日志本质是可观测性，不是预防——它什么都拦不住，它的价值是让下一次出现同类缺口时能被快速定位。
6. **依然缺少真实的行为验证**：第一轮刻意没有编造一次 LLM-in-the-loop 评估，而是如实记成后续工作，没有半途去做。第二轮评审明确点名要这三块（仅诊断、P2 简化、未授权 P0）的真实验证，所以这一轮就把它做了：三个方向、五次真实运行（详见下文），不再第二次往后拖。
7. **词数/字节数依然在增长**：这一点如实记录为观察结论，而不是当作新缺陷来"修"——见本节正上方那条说明，与本节同时加上去的。

**对应的修复，顺序与上面一致：**

1. 给两份文件都新增了第五条 Critical 标准 **C5**（Reporting Integrity——没有真正执行过的命令/profile/trace/verification 不能被声称执行过），同时收紧了 **C3**，要求多组件问题必须在*真正出问题的那个环节*上有边界证据。这把两条会引发矛盾的规则收进了 Critical 层（无条件 FAIL），而不再留在可以被抵消的 Standard 层里——S2、S4 仍然留在 Standard，但现在变成了真正意义上更"软"、更"广"的完整性检查（覆盖所有边界而不只是出问题的那个；追求详尽而不只是诚实），这样容忍 6 项里错 2 项才不会自相矛盾。`output-contract-template.md` 里"以下任一情况即判 FAIL"的清单被改写为明确说明：这五条就是五个 Critical 标准的另一种表述，不是叠加在上面的第六条规则，而且永远不会被 Standard/Hygiene 的分数抵消。`debugging-report-scorecard.md` 的 H2 现在也包含了"mode"。
2. 把两处文字都改成区分*描述*一个修复方案（仅诊断模式下允许，但要清楚标注为尚未落地的分析）和*实施*一个修复（这才是被门禁住的动作）。`output-contract-template.md` 的 Verification 一节现在会区分模式：诊断并修复 / P0 的报告要证明症状已经消失；仅诊断的报告转而要证明根因机制本身是对的，因为根本没有落地的修复可供验证。
3. `find-polluter.sh` 现在只要有任何一次运行没能正常执行，就会返回一个独立的退出码（4，已在脚本头部注释里写明），并打印带 `INCOMPLETE:` 前缀的消息，而不再 `exit 0`。对应的测试也改成了断言这个新行为，而不是像原来那样把"全部运行失败"的场景断言成退出码 0——这正是评审抓到的问题：测试本身内置了它应该去抓的那个 bug。
4. `safety-and-authorization.md` 现在明确写清楚了为什么 `go clean`/`mvn clean` 依然被预先批准（可恢复，不涉及运行时拼出来的目标路径），而 `rm -rf`/`git init` 不是（不可恢复，且/或涉及运行时拼出来的路径）——这是一条写明的风险分级规则，而不再是一处看起来自相矛盾的地方。`env` 的指引现在优先要求"默认用有针对性的查找"，并解释了脱敏作用于*报告*，而不是*已经执行完的命令输出*——真正管用的防线是从源头减少 dump 的范围。
5. 修好了 `startsWith` 的示例，改为同时检查路径分隔符边界（`normalized === tmpDir || normalized.startsWith(tmpDir + sep)`），并加了一句注释说明为什么原来那种写法是错的。改写了"为什么要多层"和"关键洞见"两节，把"结构性不可能发生"的功劳只归给第 1-3 层，第 4 层则重新定位为"下次万一出问题也能很快定位"——这是一个真实但不同的价值，不该混进前面那个说法里。
6. 通过全新、与本次编写会话没有共享上下文、事先也不知道自己在被测试的子代理，针对小型合成代码库跑了五次真实场景：仅诊断模式（通过）、没有明确授权的 P0（通过），以及 P2 假设简化路径（跑了三次——前两次模型都判断 bug 太琐碎、根本不需要走任何正式流程，直接就把它修了，这本身也是关于触发边界的一个真实、有价值的发现；第三次给了一个需要真正（哪怕很小）跨两个文件调查的场景，模型才调用了这个 skill，并且明确点名引用了简化规则，但也把 Standard 层的 S2 错误标成了 N/A——这是一次真实、由现场测试才抓到的、违反 `scope-and-severity.md`"只有 C1/C4 才能标 N/A"规则的问题，已经在该文件和 `COVERAGE.md` 的记录里改正，而不是含糊过去）。这是真实的行为证据，不是一次打分评估的替代品——`COVERAGE.md` 里也没有把它包装成后者。全部五次运行的原始 JSONL transcript 都保存在了 `evaluate/systematic-debugging-live-scenarios-2026-08-27/`，不再只是一份转述性的总结——上一轮评审准确指出"transcript 没有保存"会让原来的记录没法复核，这次是靠真的把它们存下来解决的，不是靠辩解说不存也没关系。
7. 除了本节正上方已经加上的如实说明之外，没有再做别的处理——进一步压缩字节数并不在评审给出的必做清单里，而如果为了这个指标去牺牲这一轮新增的模式/安全内容，那就是拿一个真实的修复去换一个表面的数字。

针对第 1、3、5 点专门新增了回归测试（H2/C5 是否同步、`find-polluter.sh` 的 INCOMPLETE 退出码、`defense-in-depth.md` 的边界检查），这样每一处修复都是可被检验的回归项，而不只是一次性改一下就算了。

## 13. 2026-08-27 第三轮——修正第二轮自己留下的错误

第三轮评审审的是第二轮改动本身——包括那次真实场景的记录——发现了四个问题，其中两个其实是第二轮自己文档里的错误，不是 skill 设计本身的问题：

1. **Output Contract 模板漏了 Mode 字段**：第二轮要求 H2（在 `SKILL.md` 和 `debugging-report-scorecard.md` 里都是）对 severity/mode/bug type 三项都做分类，却从来没有真的往 `output-contract-template.md` 的 Triage 一节里加一行 `Mode:`——照模板字面填报告的人，根本没地方写这个字段。
2. **第二轮自己的 live scenario 打分里有一个真的错误**：P2 第三次尝试的子代理把 Standard 层的 **S2** 标成了 N/A。`scope-and-severity.md` 明确说过只有 C1、C4 才能标 N/A——S2 本该按普通 PASS 计分（单组件问题"所有相关边界都覆盖了"这句话本来就是空泛地成立的）。第二轮的 `COVERAGE.md` 记录却把这个写成"正确应用"，这个判断是错的——它把一次真实的规则违反打成了成功，而这份文档本来存在的目的，恰恰就是抓这种错误。
3. **声称做了真实验证，却没有留存证据**：第二轮一边说"完整 transcript 没有保存"，一边自己也把场景数量数错了（正文写"四次"，表格却列了五行——仅诊断、P0，加三次 P2 尝试）。这两个都是第二轮自己文档层面的缺陷：一份没法复核的总结，加上描述这份"证明严谨性"的证据时犯的一个数数错误。
4. **`env`/`tcpdump` 仍然裸露在 `allowed-tools` 里**：第二轮的 `safety-and-authorization.md` 已经正确解释过"报告里再脱敏，也改不了命令执行那一刻已经发生的泄露"，但第二轮没有把这个逻辑用到 `allowed-tools` 本身的授权上，这两个命令依然是预先批准、不需要逐次确认。

**对应的修复，顺序与上面一致：**

1. 在 `output-contract-template.md` 的 Triage 一节里加上了 `Mode: diagnose-only|diagnose-and-fix|P0-incident`，并指向 `scope-and-severity.md`。
2. 把 `COVERAGE.md` 的记录改成如实描述 S2/N/A 是一个打分错误，而不是对约定的合理扩展；同时加强了 `scope-and-severity.md` 里 N/A 规则的措辞，明确点名 S2 作为"其他标准都不算"这句话的例子——毕竟已经有一个真实模型在这个边界上判断错了一次。
3. 把全部五次 live scenario 的原始 JSONL transcript 都拷贝进了 `evaluate/systematic-debugging-live-scenarios-2026-08-27/`（配了一份 `README.md`，把文件和场景对应上，也直接写明了 S2 打分错误这件事），不再只是断言"不保存也没关系"；把文档里所有写错的"四次"都改成了"五次"，包括这份文档自己。
4. 把 `env*`、`tcpdump*` 从 `allowed-tools` 里去掉了（跟第一轮对 `git init`/`rm -rf` 的处理一样）——现在这两个命令都需要逐次明确确认；`safety-and-authorization.md` 和 `SKILL.md` 里对应的检查清单也更新成了这个说法，并且仍然建议一旦获得确认，就优先用有针对性的查找、限定抓包范围。

第 2、3 点值得说清楚：这两个不是第三轮编写会话新引入的缺陷——是第二轮自己的编写会话在试图增加严谨性的过程中犯下的错误（一次真实验证的努力，本身却带着一个打分错误和一处文档疏漏）。把这件事记下来、而不是悄悄改掉不提，正是这个 skill 对调试报告要求的"不能有沉默的错误"标准，用在加固这个 skill 本身的过程上。
