---
title: security-review skill 设计解析
owner: awesome-skills maintainers
status: active
last_updated: 2026-03-27
applicable_versions: current repository version
---

# security-review skill 解析

`security-review` 是一套以 exploitability-first 为核心的安全审查流程框架。它的核心设计思想是：**安全审查的目标是先判断变更需要多深的审查、哪些安全域真正适用、哪些风险有可利用路径、哪些疑点应被抑制、哪些区域尚未覆盖，然后再把发现以带有置信度、标准映射、基线状态和未覆盖风险声明的方式交付出来。** 因此它把审查深度、证据置信度、误报抑制、适用性优先执行、A-F 门禁、场景检查清单、自动化证据和输出契约串成了一条固定流程。

## 1. 定义

`security-review` 用于：

- 对代码变更执行 exploitability-first 的安全审查
- 覆盖 auth、input、secrets、API、数据流、依赖、资源生命周期、并发与容器等风险
- 先按变更范围与触发信号判定 Lite / Standard / Deep 审查深度
- 用置信度、CWE/OWASP 映射和基线状态表达发现
- 抑制误报，并显式记录未覆盖风险
- 通过通用强制门禁（如 A 号门禁）和 Go 项目的专项覆盖门禁（如 D 号门禁）约束审查质量

它输出的不只是 findings。按审查深度不同，输出还会包含：

- 审查深度及其理由
- Go 10 个安全域覆盖情况
- 自动化证据
- 开放问题 / 前提假设
- 风险接受记录
- 修复建议计划
- 机器可读 JSON
- 加固建议
- 未覆盖风险清单

从设计上看，它更像一个“安全审查治理框架”，而不是一个泛化的代码安全点评提示词。

## 2. 背景与问题

这个 skill 要解决的，不是“模型看不出安全问题”，而是安全审查任务天然有几个高风险失真点：

- 会发现问题，但不区分可利用漏洞和理论疑点
- 会报安全问题，但不给置信度和标准映射
- 会给出看似完整的报告，但不声明哪些地方根本没覆盖

如果没有明确流程，常见问题通常集中在 8 类：

| 问题 | 典型后果 |
|------|----------|
| 不先选审查深度 | 简单变更被过度审查，复杂变更可能审查不足 |
| 不先做适用性判断 | 每个域都硬审一遍，成本高且 N/A 泛滥 |
| 不区分 confirmed / likely / suspected | 严重性和证据强度混在一起 |
| 不做误报抑制 | path traversal、CSRF、随机数等领域容易被过报 |
| 不检查资源生命周期 | 连接、事务、响应体、goroutine 泄漏被漏掉 |
| 不声明未覆盖风险 | 报告看起来完整，实际有巨大盲区 |
| 不做标准映射 | 结果难以进入治理、审计和合规流程 |
| 不和 baseline 对比 | 新问题、回归问题、历史遗留问题混在一起 |

`security-review` 的设计逻辑，就是先把“这次变更该审到什么程度、哪些域真正相关、哪些风险真能打通利用路径”说清楚，再把审查输出做成可审计、可追责、可落地的结构化结果。

## 3. 与常见替代方案的对比

先看它与几种常见做法的区别：

| 维度 | `security-review` skill | 直接让模型“做安全 review” | 手工经验型安全 review |
|------|-------------------------|----------------------------|------------------------|
| 审查深度路由 | 强 | 弱 | 中 |
| 误报抑制纪律 | 强 | 弱 | 中 |
| 适用性优先执行 | 强 | 弱 | 弱 |
| 置信度与标准映射 | 强 | 弱 | 中 |
| 资源生命周期审查 | 强 | 中 | 中 |
| 未覆盖风险声明 | 强 | 弱 | 弱 |
| 机器可消费输出 | 强 | 弱 | 弱 |
| 基线对比能力 | 强 | 弱 | 中 |

它的价值，不只是让安全报告“更像审计产物”，而是把安全审查从一次性的漏洞点评提升成有边界、有门禁、有证据等级的工程化审查流程。

## 4. 核心设计逻辑

### 4.1 把 审查深度选择 放在第一步

`security-review` 的第一步不是直接找漏洞，而是先选择：

- Lite
- Standard
- Deep

并结合文件数量与触发信号来决定。

这一步是整个 skill 的结构中轴，因为安全审查最常见的问题之一不是“完全没看”，而是“所有变更按同一深度去看”。`security-review` 明确规定：

