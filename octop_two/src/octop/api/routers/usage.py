"""Token usage router — query the usage_log ledger.

  GET /api/usage/summary             → caller's own roll-up
  GET /api/usage/summary?as_user=N   → admin scope; another user's roll-up
  GET /api/usage/summary?agent_id=X  → scope to one agent (must be visible)
  GET /api/usage/export.xlsx         → Excel detail for the same scope
  GET /api/usage/quotas              → month-to-date usage vs. quota (own row;
                                       admins see all users)
  GET /api/admin/usage/summary       → global roll-up (admin only)
  GET /api/admin/usage/export.xlsx   → Excel detail (admin only)

Query params:
  window      = today | yesterday | last_7d | last_30d | all
                | day:YYYY-MM-DD | month:YYYY-MM
                | range:YYYY-MM-DD:YYYY-MM-DD   (default last_30d)
  granularity = total | by_day | by_agent | by_model | by_user   (default by_day)
"""

from __future__ import annotations

import re
from io import BytesIO
from typing import Any, cast

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from octop.api.common.content_disposition import content_disposition
from octop.api.common.usage_xlsx import build_usage_xlsx
from octop.api.deps import current_user, get_server
from octop.i18n import tr
from octop.infra.errors import ErrorCode, OctopError
from octop.infra.utils.locale import normalize_locale, resolve_request_locale

router = APIRouter()

_SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]+")
_XLSX_MEDIA = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_DAY_WINDOW_RE = re.compile(r"^day:(\d{4}-\d{2}-\d{2})$")
_MONTH_WINDOW_RE = re.compile(r"^month:(\d{4}-\d{2})$")
_RANGE_WINDOW_RE = re.compile(r"^range:(\d{4}-\d{2}-\d{2}):(\d{4}-\d{2}-\d{2})$")


def _resolve_user_scope(
    *,
    user: Any,
    as_user: int | None,
    server: Any,
) -> int:
    """Mirror of the agents router's ``?as_user=`` semantics: an admin
    may query another user's bucket; non-admins are pinned to their own
    id."""
    if as_user is None or as_user == user.id:
        return int(user.id)
    if not user.is_admin:
        raise OctopError(ErrorCode.FORBIDDEN, "as_user requires admin")
    target = server.user_manager.get_by_id(as_user)
    if target is None:
        raise OctopError(ErrorCode.NOT_FOUND, "user not found")
    return int(target.id)


def _server_timezone(server: Any) -> str:
    config = getattr(server, "config", None)
    tz = getattr(config, "default_timezone", None) if config is not None else None
    return str(tz or "UTC")


def _summary_or_raise(
    *,
    server: Any,
    user_id: int | None,
    agent_id: str | None,
    window: str,
    granularity: str,
) -> dict[str, Any]:
    try:
        result = cast(
            "dict[str, Any]",
            server.services.usage_repo.summary(
                user_id=user_id,
                agent_id=agent_id,
                window=window,
                granularity=granularity,
                timezone=_server_timezone(server),
            ),
        )
    except ValueError as exc:
        raise OctopError(ErrorCode.INTERNAL_ERROR, str(exc), status=400) from exc
    if granularity == "by_user":
        # Translate user_id buckets into human-readable usernames.
        usernames = _username_map(server)
        for bucket in result.get("buckets", []):
            uid = int(bucket.get("key", 0))
            bucket["label"] = usernames.get(uid) or f"user-{uid}"
    return result


def _assert_agent_exists(server: Any, agent_id: str | None) -> None:
    if agent_id is None:
        return
    assert server.app_runtime is not None
    if server.app_runtime.agent_registry.get_row(agent_id) is None:
        raise OctopError(ErrorCode.AGENT_NOT_FOUND, f"agent {agent_id!r} not found")


def _agent_name_map(server: Any) -> dict[str, str]:
    rows = server.services.agent_repo.list_all(include_disabled=True)
    return {str(row.agent_id): str(row.name or row.agent_id) for row in rows}


def _username_map(server: Any) -> dict[int, str]:
    out: dict[int, str] = {}
    users = server.user_manager.list_all(include_disabled=True)
    for user in users:
        uid = getattr(user, "id", None)
        if uid is None:
            continue
        name = getattr(user, "username", None) or getattr(user, "display_name", None) or ""
        out[int(uid)] = str(name)
    return out


