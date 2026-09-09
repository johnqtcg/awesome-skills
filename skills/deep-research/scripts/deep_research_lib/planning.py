"""Multilingual research-kind and depth planning."""

from __future__ import annotations

import re
from typing import Any, Dict, Tuple

VALID_MODES = ("quick", "standard", "deep")
VALID_RESEARCH_KINDS = ("web", "codebase", "hybrid")
MODE_BUDGETS: Dict[str, Dict[str, int]] = {
    "quick": {
        "retrieval_min": 5,
        "retrieval_max": 10,
        "content_max": 5,
        "live_verification_max": 5,
        "report_sources_max": 8,
    },
    "standard": {
        "retrieval_min": 15,
        "retrieval_max": 25,
        "content_max": 10,
        "live_verification_max": 10,
        "report_sources_max": 20,
    },
    "deep": {
        "retrieval_min": 30,
        "retrieval_max": 50,
        "content_max": 15,
        "live_verification_max": 15,
        "report_sources_max": 40,
    },
}

CODEBASE_SIGNALS = (
    "our internal repository",
    "our repository",
    "our codebase",
    "this repository",
    "this repo",
    "internal codebase",
    "in the codebase",
    "current repository",
    "current repo",
    "source tree",
    "这个仓库",
    "本仓库",
    "当前仓库",
    "仓库里",
    "仓库中",
    "代码库",
    "项目代码",
    "当前代码",
    "源码中",
    "源码里",
    "this project",
    "our project",
    "the current project",
    "本项目",
    "这个项目",
    "该项目",
    "项目里",
    "项目中",
)

# A path-shaped token is stronger evidence of local work than any phrase list,
# but it must not fire on an import path used as a topic. `crypto/tls` names a
# package the user is asking *about*; `internal/auth/token.go` and
# `skills/deep-research` name files the user is asking us to *open*. The
# difference is a file extension, a leading ./ or @, or a directory name that
# only exists inside a checkout.
REPOSITORY_PATH_RE = re.compile(
    r"(?:^|[\s\"'`(\[])"
    r"(?:"
    r"[@.]{1,2}/[\w.\-/]+"
    r"|(?:skills|internal|cmd|pkg|src|scripts|tests|test|lib|app|api|docs)/[\w.\-/]+"
    r"|[\w.\-/]+\.(?:go|py|ts|tsx|js|jsx|java|rs|rb|c|h|cc|cpp|sh|md|ya?ml|json|toml|sql)\b"
    r")"
)

# A question that enumerates causes, factors or options is not a single fact,
# no matter how it starts.
MULTIPLICITY_SIGNALS = (
    "factors",
    "reasons",
    "causes",
    "ways",
    "options",
    "approaches",
    "strategies",
    "trade-offs",
    "tradeoffs",
    "across",
    "different",
    "various",
    "pros and cons",
    "哪些",
    "多种",
    "各种",
    "分别",
    "有什么区别",
)
EXTERNAL_SIGNALS = (
    "best practice",
    "official documentation",
    "external",
    "industry",
    "compare with",
    "web research",
    "online sources",
    "最佳实践",
    "官方文档",
    "外部资料",
    "业界",
    "行业",
    "联网",
    "网上资料",
    "公网",
)
DEEP_SIGNALS = (
    "deep dive",
    "thorough",
    "comprehensive",
    "security trade-off",
    "security tradeoff",
    "payment processor",
    "production-impact",
    "production impact",
    "architecture decision",
    "multi-vendor",
    "trend report",
    "深入",
    "深度",
    "全面",
    "详尽",
    "彻底",
    "架构决策",
    "生产影响",
    "趋势报告",
)
SECURITY_SIGNALS = (
    "security",
    "secure",
    "vulnerability",
    "threat",
    "compliance",
    "安全",
    "漏洞",
    "威胁",
    "合规",
)
QUICK_SIGNALS = (
    "quick check",
    "briefly",
    "single fact",
    "快速检查",
    "快速核实",
    "简要",
    "单一事实",
)
COMPARISON_SIGNALS = (
    " compare ",
    " versus ",
    " vs ",
    "trade-off",
    "tradeoff",
    "比较",
    "对比",
    "区别",
    "取舍",
)
PROVIDER_SIGNALS = (
    "aws",
    "azure",
    "gcp",
    "google cloud",
    "alibaba cloud",
    "oracle cloud",
    "阿里云",
    "腾讯云",
    "华为云",
)
QUESTION_STARTS = (
    "what ",
    "which ",
    "when ",
    "where ",
    "who ",
    "什么",
    "哪个",
    "何时",
    "哪里",
    "谁",
)


