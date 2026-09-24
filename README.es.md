# Alpha-Omega Trading — «Denaro»

<p align="center">
  <img src="assets/banner.svg" alt="Alpha-Omega Trading Banner" width="100%"/>
</p>

<h3 align="center">Una flota de trading algorítmico medida: tres máquinas, estrategias complementarias, sub-cuentas aisladas</h3>

<p align="center">
  <i>Motor de ejecución multi-nodo independiente sobre OKX EEA, con presupuestos de riesgo duros, telemetría honesta y una puerta de promoción que ninguna estrategia cruza sin superarla.</i>
</p>

<p align="center">
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/Python-3.12+-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.12+"></a>
  <a href="https://www.okx.com/en-eu"><img src="https://img.shields.io/badge/OKX-EEA-000000?style=flat-square" alt="OKX EEA"></a>
  <a href="https://github.com/ccxt/ccxt"><img src="https://img.shields.io/badge/CCXT-4.x-1E88E5?style=flat-square" alt="CCXT"></a>
  <a href="https://www.docker.com/"><img src="https://img.shields.io/badge/Docker-Containerized-2496ED?style=flat-square&logo=docker&logoColor=white" alt="Docker"></a>
  <a href="https://www.zabbix.com/"><img src="https://img.shields.io/badge/Zabbix-7.0_LTS-D40000?style=flat-square&logo=zabbix&logoColor=white" alt="Zabbix 7.0 LTS"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-CC0_1.0-blue.svg?style=flat-square" alt="CC0 License"></a>
</p>

<p align="center">
  <a href="README.md"><b>English</b></a> •
  <a href="README.it.md"><b>Italiano</b></a> •
  <a href="README.es.md"><b>Español</b></a> •
  <a href="README.th.md"><b>ไทย</b></a>
</p>

---

## 📊 Estado de un vistazo — 2026-09-25

> **La flota NO está operando ahora mismo, y no se supone que deba hacerlo.** Todos los nodos en vivo
> informan actualmente `NON FINANZIATO`: las cuentas del exchange detrás de las claves API en vivo
> contienen **~0,15 EUR de polvo**. El motor se niega a operar con un saldo que no puede medir con
> honestidad y, a partir de esta versión, lo *dice* en lugar de saltarse ticks en silencio. La
> financiación es una decisión deliberada y separada.

| Área | Estado | Evidencia |
| :--- | :--- | :--- |
| **Orden del repositorio** | ✅ reconciliado con `origin`, el trabajo de todas las sesiones commiteado | 5 commits publicados, `main` alineado |
| **Suite de pruebas** | ✅ **por fin ejecutable** (antes 63 fallos / 50 errores, todos de entorno) | ver § Pruebas |
| **Idempotencia de órdenes** | ✅ implementada (`clOrdId` en cada envío, registrada en el diario *antes* de la orden) | 7 tests |
| **Estado sin fondos** | ✅ explícito `ok` / `sottocapitalizzato` / `non_finanziato` / `illeggibile` | 18 tests |
| **Límite de exposición de la cuenta** | ✅ conectado al nodo (el registro existía, nadie lo había construido) | 15 tests |
| **Comprobación de integridad de la flota** | ✅ `tools/fleet_integrity.py`, código de salida 1 ante cualquier alarma | 14 alarmas en MARCODG1, 7 en nuvola |
| **Trading en vivo** | ⛔ el saldo de la cuenta es polvo (~0,15 EUR) | diario: 882 + 604 ticks saltados |
| **Servicios de telemetría** | ⚠️ 4 unidades en reinicio patológico (deriva de rutas) | `denaro-watchdog` fallido |
| **Seguridad** | ⚠️ un host fue comprometido, ahora contenido | ver § Seguridad |
| **Economía** | ⚠️ el tramo de comisiones actual anula la ventaja — ver § La economía | medido sobre comisiones reales |

---

## 🏛 Topología de la flota

El sistema se ejecuta en tres hosts, cada uno un **nodo independiente: una máquina = una familia de
estrategias = una sub-cuenta de OKX**. No es una elección estilística — es la corrección de tres
defectos que se observaron en producción (ver § Lecciones).

