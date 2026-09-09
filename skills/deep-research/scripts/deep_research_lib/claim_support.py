"""Claim-support review: does the excerpt actually support the claim?

Excerpt containment proves a quotation is real. It does not prove the quotation
supports the sentence built on top of it. A finding whose claim is the exact
negation of its own excerpt passes every containment check, so citation
integrity and claim support must be two separate verdicts.

This module supplies the second verdict. It is deliberately split in two:

1. An author attestation (`support_review` on the finding). Semantic entailment
   is not decidable here, so the author declares it and the declaration is
   recorded, required for High, and auditable. A missing declaration is
   `unreviewed`, never an implicit pass.
2. Two mechanical screens that can only *remove* support, never grant it:
   polarity divergence and numeric drift. They are high-precision screens, not
   proofs; a screen that cannot decide returns "no signal" rather than a guess.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

SUPPORT_SCHEMA = "deep-research/support-review-v1"
VALID_STANCES = ("supports", "partial", "context-only", "contradicts")
STANCES_ALLOWING_HIGH = ("supports",)
MIN_OVERRIDE_RATIONALE = 20

# Standalone negators only. Bound prefixes ("non-", "un-") are excluded on
# purpose and the tokenizer keeps hyphenated compounds whole, so
# "non-idempotent" becomes one token that does not stem-match "idempotent".
# Reading the fragment as a negator produced a false conflict on a correct
# finding whose excerpt stated the negative complement of the claim.
NEGATORS = frozenset({
    "not", "no", "never", "cannot", "cant", "wont", "dont", "doesnt", "isnt",
    "arent", "wasnt", "werent", "without", "lacks", "lack", "fails", "unable",
    "excludes", "exclude", "prohibited", "forbidden", "refuses", "refuse",
    "不", "没有", "无", "未", "非", "禁止", "不会", "不能", "不可", "不得",
})

# Words too common to anchor on. An anchor built only from these would match
# unrelated sentences and produce noise in both directions.
ANCHOR_STOPWORDS = frozenset({
    "the", "a", "an", "of", "to", "in", "is", "are", "was", "were", "be",
    "been", "and", "or", "that", "this", "it", "its", "for", "on", "by",
    "with", "as", "at", "from", "all", "any", "will", "can", "may", "must",
    "should", "when", "if", "then", "than", "so", "such", "each", "every",
    "有", "的", "了", "和", "与", "在", "是", "会", "被", "对",
})

MIN_ANCHOR_TOKENS = 2
MIN_ANCHOR_CONTENT_WORDS = 2

# Hyphenated compounds stay whole; a period splits a clause only at a real
# sentence boundary so identifiers like `t.Setenv` and `go.mod` survive intact.
_TOKEN_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*|[一-鿿]")
_CLAUSE_RE = re.compile(
    r"[,;:!?()\[\]、。，；：]"
    r"|\.(?=\s|$)"
    r"|\b(?:and|but|so|while|whereas|although|though|because)\b"
)
_NUMBER_RE = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)")


def _tokens(text: str) -> List[str]:
    return [word.replace("-", "") for word in _TOKEN_RE.findall(str(text or "").lower())]


def _clauses(text: str) -> List[Tuple[List[str], bool]]:
    """Split into clauses and mark each one negated or not.

    Negation scope is clausal because the two simpler alternatives both
    regress, and `tests/test_claim_support.py` holds an executable record of
    each: a window of tokens before the anchor reads "math/rand is not secure"
    as positive, and judging the whole excerpt at once lets one negative
    sentence contradict a claim the neighbouring sentence supports. The clause
    is the smallest span that carries the polarity of the statement the anchor
    belongs to.
    """
    out: List[Tuple[List[str], bool]] = []
    for part in _CLAUSE_RE.split(str(text or "").lower()):
        if not part:
            continue
        tokens = [word.replace("-", "") for word in _TOKEN_RE.findall(part)]
        if tokens:
            out.append((tokens, any(word in NEGATORS for word in tokens)))
    return out


def _flatten(clauses: Sequence[Tuple[List[str], bool]]) -> List[str]:
    tokens: List[str] = []
    for clause_tokens, _ in clauses:
        tokens.extend(clause_tokens)
    return tokens


def _negated_at(clauses: Sequence[Tuple[List[str], bool]], position: int) -> bool:
    offset = 0
    for clause_tokens, negated in clauses:
        if offset <= position < offset + len(clause_tokens):
            return negated
        offset += len(clause_tokens)
    return False


def _stem(word: str) -> str:
    """Strip the few English inflections that break otherwise-identical anchors."""
    for suffix in ("ing", "ed", "es", "s"):
        if len(word) > 4 and word.endswith(suffix):
            return word[: -len(suffix)]
    return word


def _content_ngrams(tokens: Sequence[str], size: int) -> Dict[Tuple[str, ...], List[int]]:
    """Index stemmed n-grams that carry at least two real content words."""
    index: Dict[Tuple[str, ...], List[int]] = {}
    for start in range(len(tokens) - size + 1):
        window = tokens[start : start + size]
        content_words = sum(
            1
            for word in window
            if word not in ANCHOR_STOPWORDS and word not in NEGATORS
        )
        if content_words < MIN_ANCHOR_CONTENT_WORDS:
            continue
        index.setdefault(tuple(_stem(word) for word in window), []).append(start)
    return index


def polarity_conflict(claim: str, excerpt: str) -> Optional[str]:
    """Return the shared anchor phrase when claim and excerpt disagree in polarity.

    Returns ``None`` for "no signal": either no shared anchor exists (the two
    texts are paraphrases the screen cannot align) or the polarities agree.
    A returned anchor means one text negates what the other asserts.

    This is a screen, not an entailment check. It has a known blind spot for
    statements that are semantically equal but lexically opposite — "cannot be
    used" versus "will panic" — which it reports as a conflict. That direction
    is the safe one: it demands an author attestation instead of passing
    silently. See `tests/claim_support_corpus.json`, class `lexically-opposed`.
    """
    claim_clauses = _clauses(claim)
    excerpt_clauses = _clauses(excerpt)
    claim_tokens = _flatten(claim_clauses)
    excerpt_tokens = _flatten(excerpt_clauses)
    if not claim_tokens or not excerpt_tokens:
        return None
    largest = min(len(claim_tokens), len(excerpt_tokens))
    # Every anchor length is examined, not just the longest. In a multi-sentence
    # excerpt the longest shared phrase often sits in an unrelated sentence
    # while the sentence that actually contradicts the claim shares a shorter
    # one, so stopping at the first length that matches anything hides the
    # conflict that matters.
    for size in range(largest, MIN_ANCHOR_TOKENS - 1, -1):
        claim_index = _content_ngrams(claim_tokens, size)
        excerpt_index = _content_ngrams(excerpt_tokens, size)
        for anchor in sorted(set(claim_index) & set(excerpt_index)):
            claim_negated = all(
                _negated_at(claim_clauses, i) for i in claim_index[anchor]
            )
            excerpt_negated = all(
                _negated_at(excerpt_clauses, i) for i in excerpt_index[anchor]
            )
            if claim_negated != excerpt_negated:
                return " ".join(anchor)
    return None


def numbers_in(text: str) -> List[str]:
    """Return normalized standalone numbers, ignoring version-style dotted runs."""
    out: List[str] = []
    for raw in _NUMBER_RE.findall(str(text or "")):
        value = raw.rstrip("0").rstrip(".") if "." in raw else raw
        out.append(value or "0")
    return out


def numeric_drift(claim: str, excerpts: Sequence[str]) -> List[str]:
    """Return numbers asserted by the claim that no cited excerpt contains."""
    quoted = set()
    for excerpt in excerpts:
        quoted.update(numbers_in(excerpt))
    return [n for n in dict.fromkeys(numbers_in(claim)) if n not in quoted]


def _claim_text(finding: Dict[str, Any]) -> str:
    parts = [
        str(finding.get("title", "")),
        str(finding.get("analysis", "")),
        str(finding.get("statement", "")),
        str(finding.get("content", "")),
    ]
    return " ".join(part for part in parts if part.strip())


def read_attestation(finding: Any) -> Dict[str, Any]:
    """Normalize the author-supplied `support_review` block.

    An absent or malformed block yields stance ``unreviewed``. It never yields
    a passing stance, so omitting the block cannot be mistaken for approval.
    """
    block = finding.get("support_review") if isinstance(finding, dict) else None
    if not isinstance(block, dict):
        return {"stance": "unreviewed", "rationale": "", "reviewed_by": "", "derived_numbers": False}
    stance = str(block.get("stance", "")).strip().lower()
    if stance not in VALID_STANCES:
        stance = "unreviewed"
    return {
        "stance": stance,
        "rationale": str(block.get("rationale", "")).strip(),
        "reviewed_by": str(block.get("reviewed_by", "")).strip(),
        "derived_numbers": bool(block.get("derived_numbers", False)),
    }


def review_claim_support(
    finding: Any,
    verified_evidence: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    """Produce the claim-support verdict for one finding.

    The verdict is independent of citation integrity: `verified_evidence` has
    already proved every excerpt was really read. This answers the separate
    question of whether those excerpts back the sentence.

    Returned ``state``:

    - ``contradicted`` — a screen or the author says the excerpt opposes the
      claim. The finding is not publishable.
    - ``disputed`` — a screen flagged a conflict the author explicitly
      overrode with a rationale. Publishable, capped below High.
    - ``unreviewed`` — no attestation. Publishable, capped below High.
    - ``qualified`` — attested as partial or context-only. Capped below High.
    - ``attested`` — attested as supporting and no screen objected. High-eligible.
    """
    attestation = read_attestation(finding)
    excerpts = [
        str(item.get("excerpt", ""))
        for item in verified_evidence
        if str(item.get("excerpt", "")).strip()
    ]
    claim = _claim_text(finding if isinstance(finding, dict) else {})

    conflicts: List[str] = []
    for excerpt in excerpts:
        anchor = polarity_conflict(claim, excerpt)
        if anchor:
            conflicts.append(anchor)
    drift = numeric_drift(claim, excerpts) if excerpts and not attestation["derived_numbers"] else []

    screens = {
        "polarity_conflicts": list(dict.fromkeys(conflicts)),
        "unquoted_numbers": drift,
        "excerpts_reviewed": len(excerpts),
    }

    if attestation["stance"] == "contradicts":
        state = "contradicted"
    elif conflicts and attestation["stance"] not in STANCES_ALLOWING_HIGH:
        state = "contradicted"
    elif conflicts:
        state = (
            "disputed"
            if len(attestation["rationale"]) >= MIN_OVERRIDE_RATIONALE
            else "contradicted"
        )
    elif attestation["stance"] == "unreviewed":
        state = "unreviewed"
    elif attestation["stance"] in {"partial", "context-only"}:
        state = "qualified"
    elif drift:
        state = "qualified"
    else:
        state = "attested"

    return {
        "schema": SUPPORT_SCHEMA,
        "state": state,
        "stance": attestation["stance"],
        "rationale": attestation["rationale"],
        "reviewed_by": attestation["reviewed_by"],
        "high_eligible": state == "attested",
        "publishable": state != "contradicted",
        "screens": screens,
    }


def support_reasons(review: Dict[str, Any]) -> List[str]:
    """Human-readable downgrade reasons for one claim-support verdict."""
    state = review.get("state")
    screens = review.get("screens", {})
    conflicts = screens.get("polarity_conflicts", [])
    drift = screens.get("unquoted_numbers", [])
    reasons: List[str] = []
    if state == "contradicted":
        if review.get("stance") == "contradicts":
            reasons.append("author review records that the excerpt contradicts the claim")
        elif conflicts:
            reasons.append(
                "excerpt polarity opposes the claim at: "
                + ", ".join(conflicts)
                + "; supply support_review with stance=supports and a rationale to override"
            )
    elif state == "disputed":
        reasons.append(
            "polarity screen flagged "
            + ", ".join(conflicts)
            + "; author override recorded, so this claim cannot be High"
        )
    elif state == "unreviewed":
        reasons.append(
            "claim support was not reviewed; excerpt containment alone does not "
            "prove the excerpt supports the claim"
        )
    elif state == "qualified":
        if drift:
            reasons.append(
                "claim asserts numbers no cited excerpt contains: " + ", ".join(drift)
            )
        else:
            reasons.append(
                f"author review recorded stance={review.get('stance')}, which is "
                "weaker than full support"
            )
    return reasons


def summarize_claim_support(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate per-finding verdicts into the report-level second axis."""
    counts = {"attested": 0, "qualified": 0, "unreviewed": 0, "disputed": 0, "contradicted": 0}
    for row in rows:
        review = row.get("claim_support") if isinstance(row, dict) else None
        if isinstance(review, dict):
            counts[review.get("state", "unreviewed")] = (
                counts.get(review.get("state", "unreviewed"), 0) + 1
            )
    if counts["contradicted"]:
        state = "conflicted"
    elif counts["disputed"]:
        state = "disputed"
    elif counts["unreviewed"] or counts["qualified"]:
        state = "partially-reviewed"
    elif counts["attested"]:
        state = "reviewed"
    else:
        state = "none"
    return {"state": state, "counts": counts}
