package fixture

import "testing"

func TestSum(t *testing.T) {
	t.Parallel()

	if got := Sum(2, 3); got != 5 {
		t.Errorf("Sum(2, 3) = %d, want 5", got)
	}
}
