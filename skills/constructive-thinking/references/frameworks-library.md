# Frameworks Library

Load this when you are unsure which **Frame** fits the user's input, or when you want a quick reminder of what Crux and Nodes typically look like inside that Frame. Also covers the four classical structured-thinking frameworks the skill is built on.

---

## The Five Frames

Every brief is one of these five shapes. Force the input into exactly one. If two seem to fit, the secondary frame belongs *inside a Node*, not in parallel.

### Frame 1 — Decision

**Trigger**: "we need to pick between A and B", "should we...", "approve / reject", "which option".

| Element | Typical content |
|---|---|
| Frame | "Decision — choosing between X and Y" |
| Crux | The tension that makes the choice non-obvious. Usually "X is faster but Y is safer" or "X costs less but Y is reversible" |
| Nodes | The 2–3 decision criteria that actually move the needle, plus one Node that names the option you are *not* recommending and why it loses |
| Tilt | The verb is "ship", "adopt", "approve", "go with", "pick" |
| Reasoning | Why your option wins on the criteria; what you accept by losing on the others |

**Anti-pattern**: presenting both options at equal weight. The Tilt has to commit.

### Frame 2 — Status

**Trigger**: "where are we on...", "update on...", "weekly review", "are we on track".

| Element | Typical content |
|---|---|
| Frame | "Status — Q3 launch readiness" |
| Crux | The single thing that determines whether the status is green/yellow/red. Almost always a *binding* constraint, not a long list of items |
| Nodes | 3 items: what is done, what is at risk, what is blocking. Plus, when relevant, what changed since last update |
| Tilt | What you are doing / asking for next. Verbs: "continue", "escalate", "rebaseline", "no action needed" |
| Reasoning | Why the trajectory holds (or doesn't); what specifically changes the answer |

**Anti-pattern**: listing every workstream's % complete. Surface only what changes the status verdict.

### Frame 3 — Diagnosis

**Trigger**: "what's wrong", "why is X broken", "root cause", "what's going on with...".

| Element | Typical content |
|---|---|
| Frame | "Diagnosis — recurring p99 spikes on the auth API" |
| Crux | The actual root cause stated as a *mechanism*, not a symptom. "A connection leak in the OAuth refresh path saturates the pool every 6 hours." |
| Nodes | The evidence chain: what we observed, what we measured, what we ruled out |
| Tilt | The fix you recommend. Verbs: "patch", "rollback", "rearchitect", "monitor", "accept-and-document" |
| Reasoning | Why this fix beats the obvious alternatives; what you accept by not doing the others |

**Anti-pattern**: presenting a list of symptoms as if they were causes. The Crux must name a mechanism.

> Note: for *formal* incident postmortems with timelines, severity classification, and tracked action items, route to `incident-postmortem`. This Frame is for the verbal brief or one-pager that goes up to leadership *before* the formal postmortem lands.

### Frame 4 — Proposal

**Trigger**: "I want to...", "proposing that we...", "ask for approval/resources", "RFC summary".

| Element | Typical content |
|---|---|
| Frame | "Proposal — invest in a dedicated search team for FY26" |
| Crux | The reason status quo is no longer acceptable. Either an opportunity slipping or a cost compounding |
| Nodes | What you propose (one sentence), what it costs (people / money / time), the second-order effect on adjacent teams |
| Tilt | The verb is "approve", "fund", "staff", "greenlight", "charter" |
| Reasoning | Why this proposal beats doing nothing and beats the cheaper variant; what you accept |

**Anti-pattern**: leading with vision and burying the ask. The ask is the Tilt; it goes first.

### Frame 5 — Escalation

**Trigger**: "we are blocked", "I need your help with...", "this needs to go up", "stuck".

| Element | Typical content |
|---|---|
| Frame | "Escalation — blocked by Vendor X SLA breach" |
| Crux | Why *this specific person* is the one who can unblock it. ("Only you can authorize the contract penalty clause.") |
| Nodes | What we tried, what didn't work, what is at risk if it stays blocked |
| Tilt | The specific action you need from the audience. Verbs: "escalate", "authorize", "intervene", "decide" |
| Reasoning | Why we are not the right person to unblock this; why waiting makes it worse |

**Anti-pattern**: making it sound like a status update when the audience needs to act. Escalations must explicitly name the action requested.

---

## The Four Underlying Frameworks

These are the classical structured-thinking frameworks this skill is built on. You do not need to teach them to the user — apply them.

### Pyramid Principle (Barbara Minto)

> Start with the answer. Then the supporting points. Then the evidence.

The skill's Output Contract *is* Pyramid Principle:

- Top of pyramid: **BLUF / Tilt** (the answer)
- Middle: **Crux + Nodes** (the supporting structure)
- Bottom: **Reasoning** (the evidence)

The leader reads the top, decides if they need more, drops down a level. They should never have to read bottom-up.

Key Minto rule applied here: **ideas at each level summarize the ideas below them**. The Tilt summarizes the Reasoning. The Crux summarizes the dominant tension. The Frame summarizes the problem shape. If a child element does not roll up cleanly into its parent, the structure is broken.

### SCQA (Situation – Complication – Question – Answer)

> Best for **Diagnosis** and **Escalation** frames.

- **Situation** — what was true and stable
- **Complication** — what changed that broke the stability
- **Question** — the question that change forces
- **Answer** — your recommendation

SCQA maps to this skill's structure:

| SCQA | Skill element |
|---|---|
| Situation | (implicit in the user's context) |
| Complication | Crux |
| Question | Frame |
| Answer | Tilt |

SCQA is useful when the user's input is full of *background* and you are struggling to identify the Crux — ask "what changed?" and "what does that change force us to decide?".

### MECE (Mutually Exclusive, Collectively Exhaustive)

> Applied to **Nodes**.

A set of Nodes is MECE if:

- **Mutually Exclusive** — no Node says the same thing twice in different words
- **Collectively Exhaustive** — the Nodes together cover everything that matters for the Tilt

Quick MECE check:

1. Read your Nodes. Could you delete one without losing decision-relevant information? If yes, delete it — it was overlapping with another.
2. Could a reasonable listener ask "but what about Z?" where Z is decision-critical and not in any Node? If yes, you are missing a Node.

MECE is the discipline that produces 3–5 Nodes, never 8.

### BLUF (Bottom Line Up Front)

> Originally a US military briefing convention. Forces the first sentence to be the conclusion.

In this skill, BLUF *is* the Tilt restated as the opening line. Two rules:

1. **No preamble.** "I think...", "Based on the analysis...", "After discussion with the team..." — all forbidden as the opening.
2. **Verb-led.** "Ship option B." "Delay the launch by two weeks." "Approve the vendor swap." Not "We could consider shipping option B."

A leader who reads only the BLUF should be 80% as informed as one who reads the full brief. If yours fails that test, the BLUF is too weak.

---

## Choosing the Right Frame When Two Seem to Fit

A common failure mode: the user's input feels like both Status *and* Proposal, or both Diagnosis *and* Decision. Pick one by asking:

> **What does the audience need to *do* after reading this?**

- Decide between options → **Decision**
- Stay informed, no action → **Status**
- Understand a problem → **Diagnosis**
- Approve / fund / staff something → **Proposal**
- Unblock you specifically → **Escalation**

The "do" determines the Frame. The other elements become Nodes.

### Concrete example

User input: "I want to update you on the auth migration. We hit a snag with the OAuth provider, I think we need to switch vendors but I want your sign-off."

- Could be Status (here is the update)
- Could be Diagnosis (here is the snag)
- Could be Proposal (asking for sign-off on vendor switch)

The "do" is: **approve the vendor switch**. So this is a **Proposal**. The status update and the diagnosis both become Nodes inside the Proposal.

---

## When the User Has No Tilt Yet

Sometimes the user genuinely does not have a recommendation — they are still thinking. The skill's Gate 4 still applies: **the skill commits a Tilt** based on the Nodes, and explicitly flags it as "best read of the evidence — open to override."

This is more useful than no Tilt because:

1. It forces the structure to actually resolve
2. The user often realizes they disagree, which surfaces their real position
3. The audience gets a position to react to, which is faster than asking them to generate one

If the user pushes back ("I'm not ready to commit"), explain: the Tilt is a *position to argue with*, not a final answer. Then ask them to either accept it, modify it, or replace it before delivery.