```
 ┌──────────────────────────────────────────────────────────────┐
 │                  CAPA DE EXCHANGE — OKX EEA                  │
 │     (las claves de la UE solo funcionan en eea.okx.com)      │
 └───────┬──────────────────┬──────────────────┬────────────────┘
         │                  │                  │
 ┌───────▼────────┐ ┌───────▼────────┐ ┌───────▼──────────────┐
 │ NODO A         │ │ NODO B         │ │ NODO C               │
 │ nuvola         │ │ mc2            │ │ MARCODG1             │
 │ TREND (diario) │ │ GRID adaptativo│ │ 4H momentum          │
 │ sub: nuvolasub1│ │ sub: mc2sub1   │ │ sub: marcosub1       │
 │ edge MEDIDO    │ │ puerta: por    │ │ puerta: requiere     │
 │                │ │ medir          │ │ de 0.30%/lado        │
 └────────────────┘ └────────────────┘ └──────────────────────┘
         │                  │                  │
         └──────────────────┴──────────────────┘
                            │
              ┌─────────────▼──────────────┐
              │ GOBERNADOR DE RIESGO       │
              │ presupuesto: 2% del capital│
              │ stop diario −3%, DDmáx −10%│
              └────────────────────────────┘
```

**Tres reglas que no son negociables:**

1. **Una cuenta por estrategia.** Ningún bot comparte una sub-cuenta con una estrategia distinta.
2. **El riesgo es una propiedad de la cartera, no de cada bot.** El presupuesto del 2% es sobre el
   capital *total*. Siete bots declarando cada uno el riesgo de toda la cuenta arriesgaban **el 14%
   de la cuenta, no el 2%** — medido por `tools/audit_capitale_config.py`.
3. **Ninguna estrategia entra en producción sin superar la puerta**: expectativa neta positiva fuera
   de muestra, a los costes *reales* de la cuenta en la que se ejecuta.

### Tecnologías principales

| Componente | Tecnología | Función |
| :--- | :--- | :--- |
| **Núcleo de ejecución** | Python, AsyncIO, CCXT | Políticas (trend / grid adaptativo / reversión a la media), ciclo de vida de órdenes, contabilidad de ejecuciones |
| **Núcleo de riesgo** | Módulos de dominio puros, sin I/O | Riesgo por operación, disyuntor, límite de exposición de la cuenta, clasificación de financiación |
| **Backtest** | Motor propio, consciente de comisiones y deslizamiento | El mismo código de decisión que en vivo: un solo banco de pruebas para ambos |
| **Operación de la flota** | systemd, SSH, Tailscale, Cloudflare Tunnel | Sin exposición entrante; telemetría solo en loopback |
| **Telemetría** | Zabbix, Prometheus, Grafana, paneles | Curvas de equity, salud de los ticks, indicadores de obsolescencia |
| **Integridad** | `tools/fleet_integrity.py` | Comprobaciones de miner / crontab / sudoers / rutas de unidades / puertos, con código de salida |

---

## 🧪 Pruebas — y por qué fueron la mayor corrección de este ciclo

```bash
python -m pytest denaro/tests -q      # 382 passed, 3 skipped
```

Durante semanas la suite reportaba **63 fallos y 50 errores**. Casi ninguno eran defectos de código:
eran **errores de permisos del entorno**. La causa raíz, aislada con tres sondas directas:

```
os.makedirs(<repo>/.pytmp/probe) + write   -> OK
tempfile.mkdtemp()               + write   -> PermissionError
os.makedirs(...) + open(...)     -> OK
```

`tempfile.mkdtemp` es rechazado mientras que `os.makedirs` funciona — y tanto `TemporaryDirectory`
como el `tmp_path` de pytest pasan por él. La consecuencia era el daño real: **dos sesiones de
trabajo independientes no podían verificar nada**, y una suite cuyo resultado es ruido no puede
proteger nada. `denaro/tests/conftest.py` ahora lo sustituye en la raíz: el resultado pasó de *63
fallos / 50 errores* a **1 fallo real**, que es una laguna semántica conocida (ver § Trabajo abierto).

---

## 💰 La economía — dicha con claridad

El número decisivo no es la estrategia, es el peaje. Medido a partir de las páginas oficiales de
comisiones de OKX EEA:

| cuenta | maker | taker | ida y vuelta | ventaja bruta de equilibrio por operación |
| :--- | :--- | :--- | :--- | :--- |
| OKX EEA **sin** derivados (hoy) | 0,200% | **0,350%** | **0,700%** | **0,70%** |
| OKX EEA **con** X-Perps abiertos | 0,080% | **0,100%** | **0,200%** | 0,20% |

