# awesome-skills

![License](https://img.shields.io/badge/license-MIT-blue)

一个围绕高质量 Skill 设计、评审、验证与工作流落地构建的开源项目。

它不是单纯的 `SKILL.md` 样例集合，而是把“如何写高质量 skill”这件事拆成了完整闭环：

- 方法论文档：解释为什么这样设计
- skill 示例：展示高质量 skill 应该长什么样
- 评审报告：说明这些 skill 为什么好，问题在哪里
- 输出样例：证明这些 skill 在真实任务里能产出什么

## 目录

- [项目概览](#cn-overview)
- [项目亮点](#cn-highlights)
- [项目结构](#cn-project-structure)
- [推荐阅读路径](#cn-reading-path)
- [文档体系](#cn-bestpractice)
- [skill 示例](#cn-skills)
- [评审与输出样例](#cn-evaluate-and-output)
- [治理文档](#cn-governance)
- [适合谁](#cn-audience)
- [License](#cn-license)

<a id="cn-overview"></a>
## 项目概览

- 项目定位：高质量 skill 方法论 + skill 资产 + 评审 + 输出样例。
- 文档入口：[`bestpractice/README.zh-CN.md`](/Users/john/awesome-skills/bestpractice/README.zh-CN.md)。
- Skill 数量：`16` 个（见 [`skills/`](/Users/john/awesome-skills/skills)）。
- 评审报告数量：`32` 份，中英双语成对存在（见 [`evaluate/`](/Users/john/awesome-skills/evaluate)）。
- 输出样例目录：`10` 个（见 [`outputexample/`](/Users/john/awesome-skills/outputexample)）。

这个仓库的核心目标不是“展示 prompt 怎么写”，而是回答三个更难的问题：

1. 高质量 skill 到底应该如何设计？
2. 写出来之后如何证明它真的有效？
3. 如何把它融入日常开发与团队工作流，而不是停留在演示层？

<a id="cn-highlights"></a>
## 项目亮点

### 1. 文档质量评价：极高的系统性与落地价值

项目最有价值的部分，不是 `skills/` 里的高质量skill，而是 [`bestpractice/`](/Users/john/awesome-skills/bestpractice) 这套完整的方法论文档。
它在结构化思维、理论抽象和工程落地上都有很强的参考价值。

### 2. 架构清晰，层次分明

最佳实践文档采用了skill设计哲学主张的“渐进式披露”思路，把内容分为：

- 基础篇
- 进阶篇
- 评估篇
- 集成篇
- 附录与导航文档

读者可以按经验水平和目标直接进入需要的部分，而不必从头到尾线性阅读。这个结构本身就在示范“如何写一份对 AI 和人类都友好的长文档”。

### 3. 原创且高度凝练的设计模式

项目从大量实际任务里抽象出了一组对 LLM 落地非常关键的模式，例如：

- 强制门禁
- 反例教学
- 诚实降级
- 渐进式披露
- 输出契约
- 量化评估

这些模式直接针对当前 LLM 最常见的问题：幻觉、误报、上下文溢出、输出不稳定、不可验证。

### 4. 量化驱动，拒绝“凭感觉”

[`bestpractice/评估篇.md`](/Users/john/awesome-skills/bestpractice/评估篇.md) 价值在于，它们把“skill 好不好”从主观感觉变成了可评估对象。

重点不再是“看起来不错”，而是：

- 触发是否准确
- 实际任务表现是否优于不用 skill 的基线
- Token 成本是否值得

这也是 [`evaluate/`](/Users/john/awesome-skills/evaluate) 目录存在的意义：仓库不只给出 skill，还给出评审证据。

### 5. 极强地可执行性和工程闭环

这个项目不是只讲 `What` 和 `Why`，而是把 `How` 也补齐了。你可以在仓库里直接看到完整链路：

- 方法论在 [`bestpractice/`](/Users/john/awesome-skills/bestpractice)
- skill 示例在 [`skills/`](/Users/john/awesome-skills/skills)
- 评审在 [`evaluate/`](/Users/john/awesome-skills/evaluate)
- 输出结果在 [`outputexample/`](/Users/john/awesome-skills/outputexample)

这意味着它不是抽象讨论，而是一套可以被复用、被检视、被持续迭代的工程化资产。

### 6. 能力壁垒不在“会用 AI”，而在“能把 AI 变成可靠能力”

系统掌握这套方法，最终获得的不是“会写 prompt”，而是更稀缺的复合型能力：

- 把隐性经验拆成结构化规则
- 把不稳定 AI 输出约束成可复用工作流
- 把 skill 接入真实研发流程，而不是停留在演示
- 用评审和样例证明价值，而不是只讲概念

<a id="cn-project-structure"></a>
## 项目结构

```text
.
├── bestpractice/        # Skill 最佳实践文档，中英双语
├── skills/              # 按最佳实践编写的高质量 skill 示例
├── evaluate/            # skill 评审报告，中英双语
├── outputexample/       # 真实输出样例
├── README.md            # README文档
├── README.zh-CN.md
└── LICENSE
```

四个核心目录的职责如下：

| 路径 | 作用 |
| --- | --- |
| [bestpractice/](/Users/john/awesome-skills/bestpractice) | 介绍如何写高质量 skill，如何评估 skill，以及如何把 skill 融入工作流 |
| [skills/](/Users/john/awesome-skills/skills) | 经过方法论约束后的高质量 skill 示例 |
| [evaluate/](/Users/john/awesome-skills/evaluate) | 对 skill 的正式评审报告，解释优点、缺点与改进点 |
| [outputexample/](/Users/john/awesome-skills/outputexample) | skill 在真实任务中的实际输出，如 PDF、测试代码、Makefile、CI 配置、截图等 |

<a id="cn-reading-path"></a>
## 推荐阅读路径

如果你第一次进入项目，推荐按这个顺序阅读：

1. 从 [`bestpractice/README.zh-CN.md`](/Users/john/awesome-skills/bestpractice/README.zh-CN.md) 建立整体认知
2. 进入某个具体 skill，例如 [`skills/google-search/SKILL.md`](/Users/john/awesome-skills/skills/google-search/SKILL.md)
3. 对照它的评审报告，例如 [`evaluate/google-search-skill-eval-report.zh-CN.md`](/Users/john/awesome-skills/evaluate/google-search-skill-eval-report.zh-CN.md)
4. 再看它的真实输出，例如 [`outputexample/google-search/中国制造2025目标完成度研究.pdf`](/Users/john/awesome-skills/outputexample/google-search/中国制造2025目标完成度研究.pdf)

如果你偏向英文阅读，可以从 [`bestpractice/README.md`](/Users/john/awesome-skills/bestpractice/README.md) 开始。

<a id="cn-bestpractice"></a>
## 文档体系

[`bestpractice/`](/Users/john/awesome-skills/bestpractice) 是整个项目的方法论入口：

- [`基础篇.md`](/Users/john/awesome-skills/bestpractice/基础篇.md)
- [`进阶篇.md`](/Users/john/awesome-skills/bestpractice/进阶篇.md)
- [`评估篇.md`](/Users/john/awesome-skills/bestpractice/评估篇.md)
- [`集成篇.md`](/Users/john/awesome-skills/bestpractice/集成篇.md)

这些文档主要回答：

- 为什么 skill 会成为 AI 编程助手中的关键抽象
- 高质量 skill 应该遵循什么设计模式
- 如何用量化方法评估 skill 的真实价值
- 如何把 skill 融入开发流程，而不是停留在单次对话里

<a id="cn-skills"></a>
## skill 示例

当前项目收录的高质量 skill 都位于 [`skills/`](/Users/john/awesome-skills/skills) 下，并以各自目录中的 `SKILL.md` 作为主入口。它们不是一组互相孤立的能力，而是可以按工作场景组织成若干类；其中，后端开发相关 skill 可以互相配合，形成一条完整的质量管线。

### 后端开发：完整质量管线

后端相关 skill 的价值，不只是“每个 skill 单独能干活”，而是它们能首尾衔接，构成从编码到合并的工程化闭环：

```text
编码
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
| `go-makefile-writer` | 本地工程入口 | 为 Go 仓库设计或重构根 Makefile | 标准化 `fmt/test/lint/build/run` 入口，让本地命令和 CI 门禁对齐 |
| `git-commit` | 提交前门禁 | 安全创建 Git 提交 | 提交前检查仓库状态、潜在敏感信息和冲突，并生成规范化 commit message |
| `create-pr` | 提交后到评审前 | 为 GitHub 主分支创建高质量 PR | 强调预检、质量门禁和结构化 PR 内容，降低 reviewer 理解成本 |
| `go-ci-workflow` | CI 编排 | 创建或重构 Go 仓库的 GitHub Actions CI | 强调 Make 驱动、本地与 CI 一致、缓存与 job 设计、门禁分层 |
| `go-code-reviewer` | 自动审查 | 对 Go 代码做缺陷优先评审 | 聚焦真实 bug、回归和风险，不把代码审查退化成风格检查 |
| `security-review` | 安全审查 | 对代码变更做 exploitability-first 安全评审 | 以“是否可利用”为优先级，覆盖认证、输入、依赖、并发和容器风险 |

### 测试与验证

这一类 skill 负责把“代码写出来”推进到“代码被验证过”。它们覆盖单元测试、TDD、集成测试、E2E、模糊测试和复杂故障排查。

| Skill 名称 | 功能用途 | 主要亮点 / 优势 |
| --- | --- | --- |
| `unit-test` | 为 Go 代码添加或修复单元测试 | 强调表驱动、子测试和 bug 挖掘，关注边界、映射丢失和并发问题 |
| `tdd-workflow` | 在 Go 服务中执行务实的 TDD 流程 | 强调 `Red -> Green -> Refactor` 证据链，以及风险路径覆盖 |
| `api-integration-test` | 为内部 API 和服务间调用编写、维护和运行 Go 集成测试 | 强调真实运行时配置、显式门禁、超时/重试安全，适合接口验证与失败排查 |
| `thirdparty-api-integration-test` | 为第三方 API 编写和运行真实调用的集成测试 | 带显式运行门禁、超时控制和安全约束，适合验证外部依赖契约 |
| `e2e-best-practise` | 设计、维护和执行关键用户旅程的 E2E 测试 | 兼顾探索、回归、CI 落地和产物留存，强调稳定性与可维护性 |
| `fuzzing-test` | 为 Go 代码生成模糊测试 | 先做适用性门禁，不适合的目标会明确拒绝，避免产出低价值 fuzz case |
| `systematic-debugging` | 对 bug、异常行为和失败场景做系统化排查 | 明确要求先找根因再修复，避免拍脑袋试错式修 bug |


完整的示例可参考: https://github.com/johnqtcg/issue2md (.github/workflows/ci.yml)


### 搜索、调研与报告

这一类 skill 适合做信息搜集、事实核查、资料对比和正式研究输出。

| Skill 名称 | 功能用途 | 主要亮点 / 优势 |
| --- | --- | --- |
| `google-search` | 用 Google 检索做资料搜集、事实验证和来源核查 | 强调查询分类、证据链、交叉核验和可复用搜索串 |
| `deep-research` | 做带来源支撑的深度研究与分析 | 强制内容抽取、交叉验证和抗幻觉检查，适合研究、比较和趋势分析 |

### 工具执行与任务自动化

这一类 skill 偏向“把任务执行完”。

| Skill 名称 | 功能用途 | 主要亮点 / 优势 |
| --- | --- | --- |
| `yt-dlp-downloader` | 生成并执行 `yt-dlp` 下载命令 | 先探测格式再下载，支持单视频、播放列表、音频、字幕和认证内容等场景 |

<a id="cn-evaluate-and-output"></a>
## 评审与输出样例

这个仓库和普通“skills 示例仓库”最大的区别，是它不仅展示 skill，还展示：

1. 这个 skill 为什么好
2. 它在真实任务中产出了什么

你可以直接对照阅读：

- 评审报告：[`evaluate/`](/Users/john/awesome-skills/evaluate)
- 输出样例：[`outputexample/`](/Users/john/awesome-skills/outputexample)

典型例子：

- `google-search`
  - 评审：[`evaluate/google-search-skill-eval-report.zh-CN.md`](/Users/john/awesome-skills/evaluate/google-search-skill-eval-report.zh-CN.md)
  - 输出：[`outputexample/google-search/中国制造2025目标完成度研究.pdf`](/Users/john/awesome-skills/outputexample/google-search/中国制造2025目标完成度研究.pdf)
- `unit-test`
  - 评审：[`evaluate/unit-test-skill-eval-report.zh-CN.md`](/Users/john/awesome-skills/evaluate/unit-test-skill-eval-report.zh-CN.md)
  - 输出：[`outputexample/unit-test/`](/Users/john/awesome-skills/outputexample/unit-test)
- `yt-dlp-downloader`
  - 输出截图：[`outputexample/yt-dlp-downloader/`](/Users/john/awesome-skills/outputexample/yt-dlp-downloader)

<a id="cn-governance"></a>
## 治理文档

如果你准备参与贡献，或者需要查看仓库治理规则，建议从这里开始：

- 贡献指南：[`CONTRIBUTING.zh-CN.md`](/Users/john/awesome-skills/CONTRIBUTING.zh-CN.md)
- 安全策略：[`SECURITY.zh-CN.md`](/Users/john/awesome-skills/SECURITY.zh-CN.md)
- 行为准则：[`CODE_OF_CONDUCT.zh-CN.md`](/Users/john/awesome-skills/CODE_OF_CONDUCT.zh-CN.md)


<a id="cn-audience"></a>
## 适合谁

- 想系统学习如何写高质量 skill 的人
- 想把 Claude Code / Agent 能力沉淀为可复用资产的人
- 想看“方法论 + skill + 评审 + 输出样例”完整闭环的人
- 想把 AI 能力接入真实研发流程，而不是停留在 prompt 演示层的人

<a id="cn-license"></a>
## License

本项目使用 MIT License，见 [`LICENSE`](/Users/john/awesome-skills/LICENSE)。
