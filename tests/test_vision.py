import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from robot_server.vision import VisionManager


class VisionEnvironmentTests(unittest.TestCase):
    def test_dashboard_loads_the_installed_optional_vision_environment(self):
        with tempfile.TemporaryDirectory() as temporary:
            site_packages = Path(temporary)
            package = site_packages / "ultralytics"
            package.mkdir()
            (package / "__init__.py").write_text(
                "class YOLO:\n    def __init__(self, model_path): self.model_path = model_path\n",
                encoding="utf-8",
            )
            previous_module = sys.modules.pop("ultralytics", None)
            try:
                with patch.dict("os.environ", {"VISION_SITE_PACKAGES": str(site_packages)}, clear=False):
                    manager = VisionManager({})
                    model = manager._load_model()
                self.assertEqual(model.model_path, "yolo11n_ncnn_model")
            finally:
                sys.path[:] = [path for path in sys.path if path != str(site_packages)]
                sys.modules.pop("ultralytics", None)
                if previous_module is not None:
                    sys.modules["ultralytics"] = previous_module

    def test_missing_configured_vision_environment_has_a_clear_error(self):
        with patch.dict("os.environ", {"VISION_SITE_PACKAGES": "/not/a/vision/environment"}, clear=False):
            manager = VisionManager({})
        with self.assertRaisesRegex(RuntimeError, "Configured YOLO environment is missing"):
            manager._load_model()


if __name__ == "__main__":
    unittest.main()
