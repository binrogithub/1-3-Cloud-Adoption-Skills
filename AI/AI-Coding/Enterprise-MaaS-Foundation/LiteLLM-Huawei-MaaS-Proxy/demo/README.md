# LiteLLM 三层滚动预算 Demo（OpenCode Go 风格）

1:1 复刻 OpenCode Go 的三层额度语义（**滚动窗口**，非整点重置），
直接集成在本 LiteLLM-Huawei-MaaS-Proxy 栈上：

| 层级 | OpenCode Go 生产值 | Demo 缩放值（当前生效） |
|------|-------------------|------------------------|
| key（会话） | 5 小时 / $12 | 5 分钟 / $0.05 |
| user（周）  | 7 天 / $30   | 15 分钟 / $0.12 |
| team（月）  | 30 天 / $60  | 30 分钟 / $0.25 |

## 实现组成

- `assets/config/rolling_budget_hook.py` —— pre-call hook，每次请求前对
  `LiteLLM_SpendLogs` 表做三个滑动窗口 SUM 查询（复用 proxy 内置 Prisma 连接，
  零额外依赖），任一层超限返回 429；旧消费滑出窗口后额度自动恢复；
- `litellm_config.yaml` —— 注册回调、`demo-model`（mock 模型，约 $0.01/次账面
  消费，不打真实上游）、`proxy_batch_write_at: 1`；
- `docker-compose.yml` —— 挂载 hook + `BUDGET_TIER_*` 三个环境变量。

## 演示步骤

```bash
cd <stack-root>                  # 本 skill 目录（docker-compose.yml 所在处）
docker compose up -d litellm     # 应用配置（重建 litellm 容器，约 30 秒）
./demo/setup.py                  # 建 team/user/key（一次即可），key 存 demo/.demo_key
./demo/demo.py                   # 开始演示
```

时间线：

1. **第一幕**（约 10 秒）：mock 模型每次请求约 $0.01，第 6 个请求触发 429，
   错误体写明 `最近5分钟内已消费 $0.05（限额 $0.05）`；
2. **第二幕**（约 4–5 分钟）：脚本每 15 秒重试，最早那笔消费滑出 5 分钟窗口的
   瞬间恢复 200 —— 现场讲解"这是滑动窗口，不是到点清零"。

## 给客户看的辅助画面

- LiteLLM Admin UI：<http://localhost:4000/ui>，按 key/user/team 的消费看板；
- Grafana：<http://localhost:3000>（本栈已带 Prometheus 指标）；
- 现场审计（证明额度算自真实账单数据）：

  ```bash
  docker exec litellm_pg_db psql -U llmproxy -d litellm -c \
    "SELECT COUNT(*) AS requests, ROUND(SUM(spend)::numeric, 4) AS spent_usd
     FROM \"LiteLLM_SpendLogs\"
     WHERE \"startTime\" > NOW() - interval '5 minutes';"
  ```

## 切换到生产值

在栈根目录的 `.env` 里加（然后 `docker compose up -d litellm`）：

```bash
BUDGET_TIER_KEY=5h:12
BUDGET_TIER_USER=7d:30
BUDGET_TIER_TEAM=30d:60
```

生产建议：给 SpendLogs 建 `(api_key, "startTime")`、`("user", "startTime")`、
`(team_id, "startTime")` 索引；高 QPS 下在 hook 里加 Redis 短 TTL 缓存；
按需把 hook 的 fail-open（DB 故障放行）改成 fail-closed；
`proxy_batch_write_at` 可改回 10（生产窗口是小时/天级，1–10 秒滞后无感）。

## 注意事项

- spend log 异步落库，预算判定有 1–2 秒滞后，突发并发可能略微超限
  （商业产品同样是近实时判定）；
- `setup.py` 重复运行会创建新的 team/key，demo 期间运行一次即可；
- 重新演示：直接再跑 `./demo/demo.py`（窗口内仍有消费会更快触发 429）。
