# mongo-migration 技能评估报告

> **评估框架**: skill-creator A/B 实测对比法
> **评估日期**: 2026-04-18
> **评估对象**: `skills/mongo-migration/`（MongoDB 4.4–7.0+ 迁移安全审查技能）

---

MongoDB 迁移安全审查场景专业性较强，基础 Claude 模型在核心缺陷识别上表现出色，但在输出结构规范性与 Token 效率上存在可测量差距。A/B 测试设计了 3 个场景共 24 条断言，覆盖技能的三个核心工作模式。

---

## 1. Skill 概述

**核心组件**：

| 文件 | 行数 | 职责 |
|------|------|------|
| `SKILL.md` | 321 行 | 主框架：4 个 Gate、3 个深度级别、12 项 Scorecard、9 节输出合约 |
| `references/mongo-ddl-lock-matrix.md` | ~150 行 | Standard/Deep 深度加载：版本 × 锁行为矩阵 |
| `references/large-collection-migration.md` | ~180 行 | Deep 深度加载：_id-range 批量、字段类型迁移 6 步、滚动索引构建 |
| `references/migration-anti-examples.md` | ~100 行 | 扩展反例 AE-7 至 AE-13 |

**覆盖的 MongoDB 核心安全规范**：
- `_id`-range 分批更新（非无界 updateMany）
- Write concern 显式设置（w:"majority"）
- Validator 渐进模式（moderate → strict，非直接 strict）
- 字段类型迁移新字段模式（amount_v2 + 双读 + 回填 + 清理）
- 滚动索引构建（>50M docs）

---

## 2. 测试设计

### 2.1 场景定义

| # | 场景名称 | 集合规模 | 核心挑战 | 预期结果 |
|---|----------|----------|----------|----------|
| 1 | 索引安全 + Validator 渐进 | 15M docs, 18 GB | 无界 updateMany、无重复检查的 unique index、strict validator 早于回填 | 识别 3 个 Critical 缺陷，提供 _id-range 批量方案 |
| 2 | 大集合字段类型迁移 | 8M docs, 12 GB | 原地类型覆写（不可逆）、无 write concern、无 _id 分批 | 推荐 amount_v2 新字段模式，Scorecard 0/12 |
| 3 | 降级模式（无上下文） | 未知 | 版本/规模/部署类型全部未知 | 进入 Minimal 模式，保守假设全列出，Data basis 标注 |

### 2.2 断言矩阵（24 项）

**场景 1 — 索引安全 + Write Concern（9 项）**

| ID | 断言 | With-Skill | Without-Skill |
|----|------|:----------:|:-------------:|
| A1 | 识别 `updateMany({}, ...)` 无 `_id` 分批为 WiredTiger ticket 耗尽风险 | PASS | PASS |
| A2 | 识别 `createIndex({unique:true})` 前缺少重复数据预检查 | PASS | PASS |
| A3 | 识别 `validationLevel:"strict"` 在回填前直接启用为 UNSAFE | PASS | PASS |
| A4 | 建议 `validationLevel` 采用 `"moderate"` → `"strict"` 渐进模式 | PASS | PASS |
| A5 | 所有操作明确设置 `w:"majority"` write concern，并标注为 Critical 缺失 | PASS | PASS |
| A6 | 提供 `_id`-range 分批回填脚本（含 sleep 节流） | PASS | PASS |
| A7 | 原始脚本 Scorecard：Critical **0/3**（lock_timeout/write concern/rollback 全部缺失） | PASS | PASS |
| A8 | `§9.9` 包含 email 字段存在性、null 值处理、oplog 窗口等 ≥5 条风险 | PASS | PASS |
| A9 | `§9.9` 使用规定表格格式（Area \| Reason \| Impact \| Follow-up） | PASS | **FAIL** |

**场景 1 小结**：With-Skill 9/9，Without-Skill 8/9（失分于 §9.9 表格格式）

---

**场景 2 — 大集合字段类型迁移（9 项）**

