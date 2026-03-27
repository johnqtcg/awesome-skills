---
title: google-search skill 设计解析
owner: awesome-skills maintainers
status: active
last_updated: 2026-03-27
applicable_versions: current repository version
---

# google-search skill 解析

`google-search` 是一套把“帮我搜一下”转成可验证搜索流程的检索与验证框架。它的核心设计思想是：**搜索的目标是先判断用户到底要知道什么、需要多强证据、该用什么语言和来源路径、最多搜到什么程度，然后再把结果以带有可信度、降级状态和可复用查询的形式交付出来。** 因此它把 范围、歧义、证据、语言、来源路径、模式、预算、执行真实性 八道门串成一条明确流程。

## 1. 定义

`google-search` 用于：

- 事实查询与最新状态确认
- 官方文档、标准、发布说明检索
- 程序员搜索，例如错误调试、API 文档、GitHub / Stack Overflow / RFC 查询
- 技术比较、工具筛选、资料下载、公开信息搜集
- 需要来源支撑和不确定性说明的搜索任务

它输出的不只是答案，还包括：

- 当前执行模式
- 降级级别
- 结论摘要
- 证据链满足情况
- 关键证据与来源评估
- 关键数字的可信度与来源层级标签
- 可复用查询
- 在 Standard / Deep 模式下通常还会补充 gate 执行摘要

从设计上看，它更像一个“搜索操作纪律框架”，而不是一个会调用 Google 的提示词。

## 2. 背景与问题

这个 skill 要解决的，不是“模型不会搜索”，而是模型在搜索任务里很容易出现以下结构性问题：

- 会找资料，但不先定义证据标准
- 会综合信息，但不标注不确定性和来源层级
- 会给答案，但不会留下可复盘、可继续的搜索路径

如果没有这套框架，常见问题通常集中在 8 类：

| 问题 | 典型后果 |
|------|----------|
| 不先分类搜索目标 | factual lookup、教程学习、错误调试、技术比较混用同一套策略 |
| 不先定义 evidence chain | 明明只看到二手总结，却给出像一手结论一样的答案 |
| 不区分模式和预算 | 简单问题搜太多，复杂问题搜不够 |
| 不处理歧义 | 用户说“苹果”“Redis”“某个人名”时直接沿错误方向搜索 |
| 不区分 official / primary / third-party | 官方文档、竞品博客、SEO 汇总被等权处理 |
| 不做 honest degradation | 证据不足时仍给出完整口吻的结论 |
| 不留 reusable queries | 用户无法接着搜，也无法复核你的路径 |
| 不区分 snippet 和 full-page verification | 搜索摘要被误当成已验证内容 |

`google-search` 的设计逻辑，就是先把“这次搜索要得到什么级别的结论”说清楚，再把“应该怎么搜、搜到哪一步停、结果怎么标注”系统化。

## 3. 与常见替代方案的对比

先看它与几种常见做法的区别：

| 维度 | `google-search` skill | 直接让模型“帮我搜一下” | 手工随手搜几次 |
|------|-----------------------|--------------------------|----------------|
| 任务分类 | 强 | 弱 | 弱 |
| 证据链约束 | 强 | 弱 | 弱 |
| 模式与预算控制 | 强 | 弱 | 弱 |
| 来源路径排序 | 强 | 中 | 弱 |
| 可信度与来源层级标注 | 强 | 弱 | 弱 |
| 诚实降级 | 强 | 弱 | 弱 |
| 可复用查询 | 强 | 弱 | 弱 |
| 搜索过程可审计性 | 强 | 弱 | 弱 |

它的价值，不只是让答案“更像研究结果”，而是把搜索从一次性的链接收集提升成可以被审查、复用和继续执行的工作流。

## 4. 核心设计逻辑

### 4.1 先做 范围分类 vs 先写 query

`google-search` 的第一道门是 范围分类 Gate。它要求先判断请求属于：

- Information
- Knowledge
- Materials
- Tools
- Public-information lookup
- Programmer search

同时还要判断用户的目标是：

- Know
- Learn
- Create
- Complete a task

这一步非常关键，因为不同类别的搜索，查询模式、来源排序、证据标准都完全不同。比如“最新公司变动”需要时效性与官方声明，“Go 错误调试”需要精确错误串和 GitHub / Stack Overflow，“框架对比”需要 benchmark 和 methodology disclosure。如果一开始分类错了，后面所有 query 都可能跑偏。

### 4.2 歧义 Gate 必须是 Hard Stop

