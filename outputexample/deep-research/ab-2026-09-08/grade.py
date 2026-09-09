"""Grade the deep-research A/B matrix.

Three rules this grader is built around, each learned from a harness that
reported a number it had not earned:

1. Completeness is checked before any score is computed. A missing or errored
   cell is reported as missing, never silently treated as a loss or a pass.
2. The treatment is asserted per cell. A `skill` cell that did not actually
   receive the skill is a second control arm wearing the treatment's name, and
   would let the treatment claim wins it never ran for.
3. Both arms are measured by the identical mechanical check, using the skill's
   own excerpt normalization, so the measurement cannot favour the arm that
   was told about it.

A cited page that cannot be fetched is reported as `unfetchable`, distinct from
`mismatch`. Only a page that was actually read can refute an excerpt.
"""

from __future__ import annotations

import importlib.util
import json
import re
import statistics
import sys
from pathlib import Path

import os
WORK = Path("/tmp/claude-503/dr_ab")
CELLS = Path(os.environ.get("CELLS_DIR", str(WORK / "cells")))
SKILL = Path("/Users/john/awesome-skills/skills/deep-research")

spec = importlib.util.spec_from_file_location("dr_grade", SKILL / "scripts/deep_research.py")
dr = importlib.util.module_from_spec(spec)
sys.modules["dr_grade"] = dr
spec.loader.exec_module(dr)
_ORIGINAL_EXTRACT = dr.extract_text_from_html

def loose_normalize(text: str) -> str:
    """Punctuation-insensitive comparison.

    The skill's shipped matcher is `" ".join(text.split()).casefold()` with no
    punctuation handling, so a page rendering curly quotes rejects a quote the
    model copied correctly with straight ones. Measuring support with that
    matcher alone would score typography, not fidelity, so both are reported:
    `strict` is what the skill actually enforces today, `loose` is whether the
    model really did quote the page.
    """
    return re.sub(r"[^a-z0-9]+", " ", (text or "").casefold()).strip()


VERDICT_RE = re.compile(r"^\s*VERDICT:\s*(YES|NO)\s*$", re.M | re.I)
SOURCE_RE = re.compile(r"^\s*[-*]?\s*(?:<)?(https?://[^\s|>]+)(?:>)?\s*\|\|\|\s*(.+?)\s*$", re.M)


def parse_answer(text: str) -> dict:
    verdicts = VERDICT_RE.findall(text or "")
    sources = [(u.rstrip(".,);"), e.strip().strip("<>").strip())
               for u, e in SOURCE_RE.findall(text or "")]
    return {
        "verdict": verdicts[-1].upper() if verdicts else None,
        "verdict_count": len(verdicts),
        "sources": [{"url": u, "excerpt": e} for u, e in sources if e],
    }


def load_cells() -> list[dict]:
    cells = []
    for meta_path in sorted(CELLS.glob("*/meta.json")):
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        answer = (meta_path.parent / "answer.txt").read_text(encoding="utf-8", errors="replace")
        meta["parsed"] = parse_answer(answer)
        meta["_dir"] = str(meta_path.parent)
        cells.append(meta)
    return cells


def completeness(cells: list[dict], fixtures: list[dict], reps: int) -> dict:
    expected = {(f["id"], arm, rep)
                for f in fixtures for arm in ("control", "skill") for rep in range(reps)}
    seen = {(c["fixture"], c["arm"], c["rep"]) for c in cells}
    missing = sorted(expected - seen)
    errored = [(c["fixture"], c["arm"], c["rep"]) for c in cells if c["returncode"] != 0]
    # Treatment assertion: skill cells must carry the skill, control cells must not.
    bad_treatment = [
        (c["fixture"], c["arm"], c["rep"], c["system_prompt_bytes"])
        for c in cells
        if (c["arm"] == "skill") != (c["system_prompt_bytes"] > 1000)
    ]
    no_verdict = [(c["fixture"], c["arm"], c["rep"])
                  for c in cells if c["parsed"]["verdict"] is None]
    return {
        "expected_cells": len(expected),
        "observed_cells": len(seen),
        "missing": missing,
        "errored": errored,
        "treatment_violations": bad_treatment,
        "cells_without_a_parsable_verdict": no_verdict,
        "complete": not missing and not errored and not bad_treatment,
    }


FULL_PAGE_CHARS = 400_000


def _full_extract(raw_html: str, max_chars: int = FULL_PAGE_CHARS) -> str:
    """Extract with the cap effectively removed.

    The shipped extractor stops at CONTENT_MAX_CHARS (15,000). On a long
    reference page such as pkg.go.dev/testing that cut lands mid-document, so a
    correct excerpt taken from the tail cannot be found and would be reported
    as unsupported. Grading against the truncated text would score the
    extractor, not the model, so the grader reads the whole page and reports
    the skill's own cap as a separate, named limitation.
    """
    return _ORIGINAL_EXTRACT(raw_html, max_chars=max_chars)


