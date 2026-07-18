"""Multilingual research-kind and depth planning."""

from __future__ import annotations

from typing import Any, Dict, Tuple

VALID_MODES = ("quick", "standard", "deep")
VALID_RESEARCH_KINDS = ("web", "codebase", "hybrid")
MODE_BUDGETS: Dict[str, Dict[str, int]] = {
    "quick": {
        "retrieval_min": 5,
        "retrieval_max": 10,
        "content_max": 5,
        "report_sources_max": 8,
    },
    "standard": {
        "retrieval_min": 15,
        "retrieval_max": 25,
        "content_max": 10,
        "report_sources_max": 20,
    },
    "deep": {
        "retrieval_min": 30,
        "retrieval_max": 50,
        "content_max": 15,
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


def classify_research_kind(request: str) -> str:
    text = str(request or "").casefold()
    has_codebase = any(signal in text for signal in CODEBASE_SIGNALS)
    has_external = any(signal in text for signal in EXTERNAL_SIGNALS)
    if has_codebase and has_external:
        return "hybrid"
    if has_codebase:
        return "codebase"
    return "web"


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
    provider_count = sum(1 for signal in PROVIDER_SIGNALS if signal in text)
    if (
        any(signal in text for signal in DEEP_SIGNALS)
        or has_security
        or (has_comparison and provider_count >= 2)
    ):
        return "deep", "auto:high-complexity-or-risk"
    if any(signal in text for signal in QUICK_SIGNALS):
        return "quick", "auto:explicit-quick-signal"
    if text.startswith(QUESTION_STARTS) and not has_comparison:
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
    if not kind:
        kind = classify_research_kind(request)
    mode, mode_basis = select_research_mode(request, explicit_mode=explicit_mode)
    return {
        "request": request,
        "research_kind": kind,
        "mode": mode,
        "mode_basis": mode_basis,
        "budget": dict(MODE_BUDGETS[mode]),
        "requires_web_content": kind in {"web", "hybrid"},
        "requires_code_evidence": kind in {"codebase", "hybrid"},
    }