| ID | 断言 | With-Skill | Without-Skill |
|----|------|:----------:|:-------------:|
| B1 | 识别无界 `updateMany` 为 Critical 缺陷（WiredTiger write ticket 耗尽） | PASS | PASS |
| B2 | 识别原地字段类型覆写为 UNSAFE（不可逆 + 旧代码立即失效） | PASS | PASS |
| B3 | 推荐 `amount_v2` 新字段 + 双读 + 回填 + 验证器 + 清理（6 步模式） | PASS | PASS |
| B4 | 在回滚方案中明确标注 Phase 5（`$unset` 旧字段）为 **irreversible**，需备份 | PASS | PASS |
| B5 | 将 write concern 从 `w:1` 升级至 `w:"majority"` 作为必须项 | PASS | PASS |
| B6 | 提供 `_id`-range 批量迁移脚本（含幂等过滤 + sleep 节流） | PASS | PASS |
| B7 | 原始脚本 Scorecard：**0/12**（所有 Critical/Standard/Hygiene 全部 FAIL） | PASS | PASS |
| B8 | 识别 `validationLevel:"strict"` 在回填前启用为 UNSAFE（AE-3） | PASS | PASS |
| B9 | `§9.9` 使用规定表格格式（Area \| Reason \| Impact \| Follow-up） | PASS | **FAIL** |

**场景 2 小结**：With-Skill 9/9，Without-Skill 8/9（失分于 §9.9 表格格式）

---

**场景 3 — 降级模式（无上下文）（6 项）**

| ID | 断言 | With-Skill | Without-Skill |
|----|------|:----------:|:-------------:|
| C1 | 声明 Minimal/Degraded Mode，`Data basis: minimal` 标注 | PASS | PASS |
| C2 | 所有风险评估带条件假设，不作无条件"安全"声明 | PASS | PASS |
| C3 | `§9.9` 使用规定表格格式，覆盖 ≥8 条已知未知量 | PASS | **FAIL** |
| C4 | 识别 MongoDB 版本对索引构建方法的影响（<4.2 vs 4.2+） | PASS | PASS |
| C5 | 建议先运行 `estimatedDocumentCount()` 确定集合规模 | PASS | PASS |
| C6 | 建议以 `{device_type: {$exists: false}}` 为幂等过滤条件 | PASS | PASS |

**场景 3 小结**：With-Skill 6/6，Without-Skill 5/6（失分于 §9.9 表格格式）

---

## 3. 通过率对比

### 3.1 总体断言通过率

| 配置 | PASS | FAIL | 通过率 |
|------|------|------|--------|
| **With Skill** | **24/24** | 0 | **100%** |
| Without Skill | 21/24 | 3 | 87.5% |

**Delta：+12.5 percentage points**

### 3.2 按场景通过率

| 场景 | With-Skill | Without-Skill | 差距 |
|------|-----------|--------------|------|
| S1 索引安全 | 9/9 (100%) | 8/9 (88.9%) | A9 §9.9 格式 |
| S2 类型迁移 | 9/9 (100%) | 8/9 (88.9%) | B9 §9.9 格式 |
| S3 降级模式 | 6/6 (100%) | 5/6 (83.3%) | C3 §9.9 格式 |

**规律**：3 个失分项全部来自同一根因——§9.9 Uncovered Risks 输出格式。无 Skill 组使用编号列表或散文段落；有 Skill 组使用规定的 4 列表格（Area \| Reason \| Impact \| Follow-up）。这是技能输出合约（§9 Output Contract）对格式的强制约束，而非内容知识差异。

---

## 4. 关键差异分析

### 4.1 With-Skill 专有行为

| 行为 | 依据 |
|------|------|
| §9.9 以表格格式呈现（Area\|Reason\|Impact\|Follow-up） | §9 Output Contract 强制规定 |
| 明确引用 Anti-example 编号（AE-2、AE-3、AE-4） | §7 Anti-Examples 交叉参照 |
| Gate-by-Gate 显式分析（Gate 1–4 逐项标注） | §2 Mandatory Gates 框架 |
| `Data basis:` 标注（full/degraded/minimal/planning） | §8 Scorecard 必须字段 |
| Scorecard 格式为 `X/12 — Critical Y/3, Standard Z/5, Hygiene W/4` | §8 精确格式要求 |

### 4.2 核心知识对比

