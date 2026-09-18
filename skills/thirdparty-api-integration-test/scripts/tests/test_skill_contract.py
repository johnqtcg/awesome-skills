"""Contract + consistency tests for the thirdparty-api-integration-test skill."""

import importlib.util
import os
import re
import unittest

SKILL_ROOT = os.path.join(os.path.dirname(__file__), "..", "..")


def load_fixture_source():
    """Return `_FIXTURE` from the sibling behavioral test, imported BY PATH.

    A bare `from test_behavioral_integration import _FIXTURE` only resolves when the tests dir is
    on sys.path — true under `unittest discover -s tests` (run_regression.sh) but NOT under
    `pytest skills/` from the repo root, where it raises ModuleNotFoundError. Loading by explicit
    path with a per-file unique module name works under both runners and avoids colliding with the
    identically-named module in the sibling api-integration-test skill."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_behavioral_integration.py")
    spec = importlib.util.spec_from_file_location("_sibling_" + re.sub(r"\W+", "_", path), path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod._FIXTURE
SKILL_MD = os.path.join(SKILL_ROOT, "SKILL.md")
REFS_DIR = os.path.join(SKILL_ROOT, "references")


def read(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


SKILL_TEXT = read(SKILL_MD)
SKILL_LINES = SKILL_TEXT.splitlines()

# The Go safety helpers were extracted from SKILL.md into references/go-baseline.md (to keep
# SKILL.md lean). Code-level asserts search SKILL.md + that baseline together, so a token is
# found regardless of which file holds it.
BASELINE_MD = os.path.join(REFS_DIR, "go-baseline.md")
BASELINE_TEXT = read(BASELINE_MD)
DOC_TEXT = SKILL_TEXT + "\n\n" + BASELINE_TEXT


def _strip_line_comment(line: str) -> str:
    """Cut a Go line at its `//` comment, but ONLY when the `//` is outside a string/rune
    literal. `line.split("//")[0]` wrongly truncates code containing `"://"` (redactURL,
    grpcTargetHost), hiding drift after that point — this is string-aware instead."""
    i, n, in_str = 0, len(line), None
    while i < n:
        c = line[i]
        if in_str is not None:
            if in_str == '"' and c == "\\":
                i += 2
                continue
            if c == in_str:
                in_str = None
            i += 1
            continue
        if c in "\"`'":
            in_str = c
            i += 1
            continue
        if c == "/" and i + 1 < n and line[i + 1] == "/":
            return line[:i]
        i += 1
    return line


def _brace_delta(code: str) -> int:
    """Net `{` minus `}` in a (comment-stripped) line, ignoring braces inside Go string/rune
    literals — otherwise a `"{"` in a literal would misplace the function boundary. Block
    comments (`/* */`) are not handled; the helpers use none, and a stray one would surface as a
    body-diff, not a silent miss."""
    depth, i, n, in_str = 0, 0, len(code), None
    while i < n:
        c = code[i]
        if in_str is not None:
            if in_str == '"' and c == "\\":
                i += 2
                continue
            if c == in_str:
                in_str = None
            i += 1
            continue
        if c in "\"`'":
            in_str = c
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
        i += 1
    return depth


def norm_func(src: str, name: str) -> str:
    """Extract a top-level Go func by name; strip comments + ALL whitespace. Uses
    brace DEPTH (string-aware) to find the true end so the FULL body is compared."""
    started, depth, out = False, 0, []
    for ln in src.splitlines():
        code = _strip_line_comment(ln)
        if not started:
            if ("func " + name + "(") not in ln:
                continue
            started = True
        out.append(code)
        depth += _brace_delta(code)
        if depth == 0:
            break
    return "".join("".join(out).split())


def norm_method(src: str, recv_type: str, name: str) -> str:
    """Like norm_func but for a receiver method `func (x *RecvType) name(...)` — so the
    cost-enforcement methods (callBudget.spend, budgetTransport.RoundTrip) are drift-guarded too."""
    start = re.compile(r"func\s*\(\s*\w+\s+\*?" + re.escape(recv_type) + r"\s*\)\s*" + re.escape(name) + r"\(")
    started, depth, out = False, 0, []
    for ln in src.splitlines():
        code = _strip_line_comment(ln)
        if not started:
            if not start.search(ln):
                continue
            started = True
        out.append(code)
        depth += _brace_delta(code)
        if depth == 0:
            break
    return "".join("".join(out).split())


def _paren_group(s, open_idx):
    depth = 0
    for i in range(open_idx, len(s)):
        if s[i] == "(":
            depth += 1
        elif s[i] == ")":
            depth -= 1
            if depth == 0:
                return s[open_idx + 1:i]
    return None


def _arg_count(argstr):
    if argstr.strip() == "":
        return 0
    depth, count, in_str, i = 0, 1, None, 0
    while i < len(argstr):
        c = argstr[i]
        if in_str:
            if c == "\\":
                i += 2
                continue
            if c == in_str:
                in_str = None
        elif c in "\"`'":
            in_str = c
        elif c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
        elif c == "," and depth == 0:
            count += 1
        i += 1
    return count


def _code_fences(text: str) -> str:
    """Concatenate the contents of every ``` fenced code block — so a prose mention
    like `maskID()` is not miscounted as a 0-arg call by the arity checker."""
    parts, inside, buf = [], False, []
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            if inside:
                parts.append("\n".join(buf)); buf = []
            inside = not inside
            continue
        if inside:
            buf.append(line)
    return "\n".join(parts)


def go_call_arities(text, name):
    text = _code_fences(text)
    def_arity, calls = None, []
    for m in re.finditer(re.escape(name) + r"\(", text):
        content = _paren_group(text, m.end() - 1)
        if content is None:
            continue
        arity = _arg_count(content)
        if text[:m.start()].rstrip().endswith("func"):
            def_arity = arity
        else:
            calls.append(arity)
    return def_arity, calls


HELPERS = ("isProdVendorTarget", "assertTestAccount", "requireVendorIntegration",
           "assertVendorDestructiveSafe", "maskID", "redactURL", "unwrapURLErr",
           "parseRetryAfter", "getHonoringRateLimit", "grpcTargetHost", "isProdGRPCTarget",
           "vendorMaxCalls", "newVendorBudget", "newBudgetTransport",
           "redactGRPCTarget", "requireVendorGRPCIntegration",
           "assertVendorGRPCDestructiveSafe")

# Receiver methods are not matched by norm_func; guard them separately — these two are where
# the cost cap is actually enforced, so a doc/fixture drift here would be a real safety hole.
METHODS = (("callBudget", "spend"), ("budgetTransport", "RoundTrip"))


class Frontmatter(unittest.TestCase):
    def test_name(self):
        self.assertIn("name: thirdparty-api-integration-test", SKILL_TEXT)

    def test_description_keywords(self):
        m = re.match(r"^---\n(.*?)\n---\n", SKILL_TEXT, re.DOTALL)
        self.assertIsNotNone(m)
        self.assertIn("third-party", m.group(1).lower())

    def test_allowed_tools(self):
        self.assertIn("allowed-tools:", SKILL_TEXT)

    def test_line_budget(self):
        self.assertLessEqual(len(SKILL_LINES), 500, f"SKILL.md is {len(SKILL_LINES)} lines")


class SafetyRules(unittest.TestCase):
    def setUp(self):
        self.skill = DOC_TEXT

    def test_skip_vs_fail_documented(self):
        self.assertIn("Skip vs Fail", self.skill)
        self.assertIn("t.Fatalf", self.skill)

    def test_prod_host_fail_closed(self):
        for tok in ("IsAbs()", "Hostname() ==", '!= "http"', '!= "https"', "VENDOR_SANDBOX_HOSTS"):
            self.assertIn(tok, self.skill, f"prod-host guard missing: {tok}")

    def test_account_allowlist_required(self):
        self.assertIn("VENDOR_TEST_ACCOUNTS is required", self.skill)

    def test_destructive_rules(self):
        self.assertIn("INTEGRATION_ALLOW_DESTRUCTIVE", self.skill)
        self.assertIn("forbidden against a production/live target", self.skill)
        self.assertIn("require an idempotency key", self.skill)

    def test_cost_budget(self):
        self.assertIn("VENDOR_MAX_CALLS", self.skill)

    def test_rate_limit_handling(self):
        self.assertIn("Retry-After", self.skill)
        self.assertIn("rate-limit", self.skill)
        # #1: real handling — parse + bounded honor, persistent 429 is a failure not a skip.
        self.assertIn("parseRetryAfter", self.skill)
        self.assertIn("getHonoringRateLimit", self.skill)
        self.assertIn("not a skip", self.skill)

    def test_masking_helpers(self):
        # #3: fatals mask the account and redact the URL.
        self.assertIn("maskID(account)", self.skill)
        self.assertIn("redactURL(baseURL)", self.skill)

    def test_masking(self):
        self.assertIn("Mask", self.skill)
        self.assertTrue("customer/tenant" in self.skill or "customer/tenant/account" in self.skill)

    def test_grpc_specifics(self):
        self.assertIn("status.Code(err)", self.skill)
        self.assertIn("conn.Close()", self.skill)

    def test_grpc_gate_closed(self):
        # #3: a real gRPC gate helper, and the resolver scheme is restricted (fail closed).
        self.assertIn("requireVendorGRPCIntegration", self.skill)
        self.assertIn('case "", "dns", "passthrough":', self.skill)

    def test_grpc_destructive_rules(self):
        # gRPC mutations get the same destructive gate as HTTP: a helper, the flag,
        # prod-forbidden-under-all-flags, and a mandatory idempotency key.
        self.assertIn("assertVendorGRPCDestructiveSafe", self.skill)
        self.assertIn("destructive gRPC calls are forbidden against a production/live target", self.skill)
        self.assertIn("destructive gRPC calls require an idempotency key", self.skill)

    def test_retry_budget_max_two(self):
        # #2: the retry rule and the example agree on max 2.
        self.assertIn("max 2 retries", self.skill)

    def test_log_masking_rule(self):
        # #4: the old "Log parsed values" advice (which invites logging raw IDs) is gone.
        self.assertNotIn("Log parsed values at `t.Logf` level for debugging", self.skill)
        self.assertIn("mask identifiers", self.skill.lower().replace("**", ""))

    def test_no_false_shared_claim(self):
        # The old wording claimed the gate/output-contract were shared. They are not.
        self.assertNotIn("_Shared with `$api-integration-test`._", self.skill)
        self.assertIn("separate file", self.skill)


class Commands(unittest.TestCase):
    def test_every_run_command_has_count1(self):
        for label in ("SKILL.md", "vendor-examples.md"):
            text = SKILL_TEXT if label == "SKILL.md" else read(os.path.join(REFS_DIR, "vendor-examples.md"))
            for line in text.splitlines():
                if "go test -tags=integration" in line and any(f in line for f in ("-run ", "-timeout", "-v ")):
                    self.assertIn("-count=1", line, f"{label}: run command missing -count=1:\n{line}")

    def test_runner_forces_safety_flags(self):
        # The actual runner — not just the doc's example commands — fixes -tags/-count/-timeout,
        # restricts extra args to a strict allowlist (so -test.count/-test.timeout can't slip in),
        # and refuses to report a zero-execution success.
        sh = read(os.path.join(SKILL_ROOT, "scripts", "run_vendor_integration.sh"))
        self.assertIn("-tags=integration", sh)
        self.assertIn("-count=1", sh)
        self.assertIn('-timeout="$timeout_val"', sh)
        self.assertIn('-p="$par"', sh)                       # suite concurrency fixed (cost)
        self.assertIn('-parallel="$par"', sh)
        self.assertIn("refuse disallowed go test arg", sh)   # strict allowlist for extras
        self.assertIn("no test PASSED", sh)                  # all-skip / zero-execution guard
        self.assertIn("none matching", sh)                   # integration-name-match guard
        self.assertNotIn('source "$envfile"', sh)            # env file parsed as data, never executed


class GateParity(unittest.TestCase):
    """The thirdparty gate is a separate file — guard that it stays at the same
    safety bar as api-integration-test's (resolved-host, degradation, skip-vs-fail)."""

    def setUp(self):
        self.gate = read(os.path.join(REFS_DIR, "common-integration-gate.md"))

    def test_gate_has_resolved_host_and_account(self):
        for tok in ("resolved host", "VENDOR_SANDBOX_HOSTS", "VENDOR_TEST_ACCOUNTS", "absolute `http(s)` URL"):
            self.assertIn(tok, self.gate, f"gate missing: {tok}")

    def test_gate_has_degradation_levels(self):
        for tok in ("Full", "Scaffold", "Blocked"):
            self.assertIn(tok, self.gate)

    def test_gate_has_skip_vs_fatal(self):
        self.assertIn("t.Fatalf", self.gate)
        self.assertIn("not a silent `t.Skip`", self.gate)

    def test_output_contract_ci_integrity(self):
        oc = read(os.path.join(REFS_DIR, "common-output-contract.md"))
        self.assertIn("(cached)", oc)
        self.assertIn("Never report PASS when tests were actually skipped", oc)


class VendorExamples(unittest.TestCase):
    def setUp(self):
        self.ex = read(os.path.join(REFS_DIR, "vendor-examples.md"))

    def test_uses_call_budget_in_chain(self):
        # #2: the budget must actually be in the call chain, not just an env var.
        self.assertIn("newVendorBudget(t)", self.ex)
        self.assertTrue("getHonoringRateLimit" in self.ex or "budget.spend(t)" in self.ex,
                        "example does not spend the call budget before a real call")

    def test_no_skip_on_rate_limit(self):
        # #1: the old t.Skipf-on-429 anti-pattern (a persistent 429 false-greens CI) is gone.
        self.assertNotIn("t.Skipf", self.ex)
        self.assertIn("getHonoringRateLimit", self.ex)

    def test_uses_real_vendor_client(self):
        # #5: exercise the production client path (auth/serialization/error mapping).
        self.assertIn("vendor.NewClient", self.ex)
        self.assertIn("client.GetResource", self.ex)

    def test_client_uses_budget_transport(self):
        # #1: the client path budgets at the transport (catches internal retries).
        self.assertIn("newBudgetTransport(t, nil)", self.ex)

    def test_rate_limit_retry_is_two(self):
        # #2: the raw example uses maxRetries=2 (not 3).
        for line in self.ex.splitlines():
            if "getHonoringRateLimit(" in line:
                self.assertIn(", 2,", line, f"getHonoringRateLimit not called with maxRetries=2:\n{line}")

    def test_grpc_gate_guidance(self):
        # #3: gRPC uses the full gate helper, not just the prod check.
        self.assertIn("requireVendorGRPCIntegration", self.ex)


class HelperConsistency(unittest.TestCase):
    def setUp(self):
        self.skill = DOC_TEXT

    def test_helper_bodies_identical_doc_vs_fixture(self):
        _FIXTURE = load_fixture_source()
        for name in HELPERS:
            doc = norm_func(self.skill, name)
            fix = norm_func(_FIXTURE, name)
            self.assertTrue(doc, f"{name} not found in SKILL.md")
            self.assertTrue(fix, f"{name} not found in fixture")
            self.assertEqual(doc, fix, f"{name}: SKILL.md and fixture bodies differ")

    def test_comment_stripper_is_string_aware(self):
        # regression for the `ln.split("//")[0]` bug: `://` inside a Go string must NOT be
        # treated as a comment, else drift after it (redactURL, grpcTargetHost) is invisible.
        a = 'func f(s string) string {\n\treturn s + "://xxx"\n}'
        b = 'func f(s string) string {\n\treturn s + "://yyy"\n}'
        self.assertIn('"://xxx"', norm_func(a, "f"), "`://` was cut as a comment")
        self.assertNotEqual(norm_func(a, "f"), norm_func(b, "f"),
                            "drift after `://` in a string is not detected")
        # a real trailing comment IS still stripped
        c = 'func g() { return } // trailing'
        self.assertNotIn("trailing", norm_func(c, "g"))

    def test_brace_counting_is_string_aware(self):
        # a `{` inside a string literal must not extend the function boundary past its real `}`.
        src = 'func h() string {\n\ts := "{"\n\treturn s\n}\nfunc after() { return }'
        body = norm_func(src, "h")
        self.assertIn('"{"', body, "string content dropped")
        self.assertNotIn("after", body, "brace inside a string literal ran the boundary past func h")

    def test_method_bodies_identical_doc_vs_fixture(self):
        _FIXTURE = load_fixture_source()
        for recv, name in METHODS:
            doc = norm_method(self.skill, recv, name)
            fix = norm_method(_FIXTURE, recv, name)
            self.assertTrue(doc, f"{recv}.{name} not found in SKILL.md")
            self.assertTrue(fix, f"{recv}.{name} not found in fixture")
            self.assertEqual(doc, fix, f"{recv}.{name}: SKILL.md and fixture bodies differ")

    def test_helper_call_sites_match_definition_arity(self):
        corpus = "\n".join([
            self.skill,
            read(os.path.join(REFS_DIR, "vendor-examples.md")),
            read(os.path.join(REFS_DIR, "common-integration-gate.md")),
        ])
        for name in HELPERS:
            defn, calls = go_call_arities(corpus, name)
            self.assertIsNotNone(defn, f"{name}: no definition found")
            for c in calls:
                self.assertEqual(c, defn,
                                 f"{name}: a doc call passes {c} args but the definition takes {defn}")


