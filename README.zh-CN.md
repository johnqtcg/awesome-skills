# awesome-skills

> 面向工程化落地的 **Claude Code Skill** 体系——设计说明 · 量化评估 · 黄金测试 · 完整工作流集成

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Stars](https://img.shields.io/github/stars/johnqtcg/awesome-skills?style=social)](https://github.com/johnqtcg/awesome-skills)
[![English](https://img.shields.io/badge/Docs-English-blue)](index.md)

一个围绕高质量 **Claude Code Skill** 方法论、设计说明、评审、验证与工作流落地构建的开源项目。

- **21** 个生产级 Claude Code Skills：覆盖 Go、测试、安全、CI/CD、调研、文档、规划
- **42** 份设计说明文档（中英双语），每个 skill 都有对应的说明链路
- **42** 份量化评审报告（中英双语），含可追溯指标
- **169** 个 golden JSON 场景 + **40** 个 Python 测试文件，确定性回归保障
- 测试 skills：`unit-test` · `tdd-workflow` · `api-integration-test` · `e2e-test` · `fuzzing-test`
- 交付管线：`go-makefile-writer` → `git-commit` → `create-pr` → `go-ci-workflow` → `go-code-reviewer` → `security-review`

<a id="cn-quickstart"></a>
## 快速开始

1. 浏览下方 [skill 列表](#cn-skills)，找到适合你工作场景的 skill
2. 将 `skills/<名称>` 目录复制到你的项目中：
   - 项目级（仅当前项目）：`.claude/skills/<名称>`
   - 个人级（所有项目）：`~/.claude/skills/<名称>`
3. 在 Claude Code 中，当任务匹配时 skill 会自动激活

了解 skill 设计方法论：

- 中文：[bestpractice/README.zh-CN.md](bestpractice/README.zh-CN.md)
- English：[bestpractice/README.md](bestpractice/README.md)

了解某个具体 skill 为什么这样设计：

- 中文：[rationale/index.zh-CN.md](rationale/index.zh-CN.md)
- English：[rationale/index.md](rationale/index.md)

<a id="cn-overview"></a>
## 项目概览

文档入口包括：

- 方法论：[`bestpractice/README.zh-CN.md`](bestpractice/README.zh-CN.md)
- skill 级设计说明：[`rationale/index.zh-CN.md`](rationale/index.zh-CN.md)

这个项目的核心目标不是“展示 prompt 怎么写”，而是回答四个更难的问题：

1. 高质量 skill 到底应该如何设计？
2. 这些设计原则落实到某个具体 skill 上时，会怎样体现为它的结构、门禁与取舍？
3. 写出来之后如何证明它真的有效？
4. 如何把它融入日常开发与团队工作流，而不是停留在演示层？

<a id="cn-highlights"></a>
## 项目亮点

### 1. 五层可追溯架构

项目最有辨识度的地方，是把内容组织成了一条完整且可追溯的链路：

`bestpractice/` → `rationale/` → `skills/` → `evaluate/` → `outputexample/`

这五层组成了一条可验证的知识链：

- 方法论定义 skill 应该如何设计
- 设计说明解释这些原则是如何在某个具体 skill 里贯彻的
- skill 示例展示最终可执行产物的样子
- 评审报告验证 skill 到底好不好
- 输出样例证明 skill 在真实任务里能产出什么

### 2. rationale - 理清 skill 设计思路

每个 skill 都配有设计说明文档，例如 [`rationale/google-search/design.md`](rationale/google-search/design.md) 和 [`rationale/google-search/design.zh-CN.md`](rationale/google-search/design.zh-CN.md)。这些文档主要用来说明：

- 这个 skill 具体要解决什么问题
- 为什么它的流程、门禁、结构和输出格式会这样设计
- 常见替代方案为什么不够理想
- 这个设计最值得关注的亮点是什么

这让项目不只是提供一组可直接使用的示例，也提供了一套可以被研究、质疑和复用的设计逻辑。

### 3. 通用方法论驱动 skill 设计

项目最有价值的资产，是 [`bestpractice/`](bestpractice/README.zh-CN.md) 和 [`rationale/`](rationale/index.zh-CN.md)，而不只是 [`skills/`](skills/index.md) 里有多少个 skill。这里总结出的设计模式是可迁移的通用方法论，例如：

- 强制门禁
- 反例教学
- 诚实降级
- 渐进式披露
- 输出契约
- 量化评估

这些模式不依赖某种特定语言或平台。掌握它们的人，可以把同样的方法迁移到别的语言、别的工作流、别的 agent 系统里。也正因为如此，项目是在“教你如何构建专业 skill”，而不是只给一组现成模板。

### 4. 提供可量化的评估框架

[`bestpractice/评估篇.md`](bestpractice/评估篇.md) 把“skill 好不好”拆成三个可量化维度：

- 触发准确率
- 真实任务表现
- Token 成本效益比

这套框架的价值，在 [`evaluate/`](evaluate/index.md) 里的正式评审报告中可以直接看到。例如：

- `go-code-reviewer`：微妙场景信噪比提升 +36 个百分点，开发者时间 ROI 达 347x
- `unit-test`：Assertion 通过率提升 +38.4 个百分点
- `google-search`：Assertion 通过率提升 +74.1 个百分点

这比“这些 skill 看起来很好用”强得多，因为它给出了可追溯的数字、评估过程和迭代依据。

### 5. 适合工程化维护的回归测试体系

这个项目没有把“让一个 LLM 去评价另一个 LLM”当成主要守护手段，而是优先采用确定性验证：

- `132` 个 golden JSON 场景
- `29` 个 Python 测试文件
- 合约测试守护门禁、输出契约和结构规则
- 黄金场景测试守护真实任务覆盖

这些测试快、可版本化、可 diff、可复跑。这个设计决策本身就体现了很强的工程判断力：关键质量约束应该尽量落到确定性脚本里，而不是只停留在自然语言描述中。

### 6. skill 可以编织成完整的工程化质量流水线

项目里的后端相关 skill 不是互相孤立的，它们可以首尾衔接成一条完整质量管线：

`go-makefile-writer` → `git-commit` → `create-pr` → `go-ci-workflow` → `go-code-reviewer` → `security-review`

而且项目里有对应的评审报告、工作流示例和输出产物，证明这不是纸面上的“概念链路”，而是可以在真实工程实践中被复用和验证的工作体系。

### 7. "隐性→显性→可执行" 知识论

这个项目真正有长期价值的地方，还不只是 skill 文件本身，而是它表达了一种更强的知识演化路径：

- 大脑中的隐性经验
- 文档中的显性规则
- skill / script / test 中可执行、可约束的能力

这条路径把原本不稳定、不可传承的个人经验，转化成了团队可共享、可检查、可持续演进的工程资产。

<a id="cn-project-structure"></a>
## 项目结构

```text
.
├── bestpractice/        # Skill 最佳实践文档，中英双语
├── rationale/           # 每个 skill 的设计说明，中英双语
├── skills/              # 按最佳实践编写的高质量 skill 示例
├── evaluate/            # skill 评审报告，中英双语
├── outputexample/       # 真实输出样例
├── README.md            # README文档
├── README.zh-CN.md
└── LICENSE
```

五个核心目录的职责如下：

| 路径 | 作用 |
| --- | --- |
| [bestpractice/](bestpractice/README.zh-CN.md) | 介绍如何写高质量 skill，如何评估 skill，以及如何把 skill 融入工作流 |
| [rationale/](rationale/index.zh-CN.md) | 结合具体 skill 解释其设计过程、设计逻辑、权衡取舍，以及它到底在解决什么问题 |
| [skills/](skills/index.md) | 经过方法论约束后的高质量 skill 示例 |
| [evaluate/](evaluate/index.md) | 对 skill 的正式评审报告，解释优点、缺点与改进点 |
| [outputexample/](outputexample/index.md) | skill 在真实任务中的实际输出，如 PDF、测试代码、Makefile、CI 配置、截图等 |

<a id="cn-reading-path"></a>
## 推荐阅读路径

如果你第一次进入项目，推荐按这个顺序阅读：

1. 从 [`bestpractice/README.zh-CN.md`](bestpractice/README.zh-CN.md) 建立整体认知
2. 阅读某个 skill 的设计说明，例如 [`rationale/google-search/design.zh-CN.md`](rationale/google-search/design.zh-CN.md)
3. 再进入这个 skill 本身，例如 [`skills/google-search/SKILL.md`](skills/google-search/SKILL.md)
4. 对照它的评审报告，例如 [`evaluate/google-search-skill-eval-report.zh-CN.md`](evaluate/google-search-skill-eval-report.zh-CN.md)
5. 再看它的真实输出，例如 [`outputexample/google-search/中国制造2025目标完成度研究.pdf`](outputexample/google-search/中国制造2025目标完成度研究.pdf)

如果你偏向英文阅读，可以从 [`bestpractice/README.md`](bestpractice/README.md) 开始。

<a id="cn-bestpractice"></a>
## 文档体系

[`bestpractice/`](bestpractice/README.zh-CN.md) 是整个项目的方法论入口：

- [`基础篇.md`](bestpractice/基础篇.md)
- [`进阶篇.md`](bestpractice/进阶篇.md)
- [`评估篇.md`](bestpractice/评估篇.md)
- [`集成篇.md`](bestpractice/集成篇.md)

这些文档主要回答：

- 为什么 skill 会成为 AI 编程助手中的关键抽象
- 高质量 skill 应该遵循什么设计模式
- 如何用量化方法评估 skill 的真实价值
- 如何把 skill 融入开发流程，而不是停留在单次对话里

<a id="cn-rationale"></a>
## skill 设计说明

[`rationale/`](rationale/index.zh-CN.md) 汇总了每个 skill 的设计说明，把 [`bestpractice/`](bestpractice/README.zh-CN.md) 里的通用原则和 [`skills/`](skills/index.md) 里的具体实现串联了起来。

每份设计说明都会围绕一个 skill，重点讲清楚：

- 这个 skill 具体要解决什么问题
- 为什么它的门禁、结构、参考资料和输出格式会这样设计
- 常见替代方案为什么不够理想
- 这个设计最值得关注的亮点是什么

代表性示例：

- [`rationale/google-search/design.zh-CN.md`](rationale/google-search/design.zh-CN.md)
- [`rationale/update-doc/design.zh-CN.md`](rationale/update-doc/design.zh-CN.md)
- [`rationale/go-code-reviewer/design.zh-CN.md`](rationale/go-code-reviewer/design.zh-CN.md)

<a id="cn-skills"></a>
## skill 示例

当前项目收录的高质量 skill 都位于 [`skills/`](skills/index.md) 下，并以各自目录中的 `SKILL.md` 作为主入口。若想理解某个 skill 为什么这样设计，可以对照阅读 `rationale/<name>/` 下的设计说明。它们不是一组互相孤立的能力，而是可以按工作场景组织成若干类；其中，后端开发相关 skill 可以互相配合，形成一条完整的质量管线。

### 后端开发：完整质量管线

后端相关 skill 的价值，不只是“每个 skill 单独能干活”，而是它们能首尾衔接，构成从编码到合并的工程化闭环：

```text
编码
  ↓
编写 / 修复测试
  （unit-test · tdd-workflow · api-integration-test · e2e-test · fuzzing-test）
  ↓
make fmt / make lint（本地质量检查，go-makefile-writer 生成）
  ↓
git commit（git-commit skill：安全扫描 + 质量门禁 + 规范化 message）
  ↓
git push
  ↓
create PR（create-pr skill：多道门禁 + 结构化 PR body）
  ↓
CI 触发
  ├── make ci（格式 + 测试 + lint + 覆盖率 + 构建）
  ├── make docker-build（容器镜像验证）
  ├── Claude Code Review（go-code-reviewer skill：自动代码审查）
  └── govulncheck / 安全检查（security-review skill 关注风险模型）
  ↓
人工审查 + 合并
```

这条管线里的关键 skill 如下：

| Skill 名称 | 所处阶段 | 功能用途 | 主要亮点 / 优势 |
| --- | --- | --- | --- |
| `go-makefile-writer` | 本地工程入口 | 为 Go 项目设计或重构根 Makefile | 标准化 `fmt/test/lint/build/run` 入口，让本地命令和 CI 门禁对齐 |
| `git-commit` | 提交前门禁 | 安全创建 Git 提交 | 提交前检查项目状态、潜在敏感信息和冲突，并生成规范化 commit message |
| `create-pr` | 提交后到评审前 | 为 GitHub 主分支创建高质量 PR | 强调预检、质量门禁和结构化 PR 内容，降低 reviewer 理解成本 |
| `go-ci-workflow` | CI 编排 | 创建或重构 Go 项目的 GitHub Actions CI | 强调 Make 驱动、本地与 CI 一致、缓存与 job 设计、门禁分层 |
| `go-code-reviewer` | 自动审查 | 对 Go 代码做缺陷优先评审 | 聚焦真实 bug、回归和风险，不把代码审查退化成风格检查 |
| `security-review` | 安全审查 | 对代码变更做 exploitability-first 安全评审 | 以“是否可利用”为优先级，覆盖认证、输入、依赖、并发和容器风险 |

### 测试与验证

这一类 skill 负责把“代码写出来”推进到“代码被验证过”。它们覆盖单元测试、TDD、集成测试、E2E、模糊测试和复杂故障排查。

| Skill 名称                          | 功能用途                           | 主要亮点 / 优势 |
|-----------------------------------|--------------------------------| --- |
| `unit-test`                       | 为 Go 代码添加或修复单元测试               | 强调表驱动、子测试和 bug 挖掘，关注边界、映射丢失和并发问题 |
| `tdd-workflow`                    | 在 Go 服务中执行务实的 TDD 流程           | 强调 `Red -> Green -> Refactor` 证据链，以及风险路径覆盖 |
| `api-integration-test`            | 为内部 API 和服务间调用编写、维护和运行 Go 集成测试 | 强调真实运行时配置、显式门禁、超时/重试安全，适合接口验证与失败排查 |
| `thirdparty-api-integration-test` | 为第三方 API 编写和运行真实调用的集成测试        | 带显式运行门禁、超时控制和安全约束，适合验证外部依赖契约 |
| `e2e-test`                        | 设计、维护和执行关键用户行为的 E2E 测试         | 兼顾探索、回归、CI 落地和产物留存，强调稳定性与可维护性 |
| `fuzzing-test`                    | 为 Go 代码生成模糊测试                  | 先做适用性门禁，不适合的目标会明确拒绝，避免产出低价值 fuzz case |
| `systematic-debugging`            | 对 bug、异常行为和失败场景做系统化排查          | 明确要求先找根因再修复，避免拍脑袋试错式修 bug |


完整的示例可参考: https://github.com/johnqtcg/issue2md (.github/workflows/ci.yml)


### 搜索、调研与报告

这一类 skill 适合做信息搜集、事实核查、资料对比和正式研究输出。

| Skill 名称 | 功能用途 | 主要亮点 / 优势 |
| --- | --- | --- |
| `google-search` | 用 Google 检索做资料搜集、事实验证和来源核查 | 强调查询分类、证据链、交叉核验和可复用搜索串 |
| `deep-research` | 做带来源支撑的深度研究与分析 | 强制内容抽取、交叉验证和抗幻觉检查，适合研究、比较和趋势分析 |

### 技术文档与写作

这一类 skill 关注把工程知识沉淀成团队可以直接复用、持续维护的技术文档。

| Skill 名称 | 功能用途 | 主要亮点 / 优势 |
| --- | --- | --- |
| `writing-plans` | 为多步骤任务生成基于证据的实现计划 | 强调 mode-aware planning、已验证路径标签、依赖图和强制性的计划后审查，让计划真正可执行而不是停留在描述层 |
| `update-doc` | 让项目文档与最新代码保持同步 | 强调按作用域更新文档、docs drift 检查、项目类型路由，以及基于证据同步 README 和相关文档 |
| `readme-generator` | 基于项目证据生成或重构项目 `README.md` | 强调项目形态识别、证据驱动的结构组织、可维护 README 模式，以及对 service、library、CLI、monorepo 等项目的适配 |
| `tech-doc-writer` | 编写、审查和改进技术文档，如 runbook、故障排查文档、API 文档和 RFC/ADR 风格设计文档 | 强调文档类型分类、受众分析、质量门禁和防陈旧机制，产出更清晰、可维护的技术文档 |

### 工具执行与任务自动化

这一类 skill 偏向“把任务执行完”。

| Skill 名称 | 功能用途 | 主要亮点 / 优势 |
| --- | --- | --- |
| `yt-dlp-downloader` | 生成并执行 `yt-dlp` 下载命令 | 先探测格式再下载，支持单视频、播放列表、音频、字幕和认证内容等场景 |
| `local-transcript` | 将本地音视频转写为 `txt` / `pdf` / `docx` | 使用加速的本地 ASR 管线结合后处理与校对，输出更干净的中文转写文本，并支持段落化、标点规范化和多格式导出 |

<a id="cn-evaluate-and-output"></a>
## 评审与输出样例

这个项目和普通“skills 示例项目”最大的区别，是它不仅展示 skill，还展示：

1. 这个 skill 为什么要这样设计
2. 这个 skill 为什么好
3. 它在真实任务中产出了什么

你可以直接对照阅读：

- 设计说明：[`rationale/`](rationale/index.zh-CN.md)
- 评审报告：[`evaluate/`](evaluate/index.md)
- 输出样例：[`outputexample/`](outputexample/index.md)

典型例子：

- `google-search`
  - 设计说明：[`rationale/google-search/design.zh-CN.md`](rationale/google-search/design.zh-CN.md)
  - 评审：[`evaluate/google-search-skill-eval-report.zh-CN.md`](evaluate/google-search-skill-eval-report.zh-CN.md)
  - 输出：[`outputexample/google-search/中国制造2025目标完成度研究.pdf`](outputexample/google-search/中国制造2025目标完成度研究.pdf)
- `unit-test`
  - 设计说明：[`rationale/unit-test/design.zh-CN.md`](rationale/unit-test/design.zh-CN.md)
  - 评审：[`evaluate/unit-test-skill-eval-report.zh-CN.md`](evaluate/unit-test-skill-eval-report.zh-CN.md)
  - 输出：[`outputexample/unit-test/`](outputexample/unit-test/index.md)
- `yt-dlp-downloader`
  - 设计说明：[`rationale/yt-dlp-downloader/design.zh-CN.md`](rationale/yt-dlp-downloader/design.zh-CN.md)
  - 输出截图：[`outputexample/yt-dlp-downloader/`](outputexample/yt-dlp-downloader/index.md)

<a id="cn-governance"></a>
## 治理文档

如果你准备参与贡献，或者需要查看项目治理规则，建议从这里开始：

- 贡献指南：[`CONTRIBUTING.zh-CN.md`](CONTRIBUTING.zh-CN.md)
- 安全策略：[`SECURITY.zh-CN.md`](SECURITY.zh-CN.md)
- 行为准则：[`CODE_OF_CONDUCT.zh-CN.md`](CODE_OF_CONDUCT.zh-CN.md)


<a id="cn-audience"></a>
## 适合谁

- 想系统学习如何写高质量 skill 的人
- 想把 Claude Code / Agent 能力沉淀为可复用资产的人
- 想看“方法论 + 设计说明 + skill + 评审 + 输出样例”完整闭环的人
- 想把 AI 能力接入真实研发流程，而不是停留在 prompt 演示层的人

<a id="cn-license"></a>
## License

本项目使用 MIT License，见 [`LICENSE`](LICENSE)。