def _export_filename(window: str, *, locale: str) -> str:
    """``{title}_{YYYY-MM-DD-YYYY-MM-DD}.xlsx`` (no ``range`` / preset labels)."""
    prefix = tr("usage_export.filename_prefix", normalize_locale(locale))
    range_match = _RANGE_WINDOW_RE.fullmatch(window)
    if range_match is not None:
        period = f"{range_match.group(1)}-{range_match.group(2)}"
    else:
        day_match = _DAY_WINDOW_RE.fullmatch(window)
        if day_match is not None:
            period = day_match.group(1)
        else:
            month_match = _MONTH_WINDOW_RE.fullmatch(window)
            if month_match is not None:
                period = month_match.group(1)
            else:
                period = _SAFE_FILENAME_RE.sub("_", window).strip("._") or "usage"
    return f"{prefix}_{period}.xlsx"


def _export_response(
    *,
    request: Request,
    server: Any,
    user_id: int | None,
    agent_id: str | None,
    window: str,
) -> StreamingResponse:
    timezone = _server_timezone(server)
    locale = resolve_request_locale(request)
    try:
        rows = server.services.usage_repo.list_detail(
            user_id=user_id,
            agent_id=agent_id,
            window=window,
            timezone=timezone,
        )
    except ValueError as exc:
        raise OctopError(ErrorCode.INTERNAL_ERROR, str(exc), status=400) from exc

    by_day = _summary_or_raise(
        server=server,
        user_id=user_id,
        agent_id=agent_id,
        window=window,
        granularity="by_day",
    )["buckets"]
    by_agent = _summary_or_raise(
        server=server,
        user_id=user_id,
        agent_id=agent_id,
        window=window,
        granularity="by_agent",
    )["buckets"]
    by_model = _summary_or_raise(
        server=server,
        user_id=user_id,
        agent_id=agent_id,
        window=window,
        granularity="by_model",
    )["buckets"]

    payload = build_usage_xlsx(
        rows=rows,
        by_day=by_day,
        by_agent=by_agent,
        by_model=by_model,
        agent_names=_agent_name_map(server),
        usernames=_username_map(server),
        timezone=timezone,
        locale=locale,
    )
    filename = _export_filename(window, locale=locale)
    return StreamingResponse(
        BytesIO(payload),
        media_type=_XLSX_MEDIA,
        headers={"Content-Disposition": content_disposition(filename)},
    )


@router.get("/usage/summary")
async def user_summary(
    window: str = "last_30d",
    granularity: str = "by_day",
    agent_id: str | None = None,
    as_user: int | None = None,
    user: Any = Depends(current_user),
    server: Any = Depends(get_server),
) -> dict[str, Any]:
    user_id = _resolve_user_scope(user=user, as_user=as_user, server=server)
    _assert_agent_exists(server, agent_id)
    return _summary_or_raise(
        server=server,
        user_id=user_id,
        agent_id=agent_id,
        window=window,
        granularity=granularity,
    )


@router.get(
    "/usage/export.xlsx",
    summary="Export usage_log detail as Excel",
    response_class=StreamingResponse,
)
async def user_export(
    request: Request,
    window: str = "last_30d",
    agent_id: str | None = None,
    as_user: int | None = None,
    user: Any = Depends(current_user),
    server: Any = Depends(get_server),
) -> StreamingResponse:
    user_id = _resolve_user_scope(user=user, as_user=as_user, server=server)
    _assert_agent_exists(server, agent_id)
    return _export_response(
        request=request,
        server=server,
        user_id=user_id,
        agent_id=agent_id,
        window=window,
    )


# --- quotas (secondary-dev, additive) -----------------------------------

