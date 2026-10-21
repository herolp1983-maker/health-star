# GitHub 自动交付配置

目标仓库为私有的 [herolp1983-maker/codex](https://github.com/herolp1983-maker/codex)。`main` 的首次 README 基线是 `793bef7565415150397eb2c419c730c695119001`。用户选择免费、无需手动合并的交付方式，具体条件见 [AUTONOMOUS.md](AUTONOMOUS.md)。

2026-10-20 在 GitHub 设置页面核实：当前私有仓库的 Rulesets 和经典分支保护都提示不会生效，原生 Auto-merge 开关不可用，Squash 合并可用。因此 `engineering/project.json` 选择 `agent-verified`。Codex 检查独立审核、本地测试、五个真实 GitHub Actions Job、PR 当前 head 与 base 后，通过 GitHub API 指定 `expected_head_sha` 自动 Squash。缺失、失败或过期的证据不能合并。

这种方式只约束 Codex 的交付操作。GitHub 服务器当前不会阻止其他有写权限的人绕过 PR 或检查直接修改 `main`。未来若账户具有可生效的分支规则，可验证 Require PR、五个 Actions required checks、最新分支条件及无 bypass 后，再改成 `server-enforced`；不得只凭保存了规则就宣称它生效。

CI 超过八分钟时，只有实际 PR 存在才创建本聊天的定期续查；最多持续 24 小时，并沿用同一份两轮修复台账。不要购买套餐、公开仓库或要求用户手工点 Merge。
