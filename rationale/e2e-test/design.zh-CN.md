---
title: e2e-test skill 设计解析
owner: awesome-skills maintainers
status: active
last_updated: 2026-03-27
applicable_versions: current repository version
---

# e2e-test skill 解析

`e2e-test` 是一套围绕关键用户旅程设计的端到端测试执行框架。它的核心设计思想是：**E2E 任务首先要判断应该覆盖哪条旅程、当前环境是否真的可跑、应该选哪个 runner、结果能否证明稳定，以及最终产物是否足够让团队复用、分诊和接入 CI。** 因此它把任务分类、仓库事实发现、环境门禁、runner 选择、稳定性校验、副作用控制和结构化输出收束成一条明确流程。

## 1. 定义

`e2e-test` 用于：

- 选择高价值用户旅程做 E2E 覆盖
- 创建或更新 Playwright 测试
- 用 Agent Browser 做探索、复现，并把结果转成可维护代码
- 处理 flaky test 分诊
- 设计 E2E CI gate
- 在非 JavaScript 项目中选择项目原生 runner 完成同类工作

它输出的不只是测试代码，还包括：

- 任务类型与 runner 选择理由
- 环境和配置状态
- 已覆盖旅程或待分诊失败
- 实际执行命令与执行状态
- artifact 位置
- 下一步动作

在输出会被 CI 或下游工具消费时，它还要求追加机器可读 JSON 摘要；如果本次任务生成了代码，还要补充创建 / 更新的文件，以及脚手架场景下的 skip 条件或 TODO 标记。

## 2. 背景与问题

这个 skill 要解决的，不是“团队不会写浏览器脚本”，而是 E2E 工作在真实仓库里经常同时遇到三类问题：

- 测试目标不清，不知道该覆盖哪条旅程才值回票价
- 环境与依赖并不完备，却仍被写成“可运行”
- 单次通过被误当成稳定，探索结果也没有被沉淀成长期可维护资产

如果没有明确框架，常见失真通常集中在 8 类：

| 问题 | 典型后果 |
|------|----------|
| 把所有浏览器任务都当成 Playwright 代码生成 | 在没有 Node.js / Playwright 的项目里硬套错误工具链 |
| 没先查环境、账号、依赖 | URL、账号、功能开关、sandbox 条件全靠猜 |
| 没有执行完整性约束 | 没跑过却写得像跑过，团队误判当前状态 |
| 单次通过就宣告稳定 | flaky bug 被误判为已修复 |
| 缺少副作用约束 | 测试误打真实支付、真实通知或生产数据 |
| 探索步骤和代码生成脱节 | Agent Browser 里的发现无法沉淀为长期收益 |
| 结构化交付缺失 | 测试、分诊报告和 CI 方案难以横向比较和复盘 |
| 过度依赖 Playwright 细则 | 在非 JS 项目里引入大量无效上下文，增加判断噪音 |

`e2e-test` 的设计逻辑，就是先回答“值不值得做、能不能安全做、该用什么方式做”，再决定写什么代码或给出什么分诊/治理结果。

## 3. 与常见替代方案的对比

先看它与几种常见做法的区别：

| 维度 | `e2e-test` skill | 直接让模型“写个 E2E” | 只做手工探索或临时脚本 |
|------|------------------|----------------------|--------------------------|
| 旅程价值选择 | 强 | 弱 | 弱 |
| 环境 / 配置门禁 | 强 | 弱 | 弱 |
| runner 选择与降级 | 强 | 弱 | 弱 |
| 执行完整性 | 强 | 弱 | 弱 |
| 稳定性证明 | 强 | 弱 | 弱 |
| 副作用控制 | 强 | 弱 | 弱 |
| 探索到代码的桥接 | 强 | 中 | 弱 |
| 结构化交付 | 强 | 弱 | 弱 |
| CI 接入友好度 | 强 | 中 | 弱 |

它的价值不只是“会写测试”，而是把 E2E 工作从零散动作提升成一套可审计、可复用、可治理的工程流程。

## 4. 核心设计逻辑

### 4.1 先做任务分类 vs 直接写代码

`e2e-test` 的 Operating 模式l 第一步就是先判断任务属于哪一类：

- 新旅程覆盖
- flaky 分诊
- 失败 CI 调查
- 探索性浏览器复现
- 测试架构或 CI gate 设计

这一步非常关键，因为这些任务虽然都可能被统称为“E2E”，但目标完全不同。

