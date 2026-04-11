# go-benchmark Skill 评估报告

> 评估框架: [skill-creator](https://github.com/anthropics/skills/tree/main/skills/skill-creator)
> 评估日期: 2026-04-11
> 评估对象: `go-benchmark`

---

`go-benchmark` 是一个专注于 Go 性能基准测试与 pprof 分析的专项 skill。评估横跨三个场景（从源码写基准 / 审查有缺陷的基准 / 分析 benchstat 数据），共 24 项断言，With-Skill 全部通过（24/24，100%），Without-Skill 通过率 46%（11/24），总体提升 **+54 百分点**。三个最突出的差距：第一，With-Skill 始终声明 `var sinkString` / `var sinkErr` 并解释为何 `_ = result` 会导致编译器消除整个调用，Without-Skill 在场景 1 完全未使用 sink 变量，在场景 2 则明确说 `_ = data` 是"safe here"；第二，Evidence Gate 驱动的 mode / data_basis 声明和 Auto Scorecard 块在三个场景的 Without-Skill 输出中均不存在（0/3）；第三，场景 3（benchstat 数据分析）Without-Skill 得分意外偏高（6/8，75%）——这一发现揭示了 skill 对统计分析型任务的增量价值有限，真正的杠杆在于基准代码的写作和审查。

---

## 1. Skill 概述

`go-benchmark` 定义了 5 条 Hard Rules（静默腐化防护）、3 个 Mandatory Gates（Evidence / Applicability / Scope）、三阶段工作流（Write → Run & Profile → Analyze & Optimize）、4 字段 Output Contract、以及 Auto Scorecard 三层门禁（Critical / Standard / Hygiene）。

**核心组件**:

| 文件 | 行数 | 职责 |
|------|------|------|
| `SKILL.md` | 378 | 主技能定义（5 Hard Rules、3 Gates、3 阶段工作流、Output Contract、Anti-Examples、Auto Scorecard） |
| `references/benchmark-patterns.md` | ~120 | `b.*` API 详细模式：per-iteration setup/teardown、`b.SetBytes`、`b.ReportAllocs`、helper 函数 |
| `references/pprof-analysis.md` | ~150 | Flame graph 解读、alloc 热点模式、`-alloc_objects` vs `-alloc_space` 选择 |
| `references/optimization-patterns.md` | ~100 | `sync.Pool`、预分配、逃逸分析等修复配方 |
| `references/benchmark-antipatterns.md` | ~100 | 扩展反例目录，超出内联 3 对之外的边缘场景 |
| `references/benchstat-guide.md` | ~80 | benchstat 输出解读、p 值、噪声降低、统计有效性 |

**回归测试总量：96 项**（65 contract + 30 golden + 1 integrity），所有关键维度覆盖率 100%。

---

## 2. 测试设计

### 2.1 场景定义

三个场景对应 SKILL.md 定义的三种工作模式，取自真实用户会话原型：

| # | 场景名称 | 输入内容 | 核心考察点 |
|---|----------|----------|------------|
| 1 | Phase 1 — 从源码写基准 | RLE Encode/Decode Go 源码，无运行时数据 | var sink 声明、ResetTimer 时机、-benchmem、O(n) 子基准、双返回值 sink |
| 2 | Phase 1+2 — 审查有缺陷的基准 | 含 3 处 Hard Rules 违规的 JSON 序列化基准（timer inside loop、`_ = data`、缺 -benchmem）+ -count=1 | 按规则名系统列出违规；识别 `_ =` 的编译器消除风险；提供修正文件 |
| 3 | Phase 3 — 分析 benchstat 噪声数据 | benchstat 输出（time/op: ± 7–13%，p=0.063–0.095；allocs/op: ± 0%，p=0.008） | 区分统计显著（allocs/op）与不显著（time/op）；给出降噪命令 |

### 2.2 断言矩阵（24 项）

**场景 1 — Phase 1: 从源码写基准（9 项）**

| ID | 断言 | With-Skill | Without-Skill |
|----|------|:----------:|:-------------:|
| A1 | 声明 package-level `var sink`，不使用 `_ =` | PASS | FAIL |
| A2 | `b.ResetTimer()` 在 setup 后、loop 前正确放置 | PASS | PASS |
| A3 | run 命令包含 `-benchmem` 标志 | PASS | PASS |
| A4 | run 命令指定 `-count` 标志（≥5 探索，≥10 对比） | PASS | FAIL |
| A5 | O(n) Encode 函数添加 ≥3 个 input size 子基准 | PASS | PASS* |
| A6 | Decode 的两个返回值均有 sink（string + error） | PASS | FAIL |
| A7 | 明确声明 data_basis=`static analysis only`，提示需运行命令获得真实数字 | PASS | FAIL |
| A8 | 回复末尾输出 Auto Scorecard 块（Critical/Standard/Hygiene） | PASS | FAIL |
| A9 | 声明全部 4 个 Output Contract 字段（mode/data_basis/scorecard_result/profiling_method） | PASS | FAIL |

> *A5 注：Without-Skill 提供了 7 个独立的 Encode 基准函数覆盖不同输入，但使用的是平铺式顶层函数而非 `b.Run()` 形式的 size sweep，PASS（实质覆盖了多种尺寸，形式不同）。

**场景 2 — Phase 1+2: 审查有缺陷的基准（7 项）**

| ID | 断言 | With-Skill | Without-Skill |
|----|------|:----------:|:-------------:|
| B1 | 识别 `b.ResetTimer()` 在 loop 内的 Hard Rule 违规（破坏计时） | PASS | PASS |
| B2 | 识别 `_ = data` 的 sink 问题（编译器可能消除整个调用） | PASS | FAIL |
| B3 | 识别 run 命令缺少 `-benchmem` 标志 | PASS | PASS |
| B4 | 识别 `-count=1` 对比场景不足（需 `-count=10` + benchstat） | PASS | FAIL |
| B5 | 提供修正后的完整基准文件（所有问题均已修复） | PASS | FAIL |
| B6 | 回复末尾输出 Auto Scorecard 块 | PASS | FAIL |
| B7 | 声明全部 4 个 Output Contract 字段 | PASS | FAIL |

**场景 3 — Phase 3: 分析 benchstat 噪声数据（8 项）**

| ID | 断言 | With-Skill | Without-Skill |
|----|------|:----------:|:-------------:|
| C1 | 标记 ± 7–13% 高噪声超过 ±5% 阈值 | PASS | PASS |
| C2 | 正确解读 time/op 的 p 值（0.063–0.095 > 0.05）= 不显著 | PASS | PASS |
| C3 | 推荐 `-benchtime=2s` 或 `-count=20` 降噪 | PASS | PASS |
| C4 | 正确识别 allocs/op 的 p=0.008 < 0.05 = 统计显著 | PASS | PASS |
| C5 | 明确区分：time/op 不确定，allocs/op 已确认 | PASS | PASS |
| C6 | 提供精确的 next-step 命令（含正确的 `-count`/`-benchtime`） | PASS | PASS |
| C7 | 回复末尾输出 Auto Scorecard 块 | PASS | FAIL |
| C8 | 声明全部 4 个 Output Contract 字段 | PASS | FAIL |

### 2.3 触发准确率分析

当前 description 采用双层触发策略：

```
Go performance benchmarking and pprof profiling specialist. ALWAYS use when
writing benchmark functions (testing.B), generating or reading pprof profiles,
interpreting flame graphs, finding memory allocation hotspots, comparing
implementations with benchstat, or measuring ns/op / B/op / allocs/op.
In Go code contexts, also trigger when the user says "it's slow", "too many
allocations", "find the bottleneck", or "profile this Go code".
```

- **显式触发词**（确定性高）：`testing.B`、`pprof profiles`、`flame graphs`、`benchstat`、`ns/op`、`B/op`、`allocs/op`
- **隐式触发词**（上下文感知）：`"it's slow"`、`"too many allocations"`、`"find the bottleneck"`——通过「In Go code contexts」限定词防止非 Go 场景误触发

**Should-Trigger 场景（10 个）**

| # | 提示词摘要 | 预计结果 |
|---|------------|:--------:|
| T1 | 「给我的 Go JSON 解析器写 benchmark 函数」 | ✅ 触发 |
| T2 | 「解读这段 benchstat 比较输出」 | ✅ 触发 |
| T3 | 「帮我读这个 flame graph，找最宽的 box」 | ✅ 触发 |
| T4 | 「我的 Go 服务很慢，能帮我找瓶颈吗」 | ✅ 触发 |
| T5 | 「Go HTTP handler 的 allocs/op 太高了，怎么降」 | ✅ 触发 |
| T6 | 「用 benchstat 对比两个 Go 实现，结果对吗」 | ✅ 触发 |
| T7 | 「Go 代码分配太多内存了，help me profile this」 | ✅ 触发 |
| T8 | 「write a testing.B benchmark for concurrent cache」 | ✅ 触发 |
| T9 | 「这个基准的 b.ResetTimer 位置对吗」 | ✅ 触发 |
| T10 | 「生成 CPU profile，go test -bench=BenchmarkQuery」 | ✅ 触发 |

**Should-Not-Trigger 场景（8 个）**

| # | 提示词摘要 | 预计结果 | 潜在风险 |
|---|------------|:--------:|----------|
| N1 | 「给我的 Go calculator 写 table-driven 单元测试」 | ✅ 不触发 | 低（testing.T ≠ testing.B） |
| N2 | 「用 cProfile 分析这个 Python 函数」 | ✅ 不触发 | 低（非 Go，限定词有效） |
| N3 | 「我的 MySQL 查询太慢，优化 SQL」 | ✅ 不触发 | 低（非 Go） |
| N4 | 「修复 Go goroutine 的 race condition」 | ✅ 不触发 | 低（并发安全 ≠ 性能分析） |
| N5 | 「我的 Rust 程序内存占用高」 | ✅ 不触发 | 低（非 Go） |
| N6 | 「帮我写 Go 的错误处理测试」 | ✅ 不触发 | 低（testing ≠ benchmarking） |
| N7 | 「my Go service has high memory usage, help」 | ⚠️ 可能触发 | 中（"memory"+"Go" 可触发；但触发合理，可通过 Applicability Gate 二次过滤） |
| N8 | 「compare these two Go sorting algorithms」（无性能测量上下文） | ⚠️ 可能触发 | 中（"compare"+"Go"可能误触发；Applicability Gate 可托底） |

**触发准确率估算：F1 ≈ 88%**（should-trigger 10/10 覆盖；should-not-trigger 6/8 精准拒绝，N7/N8 属于合理触发边界）

---

## 3. 通过率对比

### 3.1 总体通过率

| 配置 | 通过 | 失败 | 通过率 |
|------|------|------|--------|
| **With Skill** | **24** | **0** | **100%** |
| **Without Skill** | **11** | **13** | **46%** |

**通过率提升：+54 百分点**

### 3.2 按场景通过率

| 场景 | With-Skill | Without-Skill | 差值 |
|------|:----------:|:-------------:|:----:|
| 1. Phase 1 — 从源码写基准（9 项） | 9/9 (100%) | 2/9 (22%) | +78pp |
| 2. Phase 1+2 — 审查有缺陷基准（7 项） | 7/7 (100%) | 3/7 (43%) | +57pp |
| 3. Phase 3 — 分析 benchstat 数据（8 项） | 8/8 (100%) | 6/8 (75%) | +25pp |

**重要发现**：场景 3 的 Without-Skill 得分（75%）显著高于场景 1（22%）和场景 2（43%）。这揭示了一个非对称价值分布：基线 Claude 在统计概念理解（p 值、CV 阈值）方面已相当能干，skill 对「分析型任务」的增量价值有限（+25pp）；真正的杠杆在于「代码写作/审查型任务」，这是基线最容易犯隐性错误的领域（+57–78pp）。

### 3.3 实质性维度（去除结构性流程断言，12 项）

| ID | 检查项 | With-Skill | Without-Skill |
|----|--------|:----------:|:-------------:|
| S1 | 场景 1：benchmark 代码实际使用 `var sink`（非 `_ =`） | PASS | FAIL |
| S2 | 场景 1：`b.ResetTimer()` 正确放置（不在 loop 内） | PASS | PASS |
| S3 | 场景 1：run 命令包含 `-benchmem` | PASS | PASS |
| S4 | 场景 1：O(n) 函数有多 size 覆盖（≥3 尺寸） | PASS | PASS |
| S5 | 场景 1：Decode 的 `(string, error)` 两者均 sink | PASS | FAIL |
| S6 | 场景 2：识别 `_ = data` 的编译器消除风险 | PASS | FAIL |
| S7 | 场景 2：识别 `b.ResetTimer()` inside loop | PASS | PASS |
| S8 | 场景 2：识别缺少 `-benchmem` | PASS | PASS |
| S9 | 场景 2：修正文件中所有 sink 问题均已修复 | PASS | FAIL |
| S10 | 场景 3：标记 ±>5% 噪声并推荐降噪方案 | PASS | PASS |
| S11 | 场景 3：正确区分 time/op（不显著）vs allocs/op（已确认） | PASS | PASS |
| S12 | 场景 3：提供精确的 next-step 命令 | PASS | PASS |

**实质性通过率（严格）**：With-Skill **12/12 (100%)** vs Without-Skill **7/12 (58%)**，提升 **+42pp**。

---

## 4. 关键差异分析

### 4.1 With-Skill 独有的行为（Without-Skill 完全缺失）

| 行为 | 实测表现 |
|------|----------|
| **Evidence Gate 三路分类** | 场景 1 输出：「Source code only is available. I can write the benchmarks... but I cannot provide real ns/op numbers without running them.」Baseline 完全未执行此步骤 |
| **package-level var sink（系统性）** | 场景 1 声明 `var sinkString string` + `var sinkErr error` 并附解释：「Using _ = would allow the compiler to prove results are unused and optimize the calls away entirely.」 |
| **Output Contract 4 字段** | 场景 1/2/3 均在回复顶部或末尾声明 mode / data_basis / profiling_method；Without-Skill 三个场景均未出现任何 Output Contract 输出 |
| **Auto Scorecard 块** | 场景 1/2/3 均在回复末尾输出 Critical/Standard/Hygiene 三层门禁状态；Without-Skill 三个场景均无 Scorecard |
| **`_ = data` 编译器消除风险识别** | 场景 2：With-Skill 明确列为 Violation 1（Critical Hard Rule）并解释「compiler is permitted to optimize away the entire json.Marshal call」；Without-Skill 说「safe here」（技术上对于 json.Marshal 无自定义类型确实不会消除，但错误示范了原则） |

### 4.2 Without-Skill 能做到但质量较低的行为

| 行为 | With-Skill 质量 | Without-Skill 质量 |
|------|-----------------|-------------------|
| `b.ResetTimer()` bug 识别 | 按 Hard Rule #2 命名，分析「只有最后一次迭代的计时有效」 | 正确识别为 Critical Bug，质量相当（B1 PASS） |
| benchstat 统计分析 | Evidence Gate 分类 + 明确区分 time/op（p>0.05）vs allocs/op（p=0.008）+ 自动 Scorecard | 质量相当——正确解读 p 值、噪声阈值、allocs 显著性（C1-C6 全 PASS） |
| `-benchmem` 识别 | Hard Rule #3 违规，精确列出行号和修复命令 | 正确识别，建议改用 `-benchmem`（B3 PASS） |
| 修正后基准文件 | `var sinkBytes []byte; var sinkErr error` 正确 sink 两个返回值 | 修正了 ResetTimer 问题，但「修正」文件仍保留 `_ = data`（B5 FAIL） |

### 4.3 场景级关键发现

**场景 1（从源码写基准）**:
- **With-Skill**：Evidence Gate 声明 `write` / `static analysis only`；Scope Gate 选择多 size 子基准（64B/1KB/64KB/1MB）；声明 `var sinkString string` + `var sinkErr error`（附编译器消除解释）；所有 `Decode` 调用使用 `sinkString, sinkErr = Decode(...)`；run 命令：`-benchmem -count=5`（探索）和 `-count=10`（对比）；Auto Scorecard：Critical ✅✅✅ Standard 5/5 Hygiene 4/4。
- **Without-Skill**：使用 `for b.Loop()` 新语法（Go 1.24+）并解释其优势。提供了 7 个平铺 Encode 基准覆盖不同输入特征（空/单字符/无重复/短重复/长重复/混合）——覆盖思路清晰。**但**：基准函数内完全没有使用 sink 变量，结果直接被 `b.Loop()` 抛弃；Decode 结果同样未捕获；run 命令缺 `-count`；无 Evidence Gate / Scorecard / Output Contract。值得注意的是，Without-Skill 在注释中提到「assign the return to package-level sink variables if you observe suspiciously fast numbers」——将 sink 定性为可选的后备手段，而非必须的预防规则。

**场景 2（审查有缺陷的基准）**:
- **With-Skill**：系统列出 4 处违规（3 Critical + 1 Standard），每处按 Hard Rule 编号、违规行、机制解释、修复代码：Violation 1 的解释明确点出「compiler is permitted to optimize away the entire json.Marshal call」；修正文件使用 `var sinkBytes []byte; var sinkErr error`，所有调用改为 `sinkBytes, sinkErr = json.Marshal(u)`；Scorecard 显示 Critical ❌❌❌（审查的是已违规代码，分显示原状态）。
- **Without-Skill**：在「Critical Bug」节正确识别了 `b.ResetTimer()` in loop；在「Minor」节提到 `-benchmem` 和建议 `-count=5`。**关键缺失**：`_ = data` 被描述为「safe here」因为 json.Marshal 不会失败——这混淆了错误处理安全性和编译器优化风险，导致修正文件仍保留了 `_ = data`，根本问题未被修复。

**场景 3（分析 benchstat 数据）**:
- **With-Skill**：Evidence Gate 分类为 `analyze` / `benchmark output`；完整覆盖 C1-C6 的所有统计分析；额外提供 pprof diff 命令（`-diff_base mem-old.prof mem-new.prof`）和超线性分配增长的分析（allocs 比率：1×/3.7×/14.8× vs 输入 1×/4×/16×）；Auto Scorecard 标注 Standard 3/5（缺 `-count=10` 和 alloc 目标）。
- **Without-Skill**：同样正确覆盖了 C1-C6 的所有统计断言，质量和深度与 With-Skill 相当。提供了明确的 `-count=20 -benchtime=3s` 建议和统计功效估算（「需要约 15-20 个样本才能以 80% 功效检测 7% 的改进」）。唯一缺失：Auto Scorecard 和 Output Contract 字段。

---

## 5. Token 效费比分析

### 5.1 实测 Token 消耗（6 个评估代理）

| 代理 | 场景 | Total Tokens | 耗时 (s) | Tool Uses |
|------|------|:------------:|:--------:|:---------:|
| S1 With-Skill | 从源码写基准 | 32,898 | 184.9 | 8 |
| S1 Without-Skill | 从源码写基准 | 21,483 | 76.6 | 5 |
| S2 With-Skill | 审查有缺陷基准 | 29,439 | 102.6 | 7 |
| S2 Without-Skill | 审查有缺陷基准 | 20,471 | 77.9 | 4 |
| S3 With-Skill | 分析 benchstat | 28,598 | 124.0 | 6 |
| S3 Without-Skill | 分析 benchstat | 20,331 | 72.5 | 5 |

**With-Skill 均值**：30,312 tokens，137.2s，7 tool uses/eval
**Without-Skill 均值**：20,762 tokens，75.7s，5 tool uses/eval
**额外 token 开销**：+9,550 tokens/eval（**+46%**）
**额外时间开销**：+61.5s/eval（**+81%**）

### 5.2 Skill 上下文成本

| 组件 | 行数 | 估算 Token 数 | 加载时机 |
|------|------|-------------|----------|
| `SKILL.md` | 378 | ~2,380 | 始终加载 |
| `benchmark-patterns.md` | ~120 | ~750 | Phase 1 写基准时 |
| `pprof-analysis.md` | ~150 | ~950 | Phase 3 读 pprof 时 |
| `optimization-patterns.md` | ~100 | ~600 | 应用修复时 |
| `benchmark-antipatterns.md` | ~100 | ~600 | 扩展反例场景 |
| `benchstat-guide.md` | ~80 | ~500 | 分析统计有效性时 |
| **Phase 1 典型总计** | | **~3,130** | SKILL.md + benchmark-patterns.md |
| **Phase 3 典型总计** | | **~3,330** | SKILL.md + pprof-analysis.md |

### 5.3 效费比计算

| 指标 | 值 |
|------|-----|
| 通过率提升（严格） | +54pp |
| 实质性通过率提升 | +42pp |
| Skill 上下文成本（仅 SKILL.md） | ~2,380 tokens |
| Skill 上下文成本（典型，含 1 ref） | ~3,130–3,330 tokens |
| 运行时额外 token 开销（实测均值） | +9,550 tokens/eval（+46%） |
| **每 1% 通过率提升的 Token（仅上下文）** | **~44 tokens/1%** |
| **每 1% 通过率提升的 Token（含运行时开销）** | **~177 tokens/1%** |

### 5.4 与其他 Skill 效费比对比

| Skill | 上下文 Token | 通过率提升 | 上下文 Tok/1% | 含运行时 Tok/1% |
|-------|:----------:|:---------:|:------------:|:--------------:|
| `git-commit` | ~1,300 | +77pp | ~17 | ~73 |
| **`go-benchmark`** | **~2,380–3,330** | **+54pp** | **~44–62** | **~177** |
| `go-makefile-writer` | ~1,960–4,300 | +31pp | ~63–139 | — |

**go-benchmark 效费比低于 git-commit 的原因分析：**

1. **SKILL.md 更长（378 vs 169 行）**：Anti-Examples 内联（3 组 BAD/GOOD）、Auto Scorecard 模板、Output Contract 表格占用约 100 行
2. **通过率提升绝对值较小（+54pp vs +77pp）**：场景 3 的 Without-Skill 已达 75%，大幅拉低了整体提升幅度
3. **运行时开销更高（+46% tokens，+81% 时间）**：3 个 Gates 的执行、4 字段 Output Contract 的声明、详细 Scorecard 输出均增加了 token 消耗

**重要上下文**：如果仅看 go-benchmark 真正擅长的场景（Phase 1 + Phase 2），对应提升为 +78pp 和 +57pp，效费比将接近 git-commit 水平。+54pp 的整体数字被场景 3 的低增量（+25pp）稀释。

---

## 6. 综合评分

### 6.1 分维度评分

| 维度 | With Skill | Without Skill | 差值 |
|------|:----------:|:-------------:|:----:|
| 静默腐化防护（var sink 系统性声明与解释） | 5.0/5 | 1.0/5 | +4.0 |
| 数据分类与诚实降级（Evidence Gate） | 5.0/5 | 0.5/5 | +4.5 |
| 输出结构一致性（Output Contract + Auto Scorecard） | 5.0/5 | 0.0/5 | +5.0 |
| 基准代码审查系统性（按 Hard Rule 名逐项） | 5.0/5 | 2.5/5 | +2.5 |
| 统计分析能力（benchstat p 值、噪声阈值） | 5.0/5 | 4.0/5 | +1.0 |
| Token 效费比（Tok/1% 相对领域复杂度） | 3.5/5 | — | — |
| **综合均值（前 5 维度）** | **5.0/5** | **1.6/5** | **+3.4** |

### 6.2 加权总分

| 维度 | 权重 | 得分 | 理由 | 加权 |
|------|------|:----:|------|:----:|
| Assertion 通过率（delta） | 25% | 8.5/10 | +54pp 严格；若仅计 Phase 1+2 则 +68pp；受场景 3 低增量稀释 | 2.13 |
| 静默腐化防护 | 20% | 9.5/10 | `_ = data` 识别是 Baseline 高频错误（场景 1 完全未 sink；场景 2 说"safe"）；skill 唯一可靠防线 | 1.90 |
| 数据分类与诚实降级 | 20% | 10.0/10 | Evidence Gate 在三个场景均正确执行；防止无数据时伪造 ns/op（golden fixture BENCH-009 验证） | 2.00 |
| 输出结构一致性 | 15% | 10.0/10 | Without-Skill 三场景均无 Output Contract 或 Scorecard（0/3）；With-Skill 三场景全覆盖（3/3） | 1.50 |
| 统计分析能力 | 10% | 8.0/10 | Without-Skill 场景 3 达 75%——基线已很强；skill 增量有限但 Scorecard 中对 -count 的系统性建议优于 baseline | 0.80 |
| Token 效费比 | 10% | 7.0/10 | ~44 tok/1%（上下文），优于 go-makefile-writer 但弱于 git-commit；运行时开销+46% 是主要压力；场景 3 低增量也拉低了分母 | 0.70 |
| **加权总分** | **100%** | | | **9.03/10** |

---

## 7. 结论

`go-benchmark` 在三个场景共 24 项断言中实现 100% 通过，与 Without-Skill（46%）相比提升 **+54pp**。评估揭示了一个非对称价值分布：

**高价值区（Phase 1 + Phase 2，代码写作/审查）**：
- Phase 1 提升 +78pp：Without-Skill 在实际 benchmark 代码中完全未使用 sink 变量，或将其标注为可选后备手段；sink 的系统性缺失是静默的、无法从运行结果直接发现的错误
- Phase 2 提升 +57pp：Without-Skill 对 `_ = data` 的判断（「safe here」）在技术上具体而言并非完全错误，但导致整个修正文件的 sink 问题未被根治——展示了原则性理解 vs 场景性判断的差距

**低价值区（Phase 3，统计分析）**：
- Phase 3 提升 +25pp：Without-Skill 在 p 值、CV 阈值、显著性判断方面表现相当，skill 主要增量来自 Scorecard 和 Output Contract 结构化输出，而非实质性分析能力

**核心价值点**:
1. **静默腐化防护**：`_ = encode(input)` 看起来合法、编译通过、无报错，但编译器在特定优化 pass 可以完全消除该调用，benchmark 则变成测量循环开销。这是 Baseline 在高频易犯、难以自检的盲区，Hard Rule #1 是唯一可靠保障
2. **Evidence Gate**：在用户「什么都没提供」时（golden fixture BENCH-009），强制触发降级路径，阻止推测性分析
3. **输出一致性**：Output Contract + Auto Scorecard 确保跨用户、跨会话的输出格式可预期，是 Baseline 完全缺失的结构化质量报告机制

**改进建议**:
1. **提高场景 3 增量价值**：benchstat-guide.md 可增加「超线性分配增长」（allocs 与输入尺寸比例分析）和 pprof diff 工作流，使统计分析输出超出 Baseline 的自然上限
2. **Auto Scorecard 可精简**：将模板（约 40 行）移入 reference file，SKILL.md 保留指针，预计节省 ~200 tokens 改善效费比
3. **触发准确率**：当前 F1≈88%，主要短板在隐式触发词（「my Go service has high memory usage」）的边界。可考虑在 description 中增加一条负向示例（「not for general Go debugging or unit testing」）以降低误触发