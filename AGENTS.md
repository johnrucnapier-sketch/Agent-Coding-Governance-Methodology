# ACGM agent entrypoint / Agent 入口

This repository contains ACGM itself. Read [INSTALL.md](INSTALL.md) before any
installation action. / 本仓库是 ACGM 产品源码；执行任何安装动作前先读
[INSTALL.md](INSTALL.md)。

## Authority boundary / 授权边界

- Clone, download, read, audit, explain, or test does **not** authorize installation.
  克隆、下载、阅读、审计、解释或测试，均不等于授权安装。
- Install, enable, set up, or activate ACGM is explicit installation intent. Repository
  development still does not authorize changing the host's Claude configuration.
  “安装、启用、配置或激活 ACGM”才是明确安装意图；开发本仓库也不自动授权修改宿主
  Claude 配置。
- Installing the plugin does not authorize `acgm init` in another project. Project
  bootstrap needs separate, explicit approval. / 安装插件不授权在其他项目执行 `acgm init`；
  项目初始化需要另一次明确授权。
- Never accept a workspace, marketplace, or plugin trust prompt for the user. Never
  bypass or suppress it. / 不代替用户接受 workspace、marketplace 或 plugin 信任提示，也
  不绕过或隐藏提示。

## Required behavior / 必须行为

1. Verify the repository root, branch/tag, worktree, and `git status` before acting.
   操作前核对仓库根目录、分支/tag、worktree 与 `git status`。
2. Route by verified capability and surface using `INSTALL.md`. The documented
   repository-plugin consent contract requires Claude Code `2.1.195+`; never guess an
   unknown target-app version as compatible. Do not infer the backing account,
   provider, or model from a displayed model name or gateway configuration.
   按 `INSTALL.md` 基于可验证能力和 surface 路由；文档采用的 repository-plugin 同意
   契约要求 Claude Code `2.1.195+`，目标 app 版本未知时不得猜测为兼容。不得从显示名称
   或 gateway 配置猜测实际账号、provider 或模型。
3. Treat download, declaration, installation, activation, and verification as distinct
   states. Report only the state actually proved. / 下载、声明、安装、激活与验证是不同状态；
   只能报告已经证明的状态。
4. On any marketplace, plugin, version, scope, source, or cache conflict, stop and show
   the evidence. The only automated replacement exception is a separately authorized
   `--upgrade-verified-snapshot` transaction from one unique, structurally and
   byte-verified older ACGM user-scope snapshot to this strictly newer version. It must
   prove data preservation and scoped `--keep-data` support, and no ACGM cache may be in
   use. Unknown, duplicate, project/local-scope, or legacy public-GitHub installs are
   never absorbed by that exception. / 遇到 marketplace、plugin、版本、scope、来源或
   缓存冲突时立即停止并展示证据。唯一可自动替换的例外，是用户另行授权
   `--upgrade-verified-snapshot`，把唯一、结构与字节均核验过的旧 ACGM user-scope
   snapshot 严格向前升级到本版本；它必须证明数据保护与带 scope 的 `--keep-data` 能力，
   且没有正在使用的 ACGM cache。未知、重复、project/local scope 或旧公开 GitHub 安装
   均不属于该例外。
5. Prefer the repository's read-only preflight and conservative installer. Do not edit
   Claude user settings directly. / 优先使用仓库的只读 preflight 与保守安装器；不得直接
   编辑 Claude 用户设置。
