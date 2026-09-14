package eval

// Add returns the sum of two ints. Fixed-path arithmetic: no parsing, no branching on
// input structure, no invariant a fuzzer could violate that a table test would not.
func Add(a, b int) int { return a + b }

// Double returns 2*n. Same shape.
func Double(n int) int { return n * 2 }
