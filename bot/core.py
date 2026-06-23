from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import yaml
except Exception:
    yaml = None

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "settings.yaml"
RESULTS_DIR = ROOT / "results"
ACCOUNTS_PATH = ROOT / "data" / "accounts.json"
PROJECTS_PATH = ROOT / "data" / "projects.json"

DEFAULT_SETTINGS: dict[str, Any] = {
    "projects": {
        "kuongate": {
            "name": "Kuongate",
            "chain": "ethereum",
            "wl_url": "https://kuongate.xyz",
            "adapter": "kuongate",
            "submit_path": "/api/allowlist/submit",
            "required_fields": ["twitter_handle", "share_link"],
            "field_map": {
                "username": "twitter_handle",
                "share_link": "share_link",
                "wallet": "wallet_address",
                "email": "gmail",
                "project_name": "project_name",
                "note": "note",
                "image": "image",
            },
            "mint": {
                "provider": "seadrop",
                "collection_slug": "",
                "contract_address": "",
                "chain": "ethereum",
                "quantity": 1,
                "value_wei": "0",
                "mint_function": "mint",
                "quantity_field": "quantity",
                "price_field": "value",
                "recipient_field": "recipient",
                "recipient_mode": "sender",
                "tx_overrides": {},
                "allow_user_edit": True,
            },
            "stages": [
                {"name": "GTD", "stage_type": "GTD", "open": False, "eligible": False},
                {"name": "FCFS", "stage_type": "FCFS", "open": False, "eligible": False},
                {"name": "PUBLIC", "stage_type": "PUBLIC", "open": True, "eligible": True},
            ],
            "seadrop": {
                "enabled": True,
                "collection_slug": "",
                "chain": "ethereum",
                "mint_quantity_default": 1,
                "slippage_tolerance": 0.01,
            },
            "rpc": {
                "name": "default",
                "url": "",
                "chain_id": "1",
            },
            "proxy": {
                "enabled": False,
                "url": "",
                "rotate": False,
            },
            "captcha": {
                "provider": "2captcha",
                "api_key": "",
                "sitekey": "",
            },
        }
    },
    "accounts": [
        {
            "account_id": 1,
            "label": "main",
            "wallet_address": "",
            "twitter_handle": "",
            "gmail": "",
            "discord_user_id": "",
            "discord_bot_name": "",
            "status": "active",
            "notes": "",
        }
    ],
    "global": {
        "wallet_settings": {
            "source": "manual",
            "default_mint_accounts": 1,
        },
        "rpc": {
            "default_url": "",
            "fallback_urls": [],
        },
        "proxy": {
            "enabled": False,
            "default_url": "",
            "rotate": False,
        },
        "captcha": {
            "provider": "2captcha",
            "api_key": "",
        },
    },
    "ui": {
        "allow_user_edit": True,
        "persist_to_local_storage": True,
    },
}


@dataclass
class Wallet:
    wallet_address: str
    twitter_handle: str = ""
    gmail: str = ""
    note: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Project:
    key: str
    name: str
    chain: str = "ethereum"
    wl_url: str = ""
    adapter: str = "kuongate"
    submit_path: str = ""
    required_fields: list[str] = field(default_factory=list)
    field_map: dict[str, str] = field(default_factory=dict)
    mint: dict[str, Any] = field(default_factory=dict)
    stages: list[dict[str, Any]] = field(default_factory=list)
    seadrop: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    if yaml is not None:
        with path.open("r", encoding="utf-8") as handle:
            loaded = yaml.safe_load(handle) or {}
            return loaded if isinstance(loaded, dict) else {}
    return json.loads(path.read_text(encoding="utf-8"))


def _merge_defaults(base: Any, override: Any) -> Any:
    if isinstance(base, dict):
        if not isinstance(override, dict):
            override = {}
        merged: dict[str, Any] = {}
        for key, value in base.items():
            merged[key] = _merge_defaults(value, override.get(key))
        for key, value in override.items():
            if key not in merged:
                merged[key] = value
        return merged
    if isinstance(base, list):
        return override if isinstance(override, list) else list(base)
    return base if override is None else override


def load_settings() -> dict[str, Any]:
    loaded = load_yaml(CONFIG_PATH)
    return _merge_defaults(DEFAULT_SETTINGS, loaded if isinstance(loaded, dict) else {})


def load_projects() -> dict[str, Any]:
    settings = load_settings()
    projects = settings.get("projects")
    if isinstance(projects, dict) and projects:
        return projects
    if PROJECTS_PATH.exists():
        payload = json.loads(PROJECTS_PATH.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    return {}


def get_project(key: str) -> Project:
    settings = load_projects().get(key, {})
    if not isinstance(settings, dict):
        settings = {}
    return Project(
        key=key,
        name=settings.get("name", key),
        chain=settings.get("chain", "ethereum"),
        wl_url=settings.get("wl_url", ""),
        adapter=settings.get("adapter", "kuongate"),
        submit_path=settings.get("submit_path", ""),
        required_fields=list(settings.get("required_fields", []) or []),
        field_map=dict(settings.get("field_map", {}) or {}),
        mint=dict(settings.get("mint", {}) or {}),
        stages=list(settings.get("stages", []) or []),
        seadrop=dict(settings.get("seadrop", {}) or {}),
        raw=settings,
    )


def ensure_results_dir() -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    return RESULTS_DIR