skill 明确规定：如果类别、目标、实体或时间范围有歧义，就要 **STOP and ASK**。

这是一个很重要的设计决策，因为搜索最浪费的地方，往往不是没搜到，而是从一开始就在搜错对象。例如：

- “苹果”是水果还是 Apple 公司
- “Redis”是想知道概念、调优、报错还是产品替代
- “最新”到底指今天、本周，还是某个版本周期内

因此 `google-search` 不把澄清当成礼貌动作，而是把它当成降低误搜成本的必要门槛。

### 4.3 证据要求 Gate 是整个 skill 的中轴

这个 skill 最有辨识度的地方之一，是它要求在写 query 之前先定义 minimum evidence chain。

它会根据结论类型，先决定至少需要什么样的证据，例如：

- 单一事实：至少 1 个 official / primary source
- best practice：1 个官方依据 + 1 个实践报告
- 数字或统计：1 个 primary dataset + 1 个独立交叉验证
- 技术比较：2 个以上独立 benchmark，且要说明方法
- 争议或高变化主题：至少 3 个来自不同层级的来源，并显式解决冲突

这层设计的价值，在于它先定义“什么样的证据才配支撑这种结论”，再决定“该搜什么”。这让 `google-search` 不会因为看到了几个看似相关的结果，就过早结束搜索。

### 4.4 用 语言 Gate 决定查询语言 vs 默认全英文

很多搜索 skill 会默认英文优先，但 `google-search` 专门把 语言 Detection 单列出来，要求在 EN / CN / Both 之间做判断。

这种设计非常合理，因为：

- global technology、RFC、vendor docs 通常英语更强
- 中国本地政策、公司动态、中文社区经验分享必须依赖中文
- 很多工程实践问题要同时搜英文官方文档和中文踩坑文章

这也是为什么它会在需要时加载 `chinese-search-ecosystem.md`。这份参考资料不只是“补几条中文 query”，而是在提醒模型：Google 不是中国内容世界的全貌，很多微信、小红书、抖音、百度系内容根本不该继续在 Google 上死磕。

### 4.5 来源路径 Gate 强调“优先找源头 vs 找评论”

`google-search` 明确给出 source ranking：

1. 官方站点、官方账号、原始发布者
2. primary document / dataset / filing / standard / release notes
3. 正确引用原始材料的权威媒体或机构
4. 高质量专业社区
5. 聚合页、转载、SEO 页面

这个设计解决的是搜索中的一个常见错觉：搜索结果排在前面，不等于它是最好的证据。skill 的核心偏好是“先找 source，再看 commentary”，这让它特别适合：

- 官方文档检索
- 版本 / 发布 / 状态确认
- 需要追溯原始出处的数字或政策结论

### 4.6 显式区分 Quick / Standard / Deep 三种模式

`google-search` 不把所有搜索任务都当成同一类工作，而是先自动选择或接受用户指定的模式：

- Quick
- Standard
- Deep

并给出不同的预算和输出要求。

这是很成熟的设计，因为搜索任务的成本和严谨度本来就不一样：

- Quick 适合有明确官方答案的简单事实查询
- Standard 适合默认的大多数搜索任务
- Deep 适合高冲突、多来源对比、研究型问题

评估也非常清楚地证明了这一点：基础模型本身能搜出好内容，但几乎不会自然地产生 mode、budget、degradation 这些搜索过程元数据。`google-search` 的核心增量，正是把“搜得怎么样”变成可声明、可检查的流程状态。

### 4.7 预算控制 Gate 要强制终止搜索

很多搜索任务的失败，不是搜得太少，而是搜得太久却没有及时承认 framing 有问题。`google-search` 明确给出每种模式的查询预算：

- Quick: 2
- Standard: 5
- Deep: 8

如果预算耗尽仍找不到足够证据，就必须停下来，报告：

- 找到了什么
- 还缺什么
- 下一步应该换什么策略

这层设计特别重要，因为它把“停止搜索”也变成一个受约束的决策，而不是无限点击。参考资料 `ai-search-and-termination.md` 进一步强化了这一点：8 条 query 之后还找不到，问题往往是 framing 错了，而不是点得不够多。

### 4.8 执行真实性门禁 会强调 snippet 不等于 verification

这个 skill 在执行完整性上非常严格，明确要求：

- 没执行的 query 不得假装执行过
- 没打开的页面不能说已经验证
- 搜索 snippet 不能当 full-page confirmation

这层设计很关键，因为搜索工具非常容易让人产生“我已经看过了”的错觉。实际上，snippet 只是一段预览，不代表正文就真的支持这个结论。

