# ⚡ ALPHA-OMEGA TRADING — ATLAS

[![License: Unlicense](https://img.shields.io/badge/license-Unlicense-blue.svg)](http://unlicense.org/)
[![Python](https://img.shields.io/badge/python-3.12%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![CCXT](https://img.shields.io/badge/exchange-CCXT%20Pro%20%2F%20Kraken%20%7C%20OKX-5741D9?logo=bitcoin&logoColor=white)](https://github.com/ccxt/ccxt)
[![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20systemd-FCC624?logo=linux&logoColor=black)](https://www.freedesktop.org/wiki/Software/systemd/)
[![Status](https://img.shields.io/badge/status-LIVE-brightgreen)](https://github.com/grivetto/alpha-omega-trading)

> **ATLAS** คือวิวัฒนาการแบบโมดูลาร์ อะซิงโครนัส และหลายเอ็กซ์เชนจ์ของระบบ **Denaro** เดิม ใช้เอ็กซ์เชนจ์เดียวกัน ข้อมูลรับรองเดียวกัน ปรัชญาเดียวกัน — แต่สร้างใหม่ด้วยสถาปัตยกรรมที่สะอาด รูปแบบการทนทานต่อความผิดพลาด และการจัดการความเสี่ยงในตัว

---

## 🏗️ ATLAS คืออะไร

ATLAS เป็นระบบเทรดดิ้งอัลกอริทึมแบบกระจาย เขียนด้วย Python 3.12 และ `asyncio` แทนที่โค้ดเบสแบบเสาหินของ Denaro ด้วยสถาปัตยกรรมแบบโมดูลาร์:

- **หลายเอ็กซ์เชนจ์**: Kraken และ OKX Europe (EEA) ผ่าน CCXT async + CCXT Pro (WebSocket)
- **หลายโหนด**: หนึ่งอินสแตนซ์ต่อโหนดเทรดดิ้งหนึ่ง (`nuvola`, `MARCODG1`)
- **กลยุทธ์กริด**: ออเดอร์ limit buy/sell รอบราคากลาง
- **ทนทาน**: timeout → retry แบบ exponential backoff → แยกประเภทข้อผิดพลาดที่ไม่ควร retry
- **มีการจัดการความเสี่ยง**: จำกัด drawdown, ขาดทุนรายวัน, ขนาดโพซิชัน, exposure, correlation + kill switch
- **สังเกตได้**: logging แบบ JSON, HTTP API สำหรับ health/readiness

## 🧩 สถาปัตยกรรม

```
atlas/
├── main.py                 # จุดเข้าใช้งาน: วงจรชีวิต + dependency injection
├── core/
│   ├── config.py           # Pydantic settings + โหลด YAML พร้อมแทนที่ ${VAR}
│   ├── events.py           # EventBus (pub/sub แบบ async: tick, fill, เหตุการณ์เสี่ยง)
│   ├── lifecycle.py        # GracefulShutdown (จัดการ SIGINT/SIGTERM)
│   └── resilience.py       # decorator exchange_call: timeout → retry → circuit breaker
├── connector/
│   ├── interface.py        # คลาสพื้นฐานนามธรรม ExchangeConnector
│   ├── ccxt_adapter.py     # การใช้งาน CCXT async (REST + WebSocket)
│   └── models.py           # Ticker, OrderBook, Balance
├── strategy/
│   └── engine.py           # GridStrategy + StrategyEngine (ลูป tick, กันออเดอร์ซ้ำ)
├── execution/
│   ├── router.py           # ExecutionRouter: ท่อส่งออเดอร์
│   └── models.py           # OrderRequest, OrderResponse, CancelResponse
├── portfolio/
│   └── manager.py          # ExchangeRegistry + PortfolioManager (จำกัดความเสี่ยง, equity)
├── observability/
│   └── logging.py          # logging แบบ JSON
└── storage/                # เก็บสถานะ
```

### ท่อส่งการทำงาน

```
Ticker → StrategyEngine (GridStrategy.on_tick)
       → ExecutionRouter.submit(OrderRequest)
       → CCXTAdapter.create_order (ผ่าน exchange_call: timeout→retry→classify)
       → Exchange (Kraken / OKX EEA)
```

ลูปกลยุทธ์ถูกจำกัดอัตรา (สูงสุด 1 สัญญาณต่อสัญลักษณ์ต่อ 60 วินาที) และกันซ้ำกับออเดอร์ที่เปิดอยู่ บอทจึงไม่กองออเดอร์แบบไม่ลืมหูลืมตา

## ⚙️ การกำหนดค่า

ค่าทั้งหมดอยู่ใน `config/` เป็น YAML โดยแทนที่ `${VAR}` จากไฟล์ `.env`:

**`config/exchanges.yaml`** — ข้อมูลรับรองและการปรับจูนเอ็กซ์เชนจ์:

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
      eea: true        # → บังคับ hostname eea.okx.com (OKX Europe)
```

> ⚠️ **OKX Europe (EEA)**: flag `extra.eea: true` จำเป็น หากไม่มี บอทจะชี้ไปที่ `api.okx.com` และทุกการเรียกที่ต้องยืนยันตัวตนจะล้มเหลวด้วย error 50119/50111

**`config/strategies.yaml`** — พารามิเตอร์กลยุทธ์:

```yaml
strategies:
  - strategy_id: grid_btc_eur
    class_path: atlas.strategy.engine.GridStrategy
    enabled: true
    symbols: ["BTC/EUR"]
    exchanges: ["kraken"]
    params:
      grid_levels: 3          # จำนวนระดับกริดรอบราคากลาง
      spread_pct: 0.005       # ระยะห่างระหว่างระดับ (0.5%)
      per_level_pct: 0.10     # สัดส่วน equity ต่อระดับ
      order_size: 0.00005     # ขนาดออเดอร์ชัดเจน (แทนที่ per_level_pct)
      min_notional: 5.0       # มูลค่าออเดอร์ขั้นต่ำ
```

**`.env`** — ข้อมูลรับรอง API (ห้าม commit; ดู `.gitignore`)

## 🛡️ การจัดการความเสี่ยง

ค่าเริ่มต้น (`atlas/core/config.py`) บังคับโดย `PortfolioManager`:

| ข้อจำกัด | ค่า |
|---------|-----|
| Drawdown สูงสุดของพอร์ต | 20% |
| ขาดทุนสูงสุดต่อวัน | 5% |
| ขนาดโพซิชันสูงสุด | 25% ของ equity |
| Exposure สูงสุดต่อสกุลเงินฐาน | 30% |
| Exposure สูงสุดตาม correlation | 70% |
| เลเวอเรจสูงสุด | 1.0 (spot เท่านั้น) |

การละเมิดจะปล่อย `RiskEvent` ไปที่ event bus และสามารถกระตุ้น **kill switch** ได้

## 🔄 ความเข้ากันได้กับ Denaro

ATLAS คือวิวัฒนาการโดยตรงของ **Denaro**: รักษาสิ่งที่ใช้ได้ผล และแก้สิ่งที่ใช้ไม่ได้

| ด้าน | Denaro (เดิม) | ATLAS |
|------|---------------|-------|
| โค้ดเบส | เสาหิน (`engine_solo.py`, `bot_v5.py`) | แพ็กเกจโมดูลาร์ `atlas/` |
| การเข้าถึงเอ็กซ์เชนจ์ | เรียก CCXT ตรง | CCXT async ผ่าน `CCXTAdapter` + ชั้นความทนทาน |
| กลยุทธ์ | กริดเขียนตายตัวต่อบอท | `GridStrategy` ประกาศจาก YAML |
| ความเสี่ยง | กระจายในเช็คเฉพาะกิจ | `PortfolioManager` กลางพร้อมขีดจำกัดเข้มงวด |
| การสังเกต | ไฟล์ log | logging JSON + HTTP API `/health` + `/ready` |
| ความทนทาน | ไม่มี | timeout → retry → circuit breaker (`exchange_call`) |
| การตั้งค่า | ค่าคงที่ในโค้ด | YAML + `.env` แทนที่ `${VAR}` |

**อยู่ร่วมกัน**: ทั้งสองระบบรันบนโหนดและเอ็กซ์เชนจ์เดียวกัน อ่าน **ส่วนแยกกัน** ของ `.env` ไฟล์เดียวกัน (คีย์ Denaro vs คีย์ ATLAS) ใช้หน่วย systemd แยก และไม่เคยแชร์สถานะออเดอร์กัน พารามิเตอร์กริดของ Denaro แมปตรงไปที่พารามิเตอร์ `GridStrategy` (`grid_levels`, `spread_pct`, `per_level_pct`)

**เส้นทางการย้าย**: บอทกริด Denaro ย้ายโดย (1) เขียนพารามิเตอร์ลง `config/strategies.yaml` (2) เพิ่มส่วนคีย์ API ลง `.env` (3) เริ่ม `atlas-engine.service`

## 🚀 การติดตั้ง

```bash
# 1. ติดตั้ง dependencies
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 2. ตั้งค่า
cp .env.example .env            # ใส่ข้อมูลรับรอง API
# แก้ config/exchanges.yaml + config/strategies.yaml

# 3. รัน (foreground)
.venv/bin/python -m atlas.main

# 4. รันเป็นบริการ (production)
sudo systemctl enable --now atlas-engine
sudo systemctl enable --now atlas-watchdog   # auto-healing
```

**`atlas-engine.service`** รันบอทด้วย `Restart=always`; **`atlas-watchdog.service`** รีสตาร์ทเครื่องยนต์เมื่อไม่ตอบสนอง

### Health API

```
GET /health   → {"status": "healthy", "service": "atlas-engine", "exchanges": [...], "strategies": [...]}
GET /ready    → {"ready": true|false, "service": "atlas-engine"}
```

เซิร์ฟเวอร์ health ผูกกับ `[::]:8080` (dual-stack IPv4/IPv6) เพื่อให้โหนดหลัง CGNAT ถูกมอนิเตอร์จากระยะไกลได้

## 📊 การติดตั้งปัจจุบัน

| โหนด | เอ็กซ์เชนจ์ | คู่เทรด | บริการ |
|------|-----------|--------|--------|
| `nuvola` | Kraken | BTC/EUR | atlas-engine + watchdog |
| `MARCODG1` | OKX (EEA) | ETH/EUR, SOL/EUR, XRP/EUR, DOGE/EUR | atlas-engine + watchdog |

## 🧠 หลักการออกแบบ

1. **Code is law, profit is proof** — ทุกการตัดสินใจเทรดเป็น deterministic และตรวจสอบได้
2. **ปกป้องทุนก่อนเสมอ** — จำกัดความเสี่ยงถูกบังคับในเส้นทางโค้ด ไม่ใช่แค่ในรายการความตั้งใจ
3. **การกระจายคือความทนทาน** — สองโหนดอิสระ ไม่มีจุดเสียจุดเดียว
4. **ไม่สิ้นเปลืองอะไร** — async I/O ไม่มีเฟรมเวิร์กเกินจำเป็น หนึ่งกระบวนการต่อโหนด
5. **ไม่เคยไว้ใจข้อมูลรับรองในโค้ด** — ความลับอยู่ใน `.env` เท่านั้น (gitignored)

## 📄 สัญญาอนุญาต

[The Unlicense](http://unlicense.org/) — สาธารณสมบัติ ใช้เลย ศึกษาเลย ทำลายเลย ปรับปรุงเลย
