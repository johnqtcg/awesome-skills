# load-test Skill 评估报告

> 评估框架: [skill-creator](https://github.com/anthropics/skills/tree/main/skills/skill-creator)
> 评估日期: 2026-04-18
> 评估对象: `load-test`

---

`load-test` 是一个专注于 HTTP/gRPC 服务性能负载测试的专项 skill，涵盖 Write / Review / Analyze 三种工作模式，4 级强制门控（Context Collection → SLO-First → Scope Classification → Output Completeness），以及与 k6 / vegeta / wrk 三种工具的深度集成。评估横跨三个场景（Write 模式生成 k6 脚本 / Review 模式诊断缺陷脚本 / Analyze 模式给出 SLO 裁决），共 24 项断言，With-Skill 全部通过（24/24，100%），Without-Skill 通过率 75%（18/24）；其中 S1 基线存在工具调用污染（代理意外加载了 skill 相关文件），去除后核心差距约为 **+40pp**（S2+S3 清洁场景）。三个最突出的差距：第一，Review 模式下 With-Skill 将每个缺陷系统映射至 AE-x 编号并输出三层 Scorecard 判定，Without-Skill 给出合理建议但无规则名称映射、无 Scorecard；第二，§9.9 Uncovered Risks 在 Without-Skill 两个无污染场景均缺失（0/2），而 With-Skill 三个场景均包含（3/3，最少 5 条）；第三，Analyze 模式下 Without-Skill 的实质性分析质量与 With-Skill 接近（6/7），真正差距在输出完整性而非分析深度。

---

## 1. Skill 概述

`load-test` 定义了 4 条 Mandatory Gates（Context → SLO-First → Scope → Output Completeness）、3 级 Depth 选择（Lite / Standard / Deep）、5 种 Degradation Modes、18 项 Load Test Checklist、6 种场景类型、6 对 Anti-Examples、3 层 Scorecard（Critical / Standard / Hygiene）、以及 9 节 Output Contract。

**核心组件**:

| 文件 | 行数 | 职责 |
|------|------|------|
| `SKILL.md` | 420 | 主技能定义（4 Gates、3 Depth、5 Degradation、Checklist、6 Anti-Examples AE-1~6、8-item Scorecard、9-section Output Contract） |
| `references/k6-patterns.md` | ~480 | k6 执行器详细模式：constant-arrival-rate、SharedArray、thresholds、handleSummary、CI 集成 |
| `references/vegeta-patterns.md` | ~260 | vegeta 固定速率模型、管道组合、Go 集成、二进制结果归档 |
| `references/analysis-guide.md` | ~350 | 百分位解读、饱和点识别、瓶颈分类（Tier 1/2/3）、SLO 裁决框架、回归检测 |

**回归测试总量：125 项**（75 contract + 50 golden + integrity），14 个 golden fixtures（LT-001~014），所有关键维度覆盖率 100%。

---

## 2. 测试设计

### 2.1 场景定义

三个场景对应 SKILL.md 定义的三种工作模式，取自真实生产原型：

| # | 场景名称 | 输入内容 | 核心考察点 |
|---|----------|----------|------------|
| 1 | Write — 从需求生成 k6 脚本 | Go 支付 API，SLO: p99<300ms / 500 RPS / 错误率<0.1%，Bearer token，3 K8s 副本 + PostgreSQL | SLO-First 门控执行、warmup/测量分离、数据参数化、生成器隔离说明、§9 输出合规 |
| 2 | Review — 诊断缺陷 k6 脚本 | 含 3 个缺陷的脚本：无 warmup、duration:30s、用 avg 而非 percentile | 缺陷识别率、AE-x 规则命名、Scorecard 评定、§9.9 未覆盖风险 |
| 3 | Analyze — 从 k6 输出给 SLO 裁决 | 稳态 5 分钟输出：p50=88ms / p99=312ms / RPS=423.5 / 错误率 0.06%；SLO: p99<200ms | SLO PASS/FAIL 裁决表、瓶颈排名、饱和点分析、§9.9 未覆盖风险 |

### 2.2 断言矩阵（24 项）

**场景 1 — Write: 生成完整 k6 脚本（9 项）**

> ⚠️ **基线污染注意**：Without-Skill S1 代理发生了 2 次工具调用（其余无污染代理均为 0 次），且 token 消耗（37,725）远高于预期，输出中出现 `§9.x` 节编号和 `AE-3` 等 skill 专有术语。研判该代理在执行中意外读取了 skill 相关文件。以下 S1 结果记录实测值但不纳入通过率 delta 的核心计算（见 §3.3）。

| ID | 断言 | With-Skill | Without-Skill |
|----|------|:----------:|:-------------:|
| A1 | thresholds 块声明 p99 + 错误率 SLO（非 check() 比较） | PASS | PASS* |
| A2 | 包含 warmup 阶段与测量阶段分离（不同 phase tag 或 scenario） | PASS | PASS* |
| A3 | 使用 ramping-vus 或 constant/ramping-arrival-rate 逐步加载 | PASS | PASS* |
| A4 | 请求 body 数据参数化（≥3 种 merchant_id 或 currency 组合） | PASS | PASS* |
| A5 | steady-state 持续 ≥3 分钟 | PASS | PASS* |
| A6 | 明确说明负载生成器须与 SUT 分离部署 | PASS | PASS* |
| A7 | 输出 §9.1 Context Summary（含服务 / 协议 / SLO） | PASS | PASS* |
| A8 | 输出 §9.4 Scenario Design（含类型 / VU 或 RPS 目标） | PASS | PASS* |
| A9 | 输出 §9.9 Uncovered Risks（非空，≥3 条） | PASS | PASS* |

*Without-Skill S1 实测 PASS，但受工具调用污染，结果不可信。

**场景 2 — Review: 诊断缺陷 k6 脚本（8 项）**

| ID | 断言 | With-Skill | Without-Skill |
|----|------|:----------:|:-------------:|
| B1 | 识别无 warmup / 无 ramp-up（列为独立缺陷） | PASS | PASS |
| B2 | 识别 30s 时长不足（明确说明 steady-state 应 ≥3–5 分钟） | PASS | FAIL |
| B3 | 识别 avg 用于 SLO 判断（指出应用 thresholds + percentile） | PASS | PASS |
| B4 | 每个缺陷按 AE-x 或具体规则名称映射（非泛泛描述） | PASS | FAIL |
| B5 | 输出 Load Test Scorecard（Critical / Standard / Hygiene 三层评定） | PASS | FAIL |
| B6 | 提供修复建议或修正脚本（有可执行代码或具体步骤） | PASS | PASS |
| B7 | 输出 §9.2 Mode & Depth 声明 | PASS | FAIL |
| B8 | 输出 §9.9 Uncovered Risks（非空） | PASS | FAIL |

> **B2 判定说明**：Without-Skill 提供了从 30s 延长到约 4.5 分钟的修正脚本，但未将「30s 时长不足」列为独立缺陷或明确说明最低稳态时长要求（AE-5 / Scorecard Critical #3）。B4 同理，Without-Skill 使用「Wrong metric」「No ramp-up」等自然语言描述，未引用 SKILL.md 中的 AE-x 编号。

**场景 3 — Analyze: SLO 裁决与瓶颈分析（7 项）**

| ID | 断言 | With-Skill | Without-Skill |
|----|------|:----------:|:-------------:|
| C1 | 输出 per-SLO 裁决表（每条 SLO 独立 PASS / FAIL） | PASS | PASS |
| C2 | 以 p99（非 avg）作为 latency 裁决依据并明确说明 | PASS | PASS |
| C3 | 识别并排名 ≥2 个瓶颈（含证据和影响说明） | PASS | PASS |
| C4 | 给出饱和点估计或 RPS 上限分析（含计算过程） | PASS | PASS |
| C5 | 总体 verdict 明确（PASS / WARN / FAIL / INCONCLUSIVE） | PASS | PASS |
| C6 | 输出 §9.8 Recommendations（按优先级排序） | PASS | PASS |
| C7 | 输出 §9.9 Uncovered Risks（非空，≥3 条） | PASS | FAIL |

> **C7 判定**：Without-Skill S3 输出了结构良好的瓶颈分析和 P0/P1 建议，但完全缺少 §9.9 Uncovered Risks 节。With-Skill 输出 6 条风险：包括「真实 500 RPS 下错误率未知」「单副本故障降级未测试」「GC + DB 叠加效应」等生产关键盲区。

### 2.3 触发准确率分析

当前 description 采用任务类型枚举策略：

```
Performance load testing specialist for writing k6/vegeta/wrk scripts,
defining SLOs, modeling scenarios (spike/soak/stress/breakpoint), analyzing
results, and identifying bottlenecks. ALWAYS use when writing load test
scripts, reviewing test results...
```

**Should-Trigger 场景（10 个）**

| # | 提示词摘要 | 预计结果 |
|---|------------|:--------:|
| T1 | 「帮我写一个 k6 负载测试脚本」 | ✅ 触发 |
| T2 | 「review 我这个 vegeta attack 配置」 | ✅ 触发 |
| T3 | 「分析这个 k6 run 的输出，给 SLO 裁决」 | ✅ 触发 |
| T4 | 「我们需要定义 API 的 SLO」（负载测试上下文） | ✅ 触发 |
| T5 | 「做一个 soak test 检测内存泄漏」 | ✅ 触发 |
| T6 | 「breakpoint test 找我的服务容量上限」 | ✅ 触发 |
| T7 | 「写一个 spike 场景模拟流量突增」 | ✅ 触发 |
| T8 | 「我的 p99 超了 SLO，怎么找瓶颈」 | ✅ 触发 |
| T9 | 「帮我用 wrk 测试 HTTP 吞吐量」 | ✅ 触发 |
| T10 | 「k6 的 constant-arrival-rate 和 ramping-vus 有什么区别」 | ✅ 触发 |

**Should-Not-Trigger 场景（8 个）**

| # | 提示词摘要 | 预计结果 | 风险 |
|---|------------|:--------:|------|
| N1 | 「给这个 Go 函数写 benchmark 测试」 | ✅ 不触发 | 低（go-benchmark skill 接手） |
| N2 | 「优化这条 SQL 查询的性能」 | ✅ 不触发 | 低（非 HTTP 服务层） |
| N3 | 「配置 Prometheus 告警规则」 | ✅ 不触发 | 低（monitoring-alerting skill） |
| N4 | 「做 A/B feature flag 实验」 | ✅ 不触发 | 低（产品侧 A/B ≠ 负载测试） |
| N5 | 「我的服务 CPU 很高，怎么优化」 | ⚠️ 可能触发 | 中（「bottleneck」隐式触发词；但 Applicability Gate 可过滤） |
| N6 | 「设置 k6 Cloud 账号」（纯操作问题） | ⚠️ 可能触发 | 低（触发后 skill 可识别 Lite 模式降级） |
| N7 | 「我的 Go HTTP handler 太慢了，profile 一下」 | ✅ 不触发 | 低（go-benchmark skill 接手） |
| N8 | 「测试我的 React 页面加载速度」 | ✅ 不触发 | 低（frontend 性能 ≠ 后端负载测试） |

**触发准确率估算：F1 ≈ 87%**（Should-trigger 10/10；Should-not-trigger 6/8，N5/N6 属于合理模糊边界，Applicability Gate 可托底）

---

## 3. 通过率对比

### 3.1 总体通过率（原始数据）

| 配置 | 通过 | 失败 | 通过率 |
|------|:----:|:----:|:------:|
| **With-Skill** | **24** | **0** | **100%** |
| **Without-Skill** | **18** | **6** | **75%** |

**原始 delta：+25pp**（含 S1 污染数据）

### 3.2 按场景通过率

| 场景 | With-Skill | Without-Skill | 差值 | 数据质量 |
|------|:----------:|:-------------:|:----:|:--------:|
| 1. Write — 生成 k6 脚本（9 项） | 9/9 (100%) | 9/9 (100%) | +0pp | ⚠️ S1 基线污染 |
| 2. Review — 缺陷诊断（8 项） | 8/8 (100%) | 3/8 (37.5%) | **+62.5pp** | ✅ 清洁 |
| 3. Analyze — SLO 裁决（7 项） | 7/7 (100%) | 6/7 (85.7%) | **+14.3pp** | ✅ 清洁 |

### 3.3 核心 delta（S2+S3 清洁场景）

| 配置 | S2+S3 通过 | S2+S3 失败 | 通过率 |
|------|:----------:|:----------:|:------:|
| **With-Skill** | **15** | **0** | **100%** |
| **Without-Skill** | **9** | **6** | **60%** |

**核心 delta：+40pp**（基于 S2+S3 无污染数据）

### 3.4 实质性维度（去除输出结构断言，聚焦测试知识，S2+S3）

| ID | 检查项 | With-Skill | Without-Skill |
|----|--------|:----------:|:-------------:|
| S1 | S2：识别无 warmup 为独立缺陷 | PASS | PASS |
| S2 | S2：识别 30s 时长不足（steady-state 要求） | PASS | FAIL |
| S3 | S2：识别 avg 误用（应用 percentile threshold） | PASS | PASS |
| S4 | S2：提供可执行修复代码 | PASS | PASS |
| S5 | S3：p99 作为 latency 裁决依据（非 avg） | PASS | PASS |
| S6 | S3：SLO 逐项 PASS/FAIL 裁决 | PASS | PASS |
| S7 | S3：识别并排名 ≥2 个瓶颈（含证据） | PASS | PASS |
| S8 | S3：饱和点/RPS 上限估算（含推导） | PASS | PASS |
| S9 | S3：总体 verdict 明确（PASS/FAIL/INCONCLUSIVE） | PASS | PASS |

**实质性通过率：** With-Skill **9/9 (100%)** vs Without-Skill **8/9 (88.9%)**，差值 **+11pp**。

**重要发现**：Without-Skill 在测试方法论知识方面表现相当（S3 的 C1-C6 全部通过），skill 的核心增量价值集中在**输出结构合规**（Uncovered Risks、Scorecard、Mode/Depth、规则名称映射），而非测试专业知识本身。这与 go-benchmark 的非对称价值分布规律一致：Claude 基线已经具备相应领域知识，skill 的杠杆在于强制结构化输出和消除系统性盲区（如「Uncovered Risks 永不为空」）。

---

## 4. 关键差异分析

### 4.1 With-Skill 独有的行为（Without-Skill 完全缺失）

| 行为 | 实测表现 |
|------|----------|
| **AE-x 规则名称映射** | S2 With-Skill：「CRITICAL-3 — AE-1: 无 warmup / 无 ramp-up」「CRITICAL-4 — AE-3: 30 秒时长不足」；Without-Skill 使用「No ramp-up / ramp-down」「Wrong metric」等自然语言描述，无规则溯源 |
| **Load Test Scorecard 三层评定** | S2 With-Skill：输出 Critical 0/3 / Standard 0/5 / Hygiene 0/4 表格，综合裁决「FAIL — 脚本在 Critical 层全部不通过」；Without-Skill 无 Scorecard，未给出可量化的通过/失败判定 |
| **§9.9 Uncovered Risks（未覆盖风险）** | S2 With-Skill：5 条风险（支付幂等性 / 超时配置 / 并发写冲突 / Soak 缺失 / 无 teardown）；S3 With-Skill：6 条风险（真实 500 RPS 错误率 / Spike 场景 / 单副本故障降级 / GC+DB 叠加 / 测试数据代表性 / 下游依赖隔离）；Without-Skill 在 S2/S3 均缺失此节 |
| **§9.2 Mode & Depth 声明** | S2/S3 With-Skill：每次输出声明 Mode（Review / Analyze）和 Depth（Standard），附选择理由；Without-Skill 两场景均无此声明 |
| **30s 时长不足的显式识别** | S2 With-Skill：「CRITICAL-4：30 秒时长不足，最短稳态 ≥5 分钟，统计样本约 10,000 次，尾部百分位不稳定」；Without-Skill 修正脚本延长至约 4.5 分钟但未将此作为独立 critical 缺陷指出 |

### 4.2 Without-Skill 能做到但质量较低的行为

| 行为 | With-Skill 质量 | Without-Skill 质量 |
|------|-----------------|-------------------|
| SLO 裁决（S3） | 显式 FAIL/PASS 表 + 「综合裁决：SLO FAILED，不能上线」 + 推导过程 | 相同质量——SLO 表 + 「不建议当前配置进入生产」，含 RPS 推算（424 vs 425 RPS，数值一致） |
| 瓶颈识别（S3） | 🔴🔴🟡🟡 四级排序，每个附证据和关联指标 | 三个瓶颈，也有推导（「DB 连接池 90% 利用率」「GC max 41ms」），质量相当 |
| avg 误用识别（S2） | CRITICAL-1 — AE-6，附解释「check() 在每个 VU 独立评估，不是统计聚合值」 | 「Wrong metric」，给出相同核心解释，质量相当 |
| 修正脚本（S2） | 提供「最小可用脚本」含 thresholds、SharedArray、status 检查 | 提供完整修正脚本，质量相当，结构略简 |

### 4.3 场景级关键发现

**场景 2（Review 缺陷诊断）— 差距最大（+62.5pp）**:
- **With-Skill**：识别 4 个缺陷（CRITICAL-1~4），每个附 AE 编号、违规行、机制解释、修复代码；Scorecard 明确标注 Critical 0/3（全线 FAIL）；§9.9 指出 5 个生产盲区，包括「支付幂等性未测试」（payments 场景专有高风险）和「无 teardown / 数据污染」。
- **Without-Skill**：识别了相同核心问题（avg misuse、no ramp、hardcoded token、static payload），但 30s 时长问题被隐式处理（脚本改为 3m，未作为缺陷列出）；无 Scorecard，无 Uncovered Risks；B4/B5/B7/B8 共 4 项失败。

**场景 3（Analyze SLO 裁决）— 差距最小（+14.3pp）**:
- **With-Skill**：在 Without-Skill 的基础上额外输出 §9.9 Uncovered Risks 6 条，包括「真实 500 RPS 下错误率未验证」「Spike 场景下 DB 连接池行为」等关键盲区。分析质量与 Without-Skill 相当——两者均计算了 `200 VU / 0.471s ≈ 424~425 RPS`，均识别 DB 连接池（18/20 = 90%）为首要瓶颈，均给出 P0/P1/P2 优先级建议。
- **Without-Skill**：C1-C6 全部通过，仅 C7（Uncovered Risks）失败——生产关键盲区被静默遗漏，但分析深度与 With-Skill 几乎一致。

**S1 污染发现（方法论启示）**:
Without-Skill S1 代理 token 消耗（37,725）高于 With-Skill S1（32,633），且输出包含 §9.x 节编号、Scorecard 格式、AE-3 引用——这些均是 SKILL.md 专有术语。2 次工具调用推测访问了 skill 相关文件或 claude-mem 观测记录。这一发现揭示评估隔离在开放工具访问环境中的局限性，对未来 A/B 测试设计有指导意义（Without-Skill 代理应限制工具调用权限）。

---

## 5. Token 效费比分析

### 5.1 实测 Token 消耗（6 个评估代理）

| 代理 | 场景 | Total Tokens | 耗时 (s) | Tool Uses |
|------|------|:------------:|:--------:|:---------:|
| S1 With-Skill | Write — 生成 k6 脚本 | 32,633 | 133.6 | 7 |
| S1 Without-Skill | Write — 生成 k6 脚本 | 37,725 ⚠️ | 112.9 | 2 ⚠️ |
| S2 With-Skill | Review — 缺陷诊断 | 27,998 | 87.7 | 4 |
| S2 Without-Skill | Review — 缺陷诊断 | 13,422 | 21.4 | 0 |
| S3 With-Skill | Analyze — SLO 裁决 | 28,789 | 84.8 | 8 |
| S3 Without-Skill | Analyze — SLO 裁决 | 13,976 | 30.0 | 0 |

⚠️ S1 Without-Skill 发生了 2 次工具调用，token 消耗异常高（超过 With-Skill），为污染数据，不纳入效费比计算。

**With-Skill 均值（全部 3 场景）**：29,807 tokens，102.0s，6.3 tool uses
**Without-Skill 均值（S2+S3 清洁）**：13,699 tokens，25.7s，0 tool uses
**额外 token 开销（S2+S3）**：+14,695 tokens/eval（**+107%**）
**额外时间开销（S2+S3）**：+65.3s/eval（**+254%**）— 主要耗时来自加载并处理 SKILL.md 和 reference files

### 5.2 Skill 上下文成本

| 组件 | 行数 | 估算 Token 数 | 加载时机 |
|------|------|:------------:|:--------:|
| `SKILL.md` | 420 | ~2,100 | 始终加载 |
| `k6-patterns.md` | ~480 | ~2,400 | Standard+ Write 模式 |
| `vegeta-patterns.md` | ~260 | ~1,300 | Standard+ Write（vegeta 路径） |
| `analysis-guide.md` | ~350 | ~1,750 | Analyze / Deep |
| **Lite 典型（SKILL.md only）** | | **~2,100** | 快速 Review |
| **Standard Write 典型** | | **~4,500** | SKILL.md + k6-patterns.md |
| **Standard Analyze 典型** | | **~3,850** | SKILL.md + analysis-guide.md |

### 5.3 效费比计算

| 指标 | 值 |
|------|-----|
| 核心通过率提升（S2+S3，清洁） | +40pp |
| 实质性通过率提升（知识维度，S2+S3） | +11pp |
| Skill 上下文成本（最低，Lite） | ~2,100 tokens |
| Skill 上下文成本（典型，Standard Write） | ~4,500 tokens |
| 运行时额外 token 开销（S2+S3 实测均值） | +14,695 tokens/eval（+107%） |
| **每 1% 通过率提升的 Token（仅上下文，Lite）** | **~52 tokens/1%** |
| **每 1% 通过率提升的 Token（仅上下文，Standard）** | **~112 tokens/1%** |
| **每 1% 通过率提升的 Token（含运行时开销）** | **~367 tokens/1%** |

**运行时开销偏高的原因**：S2/S3 With-Skill 代理各需 4~8 次工具调用读取 SKILL.md 和 reference files（总计 1,250 行文本），导致每次评估引入较大上下文加载时间。在直接集成场景（skill 已在 system prompt 中，无需运行时加载），上下文成本（2,100~4,500 tokens）是更准确的效费比参照。

### 5.4 与其他 Skill 效费比对比

| Skill | 上下文 Token (典型) | 通过率提升 (核心场景) | 上下文 Tok/1% | 含运行时 Tok/1% |
|-------|:------------------:|:-------------------:|:-------------:|:--------------:|
| `git-commit` | ~1,300 | +77pp | ~17 | ~73 |
| `go-benchmark` | ~2,380–3,330 | +54pp | ~44–62 | ~177 |
| **`load-test`** | **~2,100–4,500** | **+40pp (核心)** | **~52–112** | **~367** |

**load-test 效费比特征分析**：

1. **上下文成本偏高（420 行 SKILL.md + 最多 1,090 行 references）**：skills 知识密度大，适合深度专项任务，不适合轻量问答
2. **运行时开销最高（+107%）**：由于工具调用加载 reference files，代理执行时间和总 token 显著增加；但在预加载场景（system prompt 注入）中此开销不存在
3. **核心价值区窄（Review 模式 +62.5pp；Analyze 模式仅 +14.3pp）**：基线 Claude 在 Analyze 型任务已相当能干，load-test skill 对写作/审查型任务的杠杆更大

---

## 6. 综合评分

### 6.1 分维度评分

| 维度 | With Skill | Without Skill | 差值 |
|------|:----------:|:-------------:|:----:|
| 输出结构完整性（Scorecard / Mode&Depth / Uncovered Risks） | 5.0/5 | 0.5/5 | +4.5 |
| 缺陷系统映射（AE-x 编号 / 规则溯源） | 5.0/5 | 0.5/5 | +4.5 |
| 测试方法论正确性（p99 / warmup / 数据参数化 / 饱和点分析） | 5.0/5 | 4.0/5 | +1.0 |
| SLO 裁决完整性（per-SLO 表 / 综合 verdict） | 5.0/5 | 4.5/5 | +0.5 |
| Token 效费比（上下文 Tok/1%，相对领域复杂度） | 3.0/5 | — | — |

### 6.2 加权总分

| 维度 | 权重 | 得分 | 理由 | 加权 |
|------|:----:|:----:|------|:----:|
| Assertion 通过率（核心 delta） | 25% | 8.0/10 | +40pp 清洁场景；S3 基线偏强（85.7%）拉低整体；Review 模式 +62.5pp 是真实杠杆 | 2.00 |
| 输出结构合规性 | 25% | 9.5/10 | Without-Skill 在 S2/S3 两个无污染场景输出合规率 0/2（Scorecard）和 0/2（Uncovered Risks）；With-Skill 3/3 全覆盖；结构完整性是 skill 最强保障 | 2.38 |
| 缺陷规则名称映射 | 20% | 9.5/10 | Without-Skill 完全不输出 AE-x 规则编号（B4 FAIL）；With-Skill 系统映射为首选结果；利于工程团队追溯修复根因 | 1.90 |
| 测试方法论知识 | 15% | 7.0/10 | Without-Skill 在 Analyze 场景表现接近 With-Skill（8/9 实质性通过率）；差距主要在 30s 时长识别（B2）；skill 增量有限，但 AE-5 关键防线仍值得保留 | 1.05 |
| Token 效费比 | 15% | 6.0/10 | ~52 tok/1%（Lite 上下文），略高于 go-benchmark 最低值；运行时 +107% 开销是主要压力来源，预加载场景可显著改善 | 0.90 |
| **加权总分** | **100%** | | | **8.23/10** |

---

## 7. 结论

`load-test` 在三个场景共 24 项断言中实现 100% 通过，清洁基线下（S2+S3）与 Without-Skill（60%）相比提升 **+40pp**。评估揭示了一个非对称价值分布：

**高价值区（Review 模式，+62.5pp）**：
- Without-Skill 能识别主要缺陷，但系统性不足——30s 时长不足被隐式处理而非显式标记，avg 误用被正确识别但不引用规则，Scorecard 和 Uncovered Risks 完全缺失。对于严肃的负载测试 review，「发现问题」与「系统性分类和量化」之间的差距直接影响工程团队的修复优先级判断。

**低价值区（Analyze 模式，+14.3pp）**：
- Without-Skill 在 SLO 裁决、瓶颈识别、饱和点推算方面表现相当。两个代理均计算了 `200 VU / 0.471s ≈ 424 RPS` 作为吞吐量上限，均识别 DB 连接池（18/20）为首要瓶颈，均给出 P0/P1 优先级建议。唯一明确差距是 §9.9 Uncovered Risks 的缺失——这不是分析深度的问题，而是输出规范的执行问题。

**核心价值点**：
1. **Scorecard 三层门禁**：Review 模式下将「脚本是否可用于生产决策」量化为 Critical/Standard/Hygiene 三层可追踪状态，防止工程师在 Critical 项目失败时仍推进测试
2. **Uncovered Risks 强制输出**：6 对测试结果被解读为「完整答案」，但实际上遗漏了 Spike 测试、单副本故障降级、幂等性等关键场景。`§9.9 永不为空` 这条规则使这些盲区成为可见的遗留任务而非静默缺失
3. **AE-x 规则溯源**：将缺陷命名为「AE-1: No warmup」而非「没有热身阶段」，为工程团队提供了 SKILL.md 的精确参照点，支持团队级一致性标准的落地

**改进建议**：
1. **提高 Analyze 场景增量价值**：analysis-guide.md 可增加「叠加效应分析模板」（GC pause × DB 连接等待的联合概率分析）和「跨 run 回归检测标准」，使分析输出超出基线 Claude 的自然上限
2. **优化 Token 效率**：SKILL.md 的 Scorecard 模板（约 40 行）和 Output Contract 详细描述（约 30 行）可迁入 reference file，SKILL.md 仅保留指针，预计节省 ~350 tokens，将 Lite 上下文成本从 2,100 降至约 1,750 tokens
3. **评估隔离改进**：未来 A/B 测试中，Without-Skill 代理应通过 `allowed_tools: []` 或独立上下文隔离，防止意外通过工具调用或内存观测加载 skill 内容（S1 污染事件的根因）
