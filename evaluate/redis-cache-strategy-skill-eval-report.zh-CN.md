# redis-cache-strategy 技能评估报告

> **评估框架**: skill-creator A/B 实测对比法
> **评估日期**: 2026-04-18
> **评估对象**: `skills/redis-cache-strategy/`（Redis 缓存策略设计与审查技能）

---

Redis 缓存安全规范在基础模型中具有极高的训练覆盖率，本次评估发现基线质量已达 89.6%。技能的核心价值体现在两个维度：**框架引用一致性**（AE 编号交叉参照、Gate 显式分析）和**Token 效率**（三场景平均节省 49.7%，为所有已评估技能中最稳定的效率优势）。

---

## 1. Skill 概述

**核心组件**：

| 文件 | 行数 | 职责 |
|------|------|------|
| `SKILL.md` | 341 行 | 主框架：4 Gate、3 深度、14 项 Checklist、12 项 Scorecard、9 节输出合约 |
| `references/cache-patterns.md` | 211 行 | Standard/Deep：4 种写入模式（cache-aside/write-through/write-behind/dual-write），含代码示例 |
| `references/cache-failure-modes.md` | 260 行 | Deep：4 种失效模式防御（stampede/penetration/avalanche/hot key），含 Go 代码 |
| `references/cache-anti-examples.md` | 142 行 | 扩展反例 AE-7 至 AE-13 |

**技能核心安全规范**：
- AE-1: TTL=0（永久 key）→ 数据永不过期
- AE-2: Write-behind 无持久队列 → 进程崩溃数据丢失
- AE-3: 无 singleflight 的 cache-aside → 惊群打穿 DB
- AE-5: 无 TTL + 无 token 检查的分布式锁 → 死锁 + 锁盗取
- GUARDRAIL: 金融/审计关键数据**禁止**使用 write-behind 模式

---

## 2. 测试设计

### 2.1 场景定义

| # | 场景名称 | 业务背景 | 核心挑战 | 期望结果 |
|---|----------|----------|----------|----------|
| 1 | Cache-Aside 三项缺陷 | Redis 7.0, 50K QPS, 电商商品目录 | TTL=0 + 无 stampede 保护 + 无降级路径 | 识别 3 个 Critical，Scorecard 0/3 |
| 2 | 分布式锁 + Write-Behind | Redis 6.2 Sentinel, 5K 订单/分钟, 金融数据 | 锁无 TTL/无 token 检查 + write-behind fire-and-forget | 识别 GUARDRAIL 违反，推荐 write-through |
| 3 | 最小上下文（降级模式） | 版本/部署/一致性 SLA 全部未知 | 仅有代码片段，无架构背景 | Minimal 模式，consistency SLA 未定义 |

### 2.2 断言矩阵（24 项）

**场景 1 — Cache-Aside 缺陷（9 项）**

| ID | 断言 | With-Skill | Without-Skill |
|----|------|:----------:|:-------------:|
| A1 | 识别 `TTL=0`（immortal key）为 Critical 缺陷（AE-1） | PASS | PASS |
| A2 | 识别缺少 singleflight/stampede protection 为高风险 | PASS | PASS |
| A3 | 识别缺少 cache-down degradation path 为 Critical（无限流的隐式 DB fallback 不可接受） | PASS | PASS |
| A4 | 建议 TTL with jitter（±10–20%），防止雪崩同步过期 | PASS | PASS |
| A5 | 提供 singleflight 代码方案解决 stampede | PASS | PASS |
| A6 | 识别 eviction policy 未配置（默认 noeviction → 8GB 满后所有 SET 报错） | PASS | PASS |
| A7 | 原始代码 Scorecard: Critical **0/3**（TTL/一致性/降级全部 FAIL） | PASS | PASS |
| A8 | `§9.9` 使用规定 4 列表格（Area \| Reason \| Impact \| Follow-up） | PASS | PASS |
| A9 | 明确引用 Anti-example 编号（AE-1、AE-3 等）交叉参照 | PASS | **FAIL** |

**场景 1 小结**：With-Skill 9/9，Without-Skill 8/9（失分于 AE 编号引用缺失）

---

**场景 2 — 分布式锁 + Write-Behind（9 项）**

