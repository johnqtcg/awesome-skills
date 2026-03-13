# Query Patterns

Use these patterns after classifying the search type and the user's goal. Prefer changing one variable at a time so you can tell what improved the results.

## Core Pattern Set

Build at least three queries:

1. Primary query
2. Precision query
3. Expansion query

Example:

- Primary: `OpenAI Responses API tool calling`
- Precision: `"Responses API" tool calling site:platform.openai.com`
- Expansion: `("Responses API" OR "Agents SDK") tool calling guide`

## Information and News

Use for latest facts, incidents, company updates, policy changes, public figures, and event status.

Patterns:

- `<topic> latest`
- `<topic> after:YYYY-MM-DD`
- `<topic> site:official-domain.com`
- `<topic> site:reuters.com`
- `"<exact phrase>" after:YYYY-MM-DD`
- `(<name variant 1> OR <name variant 2>) <topic>`

Tactics:

- Add dates early for unstable topics
- Search both the entity name and the exact product, event, or policy name
- Cross-check official statements against at least one reputable independent source

## Official Docs and Standards

Use for APIs, library docs, RFCs, policies, release notes, and vendor documentation.

Patterns:

- `<topic> site:vendor.com/docs`
- `site:vendor.com <product> <feature>`
- `site:ietf.org RFC <topic>`
- `site:github.com <repo> <feature> docs`
- `"<error text>" site:official-domain.com`

Tactics:

- Start with the vendor or standards body
- Use exact error strings in quotes
- Add version numbers when behavior changed across releases

## Technical Troubleshooting

Use for debugging errors, stack traces, and implementation edge cases.

Patterns:

- `"<exact error message>"`
- `"<exact error message>" site:stackoverflow.com`
- `"<exact error message>" site:github.com`
- `<library> <symptom> after:YYYY-MM-DD`
- `intitle:"<error message>" <library>`

Tactics:

- Search the full error first, then the shortest distinctive substring
- Add the runtime, framework, or OS when the error is too broad
- Exclude low-quality domains if they dominate results

## Reports, PDFs, and Research

Use for whitepapers, analyst reports, public filings, papers, and institutional summaries.

Patterns:

- `<topic> filetype:pdf`
- `"<exact report title>" filetype:pdf`
- `<topic> report filetype:pdf`
- `<topic> site:gov filetype:pdf`
- `<topic> site:edu filetype:pdf`
- `<paper title> site:publisher-domain.com`

Tactics:

- Combine `filetype:pdf` with official domains whenever possible
- Search the exact title in quotes if you already know the document name
- Compare publication dates and edition numbers

## Materials and Assets

Use for images, templates, media assets, decks, and downloadable resources.

Patterns:

- `<asset topic> filetype:pptx`
- `<asset topic> template filetype:pptx`
- `<asset topic> imagesize:1920x1080`
- `<asset topic> png`
- `<asset topic> site:official-domain.com media kit`

Tactics:

- Add format or size constraints early
- Prefer official media kits or vendor asset pages for brand materials
- If results are poor, switch to image search or a domain-specific asset source

## Tools and Software

Use for online tools, desktop software, plugins, and alternative-finding.

Patterns:

- `<task> online tool`
- `<task> mac app`
- `<task> chrome extension`
- `best <tool category> after:YYYY-MM-DD`
- `<tool name> alternatives`
- `related:<known-tool-domain.com>`

Tactics:

- Search by task first, product second
- Include platform constraints such as `mac`, `windows`, `ios`, `android`
- Look for official pricing, docs, changelogs, or marketplace listings

## Public-Information Lookups

Use for public facts about a person, company, institution, role, publication history, or public notice trail.

Patterns:

- `"<person or org name>"`
- `"<person or org name>" "<affiliation>"`
- `intext:"<person or org name>" "<affiliation or city>"`
- `"<person or org name>" site:gov.cn`
- `"<person or org name>" filetype:pdf`
- `"<person or org name>" OR "<alternate spelling>" "<organization>"`

Tactics:

- Use exact quotes for names
- Add organization, city, school, or role to disambiguate
- Compare multiple public records before treating two records as the same person
- Mark identity linkage as inference unless the sources make it explicit

## Chinese-Language Patterns

For all Chinese-language query patterns (technical, government, company, academic, platform-specific), see `references/chinese-search-ecosystem.md`.

## War Casualties and Losses

For wartime query patterns, source tiers, and output structure, see [high-conflict-topics.md](high-conflict-topics.md). That file consolidates all conflict-specific guidance in one place.

## Noise Reduction

Use these operators when results are polluted:

- `-keyword`
- `-site:domain.com`
- `intitle:`
- `allintitle:`
- `inurl:`
- quoted phrases

Example:

- `apple -fruit -recipe`
- `Go tutorial -site:csdn.net`
- `intitle:"release notes" <product>`

## Refinement Loop

If results are still weak, iterate in this order:

1. Add an exact phrase
2. Add a trusted domain
3. Add a date range
4. Add aliases or English terminology
5. Remove noisy terms or domains
6. Split one broad query into two narrow queries
