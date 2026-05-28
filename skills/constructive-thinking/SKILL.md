---
name: constructive-thinking
description: Compress chaotic information into a leader-ready structure before output. ALWAYS use when the user is preparing to brief a senior leader, present a technical proposal, write a one-pager, or otherwise turn scattered facts and feelings into Frame → Crux → Nodes → Tilt + Reasoning that fits in 3–5 minutes of reading. Trigger phrases include "向领导汇报", "做技术方案 presentation", "整理思路", "report up", "brief the boss", "summarize for leadership", "executive briefing", "one-pager". NOT for writing the final polished document (use tech-doc-writer), NOT for decomposing tasks into implementation steps (use writing-plans), NOT for incident root-cause analysis (use incident-postmortem), NOT for aggregating research with citations (use deep-research).
allowed-tools: Read, Write, Edit, Grep, Glob
---

# constructive-thinking

Turn messy thinking into a leader-ready structure. The skill teaches a **method**, not a writing template — the method compresses chaos into a five-element brief: **Frame → Crux → Nodes → Tilt → Reasoning**.

A senior leader does not have thirty minutes to absorb your story. They need you to put the structure on the table in three. This skill is the thinking discipline that makes that possible.

---

## When to Use

Use this skill when the user is about to **output** something to an audience whose time is more valuable than their patience, and the raw material in their head is unstructured:

- Briefing a senior leader on a technical decision or status
- Pitching a proposal (RFC, ADR, project plan) and needs the one-page summary to land
- Reporting up after an investigation (not the formal postmortem — the verbal brief)
- Preparing slides or talk track for a presentation
- Summarizing a long thread / Slack / email storm for someone who only has 3 minutes
- Drafting an executive summary or TL;DR for any longer artifact
- Cross-functional update where the audience does not share your context

Trigger phrases observed in practice (CN + EN):

> "向领导汇报", "整理思路", "做技术方案的 presentation", "做个 one-pager", "report up", "brief the boss", "summarize for leadership", "executive briefing", "TL;DR", "the main point"

## When NOT to Use

Route to a different skill when:

| Situation | Use this instead |
|---|---|
| Writing the **final polished document** (RFC, runbook, API doc) | `tech-doc-writer` |
| Decomposing a feature into **implementation steps** | `writing-plans` |
| Conducting **root cause analysis** on a specific incident | `incident-postmortem` |
| Aggregating **research with sources and citations** | `deep-research` |
| Formatting a **GitHub PR description** | `create-pr` / `commit` |
| User wants to **brainstorm freely** — explore, not compress | (no skill — chat) |

A useful test: if the user is going to **write something next**, use `tech-doc-writer`. If they are going to **speak to a human next**, use this skill. If they are going to **build something next**, use `writing-plans`.

---

## Core Method

The five elements come directly from how senior leaders actually consume information:

| Element | What it answers | One-line discipline |
|---|---|---|
| **Frame** (框架) | *What kind of problem is this?* | One sentence; pick from the five-frame catalog |
| **Crux** (核心矛盾) | *What makes the simple answer wrong?* | Exactly one dominant tension — never a list |
| **Nodes** (关键节点) | *What are the 3–5 things I must know?* | MECE, ordered by decision-relevance |
| **Tilt** (倾向方案) | *What do you recommend?* | A committed position, no hedging |
| **Reasoning** (理由) | *Why this over the obvious alternative?* | 2–3 bullets; include the risk you accept |

The first sentence of the output is the Tilt restated as **BLUF** (Bottom Line Up Front). The leader can stop reading there and still be 80% informed.

This is the Pyramid Principle applied to verbal/written briefing: answer first, then the structure that supports it.

---

## Mandatory Gates

Four serial blockers. Any failure halts execution — back up and rework, do not bypass.

### Gate 1 — Audience & Compression Budget

Before structuring anything, name two facts:

1. **Who** is the primary reader/listener? (CEO / VP / peer lead / cross-functional partner / committee)
2. **How much time** do they have? (1 min hallway / 3 min slide / 5 min one-pager / 15 min meeting)

If either is unknown, ask **one** targeted question of the user. Do not proceed without both.

> Why: a 1-minute hallway brief for a CEO and a 15-minute walkthrough for a peer engineer have completely different Node selections and depth. The compression budget determines what gets cut.

### Gate 2 — Frame Selection

Classify the problem into exactly **one** of five shapes:

