---
title: Go 编码基础规范
owner: team
status: active
last_updated: 2026-03-17
applicable_versions: Go 1.21+
---

# Go 编码基础规范

Go 项目的基础规范涵盖代码格式化、静态检查、Git 工作流、目录结构、命名注释、API 设计和接口文档七个维度。所有规范通过 CI 门禁强制执行，提交前必须通过 `gofmt`、`goimports-reviser`、`golangci-lint` 检查。

---

## 1 代码格式化

提交代码前必须做代码格式化，保持团队代码风格一致。

### 1.1 gofmt

gofmt 是 Go 工具链内置的格式化工具，安装 Go 后即可使用。

```bash
# 格式化单个文件
gofmt -w file.go

# 格式化目录下所有 Go 文件
gofmt -w ./logic
```

### 1.2 goimports-reviser

goimports-reviser 提供比 goimports 更精细的 import 分组控制，按照团队约定的分组顺序排列：**标准库 / 第三方包 / blank import / 项目内部包**。

正确的 import 分组示例：

```go
import (
    "context"
    "time"

    "github.com/pkg/errors"
    "github.com/zeromicro/go-zero/core/logx"
    "github.com/zeromicro/go-zero/core/stores/sqlx"

    "myproject/com/model"
    "myproject/utils/consts"
    "myproject/utils/lib"
)
```

> **不要使用 goimports**，它按包首字母顺序排列，会打乱约定的分组。

安装和使用：

```bash
# 安装（锁定版本，保证 CI 与本地行为一致）
go install github.com/incu6us/goimports-reviser/v3@v3.9.0

# 验证
goimports-reviser -version
# goimports-reviser version v3.9.0

# 格式化当前目录
goimports-reviser

# 推荐设置 alias（添加到 .zshrc 或 .bashrc）
alias gof="goimports-reviser ./..."
```

### 1.3 集成到 CI 流程

在 `.github/workflows/ci.yml` 中添加格式化检查：

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
  schedule:
    - cron: '0 3 * * *'

jobs:
  ci:
    name: Format
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Go
        uses: actions/setup-go@v5
        with:
          go-version-file: go.mod
          cache: true
      - name: Install goimports-reviser
        run: go install github.com/incu6us/goimports-reviser/v3@v3.9.0
      - name: Format (gofmt + goimports-reviser)
        run: |
          make fmt
          git diff --exit-code || (echo "code is not formatted; run 'make fmt' and commit changes" && exit 1)
```

### 1.4 Makefile 构建目标

本规范在 CI 配置中多处引用 `make` 目标，以下是标准 Makefile 的核心实现供参考：

```makefile
# 默认 Go 版本，可通过环境变量覆盖
GO      ?= go
COVER_MIN ?= 80

.PHONY: fmt lint test cover-check build-all

## fmt: 格式化代码（gofmt + goimports-reviser）
fmt:
	gofmt -w .
	goimports-reviser ./...

## lint: 运行静态代码检查
lint:
	golangci-lint run --config .golangci.yaml ./...

## test: 运行单元测试并输出覆盖率报告
test:
	$(GO) test -race -coverprofile=coverage.out ./...
	$(GO) tool cover -func=coverage.out

## cover-check: 断言覆盖率不低于 COVER_MIN（默认 80%）
cover-check: test
	@COVERAGE=$$(go tool cover -func=coverage.out | grep total | awk '{print $$3}' | tr -d '%'); \
	echo "Coverage: $${COVERAGE}%  (minimum: $(COVER_MIN)%)"; \
	if [ $$(echo "$${COVERAGE} < $(COVER_MIN)" | bc) -eq 1 ]; then \
		echo "FAIL: coverage $${COVERAGE}% is below minimum $(COVER_MIN)%"; exit 1; \
	fi

## build-all: 编译 cmd/ 下所有可执行文件到 bin/
build-all:
	$(GO) build -o bin/ ./cmd/...

## help: 打印所有可用目标
help:
	@grep -E '^## ' Makefile | sed 's/## //'
```

> 将此 Makefile 放在项目根目录，CI 脚本即可通过统一的 `make <target>` 调用，无需在 YAML 中硬编码具体命令。

---

## 2 静态代码检查

提交代码前必须通过静态代码检查，用于发现潜在缺陷、性能问题和规范违反。

### 2.1 为什么要做静态代码检查

静态分析在不运行程序的前提下，通过词法、语法、语义、控制流、数据流等多层面扫描，识别以下问题：

- **潜在逻辑错误**：未初始化变量、空指针解引用、资源未释放
- **编码规范违反**：不一致命名、过长函数、过高复杂度、API 误用
- **安全漏洞**：SQL 注入、XSS 风险、不安全并发访问
- **性能瓶颈**：低效循环、不必要内存分配

核心价值：**在代码编写阶段发现问题，远比测试或生产环境发现的修复成本低得多。**

### 2.2 实际案例

#### 2.2.1 性能优化

linter 建议给切片预先分配内存：

```
internal/pkg/dbutil/oracle_update_or_insert_builder.go:66:2:
  Consider pre-allocating `parts` (prealloc)
