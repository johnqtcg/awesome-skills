---
title: writing-plans skill 设计解析
owner: awesome-skills maintainers
status: active
last_updated: 2026-03-27
applicable_versions: current repository version
---

# writing-plans skill 解析

`writing-plans` 是一套面向多步骤任务实施前置规划的结构化规划框架。它的核心设计思想是：**高质量实施计划的目标是先判断需求是否已经清晰到值得规划、任务是否真的需要正式计划、计划中的路径是否经过验证、风险是否已分级，以及这份计划能否被一个对仓库零上下文的开发者直接执行。** 因此它把需求清晰度门禁、适用性门禁、仓库发现门禁、范围与风险门禁、执行模式、输出契约、评分卡、审阅回路和计划更新协议串成了一条固定流程。

## 1. 定义

`writing-plans` 用于：

- 为 feature、bugfix、refactor、migration、API change、docs-only 任务编写实施计划
- 在真正编码前先完成需求澄清、路径验证和风险分级
- 让计划只停留在接口级、验证级，而不是提前写完整实现
- 根据任务复杂度选择 `SKIP / Lite / Standard / Deep`
- 在计划写完后再经过自检和审阅回路才交付执行

它输出的不只是任务分解，还包括：

- 明确的执行模式
- 具体的目标，以及清晰的范围边界或显式前提假设
- 文件路径标签（`[Existing] / [New] / [Inferred] / [Speculative]`）
- 验证命令
- 回滚 / 风险说明（适用时）
- 执行交接信息

从设计上看，它更像一个“实施计划治理框架”，而不是一个把需求翻译成 checklist 的提示词。

## 2. 背景与问题

这个 skill 要解决的，不是“模型不会写计划”，而是默认的计划写作很容易出现几种高风险失真：

- 需求还不清楚，就先写出一份看起来完整的计划
- 任务其实很小，却被过度工程化成正式计划文档
- 计划里写了很多路径和代码，但这些路径和接口根本没验证过

如果没有明确流程，常见问题通常集中在 8 类：

| 问题 | 典型后果 |
|------|----------|
| 不先检查需求清晰度 | 基于误解写出“幽灵计划”，执行时大面积返工 |
| 不先做适用性判断 | 单文件小改动也写成大计划，计划成本高于执行成本 |
| 路径未验证 | 计划里出现不存在的文件、行号或模块 |
| 计划里混入完整实现代码 | 给人“已经想清楚了”的错觉，实际执行时大概率重写 |
| 不区分风险等级 | migration、auth、public API 变更和普通功能被同样对待 |
| 缺少精确验证命令 | 步骤结束只能写“检查是否可用” |
| 没有审阅者视角 | 计划结构看似正确，但任务依赖、并行关系、验证命令逻辑有漏洞 |
| 执行偏差无协议 | 实际情况和计划不一致时，没人知道该继续、修订还是重写计划 |

`writing-plans` 的设计逻辑，就是先回答“现在是否已经清晰到足以规划、值不值得写正式计划、仓库里哪些路径是真的、哪些只是推断、任务风险有多大、计划写到什么粒度才合适”，再允许进入真正的计划写作。

## 3. 与常见替代方案的对比

先看它与几种常见做法的区别：

| 维度 | `writing-plans` skill | 直接让模型“写个实施计划” | 把需求顺手拆成 TODO 列表 |
|------|-----------------------|----------------------------|---------------------------|
| 需求清晰度门禁 | 强 | 弱 | 弱 |
| 适用性判断 | 强 | 弱 | 弱 |
| 路径验证纪律 | 强 | 弱 | 弱 |
| 模式分级 (`SKIP/Lite/Standard/Deep`) | 强 | 弱 | 弱 |
| 风险 / rollback 设计 | 强 | 中 | 弱 |
| 审阅回路 | 强 | 弱 | 弱 |
| 执行偏差处理 | 强 | 弱 | 弱 |
| 计划可执行性 | 强 | 中 | 弱 |

它的价值，不只是让计划“更完整”，而是把计划从一份看起来专业的拆解文档，提升成一份路径可信、风险明确、可以交给陌生执行者直接落地的工程文档。

## 4. 核心设计逻辑

### 4.1 把 需求清晰度门禁 放在第一位

`writing-plans` 的第一道门禁不是复杂度判断，而是需求清晰度门禁。它先判断需求是否已经“清晰到足以规划”，并在必要时 STOP and ASK。

这层设计非常关键，因为计划工作的最大浪费，往往不是步骤拆得不好，而是计划写错了问题。它明确要求检查：

