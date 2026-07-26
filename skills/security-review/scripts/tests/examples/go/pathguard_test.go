package secexamples

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// TestLexicalGuardAllowsSiblingPrefixEscape pins the sibling-prefix hole in the retired
// advice. If this ever stops failing, Go changed and the §Path Traversal warning needs review.
func TestLexicalGuardAllowsSiblingPrefixEscape(t *testing.T) {
	got, allowed := lexicalGuardNoSep("/var/app", "../app-evil/secret")
	if got != "/var/app-evil/secret" {
		t.Fatalf("unexpected join result %q", got)
	}
	if !allowed {
		t.Fatal("the no-separator prefix guard is expected to WRONGLY allow this; " +
			"if it now rejects it, the documented warning is stale")
	}

	// The documented lexical fallback (trailing separator) must close this one.
	if _, ok := lexicalGuardWithSep("/var/app", "../app-evil/secret"); ok {
		t.Fatal("trailing-separator guard must reject a sibling-prefix escape")
	}
}

// TestLexicalGuardCannotSeeSymlinks proves a lexical check is not sufficient for file access,
// which is what `scenario-checklists.md` promises to catch under "symlink escape".
func TestLexicalGuardCannotSeeSymlinks(t *testing.T) {
	base := t.TempDir()
	outside := t.TempDir()
	secret := filepath.Join(outside, "secret.txt")
	if err := os.WriteFile(secret, []byte("TOP SECRET"), 0o600); err != nil {
		t.Fatal(err)
	}
	if err := os.Symlink(outside, filepath.Join(base, "link")); err != nil {
		t.Skipf("symlinks unavailable here: %v", err)
	}

	// Even WITH the trailing separator, the lexical guard sees nothing wrong.
	path, allowed := lexicalGuardWithSep(base, "link/secret.txt")
	if !allowed {
		t.Fatal("lexical guard unexpectedly rejected a symlinked path; " +
			"the docs claim it cannot detect this")
	}
	data, err := os.ReadFile(path)
	if err != nil || string(data) != "TOP SECRET" {
		t.Fatalf("expected the escape to succeed under the lexical guard, got err=%v data=%q",
			err, data)
	}
}

// TestRawOsRootLeaksViaTrailingSeparator is the GO-2026-4970 regression. The advisory frames
// this as fixed before Go 1.25.12, but it REPRODUCES on go1.26.1 — so the test asserts the
// documented mitigation rather than a version range.
//
// The invariant is version-agnostic and never skips: whatever the toolchain does with the raw
// call, `openContained` (the pattern the docs prescribe) MUST block the escape. On a patched
// toolchain (1.25.12+ / 1.26.5+ / 1.27.0-rc.2+) the raw call is also blocked, and the test
// records that as the expected good outcome instead of skipping.
func TestTrailingSeparatorEscapeIsContained(t *testing.T) {
	base := t.TempDir()
	outside := t.TempDir()
	if err := os.WriteFile(filepath.Join(outside, "secret.txt"), []byte("TOP SECRET"), 0o600); err != nil {
		t.Fatal(err)
	}
	if err := os.Symlink(outside, filepath.Join(base, "link")); err != nil {
		t.Skipf("symlinks unavailable here: %v", err)
	}

	// Without the trailing separator, containment must hold on every toolchain.
	if _, err := openRootRaw(base, "link"); err == nil {
		t.Error("os.Root allowed the bare symlink name; containment is broken beyond the known bug")
	}

	// The raw call is the version-dependent part — report which side we are on, do not skip.
	if f, err := openRootRaw(base, "link/"); err == nil {
		names, rderr := f.Readdirnames(-1)
		f.Close()
		if rderr == nil && len(names) > 0 {
			t.Logf("toolchain is AFFECTED by GO-2026-4970: raw os.Root escaped and enumerated "+
				"%v outside the root. Upgrade to 1.25.12+/1.26.5+/1.27.0-rc.2+.", names)
		} else {
			t.Logf("toolchain is AFFECTED by GO-2026-4970: raw os.Root returned a handle for "+
				"%q", "link/")
		}
	} else {
		t.Logf("toolchain appears PATCHED for GO-2026-4970: raw os.Root refused %q (%v)",
			"link/", err)
	}

	// The documented mitigation must hold either way. This is the assertion that matters.
	if _, err := openContained(base, "link/"); err == nil {
		t.Fatal("filepath.Clean pre-pass FAILED to block the trailing-separator escape — " +
			"the documented mitigation in §Path Traversal is ineffective")
	}
}

// TestCleanPrePassKeepsLegitimatePathsWorking guards against the mitigation being over-broad:
// a fix that also rejects valid input would just get removed by the next maintainer.
func TestCleanPrePassKeepsLegitimatePathsWorking(t *testing.T) {
	base := t.TempDir()
	if err := os.WriteFile(filepath.Join(base, "ok.txt"), []byte("fine"), 0o600); err != nil {
		t.Fatal(err)
	}
	if err := os.Mkdir(filepath.Join(base, "realdir"), 0o755); err != nil {
		t.Fatal(err)
	}
	for _, ok := range []string{"ok.txt", "./ok.txt", "realdir", "realdir/"} {
		f, err := openContained(base, ok)
		if err != nil {
			t.Errorf("mitigation wrongly rejected legitimate input %q: %v", ok, err)
			continue
		}
		f.Close()
	}
	for _, bad := range []string{"..", ".", "/etc/passwd"} {
		if _, err := openContained(base, bad); err == nil {
			t.Errorf("mitigation allowed %q", bad)
		}
	}
}

// TestOsRootRefusesEscapes is the positive case for the recommended fix.
func TestOsRootRefusesEscapes(t *testing.T) {
	base := t.TempDir()
	outside := t.TempDir()
	if err := os.WriteFile(filepath.Join(outside, "secret.txt"), []byte("TOP SECRET"), 0o600); err != nil {
		t.Fatal(err)
	}
	if err := os.Symlink(outside, filepath.Join(base, "link")); err != nil {
		t.Skipf("symlinks unavailable here: %v", err)
	}
	if err := os.WriteFile(filepath.Join(base, "ok.txt"), []byte("fine"), 0o600); err != nil {
		t.Fatal(err)
	}

	// Legitimate access still works.
	f, err := openContained(base, "ok.txt")
	if err != nil {
		t.Fatalf("os.Root rejected a legitimate in-root file: %v", err)
	}
	f.Close()

	for _, bad := range []string{
		"link/secret.txt", // symlink escape — the case no lexical guard catches
		"../" + filepath.Base(outside) + "/secret.txt", // traversal
		"/etc/passwd", // absolute path
	} {
		if _, err := openContained(base, bad); err == nil {
			t.Errorf("os.Root ALLOWED %q — containment is broken", bad)
		} else if !strings.Contains(err.Error(), "escapes") &&
			!os.IsNotExist(err) && !strings.Contains(err.Error(), "invalid") {
			t.Logf("%q rejected with: %v", bad, err)
		}
	}
}
