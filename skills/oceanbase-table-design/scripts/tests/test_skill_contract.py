"""Contract tests: pin down structure and rules in SKILL.md and references/ that are
prone to being reverted.

Why this exists: this skill's knowledge is spread across SKILL.md and a dozen-plus
files under references/. `check_consistency.py` handles "has the same rule drifted
across multiple places"; this file handles "is a given rule still present" -- the two
are complementary. Failure modes seen in the past:

  * SKILL.md's index table pointed at `agents/openai.yaml`, which no longer existed,
    but the lint missed all 22 local links because `strip_inline_code` blanked out
    the label of [`x`](x);
  * the auto-increment column rule went a long time without a compatibility-mode
    gate, which would generate illegal DDL in Oracle mode.

Zero LLM dependency; collected by the repo root's `python3 -m pytest skills/`.
Run: python3 -m pytest scripts/tests -q
"""
import importlib.util
import json
import os
import re
import unittest

SKILL_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
SKILL_MD = os.path.join(SKILL_ROOT, "SKILL.md")
REFS = os.path.join(SKILL_ROOT, "references")
SCRIPTS = os.path.join(SKILL_ROOT, "scripts")
MAX_SKILL_LINES = 500

REQUIRED_REFERENCES = [
    "capability-matrix.md",
    "doc-gaps.md",
    "partitioning.md",
    "indexes.md",
    "special-indexes.md",
    "tablegroup.md",
    "storage-format.md",
    "tablet-capacity.md",
    "hotspots.md",
    "anti-patterns.md",
    "verification.md",
    "input-collection.md",
    "output-contract.md",
    "mysql_mode_create_table_syntax.md",
    "oracle_mode_create_table_syntax.md",
]


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def ref(name):
    return read(os.path.join(REFS, name))


def strip_fences(text):
    """Replace fenced code blocks with an equal number of blank lines, used for
    "this assertion must appear in the body text" checks."""
    out, infence = [], False
    for ln in text.split("\n"):
        if ln.lstrip().startswith("```"):
            infence = not infence
            out.append("")
            continue
        out.append("" if infence else ln)
    return "\n".join(out)


SKILL = read(SKILL_MD)

# Only match a genuine scaffold marker: the tag is immediately followed by : ( or -
# (including an HTML comment closed with -->). Discussion prose ("no TODO / FIXME /
# XXX / TBD scaffolding left behind") is followed by `/` or ordinary words, and does
# not match.
SCAFFOLD_RE = re.compile(r"\b(TODO|FIXME|XXX|TBD)\b\s*[:(\-]")


# ─────────────────────────────── Structure ───────────────────────────────

class FrontmatterTests(unittest.TestCase):
    def setUp(self):
        m = re.search(r"\A---\n(.*?)\n---", SKILL, re.DOTALL)
        self.assertIsNotNone(m, "SKILL.md is missing YAML frontmatter")
        self.fm = m.group(1)

    def test_name_matches_directory(self):
        m = re.search(r"^name:\s*(\S+)", self.fm, re.M)
        self.assertIsNotNone(m, "frontmatter is missing name")
        self.assertEqual(m.group(1), os.path.basename(SKILL_ROOT))

    def test_name_is_kebab_case(self):
        m = re.search(r"^name:\s*(\S+)", self.fm, re.M)
        self.assertRegex(m.group(1), r"^[a-z0-9]+(-[a-z0-9]+)*$")

    def test_description_present_and_bounded(self):
        self.assertIn("description:", self.fm)
        # description is the sole basis for Claude's automatic triggering, capped at 1024 characters
        body = self.fm.split("description:", 1)[1]
        self.assertLessEqual(len(body), 1024,
                             "description exceeds the 1024-character limit")

    def test_description_has_no_xml_brackets(self):
        body = self.fm.split("description:", 1)[1]
        self.assertNotIn("<", body)
        self.assertNotIn(">", body)


class SkillSizeTests(unittest.TestCase):
    def test_skill_md_within_line_budget(self):
        # Aligned with `wc -l`: count newline characters, not the number of
        # split("\n") segments (the latter over-counts by one when the file ends
        # in a newline, which would disagree with run_regression.sh's verdict).
        n = SKILL.count("\n")
        self.assertLessEqual(
            n, MAX_SKILL_LINES,
            f"SKILL.md has {n} lines, over the {MAX_SKILL_LINES}-line limit. "
            f"Move verbatim blocks to references/ and replace with a contract-style reference.")


class ReferenceIntegrityTests(unittest.TestCase):
    def test_all_required_references_exist(self):
        for name in REQUIRED_REFERENCES:
            self.assertTrue(os.path.exists(os.path.join(REFS, name)),
                            f"missing references/{name}")

    def test_every_reference_file_is_indexed_in_skill(self):
        for name in sorted(os.listdir(REFS)):
            if not name.endswith(".md"):
                continue
            self.assertIn(f"references/{name}", SKILL,
                          f"references/{name} is not registered in SKILL.md's Section 10 index")

    def test_every_local_link_in_skill_resolves(self):
        """A link check independent of check_consistency.

        This test exists because of a real miss: the linter first blanked inline
        `code` to an empty string, so [`references/x.md`](references/x.md)'s label
        became `[]`, the link regex could not match, and all 22 local links were
        **entirely** invisible to check E. This test matches directly against the
        raw text, with no masking at all.
        """
        targets = re.findall(r"\[[^\]]+\]\((?!https?://|#)([^)#]+)", SKILL)
        self.assertGreaterEqual(len(targets), 20,
                                "too few local links extracted, the regex may be broken")
        missing = [t for t in targets
                   if not os.path.exists(os.path.join(SKILL_ROOT, t.strip()))]
        self.assertEqual(missing, [], f"local links in SKILL.md point at paths that do not exist: {missing}")

    def test_no_reference_to_nonexistent_agents_dir(self):
        """agents/openai.yaml was once indexed but the file does not exist. Must not reappear."""
        self.assertNotIn("agents/openai.yaml", SKILL)

    def test_no_scaffold_artifacts(self):
        """No TODO / FIXME / XXX / TBD leftovers allowed.

        Only matches a **genuine scaffold marker** (`TODO:` / `TODO(x)` / `FIXME -`),
        not prose that **discusses these markers**, such as "no TODO / FIXME / XXX /
        TBD scaffolding left behind." Otherwise this very check would flag the
        sentence that explains it -- which is exactly how the first version of
        COVERAGE.md was misjudged.
        """
        for root, dirs, files in os.walk(SKILL_ROOT):
            dirs[:] = [d for d in dirs if not d.startswith(".")
                       and d != "__pycache__"]
            for fn in files:
                if not fn.endswith(".md"):
                    continue
                path = os.path.join(root, fn)
                hits = SCAFFOLD_RE.findall(read(path))
                self.assertEqual(
                    hits, [],
                    f"{os.path.relpath(path, SKILL_ROOT)} contains scaffold leftovers {hits}")

    def test_scaffold_regex_actually_catches_scaffolding(self):
        """A negative control for the previous test -- the narrowed regex must not let a real leftover through either."""
        for sample in ("TODO: fill in this section",
                       "FIXME(john) needs a change here",
                       "<!-- TODO -->",
                       "XXX: temporary workaround",
                       "TBD: undecided"):
            self.assertTrue(SCAFFOLD_RE.search(sample),
                            f"the narrowed regex missed a genuine leftover: {sample!r}")
        for sample in ("no TODO / FIXME / XXX / TBD scaffolding left behind",
                       "TODO, FIXME and similar markers are forbidden"):
            self.assertFalse(SCAFFOLD_RE.search(sample),
                             f"the regex misjudged discussion prose: {sample!r}")


