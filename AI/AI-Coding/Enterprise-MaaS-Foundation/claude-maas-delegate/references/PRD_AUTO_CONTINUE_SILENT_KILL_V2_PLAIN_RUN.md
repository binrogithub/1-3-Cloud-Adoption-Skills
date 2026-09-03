# PRD：auto_continue 静默杀死探测 v2 —— 补上 `_plain_run` 的覆盖盲区

> 状态：Ready for approval
> 涉及组件：`claude-maas-delegate` skill（`scripts/delegate`）
> 前置：`PRD_AUTO_CONTINUE_SILENT_KILL_V1.md`（已实施，PR #159）
> 文档日期：2026-09-04
> 优先级：P1（v1 修复本身有效，但没覆盖到最常见的调用路径）

## 0. 结论

v1（PR #159）给 `run_with_auto_continue`（`_supervised_run` 走的那条路）
加了 `detect_silent_kill`，验收时用的是"重试"场景测的，全过。但合入之后
第一次在**全新会话**（不是 retry）上跑真实任务时，`needs_escalation` 的
摘要又变回了 v1 想根治的那条无关诊断文本——v1 的修复完全没生效。

**根因**：`scripts/delegate` 的 `run()` 函数里有这段判断（约第 442 行）：

```python
if (claude_session_id is None or supervisor is None
        or not supervisor.auto_continue_enabled()):
    return _plain_run(...)
```

`maas-delegate run` 对一个**全新的 conversation-id**（第一次调用，尚未
`bind_session`）传进来的 `claude_session_id` 就是 `None`——`session_registry`
只在成功之后才把真实 session id 绑定到 handle 上。也就是说：**每一个全新
任务的第一次尝试，走的都是 `_plain_run`，不是 `_supervised_run`。**
`detect_silent_kill` 只接在 `_supervised_run` 里，`_plain_run` 完全没有
静默杀死探测——v1 覆盖的其实是"重试"这个相对少见的情形，而"第一次跑就
被杀"这个最常见的情形，v1 一次没碰。

## 1. 为什么这次能修得很小

`_plain_run` 不像 `_supervised_run` 那样自己管理一个已知的 `session_id`
（`_supervised_run`/`run_with_auto_continue` 在发起请求前就生成好了 UUID，
用 `--session-id` 传给 claude）。`_plain_run` 在 `claude_session_id is None`
时完全不传 `--session-id`/`--resume`，由 claude 自己随机生成一个——调用方
事后才知道是哪个。

但实测确认：**claude 的 `stream-json` 输出里，不只是终态 `result` 帧带
`session_id`，第一条 `type: "system", subtype: "init"` 帧、以及此后每一条
`assistant` 帧，都带着同一个 `session_id`。** 而 `_parse_stream_json`
（`scripts/delegate:280`）现在只在 `obj.get("type") == "result"` 这个分支
里读 `session_id`——会话被杀掉、从没走到终态帧时，这个字段自然也拿不到。

所以真正要改的只有两处：

1. `_parse_stream_json` 放宽 session_id 的抓取——不只认终态 `result` 帧，
   任何带 `session_id` 字段的帧都记（取先出现的那个，同一会话里都一样）。
2. `_plain_run` 在 `not parsed["ok"]` 时，用这个（现在总能拿到的）
   `session_id`，走跟 `_supervised_run` 一样的 `find_session_jsonl` +
   `detect_silent_kill` 探测，把结果塞进返回字典的 `supervisor_outcome`/
   `silent_kill_info` 两个键。

`run()` 里组装最终摘要的那段代码（v1 已经加好的、判断
`last_res.get("supervisor_outcome") == "silent_kill"` 的分支）**完全不用
改**——它认的是这两个键，不关心是谁写进去的，`_plain_run` 只要照
`_supervised_run` 的样子填这两个键，摘要逻辑自动生效。

## 2. 方案

### 2.1 `_parse_stream_json`（`scripts/delegate:280`）

现有逻辑：

