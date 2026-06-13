# LiteLLM source patches

`proxy_server.py` and `utils.py` are **patched copies** of the corresponding
files from the pinned image `ghcr.io/berriai/litellm:v1.83.14-stable.patch.3`.
`docker-compose.yml` mounts them read-only over both the editable
(`/app/litellm/proxy/...`) and the site-packages
(`/app/.venv/lib/python3.13/site-packages/litellm/proxy/...`) copies, so the
running proxy uses the patched behavior without rebuilding the image.

## What the patches change

Both changes make the **Responses API streaming path** tolerate the
non-streaming response objects Huawei MaaS / Anthropic-style clients produce.

### `proxy_server.py` — `async_data_generator`
- If the upstream `response` is **not** an async iterator (a single
  `ResponsesAPIResponse`-like object), wrap it in a synthetic async iterator
  that emits `response.output_item.added` events per output item followed by a
  `response.completed` event — so SSE clients still receive a valid stream.
- Serialize `dict` chunks with `json.dumps(..., ensure_ascii=False)` so CJK /
  non-ASCII content is not escaped.

### `utils.py` — async chunk wrapper
- `await` the generator if it is a coroutine, and if the result is not an async
  iterator, yield it once and return (instead of raising on `async for`).

## Refreshing against a new image tag

When bumping the `litellm` image, re-derive the patches so they apply cleanly:

```bash
IMG=ghcr.io/berriai/litellm:<new-tag>
docker run --rm --entrypoint cat "$IMG" /app/litellm/proxy/proxy_server.py > /tmp/stock_proxy_server.py
docker run --rm --entrypoint cat "$IMG" /app/litellm/proxy/utils.py        > /tmp/stock_utils.py
# Re-apply the two changes above on top of the stock files, then replace
# patches/proxy_server.py and patches/utils.py. Verify:
diff /tmp/stock_proxy_server.py patches/proxy_server.py   # should show only the two hunks
diff /tmp/stock_utils.py        patches/utils.py          # should show only the one hunk
```

Also update the Python minor version in the site-packages mount path in
`docker-compose.yml` if the new image changes it (currently `python3.13`).
