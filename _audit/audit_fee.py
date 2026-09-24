"""Audit economico: tabelle fee / round-trip / break-even. Solo aritmetica su dati verificati."""
import json

# --- Fee verificati dalle pagine ufficiali (vedi report per URL) ---
# OKX EEA, conto SENZA derivati (identico a "Lv1" misurato sul conto di produzione)
OKX_NO_DERIV = {"Regular": (0.200, 0.350), "VIP1": (0.100, 0.200), "VIP2": (0.090, 0.180),
                "VIP3": (0.080, 0.150), "VIP4": (0.075, 0.100), "VIP5": (0.070, 0.085),
                "VIP6": (0.060, 0.070), "VIP7": (0.055, 0.065), "VIP8": (0.045, 0.060),
                "VIP9": (0.030, 0.055)}
# OKX EEA, conto CON derivati (X-Perps) aperti
OKX_DERIV = {"Regular": (0.0800, 0.1000), "VIP1": (0.0675, 0.0800), "VIP2": (0.0600, 0.0700),
             "VIP3": (0.0550, 0.0650), "VIP4": (0.0300, 0.0450), "VIP5": (0.0250, 0.0350),
             "VIP6": (0.0000, 0.0300), "VIP7": (-0.0020, 0.0250), "VIP8": (-0.0050, 0.0200),
             "VIP9": (-0.0075, 0.0175)}
# Soglie: (assets EUR, volume 30g EUR). None = non raggiungibile per quella via
OKX_THRESH = {"Regular": (0, 0), "VIP1": (100_001, 100_001), "VIP2": (200_001, 250_001),
              "VIP3": (2_000_001, 500_001), "VIP4": (5_000_001, 1_000_001),
              "VIP5": (20_000_001, 2_500_001), "VIP6": (50_000_001, 5_000_001),
              "VIP7": (100_000_001, 10_000_001), "VIP8": (250_000_001, 20_000_001),
              "VIP9": (500_000_001, 50_000_001)}

KRAKEN_CRYPTO = {"Tier1": (0.40, 0.80), "Tier2": (0.30, 0.60), "Tier3": (0.22, 0.38),
                 "Tier4": (0.20, 0.35), "Tier5": (0.15, 0.30), "Tier6": (0.12, 0.25),
                 "Tier7": (0.10, 0.22), "Tier8": (0.08, 0.20), "Tier9": (0.06, 0.18),
                 "Tier10": (0.04, 0.15), "Tier11": (0.02, 0.12), "Tier12": (0.00, 0.10),
                 "Pro1": (0.00, 0.09), "Pro5": (0.00, 0.05)}
KRAKEN_STABLE = {"0": (0.20, 0.20), "50k": (0.16, 0.16), "100k": (0.12, 0.12),
                 "250k": (0.08, 0.08), "500k": (0.04, 0.04), "1M": (0.02, 0.02),
                 "10M": (0.00, 0.01), "100M": (0.00, 0.001)}
KRAKEN_VOL = {"Tier1": 0, "Tier2": 2_500, "Tier3": 10_000, "Tier4": 25_000, "Tier5": 50_000,
              "Tier6": 100_000, "Tier7": 250_000, "Tier8": 500_000, "Tier9": 1_000_000,
              "Tier10": 2_500_000, "Tier11": 5_000_000, "Tier12": 10_000_000,
              "Pro1": 50_000_000, "Pro5": 500_000_000}
KRAKEN_STABLE_VOL = {"0": 0, "50k": 50_000, "100k": 100_000, "250k": 250_000,
                     "500k": 500_000, "1M": 1_000_000, "10M": 10_000_000, "100M": 100_000_000}

BYBIT_SPOT = {"VIP0": (0.1000, 0.2500), "VIP1": (0.0675, 0.1000), "VIP2": (0.0650, 0.0775),
              "VIP3": (0.0625, 0.0750), "VIP4": (0.0500, 0.0600), "VIP5": (0.0400, 0.0500)}
