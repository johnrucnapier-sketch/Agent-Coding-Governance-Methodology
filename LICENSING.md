# Licensing — 双轨 / Dual-track

This repository is a hybrid of **methodology prose** and **mechanical code**, so it
uses two licenses. The `license` field in `.claude-plugin/plugin.json` is set to
`SEE LICENSING.md` and points here.

本仓是「方法论散文 + 机械代码」的混合体,故用双轨 license。`plugin.json` 的 `license`
字段为 `SEE LICENSING.md`,指向本文件。

## Path mapping / 路径归属

| Path / 路径 | License | File |
|---|---|---|
| `METHODOLOGY.md`, `METHODOLOGY.en.md` | CC-BY-4.0 | `LICENSE-DOCS` |
| `README.md` | CC-BY-4.0 | `LICENSE-DOCS` |
| `CONTRIBUTING.md` | CC-BY-4.0 | `LICENSE-DOCS` |
| `CASES.md` | CC-BY-4.0 | `LICENSE-DOCS` |
| `skills/**/SKILL.md` (prose body) | CC-BY-4.0 | `LICENSE-DOCS` |
| `LICENSING.md` | CC-BY-4.0 | `LICENSE-DOCS` |
| `scripts/**` | MIT | `LICENSE-CODE` |
| `hooks/**` | MIT | `LICENSE-CODE` |
| `templates/**` | MIT | `LICENSE-CODE` |
| `.claude-plugin/**` | MIT | `LICENSE-CODE` |

## Notes / 说明

- The YAML frontmatter of each `SKILL.md` (the machine-read `name`/`description`) is
  mechanical and falls under MIT; the human-readable prose body falls under CC-BY-4.0.
  In practice, attributing the repo as a whole satisfies both.
- "Take the methodology and adapt it to your project" is explicitly encouraged — both
  licenses permit modification and commercial use. CC-BY-4.0 only additionally asks
  for attribution.
- 把方法论拿去按你项目改,是明确鼓励的——两个 license 都允许修改和商用;CC-BY-4.0 只额外
  要求署名。
