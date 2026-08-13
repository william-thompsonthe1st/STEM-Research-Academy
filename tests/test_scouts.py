import unittest

from robot_server.scouts import CameraRegistry, ScoutRegistry


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


class CameraRegistryTests(unittest.TestCase):
    def test_camera_registration_prefers_the_current_dhcp_address(self):
        registry = CameraRegistry()
        registry.record("B", "10.42.0.42", -47, 4321)
        record = registry.snapshot("b")
        self.assertEqual(record["ip"], "10.42.0.42")
        self.assertEqual(registry.stream_url("b", "http://larp-b-cam.local/stream"), "http://10.42.0.42/stream")

    def test_camera_registration_rejects_unknown_id(self):
        registry = CameraRegistry()
        with self.assertRaises(ValueError):
            registry.record("Z", "10.42.0.99")


if __name__ == "__main__":
    unittest.main()
