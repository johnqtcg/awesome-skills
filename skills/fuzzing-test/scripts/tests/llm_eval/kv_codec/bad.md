## Applicability Verdict

`Applicability Verdict: Suitable for fuzzing`

## Why

- It encodes and decodes bytes, so fuzzing applies.
- Should not crash.

## Action

Fuzz mode: **parser robustness**. Using Template A.

## Harness

```go
func FuzzRoundTripRecord(f *testing.F) {
	f.Add("key", int32(1))

	f.Fuzz(func(t *testing.T, key string, value int32) {
		if len(key) > 255 {
			t.Skip()
		}
		enc, err := Encode(Record{Key: key, Value: value})
		if err != nil {
			t.Skip()
		}
		_, _ = Decode(enc)
	})
}
```

## Notes

Go's fuzzer fails the target on any panic, so no assertion is needed here.

Run with `go test -fuzz=^Fuzz .`
