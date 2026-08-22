# Security Review — Python / FastAPI / Django Extension

Python idioms for the **same ten Gate D domains** — numbering and names are stack-independent
and defined once in `authorization-and-policy.md` §2. This file supplies the Python-specific
evidence for each; it does not replace or renumber them. All other gates (A-C, E-F), scenario
checklists, severity model, and output contract are unchanged.

## Contents
[Domain Checklist](#domain-checklist) · [SQL Injection](#sql-injection) ·
[Deserialization](#deserialization) · [Template Injection](#template-injection) ·
[Secrets & Crypto](#secrets--crypto)

---

## Domain Checklist

All ten are evaluated for every Python review. Where the row says *no Python-specific idiom*,
judge the domain against its canonical question in `authorization-and-policy.md` §2.

| # | Domain | Python check | Tool |
|---|--------|--------------|------|
| 1 | Randomness Safety | `secrets` module (`token_urlsafe`, `token_bytes`) for tokens/session IDs/resets. **`random` is never acceptable** for security values | `bandit` (B311) |
| 2 | Injection & Data-Access Safety | ORM (SQLAlchemy/Django) or raw SQL with bind params only — never f-strings/`%`/`.format()` into SQL; no `os.system`/`subprocess(..., shell=True)` with user input. Release: `with` blocks for sessions, files, cursors | `bandit`, `semgrep` |
| 3 | Sensitive Data Handling | No PII/secrets in `logging` output; no `logging.exception` dumping request bodies; Django `DEBUG=False` in prod (a traceback page leaks env and settings); serialiser field allowlists | `bandit` |
| 4 | Secret / Config Management | Secrets from env or a manager, never committed `settings.py`/`.env`; `SECRET_KEY` not a literal in source | `rg` pattern sweep |
| 5 | Transport Security | `ssl.create_default_context()` rather than a hand-built context; `PROTOCOL_TLS_CLIENT` not deprecated `PROTOCOL_TLSv1`; **`requests(..., verify=False)` is forbidden** in prod | `bandit` (B501) |
| 6 | Crypto Primitive Correctness | `hashlib.scrypt`/`bcrypt`/`argon2` for passwords, not `md5`/`sha1`; **`hmac.compare_digest`** for secret comparison, not `==`; `cryptography` over `pycrypto` | `bandit` |
| 7 | Concurrency & Shared-State Safety | The GIL does **not** make code safe: `await` between check and use is a TOCTOU window; module-level mutable state is shared across requests and across worker threads; blocking I/O inside `async def` stalls the loop (`run_in_executor`); multi-worker deployments share nothing in-process, so in-memory rate limits/locks silently do not work | manual review |
| 8 | Language-Specific Injection Sinks | `eval`/`exec`/`pickle.loads` on untrusted input; `yaml.load` without `SafeLoader`; **SSTI** — Jinja2 `autoescape=True`, never `Template(user_string)`; **XML** — use `defusedxml` for untrusted input, but on a current build **neither** XXE file read **nor** expansion DoS reaches the stdlib parsers, and lxml's exposure is version-gated per call site (read §Python XML before reporting either); `tarfile.extractall` path traversal (`filter='data'`) | `bandit`, `semgrep` |
| 9 | Static Scanner Posture | `bandit` run and triaged; every `# nosec` carries a rationale naming the rule ID | `bandit` |
| 10 | Dependency Vulnerability Posture | `pip-audit`, or `safety scan` (Safety 3.x documents `scan`; `check` is the legacy command); `requirements.txt`/`poetry.lock` pinned to exact versions with hashes where possible. Read the pin, not just the advisory list — several findings in this file are decided by a library version | `pip-audit`, `safety` |

> Auth (`Depends(get_current_user)`, `@login_required`/`@permission_required`, CSRF middleware)
> and input validation (Pydantic `conint`/`constr`/`Field(max_length=...)`, body size limits)
> belong to **Scenario Checklists 1 and 2**, not Gate D.

### Python XML: what actually applies (measured, and version-gated)

Do not report a blanket "Python XXE", and do not report a blanket "Python billion laughs"
either. Both the stdlib answer and the lxml answer are **gated on a library version**, and both
defaults have moved in the last three years. Establish the version before writing the finding.

Every row below is asserted against the running interpreter by
`scripts/tests/examples/python/xml_facts_test.py`, so a future version bump breaks the test
instead of silently rotting this table.

**stdlib (`xml.etree.ElementTree`, `minidom`, `sax` — all Expat-backed).** Measured on
CPython 3.14.3 / Expat 2.7.1. **The DoS answer and the XXE answer have different gates, and the
two DoS mechanisms have different gates from each other. Do not collapse them.**

| Attack | Applies to stdlib? | Gate | Evidence |
|---|---|---|---|
| **XXE — external entity → local file read** | **No** | `ElementTree`/`minidom`: any Expat, unless the app installs its own `ExternalEntityRefHandler`. `sax`: additionally opt-in via `parser.setFeature(xml.sax.handler.feature_external_ges, True)` — the one call-site switch in this table that a caller can flip without touching C internals | `<!ENTITY x SYSTEM "file:///...">` then `&x;` → `ParseError: undefined entity &x;` on the default of all three; setting `feature_external_ges` True on a `sax` parser resolves it and leaks the file |
| **XXE → SSRF via external DTD/entity URL** | **No** | same | same mechanism: the external reference is never fetched |
| **Entity amplification (billion laughs / quadratic blowup)** | **No** on Expat **≥ 2.4.0** | live below **2.4.0**; also below **2.6.0** built without `XML_DTD` (CVE-2023-52426); also below **2.6.2** for isolated external parsers (CVE-2024-28757) | a real 10⁹-char billion-laughs *and* a 2.5 GB quadratic blowup are both refused in <0.1 s: `ParseError: limit on input amplification factor (from DTD and entities) breached` |
| **Allocation amplification (large tokens / disproportional dynamic memory)** | **Yes** below Expat **2.7.2** | fixed in **2.7.2** — **CVE-2025-59375**, CVSS 3.1 base **7.5** | a ~250 KiB document could allocate ~800 MiB of heap, factor ~3,300. A *different mechanism* from the row above: the 2.4.0 entity cap does not bound it, so the classic payloads being refused proves nothing here |
| **Bounded internal entity substitution** | **Yes**, by design | — | `<!ENTITY a "HELLO">` → `HELLO`; a 3-level nest expanding to 1 000 chars is performed |

**The review rule is Expat ≥ 2.7.2 for the three mechanisms in the table above — XXE, entity
amplification, allocation amplification — and only those three**, matching upstream: *"Expat
versions lower than 2.7.2 may be vulnerable to the 'billion laughs', 'quadratic blowup' and 'large
tokens' vulnerabilities, or to disproportional use of dynamic memory"*
([Python XML security docs](https://docs.python.org/3/library/xml.html#xml-security), fetched
live while writing this: the page still names only 2.7.2, unchanged). The per-mechanism gates
above are for reasoning about a build that is pinned behind it — not for talking yourself into
calling an older build safe against *every* Expat CVE. Expat ships security fixes far more often
than "check one number" suggests — see Trap 4.

Four traps live in this table:

1. **Entity substitution is not a DoS.** Expat ≥ 2.4.0 tolerates an amplification factor up to
   **100.0**, enforced after **8 MiB of expanded output**
   ([libexpat Changes, 2.4.0 — CVE-2013-0340 / CWE-776](https://github.com/libexpat/libexpat/blob/master/expat/Changes)).
   A nested entity expanding to 1 000 characters sits *inside* that window: it shows substitution
   happens and says **nothing** about reachable DoS. Never grade "expansion occurred" as
   "amplification DoS confirmed".
2. **Refuting the classic payloads does not clear the version.** CVE-2025-59375 is an
   *allocator* amplification with its own threshold (64 MiB) and its own limit — added only in
   2.7.2. A build where billion laughs is refused can still be vulnerable to it. Two mechanisms,
   two gates; a probe that only fires the classic payloads cannot license a blanket "safe".
3. **A module-blanket claim can hide a per-module opt-in.** "Neither `ElementTree` nor `minidom`
   nor `sax` resolves external entities" is true of *defaults*, but `sax` alone exposes a
   documented feature flag, `xml.sax.handler.feature_external_ges`
   ([`xml.sax.handler` docs](https://docs.python.org/3/library/xml.sax.handler.html)), that a
   caller can set to `True` and get exactly the file-read this table calls a false positive.
   Measured directly: `parser.setFeature(xml.sax.handler.feature_external_ges, True)` before
   `parser.parse(...)` resolves the entity and leaks the file, on the same interpreter where the
   default parse refuses it. Before suppressing an XXE finding against `xml.sax` code, grep the
   call site for `setFeature` — the blanket suppression applies to the default, not to every
   invocation.
4. **"≥ 2.7.2" is not a lifetime clean bill — Expat keeps shipping CVEs above that line.**
   Verified against the upstream changelog (`github.com/libexpat/libexpat`, `expat/Changes`,
   fetched at tag `R_2_8_3`) while writing this: **2.8.1** fixed **CVE-2026-45186, CWE-407** —
   "quadratic runtime from attribute name collision checks... through moderately sized crafted XML
   input," CVSS 7.5. This is a *fourth*, distinct mechanism (attacker-controlled attribute names,
   not entities or allocator behaviour) with its own gate, **≥ 2.8.1** — refuting the classic
   entity payloads and reading Expat ≥ 2.7.2 clears neither of the two mechanisms above it. Going
   further: **2.8.0** fixed a hash-salt entropy weakness (CVE-2026-41080), and **2.8.2 alone fixed
   13 CVEs** (CVE-2026-50219, -56131, -56132, and -56403 through -56412 — ten consecutive IDs,
   not nine; recount from the changelog rather than trusting this sentence), several of them
   integer overflows that upstream classifies as memory corruption, not merely DoS. Do not
   memorize any single number from this file as "the" safe version: read the actual deployed Expat
   (`pyexpat.EXPAT_VERSION`), then check the *current*
   [upstream changelog](https://github.com/libexpat/libexpat/blob/master/expat/Changes) for that
   exact version — this file's own review rule above is already stale the moment a new Expat
   release ships, by design of software, not by an error here.

Consequences for the stdlib:

- **"XXE — arbitrary file read" against `ElementTree`/`minidom`/`sax` on their default
  configuration is a false positive** on any version — suppress under Rule 3, the parser
  structurally does not resolve external entities, and this is the one stdlib answer that is not
  version-gated. It stops being a false positive the moment `sax` code calls
  `setFeature(feature_external_ges, True)` (trap 3); check for that call before suppressing.
- **"Billion laughs" on Expat ≥ 2.4.0 is a false positive** — suppress under the same rule, and
  name the version you read.
- **On Expat < 2.7.2, a resource-exhaustion finding is live** via CVE-2025-59375 regardless of
  what the entity payloads do. Grade it on attacker reachability like any other DoS: `confirmed`
  when the endpoint is unauthenticated and the body unbounded, and pair it with a body-size cap
  in the fix. Do not report it as "XXE" or as "billion laughs" — it is neither.
- **On Expat < 2.8.1, a separate resource-exhaustion finding is live** via CVE-2026-45186
  (CWE-407, quadratic runtime from attribute-name collisions) whenever the parsed document's
  attribute names come from the attacker — an XML-import endpoint accepting arbitrary tags and
  attributes qualifies. Grade and remediate the same way as the CVE-2025-59375 row above, and do
  not conflate the two: a build already ≥ 2.7.2 (clearing CVE-2025-59375) can still be < 2.8.1
  and vulnerable to this one; they are different code paths with different fix versions.
- **On Expat < 2.8.2, do NOT treat all 13 fixed CVEs as reachable just because the parser sees
  untrusted XML — this skill's own reachability-first rule applies per CVE, not as a version-gate
  blanket.** They split into four reachability classes, verified against the upstream changelog,
  the linked CPython issue, and CPython's own C source — not assumed:
  - **Not reachable via Python at all — CVE-2026-56409/-56410/-56411.** The changelog labels
    these `xmlwf:` explicitly — they are in Expat's standalone command-line well-formedness
    checker, which `pyexpat`/`xml.etree.ElementTree` do not link against or call. Do not report
    them against Python code.
  - **Gated on the reviewed code's own handler re-entering its parser — CVE-2026-50219/-56131/-56412.**
    Verified via the changelog's own linked report,
    [cpython/cpython#146169](https://github.com/python/cpython/issues/146169): the crash requires
    application code that sets a handler (e.g. `CharacterDataHandler`) which itself calls back
    into `.Parse()`/`.ResumeParser()` on the *same* parser instance — expat's own docs call this
    out as forbidden re-entrancy. A plain `ET.fromstring(untrusted_bytes)` one-shot parse does not
    do this. Only report these against code that demonstrably re-enters its own parser from a
    handler; grep the handler bodies for a call back into the parser object before reporting.
  - **Gated on which parsing entry point the code calls — CVE-2026-56406 (`XML_ParseBuffer`
    integer overflow).** Verified by reading CPython's C sources directly, not inferred: neither
    `_elementtree.c` (the `ElementTree` accelerator — its `expat_parse()` calls
    `EXPAT(st, Parse)`, i.e. `XML_Parse`) nor `pyexpat.c`'s own `.Parse()`/`.feed()` method nor
    `xml/sax/expatreader.py` (which also calls `self._parser.Parse(...)`) ever calls
    `XML_ParseBuffer`. `ElementTree.fromstring`/`.parse`, `pyexpat.xmlparser.Parse`/`.feed`, and
    `xml.sax.parse` are therefore **not** exposed to this one — it only fires via the low-level,
    rarely-used `pyexpat.xmlparser.ParseFile()` method called directly by application code. Check
    for an explicit `.ParseFile(` call before reporting; its absence make this a false positive
    the same way the XXE row above is, not merely `likely`.
  - **Plausibly reachable via ordinary parsing of crafted content — CVE-2026-56403/-56404/-56405/
    -56407/-56408/-56132.** These are integer overflows in the internal
    attribute/namespace/CDATA engine (`storeAtts`, `addBinding`, `getAttributeId`, `textLen`
    handling, `copyString`, `doProlog`) that both `XML_Parse` and `XML_ParseBuffer` funnel into —
    unlike CVE-2026-56406 above, there is no stated entry-point gate in the changelog. Treat these
    as reachable by a sufficiently large or crafted document, the same caveat as the
    CVE-2025-59375/CVE-2026-45186 rows: a body-size cap bounds but does not zero the risk, since
    these were not independently reproduced for this document — read the version, and if in doubt
    grade `likely` rather than `confirmed`.
  There is no single crafted-payload probe that "clears" the whole group the way the
  billion-laughs test clears entity amplification — the version number against the current
  changelog, cross-referenced per CVE against the code's actual call pattern (which handler does
  what, which parsing method is called), is the only reliable check.
- Read the version, then read the
  [Python XML security docs](https://docs.python.org/3/library/xml.html#xml-security), which is
  the statement that moves. A distro build or a differently configured `pyexpat` can change the
  answer.

**lxml is version-gated too, and its safe default is newer than most guidance assumes.** Measured
on lxml 6.0.2 / libxml2 2.14.6:

| Surface | Default behaviour | Gate |
|---|---|---|
| `etree.fromstring` / `XMLParser()` / `HTMLParser()` | external entities **not** resolved (`resolve_entities='internal'`) → `XMLSyntaxError: Entity 'x' not defined` | safe default since **lxml 5.0.0** (2023-12-29) |
| network DTD / external entity URL, `no_network=True` (default) | **blocked before any I/O** → `failed to load …: Attempt to load network entity` | long-standing default |
| network DTD / external entity URL, `no_network=False` **and** `load_dtd=True` (or `dtd_validation=True`) | an outbound fetch is *attempted* — SSRF only if it actually reaches the network | every lxml version; see caveat below — this is NOT the same gate as the row above |
| `etree.iterparse()` and `ETCompatXMLParser` | external entities **resolved** → confirmed local file read | **XXE until lxml 6.1.0** (2026-04-17) — **CVE-2026-41066** |
| any parser given `resolve_entities=True` | external entities resolved → file read | every version |

So the live lxml findings are specific, not blanket:

- `iterparse()` or `ETCompatXMLParser` on untrusted XML with **lxml < 6.1.0** → real XXE
  (CVE-2026-41066). This is the one exploitable *default* in the Python XML surface, and it is
  the row most guidance omits. Grade `confirmed` once the pin is read off
  `requirements.txt` / `poetry.lock` / `uv.lock`; `likely` if the version cannot be determined.
- explicit `resolve_entities=True` on untrusted input → real, any version.
- `no_network=False` on its own **fetches nothing**: with `load_dtd` at its default (`False`),
  libxml2 never even attempts to load the external subset, network or not — measured directly,
  no exception, no delay. It only becomes a live path once `load_dtd=True` (or
  `dtd_validation=True`) is also set. Do not report a bare `no_network=False` as SSRF without
  checking whether the same parser also loads the DTD.
- Even with `load_dtd=True`, whether the attempt **reaches the network** depends on whether the
  deployed libxml2 was built with a network transport at all — that is a *libxml2 build*
  property, not an lxml version gate, and it is easy to get backwards. Measured on lxml 6.0.2 /
  libxml2 2.14.6: `no_network=True` fails immediately with the explicit `Attempt to load network
  entity` message (the row above); `no_network=False` with a `http://` or `ftp://` DOCTYPE URL
  instead fails with a generic `failed to load "...": No such file or directory` — the *identical*
  message a nonexistent `file://` path produces — and a real local HTTP listener recorded zero
  connections. That is the signature of a build with no registered network transport for those
  schemes, not of a request that was sent and refused. Grade lxml SSRF from `no_network=False`
  as `likely`, not `confirmed`, and say which you checked (`python3 -c "import lxml.etree as e;
  print(e.LIBXML_VERSION)"` plus a probe against a listener you control) — the flag alone does not
  settle it either way.
- plain `etree.fromstring` / `XMLParser()` on **lxml ≥ 5.0.0** → **false positive**; suppress.
- **lxml < 5.0.0** → external entities resolved by every parser; XXE applies broadly.

Read both versions, do not infer them:

```bash
# pyexpat.EXPAT_VERSION is the check the Python docs name; version_info is the comparable tuple.
python3 -c "import pyexpat; from xml.parsers import expat; \
print(pyexpat.EXPAT_VERSION, expat.version_info, 'patched' if expat.version_info >= (2,7,2) else 'BELOW 2.7.2 — CVE-2025-59375 live')"
python3 -c "import lxml.etree as e; print('lxml', e.LXML_VERSION, 'libxml2', e.LIBXML_VERSION)"
```

The version that matters is the one in the **deployment image**, not the reviewer's laptop. If
you cannot read it, say so and grade at `likely`, not `confirmed`.

`defusedxml` remains the right recommendation for untrusted XML regardless of version: it blocks
entity expansion outright and covers every shape above uniformly, which is what makes it a valid
*hardening* suggestion even where the current finding is a false positive.

Unlike Go — whose `encoding/xml` resolves **no** DTD entities at all, internal or external —
Python does substitute internal entities, so the Go exemption does not carry across wholesale.
But bounded substitution is not a DoS, and the amplification cap is what closes that gap.

## Secure Pattern Examples

### SQL Injection

```python
# BAD: string interpolation in SQL
@app.get("/users")
async def get_users(name: str):
    query = f"SELECT * FROM users WHERE name = '{name}'"  # injection
    return await db.fetch_all(query)

# GOOD: parameterized query
@app.get("/users")
async def get_users(name: str):
    query = "SELECT * FROM users WHERE name = :name"
    return await db.fetch_all(query, values={"name": name})
```

### Insecure Deserialization

```python
# BAD: pickle on untrusted input
import pickle
def load_session(data: bytes):
    return pickle.loads(data)  # arbitrary code execution

# GOOD: use JSON or signed serialization
import json
from itsdangerous import URLSafeTimedSerializer
serializer = URLSafeTimedSerializer(SECRET_KEY)

def load_session(token: str):
    return serializer.loads(token, max_age=3600)
```

### SSTI (Server-Side Template Injection)

```python
# BAD: user string rendered as template
from jinja2 import Template
def render(user_input: str):
    return Template(user_input).render()  # SSTI: {{ config }}

# GOOD: sandboxed environment with autoescape
from jinja2 import Environment, select_autoescape
env = Environment(autoescape=select_autoescape(["html"]))
def render(template_name: str, **kwargs):
    return env.get_template(template_name).render(**kwargs)
```

### TLS Configuration

```python
# BAD: disabled certificate verification
import ssl
ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

# GOOD: default secure context
import ssl
ctx = ssl.create_default_context()
# optionally set minimum version
ctx.minimum_version = ssl.TLSVersion.TLSv1_2
```

### Password Hashing

```python
# BAD: raw hash without salt/stretch
import hashlib
password_hash = hashlib.sha256(password.encode()).hexdigest()

# GOOD: proper password hashing
from passlib.hash import argon2
password_hash = argon2.hash(password)
if argon2.verify(provided_password, stored_hash):
    # authenticated
```

## Automation Commands

```bash
# Dependency audit
pip-audit

# Static analysis
bandit -r . -ll

# Secret sweep
rg -n "(password\s*=\s*[\"'][^\"']+|secret\s*=\s*[\"'][^\"']+|AKIA[0-9A-Z]{16})" .

# Optional: semgrep for Python patterns
semgrep --config=p/python .
```

## Common False Positives

- `pickle.loads` used only for internal cache with trusted data → suppressed with note on trust boundary.
- `yaml.load` with `Loader=SafeLoader` already specified → suppressed.
- `eval()` in migration scripts not reachable at runtime → suppressed with note.
- `hashlib.sha256` used for content fingerprinting (not password storage) → suppressed.
- `ssl.CERT_NONE` in test fixture connecting to self-signed test server → suppressed with note.
