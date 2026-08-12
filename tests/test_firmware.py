import pathlib
import unittest


FIRMWARE = pathlib.Path(__file__).parents[1] / "firmware" / "larp-scout" / "larp_scout_controller.ino"
CAMERA_FIRMWARE = pathlib.Path(__file__).parents[1] / "firmware" / "larp-esp32-cam" / "larp_esp32_cam.ino"
INSTALLER = pathlib.Path(__file__).parents[1] / "installer" / "install.sh"


class LarpFirmwareTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = FIRMWARE.read_text(encoding="utf-8")
        cls.camera_source = CAMERA_FIRMWARE.read_text(encoding="utf-8")
        cls.installer = INSTALLER.read_text(encoding="utf-8")

    def test_attachment_was_consolidated_to_one_sketch(self):
        self.assertEqual(self.source.count("void setup()"), 1)
        self.assertEqual(self.source.count("void loop()"), 1)

    def test_final_hotspot_credentials_match_installer(self):
        self.assertIn('WIFI_SSID[] = "3TSahur-Swarm"', self.source)
        self.assertIn('WIFI_PASSWORD[] = "roboswarm1"', self.source)
        self.assertIn("HOTSPOT_SSID=3TSahur-Swarm", self.installer)
        self.assertIn("HOTSPOT_PASSWORD=roboswarm1", self.installer)

    def test_echo_differential_drive_api_and_safety_are_present(self):
        self.assertIn("TankDrive drivetrain", self.source)
        self.assertNotIn("TankDriveTrain", self.source)
        self.assertNotIn("motors.reverse(", self.source)
        self.assertIn("LEFT_MOTOR_ID = 1", self.source)
        self.assertIn("RIGHT_MOTOR_ID = 6", self.source)
        self.assertIn("COMMAND_TIMEOUT_MS = 500", self.source)
        self.assertIn("drivetrain.setBrake()", self.source)
        self.assertIn("drivetrain.drive(0, 0)", self.source)

    def test_pi_integration_endpoints_and_station_mode_are_present(self):
        self.assertIn("WiFi.mode(WIFI_STA)", self.source)
        self.assertIn("PI_HEARTBEAT_UDP_PORT = 5006", self.source)
        self.assertIn("sendHeartbeat()", self.source)
        self.assertIn("registerWithPi()", self.source)
        self.assertIn('"/api/scouts/register?id="', self.source)
        self.assertIn("xTaskCreate(piRegistrationTask", self.source)
        self.assertIn("CSI_REPORT_INTERVAL_MS = 250", self.source)
        for endpoint in ("/drive", "/stop", "/status", "/motion"):
            self.assertIn(f'"{endpoint}"', self.source)
        self.assertNotIn("192, 168, 4", self.source)

    def test_csi_presence_signal_is_available_to_the_dashboard(self):
        self.assertIn("csiMotionDetected", self.source)
        self.assertIn("csiMotionLevel", self.source)
        self.assertIn('"\\\"motion\\\":"', self.source)
        self.assertIn('"\\\"motion_level\\\":"', self.source)
        self.assertIn("CSI_VARIANCE_THRESHOLD", self.source)

    def test_larp_devices_retry_the_pi_hotspot_without_blocking_startup(self):
        self.assertIn("void beginWiFi()", self.source)
        self.assertIn("void maintainWiFi()", self.source)
        self.assertIn("WiFi.disconnect(false, false)", self.source)
        self.assertIn("if (serverStarted) server.handleClient()", self.source)
        self.assertNotIn("while (WiFi.status() != WL_CONNECTED)", self.source)
        self.assertIn("void beginWiFi()", self.camera_source)
        self.assertIn("void maintainWiFi()", self.camera_source)
        self.assertIn("WiFi.disconnect(false, false)", self.camera_source)
        self.assertNotIn("while (WiFi.status() != WL_CONNECTED)", self.camera_source)

    def test_larp_camera_firmware_exposes_a_mjpeg_stream(self):
        self.assertIn("CAMERA_ID", self.camera_source)
        self.assertIn('"3TSahur-Swarm"', self.camera_source)
        self.assertIn("esp_camera_init", self.camera_source)
        self.assertIn('"/stream"', self.camera_source)
        self.assertIn("larp-a-cam", self.camera_source)
        self.assertIn("STREAM_FRAME_INTERVAL_MS = 100", self.camera_source)
        self.assertIn("vTaskDelay(pdMS_TO_TICKS", self.camera_source)

    def test_installer_schedules_reboot_outside_pipe_process(self):
        self.assertIn("systemd-run", self.installer)
        self.assertIn("--on-active=10s", self.installer)
        self.assertIn("systemctl)\" reboot", self.installer)
        self.assertNotIn("STEM_NO_REBOOT", self.installer)

    def test_installer_avoids_git_index_pack_for_normal_github_updates(self):
        self.assertIn("https://api.github.com/repos/", self.installer)
        self.assertIn("https://raw.githubusercontent.com/", self.installer)
        self.assertIn("sparse-checkout set", self.installer)
        self.assertIn("--filter=blob:none --no-checkout", self.installer)
        self.assertIn("core.compression=0", self.installer)

    def test_installer_reclaims_its_own_stale_copies(self):
        self.assertIn("prune_old_installations", self.installer)
        self.assertIn('sudo apt-get clean', self.installer)
        self.assertIn('"$APP_NAME".installing.*', self.installer)
        self.assertIn("At least 128 MB of free space", self.installer)

    def test_installer_builds_offline_before_atomic_swap(self):
        build = self.installer.index("python3 -m venv --without-pip --system-site-packages")
        imports = self.installer.index("Flask and OpenCV imports passed")
        stop = self.installer.index("systemctl stop stem-robot-dashboard.service", imports)
        swap = self.installer.index('mv "$STAGED_APP_DIR" "$APP_DIR"')
        self.assertLess(build, imports)
        self.assertLess(imports, stop)
        self.assertLess(stop, swap)
        self.assertNotIn("pip install --upgrade", self.installer)
        self.assertIn("Restoring the previous working application", self.installer)
        self.assertIn("http://127.0.0.1:8080/healthz", self.installer)

    def test_installer_uses_resizable_window_and_simple_dashboard_address(self):
        self.assertIn('nginx-light', self.installer)
        self.assertIn('listen 80 default_server', self.installer)
        self.assertIn('CAMERA_FPS=10', self.installer)
        self.assertIn('DRIVE_WATCHDOG_SECONDS=0.20', self.installer)
        self.assertNotIn('fullscreen robot dashboard', self.installer)


if __name__ == "__main__":
    unittest.main()