- 目标是否具体
- 范围边界
- 成功标准
- 约束与兼容性
- 边界情况与错误处理（主要针对 Standard / Deep）

同时它要求澄清问题只问 WHAT，不问 HOW，并限制轮次，防止过度追问。这种设计很成熟，因为它同时防止两种失真：

- 需求太模糊还硬写计划
- 一个本来清楚的小任务被连续盘问

评估里这一点很有代表性：模糊需求场景下，baseline 模型也能自然提问，所以差距没有清晰功能场景那么夸张；但 with-skill 的增量在于能给出结构化 STOP 声明、明确触发维度、以及“澄清后如何重新进入规划流程”的 pipeline。

### 4.2 适用性门禁 比“计划写得好不好”更重要

`writing-plans` 在 2 号门禁 先判断任务是不是值得写正式计划，并分成：

- `SKIP`
- `Lite`
- `Standard`
- `Deep`

这层设计非常有辨识度，因为很多计划失败并不是计划内容本身差，而是任务压根不该写正式计划。比如：

- 单文件、<30 行、小修小补：直接执行
- docs-only、config-only：SKIP 或 Lite checklist
- 单模块清晰 feature：Lite
- 多文件 feature / bugfix：Standard
- 跨模块、migration、架构变更：Deep

它解决的是“计划的形式重量和任务复杂度不匹配”的问题。评估里的 docs-only 场景就是最直观的例子：with-skill 正确走 `SKIP`，而 without-skill 虽然也意识到不需要大计划，但仍直接输出了大段 README 内容，跳过了显式决策和适用性说明。

### 4.3 仓库发现门禁 要求路径四标签体系

在真正写进任何路径之前，`writing-plans` 要求每个路径都标上：

- `[Existing]`
- `[New]`
- `[Inferred]`
- `[Speculative]`

这层设计非常关键，因为“计划文档里的路径是真是假”决定了计划能否执行。它还进一步规定：

- 没读过文件就不要写行号
- 没验证过接口就不要写完整实现代码
- repo 不可访问时进入 Degraded 模式，所有路径统一降级为 `[Speculative]`

这使计划文档里的路径状态从隐式猜测变成显式声明。评估里这一层是 with-skill 与 without-skill 差距最大的地方之一：with-skill 的文件地图全部标注路径状态，without-skill 则容易出现未验证路径甚至推测性端点。

### 4.4 范围与风险门禁 不是附属项

`writing-plans` 在 4 号门禁 要求根据变更大小和风险决定：

- 是否需要 rollback
- 是否需要 phased validation checkpoints
- 是否必须给出 dependency graph

尤其对以下高风险区域，它要求显式 rollback strategy：

- auth/authz
- payment
- database schema
- public API
- concurrency
- infrastructure

这层设计很成熟，因为计划文档如果只会写“怎么做”，不会写“怎么退”，那在真实工程里很难被信任。migration 模板就是这层设计的极端体现：它要求分阶段、每阶段 rollback、每阶段 validation，而不是一把梭。

### 4.5 把模式深度控制得这么细

`writing-plans` 的 `Lite / Standard / Deep` 不只是体量不同，而是内容 contract 不同：

- `Lite`：只有 5-15 行 checklist，不写代码块，不走审阅回路
- `Standard`：完整计划文档，只允许接口级代码块，强制 1 轮审阅
- `Deep`：完整计划 + dependency graph + phased validation + 最多 3 轮审阅

这层设计的意义，在于防止“所有计划都往最重格式靠拢”。如果没有 mode-specific contract，模型很容易把每个任务都写成 Deep 计划，导致：

- 文档负担过重
- 执行者注意力被低价值细节分散
- 实际工作迟迟不能开始

而 mode-specific 深度控制，正是在保证计划“够用”的同时，避免过度工程化。

### 4.6 明确禁止在计划里写完整实现代码

这个 skill 对代码粒度有非常严格的限制：

- `Lite` 不写 code block
- `Standard / Deep` 强制使用 `[interface]`、`[test-assertion]`、`[command]`、`[speculative]` 这些代码块标签；其中 `Deep` 还可以包含 data flow sketches、migration SQL、sequence outlines
- 明确禁止完整实现代码进入计划

这层设计非常关键，因为完整实现代码在计划阶段最容易制造一种错觉：看起来计划很具体，实际上这些代码既没编译，也没跑测试，而且很可能在真正实现时被整体推翻。

评估里 clear feature 场景下，without-skill 的最大问题之一正是直接在计划里写了完整 Config struct、handler 逻辑和 token service 代码；with-skill 则只保留接口级轮廓和测试级断言。这说明 `writing-plans` 的目标不是提前编码，而是提前约束实现边界。

