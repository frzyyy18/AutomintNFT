from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .account_manager import find_account, get_accounts
from .core import Project


@dataclass
class MintAction:
    provider: str
    chain: str
    collection_slug: str = ""
    contract_address: str = ""
    quantity: int = 1
    value_wei: str = "0"
    mint_function: str = "mint"
    quantity_field: str = "quantity"
    price_field: str = "value"
    recipient_field: str = "recipient"
    recipient_mode: str = "sender"
    tx_overrides: dict[str, Any] | None = None


@dataclass
class MintAdapter:
    project_key: str
    action: MintAction

    @classmethod
    def from_project(cls, project: Project) -> "MintAdapter":
        mint = project.mint or {}
        seadrop = project.seadrop or {}
        action = MintAction(
            provider=str(mint.get("provider", seadrop.get("provider", "seadrop"))),
            chain=str(mint.get("chain", project.chain or seadrop.get("chain", "ethereum"))),
            collection_slug=str(mint.get("collection_slug", seadrop.get("collection_slug", ""))),
            contract_address=str(mint.get("contract_address", "")),
            quantity=int(mint.get("quantity", seadrop.get("mint_quantity_default", 1)) or 1),
            value_wei=str(mint.get("value_wei", "0")),
            mint_function=str(mint.get("mint_function", "mint")),
            quantity_field=str(mint.get("quantity_field", "quantity")),
            price_field=str(mint.get("price_field", "value")),
            recipient_field=str(mint.get("recipient_field", "recipient")),
            recipient_mode=str(mint.get("recipient_mode", "sender")),
            tx_overrides=dict(mint.get("tx_overrides", {}) or {}),
        )
        return cls(project_key=project.key, action=action)

    def build_tx_payload(self, wallet_address: str | None = None, quantity: int | None = None) -> dict[str, Any]:
        mint_quantity = int(quantity or self.action.quantity or 1)
        payload = {
            "provider": self.action.provider,
            "chain": self.action.chain,
            "project": self.project_key,
            "collection_slug": self.action.collection_slug,
            "contract_address": self.action.contract_address,
            "mint_function": self.action.mint_function,
            "quantity": mint_quantity,
            "quantity_field": self.action.quantity_field,
            "price_field": self.action.price_field,
            "value_wei": self.action.value_wei,
            "recipient_field": self.action.recipient_field,
            "recipient": wallet_address if self.action.recipient_mode == "sender" else "",
            "tx_overrides": self.action.tx_overrides or {},
        }
        return payload


def build_mint_payload(project: Project, wallet_address: str = "", quantity: int | None = None) -> dict[str, Any]:
    adapter = MintAdapter.from_project(project)
    return adapter.build_tx_payload(wallet_address=wallet_address, quantity=quantity)


def mint_for_account(
    project: Project,
    wallet_address: str = "",
    quantity: int | None = None,
    target: dict[str, Any] | None = None,
) -> dict[str, Any]:
    account = find_account(wallet_address=wallet_address) if wallet_address else None
    resolved_wallet = ""
    if account:
        resolved_wallet = account.get("wallet_address", "")
    elif wallet_address:
        resolved_wallet = wallet_address

    payload = build_mint_payload(project, wallet_address=resolved_wallet, quantity=quantity)
    payload["account"] = resolved_wallet
    payload["status"] = "pending_sign"
    payload["provider"] = payload.get("provider", project.mint.get("provider", "seadrop"))
    if target:
        payload["target"] = target
    return payload


def mint_all(
    project: Project,
    selected_accounts: list[dict[str, Any]] | None = None,
    target: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    accounts = selected_accounts if selected_accounts is not None else get_accounts()
    results: list[dict[str, Any]] = []
    for account in accounts:
        wallet = account.get("wallet_address", "") if isinstance(account, dict) else ""
        if not wallet:
            continue
        results.append(mint_for_account(project, wallet_address=wallet, target=target))
    return results


def save_results(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return results
