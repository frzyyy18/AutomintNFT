from __future__ import annotations

import csv
import datetime
from typing import Any

from .account_manager import get_accounts
from .core import ensure_results_dir, get_project
from .target_resolver import resolve_target


def _now() -> str:
    return datetime.datetime.utcnow().isoformat() + "Z"


def _valid_accounts(selected_accounts: list[dict] | None = None) -> list[dict]:
    accounts = selected_accounts if selected_accounts is not None else get_accounts()
    valid: list[dict] = []
    for account in accounts:
        if str(account.get("wallet_address", "")).strip() or str(account.get("twitter_handle", "")).strip():
            valid.append(account)
    return valid


def _stage_rows(
    project_key: str,
    stages: list[dict[str, Any]],
    accounts: list[dict],
    extra: dict | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    extra = extra or {}
    default_stages = stages or [{"name": "PUBLIC", "stage_type": "PUBLIC", "open": True, "eligible": True}]
    for account in accounts:
        for stage in default_stages:
            row = {
                "project": project_key,
                "account_id": account.get("account_id"),
                "wallet_address": account.get("wallet_address", ""),
                "twitter_handle": account.get("twitter_handle", ""),
                "stage": stage.get("name", stage.get("stage_type", "PUBLIC")),
                "stage_type": stage.get("stage_type", "PUBLIC"),
                "eligible": bool(stage.get("eligible", True)),
                "open": bool(stage.get("open", True)),
                "checked_at": _now(),
            }
            row.update(extra)
            rows.append(row)
    return rows


def check_project(
    project_key: str,
    selected_accounts: list[dict] | None = None,
) -> list[dict[str, Any]]:
    project = get_project(project_key)
    accounts = _valid_accounts(selected_accounts)
    if not accounts:
        return [
            {
                "project": project.key,
                "stage": "PUBLIC",
                "stage_type": "PUBLIC",
                "eligible": True,
                "open": True,
                "checked_at": _now(),
            }
        ]
    return _stage_rows(project.key, project.stages, accounts)


def check_target(
    target_url: str,
    selected_accounts: list[dict] | None = None,
) -> list[dict[str, Any]]:
    resolved = resolve_target(target_url)
    project_key = resolved.project_key or resolved.slug or "target"
    accounts = _valid_accounts(selected_accounts)
    extra = {
        "source": resolved.source,
        "target_type": resolved.target_type,
        "normalized_url": resolved.normalized_url,
        "chain": resolved.chain,
    }
    try:
        project = get_project(project_key)
        stages = project.stages
        project_label = project.key
    except Exception:
        stages = []
        project_label = project_key

    if not accounts:
        row = {
            "project": project_label,
            "stage": "PUBLIC",
            "stage_type": "PUBLIC",
            "eligible": True,
            "open": True,
            "checked_at": _now(),
        }
        row.update(extra)
        return [row]

    return _stage_rows(project_label, stages, accounts, extra=extra)


def write_csv(rows: list[dict[str, Any]], project_key: str) -> str:
    safe_key = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in str(project_key or "target"))
    output_path = ensure_results_dir() / f"{safe_key}_eligibility.csv"
    fieldnames = sorted({key for row in rows for key in row.keys()})
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return str(output_path)
