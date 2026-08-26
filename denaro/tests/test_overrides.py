"""Test: (1) lo schema Pydantic conserva i campi sell_* (bug storico: i sell
ladder della griglia bilaterale non venivano MAI piazzati perché i campi
mancavano dallo schema e Pydantic li scartava in silenzio);
(2) il meccanismo di override strategici (strategy_overrides.json);
(3) overrides_file per-istanza (bug F1: l'istanza trend leggeva il file del
main e i bot momentum venivano convertiti in grid)."""
import json
import tempfile
from pathlib import Path

import yaml

from denaro.application.config import load_node_config

REPO = Path(__file__).resolve().parents[2]
NODE_YAML = REPO / "config" / "node.yaml"


def _bots() -> list[dict]:
    return load_node_config(NODE_YAML).to_dict()["bots"]


def test_node_config_preserves_overrides_file():
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
        yaml.safe_dump({"data_dir": "node_data",
                        "overrides_file": "config/overrides_trend.json",
                        "bots": []}, f)
        p = Path(f.name)
    try:
        cfg = load_node_config(p)
        assert cfg.to_dict()["overrides_file"] == "config/overrides_trend.json"
    finally:
        p.unlink(missing_ok=True)


def test_schema_preserves_sell_fields_okx_sol():
    bots = _bots()
    sol = [b for b in bots if b["symbol"] == "SOL/EUR" and b["mode"] == "okx"]
    assert sol, "bot okx SOL/EUR atteso nel node.yaml"
    assert sol[0]["sell_levels"] == 2, f"sell_levels scartato: {sol[0]}"
    assert sol[0]["sell_distance"] == 0.01
    assert sol[0]["sell_step"] == 0.008


def test_schema_preserves_sell_fields_kraken():
    bots = _bots()
    kraken = [b for b in bots if b["mode"] == "kraken" and b.get("enabled")]
    assert kraken and kraken[0]["sell_levels"] == 4, \
        f"kraken sell_levels scartato: {kraken}"


def test_schema_preserves_strategy_and_stop_loss():
    bots = _bots()
    doge = [b for b in bots if b["symbol"] == "DOGE/EUR" and b["mode"] == "okx"]
    assert doge and doge[0]["stop_loss_pct"] == 0.15
    paper_doge = [b for b in bots if b["symbol"] == "DOGE/EUR" and b["mode"] == "paper"]
    assert paper_doge and paper_doge[0]["strategy"] == "adaptive"


def test_apply_overrides(tmp_path):
    from denaro.denaro_node import NodeApp
    app = NodeApp.__new__(NodeApp)
    ov = {"paper:SOL/EUR": {"sell_levels": 3, "buy_distance": 0.02,
                            "evil_key": 999}}
    p = tmp_path / "strategy_overrides.json"
    p.write_text(json.dumps(ov), encoding="utf-8")
    app.overrides_path = p
    bot = {"mode": "paper", "symbol": "SOL/EUR", "levels": 3,
           "buy_distance": 0.01}
    out = app._apply_overrides(bot)
    assert out["sell_levels"] == 3
    assert out["buy_distance"] == 0.02
    assert "evil_key" not in out  # whitelist


def test_apply_overrides_by_symbol_only(tmp_path):
    from denaro.denaro_node import NodeApp
    app = NodeApp.__new__(NodeApp)
    ov = {"SOL/EUR": {"levels": 5}}
    p = tmp_path / "strategy_overrides.json"
    p.write_text(json.dumps(ov), encoding="utf-8")
    app.overrides_path = p
    bot = {"mode": "paper", "symbol": "SOL/EUR", "levels": 3}
    assert app._apply_overrides(bot)["levels"] == 5


def test_corrupt_overrides_no_crash(tmp_path):
    from denaro.denaro_node import NodeApp
    app = NodeApp.__new__(NodeApp)
    p = tmp_path / "strategy_overrides.json"
    p.write_text("{corrotto!!!", encoding="utf-8")
    app.overrides_path = p
    bot = {"mode": "paper", "symbol": "SOL/EUR", "levels": 3}
    assert app._apply_overrides(bot) == bot  # fallback silenzioso


def test_missing_overrides_file_no_crash(tmp_path):
    from denaro.denaro_node import NodeApp
    app = NodeApp.__new__(NodeApp)
    app.overrides_path = tmp_path / "inesistente.json"
    bot = {"mode": "paper", "symbol": "SOL/EUR", "levels": 3}
    assert app._apply_overrides(bot) == bot