| ID | 断言 | With-Skill | Without-Skill |
|----|------|:----------:|:-------------:|
| B1 | 识别分布式锁 TTL=0 为死锁风险（持有者崩溃后锁永不释放） | PASS | PASS |
| B2 | 识别 DEL 未检查 token 为锁盗取风险（race window 内删除他人锁） | PASS | PASS |
| B3 | 提供 Lua CAS 安全释放脚本（原子 GET-compare-DEL） | PASS | PASS |
| B4 | 识别 write-behind fire-and-forget 为金融数据 GUARDRAIL 违反 | PASS | PASS |
| B5 | 推荐 write-through（DB first 同步写，cache 作为非关键可选写） | PASS | PASS |
| B6 | 原始代码 Scorecard: Critical **0/3**（一致性/TTL/降级全部 FAIL） | PASS | PASS |
| B7 | `§9.9` 包含 `SaveOrder` 幂等性风险（重试可能产生重复金融记录） | PASS | PASS |
| B8 | `§9.9` 使用规定 4 列表格（Area \| Reason \| Impact \| Follow-up） | PASS | PASS |
| B9 | Gate 框架显式分析（Gate 1–4 逐项 PROCEED/STOP 声明） | PASS | **FAIL** |

**场景 2 小结**：With-Skill 9/9，Without-Skill 8/9（失分于 Gate 显式分析缺失）

---

**场景 3 — 最小上下文降级模式（6 项）**

| ID | 断言 | With-Skill | Without-Skill |
|----|------|:----------:|:-------------:|
| C1 | 声明 Minimal/Degraded Mode + `Data basis: minimal` 标注 | PASS | PASS |
| C2 | `§9.9` 包含 "consistency SLA undefined" 作为 Critical 风险项 | PASS | PASS |
| C3 | `§9.9` 使用规定 4 列表格（Area \| Reason \| Impact \| Follow-up） | PASS | PASS |
| C4 | 识别 `redis.Nil`（cache miss）与 Redis 连接错误（err != nil）的混淆问题 | PASS | PASS |
| C5 | 不声称策略"一致"，明确定义 staleness window 未知 | PASS | PASS |
| C6 | `§9.x` 节编号使用规范 `§` 前缀格式（如 `§9.1 Context Gate`） | PASS | **PARTIAL** |

**场景 3 小结**：With-Skill 6/6，Without-Skill 5.5/6（PARTIAL: 无 § 前缀格式）

---

## 3. 通过率对比

### 3.1 总体断言通过率

| 配置 | PASS | PARTIAL | FAIL | 通过率（严格） |
|------|------|---------|------|------------|
| **With Skill** | **24/24** | 0 | 0 | **100%** |
| Without Skill | 21/24 | 1 | 2 | 87.5% + 4.2% partial |

**Delta：+10.4 percentage points（严格 PASS 口径）**

### 3.2 按场景通过率

| 场景 | With-Skill | Without-Skill | 失分项 |
|------|-----------|--------------|-------|
| S1 Cache-Aside | 9/9 (100%) | 8/9 (88.9%) | A9: AE 编号引用 |
| S2 Lock+Write-Behind | 9/9 (100%) | 8/9 (88.9%) | B9: Gate 框架分析 |
| S3 Minimal Context | 6/6 (100%) | 5.5/6 (91.7%) | C6: §9.x 节编号格式 |

**规律**：3 个失分项来自同一类别——**框架引用规范性**（AE 编号、Gate 声明、§ 前缀）。核心安全知识（TTL jitter、singleflight、Lua CAS、write-behind guardrail）两组均 100% 覆盖。这表明 Redis 缓存安全规范已深度训练进基础模型，技能价值体现在**引用可追溯性**和 **Token 效率**，而非知识传递。

---

## 4. 关键差异分析

### 4.1 With-Skill 专有行为

| 行为 | 出现场景 | 依据 |
|------|---------|------|
| Anti-example 编号交叉引用（AE-1、AE-3、AE-5） | S1、S2 | §7 Anti-Examples 框架 |
| Gate 1–4 显式 PROCEED/STOP 逐项声明 | S1、S2 | §2 Mandatory Gates |
| `§9.x` 规范节编号前缀 | S1、S2、S3 | §9 Output Contract |
| `§9.3` 使用规定列名（Component\|Pattern\|Risk\|Notes） | S1、S2 | §9.3 格式规范 |
| Data basis 必须在 Scorecard 后追加 | S1、S2、S3 | §8 Scorecard 合约 |

