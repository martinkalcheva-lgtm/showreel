"""Reject agent turns when the acting user exhausts their monthly token budget.

Secondary-development feature (additive): month-to-date usage is compared
against the per-user monthly quota from ``~/.octop/quotas.json`` (see
``octop.infra.usage_quota``). Admins are always exempt. The check resets
naturally at the start of each month because the usage window is
``month:YYYY-MM``.

Error payload mirrors the native ``TOKEN_QUOTA_EXCEEDED`` shape so the
frontend error card renders identically.
"""

from __future__ import annotations

from typing import Any

from langchain.agents.middleware import AgentMiddleware

from octop.infra.agents.middleware.token_quota import configurable_user_id
from octop.infra.errors import ErrorCode, OctopError
from octop.infra.usage_quota import load_quota_config, month_key, quota_for


class MonthlyQuotaMiddleware(AgentMiddleware[Any, Any]):
    """Hard-stop the acting user once this month's token budget is spent."""

    def __init__(
        self,
        *,
        usage_repo: Any,
        user_repo: Any,
        timezone: str = "UTC",
    ) -> None:
        super().__init__()
        self._usage = usage_repo
        self._users = user_repo
        self._timezone = timezone

    def _enforce(self) -> None:
        user_id = configurable_user_id()
        if user_id is None:
            return
        user = self._users.get(user_id)
        if user is None or str(getattr(user, "role", "")) == "admin":
            return  # admins are never blocked by the monthly budget
        quota = quota_for(user_id, load_quota_config())
        if quota is None or quota <= 0:
            return
        used = int(
            (
                self._usage.summary(
                    user_id=user_id,
                    agent_id=None,
                    window=f"month:{month_key(self._timezone)}",
                    granularity="total",
                    timezone=self._timezone,
                ).get("totals")
                or {}
            ).get("total_tokens", 0)
        )
        if used >= quota:
            raise OctopError(
                ErrorCode.MONTHLY_QUOTA_EXCEEDED,
                "monthly token quota exceeded",
                details={"used": used, "quota": quota},
            )

    def before_agent(self, state: Any, runtime: Any) -> None:
        del state, runtime
        self._enforce()

    async def abefore_agent(self, state: Any, runtime: Any) -> None:
        del state, runtime
        self._enforce()


__all__ = ["MonthlyQuotaMiddleware"]
