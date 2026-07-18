"""Verified cited-source selection and report source ceilings."""

from __future__ import annotations

from typing import Any, Dict, Sequence, Tuple


class ReportSourceBudgetError(ValueError):
    """Raised when verified cited evidence exceeds the selected report mode."""


def _url_key(value: Any) -> str:
    url = str(value or "").strip()
    return url[:-1] if url.endswith("/") else url


def verified_evidence_records(
    validation: Dict[str, Any],
) -> list[Dict[str, Any]]:
    verified: list[Dict[str, Any]] = []
    seen: set[Tuple[str, str]] = set()
    rows = []
    for field in ("findings", "analysis_sections", "consensus", "debate"):
        value = validation.get(field, [])
        if isinstance(value, list):
            rows.extend(row for row in value if isinstance(row, dict))
    for row in rows:
        if not row.get("usable", True):
            continue
        for evidence in row.get("verified_evidence", []):
            if not isinstance(evidence, dict):
                continue
            url = str(evidence.get("url", "")).strip()
            evidence_id = str(evidence.get("id", "")).strip()
            key = (
                str(evidence.get("kind", "")).strip().lower(),
                _url_key(url) if url else evidence_id,
            )
            if not key[1] or key in seen:
                continue
            seen.add(key)
            verified.append(dict(evidence))
    return verified


def verified_evidence_keys(
    validation: Dict[str, Any],
) -> Tuple[set[str], set[str]]:
    records = verified_evidence_records(validation)
    web_urls = {
        _url_key(row.get("url", ""))
        for row in records
        if str(row.get("url", "")).strip()
    }
    repository_ids = {
        str(row.get("id", "")).strip()
        for row in records
        if str(row.get("id", "")).strip()
    }
    return web_urls, repository_ids


def select_cited_artifacts(
    results: Sequence[Any],
    code_evidence: Dict[str, Any],
    validation: Dict[str, Any],
) -> Tuple[list[Any], Dict[str, Any], int]:
    verified_records = verified_evidence_records(validation)
    web_urls = {
        _url_key(row.get("url", ""))
        for row in verified_records
        if str(row.get("url", "")).strip()
    }
    cited_results = [
        row
        for row in results
        if _url_key(getattr(row, "normalized_url", "")) in web_urls
    ]
    payload = dict(code_evidence) if isinstance(code_evidence, dict) else {}
    rows = [
        row
        for row in verified_records
        if str(row.get("id", "")).strip()
    ]
    payload["evidence"] = [
        row
        for row in rows
        if isinstance(row, dict)
        and str(row.get("kind", "")).lower() in {"code", "commit", "test"}
    ]
    count = len(cited_results) + len(payload["evidence"])
    return cited_results, payload, count


def enforce_report_source_limit(
    *,
    count: int,
    mode: str,
    limit: int,
) -> None:
    if count > limit:
        raise ReportSourceBudgetError(
            f"{mode} report permits at most {limit} verified cited sources; "
            f"received {count}"
        )
