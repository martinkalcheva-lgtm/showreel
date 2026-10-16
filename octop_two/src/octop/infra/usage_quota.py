"""Monthly per-user token quota alerts (secondary-development feature).

Purely additive: reads ``~/.octop/quotas.json`` (optional), runs an hourly
system cron job that aggregates month-to-date usage per user, and pushes a
``dashboard_push`` frame to the user's dashboard clients when usage crosses
the 80% (warning) or 100% (exceeded) threshold. Alerts are never blocking.

Expected ``quotas.json`` shape::

    {
      "default_monthly_tokens": 5000000,
      "users": { "1": 20000000 }
    }

Both keys are optional; absent file means "no quotas configured" and the
job becomes a no-op.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

QUOTA_JOB_ID = "usage-quota-alert"
QUOTAS_FILENAME = "quotas.json"
DEFAULT_MONTHLY_TOKENS = 1_000_000
WARN_RATIO = 0.8

AGENT_ID_QUOTA = "quota"
THREAD_ID_QUOTA = "quota-alert"

# user_id -> "warn" | "exceeded"; suppresses repeat alerts at the same level.
_last_alert_level: dict[int, str] = {}


def quotas_path() -> Path:
    return Path.home() / ".octop" / QUOTAS_FILENAME


def load_quota_config() -> dict[str, Any]:
    """Read ``~/.octop/quotas.json``; missing/invalid file → empty config."""
    path = quotas_path()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as exc:
        logger.warning("quota config unreadable at %s: %s", path, exc)
        return {}
    if not isinstance(raw, dict):
        return {}
    return raw


def save_quota_config(config: dict[str, Any]) -> dict[str, Any]:
    """Atomically persist ``~/.octop/quotas.json``; returns the saved dict."""
    path = quotas_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(QUOTAS_FILENAME + ".tmp")
    tmp.write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)
    return config


def quota_for(user_id: int, config: dict[str, Any]) -> int | None:
    """Resolve the monthly token limit for *user_id*; ``None`` = unlimited."""
    specific = (config.get("users") or {}).get(str(user_id))
    if specific is not None:
        try:
            return max(0, int(specific))
        except (TypeError, ValueError):
            logger.warning("invalid quota for user %s: %r", user_id, specific)
    default = config.get("default_monthly_tokens")
    if default is None:
        return None
    try:
        return max(0, int(default))
    except (TypeError, ValueError):
        logger.warning("invalid default_monthly_tokens: %r", default)
        return None


def _month_key(timezone: str) -> str:
    now = datetime.now(ZoneInfo(timezone))
    return f"{now.year:04d}-{now.month:02d}"


month_key = _month_key  # public alias for router consumption


def _month_usage_by_user(server: Any, timezone: str) -> list[dict[str, Any]]:
    """``by_user`` buckets for the current calendar month (may be empty)."""
    result = server.services.usage_repo.summary(
        user_id=None,
        agent_id=None,
        window=f"month:{_month_key(timezone)}",
        granularity="by_user",
        timezone=timezone,
    )
    return list(result.get("buckets") or [])


def _alert_frame(text: str) -> dict[str, Any]:
    return {
        "type": "dashboard_push",
        "agent_id": AGENT_ID_QUOTA,
        "thread_id": THREAD_ID_QUOTA,
        "text": text,
    }


async def check_and_alert(server: Any) -> int:
    """One quota sweep; returns the number of alerts pushed this round."""
    config = load_quota_config()
    if not config:
        return 0
    timezone = str(
        getattr(getattr(server, "config", None), "default_timezone", None)
        or "UTC"
    )
    runtime = getattr(server, "app_runtime", None)
    if runtime is None:
        return 0
    pushed = 0
    for bucket in _month_usage_by_user(server, timezone):
        try:
            user_id = int(bucket.get("key", 0))
            total = int(bucket.get("total_tokens", 0) or 0)
        except (TypeError, ValueError):
            continue
        quota = quota_for(user_id, config)
        if quota is None or quota <= 0:
            continue
        ratio = total / quota
        level: str | None = None
        if ratio >= 1.0:
            level = "exceeded"
        elif ratio >= WARN_RATIO:
            level = "warn"
        if level is None:
            _last_alert_level.pop(user_id, None)
            continue
        if _last_alert_level.get(user_id) == level:
            continue
        percent = round(ratio * 100)
        if level == "exceeded":
            text = (
                f"[配额告警] 本月 Token 用量 {total:,} 已达预算 {quota:,} 的 "
                f"{percent}%，超出预算。"
            )
        else:
            text = (
                f"[配额提醒] 本月 Token 用量 {total:,} 已达预算 {quota:,} 的 "
                f"{percent}%，请注意控制消耗。"
            )
        _last_alert_level[user_id] = level
        try:
            await runtime.gateway.ws_hub.push_to_user(user_id, _alert_frame(text))
            pushed += 1
        except Exception:
            logger.exception("quota alert push failed for user %s", user_id)
    return pushed


def install_quota_alert_job(cron_manager: Any, *, server: Any) -> None:
    """Register the hourly sweep as a process-level system cron job."""

    async def _sweep() -> None:
        try:
            count = await check_and_alert(server)
            if count:
                logger.info("quota alert: pushed %d alert(s)", count)
        except Exception:
            logger.exception("quota alert sweep failed")

    cron_manager.schedule_system_job(
        QUOTA_JOB_ID,
        trigger="cron:0 * * * *",
        func=_sweep,
    )
    logger.info("quota alert job installed (hourly, config=%s)", quotas_path())


__all__ = [
    "QUOTA_JOB_ID",
    "check_and_alert",
    "install_quota_alert_job",
    "load_quota_config",
    "month_key",
    "quota_for",
    "quotas_path",
    "save_quota_config",
]
