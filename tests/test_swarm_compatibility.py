import time
import unittest
from unittest.mock import patch

from robot_server.app import app, drive, drive_sequences, scout_registry, scout_sequences


class SwarmCompatibilityTests(unittest.TestCase):
    def setUp(self):
        app.config.update(TESTING=True)
        self.client = app.test_client()
        drive.stop()
        drive_sequences.clear()
        scout_sequences.clear()

    @staticmethod
    def command(**values):
        values["expires_at_ms"] = round(time.time() * 1000) + 300
        return values

    @patch("robot_server.app._scout_request")
    def test_all_three_robot_control_paths_are_compatible(self, scout_request):
        def simulated_scout(scout_id, path, query=None):
            if path == "/status":
                return {"id": scout_id.upper(), "motion": False, "motion_level": 0}
            return {"ok": True, "id": scout_id.upper(), "motion": query}

        scout_request.side_effect = simulated_scout
        for scout_id, address in (("A", "10.42.0.31"), ("B", "10.42.0.32")):
            response = self.client.post(
                "/api/scouts/register",
                json={"id": scout_id, "rssi": -48, "uptime_ms": 5000},
                environ_base={"REMOTE_ADDR": address},
            )
            self.assertEqual(response.status_code, 200)

        self.assertEqual(
            self.client.post("/api/drive", json=self.command(forward=1, speed=.35)).status_code,
            200,
        )
        self.assertEqual(
            self.client.post("/api/scouts/a/drive", json=self.command(y=100, speed=30)).status_code,
            200,
        )
        self.assertEqual(
            self.client.post("/api/scouts/b/drive", json=self.command(x=-100, speed=30)).status_code,
            200,
        )
        self.assertEqual(self.client.get("/api/scouts/a/status").status_code, 200)
        self.assertEqual(self.client.get("/api/scouts/b/status").status_code, 200)
        self.assertEqual(drive.last_command["forward"], 1)
        self.assertGreaterEqual(scout_request.call_count, 4)

    @patch("robot_server.app._scout_request", return_value={"ok": True})
    def test_control_routes_have_no_local_queue_buildup(self, scout_request):
        scout_registry.record("a", "10.42.0.31")
        samples = []
        for sequence in range(1, 41):
            started = time.perf_counter()
            self.assertEqual(
                self.client.post(
                    "/api/drive",
                    json=self.command(forward=1, speed=.30, session="bench", sequence=sequence),
                ).status_code,
                200,
            )
            self.assertEqual(
                self.client.post(
                    "/api/scouts/a/drive",
                    json=self.command(y=100, speed=30, session="bench", sequence=sequence),
                ).status_code,
                200,
            )
            samples.append(time.perf_counter() - started)
        p95 = sorted(samples)[int(len(samples) * .95) - 1]
        self.assertLess(p95, .050, "simulated Pi/LARP control path exceeded 50 ms")


if __name__ == "__main__":
    unittest.main()