def verify_sources(cells: list[dict], timeout: float = 25.0) -> None:
    urls = sorted({s["url"] for c in cells for s in c["parsed"]["sources"]})
    print(f"refetching {len(urls)} distinct cited URLs ...", file=sys.stderr)
    fetched = {}
    for i in range(0, len(urls), 6):
        batch = urls[i:i + 6]
        for item in dr.fetch_contents_parallel(
            batch,
            timeout=timeout,
            max_workers=6,
            max_bytes=getattr(dr, "VALIDATION_MAX_BYTES", 4_000_000),
            max_chars=FULL_PAGE_CHARS,
        ):
            fetched[dr.normalize_url(item.url) or item.url] = item
    cache = WORK / "fetched_pages.json"
    cache.write_text(json.dumps(
        {k: {"error": v.error, "words": v.word_count, "status": v.http_status}
         for k, v in fetched.items()}, indent=2), encoding="utf-8")

    for cell in cells:
        for src in cell["parsed"]["sources"]:
            key = dr.normalize_url(src["url"]) or src["url"]
            page = fetched.get(key)
            if page is None or page.error or not page.content.strip():
                src["state"] = "unfetchable"
                src["detail"] = (page.error if page else "not fetched")[:120]
                continue
            full = page.content
            truncated = full[:dr.CONTENT_MAX_CHARS]
            needle = dr._normalized_excerpt(src["excerpt"])
            loose_needle = loose_normalize(src["excerpt"])

            src["strict_match"] = bool(needle) and needle in dr._normalized_excerpt(full)
            src["loose_match"] = bool(loose_needle) and loose_needle in loose_normalize(full)
            # What the skill's shipped pipeline would actually have seen. The
            # validation path now lifts both authoring caps, so this reflects
            # the full page; set DR_PREFIX_CAP to re-measure the pre-fix state.
            cap = int(os.environ.get("DR_PREFIX_CAP", "0")) or getattr(
                dr, "VALIDATION_MAX_CHARS", dr.CONTENT_MAX_CHARS
            )
            src["visible_to_skill_validator"] = (
                bool(needle) and needle in dr._normalized_excerpt(full[:cap])
            )
            src["page_chars"] = len(full)
            src["page_exceeds_skill_cap"] = len(full) > dr.CONTENT_MAX_CHARS
            src["state"] = "verified" if src["loose_match"] else "mismatch"
            src["typography_only_failure"] = src["loose_match"] and not src["strict_match"]
            src["truncation_only_failure"] = (
                src["strict_match"] and not src["visible_to_skill_validator"]
            )
            src["final_domain"] = dr.registrable_domain(page.final_url.split("/")[2]) if "//" in page.final_url else ""
            t, tier, basis = dr.infer_source_quality(
                page.final_url.split("/")[2] if "//" in page.final_url else ""
            )
            src["source_tier"] = tier
            src["classification_basis"] = basis


SUBCOMMAND_RE = re.compile(r"deep_research\.py\s+([a-z-]+)")


def tool_profile(cell: dict) -> dict:
    """What the run actually did, from the transcript rather than from prose.

    A skill can be fully present in context and still not be executed. The only
    way to tell a followed skill from a read one is the tool calls it produced.
    """
    calls = cell.get("tool_calls") or []
    names = [c.get("name") for c in calls]
    bundled = [
        m.group(1)
        for c in calls
        for m in [SUBCOMMAND_RE.search(c.get("input", ""))]
        if m
    ]
    return {
        "tool_calls": len(calls),
        "web_search": names.count("WebSearch"),
        "web_fetch": names.count("WebFetch"),
        "bash": names.count("Bash"),
        "bundled_subcommands": sorted(set(bundled)),
        "ran_bundled_scripts": bool(bundled),
        "ran_validate_or_report": bool({"validate", "report"} & set(bundled)),
    }


