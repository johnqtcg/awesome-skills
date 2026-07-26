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
| 8 | Language-Specific Injection Sinks | `eval`/`exec`/`pickle.loads` on untrusted input; `yaml.load` without `SafeLoader`; **SSTI** — Jinja2 `autoescape=True`, never `Template(user_string)`; **XML** — use `defusedxml` for untrusted input; the live stdlib risk is *entity-expansion DoS*, **not** XXE file read (see §Python XML before reporting either); `tarfile.extractall` path traversal (`filter='data'`) | `bandit`, `semgrep` |
| 9 | Static Scanner Posture | `bandit` run and triaged; every `# nosec` carries a rationale naming the rule ID | `bandit` |
| 10 | Dependency Vulnerability Posture | `pip-audit` or `safety check`; `requirements.txt`/`poetry.lock` pinned to exact versions with hashes where possible | `pip-audit`, `safety` |

> Auth (`Depends(get_current_user)`, `@login_required`/`@permission_required`, CSRF middleware)
> and input validation (Pydantic `conint`/`constr`/`Field(max_length=...)`, body size limits)
> belong to **Scenario Checklists 1 and 2**, not Gate D.

### Python XML: what actually applies (measured, not assumed)

Do not report a blanket "Python XXE". Verified on CPython 3.14 / Expat 2.7.1 with
`xml.etree.ElementTree`:

| Attack | Applies to stdlib? | Evidence |
|---|---|---|
| **XXE — external entity → local file read** | **No** (default) | `<!ENTITY x SYSTEM "file:///...">` then `&x;` → `ParseError: undefined entity &x;`. Expat does not resolve external entities by default, so there is no file read |
| **XXE → SSRF via external DTD/entity URL** | **No** (default) | same mechanism: the external reference is never fetched |
| **Internal entity expansion (billion laughs / quadratic blowup)** | **Yes** | a 3-level nested entity expanded to 1000 chars; expansion is performed, so amplification DoS is real |
| **Plain internal entity substitution** | Yes | `<!ENTITY a "HELLO">` → `HELLO` |

Consequences for review:

- **Reporting "XXE — arbitrary file read" against stdlib `ElementTree`/`minidom`/`sax` is a
  false positive** on a default build. Record it as suppressed (Rule 3 — the parser
  structurally does not resolve external entities) rather than as a finding.
- **Do** report unbounded entity expansion on untrusted XML: that one is live. It is a DoS
  finding, graded on attacker reachability like any other.
- The result is **Expat-version and build dependent**, and the risky-version boundary moves as
  CPython bumps its bundled Expat. Do **not** quote a boundary from memory — read the current
  one from the [Python XML security docs](https://docs.python.org/3/library/xml.html#xml-security),
  then record the version you actually checked:
  ```bash
  python3 -c "from xml.parsers import expat; print(expat.version_info)"
  ```
  If you cannot determine the version, say so and grade at `likely`, not `confirmed`. A distro
  build or a differently configured `pyexpat` can also change behaviour.
- **`lxml` is a different story** — it resolves external entities and fetches network DTDs
  unless configured otherwise (`resolve_entities=False`, `no_network=True`, `load_dtd=False`).
  XXE **does** apply there. Check which library is actually imported before deciding.
- `defusedxml` remains the right recommendation for untrusted XML regardless: it blocks entity
  expansion outright and covers the shapes above uniformly.

Unlike Go — whose `encoding/xml` resolves **no** DTD entities at all, internal or external —
Python does expand internal entities, so the Go exemption does not carry across wholesale.

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