class CoverageDoc(unittest.TestCase):
    """COVERAGE.md states test/helper counts in prose; those numbers used to drift
    (they were stale by rounds). Derive the real counts from the source and assert the
    doc carries exactly them, so a count can never silently rot again."""

    def setUp(self):
        here = os.path.dirname(__file__)
        self.cov = read(os.path.join(here, "COVERAGE.md"))
        self.contract = len(re.findall(r"^\s*def test_", read(os.path.join(here, "test_skill_contract.py")), re.M))
        self.behavioral = len(re.findall(r"^\s*def test_", read(os.path.join(here, "test_behavioral_integration.py")), re.M))
        self.eval = len(re.findall(r"^\s*def test_", read(os.path.join(here, "test_llm_skill_eval.py")), re.M))
        # Every test_*.py in this directory must be in the sum. A hand-listed set of modules
        # goes stale the moment a layer is added — which is exactly what happened when the
        # skill-output eval arrived and the total silently stopped covering it.
        self.modules = sorted(f for f in os.listdir(here)
                              if f.startswith("test_") and f.endswith(".py"))

    def test_every_test_module_is_counted(self):
        self.assertEqual(
            ["test_behavioral_integration.py", "test_llm_skill_eval.py", "test_skill_contract.py"],
            self.modules,
            "a test module was added or removed; the totals below must account for it")

    def test_totals_match_reality(self):
        total = self.contract + self.behavioral + self.eval
        self.assertIn(f"{total} runnable test methods", self.cov,
                      f"COVERAGE.md total != {total} (contract {self.contract} + behavioral "
                      f"{self.behavioral} + skill-output {self.eval})")
        self.assertIn(f"{self.contract} contract + {self.behavioral} behavioral + "
                      f"{self.eval} skill-output", self.cov,
                      "COVERAGE.md layer split is stale")
        self.assertIn(f"Actual skill-output eval methods: {self.eval}", self.cov,
                      "COVERAGE.md per-file skill-output count is stale")

    def test_helper_count_matches_reality(self):
        self.assertIn(f"{len(HELPERS)} safety helpers", self.cov,
                      f"COVERAGE.md helper count != len(HELPERS)={len(HELPERS)}")

    def test_no_stale_counts_resurface(self):
        for stale in ("4 safety helpers", "10 safety helpers", "(22 tests)", "59 runnable"):
            self.assertNotIn(stale, self.cov, f"stale coverage figure resurfaced: {stale}")