### 4.7 每个任务都必须带精确 verification command

`writing-plans` 明确要求每个 task 至少有 1 个 runnable verification command，而且不能用“check that it works”这类模糊表达。

这层设计非常重要，因为计划是否可执行，不取决于步骤写得多漂亮，而取决于执行者能不能在每一步后客观判断：

- 成功了没有
- 是 build success 还是 behavior 正确
- 是局部验证还是 broader regression

这也是 reviewer checklist 中 `SB3` 被列为阻塞项的原因之一：如果 verification command 跑得通，但根本不验证声称的行为，那这份计划在逻辑上仍然不成立。

### 4.8 审阅回路 是强制而且独立于自检结果

`writing-plans` 在写完计划后要求两步：

1. 自检 / 格式门禁
2. 审阅回路 / 内容门禁

并明确规定：

- `Lite` 跳过审阅回路
- `Standard` 必须 1 轮
- `Deep` 最多 3 轮
- 审阅回路不因为自检全过而省略

这层设计很有深度，因为它承认了一件事：格式正确不等于逻辑正确。评分卡能发现：

- path label 缺失
- code block 类型错误
- verification command 缺失

但审阅回路才能发现：

- 任务依赖顺序其实不成立
- 并行任务共享写同一个文件
- 命令跑得通但验证不了目标行为
- 计划 silently 超出原始 scope

这也是为什么 `references/reviewer-checklist.md` 特别把 `SB1`、`SB3`、`SB4` 标成 Standard / Deep 的 blocking items。

### 4.9 SKIP 和 Degraded 模式 都要单独写进 contract

这个 skill 有两个非常成熟的边界设计：

- `SKIP`：任务不需要正式计划
- `Degraded 模式`：repo 不可访问，路径无法验证

它们的重要性在于，它们都在阻止模型“继续假装一切正常”。如果没有 `SKIP`，docs-only 变更会被过度工程化；如果没有 `Degraded 模式`，路径验证失败时模型会开始胡乱补文件路径。

评估和 golden fixtures 都说明，这两个分支不是边角补丁，而是 skill 正常 contract 的组成部分。

### 4.10 计划更新协议 很关键

`writing-plans` 不把计划当成一次性静态文档，而是明确规定执行偏差时要记录：

- `[Deviation]`
- planned X -> actual Y
- reason
- impact
- downstream adjustment

并分成：

- Trivial
- Significant
- Breaking

这层设计非常有工程价值，因为计划执行过程中偏差是常态。真正重要的是偏差出现时，团队有没有共同语言来判断：

- 记一下继续走
- 改后续任务
- 暂停并重规划

特别是 `>30%` 任务出现显著偏差时要求 reassess plan，这让计划文档不再是“写完就失效”的静态产物，而是可维护执行文档。

### 4.11 模板体系是核心支撑 vs 装饰

`writing-plans` 不是一份泛化 planning prompt，而是为不同类型任务提供了 plan template：

- feature
- bugfix
- refactor
- migration
- API change
- docs-only

每种模板都把该类任务最重要的 section 固化下来。例如：

- feature 强调向后兼容性
- bugfix 强调 bug reproduction 与 regression scope
- migration 强调 phased execution、rollback、validation、lock analysis
- docs-only 模板主要服务 `SKIP` / `Lite`

这种设计很好地解决了“不同任务的计划长得都一样”的问题，让计划结构与任务类型真正对齐。

### 4.12 真正的增量在前置治理，而不在自然语言拆解能力

评估已经说明，baseline 在模糊需求场景下也能自然提问题，在 docs-only 场景也能大致意识到不需要复杂计划。真正的差距在于 with-skill 额外提供了：

- 4-Gate 流程
- 路径四标签体系
- 代码块语义标签
- `SKIP / Lite / Standard / Deep` 明确判定
- 审阅回路
- 输出契约

这说明 `writing-plans` 的核心价值不是“比 baseline 更会拆步骤”，而是“比 baseline 更会决定什么时候该计划、计划该写到什么粒度、以及怎样让计划成为真正可执行文档”。

## 5. 这个设计解决了哪些具体问题

结合当前 `SKILL.md`、关键 references 和评估报告，可以把它解决的问题归纳为：

