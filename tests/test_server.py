import time
import unittest
from unittest.mock import patch

from robot_server.app import app, drive, drive_sequences, scout_registry, scout_sequences


class ServerTests(unittest.TestCase):
    def setUp(self):
        app.config.update(TESTING=True)
        self.client = app.test_client()

    def tearDown(self):
        drive.stop()
        drive_sequences.clear()
        scout_sequences.clear()

    @staticmethod
    def current_command(**values):
        values["expires_at_ms"] = round(time.time() * 1000) + 1000
        return values

    def test_health(self):
        response = self.client.get("/healthz")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["ok"])

    def test_status_exposes_optional_feature_health_without_blocking_control(self):
        response = self.client.get("/api/status")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn(data["camera_profile"], {"control", "balanced", "detail"})
        self.assertIn("vision", data)
        self.assertIn("3tsahur", data["vision"])

    def test_drive_command(self):
        response = self.client.post(
            "/api/drive",
            json=self.current_command(forward=1, strafe=0, rotate=0, speed=0.5),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(drive.last_command["forward"], 1)
        self.assertEqual(drive.last_command["speed"], 0.5)

    def test_invalid_drive_command(self):
        response = self.client.post("/api/drive", json=self.current_command(forward="fast"))
        self.assertEqual(response.status_code, 400)

    def test_stale_big_robot_command_is_ignored(self):
        self.client.post(
            "/api/drive",
            json=self.current_command(forward=0, session="test", sequence=2),
        )
        response = self.client.post(
            "/api/drive",
            json=self.current_command(forward=1, session="test", sequence=1),
        )
        self.assertTrue(response.get_json()["stale"])
        self.assertEqual(drive.last_command["forward"], 0)

    def test_non_finite_drive_command(self):
        response = self.client.post("/api/drive", json=self.current_command(forward="NaN"))
        self.assertEqual(response.status_code, 400)

    def test_expired_big_robot_command_cannot_replay(self):
        drive.drive(1, 0, 0, 0.5)
        response = self.client.post(
            "/api/drive", json={"forward": 1, "expires_at_ms": 1}
        )
        self.assertEqual(response.status_code, 409)
        self.assertTrue(response.get_json()["expired"])
        self.assertEqual(drive.last_command["forward"], 0)

    def test_implausible_future_command_is_rejected(self):
        response = self.client.post(
            "/api/drive",
            json={"forward": 1, "expires_at_ms": round(time.time() * 1000) + 60_000},
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(drive.last_command["forward"], 0)

    def test_dashboard_renders_all_three_robots(self):
        response = self.client.get("/")
        self.assertIn(b"Robot dashboards", response.data)
        self.assertIn(b'data-tab="3tsahur"', response.data)
        self.assertIn(b'data-tab="larp-a"', response.data)
        self.assertIn(b'data-tab="larp-b"', response.data)
        self.assertIn(b'data-stream-for="3tsahur"', response.data)
        self.assertIn(b'data-stream-for="larp-a"', response.data)
        self.assertIn(b'data-stream-for="larp-b"', response.data)
        self.assertIn(b"LARP Scout A", response.data)
        self.assertIn(b"LARP Scout B", response.data)
        self.assertIn(b"3TSahur", response.data)

    def test_unknown_vision_source_is_rejected_without_affecting_drive(self):
        response = self.client.get("/api/vision/unknown")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(drive.last_command["forward"], 0)

    @patch("robot_server.app.camera.configure")
    def test_camera_profile_isolated_from_drive(self, configure):
        response = self.client.post("/api/camera/profile", json={"profile": "control"})
        self.assertEqual(response.status_code, 200)
        configure.assert_called_once_with(320, 240, 6)
        drive_response = self.client.post("/api/drive", json=self.current_command(forward=1))
        self.assertEqual(drive_response.status_code, 200)
        self.assertEqual(drive.last_command["forward"], 1)

    def test_invalid_camera_profile_is_rejected(self):
        self.assertEqual(self.client.post("/api/camera/profile", json={"profile": "unsafe"}).status_code, 400)

    def test_timeline_is_bounded_and_does_not_require_hardware(self):
        created = self.client.post("/api/events", json={"kind": "test", "source": "test", "message": "timeline ok"})
        self.assertEqual(created.status_code, 200)
        listed = self.client.get("/api/events")
        self.assertEqual(listed.status_code, 200)
        self.assertTrue(any(event["message"] == "timeline ok" for event in listed.get_json()["events"]))

    @patch("robot_server.app._snapshot_bytes", return_value=None)
    def test_unavailable_snapshot_does_not_affect_drive(self, snapshot):
        response = self.client.post("/api/snapshots/3tsahur")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(drive.last_command["forward"], 0)

    @patch("robot_server.app.scout_registry.record", return_value={
        "id": "a", "ip": "10.42.0.31", "last_seen": 1.0,
        "rssi": -51, "uptime_ms": 1200, "transport": "http",
    })
    def test_scout_can_register_its_dhcp_address(self, record):
        response = self.client.get(
            "/api/scouts/register?id=A&rssi=-51&uptime_ms=1200",
            environ_base={"REMOTE_ADDR": "10.42.0.31"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["registered"])
        record.assert_called_once_with("a", "10.42.0.31", -51, 1200, "http")

    def test_scout_registration_rejects_unknown_id(self):
        response = self.client.get("/api/scouts/register?id=Z")
        self.assertEqual(response.status_code, 400)

    @patch("robot_server.app._scout_request", return_value={"id": "A", "motion": True, "motion_level": 42.5})
    def test_scout_status_proxy(self, scout_request):
        with patch("robot_server.app.scout_registry.snapshot", return_value={"ip": "10.42.0.20"}):
            response = self.client.get("/api/scouts/a/status")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["online"])
        self.assertTrue(response.get_json()["motion"])
        self.assertEqual(response.get_json()["motion_level"], 42.5)
        scout_request.assert_called_once_with("a", "/status")

    @patch("robot_server.app._scout_request", return_value={"ok": True})
    def test_scout_drive_proxy_clamps_values(self, scout_request):
        with patch("robot_server.app.scout_registry.snapshot", return_value={"ip": "10.42.0.21"}):
            response = self.client.post(
                "/api/scouts/b/drive",
                json=self.current_command(x=500, y=-500, speed=35),
            )
        self.assertEqual(response.status_code, 200)
        scout_request.assert_called_once_with(
            "b", "/drive", {"x": 100, "y": -100, "speed": 35}
        )

    @patch("robot_server.app._scout_request", return_value={"ok": True})
    def test_stale_scout_command_is_not_forwarded(self, scout_request):
        with patch("robot_server.app.scout_registry.snapshot", return_value={"ip": "10.42.0.20"}):
            self.client.post(
                "/api/scouts/a/drive",
                json=self.current_command(x=0, y=0, session="test", sequence=2),
            )
            response = self.client.post(
                "/api/scouts/a/drive",
                json=self.current_command(x=0, y=100, session="test", sequence=1),
            )
        self.assertTrue(response.get_json()["stale"])
        self.assertEqual(scout_request.call_count, 1)

    @patch("robot_server.app._scout_request", side_effect=OSError("must not be called"))
    def test_offline_scout_status_is_safe(self, scout_request):
        response = self.client.get("/api/scouts/a/status")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.get_json()["online"])
        scout_request.assert_not_called()

    @patch("robot_server.app._scout_request", side_effect=OSError("must not be called"))
    def test_offline_scout_drive_fails_fast(self, scout_request):
        response = self.client.post(
            "/api/scouts/a/drive", json=self.current_command(x=0, y=100)
        )
        self.assertEqual(response.status_code, 409)
        scout_request.assert_not_called()


if __name__ == "__main__":
    unittest.main()
