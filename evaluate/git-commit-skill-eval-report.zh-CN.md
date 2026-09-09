# git-commit Skill 评估报告

> 评估框架: [skill-creator](https://github.com/anthropics/skills/tree/main/skills/skill-creator)
> 评估日期: 2026-03-25
> 回归补充日期: 2026-04-10
> 评估对象: `git-commit`

---

`git-commit` 是一个安全增强型的提交工作流 skill，用于在执行 `git commit` 前完成仓库状态预检、暂存分析、密钥扫描、生态质量门禁和 Angular（Conventional Commits）格式消息生成。它最突出的三个亮点是：以 7 步强制工作流（Preflight → Staging → Secret Gate → Quality Gate → Compose → Commit → Report）替代了 Baseline 模型的「直接 add + commit」习惯，大幅降低了未检查变更直接入库的风险；通过正则表达式模式匹配 + 分层 Triage 实现了自动化密钥扫描，在场景 2 中精准拦截了硬编码 API Key；同时通过生态感知的质量门禁（Go/Node/Python/Java/Rust）确保每次提交前都运行了 vet/test/lint，而 Baseline 在所有场景中均跳过了此步骤。

## 1. Skill 概述

`git-commit` 是一个结构化的提交安全 skill，定义了 7 步强制工作流、硬性规则（Hard Rules）、5 种生态系统质量门禁、密钥扫描正则、以及 scope 发现机制。其目标是确保每个 commit 在执行前经过完整的安全预检、逻辑分组、密钥扫描、质量验证和规范化消息生成。2026-04 的补充回归又把新仓库 scope bootstrap、可执行 subject guard、timeout override 纳入了固定测试面。

**核心组件**:

| 文件 | 行数 | 职责 |
|------|------|------|
| `SKILL.md` | 169 | 主技能定义（7 步工作流、Hard Rules、密钥正则、scope 发现、subject guard、timeout override） |
| `references/quality-gate-go.md` | 25 | Go 生态质量门禁（go vet + go test，按包数分级） |
| `references/quality-gate-node.md` | 40 | Node.js/TS 质量门禁（pm 检测 + lint + tsc + test） |
| `references/quality-gate-python.md` | 53 | Python 质量门禁（ruff/flake8 + mypy/pyright + pytest） |
| `references/quality-gate-java.md` | 45 | Java/Kotlin 质量门禁（Maven/Gradle 多模块感知） |
| `references/quality-gate-rust.md` | 32 | Rust 质量门禁（clippy + cargo test，workspace 感知） |
| `scripts/tests/test_skill_contract.py` | 261 | 合约测试（frontmatter、必需章节、关键内容、引用完整性、golden 覆盖约束） |
| `scripts/tests/test_golden_scenarios.py` | 227 | golden 场景测试，覆盖 scope 解析、subject 校验和 timeout 选择 |

---

## 2. 测试设计

### 2.1 场景定义

回归补充说明：为保持可比性，原始 3 个评估场景不变。当前仓库版本新增了 7 个确定性 golden fixtures，专门覆盖原矩阵里没有单独拉出的 message 生成风险：新仓库 scope bootstrap、mixed roots 下的 scope omission、50 字符 executable guard，以及 timeout override 优先级。
回归补充说明（2026-09）：上文的场景结论是原始 A/B 评估的记录，保持不变。2026-09 的加固**没有重跑这些场景**，因此本报告中的任何分数都不反映该轮改动。那一轮针对一次外部评审展开，评审复现了四个脚本缺陷——生态检测排除了删除、密钥扫描与生态检测在 git 读取失败时以空输出返回 0（fail-open）、JSON 与大写键名的密钥既检测不到也不会在上下文行中遮罩、GNU `timeout` 分支缺少 `--kill-after`——以及两个测试质量缺陷：惩罚精简的 SKILL.md 行数*下限*，以及由测试文件自己用 Python 重新实现规则得出预期 scope 的 golden fixtures。scope 判定现已移入 `scripts/resolve-scope.sh`，golden fixtures 改为在真实 git 仓库上驱动该脚本；§1 的文件清单早于这次改动。当前 145 个测试中有 35 个在加固前的脚本上会失败——这才是它们确实固定了缺陷、而不只是把数量做大的证据。
第二轮补充说明（2026-09）：第二轮评审指出，第一轮修的是「被报告出来的那几处」，而不是背后的整类问题。又复现并修复了四个缺陷：按 git 转义后的显示形式读取路径（`core.quotePath`），导致中文文件名选不中任何门禁、`*.pem` 也不再匹配；阶段失败只检查了 git 读取那一段，分类器损坏时仍以空输出返回 0；脱敏规则让敏感键之前的长令牌在命中行上被完整打印；以及超时保护会静默退化到无法强制终止的工具。验证方式也从「新测试在旧代码上是否失败」升级为**变异测试**——把每个已修复的缺陷逐个重新注入，测试套件必须能抓住它。这一步查出有一个修复（密钥扫描里的 pipefail）对应的测试无论有没有修复都会通过；随后收紧了断言，要求每个失败阶段都必须各自报出错误。上文的场景结论仍早于以上全部改动，且没有重跑。
第三轮补充说明（2026-09）：第三轮发现了一个由**第二轮引入**的误阻断缺陷——pipefail、提前退出的上下文提取器、管道写入端三者叠加，会在任何超过管道缓冲区的 blob 上产生 SIGPIPE（退出 141），于是一次已完成的上下文截取被报成扫描故障。三行时干净，两万行时返回 2；所有小体积 fixture 都漏掉了，包括为 pipefail 那次修复专门写的那些。同时修复：SKILL.md 自己的 §7 报告命令会把被删除的中文路径转义成 `"\346\272\220…"`——路径转义这一类问题在三个脚本里都修了，却漏掉了文档命令。
第四轮补充说明（2026-09）：一直悬着的问题是证据范围而非规则，所以本轮产出的是证据——而证据两次改变了设计。用临时容器在五个环境里跑了实际脚本：macOS 15.6（BSD awk）、Debian 12（mawk 1.3.4 20200120）、Debian 12 + gawk 5.2.1、Ubuntu 24.04（mawk 1.3.4 20240123）、Alpine 3.24（BusyBox awk，无 perl）。只有真实矩阵才能暴露的两个事实：**Debian 12 的默认 awk 不支持正则区间**，十二个凭证模式在那里什么都匹配不到，能力探测必须拒绝运行而不是报告干净；以及 **BusyBox 的 `timeout` 根本没有实现 124 约定**（普通超时 143，带 `-k` 是 137），使上一轮"124 或 137"的契约在 Alpine 上就是错的。执行器现在按已耗时归一化为单一退出码，契约因为被改正而变短。真实 gitleaks 也第一次被实际执行：它从二进制自己的 `--help` 确认了退出码设计、显示 v8.18.4 没有 `git` 子命令（脚本正确地 fail-closed），并证伪了本仓库自己的一个 fixture——gitleaks 把 `AKIAIOSFODNN7EXAMPLE` 放进了白名单，需要真实扫描器命中的测试必须换用不在白名单里的值。
第五轮补充说明（2026-09）：三个缺陷，其中两个是第四轮引入的回归，一个使第四轮自己的评测证据失效。
第六轮补充说明（2026-09）：**第五轮声称取消缺陷已修复，这是错的。** 复测显示执行器仍会在门禁继续运行的情况下返回：`SIGHUP` 零秒返回 129 且门禁存活；忽略 TERM 的门禁在执行器被取消后又活了 12 秒并继续运行。原因是 perl 看护的子进程调用了 `setpgrp(0, 0)`——实测 perl `pgid 60922` 对门禁 `pgid 60923`——因此第五轮新增的包装层是在一个只含 perl 的组上发信号与升级；而且完全没有设置 `$SIG{HUP}`。修复方式是删掉子进程的 `setpgrp`（隔离本来就由上一层的 `set -m` 提供），于是同一个可寻址的组内包含 perl、门禁与孙进程。超时时的孙进程清理与所有退出码（超时 124、透传、截止前信号 143）已在 macOS/perl、Debian/GNU-timeout、Alpine/BusyBox 上重新验证。

值得留下的是第五轮为何会相信自己：它的测试驱动的是一个**把子进程留在同一进程组里的 `timeout` 替身**，因此从未复现出真正会出问题的拓扑。比真实系统更整洁的替身，会对着一个并不存在的系统确认修复。现在的测试直接驱动真实看护（SIGHUP、忽略 TERM 的门禁），并单独断言不变式——门禁所在的组必须可寻址，且既不是包装层的组也不是调用方的组。把修复前的看护原样恢复，现在会被抓到。

两个变异存活并被记录、而非追修：共享进程组之后，把看护旧的按 pid 转发的处理函数加回来是等价的；删掉取消消息背后的验证无法在行为上被抓到，因为其分支需要一个能在 SIGKILL 下存活的进程——它只以结构方式固定，并如实标注为结构性。
（1）`if docker run … | sed` 让矩阵判断的是 *sed*，因此容器以 42 退出时被汇总为「all exercised implementations pass」且退出码 0；完整模式下另一条 `pytest … | tail` 以同样方式掩盖失败套件。两处现在都先取状态再排版。（2）为统一超时退出码，`exec` 被换成了不转发任何信号的包装层：向执行器发 SIGTERM 后它返回 143，而门禁继续运行并在 2 秒后写出副作用。取消现在发给工具自己的进程组，等组内清空，必要时升级为 KILL，然后才退出。
（3）**评测的 skill 臂一直在没有加载 skill 的情况下运行**——`SKILL_DIR` 取自 `$0`，复制运行器就使其失效，而标签仍是 `skill`。此前作为成绩报告的四个格子是无效的；它们被删除，而不是加注。

评测现在在缺少 `SKILL.md` 时拒绝启动，把 skill 路径/行数/哈希写进每份转录以便逐格审计有效性，并支持 `EVAL_SKILL_DIR`/`EVAL_SCEN_DIR`。**评测目前的定论：未测得决策收益。** 两臂都有有效数据的场景（01–06）结论一致，因此那些格子是关于场景而非关于 skill 的证据。场景 10 是已知唯一的区分用例，且只在评分从「仅长度」收紧为「格式且长度」之后才成立。

现在有六个故障注入变异覆盖这些修复，全部被杀。其中两个最初存活，值得记录：断言取消后「完全没有副作用」是靠运气通过的（优雅 TERM 的存在本就是为了让门禁**可以**收尾），而断言进程组 kill 让取消「更快」在正确代码上就失败了——组形式真正买到的是升级动作能触及整棵进程树。套件：macOS、Ubuntu 24.04、Alpine 各 191 通过 / 5 跳过；无区间支持的 Debian 12 为 160 通过 / 36 跳过。

套件本身对自己的适用范围判断错误：在无区间支持的 Debian 上它产生了 31 项失败，而脚本的行为是对的。测试现在按能力设门，跳过时给出点名该 awk 和修复方式的理由；装上 gawk 后门打开，172 项全跑。

`scripts/eval/` 补上了决策分支探针——任何确定性套件都触及不到的那一件事。它的 README 明确写出边界：评的是 plan 模式下的一个决策声明、结果不确定、按次报告而不做平均、带一个无 skill 的对照臂、缺失答案记为 INCOMPLETE 而不计入分数。**仍未验证：** Windows/WSL、`original-awk`、macOS 上的 gitleaks，以及 Agent 的执行保真度（区别于分支选择）。本报告前面的场景结论早于全部四轮改动，且没有重跑。

决策探针结果（2026-09-07，1 次重复）：skill 臂 6/6——其中值得注意的是密钥门禁返回 2 时选择 STOP，以及 `testdata/` 下疑似真实密钥时选择 ASK。对照臂只覆盖了场景 01–02，而这两个基线模型本来也答对；**因此 04–06 没有对照数据，其表现无法归因**，且 1 次重复只能说明分支可达，不能说明稳定。

验证范围做了扩展；扩展不到的地方则明确写出：`scripts/run_portability_matrix.sh` 按可用 awk 逐个重跑套件，一个都没跑到就返回非零（空矩阵不是绿矩阵）；真实 `gitleaks` 契约测试在二进制存在时运行，不存在时是一个**可见的** skip（`run_regression.sh -rs`）；全流程测试按 §1–§7 顺序执行并断言真的落下提交——§7 那个缺陷正是它抓到的。

**当前证据的诚实边界。** 这台机器只有一个 awk（BSD 20200816，支持区间）、没有 GNU coreutils 的 `timeout`、也没有 gitleaks——因此 GNU `--kill-after` 分支是通过对 shim 断言 argv 证明的，而非真实二进制；区间缺失时的拒绝路径也是靠 shim 证明，而非一个真正不支持区间的 awk；六个 awk 行里有五行是 UNVERIFIED。运行器会把这些如实报出，而不是暗示已覆盖。上文的场景结论仍早于全部三轮改动，且没有重跑。

| # | 场景名称 | 仓库类型 | 核心挑战 | 期望结果 |
|---|----------|----------|----------|----------|
| 1 | 干净的 Go 功能 | Go calculator | 2 个文件的单一逻辑变更，所有检查应通过 | 正常提交，CC 格式 |
| 2 | Python 多关注点 + 密钥 | Python myapp | 4 个文件跨 3 个逻辑关注点 + 硬编码 `sk-proj-` API Key | 阻断提交，报告密钥 |
| 3 | Node.js >8 文件混乱历史 | Node task-api | 10 个文件 + 非 CC 历史（"WIP", "fix bug"） | 列出文件确认，分组提交 |

### 2.2 断言矩阵（35 项）

**场景 1 — 干净 Go 功能 (13 项)**

| ID | 断言 | With-Skill | Without-Skill |
|----|------|:----------:|:-------------:|
| A1 | 系统化运行所有 Preflight 检查（7 项，带命令） | PASS | FAIL |
| A2 | 检查未解决的合并冲突（diff-filter=U） | PASS | FAIL |
| A3 | 检查 detached HEAD 状态 | PASS | FAIL |
| A4 | 检查 rebase/merge/cherry-pick 进行中 | PASS | FAIL |
| A5 | 分析暂存：正确识别为单一逻辑变更 | PASS | PASS |
| A6 | 运行密钥/敏感内容扫描（filename + content 正则） | PASS | FAIL |
| A7 | 运行质量门禁：go vet + go test | PASS | FAIL |
| A8 | 检查 git log 确定 scope 频率 | PASS | PARTIAL |
| A9 | 生成 CC 格式提交消息 | PASS | PASS |
| A10 | Subject line <= 50 字符（含 type(scope):） | PASS | PASS |
| A11 | 使用祈使语气（imperative mood） | PASS | PASS |
| A12 | 输出结构化 Post-commit 报告（hash + 文件 + gate 状态） | PASS | FAIL |
| A13 | 遵循有序 7 步工作流（Output Contract） | PASS | FAIL |

**场景 2 — Python 多关注点 + 密钥 (12 项)**

| ID | 断言 | With-Skill | Without-Skill |
|----|------|:----------:|:-------------:|
| B1 | 系统化运行所有 Preflight 检查 | PASS | FAIL |
| B2 | 识别 3 个独立逻辑关注点（用户功能、配置、日志） | PASS | PARTIAL |
| B3 | 提议拆分为多个独立提交 | PASS | PARTIAL |
| B4 | 使用特定正则模式运行密钥扫描 | PASS | FAIL |
| B5 | 检测到硬编码 `sk-proj-` API Key | PASS | PASS |
| B6 | 阻断提交（BLOCK） | PASS | PASS |
| B7 | 报告精确的文件、行号和匹配模式名 | PASS | PARTIAL |
| B8 | 建议修复方案（env var + .env + 密钥轮换） | PASS | PASS |
| B9 | 运行质量门禁（pytest + ruff/flake8） | PASS | FAIL |
| B10 | 为每组逻辑变更生成 CC 格式消息 | PASS | PARTIAL |
| B11 | 所有 Subject line <= 50 字符 | PASS | PARTIAL |
| B12 | 遵循结构化输出合约 | PASS | FAIL |

**场景 3 — Node.js >8 文件混乱历史 (10 项)**

| ID | 断言 | With-Skill | Without-Skill |
|----|------|:----------:|:-------------:|
| C1 | 系统化运行所有 Preflight 检查 | PASS | FAIL |
| C2 | 检测 >8 文件并列出完整文件列表请求确认 | PASS | FAIL |
| C3 | 将变更划分为逻辑分组 | PASS | FAIL |
| C4 | 提议多个独立提交 | PASS | FAIL |
| C5 | 运行密钥扫描 | PASS | PARTIAL |
| C6 | 运行质量门禁（npm test + npm run lint） | PASS | FAIL |
| C7 | 检查 git log 获取 scope 频率 | PASS | PASS |
| C8 | 检测无 CC 历史 → 省略 scope | PASS | FAIL |
| C9 | 所有 Subject line <= 50 字符 | PASS | FAIL |
| C10 | 遵循结构化输出合约 | PASS | FAIL |

---

## 3. 通过率对比

### 3.1 总体通过率

| 配置 | 通过 | 部分通过 | 失败 | 通过率 |
|------|------|---------|------|--------|
| **With Skill** | 35 | 0 | 0 | **100%** |
| **Without Skill** | 8 | 6 | 21 | **23%** (含 PARTIAL 按 0.5 计 = 31%) |

**通过率提升: +77 百分点**（严格）/ +69pp（含 PARTIAL）

### 3.2 按场景通过率

| 场景 | With-Skill | Without-Skill | 差异 |
|------|:----------:|:-------------:|:----:|
| 1. 干净 Go 功能 | 13/13 (100%) | 4.5/13 (35%) | +65pp |
| 2. Python 多关注点 + 密钥 | 12/12 (100%) | 5.5/12 (46%) | +54pp |
| 3. Node.js >8 文件混乱历史 | 10/10 (100%) | 1.5/10 (15%) | +85pp |

### 3.3 实质性维度（不依赖流程结构的核心能力）

为排除"流程断言偏差"，额外评估 15 项与工作流结构无关的实质性检查：

| ID | 检查项 | With-Skill | Without-Skill |
|----|--------|:----------:|:-------------:|
| S1 | 场景 1: 运行测试（go test） | PASS | FAIL |
| S2 | 场景 1: 运行静态分析（go vet） | PASS | FAIL |
| S3 | 场景 1: 密钥扫描 | PASS | FAIL |
| S4 | 场景 1: CC 格式消息 | PASS | PASS |
| S5 | 场景 1: Subject <= 50 字符 | PASS | PASS |
| S6 | 场景 2: 识别多个逻辑关注点 | PASS | PARTIAL |
| S7 | 场景 2: 检测硬编码 API Key | PASS | PASS |
| S8 | 场景 2: 阻断包含密钥的提交 | PASS | PASS |
| S9 | 场景 2: 建议密钥修复方案 | PASS | PASS |
| S10 | 场景 2: 运行质量门禁 | PASS | FAIL |
| S11 | 场景 3: >8 文件触发确认 | PASS | FAIL |
| S12 | 场景 3: 提议拆分提交 | PASS | FAIL |
| S13 | 场景 3: 运行测试（npm test） | PASS | FAIL |
| S14 | 场景 3: 检测无 CC 历史 → 适配 scope 策略 | PASS | FAIL |
| S15 | 场景 3: Subject <= 50 字符 | PASS | FAIL |

**实质性通过率**: With-Skill **15/15 (100%)** vs Without-Skill **5.5/15 (37%)**，提升 **+63pp**。

---

## 4. 关键差异分析

### 4.1 With-Skill 独有的行为（Baseline 完全缺失）

| 行为 | 影响 |
|------|------|
| **7 步强制工作流** | 每步明确执行，带精确命令和预期结果，确保无遗漏 |
| **6 项 Preflight 检查** | 冲突检测、detached HEAD、rebase/merge/cherry-pick 状态、submodule 感知 |
| **正则密钥扫描** | 13 种密钥模式（AWS/GitHub/Slack/Google/Stripe/OpenAI/DB URI 等）+ 文件名模式 |
| **4 级 Triage 过滤** | allowlist → test/fixture → doc → comment，避免误报 |
| **生态感知质量门禁** | 自动检测 Go/Node/Python/Java/Rust，运行对应 vet/test/lint 工具 |
| **>8 文件确认阈值** | 超过 8 个变更文件时强制列出并请求用户确认，防止意外暂存 |
| **Scope 频率发现** | 基于 `git log` 频率（>= 3 次同 scope）决定是否使用 scope，避免凭空发明 |
| **结构化 Post-commit 报告** | 包含 hash、文件摘要、gate 状态的完整提交记录 |

### 4.2 Baseline 能做到但质量较低的行为

| 行为 | With-Skill 质量 | Without-Skill 质量 |
|------|-----------------|-------------------|
| 密钥检测 | 正则模式匹配 + 文件名扫描 + Triage 分层 | diff 人工审查，能发现明显密钥但无工具证据 |
| 逻辑分组 | 精确分组 + 提议拆分方案 + 字符数计算 | 识别不同关注点但倾向于单次提交 |
| CC 消息生成 | scope 频率分析 + 字符计数 + 祈使语气校验 | 能生成 CC 格式但不检查字符长度，偶尔超限 |
| 质量验证 | go vet + go test / npm test + lint / pytest 等 | 仅 git status 验证，不运行任何测试或 lint |
| 提交后验证 | 结构化报告（hash、文件、gate 状态） | 仅 git status 确认成功 |

### 4.3 场景级关键发现

**场景 1（干净 Go 功能）**:
- **With-Skill**: 全部 7 步通过。Preflight 7 项检查完整执行；密钥扫描无匹配；go vet + go test 全通过；scope `calc` 从历史频率中确认；消息 `feat(calc): add multiply operation`（35 字符）精确简洁；Post-commit 报告完整。
- **Without-Skill**: 仅运行 `git status` / `git diff` / `git log`（3 步），**未运行 go vet 或 go test**，无密钥扫描，无 Preflight 检查。消息 `feat(calc): add Multiply function`（33 字符）格式正确但附加了系统默认的 Co-Authored-By 行。无 Post-commit 报告。

**场景 2（Python 密钥）**:
- **With-Skill**: Preflight 通过后，精确识别 3 个逻辑关注点。密钥扫描在 `src/config.py:5` 上同时匹配 `sk-[A-Za-z0-9]{20,}` 和 `api[_-]?key\s*=` 两个模式。Triage 确认非 test/doc/comment → **BLOCK**。报告包含精确文件名、行号、匹配模式名和修复建议（`os.environ["API_KEY"]` + 密钥轮换）。提议 3 个分拆提交，每个 Subject 均 <= 50 字符（49/44/45）。
- **Without-Skill**: 通过 diff 人工审查发现了 `sk-proj-` 密钥（**PASS**），正确阻断并建议 env var 替换。但无正则模式证据链，仅提及文件名和行号，未报告匹配的正则模式名。倾向于单次提交（或最多 2 次），未识别出日志工具作为独立关注点。

**场景 3（Node.js 混乱历史）**:
- **With-Skill**: 检测 10 个文件 > 8 阈值，列出完整文件列表请求确认。分析后识别 6 个逻辑分组（config/middleware、auth+test、task+test、user+test、index wiring、README）。`git log` 无 CC 格式 → 省略 scope → 使用 `type: subject` 格式。6 个 Subject 均 <= 50 字符（42/44/42/38/等）。运行 `npm test` + `npm run lint`（均 exit 0）。
- **Without-Skill**: **直接将 10 个文件作为单次提交**，未触发任何文件数量阈值，未进行逻辑分组。消息 `feat: add auth, users, and tasks modules with tests`（**51 字符，超过 50 限制**）。未运行 `npm test` 或 `npm run lint`。虽然注意到非 CC 历史但选择忽略（仍用 CC 格式，这是正确的）。

---

## 5. Token 效费比分析

### 5.1 Skill 上下文 Token 成本

| 组件 | 行数 | 估算 Token 数 | 加载时机 |
|------|------|-------------|----------|
| `SKILL.md` | 169 | ~1,050 | 始终加载 |
| `quality-gate-go.md` | 25 | ~150 | Go 项目按需加载 |
| `quality-gate-node.md` | 40 | ~240 | Node 项目按需加载 |
| `quality-gate-python.md` | 53 | ~320 | Python 项目按需加载 |
| `quality-gate-java.md` | 45 | ~270 | Java/Kotlin 项目按需加载 |
| `quality-gate-rust.md` | 32 | ~190 | Rust 项目按需加载 |
| **典型场景总计** | ~209-237 | **~1,300-1,470** | SKILL.md + 1 个生态门禁 |

注：每次提交仅加载 1 个生态系统的 quality gate 参考文件，不会全部加载。

### 5.2 实际运行 Token 消耗（6 个评估代理）

| 代理 | 场景 | Total Tokens | 耗时 (s) | Tool Calls |
|------|------|-------------|----------|------------|
| S1 With-Skill | 干净 Go 功能 | 28,841 | 128 | 27 |
| S1 Without-Skill | 干净 Go 功能 | 22,156 | 78 | 11 |
| S2 With-Skill | Python 密钥 | 32,732 | 179 | 25 |
| S2 Without-Skill | Python 密钥 | 23,217 | 104 | 15 |
| S3 With-Skill | Node.js 混乱 | 30,068 | 122 | 42 |
| S3 Without-Skill | Node.js 混乱 | 33,290 | 170 | 24 |

**With-Skill 均值**: ~30,547 tokens, ~143s, ~31 tool calls
**Without-Skill 均值**: ~26,221 tokens, ~117s, ~17 tool calls

With-Skill 代理平均多消耗 **+17% tokens** 和 **+22% 时间**，主要用于执行额外的 Preflight 检查、密钥扫描、质量门禁等步骤。场景 3 中 Without-Skill 反常地消耗了更多 tokens（33,290 vs 30,068），因为代理在缺乏结构指导的情况下进行了更多探索性的文件读取。

### 5.3 效费比计算

| 指标 | 值 |
|------|------|
| 总体通过率提升 | +77pp（严格）/ +69pp（含 PARTIAL） |
| 实质性通过率提升 | +63pp |
| Skill 上下文成本（典型） | ~1,300 tokens |
| 运行时额外 token 开销（均值） | +4,326 tokens (+17%) |
| **每 1% 通过率提升的 Token 成本（上下文，严格）** | **~17 tokens/1%** |
| **每 1% 通过率提升的 Token 成本（上下文，实质性）** | **~21 tokens/1%** |
| **每 1% 通过率提升的 Token 成本（含运行时开销）** | **~73 tokens/1%** |

注：「上下文成本」仅计 SKILL.md + reference 加载的 token；「运行时开销」包括额外的工具调用（Preflight、secret scan、quality gate 等命令执行）。

### 5.4 与其他 Skill 效费比对比

| Skill | 上下文 Token | 通过率提升 | 上下文 Tok/1% | 含运行时 Tok/1% |
|-------|------------|-----------|-------------|----------------|
| **`git-commit`** | **~1,300** | **+77pp** | **~17** | **~73** |
| `create-pr` | ~3,400 | +71pp | ~48 | — |
| `go-makefile-writer` | ~1,960-4,300 | +31pp | ~63-139 | — |

`git-commit` 在上下文 tokens/1% 指标上表现最优（~17），主要因为：
1. **SKILL.md 极其精简**（169 行），通过渐进式加载 references 避免上下文膨胀，同时给可执行 guard 留出了空间
2. **Quality gate 分文件设计**极为高效——每次只加载 1 个生态系统的参考，平均仅增加 ~150-320 tokens
3. **通过率差异大**（+77pp）——提交是一个 Baseline 模型严重缺乏结构化安全流程的领域

即使计入运行时额外开销（~73 tok/1%），仍优于 `go-makefile-writer` 的上下文成本。这表明 skill 引导的额外工具调用（质量门禁、密钥扫描）虽然增加了 token 消耗，但其产出的安全价值远超成本。

### 5.5 Token 回报曲线分析

```
投入 Token 量与回报的映射关系:

~1,150 tokens (SKILL.md only):
  → 获得: 7 步工作流、Hard Rules、密钥正则、Staging 阈值、Scope 发现机制
  → 预计覆盖: ~85% 的通过率提升

+150-320 tokens (1 个 quality-gate reference):
  → 获得: 生态感知的 vet/test/lint 命令和阈值
  → 预计覆盖: +12% 的通过率提升（Quality Gate 断言）

+0 tokens (edge cases / examples 已内联):
  → 获得: 空提交、合并残留、submodule 处理
  → 预计覆盖: +3%（边缘场景覆盖）
```

SKILL.md 本身提供了约 85% 的价值。渐进式 reference 加载设计确保了最优的 token 使用效率。

---

## 6. 综合评分

### 6.1 分维度评分

| 维度 | With Skill | Without Skill | 差值 |
|------|-----------|--------------|------|
| Preflight 检查完整度（6 项系统化检查） | 5.0/5 | 1.0/5 | +4.0 |
| 密钥扫描能力（正则模式 + Triage） | 5.0/5 | 2.5/5 | +2.5 |
| 质量门禁执行（生态感知 vet/test/lint） | 5.0/5 | 1.0/5 | +4.0 |
| 暂存逻辑（分组 + 阈值 + 确认） | 5.0/5 | 2.0/5 | +3.0 |
| CC 消息规范度（scope 发现 + 字符计数） | 5.0/5 | 3.5/5 | +1.5 |
| 结构化输出报告（7 步有序报告） | 5.0/5 | 1.5/5 | +3.5 |
| **综合均值** | **5.0/5** | **1.9/5** | **+3.1** |

**维度得分说明**:

- **Preflight 检查完整度**: With-Skill 在 3 个场景中均系统化运行 6 项 Preflight（work tree、status、conflicts、branch、rebase、merge/cherry-pick），并检查 submodule。Without-Skill 仅运行 `git status`/`git diff`/`git log`，无冲突检测、无 detached HEAD 检查、无 rebase/merge 状态检查。
- **密钥扫描能力**: With-Skill 使用 13 种正则模式 + 文件名模式进行双重扫描，匹配后通过 4 级 Triage 过滤误报。场景 2 中精准匹配 `sk-[A-Za-z0-9]{20,}` 和 `api[_-]?key\s*=`。Without-Skill 通过 diff 阅读发现了明显密钥（场景 2 的 `sk-proj-`），但无工具证据链、无模式名报告。
- **质量门禁执行**: With-Skill 在 3 个场景中分别运行了 go vet + go test、pytest + ruff（deferred）、npm test + npm run lint。Without-Skill 在**所有 3 个场景中均未运行任何测试或 lint 工具**——这是最大的能力差距。
- **暂存逻辑**: With-Skill 场景 2 精确识别 3 个逻辑关注点并提议 3 次拆分提交；场景 3 触发 >8 文件阈值，列出完整文件列表并识别 6 个逻辑分组。Without-Skill 场景 2 倾向单次提交，场景 3 直接将 10 个文件合并为一次提交。
- **CC 消息规范度**: With-Skill 3/3 场景 Subject 均 <= 50 字符（35/49/44/45/42/38 等），基于 `git log` 频率分析决定 scope 使用。Without-Skill 场景 3 Subject **51 字符超过限制**，且不进行 scope 频率分析。
- **结构化输出报告**: With-Skill 严格遵循 7 步工作流输出，Post-commit 报告包含 hash、文件、gate 状态。Without-Skill 仅 `git status` 确认成功，无结构化报告。

### 6.2 加权总分

| 维度 | 权重 | 得分 | 理由 | 加权 |
|------|------|------|------|------|
| Assertion 通过率（delta） | 25% | 10.0/10 | +77pp（严格）/ +63pp（实质性），Token 效费比最优 | 2.50 |
| 质量门禁执行 | 20% | 10.0/10 | 3/3 场景运行生态对应工具，Baseline 全部跳过 | 2.00 |
| 密钥扫描能力 | 15% | 9.5/10 | 正则 + Triage 优秀；可增加更多 token 模式（如 JWT） | 1.43 |
| 暂存逻辑与分组 | 15% | 10.0/10 | >8 阈值 + 逻辑分组 + 拆分提议 + hunk 级暂存 | 1.50 |
| Token 效费比 | 15% | 9.0/10 | ~17 tok/1% 三个 skill 中最优；渐进加载设计优雅 | 1.35 |
| CC 消息规范度 | 10% | 9.5/10 | scope 频率发现 + 字符计数；50 字符限制严格执行 | 0.95 |
| **加权总分** | **100%** | | | **9.73/10** |

### 6.3 与其他 Skill 综合评分对比

| Skill | 加权总分 | 通过率 delta | Tokens/1% | 最大优势维度 |
|-------|---------|-------------|-----------|-------------|
| **git-commit** | **9.73/10** | +77pp | ~17 | 质量门禁 (+4.0)、Preflight (+4.0) |
| create-pr | 9.55/10 | +71pp | ~48 | Gate 流程 (+3.5)、Output Contract (+4.0) |
| go-makefile-writer | 9.16/10 | +31pp | ~63 | CI 可复现性 (+3.0)、Output Contract (+4.0) |

`git-commit` 获得三个 skill 中的**最高综合评分**，主要因为：

1. **Token 效费比显著领先**（~17 tok/1% vs ~48 和 ~63）：渐进式 reference 加载设计使 SKILL.md 仅 169 行，却覆盖了 5 种生态系统
2. **通过率差异最大**（+77pp）：git commit 是 Baseline 模型在安全预检和质量门禁方面最薄弱的领域——Baseline 在所有场景中均跳过了测试运行
3. **无明显短板**：6 个维度中无低于 9.0 的评分

**失分点**:
- 密钥扫描（9.5/10）：当前正则覆盖了主流密钥类型，但缺少 JWT、Twilio、Mailgun 等新兴 SaaS 平台的 token 模式
- Token 效费比（9.0/10）：虽然绝对效率最优，但 Edge Cases 章节（~100 tokens）在典型场景中使用率较低

---

## 7. 结论

`git-commit` skill 是本次评估中**通过率差异最大**（+77pp）且 **Token 效费比最优**（~17 tok/1%）的 skill。这表明 git commit 是一个 Baseline 模型**高度缺乏结构化安全流程**的领域——Baseline 在所有 3 个测试场景中均未运行任何测试或 lint 工具，skill 的边际价值极高。

**核心价值点**:
1. **质量门禁零到一**：Baseline 从不运行 vet/test/lint，skill 实现了「每次提交必过质量门禁」的跨越
2. **正则密钥扫描**：13 种模式 + 4 级 Triage，在场景 2 中精准拦截了硬编码 API Key，提供了 Baseline 人工审查无法匹配的工具证据链
3. **暂存安全网**：>8 文件强制确认 + 逻辑分组拆分，在场景 3 中阻止了 10 个混合文件的单次提交
4. **渐进式 Reference 加载**：5 种生态门禁分文件存储、按需加载，使典型 token 成本仅 ~1,300（SKILL.md + 1 gate）

**Skill 设计亮点**:
- SKILL.md 严格控制在 169 行（目标 <= 200），信息密度极高
- Quality gate 通过 reference 文件实现了「一个 SKILL.md 支持 5 种生态」的设计，是渐进式加载的典范
- Hard Rules 前置 + 精确阈值（8 文件、50 字符、3 次 scope 频率）使规则可验证、不模糊

**改进建议**:
1. 密钥正则可扩展覆盖 JWT、Twilio (`SK[0-9a-fA-F]{32}`)、Mailgun 等新兴平台
2. 可增加 `.commit-secret-allowlist` 文件的创建指导，降低用户首次配置的摩擦
3. Edge Cases 章节可考虑移入 reference 文件，进一步精简 SKILL.md（预计节省 ~80 tokens）
