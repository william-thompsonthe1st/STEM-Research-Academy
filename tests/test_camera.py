import unittest
from unittest.mock import patch

from robot_server.camera import CameraStream


class CameraDiscoveryTests(unittest.TestCase):
    @patch("robot_server.camera.os.path.realpath", side_effect=lambda path: {
        "/dev/v4l/by-id/usb-046d_Logitech_HD_Webcam_C270-video-index0": "/dev/video2",
    }.get(path, path))
    @patch("robot_server.camera.glob.glob")
    def test_logitech_capture_node_is_preferred_and_deduplicated(self, glob, _realpath):
        glob.side_effect = lambda pattern: (
            [
                "/dev/v4l/by-id/usb-other-video-index0",
                "/dev/v4l/by-id/usb-046d_Logitech_HD_Webcam_C270-video-index0",
            ]
            if "by-id" in pattern
            else ["/dev/video0", "/dev/video2"]
        )

        devices = CameraStream(device="auto")._candidate_devices()

        self.assertEqual(
            devices[0],
            "/dev/v4l/by-id/usb-046d_Logitech_HD_Webcam_C270-video-index0",
        )
        self.assertNotIn("/dev/video2", devices)
        self.assertIn("/dev/video0", devices)


if __name__ == "__main__":
    unittest.main()
