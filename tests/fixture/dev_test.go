//go:build dev

package fixture

import "testing"

func TestDev(t *testing.T) {
	t.Parallel()

	if !Dev {
		t.Error("Dev = false under the dev tag")
	}
}
