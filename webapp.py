from __future__ import annotations

import json
import threading
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from bot.account_manager import get_accounts, upsert_account, delete_account
from bot.core import CONFIG_PATH, DEFAULT_SETTINGS, get_project, load_settings
from bot.eligibility import check_project, check_target, write_csv
from bot.kuongate_submitter import KuongateSubmitter
from bot.mint_pipeline import mint_all, mint_for_account, save_results
from bot.target_resolver import resolve_target

PORT = 3000


def _error(handler: BaseHTTPRequestHandler, status: int, message: str, **extra) -> None:
    payload = {"status": "error", "error": message}
    payload.update(extra)
    _response(handler, status, payload)


def _save_settings(settings: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        import yaml
        CONFIG_PATH.write_text(yaml.safe_dump(settings, sort_keys=False, allow_unicode=True), encoding="utf-8")
    except Exception:
        CONFIG_PATH.write_text(json.dumps(settings, indent=2, ensure_ascii=False), encoding="utf-8")


def _as_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _split_csv(value) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return []


def _json_dict(value, fallback: dict | None = None) -> dict:
    fallback = fallback or {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            loaded = json.loads(value)
            return loaded if isinstance(loaded, dict) else fallback
        except Exception:
            return fallback
    return fallback


def _project_payload(project_key: str) -> dict:
    project = get_project(project_key)
    return {
        "key": project.key,
        "slug": project.key,
        "name": project.name,
        "chain": project.chain,
        "wl_url": project.wl_url,
        "adapter": project.adapter,
        "submit_path": project.submit_path,
        "required_fields": project.required_fields,
        "field_map": project.field_map,
        "mint": project.mint,
        "stages": project.stages,
        "seadrop": project.seadrop,
        "rpc": project.raw.get("rpc", {}),
        "proxy": project.raw.get("proxy", {}),
        "captcha": project.raw.get("captcha", {}),
    }


def _require_project(project_key: str):
    try:
        return get_project(project_key)
    except KeyError as exc:
        raise ValueError(f"project not found: {project_key}") from exc


def _json_body(handler: BaseHTTPRequestHandler) -> dict:
    length = int(handler.headers.get("Content-Length", "0") or 0)
    body = handler.rfile.read(length).decode("utf-8") if length else "{}"
    try:
        payload = json.loads(body or "{}")
    except json.JSONDecodeError as exc:
        raise ValueError("invalid json body") from exc
    if not isinstance(payload, dict):
        raise ValueError("json body must be an object")
    return payload


def _has_min_account_fields(account: dict) -> bool:
    return bool(str(account.get("wallet_address", "")).strip() or str(account.get("twitter_handle", "")).strip())


def _response(handler: BaseHTTPRequestHandler, status: int, payload: dict) -> None:
    body = json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type")
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    handler.end_headers()
    handler.wfile.write(body)


def _project_result(project: dict) -> dict:
    return {
        "slug": project.get("slug"),
        "name": project.get("name"),
        "chain": project.get("chain", "ethereum"),
        "wl_url": project.get("wl_url", ""),
        "adapter": project.get("adapter", "kuongate"),
        "submit_path": project.get("submit_path", ""),
        "required_fields": project.get("required_fields", []),
        "field_map": project.get("field_map", {}),
        "mint": project.get("mint", {}),
        "stages": project.get("stages", []),
        "seadrop": project.get("seadrop", {}),
        "rpc": project.get("rpc", {}),
        "proxy": project.get("proxy", {}),
        "captcha": project.get("captcha", {}),
    }


def _settings_payload() -> dict:
    settings = load_settings()
    projects = settings.get("projects", {}) if isinstance(settings.get("projects"), dict) else {}
    return {
        "projects": projects,
        "projects_list": [_project_result({"slug": slug, **project}) for slug, project in projects.items() if isinstance(project, dict)],
        "accounts": get_accounts(),
        "global": settings.get("global", {}),
        "ui": settings.get("ui", {}),
    }


def _normalize_project_payload(payload: dict) -> tuple[str, dict]:
    defaults = deepcopy(DEFAULT_SETTINGS["projects"]["kuongate"])
    project_key = str(payload.get("project") or payload.get("slug") or "kuongate").strip() or "kuongate"
    defaults.update({
        "name": str(payload.get("name", defaults.get("name", project_key)) or project_key),
        "chain": str(payload.get("chain", defaults.get("chain", "ethereum")) or "ethereum"),
        "wl_url": str(payload.get("wl_url", defaults.get("wl_url", "")) or ""),
        "adapter": str(payload.get("adapter", defaults.get("adapter", "kuongate")) or "kuongate"),
        "submit_path": str(payload.get("submit_path", defaults.get("submit_path", "")) or ""),
    })
    required_fields = payload.get("required_fields")
    if required_fields is not None:
        defaults["required_fields"] = _split_csv(required_fields)
    field_map = _json_dict(payload.get("field_map"), defaults.get("field_map", {}))
    defaults["field_map"] = {**defaults.get("field_map", {}), **field_map}

    mint = _json_dict(payload.get("mint"), defaults.get("mint", {}))
    seadrop = _json_dict(payload.get("seadrop"), defaults.get("seadrop", {}))
    rpc = _json_dict(payload.get("rpc"), defaults.get("rpc", {}))
    proxy = _json_dict(payload.get("proxy"), defaults.get("proxy", {}))
    captcha = _json_dict(payload.get("captcha"), defaults.get("captcha", {}))

    defaults["mint"] = {**defaults.get("mint", {}), **mint}
    defaults["seadrop"] = {**defaults.get("seadrop", {}), **seadrop}
    defaults["rpc"] = {**defaults.get("rpc", {}), **rpc}
    defaults["proxy"] = {**defaults.get("proxy", {}), **proxy}
    defaults["captcha"] = {**defaults.get("captcha", {}), **captcha}

    if "stages" in payload and isinstance(payload["stages"], list):
        defaults["stages"] = payload["stages"]

    for section in ("mint", "seadrop", "proxy"):
        if isinstance(defaults.get(section), dict):
            for key in ("enabled", "allow_user_edit", "rotate"):
                if key in defaults[section]:
                    defaults[section][key] = _as_bool(defaults[section][key])
    return project_key, defaults


def _resolve_payload_target(payload: dict) -> dict:
    target_url = str(payload.get("target_url", "") or "").strip()
    if not target_url:
        return {}
    return resolve_target(target_url).to_dict()


def _select_accounts(payload: dict) -> list[dict]:
    accounts = [account for account in get_accounts() if _has_min_account_fields(account)]
    if not accounts:
        return []

    requested_ids = payload.get("account_ids")
    requested_wallets = payload.get("wallets")

    selected = accounts
    if isinstance(requested_ids, list) and requested_ids:
        requested_ids_int = {int(item) for item in requested_ids if str(item).strip()}
        selected = [account for account in selected if int(account.get("account_id", 0) or 0) in requested_ids_int]
    if isinstance(requested_wallets, list) and requested_wallets:
        requested_wallets_norm = {str(item).strip().lower() for item in requested_wallets if str(item).strip()}
        selected = [account for account in selected if str(account.get("wallet_address", "")).strip().lower() in requested_wallets_norm]
    return selected


# ── Pipeline Streaming ──────────────────────────────────────────
_pipeline_buf: dict[str, list[dict]] = {}
_pipeline_lock = threading.Lock()


def _pipeline_stream(project_key: str, selected_accounts: list[dict], run_id: str) -> None:
    """Run mint_all and emit progress events to _pipeline_buf."""
    from bot.mint_pipeline import MintAdapter
    from bot.core import get_project

    project = get_project(project_key)

    def _emit(event: str, data: dict) -> None:
        with _pipeline_lock:
            buf = _pipeline_buf.setdefault(run_id, [])
            buf.append({"event": event, **data})

    accounts = selected_accounts if selected_accounts else get_accounts()
    total = len(accounts)
    _emit("start", {"total": total, "project": project_key})

    results: list[dict] = []
    for idx, account in enumerate(accounts):
        wallet = account.get("wallet_address", "") if isinstance(account, dict) else ""
        note = account.get("label", "") or account.get("twitter_handle", "") or ""
        progress = {"current": idx + 1, "total": total, "account_id": account.get("account_id", ""), "wallet": wallet, "note": note}
        _emit("progress", progress)
        if not wallet:
            _emit("skip", {**progress, "reason": "no wallet"})
            continue

        from bot.mint_pipeline import mint_for_account
        try:
            result = mint_for_account(project, wallet_address=wallet)
            result["account"] = wallet
            result["account_id"] = account.get("account_id", "")
            results.append(result)
            _emit("result", result)
        except Exception as exc:
            err = {"account": wallet, "account_id": account.get("account_id", ""), "status": "error", "error": str(exc)}
            results.append(err)
            _emit("error", err)

    _emit("done", {"results": results, "count": len(results)})


class RequestHandler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        return _response(self, 200, {"status": "ok"})

    def do_GET(self):
        try:
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            if parsed.path == "/":
                html = Path(__file__).with_name("index.html").read_text(encoding="utf-8")
                body = html.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if parsed.path == "/api/summary":
                settings = _settings_payload()
                return _response(self, 200, {
                    "status": "ok",
                    "name": "AutomintNFT",
                    "project_count": len(settings.get("projects", {}) or {}),
                    "account_count": len(settings.get("accounts", [])),
                    "features": ["wl", "eligibility", "mint", "pipeline", "settings", "ui", "target_resolver"],
                    "projects": settings.get("projects_list", []),
                    "accounts": settings.get("accounts", []),
                })
            if parsed.path == "/api/project":
                project_key = (params.get("project") or params.get("slug") or [""])[0]
                if not project_key:
                    return _error(self, 400, "missing project")
                _require_project(project_key)
                return _response(self, 200, {"status": "ok", "project": _project_payload(project_key)})
            if parsed.path == "/api/resolve":
                target_url = (params.get("target_url") or [""])[0]
                if not target_url:
                    return _error(self, 400, "missing target_url")
                return _response(self, 200, {"status": "ok", "target": resolve_target(target_url).to_dict()})
            if parsed.path == "/api/settings":
                return _response(self, 200, {"status": "ok", "settings": _settings_payload()})
            if parsed.path == "/api/accounts":
                return _response(self, 200, {"status": "ok", "accounts": get_accounts()})
            if parsed.path == "/api/check":
                target_url = (params.get("target_url") or [""])[0]
                if target_url:
                    rows = check_target(target_url)
                    target = resolve_target(target_url).to_dict()
                    return _response(self, 200, {"status": "ok", "target": target, "rows": rows, "results": write_csv(rows, target.get("project_key") or "target")})
                project_key = (params.get("project") or ["kuongate"])[0]
                _require_project(project_key)
                rows = check_project(project_key)
                return _response(self, 200, {"status": "ok", "project": project_key, "rows": rows, "results": write_csv(rows, project_key)})
            if parsed.path == "/api/mint":
                project_key = (params.get("project") or ["kuongate"])[0]
                project = _require_project(project_key)
                wallet = (params.get("wallet") or params.get("wallet_address") or [""])[0]
                quantity = int((params.get("quantity") or ["1"])[0])
                return _response(self, 200, {"status": "ok", "mint": mint_for_account(project, wallet_address=wallet, quantity=quantity)})
            if parsed.path == "/api/pipeline/events":
                run_id = (params.get("run_id") or [""])[0]
                since = int((params.get("since") or ["0"])[0])
                if not run_id:
                    return _error(self, 400, "missing run_id")
                with _pipeline_lock:
                    buf = _pipeline_buf.get(run_id, [])
                    new_events = buf[since:]
                return _response(self, 200, {"status": "ok", "events": new_events, "count": len(new_events), "since": since})
            if parsed.path == "/api/pipeline/start":
                project_key = (params.get("project") or ["kuongate"])[0]
                _require_project(project_key)
                target_url = (params.get("target_url") or [""])[0]
                account_ids = params.get("account_ids", [])
                run_id = f"run_{int(__import__('time').time())}"
                selected = get_accounts()
                if account_ids:
                    ids = {int(i) for i in account_ids if i.strip()}
                    selected = [a for a in selected if int(a.get("account_id", 0) or 0) in ids]
                t = threading.Thread(target=_pipeline_stream, args=(project_key, selected, run_id), daemon=True)
                t.start()
                return _response(self, 200, {"status": "ok", "run_id": run_id})
            return _response(self, 200, {"status": "ok", "message": "AutomintNFT"})
        except ValueError as exc:
            return _error(self, 400, str(exc))
        except Exception as exc:
            return _error(self, 500, "internal server error", detail=str(exc))

    def do_POST(self):
        try:
            parsed = urlparse(self.path)
            payload = _json_body(self)
            if parsed.path == "/api/account":
                if payload.get("_action") == "delete":
                    account_id = int(payload.get("account_id", 0) or 0)
                    if not account_id:
                        return _error(self, 400, "account_id required for delete")
                    accounts = delete_account(account_id)
                    return _response(self, 200, {"status": "ok", "accounts": accounts})
                accounts = upsert_account(payload)
                return _response(self, 200, {"status": "ok", "accounts": accounts})
            if parsed.path == "/api/project":
                settings = load_settings()
                projects = settings.get("projects", {}) if isinstance(settings.get("projects"), dict) else {}
                project_key, project = _normalize_project_payload(payload)
                projects[project_key] = project
                settings["projects"] = projects
                _save_settings(settings)
                return _response(self, 200, {"status": "ok", "project": _project_result({"slug": project_key, **project})})
            if parsed.path == "/api/settings":
                settings = load_settings()
                if "global" in payload and isinstance(payload["global"], dict):
                    settings["global"] = {**settings.get("global", {}), **payload["global"]}
                if "ui" in payload and isinstance(payload["ui"], dict):
                    settings["ui"] = {**settings.get("ui", {}), **payload["ui"]}
                if "accounts" in payload and isinstance(payload["accounts"], list):
                    settings["accounts"] = payload["accounts"]
                _save_settings(settings)
                return _response(self, 200, {"status": "ok", "settings": _settings_payload()})
            if parsed.path == "/api/resolve":
                resolved = _resolve_payload_target(payload)
                if not resolved:
                    return _error(self, 400, "target_url is required")
                return _response(self, 200, {"status": "ok", "target": resolved})
            if parsed.path == "/api/wl":
                resolved = _resolve_payload_target(payload)
                project_key = str(payload.get("project") or resolved.get("project_key") or "kuongate")
                project = _require_project(project_key)
                if resolved.get("wl_url") and not project.wl_url:
                    project.raw["wl_url"] = resolved["wl_url"]
                    project.wl_url = resolved["wl_url"]
                if not str(payload.get("wallet_address", "")).strip() and not str(payload.get("twitter_handle", "")).strip():
                    return _error(self, 400, "wallet_address or twitter_handle is required", target=resolved or None)
                submitter = KuongateSubmitter(project)
                result = submitter.submit(
                    wallet_address=payload.get("wallet_address", ""),
                    twitter_handle=payload.get("twitter_handle", ""),
                    extra=payload,
                )
                return _response(self, 200, {"status": "ok", "target": resolved or None, "result": result})
            if parsed.path == "/api/mint_all":
                resolved = _resolve_payload_target(payload)
                project_key = str(payload.get("project") or resolved.get("project_key") or "kuongate")
                project = _require_project(project_key)
                selected_accounts = _select_accounts(payload)
                if not selected_accounts:
                    return _error(self, 400, "no valid accounts selected", accounts=get_accounts(), target=resolved or None)
                results = save_results(mint_all(project, selected_accounts=selected_accounts))
                results = [row for row in results if str(row.get("account", "")).strip()]
                return _response(self, 200, {
                    "status": "ok",
                    "target": resolved or None,
                    "results": results,
                    "accounts_used": len(results),
                    "selected_accounts": selected_accounts,
                })
            if parsed.path == "/api/check":
                resolved = _resolve_payload_target(payload)
                if resolved:
                    rows = check_target(payload.get("target_url", ""), selected_accounts=_select_accounts(payload) or None)
                    return _response(self, 200, {"status": "ok", "target": resolved, "rows": rows, "results": write_csv(rows, resolved.get("project_key") or "target")})
                project_key = str(payload.get("project", "kuongate") or "kuongate")
                _require_project(project_key)
                rows = check_project(project_key)
                return _response(self, 200, {"status": "ok", "project": project_key, "rows": rows, "results": write_csv(rows, project_key)})
            if parsed.path == "/api/mint":
                resolved = _resolve_payload_target(payload)
                project_key = str(payload.get("project") or resolved.get("project_key") or "kuongate")
                project = _require_project(project_key)
                result = mint_for_account(
                    project,
                    wallet_address=payload.get("wallet_address", ""),
                    quantity=int(payload.get("quantity", 1) or 1),
                    target=resolved or None,
                )
                return _response(self, 200, {"status": "ok", "target": resolved or None, "mint": result})
            return _error(self, 404, "not found")
        except ValueError as exc:
            return _error(self, 400, str(exc))
        except Exception as exc:
            return _error(self, 500, "internal server error", detail=str(exc))

    def log_message(self, format, *args):
        return


def main() -> None:
    server = ThreadingHTTPServer(("0.0.0.0", PORT), RequestHandler)
    print(f"AutomintNFT server listening on http://0.0.0.0:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