### 4.2 核心技术知识对比

所有关键 Redis 安全规范两组均正确识别：

| 检查点 | With-Skill | Without-Skill |
|--------|:----------:|:-------------:|
| TTL=0（immortal key）致命性 | PASS | PASS |
| Singleflight 解决 stampede | PASS | PASS |
| Eviction policy noeviction 危险 | PASS | PASS |
| Write-behind 金融数据禁用 GUARDRAIL | PASS | PASS |
| Lua CAS 分布式锁安全释放 | PASS | PASS |
| Penetration（null-value 缓存） | PASS | PASS |
| §9.9 Uncovered Risks 4 列表格 | PASS | PASS |

**结论**：Redis 缓存安全知识是基础模型训练覆盖最完整的领域之一。技能在**技术内容**上不产生额外价值，但在**框架一致性**和 **Token 效率**上有明确优势。

### 4.3 与同类技能基线对比

| 技能 | 基线通过率 | 有 Skill 通过率 | Delta |
|------|------------|---------------|-------|
| mysql-migration | 52% | 100% | +48 pp（知识注入为主） |
| pg-migration | 87% | 100% | +13 pp |
| mongo-migration | 87.5% | 100% | +12.5 pp |
| **redis-cache-strategy** | **89.6%** | **100%** | **+10.4 pp**（框架规范为主） |

**趋势**：随着领域知识越来越成熟，技能的 Delta 逐渐收窄，价值从"知识传递"转向"结构约束"。redis-cache-strategy 代表这一趋势的极端——技能几乎不提供新知识，但提供了 49.7% 的 Token 节省。

---

## 5. Token 效费比分析

### 5.1 Skill 上下文 Token 成本

| 组件 | 行数 | 估算 Token 数 | 加载时机 |
|------|------|-------------|----------|
| `SKILL.md` | 341 | ~4,400 | 每次 |
| `cache-patterns.md` | 211 | ~2,700 | Standard/Deep |
| `cache-failure-modes.md` | 260 | ~3,300 | Deep / stampede 信号 |

### 5.2 实际运行 Token 消耗

| 代理 | 场景 | Total Tokens | Tool Calls | 输出模式 |
|------|------|-------------|------------|---------|
| Without Skill | S1 | 36,546 | 3 | 探索式推理 + Web 搜索 |
| With Skill | S1 | **19,004** | 0 | 结构化框架输出 |
| Without Skill | S2 | 37,096 | 3 | 探索式推理 + Web 搜索 |
| With Skill | S2 | **18,712** | 0 | 结构化框架输出 |
| Without Skill | S3 | 36,028 | 3 | 探索式推理 + Web 搜索 |
| With Skill | S3 | **17,415** | 0 | 结构化框架输出 |

### 5.3 效费比计算

| 指标 | S1 | S2 | S3 | **均值** |
|------|----|----|----|---------|
| 无 Skill Token | 36,546 | 37,096 | 36,028 | 36,557 |
| 有 Skill Token | 19,004 | 18,712 | 17,415 | **18,377** |
| Token 节省 | **−48.0%** | **−49.6%** | **−51.7%** | **−49.7%** |
| 质量提升 | +11.1 pp | +11.1 pp | +8.3 pp | +10.4 pp |

**结构性发现**：三场景 Token 节省极为一致（±2%），无 S3 异常（对比 mongo-migration S3 异常 +15%）。原因：redis-cache-strategy 的 §3 Depth Selection 对 Minimal context 处理正确——未知规模**不**触发 Deep depth，保持 Standard depth + 保守假设，避免过度加载参考文件。

**无 Skill 组 Tool Calls 分析**：每场景 3 次工具调用（推测为 Web 搜索 Redis 文档/Go 代码示例），这不仅增加 Token 消耗，也引入网络依赖和不确定性。有 Skill 组将知识内嵌，零工具调用，响应更稳定。

---

## 6. 综合评分

### 6.1 分维度评分（5 分制）

