import unittest
from src.sentinel import WorkstationSentinel

class TestSentinel(unittest.TestCase):
    def test_hardware_status(self):
        sentinel = WorkstationSentinel()
        status = sentinel.get_hardware_status()
        self.assertIn("ram_percent", status)
        self.assertIn("cpu_percent", status)
        self.assertIn("status", status)

if __name__ == "__main__":
    unittest.main()