- 新旅程覆盖，重点是代码质量和长期维护
- flaky 分诊，重点是复现、分类、修复与隔离决策
- CI gate 设计，重点是触发策略、artifact、secret 和分层执行
- 探索性复现，重点是尽快定位真实用户路径与稳定选择器

如果不先分类，后续的工具选择、输出结构和质量标准都会混在一起。

### 4.2 先运行仓库事实发现 vs 靠经验猜

这个 skill 要求在做 gate 决策前运行 `scripts/discover_e2e_needs.sh`，去识别：

- 是否安装了 Playwright
- Node.js 与框架信息
- 是否存在 Go Web 服务与既有 E2E 测试
- 环境变量、dev server、CI 平台和可用工具

这层设计非常重要，因为 E2E 任务里最常见的错误之一，就是对仓库现状做想当然判断。脚本化发现的意义在于：

- 先拿到仓库事实，再做 runner 和 gate 决策
- 把“为什么这么选”变成可复现证据，而不是临场推测
- 避免因为错误假设而走错整条实现路径

这也是它和普通提示词的关键差别之一：不只是建议“先看看项目”，而是要求用固定脚本把这件事做出来。

### 4.3 Agent Browser 和 Playwright 要做成双 runner 模型

`e2e-test` 没有把 Agent Browser 和 Playwright 当成可互换工具，而是明确区分：

- Agent Browser 优先用于探索、复现、截图和理解真实交互
- Playwright 优先用于可提交、可重复、可进 CI 的长期测试代码

这个设计很成熟，因为真实 E2E 工作往往有两个阶段：

- 先弄清楚用户路径到底怎么走、哪里会坏、哪些选择器稳定
- 再把这条已验证的路径沉淀成稳定代码

如果只强调 Playwright，很容易一上来就写代码，结果对真实页面行为理解不足；如果只做 Agent Browser 探索，又难以形成长期资产。双 runner 模型把这两个阶段连接起来，而不是混为一谈。

### 4.4 支持项目原生 runner vs 把 Playwright 硬套到所有仓库

`e2e-test` 虽然以 Playwright 为首选代码路径，但它同时明确规定：**非 JS 项目要使用项目原生测试框架，不要为了套 skill 而强行安装 Playwright。**

这层设计在评估里非常重要。`e2e-test` 面对纯 Go Web 项目时，正确地走了 Go HTTP client 路径，而不是强写 Playwright。

这说明 skill 的目标不是推广某个工具，而是产出“当前环境真正支持的最强交付物”。这也是它比很多“Playwright 风格提示词”更工程化的地方。

### 4.5 配置门禁和环境门禁必须前置

前两道强制门禁分别解决两类不同问题：

- 配置门禁关注变量、账号、功能开关、依赖状态
- 环境门禁关注 local / preview / staging / CI 场景下是否真的可运行

这两层不能合并，也不能后置。原因在于：

- 配置齐全，不代表环境可安全运行
- 环境存在，不代表依赖和账号已经就绪
- 缺一不可，任何一层模糊都会让后面的“可运行测试”变成伪命题

skill 的要求很明确：如果所需值缺失，就不要猜；要么给出带 `test.skip` 和 TODO 的 honest scaffold，要么直接停下来说明 blockers。

### 4.6 执行真实性 是 E2E 场景里的硬要求

`e2e-test` 明确要求：没有实际运行，就必须写 `Not run in this environment`，并说明原因和下一步命令；如果运行了，就要交代：

- 命令
- 目标环境
- pass/fail 状态
- artifact 位置

这层设计特别重要，因为 E2E 任务比普通代码生成更容易让读者误以为“已经验证过”。一旦执行完整性含糊，团队就会混淆三种完全不同的状态：

- 代码已经生成
- 测试已经执行
- 测试已经验证稳定

把这三者拆开，是这个 skill 非常核心的设计价值。

### 4.7 稳定性门禁要明确反对“单次通过 = 稳定”

稳定性门禁明确规定：对关键路径和 flaky 场景，不能因为一次通过就宣告稳定。它要求用重复运行、trace、截图和环境证据来判断：

- bug 是否真的修复
- 测试是否真的稳定
- 失败是不是纯 infra 问题

这层设计在 flaky triage 场景里尤其关键。评估报告也表明，`e2e-test` 的最大增量价值出现在 flaky 分诊，因为 skill 不只是找根因，还强制要求：

- reproduce
- classify
- fix
- 带 owner、tracking issue 和 removal deadline 的 quarantine

也就是说，它提供的是一整套分诊方法论，而不是只提供几条修复建议。

### 4.8 副作用门禁必须单独保留

E2E 测试天然容易碰到真实副作用，例如：

