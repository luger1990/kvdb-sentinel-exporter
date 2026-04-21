import os
import tempfile
import unittest
from pathlib import Path

from app.config import Config, ConfigError


class ConfigTest(unittest.TestCase):
    def tearDown(self):
        Config._config = None
        Config._config_path = None
        os.environ.pop("REDIS_PASSWORD", None)

    def test_config_parses_hosts_and_env_password(self):
        os.environ["REDIS_PASSWORD"] = "secret"
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / "config.yaml"
            config_file.write_text(
                """
sentinels:
  prod:
    default_password: "${REDIS_PASSWORD}"
    sentinel_hosts:
      - "127.0.0.1:26379"
      - host: "127.0.0.2"
        port: 26380
metrics:
  thread_pool_size: 2
web_ui:
  refresh_interval: 10
""",
                encoding="utf-8",
            )

            Config.load_config(str(config_file), force_reload=True)

        sentinel_config = Config.get_sentinel_config("prod")
        self.assertEqual(sentinel_config["default_password"], "secret")
        self.assertEqual(
            sentinel_config["sentinel_hosts"],
            [
                {"host": "127.0.0.1", "port": 26379},
                {"host": "127.0.0.2", "port": 26380},
            ],
        )
        self.assertEqual(Config.get_metrics_config()["discovery_ttl"], 30)

    def test_config_rejects_invalid_port(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / "config.yaml"
            config_file.write_text(
                """
sentinels:
  prod:
    sentinel_hosts:
      - "127.0.0.1:not-a-port"
""",
                encoding="utf-8",
            )

            with self.assertRaises(ConfigError):
                Config.load_config(str(config_file), force_reload=True)


if __name__ == "__main__":
    unittest.main()