这也是为什么 `google-search` 会特别强调：

- “I found X”
- 和 “search snippet mentions X”

必须区分开。它保护的不是措辞细节，而是证据纪律。

### 4.9 Honest Degradation 是这个 skill 的核心能力之一

`google-search` 不允许在证据不足时继续装作已经得到完整答案，而是要求显式降级为：

- Full
- Partial
- Blocked

这种设计的价值非常大。很多搜索任务真正的高质量结果，不是“给出最完整的答案”，而是“把哪些部分已经确认、哪些部分只能部分成立、哪些部分暂时搜不到”讲清楚。

评估里 Deep 模式对 Gin / Echo / Fiber 的对比就是典型案例：with-skill 会把 named company production cases 缺失、TechEmpower 二手解读等问题明确标成 `Partial`；without-skill 虽然也能写出不错内容，但不会主动把这些不确定性升级成交付层面的声明。

### 4.10 要求 Confidence + Source-tier 双标签

`google-search` 要求关键数字同时带：

- confidence label
- source-tier label

这是一条非常强的纪律，因为很多数字类结论最容易造成误导。单写一个“性能是 735,000 RPS”远远不够，还必须说明：

- 这个数来自官方、primary data，还是第三方转述
- 你对它的信心是 High、Medium 还是 Low

这让用户能立即区分：

- “官方明确给出的数字”
- 和 “别人根据 benchmark 页面解读出来的数字”

这也是评估里最明显的 skill-only 差异之一。

### 4.11 把 Reusable Queries 作为交付物的一部分

这个 skill 不是搜索完就结束，它要求把 Primary / Precision / Expansion 乃至 gap-closing query 一起交付出来。

这个设计很实用，因为搜索答案并不是一次性消费品。用户常常还需要：

- 自己继续验证
- 换时间范围继续搜
- 转给同事复现你的路径

可复用查询的价值就在于，它把“结果”变成“可以继续执行的搜索入口”。这也是基础模型通常不会自然补出的层。

### 4.12 references 采用强条件加载

`google-search` 的 references 分层非常清楚：

- `query-patterns.md` 是常驻基础
- `programmer-search-patterns.md` 只在程序员搜索类任务加载
- `source-evaluation.md` 在来源评估或冲突处理时加载
- `ai-search-and-termination.md` 在决定终止或升级时加载
- `high-conflict-topics.md` 只在高冲突话题加载
- `chinese-search-ecosystem.md` 只在中文 / 中国话题加载

这说明它很重视 token 成本控制。不是每次搜索都要带上高冲突战争信息或中文平台生态，但一旦场景触发，这些附加规则又非常关键。这种“基础规则常驻 + 重场景按需加载”的结构，是整个 skill 可扩展性的关键。

### 4.13 Content Access Resilience 是必要设计 vs 补丁

这个 skill 还额外处理了一个现实问题：`WebFetch` 不一定能穿透 Cloudflare、WAF 或 JS-heavy 页面。

因此它预先设计了 fallback chain：

1. Firecrawl（如果 `firecrawl-scrape` skill 可用）
2. snippet-only mode
3. 告知用户应直接去对应平台搜

并要求在 snippet-only 情况下：

- 降级为 `Partial`
- 说明哪些页面无法完整访问
- 降低 confidence
- 给出 direct URL

这层设计很成熟，因为它承认“工具能力受限”本身就是搜索工作流的一部分，而不是把抓取失败当成偶发异常。

## 5. 这个设计解决了哪些具体问题

结合当前 `SKILL.md`、关键 references 和评估报告，可以把它解决的问题归纳为：

| 问题类型 | skill 中的对应设计 | 实际效果 |
|----------|-------------------|----------|
| 搜索目标不清 | 范围 + 歧义 Gates | 先定义搜索任务，再生成 query |
| 证据要求模糊 | 证据要求 Gate | 先定义最小证据链，再判断答案是否成立 |
| 查询语言选错 | 语言 Detection Gate | 在 EN / CN / Both 之间做有意识选择 |
| 来源质量混乱 | 来源路径 + Source Evaluation | 优先原始来源并显式解释冲突 |
| 搜索过程失控 | 模式 + 预算控制 | 用有限预算控制搜索深度 |
| snippet 被误当验证 | 执行真实性门禁 | 区分预览、打开页面和真正验证 |
| 证据不足却给满口吻结论 | Honest Degradation | 用 Full / Partial / Blocked 管理不确定性 |
| 用户无法继续搜索 | Reusable Queries | 把搜索路径沉淀成可继续执行的查询 |
| 数字结论误导性强 | Confidence + Source-tier labels | 让关键数字的可信度一眼可见 |

