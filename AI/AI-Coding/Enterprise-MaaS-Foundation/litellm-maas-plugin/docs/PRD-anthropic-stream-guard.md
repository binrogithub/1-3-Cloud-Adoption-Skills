# PRD: anthropic_stream_guard — LiteLLM 流式 thinking 事件修复插件

日期: 2026-07-03
状态: 已评审(调研完成) → 待实现
方案: B(Claude Code 直连 LiteLLM :4000,多客户端架构)
形式约束: **LiteLLM 插件(custom callback),不修改 LiteLLM 源码**

## 1. 背景

生产链路: Claude Code(可能多实例)→ LiteLLM `:4000` `/v1/messages`(Anthropic 协议)→
`use_chat_completions_url_for_anthropic_messages: true` → OpenAI `/chat/completions` → GLM-5.2 (Huawei MaaS)。

GLM-5.2 无法关闭 reasoning 输出(实测 `enable_thinking:false` / `reasoning_effort:none` /
`thinking:{type:disabled}` 均无效),`reasoning_content` 恒定存在。LiteLLM 负责把
OpenAI 流 chunk 转回 Anthropic SSE 事件。

## 2. 问题(实测复现)

流式响应首个内容块事件序列违反 Anthropic 协议:

```
event: content_block_start
data: {"type":"content_block_start","index":0,"content_block":{"type":"text","text":""}}   ← 声明 text 块
event: content_block_delta
data: {"type":"content_block_delta","index":0,"delta":{"type":"thinking_delta","thinking":"..."}}  ← 塞 thinking 增量
```

协议要求 `thinking_delta` 只能出现在 `type:"thinking"` 的内容块中。

影响:
- Claude Code 短回复可容忍;effort=max 时思考量大,畸形流导致客户端解析失败/会话异常("high 能用、max 失败")。
- 附带风暴效应(已另行缓解): 失败累积触发 router cooldown → 单部署 30s 全局 429。

## 3. 根因(源码级)

`litellm/llms/anthropic/experimental_pass_through/adapters/streaming_iterator.py`
(v1.83.14-stable.patch.3):

- L106-112(sync `__next__`)与 L246-252(async `__anext__`): 第一个 chunk 到达时
  **无条件**发出 `content_block_start {"content_block":{"type":"text","text":""}}`,
  不检查首个 delta 的实际类型。
- L460 `_should_start_new_content_block`: 初始 `current_content_block_type="text"`,
  后续块切换逻辑正确;**仅首块类型被硬编码错误**。

## 4. 插件可行性(调研结论)

- `/v1/messages` 流式路径: `anthropic_endpoints/endpoints.py` →
  `base_process_llm_request(route_type="anthropic_messages")` →
  `async_sse_data_generator`(common_request_processing.py L1196-1215)→
  `proxy_logging_obj.async_post_call_streaming_iterator_hook`(L1767)→
  **遍历 `litellm.callbacks`,链式包裹响应迭代器**(proxy/utils.py L2264-2327)。
- 因此 CustomLogger 子类实现 `async_post_call_streaming_iterator_hook` 即可在
  **事件 dict 层**(序列化为 SSE 之前)重写流。零源码修改。
- 关键细节: utils.py L2295 用 `"async_post_call_streaming_iterator_hook" in type(callback).__dict__`
  判定 → **方法必须直接定义在插件类上**(不能靠继承)。
- chunk 形态: anthropic 路径 = 事件 dict(如 `{"type":"content_block_start",...}`);
  chat/completions 路径 = `ModelResponseStream` 对象 → 插件按类型甄别,只处理 dict 事件,
  其余透传,不影响 CCR/OpenAI 客户端。
- 插件装载(本主机已验证约束): 单文件 .py 挂载为 `/app/<module>.py`
  (LiteLLM `get_instance_fn` 按 config 同目录找 `<module>.py`,不支持包目录)。

## 5. 目标 / 非目标

目标:
1. 流式 `/v1/messages` 首个内容块类型与首个 delta 类型一致(thinking_delta → thinking 块)。
2. 修复对**所有**接入 LiteLLM 的 Claude Code 客户端生效(方案 B 多客户端架构的网关级修复)。
3. 任何异常下绝不中断/吞掉流(fail-open 透传)。

非目标:
- 不修改 LiteLLM 源码、不升级镜像。
- 不改变非 Anthropic 路径(/chat/completions 等)的任何行为。
- 不处理非流式响应(实测非流式 thinking 块类型正确)。

## 6. 方案设计

插件 `anthropic_stream_guard`(CustomLogger):

状态机(每个响应流独立):
```
buffer = None  # 暂存的 content_block_start 事件
for event in stream:
    非 dict 或非 anthropic 事件 → flush(buffer); yield event      # 透传
    event.type == content_block_start → flush(旧buffer); buffer = event  # 暂存,先不发
    event.type == content_block_delta 且 buffer 非空:
        delta.type ∈ {thinking_delta, signature_delta} 且 buffer 块型==text(且 text 为空)
            → buffer.content_block = {"type":"thinking","thinking":""}
        delta.type == text_delta 且 buffer 块型==thinking
            → buffer.content_block = {"type":"text","text":""}      # 对称保护
        yield buffer; buffer=None; yield event
    其它事件 → flush(buffer); yield event
流结束 → flush(buffer)
```

- `flush` = 原样 yield 暂存事件(未见 delta 就结束的空块,保持原样)。
- 整个 hook 包 try/except: 出错时先冲刷 buffer 再持续透传原始流。

## 7. 风险与缓解

| 风险 | 缓解 |
|---|---|
| hook 对全部流式路由生效 | 仅处理 `isinstance(chunk, dict)` 且 type ∈ Anthropic 事件集;其余透传 |
| 暂存 start 引入首字节延迟 | 仅延迟到下一事件(同一响应内相邻 SSE 事件,毫秒级) |
| 插件异常破坏流 | fail-open: except 后透传;绝不 raise |
| 与既有 callbacks 顺序耦合 | 本 hook 只在响应流侧,与 pre_call(EXA/图片/thinking-strip)正交 |
| 升级 LiteLLM 后上游修复 | 插件幂等: 块型已正确时不做任何改写,可长期共存 |

## 8. 测试计划(验收标准)

1. 单元级(容器外脚本): 流式 thinking 请求 → 断言首个 `content_block_start.content_block.type == "thinking"`,且 `thinking_delta` 只出现在 thinking 块内。
2. 事件序列合法性: start/stop 配对、index 单调、`text_delta` 仅在 text 块。
3. 回归: 非流式 200;纯文本流(无 thinking)不受影响;/chat/completions(master key)不受影响;EXA 搜索、图片注入正常。
4. 端到端: pty 驱动交互式 Claude Code,effort=high 与 effort=max 各跑多轮,0 解析错误、答案正确。
5. 负载面: 观察 litellm 日志无新增异常;Prometheus 无 5xx 上升。

## 9. 部署与回滚

- 部署: compose 挂载 `anthropic_stream_guard/callback.py:/app/anthropic_stream_guard.py:ro`;
  config `litellm_settings.callbacks` 追加 `anthropic_stream_guard.proxy_handler_instance`;重启容器。
- 回滚: 移除 callback 行 + 卷挂载,重启。配置均有 `.bak.<ts>` 备份。
