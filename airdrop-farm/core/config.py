import yaml
import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


@dataclass
class BudgetConfig:
    virtual_capital: float = 250.0
    real_capital: float = 100.0
    max_wallets: int = 20


@dataclass
class ExchangeConfig:
    api_key: str = ""
    api_secret: str = ""
    testnet: bool = False


@dataclass
class GasConfig:
    ethereum: int = 0
    base: int = 0
    scroll: int = 0
    abstract: int = 0
    linea: int = 0
    monad: int = 0
    hyperliquid: int = 0


@dataclass
class ProtocolConfig:
    airdrop: Dict[str, List[str]] = field(default_factory=dict)
    hyperliquid: Dict = field(default_factory=dict)
    yield_protocols: Dict[str, List[str]] = field(default_factory=dict)
    mexc_launchpad: Dict = field(default_factory=dict)


@dataclass
class TimingConfig:
    min_hours: int = 6
    max_hours: int = 48
    jitter_pct: float = 0.2


@dataclass
class CircuitBreakerConfig:
    max_daily_loss_pct: float = 5.0
    max_consecutive_failures: int = 10
    cooldown_hours: int = 24


@dataclass
class TelegramConfig:
    bot_token: str = ""
    chat_id: str = ""
    enabled: bool = True


@dataclass
class ZabbixConfig:
    enabled: bool = True
    url: str = "http://localhost:1080/api_jsonrpc.php"
    host: str = "airdrop-farm"
    push_interval_minutes: int = 60


@dataclass
class Config:
    budget: BudgetConfig = field(default_factory=BudgetConfig)
    exchanges: Dict[str, ExchangeConfig] = field(default_factory=dict)
    rpc: Dict[str, str] = field(default_factory=dict)
    gas: GasConfig = field(default_factory=GasConfig)
    protocols: ProtocolConfig = field(default_factory=ProtocolConfig)
    timing: TimingConfig = field(default_factory=TimingConfig)
    circuit_breaker: CircuitBreakerConfig = field(default_factory=CircuitBreakerConfig)
    telegram: TelegramConfig = field(default_factory=TelegramConfig)
    dry_run: bool = True
    zabbix: ZabbixConfig = field(default_factory=ZabbixConfig)


def load_config(config_path: str = "config.yaml") -> Config:
    """Load configuration from YAML file."""
    path = Path(config_path)
    if not path.exists():
        # Try parent directory
        path = Path(__file__).parent.parent / config_path
    
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    
    with open(path, "r") as f:
        data = yaml.safe_load(f)
    
    if not data:
        return Config()
    
    cfg = Config()
    
    # Budget
    if "budget" in data:
        b = data["budget"]
        cfg.budget = BudgetConfig(
            virtual_capital=b.get("virtual_capital", 250.0),
            real_capital=b.get("real_capital", 100.0),
            max_wallets=b.get("max_wallets", 20)
        )
    
    # Exchanges
    if "exchanges" in data:
        for name, ex in data["exchanges"].items():
            cfg.exchanges[name] = ExchangeConfig(
                api_key=ex.get("api_key", ""),
                api_secret=ex.get("api_secret", ""),
                testnet=ex.get("testnet", False)
            )
    
    # RPC
    if "rpc" in data:
        cfg.rpc = data["rpc"]
    
    # Gas
    if "gas" in data:
        g = data["gas"]
        cfg.gas = GasConfig(
            ethereum=g.get("ethereum", 0),
            base=g.get("base", 0),
            scroll=g.get("scroll", 0),
            abstract=g.get("abstract", 0),
            linea=g.get("linea", 0),
            monad=g.get("monad", 0),
            hyperliquid=g.get("hyperliquid", 0)
        )
    
    # Protocols
    if "protocols" in data:
        p = data["protocols"]
        cfg.protocols.airdrop = p.get("airdrop", {})
        cfg.protocols.hyperliquid = p.get("hyperliquid", {})
        cfg.protocols.yield_protocols = p.get("yield", {})
        cfg.protocols.mexc_launchpad = p.get("mexc_launchpad", {})
    
    # Timing
    if "timing" in data:
        t = data["timing"]
        cfg.timing = TimingConfig(
            min_hours=t.get("min_hours", 6),
            max_hours=t.get("max_hours", 48),
            jitter_pct=t.get("jitter_pct", 0.2)
        )
    
    # Circuit breaker
    if "circuit_breaker" in data:
        cb = data["circuit_breaker"]
        cfg.circuit_breaker = CircuitBreakerConfig(
            max_daily_loss_pct=cb.get("max_daily_loss_pct", 5.0),
            max_consecutive_failures=cb.get("max_consecutive_failures", 10),
            cooldown_hours=cb.get("cooldown_hours", 24)
        )
    
    # Telegram
    if "telegram" in data:
        tg = data["telegram"]
        cfg.telegram = TelegramConfig(
            bot_token=tg.get("bot_token", ""),
            chat_id=tg.get("chat_id", ""),
            enabled=tg.get("enabled", True)
        )
    
    # Dry run
    cfg.dry_run = data.get("dry_run", True)
    
    # Zabbix
    if "zabbix" in data:
        z = data["zabbix"]
        cfg.zabbix = ZabbixConfig(
            enabled=z.get("enabled", True),
            url=z.get("url", "http://localhost:1080/api_jsonrpc.php"),
            host=z.get("host", "airdrop-farm"),
            push_interval_minutes=z.get("push_interval_minutes", 60)
        )
    
    return cfg


# Singleton
_config: Optional[Config] = None

def get_config(config_path: str = "config.yaml") -> Config:
    global _config
    if _config is None:
        _config = load_config(config_path)
    return _config


if __name__ == "__main__":
    cfg = get_config()
    print(f"Budget: €{cfg.budget.virtual_capital} virtual, €{cfg.budget.real_capital} real")
    print(f"Max wallets: {cfg.budget.max_wallets}")
    print(f"Dry run: {cfg.dry_run}")
    print(f"Chains: {list(cfg.rpc.keys())}")
    print(f"Airdrop chains: {list(cfg.protocols.airdrop.keys())}")