"""Mutation tests for lint_search_report.py.

A linter that never fires is indistinguishable from no linter. Every rule here is proved
twice: it stays silent on the skill's real (correct) content, and it fires on a mutation
that reintroduces the specific defect it exists to catch.

Coverage is declared as data (ALL_RULES) and the uncovered set is *derived*, so adding a
rule without a mutation fails this file instead of silently reading as covered.
"""

import importlib.util
import pathlib
import re
import sys

import pytest


def _load_linter():
    path = pathlib.Path(__file__).resolve().parents[1] / "lint_search_report.py"
    spec = importlib.util.spec_from_file_location("gs_lint", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod      # register first: by-path exec + __future__
    spec.loader.exec_module(mod)      # annotations otherwise breaks
    return mod


L = _load_linter()

SKILL_DIR = pathlib.Path(__file__).resolve().parents[2]
SKILL_MD = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
REFS = SKILL_DIR / "references"
PROG = (REFS / "programmer-search-patterns.md").read_text(encoding="utf-8")
QPAT = (REFS / "query-patterns.md").read_text(encoding="utf-8")
WORKED = (REFS / "worked-examples.md").read_text(encoding="utf-8")
AITERM = (REFS / "ai-search-and-termination.md").read_text(encoding="utf-8")
SRCEVAL = (REFS / "source-evaluation.md").read_text(encoding="utf-8")

EXERCISED: set[str] = set()


def fires(rule, findings):
    """Record the rule as exercised and assert it fired."""
    EXERCISED.add(rule)
    hit = [f for f in findings if f.rule == rule]
    assert hit, f"{rule} did not fire; got {findings}"
    return hit


def replace_all(text, old, new):
    """Replace every occurrence and assert at least one happened.

    A mutation that silently matched nothing produces a SURVIVED verdict that looks like
    a linter gap but is really a broken mutation.
    """
    assert old in text, f"mutation anchor not found: {old!r}"
    return text.replace(old, new)


# ── The live skill must be clean ────────────────────────────────────────────────


class TestLiveSkillClean:
    def test_docs_have_no_errors(self):
        errors = [f for f in L.lint_docs() if f.severity == "error"]
        assert not errors, f"skill docs are not clean: {errors}"

    def test_self_test_passes(self):
        assert L.self_test() == 0

    def test_every_declared_rule_has_an_id_format(self):
        for rule in L.ALL_RULES:
            assert re.fullmatch(r"G[QSD]\d{3}", rule), rule


# ── Worked examples must pass the grader they teach ─────────────────────────────


class TestWorkedExamplesSatisfyContract:
    """The skill's own examples are the model answer. If they cannot pass the output
    contract, the contract is being taught wrong."""

    @pytest.mark.parametrize("heading", [
        "Example 1: Single-round factual search (Quick mode)",
        "Example 2: Multi-round search where the official chain cannot be completed "
        "(Standard mode)",
    ])
    def test_example_passes_report_lint(self, heading):
        body = L.section(WORKED, heading)
        assert body.strip(), f"worked example section not found: {heading}"
        errors = [f for f in L.lint_report(body) if f.severity == "error"]
        assert not errors, f"worked example violates the output contract: {errors}"

    def test_example_2_declares_partial(self):
        body = L.section(
            WORKED,
            "Example 2: Multi-round search where the official chain cannot be completed "
            "(Standard mode)",
        )
        assert "Partial" in L._field_value(body, "Degradation level"), (
            "Example 2 must model honest degradation: no official source gives a pool "
            "sizing number, so the chain is incomplete"
        )

    def test_example_2_labels_the_formula_as_practitioner(self):
        body = L.section(
            WORKED,
            "Example 2: Multi-round search where the official chain cannot be completed "
            "(Standard mode)",
        )
        numbers = L._field_value(body, "Key numbers")
        assert "Practitioner report" in numbers and "`Low`" in numbers, (
            "the community sizing factor must be labeled Practitioner report / Low, "
            "not Official or Mixed"
        )


# ── GD001 / GD002: GitHub qualifier discipline ─────────────────────────────────


class TestGitHubQualifierRules:
    def test_gd001_fires_when_bad_qualifier_is_recommended(self):
        mutated = replace_all(
            PROG,
            "- `path:go.mod \"go-redis\"` — projects depending on go-redis",
            "- `filename:go.mod \"go-redis\"` — projects depending on go-redis",
        )
        fires("GD001", L.lint_docs({"programmer-search-patterns.md": mutated}))

    def test_gd001_fires_on_stars_in_code_search_examples(self):
        mutated = replace_all(
            PROG,
            '- `language:go "sync.Pool"` — Go files containing the string',
            '- `language:go "sync.Pool" stars:>100` — popular Go files',
        )
        fires("GD001", L.lint_docs({"programmer-search-patterns.md": mutated}))

    def test_gd002_fires_when_the_warning_table_is_deleted(self):
        """Guard the guard: deleting the do-not-use table would make GD001 vacuous."""
        section = L.section(PROG, "Qualifiers that do NOT work in code search")
        assert section.strip(), "warning section missing"
        mutated = replace_all(PROG, section, "\nRemoved.\n")
        found = L.lint_docs({"programmer-search-patterns.md": mutated})
        fires("GD002", found)

    def test_recommended_examples_are_actually_extracted(self):
        """Negative control: if the extractor returned nothing, GD001 could never fire."""
        gh = L.section(PROG, "GitHub Code Search")
        code = L.section(gh, "Code search qualifiers")
        examples = L._recommended_examples(code)
        assert len(examples) >= 5, f"extractor found only {examples}"
        assert any("path:" in e for e in examples)

    def test_repo_search_examples_are_valid_for_that_engine(self):
        repo = L.section(L.section(PROG, "GitHub Code Search"),
                         "Repository search qualifiers")
        assert repo.strip(), "repository search subsection missing"
        for q in L._recommended_examples(repo):
            bad = [f for f in L.validate_query(q, "github-repo") if f.severity == "error"]
            assert not bad, f"{q!r} -> {bad}"

    def test_gd001_covers_the_repository_subsection_too(self):
        """The shipped linter must check every engine subsection, not just the first."""
        mutated = replace_all(
            PROG,
            "- `topic:kubernetes stars:100..1000` — by topic within a star band",
            "- `topic:kubernetes symbol:Reconcile` — by topic and symbol",
        )
        hit = fires("GD001", L.lint_docs({"programmer-search-patterns.md": mutated}))
        assert any("Repository search" in f.message for f in hit), hit

    def test_gd001_catches_an_example_no_engine_accepts(self):
        mutated = replace_all(
            PROG,
            '- `language:go "sync.Pool"` — Go files containing the string',
            '- `language:go "sync.Pool" stars:>50 path:pool.go` — popular pools',
        )
        fires("GD001", L.lint_docs({"programmer-search-patterns.md": mutated}))

    def test_engine_tag_convention_is_documented(self):
        """A report cannot be expected to tag its GitHub queries unless the skill says so."""
        gh = L.section(PROG, "GitHub Code Search")
        assert "[github-code]" in gh and "[github-repo]" in gh, (
            "the engine-tag convention must be documented where GitHub queries are taught"
        )
        row = next((l for l in SKILL_MD.split("\n") if "**Reusable queries**" in l), "")
        assert "[github-code]" in row, "Output Contract must require the tag"


# ── GD003 / GD004 / GD005: label enums ─────────────────────────────────────────


class TestLabelEnumRules:
    def test_gd003_fires_on_coined_label_in_prose(self):
        mutated = replace_all(
            WORKED, "(`High`, `Official`)", "(`Medium-High`, `Official`)"
        )
        fires("GD003", L.lint_docs({"worked-examples.md": mutated}))

    def test_gd003_allows_the_sentence_that_forbids_the_label(self):
        """The rule must permit its own correction. SKILL.md and source-evaluation.md
        both name `Medium-High` in order to ban it."""
        assert "Medium-High" in SKILL_MD and "Medium-High" in SRCEVAL
        assert not [f for f in L.lint_docs() if f.rule == "GD003"]

    def test_gd003_survives_a_hard_wrap_between_negation_and_token(self):
        """A soft line break must not strand the negation on the previous line."""
        text = "Never invent an intermediate\nlabel such as `Medium-High` here."
        assert not [
            f for f in L.lint_report(text) if f.rule == "GS007"
        ], "negation on the wrapped line above was not seen"

    def test_gd004_fires_on_out_of_enum_target_confidence(self):
        mutated = replace_all(
            SKILL_MD,
            "| Best practice or recommendation | 1 official basis + 1 practitioner report | Medium |",
            "| Best practice or recommendation | 1 official basis + 1 practitioner report | Medium-High |",
        )
        found = L.lint_docs({"SKILL.md": mutated})
        fires("GD004", found)

    def test_gd005_fires_when_a_key_number_loses_its_tier(self):
        mutated = replace_all(
            WORKED,
            "`MaxIdleConns` default = 2 (`High`, `Official`)",
            "`MaxIdleConns` default = 2 (`High`)",
        )
        fires("GD005", L.lint_docs({"worked-examples.md": mutated}))

    def test_gd007_fires_when_the_enum_is_duplicated(self):
        dup = (
            "\n\nTiers: `Official`, `Primary document/data`, `Reputable third-party`, "
            "`Practitioner report`, `OSINT`, `Adversary claim`.\n\n"
        )
        mutated = SKILL_MD + dup
        fires("GD007", L.lint_docs({"SKILL.md": mutated}))


# ── GD006: cross-file budget agreement ─────────────────────────────────────────


class TestBudgetAgreement:
    def test_gd006_fires_when_skill_and_query_patterns_disagree(self):
        mutated = replace_all(QPAT, "| Quick | ≥2 (run Precision first, Primary second) | ≤2 |",
                              "| Quick | ≥2 (run Precision first, Primary second) | ≤3 |")
        fires("GD006", L.lint_docs({"query-patterns.md": mutated}))

    def test_gd006_fires_when_termination_max_drifts(self):
        mutated = replace_all(AITERM, "Maximum: 8 queries", "Maximum: 10 queries")
        fires("GD006", L.lint_docs({"ai-search-and-termination.md": mutated}))

    def test_gd006_fires_when_skill_budget_changes_alone(self):
        mutated = replace_all(SKILL_MD, "- Quick: max 2 queries", "- Quick: max 4 queries")
        fires("GD006", L.lint_docs({"SKILL.md": mutated}))


# ── Query syntax rules ─────────────────────────────────────────────────────────

QUERY_CASES = [
    ("GQ001", 'site:go.dev "unterminated', None),
    ("GQ002", "(Redis OR Memcached site:redis.io", None),
    ("GQ003", "site: go.dev context", None),
    ("GQ004", "redis or memcached caching", None),
    ("GQ005", "link:github.com", None),
    ("GQ005", "+golang concurrency", None),
    ("GQ006", "related:github.com", None),
    ("GQ007", "wallpaper imagesize:3840x2160", None),
    ("GQ008", "Go 1.24 after:2025-13-01", None),
    ("GQ008", "Go after:not-a-date", None),
    ("GQ009", "foo:bar site:go.dev", None),
    ("GQ010", 'filename:go.mod "go-redis"', "github-code"),
    ("GQ010", 'language:go "errgroup" stars:>100', "github-code"),
    ("GQ010", 'extension:go "errgroup"', "github-code"),
    ("GQ011", "symbol:WithContext stars:>500", "github-repo"),
    ("GQ011", "path:go.mod topic:kubernetes", "github-repo"),
    ("GQ012", 'language:go "sync.Pool"', None),
    ("GQ012", "language:go errgroup stars:>100", None),
    ("GQ013", "path:go.mod stars:>100", None),
    ("GQ008", "Go after:2026-02-31", None),
    ("GQ008", "Go after:2026-02-29", None),
    ("GQ008", "Go before:2025-04-31", None),
    ("GQ008", "Go after:0000", None),
]


class TestQuerySyntax:
    @pytest.mark.parametrize("rule,query,engine", QUERY_CASES)
    def test_invalid_query_is_caught(self, rule, query, engine):
        fires(rule, L.validate_query(query, engine))

    @pytest.mark.parametrize("query,engine", [
        ('"fatal error: concurrent map writes" site:stackoverflow.com', "google"),
        ("Go 1.24 new features after:2025-01-01", "google"),
        ("(Gin OR Echo OR Fiber) benchmark Go after:2025-01-01", "google"),
        ("Go最佳实践 filetype:pdf", "google"),
        ('language:go symbol:WithContext', "github-code"),
        ('path:/(^|\\/)go\\.mod$/ "go-redis"', "github-code"),
        ("language:go stars:>=500 errgroup", "github-repo"),
        ("topic:kubernetes stars:100..1000", "github-repo"),
    ])
    def test_valid_query_is_clean(self, query, engine):
        bad = [f for f in L.validate_query(query, engine) if f.severity == "error"]
        assert not bad, f"{query!r} -> {bad}"

    def test_operator_inside_a_quoted_phrase_is_not_parsed(self):
        """`stars:` inside a phrase is search text, not a qualifier."""
        assert not L.validate_query('"stars: are pretty" language:go', "github-code")
        assert not L.validate_query('"link: broken" site:go.dev', "google")

    def test_engine_detection(self):
        assert L.detect_engine("site:go.dev context") == "google"
        assert L.detect_engine("plain words only") == "google"
        assert L.detect_engine("language:go symbol:Foo") == "github-code"
        assert L.detect_engine("language:go stars:>=500") == "github-repo"
        assert L.detect_engine('language:go "sync.Pool"') == "github-ambiguous"
        assert L.detect_engine("path:go.mod stars:>100") == "github-conflict"

    def test_valid_leap_day_is_accepted(self):
        assert not L.validate_query("Go after:2024-02-29")
        assert not L.validate_query("Go after:2026")
        assert not L.validate_query("Go after:2026/01/31")

    def test_bare_year_goes_through_the_same_construction(self):
        """`after:0000` and `after:0000-01-01` are the same value written two ways and must
        get the same verdict; the bare-year branch used to skip validation entirely."""
        assert [f.rule for f in L.validate_query("Go after:0000")] == ["GQ008"]
        assert [f.rule for f in L.validate_query("Go after:0000-01-01")] == ["GQ008"]

    def test_declaring_the_engine_decides_the_verdict(self):
        """The one case that cannot be settled from the string alone.

        `language:go errgroup stars:>100` is a valid repository search and is also exactly
        what someone writes when they wanted code from popular projects. Guessing either way
        hides one of the two readings, so an undeclared query is reported `unknown` and a
        declared one is judged against the engine named.
        """
        q = "language:go errgroup stars:>100"
        undeclared = L.validate_query(q)
        assert [f.rule for f in undeclared] == ["GQ012"]
        assert undeclared[0].severity == "unknown", "a guess must not read as a pass"

        as_code = L.validate_query(q, "github-code")
        assert any(f.rule == "GQ010" and f.severity == "error" for f in as_code), as_code

        assert not L.validate_query(q, "github-repo"), "valid as repository search"

    ENGINE_REPORT = (
        "Quick · Full\n"
        "errgroup shows up across most production Go services today.\n"
        "Round 1\n"
        "- {exec_tag}`language:go errgroup stars:>=1000`\n"
        "- `errgroup site:go.dev`\n"
        "Source: https://pkg.go.dev/golang.org/x/sync/errgroup\n"
        "Reusable queries: {reuse_tag}`language:go errgroup stars:>=1000`, "
        "`errgroup site:go.dev`\n"
    )

    def test_engine_tag_is_bound_to_the_occurrence_not_the_query_text(self):
        """A declaration must not vouch for the same query somewhere else.

        Keyed on query text, tagging the executed line silenced the untagged copy under
        Reusable queries — and a second occurrence overwrote the first, so which of two
        conflicting tags won depended on document order.
        """
        both = self.ENGINE_REPORT.format(
            exec_tag="[github-repo] ", reuse_tag="[github-repo] "
        )
        assert not L.lint_report(both), L.lint_report(both)

        borrowed = self.ENGINE_REPORT.format(exec_tag="[github-repo] ", reuse_tag="")
        hit = [f for f in L.lint_report(borrowed) if f.rule == "GS012"]
        assert hit, "the untagged occurrence borrowed the other line's declaration"
        assert hit[0].severity == "unknown"
        assert "line 7" in hit[0].where, hit[0].where

    def test_gs017_conflicting_declarations_of_one_query(self):
        conflicting = self.ENGINE_REPORT.format(
            exec_tag="[github-repo] ", reuse_tag="[github-code] "
        )
        fires("GS017", L.lint_report(conflicting))

    def test_tag_binds_to_its_own_item_not_the_whole_line(self):
        """One tagged query in a comma list must not cover its untagged neighbour."""
        report = (
            "Quick · Full\n"
            "errgroup shows up across most production Go services today.\n"
            "Round 1\n- [github-repo] `language:go errgroup stars:>=1000`\n"
            "- `errgroup site:go.dev`\n"
            "Source: https://pkg.go.dev/x\n"
            "Reusable queries: [github-repo] `language:go errgroup stars:>=1000`, "
            "`language:go symbol:WithContext` not run\n"
        )
        unknowns = [f for f in L.lint_report(report) if f.severity == "unknown"]
        assert any("symbol:WithContext" in f.where for f in unknowns), unknowns

    def test_an_untagged_github_query_is_reported_everywhere_it_appears(self):
        """Superseded the earlier version of this test, which tagged only the executed line
        and asserted the whole report was clean — that assertion encoded the borrowing bug."""
        report = self.ENGINE_REPORT.format(exec_tag="", reuse_tag="")
        rules = [f.rule for f in L.lint_report(report)]
        assert rules == ["GS012"], rules
        assert L.lint_report(report)[0].severity == "unknown"


# ── Report contract rules ──────────────────────────────────────────────────────

GOOD_QUICK = (
    "Quick · Full\n\n"
    "`sync.Pool` objects are collected by GC; since Go 1.13 a victim cache keeps them "
    "for one extra cycle.\n\n"
    "Round 1\n"
    "- Precision: `sync.Pool GC behavior site:go.dev`\n"
    "- Primary: `Go sync.Pool garbage collection`\n\n"
    "Key numbers: victim cache survives 1 GC cycle (`High`, `Official`)\n\n"
    "Source: https://go.dev/src/sync/pool.go\n\n"
    "Reusable queries: `sync.Pool GC behavior site:go.dev`, "
    "`Go sync.Pool garbage collection`\n"
)

GOOD_STANDARD = (
    "Standard · Partial\n\n"
    "The knob semantics are documented but no vendor publishes a sizing number, so the "
    "value has to come from a load test rather than from a formula.\n\n"
    "Round 1\n"
    "- `SetMaxOpenConns SetMaxIdleConns site:pkg.go.dev`\n"
    "- `max_connections wait_timeout site:dev.mysql.com`\n"
    "- `Go MySQL 连接池 生产环境 site:zhihu.com`\n\n"
    "Evidence chain status: official basis satisfied; practitioner report single-source\n\n"
    "Key evidence: `pkg.go.dev/database/sql` documents the defaults, "
    "`dev.mysql.com` documents the server-wide ceiling\n\n"
    "Key numbers: MaxIdleConns default = 2 (`High`, `Official`)\n\n"
    "Reusable queries: `SetMaxOpenConns SetMaxIdleConns site:pkg.go.dev`, "
    "`max_connections wait_timeout site:dev.mysql.com`, "
    "`Go MySQL 连接池 生产环境 site:zhihu.com`\n"
)


GOOD_DEEP = (
    "Deep · Partial\n\n"
    "Throughput differences between the three frameworks are within noise for JSON "
    "responses, and the published comparisons that do separate them disclose no hardware.\n\n"
    "Round 1\n"
    "- `Gin Echo Fiber benchmark after:2025-01-01`\n"
    "- `TechEmpower Go framework composite site:techempower.com`\n"
    "- `Fiber fasthttp tradeoff site:github.com`\n\n"
    "Evidence chain status: two independent benchmarks found; neither discloses hardware, "
    "so the methodology link is unsatisfied\n\n"
    "Key evidence: `techempower.com` composite ranking, `github.com` maintainer thread on "
    "fasthttp tradeoffs\n\n"
    "Source assessment: both benchmarks disclose versions but not hardware, "
    "so the ranking is directional only\n\n"
    "Key numbers: composite score gap 12% (`Low`, `Reputable third-party`)\n\n"
    "Reusable queries: `Gin Echo Fiber benchmark after:2025-01-01`, "
    "`TechEmpower Go framework composite site:techempower.com`, "
    "`Fiber fasthttp tradeoff site:github.com`, "
    "`Go framework benchmark hardware disclosed after:2026-01-01` not run, "
    "`fasthttp compatibility net/http middleware` not run\n"
)


class TestReportContract:
    def test_good_report_is_clean(self):
        errors = [f for f in L.lint_report(GOOD_QUICK) if f.severity == "error"]
        assert not errors, errors

    def test_gs001_missing_mode(self):
        fires("GS001", L.lint_report(GOOD_QUICK.replace("Quick · Full", "Full")))

    def test_gs002_missing_degradation(self):
        fires("GS002", L.lint_report(GOOD_QUICK.replace("Quick · Full", "Quick")))

    def test_gs003_over_budget(self):
        mutated = replace_all(
            GOOD_QUICK,
            "- Primary: `Go sync.Pool garbage collection`\n",
            "- Primary: `Go sync.Pool garbage collection`\n"
            "- Expansion: `Go sync Pool victim cache internals`\n",
        )
        fires("GS003", L.lint_report(mutated))

    def test_gs003_unknown_when_no_query_list_exists(self):
        text = (
            "Quick · Full\n\nAnswer text only.\n\n"
            "Reusable queries: `one two three`, `four five six`\n"
            "Source: https://go.dev/x\n"
        )
        hit = fires("GS003", L.lint_report(text))
        assert hit[0].severity == "unknown", (
            "a check that cannot see its subject must report unknown, not pass"
        )

    def test_gs004_too_few_reusable_queries(self):
        mutated = GOOD_QUICK.replace(
            "Reusable queries: `sync.Pool GC behavior site:go.dev`, "
            "`Go sync.Pool garbage collection`",
            "Reusable queries: `sync.Pool GC behavior site:go.dev`",
        )
        fires("GS004", L.lint_report(mutated))

    def test_gs005_missing_confidence_label(self):
        mutated = replace_all(GOOD_QUICK, "(`High`, `Official`)", "(`Official`)")
        fires("GS005", L.lint_report(mutated))

    def test_gs006_missing_tier_label(self):
        mutated = replace_all(GOOD_QUICK, "(`High`, `Official`)", "(`High`)")
        fires("GS006", L.lint_report(mutated))

    def test_gs007_coined_label(self):
        mutated = replace_all(GOOD_QUICK, "(`High`, `Official`)",
                              "(`Medium-High`, `Mixed official + practitioner`)")
        fires("GS007", L.lint_report(mutated))

    def test_gs008_snippet_as_fact(self):
        mutated = GOOD_QUICK + "\nAccording to search results, the answer is X.\n"
        fires("GS008", L.lint_report(mutated))

    def test_gs008_allows_the_anti_example_that_quotes_it(self):
        text = GOOD_QUICK + '\nBAD: "According to search results, the answer is X."\n'
        assert not [f for f in L.lint_report(text) if f.rule == "GS008"]

    def test_gs009_full_without_a_source(self):
        mutated = GOOD_QUICK.replace("Source: https://go.dev/src/sync/pool.go\n\n", "")
        fires("GS009", L.lint_report(mutated))

    def test_gs010_standard_with_one_host(self):
        text = (
            "Standard · Partial\n\nAnswer.\n\nRound 1\n"
            "- `one two three site:go.dev`\n- `four five six`\n\n"
            "Source: https://go.dev/x\n\n"
            "Reusable queries: `one two three site:go.dev`, `four five six`, "
            "`seven eight nine` not run\n"
        )
        fires("GS010", L.lint_report(text))

    # anchor only in the reusable-queries line, not the executed Primary line
    REUSE_LINE = ("Reusable queries: `sync.Pool GC behavior site:go.dev`, "
                  "`Go sync.Pool garbage collection`")

    def test_gs011_unexecuted_query_not_marked(self):
        mutated = replace_all(
            GOOD_QUICK, self.REUSE_LINE, self.REUSE_LINE + ", `sync.Pool internals deep dive`"
        )
        fires("GS011", L.lint_report(mutated))

    def test_gs011_accepts_a_marked_not_run_query(self):
        mutated = replace_all(
            GOOD_QUICK,
            self.REUSE_LINE,
            self.REUSE_LINE + ", `sync.Pool internals deep dive` (not run)",
        )
        assert not [f for f in L.lint_report(mutated) if f.rule == "GS011"]

    def test_gs011_marker_does_not_vouch_for_a_second_query(self):
        """One marked query must not license an unmarked neighbour."""
        mutated = replace_all(
            GOOD_QUICK,
            self.REUSE_LINE,
            self.REUSE_LINE + ", `first extra query here` (not run), `second extra query`",
        )
        hit = fires("GS011", L.lint_report(mutated))
        assert any("second extra query" in f.message for f in hit), hit
        assert not any("first extra query" in f.message for f in hit), hit

    def test_gs012_invalid_query_in_report(self):
        mutated = replace_all(
            GOOD_QUICK,
            "- Primary: `Go sync.Pool garbage collection`",
            "- Primary: `link:go.dev sync Pool garbage collection`",
        )
        fires("GS012", L.lint_report(mutated))

    def test_good_standard_report_is_clean(self):
        errors = [f for f in L.lint_report(GOOD_STANDARD) if f.severity == "error"]
        assert not errors, errors

    def test_gs013_report_with_metadata_but_no_answer(self):
        """The reported counter-example: a Quick/Full report carrying only two queries and
        a stray URL scored zero errors."""
        text = (
            "Quick · Full\n"
            "Round 1\n- `one two three`\n- `four five six`\n"
            "https://example.com/whatever\n"
            "Reusable queries: `one two three`, `four five six`\n"
        )
        rules = {f.rule for f in L.lint_report(text)}
        fires("GS013", L.lint_report(text))
        assert "GS009" in rules, (
            "a bare URL in the body is not a citation, so Full must also fail GS009"
        )

    def test_gs013_accepts_a_terse_but_complete_answer(self):
        """The rule separates "no answer" from "an answer", not short from long. For a factual
        Quick question "The default is 2." is complete, and a threshold tuned above that would
        fire on the good case."""
        terse = (
            "Quick · Full\n"
            "The default is 2.\n"
            "Round 1\n- `SetMaxIdleConns default site:pkg.go.dev`\n"
            "- `database/sql pool defaults`\n"
            "Source: https://pkg.go.dev/database/sql\n"
            "Reusable queries: `SetMaxIdleConns default site:pkg.go.dev`, "
            "`database/sql pool defaults`\n"
        )
        assert "GS013" not in {f.rule for f in L.lint_report(terse)}, L.lint_report(terse)

    def test_gs013_does_not_fire_on_a_conclusion_opening_with_a_field_word(self):
        """A field label is the word *plus its colon*; matching the bare word would swallow
        a real conclusion and report a missing answer that is right there."""
        text = (
            "Quick · Full\n"
            "Queries against the endpoint are capped at 100 requests per second per key.\n"
            "Round 1\n- `one two three`\n- `four five six`\n"
            "Source: https://go.dev/x\n"
            "Reusable queries: `one two three`, `four five six`\n"
        )
        assert "GS013" not in {f.rule for f in L.lint_report(text)}, L.lint_report(text)

    def test_gs009_rejects_a_url_that_is_not_in_a_source_position(self):
        mutated = replace_all(
            GOOD_QUICK,
            "Source: https://go.dev/src/sync/pool.go",
            "See also https://go.dev/src/sync/pool.go",
        )
        fires("GS009", L.lint_report(mutated))

    def test_gs010_fires_on_zero_hosts_not_only_one(self):
        """The reported counter-example: the rule was guarded by `0 < len(hosts)`, so a
        Standard report citing nothing at all skipped the check entirely."""
        text = (
            "Standard · Partial\n"
            "The pool size has to be measured under load because no vendor documents one.\n"
            "Round 1\n- `one two three`\n- `four five six`\n"
            "Evidence chain status: official basis missing\n"
            "Key evidence: none found\n"
            "Reusable queries: `one two three`, `four five six`, `seven eight nine` not run\n"
        )
        hit = fires("GS010", L.lint_report(text))
        assert "0 source host" in hit[0].message, hit[0].message

    def test_gs014_standard_without_evidence_chain(self):
        mutated = replace_all(
            GOOD_STANDARD,
            "Evidence chain status: official basis satisfied; practitioner report single-source\n\n",
            "",
        )
        fires("GS014", L.lint_report(mutated))

    def test_gs015_standard_without_key_evidence(self):
        mutated = replace_all(
            GOOD_STANDARD,
            "Key evidence: `pkg.go.dev/database/sql` documents the defaults, "
            "`dev.mysql.com` documents the server-wide ceiling\n\n",
            "",
        )
        fires("GS015", L.lint_report(mutated))

    def test_gs014_and_gs015_do_not_apply_to_quick(self):
        """Quick marks both fields MAY, so requiring them would contradict the contract."""
        rules = {f.rule for f in L.lint_report(GOOD_QUICK)}
        assert "GS014" not in rules and "GS015" not in rules

    def test_good_deep_report_is_clean(self):
        errors = [f for f in L.lint_report(GOOD_DEEP) if f.severity == "error"]
        assert not errors, errors

    def test_gs016_deep_without_source_assessment(self):
        mutated = replace_all(
            GOOD_DEEP,
            "Source assessment: both benchmarks disclose versions but not hardware, "
            "so the ranking is directional only\n\n",
            "",
        )
        fires("GS016", L.lint_report(mutated))

    def test_gs016_does_not_apply_to_standard(self):
        """The contract marks source assessment SHOULD for Standard, MUST for Deep."""
        assert "GS016" not in {f.rule for f in L.lint_report(GOOD_STANDARD)}


# ── Coverage, derived ──────────────────────────────────────────────────────────


def test_every_rule_is_exercised_by_a_mutation():
    """Derive the uncovered set. A new rule with no mutation fails here."""
    uncovered = sorted(set(L.ALL_RULES) - EXERCISED)
    assert not uncovered, f"rules with no mutation proving they fire: {uncovered}"
