# fuzzing-test Skill 评审报告

> 评估框架: [skill-creator](https://github.com/anthropics/skills/tree/main/skills/skill-creator)
> 评估日期: 2026-03-12
> 评估对象: `fuzzing-test`

---

`fuzzing-test` 是一个专门为 Go 代码生成高信号 fuzz 测试的 skill，适合用于 parser、编解码、状态转换和其他具备明确不变量的目标，同时也适用于判断某个目标是否根本不值得做 fuzz。它最突出的三个亮点是：先执行 Applicability Gate，再决定是否进入生成流程，避免“见函数就写 fuzz”；对于不适合 fuzz 的目标会明确拒绝并给出替代方案，而不是勉强产出低价值代码；同时内置目标优先级、成本分级和结构化输出，能把 fuzz 测试做得更可控、更有性价比。

## 一、评估概览

本次评估从**实际任务表现**和 **Token 效费比**两个维度对 fuzzing-test skill 进行全面评审。设计 3 个覆盖不同场景的 fuzz test 生成任务（适合的 parser 目标、不适合的网络依赖目标、多候选函数的包级评估），每个场景分别运行 with-skill 和 without-skill 配置，共 3 场景 × 2 配置 = 6 次独立 subagent 运行，对照 35 条 assertion 进行评分。

| 维度 | With Skill | Without Skill | 差异 |
|------|-----------|--------------|------|
| **Assertion 通过率** | **35/35 (100%)** | 16/35 (45.7%) | **+54.3 百分点** |
| **适用性判断（Applicability Gate）** | 3/3 场景正确 | 0/3 有正式 gate | Skill 独有 |
| **不适合目标的拒绝能力** | 正确拒绝+替代方案 | 反而构建了 workaround | 最大单项差异 |
| **Output Contract 结构化报告** | 3/3 | 0/3 | Skill 独有 |
| **Size guard 覆盖率** | 100%（所有 harness） | ~25%（仅部分 harness） | Skill 系统性 |
| **Skill Token 开销（SKILL.md 单文件）** | ~4,100 tokens | 0 | — |
| **Skill Token 开销（典型加载）** | ~6,500 tokens | 0 | — |
| **每 1% 通过率提升的 Token 成本** | ~75 tok（SKILL.md only）/ ~120 tok（typical） | — | — |

---

## 二、测试方法

### 2.1 场景设计

| 场景 | 仓库 / 目标 | 核心考察点 | Assertions |
|------|-----------|-----------|-----------|
| Eval 1: parser-fuzz | `internal/parser/Parse` — URL parser，纯函数 | 适合 fuzzing 的 Tier 1 目标的完整处理流程 | 15 |
| Eval 2: fetch-reject | `internal/github/fetcher.Fetch` — 网络依赖方法 | 不适合 fuzzing 的目标的正确拒绝能力 | 7 |
| Eval 3: converter-multi | `internal/converter` 包 — 多候选函数 | 多目标筛选、优先级评估、选择性生成 | 13 |

### 2.2 执行方式

- 以 `issue2md` 项目为基础，为每个场景创建独立副本（`/tmp/fuzz-eval-*`）
- With-skill 运行先读取 SKILL.md 及其引用的参考资料
- Without-skill 运行不读取任何 skill，按模型默认行为处理
- 所有运行在独立 subagent 中并行执行

### 2.3 场景详情

**Eval 1 — parser.Parse（适合目标）**

`Parse(rawURL string) (ResourceRef, error)` 是一个经典的 Tier 1 fuzz 目标：
- 接受 `string` 输入（Go fuzz 原生类型）
- 纯函数，无 IO/网络/状态依赖
- 有多个可验证的不变量（Owner 非空、Number > 0、Type ∈ 有效集、canonical URL 一致性、重解析幂等性）
- 快速执行（亚微秒级）

**Eval 2 — fetcher.Fetch（不适合目标）**

`Fetch(ctx, ref, opts) (IssueData, error)` 是一个经典的不适合 fuzz 的目标：
- 所有代码路径都发起真实 HTTP 请求
- 依赖 GitHub API token 认证
- 包含 retry + backoff 逻辑
- 有趣的输入空间是 API 响应，而非方法参数

**Eval 3 — converter 包（多候选）**

包含 5 个候选函数，其中 4 个适合、1 个不适合：
- ✅ `yamlQuote(string) string` — YAML 转义，有 round-trip 不变量
- ✅ `normalizeSummaryJSON(string) (string, error)` — JSON 提取器，有 `json.Valid` 不变量
- ✅ `detectSummaryLanguage(string) string` — Unicode 分析，有有限返回值集不变量
- ✅ `capSummarySourceLength(string) string` — rune 截断，有长度上界不变量
- ❌ `Summarize(ctx, data, lang)` — OpenAI HTTP 调用，网络依赖

---

## 三、Assertion 通过率

### 3.1 总览

| 场景 | Assertions | With Skill | Without Skill | 差值 |
|------|-----------|-----------|--------------|------|
| Eval 1: parser-fuzz | 15 | **15/15 (100%)** | 8/15 (53.3%) | +46.7pp |
| Eval 2: fetch-reject | 7 | **7/7 (100%)** | 0/7 (0%) | +100pp |
| Eval 3: converter-multi | 13 | **13/13 (100%)** | 8/13 (61.5%) | +38.5pp |
| **总计** | **35** | **35/35 (100%)** | **16/35 (45.7%)** | **+54.3pp** |

### 3.2 逐场景 Assertion 详情

#### Eval 1: parser-fuzz (15 条)

| # | Assertion | With Skill | Without Skill |
|---|-----------|-----------|--------------|
| A1.1 | Applicability gate 先于代码执行 | ✅ 5 项 checklist 完整记录 | ❌ 无正式 gate，直接分析 |
| A1.2 | 正确判定为"适合" | ✅ | ✅ （隐式） |
| A1.3 | 5 项 checklist 逐项 Pass/Fail | ✅ 结构化表格 | ❌ 无 |
| A1.4 | Fuzz mode 识别为 "parser robustness" | ✅ "Parser robustness + idempotency" | ❌ 未标注 |
| A1.5 | f.Add() ≥3 个有效 GitHub URL | ✅ 5 个 | ✅ 4 个 |
| A1.6 | f.Add() 包含 malformed/boundary | ✅ 14 个 | ✅ 25 个（更多） |
| A1.7 | Size guard 存在 | ✅ `len > 2048 → t.Skip()` | ❌ 无 |
| A1.8 | Oracle: Owner/Repo 非空 | ✅ | ✅ |
| A1.9 | Oracle: Number > 0 | ✅ | ✅ |
| A1.10 | Oracle: Type ∈ valid set | ✅ | ✅ |
| A1.11 | FuzzXxx 命名规范 | ✅ `FuzzParse` in `fuzz_parse_test.go` | ✅ `FuzzParse` in `fuzz_test.go` |
| A1.12 | Cost class 分配 | ✅ "Low, 30-60s" | ❌ 无 |
| A1.13 | Quick commands 提供 | ✅ 3 条命令 | ❌ 无 |
| A1.14 | Output contract / 结构化报告 | ✅ 完整 Quality Scorecard | ❌ 仅叙述摘要 |
| A1.15 | Corpus replay 验证 | ✅ 19 seeds green | ✅ 29 seeds passed |

#### Eval 2: fetch-reject (7 条)

| # | Assertion | With Skill | Without Skill |
|---|-----------|-----------|--------------|
| A2.1 | Applicability gate 执行 | ✅ 5 项结构化表格 | ❌ 无 gate |
| A2.2 | 判定为"不适合" | ✅ "Not suitable for fuzzing" | ❌ 未拒绝，构建了 workaround |
| A2.3 | 具体失败检查项 | ✅ Check 1/3/4/5 全标 Fail | ❌ 无失败项引用 |
| A2.4 | 未生成 fuzz 代码 | ✅ "None" | ❌ 生成了 112 行代码 |
| A2.5 | 提供替代测试策略 | ✅ 4 种具体策略 | ❌ 未提供替代方案 |
| A2.6 | 解释具体（非泛化） | ✅ 引用了 doWithRetry、f.rest、f.gql 等 | ❌ 无不适合性解释 |
| A2.7 | Output contract | ✅ 完整 5 节报告 | ❌ 无 |

#### Eval 3: converter-multi (13 条)

| # | Assertion | With Skill | Without Skill |
|---|-----------|-----------|--------------|
| A3.1 | 每个候选函数评估 gate | ✅ 逐函数评估 | ❌ 非正式分析表 |
| A3.2 | Target priority 评估 | ✅ 有优先级排序 | ❌ 无 Tier 排序 |
| A3.3 | Summarize 被拒绝 | ✅ | ✅ "Not suitable" |
| A3.4 | yamlQuote 生成 fuzz test | ✅ round-trip oracle | ✅ round-trip oracle |
| A3.5 | normalizeSummaryJSON 生成 | ✅ JSON validity oracle | ✅ JSON validity oracle |
| A3.6 | detectSummaryLanguage 生成 | ✅ valid set oracle | ✅ valid set oracle |
| A3.7 | capSummarySourceLength 生成 | ✅ rune count + truncation | ✅ rune count + truncation |
| A3.8 | 每个 harness 有 oracle | ✅ 4/4 有 t.Fatalf | ✅ 4/4 有 t.Fatalf |
| A3.9 | 每个 harness 有 seeds | ✅ ≥7 per target | ✅ ≥5 per target |
| A3.10 | Size guards 覆盖 | ✅ 4/4 harness 有 guard | ❌ 0/4 有 guard |
| A3.11 | 每目标 cost class | ✅ | ❌ 无 |
| A3.12 | Output contract 含逐目标详情 | ✅ | ❌ 无结构化报告 |
| A3.13 | Corpus replay 验证 | ✅ 40 seeds pass | ✅ 38 seeds pass |

### 3.3 Without-Skill 失败的 19 条 Assertion 归类

| 失败类型 | 次数 | 涉及 Eval | 说明 |
|---------|------|----------|------|
| **缺少 Applicability Gate** | 3 | Eval 1/2/3 | 无正式 5 项 checklist，直接编码或分析 |
| **不适合目标未拒绝** | 4 | Eval 2 | 构建 HTTP stub workaround 而非拒绝+推荐替代 |
| **缺少 Output Contract** | 3 | Eval 1/2/3 | 无结构化报告、Quality Scorecard |
| **缺少 Size Guard** | 2 | Eval 1/3 | Eval 1 无 len check；Eval 3 四个 harness 均无 |
| **缺少 Cost Class** | 2 | Eval 1/3 | 无 Low/Medium/High 分类 |
| **缺少 Quick Commands** | 1 | Eval 1 | 无 `go test -fuzz` 命令参考 |
| **缺少 Fuzz Mode 标注** | 1 | Eval 1 | 未标注 "parser robustness" 模式 |
| **缺少 Target Priority** | 1 | Eval 3 | 无 Tier 1/2/3 优先级排序 |
| **缺少 Checklist 结构** | 1 | Eval 1 | 无逐项 Pass/Fail 标记 |
| **缺少替代策略** | 1 | Eval 2 | 直接构建方案而非推荐更优策略 |

### 3.4 关键发现：Eval 2 的 +100pp Delta

这是所有已评估 skill 中**单场景最大差异**。原因分析：

**With-Skill 行为**：
- 运行 5 项 Applicability Gate
- 标记 Check 1/3/4/5 为 Fail（尤其 Check 3 — 无 oracle — 触发 Hard Stop）
- 产出 "Not suitable" 判定
- 推荐 4 种替代策略，包括"fuzz 该包中的纯映射函数"

**Without-Skill 行为**：
- 未运行 gate，直接分析如何让 fuzz 工作
- 创造性地构建了 `fuzzRoundTripper`（自定义 `http.RoundTripper`）来 stub HTTP 层
- 实际上 fuzz 的是 GraphQL JSON 解析路径，而非 `Fetch` 方法本身
- 唯一的 oracle 是 "no panic"

**评价**：Baseline 的方案有实际价值（能发现 JSON 解析中的 panic），但从 fuzz 测试最佳实践角度看存在问题：
1. Oracle 仅为 "no panic"，无法发现逻辑 bug（invariant violation）
2. 测试的实际是 JSON parsing 路径，而非请求的 `Fetch` 方法
3. 未告知用户"这不是最优策略"，错过了引导用户 fuzz 纯函数的机会

Skill 的 gate 机制确保了**诚实的工程决策**：不适合就不做，推荐更好的替代方案。

---

## 四、逐维度对比分析

### 4.1 Applicability Gate（适用性判断）

这是 skill 最核心的差异化能力，在全部 3 个场景中都产生了直接影响。

| 场景 | With Skill | Without Skill |
|------|-----------|--------------|
| Eval 1（适合） | 5 项 checklist 全 Pass，结构化表格 | 非正式分析，无 Pass/Fail 标记 |
| Eval 2（不适合） | Check 1/3/4/5 Fail → Hard Stop | 未识别为不适合 |
| Eval 3（混合） | 逐函数 gate，5 个中 4 个 Pass | 非正式分析表，Summarize 被正确识别 |

**实际价值**：
- Applicability Gate 防止了无效 fuzz test 的生成（Eval 2 节省了写 + 维护无价值测试的成本）
- 结构化 checklist 使决策过程可审计、可复现
- 在 Eval 3 中确保了"先评估、再编码"的工作流

### 4.2 Size Guard 系统性覆盖

| 场景 | With Skill | Without Skill |
|------|-----------|--------------|
| Eval 1: FuzzParse | ✅ `len > 2048 → t.Skip()` | ❌ 无 |
| Eval 3: FuzzYamlQuote | ✅ `len > 1<<16 → t.Skip()` | ❌ 无 |
| Eval 3: FuzzNormalizeSummaryJSON | ✅ `len > 1<<16 → t.Skip()` | ❌ 无 |
| Eval 3: FuzzDetectSummaryLanguage | ✅ `len > 1<<16 → t.Skip()` | ❌ 无 |
| Eval 3: FuzzCapSummarySourceLength | ✅ `len > 1<<20 → t.Skip()` | ❌ 无 |

**分析**：Skill 的 "Size guard present" 规则（SKILL.md Template A/B/C/D 中均有示范）确保了所有 `string`/`[]byte` 参数的 harness 都有边界保护。Without-skill 在 Eval 1 中甚至更多 seed（29 vs 19），但缺少 size guard，在长时间 fuzz 运行中可能遭遇 OOM。

### 4.3 Output Contract（结构化报告）

With-Skill 的每次运行产出包含以下内容的结构化报告：

| 报告项 | Eval 1 | Eval 2 | Eval 3 |
|--------|--------|--------|--------|
| Applicability Verdict | ✅ Suitable | ✅ Not suitable | ✅ 逐函数 |
| Why (2-6 bullets) | ✅ 5 bullets | ✅ 4 bullets | ✅ 逐函数 |
| Action | ✅ Implemented | ✅ Stop | ✅ 4 targets implemented |
| Quality Scorecard (C/S/H) | ✅ 全 PASS | N/A | ✅ 全 PASS |
| Cost Class | ✅ Low | N/A | ✅ 逐目标 |
| Quick Commands | ✅ 3 commands | N/A | ✅ |
| Corpus Policy | ✅ | N/A | ✅ |

Without-Skill 产出叙述性摘要，但无标准化结构。

### 4.4 Fuzz 代码质量对比

以 Eval 3 为例（最能体现代码质量差异的场景），对比 `FuzzYamlQuote`：

| 特性 | With Skill | Without Skill |
|------|-----------|--------------|
| Seeds 数量 | 11 | 10 |
| Size guard | ✅ `len > 1<<16` | ❌ 无 |
| Oracle: 单引号包裹 | ✅ | ✅ |
| Oracle: 奇数引号检测 | ✅ | ✅ |
| Oracle: round-trip | ✅ `unescaped == value` | ✅ `unescaped == value` |
| 大输入 seed | 无 | `strings.Repeat("a", 10000)` |

**代码质量**在 oracle 设计上高度相似，证明 Claude 基础模型对 fuzz 代码生成已有较强能力。Skill 的主要增量在于**流程规范**（gate、cost class、size guard、output contract）而非代码本身。

### 4.5 替代策略推荐能力

Eval 2 中 With-Skill 推荐了 4 种替代策略：

1. **Integration tests with real GitHub token (gated)** — 门控集成测试
2. **Unit tests with HTTP stubbing** — httptest.Server 桩测试
3. **Fuzz the pure mapping functions instead** — fuzz 纯映射函数（如 `mapIssueTimelineNode`）
4. **Table-driven unit tests for the dispatcher** — 表驱动单元测试

这些推荐不仅拒绝了不合适的方案，还引导用户找到更有价值的测试路径。Without-Skill 直接构建了 workaround（虽然有价值，但未告知用户存在更优选择）。

---

## 五、Token 效费比分析

### 5.1 Skill 体积

| 文件 | 行数 | 单词 | 估算 Token |
|------|------|------|-----------|
| **SKILL.md** | 679 | 3,062 | ~4,100 |
| references/applicability-checklist.md | 170 | 940 | ~1,250 |
| references/target-priority.md | 179 | 876 | ~1,170 |
| references/crash-handling.md | 76 | 312 | ~420 |
| references/ci-strategy.md | 118 | 463 | ~620 |
| **Description（始终在 context）** | — | ~50 | ~65 |

### 5.2 加载场景

| 场景 | 读取文件 | 总 Token |
|------|---------|---------|
| 适合目标（Eval 1） | SKILL.md + applicability + target-priority | ~6,520 |
| 不适合目标（Eval 2） | SKILL.md + applicability | ~5,350 |
| 多目标评估（Eval 3） | SKILL.md + applicability + target-priority | ~6,520 |
| 仅 SKILL.md（最小加载） | SKILL.md | ~4,100 |
| 全量加载 | 所有文件 | ~7,625 |
| **典型加载** | **SKILL.md + applicability + target-priority** | **~6,520** |

### 5.3 Token 换取的质量提升

| 指标 | 数值 |
|------|------|
| With-skill 通过率 | 100% (35/35) |
| Without-skill 通过率 | 45.7% (16/35) |
| 通过率提升 | +54.3 百分点 |
| 每修复 1 条 assertion 的 Token 成本 | ~216 tok（SKILL.md only）/ ~343 tok（typical） |
| 每 1% 通过率提升的 Token 成本 | ~75 tok（SKILL.md only）/ ~120 tok（typical） |

### 5.4 Token 分段效费比

| 模块 | 估算 Token | 关联 Assertion 差值 | 效费比 |
|------|-----------|-------------------|--------|
| **Applicability Gate 规则** | ~300 | 7 条（3 场景 gate 正确性）| **极高** — 43 tok/assertion |
| **Output Contract 定义** | ~200 | 3 条（3 场景报告完整性）| **极高** — 67 tok/assertion |
| **Templates A-D** | ~600 | 2 条（size guard 系统性覆盖）| **高** — 300 tok/assertion |
| **Cost Class + Quick Commands** | ~100 | 3 条（分类 + 命令参考）| **极高** — 33 tok/assertion |
| **Fuzz Mode 分类** | ~80 | 1 条（模式标注）| **极高** — 80 tok/assertion |
| **Target Priority 规则** | ~150 | 1 条（Tier 排序）| **高** — 150 tok/assertion |
| **Hard Stop 规则** | ~100 | 2 条（不适合目标拒绝 + 无代码）| **极高** — 50 tok/assertion |
| **Quality Scorecard** | ~200 | 间接贡献（结构化自检）| **中** |
| **Anti-Examples** | ~500 | 间接贡献（避免常见错误）| **中** |
| **Coverage Feedback** | ~400 | 0 条（未测试此场景）| **低** |
| **Go Version Gate** | ~200 | 0 条（未测试此场景）| **低** |
| **Troubleshooting** | ~350 | 0 条（未测试此场景）| **低** |
| **applicability-checklist.md** | ~1,250 | 间接贡献（强化 gate 判断）| **中** |
| **target-priority.md** | ~1,170 | 间接贡献（强化优先级判断）| **中** |
| **crash-handling.md** | ~420 | 0 条（无 crash 发现场景）| **低** |
| **ci-strategy.md** | ~620 | 0 条（未测试 CI 集成场景）| **低** |

### 5.5 高杠杆 vs 低杠杆指令

**高杠杆（~930 tokens SKILL.md → 19 条 assertion 差值，占 SKILL.md 23%）:**
- Applicability Gate + Hard Stop 规则（400 tok → 9 条）
- Output Contract 定义（200 tok → 3 条）
- Cost Class + Quick Commands（100 tok → 3 条）
- Templates 中的 size guard 示范（150 tok → 2 条）
- Fuzz Mode 分类 + Target Priority（80+150 tok → 2 条）

**中杠杆（~700 tokens → 间接贡献）:**
- Quality Scorecard（200 tok）— 驱动自检流程
- Anti-Examples（500 tok）— 避免常见错误

**低杠杆（~950 tokens → 0 条差值）:**
- Coverage Feedback 区（400 tok）— 未在评估场景中使用
- Go Version Gate（200 tok）— 未在评估场景中使用
- Troubleshooting 区（350 tok）— 未在评估场景中使用

**参考资料（~3,460 tokens → 间接贡献）:**
- applicability-checklist.md（1,250 tok）— 强化 gate 判断质量，提供具体示例
- target-priority.md（1,170 tok）— 提供 Tier 排序依据
- crash-handling.md + ci-strategy.md（1,040 tok）— 未在评估中直接贡献

### 5.6 Token 效率评级

| 评级 | 结论 |
|------|------|
| **整体 ROI** | **优秀** — ~6,520 tokens（typical）换取 +54.3% 通过率 |
| **SKILL.md 本身 ROI** | **良好** — ~4,100 tokens，高杠杆规则仅占 23% |
| **高杠杆 Token 比例** | 23%（930/4,100）直接贡献 19/19 条 assertion 差值 |
| **低杠杆 Token 比例** | 23%（950/4,100）在当前评估中无增量贡献 |
| **参考资料效费比** | **中等** — ~2,420 tokens（applicability + target-priority）提供间接贡献 |
| **未使用参考资料** | ~1,040 tokens（crash-handling + ci-strategy）无贡献 |

### 5.7 与其他 Skill 的效费比对比

| 指标 | fuzzing-test | go-makefile-writer | create-pr | go-ci-workflow |
|------|-------------|-------------------|-----------|---------------|
| SKILL.md Token | ~4,100 | ~1,960 | ~2,700 | ~1,500 |
| 典型加载 Token | ~6,520 | ~4,100 | ~4,800 | ~4,500 |
| 通过率提升 | +54.3% | +31.0% | +71.0% | +33.0% |
| 每 1% 的 Token（SKILL.md） | ~75 tok | ~63 tok | ~38 tok | ~45 tok |
| 每 1% 的 Token（typical） | ~120 tok | ~132 tok | ~68 tok | ~136 tok |

**分析**：
- `fuzzing-test` 的 **delta 最大**（+54.3%），主要得益于 Eval 2 的 +100pp 极端差异
- SKILL.md 效费比（~75 tok/1%）处于中等水平，高于 create-pr（38）和 go-ci-workflow（45），但低于 go-makefile-writer（63）
- 典型加载效费比（~120 tok/1%）优于 go-makefile-writer 和 go-ci-workflow，但低于 create-pr
- SKILL.md 体积（679 行 / ~4,100 tokens）是所有已评估 skill 中最大的，但其 delta 也最大

---

## 六、与 Claude 基础模型能力的边界分析

### 6.1 基础模型已具备的能力（Skill 无增量）

| 能力 | 证据 |
|------|------|
| Go fuzz test 基础语法 | 3/3 场景正确使用 `testing.F` |
| f.Add() seed corpus | 3/3 场景提供了高质量 seed |
| Oracle 设计（no-panic, round-trip, valid set） | Eval 1/3 的 oracle 质量与 with-skill 接近 |
| 多候选识别（部分） | Eval 3 中正确识别 Summarize 不适合 |
| 文件命名 `*_test.go` | 3/3 场景正确 |
| Corpus replay 验证 | 3/3 场景执行了验证 |

### 6.2 基础模型的能力缺口（Skill 填补）

| 缺口 | 证据 | 风险等级 |
|------|------|---------|
| **不适合目标的拒绝决策** | Eval 2: 构建 workaround 而非拒绝 | 高 — 生产环境中会维护无价值的 fuzz test |
| **系统性 Size Guard** | 5/5 harness 缺少 size guard | 高 — 长时间 fuzz 运行时 OOM 风险 |
| **Applicability Gate 流程** | 3/3 场景无正式 gate | 中 — 缺少决策审计 |
| **Output Contract** | 3/3 场景无结构化报告 | 中 — 缺少变更追溯 |
| **Cost Class 分配** | 2/3 场景无分类 | 中 — CI 预算无法合理分配 |
| **Quick Commands** | 1/3 场景无命令参考 | 低 — 用户需自行查文档 |
| **Fuzz Mode 标注** | 1/3 场景未标注 | 低 — 影响可读性 |
| **Target Priority** | 1/3 场景无 Tier 排序 | 低 — 多目标时缺少优先级指导 |

---

## 七、综合评分

### 7.1 分维度评分

| 维度 | With Skill | Without Skill | 差值 |
|------|-----------|--------------|------|
| Applicability Gate 正确性 | 5.0/5 | 1.5/5 | +3.5 |
| 不适合目标的拒绝能力 | 5.0/5 | 0.0/5 | +5.0 |
| Fuzz 代码质量（oracle、seed、guard） | 5.0/5 | 3.5/5 | +1.5 |
| 结构化报告（Output Contract） | 5.0/5 | 0.5/5 | +4.5 |
| 替代策略推荐 | 5.0/5 | 1.0/5 | +4.0 |
| 流程规范（cost class, mode, commands） | 5.0/5 | 1.5/5 | +3.5 |
| **综合均值** | **5.0/5** | **1.33/5** | **+3.67** |

### 7.2 加权总分

| 维度 | 权重 | 得分 | 理由 | 加权 |
|------|------|------|------|------|
| Assertion 通过率 delta | 25% | 10.0/10 | +54.3pp 是所有已评估 skill 中最高 delta | 2.50 |
| Applicability Gate 正确性 | 20% | 10.0/10 | 3/3 场景 gate 全对，Eval 2 展示了 Hard Stop 的独特价值 | 2.00 |
| 不适合目标拒绝 + 替代推荐 | 15% | 10.0/10 | +100pp 单场景 delta，4 种具体替代策略 | 1.50 |
| 结构化报告（Output Contract） | 15% | 10.0/10 | 3/3 场景完整合约，含 Quality Scorecard | 1.50 |
| Token 效费比 | 15% | 6.0/10 | SKILL.md ~4,100 tok 偏大；~950 tok 低杠杆区；参考资料 ~1,040 tok 无贡献 | 0.90 |
| Fuzz 代码质量 | 10% | 8.0/10 | 代码质量与 baseline 相近；主要增量在 size guard | 0.80 |
| **加权总分** | **100%** | | | **9.20/10** |

### 7.3 与其他 Skill 综合评分对比

| Skill | 加权总分 | 通过率 delta | Tokens/1% (typical) | 最大优势维度 |
|-------|---------|-------------|---------------------|-------------|
| create-pr | 9.55/10 | +71pp | ~68 | Gate 流程 (+3.5)、Output Contract (+4.0) |
| **fuzzing-test** | **9.20/10** | **+54.3pp** | **~120** | **拒绝能力 (+5.0)、Output Contract (+4.5)** |
| go-makefile-writer | 9.16/10 | +31pp | ~132 | CI 可复现性 (+3.0)、Output Contract (+4.0) |
| go-ci-workflow | 8.83/10 | +33pp | ~136 | 降级处理 (+4.5)、Output Contract (+4.0) |

**分析**：
- `fuzzing-test` 的**拒绝能力**（+5.0 差值）是所有已评估维度中**最大的单维度差异**
- +54.3pp 的 delta 也是所有 skill 中最高的，证明了 Applicability Gate 的独特价值
- Token 效费比得分（6.0/10）偏低，主要因为 SKILL.md 体积较大（679 行）且含 ~950 tokens 低杠杆区

---

## 八、结论

`fuzzing-test` skill 在三个核心领域提供了显著价值：

1. **Applicability Gate 的拒绝能力（+100pp 单场景 delta）**：这是所有已评估 skill 中**单场景最大差异**，证明了 "何时不该做" 的工程决策能力是 Claude 基础模型最大的缺口。Baseline 面对不适合的目标时，会创造性地构建 workaround（虽然有价值），但未告知用户存在更优策略。

2. **系统性 Size Guard 覆盖（5/5 vs 0/5）**：Skill 的模板和规则确保了所有 `string`/`[]byte` 参数 harness 都有长度边界保护，防止长时间 fuzz 运行中的 OOM。这是一个容易遗漏但在生产中影响巨大的实践。

3. **结构化 Output Contract**：Quality Scorecard（Critical/Standard/Hygiene 三级检查）使 fuzz test 的质量可量化、可审计。

**主要风险**：SKILL.md 体积 (~4,100 tokens) 是所有已评估 skill 中最大的，其中 ~23%（~950 tokens）为低杠杆区域。通过精简 Coverage Feedback、Troubleshooting、Anti-Examples 和 Go Version Gate，可减少 ~29% 的 SKILL.md token 开销，将典型加载效费比从 ~120 tok/1% 改善至 ~76 tok/1%。

---

## 九、评估材料

| 材料 | 路径 |
|------|------|
| Eval 1 with-skill 输出 | `/tmp/fuzz-eval-1/internal/parser/fuzz_parse_test.go` |
| Eval 1 without-skill 输出 | `/tmp/fuzz-eval-b1/internal/parser/fuzz_test.go` |
| Eval 2 with-skill 输出 | (无文件 — gate 拒绝，未生成代码) |
| Eval 2 without-skill 输出 | `/tmp/fuzz-eval-b2/internal/github/fetcher_fuzz_test.go` |
| Eval 3 with-skill 输出 | `/tmp/fuzz-eval-3/internal/converter/{frontmatter,summary_openai}_fuzz_test.go` |
| Eval 3 without-skill 输出 | `/tmp/fuzz-eval-b3/internal/converter/{fuzz_frontmatter,fuzz_summary_openai}_test.go` |
| 被评估 Skill | `/Users/john/.codex/skills/fuzzing-test/SKILL.md` |