# ══════════════════════════════════════════════════════════════════════════════════════
# Structural guards — added after a mutation sweep found the normative PROSE unpinned
# ══════════════════════════════════════════════════════════════════════════════════════

def md_section(text: str, heading: str) -> str:
    """Body under `heading`, to the next heading of the same or higher level.

    Scoping matters: an `assertIn` over a whole document stays green while the occurrence
    that *decides* something is edited. Measured — flipping both Skip-vs-Fail rows to
    `t.Skip`, inverting four of the nine "executable" vendor rules, and restoring the
    false "shared file" claim all passed the full 93-test suite together."""
    lines = text.splitlines()
    for start, ln in enumerate(lines):
        if ln.startswith("#") and ln.lstrip("#").strip() == heading:
            level = len(ln) - len(ln.lstrip("#"))
            break
    else:
        raise AssertionError(f"heading not found: {heading!r}")
    for end in range(start + 1, len(lines)):
        nxt = lines[end]
        if nxt.startswith("#") and (len(nxt) - len(nxt.lstrip("#"))) <= level:
            return "\n".join(lines[start + 1:end])
    return "\n".join(lines[start + 1:])


def md_rows(section: str) -> list:
    """Markdown table rows in `section` as cell lists (header/separator dropped, `**` stripped)."""
    rows, seen_header = [], False
    for ln in section.splitlines():
        s = ln.strip()
        if not s.startswith("|"):
            seen_header = False
            continue
        cells = [c.strip().replace("**", "") for c in s.strip("|").split("|")]
        if set("".join(cells)) <= set("-: "):
            continue
        if not seen_header:
            seen_header = True
            continue
        rows.append(cells)
    return rows