- 文件数少且未触碰安全敏感路径，可以走 Lite
- 触碰 auth、crypto、payment、新 endpoint、依赖变更，或 Dockerfile、K8s 清单、CI 流水线安全配置等基础设施/部署安全改动，则强制 Standard 或 Deep
- 大范围改动、新服务、新外部集成或 auth redesign，进入 Deep

评估里这也是 skill 最显著的独有增量之一：without-skill 能找到很多核心问题，但完全不会声明这次 review 为什么该是 Lite 或 Standard，也不会因此控制成本和解释覆盖边界。

### 4.2 Lite / Standard / Deep 不是简写，而是成本控制机制

`security-review` 不是把三种深度当标签用，而是把它们和 process 绑定：

- Lite 只跑部分步骤
- Standard 走完整 15 步
- Deep 在完整 15 步基础上扩展 call graph tracing

这层设计很重要，因为安全 review 的成本并不均匀。Lite 模式并不是“不审”，而是在真正低风险的改动上按范围策略跳过 B 号门禁/C/E，并在满足条件时进入 Fast Pass；Deep 则要求超出直接 diff 的更长路径追踪。这让 skill 把“审查强度”从隐性经验判断变成了显式控制面。

### 4.3 适用性优先执行 是必要设计

这个 skill 强制采用两阶段执行：

- Phase 1：先把每个 Go domain 标成 `Applicable` 或 `N/A`
- Phase 2：只对 `Applicable` 域做深查与工具执行

这是一个非常关键的设计，因为安全 review 很容易被“全量 checklist”拖垮。Applicability-first 让 skill 先判断哪些域真的与当前变更有关，再决定哪些域要进入深查、哪些域要触发领域相关工具。也就是说，它不是先承诺全覆盖，再用大量空表格填 `N/A`，而是先证明“为什么这个域值得查”。

### 4.4 误报抑制 规则必须前置

`security-review` 在正式发布 finding 之前，强制检查 4 类抑制条件：

1. 上游 guard 已经挡住路径
2. 输入并非攻击者可控
3. sink 已由框架安全保证
4. 只是环境层理论风险，没有可达路径

这层设计的价值非常大，因为安全审查最容易伤害团队信任的，不是漏掉一个低级硬化项，而是把本不成漏洞的点强行报成高危。评估里 without-skill 把 `/convert` 的问题报成 CSRF，把 `openAPISpecPath` 报成 path traversal；with-skill 则通过抑制规则把根因重新归到 rate limiting 或配置边界上。这说明 skill 的关键增量不只是“找问题”，更是“少报错问题”。

### 4.5 强制要求 证据置信度

每个 finding 都必须带：

- `confirmed`
- `likely`
- `suspected`

这不是报告格式上的修饰，而是证据纪律。很多安全 review 的问题不在于结论完全错，而在于把“看起来像漏洞”的东西说成“已经证实的漏洞”。`security-review` 要求：

- 高严重性问题必须有更强证据
- `confirmed` 需要代码或运行路径证明
- `likely` 明确只有一个关键运行时假设未被补齐
- `suspected` 则要老实承认证据还弱

评估里 without-skill 在 3 个场景中完全没有置信度标签，而 with-skill 3/3 全部具备。这说明 skill 的核心增量之一，是把发现从“意见”变成“证据等级明确的判断”。

### 4.6 A 号门禁 要单独审 constructor-release pairing

A 号门禁 要求对 changed code 和紧邻调用路径中的每一个 acquisition / constructor 做配对审计，例如：

- `New*`
- `Open*`
- `Acquire*`
- `Begin*`
- `Dial*`
- `Listen*`
- `Create*`
- `WithCancel/WithTimeout/WithDeadline`

并检查它们是否匹配：

- `Close`
- `Release`
- `回滚/Commit`
- `Stop`
- `Cancel`
- 或在代码中明确记录 ownership transfer

这层设计很强，因为很多安全风险并不是经典“输入漏洞”，而是资源生命周期缺陷导致的可用性和稳定性问题。`security-review` 把这类问题放进固定 gate，而不是当成“可选质量检查”，等于明确承认：资源泄漏、事务边界、goroutine 生命周期在安全上是第一类问题，而不是附带问题。

### 4.7 D 号门禁 的 10-Domain 覆盖是结构核心

对于 Go 仓库，skill 会固定覆盖 10 个域：

1. randomness safety
2. injection + SQL lifecycle
3. sensitive data handling
4. secret/config management
5. TLS safety
6. crypto primitives
7. concurrency safety
8. Go-specific injection sinks
9. static scanner posture
10. dependency posture

