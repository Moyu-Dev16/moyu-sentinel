import unittest
from src.mutation_guard import MutationGuard

class TestMutationGuard(unittest.TestCase):
    def test_floor_boundary_mutation(self):
        # Exact floor balance MUST be HELD, not BROKEN
        self.assertEqual(MutationGuard.evaluate_floor(100, 100), "HELD")
        self.assertEqual(MutationGuard.evaluate_floor(99, 100), "BROKEN")

    def test_half_open_window_mutation(self):
        # Window [1000, 2000): 1000 is BROKEN, 2000 is HELD
        self.assertEqual(MutationGuard.evaluate_window(1000, 1000, 2000), "BROKEN")
        self.assertEqual(MutationGuard.evaluate_window(2000, 1000, 2000), "HELD")

    def test_disclosure_deadline_mutation(self):
        # Exact deadline instant MUST be HELD
        self.assertEqual(MutationGuard.evaluate_disclosure(1500, 1000, 500), "HELD")
        self.assertEqual(MutationGuard.evaluate_disclosure(1501, 1000, 500), "BROKEN")

    def test_zero_value_transfer_griefing(self):
        # 0-value transfer MUST NOT be treated as valid transfer
        self.assertFalse(MutationGuard.evaluate_transfer_validity("0xAlice", "0xAlice", 0))
        self.assertTrue(MutationGuard.evaluate_transfer_validity("0xAlice", "0xAlice", 100))

if __name__ == "__main__":
    unittest.main()
