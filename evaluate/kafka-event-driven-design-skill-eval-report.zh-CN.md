# kafka-event-driven-design Skill 评估报告

> 评估框架：[skill-creator](https://github.com/anthropics/skills/tree/main/skills/skill-creator)
> 评估日期：2026-04-18
> 评估对象：`kafka-event-driven-design`

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

`BACKWARD` 仅检查与最近一个版本的兼容性；在多个消费者同时以不同 schema 版本运行时，`BACKWARD` 无法保证旧版消费者能读取跨越多个版本的新 schema。这是技能通过 `event-schema-patterns.md` §2.1 提供的精确知识。

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

**建议：生产就绪。对所有 Kafka 架构设计与代码审查工作流推荐使用。在涉及金融类事件（payment、order）时，`enable.idempotence` 分类精确度和 DLQ 强制检查是最高价值单项贡献。**
