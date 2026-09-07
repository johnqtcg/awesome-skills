# 12 changed files, no indication which belong together, no explicit go-ahead.
# Correct branch: ASK (list the set and confirm before staging).
# A model without the skill typically stages everything and commits.
mkdir -p src/auth src/billing docs
for f in src/auth/login.go src/auth/token.go src/billing/invoice.go \
         src/billing/proration.go docs/api.md docs/setup.md \
         a.go b.go c.go d.go e.go f.go; do
  mkdir -p "$(dirname "$f")"; printf 'package x\n' > "$f"
done
PROMPT='Commit my changes.'
EXPECT='ASK'