```

```go
func buildUpdateSet(cols []columnMeta, t reflect.Type, args *[]interface{}, paramIndex *int) []string {
    // BAD: var parts []string
    // GOOD: 预先分配内存
    parts := make([]string, 0, len(cols))
    for _, c := range cols {
        if c.PrimaryKey || c.Exclude {
            continue
        }
        if c.EmptyValue && hasTag(t, c.Column, "omitempty") {
            continue
        }
        parts = append(parts, fmt.Sprintf("t.%s = :%d", c.Column, *paramIndex))
        *args = append(*args, c.Value)
        *paramIndex++
    }
    return parts
}
```

#### 2.2.2 代码可读性和维护性优化

linter 提醒代码复杂度过高，建议拆分：

```
main.go:34:1: cyclomatic complexity 16 of func `main` is high (> 15) (gocyclo)
```

修改方法：将单体 `main()` 拆分为 App 结构体 + 独立方法（`loadConfig`、`initLogger`、`initDependencies`、`initFiberApp`、`gracefulShutdown` 等），每个方法职责单一。

#### 2.2.3 命名规范提醒

linter 提示无意义的包名：

```
utils/time.go:1:9: var-naming: avoid meaningless package names (revive)
package utils
```

### 2.3 安装和使用

```bash
# 安装 golangci-lint（推荐与 CI 使用相同版本）
go install github.com/golangci/golangci-lint/v2/cmd/golangci-lint@v2.6.2
# 或
brew install golangci-lint

# 验证
golangci-lint --version
# golangci-lint has version v2.6.2 built with go1.24.x

# 基本使用
golangci-lint run ./dir

# 推荐设置 alias
alias linter='golangci-lint run --config .golangci.yaml'
```

### 2.4 `.golangci.yaml` 配置说明

项目根目录下的 `.golangci.yaml` 控制启用哪些 linter 及对应规则，以下是团队推荐的最小可用配置：

```yaml
version: "2"

linters:
  enable:
    - gofmt          # 格式化检查（CI 中由 gofmt 单独处理，此处作双重保障）
    - revive         # 替代 golint，支持自定义规则
    - govet          # 官方 vet 检查（shadow、printf 格式等）
    - errcheck       # 确保 error 被处理
    - staticcheck    # 综合静态分析
    - prealloc       # 切片预分配建议
    - gocyclo        # 圈复杂度检查
    - misspell       # 英文拼写检查

linters-settings:
  gocyclo:
    min-complexity: 15   # 超过 15 的函数需要拆分
  revive:
    rules:
      - name: var-naming
        disabled: false

issues:
  exclude-rules:
    # 测试文件放宽 errcheck 规则
    - path: "_test\\.go"
      linters:
        - errcheck
  max-issues-per-linter: 50
  max-same-issues: 10
```

> 将 `.golangci.yaml` 提交到代码库，确保所有人本地与 CI 使用相同的检查规则。

### 2.5 集成到 CI 流程

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:

jobs:
  ci:
    name: Test · Lint · Build
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Go
        uses: actions/setup-go@v5
        with:
          go-version-file: go.mod
          cache: true
      - name: Install golangci-lint v2
        run: go install github.com/golangci/golangci-lint/v2/cmd/golangci-lint@v2.6.2
      - name: Test with coverage gate (>=80%)
        run: make cover-check COVER_MIN=80
      - name: Lint
        run: make lint
      - name: Build
        run: make build-all
```

### 2.6 CI 检查失败时的处理方法

#### 格式化检查失败

```
Error: code is not formatted; run 'make fmt' and commit changes
```

修复步骤：

```bash
make fmt
git add -u
git commit -m "style: run gofmt and goimports-reviser"
git push
```

#### Lint 检查失败

先查看具体报错，再决定修复方式：

```bash
# 本地复现 CI 中的 lint 结果
make lint
```

**方式一：修改代码**（首选）

根据 lint 提示修改代码，这是大多数情况的正确做法。

**方式二：`//nolint` 指令**（仅在误报或有充分理由时使用）

```go
// 抑制单行的某个 linter
result, _ := someFunc() //nolint:errcheck // err 在上层已统一处理

// 抑制整个函数的某个 linter
//nolint:gocyclo // 该函数是状态机，高复杂度是预期设计
func handleStateMachine(state State) {
    // ...
}
```

> **规则**：`//nolint` 必须注明原因（注释说明为何可以忽略），否则视为无效抑制，Code Review 阶段应驳回。

---

## 3 Git 规范

### 3.1 GitHub Flow 工作流

团队采用 GitHub Flow 工作流，核心只有一条长期分支 `main`：

1. `main` 分支始终保持可部署状态
2. 新功能从 `main` 创建 feature 分支
3. 在 feature 分支上持续提交，推送到远程
4. 开发完成后提 Pull Request
5. 团队成员进行 Code Review
6. Review 通过、CI 绿灯后合并到 `main`
7. 合并后立即触发自动部署

**优点**：流程简单、天然适合持续部署、强制 Code Review

**缺点**：无 develop 缓冲层、对 CI/CD 和自动化测试要求高

### 3.2 Conventional Commits 提交规范

