from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, urlparse

OPENSEA_HOSTS = {
    "opensea.io",
    "www.opensea.io",
    "testnets.opensea.io",
}

CHAIN_ALIASES = {
    "ethereum": "ethereum",
    "eth": "ethereum",
    "base": "base",
    "polygon": "polygon",
    "matic": "polygon",
    "arbitrum": "arbitrum",
    "optimism": "optimism",
    "solana": "solana",
}


@dataclass
class ResolvedTarget:
    input_url: str
    normalized_url: str
    source: str
    target_type: str
    slug: str = ""
    chain: str = "ethereum"
    contract_address: str = ""
    token_id: str = ""
    project_key: str = ""
    wl_url: str = ""
    notes: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "input_url": self.input_url,
            "normalized_url": self.normalized_url,
            "source": self.source,
            "target_type": self.target_type,
            "slug": self.slug,
            "chain": self.chain,
            "contract_address": self.contract_address,
            "token_id": self.token_id,
            "project_key": self.project_key,
            "wl_url": self.wl_url,
            "notes": list(self.notes or []),
        }


def _clean_url(target_url: str) -> str:
    value = str(target_url or "").strip()
    if not value:
        raise ValueError("target_url is required")
    if "://" not in value:
        value = f"https://{value}"
    parsed = urlparse(value)
    if not parsed.netloc:
        raise ValueError("invalid target_url")
    return parsed.geturl()


def _normalize_chain(value: str) -> str:
    return CHAIN_ALIASES.get(str(value or "").strip().lower(), "ethereum")


def _resolve_opensea(parsed) -> ResolvedTarget:
    path_parts = [part for part in parsed.path.split("/") if part]
    query = parse_qs(parsed.query)
    notes: list[str] = []
    chain = _normalize_chain(query.get("chain", [""])[0])

    if not path_parts:
        return ResolvedTarget(
            input_url=parsed.geturl(),
            normalized_url=parsed.geturl(),
            source="opensea",
            target_type="homepage",
            chain=chain,
            notes=["Link OpenSea umum, belum menunjuk collection/drop spesifik."],
        )

    if path_parts[0] == "collection" and len(path_parts) >= 2:
        slug = path_parts[1]
        return ResolvedTarget(
            input_url=parsed.geturl(),
            normalized_url=f"https://opensea.io/collection/{slug}",
            source="opensea",
            target_type="collection",
            slug=slug,
            project_key=slug,
            chain=chain,
            notes=["Collection OpenSea terdeteksi dari slug."],
        )

    if path_parts[0] == "collection" and len(path_parts) >= 3 and path_parts[2] == "drops":
        slug = path_parts[1]
        return ResolvedTarget(
            input_url=parsed.geturl(),
            normalized_url=f"https://opensea.io/collection/{slug}/drops",
            source="opensea",
            target_type="drop",
            slug=slug,
            project_key=slug,
            chain=chain,
            notes=["Drop OpenSea terdeteksi dari collection slug."],
        )

    if path_parts[0] == "assets" and len(path_parts) >= 3:
        chain = _normalize_chain(path_parts[1])
        contract_address = path_parts[2]
        token_id = path_parts[3] if len(path_parts) >= 4 else ""
        return ResolvedTarget(
            input_url=parsed.geturl(),
            normalized_url=parsed.geturl(),
            source="opensea",
            target_type="asset",
            chain=chain,
            contract_address=contract_address,
            token_id=token_id,
            notes=["Asset OpenSea terdeteksi; mint biasanya butuh collection/drop, bukan asset individual."],
        )

    if path_parts[0] == "drops" and len(path_parts) >= 2:
        slug = path_parts[1]
        return ResolvedTarget(
            input_url=parsed.geturl(),
            normalized_url=parsed.geturl(),
            source="opensea",
            target_type="drop",
            slug=slug,
            project_key=slug,
            chain=chain,
            notes=["Route drops OpenSea terdeteksi dari slug."],
        )

    notes.append("Route OpenSea belum dipetakan penuh; fallback ke generic link metadata.")
    return ResolvedTarget(
        input_url=parsed.geturl(),
        normalized_url=parsed.geturl(),
        source="opensea",
        target_type="unknown",
        chain=chain,
        notes=notes,
    )


def _resolve_project_site(parsed) -> ResolvedTarget:
    host = parsed.netloc.lower()
    path_parts = [part for part in parsed.path.split("/") if part]
    project_key = host.replace("www.", "").split(":")[0].replace(".", "-")
    target_type = "project"
    notes = ["Link project langsung; eligibility/WL perlu adapter atau probe situs target."]
    if path_parts and any(part in {"mint", "claim", "allowlist", "whitelist", "presale"} for part in path_parts):
        target_type = "project_action"
        notes.append("Path terlihat seperti halaman mint/WL/claim.")
    return ResolvedTarget(
        input_url=parsed.geturl(),
        normalized_url=parsed.geturl(),
        source="project_site",
        target_type=target_type,
        slug=path_parts[-1] if path_parts else project_key,
        project_key=project_key,
        wl_url=parsed.geturl(),
        notes=notes,
    )


def resolve_target(target_url: str) -> ResolvedTarget:
    normalized = _clean_url(target_url)
    parsed = urlparse(normalized)
    if parsed.netloc.lower() in OPENSEA_HOSTS:
        return _resolve_opensea(parsed)
    return _resolve_project_site(parsed)
