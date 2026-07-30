#!/usr/bin/env bash
set -uo pipefail

# Verify — against a real Playwright run — which hook a `test.skip` guard can
# actually protect. The linter's C4 rule promotes a guard found in
# `beforeAll`/`beforeEach` to the enclosing scope and refuses to promote one in
# `afterAll`/`afterEach`. That is a claim about another project's runtime
# semantics, so it is measured here rather than assumed.
#
# Opt-in: needs network (npm) and is far slower than the unit tests, so it is not
# part of run_regression.sh. Re-run it when bumping the Playwright version the
# skill targets.
#
#   bash scripts/verify_hook_semantics.sh            # uses latest @playwright/test
#   PW_VERSION=1.55.0 bash scripts/verify_hook_semantics.sh
#
# Exit 0 = observed behaviour matches what the skill documents.
# Exit 1 = mismatch; the skill's guidance needs revisiting.
# Exit 2 = could not run (no npm, install failed). NOT a verdict.

PW_VERSION="${PW_VERSION:-latest}"

command -v npm >/dev/null 2>&1 || {
  echo "verify_hook_semantics: npm not available — cannot verify" >&2
  exit 2
}

WORK="$(mktemp -d "${TMPDIR:-/tmp}/pw_hook_probe.XXXXXX")" || exit 2
trap 'rm -rf "${WORK}"' EXIT
cd "${WORK}" || exit 2

echo "=== installing @playwright/test@${PW_VERSION} (browsers not needed) ==="
printf '{"name":"pw-hook-probe","private":true}\n' > package.json
# Local cache: a shared ~/.npm may be unwritable in a sandbox.
if ! npm install --no-audit --no-fund --loglevel=error \
      --cache "${WORK}/.npmcache" "@playwright/test@${PW_VERSION}" >/dev/null 2>&1; then
  echo "verify_hook_semantics: npm install failed — cannot verify" >&2
  exit 2
fi

PW="./node_modules/.bin/playwright"
[ -x "${PW}" ] || { echo "verify_hook_semantics: playwright binary missing" >&2; exit 2; }
ACTUAL_VERSION="$("${PW}" --version 2>/dev/null)"
echo "installed: ${ACTUAL_VERSION}"

mkdir -p tests
cat > playwright.config.ts <<'CFG'
import { defineConfig } from '@playwright/test';
export default defineConfig({ testDir: './tests', reporter: [['list']] });
CFG

# None of these specs use the `page` fixture, so no browser download is required.

cat > tests/before_all.spec.ts <<'SPEC'
import { test, expect } from '@playwright/test';
test.beforeAll(async () => { test.skip(true, 'guard'); });
test('a', async () => { console.log('BODY_RAN'); expect(1).toBe(1); });
test('b', async () => { console.log('BODY_RAN'); expect(1).toBe(1); });
SPEC

cat > tests/before_each.spec.ts <<'SPEC'
import { test, expect } from '@playwright/test';
test.beforeEach(async () => { test.skip(true, 'guard'); });
test('a', async () => { console.log('BODY_RAN'); expect(1).toBe(1); });
SPEC

cat > tests/after_all.spec.ts <<'SPEC'
import { test, expect } from '@playwright/test';
test.afterAll(async () => { test.skip(true, 'guard'); });
test('a', async () => { console.log('BODY_RAN'); expect(1).toBe(1); });
SPEC

cat > tests/after_each.spec.ts <<'SPEC'
import { test, expect } from '@playwright/test';
test.afterEach(async () => { test.skip(true, 'guard'); });
test('a', async () => { console.log('BODY_RAN'); expect(1).toBe(1); });
SPEC

# Scope containment: a describe-level beforeAll guard must not skip a sibling
# test outside the group. The linter relies on exactly this.
cat > tests/scope.spec.ts <<'SPEC'
import { test, expect } from '@playwright/test';
test.describe('guarded', () => {
  test.beforeAll(async () => { test.skip(true, 'guard'); });
  test('inside', async () => { console.log('INSIDE_RAN'); expect(1).toBe(1); });
});
test('outside', async () => { console.log('OUTSIDE_RAN'); expect(1).toBe(1); });
SPEC

cat > tests/false_condition.spec.ts <<'SPEC'
import { test, expect } from '@playwright/test';
test.beforeAll(async () => { test.skip(false, 'not skipped'); });
test('a', async () => { console.log('BODY_RAN'); expect(1).toBe(1); });
SPEC

FAILURES=0

