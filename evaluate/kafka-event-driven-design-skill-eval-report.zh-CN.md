# kafka-event-driven-design Skill 评估报告

> 评估框架：[skill-creator](https://github.com/anthropics/skills/tree/main/skills/skill-creator)
> 评估日期：2026-04-18
> 评估对象：`kafka-event-driven-design`

> [!IMPORTANT]
> **状态：§1–§7 已被推翻，请先读 [§8](#8-本次评估的有效性边界2026-08-09-补充)。**
>
> 下文的 A/B 数字（含"加权通过率 +50 pp"与"生产就绪"）所用的 oracle 是从技能自己的
> 检查清单里抄出来的。该 oracle 至少把一处事实错误判成了 PASS，因此这些通过率衡量的是
> **对技能的遵循度，而不是正确性**。此后三轮外部评审在本报告判为"优点"的文档里查出了
> 实质缺陷。
>
> 今天真正被验证的是**文档**，靠的是 8 道确定性关卡（26 条语义 lint 规则、mutation
> 扫描、独立同义改写语料、golden fixture，以及对模型评估打分器的离线标定）。仍未被
> 验证的是**模型本身**：A/B 评估的框架已经就位、打分器已标定，但还没有任何一组结果
> 是对真实模型跑出来的。此外仍欠着 trigger recall/precision 与真实 broker 矩阵。
> 见 §8.5、§8.7 与 §8.8。
>
> 请勿把 §1–§7 当作"技能有效"的证据引用。

---

`kafka-event-driven-design` 是一个 Kafka 事件驱动架构设计与审查技能，覆盖 topic 设计、分区策略、事件 schema 定义（Avro/Protobuf）、幂等生产者、消费者去重、死信队列（DLQ）、精确一次语义、Schema Registry 兼容性、背压处理与消费者 lag 监控。本次评估采用 3 场景 A/B 测试（6 次真实模型调用），通过 23 条评分断言对比带技能与不带技能的响应质量。评估揭示的最关键发现是：基准模型在 Kafka 架构知识上总体扎实（场景 1 加权通过率高达 75%），而技能的核心差异化价值集中在三点：**将 `enable.idempotence=false` 正确分类为 Critical 缺陷**（基准认为"可接受"）、**强制 BACKWARD_TRANSITIVE 兼容模式**（基准使用更弱的 BACKWARD）、以及**DLQ 强制检查**（基准在 producer 审查场景中完全遗漏）。

## 1. Skill 概述

`kafka-event-driven-design` 定义了 4 个强制门控（Context Collection → Scope Classification → Risk Classification → Output Completeness）、3 个深度级别（Lite/Standard/Deep）、4 种降级模式（Full/Degraded/Minimal/Planning）和包含 14 项的设计检查表，通过 §9 输出契约确保每次输出均包含架构设计、风险评估、实现代码、监控告警和未覆盖风险章节。

**核心组件：**

| 文件 | 行数 | 职责 |
|------|------|------|
| `SKILL.md` | ~380 | 主技能定义（4 门控、3 深度、14 项检查表、6 内联 + 7 扩展 anti-examples、§8 评分卡、§9 输出契约） |
| `references/event-schema-patterns.md` | 210 | 事件信封格式、schema 演化策略（BACKWARD/FORWARD/FULL）、Avro/Protobuf/JSON Schema 对比、幂等键设计、Outbox Pattern |
| `references/consumer-failure-modes.md` | 225 | Rebalance Storm、Poison Message/DLQ、Lag Runaway、Duplicate Processing、Ordering Violation 及防御矩阵 |
| `references/consumer-anti-examples.md` | 138 | AE-7 到 AE-13：自动提交、阻塞 I/O、单分区全局排序、Group ID 复用、Compacted Topic 空值、分区增加、无 schema 校验 |
| `scripts/tests/test_skill_contract.py` | — | 50 项合约测试（12 类，覆盖 frontmatter、门控、深度、降级、检查表、评分卡、输出契约、参考文件） |
| `scripts/tests/test_golden_scenarios.py` | — | 41 项 golden 测试（11 个 fixture：4 critical 缺陷、3 standard 缺陷、2 good_practice、1 degradation、1 workflow） |

---

## 2. 测试设计

### 2.1 场景定义

| # | 场景名称 | 核心挑战 | 期望结果 |
|---|----------|----------|----------|
| 0 | Producer 配置安全审查 | `acks=1`、`Idempotent=false`、`Key=nil`，无 DLQ，无事件信封元数据 | Critical 失败全部识别，产生完整评分卡与未覆盖风险 |
| 1 | 多消费者扇出架构设计 | 3 个不同交付语义的消费者（金融/通知/分析），需要 schema 演化和消费者组隔离 | 完整架构含 BACKWARD_TRANSITIVE、幂等消费者模式、DLQ、分级 lag 告警 |
| 2 | 降级场景：Topic 设计问题 | 无环境上下文，用户询问 `events`/分区 1/保留 1 天的 topic 设计是否合理 | 正式声明降级模式，识别三项具体问题，列出阻断性未知项 |

### 2.2 断言矩阵（23 项）

**场景 0 — Producer 配置安全审查（9 项）**

| ID | 断言 | With-Skill | Without-Skill |
|----|------|:----------:|:-------------:|
| A1 | 完整的上下文收集表（§9.1，含 Kafka 版本/schema/ordering/delivery） | PASS | FAIL |
| A2 | `acks=1` 明确标记为 Critical / 数据丢失风险 | PASS | PASS |
| A3 | `Idempotent=false` 标记为 Critical（不是"可接受的权衡"） | PASS | FAIL |
| A4 | 无 DLQ 标记为 Critical（毒消息将阻塞分区） | PASS | FAIL |
| A5 | 空分区键（`Key=nil`）标记为 ordering 失效风险 | PASS | PASS |
| A6 | 无事件信封元数据（无 `event_id`）标记为去重不可能 | PASS | FAIL |
| A7 | 推荐 `acks=all` + `enable.idempotence=true`（二者同时） | PASS | PARTIAL |
| A8 | 包含 Critical/Standard/Hygiene 三层评分卡 | PASS | FAIL |
| A9 | 包含 §9.9 未覆盖风险章节 | PASS | FAIL |

**场景 0**：Without-Skill = 2 通过 + 1 部分 + 6 失败（加权 2.5/9 = 28%）| With-Skill = **9/9 全部通过**

**场景 1 — 多消费者扇出架构设计（8 项）**

| ID | 断言 | With-Skill | Without-Skill |
|----|------|:----------:|:-------------:|
| B1 | 以 Standard 或 Deep 深度正式分类并说明理由 | PASS | FAIL |
| B2 | Topic 命名遵循 `{domain}.{entity}.{event-type}` 约定 | PASS | PASS |
| B3 | 分区键使用 `order_id`（非 null，保证 per-order 排序） | PASS | PASS |
| B4 | 每个消费者服务使用独立的 Consumer Group | PASS | PASS |
| B5 | payment-service 需要幂等消费（DB 级 `ON CONFLICT DO NOTHING`） | PASS | PASS |
| B6 | Schema 包含完整事件信封（`event_id`、`event_type`、`timestamp`、`source_service`、`correlation_id`） | PASS | PARTIAL |
| B7 | Schema Registry + `BACKWARD_TRANSITIVE` 兼容性模式（非仅 `BACKWARD`） | PASS | PARTIAL |
| B8 | 分 Consumer Group 的 lag 监控 + DLQ 设计 | PASS | PASS |

**场景 1**：Without-Skill = 5 通过 + 2 部分 + 1 失败（加权 6/8 = 75%）| With-Skill = **8/8 全部通过**

**场景 2 — 降级边界场景（6 项）**

| ID | 断言 | With-Skill | Without-Skill |
|----|------|:----------:|:-------------:|
| C1 | 正式声明处于降级模式 | PASS | FAIL |
| C2 | Topic 名称 `events` 标记为反模式（过于通用，AE-1 等价） | PASS | PASS |
| C3 | 分区数 1 标记为扩展性缺陷（UNSAFE，AE-9 等价） | PASS | PASS |
| C4 | 保留 1 天标记为数据丢失风险（不适合订单系统） | PASS | PASS |
| C5 | 主动请求缺失的上下文（Kafka 版本、delivery guarantee、throughput、ordering 需求） | PASS | FAIL |
| C6 | §9.9 将所有未知项列为阻断性缺口 | PASS | FAIL |

**场景 2**：Without-Skill = 3 通过 + 0 部分 + 3 失败（加权 3/6 = 50%）| With-Skill = **6/6 全部通过**

---

## 3. 通过率对比

### 3.1 总体通过率

| 配置 | 通过 | 部分通过 | 失败 | 严格通过率 | 加权通过率（部分 = 0.5） |
|------|:----:|:-------:|:----:|:---------:|:-----------------------:|
| **With-Skill** | **23** | 0 | 0 | **100%** | **100%** |
| **Without-Skill** | 10 | 3 | 10 | 43% | **50%** |

**通过率提升：+57 pp（严格）/ +50 pp（加权）**

### 3.2 按场景通过率

| 场景 | With-Skill | Without-Skill（加权） | 差异 |
|------|:----------:|:--------------------:|:----:|
| 0. Producer 配置审查 | 9/9 (100%) | 2.5/9 (28%) | +72 pp |
| 1. 多消费者扇出设计 | 8/8 (100%) | 6/8 (75%) | +25 pp |
| 2. 降级边界场景 | 6/6 (100%) | 3/6 (50%) | +50 pp |

### 3.3 关键差异维度

| 差异维度 | With-Skill | Without-Skill |
|----------|:----------:|:-------------:|
| `enable.idempotence=false` 分类为 Critical | 3/3 (100%) | 0/3 (0%) |
| `BACKWARD_TRANSITIVE` 兼容性模式（非仅 BACKWARD） | 1/1 (100%) | 0/1 (0%) |
| §9 评分卡产出 | 3/3 (100%) | 0/3 (0%) |
| §9.9 未覆盖风险章节 | 3/3 (100%) | 0/3 (0%) |
| 降级模式正式声明 | 1/1 (100%) | 0/1 (0%) |
| DLQ 在 producer 审查中标记为 Critical | 1/1 (100%) | 0/1 (0%) |
| 完整事件信封（含 `correlation_id`） | 3/3 (100%) | 1/3 (33%) |
| 主动请求缺失上下文（Gate 1 项） | 1/1 (100%) | 0/1 (0%) |

---

## 4. 关键差异分析

### 4.1 With-Skill 独有的行为（Without-Skill 完全缺失）

**A3 — `Idempotent=false` 的 Critical 分类**

本次评估最关键的知识分歧点。不带技能的基准响应明确写道：

> *"Idempotent=false Is Acceptable Here, But Note the Trade-Off — With retries enabled and Idempotent=false, a retry after a broker ack-but-network-drop produces a duplicate message. For at-least-once this is allowed by definition..."*

这是一个有技术依据但不完整的判断——它忽视了订单场景下的业务影响。带技能的响应将其列为 Critical FAIL，并明确说明 `enable.idempotence=true` + `MaxOpenRequests=1` 是最小安全配置的一部分。这与 AE-1 的精确定义完全对应，而基准模型没有这个区分框架。

**A4 — DLQ 在 Producer 审查中的 Critical 地位**

不带技能在 Producer 代码审查场景（场景 0）中完全未提及 DLQ 的缺失。带技能在评分卡中将其列为 Critical 0/3 FAIL，并在 §9.9 中明确说明"Consumer 代码未提交 → 毒消息将无限重投 → 分区堆积"。这是技能 AE-3 的直接映射，基准在面对 producer 代码时不会主动联想到 consumer 侧的 DLQ 需求。

**B7 — `BACKWARD_TRANSITIVE` vs `BACKWARD`**

不带技能在场景 1 中推荐了 Schema Registry 并选择了 `BACKWARD` 兼容性模式。带技能选择了 `BACKWARD_TRANSITIVE`，并给出了关键理由：

> *"BACKWARD_TRANSITIVE checks compatibility against ALL previous schema versions, not just the immediately preceding one — critical when multiple consumers may be deployed at different schema versions simultaneously during rolling deploys."*

`BACKWARD` 只针对最近一个版本做检查：它保证的是**新 schema 的 reader 能读取旧数据**，因此升级顺序是消费者先行。（反过来"旧 reader 能读新数据"是 `FORWARD`，两个方向经常被写反。）当消费者可能落后不止一个版本时，`BACKWARD` 的单版本检查不足以覆盖全部历史数据，`BACKWARD_TRANSITIVE` 会对所有已注册版本做检查，补上这个缺口。

> **2026-08-09 更正**：本节此前写作"`BACKWARD` 无法保证旧版消费者能读取新 schema"，方向写反了——那描述的是 `FORWARD`。同一段英文版原文表述正确，属于中文版单侧错误。同时需要说明：`BACKWARD_TRANSITIVE` 并非无条件"最安全"，它把 schema 永久约束在全部历史版本的交集上；只有当旧数据或旧 reader 确实跨越多个版本存活时才值得付这个代价。技能正文已按此修订，评分断言 B7 的措辞也相应从"必须选 `BACKWARD_TRANSITIVE`"改为"兼容模式的选择有明确依据且方向陈述正确"。

### 4.2 Without-Skill 能做到但质量较低的行为

**B2/B3/B4/B5/B8 — 场景 1 中的 Kafka 架构知识**

不带技能在场景 1 中表现出色：正确推荐了 `order_id` 作为分区键、3 个独立 Consumer Group、payment-service 的 DB 级幂等处理（`INSERT INTO payment_records ON CONFLICT`）、per-consumer lag 告警和 DLQ。

这说明基准模型对 Kafka 常见架构模式有扎实知识。技能在场景 1 中的增量贡献主要是：完整事件信封（`correlation_id` 等）、`BACKWARD_TRANSITIVE` 的精确选择、§9 输出契约的结构完整性，以及 §9.9 中覆盖了 9 项系统性未知风险（包括"payment-service 订阅 `orders.shipped` 的必要性"、"外部支付网关幂等键"等非显而易见的风险）。

**C2/C3/C4 — 场景 2 的技术判断**

不带技能在场景 2 中对三个具体问题（topic 命名、分区数 1、保留 1 天）给出了正确且有深度的技术分析。基准模型知道这些是问题，并给出了可操作的建议值。技能的差异化价值在于：正式声明降级模式（"Degraded mode"）、主动请求 8 项 Gate 1 上下文、将所有未知项结构化为 §9.9 阻断性缺口，以及产出评分卡（0/12 FAIL）使判定结论可操作化。

### 4.3 场景级关键发现

**场景 0** 是与技能差异最大的场景（+72 pp）。基准对 acks 的问题有正确认知，但对 idempotence、DLQ、事件 schema 元数据的认知均存在缺口或分类错误。订单场景的高业务价值使这些缺口的实际风险极高。

**场景 1** 是基准最强的场景（75% 加权）。这与 oracle-migration 评估的类似发现一致：现代基准 LLM 对主流分布式系统模式有相当强的内化知识，技能的价值更多体现在精确知识（`BACKWARD_TRANSITIVE`、完整信封）和结构化输出（评分卡、§9.9）上，而非填补技术空白。

**场景 2** 展示了技能的降级协议价值：基准给出了"这几点有问题，改成这样"的实用建议，但没有触发 Gate 1 上下文收集流程，没有识别出"交付保证"和"排序需求"等会根本影响 topic 设计的缺失信息。

---

## 5. Token 效费比分析

### 5.1 Skill 上下文 Token 成本

| 文件 | 行数 | 估算 tokens |
|------|------|:-----------:|
| `SKILL.md` | ~380 | ~9,500 |
| `event-schema-patterns.md` | 210 | ~5,300 |
| `consumer-failure-modes.md` | 225 | ~5,600 |
| `consumer-anti-examples.md` | 138 | ~3,500 |
| **合计（Deep 深度全加载）** | | **~23,900** |

### 5.2 实际运行 Token 消耗（6 次真实调用）

| 场景 | Without-Skill tokens | With-Skill tokens | 额外开销 | 工具调用次数 |
|------|:--------------------:|:-----------------:|:--------:|:-----------:|
| 场景 0（Standard：SKILL.md + schema patterns + anti-examples） | 13,889 | 35,160 | +153% | 10 |
| 场景 1（Standard/Deep：全部 3 个参考文件） | 16,101 | 49,610 | +208% | 17 |
| 场景 2（Degraded：SKILL.md + schema patterns） | 13,091 | 33,925 | +159% | 9 |
| **平均** | **14,360** | **39,565** | **+175%** | **12** |

> **注：** token 数为完整会话 token（输入 + 工具调用 + 工具结果 + 输出），由 Agent 工具 usage 字段实测。场景 1 的 17 次工具调用（最高）反映了 Standard/Deep 深度需要读取全部 3 个参考文件 + SKILL.md 的真实消耗。在技能作为系统提示直接注入（非 tool-read）的生产用法中，overhead 将回落至 SKILL.md ~9,500 tokens + 按需参考文件，接近 40–60% 额外开销。

### 5.3 效费比计算

场景 0 揭示了最高的业务价值密度：基准模型对 `enable.idempotence=false` 的错误分类（认为"可接受"）在生产订单系统中会直接导致在网络抖动/broker 重启场景下产生重复事件。对于金融类事件，一次重复处理导致的双重扣款修复成本远超任何 token 开销。场景 1 显示在基准模型已有扎实知识的领域（主流 Kafka 模式），技能的增量成本-收益比最低，但仍提供了 `BACKWARD_TRANSITIVE` 等精确知识和完整输出结构。

---

## 6. 综合评分

### 6.1 分维度评分

| 维度 | With-Skill | Without-Skill | 差值 |
|------|:----------:|:-------------:|:----:|
| **Critical 缺陷识别率**（A2+A3+A4） | 3/3 (100%) | 1/3 (33%) | +67 pp |
| **Standard 知识精确性**（B6+B7） | 2/2 (100%) | 0/2 (0%) | +100 pp |
| **降级模式合规性**（C1+C5+C6） | 3/3 (100%) | 0/3 (0%) | +100 pp |
| **结构化输出完整性**（A8+A9+B1） | 3/3 (100%) | 0/3 (0%) | +100 pp |
| **基础 Kafka 知识**（A2+A5+B2+B3+B4+B5+B8+C2+C3+C4） | 10/10 (100%) | 9.5/10 (95%) | +5 pp |

### 6.2 加权总分

| 配置 | 总得分 | 加权通过率 |
|------|:------:|:---------:|
| With-Skill | 23/23 | **100%** |
| Without-Skill | 11.5/23 | **50%** |

---

## 7. 结论

`kafka-event-driven-design` 在 3 个场景和 23 条断言的 6 次真实模型调用评估中，带技能配置达到 **100% 断言覆盖率**，加权通过率从 **50% 提升至 100%**（+50 pp）。

与 oracle-migration 评估类似，本次评估也揭示了基准模型的 Kafka 知识比预期更强——场景 1（多消费者扇出设计）基准加权通过率高达 75%，说明主流 Kafka 架构模式已充分内化。技能的核心差异化价值集中在以下三点：

1. **Critical 缺陷的正确分类** — `enable.idempotence=false` 被基准认为"可接受"，被技能正确分类为 Critical FAIL。在订单等金融场景，这一误判直接导致生产重复事件风险。DLQ 缺失在 producer 审查时被基准完全遗漏，被技能通过 AE-3 强制覆盖。

2. **精确知识而非通用知识** — `BACKWARD_TRANSITIVE` vs `BACKWARD` 的区别、完整事件信封（含 `correlation_id`、`source_service`）、Outbox Pattern 的必要性——这些不是"基准不知道"的知识，而是"基准知道但不能在正确时机、正确分类下给出"的知识。技能通过参考文件提供了可引用的精确规范。

3. **结构化输出契约** — §9 输出契约（评分卡 + §9.9 未覆盖风险）将设计/审查输出转化为可用于 CI/CD 阻断的工程判定。这是基准无论知识多强都无法自发产生的输出格式。

**本节结论已被推翻，保留原文以留痕。** 本节原文写的是"生产就绪，对所有 Kafka 架构设计与代码审查工作流推荐使用"。这个结论在 §8 面前站不住：它依赖的 oracle 是从技能自己的检查清单抄来的，而该 oracle 至少把一处事实错误判成了 PASS。其中真正站得住的部分更窄，也依然成立——在金融类事件（payment、order）场景下，`enable.idempotence` 的分类和 DLQ 强制检查确实是技能与基准差异最有价值的地方。站不住的是"是否就绪"这个判定本身。当前状态见 §8。

---

## 8. 本次评估的有效性边界（2026-08-09 补充）

一次外部评审在技能中发现了若干技术错误，而本报告把其中一部分记成了"优点"。问题出在方法上，以下限制适用于上文所有数字。

**8.1 oracle 大部分来自技能自身。** 评分断言是照着技能自己的检查清单写的，因此模型只要复述技能的立场就能拿 PASS——包括立场本身是错的时候。断言 B7 奖励 `BACKWARD_TRANSITIVE`，依据是技能自称"对多数场景最安全"；而 Confluent 的实际规则中这是一个取舍，不是正确性排序。用被测对象派生出的评分标准，无法发现被测对象本身有错，只能衡量"是否照做"。

**8.2 至少有一个 oracle 本身就是错的。** Schema Registry 相关断言编码了"BACKWARD 不能删除字段"这一误解。带技能的回答复述该错误会被判 PASS；而正确回答"BACKWARD 允许删除 optional 或带默认值的字段"反而会被判 FAIL。在这一项上，评估与事实是负相关的。

**8.3 完全没有测触发准确率。** 项目评估框架要求 trigger recall/precision——该触发时是否触发、不该触发时是否保持沉默。本次只跑了在范围内的 prompt，误触发率未测。

**8.4 Token 成本没有与收益一起权衡。** 带技能回答平均多消耗约 **175%** 的 token。在没有分场景收益/成本拆解的前提下，"加权通过率 +50 pp"这个标题数字与该成本不可直接比较；场景 1（基准已达 75%）正是性价比最差的一档。

**8.5 已经替换了什么、还缺什么。** *（本小节的数字是第一轮时的状态；当前数字见 §8.7。）* 技能补上了一套 6 道确定性关卡：22 条语义 lint 规则，配自检用例证明每条规则既能触发也能保持沉默；24 项 mutation 扫描，每条规则都被一次"把结论写反"的改动检验过；每个 golden fixture 声明精确的双向检测期望；以及一张上游事实表，取值直接抄自 Apache Kafka 源码（分支 2.8 / 3.0 / 4.3 的 `ProducerConfig.java`、`ConsumerConfig.java`、`docs/operations/*.md`），而非取自被测文档。把这套 linter 指向修改前的旧文档，它独立报出 15 条规则、18 处问题，与外部评审的结论一致。

这套关卡检验的是**文档**，不是**模型**。要重跑 A/B 评估，仍然需要：由未读过该技能的人依据官方文档构建的盲测 oracle、trigger recall/precision，以及一列 token 成本。在此之前，§1–§7 的通过率应被理解为"对技能的遵循度"，而不是"正确性"。

### 8.6 第二轮外部评审（同日）又发现了什么

上述关卡建好并全绿之后，第二轮评审仍然找出**四类实质缺陷**，这是本报告中信息量最大的一条数据：

1. **linter 没有对应规则的内容错误** — 把 event sourcing 写成"需要 compacted topic"。而 `compact` 只保留每个 key 的最新值，在以 aggregate ID 为 key 的日志上恰好会删掉全部历史。
2. **linter 自身可被绕过。** 用于"允许文档引用错误说法再加以否定"的抑制机制，作用域是整句，且没有绑定到被否定的那个命题，因此 `acks=all is wrong; prefer acks=1` 报出 0 findings。另有两种改写以同样方式绕过。
3. **规则未覆盖的内部矛盾** — 某处 reference 给出固定的 `lag > 10000` 告警阈值，与技能正文自己"禁止未经推导的数值阈值"的规定直接冲突；static membership 被夸大为"重启不会触发 rebalance"；poison message 症状写成 lag 恰为 1（仅在生产已停止时成立）；以及"transactional consumer"这个并不存在的说法。
4. **支持范围漂移** — Gate 1 列了 `franz-go`，客户端矩阵里却没有。

以上全部修复，且每一条现在都有对应规则和 mutation 兜底（25 条规则、33 项 mutation，其中 6 项是直接照绕过形式构造的对抗性改写）。要带走的结论是：**一套全绿的确定性关卡，只能约束它已经写了规则的那些错误，对其余部分不提供任何保证**——最容易被高估的恰恰是它自己的覆盖面。第一轮和第二轮都是在上一轮报告"干净"之后又查出真实缺陷。

SKILL.md 作为常驻上下文，体积已从第一轮前的约 17 KB 增至约 32 KB。这买来的是版本/客户端条件化判定、治理章节、明确的 N/A 与 WARN 评分语义，以及明示的负向适用范围；这是实实在在的成本，已如实记入 COVERAGE.md，而不是辩解掉。

### 8.7 第三轮（2026-08-09）——补齐第二轮留下的缺口

第三轮评审列出六项待办。其中四项已关闭，一项前提不成立，一项确实仍然敞着。

**已关闭：**

1. **语义 lint 此前只在自己的措辞上被验证过。** 新增独立的 `scripts/paraphrase_corpus.py`：每条命题都按工程师实际会写的方式陈述一遍，错误说法与针对同一主题的正确说法各写一组，且不复用文档里的任何措辞。它查出了一轮全绿 mutation 扫描没能查出的 **13 条规则、23 处漏报**，均已修复。目前 26 条规则、113 条探针，0 漏报、0 误报；任何规则缺少任一极性的探针都会导致这道关卡失败。
2. **评分卡的 WARN/N/A 算术不够机械。** §8 现在定义五种判定，逐一说明对分子/分母的影响，阈值改为随可评分项数 `A` 缩放的 `ceil` 形式，`NOT SCOREABLE` 升级为独立判定并强制决定总判定，另附 CI 阻断用法。§9 的输出模板不再打印固定的 `/3` `/5` `/4` 分母——这是本轮新查出的、与 §8 残留矛盾的一处，现已有契约测试拦住。
3. **franz-go 没有回归锚点。** 契约测试原先只检查三个客户端，删掉 franz-go 一列照样能通过。现在测试把客户端默认值表当结构化数据解析，并针对 franz-go 那一列断言"幂等默认开启"以及 `DisableIdempotentWrite()` 被写出。由此暴露的计数陈述（"三大客户端库""全部三份 reference""三者都错"）本身也已纳入测试。
4. **reference 文件没有目录。** 四份 reference 均超过 100 行，现在开头都有一张按"要查什么症状"组织的目录表，并有测试断言每个锚点都能落到真实标题上。

**前提不成立：** 缺少 `agents/openai.yaml` 不是缺陷。该文件是在 `dc55e6f` 中被全仓库有意删除的；过时的是 `bestpractice/` 里的约定描述，已改正该处描述，而不是把文件加回来。

**仍然敞着——模型没有被评估。** §8.3 与 §8.5 依然成立：没有盲测 oracle，没有真实 broker 矩阵，**也仍然没有 trigger recall/precision 的数字**。新增的 `scripts/trigger_eval.py` 已就位——30 条探针（15 条在范围内，15 条是刻意贴边的范围外用例，取自 §1 的排除表），只把 frontmatter description 交给模型做路由判断，并按 0.90 的非对称目标计算 recall 与 precision。它的管路已验证：`--dry-run` 与"基础设施不可用即跳过"两条路径行为符合设计，且跳过时退出码为 2 而非 0，因此不可能被误当成通过。**但它没有产出过一次有效评分。** 在当前环境下，嵌套的 `claude -p` 不继承父会话凭据，所有探针都返回 `Not logged in`，于是它如实报出 `SKIPPED (infra)` 而不是一个数字。也就是说这项测量仍然欠着；它同时是可选关卡，不进 `run_regression.sh`。即便将来跑通，它也不解决盲测 oracle 的缺口——路由准确率和回答正确性是两个问题。**"全部关卡绿"至今只意味着：文档内部自洽，且不含那 26 条规则所编码的错误——不意味着技能能可测量地改善模型输出。**

*（本节数字是第三轮时的状态；当前数字见 §8.8。）*

---

## 8.8 第四轮评审——工程整改全部完成，实证测量仍待执行

六项发现全部动手改了。下文的"关闭"指的是**工程侧**关闭——矛盾消除了、关卡建起来了、脚手架能跑了。它**不**表示被测量的东西已经被测量：第 1 条的结局是一套打分器已标定、但 A/B 从未对真实模型跑过的框架。这个区分正是 §8 的立意，所以把它写进标题，而不是埋在正文里。

**1. 模型仍然没有被有效评估——框架建好了，仍然没跑。** `trigger_eval.py` 量的是路由，而且只是代理指标：它衡量的是"frontmatter 的 description 能不能被一个评判模型正确分类"，既不是宿主 agent 真实的路由决定，也不是技能加载之后回答是否正确。这三条限制现在写进了它自己的 docstring。

真正的缺口用另一种方式补上。`scripts/model_eval.py` 在 16 个 defect fixture 上跑 A/B——只有提示词 vs 提示词加 SKILL.md——而且**打分器不是模型**：按每个 fixture 声明的 `coverage_rules` 计算召回，再对模型自己输出里触发的任何 KL 规则扣分。两者都可离线复算、可审计。B 组必须过一个**绝对**阈值，而不只是赢过 A 组——只看 delta 的门禁，在两组坏得一样多的时候会放行。

它和又一个"跑不起来的脚本"的区别在 `--calibrate`：这一步给打分器打分，离线、不需要凭据，用每个 fixture 自己的 `expected_feedback`（已知正确的评审）对上一条手写诱饵（流利、笃定、但错的评审），并要求**逐个 fixture** 分开，而不是看平均值。它是回归套件的第 7 道关卡。第一次执行就在三个 fixture 上失败，且每一条都是真缺陷：`KAFKA-003` 和 `KAFKA-009` 声明的 `coverage_rules` 连它们自己的标准答案都不满足（`dead letter` 与 `DLQ` 并列、`poison`、以及 `never claim` 这种短语），`KAFKA-006` 的标准答案则从头到尾没提 Schema Registry。要求的是措辞而非覆盖面的那几条被改指到真正的概念上，唯一一处确实写薄了的答案被补齐。

**仍然敞着，且照直说：** 没有任何一组结果是对真实模型跑出来的。当前环境下嵌套的 `claude -p` 不继承会话凭据，所以 A/B 退出码是 2（`SKIPPED (infra)`），永远不会是 0。`--runner` 接受任意 CLI，因此不绑定任何一家。

**2. 版本门控自相矛盾，一处结论散在三个地方。** §2 的 STOP 要求 broker 版本和客户端**两者都**未知才停；§4 的硬规则要求**两者都**已知才给结论；§8 的 NOT SCOREABLE 行又重复了一遍"两者都未知"。同一个决定三套说法，而且三套都把四件互相独立的事实揉成了一个全局开关。

改成一张**每个评分项的最小上下文**表：producer 持久化由客户端库及其版本决定（默认值是客户端属性——broker 版本对这两个结论都不产生影响）；consumer protocol 相关的配置项由 `group.protocol`、或可推出它的 broker 版本决定；功能可用性由 broker 版本决定；**其余全部不需要版本**。最后一行才是重点——客户端版本未知只挡住第 5 项，不挡别的，更不能拿它当借口不给 partition key 或 DLQ 的结论。§4 和 §8 现在都指回这张表而不是各自复述一遍，并有一组按段落分别取文本的契约测试，断言没有任何一处把全局 and-gate 装回去；作用域切到每个段落，是为了避免"其中一处写对了"就把另外两处的错误盖住。

**3. 覆盖率文档和实际关卡脱节。** 跑的是 7 道关卡，`COVERAGE.md` 只列 5 道，因为生成器把这份清单写死在代码里了。"自动生成"只保证与生成器的世界模型一致，不保证那个模型是完整的。现在关卡清单**直接从 `run_regression.sh` 解析**；生成器描述不了的关卡是硬报错，而不是渲染成一个破折号；契约测试把表格的行数与标签绑到 runner 上——其中一条是"给守卫再加个守卫"：删掉一个条目，断言生成器拒绝构建。

**4. 正则 lint 重新定位为"已知回归检测器"。** 五条新的改写从全绿的套件里走了过去——第五条是在给模型评估打分器写一条无关探针时冒出来的，这件事本身就是佐证：

```
The event history topic belongs on cleanup.policy=compact.       (KL023)
Page when consumer lag reaches ten thousand records.             (KL024)
Static membership guarantees rolling deployments will not
  rebalance the group.                                           (KL025)
Protobuf gives the highest throughput of the registry formats.   (KL026)
Set a partition key to preserve ordering — without one, records
  are spread round-robin over the partitions.                    (KL006)
```

五条现在都能触发。KL024 增加了"数字写成英文单词"的形式（`ten thousand` 和 `10000` 是同一个凭空来的常数）；KL023 增加了一条保持邻接约束的 "belongs on" 分支，同时不碰正确写法 *"keep the event log on `cleanup.policy=delete` and compact a separate snapshot topic"*；KL025 增加了 `guarantees … will not rebalance` 形式，并用定长负向后顾断言保证**反驳**这个说法的句子不会被自己判违规；KL026 增加了"不点名输家的最高级排序"形式；KL006 增加了代词回指形式（`key … without one … round-robin`），作用域限定在同一个小句内，跨句就够不着。

更要紧的是定位本身。linter 的 docstring、同义改写语料的 docstring、`COVERAGE.md` 的缺口表现在说的是同一句话：**报出问题是真的，沉默不是放行。**5 份文件 0 条 finding，只说明其中不含任何已知的错误写法，绝不能当作"文档在语义上是正确的"的证据来引用。

**5. SKILL.md 已经没有余量。** 它正好卡在 500 行，而门禁写的是 `<= 500`——把 skill-creator 的"under 500"当成了目标。现在 **423 行**（31.5 KB），门禁下调到 435。两块内容被移走，都没有删：正文里六个反例的代码块并入了另外十一个所在的 `references/consumer-anti-examples.md`（现在是连续的 AE-1…AE-17 目录，§7 保留索引）；§8 的三张分层清单——原本是 §5 清单的逐条复制——收成一张"分层 → 条目号"的映射表。那份副本本来就已经漂了：同一种情况，§5 写 PASS，§8 写 WARN。现在每个 §5 条目自带分层标注，契约测试断言标注与 §8 表格一致，且两者合起来正好覆盖全部十六条、不重不漏。

**6. 一处目录写错了症状。** `consumer-failure-modes.md` 把毒药消息的症状写成 "lag pinned at the same offset"，而正文说得是对的：**committed offset** 停止推进，lag 持续增长。目录已改成与正文一致。

收尾时对本轮新增的守卫做变异测试，又查出一条：把 linter 扣分那一行整段删掉，标定关卡照样**全绿**——因为所有诱饵单靠召回率就已经分开了。也就是说，号称"给打分器打分"的那道关卡，只验了打分器的一半。现在新增三条扣分探针，每条都把它所属 fixture 要求的概念说全，召回率钉死在 1.0，因此只有扣分那一路能让它失败；这条变异现在能被杀掉。

当前数字：**8 道关卡** · 26 条 lint 规则 · 127 条自检用例 · 34 项 mutation（每条规则都有覆盖）· 127 条同义改写探针 · 21 个 golden fixture · 295 个 pytest 用例 · 17 个反例 · SKILL.md 423 行。权威数字由脚本生成到 `scripts/tests/COVERAGE.md`，不手工维护。

**"8 道关卡全绿"仍然不代表什么。** 它代表：文档内部自洽、不含那 26 条规则编码的错误、并且模型评估的打分器能把正确评审和笃定的错误评审分开。它不代表带着这个技能的模型答得更好——那个数字目前不存在，而现在挡在这份报告和一次诚实测量之间的，只剩把 A/B 跑起来这一步。

---

## 8.9 第五轮评审——一个评分漏洞，外加四项评估局限

**1. 带 Critical 缺陷的设计仍可能被判 PASS。** §8.8 把四个检查项标成了 unscored，却没意识到"标出来"本身就把它变成了漏洞。`atomicity mechanism`（§5 第 8 项）是"审但不计分"，而 `KAFKA-015` 把"数据库写入放进 Kafka transaction"定为 **critical**；`sensitive data` 不计分，而 `KAFKA-018` 把"PII 落在无限保留的 compacted topic 上"定为 **standard**。两类缺陷都能被查出来、写进 §9，然后评分照样 PASS。够不着结论的 severity 就是装饰。

修法是按类改，不是逐条改——**unscored 这一层直接取消**。§5 每一项现在都有权重：第 8 项 → Critical，第 16 项（敏感数据）→ Standard，第 2 项（分区数）与第 17 项（归属）→ Hygiene。不适用的项走 N/A，诚实地缩小分母；没有任何一项靠"没有层级"退出计分。

写这条不变量测试的过程又暴露了同一个漏洞的第二个、更安静的版本：`KAFKA-014`（`group.protocol=consumer` 下的 assignor 配置）、`KAFKA-021`（静态成员过度承诺）、`KAFKA-020`（照抄 lag 阈值）severity 都是 **standard**，锚点却落在 Gate 1 的一行和 §4 的一条硬规则上——消费者组/rebalance 配置根本没有对应的检查项，所以同样没有任何评分项会为它们失败。§5.3 新增 **第 13 项：消费者组配置与所用协议自洽**（Standard），三个 fixture 重新锚到真实检查项上。现在分层是 Critical 4 · Standard 7 · Hygiene 6 = 全部 17 项。

这条不变量现在是双向的关卡：每个 critical/standard fixture 必须落到一个带层级的 §5 检查项上，且每个 §5 检查项都必须带层级。

**2. Quick Reference 里仍留着全局版本论断。** 它的收尾是"不知道 broker 版本和客户端库的结论都是猜测"——而四十行之下的逐项表说的是大部分检查项根本不需要版本。已改成把加载 matrix 的要求限定在**版本敏感**的项上，并有一条作用域限定在文件头部的契约测试挡住旧写法。

**3. `model_eval.py` 的四项局限，三项已修、一项如实写明。**

- *只跑 defect。* 语料只有 16 个缺陷 fixture、没有正确样本，这会奖励"什么都判有问题"的模型——量的是悲观程度，不是判断力。现在跑 **defect + good_practice**，召回率和误报率分开报。召回率对"误伤"是瞎的（把正确代码骂一顿，该提的概念一个不少），所以每个 good_practice fixture 声明它最容易招致的那种误判的标记，标定环节要求一条"过度告警"探针能触发它、而标准答案不能触发。
- *skilled arm 不加载 reference。* §3 规定**任何**配置结论都要加载 `version-client-matrix.md`，连 Lite 深度也是；只塞 SKILL.md 的那一组，量的是技能没有规定的工作流。新增 `--refs {none,matrix,all}`，默认 `matrix`；baseline 组不受该开关影响，并有测试断言这一点。
- *只存分数、不存回答。* JSON 现在保留原始回答（`--no-transcripts` 可关）。背后没有回答的分数，在打分器变了以后没法重新评，也没法拿来争辩。
- *oracle 出自项目自身。* `expected_feedback`、`coverage_rules` 和 lint 规则都出自写这个技能的同一批工作，所以高分的含义是"模型复现了本项目所相信的东西"，不是"模型是对的"。这一条从内部修不了，现在写进模块 docstring，而不是让读者自己意会。标定证明的是在**那套信念之内**能分开好坏，仅此而已。

**4. 修上面几条时顺带查出的一个 bug。** `ask()` 只要子进程往 stdout 打了字就照单评分，不看退出码。一个打出 usage 提示或半截回答然后 exit 1 的 runner，会被记成"一次糟糕的评审"——而低分恰恰是最会被当成模型行为去追查的那种结果。现在非零退出码一律算基础设施问题（退出 2），和空回答一样。

三条变异确认新守卫该红时会红：删掉误报检查、把退出码 bug 装回去、把 `matrix` 的 reference 集合清空，三条都被杀掉。

**5. 第 1 条的修复引入了 KL025 的一个误报。** 新检查项把边界说对了——"静态成员**只在**重启能在 `session.timeout.ms` 内完成时才避免 rebalance"——而规则把它判成了违规，因为它的豁免只放过**后置**的 only（`avoids a rebalance only if…`）。禁止正确句子的守卫是缺陷。已用后顾断言修好，并从两个位置各加一条探针。

当前数字：**8 道关卡** · 26 条 lint 规则 · 128 条自检用例 · 34 项 mutation · 128 条同义改写探针 · 21 个 golden fixture · 331 个 pytest 用例 · 17 个检查项（全部计分）· 17 个反例 · SKILL.md 424 行。

**状态，不加修饰地说。** 五轮评审的工程整改到此完成。它所服务的实证测量仍然没有跑过：没有对真实模型的 A/B，没有 trigger recall/precision，没有真实 broker 矩阵。今天所有的绿，说的都是文档本身、以及检查文档的那套工具。