- **Decision** — "we need to pick between A and B"
- **Status** — "where are we on X"
- **Diagnosis** — "what's wrong and why"
- **Proposal** — "I want to do X, asking for approval/resources"
- **Escalation** — "this is blocked and needs you specifically"

If the input feels like two frames at once, the audience will not be able to follow. Force a primary frame; mention the secondary frame inside a Node, never as a parallel structure.

See `references/frameworks-library.md` for what Crux and Nodes typically look like in each frame.

### Gate 3 — Crux Identification

There must be **exactly one** Crux. The phrasing should make the leader say "ah, that's the thing."

Failure modes (halt and rework if you see these):

- "It depends on X **and** Y **and** Z" — pick the dominant one; the others become Nodes
- "There are three core issues" — there are not. There is one Crux; the rest are symptoms or Nodes
- The Crux is just a restatement of the Frame — it must name the *tension*, not the problem space

A good Crux always has a *but* or *however* inside it, explicit or implicit. Example: "We can ship Q3 **but** only by cutting feature X, which the design team has already promised to a customer."

### Gate 4 — Tilt Commitment

State a recommendation. Take a position.

Failure modes (halt and rework):

- "I see pros and cons of both options" — pick one
- "It depends on what leadership prioritizes" — make the call you would make and let leadership override
- Hedging language inside the Tilt itself: "perhaps", "maybe", "可能", "也许", "could consider"

The user can override your Tilt — that is fine and expected. But the skill output must commit first. A briefing without a recommendation wastes the leader's time on a decision they thought you had already done the work to support.

---

## Workflow

1. **Collect** raw input from the user. Accept facts, feelings, half-thoughts, slack threads, anything. Do not start structuring yet.
2. **Run Gate 1** (Audience + Budget). Ask one clarifying question if either is missing.
3. **Run Gate 2** (Frame). If uncertain between two frames, load the matching section of `references/frameworks-library.md`.
4. **Extract Nodes** — list every fact/decision/dependency that surfaces, then collapse to ≤5 by importance to the chosen Frame. Apply MECE (Mutually Exclusive, Collectively Exhaustive).
5. **Run Gate 3** (Crux). Surface the one dominant tension.
6. **Run Gate 4** (Tilt). Commit a recommendation. Write the Reasoning as 2–3 bullets including one bullet that names the risk you accept.
7. **Render** per Output Contract below. Language: match the user's invocation language (Chinese → CN labels; English → EN labels). Target ≤ 250 words for the full brief.

If the user changes the audience or budget mid-flow, restart from Gate 1 — the structure is not portable across audiences.

---

## Output Contract

Render in this exact shape. Section labels switch by language.

**English mode:**

```
【BLUF】
<single sentence stating the recommendation, no preamble, no warmup>

【Frame】
<what kind of problem this is, in one sentence>

【Crux】
<the one core conflict / constraint that makes the simple answer wrong>

【Key Nodes】
1. <node — fact, decision point, or dependency>
2. <node>
3. <node>

【Tilt】
<my recommendation — a verb-led sentence>

【Reasoning】
- <why this beats the obvious alternative>
- <the second strongest reason>
- <the risk I accept by choosing this>
```

**Chinese mode** (use these labels when the user invokes in Chinese):

```
【顶层结论】
<一句话讲清推荐方案，开门见山，不要铺垫>

【框架】
<这个事情本质上是哪类问题，一句话>

【核心矛盾】
<让简单答案站不住的那一个张力，一句话>

【关键节点】
1. <节点 —— 事实 / 决策点 / 依赖>
2. <节点>
3. <节点>

【倾向方案】
<我的推荐 —— 用动词开头的一句话>

【理由】
- <为什么这个比显而易见的另一选项更好>
- <第二条最有力的理由>
- <选择这个我接受的风险>
```

### Output Contract — hard rules

- **BLUF / 顶层结论 is the first non-label line.** No "background:", no "as discussed,", no preamble.
- **Nodes: 3–5 only.** Two is too few (the leader will sense thinness). Six is too many (you failed to compress).
- **Crux is one sentence.** If you wrote "and" twice, you have two Cruxes — collapse.
- **No hedging in Tilt.** Forbidden words: *perhaps*, *maybe*, *might want to*, *could consider*, *可能*, *也许*, *或许*, *建议考虑*. Use *ship*, *adopt*, *delay*, *cut*, *escalate*, *approve*, *上线*, *砍掉*, *延后*, *升级*, *批准*.
- **Reasoning includes the accepted risk.** A briefing that pretends there is no downside loses credibility immediately. Name the risk in one bullet.
- **Target ≤ 250 words total** (≤ 400 Chinese characters). Fits on one screen.