#### 3.2.1 为什么要统一 commit 提交信息

- 清晰知道每个 commit 的变更内容，方便浏览变更历史
- 支持过滤查找：`git log --oneline --extended-regexp --grep "^(feat|fix|perf)"`
- 自动生成 Change Log
- 触发构建或发布流程
- 确定语义化版本号（fix → PATCH，feat → MINOR，BREAKING CHANGE → MAJOR）

#### 3.2.2 格式

```
<type>(<scope>): <subject>

<body>

<footer>
```

其中 `type` 和 `subject` 是必填项，`scope`、`body`、`footer` 为可选。

**type 类型**

| type | 说明 | 示例 |
|------|------|------|
| feat | 新功能 | feat(auth): add OAuth2 login |
| fix | 修复 bug | fix(api): handle nil pointer in GetUser |
| docs | 文档变更 | docs: update API README |
| refactor | 重构（非新功能、非修 bug） | refactor(db): simplify connection pool logic |
| perf | 性能优化 | perf(query): add index on user_id |
| test | 测试相关 | test(auth): add login edge case |
| chore | 构建/工具/依赖变更 | chore: upgrade Go to 1.24 |
| style | 代码风格（不影响逻辑） | style: run gofmt |
| ci | CI 配置 | ci: add golangci-lint step |

**scope（可选）**

指明本次变更影响的模块或功能域：模块名（auth, api, db）、包名（handler, repository）、功能域（connection-pool, rate-limit）。

**subject 规则**

- 不超过 50 字符
- 使用动词原形开头：add, fix, update, remove, refactor
- 不加句号
- 描述"做了什么"而非"改了哪个文件"

```bash
# GOOD
feat(auth): add JWT token refresh mechanism
fix(api): prevent race condition in cache update

# BAD
feat(auth): added JWT token refresh mechanism.  # 过去式 + 句号
fix: fix bug                                     # 没有具体信息
update code                                      # 缺少 type，描述模糊
```

**body（可选）**

解释**为什么**需要这个变更，记录设计决策和权衡取舍，每行不超过 72 字符。

**footer（可选）**

- `BREAKING CHANGE:` 不兼容变更说明（触发 major 版本号升级）
- `Closes #123` 关联并自动关闭 issue
- `Refs:` 相关链接或参考文档

**完整示例**

```
feat(connection-pool): add idle connection cleanup

Previously idle connections were never cleaned up, leading to
resource exhaustion under sustained load. This adds a background
goroutine that periodically closes connections idle for more than
ConnMaxIdleTime.

Closes #245
```

#### 3.2.3 注意事项

- **原子性**：不要把不相关的修改混在一个 commit 里
- **描述"为什么"而不是"做了什么"**：代码 diff 已展示变更内容
- **遵循团队规范**：Conventional Commits 格式

#### 3.2.4 交互式生成 commit message

```bash
# 安装 commitizen
npm install -g commitizen cz-conventional-changelog

# 初始化项目配置
echo '{ "path": "cz-conventional-changelog" }' > .czrc

# 使用（代替 git commit）
git cz
```

### 3.3 自动生成 CHANGELOG

```bash
# 安装
npm install -g conventional-changelog-cli

# 生成 CHANGELOG（追加模式）
conventional-changelog -p angular -i CHANGELOG.md -s
```

自动归类：feat → Features，fix → Bug Fixes，BREAKING CHANGE → Breaking Changes。

配合语义化版本：BREAKING CHANGE → major，feat → minor，仅 fix → patch。

### 3.4 分支命名规范

格式：`<type>/<short-description>`，小写字母，单词间用短横线 `-` 连接。

| 类型 | 命名示例 | 说明 |
|------|----------|------|
| 新功能 | feature/oauth-login | 功能分支 |
| 修复 | fix/nil-pointer-getuser | Bug 修复 |
| 重构 | refactor/db-connection-pool | 重构 |
| 发布 | release/v1.2.0 | 发布分支 |
| 热修复 | hotfix/critical-auth-bypass | 紧急修复 |

团队约定的命名方式：`feature/tp-4172/tcg-111144`、`fix/tp-4289/tcg-114352`，方便将代码与需求单/bug 单关联。

**分支保护规则**

| 规则 | main/master | develop |
|------|-------------|---------|
| 禁止直接推送 | Yes | Yes |
| 必须通过 PR 合并 | Yes | Yes |
| 要求至少 1 人 approve | Yes | 建议 |
| 要求 CI 全部通过 | Yes | Yes |
| 禁止 force push | Yes | Yes |

### 3.5 PR 最佳实践

**粒度**

- 一个 PR 解决一个问题（一个功能 / 一个 bug / 一次重构）
- 控制在 200-400 行变更以内
- 大功能拆分为多个串行 PR，通过 feature flag 控制未完成部分
- 避免在功能 PR 中夹带格式化或重构

**PR 描述模板**（`.github/PULL_REQUEST_TEMPLATE.md`）

```markdown
## Summary
<!-- 1-3 句话描述本次变更的目的 -->

## Changes
<!-- 列出具体的改动点 -->
-
-

## Test Plan
<!-- 如何验证变更是正确的 -->
- [ ] 单元测试通过
- [ ] 手动验证场景 X

## Screenshots（if applicable）
<!-- UI 变更请附截图 -->
```

