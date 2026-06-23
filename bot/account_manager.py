from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .core import CONFIG_PATH, load_settings


def _write_settings(settings: dict[str, Any]) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        import yaml
        CONFIG_PATH.write_text(yaml.safe_dump(settings, sort_keys=False, allow_unicode=True), encoding="utf-8")
    except Exception:
        CONFIG_PATH.write_text(json.dumps(settings, indent=2, ensure_ascii=False), encoding="utf-8")


def get_accounts() -> list[dict[str, Any]]:
    settings = load_settings()
    accounts = settings.get("accounts", [])
    rows = [row for row in accounts if isinstance(row, dict)]
    return sorted(rows, key=lambda item: int(item.get("account_id", 0) or 0))


def delete_account(account_id: int) -> list[dict[str, Any]]:
    settings = load_settings()
    accounts = get_accounts()
    accounts = [item for item in accounts if int(item.get("account_id", 0) or 0) != account_id]
    settings["accounts"] = accounts
    _write_settings(settings)
    return get_accounts()


def upsert_account(account: dict[str, Any]) -> list[dict[str, Any]]:
    settings = load_settings()
    accounts = get_accounts()
    account_id = int(account.get("account_id", 0) or 0)
    if account_id <= 0:
        account_id = (max((int(item.get("account_id", 0) or 0) for item in accounts), default=0) + 1)
    row = {
        "account_id": account_id,
        "label": str(account.get("label", "") or ""),
        "wallet_address": str(account.get("wallet_address", "") or ""),
        "twitter_handle": str(account.get("twitter_handle", "") or ""),
        "gmail": str(account.get("gmail", "") or ""),
        "discord_user_id": str(account.get("discord_user_id", "") or ""),
        "discord_bot_name": str(account.get("discord_bot_name", "") or ""),
        "status": str(account.get("status", "active") or "active"),
        "notes": str(account.get("notes", account.get("note", "")) or ""),
    }
    replaced = False
    for idx, item in enumerate(accounts):
        if int(item.get("account_id", 0) or 0) == account_id:
            accounts[idx] = row
            replaced = True
            break
    if not replaced:
        accounts.append(row)
    settings["accounts"] = sorted(accounts, key=lambda item: int(item.get("account_id", 0) or 0))
    _write_settings(settings)
    return get_accounts()


def find_by_wallet(wallet_address: str) -> dict[str, Any] | None:
    wallet_address = str(wallet_address).strip().lower()
    for account in get_accounts():
        if str(account.get("wallet_address", "")).strip().lower() == wallet_address:
            return account
    return None


def find_by_twitter_handle(twitter_handle: str) -> dict[str, Any] | None:
    twitter_handle = str(twitter_handle).strip().lower().lstrip("@")
    for account in get_accounts():
        if str(account.get("twitter_handle", "")).strip().lower().lstrip("@") == twitter_handle:
            return account
    return None


def find_account(wallet_address: str = "", twitter_handle: str = "") -> dict[str, Any] | None:
    if wallet_address:
        account = find_by_wallet(wallet_address)
        if account:
            return account
    if twitter_handle:
        account = find_by_twitter_handle(twitter_handle)
        if account:
            return account
    return None
