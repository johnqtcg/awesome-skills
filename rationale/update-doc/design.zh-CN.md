---
title: update-doc skill 设计解析
owner: awesome-skills maintainers
status: active
last_updated: 2026-03-27
applicable_versions: current repository version
---

# update-doc skill 解析

`update-doc` 是一套围绕仓库文档同步设计的防漂移更新框架。它的核心设计思想是：**文档更新的关键在于基于仓库证据只更新真正受影响的文档、避免超范围重写、让每个修改都能追溯到代码来源，并在交付时说明哪些信息已经确认、哪些内容在仓库里根本找不到，以及后续怎样避免文档再次落后于代码。** 因此它把 受众与语言门禁、项目类型路由、差异范围门禁、命令可验证性门禁、轻量 / 完整输出模式、Codemap 输出契约、CI 文档漂移护栏 和 质量评分卡 串成了一条固定流程。

## 1. 定义

`update-doc` 用于：

- 在代码变更后同步 README、`docs/`、codemap 等仓库文档
- 生成基于证据的文档补丁，而不是泛化重写
- 根据仓库类型选择不同的文档结构
- 用轻量 / 完整两种输出模式控制更新粒度
- 为后续文档漂移补上 CI 与维护护栏

它输出的不只是文档改动，还包括：

- 变更文件
- 证据映射
- 命令验证
- 评分卡（在完整模式下）
- 待补缺口（在完整模式下必需；轻量模式暴露真实缺口时可出现）

从设计上看，它更像一个“文档同步治理框架”，而不是一个泛化的文档润色提示词。

## 2. 背景与问题

这个 skill 要解决的，不是“模型不会写文档”，而是代码发生变化后，文档更新任务天然容易出现几种高风险失真：

- 文档改了，但改过头了
- 文档写得很完整，但很多内容其实不是从仓库证据来的
- 文档这次补齐了，但下次又会漂移

如果没有明确流程，常见问题通常集中在 8 类：

| 问题 | 典型后果 |
|------|----------|
| 不先判断项目类型 | CLI README 被写成后端服务说明，monorepo 被写成目录树 dump |
| 不先限制 diff 作用域 | 小改动引发整篇 README 重写，结构和导航被破坏 |
| 不区分轻量更新与全量更新 | 简单 patch 也输出一整套重构，大型改动却没有完整报告 |
| claim 不可追溯 | PR review 无法判断文档改动是否真来自代码证据 |
| 缺少 `Not found in repo` 纪律 | 信息缺口被模型自行脑补 |
| 命令验证状态不清 | 用户看不出哪些命令跑过、哪些只是从源码推导 |
| codemap 没有固定 contract | 复杂仓库的架构文档结构不稳定、难维护 |
| 不考虑 CI drift | 文档短期同步，后续又再次落后于代码 |

`update-doc` 的设计逻辑，就是先回答“当前仓库是什么类型、这次改动影响哪些文档、应该做轻量 patch 还是 full update、每个 section 的证据在哪里、哪些信息在仓库中不存在、未来怎样避免漂移”，再允许真正动手修改文档。

## 3. 与常见替代方案的对比

先看它与几种常见做法的区别：

| 维度 | `update-doc` skill | 直接让模型“更新 README/docs” | 把文档更新当作一次性写作任务 |
|------|--------------------|------------------------------|------------------------------|
| 项目类型路由 | 强 | 弱 | 弱 |
| diff 作用域控制 | 强 | 弱 | 弱 |
| 证据映射 | 强 | 弱 | 弱 |
| 输出模式区分 | 强 | 弱 | 弱 |
| codemap 契约 | 强 | 弱 | 弱 |
| `Not found in repo` 纪律 | 强 | 中 | 弱 |
| CI 文档漂移护栏 | 强 | 弱 | 弱 |
| 结构化交付 | 强 | 弱 | 弱 |

它的价值，不只是把文档“写得更好看”，而是把代码变更后的文档同步工作变成可追溯、可审查、可维护的更新流程。

## 4. 核心设计逻辑

### 4.1 先做 受众与语言门禁

`update-doc` 的第一道门禁先判断：

- 目标读者是谁
- 输出语言应该是什么

这一步的价值，不在于给文档强行添加“受众标签”，而在于防止更新时把内容写给错误的人。例如：