- 创建或修改真实数据
- 触发真实支付
- 发送真实通知
- 走不可逆工作流

因此 `e2e-test` 把副作用门禁单独列出，要求默认采用安全行为，对破坏性操作需要显式批准或隔离环境。

这一层的重要性在于，E2E 工作和单元测试不同，它常常真的会碰到完整业务路径。如果不把副作用控制做成门禁，测试就可能直接越过“验证”边界，进入“真实操作”边界。

### 4.9 把探索到代码的桥接做成显式规则

`e2e-test` 不是把 Agent Browser 当成一次性辅助工具，而是明确规定探索到代码的桥接步骤：

- 记录环境和入口 URL
- 记录命令序列
- 保存 milestone screenshot
- 记下稳定选择器或语义目标
- 把已验证流程翻译成 Playwright 断言和 helper

这层设计很有价值，因为很多探索性验证的问题并不是“找不到问题”，而是找到之后没有被系统化保留。桥接规则解决的是知识迁移问题：把一次探索结果沉淀为可维护的自动化资产。

### 4.10 references 要按场景选择性加载

`e2e-test` 的 references 结构很典型：

- `checklists.md` 和 `environment-and-dependency-gates.md` 始终加载
- Playwright-only 资料只在 JS / Playwright 项目中加载
- Agent Browser workflow 只在使用浏览器探索时加载
- `golden-examples.md` 只在组织输出结构或处理 flaky triage 时加载

这种设计非常合理，因为这个 skill 的覆盖面很广。如果每次都把 Playwright 深度细节、Agent Browser 流程和 golden examples 全部塞进上下文，就会出现两个问题：

- 非相关技术栈被无效信息淹没
- 真正高价值的门禁与决策规则反而被稀释

选择性加载的意义，就是让 skill 既能覆盖复杂场景，又不至于在简单场景里造成上下文浪费。

### 4.11 质量评分卡 不是装饰，而是治理接口

`e2e-test` 的 质量评分卡 明确分成 `Critical / Standard / Hygiene`，并且允许非 Playwright runner 把 Playwright 专属项标记为 `N/A`。

这个设计很成熟，原因有三点：

- 它把“好测试”的要求从口头建议变成了可核对清单
- 它避免用 Playwright 标准错误惩罚非 JS 项目
- 它天然适合和 CI、评审、分诊流程结合

也正因为如此，这个 skill 的输出不仅适合生成测试，也适合做测试治理。

### 4.12 同时服务人类阅读和工具消费的输出合同

`e2e-test` 的输出契约固定要求返回 9 项关键信息；当输出将被 CI 或下游工具消费时，必须追加机器可读 JSON；如果本次生成了代码，还要补充创建或更新的文件，以及脚手架场景下的 skip 条件或 TODO 标记。

这里有两个层次：

- 对人类读者，结构化输出解决“当前状态到底是什么、缺什么、下一步做什么”
- 对自动化系统，JSON 解决“能不能被流水线、报告系统或治理工具直接消费”

评估报告也清楚说明了这一点：基础模型在内容质量上并不差，但没有稳定的结构化报告和 JSON 摘要，因此很难形成跨任务治理能力。

## 5. 这个设计解决了哪些具体问题

结合当前 `SKILL.md`、references 和评估报告，可以把它解决的问题归纳为：

| 问题类型 | skill 中的对应设计 | 实际效果 |
|----------|-------------------|----------|
| E2E 任务类型混淆 | 任务分类 | 根据目标切换覆盖、分诊、CI 设计或探索复现路径 |
| 错误选择 runner | discovery 脚本 + runner 选择指引 | 按仓库事实选择 Playwright、Agent Browser 或项目原生 runner |
| 缺失配置却伪装成可运行 | 配置门禁 | 诚实输出 runnable test、guarded scaffold 或 blockers |
| 环境就绪度判断模糊 | 环境门禁 | 明确 local / preview / staging / CI 的差异与停止条件 |
| 没运行却像运行过 | 执行真实性门禁 | 清楚区分 generated、executed、validated |
| 单次通过即宣告稳定 | 稳定性门禁 + flaky 测试策略 | 引入重复运行、trace 和隔离纪律 |
| 真实副作用风险被忽略 | 副作用门禁 | 限制破坏性流程和真实业务副作用 |
| 探索成果无法沉淀 | Agent Browser 桥接规则 | 把探索结果转化为可维护代码 |
| 报告难以比较和自动化接入 | 输出契约 + 可选 JSON | 同时服务团队协作与 CI/tooling |

## 6. 主要亮点