BYBIT_FIAT = {"VIP0": (0.1500, 0.2500), "VIP1": (0.1200, 0.2500), "VIP2": (0.1000, 0.2200),
              "VIP3": (0.1000, 0.2000), "VIP4": (0.1000, 0.1500), "VIP5": (0.0675, 0.1200)}
BYBIT_THRESH = {"VIP0": (0, 0), "VIP1": (100_000, 1_000_000), "VIP2": (250_000, 5_000_000),
                "VIP3": (500_000, 10_000_000), "VIP4": (1_000_000, 25_000_000),
                "VIP5": (2_000_000, 50_000_000)}

CAPITAL = 52.0
def rt(maker, taker):  # round trip taker/taker in %
    return 2 * taker
def euro(pct_rt, cap=CAPITAL):
    return cap * pct_rt / 100.0

L = []
def p(s=""): L.append(s)

p("# AUDIT ECONOMICO — tabelle calcolate")
p()
p("## A. Round-trip e break-even (taker/taker), capitale 52 EUR")
p()
p("| Venue / livello | Maker | Taker | Round-trip % | Break-even edge lordo/trade | Costo su 52 EUR | N. trade/anno a pareggio con edge 2% |")
p("|---|---|---|---|---|---|---|")
rows = [
    ("OKX EEA spot, NO derivati (Regular = oggi)", 0.200, 0.350),
    ("OKX EEA spot, CON X-Perps (Regular)", 0.0800, 0.1000),
    ("OKX EEA swap taker (acctLv2 richiesto)", 0.02, 0.05),
    ("Bybit EU spot crypto VIP0", 0.1000, 0.2500),
    ("Bybit EU fiat pair (USDC/EUR) VIP0", 0.1500, 0.2500),
    ("Kraken stablecoin/FX (EUR/USDC) tier 0", 0.20, 0.20),
    ("Kraken spot crypto Tier1", 0.40, 0.80),
    ("Binance (non piu' disponibile per IT dal 2026-07-01)", None, None),
]
for name, mk, tk in rows:
    if tk is None:
        p(f"| {name} | n/d | n/d | n/d | n/d | n/d | n/d |")
        continue
    r = rt(mk, tk)
    be = 2 * tk            # edge lordo per trade necessario = round-trip
    e = euro(r)
    n = 2.0 / r if r > 0 else float("inf")
    p(f"| {name} | {mk:.4g}% | {tk:.4g}% | {r:.4f}% | {be:.4f}% | {e:.4f} EUR | {n:.2f} |")
p()
p("Nota: 'break-even edge lordo per trade' = 2xfee_taker, che e' anche il costo di")
p("attraversare lo spread. Il valore 0.7778% di docs/39 somma 2x0.35 con lo spread mediano")
p("0.0778%: e' un doppio conteggio (la fee taker GIA' paga lo spread). La misura corretta")
p("e' 0.70%. Errore prudenziale (~11% di sovrastima), non cambia alcuna conclusione.")
p()

p("## B. Costo effettivo A GIRO COMPLETO, taker/taker")
p()
p("| Venue | fee/lato | round-trip (2x) | in EUR su 52 |")
p("|---|---|---|---|")
for name, f in [("OKX EEA spot oggi (NO derivati)", 0.350),
                ("OKX EEA spot CON X-Perps aperti", 0.100),
                ("OKX EEA swap taker (acctLv2)", 0.050),
                ("OKX swap taker + funding 3g", 0.050 + 0.018),
                ("Bybit EU spot taker VIP0", 0.250),
                ("Kraken EUR/USDC stabile taker", 0.200),
                ("Kraken spot crypto Tier1 taker", 0.800)]:
    r = 2 * f
    p(f"| {name} | {f:.3f}% | {r:.4f}% | {euro(r):.4f} |")
p()