- README 首屏通常主要服务外部读者或新贡献者
- ops 文档服务维护者
- codemap 服务想理解仓库结构的工程师

skill 也明确要求：如果用户没指定语言，就跟随仓库现有语言，而不是随意切换。这种设计避免了“文档更新后语气和语言层次漂移”的问题。

### 4.2 项目类型路由 是基础层

在真正改文档之前，`update-doc` 先把仓库路由成：

- Service / Backend
- Library / SDK
- CLI Tool
- Monorepo

这层设计是整个 skill 的结构支点，因为文档更新是否合理，很大程度取决于你是不是在按正确的项目类型组织内容。比如：

- Service 文档要优先 runtime modes、config/env、ops commands
- CLI 文档要优先 install、usage examples、flags/options
- Monorepo 要优先 module index table 和子模块链接，而不是整棵目录树

评估里这是最稳定的 skill-only 差异之一：with-skill `3/3` 全对，without-skill `0/3`。尤其在 monorepo 场景里，without-skill 直接退化成目录树 dump，而 with-skill 能稳定走 module index + codemap 路径。这说明项目类型路由不是写作偏好，而是后续一切结构决策的前提。

### 4.3 差异范围门禁 要放得这么靠前

`update-doc` 明确要求：

- 先根据 `git diff --name-only` 或受影响代码路径推断文档范围
- 优先做受影响 section 的 patch
- 只有用户要求时才扩大成更大范围重写

这层设计非常关键，因为很多文档更新任务其实不是“重写 README”，而是“修 1-2 处已经和代码不一致的地方”。如果没有 diff scope 纪律，模型很容易顺手把整篇文档重排一遍，结果：

- 导航被打乱
- 标题顺序改变
- 用户原本满意的结构被无关重写

评估里最大的质量差距之一正来自这里：轻量 CLI patch 场景下，without-skill 额外添加了 “How It Works” 和 “Error Handling”，而 with-skill 只修补真正过时的 flag 文档。这说明 diff scope gate 的核心价值，是让文档更新“对症下药”，而不是“借机重写”。

### 4.4 Lightweight / Full 输出模式

这个 skill 不把所有更新任务都当成同一种工作，而是分成：

- Lightweight Output 模式
- Full Output 模式

触发逻辑也非常明确：

- 轻量模式适合 1-2 个文档文件、小范围修补、无新 runtime/API/deploy 变化
- 全量模式适合 codemap、新 runtime、多模块影响、README 大幅重组或用户明确要求全量审计

这层设计很成熟，因为它同时解决了两个问题：

- 小改动不该背上过重报告成本
- 大改动不能只给一个简短 patch 而没有完整审计信息

评估里 without-skill 完全没有这个模式概念，结果在简单场景里改得太多，在复杂场景里又给得太少。with-skill 的差异化优势，正是在“更新粒度”和“报告粒度”同时受控。

### 4.5 证据映射是核心增量 vs 附属表格

`update-doc` 要求每个改动 section 都能映射到仓库证据：

- 代码入口
- env/config 读取
- 路由 / handler
- Makefile / CI / runtime script
- 依赖清单

它真正要解决的是“文档 claim 可审计性”问题。评估也很清楚地说明：

- baseline 模型在事实准确性上已经不差
- 真正的差距在于 with-skill 能把 claim 结构化映射回源码

也就是说，这个 skill 并不是主要提升“对不对”，而是主要提升“能不能证明为什么对”。这对 PR review、后续维护和多人协作都很重要。

### 4.6 `Not found in repo` 纪律必须强制存在

skill 明确要求：

- 仓库里找不到的信息，要写成 `Not found in repo`
- 不要发明 API、路由、环境变量、端口、任务流、依赖

这层设计非常关键，因为文档更新任务最容易产生一种表面很专业的幻觉：模型为了让文档“更完整”，会自动补上看起来合理但仓库里没有证据的内容。

`update-doc` 的做法是把缺口保留下来，而不是把缺口伪装成答案。这种设计短期看会让文档“没那么满”，但长期看能大幅减少文档误导。monorepo 场景中的 `Not found in repo` 纪律，就是这种设计价值最直观的体现。

### 4.7 命令可验证性门禁 不把内部标记塞进用户文档

这个 skill 对命令验证的态度很细：