### 6.1 把 E2E 工作做成了完整执行框架

`e2e-test` 的重点不是某一个测试框架，而是把旅程选择、runner 选择、环境判断、稳定性判断和交付结构串成一个闭环。

### 6.2 对环境适应和诚实降级处理得很成熟

它不会因为“这是 E2E task”就一律输出 Playwright，而是要求先看仓库事实，再给出当前环境能支持的最强结果。

### 6.3 在 flaky 分诊场景里特别强

评估里它最大的优势就来自 flaky triage，因为 skill 不只是帮忙分析，还要求遵循 reproduce、classify、fix、quarantine 的标准流程，并给出稳定性验证要求。

### 6.4 同时兼顾探索速度和长期可维护性

Agent Browser 负责快速探索和复现，Playwright 或原生框架负责可提交代码，这种分工让探索结果不会停留在一次性操作里。

### 6.5 结构化输出非常适合测试治理

Task type、Runner choice、Environment gate、Config status、Executed commands、Artifacts、Next actions，再加上在 CI / tooling 场景下必须提供的 JSON，以及代码生成时附带的文件和 skip/TODO 信息，这些内容天然适合被团队复盘、被 CI 消费、被治理工具汇总。

### 6.6 选择性加载让大 skill 仍然保持实用

`e2e-test` 的参考资料很多，但它没有要求每次全量加载，而是用“始终加载 + 场景按需加载”的方式控制上下文成本，这正是复杂 skill 可持续扩展的关键。

## 7. 什么时候适合用，什么时候不该硬用

| 场景 | 是否适合 | 原因 |
|------|----------|------|
| 关键用户旅程自动化覆盖 | 适合 | 这是它的核心场景 |
| flaky test 分诊 | 适合 | 这是它增量价值最明显的场景 |
| 设计 E2E CI gate | 适合 | 结构化输出、artifact 和分层策略很有用 |
| 先探索再转成稳定自动化代码 | 适合 | Agent Browser 桥接规则正是为此设计 |
| 非 JS Web 项目的 E2E | 适合 | 它支持原生 runner 和诚实降级 |
| 纯视觉审美检查 | 不适合 | 这不属于自动化旅程价值 |
| 负载 / 压测 | 不适合 | 这不是 E2E 技能的目标 |
| 需要猜测私有账号、密钥或 endpoint | 不适合 | skill 明确禁止这种做法 |

## 8. 结论

`e2e-test` 的真正亮点，不是它偏好 Playwright 或会用 Agent Browser，而是它把端到端测试里最容易失真的部分系统化了：先识别任务类型，再用 discovery 脚本拿到仓库事实，随后通过配置、环境、执行完整性、稳定性和副作用几道门禁，选择合适的 runner，最后把结果以结构化方式交付给人和系统。

从设计上看，这个 skill 非常清楚地体现了一条原则：**E2E 的价值不只是“覆盖到了”，而是“覆盖得真实、判断得诚实、结果能复用、故障能治理”。** 这也是它特别适合关键旅程、flaky 分诊和 CI gate 设计的原因。

## 9. 文档维护

当以下内容发生变化时，这份文档应该同步更新：

- `skills/e2e-test/SKILL.md` 中的 runner 策略、强制门禁、输出契约、质量评分卡 或 CI Strategy 发生变化。
- `skills/e2e-test/references/checklists.md`、`environment-and-dependency-gates.md`、`agent-browser-workflows.md`、`golden-examples.md` 或 Playwright references 中的关键规则发生变化。
- `skills/e2e-test/scripts/discover_e2e_needs.sh` 的检测字段、判定逻辑或 verdict 结构发生变化。
- `evaluate/e2e-test-skill-eval-report.zh-CN.md` 中支撑本文结论的关键结果发生变化。
- skill 在 runner 适配或输出合同方面有明显重构。

建议按季度复查一次；如果 `e2e-test` 的 gate、runner 策略或 discovery 脚本有明显重构，则应立即复查。

## 10. 相关阅读

- `skills/e2e-test/SKILL.md`
- `skills/e2e-test/references/checklists.md`
- `skills/e2e-test/references/environment-and-dependency-gates.md`
- `skills/e2e-test/references/golden-examples.md`
- `skills/e2e-test/references/agent-browser-workflows.md`
- `skills/e2e-test/references/playwright-patterns.md`
- `skills/e2e-test/references/playwright-deep-patterns.md`
- `skills/e2e-test/scripts/discover_e2e_needs.sh`
- `evaluate/e2e-test-skill-eval-report.zh-CN.md`