## 6. 主要亮点

### 6.1 它把搜索从“找链接”提升成“找证据”

这是整个 skill 最根本的升级。它不是围绕搜索引擎操作，而是围绕“结论需要什么证据”来设计流程。

### 6.2 证据链和降级机制是最大亮点

很多搜索工具能找到内容，但不会告诉你为什么这个答案现在只能算 `Partial`。`google-search` 明确把这件事制度化了。

### 6.3 双标签数字规则非常强

confidence + source-tier 的组合，让数字类结论从“看起来很具体”变成“来源与可信度都透明”。

### 6.4 对搜索预算和终止条件有明确纪律

这让它不会陷入无限 refinement，也不会把“没搜到”伪装成“已经证伪”。

### 6.5 可复用查询让结果具有长期价值

输出不只是这次的答案，还包括下一次继续搜的入口。这一点在协作和复盘里特别有用。

### 6.6 当前版本的价值，更像搜索方法论而不是检索技巧

评估里已经很清楚：基础模型在内容质量上并不差，差的是 mode、budget、evidence chain、degradation、source-tier、reusable queries 这些操作纪律。也就是说，这个 skill 的真正增量在“搜索治理”，而不是“会不会搜”。

## 7. 什么时候适合用，什么时候不该硬用

| 场景 | 是否适合 | 原因 |
|------|----------|------|
| 官方文档、标准、版本、状态查询 | 非常适合 | source path 和 evidence chain 很有价值 |
| 程序员错误调试与资料检索 | 非常适合 | programmer search 模式很成熟 |
| 技术比较与 benchmark 对比 | 适合 | 需要 Deep 模式和来源评估 |
| 公开信息搜集 | 适合 | 但必须严格区分 fact 与 inference |
| 中文 / 中国话题搜索 | 适合 | 但要利用中文生态与平台级回退策略 |
| 高冲突、快变化主题 | 适合 | 但需要更严格 source-tier 和降级纪律 |
| 需要深度综合研究报告 | 不一定最优 | 可能更适合 `deep-research` |
| 需要抓取登录墙或重 JS 页面全文 | 不一定最优 | 可能需要 Firecrawl 或平台内搜索 |

## 8. 结论

`google-search` 的真正亮点，不是它能帮你搜到答案，而是它把搜索任务里最容易被忽略的工程判断系统化了：先分类、再定义证据链、再决定语言和来源路径，再用模式与预算控制搜索成本，最后用可信度标签、降级声明和可复用查询把整个搜索过程交付出来。

从设计上看，这个 skill 很清楚地体现了一条原则：**高质量搜索的关键，不是搜得越多越好，而是知道应该搜什么、需要什么证据、什么时候该停，以及证据不足时如何诚实表达。** 这也是它特别适合事实查询、调试检索、技术对比和来源核验任务的原因。

## 9. 文档维护

当以下内容发生变化时，这份文档应该同步更新：

- `skills/google-search/SKILL.md` 中的 强制门禁、模式 定义、预算控制、执行真实性、Honest Degradation、输出契约 或 Content Access Resilience 发生变化。
- `skills/google-search/references/query-patterns.md`、`programmer-search-patterns.md`、`source-evaluation.md`、`ai-search-and-termination.md`、`high-conflict-topics.md` 或 `chinese-search-ecosystem.md` 中的关键规则发生变化。
- skill 对 confidence / source-tier、snippet-only、platform-specific fallback 的要求发生明显调整。
- `evaluate/google-search-skill-eval-report.md` 或 `evaluate/google-search-skill-eval-report.zh-CN.md` 中支撑本文判断的核心结果发生变化。

建议按季度复查一次；如果 `google-search` 的 gates、输出契约 或来源评估规则有明显重构，则应立即复查。

## 10. 相关阅读

- `skills/google-search/SKILL.md`
- `skills/google-search/references/query-patterns.md`
- `skills/google-search/references/programmer-search-patterns.md`
- `skills/google-search/references/source-evaluation.md`
- `skills/google-search/references/ai-search-and-termination.md`
- `skills/google-search/references/high-conflict-topics.md`
- `skills/google-search/references/chinese-search-ecosystem.md`
- `evaluate/google-search-skill-eval-report.md`
- `evaluate/google-search-skill-eval-report.zh-CN.md`