- 跑过的命令，在 assistant response 里说明
- 没跑过的命令，也要诚实说明
- 但默认不要把 “Not verified in this environment” 之类标签直接塞进用户-facing 文档

这层设计很成熟，因为它区分了两件事：

- 对用户和团队诚实
- 不把内部工作流噪音泄漏到正式文档

也就是说，verification state 属于交付报告，不一定属于文档正文。这个边界如果不划清，很容易把 README 写成带内部审计标签的半成品。

### 4.8 Anti-Patterns 会被单独列出来

`update-doc` 的 Anti-Patterns 不只是一般性写作建议，而是直接针对文档更新中的常见坏行为：

- 把评分卡 / 证据表泄漏进用户文档
- 为了“更完整”把 README 首页写成维护者手册
- 为了简化删除有用 ToC
- 只更新输出示例，而不保留 input -> result -> output-shape 的读者路径
- 在 monorepo README 里全量 dump 目录树

这层设计的意义，在于提前把“看起来也说得通，但实际会伤害文档 UX”的行为做成显式禁止项。评估里 without-skill 在 monorepo 场景里出现了目录树 dump，正说明这些 anti-pattern 不是理论上的。

### 4.9 独立的 Codemap 输出契约

当用户要求 codemap 时，`update-doc` 不是泛泛地生成几篇说明，而是要求按仓库形态生成 evidence-backed 的 contract 文件，例如：

- `docs/CODEMAPS/INDEX.md`
- `docs/CODEMAPS/backend.md`
- `docs/CODEMAPS/integrations.md`
- `docs/CODEMAPS/workers.md`（存在 workers / cron / queues 时）
- `docs/CODEMAPS/frontend.md`（存在 frontend 时）
- `docs/CODEMAPS/database.md`（存在 schema evidence 时）

并要求每篇 codemap 至少包含：

- last updated
- entry points
- key modules table
- evidence-backed data flow
- external dependencies
- cross-links

这层设计很关键，因为 codemap 不是普通 README patch，而是仓库结构文档。没有 contract，就很容易变成一篇随手写的架构笔记；有了 contract，codemap 才会形成稳定的可维护结构。评估里 codemap completeness 是 skill-only 差异，也正说明这一点。

### 4.10 CI 文档漂移护栏 是这个 skill 的后半程重点

`update-doc` 不把任务停在“这次文档已经同步了”，而是继续要求考虑：

- markdown lint
- link checker
- docs drift check
- ownership / update timing note

这层设计非常有治理价值，因为文档漂移本质上是一个持续问题，而不是一次性问题。如果只修当前 diff，不想后续 guardrail，文档很快还会再次过时。

评估里 `CI 文档漂移护栏` 是 skill-only 能力之一，说明基础模型默认不会主动想到“这次更新之后，未来怎么防止再漂移”。这正是这个 skill 的长期价值所在。

### 4.11 README UX Rules 被放在结构规则里

对 top-level README，`update-doc` 明确要求：

1. value proposition 在 implementation detail 前
2. install / quick start 在维护者工作流前
3. 长文档保留 compact ToC
4. end-to-end example 在深度参考前

这层设计很有必要，因为 README 更新很容易在“补信息”的名义下变得越来越像内部维护手册。skill 的规则本质上是在保护 README 作为 homepage 的角色：先帮助读者理解项目和快速上手，再展开深层维护信息。

### 4.12 真正的增量在方法论，而不在事实提取

评估已经说明，without-skill 在很多事实性内容上也能做对：

- 环境变量
- 端口
- API routes
- Makefile target
- docker-compose 基本说明

真正的差距在于：

- 没有 project-type routing
- 没有输出模式
- 没有证据映射
- 没有质量评分卡
- 没有 CI 文档漂移意识
- 没有 codemap 契约

这说明 `update-doc` 的核心价值不是“让模型更会读代码”，而是“让模型以一种可追溯、可控、可维护的方式更新文档”。

## 5. 这个设计解决了哪些具体问题

结合当前 `SKILL.md`、关键 references 和评估报告，可以把它解决的问题归纳为：

