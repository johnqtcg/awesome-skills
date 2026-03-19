# update-doc Skill 评审报告

> 评估框架: [skill-creator](https://github.com/anthropics/skills/tree/main/skills/skill-creator)
> 评估日期: 2026-03-19
> 评估对象: `update-doc`

---

`update-doc` 是一个在代码变更后同步仓库文档的 skill，适合修补或重建 README、codemap 以及相关工程文档。它的三个主要亮点是：通过项目类型路由和 lightweight/full 两种输出模式，让文档更新范围贴合真实仓库形态和变更规模，避免过度重写；通过 evidence-backed diff、scorecard 和 codemap contract，把文档修改变成可追溯、可审查的更新，而不是临时性补丁；以及通过 CI drift guardrails 和维护指引，降低文档在后续迭代中再次落后于代码的概率。

## 一、评估概览

本次评估从**实际任务表现**和 **Token 效费比**两个维度对 update-doc skill 进行全面评审。设计 3 个递进复杂度的文档更新场景（CLI 工具轻量 README 修补、Service/Backend 全量 README 更新、Monorepo Codemap 生成+README 重构），每个场景分别运行 with-skill 和 without-skill 配置，共 3 场景 × 2 配置 = 6 次独立 subagent 运行，对照 42 条 assertion 进行评分。

| 维度 | With Skill | Without Skill | 差异 |
|------|-----------|--------------|------|
| **Assertion 通过率** | **42/42 (100%)** | 18/42 (42.9%) | **+57.1 百分点** |
| **项目类型路由** | 3/3 全对 | 0/3 | Skill 独有 |
| **输出模式选择** | 3/3 全对 | 0/3 | Skill 独有 |
| **结构化报告（Evidence Map/Scorecard）** | 6/6 | 0/6 | Skill 独有 |
| **CI Drift Guardrails** | 2/2 | 0/2 | Skill 独有 |
| **Diff 作用域纪律** | 2/2 | 0/2 | 最大质量差异 |
| **Codemap 结构完整性** | 2/2 | 0/2 | Skill 独有 |
| **Skill Token 开销（SKILL.md 单文件）** | ~2,100 tokens | 0 | — |
| **Skill Token 开销（含参考资料）** | ~2,640 tokens | 0 | — |
| **每 1% 通过率提升的 Token 成本** | ~46 tokens（full） | — | — |

---

## 二、测试方法

### 2.1 场景设计

| 场景 | 仓库 | 核心考察点 | Assertions |
|------|------|-----------|-----------|
| Eval 1: CLI 轻量修补 | `go-file-converter`（Go CLI 工具） | 轻量模式选择、diff 作用域、CLI 项目路由、evidence-backed、anti-pattern 规避 | 13 |
| Eval 2: Service 全量更新 | `go-notification-service`（Go + Gin + PostgreSQL） | 全量模式选择、Service 路由、runtime modes、Quality Scorecard、CI drift guardrails | 15 |
| Eval 3: Monorepo Codemap | `platform-monorepo`（Go + TypeScript 混合） | Monorepo 路由、Codemap Output Contract、Full Output Mode、`Not found in repo` 纪律 | 14 |

### 2.2 测试仓库详情

**Eval 1: go-file-converter**
- `cmd/convert/main.go`：flag 解析（`--format` 默认 "json"、`--output-dir` 默认 "."、`--verbose`）
- 已有 `README.md`：缺 `--output-dir`，`--format` 默认值过时（写为 `csv`）
- 考察重点：仅修补 2 处差异，不做全量重写

**Eval 2: go-notification-service**
- `cmd/api/main.go`（API 服务器）+ `cmd/worker/main.go`（新增 Worker 模式）
- 新增环境变量 `WORKER_CONCURRENCY`（默认 5）、`QUEUE_URL`（必需）
- Makefile 含 9 个 targets、`docker-compose.yml` 含 4 个服务
- 已有 `README.md` 仅覆盖 API 模式

**Eval 3: platform-monorepo**
- `services/auth/`（Go，端口 8080→8443 TLS）、`services/billing/`（Go，新增 Stripe 集成）
- `packages/ui-kit/`（TS）、`packages/api-client/`（TS，新增 AuthClient + BillingClient）
- `.github/workflows/ci.yml` 含 markdownlint
- 已有 `README.md` 缺少 billing、api-client，auth 端口过时

### 2.3 执行方式

- 每个场景创建独立 Git 仓库，预置代码和 go.mod
- With-skill 运行先读取 SKILL.md 及其引用的参考资料（update-doc.md、project-routing.md、ci-drift.md）
- Without-skill 运行不读取任何 skill，按模型默认行为更新文档
- 所有运行在独立 subagent 中并行执行

---

## 三、Assertion 通过率

### 3.1 总览

| 场景 | Assertions | With Skill | Without Skill | 差值 |
|------|-----------|-----------|--------------|------|
| Eval 1: CLI 轻量修补 | 13 | **13/13 (100%)** | 5/13 (38.5%) | +61.5% |
| Eval 2: Service 全量更新 | 15 | **15/15 (100%)** | 8/15 (53.3%) | +46.7% |
| Eval 3: Monorepo Codemap | 14 | **14/14 (100%)** | 5/14 (35.7%) | +64.3% |
| **总计** | **42** | **42/42 (100%)** | **18/42 (42.9%)** | **+57.1%** |

### 3.2 Without-Skill 失败的 24 条 Assertion 归类

| 失败类型 | 次数 | 涉及 Eval | 说明 |
|---------|------|----------|------|
| **项目类型未显式分类** | 3 | 全部 | 无 "CLI Tool" / "Service" / "Monorepo" 路由声明 |
| **输出模式未选择** | 3 | 全部 | 无 Lightweight / Full 模式概念 |
| **缺少结构化 Evidence Map** | 2 | Eval 1/2 | 无 section → source file 映射表 |
| **缺少 Quality Scorecard** | 2 | Eval 2/3 | 无 12 项 PASS/FAIL 评分 |
| **缺少 Command Verification** | 2 | Eval 1/2 | 无执行 vs 未执行命令区分 |
| **缺少 Changed Files 列表** | 1 | Eval 1 | 无结构化变更文件清单 |
| **缺少 Open Gaps** | 1 | Eval 2 | 无未解决项清单 |
| **缺少 CI Drift Guardrails** | 2 | Eval 2/3 | 未识别现有 CI 或建议补充 |
| **未标记 `Not found in repo`** | 1 | Eval 3 | 缺失信息未显式标注 |
| **Diff 作用域溢出** | 2 | Eval 1 | 添加了 "How It Works"、"Error Handling" 等不必要段落 |
| **结构保持失败** | 1 | Eval 1 | README 标题/段落顺序被修改 |
| **Codemap 结构不完整** | 2 | Eval 3 | 缺少 last updated、data flow、cross-links 等必需字段 |
| **模块索引表缺失** | 1 | Eval 3 | 用目录树替代了模块索引表 |
| **目录树全量 dump** | 1 | Eval 3 | README 中嵌入完整目录树而非使用表格 |

### 3.3 失败分层分析

将 24 条失败按"基线模型是否可能自发做到"分为两层：

| 层级 | 失败数 | 说明 |
|------|--------|------|
| **流程/方法论缺失**（模型不会自发产出） | 17 | 项目分类、模式选择、Evidence Map、Scorecard、Command Verification、Open Gaps、CI Drift、`Not found in repo` |
| **质量/纪律缺失**（模型可以但未做到） | 7 | diff 作用域纪律、结构保持、Codemap 完整性、避免目录树 dump |

**解读**：skill 的核心价值在于**注入 17 项方法论纪律**，同时通过 anti-patterns 和 diff scope gate 提供 **7 项质量护栏**。

### 3.4 趋势：Skill 优势在高复杂度场景最大

| 场景复杂度 | Without-Skill 通过率 | With-Skill 优势 |
|-----------|---------------------|----------------|
| Eval 1（简单） | 38.5% | +61.5% |
| Eval 2（中等） | 53.3% | +46.7% |
| Eval 3（复杂） | 35.7% | +64.3% |

与 go-makefile-writer 相反（简单场景优势最大），update-doc 的优势在**最复杂的 monorepo 场景**最大。原因：Eval 3 需要 Codemap Output Contract、多模块路由、CI drift 识别等 skill 独有能力，基线模型几乎无法自发完成。

---

## 四、逐维度对比分析

### 4.1 项目类型路由

这是 skill 的**基础能力**，直接决定了后续所有决策的正确性。

| 场景 | With Skill | Without Skill |
|------|-----------|--------------|
| Eval 1 | "CLI Tool" → 选择 flag/options 优先策略 | 无分类，泛化处理 |
| Eval 2 | "Service / Backend" → 选择 runtime modes 优先策略 | 无分类，但自然做了合理更新 |
| Eval 3 | "Monorepo" → 选择 module index + 子模块链接策略 | 无分类，用目录树替代 |

**分析**：Without-skill 在 Eval 2 中恰好产出了合理的 Service 文档结构，但缺乏显式路由意味着**不可预测性**——同一模型在 Eval 3 中选择了目录树 dump 而非模块索引表。Skill 的路由机制保证了跨场景的**一致性**。

### 4.2 输出模式选择

| 场景 | With Skill | Without Skill |
|------|-----------|--------------|
| Eval 1 | Lightweight（1 文件、窄修补） | 无模式概念，做了超范围重写 |
| Eval 2 | Full（新 runtime mode 触发） | 无模式概念，简洁回复 |
| Eval 3 | Full（codemap 创建 + 多模块） | 无模式概念，简洁回复 |

**分析**：Without-skill 在 Eval 1 中的**过度重写**（添加 "How It Works"、"Error Handling" 段落）正是 skill 的 Lightweight 模式和 Diff Scope Gate 要防止的行为。在 Eval 2/3 中，without-skill 的简洁回复虽然不冗余，但**缺少了 Evidence Map、Scorecard、Open Gaps 等结构化输出**。

### 4.3 Evidence-Backed 准确性

两种配置在**事实准确性**上都表现良好：

| 维度 | With Skill | Without Skill |
|------|-----------|--------------|
| 环境变量默认值 | 全部正确 | 全部正确 |
| 端口号 | 全部正确 | 全部正确 |
| API 路由/端点 | 全部正确 | 全部正确 |
| 未捏造内容 | ✅ | ✅ |
| 结构化 Evidence 追溯 | ✅（每个 claim 映射到源文件+行号） | ❌（叙述性验证，无结构化映射） |

**关键差异**：Skill 不是在**准确性**上胜出，而是在**可审计性**上——Evidence Map 使每个文档 claim 可追溯到具体代码行号，支持 PR review 和后续维护。

### 4.4 Anti-Pattern 规避

| Anti-Pattern | With Skill | Without Skill |
|-------------|-----------|--------------|
| Scorecard 泄漏到 README | ✅ 未泄漏 | ✅ 无 Scorecard 可泄漏 |
| 验证标签泄漏到 README | ✅ 未泄漏 | ✅ 未泄漏 |
| 受众标签/作者评论 | ✅ 未添加 | ✅ 未添加 |
| Quick start 被推到后面 | ✅ 保持在前 | ✅ 保持在前 |
| 删除有用导航 | ✅ 保留并改进 | ⚠️ Eval 3 中用目录树替代表格 |
| 超范围重写 | ✅ 严格 diff 作用域 | ❌ Eval 1 中添加不必要段落 |
| 目录树全量 dump | ✅ 使用表格 | ❌ Eval 3 中 dump 完整目录树 |

### 4.5 Codemap 质量（Eval 3 专项）

| 维度 | With Skill | Without Skill |
|------|-----------|--------------|
| INDEX.md 结构 | 概览 + Codemap 表格（含链接）+ 跨模块关注点 | 扁平列表，无子文件链接 |
| 独立 Codemap 文件 | backend.md + frontend.md | 仅 INDEX.md 一个文件 |
| Last updated date | ✅ | ❌ |
| Entry points | ✅ | ✅（部分） |
| Key modules table | ✅ | ❌（叙述格式） |
| Data flow | ✅（ASCII 图） | ❌ |
| External deps | ✅ | ❌ |
| Cross-links | ✅（服务↔客户端互链） | ❌ |

### 4.6 CI Drift Guardrails（Eval 2/3 专项）

| 维度 | With Skill | Without Skill |
|------|-----------|--------------|
| 识别现有 CI 配置 | ✅ 识别 markdownlint（Eval 3） | ❌ 未分析 |
| 建议 docs drift check | ✅ 含示例 YAML | ❌ |
| 建议 link checker | ✅ 推荐 lychee | ❌ |
| 建议 CODEOWNERS | ✅ | ❌ |

---

## 五、Token 效费比分析

### 5.1 Skill 体积

| 文件 | 行数 | 单词 | 字节 | 估算 Token |
|------|------|------|------|-----------|
| **SKILL.md** | 291 | 1,426 | 9,923 | ~2,100 |
| references/update-doc.md | 39 | 142 | 961 | ~200 |
| references/project-routing.md | 37 | 89 | 588 | ~150 |
| references/ci-drift.md | 26 | 94 | 676 | ~150 |
| **Description（始终在 context）** | — | ~30 | — | ~40 |
| **总计** | **393** | **1,781** | **12,148** | **~2,640** |

### 5.2 SKILL.md 功能模块拆分

| 模块 | 估算 Token | 关联 Assertion Delta | 效费比 |
|------|-----------|---------------------|--------|
| **Hard Rules** | ~200 | 4 条（a4,a5,a12→已通过; b5,b15,c6,c7→已通过; c12→1 delta） | **高** — 50 tok/delta |
| **Gate 1: Audience/Language** | ~120 | 0 条 delta（c14 双方均通过） | **低** — 无增量 |
| **Gate 2: Project Type Routing** | ~100 | 3 条 delta（a1,b1,c1） | **极高** — 33 tok/delta |
| **Gate 3: Diff Scope** | ~120 | 2 条 delta（a2,a13） | **极高** — 60 tok/delta |
| **Gate 4: Command Verifiability** | ~100 | 1 条 delta（b10） | **高** — 100 tok/delta |
| **Anti-Patterns** | ~200 | 3 条 delta（a6,c9,c10） | **高** — 67 tok/delta |
| **Standard Workflow** | ~300 | 0 条直接 delta | **低** — 间接流程指导 |
| **Lightweight Output Mode** | ~200 | 4 条 delta（a3,a9,a10,a11） | **极高** — 50 tok/delta |
| **Full Output Mode** | ~130 | 5 条 delta（b2,b8,b9,b12,c2） | **极高** — 26 tok/delta |
| **Evidence Commands** | ~100 | 0 条直接 delta | **低** — 间接探索指导 |
| **Project-Type Guidance** | ~280 | 1 条 delta（c5） | **中** — 280 tok/delta |
| **README UX Rules** | ~100 | 0 条 delta（b7 双方均通过） | **低** — 无增量 |
| **Codemap Output Contract** | ~200 | 2 条 delta（c3,c4） | **高** — 100 tok/delta |
| **CI Drift Guardrails** | ~100 | 2 条 delta（b13,c13） | **极高** — 50 tok/delta |
| **Quality Scorecard** | ~250 | 2 条 delta（b8,c11） | **高** — 125 tok/delta |
| **Output Format** | ~150 | 已计入 Lightweight/Full 模式 | — |

### 5.3 高杠杆 vs 低杠杆指令

**高杠杆（~850 tokens → 17 条 delta，~50 tok/delta）:**

| 模块 | Token | Delta |
|------|-------|-------|
| Gate 2: Project Type Routing | ~100 | 3 |
| Gate 3: Diff Scope | ~120 | 2 |
| Lightweight Output Mode | ~200 | 4 |
| Full Output Mode | ~130 | 5 |
| CI Drift Guardrails | ~100 | 2 |
| Anti-Patterns（部分） | ~100 | 1 |

**中杠杆（~750 tokens → 7 条 delta，~107 tok/delta）:**

| 模块 | Token | Delta |
|------|-------|-------|
| Hard Rules | ~200 | 1 |
| Gate 4: Command Verifiability | ~100 | 1 |
| Anti-Patterns（部分） | ~100 | 2 |
| Codemap Output Contract | ~200 | 2 |
| Quality Scorecard（含 Output Format） | ~150 | 1 |

**低杠杆（~1,000 tokens → 0 条 delta）:**

| 模块 | Token | 说明 |
|------|-------|------|
| Gate 1: Audience/Language | ~120 | c14 双方均通过 |
| Standard Workflow | ~300 | 间接流程指导 |
| Evidence Commands | ~100 | 间接探索指导 |
| README UX Rules | ~100 | b7 双方均通过 |
| Project-Type Guidance（部分） | ~180 | Service/Library 指导未产生差异 |
| Output Format 重复区 | ~100 | 与模式区重叠 |

### 5.4 Token 效率评级

| 评级 | 结论 |
|------|------|
| **整体 ROI** | **优秀** — ~2,640 tokens 换取 +57.1% 通过率 |
| **SKILL.md 本身 ROI** | **优秀** — ~2,100 tokens 包含全部高杠杆规则 |
| **高杠杆 Token 比例** | ~40%（850/2,100）直接贡献 17/24 条 delta |
| **低杠杆 Token 比例** | ~48%（1,000/2,100）在当前评估中无增量贡献 |
| **参考资料效费比** | **中等** — ~540 tokens 提供补充指导但无独立 assertion delta |

### 5.5 跨 Skill 效费比对比

| 指标 | update-doc | go-makefile-writer | git-commit |
|------|-----------|-------------------|------------|
| SKILL.md Token | ~2,100 | ~1,960 | ~1,120 |
| 总加载 Token | ~2,640 | ~4,100-4,600 | ~1,120 |
| 通过率提升 | **+57.1%** | +31.0% | +22.7% |
| 每 1% 的 Token（SKILL.md） | **~37 tok** | ~63 tok | ~51 tok |
| 每 1% 的 Token（full） | **~46 tok** | ~149 tok | ~51 tok |
| Assertion 总数 | 42 | 42 | 22 |

**update-doc 是三个 skill 中 Token 效费比最高的**，原因：

1. **极大的通过率 delta**（+57.1%）：skill 注入了 17 项基线模型完全不具备的方法论
2. **紧凑的参考资料**（仅 ~540 tokens）：相比 makefile-writer 的 ~2,600 tokens 参考资料
3. **高杠杆模块占比合理**：40% 的 SKILL.md 内容直接驱动 71% 的 assertion delta

---

## 六、与 Claude 基础模型能力的边界分析

### 6.1 基础模型已具备的能力（Skill 无增量）

| 能力 | 证据 |
|------|------|
| 环境变量正确提取和文档化 | 3/3 场景双方均正确 |
| 端口号/默认值准确 | 3/3 场景双方均正确 |
| API 路由正确列举 | 3/3 场景双方均正确 |
| 不捏造代码中不存在的内容 | 3/3 场景双方均未捏造 |
| Makefile target 正确引用 | 2/2 相关场景均正确 |
| README 读者友好的排版 | Eval 2 without-skill 的阅读流也合理 |
| 基本的 docker-compose 文档化 | Eval 2 双方均正确覆盖 |

### 6.2 基础模型的能力缺口（Skill 填补）

| 缺口 | 证据 | 风险等级 |
|------|------|---------|
| **无显式项目类型路由** | 3/3 场景无分类 | 高 — 导致策略不一致 |
| **无输出模式控制** | 3/3 场景无模式概念 | 高 — Eval 1 过度重写，Eval 2/3 缺少报告 |
| **无 diff 作用域纪律** | Eval 1 添加不必要段落 | 中 — 维护成本增加 |
| **无结构化 Evidence 追溯** | 3/3 场景无 Evidence Map | 中 — PR review 缺少审计线索 |
| **无 Quality Scorecard** | 3/3 场景无 Scorecard | 中 — 缺少系统性质量检查 |
| **无 CI Drift 意识** | 2/2 相关场景未提及 | 高 — 文档会再次落后 |
| **Codemap 结构不规范** | Eval 3 扁平文件无必需字段 | 中 — 架构文档不可维护 |
| **目录树 dump 反模式** | Eval 3 嵌入完整目录树 | 低 — 影响可读性 |

### 6.3 能力边界总结

基础模型在**事实提取和基本文档撰写**方面能力强大（环境变量、端口、路由全部正确），但在**方法论纪律**方面完全缺失。Skill 的价值不是"让模型更聪明"，而是"给模型一套可重复的工作流程"——项目分类 → diff 作用域 → 输出模式 → 结构化报告 → CI 维护建议。

---

## 七、综合评分

### 7.1 分维度评分

| 维度 | With Skill | Without Skill | 差值 |
|------|-----------|--------------|------|
| 项目类型路由与 diff 作用域 | 5.0/5 | 1.0/5 | +4.0 |
| Evidence-Backed 准确性 | 5.0/5 | 3.5/5 | +1.5 |
| 输出模式与结构正确性 | 5.0/5 | 1.0/5 | +4.0 |
| Anti-Pattern 规避与 README UX | 5.0/5 | 3.0/5 | +2.0 |
| Token 效费比 | 4.5/5 | — | — |
| CI Drift 与可维护性 | 5.0/5 | 1.0/5 | +4.0 |
| **综合均值** | **4.92/5** | **1.75/5** | **+3.17** |

### 7.2 加权总分

| 维度 | 权重 | 得分 | 加权 |
|------|------|------|------|
| Assertion 通过率（delta） | 25% | 10/10 | 2.50 |
| Evidence-Backed 准确性 | 20% | 9.0/10 | 1.80 |
| Output Mode & 结构正确性 | 15% | 10/10 | 1.50 |
| Token 效费比 | 15% | 9.0/10 | 1.35 |
| Anti-Pattern 规避 & README UX | 15% | 9.0/10 | 1.35 |
| Project-Type 路由 & Diff 作用域 | 10% | 10/10 | 1.00 |
| **加权总分** | | | **9.50/10** |

---

## 八、改进建议

### 8.1 [P1] 精简低杠杆模块

约 1,000 tokens（~48% of SKILL.md）在当前评估中无增量贡献：

| 模块 | Token | 建议 |
|------|-------|------|
| Standard Workflow | ~300 | 压缩为 3-4 行简要步骤列表，详细版移至参考文件 |
| Evidence Commands | ~100 | 移至 `references/evidence-commands.md`，按需加载 |
| Gate 1: Audience/Language | ~120 | 保留但精简（基线模型已自发遵循 repo 语言） |
| README UX Rules | ~100 | 基线模型已自发保持合理读者流，可压缩 |

预计减少 ~400-500 tokens，不影响高杠杆 assertion 通过率，将 SKILL.md 效率从 37 tok/1% 优化至 ~28 tok/1%。

### 8.2 [P1] 增强 Monorepo Codemap 指导

Eval 3 的 Codemap Output Contract 是 with-skill 与 without-skill 差距最大的维度之一。建议：

- 添加一个简短的 Codemap INDEX.md 模板到 `references/codemap-template.md`
- 明确 INDEX.md 必须包含：概览、子 codemap 链接表、跨模块关注点
- 为每种项目类型（Service/Monorepo）指定哪些 codemap 文件是必需的

### 8.3 [P2] 参考资料的条件加载指引

当前 3 个参考文件（~540 tokens）全部读取时不到 SKILL.md 的 1/4。但可以更明确地标注加载条件：

- **简单修补**（Eval 1 类）：仅 SKILL.md 即可，无需参考资料（~2,100 tokens）
- **Service 全量更新**（Eval 2 类）：SKILL.md + ci-drift.md（~2,250 tokens）
- **Monorepo codemap**（Eval 3 类）：SKILL.md + 全部参考资料（~2,640 tokens）

### 8.4 [P2] 增加更多评估场景

当前未覆盖的 skill 功能：

| 未测试功能 | 建议场景 |
|-----------|---------|
| Library/SDK 路由 | npm 包的 README 更新 |
| 中文文档项目 | 中文 README 的 update-doc |
| 现有 Codemap 的增量更新 | 已有 codemap 的 diff-scoped 修补 |
| 用户要求全量审计 | 用户显式要求 Scorecard 在文档中 |
| Multi-language repo | Python + Go 混合仓库 |

### 8.5 [P3] 考虑将 Quality Scorecard 列表移至参考文件

Scorecard 的 12 项检查（~250 tokens）始终加载但仅在 Full Output Mode 使用。可移至 `references/scorecard.md`，SKILL.md 中保留一句"参考 references/scorecard.md 的 12 项检查"。

---

## 九、评估材料

| 材料 | 路径 |
|------|------|
| 被评估 Skill | `/Users/john/.codex/skills/update-doc/SKILL.md` |
| Skill 参考资料 | `/Users/john/.codex/skills/update-doc/references/*.md` |
| Eval 1 with-skill 输出 | `/tmp/update-doc-eval/workspace/iteration-1/eval-1/with_skill/outputs/` |
| Eval 1 without-skill 输出 | `/tmp/update-doc-eval/workspace/iteration-1/eval-1/without_skill/outputs/` |
| Eval 2 with-skill 输出 | `/tmp/update-doc-eval/workspace/iteration-1/eval-2/with_skill/outputs/` |
| Eval 2 without-skill 输出 | `/tmp/update-doc-eval/workspace/iteration-1/eval-2/without_skill/outputs/` |
| Eval 3 with-skill 输出 | `/tmp/update-doc-eval/workspace/iteration-1/eval-3/with_skill/outputs/` |
| Eval 3 without-skill 输出 | `/tmp/update-doc-eval/workspace/iteration-1/eval-3/without_skill/outputs/` |
| 测试仓库 | `/tmp/update-doc-eval/repos/{go-file-converter,go-notification-service,platform-monorepo}/` |
| 报告格式参考 | `/Users/john/go-notes/skills/go-makefile-writer-skill-eval-report.md` |
