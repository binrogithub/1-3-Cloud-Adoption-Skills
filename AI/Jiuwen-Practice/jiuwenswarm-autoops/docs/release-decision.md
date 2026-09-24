# JiuwenSwarm AutoOps 发布判定

当前判定：**NO_GO**。

判定必须由 `scripts/release-check.py` 针对一个明确的制品 manifest 生成。manifest 需要绑定源代码 commit、制品 SHA、非敏感配置 SHA、AO50/关键场景清单 SHA、环境清单、run/attempt 和证据文件 hash。不同制品的历史 PASS 不得拼接为当前 PASS。

## 判定命令

```bash
python3 scripts/release-check.py --stage rc \
  --manifest <candidate-manifest.json> \
  --evidence-root <evidence-root>

python3 scripts/release-check.py --stage ga \
  --manifest <candidate-manifest.json> \
  --evidence-root <evidence-root>
```

退出码 `0` 只表示指定阶段的证据门通过，退出码 `1` 表示 NO_GO，退出码 `2` 表示输入或 schema 错误。输出中的 `release_decision.tag_created` 始终为 `false`；脚本不会创建 tag、push 或发布。

RC 需要全部 P0 任务、当前制品的真实安装和业务证据。GA 还需要全部 P1、客户支持矩阵以及同一制品的 REL-07-01/02/03：部署模式必须是 `deployed`，观察至少 86400 秒，并包含事件、对账和恢复演练证据。

## 当前限制

工作区仍有未提交变更，且尚无绑定最终制品、完整 AO50 业务 evidence 和带事件的真实 24 小时证据。因此当前报告只能保留 NO_GO，不能将开发测试结果改写为 RC 或 GA。