| 维度 | With Skill | Without Skill | 差值 |
|------|:----------:|:-------------:|:----:|
| Critical 缺陷识别完整性 | 5.0 | 5.0 | 0.0 |
| Anti-Pattern 框架引用规范 | 5.0 | 3.0 | **+2.0** |
| 输出结构规范性（§9 合约） | 5.0 | 4.0 | +1.0 |
| 实现方案质量（代码/TTL/Lua） | 5.0 | 4.5 | +0.5 |
| 降级与监控设计 | 5.0 | 4.5 | +0.5 |
| 领域特定 Guardrail 执行 | 5.0 | 4.5 | +0.5 |

### 6.2 加权总分（满分 10 分）

| 维度 | 权重 | With-Skill | Without-Skill | 评分理由 |
|------|------|:----------:|:-------------:|---------|
| Critical 缺陷识别 | 25% | 10.0/10 | 10.0/10 | 两组均 100% 识别所有关键安全问题 |
| Anti-Pattern 框架引用 | 20% | 10.0/10 | 6.0/10 | 有 Skill 显式引用 AE-1/AE-3/AE-5；无 Skill 仅描述问题不引用编号 |
| 输出结构规范性 | 20% | 10.0/10 | 8.0/10 | §9 节结构两者均有；有 Skill 保证 §9.x 前缀、Gate 声明和规范列名 |
| 实现方案质量 | 15% | 10.0/10 | 9.0/10 | 两者均提供 Lua CAS/singleflight；有 Skill 更系统化（含 dual-write debounce） |
| 降级与监控设计 | 10% | 10.0/10 | 9.0/10 | 两者均有完整 §9.7/§9.8；有 Skill 更结构化（表格 vs 散文） |
| 领域 Guardrail 执行 | 10% | 10.0/10 | 9.0/10 | 两者均识别 write-behind GUARDRAIL；有 Skill 明确标注 GUARDRAIL VIOLATION |
| **加权总分** | **100%** | **10.00/10** | **8.45/10** | — |

---

## 7. 核心发现与建议

### 发现 1：redis-cache-strategy 是已评估技能中基线最强的

基线质量 89.6% 表明 Redis 缓存安全规范（singleflight、TTL jitter、Lua CAS、write-behind 禁忌）已成为基础模型的"内置知识"。这与 mysql-migration（52% 基线）形成鲜明对比——技能在该技能上的价值主要来自**框架约束**而非知识注入。

**对技能设计的启示**：对于知识成熟的领域，技能应更侧重输出结构规范化（§9 合约、AE 编号、Gate 框架），而非知识文档化。

### 发现 2：Token 效率是最一致的差异化优势（−49.7%）

三个场景均稳定节省约 50%，无异常场景（对比 mongo-migration S3 异常）。这源于：
- 有 Skill 组：框架指导下直接生成结构化输出，0 工具调用
- 无 Skill 组：探索式推理 + 3 次 Web 搜索，生成更多但重复的内容

对于频繁执行的 Redis cache review（如 CI/CD 中的 PR 审查），月度 100 次场景下 Token 节省约 50%，对应约 2× 的成本效率。

### 发现 3：S3 Minimal Context 无异常——技能 Depth 触发规则设计正确

redis-cache-strategy 在 Minimal context（版本/规模/SLA 未知）下正确选择 Standard depth 而非 Deep，避免了 mongo-migration 中因 Deep depth 触发导致的 S3 Token 超额。这表明 §3 Depth Selection 的保守触发规则设计合理。

### 发现 4：§9.9 表格格式已被基线广泛采用

与前几次评估相同，无 Skill 组同样自发使用 `| Area | Reason | Impact | Follow-up |` 4 列格式。这说明该格式已成为基础模型的默认输出模式，可能源于技能文档的训练数据覆盖。

**建议**：鉴于格式已广泛覆盖，技能的维护重点应转向**更难被基线正确执行的规则**：
1. 复杂场景下的 Pattern Selection Matrix（e.g., 混合读写比例的模式选择）
2. multi-service shared cache 的 isolation 设计
3. Redlock vs 单机锁的适用场景区分

---

## 8. 结论

**redis-cache-strategy 技能评定：生产就绪，推荐用于所有 Redis 缓存层设计与审查工作流。**

