// Package fixture is the Go code this repository's CI runs the Go workflow on: one function
// and its test, with a second constant under the dev build tag so the tagged legs compile
// something the untagged ones do not.
package fixture

// Sum adds two numbers.
func Sum(a, b int) int {
	return a + b
}
