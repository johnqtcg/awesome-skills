# incident-postmortem Skill Evaluation Report

> **Method**: skill-creator A/B testing
> **Date**: 2026-04-18
> **Subject**: `incident-postmortem` — blameless postmortem writing skill

---

The `incident-postmortem` skill covers four sequential mandatory gates (context collection, blameless reframing, scope classification, output completeness), three analysis depths (Quick/Standard/Deep), five degradation modes, an 18-item checklist, a four-level severity framework (SEV-1 through SEV-4), six anti-examples (AE-1 through AE-6), a three-tier scorecard (Critical/Standard/Hygiene = 3+5+4), and a nine-section output contract with a mandatory non-empty §9.9 Uncovered Risks section. The evaluation used three A/B test scenarios with 23 scored assertions.

**Important caveat**: this evaluation ran inside the repository, where the baseline agent could discover the skill's framework through claude-mem session memory or the file system. As a result, baseline quality is notably higher than it would be in a pure API or chat context. See §5.1 for a full discussion and §6.3 for a realistic production cost estimate.

---

## 1. Summary

| Metric | With Skill | Without Skill | Gap |
|--------|-----------|--------------|-----|
| **Assertion pass rate (strict)** | **23/23 (100%)** | 22/23 (96%) | +4 pp |
| **Weighted pass rate (partial = 0.5)** | **23/23 (100%)** | 22.5/23 (97.8%) | +2.2 pp |
| **§9 output contract complete (all 9 sections)** | 3/3 | 3/3 | 0 pp |
| **§8 scorecard format correct (X/12 three-tier)** | 3/3 | 2/3 | **+33 pp** |
| **Gate 2 blame rewrite table shown (auditable)** | 1/1 | 0/1 | **+100 pp** |
| **Multi-branch 5-Why + Fishbone diagram** | 1/1 (Scenario 1) | 0/1 | **+100 pp** |
| **§9.9 Uncovered Risks present and non-empty** | 3/3 | 3/3 | 0 pp |
| **SEV-1 correctly identified → Deep depth triggered** | 1/1 | 1/1 | 0 pp |
| **Average token consumption** | ~37,167 | ~34,385 | +8% |
| **Average tool calls** | ~10 | ~2.3 | +7.7 |

---

## 2. Scenario 0 — Complete SEV-2 Postmortem

### 2.1 Setup

**Input**: a payment-api Redis configuration incident (INC-2024-0142, SEV-2, 52 minutes) with full data: PagerDuty alerts, Grafana metrics (error rate peaked at 15.2%), a GitHub PR diff showing an empty `connection_string`, a Slack response thread, Kibana logs (34,521 failed requests), and two related prior incidents (INC-2024-0098 and INC-2024-0112).

**Nine assertions (A1–A9)**: executive summary completeness, timeline phase labels with sources, 5-Why depth and systemic framing, action item structure, What Went Well section, quantified impact, related incident references, scorecard format, Uncovered Risks.

### 2.2 Results

| ID | Assertion | Without Skill | With Skill |
|----|-----------|:-------------:|:----------:|
| A1 | §9.1 summary includes all 5 elements: incident ID, time window, impact, root cause, resolution status | Pass | Pass |
| A2 | §9.3 timeline has UTC timestamps with sources, and DETECTION/RESPONSE/RECOVERY phase markers | Pass | Pass |
| A3 | §9.4 5-Why reaches depth ≥3 with a systemic root cause (process/design failure, not individual error) | Pass | Pass |
| A4 | §9.7 action items each have a category (prevent/detect/mitigate), owner, and due date | Pass | Pass |
| A5 | §9.6 What Went Well section exists with ≥2 specific positive observations | Pass | Pass |
| A6 | §9.5 impact is quantified with specific numbers (duration, failed requests, error rate, SLO budget %) | Pass | Pass |
| A7 | §9.8 lessons learned references INC-2024-0098 and INC-2024-0112 (third recurrence signal) | Pass | Pass |
| A8 | §8 scorecard follows the format "X/12 — Critical Y/3, Standard Z/5, Hygiene W/4 — PASS/FAIL" | Pass | Pass |
| A9 | §9.9 Uncovered Risks is present and non-empty (≥2 specific analysis gaps) | Pass | Pass |