p("## C. Sensibilita' del trend giornaliero (params FISSI canale40/trail3/stop2, 19 asset)")
p("Dati docs/17 §9.3 — gli unici tre punti realmente misurati:")
p()
p("| fee per lato | alpha cumulato | t |")
p("|---|---|---|")
pts = [(0.00, 34.98, 4.51), (0.20, 12.33, 1.73), (0.35, -1.97, -0.30)]
for f, a, t in pts:
    p(f"| {f:.2f}% | {a:+.2f}% | {t:+.2f} |")
p()
# regressione su (0.00,0.20) e (0.20,0.35)
import statistics
xs = [0.00, 0.20, 0.35]; ys = [34.98, 12.33, -1.97]
n = len(xs); mx = sum(xs)/n; my = sum(ys)/n
slope = sum((x-mx)*(y-my) for x, y in zip(xs, ys)) / sum((x-mx)**2 for x in xs)
inter = my - slope*mx
p(f"Interpolazione lineare sui tre punti: alpha(f) = {inter:.2f} + ({slope:.2f})*f   [f in %]")
for f in (0.00, 0.05, 0.10, 0.15, 0.20, 0.25, 0.35):
    p(f"  - f = {f:.2f}%/lato -> alpha stimato {inter + slope*f:+.2f}%")
p(f"  - break-even (alpha=0) a f = {-inter/slope:.3f}% per lato")
p()
p("CONFRONTO CON docs/17 §9.2 (campione CON selezione dei parametri per asset):")
p("| fee/lato | TREND alpha | t |")
p("|---|---|---|")
for f, a, t in [(0.00,104.13,3.92),(0.05,95.59,3.68),(0.10,86.73,3.40),
                (0.20,72.72,2.99),(0.35,54.43,2.41)]:
    p(f"| {f:.2f}% | {a:+.2f}% | {t:+.2f} |")
p("A 0.10%/lato quella tabella da' t = 3.40, cioe' SOPRA la soglia di significativita' 2.")
p("Ma la stessa pagina avverte che quei valori sono 'gonfiati dalla selezione dei")
p("parametri per asset': la tabella a parametri FISSI (§9.3) ha solo 3 punti misurati")
p("(0.00 / 0.20 / 0.35) e il punto a 0.10% non esiste. L'interpolazione e' una STIMA.")
p()
p()
p("ATTENZIONE: interpolazione su 3 punti, non una misura. I punti a 0.05/0.10/0.15%/lato")
p("NON sono stati simulati. Dichiarato come stima, non come fatto.")
p()

p("## D. Robustezza misurata (configurazioni robuste su 24) — docs/40 §40.1")
p()
p("| fee per lato | 4H (19 asset) | 4H largo (28) | 1D (19) | 1D largo (47) |")
p("|---|---|---|---|---|")
for f, a, b, c, d in [(0.35,3,4,14,7),(0.27,9,11,17,9),(0.25,9,14,18,9),
                      (0.20,13,19,18,10),(0.10,18,21,18,12),(0.05,20,21,18,12)]:
    p(f"| {f:.2f}% | {a} | {b} | {c} | {d} |")
p()

p("## E. Trade necessari per assorbire la fee (edge lordo per trade = R)")
p()
p("| edge lordo/trade | trade/anno a pareggio @0.35%/lato | @0.25%/lato | @0.20%/lato | @0.10%/lato | @0.05%/lato |")
p("|---|---|---|---|---|---|")
for R in (0.5, 1.0, 2.0, 3.0, 5.0):
    cells = []
    for f in (0.35, 0.25, 0.20, 0.10, 0.05):
        cells.append(f"{R/(2*f):.2f}")
    p(f"| {R:.1f}% | " + " | ".join(cells) + " |")
p()
p("Frequenza misurata dal progetto: ~10 trade per asset in 2.5 anni = 4 trade/anno per asset (docs/17 §10).")
p("Con 5 posizioni contemporanee su 1 conto: ~4 trade/anno per slot.")

out = "\n".join(L)
open("_audit/calcoli.md", "w", encoding="utf-8").write(out)
print(out)