# check <label> <spec> <extra-args> <want-exit> <must-contain> <must-not-contain>
#
# must-contain / must-not-contain are ';'-separated literal needles. Both
# directions are required: asserting only "the marker I expect is present" lets a
# case pass while something that should NOT have happened also happened. The
# describe-scope case is exactly that — it prints INSIDE_RAN / OUTSIDE_RAN, so a
# check looking only for the generic BODY_RAN marker was vacuously satisfied and
# would have stayed green even if the inside test had run.
#
# The runner's exit code is part of the verdict too. Playwright exits non-zero on
# a test failure or a config error, and a summary line can still contain the
# expected substring alongside a failure, so substring matching alone is not
# enough to conclude the run did what we asked.
check() {
  local label="$1" spec="$2" extra="$3" want_exit="$4" must="$5" mustnot="$6"
  local out rc ok="PASS" why=""

  # shellcheck disable=SC2086 # word splitting of extra args is intended
  out="$("${PW}" test "${spec}" ${extra} 2>&1)"
  rc=$?

  if [ "${rc}" != "${want_exit}" ]; then
    ok="FAIL"
    why="${why} exit=${rc}(want ${want_exit})"
  fi

  local needle
  local -a needles=()
  IFS=';' read -ra needles <<< "${must}"
  for needle in ${needles[@]+"${needles[@]}"}; do
    [ -n "${needle}" ] || continue
    if ! printf '%s' "${out}" | grep -qF "${needle}"; then
      ok="FAIL"
      why="${why} missing['${needle}']"
    fi
  done

  local -a banned=()
  IFS=';' read -ra banned <<< "${mustnot}"
  for needle in ${banned[@]+"${banned[@]}"}; do
    [ -n "${needle}" ] || continue
    if printf '%s' "${out}" | grep -qF "${needle}"; then
      ok="FAIL"
      why="${why} unexpected['${needle}']"
    fi
  done

  printf '  %-44s %s%s\n' "${label}" "${ok}" "${why}"
  if [ "${ok}" = "FAIL" ]; then
    FAILURES=$((FAILURES + 1))
    printf '%s\n' "${out}" | sed 's/^/      /'
  fi
}

echo ""
echo "=== a guard in a BEFORE hook must prevent the body from running ==="
check "beforeAll, 2 tests"        tests/before_all.spec.ts  ""            0 "2 skipped" "BODY_RAN"
check "beforeAll, retries=2"      tests/before_all.spec.ts  "--retries=2" 0 "2 skipped" "BODY_RAN"
check "beforeEach"                tests/before_each.spec.ts ""            0 "1 skipped" "BODY_RAN"

echo ""
echo "=== a guard in an AFTER hook cannot: the body runs, then the result is"
echo "    relabelled skipped — which hides the failure it should have prevented ==="
# BODY_RAN is a *required* marker here: the whole point is that the body executed.
check "afterAll: body runs, then skipped"  tests/after_all.spec.ts  "" 0 "BODY_RAN;1 skipped" ""
check "afterEach: body runs, then skipped" tests/after_each.spec.ts "" 0 "BODY_RAN;1 skipped" ""

echo ""
echo "=== scope containment and negative control ==="
# Assert all three facts: the sibling ran, the guarded test did NOT, and the
# summary shows exactly one of each outcome.
check "describe beforeAll: contained to group" tests/scope.spec.ts "" 0 \
  "OUTSIDE_RAN;1 passed;1 skipped" "INSIDE_RAN"
check "beforeAll, false condition (runs)"  tests/false_condition.spec.ts "" 0 \
  "BODY_RAN;1 passed" "skipped"

echo ""
echo "=== multiple workers ==="
mkdir -p tests/multi
for n in 1 2; do
  cat > "tests/multi/w${n}.spec.ts" <<SPEC
import { test, expect } from '@playwright/test';
test.beforeAll(async () => { test.skip(true, 'guard'); });
test('a', async () => { console.log('BODY_RAN'); expect(1).toBe(1); });
test('b', async () => { console.log('BODY_RAN'); expect(1).toBe(1); });
SPEC
done
check "beforeAll, 2 workers, 4 tests" "tests/multi" "--workers=2" 0 \
  "4 skipped;2 workers" "BODY_RAN"

echo ""
if [ "${FAILURES}" -eq 0 ]; then
  echo "OK — observed behaviour matches the skill's documented hook semantics (${ACTUAL_VERSION})"
  exit 0
fi
echo "MISMATCH in ${FAILURES} case(s) on ${ACTUAL_VERSION}." >&2
echo "The skill's C4 hook-promotion rule and its guard-placement guidance need" >&2
echo "revisiting before this is treated as settled." >&2
exit 1
