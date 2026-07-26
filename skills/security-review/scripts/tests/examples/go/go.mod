module secexamples

// 1.24: os.Root / os.OpenRoot, used by the recommended path-containment example.
// (A lower directive would still compile — it gates language features, not stdlib symbols —
// but declaring 1.24 states the real API requirement.)
//
// GO-2026-4970 (os.Root trailing-separator containment escape) is fixed in Go 1.25.12+,
// 1.26.5+, 1.27.0-rc.2+. Production builds should use a fixed toolchain — that is the fix.
//
// This directive stays at the API floor (1.24) on purpose: raising it would make the example
// module unbuildable on older toolchains without adding safety, and TestTrailingSeparatorEscape-
// IsContained is written to pass on affected AND patched toolchains, asserting the documented
// filepath.Clean mitigation either way. Keep govulncheck in CI for the authoritative answer.
go 1.24