class NormativeRuleGuards(unittest.TestCase):
    """22 mutations were applied; **11 survived the full suite**. The Go helpers and the
    runner were caught every time (full-body identity + 21 runner tests), but the prose that
    states the rules was unguarded — including the section that calls itself
    "concrete, testable rules — not principles. A behavioral fixture exercises each".

    The behavioral fixture exercises the *Go helpers*, which are a separate copy; inverting
    the *rule text* changed nothing it looks at. Each test below was confirmed to fail
    against the mutation it names."""

    SKIP_VS_FAIL = {
        "Run gate unset (`THIRDPARTY_INTEGRATION != 1`)": "`t.Skip` (not requested)",
        "Gate set, a required var missing/empty": "`t.Fatalf`",
        "Gate set, target is prod/live (ENV, host not on `VENDOR_SANDBOX_HOSTS`, or non-test account) without `INTEGRATION_ALLOW_PROD=1`": "`t.Fatalf`",
        "Gate set, destructive op without `INTEGRATION_ALLOW_DESTRUCTIVE=1`": "`t.Skip` (opt-in tier — keep in a separate CI job)",
    }

    def test_skip_vs_fail_cells_are_pinned(self):
        rows = {r[0]: r[1] for r in md_rows(md_section(SKILL_TEXT, "Skip vs Fail (CI Integrity)"))}
        self.assertEqual(set(self.SKIP_VS_FAIL), set(rows),
                         "a Skip-vs-Fail row was added or removed without being pinned")
        for situation, behavior in self.SKIP_VS_FAIL.items():
            with self.subTest(situation=situation[:48]):
                self.assertEqual(behavior, rows[situation])

    # The nine rules the skill itself calls executable. Each entry is the exact opening
    # clause that carries the rule's *direction* — allowlist vs denylist, require vs may,
    # forbidden vs permitted. Those are the words a mutation flips.
    VENDOR_RULES = [
        "1. **Sandbox host allowlist (fail closed).**",
        "2. **Test account allowlist (fail closed).**",
        "3. **Production writes forbidden under ALL flags.**",
        "4. **Mutations require an idempotency key.**",
        "5. **Bounded call budget (cost control).**",
        "6. **Retry-After / 429 handling.**",
        "7. **Mask sensitive IDs and secrets.**",
        "8. **gRPC specifics**",
        "9. **Retry policy bounded and explicit.**",
    ]

    def test_the_nine_vendor_rules_keep_their_direction(self):
        section = md_section(SKILL_TEXT, "Vendor-Specific Safety Additions (executable rules)")
        for rule in self.VENDOR_RULES:
            with self.subTest(rule=rule[:44]):
                self.assertIn(rule, section)
        # The direction-carrying phrases, checked inside this section only.
        self.assertIn("Unset or non-matching host → treated as production (refuse)", section)
        self.assertIn("`VENDOR_TEST_ACCOUNTS` is required", section)
        self.assertIn("fails even with\n   `ALLOW_PROD=1` + `ALLOW_DESTRUCTIVE=1`", section)
        self.assertIn("must pass a non-empty\n   `Idempotency-Key`", section)
        self.assertIn("`VENDOR_MAX_CALLS` (default 20)", section)
        self.assertIn("classify the failure as `rate-limit`, never `contract`", section)
        self.assertIn("Never log tokens, API keys, or raw customer/tenant/account", section)
        # and the count claimed by the heading's own framing
        numbered = re.findall(r"(?m)^(\d+)\. \*\*", section)
        self.assertEqual([str(i) for i in range(1, 10)], numbered,
                         f"the executable-rule list is no longer 1..9: {numbered}")

    def test_retry_budget_and_timeout_band_are_pinned(self):
        pattern = md_section(SKILL_TEXT, "Required Pattern")
        self.assertIn("**max 2 retries (3 total attempts)**", pattern)
        self.assertIn("`getHonoringRateLimit` is called with `maxRetries=2`", pattern)
        safety = md_section(SKILL_TEXT, "Safety Rules")
        self.assertIn("Keep timeout strict (for example 10-30s)", safety)

    def test_build_tag_is_the_integration_tag_in_every_document(self):
        """Rename the tag in one place and the CI target runs nothing while reporting success."""
        docs = {"SKILL.md": SKILL_TEXT,
                "go-baseline.md": BASELINE_TEXT,
                "common-integration-gate.md": read(os.path.join(REFS_DIR, "common-integration-gate.md")),
                "checklists.md": read(os.path.join(REFS_DIR, "checklists.md"))}
        for name, text in docs.items():
            with self.subTest(doc=name):
                self.assertIn("//go:build integration", text)
                self.assertNotIn("//go:build vendortest", text)

    def test_the_skill_is_not_model_invocable(self):
        """This skill makes real, billable calls to an external vendor. It must never be
        auto-selected — a user asks for it by name or it does not run."""
        fm = SKILL_TEXT.split("---")[1]
        self.assertIn("disable-model-invocation: true", fm)

    def test_the_parallel_files_are_not_claimed_to_be_shared(self):
        """A previous round had to remove a false "shared with $api-integration-test" claim:
        the files are independent copies and had drifted ~118 lines. The claim must not come
        back, because it tells a maintainer an edit here propagates when it does not."""
        for name, text in (("SKILL.md", SKILL_TEXT),
                           ("common-integration-gate.md",
                            read(os.path.join(REFS_DIR, "common-integration-gate.md"))),
                           ("common-output-contract.md",
                            read(os.path.join(REFS_DIR, "common-output-contract.md")))):
            with self.subTest(doc=name):
                self.assertIsNone(
                    re.search(r"shared with\s+`?\$?api-integration-test", text, re.I),
                    f"{name} claims the file is shared; it is a separate copy")
        self.assertIn("it is a **separate file**, not shared; edits do not propagate between skills.",
                      SKILL_TEXT)

    def test_the_quality_rubric_has_tiers_and_is_reachable(self):
        """`checklists.md` shipped 9 flat items with no tiers and no pass criteria, and the
        output contract asked for no verdict — so nothing defined whether the authored tests
        were acceptable, only whether the run passed. A rubric nobody reports is a rubric
        nobody applies."""
        ck = read(os.path.join(REFS_DIR, "checklists.md"))
        self.assertIn("`Critical`: any single FAIL → overall **FAIL**", ck)
        self.assertIn("`Standard`: ≥ 4/5", ck)
        self.assertIn("`Hygiene`: ≥ 3/4", ck)
        quality = ck.split("## Test Quality Checklist", 1)[1]
        for tier, prefix, want in (("Critical", "C", 4), ("Standard", "S", 5), ("Hygiene", "H", 4)):
            body = quality.split(f"### {tier}", 1)[1]
            ids = re.findall(rf"(?m)^\|\s*({prefix}\d+)\s*\|", body)
            with self.subTest(tier=tier):
                self.assertEqual(want, len(set(ids)),
                                 f"{tier} tier has {sorted(set(ids))} but the bar says /{want}")
        oc = read(os.path.join(REFS_DIR, "common-output-contract.md"))
        self.assertIn("Quality scorecard verdict", oc,
                      "the output contract must require the verdict")
        self.assertIn("Critical FAIL", oc)
        self.assertIn("MUST then score it", SKILL_TEXT,
                      "SKILL.md must instruct that authored code is scored, not merely that "
                      "the checklist file may be read")

    def test_the_shared_claim_detector_still_detects(self):
        """Synthetic input: the guard above is pinned to text that is correct today, so a
        pattern edited into one that matches nothing would pass vacuously."""
        pat = re.compile(r"shared with\s+`?\$?api-integration-test", re.I)
        for bad in ("shared with $api-integration-test", "Shared with `api-integration-test`",
                    "shared with api-integration-test"):
            self.assertIsNotNone(pat.search(bad), bad)
        self.assertIsNone(pat.search("a separate file from $api-integration-test's gate"))


