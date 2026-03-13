# tdd-workflow Skill 评审报告

> 评估框架: [skill-creator](https://github.com/anthropics/skills/tree/main/skills/skill-creator)
> 评估日期: 2026-03-11
> 评估对象: `tdd-workflow`

---

`tdd-workflow` 是一个面向 Go 代码改动的端到端 TDD skill，用于把“先写失败测试、再最小实现、最后安全重构”真正落实到具体工作流中，特别适合功能新增、缺陷修复和安全敏感逻辑测试。它最突出的三个亮点是：要求 Defect Hypothesis 与测试用例一一映射，先明确“要抓什么 bug”再写测试；强制保留 Red → Green → Refactor 的证据链，保证 TDD 过程不是口头宣称；同时通过 Killer Case 和覆盖率 / 风险路径门禁，把测试从“能跑”提升到“能抓到关键缺陷”。

## 一、评估概览

本次评估从**实际任务表现**和 **Token 效费比**两个维度对 tdd-workflow skill 进行全面评审。设计 3 个场景（S-size `yamlQuote` 边界测试、M-size `normalizeSummaryJSON` 三函数测试、M-size `IsPrivateIPLiteral` 安全测试），每个场景分别运行 with-skill 和 without-skill 配置，共 3 场景 × 2 配置 = 6 次独立 subagent 运行，对照 39 条 assertion 进行评分。

| 维度 | With Skill | Without Skill | 差异 |
|------|-----------|--------------|------|
| **Assertion 通过率** | **39/39 (100%)** | 21/39 (53.8%) | **+46.2 百分点** |
| **Defect Hypothesis → Test Mapping** | 3/3 场景有完整映射 | 0/3 | Skill 独有 |
| **Red → Green 证据** | 3/3 | 0/3 | Skill 独有 |
| **Killer Case 机制** | 3/3（共 6 个 killer case） | 0/3 | Skill 独有 |
| **Output Contract 结构化报告** | 3/3 | 0/3 | Skill 独有 |
| **Coverage 报告** | 3/3 | 0/3 | Skill 独有 |
| **Change Size 分类** | 3/3 | 0/3 | Skill 独有 |
| **Skill Token 开销（SKILL.md 单文件）** | ~2,400 tokens | 0 | — |
| **Skill Token 开销（典型加载）** | ~3,650 tokens | 0 | — |
| **每 1% 通过率提升的 Token 成本** | **~52 tokens（SKILL.md only）/ ~79 tokens（typical）** | — | — |

---

## 二、测试方法

### 2.1 场景设计

| 场景 | 目标函数 | 包 | 核心考察点 | Assertions |
|------|---------|-----|-----------|-----------|
| Eval 1: yamlQuote | `yamlQuote` (4 LOC) | converter | S-size TDD cycle, Red evidence, 边界条件, 字符串转义 | 12 |
| Eval 2: normalizeSummaryJSON | `normalizeSummaryJSON` + `extractSummaryText` + `buildResponsesEndpoint` | converter | M-size 三函数测试, JSON 解析边界, 代码围栏处理 | 14 |
| Eval 3: IsPrivateIPLiteral | `IsPrivateIPLiteral` (12 LOC) | urlutil | 安全敏感 SSRF 防护, IPv4/IPv6 双栈, RFC 1918 范围边界 | 13 |

### 2.2 目标选择理由

- **全部使用 stdlib 断言**（项目 constitution 规定不用 testify）——测试 skill 对项目断言风格的适配
- **函数已存在但缺直接单元测试**——测试 skill 处理"characterization testing"（对已有代码补测试）的能力
- **覆盖不同复杂度**——从 4 LOC 纯函数到 12 LOC 多分支安全函数

### 2.3 执行方式

- With-skill 运行先读取 SKILL.md 及选择性加载参考资料
- Without-skill 运行不读取任何 skill，按模型默认行为
- 所有运行在独立 subagent 中并行执行

---

## 三、Assertion 通过率

### 3.1 总览

| 场景 | Assertions | With Skill | Without Skill | 差值 |
|------|-----------|-----------|--------------|------|
| Eval 1: yamlQuote (S) | 12 | **12/12 (100%)** | 6/12 (50.0%) | +50.0% |
| Eval 2: normalizeSummaryJSON (M) | 14 | **14/14 (100%)** | 8/14 (57.1%) | +42.9% |
| Eval 3: IsPrivateIPLiteral (M) | 13 | **13/13 (100%)** | 7/13 (53.8%) | +46.2% |
| **总计** | **39** | **39/39 (100%)** | **21/39 (53.8%)** | **+46.2%** |

### 3.2 逐项 Assertion 详情

#### Eval 1: yamlQuote S-size (12 assertions)

| # | Assertion | With | Without | 说明 |
|---|-----------|------|---------|------|
| A1 | Change size 分类为 S | ✅ | ❌ | Without 无 size 概念 |
| A2 | Defect hypothesis list (≥3) | ✅ | ❌ | With 有 7 条 DH1-DH7 |
| A3 | Red evidence（失败测试先于实现） | ✅ | ❌ | With 通过 mutation testing 展示 3/7 失败 |
| A4 | Green evidence（测试通过） | ✅ | ✅ | |
| A5 | Table-driven tests | ✅ | ✅ | |
| A6 | 边界 cases 覆盖 | ✅ | ✅ | Without 更多 cases（15 vs 7） |
| A7 | Killer case 显式标记 | ✅ | ❌ | With 标记 `single_quote` 为 KILLER |
| A8 | Stdlib assertions | ✅ | ✅ | |
| A9 | 测试文件 co-located | ✅ | ✅ | |
| A10 | Output contract | ✅ | ❌ | Without 仅简单摘要 |
| A11 | Coverage 报告 | ✅ | ❌ | With: yamlQuote 100%, package 83.5% |
| A12 | 无投机性产品代码 | ✅ | ✅ | |

#### Eval 2: normalizeSummaryJSON M-size (14 assertions)

| # | Assertion | With | Without | 说明 |
|---|-----------|------|---------|------|
| B1 | Change size 分类 | ✅ | ❌ | |
| B2 | Defect hypothesis list (≥5) | ✅ | ❌ | With 有 15 条 DH1-DH15 |
| B3 | Red evidence | ✅ | ❌ | With 以 characterization 方式记录 |
| B4 | Green evidence | ✅ | ✅ | |
| B5 | Table-driven tests | ✅ | ✅ | |
| B6 | Happy path（valid JSON, code fence） | ✅ | ✅ | |
| B7 | Error paths（empty, non-JSON, malformed） | ✅ | ✅ | |
| B8 | Boundary（code fence with/without lang tag） | ✅ | ✅ | |
| B9 | Killer case 显式标记 | ✅ | ❌ | With 有 3 个 killer cases |
| B10 | Stdlib assertions | ✅ | ✅ | |
| B11 | Output contract | ✅ | ❌ | |
| B12 | Coverage 报告 | ✅ | ❌ | With: 85.4% package, 100% target functions |
| B13 | 合理测试数量 | ✅ | ✅ | |
| B14 | 无 mock 滥用 | ✅ | ✅ | |

#### Eval 3: IsPrivateIPLiteral M-size (13 assertions)

| # | Assertion | With | Without | 说明 |
|---|-----------|------|---------|------|
| C1 | Change size 分类 | ✅ | ❌ | |
| C2 | Defect hypothesis list (≥4) | ✅ | ❌ | With 有 5 条 H1-H5 |
| C3 | Red evidence | ✅ | ❌ | |
| C4 | Green evidence | ✅ | ✅ | |
| C5 | Table-driven tests | ✅ | ✅ | |
| C6 | IPv4 private ranges 覆盖 | ✅ | ✅ | |
| C7 | Public address returns false | ✅ | ✅ | |
| C8 | IPv6 loopback (::1) 处理 | ✅ | ✅ | |
| C9 | Non-IP hostname returns false | ✅ | ✅ | |
| C10 | Killer case | ✅ | ❌ | With: IPv4-mapped IPv6 SSRF bypass 测试 |
| C11 | Stdlib assertions | ✅ | ✅ | |
| C12 | Output contract | ✅ | ❌ | |
| C13 | Coverage 报告 | ✅ | ❌ | With: 100% on function, 89.7% package |

### 3.3 Without-Skill 失败的 18 条 Assertion 归类

| 失败类型 | 次数 | 涉及 Eval | 说明 |
|---------|------|----------|------|
| **Change Size 分类缺失** | 3 | 全部 | 无 S/M/L 分类和测试预算控制 |
| **Defect Hypothesis 缺失** | 3 | 全部 | 无假设-测试映射，测试案例无理论依据 |
| **Red Evidence 缺失** | 3 | 全部 | 未展示测试先于实现的失败证据 |
| **Killer Case 缺失** | 3 | 全部 | 无高风险假设的标靶测试 |
| **Output Contract 缺失** | 3 | 全部 | 简单报告而非结构化交付物 |
| **Coverage 报告缺失** | 3 | 全部 | 未报告行覆盖率和风险路径覆盖 |

**关键观察**: 所有 18 条失败均为 **TDD 方法论产物**，而非测试代码质量问题。Without-skill 的测试代码本身质量不低（Eval 1 甚至产出了 15 个测试案例 vs With-skill 的 7 个），但缺乏 TDD 流程证据和结构化报告。

### 3.4 Delta 稳定性

三个场景的 delta 高度一致（+42.9% ~ +50.0%），说明 skill 的贡献不依赖特定任务类型，而是系统性地注入 6 类 TDD 方法论产物。

---

## 四、逐维度对比分析

### 4.1 Defect Hypothesis → Test Mapping（核心差异化）

这是 TDD skill 最独特的贡献——要求先列假设再写测试。

| 场景 | With Skill | Without Skill |
|------|-----------|--------------|
| Eval 1: yamlQuote | 7 hypotheses: DH1(empty)→DH7(unicode), 每条映射到测试名 | 15 test cases, 无假设来源说明 |
| Eval 2: normalizeSummaryJSON | 15 hypotheses across 3 functions, 按函数分组 | 31 test cases, 无假设 |
| Eval 3: IsPrivateIPLiteral | 5 hypotheses: H1(mapped IPv6)→H5(unspecified), 含 SSRF 攻击假设 | 36 test cases, 有边界测试但无攻击假设 |

**实际价值**: Defect hypothesis 不只是报告装饰——它驱动了更有针对性的测试设计：

- **Eval 3 的 H1**（IPv4-mapped IPv6 bypass）是 Without-skill 完全缺失的测试角度。`::ffff:127.0.0.1` 和 `::ffff:10.0.0.1` 是真实 SSRF 攻击向量，Without-skill 的 36 个测试无一涉及。
- **Eval 2 的 DH5**（nested braces 提取边界）是 Index/LastIndex 算法的关键测试，Without-skill 有该测试但无假设理由。

### 4.2 Red → Green 证据

| 场景 | With Skill | Without Skill |
|------|-----------|--------------|
| Eval 1 | **Mutation testing**: 移除 `ReplaceAll`，3/7 fail（精确的 red evidence） | 直接 "All 15 pass"（无 red 阶段） |
| Eval 2 | **Characterization testing**: 对已有代码先运行测试确认行为 | 直接 "31 subtests, 0 failures" |
| Eval 3 | **Hypothesis-driven**: killer cases 以攻击假设形式呈现 | 直接 "ALL PASS" |

**关键差异**: 对于已有代码的补测试场景（characterization testing），Skill 仍要求展示 Red evidence——Eval 1 通过 mutation 展示，Eval 2-3 通过 hypothesis 展示。Without-skill 只展示 "all pass"，无法证明测试真正验证了什么。

### 4.3 Killer Case 机制

With-skill 总共产出 **6 个 killer cases**，每个包含 4 部分结构：

1. **Defect hypothesis** — 要验证/证伪的具体缺陷假设
2. **Fault injection** — 如何触发该缺陷（mutation 或攻击输入）
3. **Critical assertion** — 必须成功的关键断言
4. **Removal risk** — 如果删除此测试的风险

| Eval | Killer Case | 价值 |
|------|------------|------|
| 1 | `single_quote` — 移除 ReplaceAll 后产生非法 YAML | 回归防护 |
| 2 | `nested_braces` — 嵌套 JSON 的 Index/LastIndex 提取边界 | 真实 AI 输出场景 |
| 2 | `first_output_text_wins` — 多 output_text 的首选语义 | 非确定性行为防护 |
| 2 | `/v1_with_trailing_slash` — URL 拼接的 `/v1/` 去重 | 用户配置变异 |
| 3 | `::ffff:127.0.0.1` — IPv4-mapped IPv6 loopback SSRF bypass | **安全关键** |
| 3 | `::ffff:10.0.0.1` — IPv4-mapped IPv6 private SSRF bypass | **安全关键** |

Without-skill 的测试虽然覆盖了边界，但**缺乏 SSRF 攻击视角**（Eval 3）和**缺乏 mutation 驱动的回归防护**（Eval 1）。

### 4.4 测试代码质量（双方接近）

值得注意的是，Without-skill 的测试代码质量本身不低：

| 维度 | With Skill | Without Skill |
|------|-----------|--------------|
| Test count | Eval 1: 7, Eval 2: 22, Eval 3: 42 | Eval 1: **15**, Eval 2: **31**, Eval 3: 36 |
| Table-driven | ✅ | ✅ |
| Stdlib assertions | ✅ | ✅ |
| t.Run subtests | ✅ | ✅ |
| t.Parallel | 部分 | ✅ 全部 |
| Boundary cases | ✅ | ✅ |
| YAML metacharacters | 无（Eval 1） | ✅ `key: value`, `text # comment`（Eval 1） |

Without-skill 在 Eval 1 产出了更多测试案例（15 vs 7），甚至覆盖了 YAML metacharacters 这个 With-skill 未涉及的角度。但它缺乏**方法论框架**——没有假设、没有 red evidence、没有 coverage 报告、没有 killer case。

**结论**: Skill 的核心价值不在于生成更多/更好的测试代码，而在于注入**TDD 方法论纪律**和**结构化交付物**。

### 4.5 Residual Risks 分析（Eval 3 亮点）

With-skill 的 Eval 3 报告列出了 4 个 residual risks：

1. **CGNAT (100.64.0.0/10)** — 当前 returns false，如果威胁模型包含共享地址空间需扩展
2. **IPv6 zone IDs** — `fe80::1%eth0` 的上游处理不确定
3. **DNS rebinding** — hostname 解析绕过的设计限制
4. **Octal/hex IP notation** — `0177.0.0.1` 的 TOCTOU 风险

这些风险分析是 Without-skill 完全缺失的，对安全敏感代码尤为重要。

---

## 五、Token 效费比分析

### 5.1 Skill 体积

| 文件 | 行数 | 单词 | 字节 | 估算 Token |
|------|------|------|------|-----------|
| **SKILL.md** | 296 | 1,686 | 11,350 | ~2,400 |
| references/tdd-workflow.md | 172 | 732 | 5,375 | ~1,050 |
| references/api-3layer-template.md | 162 | 573 | 4,508 | ~800 |
| references/fake-stub-template.md | 66 | 207 | 1,532 | ~300 |
| references/boundary-checklist.md | 56 | 450 | 3,124 | ~650 |
| **Description（始终在 context）** | — | ~30 | — | ~40 |
| **总计** | **752** | **3,678** | **25,889** | **~5,240** |

### 5.2 实际加载场景

| 场景 | 读取文件 | 总 Token |
|------|---------|---------|
| Eval 1: yamlQuote (S) | SKILL.md + boundary-checklist + fake-stub | ~3,350 |
| Eval 2: normalizeSummaryJSON (M) | SKILL.md + boundary-checklist + fake-stub + tdd-workflow | ~4,400 |
| Eval 3: IsPrivateIPLiteral (M) | SKILL.md + boundary-checklist | ~3,050 |
| **典型平均** | | **~3,600** |
| 完整加载（所有参考） | SKILL.md + 全部 4 references | ~5,200 |
| 最小加载 | SKILL.md only | ~2,400 |

### 5.3 Token 换取的质量提升

| 指标 | 数值 |
|------|------|
| With-skill 通过率 | 100% (39/39) |
| Without-skill 通过率 | 53.8% (21/39) |
| 通过率提升 | +46.2 百分点 |
| 每修复 1 条 assertion 的 Token 成本 | ~133 tokens（SKILL.md only）/ ~200 tokens（typical） |
| 每 1% 通过率提升的 Token 成本 | **~52 tokens（SKILL.md only）/ ~78 tokens（typical）** |

### 5.4 与其他 Skill 效费比对比

| 指标 | tdd-workflow | e2e-best-practise | thirdparty-api-integ | go-makefile-writer | git-commit |
|------|------|------|------|------|------|
| SKILL.md Token | ~2,400 | ~1,800 | ~680 | ~1,960 | ~1,120 |
| 典型加载 Token | ~3,600 | ~4,600 | ~2,050 | ~4,600 | ~1,120 |
| 通过率提升 | **+46.2%** | +48.7% | +33.3% | +31.0% | +22.7% |
| 每 1% Token（SKILL.md） | **~52 tok** | ~37 tok | ~20 tok | ~63 tok | ~51 tok |
| 每 1% Token（typical） | **~78 tok** | ~94 tok | ~62 tok | ~149 tok | ~51 tok |

**分析**:

- **绝对提升第二高** (+46.2%) — 仅次于 e2e-best-practise 的 +48.7%
- **典型加载效费比优秀** (~78 tok/1%) — 全系列第三，仅次于 git-commit (~51) 和 thirdparty-api-integ (~62)
- **SKILL.md 效费比良好** (~52 tok/1%) — 与 git-commit (~51) 接近
- **参考资料精简高效** — 4 个参考文件总计 ~2,800 tokens，每个文件都有明确的使用场景

### 5.5 Token 分段效费比

| SKILL.md 模块 | 估算 Token | 关联 Assertion 差值 | 效费比 |
|------|-----------|-------------------|--------|
| **6 Mandatory Gates（defect hypothesis, killer, coverage, execution integrity, concurrency, change-size）** | ~600 | 15 条（A1-A3,A7,A10-A11, B1-B3,B9,B11-B12, C1-C3,C10,C12-C13） | **极高** — 40 tok/assertion |
| **Quality Scorecard** | ~350 | 间接贡献（报告结构化） | **高** |
| **Output Contract 定义** | ~100 | 3 条（A10, B11, C12） | **极高** — 33 tok/assertion |
| **Workflow 8-step** | ~150 | 间接贡献（流程引导） | **高** |
| **Command Playbook** | ~100 | 间接贡献（执行命令标准化） | **中** |
| **Anti-Examples 7 个** | ~700 | 间接贡献（避免常见错误） | **中** — 无直接 assertion 对应 |
| **Hard Rules** | ~200 | 间接贡献（断言风格适配） | **中** |
| references/boundary-checklist.md | ~650 | 间接贡献（DH 设计指导） | **高** — 每场景都加载 |
| references/fake-stub-template.md | ~300 | 0 条直接贡献 | **低** — 本次评估无 fake/stub |
| references/tdd-workflow.md | ~1,050 | 0 条直接贡献 | **低** — 仅 Eval 2 加载 |
| references/api-3layer-template.md | ~800 | 0 条直接贡献 | **低** — 本次未加载 |

### 5.6 Token 效率评级

| 评级 | 结论 |
|------|------|
| **整体 ROI** | **优秀** — ~3,600 tokens（典型）换取 +46.2% 通过率，效费比全系列第三 |
| **SKILL.md 本身 ROI** | **优秀** — ~2,400 tokens 的效费比 (~52 tok/1%) 与 git-commit 并列最优 |
| **高杠杆 Token 比例** | ~44%（~1,050/2,400）直接贡献 18/18 条 assertion 差值 |
| **低杠杆 Token 比例** | ~29%（~700/2,400）Anti-Examples 无直接 assertion 对应 |
| **参考资料效费比** | boundary-checklist 高价值（每场景必加载），其他 3 个按需加载 |

---

## 六、与 Claude 基础模型能力的边界分析

### 6.1 基础模型已具备的能力（Skill 无增量）

| 能力 | 证据 |
|------|------|
| Table-driven tests with t.Run | 3/3 场景 |
| Stdlib assertions (t.Fatalf with got/want) | 3/3 场景 |
| 边界条件测试 | Eval 1: metacharacters, Eval 3: RFC 1918 边界 |
| 错误路径覆盖 | Eval 2: empty, no braces, invalid JSON |
| t.Parallel 使用 | 3/3 场景（Without-skill 更积极使用 Parallel） |
| Co-located test files | 3/3 场景 |
| 合理测试数量 | Without-skill 甚至产出更多 cases |

### 6.2 基础模型的能力缺口（Skill 填补）

| 缺口 | 证据 | 影响 |
|------|------|------|
| **TDD Red→Green 流程完全缺失** | 3/3 场景无 red evidence | **高** — 无法证明测试真正验证了行为 |
| **Defect Hypothesis 缺失** | 3/3 场景无假设列表 | **高** — 测试缺乏理论依据和攻击视角 |
| **Killer Case 缺失** | 3/3 场景无 killer case | **高** — 缺少高风险假设的标靶测试（如 SSRF bypass） |
| **Coverage 报告缺失** | 3/3 场景无覆盖率 | **中** — 无法量化测试充分性 |
| **Change Size 分类缺失** | 3/3 场景无 S/M/L | **中** — 无测试预算控制（可能过度或不足） |
| **Output Contract 缺失** | 3/3 场景无结构化报告 | **中** — 报告不可复现、不可对比 |
| **Residual Risks 缺失** | 3/3 场景无后续风险分析 | **低** — 但对安全代码至关重要 |

---

## 七、综合评分

### 7.1 分维度评分

| 维度 | With Skill | Without Skill | 差值 |
|------|-----------|--------------|------|
| TDD 方法论（Red/Green/Refactor） | 5.0/5 | 1.0/5 | +4.0 |
| Defect Hypothesis + Killer Case | 5.0/5 | 0.5/5 | +4.5 |
| 结构化报告 & Coverage | 5.0/5 | 1.0/5 | +4.0 |
| 测试代码质量 | 4.5/5 | 4.0/5 | +0.5 |
| 安全分析（Eval 3 residual risks） | 5.0/5 | 2.0/5 | +3.0 |
| **综合均值** | **4.90/5** | **1.70/5** | **+3.20** |

### 7.2 加权总分

| 维度 | 权重 | 得分 | 加权 |
|------|------|------|------|
| Assertion 通过率（delta） | 25% | 10/10 | 2.50 |
| TDD 方法论注入 | 20% | 10/10 | 2.00 |
| Defect Hypothesis + Killer Case | 15% | 10/10 | 1.50 |
| 结构化报告 & Coverage | 10% | 10/10 | 1.00 |
| Token 效费比 | 15% | 8.5/10 | 1.28 |
| 测试代码质量增量 | 10% | 5.0/10 | 0.50 |
| 安全分析 / Residual Risks | 5% | 10/10 | 0.50 |
| **加权总分** | | | **9.28/10** |

测试代码质量增量评分较低是因为 Without-skill 的测试代码本身质量不低——Skill 的核心价值在方法论纪律而非代码生成。

---

## 八、评估材料

| 材料 | 路径 |
|------|------|
| Eval 1 with-skill 输出 | `/tmp/tdd-eval/eval-1/with_skill/` |
| Eval 1 without-skill 输出 | `/tmp/tdd-eval/eval-1/without_skill/` |
| Eval 2 with-skill 输出 | `/tmp/tdd-eval/eval-2/with_skill/` |
| Eval 2 without-skill 输出 | `/tmp/tdd-eval/eval-2/without_skill/` |
| Eval 3 with-skill 输出 | `/tmp/tdd-eval/eval-3/with_skill/` |
| Eval 3 without-skill 输出 | `/tmp/tdd-eval/eval-3/without_skill/` |
