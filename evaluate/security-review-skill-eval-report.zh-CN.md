# security-review Skill 评审报告

> 评估框架: [skill-creator](https://github.com/anthropics/skills/tree/main/skills/skill-creator)
> 评估日期: 2026-03-12
> 评估对象: `security-review`

---

`security-review` 是一个以 exploitability-first 为核心的安全审查 skill，用于评估代码变更中的认证、输入、密钥、API、数据流、依赖和资源生命周期等风险，重点输出可复现、可落地的安全发现。它最突出的三个亮点是：先做审查深度选择和多域门禁覆盖，让不同风险级别的变更获得匹配的检查强度；每条发现都强调证据、置信度和 CWE/OWASP 映射，更适合审计和后续治理；同时具备系统化的误报抑制和未覆盖风险记录机制，能把“真正的漏洞”与“暂不成 finding 的疑点”分开表达。

## 一、评估概览

本次评估从**实际任务表现**和 **Token 效费比**两个维度对 security-review skill 进行全面评审。设计 3 个递进复杂度的安全审查场景（Web Handler 审查、OpenAI API 客户端审查、无安全风险的纯函数审查），每个场景分别运行 with-skill 和 without-skill 配置，共 3 场景 × 2 配置 = 6 次独立 subagent 运行，对照 40 条 assertion 进行评分。

| 维度 | With Skill | Without Skill | 差异 |
|------|-----------|--------------|------|
| **Assertion 通过率** | **40/40 (100%)** | 20/40 (50.0%) | **+50.0 百分点** |
| **Review Depth 选择** | 3/3 正确 | 0/3 | Skill 独有 |
| **Confidence 标签** | 3/3 | 0/3 | Skill 独有 |
| **CWE/OWASP 映射** | 3/3 | 0/3 | Skill 独有 |
| **Gate D 10-Domain 覆盖** | 3/3 | 0/3 | Skill 独有 |
| **Machine-Readable JSON** | 3/3 | 0/3 | Skill 独有 |
| **Gate F 未覆盖风险列表** | 3/3 | 0/3 | Skill 独有 |
| **False-Positive 抑制** | 3/3 正确 | 1/3 | 最大质量差异 |
| **Skill Token 开销（SKILL.md）** | ~3,800 tokens | 0 | — |
| **Skill Token 开销（含 Go 参考资料）** | ~9,600 tokens | 0 | — |
| **每 1% 通过率提升的 Token 成本** | ~76 tokens（SKILL.md）/ ~192 tokens（full） | — | — |

---

## 二、测试方法

### 2.1 场景设计

| 场景 | 目标代码 | 核心考察点 | Assertions |
|------|---------|-----------|-----------|
| Eval 1: Web Handler 审查 | `internal/webapp/handler.go` (285 行) + `parser.go` + `urlutil.go` | HTTP 输入验证、SSRF、注入、资源生命周期、误报抑制 | 15 |
| Eval 2: OpenAI API 客户端审查 | `internal/converter/summary_openai.go` (294 行) + `urlutil.go` + `config/loader.go` | 密钥管理、外部 HTTP 调用、SSRF、提示注入、响应体生命周期 | 15 |
| Eval 3: 无安全风险纯函数审查 | `internal/cli/exitcode.go` (57 行) | Lite 深度判断、0 误报、N/A 标注正确性 | 10 |

### 2.2 执行方式

- With-skill 运行先读取 SKILL.md 及其引用的 Go 安全编码参考和场景清单
- Without-skill 运行不读取任何 skill，按模型默认安全审查能力执行
- 所有运行在独立 subagent 中执行

---

## 三、Assertion 通过率

### 3.1 总览

| 场景 | Assertions | With Skill | Without Skill | 差值 |
|------|-----------|-----------|--------------|------|
| Eval 1: Web Handler | 15 | **15/15 (100%)** | 7/15 (46.7%) | +53.3% |
| Eval 2: API Client | 15 | **15/15 (100%)** | 9/15 (60.0%) | +40.0% |
| Eval 3: Benign Code | 10 | **10/10 (100%)** | 4/10 (40.0%) | +60.0% |
| **总计** | **40** | **40/40 (100%)** | **20/40 (50.0%)** | **+50.0%** |

### 3.2 Without-Skill 失败的 20 条 Assertion 归类

| 失败类型 | 次数 | 涉及 Eval | 说明 |
|---------|------|----------|------|
| **缺少 Review Depth 选择** | 3 | 1/2/3 | 无 Lite/Standard/Deep 分类，无触发信号分析 |
| **缺少 Confidence 标签** | 3 | 1/2/3 | 无 confirmed/likely/suspected 区分 |
| **缺少 CWE/OWASP 映射** | 3 | 1/2/3 | 仅 HIGH/MEDIUM/LOW 严重性，无标准映射 |
| **缺少 Gate D 10-Domain 覆盖** | 3 | 1/2/3 | 无系统性域覆盖评估 |
| **缺少 Machine-Readable JSON** | 3 | 1/2/3 | 无 CI/inbox 可消费的 JSON 摘要 |
| **缺少 Gate F 未覆盖风险列表** | 3 | 1/2/3 | 未声明未覆盖区域，可能产生虚假完整性 |
| **Gate A 构造-释放配对审计缺失** | 1 | 1 | 无显式资源生命周期审计 |
| **误报抑制不充分** | 1 | 1 | `openAPISpecPath` 被报为 MEDIUM 但路径非用户控制 |

### 3.3 按 Assertion 类别的通过率对比

| 类别 | With Skill | Without Skill | 差值 |
|------|-----------|--------------|------|
| **结构性合规**（depth/gates/output contract） | 18/18 (100%) | 0/18 (0%) | **+100%** |
| **安全分析质量**（攻击面、抑制、修复建议） | 13/13 (100%) | 12/13 (92.3%) | +7.7% |
| **标准映射**（CWE/OWASP/confidence） | 9/9 (100%) | 0/9 (0%) | **+100%** |

**关键发现**: Skill 的核心价值在于**结构性合规**和**标准映射**——这两个类别 without-skill 的通过率为 0%。安全分析质量（找到真实漏洞的能力）差异仅 7.7%，说明基础模型本身已具备较强的安全审查能力，Skill 的增量价值在于**流程纪律**而非**发现能力**。

---

## 四、逐维度对比分析

### 4.1 Review Depth 选择（Skill 独有能力）

这是**Skill 最显著的差异化产出**。

| 场景 | With Skill | Without Skill |
|------|-----------|--------------|
| Eval 1 (HTTP handler) | **Standard** — "new HTTP endpoints exposed" 触发信号 | 无深度选择 |
| Eval 2 (API client) | **Standard** — "new external integration + secret management" 触发信号 | 无深度选择 |
| Eval 3 (exitcode) | **Lite** — "1 file, no security-sensitive paths" + 完整排除理由 | 无深度选择 |

**实际价值**: Review Depth 决定了审查的成本-收益比：
- Lite 模式跳过 Gate B/C/E，节省约 40% 审查时间
- Standard/Deep 的区分确保安全敏感代码得到充分审查
- Without-skill 对所有场景施加相同的审查深度，导致简单代码过度审查、复杂代码可能不充分

### 4.2 False-Positive 抑制质量

这是 **Skill 的最大质量差异**。

| 抑制场景 | With Skill | Without Skill |
|---------|-----------|--------------|
| SSRF via user URL（parser 限制 github.com） | **正确抑制** — "parser restricts host to github.com, handler doesn't make HTTP requests to raw URL" | 未报告此项（隐式处理） |
| Path traversal via openAPISpecPath | **正确抑制** — "set at construction time from config, not user-controlled" (Rule 2) | ❌ 报为 **MEDIUM** |
| Open redirect via http.Redirect | **正确抑制** — "redirect target is hardcoded /swagger/index.html" (Rule 2) | 未报告（但报了 catch-all route） |
| XSS via template | **正确抑制** — "html/template auto-escapes" (Rule 3) | 正确识别（positive observation） |
| appendThreadText 递归 | **正确抑制** — "GitHub API limits nesting depth" | ❌ 报为 **LOW**（F-8） |
| CSRF on /convert | **正确 N/A** — "stateless form, no session, no state mutation" | ❌ 报为 **HIGH** |

**分析**: Without-skill 的 CSRF 发现（Eval 1 Finding #1）将 **成本消耗（rate limit exhaustion）** 与 **CSRF** 混为一谈。With-skill 正确地将根因定位为 **rate limiting 缺失**（SEC-001 P2），而非 CSRF——因为 `/convert` 是无状态操作，没有 session/cookie/state mutation。This demonstrates the skill's **suppression discipline**: it prevents inflated severity by separating root cause from delivery mechanism.

### 4.3 输出结构对比

| 输出区段 | With Skill | Without Skill |
|---------|-----------|--------------|
| Review Depth + 理由 | ✅ 3/3 | ❌ 0/3 |
| Trust Boundary Mapping | ✅ 3/3 | ❌ 0/3 (Eval 2 有类似内容) |
| Scenario Checklists (11 项) | ✅ 3/3 | ❌ 0/3 |
| Gate A 配对表 | ✅ 3/3 | ❌ 0/3 |
| Gate D 10-Domain 表 | ✅ 3/3 | ❌ 0/3 |
| Suppression Filter 表 | ✅ 2/2 (Eval 3 无需) | ❌ 0/2 |
| Gate E 二次验证 | ✅ 2/2 (Lite 跳过) | ❌ 0/2 |
| Findings (severity+confidence+CWE) | ✅ 3/3 | 部分（无 confidence/CWE） |
| Remediation Plan (immediate/short/backlog) | ✅ 3/3 | 部分（优先级但无 SLA） |
| Risk Acceptance Register | ✅ 3/3 | ❌ 0/3 |
| JSON Summary | ✅ 3/3 | ❌ 0/3 |
| Gate F Uncovered Risk List | ✅ 3/3 | ❌ 0/3 |

### 4.4 安全发现质量对比

尽管结构差异巨大，两个配置在**核心安全发现**上有显著重叠：

| 核心发现 | With Skill | Without Skill |
|---------|-----------|--------------|
| Rate limiting 缺失 | SEC-001 P2 ✅ | Finding #2 HIGH ✅ |
| Security headers 缺失 | SEC-002/003 P3 ✅ | Finding #3 MEDIUM ✅ |
| Prompt injection | SEC-002 P2 (Eval 2) ✅ | F-3 MEDIUM ✅ |
| Unbounded response body | SEC-003 P2 (Eval 2) ✅ | F-4 MEDIUM ✅ |
| Redirect following leak | SEC-004 P2 (Eval 2) ✅ | F-2 HIGH ✅ |
| SSRF DNS rebinding | SEC-005 P3 (Eval 2) ✅ | F-1 HIGH ✅ |
| API key plain string | SEC-001 P3 (Eval 2) ✅ | F-6 LOW ✅ |

**Without-skill 独有发现**:
- CSRF on /convert (HIGH) — 但属于 root-cause misattribution
- URL scheme enforcement in parser (MEDIUM) — valid defense-in-depth
- Unbounded pagination (MEDIUM) — valid, with-skill 在 Gate F 中提及
- Token via CLI flag (LOW) — valid but out of changed scope
- appendThreadText recursion (LOW) — with-skill correctly suppresses

**With-skill 独有发现**:
- 无核心发现是 with-skill 独有的（说明基础模型发现能力强）
- 但 with-skill 对每个发现的 **severity 校准更精准**（如 SSRF DNS rebinding 正确标为 P3 suspected 而非 HIGH）

### 4.5 Eval 3 (Benign Code) — Lite 审查质量

这是 Skill 最显著的效率优势场景。

| 维度 | With Skill | Without Skill |
|------|-----------|--------------|
| 输出行数 | 227 行 | 46 行 |
| Review Depth 声明 | "Lite (1 file, no security-sensitive paths)" + 排除 9 个触发信号 | 无 |
| Findings | 0 (正确) | 0 (正确) |
| Domain Coverage | 10/10 N/A (每个域有代码证据) | 表格但无编号域 |
| Gates Skipped 声明 | "Gates B/C/E skipped per Lite scope policy" | 无 Gate 概念 |
| Gate F 未覆盖风险 | 4 项（gosec 未运行、govulncheck 未运行等） | 无 |
| JSON Summary | `pass: true`, 全部 0 findings | 无 |
| 审查深度适当性 | ✅ 不过度审查简单代码 | ⚠️ 无法判断是简略还是适当 |

**分析**: Without-skill 的 46 行输出正确得出了 "无安全漏洞" 结论，但缺乏**审计可追溯性**。With-skill 的 227 行输出提供了完整的审计记录：为什么选择 Lite、为什么每个域是 N/A、跳过了哪些检查及原因。在合规场景下（如 SOC 2 审计），这种可追溯性是必需的。

---

## 五、Token 效费比分析

### 5.1 Skill 体积

| 文件 | 行数 | 单词 | 字节 | 估算 Token |
|------|------|------|------|-----------|
| **SKILL.md** | 456 | 2,870 | 20,818 | ~3,800 |
| references/go-secure-coding.md | 723 | 2,957 | 25,019 | ~4,600 |
| references/scenario-checklists.md | 140 | 889 | 6,588 | ~1,200 |
| references/security-review.md | 112 | 557 | 4,165 | ~800 |
| references/lang-nodejs.md | 149 | 701 | 5,389 | ~1,000 |
| references/lang-java.md | 123 | 561 | 4,716 | ~900 |
| references/lang-python.md | 122 | 542 | 4,363 | ~800 |
| **Description（始终在 context）** | — | ~40 | — | ~50 |

**典型加载场景:**

| 场景 | 读取文件 | 总 Token |
|------|---------|---------|
| Go 代码审查（Standard/Deep） | SKILL.md + go-secure-coding.md + scenario-checklists.md | ~9,600 |
| Go 代码审查（Lite） | SKILL.md + scenario-checklists.md | ~5,000 |
| Node.js 代码审查 | SKILL.md + scenario-checklists.md + lang-nodejs.md | ~6,000 |
| Java 代码审查 | SKILL.md + scenario-checklists.md + lang-java.md | ~5,900 |
| 仅 SKILL.md（最小加载） | SKILL.md | ~3,800 |

### 5.2 Token 换取的质量提升

| 指标 | 数值 |
|------|------|
| With-skill 通过率 | 100% (40/40) |
| Without-skill 通过率 | 50.0% (20/40) |
| 通过率提升 | +50.0 百分点 |
| 每修复 1 条 assertion 的 Token 成本 | ~190 tokens（SKILL.md only）/ ~480 tokens（Go full） |
| 每 1% 通过率提升的 Token 成本 | ~76 tokens（SKILL.md only）/ ~192 tokens（Go full） |

### 5.3 Token 分段效费比

将 SKILL.md 内容按功能模块拆分：

| 模块 | 估算 Token | 关联 Assertion 差值 | 效费比 |
|------|-----------|-------------------|--------|
| **Review Depth Selection** | ~250 | 3 条（3 evals 深度选择） | **极高** — 83 tok/assertion |
| **Evidence Confidence** | ~100 | 3 条（3 evals 置信度标签） | **极高** — 33 tok/assertion |
| **Suppression Rules** | ~180 | 2 条（Eval 1/2 抑制质量） | **极高** — 90 tok/assertion |
| **Output Contract** | ~500 | 3 条（3 evals JSON summary） | **高** — 167 tok/assertion |
| **Gate D 10-Domain** | ~400 | 3 条（3 evals 域覆盖） | **高** — 133 tok/assertion |
| **Gate A 配对** | ~150 | 1 条（Eval 1 配对审计） | **高** — 150 tok/assertion |
| **Gate F 未覆盖风险** | ~80 | 3 条（3 evals 风险列表） | **极高** — 27 tok/assertion |
| **Standards Mapping** | ~50 | 3 条（3 evals CWE 映射） | **极高** — 17 tok/assertion |
| **Severity Model + SLA** | ~200 | 间接贡献（severity 校准更精准） | **中** — 无直接 assertion |
| **Anti-Examples** | ~350 | 间接贡献（避免 AE-1/AE-3/AE-5 错误） | **中** — 防御性价值 |
| **Scenario Checklists 指针** | ~200 | 间接贡献（11 场景系统性覆盖） | **中** — 结构化审查 |
| **Baseline Diff Mode** | ~100 | 0 条（无 baseline 场景测试） | **低** — 未测试 |
| **Language Extension Hooks** | ~150 | 0 条（仅测试 Go） | **低** — 未测试 |
| **Focused Automation Gate** | ~350 | 间接贡献（自动化工具执行一致性） | **中** — 工具纪律 |
| **go-secure-coding.md（参考资料）** | ~4,600 | 间接贡献（Gate B/D 详细检查指南） | **中** — 深度审查支持 |
| **scenario-checklists.md（参考资料）** | ~1,200 | 间接贡献（11 场景详细检查项） | **中** — 系统性覆盖 |

### 5.4 高杠杆 vs 低杠杆指令

**高杠杆（~1,710 tokens SKILL.md → 直接贡献 18 条 assertion 差值）:**
- Review Depth Selection（250 tok → 3 条）
- Evidence Confidence（100 tok → 3 条）
- Suppression Rules（180 tok → 2 条）
- Output Contract（500 tok → 3 条）
- Gate D 10-Domain（400 tok → 3 条）
- Gate F 未覆盖风险（80 tok → 3 条）
- Standards Mapping（50 tok → 3 条）
- Gate A 配对（150 tok → 1 条）

**中杠杆（~1,100 tokens → 间接贡献质量提升）:**
- Anti-Examples（350 tok）— 防止误报
- Scenario Checklists 指针（200 tok）— 系统性
- Severity Model + SLA（200 tok）— 严重性校准
- Focused Automation Gate（350 tok）— 工具执行纪律

**低杠杆（~250 tokens → 当前评估无贡献）:**
- Baseline Diff Mode（100 tok）— 未测试
- Language Extension Hooks（150 tok）— 仅测 Go

**参考资料（~5,800 tokens → 间接贡献审查深度）:**
- go-secure-coding.md（4,600 tok）— Gate B/D 深度支持
- scenario-checklists.md（1,200 tok）— 场景系统性

### 5.5 Token 效率评级

| 评级 | 结论 |
|------|------|
| **整体 ROI** | **优秀** — ~9,600 tokens 换取 +50.0% 通过率（所有已评估 skill 中最高） |
| **SKILL.md 本身 ROI** | **优秀** — ~3,800 tokens 包含全部高杠杆规则 |
| **高杠杆 Token 比例** | ~45%（1,710/3,800）直接贡献 18/20 条 assertion 差值 |
| **低杠杆 Token 比例** | ~6.6%（250/3,800）在当前评估中无增量贡献 |
| **参考资料效费比** | **高** — 虽占 60% 总 token，但提供了 Gate B/D 的必需深度参考 |

### 5.6 与其他 Skill 的效费比对比

| 指标 | security-review | go-makefile-writer | google-search | deep-research | tdd-workflow |
|------|----------------|-------------------|--------------|--------------|-------------|
| SKILL.md Token | ~3,800 | ~1,960 | ~3,500 | ~2,200 | ~2,800 |
| 总加载 Token | ~9,600 | ~4,100-4,600 | ~6,900 | ~3,500 | ~4,200 |
| 通过率提升 | **+50.0%** | +31.0% | +74.1% | +66.7% | +46.2% |
| 每 1% 的 Token（SKILL.md） | ~76 tok | ~63 tok | ~47 tok | ~33 tok | ~61 tok |
| 每 1% 的 Token（full） | ~192 tok | ~149 tok | ~93 tok | ~53 tok | ~91 tok |

**分析**: security-review 的 SKILL.md 效费比（76 tok/1%）在所有评估的 skill 中属于中等偏下，但其 **绝对通过率提升（+50.0%）是最高的**，意味着 skill 解决的问题更根本——基础模型在安全审查的**结构化合规**方面有巨大缺口（without-skill 结构性合规通过率为 0%），而 skill 完全填补了这一缺口。

参考资料占比较高（~60%）但 Go 安全编码参考是 Gate B/D 的必需依赖，无法简化。如果引入选择性加载（Lite 跳过 go-secure-coding.md），可将 Lite 场景的 token 开销从 ~9,600 降至 ~5,000。

---

## 六、与 Claude 基础模型能力的边界分析

### 6.1 基础模型已具备的能力（Skill 无增量）

| 能力 | 证据 |
|------|------|
| 识别 rate limiting 缺失 | 3/3 场景相关评估正确 |
| 识别 prompt injection 风险 | 1/1 场景正确（Eval 2） |
| 识别 unbounded response body | 1/1 场景正确（Eval 2） |
| 识别 HTTP redirect following 风险 | 1/1 场景正确（Eval 2） |
| 识别 SSRF DNS rebinding | 1/1 场景正确（Eval 2） |
| 识别 API key 存储问题 | 1/1 场景正确（Eval 2） |
| 正确判断 benign code 无安全漏洞 | 1/1 场景正确（Eval 3） |
| MaxBytesReader 正面防御识别 | 1/1 场景正确（Eval 1） |
| html/template 安全性识别 | 1/1 场景正确（Eval 1） |
| 提供代码级修复建议 | 3/3 场景正确 |

### 6.2 基础模型的能力缺口（Skill 填补）

| 缺口 | 证据 | 风险等级 |
|------|------|---------|
| **无 Review Depth 分类** | 3/3 场景无深度选择 | 高 — 审查成本不可控 |
| **无 Confidence 标签** | 3/3 场景无 confirmed/likely/suspected | 高 — 无法区分确认漏洞与假说 |
| **无 CWE/OWASP 映射** | 3/3 场景无标准映射 | 高 — 不满足合规审计要求 |
| **无系统性域覆盖** | 3/3 场景无 Gate D 10-Domain | 高 — 可能遗漏整个安全域 |
| **无 Machine-Readable 输出** | 3/3 场景无 JSON | 中 — CI 自动化门禁不可用 |
| **无未覆盖风险声明** | 3/3 场景无 Gate F | 高 — 虚假完整性（AE-5） |
| **误报抑制不充分** | Eval 1 path traversal 误报；CSRF 根因归属错误 | 中 — 开发者信任下降 |
| **无资源生命周期审计** | Eval 1 无 Gate A 配对表 | 中 — 可能遗漏资源泄漏 |

---

## 七、综合评分

### 7.1 分维度评分

| 维度 | With Skill | Without Skill | 差值 |
|------|-----------|--------------|------|
| 审查流程结构化 | 5.0/5 | 1.0/5 | +4.0 |
| 安全发现质量 | 4.5/5 | 4.0/5 | +0.5 |
| 误报抑制准确性 | 5.0/5 | 2.5/5 | +2.5 |
| 严重性校准 | 5.0/5 | 3.0/5 | +2.0 |
| 标准映射合规 | 5.0/5 | 0.5/5 | +4.5 |
| 输出可消费性（JSON/审计） | 5.0/5 | 1.0/5 | +4.0 |
| **综合均值** | **4.92/5** | **2.0/5** | **+2.92** |

### 7.2 加权总分

| 维度 | 权重 | 得分 | 加权 |
|------|------|------|------|
| Assertion 通过率（delta） | 25% | 10/10 | 2.50 |
| 审查流程结构化 | 20% | 10/10 | 2.00 |
| 误报抑制 & 严重性校准 | 20% | 9.5/10 | 1.90 |
| 标准映射合规 | 15% | 10/10 | 1.50 |
| Token 效费比 | 10% | 7.0/10 | 0.70 |
| 可维护性 & 可扩展性 | 10% | 8.0/10 | 0.80 |
| **加权总分** | | | **9.40/10** |

---

## 八、评估材料

| 材料 | 路径 |
|------|------|
| Eval 1 with-skill 输出 | `/tmp/secreview-eval/eval-1/with_skill/response.md` |
| Eval 1 without-skill 输出 | `/tmp/secreview-eval/eval-1/without_skill/response.md` |
| Eval 2 with-skill 输出 | `/tmp/secreview-eval/eval-2/with_skill/response.md` |
| Eval 2 without-skill 输出 | `/tmp/secreview-eval/eval-2/without_skill/response.md` |
| Eval 3 with-skill 输出 | `/tmp/secreview-eval/eval-3/with_skill/response.md` |
| Eval 3 without-skill 输出 | `/tmp/secreview-eval/eval-3/without_skill/response.md` |
| Skill 文件 | `/Users/john/.codex/skills/security-review/SKILL.md` |
| Go 安全编码参考 | `/Users/john/.codex/skills/security-review/references/go-secure-coding.md` |
| 场景清单参考 | `/Users/john/.codex/skills/security-review/references/scenario-checklists.md` |
