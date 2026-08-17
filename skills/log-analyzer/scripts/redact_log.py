#!/usr/bin/env python3
"""Deterministic PII / secret redaction for log lines.

The log-analyzer skill treats redaction as a hard gate (SKILL.md Gate 2). A gate
enforced only by prose is not enforced, so this script is the executable form of
that gate: pipe every log source through it once, before quoting anything.

Three subcommands, split by CAPABILITY rather than by task, because the skill's
permission grant is a prefix glob and cannot exclude a flag:

    redact_log.py scan   app.log            # redact to stdout      -- READ-ONLY
    redact_log.py verify app.redacted.log   # exit 1 on residue     -- READ-ONLY
    redact_log.py write  app.log -o out.log # redact to a file      -- WRITES

`scan` and `verify` have no write-capable option at all -- the parser rejects
`--output` on them, so their read-only-ness is enforced by argparse rather than by
convention. Only those two are auto-approved in SKILL.md; `write` creates a file
and therefore prompts. Do not "fix" that by widening the grant to the script path:
that would auto-approve arbitrary file creation, which is exactly what the earlier
single-entry-point version did while claiming to be stdout-only.

Correlation identifiers (trace_id, request_id, span_id, ...) are never redacted
-- they carry no secret and the whole investigation depends on them.

A per-category count is written to stderr so the analyst can fill in
`Execution Status -> PII redaction applied: yes (categories: ...)`.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from typing import Callable, Iterable

# Keys whose *value* is sensitive regardless of what the value looks like.
SENSITIVE_KEYS = frozenset({
    "access_token", "api_key", "apikey", "auth", "authorization", "client_secret",
    "cookie", "credit_card", "id_token", "passwd", "password", "private_key",
    "pwd", "refresh_token", "secret", "session", "session_id", "sessionid",
    "set-cookie", "ssn", "token",
})

# Keys that must survive untouched: the analysis is built on them.
PRESERVED_KEYS = frozenset({
    "correlation_id", "parent_id", "request_id", "span_id", "trace_id",
    "traceparent", "tracestate", "x_request_id",
})

# Redacted only under --redact-user-id, i.e. for a report leaving the company.
# Internally these are kept: user_id walks traces, tenant_id confirms blast
# radius. Externally they identify a customer, which is what makes them PII.
EXTERNAL_ONLY_KEYS = frozenset({
    "account_id", "customer_id", "email", "org_id", "organization_id",
    "tenant", "tenant_id", "user", "user_email", "user_id", "username",
})

# Keys whose values are numeric and must never be mistaken for a card number.
# Epoch-millisecond timestamps are 13 digits and ~10% of them pass Luhn by
# chance, so the Luhn check alone is not enough -- the field name decides.
_NUMERIC_KEY = re.compile(
    r"(?i)(time|timestamp|ts|epoch|date|millis|nanos|seq|offset|size|bytes|"
    r"count|len|length|duration|port|pid|code|status|_at|_ms|_us|_ns|_id|id)$"
)

# Optional `key=` / `"key":` prefix captured so _pan_sub can inspect the field
# name. Python's re has no variable-width lookbehind, hence the capture group.
_KEY_PREFIX = r"""(["']?[A-Za-z_][A-Za-z0-9_.-]*["']?\s*[:=]\s*)?"""

REDACTED = "***REDACTED***"

# A key=value value, in every form real logs use. An unquoted run stops at the
# first delimiter; a quoted run may contain spaces and delimiters.
#
# The earlier `[^\s,;&"'}\]]+` EXCLUDED the quote characters, so it stopped dead at
# the opening `"`. Every quoted secret therefore survived: `password="hunter 2"`,
# `user_id="u-17"`, `tenant_id="acme corp"` all passed `verify` as clean. Quoting a
# value is the normal way to write one that contains a space.
_VALUE = r"""(?!["']?\*\*\*)(?:"[^"\n]*"|'[^'\n]*'|[^\s,;&"'}\]]+)"""

# `key=`, `key:`, `"key":` -- the optional quotes around the key name are what make
# the rules fire on a JSON line that fell back to text handling.
_KEY_SEP = r"""["']?\s*[:=]\s*"""
_KEY_OPEN = r"""["']?"""


def _luhn_ok(digits: str) -> bool:
    """Standard Luhn checksum. Cuts the card-number false-positive rate ~10x."""
    total, alt = 0, False
    for ch in reversed(digits):
        d = ord(ch) - 48
        if alt:
            d *= 2
            if d > 9:
                d -= 9
        total += d
        alt = not alt
    return total % 10 == 0


def _iban_ok(s: str) -> bool:
    """ISO 13616 MOD-97 check: move the first 4 chars to the end, map letters to
    two-digit numbers (A=10 .. Z=35), and require the integer mod 97 == 1.

    Without the checksum, `\\b[A-Z]{2}\\d{2}[A-Z0-9]{10,30}\\b` also matches
    build IDs, container tags and AWS resource names.
    """
    s = s.replace(" ", "").upper()
    if not (15 <= len(s) <= 34):
        return False
    rot = s[4:] + s[:4]
    digits = "".join(str(ord(c) - 55) if c.isalpha() else c for c in rot)
    if not digits.isdigit():
        return False
    # Chunked to avoid building one enormous int for a long IBAN.
    rem = 0
    for ch in digits:
        rem = (rem * 10 + int(ch)) % 97
    return rem == 1


def _iban_sub(m: re.Match[str]) -> str:
    raw = m.group(0)
    return "***REDACTED-IBAN***" if _iban_ok(raw) else raw


def _pan_sub(m: re.Match[str]) -> str:
    """Redact only if it is Luhn-valid AND not the value of a numeric field."""
    raw = m.group(0)
    prefix = m.group(1) or ""
    if prefix:
        key = prefix.strip().rstrip(":=").strip().strip("\"'")
        if _NUMERIC_KEY.search(key):
            return raw
    digits = re.sub(r"[ -]", "", m.group(2))
    if not (13 <= len(digits) <= 19) or not _luhn_ok(digits):
        return raw
    return prefix + "***REDACTED-PAN***"


def _email_sub(m: re.Match[str]) -> str:
    return f"{m.group(1)[0]}***@{m.group(2)}"


# Order matters. Broad structural secrets (private keys, headers) are redacted
# before narrow value-shaped ones, so a token inside a header is not partially
# rewritten by an earlier rule.
_RULES: list[tuple[str, re.Pattern[str], Callable[[re.Match[str]], str] | str]] = [
    ("private_key",
     re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
                re.DOTALL),
     "***REDACTED-PRIVATE-KEY***"),

    ("bearer",
     re.compile(r"\bBearer\s+[A-Za-z0-9._~+/-]+=*"),
     "Bearer " + REDACTED),

    # Any other Authorization scheme (Basic, Digest, AWS4-HMAC-SHA256, ...).
    ("authorization",
     re.compile(r"(?i)\bauthorization\b" + _KEY_SEP +
                r"""(?!["']?\*\*\*)(?:"[^"\n]*"|'[^'\n]*'"""
                r"""|[^\s,;"'}\]]+(?:\s+[^\s,;"'}\]]+)?)"""),
     "Authorization: " + REDACTED),

    # Scoped to the cookie pair list itself: `name=v; name2=v2`. Consuming to
    # end-of-line would also swallow the trace_id/request_id that usually follow
    # in a log line, contradicting the promise to preserve correlation IDs.
    # The `(?!\*\*\*)` guards are not cosmetic: --verify defines residue as "the
    # redactor would still act here", so a rule that re-fires on its own output
    # reports a permanent false leak.
    ("cookie",
     re.compile(r"(?i)\b(?:set-)?cookie\b\s*[:=]\s*(?!\*\*\*)[^;\s]+(?:\s*;\s*[^;\s]+)*"),
     "Cookie: " + REDACTED),

    # Session identifiers appearing as bare key=value outside a Cookie header.
    ("session",
     re.compile(r"(?i)" + _KEY_OPEN + r"\b(jsessionid|phpsessid|sessionid|session_id|sid)"
                + _KEY_SEP + _VALUE),
     r"\1=" + REDACTED),

    ("url_password",
     re.compile(r"://([^:/@\s]+):(?!\*\*\*@)[^@/\s]+@"),
     r"://\1:***@"),

    ("api_key",
     re.compile(r"\b(?:sk-[A-Za-z0-9_-]{20,}"
                r"|AKIA[0-9A-Z]{16}"
                r"|ASIA[0-9A-Z]{16}"
                r"|xox[bpasr]-[A-Za-z0-9-]{10,}"
                r"|ghp_[A-Za-z0-9]{30,}"
                r"|gho_[A-Za-z0-9]{30,}"
                r"|github_pat_[A-Za-z0-9_]{20,}"
                r"|glpat-[A-Za-z0-9_-]{20,}"
                r"|AIza[A-Za-z0-9_-]{30,})"),
     "***REDACTED-API-KEY***"),

    # Values of sensitive keys in text logs (password=hunter2, token: "abc def").
    ("secret_kv",
     re.compile(r"(?i)" + _KEY_OPEN + r"\b(password|passwd|pwd|secret|client_secret|api[_-]?key|"
                r"access_token|refresh_token|id_token|token)" + _KEY_SEP + _VALUE),
     r"\1=" + REDACTED),

    ("govt_id",
     re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
     "***REDACTED-ID***"),

    # IBAN: shape first, MOD-97 checksum decides. Runs before the PAN rules so a
    # numeric IBAN body is not partially eaten as a card number.
    #
    # IGNORECASE because _iban_ok() upcases before checking: without it the helper
    # accepted `gb82west…` while the pattern never offered it, so a log normalised
    # to lower case leaked. The checksum still does the real filtering, so widening
    # the shape costs nothing.
    ("iban",
     re.compile(r"(?i)(?<![\w-])[A-Z]{2}\d{2}(?:[ ]?[A-Z0-9]{4}){2,7}[ ]?[A-Z0-9]{1,4}(?![\w-])"),
     _iban_sub),

    # Card numbers: grouped or contiguous, Luhn-checked, and skipped when the
    # preceding field name says the value is numeric (epoch millis are 13 digits).
    ("pan",
     re.compile(r"(?<![\w.-])" + _KEY_PREFIX + r"(\d{4}[ -]\d{4}[ -]\d{4}[ -]\d{1,7})(?![\w.-])"),
     _pan_sub),
    ("pan",
     re.compile(r"(?<![\w.-])" + _KEY_PREFIX + r"(\d{13,19})(?![\w.-])"),
     _pan_sub),

    # Phones require an explicit international prefix or NANP shape, so that
    # ISO-8601 timestamps and version strings are not mangled.
    #
    # The middle digits are masked and the LAST FOUR are kept, which is what both
    # SKILL.md Gate 2 and log-pii-redaction.md promise ("mask middle digits").
    # An earlier version masked everything, quietly contradicting both.
    ("phone",
     re.compile(r"\+\d{1,3}[- ]?\(?\d{2,4}\)?[- ]?\d{3,4}[- ]?(\d{4})\b"),
     r"+***-***-\1"),
    ("phone",
     re.compile(r"(?<![\w.-])\d{3}-\d{3}-(\d{4})(?![\w.-])"),
     r"***-***-\1"),

    ("email",
     re.compile(r"\b([A-Za-z0-9._%+-]+)@([A-Za-z0-9.-]+\.[A-Za-z]{2,})\b"),
     _email_sub),
]

_IP_RULE = ("ip", re.compile(r"(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?![\w.])"), "<masked-ip>")

# --redact-user-id in TEXT logs. The JSON walker matches EXTERNAL_ONLY_KEYS by
# field name, but plain-text lines (and the non-JSON continuation lines inside a
# JSON stream, e.g. a stack trace) never reach it. Without this rule an external
# report leaked `user_id=u-17 tenant_id=acme` verbatim while verify said clean.
_EXTERNAL_KV_RULE = (
    "external_kv",
    re.compile(r"(?i)" + _KEY_OPEN + r"\b(" + "|".join(sorted(EXTERNAL_ONLY_KEYS, key=len, reverse=True))
               + r")" + _KEY_SEP + _VALUE),
    r"\1=" + REDACTED,
)

# Rules that indicate a genuine secret whatever the surrounding field is called.
# Applied even to PRESERVED_KEYS, because "the key is named trace_id" is not
# evidence that its value is safe -- an email or token parked in a correlation
# field is still a leak.
_SECRET_RULE_NAMES = frozenset({
    "private_key", "bearer", "authorization", "cookie", "session",
    "url_password", "api_key", "secret_kv", "email", "govt_id",
    # IBAN belongs here even though it is value-shaped: MOD-97 makes a false
    # positive very unlikely, so it is safe to run over preserved correlation
    # fields. Without it, a valid IBAN misfiled into trace_id survived verbatim.
    # `pan` and `phone` stay out: a decimal trace_id can pass Luhn.
    "iban",
})

# A private key spans many lines, but the CLI reads one line at a time, so the
# DOTALL rule above can never match through a stream. These anchors drive a
# small state machine in Redactor.line().
_KEY_BEGIN = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")
_KEY_END = re.compile(r"-----END [A-Z ]*PRIVATE KEY-----")

# --verify deliberately has NO pattern list of its own. An earlier version kept a
# separate six-entry table, which silently omitted `secret_kv`, `cookie`,
# `session`, `pan` and `phone` -- so `password=hunter2` and `Cookie: session=abc`
# were reported as "verify: clean". A verifier that misses a category the
# redactor advertises is worse than none, because it turns an unchecked leak into
# a positive assurance.
#
# Instead, residue is defined as "the redactor would still change this", which
# cannot drift from _RULES because it IS _RULES. This requires the rules to be
# idempotent at the counter level, which test_redact_log.py pins per category.


class Redactor:
    """Applies the rule set to text or parsed JSON, counting what it changed."""

    def __init__(self, mask_ip: bool = False, redact_user_id: bool = False) -> None:
        self.rules = list(_RULES)
        if mask_ip:
            self.rules.append(_IP_RULE)
        if redact_user_id:
            self.rules.append(_EXTERNAL_KV_RULE)
        self.redact_user_id = redact_user_id
        self.counts: dict[str, int] = {}
        self.lines = 0
        self.json_parsed = 0
        self.json_failed = 0
        self._in_private_key = False

    def _bump(self, name: str, n: int) -> None:
        if n:
            self.counts[name] = self.counts.get(name, 0) + n

    def text(self, s: str, secrets_only: bool = False) -> str:
        """Apply the rule set. secrets_only skips the numeric-shape PII rules
        (card, phone), which produce false positives on identifier values.

        Counts CHANGES, not matches. `re.subn` reports how often the pattern
        matched, but the callback rules (pan, iban) deliberately decline when the
        checksum fails and return the text unchanged. Counting matches made
        `verify` -- which defines residue as "the redactor would still act here"
        -- fail on any log containing a 13-19 digit order number or an epoch
        timestamp, because the PAN rule matched and then declined.
        """
        for name, pattern, repl in self.rules:
            if secrets_only and name not in _SECRET_RULE_NAMES:
                continue
            if callable(repl):
                changed = 0

                def _counting(m: re.Match[str], _r=repl) -> str:
                    nonlocal changed
                    out = _r(m)
                    if out != m.group(0):
                        changed += 1
                    return out

                s = pattern.sub(_counting, s)
                n = changed
            else:
                s, n = pattern.subn(repl, s)
            self._bump(name, n)
        return s

    def _private_key_block(self, raw: str) -> str | None:
        """Streaming state machine for PEM blocks spanning multiple lines.

        Returns the replacement line, or None if this line is not part of a
        multi-line key block. Single-line BEGIN...END pairs are left to the
        ordinary rule so the surrounding text on that line survives.
        """
        if self._in_private_key:
            if _KEY_END.search(raw):
                self._in_private_key = False
            return ""  # body and END line are dropped entirely
        if _KEY_BEGIN.search(raw) and not _KEY_END.search(raw):
            self._in_private_key = True
            self._bump("private_key", 1)
            return _KEY_BEGIN.sub("***REDACTED-PRIVATE-KEY***", raw)
        return None

    def _walk(self, node: object, key: str | None = None) -> object:
        if isinstance(node, dict):
            out = {}
            for k, v in node.items():
                lk = k.lower()
                if lk in PRESERVED_KEYS:
                    # Preserve the field, but still scan its value: a correlation
                    # key is not a licence to emit whatever it happens to hold.
                    # Numeric-shape rules stay off so a decimal trace_id is not
                    # eaten as a card number.
                    out[k] = self.text(v, secrets_only=True) if isinstance(v, str) else v
                elif lk in SENSITIVE_KEYS or (self.redact_user_id and lk in EXTERNAL_ONLY_KEYS):
                    # Skip when already redacted: verify() defines residue as
                    # "the redactor would still act here", so re-firing on the
                    # sentinel reports a permanent false leak.
                    if v == REDACTED:
                        out[k] = v
                    else:
                        out[k] = REDACTED
                        self._bump("json_key:" + lk, 1)
                else:
                    out[k] = self._walk(v, lk)
            return out
        if isinstance(node, list):
            return [self._walk(v, key) for v in node]
        if isinstance(node, str):
            return self.text(node)
        return node

    def line(self, raw: str, json_mode: bool) -> str:
        self.lines += 1
        block = self._private_key_block(raw)
        if block is not None:
            return block
        if not json_mode:
            return self.text(raw)
        stripped = raw.strip()
        if not stripped:
            return raw
        try:
            obj = json.loads(stripped)
        except (ValueError, RecursionError):
            # Stack-trace continuation lines and mixed formats land here.
            self.json_failed += 1
            return self.text(raw)
        self.json_parsed += 1
        return json.dumps(self._walk(obj), ensure_ascii=False, separators=(",", ":"))

    def summary(self) -> dict[str, object]:
        return {
            "lines": self.lines,
            "json_parsed": self.json_parsed,
            "json_unparsed": self.json_failed,
            "categories": dict(sorted(self.counts.items())),
        }


def verify(stream: Iterable[str], json_mode: bool = False, *,
           mask_ip: bool = False, redact_user_id: bool = False) -> dict[str, int]:
    """Return residual-secret hits per category. Empty dict means clean.

    Residue is whatever the redactor would still act on, so the check can never
    cover fewer categories than the redactor implements.

    The policy flags MUST be passed through. Verifying an external-facing file
    with a default Redactor checks a weaker policy than the one that produced it
    and reports `clean` on output still carrying user_id, tenant_id and IPs --
    the verifier has to know which policy it is verifying against.
    """
    red = Redactor(mask_ip=mask_ip, redact_user_id=redact_user_id)
    for raw in stream:
        red.line(raw.rstrip("\n"), json_mode)
    return dict(sorted(red.counts.items()))


def _open_exclusive(path: str):
    """Create PATH for writing, refusing to clobber or follow anything.

    O_EXCL fails if the path exists at all, which also defeats a symlink planted
    at the destination -- the redacted copy of a log must never be able to
    overwrite the log itself, or any other existing file.
    """
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(path, flags, 0o600)
    return os.fdopen(fd, "w", encoding="utf-8")


def _add_common(p: argparse.ArgumentParser) -> None:
    p.add_argument("path", nargs="?", default="-", help="log file, or - for stdin")
    p.add_argument("--json", action="store_true",
                   help="treat each line as JSON; redact by field name as well as by value")
    p.add_argument("--mask-ip", action="store_true",
                   help="also mask IPv4 addresses (do this for reports leaving the company)")
    p.add_argument("--redact-user-id", action="store_true",
                   help="also redact user_id / email / tenant_id / org_id "
                        "(external-facing reports)")
    p.add_argument("--summary-json", action="store_true",
                   help="emit the stderr summary as JSON")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    # scan and verify deliberately have NO output option. Their read-only-ness is
    # enforced by the parser, which is what makes it safe to auto-approve them.
    _add_common(sub.add_parser("scan", help="redact to stdout (read-only)"))
    _add_common(sub.add_parser("verify", help="report residual secrets (read-only); "
                                              "exit 1 if any are found"))

    w = sub.add_parser("write", help="redact to a file (WRITES; not auto-approved)")
    _add_common(w)
    w.add_argument("-o", "--output", metavar="PATH", required=True,
                   help="destination, created with O_EXCL|O_NOFOLLOW: an existing "
                        "path, symlink, or non-regular file is refused, so a "
                        "redaction pass can never overwrite the log it is reading")

    args = ap.parse_args(argv)

    src = sys.stdin if args.path == "-" else open(args.path, encoding="utf-8", errors="replace")
    try:
        if args.cmd == "verify":
            # The verifier must apply the SAME policy as the redaction it checks.
            # Verifying an external-facing file without these flags reported
            # `clean` on output still containing user_id and IP addresses.
            hits = verify(src, args.json, mask_ip=args.mask_ip,
                          redact_user_id=args.redact_user_id)
            if hits:
                print("RESIDUAL SECRETS FOUND: "
                      + ", ".join(f"{k}={v}" for k, v in hits.items()), file=sys.stderr)
                return 1
            print("verify: clean", file=sys.stderr)
            return 0

        out = sys.stdout
        if args.cmd == "write":
            try:
                out = _open_exclusive(args.output)
            except OSError as e:
                print(f"refusing to write {args.output!r}: {e}", file=sys.stderr)
                return 2

        red = Redactor(mask_ip=args.mask_ip, redact_user_id=args.redact_user_id)
        try:
            for raw in src:
                out.write(red.line(raw.rstrip("\n"), args.json) + "\n")
        finally:
            if out is not sys.stdout:
                out.close()
    finally:
        if src is not sys.stdin:
            src.close()

    summary = red.summary()
    if args.summary_json:
        print(json.dumps(summary), file=sys.stderr)
    else:
        cats = summary["categories"]
        rendered = ", ".join(f"{k}={v}" for k, v in cats.items()) if cats else "none detected"
        print(f"redacted {summary['lines']} lines; categories: {rendered}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
