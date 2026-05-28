# Audience and Compression

Load this when the audience is non-obvious, or the user names a tight time budget (≤ 60 seconds) and you need the discipline to compress further.

The audience determines what gets cut. A great brief for a CEO would be a bad brief for a peer engineer, and vice versa. Compression is not the same problem at every tier.

---

## Audience tiers and what they actually care about

| Audience | Time budget | They want | They do NOT want |
|---|---|---|---|
| **CEO / C-level** | 1–3 min | The decision and the risk you accept | Implementation detail, vendor names they don't recognize, jargon |
| **VP / Director** | 3–5 min | The Tilt, the Crux, the cost (people / money / time), the second-order effect on adjacent orgs | Step-by-step plans; how-it-works |
| **Peer technical lead** | 10–15 min | All five elements at full depth; sometimes wants the rejected alternatives | Hand-wavy reasoning; missing risk acknowledgement |
| **Cross-functional partner** (PM, design, legal) | 5–10 min | The Frame heavy (so they can locate themselves), the impact on their team | Deep technical Nodes that aren't decision-relevant for them |
| **Skip-level (your manager's manager)** | 3 min | Reassurance that the right thinking has happened; the one thing that might cause them to override | Detailed history; defensive justification |
| **Committee / multi-stakeholder** | 5 min | The Frame and the Crux at full clarity (different people in the room have different priors) | Anything that assumes shared context |

The compression budget is the second variable: a CEO in a hallway gets ~30 seconds; a CEO in a scheduled 1:1 gets 3 minutes. Same audience, different budget, different brief.

---

## The four compression levels

The skill produces the **Standard brief** by default. The other levels are available when the audience demands them.

### Level 1 — Hallway / 60 seconds

```
【BLUF】 <verb-led recommendation>
【Crux】 <one sentence>
【Tilt】 <verb-led restatement>
```

Drop Frame (audience knows the problem space), drop Nodes (they will ask), drop Reasoning (they will trust you for 60 seconds).

This is the "elevator" version. Use only when the user explicitly says "I have one minute" or "they'll catch me in the hallway."

### Level 2 — One-pager / 3 minutes (Standard)

The full Output Contract: BLUF + Frame + Crux + 3–5 Nodes + Tilt + Reasoning. ≤ 250 words. This is the default.

### Level 3 — Working session / 15 minutes

The full Output Contract + an "Alternatives Considered" Node, and a "Risks not yet de-risked" line under Reasoning.

```
... standard structure ...

【Alternatives Considered】
- Option A: <why rejected>
- Option B: <why rejected>

【Reasoning】
- <why this wins>
- <accepted risk>
- <risk not yet de-risked — needs follow-up>
```

This is for peer technical leads or working groups where the audience will actively probe.

### Level 4 — Briefing pack / 30+ minutes

This is no longer this skill's job. Route to `tech-doc-writer` for the formal document. Use this skill to produce the executive summary that *sits at the top* of that document.

---

## Audience-specific surfacing rules

These rules tune which facts surface and which disappear, holding the structure constant.

### CEO / C-level

- Surface: dollar figures, customer-visible impact, competitive implications, strategic optionality
- Hide: which database, which framework, which engineer, what the diff looks like
- Use plain English even for technical decisions ("we picked the slower but more reversible option")
- Risk bullet must be in business terms, not technical terms

### VP / Director

- Surface: cost in people/quarters, blast radius to adjacent teams, what unblocks/blocks downstream work
- Hide: code-level decisions, library choices, infra primitive choices unless they have org-level cost
- They often want to know what *they* need to do — make the Tilt action-oriented if they are the audience

### Peer technical lead

- Surface everything. They want depth. They will be embarrassed if you over-summarize and they have to ask "but how does X work?"
- Crux can be technical (specific mechanism, specific tradeoff)
- Reasoning can name specific libraries / patterns
- Acknowledged risk should be technical

### Cross-functional partner

- Surface: how the decision changes *their* workstream; what input you need from them; what timeline they should plan around
- The Frame is heavier here than with technical audiences — they need to know what kind of problem this is to know how to react
- Avoid acronyms specific to your function. Define on first use even if obvious to you.

### Skip-level

- Surface: that you have a coherent position; the one factor that would make a reasonable person disagree
- Skip-levels are often *checking your judgment*, not the decision itself. Make the judgment legible.

### Committee

- Frame must be airtight — committees have asymmetric context
- Crux must be uncontroversial as a *description of the tension*, even if the Tilt is controversial
- Pre-empt the predictable objection from each function: legal, finance, security, product

---

## Compression discipline — what gets cut first

When the audience is fixed and the time budget shrinks, cut in this order:

1. **First to go**: reasoning bullets beyond the strongest one
2. **Next**: Nodes that are "nice to know" rather than decision-relevant
3. **Next**: Frame (audience can usually infer)
4. **Never cut**: Tilt, BLUF, Crux

If you cannot keep BLUF + Crux + Tilt in 60 seconds, your Crux is too long. Rewrite it.

A reliable test: read the Crux aloud at normal speaking pace. If it takes more than 8 seconds, it is wrong — collapse.

---

## Audience mismatch — when the user has the audience wrong

Sometimes the user says "I'm briefing the CEO" but the brief they've drafted is at peer-engineer depth. The skill should:

1. Render the brief at the audience's appropriate depth (not the user's draft depth)
2. Flag the mismatch explicitly: "Note: I compressed Nodes 3 and 4 — they are technical detail the CEO will not use. Kept them for your reference at the bottom."

This protects the user from the very common failure of briefing-up at the wrong altitude.

---

## Language and tone

When the user invokes in Chinese, the brief renders with CN labels. Two additional rules apply:

1. **避免英文术语滥用** — use Chinese terms where they exist; reserve English only for proper nouns and well-established technical terms (e.g., 用 "数据库" 不用 "DB"，但 "OAuth" 可以保留)
2. **不要书面化过度** — the brief should read naturally when said aloud in a meeting, not like a formal document. Avoid "兹此" "鉴于" "综上所述" style.

For both languages: the tone is *direct but not blunt*. A leader does not need to be lectured; they need to be informed. Skip the throat-clearing.