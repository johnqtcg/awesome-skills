---
title: 贡献指南
owner: john
status: active
last_updated: 2026-03-13
applicable_versions: repository layout as of 2026-03
---

# 贡献指南

感谢你参与 `awesome-skills`。

项目是一个围绕 **设计高质量skill、skill分享、评审报告和输出样例** 构建的知识与实践仓库。贡献时，请优先考虑内容质量、结构完整性、可验证性。

Language:
- English: [CONTRIBUTING.md](CONTRIBUTING.md)
- 中文：`CONTRIBUTING.zh-CN.md`

## 1. 基本原则

请围绕以下目标贡献内容：

- 让 skill 方法论更清晰、更系统、更可执行
- 让 `skills/` 中的示例更高质量、更可复用
- 让 `evaluate/` 中的评审更具体、更有证据
- 让 `outputexample/` 中的样例更能证明 skill 的真实价值

核心要求：

- 以仓库现有结构为准，不引入与本项目定位不符的工程模板
- 文档优先讲清楚 `What / Why / How`
- 贡献内容应尽量可验证，不要只写抽象观点
- 中英文内容应保持一致，避免一边更新、一边过期

## 2. 你可以贡献什么

本仓库欢迎以下几类贡献：

1. 改进 `bestpractice/` 中的方法论文档
2. 新增或重构 `skills/` 中的高质量 skill
3. 补充或修正 `evaluate/` 中的评审报告
4. 补充或更新 `outputexample/` 中的输出样例
5. 修复 README、目录导航、链接和双语同步问题
6. 修正文档中的事实错误、表达歧义或示例缺陷

## 3. 仓库结构约定

请先熟悉仓库的四个核心目录：

| 路径 | 作用 |
| --- | --- |
| [`bestpractice/`](bestpractice/README.zh-CN.md) | skill 最佳实践文档，中英双语 |
| [`skills/`](skills/index.md) | 高质量 skill 示例 |
| [`evaluate/`](evaluate/index.md) | 对 skill 的评审报告，中英双语 |
| [`outputexample/`](outputexample/index.md) | skill 的真实输出样例 |

## 4. 推荐的贡献单元

如果你要新增一个高质量 skill，推荐按“完整贡献单元”提交，而不是只提交一个孤立的 `SKILL.md`：

1. `skills/<skill-name>/SKILL.md`
2. 至少一份评审报告：
   - `evaluate/<skill-name>-skill-eval-report.zh-CN.md`
   - `evaluate/<skill-name>-skill-eval-report.md`
3. 至少一个输出样例目录：
   - `outputexample/<skill-name>/`

这不是机械要求，但这是本仓库当前最符合实际的贡献方式。仓库现有内容就是按这种闭环组织的。

## 5. 命名与组织约定

请遵循仓库已有命名方式：

- skill 目录名使用 `kebab-case`
- skill 主文件固定为 `SKILL.md`
- 评审报告文件名使用：
  - `<skill-name>-skill-eval-report.md`
  - `<skill-name>-skill-eval-report.zh-CN.md`
- 输出样例目录通常与 skill 同名：
  - `outputexample/<skill-name>/`

如果你修改的是双语文档，请同步更新对应语言版本，例如：

- `README.md` 和 `README.zh-CN.md`
- `CONTRIBUTING.md` 和 `CONTRIBUTING.zh-CN.md`
- `bestpractice/*.md` 和对应英文文档

## 6. 文档与内容质量要求

提交前请至少自查以下事项：

1. 文档结构清晰，读者能快速知道结论和入口
2. 术语前后一致，不混用同义词
3. Markdown 链接和路径有效
4. 中英文版本没有明显内容漂移
5. 新增 skill 时，描述、门禁、反例、输出契约等核心部分完整
6. 新增评审时，不要只写“很好/不好”，要写出证据和判断依据
7. 新增输出样例时，文件命名和目录结构应清晰可追溯

## 7. 提交前建议执行的检查

贡献前建议至少执行这些仓库级检查：

```bash
find skills -maxdepth 2 -name SKILL.md | sort
find evaluate -maxdepth 1 -type f | sort
find outputexample -maxdepth 2 -type f | sort
sed -n '1,200p' README.zh-CN.md
sed -n '1,200p' README.md
git diff --check
```

如果你正在新增某个 skill，建议再检查一次它的闭环文件是否齐全：

```bash
find "skills/<skill-name>" -maxdepth 2 -type f | sort
find evaluate -maxdepth 1 -type f | rg "<skill-name>"
find outputexample -maxdepth 2 -type f | rg "<skill-name>"
```

## 8. 分支与提交建议

建议的分支命名：

- `feature/<topic>`
- `docs/<topic>`
- `fix/<topic>`
- `chore/<topic>`

建议的提交信息风格：

```text
<type>(<scope>): <subject>
```

示例：

```text
docs(readme): reorganize skill categories
feat(skill): add thirdparty api integration example
fix(bestpractice): correct broken section links
```

## 9. Pull Request 要求

请在 PR 描述中尽量包含：

- 变更背景与目标
- 主要改动内容
- 为什么这样改
- 如果涉及 skill：配套的评审报告和输出样例在哪里
- 如果涉及双语文档：是否已同步中英文版本

推荐 PR 自检清单：

- [ ] 改动符合本仓库“方法论 + skill + 评审 + 输出样例”的定位
- [ ] 相关 Markdown 链接和路径有效
- [ ] 中英文内容已同步，或明确说明未同步原因
- [ ] 如果新增 skill，已补充对应评审和输出样例，或明确说明缺失原因
- [ ] README / 导航文档在必要时已同步更新

## 10. 安全与负责任披露

仓库治理文档：

- 安全文档：
  - [SECURITY.zh-CN.md](SECURITY.zh-CN.md)
  - [SECURITY.md](SECURITY.md)
- 行为准则：
  - [CODE_OF_CONDUCT.zh-CN.md](CODE_OF_CONDUCT.zh-CN.md)
  - [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)

如果你的贡献涉及：

- 可利用的安全问题
- 凭证、密钥或敏感数据
- 可能误导用户执行危险操作的内容

请不要在公开 Issue 或 PR 中直接披露可利用细节。先以最小必要信息说明问题，再与维护者确认后续处理方式。

## 11. 维护说明

当以下内容变化时，请同步更新贡献指南：

1. 仓库目录结构变化
2. 新增或移除核心目录
3. skill / 评审 / 输出样例的命名约定变化
4. 双语文档维护策略变化