class RegressionRunnerTests(unittest.TestCase):
    def test_run_regression_exists_and_is_executable(self):
        p = os.path.join(SCRIPTS, "run_regression.sh")
        self.assertTrue(os.path.exists(p), "missing scripts/run_regression.sh")
        self.assertTrue(os.access(p, os.X_OK), "run_regression.sh is not executable")

    def test_run_regression_invokes_every_static_check(self):
        text = read(os.path.join(SCRIPTS, "run_regression.sh"))
        for needed in ("check_consistency.py",
                       "check_consistency.py --self-test",
                       "run_cases.py --validate",
                       "estimate_tablets.py --self-test",
                       "check_negative_log.py --self-test",
                       "run_integration.sh --self-test",
                       "gen_toc.py --self-test",
                       "scripts/tests"):
            self.assertIn(needed, text,
                          f"run_regression.sh does not run {needed}")

    def test_every_script_with_a_self_test_is_wired_in(self):
        """Derived, not listed: an unwired self-test is dead code that reads as coverage.

        The list above can go stale silently. This walks the scripts directory instead,
        so adding a `--self-test` to any script and forgetting the runner fails here.
        """
        runner = read(os.path.join(SCRIPTS, "run_regression.sh"))
        for fn in sorted(os.listdir(SCRIPTS)):
            if not fn.endswith((".py", ".sh")) or fn == "run_regression.sh":
                continue
            body = read(os.path.join(SCRIPTS, fn))
            if '"--self-test"' not in body and "--self-test)" not in body:
                continue
            self.assertIn(
                f"{fn} --self-test", runner,
                f"{fn} has a --self-test that run_regression.sh never invokes")

    def test_size_budget_covers_words_not_just_lines(self):
        """A line budget alone lets sections grow verbose without growing the file."""
        text = read(os.path.join(SCRIPTS, "run_regression.sh"))
        self.assertIn("wc -w", text)
        self.assertIn("5000", text)

    def test_coverage_doc_exists(self):
        self.assertTrue(
            os.path.exists(os.path.join(SCRIPTS, "tests", "COVERAGE.md")))


# ─────────────────── Rule pins: L0 and the compatibility-mode gate ───────────────────

class L0Tests(unittest.TestCase):
    """L0 means "the server rejects the statement". Anything that merely wastes
    resources or defeats pruning belongs in the L1-B block instead.

    These are per-subject assertions rather than a bare item count: a count alone is
    satisfied by any twelve items, so an item could be swapped for an unrelated one
    and the pin would stay green. Each subject below is named individually, and the
    tier boundary is asserted in both directions.
    """

    #: subject -> a probe that must appear in the L0 block. One entry per hard
    #: constraint; deleting a constraint now names itself in the failure message.
    L0_SUBJECTS = {
        "partition-key vs. primary/unique key three-branch rule": r"subset of the primary key",
        "unique index must cover the partition key": r"unique index must include all partition key",
        "Community Edition has no Oracle mode": r"edition = community",
        "Oracle mode has no PARTITION BY KEY": r"no `PARTITION BY KEY`",
        "MySQL HASH/RANGE/LIST key type": r"integer or YEAR type",
        "mode-dependent partition ceiling": r"max_partition_num",
        "SIZE is a RANGE modifier only": r"SIZE\('\.\.\.'\)",
        "RANGE boundaries strictly increasing": r"VALUES LESS THAN",
        "version/edition feature gate": r"below the feature requirement",
        "clause order": r"table option`? ?→ ?`?partition option",
        "AUTO_INCREMENT is MySQL-only": r"AUTO_INCREMENT` family is exclusive to MySQL mode",
    }

    def setUp(self):
        m = re.search(r"### L0 Hard Constraint Checklist\n(.*?)\n### ", SKILL, re.DOTALL)
        self.assertIsNotNone(m, "could not find the L0 Hard Constraint Checklist")
        self.block = m.group(1)
        b = re.search(r"### L1-B Design Blocker Checklist\n(.*?)\n(?:---|## )", SKILL, re.DOTALL)
        self.assertIsNotNone(b, "could not find the L1-B Design Blocker Checklist")
        self.blocker_block = b.group(1)

    def test_every_l0_subject_still_present(self):
        for subject, probe in self.L0_SUBJECTS.items():
            with self.subTest(subject=subject):
                self.assertRegex(
                    self.block, probe,
                    f"L0 no longer covers: {subject}. Was the item deleted, or "
                    f"reworded past its probe?")

    def test_l0_item_count_matches_subject_list(self):
        items = re.findall(r"^\s*(\d+)\.\s", self.block, re.M)
        self.assertEqual(
            len(items), len(self.L0_SUBJECTS),
            "the L0 item count and the subject list above have drifted -- add or remove "
            "an L0_SUBJECTS entry in the same commit that changes the checklist")

    def test_l0_covers_autoinc_compat_mode_gate(self):
        self.assertIn("AUTO_INCREMENT_MODE", self.block)
        self.assertIn("IDENTITY", self.block)

    def test_ndv_rule_is_not_l0(self):
        """Regression pin for the 2026-08-12 review finding.

        NDV <= partition count creates a legal table, so classifying it L0 (which
        blocks DDL generation) contradicts this skill's own definition of L0 and
        rejects deliberately sparse designs. It must live in the L1-B block.
        """
        for banned in ("NDV", "distinct_count", "cardinality"):
            self.assertNotIn(
                banned, self.block,
                f"{banned!r} is back in the L0 checklist -- partition-key cardinality is "
                f"an L1-B design blocker (legal DDL), not a hard constraint")

    def test_ndv_rule_is_in_the_blocker_block(self):
        self.assertRegex(self.blocker_block, r"NDV|cardinality")
        self.assertIn("partition count", self.blocker_block)

    def test_blocker_tier_still_emits_ddl(self):
        """The whole point of the tier: a blocker must not stop DDL generation."""
        self.assertRegex(
            self.blocker_block, r"execute successfully|legal",
            "the L1-B block no longer states that these statements are legal")
        self.assertIn("rule_tier: L1_blocker", SKILL,
                      "the machine tag for the blocker tier is missing")
        self.assertIn("Never grounds for calling a design infeasible", SKILL)

    def test_blocker_tier_has_an_override_path(self):
        """Without a documented override, "default fail" silently becomes "always fail"."""
        self.assertIn("accepted_with_reason", SKILL)
        self.assertIn("accepted_reason", ref("partitioning.md"))

    def test_four_criteria_are_tier_annotated(self):
        """Only the key-type criterion is enforced by the parser; the other three are
        design guidance. Presenting all four as one hard gate is the original defect."""
        p = ref("partitioning.md")
        self.assertIn("L1-B", p)
        self.assertRegex(
            p, r"only criterion 3 is enforced|Only criterion 3 is enforced",
            "partitioning.md §2.1 no longer states which of the four criteria the server "
            "actually enforces")