def normalize_mode(mode: str) -> str:
    normalized = str(mode or "").strip().lower()
    if normalized and normalized not in VALID_MODES:
        raise ValueError(f"unsupported mode: {mode}")
    return normalized


def classify_research_kind(request: str) -> Tuple[str, str]:
    """Return (research_kind, basis). Basis names the evidence for the choice."""
    text = str(request or "").casefold()
    phrase_hit = next(
        (signal for signal in CODEBASE_SIGNALS if signal in text), ""
    )
    path_match = REPOSITORY_PATH_RE.search(text)
    has_external = any(signal in text for signal in EXTERNAL_SIGNALS)
    if phrase_hit:
        local_basis = f"codebase-phrase:{phrase_hit}"
    elif path_match:
        local_basis = f"repository-path:{path_match.group(0).strip()}"
    else:
        local_basis = ""
    if local_basis and has_external:
        return "hybrid", f"{local_basis}+external-signal"
    if local_basis:
        return "codebase", local_basis
    return "web", "no-local-signal"


def classify_research_kind_name(request: str) -> str:
    """Compatibility wrapper for callers that only need the kind."""
    kind, _ = classify_research_kind(request)
    return kind


def select_research_mode(
    request: str,
    explicit_mode: str = "",
) -> Tuple[str, str]:
    override = normalize_mode(explicit_mode)
    if override:
        return override, "user"

    text = str(request or "").casefold()
    padded = f" {text} "
    has_comparison = any(signal in padded for signal in COMPARISON_SIGNALS)
    has_security = any(signal in text for signal in SECURITY_SIGNALS)
    has_multiplicity = any(signal in text for signal in MULTIPLICITY_SIGNALS)
    provider_count = sum(1 for signal in PROVIDER_SIGNALS if signal in text)
    explicit_deep = any(signal in text for signal in DEEP_SIGNALS)
    explicit_quick = any(signal in text for signal in QUICK_SIGNALS)

    if explicit_deep or (has_comparison and provider_count >= 2):
        return "deep", "auto:high-complexity-or-risk"
    # An explicit "quick check" outranks the bare security keyword. Matching
    # "security" anywhere sent "quickly confirm what the word security means"
    # to Deep, spending a 50-call budget on a definition.
    if explicit_quick:
        return "quick", "auto:explicit-quick-signal"
    if has_security and (has_comparison or provider_count >= 1 or has_multiplicity):
        return "deep", "auto:security-decision"
    if has_security:
        return "standard", "auto:security-topic-without-decision"
    # "What ...?" is only a single fact when it asks for one. A question that
    # enumerates factors or spans several cases is a synthesis task.
    if text.startswith(QUESTION_STARTS) and not has_comparison and not has_multiplicity:
        return "quick", "auto:single-fact"
    return "standard", "auto:default"


def plan_research(
    request: str,
    explicit_mode: str = "",
    explicit_kind: str = "",
) -> Dict[str, Any]:
    kind = str(explicit_kind or "").strip().lower()
    if kind and kind not in VALID_RESEARCH_KINDS:
        raise ValueError(f"unsupported research kind: {explicit_kind}")
    kind_basis = "user" if kind else ""
    if not kind:
        kind, kind_basis = classify_research_kind(request)
    mode, mode_basis = select_research_mode(request, explicit_mode=explicit_mode)
    return {
        "request": request,
        "research_kind": kind,
        "research_kind_basis": kind_basis,
        "mode": mode,
        "mode_basis": mode_basis,
        "classification_confidence": classification_confidence(
            kind_basis,
            mode_basis,
        ),
        "budget": dict(MODE_BUDGETS[mode]),
        "requires_web_content": kind in {"web", "hybrid"},
        "requires_code_evidence": kind in {"codebase", "hybrid"},
    }


# Deterministic is not the same as accurate. A keyword rule always returns an
# answer, so the plan must also say how much that answer is worth: a decision
# taken from a default rather than a matched signal is a guess the caller
# should confirm or override with --mode / --research-kind.
LOW_CONFIDENCE_BASES = frozenset({"no-local-signal", "auto:default", "auto:single-fact"})


def classification_confidence(kind_basis: str, mode_basis: str) -> str:
    """Report `high` only when both decisions came from a matched signal."""
    if kind_basis == "user" and mode_basis == "user":
        return "high"
    weak = [b for b in (kind_basis, mode_basis) if b in LOW_CONFIDENCE_BASES]
    if not weak:
        return "high"
    return "low" if len(weak) == 2 else "medium"