| 问题类型 | skill 中的对应设计 | 实际效果 |
|----------|-------------------|----------|
| 文档结构和仓库类型不匹配 | 项目类型路由 | README / docs 结构更贴合项目形态 |
| 小改动引发大重写 | 差异范围门禁 + 轻量模式 | 更新更克制 |
| 大改动缺少完整审计 | 完整输出模式 | 报告更完整 |
| 文档 claim 不可追溯 | 证据映射 | 更易审查 |
| 信息缺口被脑补 | `Not found in repo` 纪律 | 输出更诚实 |
| 用户文档混入内部审计标记 | 命令可验证性门禁 + Anti-Patterns | 文档更干净 |
| codemap 结构漂移 | Codemap 输出契约 | 架构文档更稳定 |
| 文档再次落后于代码 | CI 文档漂移护栏 | 维护性更强 |

## 6. 主要亮点

### 6.1 它把文档更新从写作任务改造成同步任务

核心目标不是“写一篇更完整的文档”，而是“让文档重新和代码保持一致”。

### 6.2 项目类型路由是最有辨识度的设计之一

CLI、Service、Library、Monorepo 用不同结构更新，这是 skill 最稳定的差异来源之一。

### 6.3 轻量 / 完整双模式非常实用

它把小 patch 和大改动区分开来，既防止过度重写，也防止复杂更新缺少审计。

### 6.4 证据映射让文档改动真正变得可审查

skill 的关键增量不在内容正确本身，而在“能指回哪段代码支持这个文档 claim”。

### 6.5 Codemap 契约和 CI 文档漂移护栏让它具备长期维护价值

这使它不只是修当前文档，还把后续如何防漂移纳入设计。

### 6.6 当前版本的真正增量，在方法论与治理，而不是基础写作能力

评估已经说明：baseline 模型本来就能提取很多事实；真正的差距在结构化路由、作用域纪律、输出模式、审计报告和漂移防护。这说明 `update-doc` 的核心价值是文档同步治理，而不是单纯“更会写 README”。

## 7. 什么时候适合用，什么时候不该硬用

| 场景 | 是否适合 | 原因 |
|------|----------|------|
| 代码改动后同步 README / docs | 非常适合 | 这是核心场景 |
| codemap 生成或重构 | 非常适合 | 有固定输出契约 |
| monorepo 根 README 与模块索引更新 | 非常适合 | project routing 很关键 |
| 仅想写一篇全新技术文档 | 不一定最优 | 超出这个 skill 的核心同步场景 |
| 与代码无关的文案润色 | 不适合 | 它强调 repo evidence |
| 想凭常识补齐仓库中不存在的信息 | 不适合 | 它会保留 `Not found in repo` |

## 8. 结论

`update-doc` 的真正亮点，不是它能把 README 写得更像标准答案，而是它把代码变更后的文档同步工作系统化了：先判断语言和项目类型，再收紧 diff 作用域，再决定走轻量还是完整模式，然后用证据映射、`Not found in repo`、命令验证、codemap 契约和 CI 文档漂移护栏约束最终交付物。

从设计上看，这个 skill 很清楚地体现了一条原则：**高质量文档更新的关键，不是把文档写得“更丰满”，而是让每一处修改都能回到仓库证据、让小改动只改小范围、让复杂改动带上完整审计信息，并且让团队知道以后怎样防止文档再次漂移。** 这也是它特别适合 README patch、docs drift 修复和 codemap 维护场景的原因。

## 9. 文档维护

当以下内容发生变化时，这份文档应该同步更新：

- `skills/update-doc/SKILL.md` 中的 hard rules、pre-update gates、轻量 / 完整输出模式、Codemap 输出契约、CI 文档漂移护栏、质量评分卡或输出格式发生变化。
- `skills/update-doc/references/update-doc.md`、`project-routing.md` 或 `ci-drift.md` 中的关键规则发生变化。
- `evaluate/update-doc-skill-eval-report.md` 或 `evaluate/update-doc-skill-eval-report.zh-CN.md` 中支撑本文判断的核心结果发生变化。

建议按季度复查一次；如果 `update-doc` 的项目类型路由、输出模式、codemap 契约或漂移护栏机制有明显重构，则应立即复查。

## 10. 相关阅读

- `skills/update-doc/SKILL.md`
- `skills/update-doc/references/update-doc.md`
- `skills/update-doc/references/project-routing.md`
- `skills/update-doc/references/ci-drift.md`
- `evaluate/update-doc-skill-eval-report.md`
- `evaluate/update-doc-skill-eval-report.zh-CN.md`