class AutoIncrementModeGateTests(unittest.TestCase):
    """The auto-increment column rule must branch by compatibility mode -- this is a
    paired assertion, both sides must be present.

    Either side alone is meaningless: saying only "Oracle has no AUTO_INCREMENT"
    without giving IDENTITY leaves the Agent stuck; giving only IDENTITY without
    forbidding AUTO_INCREMENT leaves the Agent free to copy the MySQL form anyway.
    """
    def test_oracle_bnf_genuinely_lacks_auto_increment(self):
        """The factual basis for the rule: the Oracle BNF mirror really has no AUTO_INCREMENT.

        Only the content inside the fence is kept -- the file's introductory prose mentions the term too.
        """
        text = ref("oracle_mode_create_table_syntax.md")
        keep, infence = [], False
        for ln in text.split("\n"):
            if ln.lstrip().startswith("```"):
                infence = not infence
                continue
            if infence:
                keep.append(ln)
        fenced = "\n".join(keep)
        self.assertNotIn("AUTO_INCREMENT", fenced.upper().replace("AUTO_INCREMENT_MODE", ""),
                         "AUTO_INCREMENT appears in the Oracle BNF mirror -- this rule's factual "
                         "basis no longer holds, re-check the official documentation")

    def test_oracle_bnf_has_identity(self):
        self.assertIn("AS IDENTITY", ref("oracle_mode_create_table_syntax.md"))

    def test_capability_matrix_splits_by_compat_mode(self):
        cm = ref("capability-matrix.md")
        self.assertIn("GENERATED BY DEFAULT AS IDENTITY", cm)
        self.assertIn("CREATE SEQUENCE", cm)

    def test_doc_gaps_scopes_autoinc_to_mysql_mode(self):
        dg = ref("doc-gaps.md")
        self.assertIn("MySQL mode only", dg)
        self.assertIn("IDENTITY", dg)

    def test_skill_step11_gates_by_mode(self):
        self.assertIn("compatibility-mode gate first", SKILL)

    def test_prohibition_listed(self):
        self.assertIn(
            "Write `AUTO_INCREMENT` / `AUTO_INCREMENT_MODE` / `auto_increment_cache_size` in Oracle-mode DDL",
            SKILL)

    def test_anti_pattern_registered(self):
        self.assertIn("AUTO_INCREMENT_MODE", ref("anti-patterns.md"))

    def test_cache_size_explains_gap_magnitude(self):
        """The source of the skip magnitude must be stated, otherwise "use BIGINT" becomes an unsupported slogan."""
        self.assertIn("AUTO_INCREMENT_CACHE_SIZE", ref("capability-matrix.md"))
        self.assertIn("1000000", ref("capability-matrix.md"))

    def test_nocache_scoped_to_oracle_sequences(self):
        """Regression pin for the 2026-08-12 review finding.

        Three files recommended `NOCACHE` as the MySQL way to suppress auto-increment
        gaps. The MySQL table option is `auto_increment_cache_size [=] INT_VALUE` -- an
        integer -- so that advice produces a syntax error, not a slower-but-gapless
        table. The mirror image of the Oracle-side gate, and it needs the same pin.
        """
        dg = ref("doc-gaps.md")
        self.assertIn("2.3.1", dg,
                      "doc-gaps.md lost the section that scopes NOCACHE by mode")
        self.assertIn("auto_increment_cache_size [=] INT_VALUE", dg,
                      "the integer-only production is the factual basis for the rule")
        self.assertIn("CREATE SEQUENCE", dg)

    def test_mysql_bnf_has_no_nocache(self):
        """The factual basis: if a refreshed BNF ever adds NOCACHE, this rule is void."""
        text = ref("mysql_mode_create_table_syntax.md")
        keep, infence = [], False
        for ln in text.split("\n"):
            if ln.lstrip().startswith("```"):
                infence = not infence
                continue
            if infence:
                keep.append(ln)
        self.assertNotIn(
            "NOCACHE", "\n".join(keep).upper(),
            "NOCACHE appears in the MySQL BNF mirror -- re-check the official docs, "
            "doc-gaps.md §2.3.1 depends on its absence")

    def test_nocache_prohibition_is_a_behavioral_constraint(self):
        self.assertIn("Write `NOCACHE` in MySQL-mode DDL", SKILL,
                      "the must-not list lost the NOCACHE prohibition")

    def test_nocache_disable_value_stays_unverified(self):
        """Claiming a specific value disables caching would be an unverified promise.

        Deliberately a single exact phrase and its negation, not an `|` of synonyms:
        the first draft of this test offered an alternative that also matched a
        neighbouring sentence, so inverting the claim left the test green. The mutation
        sweep caught it. A reworded corpus now breaks the mutation's `find` string
        loudly instead of quietly disarming the assertion here.
        """
        dg = ref("doc-gaps.md")
        self.assertIn(
            "disables caching entirely is `unverified`", dg,
            "the disable-caching claim is no longer tagged unverified")
        self.assertNotRegex(
            dg, r"disables caching entirely is (?:confirmed|verified|documented)\b",
            "doc-gaps.md now claims the disable-caching value is settled -- it was "
            "never confirmed on an instance")