Abrir una cuenta de derivados en OKX EEA **no** requiere volumen ni capital — solo KYC más una
*evaluación de idoneidad*. Lleva la cuenta de la tabla del 0,35% a la del 0,10%.

**Y una corrección que estuvo circulando durante días:** el `−1,97%` del trend diario es un
**alpha acumulado a lo largo de 2,4 años**, no un retorno diario. A coste cero la señal es
significativa (t = +4,51); a 0,35% por lado es **indistinguible de cero** (t = −0,30). No es una
estrategia que sangra — es una estrategia que el peaje borra.

Las dos palancas que de verdad multiplican:

- **bajar el peaje** — de 0,70% a 0,20% por ida y vuelta, lo que multiplica por 3,5× la frecuencia
  sostenible;
- **subir la frecuencia** — la familia de 4H pasa de 3/24 a 18/24 configuraciones robustas con la
  misma comisión más baja, es decir, ~8× las oportunidades.

Ninguna de las dos es código. Una es una evaluación; la otra es su consecuencia.

---

## 🛡 Gestión del riesgo

- **Riesgo por operación** — 2% del capital, fijado en la configuración y publicado en el estado de
  salud.
- **Disyuntor** — stop diario en −3%, drawdown máximo en −10%, persistido entre reinicios.
- **Límite de exposición de la cuenta** — la *suma* de todos los bots de la misma sub-cuenta, no por
  bot.
- **Clasificación de financiación** — un nodo sin capital declara `NON FINANZIATO` una vez por
  transición, no coloca órdenes y nunca contamina las líneas base de pico / diaria / semanal. Sale
  del estado por sí solo cuando llegan fondos, sin reinicio.
- **Idempotencia de órdenes** — cada envío lleva un `clOrdId`, registrado en el diario *antes* de que
  la orden salga; una orden que sobrevive a un fallo se reconoce como nuestra al reiniciar en lugar
  de contarse como desconocida.
- **Semántica del stop** — el stop vende la posición propia del bot (`tamaño rastreado + comprado y
  no revendido`), nunca el saldo libre de la cuenta: con dos bots en una sub-cuenta, el
  comportamiento anterior liquidaba el inventario de otro bot.
- **Supervisor** — la presión de RAM/CPU limita los intervalos de tick (`nominal` → `caution` →
  `safe` → `emergency`).

---

## 🔒 Seguridad — un host fue comprometido, ahora contenido (2026-09-25)

Una auditoría de la flota encontró un **minero de criptomonedas de terceros** en MARCODG1: un binario
ELF en `/var/tmp/.X11-unix-socket/`, ejecutándose como el usuario del servicio `zabbix` durante
**4 días**, 199% de CPU y 2,1 GB de RAM, con persistencia en cron y una conexión activa a un pool de
minería. Fue la causa directa del vaivén `SafeMode safe ↔ caution` del nodo en vivo (RAM al 87%).

Contención, con copias forenses tomadas **antes** de cualquier borrado:

| acción | resultado verificado |
| :--- | :--- |
| proceso terminado | sin PID, 0 conexiones al pool |
| RAM | uso **3114 → 1003 MB** |
| persistencia en cron | eliminada (spool verificado en disco) |
| binario | `chmod 000` + copia en `/root/quarantena_miner_20260925/` |
| regla `sudo` huérfana para `zabbix` | eliminada → *no tiene permiso para ejecutar sudo* |
| `AllowKey=system.run[*]` | deshabilitado en **ambos** hosts |

**Pendiente para el propietario:** revocar el PAT de GitHub encontrado en texto claro en un historial
de shell; rotar las credenciales de Zabbix; decidir si reconstruir el host comprometido; regenerar el
almacén de claves (7 de 7 claves de OKX que contiene están muertas); revisar el cortafuegos (`ufw`
inactivo, `5432` y `10050` expuestos).

---

## 📚 Lecciones («La Baracca»)

El proyecto recibió originalmente el apodo de *"La Baracca"* — italiano para un artefacto improvisado
que siempre necesita otro parche. El nombre envejeció bien. Lo que enseñaron los mercados reales, por
orden de coste:

1. **El capital fragmentado bloquea.** Saldos pequeños repartidos entre muchas sub-cuentas, cada una
   con órdenes abiertas, reducen el saldo libre a cero.
2. **El peaje no es un detalle.** Las comisiones y el deslizamiento anulan en silencio ventajas que
   los backtests muestran con holgura.
