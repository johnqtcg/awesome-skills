# One real fix plus an unrelated whitespace-only reformat of a different package.
# Correct branch: SPLIT (one commit = one logical change).
mkdir -p internal/auth internal/report
printf 'package auth\n\nfunc Refresh() error {\n\tif tok == nil {\n\t\treturn ErrNil\n\t}\n\treturn nil\n}\n' > internal/auth/refresh.go
printf 'package report\n\nfunc Render()  {\n}\n' > internal/report/render.go
git add -A && git commit -qm "chore: seed"
printf 'package auth\n\nfunc Refresh() error {\n\tmu.Lock()\n\tdefer mu.Unlock()\n\tif tok == nil {\n\t\treturn ErrNil\n\t}\n\treturn nil\n}\n' > internal/auth/refresh.go
printf 'package report\n\nfunc Render() {\n}\n' > internal/report/render.go
PROMPT='Commit my changes.'
EXPECT='SPLIT|ASK'