这是它最像“框架”而不是“提示词”的地方。它并不假设每次 review 都会自然想到这些域，而是把这些域硬编码成必经结构，再允许通过 `Applicable/N/A` 机制来控制成本。评估也清楚地说明：without-skill 在核心安全发现上并不弱，但在 D 号门禁 这样的系统性覆盖上完全缺失；这也是其结构性合规缺口的重要组成部分。

### 4.8 E 号门禁 的 second-pass falsification 很关键

这个 skill 明确要求在第一轮 finding 之后，再做一轮“反证式复查”：

- 如果第一轮过度关注某类 exploit，会漏掉什么
- availability、consistency、lifecycle、partial-failure path 有没有被低估
- transaction、rollback、cleanup、idempotency race 是否遗漏

这层设计很成熟，因为安全审查中的偏差，很多时候不是不会看，而是第一轮被某类风险吸走注意力。E 号门禁等于强制审查者主动怀疑自己的第一轮结论，从而降低“只会报自己第一眼看到的问题”的偏差。

### 4.9 `Uncovered Risk List` 作为 F 号门禁的必备输出

`security-review` 明确规定：无论有没有 findings，都必须输出未覆盖风险列表。

每项要写清楚：

- 哪块没覆盖
- 为什么没覆盖
- 如果这块藏着 defect，影响是什么
- 后续建议和 owner 提议

这是整个 skill 最有治理价值的设计之一。很多安全 review 的真正危险，不是 findings 太少，而是报告让人误以为“已经看全了”。F 号门禁 直接对抗这种虚假完整性。评估里 without-skill 在 3 个场景全部缺失 F 号门禁，而 with-skill 全部提供，这也是其结构性增量的重要来源。

### 4.10 强制把 findings 做成标准映射产物

每个 finding 在适用时都要带：

- `CWE-xxx`
- `OWASP ASVS <section>`

这层设计的价值，在于让安全 review 的结果不止服务当前工程师，也能服务后续治理、审计和跨团队沟通。没有标准映射，报告更像一次性意见；有了映射，报告就能进入合规表、整改台账和风险追踪流程。评估里这也是最明显的 skill-only 差异之一：without-skill 3/3 缺失，with-skill 3/3 完整。

### 4.11 聚焦自动化门禁 是“可跑则跑、不可跑则明说”

这个 skill 对自动化工具的态度不是“必须都跑”，而是：

- baseline secret sweep 必跑
- `gosec`、`govulncheck`、`go test -race` 按适用域与成本触发
- 没跑就要写明为什么没跑

这层设计非常务实，因为安全自动化的价值很高，但工具可用性、构建状态、测试条件并不总是满足。skill 因此既不允许“没跑却假装跑了”，也不要求“无论什么项目都把所有工具跑一遍”。它把工具执行纳入证据纪律，而不是纳入表演性流程。

### 4.12 语言扩展 hooks 很重要

尽管 `security-review` 默认面向 Go，它并没有把全部方法绑死在 Go 上。skill 明确保留了：

- Node.js / TypeScript
- Java / Spring
- Python / FastAPI / Django

这些语言扩展钩子。

这层设计说明它的真正稳定核心不是 Go 语法知识，而是：

- exploitability-first
- review depth routing
- suppression discipline
- uncovered-risk declaration
- 输出契约

Go 只是当前实现最深的一条 reference path。这个设计让 skill 可以把“审查治理框架”与“语言特定检查项”分离，具备更好的扩展性。

### 4.13 Baseline Diff 模式 被保留

当历史审查产物存在时，skill 会要求把问题标记为：

- `new`
- `regressed`
- `unchanged`
- `resolved`

这层设计在当前评估里没有被充分触发，但它很重要，因为安全 review 很少只做一次。没有 baseline diff，团队就无法区分：

- 这次改动新引入了什么
- 历史问题是否恶化
- 哪些问题已经真正修掉

也就是说，Baseline Diff 模式 让安全审查具备连续治理能力，而不是每次都从零开始写一份孤立报告。

## 5. 这个设计解决了哪些具体问题

结合当前 `SKILL.md`、关键 references 和评估报告，可以把它解决的问题归纳为：

| 问题类型 | skill 中的对应设计 | 实际效果 |
|----------|-------------------|----------|
| 审查深度失控 | 审查深度选择 | 简单变更不被过度审查，复杂变更不漏审 |
| N/A 过多且成本高 | 适用性优先执行 | 先 triage 再深查 |
| 误报过多 | 误报抑制规则 | 提升开发者信任 |
| 发现证据等级模糊 | 证据置信度 | 区分 confirmed / likely / suspected |
| 资源生命周期问题被漏掉 | A 号门禁 + B 号门禁 | 补足连接、事务、响应体、goroutine 风险 |
| 安全域覆盖不系统 | D 号门禁 10-Domain | 审查结构更完整 |
| 报告给人虚假完整感 | F 号门禁 Uncovered Risk List | 明确声明盲区 |
| 安全报告难以治理 | CWE/OWASP mapping + JSON summary | 更适合审计、CI 和跟踪 |

