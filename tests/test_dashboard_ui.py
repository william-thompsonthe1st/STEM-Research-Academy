import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = (PROJECT_ROOT / "robot_server" / "templates" / "index.html").read_text(encoding="utf-8")
STYLES = (PROJECT_ROOT / "robot_server" / "static" / "dashboard.css").read_text(encoding="utf-8")
SCRIPT = (PROJECT_ROOT / "robot_server" / "static" / "dashboard.js").read_text(encoding="utf-8")


class DashboardTabTests(unittest.TestCase):
    def test_all_three_robot_tabs_have_separate_panels(self):
        for robot in ("3tsahur", "larp-a", "larp-b"):
            self.assertIn(f'data-tab="{robot}"', TEMPLATE)
            self.assertIn(f'data-tab-panel="{robot}"', TEMPLATE)
        self.assertEqual(TEMPLATE.count('role="tab"'), 3)
        self.assertEqual(TEMPLATE.count('role="tabpanel"'), 3)

    def test_each_tab_has_its_own_video_and_controls(self):
        self.assertIn('alt="Live Logitech C270 camera feed from 3TSahur"', TEMPLATE)
        self.assertIn('alt="Live Inland ESP32-CAM feed from LARP Scout A"', TEMPLATE)
        self.assertIn('alt="Live Inland ESP32-CAM feed from LARP Scout B"', TEMPLATE)
        self.assertIn('aria-label="3TSahur drive controls"', TEMPLATE)
        self.assertIn('aria-label="LARP Scout A drive controls"', TEMPLATE)
        self.assertIn('aria-label="LARP Scout B drive controls"', TEMPLATE)

    def test_only_the_selected_tab_keeps_a_camera_stream_open(self):
        self.assertEqual(TEMPLATE.count("data-stream-for="), 3)
        self.assertEqual(TEMPLATE.count("data-stream-src="), 3)
        self.assertIn("function activateOnlySelectedCamera", SCRIPT)
        self.assertIn("feed.removeAttribute('src')", SCRIPT)
        self.assertIn("activateOnlySelectedCamera(id);", SCRIPT)

    def test_larp_tabs_show_the_csi_presence_indicator(self):
        self.assertEqual(TEMPLATE.count("CSI presence sensor"), 2)
        self.assertIn('id="scout-a-csi"', TEMPLATE)
        self.assertIn('id="scout-b-csi"', TEMPLATE)
        self.assertIn("function renderCsiSensor", SCRIPT)
        self.assertIn("Possible presence - check video", SCRIPT)
        self.assertIn("scoutStatusInFlight", SCRIPT)
        self.assertIn(".csi-sensor.detected", STYLES)

    def test_vision_has_a_per_camera_toggle_and_overlay(self):
        for source in ("3tsahur", "larp-a", "larp-b"):
            self.assertIn(f'data-vision-toggle="{source}"', TEMPLATE)
            self.assertIn(f'data-vision-overlay="{source}"', TEMPLATE)
        self.assertIn("key === 'c'", SCRIPT)
        self.assertIn("toggleVision(activeRobotTab)", SCRIPT)
        self.assertIn("/api/vision/${source}", SCRIPT)
        self.assertIn("Vision unavailable - robot controls remain active", SCRIPT)
        self.assertIn(".vision-overlay", STYLES)

    def test_mission_tools_profiles_and_health_are_optional_dashboard_features(self):
        self.assertIn('id="camera-profile"', TEMPLATE)
        self.assertIn('id="health-panel"', TEMPLATE)
        self.assertEqual(TEMPLATE.count('data-snapshot="'), 3)
        self.assertEqual(TEMPLATE.count('data-calibrate="'), 2)
        self.assertIn('id="deadman"', TEMPLATE)
        self.assertIn('id="event-list"', TEMPLATE)
        self.assertIn("/api/camera/profile", SCRIPT)
        self.assertIn("/api/snapshots/${source}", SCRIPT)
        self.assertIn("navigator.getGamepads", SCRIPT)
        self.assertIn("lastGamepadSignature", SCRIPT)
        self.assertIn("lastGamepadSentAt", SCRIPT)
        self.assertIn("now - lastGamepadSentAt >= 80", SCRIPT)

    def test_tab_switching_is_keyboard_accessible_and_stops_motion(self):
        self.assertIn('function selectRobotTab', SCRIPT)
        self.assertIn("if (changingTabs) killAll();", SCRIPT)
        self.assertIn("event.key === 'ArrowRight'", SCRIPT)
        self.assertIn("event.key === 'Home'", SCRIPT)

    def test_3tsahur_gimbal_and_ramp_controls_are_isolated_from_drive(self):
        self.assertIn('id="gimbal-mode"', TEMPLATE)
        self.assertIn('id="ramp-toggle"', TEMPLATE)
        self.assertIn('data-gimbal="pan-left"', TEMPLATE)
        self.assertIn("key === 'g'", SCRIPT)
        self.assertIn("key === 'r'", SCRIPT)
        self.assertIn("/api/actuators/gimbal", SCRIPT)
        self.assertIn("/api/actuators/ramp", SCRIPT)
        self.assertIn("Planning only · no servo output", SCRIPT)
        self.assertIn(".actuator-card", STYLES)

    def test_video_and_controls_use_separate_grid_columns(self):
        self.assertIn('grid-template-columns: minmax(0, 1.55fr) minmax(340px, .9fr);', STYLES)
        self.assertNotIn('.drive-card { position: absolute', STYLES)
        self.assertNotIn('.scout-controls { position: absolute', STYLES)


if __name__ == "__main__":
    unittest.main()
