import unittest
import os
from src.keeperhub_adapter import KeeperHubAdapter

class TestKeeperHubAdapter(unittest.TestCase):
    def setUp(self):
        self.test_log = "test_audit.jsonl"
        self.adapter = KeeperHubAdapter(audit_path=self.test_log)

    def tearDown(self):
        if os.path.exists(self.test_log):
            try:
                os.remove(self.test_log)
            except:
                pass

    def test_deterministic_hash(self):
        sim1 = self.adapter.simulate_action("test", {"foo": "bar"})
        sim2 = self.adapter.simulate_action("test", {"foo": "bar"})
        self.assertEqual(sim1["simulation_hash"], sim2["simulation_hash"])

    def test_transfer_execution(self):
        res = self.adapter.execute_transfer("0x1234567890123456789012345678901234567890", 1000)
        self.assertEqual(res["status"], "EXECUTED")
        self.assertTrue(res["tx_hash"].startswith("0xkh_"))

    def test_contract_call(self):
        res = self.adapter.execute_contract_call("0xabc", "mint", [1, "test"])
        self.assertEqual(res["status"], "EXECUTED")
        self.assertTrue("gas_used" in res)

if __name__ == "__main__":
    unittest.main()
