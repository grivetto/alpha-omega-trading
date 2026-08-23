<div align="center">

# ⚡ ALPHA-OMEGA TRADING ⚡

### *El sistema de trading algorítmico distribuido definitivo — del papel a las ganancias, a través de dos nodos, sin compromisos.*

[![License: Unlicense](https://img.shields.io/badge/license-Unlicense-blue.svg)](http://unlicense.org/)
[![Python](https://img.shields.io/badge/python-3.12%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![CCXT](https://img.shields.io/badge/exchange-CCXT%20Pro%20%2F%20Kraken%20%7C%20OKX-5741D9?logo=bitcoin&logoColor=white)](https://github.com/ccxt/ccxt)
[![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20systemd%20%7C%20Docker-FCC624?logo=linux&logoColor=black)](https://www.freedesktop.org/wiki/Software/systemd/)
[![Status](https://img.shields.io/badge/status-LIVE%20%E2%82%AC50%20CAPITAL%20%7C%2012%20BOTS%20OPERATIONAL-brightgreen)](https://github.com/grivetto/alpha-omega-trading)
[![Architecture](https://img.shields.io/badge/architecture-distributed%2C%20async%2C%20fleet%20orchestrated-brightgreen)]()
[![Monitoring](https://img.shields.io/badge/monitoring-Zabbix%20%2B%20Grafana%20%2B%20Telegram-FF6F00?logo=grafana&logoColor=white)]()

**Sistema de trading distribuido, asíncrono y multiestrategia orquestado a través de dos máquinas. Datos de mercado en tiempo real vía ZeroMQ, estado compartido vía Redis Streams, gestión de riesgo de portafolio, selección dinámica de pares — todo validado en papel, ahora EN VIVO.**

</div>

---

## 🚀 GO-LIVE: 2026-08-10 22:42:30 CEST — €50 CAPITAL REAL DESPLEGADO (Arquitectura v2.3 Split-by-Exchange)

> **GO-LIVE CONFIRMADO** — El sistema está operativo con capital real. Arquitectura split-by-exchange: sin conflictos de cuenta.

| Exchange | Cuenta | Capital | Nodo | Bots | Pares |
|----------|--------|---------|------|------|-------|
| **Kraken** | Compartida | €25.50 EUR | Nuvola | 6 | ADA, DOGE, ETH, LINK, SOL, XRP |
| **OKX (EEA)** | Compartida | €25.00 EUR | MARCODG1 | 6 | ADA, BICO, DOGE, GRVT, LINK, XRP |
| **TOTAL** | — | **€50** | 2 | **12** | 12 pares únicos |

**Límites de Riesgo Activados (por exchange):**
- Max DD por bot: 15% (€1.04)
- Límite de pérdida diaria: 5% (€1.25)
- Kill switch de portafolio: 20% (€5)
- Filtro de correlación: 0.7
- Máximo 2 posiciones por moneda base

**Monitoreo:**
- ✅ Zabbix en mc2 (monitoreo cada minuto)
- ✅ Health API :8900 por nodo

---

## 🎯 Filosofía

> **La protección del capital es la ley. La eficiencia es ganancia. El código es la ley. La ganancia es la prueba. La distribución es resiliencia.**

Alpha-Omega Trading nació de una restricción simple: **el capital limitado no debe ser especulado — debe ser cultivado a través de una infraestructura distribuida y resiliente.**

Cada decisión de diseño sigue cuatro reglas:

1. **🛡️ Nunca arriesgar lo que no puedes permitirte perder** — circuit breakers, límites de drawdown, caps de posición y límites de correlación no son características opcionales; son la base en cada capa (bot, portafolio, flota).
2. **⚙️ No desperdiciar nada** — sin frameworks hinchados, sin procesos redundantes, sin servicios abandonados consumiendo RAM. I/O asíncrono, buffers circulares, arrays tipados, GC explícito. Un proceso, un propósito, huella mínima.
3. **📈 Ventaja asimétrica** — órdenes de grid pequeñas y pacientes cosechando volatilidad. Muchas victorias pequeñas, pérdidas estrictamente acotadas. Múltiples estrategias para múltiples regímenes.
4. **🌐 La distribución es resiliencia** — sin punto único de fallo. Dos nodos de trading, coordinador central, estado compartido, failover automático. La flota sobrevive caídas de nodos, cortes de exchange, particiones de red.

Esto no es un bot para hacerse rico rápido. Es una **disciplina de ingeniería aplicada a los mercados**: empezar con €100, probar la estrategia en papel a través de una flota distribuida, y luego — y solo entonces — escalar con confianza.

---

## 📜 Historia del Proyecto

| Milestone | Fecha / Commit | Descripción |
|-----------|---------------|-------------|
| **🌱 Live Bot (v0)** | pre-repo | Bot grid Kraken DOGE/EUR de un solo archivo. Funcionó en vivo en Raspberry Pi con ~€200 de capital durante meses. Persistencia systemd, recarga manual de estado. Probó el concepto; expuso los límites de un monolito. |
| **📉 El Colapso de Binance** | 2026-06-29 → 07-01 | **El proyecto empezó a perder ritmo — y euros.** La flota live de Denaro estaba completamente operativa en sub-cuentas de Binance… hasta que no lo estuvo. Binance revocó silenciosamente los permisos de trading en API keys de sub-cuentas EU. Bots hambrientos, posiciones varadas, ~€206 congelados en medio del grid. Causa: **Aplicación MiCA el 1 de julio de 2026**. Lección: **el riesgo de exchange es riesgo real**. |
| **🐙 El Pivote a Kraken** | 2026-07-01 | El mismo día: todo convertido a EUR en Binance (~€344 recuperados), retirado vía SEPA, infraestructura redirigida a **Kraken** — MiCA-compliant, licenciado en UE, API superior. Binance y Bybit deprecados permanentemente. |
| **🏗️ p1 — Scaffold Modular** | `504172c` | Refactor completo. Monolito dividido en 5 módulos limpios: `engine`, `exchange`, `strategy`, `state`, `risk`. Arquitectura inspirada en Freqtrade, Hummingbot, OctoBot, Jesse. |
| **🔄 p2 — Paper Runner** | `0b2e0f3` | `PaperEngine` loop principal: intervalo de tick configurable, grid wiring, persistencia de estado a JSON. Entry point `run_paper.py`. |
| **🩹 p2.1 — Fix Sandbox Kraken** | `054b957` | El cliente CCXT de Kraken no tiene atributo `sandbox`. El adaptador de exchange captura el error y hace fallback a API live readonly. |
| **🛡️ p2.2 — Guard + Graceful Shutdown** | `015627a` | Guard `getattr` contra `AttributeError`; manejador SIGINT/SIGTERM detiene engine, guarda portafolio, sale limpiamente. |
| **🧹 p3 — Limpieza de Infraestructura** | — | Eliminación de **todos** los servicios legacy Denaro, cron jobs, units systemd, timers, binarios y procesos huérfanos en ambos nodos. Un servicio sobrevive: `denaro-paper`. |
| **🧪 p4 — Test Suite Paper Trading** | actual | 33 tests unitarios + integración. Engine tick, risk gates, grid, trailing stop, fill/orderbook de paper exchange, runner de backtest. |
| **🌐 DDNS + Automatización Multi-Nodo** | 2026-07-30 | **No-IP DDNS desplegado en ambos nodos de trading** (`nuvola` → `sgrivett.ddns.net`, `MARCODG1` → `mgrivett.ddns.net`). Systemd timer (10 min) + archivo de credenciales seguro. |
| **🔑 Rotación & Validación de API Keys** | 2026-07-31 | **Key Kraken rotada** (post-MiCA). Nueva key validada: permisos de trading ✅. **Keys MEXC validadas en ambos nodos**. Bybit deprecado (MiCA), eliminado. |
| **💸 El Misterio de los 115 USDT** | 2026-07-22 | **115.74 USDT (ERC20) enviados a Kraken — nunca llegaron. No on-chain.** API de Kraken carece de permisos de funding. Ticket de soporte abierto con TxID, prueba de no-llegada. |
| **🤖 Airdrop Farm v1** | 2026-07-31 | **Airdrop farmer autónomo multiestrategia** desplegado en nuvola (systemd). 20 wallets, 4 estrategias, €250 virtual/€100 real. Scheduler Poisson, circuit breaker, idempotente. Zabbix en MC2. |
| **🔄 Reboot Completo & Verificación** | 2026-07-31 | Ambos nodos reiniciados para actualizaciones de kernel. Post-reboot: todos los servicios systemd saludables. |
| **⚡ ShadowGrid v2.0 & Fleet Multi-Bot** | 2026-08-07 | **Transformación completa en una flota adaptativa de 14 bots a través de 2 exchanges.** Spread adaptativo ATR, filtro de momentum ADX/RSI, circuit breaker DD 15%, límite de pérdida diaria 5%, re-anclaje dinámico 6%. Supervisor de flota, scanner de pares, rebalancer. 14 bots totales, €200 capital paper. |
| **🛡️ ShadowGrid v2.1 — Riesgo & Alertas** | 2026-08-08 | **Gestión de riesgo a nivel de portafolio + alertas multi-canal.** Risk Manager: matriz de correlación, límites de exposición, targeting de volatilidad, asignación de riesgo paritario, kill switch multi-capa. Alert System: canales Telegram/Email/Log con deduplicación. Selección dinámica de pares con detección de régimen, scoring de decaimiento de rendimiento, filtrado de correlación, auto-rotación semanal. |
| **🏗️ ShadowGrid v2.2 — Arquitectura Unificada** | 2026-08-09 | **Unificación de ShadowGrid v2 (features de producción) + neo (rendimiento async).** Nuevo paquete `alpha_omega` con UnifiedTradingEngine, DistributedFleetCoordinator, DistributedPairScanner, PortfolioRiskManager. ZeroMQ Pub/Sub para datos de mercado, Redis Streams para estado compartido, elección de líder Raft. 24 bots (12/nodo), €200 capital paper. Todos los issues de auditoría resueltos. |
| **🚀 GO-LIVE — Trading en Vivo con Capital Real** | **2026-08-10 22:42:30 CEST** | **€50 de capital real desplegados en 2 nodos.** Endpoint OKX EEA (`eea.okx.com`) validado. Keys live de Kraken validadas. 12 bots operativos (6/nodo). Gestión de riesgo armada. Arquitectura split-by-exchange: Nuvola=Kraken, MARCODG1=OKX. |
| **🏗️ v2.3 — Arquitectura Split-by-Exchange** | **2026-08-11** | **Fix crítico: eliminados conflictos de cuenta.** Nuvola tradea solo Kraken (6 bots), MARCODG1 solo OKX (6 bots). Cuentas compartidas por exchange, sin colisiones de órdenes. Zabbix monitoring desplegado en mc2. Capital total correcto: €50 (no €101). Endpoint OKX WebSocket arreglado (eea.okx.com). |
| **🔑 Validación & Testing de API Keys** | **2026-08-22** | **Testing completo de API keys en todos los nodos.** Keys Kraken en NUVOLA (2 pares funcionando, EUR=22.20), keys OKX en MARCODG1 (estables 2+ días). Arreglados problemas de base64 padding e IP whitelist. Todos los exchanges operativos. |
| **🤝 Compatibilidad Denaro-Atlas** | **2026-08-22** | **Capa de compatibilidad oficial entre Denaro (legacy estable) y Atlas (next-gen gestionado por Hermes).** Ambos sistemas coexisten en los mismos nodos con API keys separadas. Denaro ejecuta solo-engine (Kraken/OKX grid), Atlas vía Hermes AI. Sin conflictos con aislamiento de keys. Estado operativo completo en NUVOLA y MARCODG1. |

---

## 🤝 Compatibilidad Denaro-Atlas

Alpha-Omega Trading ahora soporta oficialmente la coexistencia de dos sistemas de trading en los mismos nodos:

| Sistema | Versión | Gestor | Exchange | Descripción |
|---------|---------|--------|----------|-------------|
| **Denaro** | v3.x (legacy) | Sistema operativo | Kraken, OKX | Motor SOLO estable, grid multi-nivel, systemd |
| **Atlas** | Next-gen | Hermes AI | Kraken, OKX | Arquitectura async moderna, DCA + Grid, auto-healing |

**Requisitos para coexistencia:**
- API keys **separadas** por sistema (no compartir keys entre Denaro y Atlas)
- Sub-cuentas OKX dedicadas o keys globales separadas
- Cada sistema gestiona su propio estado y posiciones

**Beneficios:**
- ✅ Denaro: Estabilidad probada, simple, confiable
- ✅ Atlas: Features avanzadas, gestión automática por IA
- ✅ Diversificación de estrategias en el mismo hardware

---

## 🏗️ Arquitectura

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      SISTEMA ALPHA-OMEGA TRADING                             │
└─────────────────────────────────────────────────────────────────────────────┘

           ┌──────────────┐         ┌──────────────┐         ┌──────────────┐
           │     mc2      │◄───────►│    nuvola    │◄───────►│  MARCODG1    │
           │  (Home/DB)   │  ZeroMQ │  (Primario)  │  ZeroMQ │ (Secundario) │
           └──────┬───────┘         └──────┬───────┘         └──────┬───────┘
                  │                        │                        │
                  │         ┌──────────────┴──────────────┐        │
                  │         │        Redis Cluster        │        │
                  │         │   (Estado Compartido)       │        │
                  │         └──────────────┬──────────────┘        │
                  │                        │                        │
                  ▼                        ▼                        ▼
         ┌───────────────┐         ┌───────────────┐         ┌───────────────┐
         │ TimescaleDB   │         │  Kraken EUR   │         │  OKX USDT     │
         │ Histórico     │         │  Denaro+Atlas │         │  Denaro+Atlas │
         └───────────────┘         └───────────────┘         └───────────────┘
```

---

## 🚀 Quick Start

```bash
# Clonar repositorio
git clone https://github.com/griveto/alpha-omega-trading.git
cd alpha-omega-trading

# Configurar entorno
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configurar .env
cp .env.example .env
# Editar .env con tus API keys

# Iniciar en modo paper
python -m alpha_omega.core.engine_solo --exchange kraken --symbol SOL/EUR --capital 15.0 --paper

# Desplegar con systemd
./scripts/deploy_alpha_omega.sh
```

---

**Desarrollado con ❤️ para el trading algorítmico distribuido.**