| 检查点 | With-Skill | Without-Skill |
|--------|-----------|--------------|
| WiredTiger ticket 耗尽识别 | PASS | PASS |
| `_id`-range 分批方案 | PASS | PASS |
| amount_v2 新字段模式 | PASS | PASS |
| moderate → strict 渐进 | PASS | PASS |
| irreversible 分类（$unset 阶段） | PASS | PASS |

**结论**：MongoDB 迁移核心安全知识（WiredTiger、_id-range、validator 渐进）已深度训练进基础模型。技能的价值集中在**结构强制性**，而非知识传递。

### 4.3 S3 异常：有 Skill 组 Token 更多

场景 3（降级模式）出现反转：有 Skill 组（36,706 tokens，3 次工具调用）> 无 Skill 组（31,986 tokens，2 次工具调用）。

**原因**：SKILL.md §3 规定"未知集合规模 → 假设 Large → Deep depth → 加载两个参考文件"。有 Skill 组遵循此规则加载了 `large-collection-migration.md` 和 `mongo-ddl-lock-matrix.md`，产生额外输入 token 和工具调用。无 Skill 组保持在 Standard depth 水平，信息更精简。

**影响**：这是技能设计的保守性体现（宁可多加载也不漏判），但在完全无上下文场景下会增加成本。

---

## 5. Token 效费比分析

### 5.1 Skill 上下文 Token 成本

| 组件 | 行数 | 估算 Token 数 | 加载时机 |
|------|------|-------------|----------|
| `SKILL.md` | 321 | ~4,200 | 每次 |
| `mongo-ddl-lock-matrix.md` | ~150 | ~2,000 | Standard/Deep |
| `large-collection-migration.md` | ~180 | ~2,400 | Deep / 大集合 |

### 5.2 实际运行 Token 消耗

| 代理 | 场景 | Total Tokens | Tool Calls | 模式 |
|------|------|-------------|------------|------|
| Without Skill | S1 | 36,844 | 3 | 无 Skill |
| With Skill | S1 | **19,574** | 0 | 有 Skill |
| Without Skill | S2 | 37,583 | 3 | 无 Skill |
| With Skill | S2 | **19,374** | 0 | 有 Skill |
| Without Skill | S3 | 31,986 | 2 | 无 Skill |
| With Skill | S3 | 36,706 | 3 | 有 Skill（异常：加载参考文件） |

### 5.3 效费比计算

| 指标 | S1 | S2 | S3（异常）| 加权均值 |
|------|----|----|----|---------|
| 无 Skill Token | 36,844 | 37,583 | 31,986 | 35,471 |
| 有 Skill Token | 19,574 | 19,374 | 36,706 | 25,218 |
| Token 变化 | **−46.9%** | **−48.5%** | +14.8% | **−28.9%** |
| 质量提升 | +11.1 pp | +11.1 pp | +16.7 pp | +12.5 pp |

**S1/S2 效费比最优**：在有充足上下文时（版本、规模已知），有 Skill 节省近 50% Token，同时质量略优。Token 节省源于：结构化输出替代探索性推理（无 Skill 组先搜索再整合）、0 额外工具调用。

**S3 负效比区间**：当上下文严重缺失时，技能框架倾向于保守性深度触发（Deep + 加载所有参考），反而增加 Token 消耗。对比 pg-migration（S3 相同情况无此异常），说明 mongo-migration 的 Deep 触发条件在 Minimal 上下文下过于激进。这是一个**可改进点**（见 §7）。

---

## 6. 综合评分

### 6.1 分维度评分（5 分制）

| 维度 | With Skill | Without Skill | 差值 |
|------|:----------:|:-------------:|:----:|
| Critical 缺陷识别完整性 | 5.0 | 4.8 | +0.2 |
| Write Safety 强制执行 | 5.0 | 4.5 | +0.5 |
| 回滚方案分类准确性 | 5.0 | 4.5 | +0.5 |
| 输出结构规范性（§9 格式合规） | 5.0 | 3.5 | **+1.5** |
| 迁移脚本质量（_id-range、幂等性） | 5.0 | 4.5 | +0.5 |
| 降级模式处理 | 5.0 | 4.0 | +1.0 |

### 6.2 加权总分（满分 10 分）

