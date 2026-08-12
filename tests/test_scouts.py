import unittest

from robot_server.scouts import ScoutRegistry


class ScoutRegistryTests(unittest.TestCase):
    def test_http_registration_records_address_and_transport(self):
        registry = ScoutRegistry(port=0)
        try:
            registry.record("A", "10.42.0.31", -52, 1234, "http")
            record = registry.snapshot("a")
            self.assertEqual(record["ip"], "10.42.0.31")
            self.assertEqual(record["rssi"], -52)
            self.assertEqual(record["transport"], "http")
        finally:
            registry.close()

    def test_registration_rejects_unknown_robot(self):
        registry = ScoutRegistry(port=0)
        try:
            with self.assertRaises(ValueError):
                registry.record("Z", "10.42.0.99")
        finally:
            registry.close()


if __name__ == "__main__":
    unittest.main()