class TenantDefaultGateTests(unittest.TestCase):
    """"No Column Group means row storage" was once treated as an unconditional fact."""

    def test_step0_collects_tenant_defaults(self):
        self.assertIn("tenant_defaults", SKILL)
        self.assertIn("default_table_store_format", SKILL)

    def test_storage_format_documents_the_trap(self):
        sf = ref("storage-format.md")
        self.assertIn("default_table_store_format", sf)
        for value in ("row", "column", "compound"):
            self.assertIn(value, sf)

    def test_default_value_is_stated_as_row(self):
        """The default value must be stated as row, otherwise the scope in which
        "no clause means row storage" holds is left unclear.

        Markdown emphasis markers (`**`, backticks) are stripped first, otherwise a
        perfectly correct form like "default **`row`**" would fail to match because
        of the markup sitting in the middle.
        """
        for name in ("storage-format.md", "capability-matrix.md"):
            plain = re.sub(r"[`*]", "", ref(name))
            self.assertRegex(
                plain, r"default\s*row|row \(default\)",
                f"{name} does not state that the default of default_table_store_format is row")

    def test_auto_append_semantics_documented(self):
        """The official semantics is "the clause is appended automatically," not
        "the storage engine changes" -- stating this is what makes it possible to
        explain why writing the clause explicitly makes the table immune to this
        parameter."""
        sf = ref("storage-format.md").lower()
        self.assertIn("column group(each column)", sf)
        self.assertIn("column group(all columns, each column)", sf)

    def test_official_boundary_conditions_documented(self):
        for text in (ref("storage-format.md"), ref("capability-matrix.md")):
            self.assertIn("index tables", text)
            self.assertIn("user tenant", text)

    def test_min_version_stated(self):
        self.assertIn("V4.3.0", ref("capability-matrix.md"))

    def test_explicit_write_is_the_recommended_workaround(self):
        sf = ref("storage-format.md")
        self.assertIn("WITH COLUMN GROUP(all columns)", sf)
        # the recommendation must be anchored to the official basis (once the clause
        # is written the parameter no longer applies), not to intuition
        self.assertIn("no longer applies", sf)

    def test_v1_static_check_exists(self):
        self.assertIn("tenant_default_gate", ref("verification.md"))

    def test_collection_sql_provided(self):
        self.assertIn("store_format", ref("input-collection.md"))

    def test_anti_pattern_registered(self):
        self.assertIn("default_table_store_format", ref("anti-patterns.md"))


class PartitionKeySelectionTests(unittest.TestCase):
    def test_ndv_rule_in_partitioning(self):
        p = ref("partitioning.md")
        self.assertIn("ndv_vs_partition_count", p)
        self.assertIn("distinct_count", p)

    def test_four_criteria_present(self):
        p = strip_fences(ref("partitioning.md"))
        self.assertIn("empty partitions", p)

    def test_hash_high_cardinality_list_low_cardinality_contrast(self):
        """The two criteria, which point in opposite directions, must both be present -- otherwise you get "HASH-partition by status code."""
        for text in (SKILL, ref("partitioning.md")):
            self.assertRegex(text, r"low.{0,4}cardinality", re.I)
            self.assertIn("LIST", text)

    def test_missing_stat_yields_unverified_not_pass(self):
        self.assertIn("must not default to pass", SKILL)


class StorageArchitectureTests(unittest.TestCase):
    def test_four_htap_tiers_documented(self):
        sf = ref("storage-format.md")
        self.assertIn("columnstore index", sf)
        self.assertIn("row-store index", sf)
        self.assertIn("30%", sf)

    def test_index_level_column_group_is_c3(self):
        """Officially given architecture and overhead, but no syntax -> must not go into the primary DDL."""
        self.assertIn("C3", ref("storage-format.md"))
        self.assertIn("candidate_ddl", ref("storage-format.md"))

    def test_columnstore_replica_consistency_model_stated(self):
        self.assertIn("eventually consistent", ref("storage-format.md"))

    def test_row_column_redundant_overhead_still_documented(self):
        self.assertIn("2×", ref("storage-format.md"))


class TableModeSemanticsTests(unittest.TestCase):
    def test_major_compaction_is_the_axis(self):
        sf = ref("storage-format.md")
        self.assertIn("major compaction", sf)
        for v in ("NORMAL", "QUEUING", "MODERATE", "SUPER", "EXTREME"):
            self.assertIn(v, sf)

    def test_all_but_normal_are_queuing_tables(self):
        self.assertIn("except `NORMAL`", ref("storage-format.md"))

    def test_queue_strength_framing_is_rejected_not_used(self):
        """""Queuing intensity" may only appear in a corrective context."""
        for name in ("storage-format.md",):
            body = strip_fences(ref(name))
            lines = body.split("\n")
            for i, ln in enumerate(lines):
                if "queue intensity" not in ln.lower() and "queuing intensity" not in ln.lower():
                    continue
                window = "\n".join(lines[max(0, i - 3):i + 4]).lower()
                self.assertTrue(
                    any(g in window for g in ("not", "wrong", "misleads", "incorrect")),
                    f"{name}:{i+1} 'queue/queuing intensity' appears outside a corrective context")


class HotspotDirectionTests(unittest.TestCase):
    def test_read_write_split_is_first(self):
        h = ref("hotspots.md")
        self.assertIn("Read-intensive", h)
        self.assertIn("Write-intensive", h)

    def test_read_hot_row_type_exists(self):
        self.assertIn("read_hot_row", ref("hotspots.md"))
        self.assertIn("read_hot_row", SKILL)

    def test_read_hotspot_does_not_get_bucket_advice(self):
        h = ref("hotspots.md")
        self.assertIn("do not add partitions", h)

    def test_replicated_table_is_the_read_hotspot_answer(self):
        self.assertIn("DUPLICATE_SCOPE", ref("hotspots.md"))

    def test_missing_top1_share_forbids_none_verdict(self):
        self.assertIn("no hotspot", ref("hotspots.md"))

    def test_contract_supports_multiple_types(self):
        self.assertIn("types:", ref("hotspots.md"))


class SpecialIndexTests(unittest.TestCase):
    def test_predicate_whitelist_present(self):
        si = ref("special-indexes.md")
        for pred in ("MEMBER OF", "JSON_CONTAINS", "JSON_OVERLAPS"):
            self.assertIn(pred, si)

    def test_existing_table_switch_documented(self):
        self.assertIn("_enable_add_fulltext_index_to_existing_table",
                      ref("special-indexes.md"))

    def test_chinese_corpus_cannot_use_space_parser(self):
        self.assertIn("must not use `SPACE`", ref("special-indexes.md"))

    def test_explain_judged_by_name_not_operator_alone(self):
        """Even after a multi-value index hit, the operator name can still read TABLE FULL SCAN -- the easiest place to misjudge."""
        si = ref("special-indexes.md")
        self.assertIn("TEXT RETRIEVAL SCAN", si)
        self.assertIn("SYS_NC_mvi_", si)
        self.assertIn("operator name", si)

    def test_referenced_from_skill_step6(self):
        self.assertIn("references/special-indexes.md", SKILL)

    def test_referenced_from_indexes(self):
        self.assertIn("special-indexes.md", ref("indexes.md"))

    def test_autosplit_interaction_flagged(self):
        self.assertRegex(ref("special-indexes.md"),
                          r"automatic partition|auto-split|automatic splitting")