@router.get("/usage/quotas")
async def usage_quotas(
    user: Any = Depends(current_user),
    server: Any = Depends(get_server),
) -> dict[str, Any]:
    """Month-to-date usage vs. per-user token quota.

    Admins see every user; regular users only see their own row.
    ``quota`` is ``null`` when no quota is configured for that user.
    """
    from octop.infra.usage_quota import (  # noqa: PLC0415
        load_quota_config,
        month_key,
        quota_for,
    )

    config = load_quota_config()
    timezone = _server_timezone(server)
    try:
        buckets = server.services.usage_repo.summary(
            user_id=None,
            agent_id=None,
            window=f"month:{month_key(timezone)}",
            granularity="by_user",
            timezone=timezone,
        ).get("buckets") or []
    except ValueError as exc:
        raise OctopError(ErrorCode.INTERNAL_ERROR, str(exc), status=400) from exc
    usage_by_id = {
        int(b.get("key", 0)): int(b.get("total_tokens", 0) or 0) for b in buckets
    }
    usernames = _username_map(server)
    users_out: list[dict[str, Any]] = []
    for uid, name in sorted(usernames.items()):
        if not user.is_admin and uid != int(user.id):
            continue
        quota = quota_for(uid, config)
        total = usage_by_id.get(uid, 0)
        percent = round(total / quota * 100) if quota else None
        level = None
        if quota and percent is not None:
            if percent >= 100:
                level = "exceeded"
            elif percent >= 80:
                level = "warn"
        users_out.append(
            {
                "user_id": uid,
                "username": name,
                "total_tokens": total,
                "quota": quota,
                "percent": percent,
                "level": level,
            }
        )
    return {
        "month": month_key(timezone),
        "quotas_configured": bool(config),
        "users": users_out,
    }


class QuotaConfigBody(BaseModel):
    default_monthly_tokens: int | None = Field(default=None, ge=0)


@router.get("/usage/quotas/config")
async def usage_quotas_config_get(
    user: Any = Depends(current_user),
) -> dict[str, Any]:
    """Current default monthly token budget plus an edit-permission flag."""
    from octop.infra.usage_quota import (  # noqa: PLC0415
        DEFAULT_MONTHLY_TOKENS,
        load_quota_config,
    )

    raw = load_quota_config().get("default_monthly_tokens")
    return {
        "default_monthly_tokens": (
            raw if isinstance(raw, int) and raw >= 0 else None
        ),
        "fallback_default": DEFAULT_MONTHLY_TOKENS,
        "can_edit": bool(user.is_admin),
    }


@router.put("/usage/quotas/config")
async def usage_quotas_config_put(
    body: QuotaConfigBody,
    user: Any = Depends(current_user),
) -> dict[str, Any]:
    """Admin-only: set or clear the default monthly token budget."""
    if not user.is_admin:
        raise OctopError(ErrorCode.FORBIDDEN, "admin required")
    from octop.infra.usage_quota import (  # noqa: PLC0415
        load_quota_config,
        save_quota_config,
    )

    config = load_quota_config()
    if body.default_monthly_tokens is None:
        config.pop("default_monthly_tokens", None)
    else:
        config["default_monthly_tokens"] = int(body.default_monthly_tokens)
    save_quota_config(config)
    return {
        "default_monthly_tokens": config.get("default_monthly_tokens"),
        "configured": bool(config),
    }


# --- admin --------------------------------------------------------------

admin_router = APIRouter()


@admin_router.get("/usage/summary")
async def admin_summary(
    window: str = "last_30d",
    granularity: str = "by_day",
    user_id: int | None = None,
    agent_id: str | None = None,
    user: Any = Depends(current_user),
    server: Any = Depends(get_server),
) -> dict[str, Any]:
    """Global usage roll-up. Optional ``user_id`` / ``agent_id`` narrow
    the scope; absent both fields mean *all rows*. Admin only."""
    if not user.is_admin:
        raise OctopError(ErrorCode.FORBIDDEN, "admin required")
    return _summary_or_raise(
        server=server,
        user_id=user_id,
        agent_id=agent_id,
        window=window,
        granularity=granularity,
    )


@admin_router.get(
    "/usage/export.xlsx",
    summary="Export global usage_log detail as Excel",
    response_class=StreamingResponse,
)
async def admin_export(
    request: Request,
    window: str = "last_30d",
    user_id: int | None = None,
    agent_id: str | None = None,
    user: Any = Depends(current_user),
    server: Any = Depends(get_server),
) -> StreamingResponse:
    if not user.is_admin:
        raise OctopError(ErrorCode.FORBIDDEN, "admin required")
    return _export_response(
        request=request,
        server=server,
        user_id=user_id,
        agent_id=agent_id,
        window=window,
    )
