"""
LiteLLM Proxy 滚动窗口（rolling window）预算 hook。

1:1 复刻 OpenCode Go 的三层额度语义：任意时刻往回看 N 时间内的累计消费，
超过限额则拒绝请求（429）；旧消费滑出窗口后额度自动恢复，没有"整点重置"。

三层额度通过环境变量配置，格式 "<数字><s|m|h|d>:<美元>"：
  BUDGET_TIER_KEY   按 virtual key 维度   （OpenCode: 5h:12）
  BUDGET_TIER_USER  按 user 维度          （OpenCode: 7d:30）
  BUDGET_TIER_TEAM  按 team 维度          （OpenCode: 30d:60）

数据来源是 LiteLLM 自带的 LiteLLM_SpendLogs 表（每笔请求的真实账单记录），
因此额度计算可审计。查询复用 proxy 内置的 Prisma 连接，无需额外依赖。
生产环境建议建索引：
  CREATE INDEX ON "LiteLLM_SpendLogs" (api_key, "startTime");
  CREATE INDEX ON "LiteLLM_SpendLogs" ("user", "startTime");
  CREATE INDEX ON "LiteLLM_SpendLogs" (team_id, "startTime");
"""

import os
import re

from fastapi import HTTPException
from litellm._logging import verbose_proxy_logger
from litellm.integrations.custom_logger import CustomLogger

_UNIT_SECONDS = {"s": 1, "m": 60, "h": 3600, "d": 86400}
_UNIT_LABEL_ZH = {"s": "秒", "m": "分钟", "h": "小时", "d": "天"}
_UNIT_LABEL_EN = {"s": "second", "m": "minute", "h": "hour", "d": "day"}


def _parse_tier(spec: str):
    """'5h:12' -> (18000, 12.0, '5小时', '5 hours')"""
    m = re.fullmatch(r"\s*(\d+)([smhd]):(\d+(?:\.\d+)?)\s*", spec)
    if not m:
        raise ValueError(
            f"Bad budget tier spec {spec!r}, expected like '5h:12' or '5m:0.05'"
        )
    n, unit, limit = int(m.group(1)), m.group(2), float(m.group(3))
    label_zh = f"{n}{_UNIT_LABEL_ZH[unit]}"
    label_en = f"{n} {_UNIT_LABEL_EN[unit]}{'s' if n > 1 else ''}"
    return n * _UNIT_SECONDS[unit], limit, label_zh, label_en


# (SpendLogs 列名, 窗口秒数, 限额美元, 窗口中文名, 窗口英文名, 层级名)
TIERS = []
for env_var, column, tier_name, default in [
    ("BUDGET_TIER_KEY", "api_key", "key", "5h:12"),
    ("BUDGET_TIER_USER", "user", "user", "7d:30"),
    ("BUDGET_TIER_TEAM", "team_id", "team", "30d:60"),
]:
    window_s, limit_usd, label_zh, label_en = _parse_tier(os.getenv(env_var, default))
    TIERS.append((column, window_s, limit_usd, label_zh, label_en, tier_name))


# 逗号分隔的 key alias 白名单；为空时对所有 key 生效（原始行为）
_ENFORCED_ALIASES = {
    a.strip()
    for a in os.getenv("BUDGET_LIMIT_KEY_ALIASES", "").split(",")
    if a.strip()
}


class RollingBudgetHook(CustomLogger):
    async def async_pre_call_hook(self, user_api_key_dict, cache, data, call_type):
        # 如果设置了白名单，只对白名单内的 key alias 执行预算检查
        if _ENFORCED_ALIASES:
            alias = getattr(user_api_key_dict, "key_alias", None) or ""
            if alias not in _ENFORCED_ALIASES:
                return data

        # 延迟导入：prisma_client 在 proxy 启动完成后才初始化
        from litellm.proxy import proxy_server

        identifiers = {
            "api_key": user_api_key_dict.token,  # SpendLogs 存的是哈希后的 key，token 即哈希值
            "user": user_api_key_dict.user_id,
            "team_id": user_api_key_dict.team_id,
        }
        try:
            if proxy_server.prisma_client is None:
                verbose_proxy_logger.warning(
                    "rolling budget check skipped: prisma_client not ready"
                )
                return data
            for column, window_s, limit_usd, label_zh, label_en, tier_name in TIERS:
                ident = identifiers[column]
                if not ident:
                    # master key 等没有 user/team 归属的请求跳过该层
                    continue
                rows = await proxy_server.prisma_client.db.query_raw(
                    f'SELECT COALESCE(SUM(spend), 0)::float8 AS spent'
                    f' FROM "LiteLLM_SpendLogs"'
                    f' WHERE "{column}" = $1'
                    f'   AND "startTime" > NOW() - make_interval(secs => $2)',
                    ident,
                    float(window_s),
                )
                spent = float(rows[0]["spent"]) if rows else 0.0
                if spent >= limit_usd:
                    msg = (
                        f"Rolling budget exceeded for tier '{tier_name}': "
                        f"spent ${spent:.4f} in the last {label_en} "
                        f"(limit ${limit_usd}). "
                        f"Budget restores automatically as the oldest "
                        f"spend slides out of the window."
                    )
                    raise HTTPException(
                        status_code=400,
                        detail={
                            "error": "rolling_budget_exceeded",
                            "message": msg,
                            "tier": tier_name,
                            "window": label_en,
                            "limit_usd": limit_usd,
                            "spent_usd": round(spent, 6),
                        },
                    )
        except HTTPException:
            raise
        except Exception as e:
            # DB 暂不可用时放行（fail-open），避免预算检查变成全局单点故障；
            # 如需 fail-closed 改成 raise 即可
            verbose_proxy_logger.warning(f"rolling budget check skipped: {e}")
        return data


proxy_handler_instance = RollingBudgetHook()
