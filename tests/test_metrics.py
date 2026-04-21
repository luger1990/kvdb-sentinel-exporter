import unittest

try:
    from app.metrics import RedisMetricsCollector
except ModuleNotFoundError as exc:
    RedisMetricsCollector = None
    IMPORT_ERROR = exc
else:
    IMPORT_ERROR = None


class MetricsTest(unittest.TestCase):
    def test_metrics_include_scrape_status_up_zero_and_build_info(self):
        if RedisMetricsCollector is None:
            self.skipTest(f"missing dependency: {IMPORT_ERROR}")

        collector = RedisMetricsCollector()
        collector.collect_scrape_metrics(
            "prod",
            success=False,
            duration=1.25,
            sentinel_status=[{"host": "127.0.0.1", "port": 26379, "up": 1}],
        )
        collector.collect_metrics(
            {
                "127.0.0.1:6379": {
                    "up": 1,
                    "master_name": "mymaster",
                    "node_role": "master",
                    "type": 1,
                    "redis_version": "7.2.4",
                    "used_memory": 100,
                    "used_memory_rss": 120,
                    "total_commands_processed": 42,
                },
                "127.0.0.2:6379": {
                    "up": 0,
                    "master_name": "mymaster",
                    "node_role": "slave",
                    "type": 1,
                    "error": "connection refused",
                },
            },
            "prod",
        )

        metrics_text = collector.get_metrics().decode()

        self.assertIn('kvdb_scrape_success{sentinel_name="prod"} 0.0', metrics_text)
        self.assertIn('kvdb_sentinel_up{sentinel_host="127.0.0.1",sentinel_name="prod",sentinel_port="26379"} 1.0', metrics_text)
        self.assertIn('kvdb_up{db_instance="127.0.0.2:6379",db_instance_ip="127.0.0.2",group_name="mymaster",role="slave",sentinel_name="prod"} 0.0', metrics_text)
        self.assertIn('kvdb_memory_used_bytes{db_instance="127.0.0.1:6379",db_instance_ip="127.0.0.1",group_name="mymaster",role="master",sentinel_name="prod"} 100.0', metrics_text)
        self.assertIn('kvdb_build_info{db_instance="127.0.0.1:6379",db_instance_ip="127.0.0.1",engine="redis",group_name="mymaster",role="master",sentinel_name="prod",version="7.2.4"} 1.0', metrics_text)
        self.assertIn("kvdb_commands_processed_total", metrics_text)


if __name__ == "__main__":
    unittest.main()
