import unittest
from unittest.mock import patch

from robot_server.camera import CameraStream


class CameraDiscoveryTests(unittest.TestCase):
    def test_logitech_model_name_is_derived_from_the_persistent_device_path(self):
        self.assertEqual(
            CameraStream._camera_name("/dev/v4l/by-id/usb-046d_Logitech_HD_Pro_Webcam_C930e-video-index0"),
            "Logitech HD Pro Webcam C930e",
        )

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

    def test_capture_supervisor_retries_after_disconnect(self):
        stream = CameraStream()
        stream._running = True
        calls = 0

        def capture_once(_generation):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise RuntimeError("USB camera disconnected")
            stream._running = False

        with patch.object(stream, "_capture_once", side_effect=capture_once), patch.object(
            stream._condition, "wait", return_value=True
        ):
            stream._capture()

        self.assertEqual(calls, 2)
        self.assertEqual(stream.restart_count, 1)
        self.assertIn("disconnected", stream.error)

    def test_profile_change_restarts_an_active_capture_worker(self):
        stream = CameraStream()
        stream._running = True
        with patch.object(stream, "close"), patch.object(stream, "start") as start:
            stream.configure(320, 240, 6)
        self.assertEqual((stream.width, stream.height, stream.fps), (320, 240, 6))
        start.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
