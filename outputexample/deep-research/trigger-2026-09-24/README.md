# Trigger-rate re-measurement, 2026-09-24

Same 20-query eval set as `../ab-2026-09-08/three-dimension/trigger_eval_set.json`, same
detector (Skill tool naming `deep-research`, or a Read of its SKILL.md), 3 runs per query,
`--max-turns 4`, the user's default model, 102 skills installed. The personal copy at
`~/.claude/skills/deep-research/SKILL.md` had only its `description` block swapped per cell,
and was restored byte-identical afterwards (`run_new.sh` checks the description before and
after every cell).

| Cell | Description | Listing budget | Should-trigger runs | Query-level recall | False triggers |
|---|---|---|---|---|---|
| `old_default_pos.json` | before 2026-09-24 | default (30,000 chars vs 44,715 listed) | 11/30 = 37% | 4/10 | not run |
| `new_default_all.json` | 2026-09-24 rewrite | default | 14/28 = 50% (2 timeouts excluded) | 5/10 | 0/30 |
| `new_bigbudget_pos.json` | 2026-09-24 rewrite | `SLASH_COMMAND_TOOL_CHAR_BUDGET=200000` | 16/29 = 55% (1 timeout excluded) | 5/10 | not run |

**Reading.** The rewrite moved the classes it targeted — code-base investigation (q03 0→2/3),
contradicting manual pages (q08 0→2/3 and 3/3), claim refutation (q01 0→1/3) — with no false
triggers. Raising the listing budget added little (50% → 55%), so description truncation is not
the main cause of the remaining misses. At 28–30 runs per cell the 95% interval on each rate is
roughly ±18 points: the improvement is directional, not significant, and recall is far from the
90% bar.

**What still loses.** q04 (document TLS config against NIST for an audit) and q05 (verify a
vendor's uptime claims before signing) stay at 0/3 in every cell. q04 goes straight to
`Bash`/`Read`; q05 goes to the claude-mem memory search tool. q01 and q06 mostly go to
`ToolSearch` → `WebSearch`. The model reaches for a direct tool when it believes it can answer,
which description wording has not overcome.

`new_default_all.CONTAMINATED.json` from the first attempt is not kept: the installed copy was
restored mid-cell, so those runs mixed both descriptions.