| 维度 | 权重 | With-Skill 得分 | Without-Skill 得分 | 理由 |
|------|------|:--------------:|:-----------------:|------|
| Critical 缺陷识别 | 25% | 10.0/10 | 9.5/10 | 两者均精准识别 3 个 Critical 缺陷；无 Skill 组仅在 AE 交叉参照上略弱 |
| Write Safety 强制 | 20% | 10.0/10 | 9.0/10 | 两者均要求 w:majority；有 Skill 组将其标注为 Critical 层强制项 |
| 回滚方案分类 | 15% | 10.0/10 | 9.0/10 | 两者均识别 irreversible 阶段；有 Skill 组用三分类框架更系统 |
| 输出结构规范性 | 20% | 10.0/10 | 7.0/10 | §9.9 表格格式：有 Skill 100% 合规；无 Skill 100% 不合规 |
| 迁移脚本质量 | 10% | 10.0/10 | 9.0/10 | 两者均提供 _id-range 脚本；有 Skill 含幂等过滤和检查点 |
| 降级模式处理 | 10% | 10.0/10 | 8.0/10 | 有 Skill 组明确 Data basis 标注和 Gate 框架；无 Skill 同样进入保守模式但结构松散 |
| **加权总分** | **100%** | **10.00/10** | **8.77/10** | — |

---

## 7. 核心发现与改进建议

### 发现 1：mongo-migration 基线接近 pg-migration，同为"强基线"技能

| 技能 | 基线通过率 | 有 Skill 通过率 | Delta |
|------|------------|---------------|-------|
| mysql-migration | 52% | 100% | +48 pp |
| pg-migration | 87% | 100% | +13 pp |
| **mongo-migration** | **87.5%** | **100%** | **+12.5 pp** |

MongoDB 迁移安全规范（WiredTiger、_id-range、validator 渐进）已被广泛训练进基础模型，基线质量相当强。技能价值集中在格式强制性（§9.9 表格、AE 交叉参照）而非知识注入。

### 发现 2：§9.9 格式是最一致的差异化来源

在 3 个场景中，无 Skill 组在内容上和有 Skill 组高度重叠，唯一一致的失分来自 §9.9 输出格式。无 Skill 组使用的散文/编号列表：
- 难以在 CI/CD 流水线中机器解析
- 缺少 `Impact` 和 `Follow-up` 维度，不利于团队后续追踪

有 Skill 组的 4 列表格直接可复制为 JIRA/Linear ticket 描述。

### 发现 3：S3（降级模式）技能过于激进地触发 Deep depth

SKILL.md 规定"未知集合规模 → 保守假设为 Large → Deep depth → 加载所有参考文件"，导致在 Minimal 上下文下产生 ~14.8% 额外 Token。**改进建议**：在 §3 Depth Selection 中增加一条规则：

> 若上下文为 Minimal（仅有脚本，无规模/版本信息），在触发 Deep depth 前先询问用户确认集合规模，或保持在 Degraded 模式下使用 Standard depth，避免在信息缺失时过度消耗。

### 发现 4：Token 效率在有上下文场景下显著优于无上下文

| 场景类型 | Token 节省 |
|----------|-----------|
| 有充足上下文（S1, S2） | −46% ~ −49% |
| 无上下文（S3） | +15%（负效比） |

建议在迁移审查工作流中优先收集 MongoDB 版本和集合规模，再调用技能——这能最大化 Token 效率。

---

## 8. 结论

**mongo-migration 技能评定：生产就绪，强烈推荐用于所有 MongoDB 迁移审查场景。**

**核心价值点**：
1. **格式强制性**：§9.9 Uncovered Risks 的 4 列表格格式让风险项可追踪、可机器解析，无 Skill 组 100% 不满足此格式
2. **评估框架一致性**：Gate 分析、AE 交叉参照、Data basis 标注确保每次审查可重复、可比较
3. **有上下文时 Token 高效**：S1/S2 节省 47% Token，来源于结构化输出替代探索性推理

**改进建议**：
1. §3 Depth Selection 增加 Minimal 上下文下避免 Deep 过度触发的规则
2. §9 Output Contract 增加 golang-migrate / mongomigrate 等框架的事务包裹行为说明（对应 pg-migration 的 golang-migrate 注意事项）
3. 考虑增加第 4 个测试场景覆盖 reshardCollection（shard key 迁移），这是 MongoDB 5.0+ 最复杂的运维操作