class InputCollectionTests(unittest.TestCase):
    """An input gate with no collection method just leaves the user stuck or making up numbers."""

    def test_audit_view_query_present(self):
        ic = ref("input-collection.md")
        self.assertIn("GV$OB_SQL_AUDIT", ic)
        self.assertIn("memstore_read_row_count", ic)

    def test_every_hard_required_input_has_a_collection_path(self):
        ic = ref("input-collection.md")
        for field in ("frequency_share", "distinct_count", "top1_key_share",
                      "delete_qps", "steady_row_count"):
            self.assertIn(field, ic, f"{field} has no corresponding collection instructions")

    def test_tablet_and_tenant_queries_present(self):
        ic = ref("input-collection.md")
        self.assertIn("DBA_OB_TABLETS", ic)
        self.assertIn("GV$OB_TENANT_RESOURCE_LIMIT", ic)

    def test_workload_form_moved_here(self):
        ic = ref("input-collection.md")
        self.assertIn("workload:", ic)
        self.assertIn("access_patterns", ic)

    def test_degradation_table_present(self):
        self.assertIn("Graceful Degradation", ref("input-collection.md"))

    def test_skill_requires_sql_when_asking(self):
        self.assertIn("SQL to obtain", SKILL)

    def test_review_mode_also_points_at_collection(self):
        m = re.search(r"## 6\. Schema Review Mode(.*?)\n## ", SKILL, re.DOTALL)
        self.assertIsNotNone(m)
        self.assertIn("input-collection.md", m.group(1))


class OfficialConflictTests(unittest.TestCase):
    """When two official documents say opposite things, do not pick a side -- route by scenario."""

    def test_conflict_section_exists(self):
        self.assertIn("official documents contradict each other", ref("doc-gaps.md"))

    def test_primary_key_conflict_recorded(self):
        dg = ref("doc-gaps.md")
        self.assertIn("Columnstore table without a primary key", dg)
        self.assertIn("Every table must have a primary key", dg)

    def test_autoinc_type_conflict_recorded(self):
        self.assertIn("prohibited", ref("doc-gaps.md").lower())

    def test_oracle_subset_rule_stays_unverified(self):
        cm = ref("capability-matrix.md")
        self.assertRegex(cm, r"primary key need not (?:include|contain) the partition key")
        self.assertIn("unverified", cm)

    def test_prohibition_against_picking_a_side(self):
        self.assertRegex(SKILL, r"pick(?:ing)? one side")


class TabletCapacityTests(unittest.TestCase):
    """Added 2026-08-12 after the mutation sweep found this file completely unpinned.

    Renaming `_max_tablet_cnt_per_gb` throughout tablet-capacity.md broke no test at
    all. `check_consistency.py` does have a paired assertion for this parameter, but
    it is *conditional on the name matching* -- rename the subject and the guard stops
    firing rather than failing. That is a fail-open guard, so the name needs a positive
    assertion somewhere, which is here.
    """

    def test_tablet_formula_documented(self):
        tc = ref("tablet-capacity.md")
        for param in ("_max_tablet_cnt_per_gb", "_storage_meta_memory_limit_percentage"):
            self.assertIn(param, tc,
                          f"{param} is gone from tablet-capacity.md -- the Tablet ceiling "
                          f"formula has lost the parameter it is computed from")
        self.assertIn("20000", tc, "the default of _max_tablet_cnt_per_gb is missing")

    def test_ceiling_takes_the_smaller_of_two_formulas(self):
        """One formula alone silently over-reports headroom whenever the other binds."""
        tc = ref("tablet-capacity.md")
        self.assertIn("Formula A", tc)
        self.assertIn("Formula B", tc)
        self.assertRegex(
            SKILL, r"taking the \*\*smaller\*\*|min\(",
            "SKILL.md Step 10 no longer says the ceiling is the smaller of the two formulas")

    def test_comparison_is_per_node_not_cluster_total(self):
        """Comparing a cluster-wide total against a per-node ceiling passes designs that
        will not fit on any single OBServer."""
        for text in (SKILL, ref("tablet-capacity.md")):
            self.assertRegex(text, r"per[- ]node|per OBServer")
        self.assertIn("unit_num", SKILL)

    def test_tablets_summed_across_indexes(self):
        self.assertRegex(ref("tablet-capacity.md"), r"global index|local index")


class IntegrationStatusTests(unittest.TestCase):
    """The "not yet run" disclaimer must track reality in both directions.

    A stale disclaimer is the more dangerous drift: once the suite HAS been run, a
    README still saying "not yet executed" makes the team re-run it, while a README
    saying "verified" with no results file makes them trust something that never ran.
    Both are checked against the presence of results on disk rather than against prose.
    """

    IT_DIR = os.path.join(SKILL_ROOT, "tests", "integration")

    def _has_results(self):
        """True only for results from a real run against an instance.

        A `--dry-run` produces a summary that looks exactly like a real one apart from
        a `dry_run: 1` line, and `overall: PASS` on top of it. Counting that as "the
        suite has been run" is the same error as reading a skipped test as a passing
        one -- it would push someone to mark the real-database layer verified on the
        strength of a run that never touched a database. So a dry-run summary is
        explicitly not evidence here.
        """
        d = os.path.join(self.IT_DIR, "results")
        if not os.path.isdir(d):
            return False
        for root, _dirs, files in os.walk(d):
            for fn in files:
                if fn.startswith("."):
                    continue
                path = os.path.join(root, fn)
                try:
                    with open(path, encoding="utf-8", errors="replace") as f:
                        body = f.read()
                except OSError:
                    continue
                if re.search(r"^\s*dry_run:\s*1\s*$", body, re.M):
                    continue                      # dry run: proves nothing about an instance
                if "DRY-RUN" in body and "dry_run:" in body:
                    continue
                return True
        return False

    def test_dry_run_summary_is_not_counted_as_a_real_run(self):
        """Negative control for the helper above.

        Without this, `_has_results` could quietly start returning False for everything
        (a bad path, a changed layout) and `test_status_matches_whether_results_exist`
        would pass forever by checking nothing.
        """
        import tempfile
        dry = ("version: 4.5.0\nmode: mysql\ndry_run: 1\noverall: PASS\n"
               "  positive  mysql_base.sql  DRY-RUN\n")
        real = ("version: 4.5.0\nmode: mysql\ndry_run: 0\noverall: PASS\n"
                "  positive  mysql_base.sql  OK\n")
        with tempfile.TemporaryDirectory() as tmp:
            class Probe(IntegrationStatusTests):
                IT_DIR = tmp
            os.makedirs(os.path.join(tmp, "results", "4.5.0-mysql"))
            p = os.path.join(tmp, "results", "4.5.0-mysql", "summary.txt")
            with open(p, "w", encoding="utf-8") as f:
                f.write(dry)
            self.assertFalse(Probe("test_dry_run_summary_is_not_counted_as_a_real_run")._has_results(),
                             "a dry-run summary is being counted as a real run")
            with open(p, "w", encoding="utf-8") as f:
                f.write(real)
            self.assertTrue(Probe("test_dry_run_summary_is_not_counted_as_a_real_run")._has_results(),
                            "a real run is not being detected, so the status check is inert")

    def test_status_matches_whether_results_exist(self):
        readme = read(os.path.join(self.IT_DIR, "README.md"))
        claims_unrun = "Not yet executed" in readme
        if self._has_results():
            self.assertFalse(
                claims_unrun,
                "tests/integration/results/ has content but the README still says "
                "'Not yet executed' -- backfill the findings and update the status table")
        else:
            self.assertTrue(
                claims_unrun,
                "no results on disk, so the README must still say 'Not yet executed' -- "
                "never mark the real-database layer verified from reasoning alone")

    def test_results_default_path_is_skill_relative(self):
        """Regression pin: the default output path must not depend on the caller's cwd.

        `OUT` defaulted to the relative "tests/integration/results", resolved against
        whatever directory the script was launched from, while `SQLDIR` was correctly
        derived from the script's own location. A `--dry-run` from the repo root
        therefore created a stray results tree beside the repo's real directories --
        outside the skill, and outside the `.gitignore` that was meant to cover it.
        """
        sh = read(os.path.join(SCRIPTS, "run_integration.sh"))
        self.assertNotRegex(
            sh, r'OUT="tests/integration/results"',
            "the results default is cwd-relative again; resolve it from $ROOT instead")
        self.assertIn(
            '${OUT:=$ROOT/tests/integration/results}', sh,
            "the results default is no longer anchored to the skill directory")

    def test_generated_results_are_gitignored(self):
        gi = read(os.path.join(SKILL_ROOT, ".gitignore"))
        self.assertIn("tests/integration/results/", gi)

    def test_skill_repeats_the_not_run_caveat(self):
        """SKILL.md is what the Agent reads; the caveat has to be there, not only here."""
        self.assertIn("not yet run", SKILL)

    def test_unverified_claims_name_a_real_confirmation_path(self):
        """A confirmation path pointing at a file that does not cover the claim is a
        dead end dressed as a plan.

        The auto-increment cache claim in doc-gaps.md §2.3.1 sends the reader to
        mysql_probe.sql, so that probe must actually exercise the option.
        """
        dg = ref("doc-gaps.md")
        self.assertIn("mysql_probe.sql", dg)
        probe = read(os.path.join(self.IT_DIR, "mysql_probe.sql"))
        self.assertIn(
            "AUTO_INCREMENT_CACHE_SIZE", probe,
            "doc-gaps.md sends the cache-size question to mysql_probe.sql, but that "
            "probe never sets the option -- the confirmation path is dangling")
        self.assertIn(
            "NOCACHE", probe,
            "the probe should also record the error a bare NOCACHE produces, since that "
            "is the evidence for the L0 statement")