**核心价值点**：
1. **Token 效率第一**：三场景平均节省 49.7%，是已评估技能中最稳定的效率优势，适合高频 CI/PR 场景
2. **框架引用可追溯**：AE 编号、Gate 声明、`§9.x` 前缀确保每次审查可对照规范追溯
3. **Zero Web 搜索依赖**：知识内嵌使有 Skill 组完全不依赖外部工具，在网络受限或响应时间敏感场景下优势明显

**改进建议**：
1. 增加 multi-service shared cache 场景的 golden fixture（CACHE-015），覆盖租户隔离 + keyspace 分离
2. §7 Anti-Examples 补充 AE-14（Redis Cluster 下 Lua script 原子性失效），对应 cluster 部署的常见误区
3. 考虑在 §4 Degradation Modes 中明确说明：Minimal context 下不触发 Deep depth（当前隐式，建议显式化）

---

## 9. 整改轮次 —— 2026-08-10

> 上文 §1–§7 记录的是 2026-04-18 的 A/B 运行，**作为质量结论已被取代**：它们产
> 生于 9.1 所述评分缺陷被发现之前，而一次「发现了 Critical 缺陷仍可判 PASS」的
> 评测无法为它所测量的技能背书。保留它们仅作为历史基线。

### 9.1 真正要害的问题：评分卡无法对清单的发现采取行动

§5 列了 14 项检查，§8 评的是**另外** 14 项。两份清单已经漂移，三个 `critical`
golden fixture 只落在允许一项失败的 Standard 层：

| Fixture | 缺陷 | 被评在 | 后果 |
|---------|------|--------|------|
| CACHE-012 | 金融数据用写后异步落库，fire-and-forget goroutine | 「模式匹配业务场景」（Standard） | 评审发现并标为 Critical，最终仍判 PASS |
| CACHE-014 | 多租户键缺租户前缀，跨租户读取 | 「键命名规范」（Standard） | 授权绕过被当成命名瑕疵 |
| CACHE-017 | 无 fencing 的 correctness lock | 「分布式锁」（Standard） | 重复扣款被评为部分通过 |

§8 的层级也没有描述真实情况的词汇：没有 `N/A`，没有 `NOT SCOREABLE`，没有说明
`WARN` 是否计为通过，固定的 `/14` 分母逼你要么为一个根本不需要锁的系统判 FAIL，
要么捏造一个通过。

**处理方式。** §8 不再定义条目。§5 是唯一清单，条目带层级 ID（`C1–C9`、`S1–S7`、
`H1–H5`），§8 只规定这些 ID 如何计数。上述三个 fixture 现在分别映射到 `C6`、
`C7`、`C9`——全部 Critical，全部可阻断。评分词汇定义在条目所在处：PASS / WARN /
FAIL / N/A / NOT SCOREABLE，分母动态，`WARN` 明确判为 Critical 层不通过，并新增
第三种结论 **INCOMPLETE**，专门收容此前无处安放的情形：某个 Critical 条目无法评
估。「我们没法检查」永远不等于通过。

三道机制把它钉住，防止悄悄漂回去：

- `RC010`（lint）—— §5 的 ID 必须逐层连续，且被 §8 声明的区间恰好覆盖；§8 不得
  再出现自己的清单。
- `RC014`（lint）—— §5 必须定义全部五种判定，并写明沉默等于 FAIL 而非 N/A。
- `TestScorecardReachability`（pytest）—— 每个 fixture 声明它违反的 §5 ID，
  `critical` fixture 若最高层级低于 Critical 即测试失败。`M15` 把 CACHE-014 改回
  `H1`，被杀死。

### 9.2 版本模型

Gate 1 此前只给 `6.x / 7.x`，未知时默认 **6.0**。截至 2026-08，当前发行版是
**8.10**（2026-07-29），8.0 / 8.2 / 8.4 / 8.6 / 8.8 均已 GA，6.2 / 7.2 / 7.4 仍在
发补丁。那个过期默认值在两个方向上都是错的——既凭空造出已不存在的限制，又遮蔽了
如今更优的原语。

版本现在按**结论**逐条设卡，而非全局设卡，并列出七条具体结论及其分界点。
`RC015`（lint）要求每个受版本约束的特性名在出现处必须带版本。
`references/redis-version-matrix.md` 记录每个版本的变化、版本未知时该走哪条分支，
以及每条断言的核对方式。

