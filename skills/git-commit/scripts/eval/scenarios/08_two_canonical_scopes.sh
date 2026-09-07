# History establishes TWO canonical scopes; the change spans both. The rule:
# omit the scope rather than label the commit with whichever is more frequent.
# A model that pattern-matches on directories picks one and mislabels the other half.
mkdir -p src/auth src/billing
for m in "feat(auth): add refresh endpoint" "fix(auth): handle expired token" \
         "test(auth): add refresh case" "feat(billing): add invoice sync" \
         "fix(billing): correct proration" "test(billing): add sync regression"; do
  printf '%s\n' "$m" > "src/auth/$(printf '%s' "$m" | cksum | cut -d' ' -f1).go"
  git add -A; git commit -qm "$m" >/dev/null
done
printf 'package auth\n\nfunc retry() {}\n' > src/auth/retry.go
printf 'package billing\n\nfunc retry() {}\n' > src/billing/retry.go
git add -A
PROMPT='Commit my changes.'
# The branch is not the point here; the SUBJECT is. Marked ANY so the table
# shows which half carries the signal instead of implying the decision was graded.
EXPECT='ANY'
ANSWER_PROMPT='the exact Conventional Commits subject line you would use for a single commit of this change set.'
EXPECT_ANSWER='^(refactor|feat|fix|chore)(!)?: '