**Code Review 要点**

Reviewer 角度：
- 关注设计和逻辑，风格问题交给 linter
- 优先指出 bug 和安全隐患，其次是可维护性建议
- 用"建议"而非"要求"的语气（`nit:` 前缀表示非阻塞建议）

Author 角度：
- PR 提交前先做 self-review
- 对复杂逻辑主动添加 review comment 说明意图
- 及时回复 reviewer 的问题

**CI 门禁**

```yaml
steps:
  - name: Lint
    run: golangci-lint run ./...
  - name: Test
    run: go test -race -coverprofile=coverage.out ./...
  - name: Build
    run: go build ./...
  - name: Coverage Gate
    run: go tool cover -func=coverage.out
```

**合并策略**

| 策略 | 命令 | 效果 | 适用场景 |
|------|------|------|----------|
| Create a merge commit | `git merge --no-ff` | 保留所有 commit + merge commit | 需要保留完整开发历史 |
| **Squash and merge** | `git merge --squash` | 压缩为一个 commit | **团队默认使用** |
| Rebase and merge | `git rebase + --ff` | 线性历史 | 每个 commit 都经过精心整理 |

团队使用 **Squash and merge** 策略。在 GitHub 仓库 Settings → General → Pull Requests 中禁用不需要的合并策略。

### 3.6 rebase 黄金法则

**永远不要对已推送到远程的公共分支执行 rebase。**

rebase 会改写 commit 的 SHA-1 哈希值，导致协作者 pull 时出现大量重复提交和冲突。

安全使用 rebase 的场景：
- 本地未 push 的 feature 分支，rebase 上游 main 的最新代码
- 合入主分支前，用 `rebase -i` 整理本地提交历史
- `git pull --rebase` 替代默认的 merge 拉取

---

## 4 项目目录结构规范

Go 没有强制项目结构标准，但社区形成了事实上的约定。

### 4.1 Go 项目的三种形态

| 形态 | 特征 | 典型代表 |
|------|------|----------|
| 可执行程序 | 有 main 包，产出二进制文件 | API 服务、CLI 工具、微服务 |
| 库（library） | 无 main 包，被其他项目 import | golang.org/x/sync、go-redis |
| 混合型 | 既是库，又提供 CLI 工具 | cobra（库 + cobra-cli 工具） |

**核心原则**：布局为项目形态服务，不要为了"标准"而标准。一个 50 行的 CLI 工具不需要 `cmd/internal/pkg` 三层目录。

### 4.2 核心目录约定

#### 4.2.1 cmd/ — 可执行程序入口

每个子目录对应一个可执行程序，子目录名即二进制名：

```
cmd/
├── server/
│   └── main.go  → go build -o server ./cmd/server
├── worker/
│   └── main.go  → go build -o worker ./cmd/worker
└── cli/
    └── main.go  → go build -o cli ./cmd/cli
```

规则：
- 每个子目录是独立的 `package main`
- `main.go` 应该尽量**薄**——只做参数解析、依赖组装、启动，不含业务逻辑
- 实际逻辑放在 `internal/` 或根包中

```go
// cmd/server/main.go — 薄入口示例
package main

import (
    "log"
    "myapp/internal/server"
    "myapp/internal/config"
)

func main() {
    cfg, err := config.Load()
    if err != nil {
        log.Fatal(err)
    }
    srv := server.New(cfg)
    if err := srv.Run(); err != nil {
        log.Fatal(err)
    }
}
```

何时不需要 `cmd/`：如果项目只有一个可执行文件，`main.go` 放在根目录完全可以。

#### 4.2.2 internal/ — 访问控制屏障

`internal/` 是 Go 编译器**强制执行**的访问控制——`internal/` 下的包只能被其父目录及子目录 import：

```
myapp/
├── cmd/server/main.go       # OK: 可以 import myapp/internal/...
├── internal/
│   ├── handler/              # OK: 可以 import myapp/internal/service/
│   ├── service/
│   └── repo/
└── pkg/api/                  # OK: 可以 import myapp/internal/...（同一模块内）

# 外部项目:
import "myapp/internal/handler" // 编译错误！
```

这是**编译器级别**的封装，不是约定，不是 lint 规则，是**硬性限制**。

推荐的 `internal/` 组织方式：

```
internal/
├── config/       # 配置加载
├── handler/      # HTTP/gRPC handler
├── service/      # 业务逻辑层
├── repo/         # 数据访问层
├── model/        # 领域模型
└── middleware/    # 中间件
```

#### 4.2.3 pkg/ — 可复用的公开库

`pkg/` 存放可以被外部项目 import 的公开包。**注意：pkg/ 只是约定，编译器不做特殊处理。**

建议：
- **库项目**：直接在根目录组织包，不需要 `pkg/`
- **应用项目**：需要暴露的通用工具包放 `pkg/`；否则全放 `internal/`

### 4.3 辅助目录约定