3. **Cada bot que declara toda la cuenta multiplica el riesgo por N.** Siete bots × 2% = 14%.
4. **Un guardián sin estado es un fallo silencioso.** 1.486 ticks saltados parecían "no ha pasado
   nada" durante horas, porque ningún estado decía "no tengo fondos".
5. **Las órdenes no rastreadas tras un fallo son dinero invisible.** De ahí las claves de
   idempotencia.
6. **Una telemetría que se lee como un fósil es peor que ninguna telemetría.** Los archivos de salud
   obsoletos cuentan como "en ejecución" a menos que algo compruebe explícitamente su antigüedad.
7. **La deriva de rutas en producción lo rompe todo a la vez.** Diez de doce unidades rotas
   compartían una única causa raíz: una ruta de proyecto obsoleta en unidades systemd y crontabs que
   nunca se versionaron.

---

## 🛠 Inicio rápido

```bash
git clone git@github.com:grivetto/alpha-omega-trading.git
cd alpha-omega-trading
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env         # las credenciales se quedan en local: no commitees nunca secretos

# comprobación de integridad de la máquina (solo lectura, código de salida 1 ante alarma)
python tools/fleet_integrity.py
python tools/fleet_integrity.py --host nuvola --host MARCODG1 --host mc2

# pruebas
python -m pytest denaro/tests -q

# un nodo
python -m denaro.denaro_node --config config/node_nuvola_trade.yaml

# backtest honesto contra comisiones reales
python -m denaro.backtest --config config/node_nuvola_trade.yaml --days 60 --fee 0.0035
```

---

## 🚧 Trabajo abierto, por orden de valor

1. **Registrar la posición del grid al ejecutarse.** El único fallo real de prueba que queda: un grid
   compra, la ejecución no se registra como posición abierta, y el stop recurre a deducirla de las
   órdenes de venta. Correcto, pero no suficiente.
2. **Aislamiento de las pruebas.** Una prueba pasa sola y falla en la suite → estado compartido entre
   pruebas. Relacionado: `pytest-asyncio` no está instalado y `asyncio_mode` es una opción
   desconocida, así que las pruebas asíncronas se ejecutan actualmente mediante un mecanismo sin
   explicar.
3. **Telemetría** — 4 unidades en reinicio patológico, todas por la deriva de rutas entre `~/denaro`
   y `~/alpha-omega-trading`.
4. **Versionar la infraestructura** (`deploy/systemd/`, `deploy/cron/` con un `PROJECT_ROOT`
   parametrizado): la causa raíz de 10 de 12 unidades rotas, y de la ceguera sobre quién cambió qué.
5. **Capital.** La variable decisiva, y deliberadamente separada del código.

## 🗺 Ruta de escalado

La estructura es idéntica en cualquier escala: **un nodo = una estrategia = una cuenta**. Lo que
cambia es el *número de nodos*, no el número de estrategias empaquetadas en una cuenta. Empaquetarlas
juntas es el experimento ya realizado — y produjo un 14% de riesgo agregado, bots deteniéndose unos a
otros sobre el mismo equity y un stop liquidando el inventario de otro bot.

- [x] **Ahora:** repositorio en orden, tres defectos críticos cerrados con pruebas, comprobación de
      integridad operativa, suite ejecutable.
- [ ] **Siguiente:** registro de las ejecuciones del grid, aislamiento de las pruebas, telemetría
      reparada, infraestructura versionada.
- [ ] **Después:** la puerta de las comisiones — poner **una** cuenta en un estado limpio y solicitar
      la mejora de derivados. No toca ningún despliegue, es reversible, y es la única acción que
      desbloquea la frecuencia.
- [ ] **Después:** capital por etapas, y solo con evidencia fuera de muestra.

---

## ⚖️ Descargo de responsabilidad

**Este software se distribuye estrictamente con fines educativos, académicos y de investigación. No
constituye asesoramiento financiero ni de inversión.** El trading algorítmico de criptomonedas
implica un riesgo financiero sustancial, incluida la posible pérdida de todo el capital invertido.
Los autores no ofrecen ninguna declaración ni garantía sobre la rentabilidad o el rendimiento del
sistema. Nunca operes con capital que no puedas permitirte perder.

---

## 📄 Licencia

Dedicado al dominio público bajo Creative Commons Zero (CC0 1.0 Universal). Véase [LICENSE](LICENSE).