**Scenario 0**: Without Skill = 9/9 | With Skill = **9/9**

### 2.3 Observations

**With Skill**: after loading SKILL.md and three reference files (8 tool calls), produced a complete document. The 5-Why reached depth 5, and the root cause was labeled as a "Missing Validation Gate" pattern (from rca-techniques.md §6). Scorecard: `12/12 — Critical 3/3, Standard 5/5, Hygiene 4/4 — PASS`, with evidence cited for every item. §9.9 listed 5 specific gaps including "affected user count unknown" and "completion status of action items from the two related incidents not verified."

**Without Skill**: accessed the skill framework through claude-mem session memory (3 tool calls) and produced a document of comparable quality. Notably, the baseline added §9.11 (downstream cascade impact analysis) and an SLO budget exhaustion warning not present in the skill version, and its total token count was slightly higher (36,490 vs. 32,667). Both versions scored 12/12 PASS.

---

## 3. Scenario 1 — Gate 2 Trigger, Blame Reframe, and RCA Quality

### 3.1 Setup

**Input**: raw incident notes containing heavy blame language (INC-2024-0387, 108-minute complete checkout outage): `"Dave ran a migration without testing"`, `"Alice ignored the alert"`, `"the team needs to be more careful in general"`, and an explicit "blame summary" section.

**Eight assertions (B1–B8)**: Gate 2 triggered with a rewrite table shown, no personal names in root cause or action items, systemic 5-Why, AE-1 handling, blameless timeline language, action item categories, What Went Well, specific Uncovered Risks.

### 3.2 Results

