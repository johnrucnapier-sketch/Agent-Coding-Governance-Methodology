# PUBLISHING — 新手级发布 runbook

> 给从没在 GitHub 发布过东西的人。照着做就行。
> 全程**只需一个个人 GitHub 账号**。**你不需要任何企业/组织(Organization)认证**——
> 那套更复杂、和开源一个个人项目无关,**全部跳过**。

> 诚实声明(方法论 §5/§7):**第 1 步和第 3 步只有你本人能做**——注册账号是你的身份,
> `gh auth login` 是把你的身份授权给本机。agent **不能也不应**替你做这两步;这不是
> 能力缺陷,是边界。其余步骤 agent 可在对话里实时带你做或替你执行。

---

## 第 1 步 ·【仅你本人】注册个人 GitHub 账号

1. 打开 https://github.com/signup
2. 用邮箱注册,设用户名(这个用户名很重要,后面到处要用,记下来)。
3. 验证邮箱。完成。
4. **不要**创建/加入任何 Organization、不要做企业认证、不要建 Team。个人号就够。

> 记下你的用户名,下文写作 `<你的用户名>`。

## 第 2 步 · 安装 GitHub CLI(`gh`)

macOS:

```bash
brew install gh
```

验证:

```bash
gh --version
```

看到版本号即可。(没装 Homebrew 就先 https://brew.sh 一行命令装 brew。)

## 第 3 步 ·【仅你本人】认证 `gh`

```bash
gh auth login
```

交互里依次选:

1. `GitHub.com`(回车)
2. `HTTPS`(回车)
3. `Authenticate Git with your GitHub credentials?` → `Yes`
4. `Login with a web browser`(回车)→ 终端显示一个 **one-time code**(像 `ABCD-1234`)
5. 终端按回车会自动打开浏览器;在浏览器里粘贴那个 code → 点 **Authorize**
6. 回到终端,显示 `✓ Logged in as <你的用户名>` 即成功

验证:

```bash
gh auth status
```

显示 `Logged in to github.com as <你的用户名>` 即可。

## 第 4 步 · 填占位(把 TODO 换成你的用户名)

仓库里有几处发布期占位:`TODO_OWNER`、`TODO_AUTHOR_HANDLE`。
先看它们在哪:

```bash
cd "/Users/mac/Claude Code项目治理方法论"
grep -rl 'TODO_OWNER\|TODO_AUTHOR_HANDLE' . --exclude-dir=.git --exclude-dir=docs
```

预期命中:`.claude-plugin/plugin.json`、`.claude-plugin/marketplace.json`、
`LICENSE-CODE`、`LICENSE-DOCS`(以及 `PUBLISHING.md` 本身——它就是在教你替换,会自己
命中关键词,属正常,不用改它)。

把这两个文件里的 `TODO_OWNER` 和 `TODO_AUTHOR_HANDLE` 都改成 `<你的用户名>`。
让 agent 替你批量替换最省事(这步 agent 可以做),或手动逐个改。改完再 grep 一次
(下面命令排除 PUBLISHING.md 自身),应无残留:

```bash
grep -rl 'TODO_OWNER\|TODO_AUTHOR_HANDLE' . --exclude-dir=.git --exclude-dir=docs --exclude=PUBLISHING.md || echo "ALL-FILLED-OK"
```

## 第 5 步 · 创建公开仓库并推送(一条命令)

确认在仓库目录:

```bash
cd "/Users/mac/Claude Code项目治理方法论"
gh repo create Agent-Coding-Governance-Methodology --public --source=. --remote=origin --push
```

这条会:在你账号下建一个名为 `Agent-Coding-Governance-Methodology` 的**公开**仓、
把本地 commit 推上去。完成后命令会打印仓库 URL。

> ⚠️ 这是不可透明回滚的**公开**动作:仓库内容会被公开、可能被缓存/索引。本仓已设计为
> 零业务内容,但推之前你可以最后 `git status` + 扫一眼确认没夹带私货。

## 第 6 步 · 让别人能装这个 plugin

在 README 里你已经写了安装方式。提醒使用者:**确切的 Claude Code plugin /
marketplace 安装命令以当前官方文档为准**(CC 命令可能随版本变化)。当前形态大致是
`/plugin marketplace add <你的用户名>/Agent-Coding-Governance-Methodology`,以官方
文档为准。

---

## 出问题了?

- `gh: command not found` → 第 2 步没成功,重装 `gh`。
- `gh auth login` 浏览器没弹 → 手动打开终端给的那个 URL,贴 code。
- `repo create` 报 name 已存在 → 换个仓名,或先去网页删掉旧的同名空仓。
- 不确定要不要公开 → 先 `--private` 代替 `--public` 建私有仓,确认无误后再到仓库
  Settings 改 public。

> 需要的话,把 agent 拉进一个新对话,说"带我做 GitHub 发布",它会按本文件一步步陪你走。
> 它仍然不能替你做第 1、3 步,但会在旁边逐步给你确切指令。