class OutputContractTests(unittest.TestCase):
    def test_contract_file_lists_all_checks(self):
        oc = ref("output-contract.md")
        for key in ("capability_matrix", "tenant_defaults", "autoinc_mode_gate",
                    "key_constraints", "unique_key_constraint",
                    "partition_key_selection", "partition_pruning",
                    "distributed_txn", "hotspot", "special_index",
                    "table_group", "capacity"):
            self.assertIn(f"{key}:", oc, f"checks is missing {key}")

    def test_evidence_rule_kept(self):
        self.assertIn("without evidence", ref("output-contract.md"))
        self.assertIn("without evidence", SKILL)

    def test_no_pseudo_precise_score(self):
        self.assertIn("false precision", ref("output-contract.md"))

    def test_tablegroup_risk_is_version_branched(self):
        oc = ref("output-contract.md")
        self.assertIn("V4.4.2 BP1", oc)
        self.assertIn("must not be reused across", oc)

    def test_skill_points_at_contract_file(self):
        self.assertIn("references/output-contract.md", SKILL)


class AntiPatternTests(unittest.TestCase):
    def test_count_matches_between_skill_and_reference(self):
        ap = ref("anti-patterns.md")
        items = re.findall(r"^(\d+)\.\s\*\*", ap, re.M)
        self.assertGreaterEqual(len(items), 26)
        n = max(int(i) for i in items)
        self.assertIn(f"{n} anti-patterns", SKILL,
                      f"anti-patterns.md has {n} items, but SKILL.md's Section 7 states a different number")

    def test_new_anti_patterns_present(self):
        ap = ref("anti-patterns.md")
        for needle in ("AUTO_INCREMENT_MODE", "default_table_store_format",
                       "queuing intensity", "read **hotspot", "special-indexes.md",
                       "input-collection.md"):
            self.assertIn(needle, ap)


# ───────────────── The validator's own validator: the linter's own regression ─────────────────

def _load_linter():
    path = os.path.join(SCRIPTS, "check_consistency.py")
    spec = importlib.util.spec_from_file_location("ob_check_consistency", path)
    mod = importlib.util.module_from_spec(spec)
    # This module uses plain structures beyond dataclass/annotations, so a direct
    # exec is fine; it is still registered into sys.modules first, in case a
    # dataclass is introduced later and hits the by-path-loading pitfall.
    import sys
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