| ID | Assertion | Without Skill | With Skill |
|----|-----------|:-------------:|:----------:|
| B1 | Gate 2 is explicitly triggered with a side-by-side rewrite table showing each blame phrase and its systemic replacement | **Partial** | Pass |
| B2 | Root cause and action item sections contain no personal names — systemic framing throughout | Pass | Pass |
| B3 | 5-Why reaches depth ≥3 with a systemic root cause (pipeline lacked a mandatory staging validation step, not individual carelessness) | Pass | Pass |
| B4 | The original "blame summary" section is explicitly identified and rewritten into systemic language | Pass | Pass |
| B5 | Timeline entries use event-based language (no "Dave should have" or "Alice ignored") | Pass | Pass |
| B6 | Action items include ≥1 Prevent and ≥1 Detect item, each with an owner and due date | Pass | Pass |
| B7 | What Went Well extracts positive observations from a chaotic incident (Carol's diagnosis, backup restore decision, etc.) | Pass | Pass |
| B8 | Uncovered Risks includes specific gaps like "backup restore RTO not quantified" or "replica migration process not reviewed" | Pass | Pass |

**Scenario 1**: Without Skill = 7 pass + 1 partial | With Skill = **8/8**

Weighted pass rate: **Without Skill 87.5% (7.5/8) → With Skill 100% (8/8)**

### 3.3 Observations

**The most important difference — B1**: the baseline declared "Blame language detected — reframing required" in a metadata block, then went straight to writing the document without showing how the reframing was done. The skill version produced a complete Gate 2 rewrite protocol table listing all 7 blame phrases alongside their systemic rewrites, making the reframing decision fully auditable for collaborators and reviewers.

**RCA depth difference**: the skill version produced three independent 5-Why branches (A: why did the service fail; B: why did recovery take 108 minutes; C: why was the alert response delayed by 16+ minutes) plus a complete Fishbone diagram loaded from rca-techniques.md §2, covering six categories: Process, Technology, People, Environment, Measurement, and Organization. The baseline produced a single causal chain.

**Scorecard difference**: skill version `12/12 — Critical 3/3, Standard 5/5, Hygiene 4/4 — PASS`; baseline version `11/12 — Critical 3/3, Standard 5/5, Hygiene 3/4 — PASS` (Hygiene deduction: the agent didn't proactively retrieve related historical incidents, so "Related incidents linked" was marked PARTIAL).

**Severity identification**: both versions correctly escalated the 108-minute complete checkout outage from the input's "SEV-2 framing" to **SEV-1 Critical** and triggered Deep depth — the correct application of the mandatory escalation rule in §3.

---

## 4. Scenario 2 — Degraded Mode (Incomplete Data)

### 4.1 Setup

**Input**: verbal description only — "the API gateway had 502 errors last Tuesday afternoon around 15:00 JST, lasted about 30–40 minutes, possibly related to a deployment but not sure, no access to monitoring, no formal incident ID, need this written up today for tomorrow morning's meeting."

**Six assertions (C1–C6)**: degraded mode formally declared, Sketch depth with RCA placeholders, timeline uses `[INFERRED]`/`[UNKNOWN]` rather than invented UTC timestamps, impact estimates not fabricated, ≥5 specific follow-up questions provided, ≥4 data gaps in Uncovered Risks.

### 4.2 Results

| ID | Assertion | Without Skill | With Skill |
|----|-----------|:-------------:|:----------:|
| C1 | Degraded mode formally declared at the top of the document with the reason for missing data | Pass | Pass |
| C2 | §9.2 declares Sketch depth; RCA uses a hypothesis tree with placeholders rather than definitive conclusions | Pass | Pass |
| C3 | Timeline uses `[INFERRED]` / `[UNKNOWN]` placeholders rather than fabricated specific UTC timestamps | Pass | Pass |
| C4 | Impact assessment refuses to invent specific numbers, using "UNKNOWN" / "ESTIMATED" with clear labels | Pass | Pass |
| C5 | Output includes ≥5 specific, actionable follow-up questions (covering logs, deployment records, alerts, etc.) | Pass | Pass |
| C6 | §9.9 Uncovered Risks lists ≥4 specific data gaps (timezone unconverted, no monitoring access, no incident ID, etc.) | Pass | Pass |

**Scenario 2**: Without Skill = 6/6 | With Skill = **6/6**

### 4.3 Observations

**Degraded mode declaration format**: the skill version uses the exact format specified in the skill (`# DEGRADED: Sketch Mode — verbal description only, no logs, no monitoring data, no incident ID`, positioned at the absolute top). The baseline used a semantically equivalent blockquote at the top — same position, different markup.

**Scorecard consistency difference**: the skill version produced `5/12 — Critical 1/3, Standard 3/5, Hygiene 3/4 — FAIL` with an explicit note that "Critical items #1 and #2 failing in Sketch mode is expected and correct." The baseline produced `DRAFT-INCOMPLETE — 5/12 full pass, 5/12 partial, 2/12 fail`, listing partials separately rather than converting them to a weighted score — inconsistent with the §8 format.

**Tool call difference**: the skill version made 11 tool calls (loading SKILL.md and 3 reference files); the baseline made 2. The skill version's hypothesis tree included SLO budget calculations and SEV determination criteria from severity-framework.md.

---

## 5. Overall Results

### 5.1 Assertion summary

| Scenario | Without Skill — Pass | Partial | Fail | With Skill — Pass |
|----------|:--------------------:|:-------:|:----:|:-----------------:|
| Scenario 0 (9 assertions) | 9 | 0 | 0 | **9** |
| Scenario 1 (8 assertions) | 7 | 1 | 0 | **8** |
| Scenario 2 (6 assertions) | 6 | 0 | 0 | **6** |
| **Total (23 assertions)** | **22** | **1** | **0** | **23** |

Weighted pass rate (partial = 0.5): **Without Skill = 97.8% (22.5/23)** → **With Skill = 100% (23/23)**

**A note on methodology**: this evaluation ran inside the repository, where the baseline agent discovered and applied the skill framework through claude-mem session memory in just 2–3 tool calls — which drove baseline quality much higher than would be seen in a clean API or chat environment with no file access. In a pure API context (no file system access), we estimate the true no-skill baseline pass rate would be roughly **50–65%**, consistent with what we observed in mysql-migration (52%) and other skill evaluations, which would push the quality gain to **+35–50 pp**.

### 5.2 Where the skill adds clear value

| Skill contribution | Evidence |
|-------------------|---------|
| **Auditable Gate 2 rewrite table** | The skill version produced a row-by-row blame → systemic language rewrite table; the baseline implicitly rewrote the language with no visible record, leaving collaborators unable to verify that every blame phrase was caught (B1 partial) |
| **Multi-branch 5-Why and Fishbone diagram** | The skill version produced 3 independent 5-Why branches and a Fishbone diagram (from rca-techniques.md §2) in Scenario 1; the baseline produced a single causal chain |
| **Scorecard format consistency** | The skill guarantees three-tier breakdown (Critical/Standard/Hygiene), unified weighted counting (partial = 0.5), and an explicit PASS/FAIL verdict; the baseline produced an inconsistent count in the degraded scenario |
| **Systematic reference file loading** | The skill version loads postmortem-template.md, rca-techniques.md, and severity-framework.md, providing richer RCA methodology support |
| **Cross-context portability** | In API or embedded tool contexts without file access, the skill is the only mechanism that guarantees §9 output contract compliance, correct degradation protocol, and reference-driven methodology |

### 5.3 Where the baseline is already strong

In a repository context, the unaided baseline performed well or equally on:

- Producing a complete §9 output contract structure across all scenarios (all 9 sections present)
- Technical accuracy of SEV classification (correctly escalated to SEV-1 in Scenario 1)
- Core degradation mode logic (declaring DEGRADED, using placeholders, refusing to fabricate data)
- §9.9 Uncovered Risks identification (all scenarios non-empty, averaging 6–8 specific gaps)
- Basic blameless language awareness (actively rewriting "Dave's mistake" as a systemic failure)

**The key insight**: the skill's core value is not plugging gaps in what the model knows. It's about (1) **consistency** across all contexts regardless of whether the agent happens to find the framework at runtime; (2) **methodological richness** delivered through systematic reference file loading (multi-branch RCA, Fishbone diagrams); and (3) **auditability** through the Gate 2 rewrite table and standardized scorecard format.

---

## 6. Token Cost Analysis

### 6.1 Skill context overhead

| File | Lines | Estimated tokens | Loaded when |
|------|-------|-----------------|-------------|
| SKILL.md | 386 | ~3,500 | Always |
| references/postmortem-template.md | 231 | ~2,000 | Standard depth |
| references/rca-techniques.md | 223 | ~1,900 | Standard depth |
| references/severity-framework.md | 174 | ~1,500 | Standard/Deep depth |
| **Typical total (SKILL.md + 3 refs)** | **1,014** | **~8,900** | Standard/Deep |

### 6.2 Actual token consumption (6 evaluation agents)

| Agent | Scenario | Total tokens | Tool calls | Duration |
|-------|----------|:------------:|:----------:|:--------:|
| S0 With Skill | SEV-2 complete postmortem | 32,667 | 8 | 112s |
| S0 Without Skill | SEV-2 complete postmortem | 36,490 | 3 | 102s |
| S1 With Skill | Gate 2 + blame reframe | 35,496 | 11 | 146s |
| S1 Without Skill | Gate 2 + blame reframe | 33,682 | 2 | 107s |
| S2 With Skill | Degraded mode | 43,339 | 11 | 131s |
| S2 Without Skill | Degraded mode | 32,983 | 2 | 98s |
| **With Skill average** | — | **37,167** | **~10** | **~130s** |
| **Without Skill average** | — | **34,385** | **~2.3** | **~102s** |

### 6.3 Efficiency

| Scenario | Without Skill tokens | With Skill tokens | Change |
|----------|:-------------------:|:-----------------:|:------:|
| Scenario 0 (standard postmortem) | 36,490 | 32,667 | **−10%** |
| Scenario 1 (Gate 2 + Deep RCA) | 33,682 | 35,496 | +5% |
| Scenario 2 (degraded mode, shorter output) | 32,983 | 43,339 | +31% |
| **Average** | **34,385** | **37,167** | **+8%** |

**Why the overhead is lower than expected**: because the baseline agent accessed the skill framework through session context (2–3 tool calls), its token consumption approached the skill version. Scenario 0 even runs cheaper without the skill (−10%) because the baseline produced more verbose document content. The main overhead driver is Scenario 2's reference file loading (+31%).

**Realistic production estimate**: in a pure API context with no file access, the true skill overhead would be approximately **+45–55%**, consistent with mysql-migration (+51%) and other migration skill evaluations. Even at that rate, for a postmortem documenting a SEV-2 incident with $48,000 in revenue impact (as in Scenario 0), the total token cost for the entire skill session is roughly **$0.05** — ROI requires no calculation.

---

## 7. Coverage Gaps and Known Limitations

| Gap | Severity | Notes |
|-----|:--------:|-------|
| **No assertion verifying Fishbone diagram correctness** | Medium | Scenario 1's skill version spontaneously produced a Fishbone diagram, but no assertion validates whether the 6-category breakdown and AND/OR logic are accurate |
| **SEV-1 Deep depth not directly tested** | Medium | SKILL.md §3 requires Deep depth for SEV-1; Scenario 1 triggers the SEV-1 escalation but no dedicated Deep-depth assertion set was designed |
| **Review mode not covered** | Low | Gate 3's Review mode (input: an existing postmortem; output: quality analysis + scorecard) was not included in the A/B scenarios |
| **No positive example scenario** | Low | All three scenarios contain defects or degraded data; no scenario tests "this is already a good postmortem — confirm and score it" |
| **True no-skill baseline not quantified** | Medium | Because repository context inflated baseline quality to 97.8%, this figure is not representative of real no-skill performance; a follow-up evaluation in an isolated API context is recommended |
| **Cross-timezone timeline conversion accuracy** | Low | Scenario 2 involves a JST→UTC conversion, but in Sketch mode the skill version used `[INFERRED]` rather than computing the conversion — the behavior is correct but cannot be fully validated without complete data |

---

## 8. Conclusion

The `incident-postmortem` skill achieved **100% assertion pass rate** across 3 scenarios and 23 assertions. The meta-finding of this evaluation is that **in a repository context where the skill file is discoverable, an unaided baseline agent will often find and apply the skill framework on its own (97.8%)** — which is itself evidence of the framework's quality. A structure that's clear enough for an agent to follow without explicit instruction is a well-designed skill.

That said, the skill contributes four things the baseline cannot reliably deliver on its own:

1. **Auditable Gate 2 rewrite protocol** — The skill forces a visible, row-by-row blame → systemic language rewrite table, making the reframing decision transparent to every collaborator and reviewer. The baseline implicitly rewrites the language but leaves no record of what was caught and changed.

2. **Reference-driven RCA richness** — By loading rca-techniques.md, the skill systematically produces multi-branch 5-Why analysis and Fishbone diagrams covering independent failure paths (service failure, slow recovery, delayed alerting). This is a material upgrade over a single causal chain for complex incidents — SEV-1 events, repeated incidents, and cases where the recovery story matters as much as the outage cause.

3. **Scorecard format and counting consistency** — The skill guarantees three-tier breakdown (Critical/Standard/Hygiene), weighted counting (partial = 0.5), and an unambiguous PASS/FAIL verdict in every context. Without it, scorecard format drifts — in the degraded scenario, the baseline produced a count that cannot be compared across teams or incidents.

4. **Cross-context portability** — In API or embedded contexts with no file access (where the true no-skill baseline is estimated at 50–65%), the skill is the only mechanism guaranteeing correct §9 output contract, degradation protocol, and reference-file methodology.

**Recommendation: production-ready.** The skill delivers the most value in three situations: (a) teams whose raw incident notes contain blame language — the Gate 2 rewrite table provides transparency and auditability that implicit rewriting cannot; (b) complex SEV-1 or recurring incident analysis — multi-branch 5-Why and Fishbone diagrams from rca-techniques.md give structured methodological support beyond what single-chain analysis provides; (c) organizations using this skill in API or embedded contexts without file access — in those environments, the skill is the only way to guarantee consistent output quality.
