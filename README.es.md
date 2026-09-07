# Alpha-Omega Trading

**_Nombre en clave "Denaro": un motor de trading en red (grid trading) unificado y distribuido para OKX y Kraken, con trading en papel realista, capital vivo por etapas y monitorización basada en Zabbix._

Alpha-Omega trading es un sistema en Python que ejecuta el mismo motor de trading en varias máquinas ("nodos"), cada una operando uno o más mercados en OKX o Kraken a través de la librería CCXT. Está diseñado para un despliegue disciplinado, probado con backtests y validado en papel, con un **presupuesto vivo pequeño y por etapas** — la cuenta viva se mantiene deliberadamente separada del desarrollo y es lo bastante pequeña como para que un drawdown completo sea asumible mientras el motor sigue en fase de validación.

> [English](README.md) · [Italiano](README.it.md) · [Español](README.es.md) · [ไทย](README.th.md)

---

## Tabla de contenidos

- [Estado honesto](#estado-honesto)
- [Qué hace](#qué-hace)
- [Arquitectura](#arquitectura)
- [Controles de seguridad y riesgo](#controles-de-seguridad-y-riesgo)
- [Monitorización y alertas](#monitorización-y-alertas)
- [Primeros pasos](#primeros-pasos)
- [Ejecutar nodos vivos y de papel](#ejecutar-nodos-vivos-y-de-papel)
- [Ejecutar como servicios systemd](#ejecutar-como-servicios-systemd)
- [Configuración](#configuración)
- [Estructura del repositorio](#estructura-del-repositorio)
- [Pruebas](#pruebas)
- [Hoja de ruta](#hoja-de-ruta)
- [Descargo de responsabilidad](#descargo-de-responsabilidad)
- [Licencia](#licencia)

---

## Estado honesto

Se trata de **software de nivel de investigación en validación en vivo**, no de un producto terminado para generar dinero.

- El trading es real, pero se realiza con un **presupuesto de capital pequeño** (del orden de decenas de euros), acotado intencionadamente para que los bugs y los drawdowns sean asumibles mientras se demuestra el valor del motor.
- Las estrategias se validan primero en un **motor de trading en papel realista** antes de comprometer cualquier capital vivo, y se prevé que el capital vivo aumente **por etapas** solo después de cumplir determinados umbrales estadísticos (véase la [Hoja de ruta](#hoja-de-ruta)).
- Los intentos anteriores **no han producido de forma consistente resultados sólidos**. El código base actual refleja las lecciones de dichos intentos: un énfasis en los kill-switches, los stop-loss, las comprobaciones previas al vuelo y una contabilidad honesta de comisiones/deslizamiento (slippage), en lugar de pronósticos optimistas.
- Ninguna cifra de este repositorio es una promesa de rentabilidades futuras. Véase el [Descargo de responsabilidad](#descargo-de-responsabilidad).

Trate este repositorio como una referencia de cómo-no-y-cómo operar una pequeña flota de trading algorítmico — y ajuste sus propias expectativas en consecuencia.

---

## Qué hace

El motor ejecuta **trading en red (grid trading) de doble sentido**: coloca órdenes de compra a medida que el precio cae dentro de una escalera de niveles configurada, y órdenes de venta en niveles de toma de beneficios por encima, cosechando pequeñas ganancias de la oscilación mientras mantiene inventario entre los niveles. Varias familias de estrategias viven bajo `denaro/domain/` (grid, momentum, mean-reversion, variantes adaptativas/volatilidad y sensibles al régimen); el motor de nodo que las rodea es compartido e independiente del exchange.

Rasgos principales:

- **Motor unificado, muchos mercados.** El mismo proceso `denaro.denaro_node`, configurado mediante un archivo YAML, ejecuta cualquier combinación de mercados vivos y de papel con capital, símbolos, niveles y ajustes de riesgo por bot.
- **Trading en papel realista.** Un motor de papel dedicado aplica las comisiones reales del exchange, el nocional mínimo, el deslizamiento (slippage) y los stop-loss, de modo que los resultados de la simulación sean comparables al comportamiento en vivo.
- **Independiente del exchange.** Todo el acceso a órdenes y a datos de mercado se sitúa detrás de una capa de adaptadores (basada en CCXT) en `denaro/infrastructure/exchanges`, de modo que las estrategias nunca hablan con un exchange específico.
- **Orientación al rendimiento.** I/O asíncrono, feeds de precios por WebSocket con difusión ZMQ, limitación de velocidad (rate limiting) y un supervisor que ralentiza los ticks bajo presión de CPU/RAM.

---

## Arquitectura

La flota se distribuye entre tres clases de máquinas según su rol, no según una topología fija:

- **Nodos de trading** — hosts VPS (el proyecto usa actualmente dos, denominados nodos) que ejecutan uno o varios procesos `denaro_node`. Cada uno interpreta su propio `config/node_*.yaml` e informa de su estado de salud.
- **Host de monitorización** — una máquina que agrega el estado de salud de los nodos y ejecuta la monitorización. En este despliegue se encuentra detrás de CGNAT y solo se alcanza a través de **túneles SSH inversos** originados por los nodos de trading, por lo que no se requiere ninguna regla de firewall de entrada.
- **Niveles opcionales de orquestación / alimentación (feeder)** — el motor también incluye una capa de "cerebro"/feeder utilizada para coordinar decisiones de nivel superior y alimentar señales entre componentes.

Una vista simplificada de las relaciones en tiempo de ejecución:

```
┌──────────────┐   ┌──────────────┐     ┌──────────────┐
│   NODE A     │   │   NODE B     │     │  ORCHESTRATOR│
│ denaro_node  │   │ denaro_node  │     │ (optional)   │
│ grid markets │   │ grid markets │     │  brain/feed  │
└──────┬───────┘   └──────┬───────┘     └──────┬───────┘
       │                  │                    │
       └─────────┬────────┴────────────────────┘
                 │   health / metrics over network
        ┌────────▼─────────┐
        │   MONITORING     │   Zabbix server + web dashboard
        │   (aggregates,   │   reachable over reverse SSH tunnel
        │    https access) │
        └──────────────────┘
```

Los detalles de comunicación, plano de control y monitorización dependen del despliegue; el mecanismo utilizado actualmente son los **túneles SSH inversos (autossh)**, de modo que incluso un host NATed pueda ser alcanzado y pueda actuar como servidor de monitorización.

---

## Controles de seguridad y riesgo

La gestión del riesgo es una preocupación de primer nivel, integrada en el motor del nodo en lugar de añadida por separado a cada estrategia:

- **Stop-loss** por bot y un **disyuntor (circuit-breaker) global diario / semanal** que detiene un símbolo o un nodo cuando se cruzan los límites de pérdida configurados.
- **Comprobaciones previas al vuelo** antes de cada colocación de órdenes (validación anti-interbloqueo y dimensionado de la posición), de modo que un bot mal configurado o desactualizado no pueda operar a ciegas.
- **Modo seguro** — un conjunto graduado de estados de limitación (caution → safe → emergency) impulsado por el supervisor (presión de RAM/CPU/ticks) que ralentiza o detiene progresivamente un nodo antes de que se agoten los recursos.
- **Sub-cuentas.** El trading vivo en OKX/Kraken se ejecuta en **sub-cuentas dedicadas** del exchange, nunca en la cuenta principal, de modo que los errores operativos queden contenidos.
- **Credenciales** que viven solo en un `.env` local (nunca commiteadas) y se cargan en tiempo de ejecución.
- **Escalonamiento del presupuesto vivo.** El capital crece en etapas explícitas (papel → vivo pequeño → vivo mayor) y solo después de cumplir los desencadenantes registrados en la hoja de ruta.

---

## Monitorización y alertas

- **Zabbix** se utiliza como backend de agregación y alertas. Los nodos envían métricas (equity, PnL por bot, bloqueos previos al vuelo, estado de salud obsoleto, presión de recursos) al **trapper** de Zabbix.
- Existen desencadenantes para: cruces del circuit-breaker, pérdida diaria/semanal, heartbeats obsoletos, bloqueos previos al vuelo y presión de recursos.
- **La autocuración (auto-heal) está desactivada por defecto.** Las primeras iteraciones reiniciaban los bots vivos de forma espuria; la recuperación es ahora una acción deliberada y registrada en lugar de un reinicio automático.
- Un **panel web (dashboard)** de solo lectura ofrece una vista rápida del estado de salud de nodos y bots.

---

## Primeros pasos

Requisitos:

- Python **3.12+**
- Un entorno `uv` o `venv`
- Docker + Docker Compose solo si además se ejecuta el stack de monitorización Zabbix
- Claves de API del exchange para OKX y/o Kraken (en un `.env` local, nunca commiteadas)

Clonar e instalar:

```bash
git clone git@github.com:grivetto/alpha-omega-trading.git
cd alpha-omega-trading

python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env      # then fill in your API keys
```

---

## Ejecutar nodos vivos y de papel

El motor es una aplicación de consola impulsada por un archivo de configuración:

```bash
# Live grid node (per config file)
python -m denaro.denaro_node --config config/node.yaml

# Paper trading node
python -m denaro.denaro_node --config config/node_paper.yaml

# A Kraken trend-following live config (example)
python -m denaro.denaro_node --config config/node_trend_live_kraken.yaml
```

Las configuraciones adicionales proporcionadas (`config/node_nuvola.yaml`, `config/node_mc2.yaml`, `config/node_adaptive_vol_grid_paper.yaml`, …) corresponden a roles específicos de nodo/estrategia; véase la sección [Configuración](#configuración).

Ejecute `python -m denaro.denaro_node --help` para las opciones (se admite `--verbose`).

---

## Ejecutar como servicios systemd

Para los nodos de producción, se proporcionan archivos de unidad en `systemd/`. Pasos típicos en un host determinado:

```bash
sudo cp systemd/*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now denaro-node            # name depends on the host role
```

Los archivos de unidad cubren actualmente los roles de nodo, salud, agregador, panel, feeder y túnel inverso (`zabbix-tunnel`). **Ajuste las rutas de `ExecStart`** en las unidades para que coincidan con el home de usuario, la ruta del repositorio y el venv utilizados en cada host — los valores distribuidos reflejan un despliegue específico.

---

## Configuración

Cada nodo lee un archivo YAML que define, entre otras cosas:

- `exchange_rest`: el exchange (p. ej. `okx`) y el modo EEA.
- `bots`: una lista de mercados, cada uno con símbolo, `mode` (`live`/`paper`), `capital`, `levels` de grid y ajustes específicos de la estrategia.
- `safemode`: los umbrales de limitación de RAM/CPU (`caution_pct`, `safe_pct`, `emergency_pct`) y su intervalo.
- `supervisor`: umbrales críticos de recursos y limitación de ticks.
- `data_dir`: dónde persiste el nodo su estado en tiempo de ejecución y los datos de mercado.

Mantenga las credenciales del exchange fuera de los archivos de configuración — póngalas en `.env` y cárguelas en tiempo de ejecución.

---

## Estructura del repositorio

```
config/                  Per-node YAML configuration
denaro/
  domain/                Strategies and risk/regime/indicator logic (grid, momentum, adaptive, …)
  application/           Orchestration: portfolio, supervisor, safe-mode
  infrastructure/        Exchange adapters (CCXT), market data, storage, feeder
  denaro_node.py         Unified node entry point
scripts/                 Deployment helpers
systemd/                 systemd unit files (node, health, aggregator, tunnel, …)
zabbix/                  Monitoring integration (healer, push_metrics)
tests/                   Tests
.env.example             Credential template (keys never committed)
```

---

## Pruebas

El proyecto usa `pytest` (con `pytest-asyncio` para las capas asíncronas). Instale las extensiones de desarrollo y ejecute:

```bash
pip install -e ".[dev]"
pytest
```

---

## Hoja de ruta

- [ ] Mantener un registro vivo validado durante una ventana de observación definida (p. ej., varias semanas por bot).
- [ ] Puertas automáticas de promoción: una estrategia puede recibir más capital solo cuando supera los umbrales registrados (factor de beneficio, drawdown máximo, Sharpe).
- [ ] Aumento por etapas del capital (papel → vivo pequeño → 100–500 EUR → 1000 EUR) a medida que se cumplen las condiciones.
- [ ] Plantillas de monitorización con gráficos de equity/PnL/volumen por bot.
- [ ] Empaquetado más limpio: alinear los metadatos de `pyproject.toml` con el diseño real del paquete `denaro`.

---

## Descargo de responsabilidad

**Este software se proporciona únicamente con fines educativos y de investigación. No constituye asesoramiento financiero.** El trading algorítmico de criptoactivos conlleva un riesgo sustancial, incluida la pérdida total del capital desplegado. El rendimiento pasado o en papel no garantiza resultados futuros; las comisiones, el deslizamiento (slippage), las lagunas de liquidez y las interrupciones del exchange pueden convertir un backtest rentable en una campaña en vivo perdedora. Solo despliegue capital que pueda permitirse perder por completo, y nunca opere con dinero del que dependa. Los autores no aceptan ninguna responsabilidad por cualquier pérdida derivada del uso de este código.

---

## Licencia

Dominio público (equivalente a CC0). Véase el archivo [LICENSE](LICENSE) para la dedicación completa — sin derechos reservados; use, copie, modifique y venda libremente, bajo su propio riesgo.