```python
if isinstance(obj, dict) and obj.get("type") == "result":
    found_terminal = True
    subtype = obj.get("subtype")
    is_error = obj.get("is_error")
    session_id = obj.get("session_id")
    ...
```

改为：任何帧只要带 `session_id` 字段就记录（`session_id = session_id or
obj.get("session_id")`，放在循环体最前面、`type=="result"` 判断之外），
`found_terminal`/`subtype`/`is_error` 仍然只在 `type=="result"` 时更新——
这三个字段的语义不变，只放宽 session_id 的来源。

### 2.2 `_plain_run`（`scripts/delegate:475`）

在现有的：

```python
parsed = _parse_stream_json(proc.stdout or "", exit_code=proc.returncode)
return { "ok": parsed["ok"], ... "session_id": parsed["session_id"] }
```

之前插入静默杀死探测——只在 `not parsed["ok"]` 且能拿到 session_id 时才做，
成功路径不受影响：

```python
supervisor_outcome = None
silent_kill_info = None
if not parsed["ok"] and parsed["session_id"]:
    supervisor = _load_supervisor()  # 已有的懒加载函数，scripts/delegate:528
    if supervisor is not None:
        cfg_dir = Path(os.environ.get("CLAUDE_CONFIG_DIR")
                       or (Path(os.environ.get("HOME", str(Path.home())))
                           / ".claude-maas"))
        session_jsonl = supervisor.find_session_jsonl(cfg_dir,
                                                       parsed["session_id"])
        if session_jsonl is not None:
            sk_info = supervisor.detect_silent_kill(session_jsonl)
            if sk_info is not None:
                supervisor_outcome = "silent_kill"
                silent_kill_info = sk_info
```

返回字典追加 `"supervisor_outcome": supervisor_outcome,
"silent_kill_info": silent_kill_info`——跟 `_supervised_run` 现有返回字典
的两个键同名同形状，`run()` 里的摘要分支不用动。

## 3. 不变式（延续 v1）

- 不新增自动重试——`_plain_run` 判定 `silent_kill` 后跟今天一样返回
  `ok: False`，重试与否仍由 `run()` 外层的既有重试预算逻辑决定，不因为
  多了这个分类而改变次数。
- 不影响成功路径——探测只在 `not parsed["ok"]` 时跑，多一次文件系统查找
  不影响成功任务的行为或性能。
- `_supervised_run` 的既有逻辑不动——这次只碰 `_parse_stream_json`（两条
  路径共用，放宽是安全的：`result` 帧原本就带 `session_id`，不会因为
  提前记录而丢失或改变）和 `_plain_run`。

## 4. 验收

- 单元测试：构造一个 `stream-json` 输出，只有 `system/init` 帧带
  `session_id`、从未出现 `result` 帧（模拟被杀），断言
  `_parse_stream_json` 现在能拿到 `session_id`（v1 之前的行为应该是
  `None`——测试要能证明这条从 RED 到 GREEN）。
- 单元测试：`_plain_run` 场景下，给一个不完整的 `stream-json` 输出 + 对应
  的 fixture session jsonl（结尾是 `attachment`/`last-prompt`，没有
  assistant 错误记录），断言返回字典里 `supervisor_outcome ==
  "silent_kill"` 且 `ok is False`。
- 回归：PR #159 的 `tests/test_silent_kill.py` 13 个用例全部保持通过——
  这次改动不改变 `_supervised_run`/`detect_silent_kill`/`run_with_auto_continue`
  本身的判定逻辑。
- 成功路径不受影响：一个正常成功的 `_plain_run` 场景（有 `result` 帧、
  `is_error: false`）测试其 `ok is True` 且不携带
  `supervisor_outcome`/`silent_kill_info`（或为 `None`），确认新代码没有
  误伤成功路径。

## 5. 回滚

只改了 `_parse_stream_json` 一处放宽（无害，`result` 帧原本就有这个字段）
和 `_plain_run` 一段新增的探测（`not parsed["ok"]` 时才跑，纯增量）。删掉
这段新增代码即可完全回退到 v1 的状态。
