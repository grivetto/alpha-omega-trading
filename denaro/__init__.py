"""Denaro — package principale.

Componenti attive (runtime attuale, un processo per nodo):
- `denaro_node.py`      — il Node: event loop asyncio che ospita N bot
- `domain/`             — dominio puro, zero I/O (types, indicators, risk,
                          grid, momentum, meanrev, regime, policy)
- `application/`        — orchestrazione (orchestrator, portfolio, supervisor,
                          safemode, config)
- `infrastructure/`     — adattatori exchange (okx, kraken, paper), market
                          data, rate limiter, storage, feeder
- `backtest/`           — harness di validazione a parita' live
- `scripts/`, `tests/`  — operativita' read-only e test di parita'/invarianti

DEPRECATI — motori storici pre-Node, non usati dal runtime attuale:
- `engine_solo_v33.py`  — motore flat del cutover di agosto 2026
- `engine_paper.py`     — simulatore della prima fase paper
- `health_server_v33.py` / `health_server_mc2.py` — telemetria di quei motori

Non aggiungere nuova logica ai moduli deprecati: il percorso vivo e'
`denaro_node.py` + `application/orchestrator.py`.
"""
