package main

import (
	"encoding/json"
	"reflect"
	"testing"
)

/*
 go test -run=^$ -fuzz=^FuzzJSONUnmarshal$ -fuzztime=5s .
fuzz: elapsed: 0s, gathering baseline coverage: 0/13 completed
fuzz: elapsed: 0s, gathering baseline coverage: 13/13 completed, now fuzzing with 10 workers
fuzz: elapsed: 3s, execs: 134243 (44740/sec), new interesting: 159 (total: 172)
fuzz: elapsed: 6s, execs: 229329 (31691/sec), new interesting: 219 (total: 232)
fuzz: elapsed: 6s, execs: 229329 (0/sec), new interesting: 219 (total: 232)
PASS
ok      tcg-acs-go-sp   6.377s
*/

func FuzzJSONUnmarshal(f *testing.F) {
	f.Add([]byte{})
	f.Add([]byte("null"))
	f.Add([]byte("true"))
	f.Add([]byte("0"))
	f.Add([]byte(`""`))
	f.Add([]byte(`[]`))
	f.Add([]byte(`{}`))
	f.Add([]byte(`{"k":"v","n":1,"arr":[true,false,null]}`))
	f.Add([]byte(`{"nested":{"items":[1,2,3],"flag":true}}`))
	f.Add([]byte(`{"unterminated"`))
	f.Add([]byte(`{"bad":`))
	f.Add([]byte(`[`))
	f.Add([]byte(`"`))

	f.Fuzz(func(t *testing.T, data []byte) {
		if len(data) > 1<<16 {
			t.Skip()
		}

		var got any
		if err := json.Unmarshal(data, &got); err != nil {
			return
		}

		normalized, err := json.Marshal(got)
		if err != nil {
			t.Fatalf("marshal after successful unmarshal failed: %v", err)
		}

		var reparsed any
		if err := json.Unmarshal(normalized, &reparsed); err != nil {
			t.Fatalf("re-unmarshal normalized JSON failed: %v; normalized=%q", err, normalized)
		}

		if !reflect.DeepEqual(reparsed, got) {
			t.Fatalf("normalized round-trip mismatch: got=%#v reparsed=%#v normalized=%q", got, reparsed, normalized)
		}
	})
}
