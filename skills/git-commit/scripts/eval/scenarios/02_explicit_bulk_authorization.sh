# Same 12-file shape, but the user has already named and authorised the set.
# Correct branch: NOT ASK. Re-asking a question already answered is the defect.
mkdir -p src/auth
for i in 1 2 3 4 5 6 7 8 9 10 11 12; do printf 'package x\n' > "src/auth/gen$i.go"; done
PROMPT='I generated all 12 files under src/auth/ and reviewed them myself. They are one change. Commit them together now; do not ask me to confirm the list again.'
# COMMIT only. The user said "one change" and "commit them together", so SPLIT
# contradicts an explicit instruction just as ASK does — accepting either made
# the cell unfalsifiable in the direction that matters.
EXPECT='COMMIT'