全部版本事实取自一手来源——`src/commands/*.json`（`since` 字段，以及 `SET` 的
`history` 数组）、`src/config.c`（`maxmemory_policy_enum[]`、listpack/ziplist 配置
别名）和 GitHub release 正文，而非凭记忆。其中四条直接改写本技能的建议：
`DELEX … IFEQ` / `SET … IFEQ`（8.4）取代 Lua CAS 释放锁，并支持带版本守卫的缓存
写入；`HOTKEYS`（8.6）取代客户端侧热键估算；内置 cuckoo filter `CF.*`（8.0）让穿
透防护的过滤器可删除；compact hashes（8.10）改变 Hash 与 String 的内存权衡。

### 9.3 技术修正

| 部位 | 原先 | 现在 |
|------|------|------|
| write-through 读路径 | 「always fresh since writes update cache」——与下方三段处解释其为何不成立的章节自相矛盾 | 顺利路径上是 read-your-writes，矛盾在源头消除；`RC017` 对任何未在**同一行**限定的绝对新鲜度断言触发 |
| Cluster fencing 示例 | 锁键与 fence 计数器同处一个 Lua 脚本，落在不同 hash slot | 通过 `fenceKeysFor` 共用 hash tag，并补充 fence 计数器的持久性与 failover 单调性失效模式及三种处理方式 |
| 延迟双删 | 固定 100ms–1s，「延迟任务，或 goroutine 里 sleep」 | 由 p99.9 DB 读 + 回填 + 队列延迟推导；进程内 sleep 被明确否定为与 AE-2 同类缺陷；`RC016` 强制执行 |
| reference 导航 | 四份 reference 均无目录（failure-modes 长达 440 行） | 五份全部有目录，按 GitHub 锚点算法与真实标题逐条断言——目录漂移会被 `M24` 杀死 |

### 9.4 修复过程中发现的门禁缺陷

以下两条不在评审意见内，但值得记录，因为它们都在让测试套件显得比实际更有把握：

1. **沙箱环境下 Go 门恒返回 1。** 不可写的构建缓存产生
   `go: failed to trim cache: … operation not permitted`，而所有包其实都编译成功
   了。该门报 FAIL——更糟的是，变异扫描把**每一个**变异都记成「被 go 杀死」，因为
   无论变异做了什么 go 门都返回 1。此前的「12/12 killed」因此有一部分是假象。现在
   该门先编译一个已知正确的包作为正向对照，必要时回退到私有 `GOCACHE`，并把「非零
   退出但无编译诊断」判为 INCOMPLETE（退出码 3）而不是判某个片段有问题。修好之后，
   立刻暴露出一个变异（`M20`）实际存活。
2. **`test_verdict_format` 是空断言。** `assert "X/12" in SKILL_MD or "PASS/FAIL"
   in SKILL_MD` 靠后半句恒真通过，于是 `X/12` 那半句跨越两次重新编号一直失效却从
   未变红。现在每条评分卡断言都先解析结构再校验取值。

`COVERAGE.md` 自身也在少报：门禁表硬编码 6 行而 runner 实跑 7 个门；Go 门覆盖文件
列表用的正则在第一个 `]` 处就停了，于是声称只覆盖 `SKILL.md`，而该门一直在扫描全
部 reference。两者现在都是推导得出——门禁表从 `run_regression.sh` 解析，文件列表从
门禁模块导入。

### 9.5 实证闭环——测了什么，没测什么

评审最有力的一点是：自动化验证只证明了**文档**自洽，从未观察过模型。现已建立两套
测量装置：

- **`model_eval.py`** —— 在 15 个 defect + good_practice fixture 上做 A/B：arm A
  只有代码，arm B 追加 SKILL.md 与 §10 规定加载的 reference。评分器是确定性的，绝
  不用 LLM 评判，打分五个显式轴：概念召回、§5 条目 ID 引用、判定正确性、对正确代码
  的误报、以及复述技能已判定为错误的说法（按分句判定，因此「引用谬误以驳斥它」不
  扣分）。
- **`trigger_eval.py`** —— 在 15 条正例、12 条负例上测路由召回率与精确率；负例都是
  真实的 Redis 问题，复用 description 的词汇，但落在 §1 与 Gate 2 明确外派的领域。