### Optional: Audience-tuned variants

After rendering the standard brief, if the user names a tight time budget (e.g., "I have 60 seconds"), additionally produce a **collapsed variant**:

```
【BLUF】 <recommendation>
【Crux】 <one sentence>
【Tilt】 <verb-led sentence>
```

This is the hallway version. Drop Frame, Nodes, and Reasoning. The leader will ask for the missing pieces if they want them.

---

## Anti-Patterns

Recognize and rework these failure modes before delivering.

### AP-1 — Background-first ramble
- **BAD**: "So last quarter we started looking at the indexing pipeline, and over time we noticed..."
- **GOOD**: "【BLUF】 Re-shard the indexing pipeline now; accept a 4-hour read-only window Saturday night."

The reader earned the right to background by reading the brief, not the other way around.

### AP-2 — Overlapping Nodes
- **BAD**: Nodes = [latency is high, p99 is degraded, slow queries, DB is the bottleneck]
- **GOOD**: Nodes = [DB write contention is the bottleneck, two read replicas are saturated, the new index plan reduces both]

The BAD list says the same thing four ways. The GOOD list passes MECE.

### AP-3 — Crux as a problem space, not a tension
- **BAD**: "Crux: we need to balance performance and cost."
- **GOOD**: "Crux: the cheapest fix (add a replica) lands in 6 weeks; the only fix that lands before the holiday freeze costs 3× as much."

"Balance X and Y" is not a Crux — it's a topic. A real Crux names a *binding* constraint.

### AP-4 — Tilt-less brief
- **BAD**: "Tilt: we should discuss whether option A or B fits leadership's priorities better."
- **GOOD**: "Tilt: ship option B. Accept the 2-week delay; reject option A's tech-debt cost."

If you cannot commit, you are not ready to brief — go back to Gate 4.

### AP-5 — Hedge-soup Reasoning
- **BAD**: "This *could* work, *probably* aligns with our roadmap, and *might* be acceptable."
- **GOOD**: "This unblocks the Q4 launch deterministically. Eats $50k in extra compute. Risk: locks us into vendor X for 12 months."

Hedge words signal you have not done the thinking.

### AP-6 — Wrong-audience depth
- **BAD** (briefing CEO): Node = "We chose Postgres over Mongo because of B-tree index locality and the WAL replication semantics."
- **GOOD** (briefing CEO): Node = "Postgres unblocks the analytics team; Mongo would have cost us a 6-week migration."

The CEO does not need to know what a B-tree is. Surface only decision-relevant facts.

### AP-7 — Two frames in parallel
- **BAD**: A brief that is half "here is the status" and half "I need approval to proceed."
- **GOOD**: Pick one. If it is Proposal, the status goes inside a Node. If it is Status, the approval ask goes into the Tilt.

### AP-8 — Restating the question as the Frame
- **BAD**: User asks "what should we do about the outage?" → Frame: "we need to do something about the outage."
- **GOOD**: Frame: "Diagnosis — the outage is recurring, root cause is a leaked DB connection on the auth path."

The Frame names the *shape* of the problem, not the question.

---

## References — when to load

Load these only when the section's trigger applies. They are not in the always-on context.

| File | Load when |
|---|---|
| `references/frameworks-library.md` | Unsure which Frame fits, or want to remind yourself what Crux/Nodes typically look like for that Frame. Also covers Pyramid Principle, SCQA, MECE, BLUF in one place. |
| `references/audience-and-compression.md` | The audience is non-obvious, or the user names a tight time budget (≤ 60 seconds) and you need the compression discipline for hallway briefings. |
| `references/anti-patterns.md` | You suspect your draft is hitting one of the failure modes above and want to see more BAD → GOOD worked examples (8 examples, mix of CN and EN scenarios). |

---

## Quick reminders

- **The Tilt is the first sentence.** Everything else exists to support it.
- **One Crux. One Frame. One Tilt.** Multiplicity is failure.
- **3–5 Nodes, MECE, decision-ordered.** Not chronological, not topical.
- **Name the risk you accept.** Credibility comes from acknowledged trade-offs, not from pretending there are none.
- **Match the audience's vocabulary.** A great brief is one the audience can repeat verbatim to the next person.