class CountClaimTests(unittest.TestCase):
    """Numbers written in prose about things the repo can count.

    Added 2026-08-12 after a review found two that had silently gone stale:
    `verification.md` said the runner "runs six checks" when it had ten stages, and
    `COVERAGE.md` pinned "the L0 checklist has >= 12 items" when the list was 11. Neither
    was a correctness bug, but both are the same failure as any two lists that must
    agree: the count is a second copy of a fact, and the copy is never updated.

    Two defences, in order of preference:
      1. **Do not write the number.** Most of these were fixed by deleting the count and
         pointing at the source of truth instead.
      2. When a number genuinely helps the reader, derive the truth here and compare.

    The scan below is deliberately over-eager: it flags any phrasing that *looks* like a
    count of a countable thing, so a newly invented phrasing fails loudly rather than
    being missed. The cost of a false positive is rewording one sentence.
    """

    #: doc-side phrasings that assert a count of the runner's stages
    STAGE_COUNT_RE = re.compile(
        r"(?:runs|running|all|in)\s+(?:(\d+)|(one|two|three|four|five|six|seven|eight|"
        r"nine|ten|eleven|twelve))\s+(?:static\s+)?(?:checks|stages|steps)", re.I)
    WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
             "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12}

    def _md_files(self):
        for root, dirs, files in os.walk(SKILL_ROOT):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d != "__pycache__"]
            for fn in files:
                if fn.endswith(".md"):
                    yield os.path.join(root, fn)

    def _runner_stage_count(self):
        """Ground truth: `run` invocations plus the inline stages in run_regression.sh."""
        sh = read(os.path.join(SCRIPTS, "run_regression.sh"))
        named = len(re.findall(r"^run \"", sh, re.M))
        inline = len(re.findall(r'^echo "--- ', sh, re.M))
        return named + inline

    def test_no_stale_stage_count_in_prose(self):
        truth = self._runner_stage_count()
        self.assertGreater(truth, 0, "could not count the runner's stages")
        for path in self._md_files():
            body = read(path)
            for m in self.STAGE_COUNT_RE.finditer(body):
                claimed = int(m.group(1)) if m.group(1) else self.WORDS[m.group(2).lower()]
                rel = os.path.relpath(path, SKILL_ROOT)
                self.assertEqual(
                    claimed, truth,
                    f"{rel} claims {claimed} regression checks but run_regression.sh has "
                    f"{truth} stages: {m.group(0)!r}. Prefer deleting the number and "
                    f"pointing at run_regression.sh -- a prose count is a second copy of "
                    f"a fact that nobody updates.")

    def test_stage_count_regex_would_catch_a_stale_claim(self):
        """Negative control: an over-eager scan that matches nothing is not a guard."""
        truth = self._runner_stage_count()
        for sample in ("It runs six checks in sequence",
                       "runs all 6 checks",
                       "running three static checks"):
            m = self.STAGE_COUNT_RE.search(sample)
            self.assertIsNotNone(m, f"the scan no longer matches {sample!r}")
            claimed = int(m.group(1)) if m.group(1) else self.WORDS[m.group(2).lower()]
            self.assertNotEqual(
                claimed, truth,
                "this control needs a number that differs from the real stage count; "
                f"the runner now has {truth} stages, so pick different samples")

    def test_reference_count_claims_match_reality(self):
        """"All N required reference files" style claims."""
        real = len([f for f in os.listdir(REFS) if f.endswith(".md")])
        for path in self._md_files():
            body = read(path)
            for m in re.finditer(r"[Aa]ll (\d+) (?:required )?reference", body):
                rel = os.path.relpath(path, SKILL_ROOT)
                self.assertEqual(
                    int(m.group(1)), real,
                    f"{rel} says {m.group(1)} reference files, but references/ holds "
                    f"{real} .md files")

    def test_l0_count_is_not_restated_in_prose(self):
        """The L0 item count lives in `L0Tests.L0_SUBJECTS` and nowhere else.

        A doc that also states it is a second copy; the previous one drifted to ">= 12"
        while the list held 11.
        """
        for path in self._md_files():
            body = read(path)
            m = re.search(r"L0 checklist has\s*>?=?\s*(\d+)", body)
            if m:
                rel = os.path.relpath(path, SKILL_ROOT)
                self.fail(f"{rel} restates the L0 item count ({m.group(1)}); the count is "
                          f"derived in L0Tests.L0_SUBJECTS -- describe the check, not the number")

    def test_word_budget_has_real_headroom(self):
        """4998/5000 passes, but any one-sentence edit crosses the line.

        A budget with two words of slack is a tripwire, not a budget -- the next commit
        trips it and the natural response is to raise the ceiling, which retires the
        constraint. Keep genuine slack so the gate stays credible.
        """
        words = len(SKILL.split())
        self.assertLessEqual(words, 5000, f"SKILL.md is {words} words, over the 5000 budget")
        self.assertLessEqual(
            words, 4950,
            f"SKILL.md is {words} words -- under the 5000 ceiling but with under 50 words "
            f"of headroom. Trim now, while it is a choice rather than a blocked commit.")


class UncoveredRulePinsTests(unittest.TestCase):
    """Pins added 2026-08-12 for rules that were registered in `cases.json` but had no
    contract test, so the mutation sweep had nothing to anchor to.

    The set-closure assertion in `test_mutation_sweep.py` made the gap countable: 28 of
    44 rules were in neither the mutation list nor the exemption list. Filling the gap
    with exemptions would have been the cheap move and would have recorded the hole as
    "covered". These are the real pins instead -- one probe per rule, each chosen so
    that inverting the rule breaks it.
    """

    # --- version-forked rules: both directions are errors ---
    def test_tablegroup_none_semantics_is_version_forked(self):
        """Bound to the exact removal claim, with no `|` alternatives.

        The first draft used `r"has been removed|no longer"`; tablegroup.md line 45
        happens to say "table groups no longer have a partition concept" about V4.2.0,
        so the second alternative matched an unrelated sentence and the mutation that
        inverted the actual claim survived. Third occurrence of that shape in one
        session -- see the NOCACHE and cache-disabling tests for the other two.
        """
        tg = ref("tablegroup.md")
        self.assertIn("V4.4.2 BP1", tg)
        self.assertIn(
            'semantic has been removed', tg,
            "tablegroup.md no longer states that the SHARDING=NONE single-node "
            "semantics was REMOVED at BP1 -- asserting the old behaviour on a new "
            "version is as wrong as the reverse")

    def test_tablegroup_scope_has_a_minimum_version(self):
        for name in ("tablegroup.md", "capability-matrix.md"):
            self.assertRegex(
                ref(name), r"SCOPE[^\n]{0,120}4\.4\.2|4\.4\.2[^\n]{0,120}SCOPE",
                f"{name} no longer ties the SCOPE attribute to V4.4.2 BP1")

    def test_partition_ceiling_is_mode_dependent(self):
        cm = ref("capability-matrix.md")
        self.assertIn("8192", cm)
        self.assertIn("65536", cm)
        # Single claim, no alternatives: the earlier `|does not use` alternative sat on
        # the *same table row* as this phrase, so it matched no matter what happened to
        # the mode qualifier and the mutation survived.
        self.assertIn(
            "applies only to MySQL mode", cm,
            "capability-matrix.md no longer scopes max_partition_num to MySQL mode, so "
            "an 8192 gate would wrongly reject a legal Oracle design")

    def test_version_gate_names_a_required_version_field(self):
        self.assertIn("required_version", ref("capability-matrix.md"))

    # --- absolute-rule traps: an L2 number must never become a rejection ---
    def test_l2_threshold_may_not_reject_a_design(self):
        self.assertIn("Use an L2 empirical threshold to judge a design a \"failure\"", SKILL)
        self.assertIn("Treating an L2 empirical threshold as grounds for rejecting a design",
                      ref("anti-patterns.md"))

    def test_primary_ddl_is_c1_only(self):
        self.assertIn("the primary DDL may only use C1", SKILL)
        self.assertIn("candidate_ddl", SKILL)

    def test_evidence_gate_forbids_pass_without_evidence(self):
        self.assertIn("without evidence", SKILL)
        self.assertIn("without evidence", ref("output-contract.md"))

    # --- storage semantics: each wrong answer costs storage or a whole scenario ---
    def test_storage_decision_is_two_axes_with_isolation_first(self):
        self.assertIn("Decide axis 2 first", SKILL)
        self.assertIn(
            "isolation_required", ref("storage-format.md"),
            "storage-format.md no longer names the isolation axis, so a workload that "
            "needs physical isolation can be short-circuited by axis 1")

    def test_skip_index_is_the_answer_for_narrow_aggregation(self):
        self.assertIn("SKIP_INDEX(MIN_MAX, SUM)", SKILL)
        self.assertIn("SKIP_INDEX", ref("storage-format.md"))

    def test_queuing_table_identification_needs_measured_inputs(self):
        sf = ref("storage-format.md")
        self.assertIn("delete_qps", sf)
        self.assertIn("steady_row_count", sf)

    # --- syntax rules that differ by mode ---
    def test_list_enumeration_syntax_differs_by_mode(self):
        dg = ref("doc-gaps.md")
        self.assertIn("VALUES IN", dg)
        self.assertRegex(
            dg, r"MySQL mode uses `VALUES IN \(\.\.\.\)`, Oracle mode uses",
            "doc-gaps.md §1 no longer contrasts the two LIST enumeration forms")

    def test_list_default_partition_recommended(self):
        self.assertIn("catch-all", SKILL)
        self.assertIn("list_default_partition", ref("verification.md"))

    # --- automatic partition splitting ---
    def test_autosplit_restrictions_enumerated(self):
        p = ref("partitioning.md")
        self.assertIn("not supported", p)
        self.assertIn("columnstore tables", p)

    def test_autosplit_threshold_needs_the_tenant_switch(self):
        for text in (SKILL, ref("partitioning.md")):
            self.assertIn("auto_split_tablet_size", text)
            self.assertIn("enable_auto_split", text)

    # --- index cost decisions ---
    def test_global_index_is_a_cost_decision_not_a_ban(self):
        self.assertIn("index_decision", ref("indexes.md"))
        self.assertIn("global indexes are banned because they slow writes", SKILL,
                      "SKILL.md lost the corrective phrasing, so 'global indexes are "
                      "banned' can be restated as a rule")

    def test_global_index_on_archival_table_flags_rebuild(self):
        self.assertIn("global index rebuild", ref("indexes.md"))
        self.assertIn("global-index-rebuild", ref("partitioning.md"))

    def test_autoinc_partition_key_costs_cross_node_txn(self):
        self.assertIn("cross-node transactions", ref("indexes.md"))

    # --- workflow rules ---
    def test_conflicting_dimensions_is_not_a_failure(self):
        self.assertIn("Conflicting dimensions are normal, not a design failure", SKILL)

    def test_quantified_inputs_required_and_collectable(self):
        self.assertIn("SQL to obtain", SKILL)
        self.assertIn("frequency_share", ref("input-collection.md"))

    def test_official_conflicts_route_by_scenario(self):
        self.assertIn("official documents contradict each other", ref("doc-gaps.md"))

    def test_duplicate_table_is_the_dictionary_join_answer(self):
        self.assertIn("DUPLICATE_SCOPE", ref("tablegroup.md"))

    def test_hotspot_five_types_present(self):
        h = ref("hotspots.md")
        for t in ("read_hot_row", "single_row", "single_partition", "range_tail", "leader_skew"):
            self.assertIn(t, h)

    def test_tablet_worst_node_drives_capacity(self):
        self.assertIn(
            "worst node", ref("tablet-capacity.md"),
            "tablet-capacity.md no longer says heterogeneous Zones/Units are judged on "
            "the worst node, so a design can pass on the average and fail in place")

    def test_column_group_redundancy_cost_stated(self):
        sf = ref("storage-format.md")
        self.assertIn("all columns, each column", sf)
        self.assertIn("each column", sf)

    def test_htap_index_tier_overhead_stated(self):
        self.assertIn("30%", ref("storage-format.md"))

    def test_noorder_has_no_tps_threshold(self):
        self.assertIn("no TPS threshold", SKILL)
        self.assertIn("Do not set a TPS threshold", ref("doc-gaps.md"))