两者离线均可自检，且这两项自检就是回归门 6 和 7。`--calibrate` 跑 60 个轴探针：对
每个 fixture、每个适用的轴，构造一个只应移动**该轴**的诱饵响应。首次运行即抓出两个
真实的评分器缺陷——`items` 轴因回退到标题关键词而沦为 `recall` 的副本；误报轴因共用
`Verdict: FAIL` 探针而与判定轴重叠。两者均已修复：各轴联动的评分器会在某个机制被删
除后仍报告健康。

**尚未测量的部分，明说：** A/B 运行本身没有执行。本环境中嵌套 CLI 未登录，两套装置
均以退出码 3（INCOMPLETE）终止并打印原因。此处已验证的是装置本身——参数解析、经
stdin 投递 prompt（走 argv 失败：变参的 `--disallowed-tools` 吞掉了 prompt，且 arm B
的 prompt 有数十 KB）、runner 预检、退出码 3 路径，以及已校准的评分器。
**A/B 结果尚未取得，本报告中任何评分都不应被理解为包含了它。**

### 9.6 本轮之后的状态

| | 之前 | 之后 |
|---|------|------|
| 回归门 | 7 | 9 |
| Lint 规则 | 13 | 17 |
| 变异 | 12（且 go 门损坏虚高了击杀数） | 24，全部被预期的门杀死 |
| 收集到的测试 | 232 | 291 |
| 参与评分的检查项 | §5 有 14 项，§8 是另外 14 项 | 21 项，单一清单，带层级标签 |
| 判定 | PASS / FAIL | PASS / FAIL / INCOMPLETE，另有 N/A 与 NOT SCOREABLE 及动态分母 |
| 覆盖的 Redis 版本 | 6.x / 7.x，默认 6.0 | 6.2 → 8.10，按结论设卡，无默认值 |
| Reference | 4 份，无目录 | 5 份，全部带被断言的目录 |
| SKILL.md | 389 行 | 439 行（预算由 420 提到 440，代价是把 AE-1…AE-6 移入 reference 并删除 §8 的重复清单） |

按优先级尚待完成：用已登录的模型跑通 A/B 与触发评测并把数字记入本节；为九个尚无
fixture 的 §5 条目补充用例（`C1`、`S1`、`S5`、`S6`、`H1`–`H5`——该列表由
`COVERAGE.md §4` 推导，非手工维护）；以及用真实的 7.2 / 7.4 / 8.10 服务器验证版本矩
阵，而不仅仅依据源码树。

---

## 10. 整改轮次 2 —— 2026-08-10（同日，第二次评审）

第二轮评审发现五个问题。其中三个出在当天早些时候刚加的机制里——这恰恰是这次发现
最有价值的地方：新门禁正是"未挣得的绿"最容易出现的位置。

### 10.1 变异扫描仍可能报出它并未挣得的击杀数

两个漏洞，都关于**数字的可信度**而非变异本身：

- **没有 baseline 要求。** 扫描只在 go 门返回 3 时拒绝运行。若任一门在未变异的树上
  已经是红的，那么每个变异都会被这同一个失败的门"杀死"，而扫描照样打印满分。现在
  三个门必须全部返回 0 才会施加第一个变异；返回 3 判 INCOMPLETE，返回 1 则明确报错
  并停止。
- **击杀归属只是提示。** 被非声明门捕获的变异只打印 `(expected lint)` 却仍计为
  killed——于是一条已死的 lint 规则，只要它的变异碰巧弄坏了构建，就永远不会暴露。
  现在归属不符即判 `MISKILLED` 并使扫描失败。

两者都做了探测验证：弄红 baseline 后扫描拒绝运行且不打印任何计数；把某个变异的预期
门改错会产生 `MISKILLED M21 [killed by lint, expected go]` 并以退出码 1 结束。

### 10.2 Go 正向对照没有覆盖真正失败的那条路径

探针编译的是无外部依赖的包，而它要防的故障发生在模块解析阶段——于是探针可以通过，
真正的构建却因同一个环境原因失败。更关键的是，Go 的缓存 trim 是**周期性**的，不是每
次调用都做：它把上次尝试记在 `trim.txt` 里，隔一段时间才重试。现在连跑三次旧探针全
部返回 0，说明那个条件式回退只是偶尔触发。**偶发的回退比没有回退更糟**，因为它产生
的 INCOMPLETE 无法复现。