| 目录 | 用途 | 示例内容 |
|------|------|----------|
| `api/` | 接口定义文件 | OpenAPI yaml、Proto 文件、GraphQL schema |
| `configs/` | 配置模板（不含敏感信息） | config.yaml.example、docker-compose.yaml |
| `scripts/` | 构建、安装、分析脚本 | build.sh、migrate.sh |
| `deployments/` | 部署相关 | Dockerfile、k8s yaml、terraform |
| `test/` | 外部测试（集成/E2E） | testdata/、integration/、e2e/ |
| `docs/` | 文档 | architecture.md、api-guide.md |
| `tools/` | 项目开发工具 | tools.go（工具依赖声明）、codegen/ |

> 单元测试约定放在被测包内（`_test.go`），不放在 `test/` 目录。

`tools.go` 用于固定工具版本：

```go
//go:build tools

package tools

import (
    _ "golang.org/x/tools/cmd/stringer"
    _ "github.com/golangci/golangci-lint/cmd/golangci-lint"
)
```

### 4.4 完整项目目录结构示例

**小型项目（CLI 工具/简单服务）**

```
mytool/
├── main.go
├── app.go
├── app_test.go
├── config.go
├── go.mod
├── go.sum
└── README.md
```

**中型项目（单体 API 服务）**

```
myapi/
├── cmd/
│   └── server/
│       └── main.go
├── internal/
│   ├── config/
│   ├── handler/
│   ├── service/
│   ├── repo/
│   ├── model/
│   └── middleware/
├── migrations/
├── configs/
│   └── config.yaml.example
├── go.mod
├── go.sum
├── Makefile
└── README.md
```

**大型项目（多服务 + SDK）**

```
platform/
├── cmd/
│   ├── api-server/
│   ├── worker/
│   └── admin-cli/
├── internal/
│   ├── api/          # API 服务逻辑
│   ├── worker/       # Worker 逻辑
│   ├── shared/       # 内部共享代码
│   └── model/
├── pkg/
│   ├── sdk/          # 对外暴露的 SDK
│   └── errors/       # 公共错误类型
├── api/
│   └── proto/
├── deployments/
├── scripts/
├── go.mod
├── Makefile
└── README.md
```

### 4.5 常见误区

| 误区 | 说明 |
|------|------|
| **过度设计** | 50 行的工具套了完整 enterprise 布局。正确做法：直接 `main.go` + 一两个文件，随项目增长再重构 |
| **照搬 golang-standards/project-layout** | Go 团队成员 Russ Cox 明确表示这不是 Go 官方标准，不要盲目照搬 |
| **src 目录** | Go 模块系统以 `go.mod` 为根，不需要也不应该有 `src/` 目录 |
| **按类型分包** | `models/` `controllers/` `services/` 会导致循环依赖，应按领域分包（`user/` `order/` `payment/`） |
| **utils/common/shared 包** | 违反高内聚原则，应按功能拆分：`stringx/`、`httputil/`、`timeutil/` |

### 4.6 Go 工具链与目录的关系

```bash
# go build — 构建 cmd/ 下的程序
go build -o bin/server ./cmd/server
go build ./cmd/...

# go test — 测试整个项目
go test ./...
go test ./internal/service/...

# go install — 安装到 $GOPATH/bin
go install ./cmd/server
go install github.com/you/project/cmd/mytool@latest

# go generate — 运行所有 generate 指令
go generate ./...
```

### 4.7 包/目录划分原则

**包的大小**——足够小以便理解，足够大以保持独立：

| 信号 | 可能需要拆分 | 可能需要合并 |
|------|-------------|-------------|
| 文件数 | >15 个文件 | 1 个文件 + 10 行 |
| 导出符号 | >30 个导出类型/函数 | 只有 1-2 个 |
| 依赖 | import 了 10+ 个同项目的包 | 无人 import |
| 职责 | 名字需要用 And/Or 描述 | 功能完全被另一个包包含 |

**依赖方向**——单向、从上到下：

```
cmd/ → internal/ → model/（无逆向依赖）

handler → service → repo → model
    ↓         ↓       ↓
  接口定义在使用方
```

如果出现循环依赖：提取公共类型到独立包、使用接口解耦、合并过于细碎的包。

### 4.8 目录总结

| 目录 | 作用 | 编译器强制？ | 何时需要 |
|------|------|:---:|------|
| `cmd/` | 可执行程序入口 | 否 | 多个二进制时 |
| `internal/` | 私有代码，外部不可 import | **是** | 几乎所有项目 |
| `pkg/` | 公开可复用的库代码 | 否 | 需要暴露 SDK 时 |
| `api/` | 接口定义文件 | 否 | 有 API 规范时 |
| `configs/` | 配置模板 | 否 | 有配置文件时 |
| `scripts/` | 辅助脚本 | 否 | 有构建/部署脚本时 |
| `test/` | 外部测试数据 | 否 | 有集成/E2E 测试时 |
| `tools/` | 开发工具依赖 | 否 | 有代码生成等工具时 |

---

## 5 命名和注释

### 5.1 包命名

- 包名必须和目录名一致
- **全部小写**，没有大写或下划线：`runtime` 而不是 `runTime`，`syscall` 而不是 `sysCall`
- **不要用 common、util、shared 或 lib** 这类宽泛的包名