| 问题类型 | skill 中的对应设计 | 实际效果 |
|----------|-------------------|----------|
| 需求模糊时硬写计划 | 需求清晰度门禁 | 计划更少返工 |
| 小任务也被过度工程化 | 适用性门禁 + `SKIP/Lite` | 计划成本更合理 |
| 计划里出现幽灵路径 | 仓库发现门禁 + 四标签体系 | 文件地图更可信 |
| 计划提前写成实现代码 | Code Level Rules + anti-examples | 计划边界更清楚 |
| 风险任务没有 rollback | 范围与风险门禁 + templates | 执行更安全 |
| 步骤不可验证 | Mandatory verification commands | 计划更可执行 |
| 结构对了但逻辑仍错 | 审阅回路 | 计划更稳健 |
| 执行偏差无人处理 | 计划更新协议 | 计划更可维护 |

## 6. 主要亮点

### 6.1 4 个门禁的前置流程是整个 skill 的核心骨架

它先判断能不能计划，再判断值不值得计划，再判断路径是否可信，最后判断风险和 rollout 需求。

### 6.2 `SKIP / Lite / Standard / Deep` 模式选择非常实用

它把 docs-only、小 bugfix、普通 feature、跨模块迁移明确区分开来，避免一刀切。

### 6.3 路径四标签体系很有辨识度

这让计划中的文件路径从“看起来合理”变成“状态明确、可追溯”。

### 6.4 代码块语义标签有效阻止了计划变成伪实现

`[interface]`、`[test-assertion]`、`[command]` 让计划保持在正确粒度。

### 6.5 审阅回路 让计划从“格式正确”升级成“逻辑可信”

这是它区别于普通 checklist 生成器的重要设计。

### 6.6 当前版本的真正增量，在计划治理而不在普通任务拆解

评估已经说明：baseline 也能做部分自然提问和简单任务拆解；真正差异在门禁、模式、路径纪律、审查循环和契约化输出。这说明 `writing-plans` 的核心价值是 planning governance，而不是单纯“更会列步骤”。

## 7. 什么时候适合用，什么时候不该硬用

| 场景 | 是否适合 | 原因 |
|------|----------|------|
| 多文件 feature / bugfix / refactor / migration | 非常适合 | 这是核心场景 |
| 跨模块、高风险或需 phased rollout 的任务 | 非常适合 | Deep mode 很有价值 |
| docs-only、config-only、小修补 | 不一定需要正式计划 | 往往应走 `SKIP` 或 `Lite` |
| 单文件、<30 行、5 分钟内可完成的小改动 | 不适合正式计划 | 适用性门禁 会直接跳过 |
| repo 不可访问但仍要先给执行框架 | 适合 | 可进入 Degraded 模式 |

## 8. 结论

`writing-plans` 的真正亮点，不是它能把需求拆成更多步骤，而是它把实施前规划中最容易失真的部分系统化了：先澄清需求，再判断是否值得规划，再验证路径和技术栈，再决定计划的模式和风险深度，然后通过接口级代码块、精确验证命令、审阅回路和偏差处理协议，把计划变成一份可执行、可修订、可审查的工程文档。

从设计上看，这个 skill 很清楚地体现了一条原则：**高质量实施计划的关键，不是任务拆得越细越好，而是让计划先建立在清晰需求和可信路径上，让执行者知道每一步怎么验证、知道哪里可以并行、知道高风险步骤如何回滚，也知道现实偏离计划时应当如何更新这份计划。** 这也是它特别适合 feature planning、migration planning 和复杂 bugfix planning 场景的原因。

## 9. 文档维护

当以下内容发生变化时，这份文档应该同步更新：

- `skills/writing-plans/SKILL.md` 中的 4 个门禁、执行模式、输出契约、评分卡、审阅回路、降级模式或计划更新协议发生变化。
- `skills/writing-plans/references/requirements-clarity-gate.md`、`applicability-gate.md`、`repo-discovery-protocol.md`、`reviewer-checklist.md`、`plan-update-protocol.md`、`anti-examples.md` 或计划模板中的关键规则发生变化。
- `evaluate/writing-plans-skill-eval-report.zh-CN.md` 中支撑本文判断的核心结果发生变化。

建议按季度复查一次；如果 `writing-plans` 的门禁结构、模式选择、路径标注体系或审阅回路有明显重构，则应立即复查。

## 10. 相关阅读

- `skills/writing-plans/SKILL.md`
- `skills/writing-plans/references/requirements-clarity-gate.md`
- `skills/writing-plans/references/applicability-gate.md`
- `skills/writing-plans/references/repo-discovery-protocol.md`
- `skills/writing-plans/references/reviewer-checklist.md`
- `skills/writing-plans/references/plan-update-protocol.md`
- `skills/writing-plans/references/anti-examples.md`
- `skills/writing-plans/references/golden-scenarios.md`
- `evaluate/writing-plans-skill-eval-report.zh-CN.md`