class LinterSelfRegressionTests(unittest.TestCase):
    """A bug in the validator itself produces a false green, so it must be tested just like the thing it validates."""

    def setUp(self):
        self.lint = _load_linter()

    def test_strip_inline_code_preserves_link_labels(self):
        """A past failure: blanking the label turned [`x`](x) into [](x), and the link check could no longer match it.

        This is the sole reason this skill ever had "lint all green, but a broken path sitting in the index."
        """
        src = "| [`references/x.md`](references/x.md) | description |"
        out = self.lint.strip_inline_code(src)
        found = re.findall(r"\[[^\]]+\]\((?!https?://|#)([^)#]+)", out)
        self.assertEqual(found, ["references/x.md"],
                         "strip_inline_code has swallowed the link label again, the link check will miss everything")

    def test_strip_inline_code_still_masks_bnf_fragments(self):
        """The original intent of masking must not be lost: a BNF fragment like `RANGE [COLUMNS](cols)` must not be read as a link."""
        src = "the partitioning form `RANGE [COLUMNS](cols)` is shown in the table below"
        out = self.lint.strip_inline_code(src)
        self.assertEqual(
            re.findall(r"\[[^\]]+\]\((?!https?://|#)([^)#]+)", out), [])

    def test_strip_inline_code_preserves_width(self):
        """Equal-length substitution: a width change would cause adjacency-dependent rules to misjudge."""
        src = "a `bc` d"
        self.assertEqual(len(self.lint.strip_inline_code(src)), len(src))

    def test_link_checker_would_catch_a_broken_index_entry(self):
        """End to end: feed a broken link into the real check_links logic."""
        targets = re.findall(
            r"\[[^\]]+\]\((?!https?://|#)([^)#]+)",
            self.lint.strip_inline_code(
                "| [`references/definitely-missing.md`]"
                "(references/definitely-missing.md) | x |"))
        self.assertEqual(targets, ["references/definitely-missing.md"])
        self.assertFalse(
            os.path.exists(os.path.join(SKILL_ROOT, targets[0])),
            "this test depends on that path not existing")


class CasesRegistryTests(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(SKILL_ROOT, "tests", "cases.json"),
                  encoding="utf-8") as f:
            self.spec = json.load(f)

    def test_every_rule_source_exists(self):
        for rid, r in self.spec["rules"].items():
            src = r.get("source")
            self.assertTrue(os.path.exists(os.path.join(SKILL_ROOT, src)),
                            f"the source for rule {rid} does not exist: {src}")

    def test_new_rules_registered(self):
        for rid in ("R-AUTOINC-MODE-GATE", "R-TENANT-DEFAULT-FORMAT",
                    "R-NDV-GT-PARTITIONS", "R-HTAP-FOUR-TIERS",
                    "R-TABLEMODE-COMPACTION", "R-HOTSPOT-READ-DIRECTION",
                    "R-SPECIAL-INDEX", "R-INPUT-COLLECTION",
                    "R-DOC-CONFLICT-SPLIT"):
            self.assertIn(rid, self.spec["rules"])

    def test_every_rule_has_a_case(self):
        covered = {rid for c in self.spec["cases"] for rid in c.get("rules", [])}
        self.assertEqual(sorted(set(self.spec["rules"]) - covered), [])


if __name__ == "__main__":
    unittest.main()
