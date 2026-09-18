## Scope verdict

`Scope: OUT OF SCOPE for $api-integration-test`

## Recommended skill

**`$unit-test`** — table-driven unit tests for `NormalizeTag`.

## Reason

`NormalizeTag(raw string) string` is a **pure function**: no client, no transport, no
network, no I/O, no clock, no external dependency of any kind. This skill's Scope
Validation Gate admits internal HTTP/gRPC APIs and service-to-service adapters — a target
must have something to integrate *with*.

Two consequences worth stating plainly, because "just add a build tag and call it an
integration test" is the tempting mistake:

- There is no real transport to exercise. An "integration test" here would either be a
  unit test wearing a `//go:build integration` tag — which hides it from the default
  `go test ./...` and gains nothing — or it would have to substitute a transport that
  does not exist.
- Per §Test Taxonomy, even a stub `httptest` server in front of a real client is an
  *adapter test*, not an integration test. This target does not even have a client.

What `NormalizeTag` does need is boundary coverage, which is exactly `$unit-test`'s job:
empty input, whitespace-only, leading/trailing separators, runs of `-`/`_`/space collapsing
to one, mixed case, and a non-ASCII rune (the loop is rune-wise, so a multi-byte character
is a real boundary).

**Hard stop.** Per the Scope Validation Gate, the remaining gates are skipped and no test
code is generated.