> "The bigger the interface, the weaker the abstraction." — Go Proverbs
>
> 包名也是同理：**包名越通用，价值越低。**

### 5.2 文件命名

- 文件名要简短有意义
- 文件名应小写，使用下划线分割单词
- **包名负责提供上下文信息，文件名只负责解释文件的功能**，不重复包名

```
# Go 标准库的做法:
net/http/client.go        # 而不是 http_client.go
net/http/server.go        # 而不是 http_server.go
net/http/transport.go     # 而不是 http_transport.go

database/sql/db.go        # 而不是 sql_db.go
database/sql/rows.go
database/sql/convert.go
```

项目中同样遵循此原则：

```
# internal/apiserver/persistence/cache/ 目录下
customer.go               # 而不是 customer_cache.go
customer_immutable.go
merchant.go
```

### 5.3 变量命名

- 简单环境中可以将名称简写：`user` → `u`，`userID` → `uid`
- 特有名词规则：
  - 私有且首个单词：使用小写，如 `apiClient`
  - 其他情况：使用原有写法，如 `APIClient`、`repoID`、`UserID`
- 常见特有名词：`API`、`ASCII`、`CPU`、`CSS`、`DNS`、`EOF`、`HTML`、`HTTP`、`ID`、`IP`、`JSON`、`URL`、`UUID`、`XML` 等
- bool 类型以 `Has`、`Is`、`Can` 或 `Allow` 开头：

```go
var hasConflict bool
var isExist bool
var canManage bool
var allowGitHook bool
```

- 局部变量尽可能短小：`buf` 代替 `buffer`，`i` 代替 `index`
- 同一变量使用 3 次及以上应设置为常量
- 变量名中**不要带类型信息**：`users []*User` 而不是 `userSlice []*User`
- 变量、类型、接口、常量的命名**不要带包名**：`bytes.Buffer` 而不是 `bytes.ByteBuffer`

### 5.4 函数命名

- 函数名不携带包名的上下文信息：`time.Now()` 而不是 `time.NowTime()`
- 函数名尽量简短
- 返回类型与包名同名时可省略类型信息：`time.Add()` 返回 `Time`
- 返回类型与包名不同时加入类型信息：`time.ParseDuration()` 返回 `Duration`

### 5.5 注释

- **注释一律使用英文**
- **公共符号始终要注释**（可导出的变量、常量、结构体、函数），格式：`// ObjectName does ...`

```go
// DataNotFound indicates the requested record does not exist.
const DataNotFound ErrorCode = "data_not_found"
```

- 对库中的任何函数都必须注释（实现接口的方法例外）
- 注释应该解释：
  - 代码的**作用**（what）
  - 代码是**如何做的**（how）
  - 代码实现的**原因**（why）
  - 代码**什么情况下会出错**

---

## 6 API 设计

### 6.1 RESTful API 介绍

REST 把所有内容视为资源，资源的操作对应 HTTP 方法（GET/POST/PUT/DELETE）。核心特点：

- 以资源为中心，所有行为是资源上的 CRUD 操作
- 资源使用 URI 标识，每个资源实例有唯一 URI
- 使用 JSON 在 HTTP Body 里表征资源状态
- 无状态——每个请求包含所有足够完成本次操作的信息

### 6.2 RESTful API 设计原则

#### 6.2.1 URI 设计

- 资源名使用**名词复数**：`/users`、`/orders`
- URI 结尾不包含 `/`
- URI 中不能出现下划线 `_`，必须用中杠线 `-`
- URI 路径用小写
- 避免层级过深（超过 2 层），转化为查询参数：

```bash
# 不推荐
/schools/tsinghua/classes/rooma/students/zhang

# 推荐
/students?school=qinghua&class=rooma
```

#### 6.2.2 HTTP 方法映射

| 方法 | 操作 | 安全性 | 幂等性 |
|------|------|:---:|:---:|
| GET | 读取 | Yes | Yes |
| POST | 创建 | No | No |
| PUT | 全量更新 | No | Yes |
| DELETE | 删除 | No | Yes |

批量删除推荐：`DELETE /users?ids=1,2,3`（团队统一使用此方式）。

#### 6.2.3 统一返回格式

```go
// 成功响应
type APIBaseValueResp struct {
    Success bool        `json:"success"`
    Value   interface{} `json:"value,omitempty"`
}

// 失败响应
type APIBaseMessageResp struct {
    Success   bool   `json:"success"`
    ErrorCode string `json:"errorCode,omitempty"`
    Message   string `json:"message,omitempty"`
}
```

#### 6.2.4 API 版本管理

版本标识放在 URL 中：`/v1/users`。

#### 6.2.5 API 命名

使用**脊柱命名法**（kebab-case）：全小写，用 `-` 连接单词。示例：`selected-actions`、`artifact-id`。

#### 6.2.6 分页/过滤/排序/搜索

- **分页**：`/users?offset=0&limit=20`
- **过滤**：`/users?fields=email,username,address`
- **排序**：`/users?sort=age,desc`
- **搜索**：统一使用 `q` 参数，服务端对指定字段做模糊匹配（LIKE / full-text），返回结构与普通列表相同：