def summarize(cells: list[dict], fixtures: dict) -> dict:
    out = {}
    for arm in ("control", "skill"):
        rows = [c for c in cells if c["arm"] == arm and c["returncode"] == 0]
        correct = [c for c in rows
                   if c["parsed"]["verdict"] == fixtures[c["fixture"]]["answer"]]
        all_src = [s for c in rows for s in c["parsed"]["sources"]]
        verified = [s for s in all_src if s.get("state") == "verified"]
        mismatch = [s for s in all_src if s.get("state") == "mismatch"]
        unfetchable = [s for s in all_src if s.get("state") == "unfetchable"]
        checkable = len(verified) + len(mismatch)
        strict_ok = [s for s in all_src if s.get("strict_match")]
        validator_ok = [s for s in all_src if s.get("visible_to_skill_validator")]
        truncation_only = [s for s in all_src if s.get("truncation_only_failure")]
        typography_only = [s for s in all_src if s.get("typography_only_failure")]
        cells_with_verified = [
            c for c in rows
            if any(s.get("state") == "verified" for s in c["parsed"]["sources"])
        ]
        cells_with_verified_primary = [
            c for c in rows
            if any(
                s.get("state") == "verified"
                and any(d in s["url"] for d in fixtures[c["fixture"]]["primary_domains"])
                for s in c["parsed"]["sources"]
            )
        ]
        profiles = [tool_profile(c) for c in rows]
        out[arm] = {
            "cells": len(rows),
            "cells_that_ran_bundled_scripts": sum(1 for p in profiles if p["ran_bundled_scripts"]),
            "cells_that_ran_validate_or_report": sum(1 for p in profiles if p["ran_validate_or_report"]),
            "subcommands_seen": sorted({sc for p in profiles for sc in p["bundled_subcommands"]}),
            "median_tool_calls": statistics.median([p["tool_calls"] for p in profiles]) if profiles else None,
            "total_web_search": sum(p["web_search"] for p in profiles),
            "total_web_fetch": sum(p["web_fetch"] for p in profiles),
            "verdict_correct": len(correct),
            "accuracy": round(len(correct) / len(rows), 3) if rows else None,
            "citations_total": len(all_src),
            "citations_per_cell": round(len(all_src) / len(rows), 2) if rows else None,
            "citations_verified": len(verified),
            "citations_mismatched": len(mismatch),
            "citations_unfetchable": len(unfetchable),
            "support_rate_of_checkable": round(len(verified) / checkable, 3) if checkable else None,
            "citations_passing_skills_own_strict_matcher": len(strict_ok),
            "strict_support_rate_of_checkable": round(len(strict_ok) / checkable, 3) if checkable else None,
            "quotes_correct_but_rejected_on_typography": len(typography_only),
            "citations_the_skills_own_validator_would_accept": len(validator_ok),
            "quotes_correct_but_lost_to_the_15k_extraction_cap": len(truncation_only),
            "cells_with_at_least_one_verified_quote": len(cells_with_verified),
            "cells_with_a_verified_primary_source": len(cells_with_verified_primary),
            "median_duration_s": statistics.median([c["duration_s"] for c in rows]) if rows else None,
            "total_output_tokens": sum(
                (c.get("usage") or {}).get("output_tokens", 0) for c in rows
            ),
            "median_answer_chars": statistics.median([c["answer_chars"] for c in rows]) if rows else None,
        }
    return out


def per_fixture(cells: list[dict], fixtures: dict) -> list[dict]:
    rows = []
    for fid, f in fixtures.items():
        entry = {"fixture": fid, "answer_key": f["answer"]}
        for arm in ("control", "skill"):
            cs = [c for c in cells if c["fixture"] == fid and c["arm"] == arm and c["returncode"] == 0]
            entry[arm] = {
                "verdicts": [c["parsed"]["verdict"] for c in cs],
                "correct": sum(1 for c in cs if c["parsed"]["verdict"] == f["answer"]),
                "n": len(cs),
                "verified_quotes": sum(
                    1 for c in cs for s in c["parsed"]["sources"] if s.get("state") == "verified"
                ),
                "mismatched_quotes": sum(
                    1 for c in cs for s in c["parsed"]["sources"] if s.get("state") == "mismatch"
                ),
            }
        rows.append(entry)
    return rows


def main() -> int:
    fixture_doc = json.loads((WORK / "fixtures.json").read_text(encoding="utf-8"))
    fixtures = {f["id"]: f for f in fixture_doc["fixtures"]}
    reps = int(sys.argv[1]) if len(sys.argv) > 1 else 2

    cells = load_cells()
    gate = completeness(cells, list(fixtures.values()), reps)
    print(json.dumps({"completeness": gate}, indent=2))
    if not gate["complete"]:
        print("\nMATRIX INCOMPLETE — scores below are provisional and must be "
              "labelled as such.\n", file=sys.stderr)

    verify_sources(cells)
    report = {
        "completeness": gate,
        "summary": summarize(cells, fixtures),
        "per_fixture": per_fixture(cells, fixtures),
        "cells": [
            {
                "fixture": c["fixture"], "arm": c["arm"], "rep": c["rep"],
                "verdict": c["parsed"]["verdict"], "duration_s": c["duration_s"],
                "system_prompt_bytes": c["system_prompt_bytes"],
                "output_tokens": (c.get("usage") or {}).get("output_tokens", 0),
                "tools": tool_profile(c),
                "sources": c["parsed"]["sources"],
            }
            for c in cells
        ],
    }
    (WORK / os.environ.get("RESULTS_NAME", "results.json")).write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"summary": report["summary"]}, indent=2))
    return 0 if gate["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
