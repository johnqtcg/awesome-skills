# Security Review — Node.js / TypeScript Extension

Node.js/TypeScript idioms for the **same ten Gate D domains** — the numbering and names are
stack-independent and defined once in `authorization-and-policy.md` §2. This file supplies the
Node-specific evidence for each; it does not replace or renumber them. All other gates (A-C,
E-F), scenario checklists, severity model, and output contract are unchanged.

## Contents
[Domain Checklist](#domain-checklist) · [Command Injection](#command-injection) ·
[Prototype Pollution](#prototype-pollution) · [SSRF](#ssrf) · [TLS & Crypto](#tls--crypto) ·
[Input Validation](#input-validation)

---

## Domain Checklist

All ten are evaluated for every Node review. Where the row says *no Node-specific idiom*, judge
the domain against its canonical question in `authorization-and-policy.md` §2 — do not skip it.

| # | Domain | Node.js check | Tool |
|---|--------|---------------|------|
| 1 | Randomness Safety | `crypto.randomBytes`/`randomUUID` for tokens, session IDs, resets. **`Math.random()` is never acceptable** for security values | `eslint-plugin-security` |
| 2 | Injection & Data-Access Safety | `child_process.exec` with string interpolation → `execFile` with args array; template-literal SQL → parameterized (`pg` `$1`, Prisma, Knex). Release: always `client.release()`/`finally` on pool clients | `eslint-plugin-security`, `semgrep` |
| 3 | Sensitive Data Handling | No PII/tokens in `console.log`/pino/winston output; no full objects logged with `JSON.stringify(req)`; response shaping so internal fields are not serialised | manual review |
| 4 | Secret / Config Management | No committed `.env`; `dotenv` dev-only; production uses a secret manager | `rg` pattern sweep |
| 5 | Transport Security | `https.Agent` with `minVersion: 'TLSv1.2'`; **`rejectUnauthorized: false` is forbidden** outside tests; `NODE_TLS_REJECT_UNAUTHORIZED=0` never set in prod | manual review |
| 6 | Crypto Primitive Correctness | `bcrypt`/`argon2` for passwords, not `createHash('md5'\|'sha1')`; constant-time compare that **cannot throw** on length mismatch (see §TLS & Crypto) | manual review |
| 7 | Concurrency & Shared-State Safety | Single-threaded event loop does **not** remove the risk: `await` between a check and its use is a TOCTOU window; module-level mutable caches are shared across requests; `worker_threads`/cluster share nothing but may race on external state | manual review |
| 8 | Language-Specific Injection Sinks | Prototype pollution (`lodash.merge`/`Object.assign` on untrusted input → `Map` or null-prototype); ReDoS (unbounded regex on user input → `re2` or cap length first); SSRF via `fetch`/`axios` (see §SSRF); `vm`/`eval` on user input | `eslint-plugin-security` |
| 9 | Static Scanner Posture | `eslint-plugin-security` and/or `semgrep` run and triaged; every `// eslint-disable-next-line security/*` carries a rationale | `eslint`, `semgrep` |
| 10 | Dependency Vulnerability Posture | `npm audit --production`; `package-lock.json` committed and current. Prefer reachability evidence over raw advisory counts | `npm audit`, `snyk` |

> Auth middleware order (`helmet` → `cors` → `rateLimit` → `auth` → routes, and never calling
> `next()` after `res.send()`) and input validation (`zod`/`joi`/`express-validator`,
> `express.json({ limit: '1mb' })`) belong to **Scenario Checklists 1 and 2**, not Gate D.

## Secure Pattern Examples

### Command Injection

```javascript
// BAD: exec with string interpolation
const { exec } = require('child_process');
app.get('/ping', (req, res) => {
  exec(`ping -c 4 ${req.query.host}`, (err, stdout) => {
    // host=; rm -rf / → command injection
    res.send(stdout);
  });
});

// GOOD: execFile with separate args
const { execFile } = require('child_process');
app.get('/ping', (req, res) => {
  const host = req.query.host;
  if (!/^[a-zA-Z0-9.-]+$/.test(host)) {
    return res.status(400).send('invalid host');
  }
  execFile('ping', ['-c', '4', host], (err, stdout) => {
    res.send(stdout);
  });
});
```

### Prototype Pollution

```javascript
// BAD: deep merge of untrusted input
const lodash = require('lodash');
app.post('/settings', (req, res) => {
  lodash.merge(config, req.body);
  // body: {"__proto__": {"isAdmin": true}} → pollutes all objects
});

// GOOD: use allowlisted fields
app.post('/settings', (req, res) => {
  const { theme, language } = req.body;
  config.theme = theme;
  config.language = language;
});
```

### SSRF

```javascript
// BAD: user URL fetched without validation
app.get('/proxy', async (req, res) => {
  const resp = await fetch(req.query.url); // SSRF
  res.send(await resp.text());
});

// ALSO BAD: allowlist only. fetch() follows redirects by default, so an allowlisted
// host can 302 to http://169.254.169.254/ and the allowlist is never re-consulted.
// new URL() also throws on malformed input — unhandled, that is a 500.
app.get('/proxy', async (req, res) => {
  const parsed = new URL(req.query.url);          // throws on bad input
  if (!ALLOWED_HOSTS.has(parsed.hostname)) {
    return res.status(403).send('blocked');
  }
  const resp = await fetch(parsed.toString());    // redirects still followed
  res.send(await resp.text());
});

// MINIMUM DEFENSE (PARTIAL — residual DNS-rebinding risk).
// This is the floor, not "safe": dns.lookup and the socket's own resolution are two separate
// lookups, so an attacker controlling DNS can still change the answer in between. Node has no
// per-connect hook equivalent to Go's Dialer.Control. See the note after this block for what a
// genuinely closed defense requires.
const dns = require('node:dns').promises;
const net = require('node:net');
const ALLOWED_HOSTS = new Set(['api.example.com', 'cdn.example.com']);

function isPublicAddress(ip) {
  const v = net.isIP(ip) === 6 && ip.startsWith('::ffff:') ? ip.slice(7) : ip; // unmap
  if (net.isIP(v) === 4) {
    const [a, b] = v.split('.').map(Number);
    if (a === 10 || a === 127 || a === 0 ||
        (a === 172 && b >= 16 && b <= 31) ||
        (a === 192 && b === 168) ||
        (a === 169 && b === 254) ||          // link-local incl. cloud IMDS
        (a === 100 && b >= 64 && b <= 127)) {  // CGNAT
      return false;
    }
    return true;
  }
  const lower = v.toLowerCase();
  return !(lower === '::1' || lower.startsWith('fc') || lower.startsWith('fd') ||
           lower.startsWith('fe80'));
}

app.get('/proxy', async (req, res) => {
  let parsed;
  try {
    parsed = new URL(req.query.url);            // never let this throw uncaught
  } catch {
    return res.status(400).send('bad url');
  }
  if (parsed.protocol !== 'https:' || !ALLOWED_HOSTS.has(parsed.hostname)) {
    return res.status(403).send('blocked');
  }
  // Check EVERY A/AAAA record, not just the first.
  const addrs = await dns.lookup(parsed.hostname, { all: true });
  if (!addrs.every((a) => isPublicAddress(a.address))) {
    return res.status(403).send('blocked address');
  }
  const resp = await fetch(parsed.toString(), {
    redirect: 'manual',                          // the control an allowlist cannot give
    signal: AbortSignal.timeout(10_000),
  });
  if (resp.status >= 300 && resp.status < 400) {
    return res.status(502).send('redirect refused');
  }
  res.send(await resp.text());
});
```

#### What "closed" actually requires (Node)

The block above is the **minimum bar** — a review must not describe it as SSRF mitigated:

| Level | Approach | Residual risk |
|---|---|---|
| **Minimum (the code above)** | Allowlist + scheme pin + `redirect: 'manual'` + check every `dns.lookup` record | **DNS rebinding still open** — two separate resolutions |
| **Strong** | Resolve once, then connect to the *validated IP*, carrying the hostname only in `Host`/SNI. In Node: a custom `http.Agent` with a `lookup` option returning the already-validated address, so the socket cannot re-resolve. Re-apply on every retry and redirect hop | Small; depends on pinning being applied consistently |
| **Strongest** | Take the decision out of the process: route outbound traffic through a **vetted egress proxy**, or a network policy / security group that cannot reach link-local or RFC1918 ranges | Enforcement lives outside the exploitable process |

For services handling untrusted URLs at scale, prefer the egress-proxy or network-policy option.
When only the minimum is present, report it as a finding with the residual risk recorded — not
as "SSRF mitigated".

### TLS & Crypto

```javascript
// BAD: disabled certificate verification
const https = require('https');
const agent = new https.Agent({ rejectUnauthorized: false }); // MitM

// GOOD: default verification with minimum TLS version
const agent = new https.Agent({
  minVersion: 'TLSv1.2',
  // rejectUnauthorized defaults to true
});

// BAD: timing-unsafe comparison
if (providedToken === storedToken) { /* ... */ }

// ALSO BAD: timingSafeEqual THROWS RangeError when byte lengths differ
// ("Input buffers must have the same byte length"). providedToken is attacker-controlled,
// so any wrong-length token becomes an unhandled exception -> 500 / crash, not a rejection.
if (crypto.timingSafeEqual(Buffer.from(providedToken), Buffer.from(storedToken))) { /* ... */ }

// GOOD: compare fixed-length digests, so length is always equal and never leaks
const crypto = require('crypto');

function safeTokenEqual(provided, stored) {
  if (typeof provided !== 'string') return false;
  // Hashing normalises length: unequal inputs can never throw, and the length of the
  // supplied token is not revealed by an early return.
  const a = crypto.createHash('sha256').update(provided, 'utf8').digest();
  const b = crypto.createHash('sha256').update(stored, 'utf8').digest();
  return crypto.timingSafeEqual(a, b);
}

if (safeTokenEqual(providedToken, storedToken)) {
  // safe
}

// Acceptable alternative when both sides are guaranteed fixed-width (e.g. hex digests):
// check length FIRST and return false — never let timingSafeEqual throw.
function safeFixedWidthEqual(provided, stored) {
  const a = Buffer.from(provided, 'utf8');
  const b = Buffer.from(stored, 'utf8');
  if (a.length !== b.length) return false; // leaks only length, not content
  return crypto.timingSafeEqual(a, b);
}

// BAD: MD5 for password
const hash = crypto.createHash('md5').update(password).digest('hex');

// GOOD: bcrypt
const bcrypt = require('bcrypt');
const hash = await bcrypt.hash(password, 12);
const valid = await bcrypt.compare(providedPassword, storedHash);
```

### Input Validation

```javascript
// BAD: no body size limit
app.use(express.json()); // default limit is 100kb but should be explicit

// GOOD: explicit limits
app.use(express.json({ limit: '1mb' }));
app.use(express.urlencoded({ extended: false, limit: '1mb' }));
```

## Automation Commands

```bash
# Dependency audit
npm audit --production

# Secret sweep
rg -n "(AKIA[0-9A-Z]{16}|-----BEGIN .* KEY-----|ghp_[A-Za-z0-9]{36}|xox[baprs]-|password\s*=|secret\s*=|token\s*=)" .

# Optional: semgrep for Node.js patterns
semgrep --config=p/nodejs .
```

## Common False Positives

- `child_process.execFile` with hardcoded binary and no user input in args → suppressed.
- `eval()` in build scripts (webpack config, babel transform) not reachable at runtime → suppressed with note.
- `Object.assign` on server-controlled objects only → suppressed.
- `rejectUnauthorized: false` in test suite connecting to self-signed test server → suppressed with note.
- `crypto.createHash('sha256')` used for content fingerprinting, not password storage → suppressed.