## 6. 主要亮点

### 6.1 它把安全 review 变成 exploitability-first 的流程

这不是“多看几个安全 checklist”，而是先问：这条路径真能被打通吗。

### 6.2 审查深度路由是最显著的结构亮点之一

Lite、Standard、Deep 把安全审查成本和变更风险绑定起来，这是基础模型默认行为里最缺的一层。

### 6.3 误报抑制机制非常关键

很多团队不是不需要安全 review，而是受不了误报。`security-review` 正是在这一点上显著提高了报告质量。

### 6.4 A 号门禁 / D / F 组合形成了清晰的治理闭环

A 号门禁 管生命周期，D 号门禁 管域覆盖，F 号门禁 管未覆盖声明，三者一起显著降低“看起来严谨、实际有盲区”的风险。

### 6.5 输出契约非常适合后续治理

confidence、CWE/OWASP、baseline 状态、JSON summary，让结果能直接进入治理流程，而不只是停留在聊天窗口里。

### 6.6 当前版本的真正增量，在流程纪律而不在漏洞发现本身

评估已经说明：基础模型在很多核心漏洞发现上并不弱；真正的差距在 depth routing、suppression、standard mapping、uncovered risk、JSON output 和系统化覆盖。这说明 `security-review` 的核心价值是审查治理，而不是单纯“更会找漏洞”。

## 7. 什么时候适合用，什么时候不该硬用

| 场景 | 是否适合 | 原因 |
|------|----------|------|
| auth、input、secret、payment、API 等敏感改动 | 非常适合 | 触发信号和多域检查都很强 |
| Go 服务或基础设施相关改动 | 非常适合 | A 号门禁 / D 支持最完整 |
| 需要审计留痕的安全 review | 非常适合 | confidence、mapping、JSON、F 号门禁 都很有价值 |
| benign code 或低风险改动 | 适合 | Lite + Fast Pass 能控制成本 |
| 只想随手看一眼有没有明显漏洞 | 不一定需要全量用 | 但 Lite 模式通常仍有价值 |
| 完全不需要结构化输出的非正式讨论 | 不一定最优 | 可能普通 review 即可 |

## 8. 结论

`security-review` 的真正亮点，不是它能替你报出更多“看起来像安全问题”的条目，而是它把安全审查里最容易失真的工程判断系统化了：先按风险和范围选深度，再按适用性选择该查哪些域，再用 suppression discipline 控制误报，用 confidence 和标准映射控制表述强度，最后用 F 号门禁 明确告诉读者这份报告没覆盖什么。

从设计上看，这个 skill 很清楚地体现了一条原则：**高质量安全 review 的关键，不是让报告变长，而是让每条 finding 都有可利用路径、让每个未覆盖区域都被点名、让整个审查过程知道自己看了什么、没看什么、为什么。** 这也是它特别适合工程安全审查、审计留痕和结构化治理场景的原因。

## 9. 文档维护

当以下内容发生变化时，这份文档应该同步更新：

- `skills/security-review/SKILL.md` 中的 审查深度、证据置信度、Suppression Rules、A 号门禁-F、场景检查清单、聚焦自动化门禁、标准映射 或 输出契约 发生变化。
- `skills/security-review/references/go-secure-coding.md`、`scenario-checklists.md`、`severity-calibration.md`、`anti-examples.md`、`security-review.md` 或语言扩展 references 中的关键规则发生变化。
- `evaluate/security-review-skill-eval-report.md` 或 `evaluate/security-review-skill-eval-report.zh-CN.md` 中支撑本文判断的核心结果发生变化。

建议按季度复查一次；如果 `security-review` 的深度路由、误报抑制规则、D 号门禁 / F 号门禁 输出要求或标准映射规则有明显重构，则应立即复查。

## 10. 相关阅读

- `skills/security-review/SKILL.md`
- `skills/security-review/references/go-secure-coding.md`
- `skills/security-review/references/scenario-checklists.md`
- `skills/security-review/references/severity-calibration.md`
- `skills/security-review/references/anti-examples.md`
- `evaluate/security-review-skill-eval-report.md`
- `evaluate/security-review-skill-eval-report.zh-CN.md`
