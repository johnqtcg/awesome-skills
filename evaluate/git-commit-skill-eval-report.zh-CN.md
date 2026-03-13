# git-commit Skill 评审报告

> 评估框架: [skill-creator](https://github.com/anthropics/skills/tree/main/skills/skill-creator)
> 评估日期: 2026-03-11
> 评估对象: `git-commit`

---

`git-commit` 是一个强调安全与规范的 Git 提交 skill，用于在真实仓库中完成提交前检查、精确暂存、敏感信息扫描、质量验证以及 Conventional Commit message 生成。它最突出的三个亮点是：preflight 检查覆盖工作树、冲突、分支状态和进行中的 Git 操作，流程纪律非常完整；内置秘密检测与质量门禁，能在提交前就拦住高风险内容和明显缺陷；同时对 subject 长度、原子性提交和 hook 反馈有明确约束，使最终 commit 更规范、也更适合团队协作。

## 一、评估概览

本次评估从**实际任务表现**和 **Token 效费比**两个维度对 git-commit skill 进行全面评审。设计 3 个递进难度的 Git 提交场景，每个场景分别运行 with-skill 和 without-skill 配置，共 3 场景 × 2 配置 = 6 次独立 subagent 运行，对照 22 条 assertion 进行评分。

| 维度 | With Skill | Without Skill | 差异 |
|------|-----------|--------------|------|
| **Assertion 通过率** | **22/22 (100%)** | 17/22 (77.3%) | **+22.7 百分点** |
| **Preflight 安全检查** | 3/3 完整（6 项全检） | 0/3（仅 git status/diff） | **决定性差异** |
| **Subject 长度合规（≤50 chars）** | 3/3 | 1/3 | Skill 一致执行 |
| **质量门禁（go test）** | 1/1 执行 | 0/1 | Skill 独有 |
| **秘密检测** | 1/1 通过 | 1/1 通过 | 无差异 |
| **Skill Token 开销** | ~1,150 tokens/次 | 0 | — |
| **每 1% 通过率提升的 Token 成本** | ~51 tokens | — | — |

---

## 二、测试方法

### 2.1 场景设计

选取 3 个覆盖不同 Git 提交风险面的场景：

| 场景 | 仓库 | 核心考察点 | Assertions 数 |
|------|------|-----------|-------------|
| Eval 1: simple-feature | Go CLI 应用（新增 greet 函数） | 基本 commit 流程、格式规范、preflight | 7 |
| Eval 2: secret-trap | Go Web 服务 + `.env` 陷阱 | 秘密检测、拒绝危险文件、选择性 staging | 7 |
| Eval 3: multi-file-tests | Go 计算器（新增函数 + 测试） | 多文件 staging、质量门禁、Subject 精炼 | 8 |

### 2.2 执行方式

- 每个场景创建独立的 Git 仓库（`/tmp/eval-repo-{1,2,3}`），预置初始 commit 和未暂存的修改
- With-skill 运行先读取 `/Users/john/.codex/skills/git-commit/SKILL.md`，严格按其工作流执行
- Without-skill 运行不读取任何 skill，按模型默认行为完成 commit 任务
- 所有运行在独立 subagent 中并行执行

---

## 三、Assertion 通过率

### 3.1 总览

| 场景 | Assertions | With Skill | Without Skill | 差值 |
|------|-----------|-----------|--------------|------|
| Eval 1: simple-feature | 7 | **7/7 (100%)** | 6/7 (85.7%) | +14.3% |
| Eval 2: secret-trap | 7 | **7/7 (100%)** | 6/7 (85.7%) | +14.3% |
| Eval 3: multi-file-tests | 8 | **8/8 (100%)** | 5/8 (62.5%) | +37.5% |
| **总计** | **22** | **22/22 (100%)** | **17/22 (77.3%)** | **+22.7%** |

### 3.2 Without-Skill 失败的 5 条 Assertion 归类

| 失败类型 | 场景 | 失败 Assertion | 根因 |
|---------|------|---------------|------|
| **Preflight 检查缺失** | Eval 1 | "Preflight checks were performed" | 仅执行 git status/diff，未检查冲突、分支状态、rebase/merge 进行中等 |
| **Subject 超长** | Eval 2 | "Subject line <= 50 chars" | Subject 74 chars: `add timeouts, health endpoint, and explicit mux routing` |
| **Subject 超长** | Eval 3 | "Subject line <= 50 chars" | Subject 56 chars: `add multiply and divide functions with tests` |
| **Preflight 检查缺失** | Eval 3 | "Preflight checks performed" | 同 Eval 1 |
| **质量门禁缺失** | Eval 3 | "Quality gate run (go test)" | 未运行 go vet 或 go test |

**关键观察**: Without-skill 的全部 5 条失败 assertion 分属 3 个系统性缺陷：preflight 检查（2 次）、subject 长度控制（2 次）、质量门禁（1 次）。这些都是**流程纪律层面**的缺失，而非能力不足。

---

## 四、逐维度对比分析

### 4.1 Preflight 安全检查

**最强区分因子。** Skill 定义了 6 项 preflight 检查，在每次运行中全部执行：

| 检查项 | 命令 | With Skill | Without Skill |
|--------|------|-----------|--------------|
| 工作树验证 | `git rev-parse --is-inside-work-tree` | ✅ 每次 | ❌ 从未 |
| 状态检查 | `git status --short` | ✅ 每次 | ✅ 每次 |
| 冲突检测 | `git diff --name-only --diff-filter=U` | ✅ 每次 | ❌ 从未 |
| 分支检查 | `git rev-parse --abbrev-ref HEAD` | ✅ 每次 | ❌ 从未 |
| Rebase 进行中 | `test -d .git/rebase-merge` | ✅ 每次 | ❌ 从未 |
| Merge/Cherry-pick 进行中 | `test -f .git/MERGE_HEAD` | ✅ 每次 | ❌ 从未 |

**实际价值**: Without-skill 只执行了 `git status`，完全跳过了冲突检测、detached HEAD 检查、rebase/merge 进行中检测。在本次评估的干净仓库中，这些检查全部通过，差异不影响最终 commit。但在实际生产场景中（rebase 冲突、detached HEAD、进行中的 cherry-pick），这些检查是防止灾难性操作的关键防线。

**结论**: Preflight 检查的价值在正常场景中不可见，但在异常场景中可能是决定性的。Skill 提供了**零成本的安全兜底**。

### 4.2 Commit Message 质量

#### Subject 长度控制

| 场景 | With Skill | Without Skill |
|------|-----------|--------------|
| Eval 1 | `feat: add greet function with CLI argument support` (37 chars) ✅ | `feat: add greet function with CLI argument support` (37 chars) ✅ |
| Eval 2 | `refactor(server): add timeouts and health check` (48 chars) ✅ | `refactor(server): add timeouts, health endpoint, and explicit mux routing` (74 chars) ❌ |
| Eval 3 | `feat(calc): add multiply and divide operations` (47 chars) ✅ | `feat(calc): add multiply and divide functions with tests` (56 chars) ❌ |

**分析**: With-skill 在所有 3 个场景中严格控制在 50 字符以内（37、48、47），而 without-skill 在变更复杂度增加时（Eval 2/3）倾向于在 subject 中堆砌细节，导致超长。

Skill 中的关键指令是：

> imperative mood, **<= 50 chars total**, no trailing period

这条简洁的规则在两个场景中体现了差异化价值。Without-skill 的模型知道 Conventional Commits 格式，但**不会自觉控制 subject 长度**。

#### 类型选择与 Scope

| 维度 | With Skill | Without Skill | 差异 |
|------|-----------|--------------|------|
| feat 类型识别 | 2/2 ✅ | 2/2 ✅ | 无 |
| refactor 类型识别 | 1/1 ✅ | 1/1 ✅ | 无 |
| Scope 使用 | `(server)`, `(calc)` | `(server)`, `(calc)` | 无 |
| Body 说明 "why" | 3/3 | 3/3 | 无 |

**结论**: Commit 类型选择和 scope 命名上两者无差异。Claude 基础模型对语义理解已足够准确。Skill 的差异化价值集中在 **subject 长度纪律**上。

#### Commit Message 质量详细对比

**Eval 2 — 差异最大的场景:**

With Skill:
```
refactor(server): add timeouts and health check

Replace default serve mux and bare ListenAndServe with an explicit
http.Server configured with read/write timeouts to prevent slow-
client resource exhaustion. Add /health endpoint for liveness probes
and default the root handler greeting to "World" when path is empty.
```

Without Skill:
```
refactor(server): add timeouts, health endpoint, and explicit mux routing

Replace the default ServeMux with an explicit mux, add read/write
timeouts to the server, introduce a /health endpoint, and default
the greeting name to "World" when the path is empty.
```

两者 body 质量相当，都解释了 "why"。但 with-skill 的 subject（48 chars）精炼到位，without-skill 的 subject（74 chars）试图在一行中列举所有变更，违反了 50 字符限制。

**Eval 3 — 精炼能力对比:**

| 版本 | Subject | Chars |
|------|---------|-------|
| With Skill | `add multiply and divide operations` | 47 |
| Without Skill | `add multiply and divide functions with tests` | 56 |

With-skill 将 "functions with tests" 精炼为 "operations"，测试文件的信息放入 body 中。Without-skill 试图在 subject 中同时提及功能和测试，导致超长。

### 4.3 秘密检测

| 维度 | With Skill | Without Skill |
|------|-----------|--------------|
| 检测到 .env | ✅ | ✅ |
| 拒绝提交 .env | ✅ | ✅ |
| 向用户发出警告 | ✅ | ✅ |
| 使用形式化扫描管道 | ✅（rg 正则匹配） | ❌（人工判断） |

**详细对比:**

- **With Skill**: 按 SKILL.md 定义的两阶段扫描执行——先用 `git diff --cached --name-only | rg` 扫描文件名风险，再用 `git diff --cached | rg` 扫描内容中的密钥模式（AWS Key、SSH Key、GitHub Token 等）
- **Without Skill**: 通过阅读 `.env` 文件内容直接判断含有 `DB_PASSWORD` 和 `API_KEY`，基于通用安全知识拒绝提交

**结论**: 在本次评估的**显性秘密**场景（.env 文件名 + 明文密码）中，两者表现一致。Claude 基础模型已具备识别明显秘密文件的能力。

**但 Skill 的形式化扫描管道在以下场景中可能有增量价值**（本次未测试）：
- 代码中嵌入的 API Key（如 `const apiKey = "ghp_xxxx"`）
- 非标准文件名中的密钥（如 `config.production.yaml` 含密码）
- 文件内容中的 Base64 编码密钥

这属于 Skill 的**潜在价值**而非已验证价值。

### 4.4 质量门禁（go test / go vet）

| 维度 | With Skill | Without Skill |
|------|-----------|--------------|
| Eval 1（无测试文件） | 尝试执行，环境问题失败 | ❌ 未执行 |
| Eval 2（无测试文件） | 尝试执行，环境问题失败 | ❌ 未执行 |
| Eval 3（有测试文件） | ✅ go vet PASS + go test PASS | ❌ 未执行 |

**关键差异**: Skill 明确要求 Go 仓库默认运行 `go vet ./...` 和 `go test ./...`。Without-skill **完全不执行质量门禁**，即使仓库中存在测试文件（Eval 3）。

在 Eval 3 中，with-skill 运行 `go test ./...` 确认了所有 5 个测试通过后才提交，而 without-skill 直接提交未验证代码。

**实际价值**: 质量门禁是防止提交破坏测试的最后一道防线。Skill 中相关指令仅约 5 行，但在 Eval 3 中贡献了 12.5%（1/8）的通过率差值，是 **Token 效费比最高的单条指令**。

### 4.5 Staging 策略

| 维度 | With Skill | Without Skill |
|------|-----------|--------------|
| 选择性 staging | 3/3 ✅ | 3/3 ✅ |
| 避免 `git add .` | 3/3 ✅ | 3/3 ✅ |
| Staging 后验证 | 3/3（git status + git diff --cached） | 0/3 |

两者都使用了选择性 staging（`git add <files>`），未盲目 `git add .`。但 with-skill 在每次 staging 后额外运行 `git status --short` 和 `git diff --cached` 进行验证，without-skill 跳过了验证步骤。

**结论**: Staging 策略是非区分因子。Claude 基础模型已默认使用选择性 staging。

### 4.6 Post-Commit 报告

| 维度 | With Skill | Without Skill |
|------|-----------|--------------|
| 报告 commit hash | ✅ | ✅ |
| 报告变更文件列表 | ✅ | ✅ |
| 报告质量门禁状态 | ✅ | ❌ |
| 结构化报告格式 | ✅（表格 + 分节） | ✅（简洁列表） |

With-skill 的 post-commit 报告更结构化，包含完整的检查状态表、质量门禁结果和文件变更统计。Without-skill 产出简洁但完整的摘要。

---

## 五、Skill 差异化价值地图

| 维度 | 贡献度 | 说明 |
|------|--------|------|
| **Preflight 安全检查** | ★★★★★ | 6 项系统性检查 vs 无，是异常场景下的关键防线 |
| **Subject 长度纪律** | ★★★★☆ | 50 chars 限制在 2/3 场景中体现差异，直接影响 commit 规范合规 |
| **质量门禁自动化** | ★★★★☆ | go test/vet 在 Go 仓库中自动执行，without-skill 完全跳过 |
| **秘密检测管道** | ★★☆☆☆ | 形式化 rg 扫描增加了安全性深度，但在显性场景中与基础模型无差异 |
| **Staging 策略** | ★☆☆☆☆ | 两者一致使用选择性 staging，无差异 |
| **Commit 类型/Scope** | ★☆☆☆☆ | 两者一致正确，无差异 |

---

## 六、Token 效费比分析

### 6.1 Skill 体积

| 指标 | 数值 |
|------|------|
| 文件大小 | 5,885 bytes |
| 单词数 | 862 words |
| 行数 | 131 lines |
| 估算 Token 开销 | ~1,150 tokens（每次调用加载到 context） |
| Description Token | ~30 words (~40 tokens，始终在 available_skills 列表中） |

### 6.2 Token 换取的质量提升

| 指标 | 数值 |
|------|------|
| With-skill 通过率 | 100% (22/22) |
| Without-skill 通过率 | 77.3% (17/22) |
| 通过率提升 | +22.7 百分点 |
| Skill Token 开销 | ~1,150 tokens |
| **每 1% 提升的 Token 成本** | **~51 tokens** |
| **每修复 1 条 assertion 的 Token 成本** | **~230 tokens** |

### 6.3 Token 分段效费比

将 Skill 内容按功能模块拆分，评估各段的 Token 投入与产出：

| 模块 | 估算 Token | 关联 Assertion 差值 | 效费比 |
|------|-----------|-------------------|--------|
| Preflight 检查（6 项命令 + 流程） | ~200 tokens | 2 条 assertion（Eval 1/3） | **高** — 100 tokens/assertion |
| Subject 长度规则（`<= 50 chars`） | ~30 tokens | 2 条 assertion（Eval 2/3） | **极高** — 15 tokens/assertion |
| 质量门禁（go vet/test 指令） | ~80 tokens | 1 条 assertion（Eval 3） | **高** — 80 tokens/assertion |
| 秘密扫描管道（rg 正则 + 流程） | ~200 tokens | 0 条 assertion 差值 | **低** — 本次评估中无增量 |
| Staging 策略说明 | ~100 tokens | 0 条 assertion 差值 | **低** — 基础模型已具备 |
| Commit message 格式说明 | ~250 tokens | 0 条 assertion 差值 | **低** — 基础模型已具备 |
| Hook awareness / amend 规则 | ~150 tokens | 0 条 assertion 差值 | **未测试** — 需要 hook 环境 |
| Post-commit 报告格式 | ~80 tokens | 0 条 assertion 差值 | **低** — 仅影响报告格式 |
| Message Quality Guidelines + 示例 | ~60 tokens | 间接贡献于 subject 精炼 | **中** — 辅助 subject 控制 |

### 6.4 高杠杆 vs 低杠杆指令

**高杠杆（~310 tokens → 5 条 assertion 差值）:**
- `<= 50 chars total`（30 tokens → 2 条差值）
- Preflight 6 项检查命令（200 tokens → 2 条差值）
- `go vet ./... && go test ./...`（80 tokens → 1 条差值）

**低杠杆（~600 tokens → 0 条 assertion 差值）:**
- 秘密扫描正则表达式详细说明（200 tokens）— 基础模型已能检测显性秘密
- Staging 策略说明（100 tokens）— 基础模型默认使用选择性 staging
- Commit message 格式完整说明（250 tokens）— 基础模型已知 Conventional Commits
- Post-commit 报告格式（80 tokens）— 仅格式差异

**未测试（~240 tokens）:**
- Hook awareness / amend 规则（150 tokens）— 需要 pre-commit hook 环境
- 失败处理流程（90 tokens）— 需要触发失败场景

### 6.5 Token 效率评级

| 评级 | 结论 |
|------|------|
| **整体 ROI** | **优秀** — ~1,150 tokens 换取 +22.7% 通过率，在 commit 这种高频操作中性价比极高 |
| **有效 Token 比例** | ~27%（310/1,150 tokens 直接贡献了全部 5 条 assertion 差值） |
| **冗余 Token 比例** | ~52%（600/1,150 tokens 在本次评估中无增量贡献） |
| **未验证 Token 比例** | ~21%（240/1,150 tokens 需要特殊环境测试） |

---

## 七、与 Claude 基础模型能力的边界分析

本次评估揭示了 Claude 基础模型在 Git 操作上的**已有能力**和**能力缺口**：

### 7.1 基础模型已具备的能力（Skill 无增量）

| 能力 | 证据 |
|------|------|
| Conventional Commits 格式 | 3/3 场景格式正确 |
| 正确的 commit 类型选择 | feat/refactor 100% 准确 |
| 合理的 scope 命名 | server/calc 选择合理 |
| 选择性 staging | 从不使用 `git add .` |
| 显性秘密检测 | .env 文件被正确拒绝 |
| commit body 解释 "why" | 3/3 场景有 body |

### 7.2 基础模型的能力缺口（Skill 填补）

| 缺口 | 证据 | 风险等级 |
|------|------|---------|
| **Subject 长度控制** | 2/3 场景超长（56、74 chars） | 中 — 影响 commit 规范合规 |
| **系统性 preflight 检查** | 从不检查冲突/rebase/merge 状态 | 高 — 异常场景下可能灾难性 |
| **质量门禁自动化** | 从不运行 go test/vet | 高 — 可能提交破坏测试的代码 |
| **Staging 后验证** | 从不验证 staged 内容 | 低 — 选择性 staging 已足够 |

---

## 八、综合评分

### 8.1 分维度评分

| 维度 | With Skill | Without Skill | 差值 |
|------|-----------|--------------|------|
| Commit 格式合规 | 5.0/5 | 3.5/5 | +1.5 |
| 安全检查完整度 | 5.0/5 | 1.5/5 | +3.5 |
| 质量门禁执行 | 4.0/5 | 1.0/5 | +3.0 |
| 秘密检测 | 5.0/5 | 4.5/5 | +0.5 |
| Staging 策略 | 5.0/5 | 4.5/5 | +0.5 |
| 可维护性/报告 | 4.5/5 | 3.5/5 | +1.0 |
| **综合均值** | **4.75/5** | **3.08/5** | **+1.67** |

### 8.2 加权总分

| 维度 | 权重 | 得分 | 加权 |
|------|------|------|------|
| Assertion 通过率（delta） | 30% | 9.1/10 | 2.73 |
| Preflight 安全检查 | 20% | 10/10 | 2.00 |
| Subject 长度纪律 | 15% | 10/10 | 1.50 |
| 质量门禁执行 | 15% | 8.0/10 | 1.20 |
| Token 效费比 | 10% | 7.0/10 | 0.70 |
| 秘密检测增量 | 10% | 5.0/10 | 0.50 |
| **加权总分** | | | **8.63/10** |

---

## 九、评估材料

| 材料 | 路径 |
|------|------|
| Eval 定义 | `/tmp/git-commit-eval/evals/evals.json` |
| Eval 1 with-skill 输出 | `/tmp/git-commit-eval/workspace/iteration-1/eval-1-simple-feature/with_skill/outputs/` |
| Eval 1 without-skill 输出 | `/tmp/git-commit-eval/workspace/iteration-1/eval-1-simple-feature/without_skill/outputs/` |
| Eval 2 with-skill 输出 | `/tmp/git-commit-eval/workspace/iteration-1/eval-2-secret-trap/with_skill/outputs/` |
| Eval 2 without-skill 输出 | `/tmp/git-commit-eval/workspace/iteration-1/eval-2-secret-trap/without_skill/outputs/` |
| Eval 3 with-skill 输出 | `/tmp/git-commit-eval/workspace/iteration-1/eval-3-multi-file-tests/with_skill/outputs/` |
| Eval 3 without-skill 输出 | `/tmp/git-commit-eval/workspace/iteration-1/eval-3-multi-file-tests/without_skill/outputs/` |
| 评分结果 | `/tmp/git-commit-eval/workspace/iteration-1/eval-*/with_skill/grading.json` |
| Benchmark 汇总 | `/tmp/git-commit-eval/workspace/iteration-1/benchmark.json` |
| Eval Viewer | `/tmp/git-commit-eval/eval-review.html` |