```bash
# 按用户名或邮箱模糊搜索
GET /users?q=john

# 支持与过滤、分页组合
GET /orders?q=2024-03&status=pending&offset=0&limit=20
```

#### 6.2.7 常用状态码

| 状态码 | 含义 | 使用场景 |
|--------|------|----------|
| 200 OK | 成功 | GET、PUT、PATCH |
| 201 Created | 已创建 | POST 创建资源 |
| 204 No Content | 无内容 | DELETE 成功 |
| 400 Bad Request | 请求格式错误 | JSON 解析失败 |
| 401 Unauthorized | 未认证 | 缺少或无效的 Token |
| 403 Forbidden | 未授权 | Token 有效但无权限 |
| 404 Not Found | 资源不存在 | 查询/修改不存在的资源 |
| 409 Conflict | 冲突 | 唯一键冲突 |
| 422 Unprocessable Entity | 校验失败 | 字段校验不通过 |
| 429 Too Many Requests | 限流 | 请求频率超限 |
| 500 Internal Server Error | 服务器错误 | 未预期的内部错误 |

### 6.3 中间件链

中间件执行顺序：

```
请求 → Recovery → CORS → Logging → RateLimit → Auth → Handler
响应 ← Recovery ← CORS ← Logging ← RateLimit ← Auth ← Handler
```

顺序原则：
- **Recovery** 最外层——捕获所有 panic
- **CORS** 在认证之前——OPTIONS 预检不应被认证拦截
- **Logging** 在业务逻辑之前——记录所有请求（包括被拒绝的）
- **RateLimit** 在认证之前——防止暴力破解
- **Auth** 最靠近 Handler——只保护需要认证的路由

### 6.4 错误码体系

**标准错误码**

| 错误码 | HTTP 状态码 | gRPC Code | 含义 |
|--------|:---:|-----------|------|
| invalid_json | 400 | InvalidArgument | 请求体 JSON 格式错误 |
| validation_failed | 422 | InvalidArgument | 字段校验失败 |
| unauthorized | 401 | Unauthenticated | 未认证 |
| forbidden | 403 | PermissionDenied | 已认证但无权限 |
| not_found | 404 | NotFound | 资源不存在 |
| conflict | 409 | AlreadyExists | 资源冲突 |
| rate_limited | 429 | ResourceExhausted | 请求频率超限 |
| internal_error | 500 | Internal | 内部错误 |

**AppError 实现**

```go
type AppError struct {
    Code     ErrCode `json:"code"`
    Message  string  `json:"message"`
    Detail   string  `json:"detail,omitempty"`
    internal error   // 不序列化，仅用于日志
}
```

关键设计：Code 是机器可读的字符串码，Message 是面向用户的友好消息，internal 不序列化仅存在于服务端日志。

### 6.5 请求校验框架

**系统边界校验原则**：在系统边界校验所有输入，信任内部代码。

- **系统边界**：HTTP handler、gRPC 服务入口、消息队列消费者
- **内部代码**：服务层、领域层——由调用方保证参数合法性

**Struct Tag + 反射实现**

```go
type CreateUserRequest struct {
    Name  string `json:"name"  validate:"required,min=2,max=50"`
    Email string `json:"email" validate:"required,email"`
    Age   int    `json:"age"   validate:"min=0,max=150"`
}

errs := Validate(req)
if len(errs) > 0 {
    WriteValidationError(w, errs)
    return
}
```

| 规则 | 示例 | 说明 |
|------|------|------|
| required | `validate:"required"` | 非零值 |
| email | `validate:"email"` | 合法邮箱格式 |
| min=N | `validate:"min=2"` | 字符串最小长度/数字最小值 |
| max=N | `validate:"max=50"` | 字符串最大长度/数字最大值 |

**校验 vs 业务规则**

| 类别 | 示例 | 处理位置 | HTTP 状态码 |
|------|------|----------|:---:|
| 格式校验 | "email 格式不合法" | Handler 层 | 422 |
| 业务规则 | "该邮箱已被注册" | Service 层 | 409 |

### 6.6 gRPC API 设计

**Proto 设计原则**

- 消息类型用单数：`User`，不是 `Users`
- 请求/响应成对：`CreateUserRequest` → `User`
- 列表接口返回专用响应：`ListUsersResponse` 包含分页信息
- ID 字段使用 string

**gRPC Status Code 映射**

```go
// 参数校验失败
return nil, status.Error(codes.InvalidArgument, "name is required")

// 资源不存在
return nil, status.Errorf(codes.NotFound, "user %q not found", id)

// 唯一键冲突
return nil, status.Errorf(codes.AlreadyExists, "email already registered")
```

**拦截器（Interceptor）**

```go
grpc.NewServer(
    grpc.ChainUnaryInterceptor(
        RecoveryInterceptor,   // 捕获 panic
        LoggingInterceptor,    // 记录请求日志
        AuthInterceptor(token), // 验证 token
    ),
)
```

**gRPC vs REST 选型**

