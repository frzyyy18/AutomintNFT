from __future__ import annotations

from typing import Any

from .account_manager import find_by_twitter_handle, find_by_wallet, get_accounts
from .core import Project, load_settings


class KuongateSubmitter:
    def __init__(self, project: Project | dict[str, Any]):
        self.project = project if isinstance(project, Project) else Project(key=str(project.get("key", "kuongate")), name=str(project.get("name", "Kuongate")))
        self.field_map = self.project.field_map or {}

    def resolve_account(self, wallet_address: str = "", twitter_handle: str = "") -> dict[str, Any]:
        account = None
        if wallet_address:
            account = find_by_wallet(wallet_address)
        if account is None and twitter_handle:
            account = find_by_twitter_handle(twitter_handle)
        if account is None:
            raise ValueError("account not found")
        return account

    def build_payload(self, account: dict[str, Any], extra: dict[str, Any] | None = None) -> dict[str, Any]:
        extra = extra or {}
        return {
            self.field_map.get("username", "twitter_handle"): account.get("twitter_handle", ""),
            self.field_map.get("share_link", "share_link"): extra.get("share_link", ""),
            self.field_map.get("wallet", "wallet_address"): account.get("wallet_address", ""),
            self.field_map.get("email", "gmail"): account.get("gmail", ""),
            self.field_map.get("project_name", "project_name"): self.project.name,
            self.field_map.get("note", "note"): extra.get("note", account.get("notes", "")),
            self.field_map.get("image", "image"): extra.get("image", ""),
            **{k: v for k, v in extra.items() if k not in {"share_link", "note", "image"}},
        }

    def submit(self, wallet_address: str = "", twitter_handle: str = "", extra: dict[str, Any] | None = None) -> dict[str, Any]:
        account = self.resolve_account(wallet_address=wallet_address, twitter_handle=twitter_handle)
        payload = self.build_payload(account, extra)
        return {
            "project": self.project.key,
            "account_id": account.get("account_id"),
            "wallet_address": account.get("wallet_address"),
            "twitter_handle": account.get("twitter_handle"),
            "target_url": self.project.wl_url,
            "payload": payload,
            "status": "pending_submit",
        }
