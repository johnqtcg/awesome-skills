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
