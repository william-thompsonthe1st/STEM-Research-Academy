import pathlib
import unittest


ROOT = pathlib.Path(__file__).parents[1]
HOTSPOT = (ROOT / "installer" / "hotspot.sh").read_text(encoding="utf-8")
BOOTSTRAP = (ROOT / "installer" / "curl-install.sh").read_text(encoding="utf-8")
INSTALLER = (ROOT / "installer" / "install.sh").read_text(encoding="utf-8")
CAMERA = (ROOT / "firmware" / "larp-esp32-cam" / "larp-esp32-cam.ino").read_text(encoding="utf-8")
SCOUT = (ROOT / "firmware" / "larp-scout" / "larp-scout.ino").read_text(encoding="utf-8")
LEGACY_SHARED_PASSWORD = "robo" + "swarm1"


class HotspotProtocolTests(unittest.TestCase):
    def test_hotspot_is_2_4_ghz_wpa2_personal(self):
        self.assertIn("802-11-wireless.band bg", HOTSPOT)
        self.assertIn("802-11-wireless.channel", HOTSPOT)
        self.assertIn("802-11-wireless-security.key-mgmt wpa-psk", HOTSPOT)
        self.assertIn("802-11-wireless-security.proto rsn", HOTSPOT)
        self.assertNotIn("802-11-wireless-security.key-mgmt sae", HOTSPOT)

    def test_bootstrap_and_installer_use_the_larp_deployment_branch(self):
        branch = 'REPO_BRANCH="${STEM_REPO_BRANCH:-agent/integrate-3tsahur-larp}"'
        self.assertIn(branch, BOOTSTRAP)
        self.assertIn(branch, INSTALLER)

    def test_camera_reconnect_reuses_its_existing_http_server(self):
        self.assertIn("WiFi.mode(WIFI_STA)", CAMERA)
        self.assertIn("WiFi.setAutoReconnect(true)", CAMERA)
        self.assertIn("WiFi.setSleep(false)", CAMERA)
        self.assertIn("if (server != nullptr) return true;", CAMERA)
        self.assertIn("WIFI_RETRY_A_MS = 2000", CAMERA)
        self.assertIn("WIFI_RETRY_B_MS = 2400", CAMERA)

    def test_firmware_does_not_contain_a_shared_hotspot_password(self):
        self.assertIn('WIFI_PASSWORD[] = "REPLACE_WITH_PI_PASSWORD"', CAMERA)
        self.assertIn('WIFI_PASSWORD[] = "REPLACE_WITH_PI_PASSWORD"', SCOUT)
        self.assertNotIn(LEGACY_SHARED_PASSWORD, CAMERA)
        self.assertNotIn(LEGACY_SHARED_PASSWORD, SCOUT)


if __name__ == "__main__":
    unittest.main()
