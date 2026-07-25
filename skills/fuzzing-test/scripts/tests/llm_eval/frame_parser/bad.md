## Applicability Verdict

`Applicability Verdict: Suitable for fuzzing`

## Why

- It's a parser, so fuzzing applies.
- Takes bytes.
- Should not crash.

## Action

Fuzz mode: **round-trip**. Using Template B.

## Harness

```go
func FuzzParseFrame(f *testing.F) {
	f.Add([]byte{0x01, 0x00})

	f.Fuzz(func(t *testing.T, data []byte) {
		if len(data) > 2 {
			t.Skip()
		}
		_, _ = ParseFrame(data)
	})
}
```

## Notes

The fuzzer will report any panic automatically, so no assertion is needed.

Run with `go test -fuzz=^Fuzz .`
