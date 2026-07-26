package secexamples

import (
	"os"
	"path/filepath"
	"strings"
)

// lexicalGuardNoSep is the guidance this skill used to give:
//
//	strings.HasPrefix(filepath.Clean(result), base)
//
// It is kept here only so the tests can demonstrate that it fails. Two escapes get through:
// a sibling directory sharing the base's name prefix, and any symlink inside the base.
func lexicalGuardNoSep(base, userInput string) (string, bool) {
	result := filepath.Join(base, userInput)
	return result, strings.HasPrefix(filepath.Clean(result), base)
}

// lexicalGuardWithSep adds the trailing separator, which closes the sibling-prefix hole but
// still cannot see symlinks — a lexical check never resolves the filesystem.
func lexicalGuardWithSep(base, userInput string) (string, bool) {
	result := filepath.Clean(filepath.Join(base, userInput))
	return result, strings.HasPrefix(result, base+string(os.PathSeparator))
}

// openRootRaw hands user input straight to os.Root. This is NOT the recommended pattern: the
// trailing-separator form (`<symlink>/`) escapes containment (GO-2026-4970, reproduced on
// go1.26.1). Kept so the tests can demonstrate the escape rather than assume it is fixed.
func openRootRaw(base, userInput string) (*os.File, error) {
	root, err := os.OpenRoot(base)
	if err != nil {
		return nil, err
	}
	defer root.Close()
	return root.Open(userInput)
}

// openContained is the recommended pattern: Clean the relative input first — which strips the
// trailing separator that bypasses containment — then let os.Root resolve it symlink-aware.
func openContained(base, userInput string) (*os.File, error) {
	rel := filepath.Clean(userInput)
	if rel == "." || rel == ".." || filepath.IsAbs(rel) {
		return nil, os.ErrPermission
	}
	root, err := os.OpenRoot(base)
	if err != nil {
		return nil, err
	}
	defer root.Close()
	return root.Open(rel)
}
