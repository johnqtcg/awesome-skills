# Security Review — Java / Spring Extension

Java/Spring idioms for the **same ten Gate D domains** — numbering and names are
stack-independent and defined once in `authorization-and-policy.md` §2. This file supplies the
Java-specific evidence for each; it does not replace or renumber them. All other gates (A-C,
E-F), scenario checklists, severity model, and output contract are unchanged.

## Contents
[Domain Checklist](#domain-checklist) · [SQL Injection](#sql-injection) ·
[SSRF in Spring](#ssrf-in-spring) · [TLS Configuration](#tls-configuration) ·
[Password Hashing](#password-hashing)

---

## Domain Checklist

All ten are evaluated for every Java review. Where the row says *no Java-specific idiom*, judge
the domain against its canonical question in `authorization-and-policy.md` §2 — do not skip it.

| # | Domain | Java/Spring check | Tool |
|---|--------|-------------------|------|
| 1 | Randomness Safety | `SecureRandom` for tokens/session IDs/resets. **`java.util.Random` / `Math.random()` never** for security values; do not seed `SecureRandom` with a constant | `spotbugs`, `find-sec-bugs` |
| 2 | Injection & Data-Access Safety | No concatenated SQL/JPQL → `@Query` with `?1`/named params or `CriteriaBuilder`; no SpEL with user input in `@Value`/`@PreAuthorize`. Release: try-with-resources on `Connection`/`Statement`/`ResultSet`/`InputStream` | `spotbugs`, `find-sec-bugs` |
| 3 | Sensitive Data Handling | No PII/secrets in `log.info()`; structured logging with field masking; **no `e.printStackTrace()`** in production; DTOs rather than entities on responses (avoid lazy-loading leaks) | `spotbugs` |
| 4 | Secret / Config Management | `application.yml` secrets via `${VAULT_*}` or Spring Cloud Vault; no plaintext passwords in committed profiles | `rg` pattern sweep |
| 5 | Transport Security | `server.ssl.protocol` = TLSv1.2 minimum; no `SSLContext.getInstance("SSL")`/`"TLSv1"`; no all-trusting `TrustManager` or `HostnameVerifier` returning true | manual review |
| 6 | Crypto Primitive Correctness | `BCryptPasswordEncoder`/`Argon2PasswordEncoder`, not MD5/SHA1; **`MessageDigest.isEqual()`** for secret comparison, not `String.equals`; no ECB mode; explicit IV handling | `find-sec-bugs` |
| 7 | Concurrency & Shared-State Safety | Spring singletons are shared across all requests — **no mutable instance fields in `@Service`/`@Controller`**; `@Transactional` boundaries must cover check-then-act on balances/permissions; `SimpleDateFormat` and other non-thread-safe fields as singletons | manual review |
| 8 | Language-Specific Injection Sinks | **Deserialization**: no `ObjectInputStream.readObject` on untrusted input; Jackson `DefaultTyping` disabled or allowlisted; XXE — `DocumentBuilderFactory`/`SAXParserFactory` must disable DTDs (`FEATURE_SECURE_PROCESSING`, `disallow-doctype-decl`); SSRF via `RestTemplate`/`WebClient` (see §SSRF) | `spotbugs`, `semgrep` |
| 9 | Static Scanner Posture | `spotbugs` + `find-sec-bugs` run and triaged; every `@SuppressWarnings`/`@SuppressFBWarnings` carries a rationale | `spotbugs`, `mvn spotbugs:check` |
| 10 | Dependency Vulnerability Posture | `mvn dependency:tree` for transitives; `OWASP dependency-check-maven` or `snyk`. Prefer reachability evidence over raw CVE counts | `dependency-check`, `snyk` |

> Auth (`@PreAuthorize`/`@Secured`, `SecurityFilterChain` order, CSRF for session auth) and
> input validation (`@Valid`, `@Size`/`@Pattern`, `spring.servlet.multipart.max-*`) belong to
> **Scenario Checklists 1 and 2**, not Gate D.

Unlike Go, **XXE and entity-expansion attacks do apply to Java** — its XML parsers honour DTDs
by default. Do not carry the Go XML exemption across (`go-secure-coding.md` §Go XML).

## Secure Pattern Examples

### Unsafe Deserialization

```java
// BAD: ObjectInputStream on untrusted data
ObjectInputStream ois = new ObjectInputStream(request.getInputStream());
Object obj = ois.readObject(); // RCE via gadget chains

// GOOD: use JSON with type validation
ObjectMapper mapper = new ObjectMapper();
// do NOT enable default typing:
// mapper.enableDefaultTyping(); // DANGEROUS
MyDTO dto = mapper.readValue(request.getInputStream(), MyDTO.class);
```

### SQL Injection

```java
// BAD: string concatenation
String query = "SELECT * FROM users WHERE name = '" + name + "'";
Statement stmt = conn.createStatement();
ResultSet rs = stmt.executeQuery(query);

// GOOD: parameterized query
PreparedStatement ps = conn.prepareStatement(
    "SELECT * FROM users WHERE name = ?");
ps.setString(1, name);
ResultSet rs = ps.executeQuery();
```

### SSRF in Spring

```java
// BAD: user URL fetched directly
@GetMapping("/fetch")
public String fetch(@RequestParam String url) {
    return restTemplate.getForObject(url, String.class); // SSRF
}

// ALSO BAD: allowlist only. RestTemplate follows redirects by default, so an
// allowlisted host can 302 to http://169.254.169.254/ and the allowlist is never
// re-checked. The hostname is also validated before resolution, leaving a rebinding window.
@GetMapping("/fetch")
public String fetch(@RequestParam String url) {
    URI uri = URI.create(url);
    if (!ALLOWED_HOSTS.contains(uri.getHost())) {
        throw new ResponseStatusException(HttpStatus.FORBIDDEN, "blocked host");
    }
    return restTemplate.getForObject(uri, String.class); // redirects still followed
}

// MINIMUM DEFENSE (PARTIAL — residual DNS-rebinding risk).
// This is the floor, not "safe": getAllByName and the eventual connect are two separate
// resolutions, and JVM DNS caching only narrows the window. Java has no per-connect hook
// equivalent to Go's Dialer.Control. See the note after this block.
private static final Set<String> ALLOWED_HOSTS = Set.of("api.example.com");

// Redirects OFF at the factory level — this is the control the allowlist cannot provide.
@Bean
RestTemplate ssrfSafeRestTemplate() {
    HttpClient client = HttpClient.newBuilder()
            .followRedirects(HttpClient.Redirect.NEVER)
            .connectTimeout(Duration.ofSeconds(5))
            .build();
    return new RestTemplate(new JdkClientHttpRequestFactory(client));
}

private static void assertPublicAddress(String host) throws UnknownHostException {
    InetAddress[] addrs = InetAddress.getAllByName(host); // check EVERY A/AAAA record
    for (InetAddress addr : addrs) {
        if (addr.isLoopbackAddress() || addr.isSiteLocalAddress() || addr.isAnyLocalAddress()
                || addr.isLinkLocalAddress() || addr.isMulticastAddress()) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "blocked address");
        }
    }
}

@GetMapping("/fetch")
public String fetch(@RequestParam String url) throws UnknownHostException {
    URI uri = URI.create(url);
    if (!ALLOWED_HOSTS.contains(uri.getHost()) || !"https".equals(uri.getScheme())) {
        throw new ResponseStatusException(HttpStatus.FORBIDDEN, "blocked host");
    }
    assertPublicAddress(uri.getHost());
    return ssrfSafeRestTemplate.getForObject(uri, String.class);
}
```

#### What "closed" actually requires (Java)

The block above is the **minimum bar** — a review must not describe it as SSRF mitigated:

| Level | Approach | Residual risk |
|---|---|---|
| **Minimum (the code above)** | Allowlist + scheme pin + `Redirect.NEVER` + check every `getAllByName` record | **DNS rebinding still open**; JVM DNS caching (`networkaddress.cache.ttl`) only narrows the window |
| **Strong** | Resolve once, then connect to the *validated IP* with the hostname supplied only for `Host`/SNI (a custom `SocketFactory`, or an `HttpClient` on a connection pool that pins the resolved address). Re-apply on every retry | Small; depends on consistent pinning |
| **Strongest** | Route outbound traffic through a **vetted egress proxy**, or a network policy / security group that cannot reach link-local or RFC1918 ranges | Enforcement lives outside the exploitable process |

Java has no direct equivalent of Go's `Dialer.Control`, so for high-risk proxies prefer the
egress-proxy or network-policy option over in-process checks. Disabling redirects is
non-negotiable either way. When only the minimum is present, report it as a finding with
residual risk recorded.

### TLS Configuration

```java
// BAD: deprecated TLS version
SSLContext ctx = SSLContext.getInstance("TLSv1"); // vulnerable

// GOOD: modern TLS
SSLContext ctx = SSLContext.getInstance("TLSv1.3");

// Spring Boot application.yml
// server:
//   ssl:
//     protocol: TLSv1.3
//     enabled-protocols: TLSv1.3,TLSv1.2
```

### Password Hashing

```java
// BAD: MD5 for password storage
MessageDigest md = MessageDigest.getInstance("MD5");
byte[] hash = md.digest(password.getBytes());

// GOOD: BCrypt
BCryptPasswordEncoder encoder = new BCryptPasswordEncoder(12);
String hash = encoder.encode(password);
if (encoder.matches(providedPassword, storedHash)) {
    // authenticated
}
```

## Automation Commands

```bash
# Dependency vulnerability check
mvn org.owasp:dependency-check-maven:check

# Secret sweep
rg -n "(password\s*[:=]\s*[\"'][^\"']+|secret\s*[:=]\s*[\"'][^\"']+|AKIA[0-9A-Z]{16})" .

# Optional: SpotBugs with find-sec-bugs plugin
mvn spotbugs:check -Dspotbugs.plugins=com.h3xstream.findsecbugs:findsecbugs-plugin
```

## Common False Positives

- `ObjectInputStream` used only for internal RPC with signature verification → suppressed with note.
- `@PreAuthorize` missing on public (unauthenticated) endpoints → N/A.
- `e.printStackTrace()` in test code only → suppressed.
- `MessageDigest("SHA-256")` used for file checksums, not password storage → suppressed.
- `SSLContext` with `TLSv1.2` in legacy client connector with documented upgrade plan → note in risk register.
