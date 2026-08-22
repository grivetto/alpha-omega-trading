# ⚡ ALPHA-OMEGA TRADING — ATLAS

[![License: Unlicense](https://img.shields.io/badge/license-Unlicense-blue.svg)](http://unlicense.org/)
[![Python](https://img.shields.io/badge/python-3.12%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![CCXT](https://img.shields.io/badge/exchange-CCXT%20Pro%20%2F%20Kraken%20%7C%20OKX-5741D9?logo=bitcoin&logoColor=white)](https://github.com/ccxt/ccxt)
[![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20systemd-FCC624?logo=linux&logoColor=black)](https://www.freedesktop.org/wiki/Software/systemd/)
[![Status](https://img.shields.io/badge/status-LIVE-brightgreen)](https://github.com/grivetto/alpha-omega-trading)

> **ATLAS** es la evolución modular, asíncrona y multi-exchange del sistema legacy **Denaro**. Mismos exchanges, mismas credenciales, misma filosofía — reconstruidos con arquitectura limpia, patrones de resiliencia y gestión de riesgo integrada.

---

## 🏗️ Qué es ATLAS

ATLAS es un sistema de trading algorítmico distribuido escrito en Python 3.12 con `asyncio`. Reemplaza el código monolítico de Denaro con una arquitectura modular:

- **Multi-exchange**: Kraken y OKX Europe (EEA) vía CCXT async + CCXT Pro (WebSocket)
- **Multi-nodo**: una instancia por nodo de trading (`nuvola`, `MARCODG1`)
- **Estrategia de grilla**: órdenes limit buy/sell alrededor del precio medio
- **Resiliente**: timeout → reintento con backoff exponencial → clasificación de errores no reintentables
- **Con gestión de riesgo**: límites de drawdown, pérdida diaria, tamaño de posición, exposición, correlación + kill switch
- **Observable**: logging JSON, API HTTP de health/readiness

## 🧩 Arquitectura

```
atlas/
├── main.py                 # Punto de entrada: ciclo de vida + inyección de dependencias
├── core/
│   ├── config.py           # Pydantic settings + carga YAML con sustitución ${VAR}
│   ├── events.py           # EventBus (pub/sub asíncrono: ticks, fills, eventos de riesgo)
│   ├── lifecycle.py        # GracefulShutdown (manejo de SIGINT/SIGTERM)
│   └── resilience.py       # decorador exchange_call: timeout → retry → circuit breaker
├── connector/
│   ├── interface.py        # clase abstracta ExchangeConnector
│   ├── ccxt_adapter.py     # implementación CCXT async (REST + WebSocket)
│   └── models.py           # Ticker, OrderBook, Balance
├── strategy/
│   └── engine.py           # GridStrategy + StrategyEngine (loop de ticks, dedup de órdenes abiertas)
├── execution/
│   ├── router.py           # ExecutionRouter: pipeline de envío de órdenes
│   └── models.py           # OrderRequest, OrderResponse, CancelResponse
├── portfolio/
│   └── manager.py          # ExchangeRegistry + PortfolioManager (límites de riesgo, equity)
├── observability/
│   └── logging.py          # logging estructurado JSON
└── storage/                # persistencia de estado
```

### Pipeline de ejecución

```
Ticker → StrategyEngine (GridStrategy.on_tick)
       → ExecutionRouter.submit(OrderRequest)
       → CCXTAdapter.create_order (vía exchange_call: timeout→retry→classify)
       → Exchange (Kraken / OKX EEA)
```

El loop de estrategia está limitado (máximo 1 señal por símbolo cada 60s) y deduplicado contra las órdenes abiertas: el bot nunca acumula órdenes a ciegas.

## ⚙️ Configuración

Toda la configuración vive en `config/` como YAML, con sustitución `${VAR}` resuelta desde `.env`:

**`config/exchanges.yaml`** — credenciales y ajuste de los exchanges:

```yaml
exchanges:
  - name: kraken
    api_key: ${KRAKEN_API_KEY}
    api_secret: ${KRAKEN_API_SECRET}
    rate_limit_rps: 5.0
    rate_limit_burst: 10
  - name: okx
    api_key: ${OKX_API_KEY}
    api_secret: ${OKX_API_SECRET}
    passphrase: ${OKX_API_PASSPHRASE}
    extra:
      eea: true        # → fuerza el hostname eea.okx.com (OKX Europe)
```

> ⚠️ **OKX Europe (EEA)**: el flag `extra.eea: true` es obligatorio. Sin él, el bot apunta a `api.okx.com` y toda llamada autenticada falla con error 50119/50111.

**`config/strategies.yaml`** — parámetros de estrategia:

```yaml
strategies:
  - strategy_id: grid_btc_eur
    class_path: atlas.strategy.engine.GridStrategy
    enabled: true
    symbols: ["BTC/EUR"]
    exchanges: ["kraken"]
    params:
      grid_levels: 3          # número de niveles de grilla alrededor del precio medio
      spread_pct: 0.005       # distancia entre niveles (0.5%)
      per_level_pct: 0.10     # asignación de equity por nivel
      order_size: 0.00005     # tamaño explícito (anula per_level_pct)
      min_notional: 5.0       # valor mínimo de la orden
```

**`.env`** — credenciales API (nunca commiteadas; ver `.gitignore`).

## 🛡️ Gestión de Riesgo

Límites por defecto (`atlas/core/config.py`), aplicados por `PortfolioManager`:

| Límite | Valor |
|--------|-------|
| Drawdown máximo del portafolio | 20% |
| Pérdida máxima diaria | 5% |
| Tamaño máximo de posición | 25% del equity |
| Exposición máxima por moneda base | 30% |
| Exposición máxima por correlación | 70% |
| Apalancamiento máximo | 1.0 (solo spot) |

Las violaciones emiten `RiskEvent` en el event bus y pueden activar el **kill switch**.

## 🔄 Compatibilidad con Denaro

ATLAS es la evolución directa de **Denaro**: conserva lo que funcionaba y corrige lo que no.

| Aspecto | Denaro (legacy) | ATLAS |
|---------|-----------------|-------|
| Código | Monolítico (`engine_solo.py`, `bot_v5.py`) | Paquete modular `atlas/` |
| Acceso a exchanges | Llamadas CCXT directas | CCXT async vía `CCXTAdapter` + capa de resiliencia |
| Estrategia | Grilla hardcodeada por bot | `GridStrategy` declarativa desde YAML |
| Riesgo | Disperso en checks ad-hoc | `PortfolioManager` central con límites estrictos |
| Observabilidad | Archivos de log | Logging JSON + API HTTP `/health` + `/ready` |
| Resiliencia | Ausente | timeout → retry → circuit breaker (`exchange_call`) |
| Configuración | Constantes en el código | YAML + `.env` con sustitución `${VAR}` |

**Coexistencia**: ambos sistemas corren en los mismos nodos y exchanges. Leen **secciones separadas** del mismo `.env` (claves Denaro vs claves ATLAS), usan unidades systemd separadas y nunca comparten estado de órdenes. Los parámetros de la grilla Denaro se mapean directamente a los parámetros de `GridStrategy` (`grid_levels`, `spread_pct`, `per_level_pct`).

**Camino de migración**: un bot de grilla Denaro se migra (1) escribiendo sus parámetros en `config/strategies.yaml`, (2) añadiendo su sección de claves API en `.env`, (3) arrancando `atlas-engine.service`.

## 🚀 Despliegue

```bash
# 1. Dependencias
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 2. Configuración
cp .env.example .env            # rellenar credenciales API
# editar config/exchanges.yaml + config/strategies.yaml

# 3. Ejecución (foreground)
.venv/bin/python -m atlas.main

# 4. Ejecución como servicio (producción)
sudo systemctl enable --now atlas-engine
sudo systemctl enable --now atlas-watchdog   # auto-healing
```

**`atlas-engine.service`** ejecuta el bot con `Restart=always`; **`atlas-watchdog.service`** reinicia el motor cuando deja de responder.

### Health API

```
GET /health   → {"status": "healthy", "service": "atlas-engine", "exchanges": [...], "strategies": [...]}
GET /ready    → {"ready": true|false, "service": "atlas-engine"}
```

El servidor de health se enlaza a `[::]:8080` (dual-stack IPv4/IPv6) para que los nodos detrás de CGNAT puedan monitorizarse remotamente.

## 📊 Despliegue actual

| Nodo | Exchange | Pares | Servicio |
|------|----------|-------|----------|
| `nuvola` | Kraken | BTC/EUR | atlas-engine + watchdog |
| `MARCODG1` | OKX (EEA) | ETH/EUR, SOL/EUR, XRP/EUR, DOGE/EUR | atlas-engine + watchdog |

## 🧠 Principios de diseño

1. **Code is law, profit is proof** — cada decisión de trading es determinista y auditable.
2. **Protección del capital primero** — los límites de riesgo se aplican en la ruta del código, no en una lista de buenos deseos.
3. **La distribución es resiliencia** — dos nodos independientes, sin punto único de fallo.
4. **No desperdiciar nada** — I/O asíncrono, sin frameworks más allá de los usados, un proceso por nodo.
5. **Nunca confiar credenciales en el código** — los secretos viven solo en `.env` (gitignored).

## 📄 Licencia

[The Unlicense](http://unlicense.org/) — dominio público. Úsalo, estúdialo, rómpelo, mejóralo.