class ShippedSurfaceIntegrity(unittest.TestCase):
    """Structure and reachability across SKILL.md + every reference."""

    @classmethod
    def setUpClass(cls):
        cls.docs = {"SKILL.md": SKILL_TEXT}
        cls.docs.update({f: read(os.path.join(REFS_DIR, f))
                         for f in sorted(os.listdir(REFS_DIR)) if f.endswith(".md")})

    @staticmethod
    def unclosed_fence(text: str):
        """Line of an unclosed fence, or None. CommonMark: a closing fence carries NO info
        string, so a ```go line inside a ``` block is content, not a closer."""
        open_at, opener_len, opener_ch = None, 0, ""
        for i, ln in enumerate(text.splitlines(), 1):
            m = re.match(r"^\s{0,3}(`{3,}|~{3,})(.*)$", ln)
            if not m:
                continue
            fence, info = m.groups()
            if open_at is None:
                open_at, opener_len, opener_ch = i, len(fence), fence[0]
            elif fence[0] == opener_ch and len(fence) >= opener_len and not info.strip():
                open_at = None
        return open_at

    def test_every_code_fence_is_balanced(self):
        for name, text in self.docs.items():
            with self.subTest(doc=name):
                self.assertIsNone(self.unclosed_fence(text),
                                  f"{name}: a fence is never closed — the rest renders as code")

    def test_the_fence_detector_still_detects(self):
        self.assertEqual(1, self.unclosed_fence("```\nx\n"))
        self.assertIsNone(self.unclosed_fence("```\nx\n```\n"))
        self.assertEqual(7, self.unclosed_fence("a\n\n```\n```go\nx\n```\n```\n"))
        self.assertIsNone(self.unclosed_fence("````text\n```go\nx\n```\n````\n"))

    def test_every_reference_pointer_resolves(self):
        pointers = {(n, t) for n, text in self.docs.items()
                    for t in re.findall(r"references/([A-Za-z0-9._-]+\.md)", text)}
        self.assertGreaterEqual(len(pointers), 5, "the pointer regex stopped matching")
        for source, target in sorted(pointers):
            with self.subTest(source=source, target=target):
                self.assertTrue(os.path.isfile(os.path.join(REFS_DIR, target)),
                                f"{source} cites references/{target}, which does not exist")

    def test_every_reference_file_is_reachable(self):
        pointed = {t for text in self.docs.values()
                   for t in re.findall(r"references/([A-Za-z0-9._-]+\.md)", text)}
        for f in sorted(os.listdir(REFS_DIR)):
            if f.endswith(".md"):
                with self.subTest(reference=f):
                    self.assertIn(f, pointed, f"references/{f} is never referenced")

    def test_every_intra_document_anchor_resolves(self):
        for name, text in self.docs.items():
            slugs = {re.sub(r"[^a-z0-9\s-]", "", h.lower()).strip().replace(" ", "-")
                     for h in re.findall(r"(?m)^#{1,6}\s+(.+?)\s*$", text)}
            for anchor in re.findall(r"\]\(#([A-Za-z0-9_-]+)\)", text):
                with self.subTest(doc=name, anchor=anchor):
                    self.assertIn(anchor, slugs, f"{name} links to a dead #{anchor}")


if __name__ == "__main__":
    unittest.main()