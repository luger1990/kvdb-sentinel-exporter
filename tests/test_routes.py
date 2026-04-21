import tempfile
import unittest
import importlib.util
from pathlib import Path

from app import create_app
from app.config import Config


class RoutesTest(unittest.TestCase):
    def tearDown(self):
        Config._config = None
        Config._config_path = None

    def test_unknown_sentinel_returns_404(self):
        if importlib.util.find_spec("flask") is None:
            self.skipTest("missing dependency: flask")

        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / "config.yaml"
            config_file.write_text("sentinels: {}\n", encoding="utf-8")
            Config.load_config(str(config_file), force_reload=True)

            app = create_app({"TESTING": True})
            client = app.test_client()

            response = client.get("/missing/metrics")

        self.assertEqual(response.status_code, 404)
        self.assertIn("Sentinel", response.get_json()["error"])


if __name__ == "__main__":
    unittest.main()
