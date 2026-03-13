# go-makefile-writer Skill 评审报告

> 评估框架: [skill-creator](https://github.com/anthropics/skills/tree/main/skills/skill-creator)
> 评估日期: 2026-03-11
> 评估对象: `go-makefile-writer`

---

`go-makefile-writer` 是一个为 Go 仓库创建或重构 Makefile 的 skill，适合统一构建、测试、lint、运行和 CI 入口，也适合把已有但质量不一的 Makefile 做最小代价收敛。它最突出的三个亮点是：能根据仓库结构自动规划目标集和命名规则，输出更稳定、可读的 Makefile；对 `install-tools`、`ci`、`tidy` 等关键目标有一致的版本锁定和规范约束，减少后续漂移；在 Refactor 模式下强调 minimal-diff 和向后兼容，既修问题也尽量不破坏已有使用习惯。

## 一、评估概览

本次评估从**实际任务表现**和 **Token 效费比**两个维度对 go-makefile-writer skill 进行全面评审。设计 3 个递进复杂度的 Makefile 生成/重构场景（单二进制创建、多二进制+Docker 创建、缺陷 Makefile 重构），每个场景分别运行 with-skill 和 without-skill 配置，共 3 场景 × 2 配置 = 6 次独立 subagent 运行，对照 42 条 assertion 进行评分。

| 维度 | With Skill | Without Skill | 差异 |
|------|-----------|--------------|------|
| **Assertion 通过率** | **42/42 (100%)** | 29/42 (69.0%) | **+31.0 百分点** |
| **命名规范合规** | 3/3 全对 | 1/3 | 最大单项差异 |
| **install-tools 版本锁定** | 3/3 | 0/3 | Skill 独有 |
| **Output Contract 结构化报告** | 3/3 | 0/3 | Skill 独有 |
| **ci target 命名** | 3/3 | 1/3 | Skill 一致 |
| **tidy target** | 3/3 | 2/3 | Skill 一致 |
| **Skill Token 开销（SKILL.md 单文件）** | ~1,960 tokens | 0 | — |
| **Skill Token 开销（含参考资料）** | ~4,700 tokens | 0 | — |
| **每 1% 通过率提升的 Token 成本** | ~63 tokens（SKILL.md only）/ ~152 tokens（full） | — | — |

---

## 二、测试方法

### 2.1 场景设计

| 场景 | 仓库 | 核心考察点 | Assertions |
|------|------|-----------|-----------|
| Eval 1: simple-create | 单 `cmd/api`，Go 1.23，无 Makefile | 基础目标集、命名规范、版本注入、质量门禁 | 15 |
| Eval 2: multi-binary-docker | 3 个 `cmd/*`，Dockerfile，Go 1.25 | 多二进制目标、Docker 目标、交叉编译 | 15 |
| Eval 3: refactor-defects | 现有 Makefile 含 6 处缺陷 | 重构模式、向后兼容、缺陷修复覆盖率 | 12 |

### 2.2 执行方式

- 每个场景创建独立 Git 仓库，预置代码和 go.mod
- With-skill 运行先读取 SKILL.md 及其引用的参考资料（golden template、quality guide）
- Without-skill 运行不读取任何 skill，按模型默认行为生成 Makefile
- 所有运行在独立 subagent 中并行执行

---

## 三、Assertion 通过率

### 3.1 总览

| 场景 | Assertions | With Skill | Without Skill | 差值 |
|------|-----------|-----------|--------------|------|
| Eval 1: simple-create | 15 | **15/15 (100%)** | 8/15 (53.3%) | +46.7% |
| Eval 2: multi-binary-docker | 15 | **15/15 (100%)** | 11/15 (73.3%) | +26.7% |
| Eval 3: refactor-defects | 12 | **12/12 (100%)** | 10/12 (83.3%) | +16.7% |
| **总计** | **42** | **42/42 (100%)** | **29/42 (69.0%)** | **+31.0%** |

### 3.2 Without-Skill 失败的 13 条 Assertion 归类

| 失败类型 | 次数 | 涉及 Eval | 说明 |
|---------|------|----------|------|
| **命名规范不合规** | 2 | Eval 1 | `build`/`run` 而非 `build-api`/`run-api`，违反 cmd/-path semantics |
| **缺少 install-tools 或版本未锁定** | 3 | Eval 1/2/3 | Eval 1 缺少 install-tools；Eval 2 用 `@latest`；Eval 3 缺少 |
| **缺少结构化 Output Report** | 3 | Eval 1/2/3 | 无 Go 版本、layout、entrypoints、validation 结果的结构化报告 |
| **ci target 缺失或命名不同** | 2 | Eval 1/2 | Eval 1 无 ci；Eval 2 名为 `check` |
| **缺少 tidy target** | 1 | Eval 1 | 无 `go mod tidy` + `go mod verify` |
| **lint 工具检查缺失** | 1 | Eval 1 | lint 定义为 vet+fmt-check，无 golangci-lint |
| **docker-build 变量不规范** | 1 | Eval 2 | 用 DOCKER_IMAGE 而非 IMAGE_NAME/IMAGE_TAG |

### 3.3 趋势：Skill 优势随场景复杂度递减

| 场景复杂度 | With-Skill 优势 |
|-----------|----------------|
| Eval 1（简单） | +46.7%（7 条失败） |
| Eval 2（中等） | +26.7%（4 条失败） |
| Eval 3（重构） | +16.7%（2 条失败） |

这符合预期：**Eval 3 的用户提示已明确列出了全部 6 处缺陷**，相当于把 skill 的知识内嵌到了提示中。Eval 1 的提示最简洁，最依赖 skill 提供的约定知识。

---

## 四、逐维度对比分析

### 4.1 命名规范（cmd/-path semantics）

这是**单项差异最大的维度**，在 Eval 1 中贡献了 2 条 assertion 失败。

| 目录结构 | With Skill | Without Skill |
|---------|-----------|--------------|
| `cmd/api/main.go` | `build-api`, `run-api` | `build`, `run` |
| `cmd/worker/main.go` | `build-worker`, `run-worker` | `build-worker`, `run-worker` |
| `cmd/server/main.go` | `build-server` | `build-server` |

**分析**: Without-skill 在多二进制场景（Eval 2/3）中自然使用了 per-binary 命名，但在**单二进制场景中默认使用泛化名称**。Skill 的规则 "Map target names to `cmd/` path semantics: `cmd/<name>` → `build-<name>`" 确保了一致性。

**实际价值**: 一致的命名规范使得：
- 项目从单二进制扩展到多二进制时无需重命名 target
- 团队间 Makefile 风格统一
- CI 脚本中可预测 target 名称

### 4.2 install-tools 与版本锁定

| 维度 | With Skill | Without Skill |
|------|-----------|--------------|
| Eval 1 | `install-tools` pinned v1.62.2 | ❌ 无 install-tools |
| Eval 2 | `install-tools` pinned v1.62.2 | ❌ lint 内 auto-install `@latest` |
| Eval 3 | `install-tools` pinned v1.62.2 | `install-tools` pinned v1.62.2 ✅ |

**分析**: Without-skill 在 Eval 2 中将 golangci-lint 安装逻辑嵌入 lint target 中（`@latest` 自动安装），这在本地开发中可用，但在 CI 中会引发：
- 非确定性构建（不同时间安装不同版本）
- 每次 CI 运行都重新安装工具（慢）

Skill 的规则明确要求 "Pin tool versions in `install-tools` for CI reproducibility"。

### 4.3 Output Contract（结构化报告）

这是 Skill **独有**的差异化产出。With-skill 在每次运行后产出包含以下内容的报告：

| 报告项 | Eval 1 | Eval 2 | Eval 3 |
|--------|--------|--------|--------|
| Mode（Create/Refactor + 理由） | ✅ | ✅ | ✅ |
| Go version（from go.mod） | 1.23 | 1.25 | 1.24 |
| Layout（single-module/monorepo） | ✅ | ✅ | ✅ |
| Entrypoints discovered | cmd/api | cmd/api, cmd/worker, cmd/migrate | cmd/server, cmd/cli |
| New/updated targets 列表 | ✅ | ✅ | ✅ |
| Deprecated/aliased targets | (none) | (none) | build-srv → build-server |
| Before vs After 对比（Refactor） | N/A | N/A | ✅ |
| Validation 结果（make help/test/build） | ✅ | ✅ | ✅ |
| Anti-pattern checklist | ✅ | — | — |

Without-skill 产出简洁的任务摘要，但无结构化的 Output Contract。

**实际价值**: Output Contract 使得：
- Makefile 变更可审计（PR review 时知道改了什么、为什么）
- Refactor 模式下的向后兼容性可追溯
- CI 验证结果有据可查

### 4.4 ci target 命名

| 场景 | With Skill | Without Skill |
|------|-----------|--------------|
| Eval 1 | `ci` | ❌ 无此 target |
| Eval 2 | `ci` | `check`（类似但命名不同） |
| Eval 3 | `ci` | `ci` ✅ |

Skill 规定 "CI target: `ci` (fmt-check + lint + test + cover-check in one pass)"。Without-skill 在 Eval 2 中使用了 `check` 名称，内容为 `fmt-check vet test`（缺少 cover-check），与标准 CI pipeline 不完全对齐。

### 4.5 Golden Template 的影响

With-skill 的 Makefile 在结构上与 golden template 高度一致（变量区→build→run→quality→ci→version→tools→clean→phony→help），而 without-skill 的结构各异。

**Eval 2 的关键差异**: Without-skill 使用了 `$(eval $(call build-template,...))` 的动态元编程模式来生成 build targets，而 with-skill 按 golden template 使用了**显式 per-binary targets**。Skill 的 Anti-Patterns 区明确标记了 "Overly dynamic Make metaprogramming (eval/call/define) that reduces readability when explicit targets would be clearer"。

### 4.6 Makefile 实际质量对比

以 Eval 2（最复杂的场景）为例，对比两份 Makefile 的关键差异：

| 特性 | With Skill | Without Skill |
|------|-----------|--------------|
| build target 风格 | 显式 per-binary | `$(eval $(call build-template))` 动态 |
| `-ldflags` 位置 | 每个 build target 显式 | GOBUILD 变量内嵌（`CGO_ENABLED=0` 也内嵌） |
| clean 行为 | `rm -rf bin/ coverage.out` | `rm -rf bin/ coverage.out` + `go clean -cache -testcache`（过度清理） |
| lint 安装 | 独立 `install-tools`，pinned | 嵌入 lint target，`@latest` |
| cross-compile | `build-linux` target | 无 |
| cover-check 阈值 | `COVER_MIN ?= 80` | 无 |
| help 格式 | awk 固定宽度，无 color | grep+awk+sort，带 ANSI color |

---

## 五、Token 效费比分析

### 5.1 Skill 体积

go-makefile-writer 是一个**多文件 skill**，包含 SKILL.md + 参考资料 + 脚本。实际加载到 context 的内容取决于 subagent 读取了哪些文件。

| 文件 | 行数 | 单词 | 字节 | 估算 Token |
|------|------|------|------|-----------|
| **SKILL.md** | 231 | 1,466 | 10,772 | ~1,960 |
| references/makefile-quality-guide.md | 268 | 1,211 | 8,837 | ~1,620 |
| references/golden/simple-project.mk | 101 | 396 | 2,864 | ~530 |
| references/golden/complex-project.mk | 193 | 777 | 6,559 | ~1,040 |
| references/pr-checklist.md | 71 | 429 | 2,980 | ~570 |
| scripts/discover_go_entrypoints.sh | 93 | 285 | 2,279 | ~380 |
| **Description（始终在 context）** | — | ~30 | — | ~40 |

**典型加载场景:**

| 场景 | 读取文件 | 总 Token |
|------|---------|---------|
| 简单项目（Eval 1） | SKILL.md + quality-guide + simple-project.mk | ~4,110 |
| 复杂项目（Eval 2） | SKILL.md + quality-guide + complex-project.mk | ~4,620 |
| 重构（Eval 3） | SKILL.md + quality-guide | ~3,580 |
| 仅 SKILL.md（最小加载） | SKILL.md | ~1,960 |

### 5.2 Token 换取的质量提升

| 指标 | 数值 |
|------|------|
| With-skill 通过率 | 100% (42/42) |
| Without-skill 通过率 | 69.0% (29/42) |
| 通过率提升 | +31.0 百分点 |
| 每修复 1 条 assertion 的 Token 成本 | ~150 tokens（SKILL.md only）/ ~355 tokens（full） |
| 每 1% 通过率提升的 Token 成本 | ~63 tokens（SKILL.md only）/ ~149 tokens（full） |

### 5.3 Token 分段效费比

将 SKILL.md 内容按功能模块拆分：

| 模块 | 估算 Token | 关联 Assertion 差值 | 效费比 |
|------|-----------|-------------------|--------|
| **Naming Convention 规则** | ~100 | 2 条（Eval 1 build-api/run-api） | **极高** — 50 tok/assertion |
| **Output Contract 定义** | ~300 | 3 条（3 evals structured report） | **高** — 100 tok/assertion |
| **install-tools 版本锁定规则** | ~80 | 3 条（3 evals pinned versions） | **极高** — 27 tok/assertion |
| **ci target 规范** | ~50 | 2 条（Eval 1/2 ci naming） | **极高** — 25 tok/assertion |
| **tidy target 规范** | ~30 | 1 条（Eval 1 tidy） | **极高** — 30 tok/assertion |
| **lint tool-check 规则** | ~40 | 1 条（Eval 1 golangci-lint check） | **高** — 40 tok/assertion |
| **docker-build 变量规范** | ~60 | 1 条（Eval 2 IMAGE_NAME/TAG） | **高** — 60 tok/assertion |
| **Anti-Patterns 区** | ~250 | 间接贡献（避免 eval/call 元编程） | **中** — 无直接 assertion |
| **Go Version Awareness** | ~150 | 0 条（未测试版本差异场景） | **低** — 无测试场景 |
| **Monorepo Support** | ~200 | 0 条（未测试 monorepo） | **低** — 无测试场景 |
| **Golden templates（参考资料）** | ~530-1,040 | 间接贡献（Makefile 结构一致性） | **中** — 模板驱动结构 |
| **Quality guide（参考资料）** | ~1,620 | 间接贡献（详细实现模式） | **中** — 提供具体 recipe |

### 5.4 高杠杆 vs 低杠杆指令

**高杠杆（~360 tokens SKILL.md → 12 条 assertion 差值）:**
- 命名规范 `cmd/<name>` → `build-<name>`（100 tok → 2 条）
- Output Contract 定义（300 tok → 3 条）注：实际模板部分贡献最大
- install-tools 版本锁定（80 tok → 3 条）
- ci target 规范（50 tok → 2 条）
- tidy target（30 tok → 1 条）
- lint 工具检查（40 tok → 1 条）

**中杠杆（~310 tokens → 间接贡献）:**
- Anti-Patterns 区（250 tok）— 避免了 Eval 2 中的 eval/call 元编程
- docker-build 变量规范（60 tok → 1 条）

**低杠杆（~350 tokens → 0 条差值）:**
- Go Version Awareness（150 tok）— 未测试
- Monorepo Support（200 tok）— 未测试

**参考资料（~2,150-2,660 tokens → 间接贡献）:**
- Golden templates 驱动了 Makefile 的整体结构一致性
- Quality guide 提供了具体的 recipe 实现

### 5.5 Token 效率评级

| 评级 | 结论 |
|------|------|
| **整体 ROI** | **良好** — ~4,100-4,600 tokens 换取 +31% 通过率 |
| **SKILL.md 本身 ROI** | **优秀** — ~1,960 tokens 包含全部高杠杆规则 |
| **高杠杆 Token 比例** | ~18%（360/1,960）直接贡献 12/13 条 assertion 差值 |
| **低杠杆 Token 比例** | ~18%（350/1,960）在当前评估中无增量贡献 |
| **参考资料效费比** | **中等** — ~2,150+ tokens 提供间接质量提升但无直接 assertion 差值 |

### 5.6 与 git-commit skill 的效费比对比

| 指标 | go-makefile-writer | git-commit |
|------|-------------------|------------|
| SKILL.md Token | ~1,960 | ~1,120 |
| 总加载 Token | ~4,100-4,600 | ~1,120 |
| 通过率提升 | +31.0% | +22.7% |
| 每 1% 的 Token（SKILL.md） | ~63 tok | ~51 tok |
| 每 1% 的 Token（full） | ~149 tok | ~51 tok |

go-makefile-writer 的 SKILL.md 效费比与 git-commit 接近，但参考资料带来了显著的额外 Token 开销。参考资料的价值主要体现在**Makefile 结构一致性**和**避免 anti-patterns**，这些是难以通过 assertion 量化的质量维度。

---

## 六、与 Claude 基础模型能力的边界分析

### 6.1 基础模型已具备的能力（Skill 无增量）

| 能力 | 证据 |
|------|------|
| .DEFAULT_GOAL := help 模式 | 3/3 场景正确 |
| .PHONY 声明 | 3/3 场景正确 |
| -ldflags 版本注入 | 3/3 场景正确 |
| -race flag in test | 3/3 场景正确 |
| docker-build/push targets | 1/1 场景正确（Eval 2） |
| 多二进制 per-binary targets | 1/1 场景正确（Eval 2） |
| build-srv → build-server 重命名 | 1/1 场景正确（Eval 3） |
| build-srv backward compat alias | 1/1 场景正确（Eval 3） |
| bin/ 目录输出 | 3/3 场景正确 |

### 6.2 基础模型的能力缺口（Skill 填补）

| 缺口 | 证据 | 风险等级 |
|------|------|---------|
| **单二进制命名泛化** | Eval 1: `build`/`run` 而非 `build-api`/`run-api` | 中 — 扩展时需重命名 |
| **install-tools 缺失或未锁定** | 3/3 场景：无 install-tools 或 `@latest` | 高 — CI 不可复现 |
| **无结构化 Output Report** | 3/3 场景无报告 | 中 — 缺少审计追溯 |
| **ci target 命名不一致** | 2/3 场景无 ci 或命名为 check | 中 — 团队约定不统一 |
| **tidy target 遗漏** | 1/3 场景无 tidy | 低 — 可手动执行 |
| **lint 缺少 golangci-lint** | 1/3 场景 lint=vet+fmt-check | 中 — 静态分析不完整 |
| **eval/call 元编程** | 1/3 场景使用动态模板 | 低 — 功能等价但可读性差 |

---

## 七、综合评分

### 7.1 分维度评分

| 维度 | With Skill | Without Skill | 差值 |
|------|-----------|--------------|------|
| 目标集完整度 | 5.0/5 | 3.5/5 | +1.5 |
| 命名规范合规 | 5.0/5 | 3.0/5 | +2.0 |
| 版本注入 & 构建质量 | 5.0/5 | 4.5/5 | +0.5 |
| CI 可复现性（tool pinning） | 5.0/5 | 2.0/5 | +3.0 |
| 结构化报告 | 5.0/5 | 1.0/5 | +4.0 |
| 可维护性 & 可读性 | 4.5/5 | 3.5/5 | +1.0 |
| **综合均值** | **4.92/5** | **2.92/5** | **+2.0** |

### 7.2 加权总分

| 维度 | 权重 | 得分 | 加权 |
|------|------|------|------|
| Assertion 通过率（delta） | 25% | 9.5/10 | 2.38 |
| 命名规范 & 目标设计 | 20% | 10/10 | 2.00 |
| CI 可复现性（tool pinning） | 15% | 10/10 | 1.50 |
| 结构化报告（Output Contract） | 15% | 10/10 | 1.50 |
| Token 效费比 | 15% | 6.5/10 | 0.98 |
| 可维护性 & Anti-pattern 规避 | 10% | 8.0/10 | 0.80 |
| **加权总分** | | | **9.16/10** |

---

## 八、评估材料

| 材料 | 路径 |
|------|------|
| Eval 定义 | `/tmp/makefile-eval/workspace/iteration-1/eval-*/eval_metadata.json` |
| Eval 1 with-skill 输出 | `/tmp/makefile-eval/workspace/iteration-1/eval-1-simple-create/with_skill/outputs/` |
| Eval 1 without-skill 输出 | `/tmp/makefile-eval/workspace/iteration-1/eval-1-simple-create/without_skill/outputs/` |
| Eval 2 with-skill 输出 | `/tmp/makefile-eval/workspace/iteration-1/eval-2-multi-binary-docker/with_skill/outputs/` |
| Eval 2 without-skill 输出 | `/tmp/makefile-eval/workspace/iteration-1/eval-2-multi-binary-docker/without_skill/outputs/` |
| Eval 3 with-skill 输出 | `/tmp/makefile-eval/workspace/iteration-1/eval-3-refactor-defects/with_skill/outputs/` |
| Eval 3 without-skill 输出 | `/tmp/makefile-eval/workspace/iteration-1/eval-3-refactor-defects/without_skill/outputs/` |
| 评分结果 | `/tmp/makefile-eval/workspace/iteration-1/eval-*/with_skill/grading.json` |
| Benchmark 汇总 | `/tmp/makefile-eval/workspace/iteration-1/benchmark.json` |
| Eval Viewer | `/tmp/makefile-eval/eval-review.html` |
