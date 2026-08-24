#!/usr/bin/env python3
"""Test config YAML+Pydantic con interpolazione ${VAR}."""
import tempfile
import unittest
from pathlib import Path

from denaro.application.config import HubConfig, NodeConfig, load_node_config


CONFIG_YAML = """
data_dir: node_data_live
hub:
  ws_enabled: true
  poll_interval: 5
supervisor:
  ram_critical_pct: 0.85
safemode:
  emergency_pct: 96.0
bots:
  - symbol: ADA/EUR
    mode: okx
    capital: 20.0
    buy_distance: 0.001
    profit_target: 0.02
    api_key: ${OKX_API_KEY}
    api_secret: ${OKX_API_SECRET}
    passphrase: ${OKX_PASSPHRASE}
  - symbol: SOL/EUR
    mode: kraken
    capital: 25.0
    api_key: ${KRAKEN_API_KEY}
    api_secret: ${KRAKEN_API_SECRET}
"""


class TestConfig(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "node.yaml"
        self.path.write_text(CONFIG_YAML, encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def test_load_e_default(self):
        env = {"OKX_API_KEY": "k1", "OKX_API_SECRET": "s1", "OKX_PASSPHRASE": "p1",
               "KRAKEN_API_KEY": "k2", "KRAKEN_API_SECRET": "s2"}
        cfg = load_node_config(self.path, env=env)
        self.assertIsInstance(cfg, NodeConfig)
        self.assertEqual(cfg.data_dir, "node_data_live")
        self.assertTrue(cfg.hub.ws_enabled)
        self.assertEqual(cfg.hub.poll_interval, 5.0)
        self.assertEqual(cfg.safemode.emergency_pct, 96.0)
        self.assertEqual(len(cfg.bots), 2)
        self.assertEqual(cfg.bots[0].mode, "okx")

    def test_interpolazione_secret(self):
        env = {"OKX_API_KEY": "chiave-okx", "OKX_API_SECRET": "segreta",
               "OKX_PASSPHRASE": "frase", "KRAKEN_API_KEY": "kk", "KRAKEN_API_SECRET": "ks"}
        cfg = load_node_config(self.path, env=env)
        self.assertEqual(cfg.bots[0].api_key, "chiave-okx")
        self.assertEqual(cfg.bots[0].api_secret, "segreta")
        self.assertEqual(cfg.bots[0].passphrase, "frase")
        self.assertEqual(cfg.bots[1].api_key, "kk")

    def test_placeholder_se_manca_env(self):
        cfg = load_node_config(self.path, env={})
        # la var mancante lascia il placeholder (nessun crash)
        self.assertEqual(cfg.bots[0].api_key, "${OKX_API_KEY}")

    def test_json_retrocompatibile(self):
        p = Path(self._tmp.name) / "node.json"
        p.write_text('{"data_dir": "x", "bots": [{"symbol": "A/EUR", "capital": 10}]}',
                     encoding="utf-8")
        cfg = load_node_config(p)
        self.assertEqual(cfg.bots[0].symbol, "A/EUR")
        self.assertEqual(cfg.bots[0].capital, 10.0)

    def test_default_hub(self):
        p = Path(self._tmp.name) / "min.yaml"
        p.write_text('{"bots": []}', encoding="utf-8")
        cfg = load_node_config(p)
        self.assertFalse(cfg.hub.ws_enabled)
        self.assertEqual(cfg.hub.poll_interval, 10.0)

    def test_to_dict(self):
        cfg = NodeConfig(bots=[{"symbol": "A/EUR", "capital": 10.0}])
        d = cfg.to_dict()
        self.assertEqual(d["data_dir"], "node_data")
        self.assertIn("bots", d)


if __name__ == "__main__":
    unittest.main()