按病因而非症状修复：该门现在**无条件**使用私有且持久的 `GOCACHE`（路径固定，因此保
持热态——冷启 7.5s，热启 0.5s），探针改为 import `github.com/redis/go-redis/v9` 并执
行 `go mod tidy`，从而覆盖模块解析。`GOMODCACHE` 刻意保持共享——需要写权限的是构建缓
存的 trim 步骤。

### 10.3 `OVERWRITTEN` 被放在了错误的可靠性层级——这是轮次 1 引入的真实错误

§5 C2 把 keyspace `OVERWRITTEN`（8.2+）与 CDC 并列为等价的事件驱动失效机制。它们并不
等价，Redis 官方文档在两点上都写得很明确：

- Pub/Sub 是 *fire and forget*——"if your Pub/Sub client disconnects, and reconnects
  later, all the events delivered during the time the client was disconnected are
  lost."即失效事件会无声且无上限地丢失。
- 在集群中，"every node … generates events about its own subset of the keyspace"，
  且这些通知"**are not** broadcasted to all nodes"——监听方必须订阅每个节点，而重新
  分片会改变归属。

第三个问题属于结构性而非文档记载：该事件表示某个 *Redis 键*变了，不是某条*数据库行*
变了。当数据库已提交、失败的恰恰是缓存写入那一步时，根本不会产生任何事件——这正是
C3 存在的那个场景。

C2 现在要求一个**权威**机制（TTL、写时显式失效，或持久事件流：CDC / outbox），并写明
keyspace 通知不计入其中，同时点明它的正当用途——带 TTL 兜底的尽力而为 L2→L1 失效。
`RC018` 会在 keyspace 通知出现在持久机制附近却没有 fire-and-forget / best-effort 限定
时触发；`M26` 把 C2 改回那句有缺陷的原文，被杀死。

### 10.4 Gate 1 的正文与 Gate 1 自己的表格矛盾

轮次 1 已经把版本改为不可默认、`maxmemory` 改为必须询问、deployment mode 在锁与多键
脚本下涉及正确性，但那段正文仍写着"其他五项都有默认值，猜错只影响调优"。已修正：只
有读写比与峰值 QPS 会退化为调优问题，其余三项各自点名了默认不安全的原因。

### 10.5 缺失的 A/B 结果现在是被强制的，不是被承诺的

运行本身仍未发生——嵌套 CLI 未登录，两套装置均以退出码 3（INCOMPLETE）终止并打印原
因。变化在于：这个缺口不再由一句任何人都能删掉的话来守。
`TestEvalResultsAreNotClaimedWithoutData` 把断言与证据双向绑定：

- 任一语言的报告中出现结果形态的数字，而磁盘上没有
  `model_eval_last_run.json` / `trigger_eval_last_run.json`，**测试失败**；
- 一旦产物存在，报告若仍不给数字，**测试失败**（报告落后于证据）；
- 两个产物都不存在时，两份报告都必须写明运行尚未发生。

三条均已探测验证，包括伪造数字的场景。这并不能替代测量本身——它保证的是报告无法脱离
测量的实际结果而漂移。

### 10.6 轮次 2 之后的状态

| | 轮次 1 之后 | 轮次 2 之后 |
|---|---|---|
| Lint 规则 | 17 | 18（`RC018`） |
| 变异 | 24 | 25，且全部**由所声明的门**杀死 |
| 收集到的测试 | 291 | 294（2 项 skip：eval 产物尚不存在） |
| 变异扫描可信度 | 只有击杀计数 | 要求 baseline 全绿；错门击杀判失败 |
| Go 门 | 回退时才用私有 `GOCACHE`，探针无依赖 | 始终使用私有 `GOCACHE`，探针解析真实模块 |
| Keyspace 通知 | 与 CDC 并列 | 独立层级，由 `RC018` 把守 |

仍然开放、未加掩饰：A/B 与触发评测的真实运行、九个尚无 fixture 的 §5 条目，以及用真实
7.2 / 7.4 / 8.10 服务器验证版本矩阵。
