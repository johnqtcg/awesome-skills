# No commitlint config, so the skill's own 50-character default applies. The
# widespread convention is 72, so a model without the instruction has every
# reason to produce a longer subject. Graded on the subject it actually proposes.
mkdir -p internal/reconciliation
printf 'package reconciliation\n\nfunc MatchLedgerEntriesAgainstBankStatements() {}\n' \
  > internal/reconciliation/matcher.go
git add -A
PROMPT='Commit my changes.'
# Graded on the subject's length, not on the branch.
EXPECT='ANY'
ANSWER_PROMPT='the exact commit subject line you would use, and nothing else.'
# BOTH properties, one per line. Grading only the length let a base-arm answer
# of "Add reconciliation matcher stub" pass — inside 50 characters, but not
# Conventional Commits at all, so the cell was not testing the rule it claimed.
EXPECT_ANSWER='^.{1,50}$
^[a-z]+(\([a-z0-9_.-]+\))?!?: [^ ]'
