"""Curated source-authority registry lookup.

Shape-based rules cannot tell an official domain from a host that merely calls
itself `docs.something`, which is why automatic T1 was restricted to government
suffixes. The cost was that go.dev, kubernetes.io and rfc-editor.org all
derived as T4, putting High out of reach for ordinary technical research.

This module reads a small curated registry instead. Membership is a checked,
dated statement about who operates a domain — never a statement that the
content is correct — and an unlisted host keeps its heuristic classification.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

REGISTRY_SCHEMA = "deep-research/source-authority-v1"
REGISTRY_PATH = (
    Path(__file__).resolve().parents[2] / "references" / "source-authority-registry.json"
)

AUTHORITY_TIERS = {
    "standards-body": ("standards", "T1"),
    "government": ("government", "T1"),
    "project-owned": ("official", "T1"),
}

# A project's own documentation is authoritative about that project and is not
# an independent voice about anything else. Claims that need corroboration must
# not treat it as the primary leg.
VENDOR_SELF_AUTHORITIES = frozenset({"project-owned"})


@lru_cache(maxsize=1)
def load_registry(path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Return registry entries, or an empty list when unreadable.

    Failing closed matters more than reporting the problem: with no entries the
    classifier falls back to the previous conservative heuristics, so a missing
    or corrupt registry can only withhold authority, never grant it.
    """
    target = Path(path) if path else REGISTRY_PATH
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if not isinstance(payload, dict) or payload.get("schema") != REGISTRY_SCHEMA:
        return []
    entries = payload.get("entries")
    if not isinstance(entries, list):
        return []
    cleaned: List[Dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        authority = str(entry.get("authority", "")).strip()
        domains = entry.get("domains")
        if authority not in AUTHORITY_TIERS or not isinstance(domains, list):
            continue
        cleaned.append(
            {
                "domains": tuple(
                    str(d).strip().lower().strip(".") for d in domains if str(d).strip()
                ),
                "subjects": tuple(str(s) for s in entry.get("subjects", []) if str(s)),
                "authority": authority,
                "basis": str(entry.get("basis", "")).strip(),
                "verified_on": str(entry.get("verified_on", "")).strip(),
            }
        )
    return cleaned


def lookup(hostname: str, registry: Optional[List[Dict[str, Any]]] = None) -> Optional[Dict[str, Any]]:
    """Return the registry entry that owns `hostname`, if any.

    Matching is exact host or a true subdomain of a listed domain. It is never
    reduced to the registrable domain: `docs.aws.amazon.com` is listed, so
    `amazon.com` must not inherit its authority.
    """
    host = str(hostname or "").strip().lower().strip(".")
    if not host:
        return None
    entries = load_registry() if registry is None else registry
    best: Optional[Dict[str, Any]] = None
    best_length = -1
    for entry in entries:
        for domain in entry["domains"]:
            if host == domain or host.endswith("." + domain):
                # Prefer the most specific listed domain when several match.
                if len(domain) > best_length:
                    best, best_length = entry, len(domain)
    return best


def classify(hostname: str) -> Optional[Dict[str, Any]]:
    """Return source type, tier, basis and vendor-self flag for a listed host."""
    entry = lookup(hostname)
    if not entry:
        return None
    source_type, tier = AUTHORITY_TIERS[entry["authority"]]
    basis = f"registry:{entry['authority']}"
    if entry["basis"]:
        basis = f"{basis}:{entry['basis']}"
    return {
        "source_type": source_type,
        "source_tier": tier,
        "classification_basis": basis,
        "authority": entry["authority"],
        "vendor_self": entry["authority"] in VENDOR_SELF_AUTHORITIES,
        "subjects": list(entry["subjects"]),
        "verified_on": entry["verified_on"],
    }