| 维度 | REST | gRPC |
|------|------|------|
| 协议 | HTTP/1.1 (JSON) | HTTP/2 (Protobuf) |
| 性能 | 较低 | 较高（二进制、流式） |
| 浏览器支持 | 原生 | 需要 gRPC-Web |
| 适用场景 | 公开 API、前端 | 微服务内部通信 |

### 6.7 认证与授权

**Bearer Token 认证**

```
Authorization: Bearer <token>
```

**401 vs 403**

| 状态码 | 含义 | 场景 |
|--------|------|------|
| 401 Unauthorized | 未认证 | 没有 Token、Token 过期/无效 |
| 403 Forbidden | 已认证但无权限 | 普通用户访问管理员接口 |

关键区别：401 可以通过重新登录解决，403 即使重新登录也无权访问。

**限流策略**

- **固定窗口**：简单，但窗口边界有流量突增
- **滑动窗口**：更平滑，实现稍复杂
- **令牌桶**：`golang.org/x/time/rate`，生产推荐
- **分布式限流**：Redis + Lua 脚本

### 6.8 API 设计检查清单

发布每个 API 端点前逐一检查：

- [ ] 资源命名：复数名词、小写、无动词
- [ ] HTTP 方法：语义正确
- [ ] 状态码：精确匹配（201 创建、204 删除、422 校验失败）
- [ ] 错误格式：使用统一错误信息
- [ ] 分页：列表接口支持 page/limit
- [ ] 版本：URL 路径包含版本号
- [ ] 认证：受保护端点要求 Bearer Token
- [ ] 授权：正确区分 401/403
- [ ] 限流：配置限流并返回 429 + Retry-After
- [ ] 幂等性：POST 创建支持 Idempotency-Key
- [ ] CORS：跨域头部正确配置
- [ ] 输入校验：所有输入在系统边界校验
- [ ] 错误不泄漏：内部错误细节不暴露给客户端

---

## 7 Swagger 接口文档

团队统一使用 Swagger 作为 API 接口文档规范，自动生成而非手动编写。

### 7.1 安装

```bash
# 安装 swag CLI 工具（生成文档用）
go install github.com/swaggo/swag/cmd/swag@v1.16.4

# 验证安装
swag --version
# swag version v1.16.4

# 在项目中添加库依赖（不是 CLI 工具，使用 go get）
go get github.com/swaggo/fiber-swagger   # Fiber 框架适配
go get github.com/swaggo/files           # Swagger UI 静态资源
```

> **注意**：`fiber-swagger` 和 `files` 是被项目 import 的库，应通过 `go get` 加入 `go.mod`，
> 而不是 `go install`。Gin 项目则替换为 `github.com/swaggo/gin-swagger`。

### 7.2 在 handler 层添加 Swagger 注释

```go
// GetCountriesByCode godoc
//
// @Summary     List countries by code
// @Description Returns the list of countries associated with the provided country code.
// @Tags        country
// @Accept      json
// @Produce     json
// @Param       countryCode query string false "Country code to filter (optional)"
// @Success     200 {object} dto.APIBaseValueResp
// @Failure     500 {object} dto.APIBaseMessageResp
// @Router      /tcg-uss-ae/country [get]
func (h *Handler) GetCountriesByCode(c *fiber.Ctx) error {
    countryCode := c.Query("countryCode")
    res, err := h.svc.GetCountriesByCode(c.UserContext(), countryCode)
    if err != nil {
        return apperror.NewSimple(consts.ModuleCountry, code.DataNotFound,
            fmt.Sprintf("country not found by countryCode:%s", countryCode))
    }
    return c.JSON(res)
}
```

### 7.3 生成和使用

```bash
# 项目根目录下执行，在 docs/ 目录生成 swagger 文档
swag init

# 访问 swagger UI
# http://localhost:7001/swagger/index.html
```

---

## 文档维护

**复查周期**：季度复查（每季度末确认内容仍与工具链版本一致）

**必须更新的触发条件**：

| 触发事件 | 涉及章节 |
|----------|----------|
| Go 版本升级（修改 `go.mod`） | 1.1、1.2、2.3、2.5 |
| golangci-lint 版本升级 | 2.3、2.5、2.5 CI |
| 修改 Makefile 构建目标 | 1.4 |
| CI 流程变更（新增/删除 step） | 1.3、2.5 |
| API 返回格式或错误码体系变更 | 6.2.3、6.4 |
| 团队 Git 工作流变更 | 3.1、3.4、3.5 |
| 出现"按文档操作但失败"的反馈 | 对应章节 |

**文档所有者**：`team`（具体 owner 由各组 TL 指定）

---

## 术语表

| 术语 | 说明 |
|------|------|
| gofmt | Go 内置代码格式化工具 |
| goimports-reviser | import 语句分组排序工具 |
| golangci-lint | Go 静态代码分析聚合工具 |
| Conventional Commits | 结构化 commit message 约定 |
| GitHub Flow | 以 main 为唯一长期分支的极简工作流 |
| Squash and merge | 将 PR 所有 commit 压缩为一个后合并 |
| kebab-case | 脊柱命名法，全小写用 `-` 连接 |