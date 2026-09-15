#!/usr/bin/env bash
# validate.sh — gate di validazione OBBLIGATORIO prima di qualunque modifica
# ai parametri live.
#
# Perche' esiste: la storia del progetto mostra 7 riscritture in 8 settimane,
# nessuna delle quali preceduta da una validazione. Ora la validazione e' un
# comando, non un'opinione.
#
# Uso:
#   bash scripts/validate.sh                       # valida tutte le config LIVE
#   bash scripts/validate.sh config/node_mc2.yaml  # valida una config
#
# Esce 0 solo se TUTTE le config validate hanno alpha >= 0 vs buy&hold
# sull'orizzonte testato. In caso contrario esce 1 e stampa il verdetto.
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

DAYS="${DAYS:-90}"
TIMEFRAME="${TIMEFRAME:-5m}"
OUT_DIR="${OUT_DIR:-backtest_out/validation}"
mkdir -p "$OUT_DIR"

if [ "$#" -gt 0 ]; then
  CONFIGS=("$@")
else
  # Solo le config con bot realmente live.
  CONFIGS=(config/node_mc2.yaml config/node_trend_live_kraken.yaml)
fi

FAIL=0
for cfg in "${CONFIGS[@]}"; do
  name="$(basename "$cfg" .yaml)"
  json="$OUT_DIR/$name.json"
  echo "───────────────────────────────────────────────"
  echo "VALIDATE $cfg  (giorni=$DAYS, timeframe=$TIMEFRAME)"
  python -m denaro.backtest --config "$cfg" --days "$DAYS" --timeframe "$TIMEFRAME" --json "$json" || {
    echo "  !! backtest fallito per $cfg"; FAIL=1; continue;
  }
  python - "$json" <<'PY'
import json, sys
try:
    data = json.load(open(sys.argv[1]))
except Exception as exc:
    print(f"  !! output non leggibile: {exc}"); sys.exit(1)
items = data if isinstance(data, list) else data.get("results", [data])
bad = []
for r in items:
    sym = r.get("symbol", "?")
    ret = r.get("return_pct", r.get("roi"))
    bh = r.get("buy_hold_pct", r.get("benchmark_pct"))
    alpha = None
    if ret is not None and bh is not None:
        alpha = ret - bh
    verdict = "OK" if (alpha is not None and alpha >= 0) else "REJECT"
    if verdict == "REJECT":
        bad.append(sym)
    print(f"  {sym:<12} ret={ret} bh={bh} alpha={alpha} maxDD={r.get('max_drawdown_pct')} -> {verdict}")
sys.exit(1 if bad else 0)
PY
  [ $? -ne 0 ] && FAIL=1
done

echo "───────────────────────────────────────────────"
if [ $FAIL -ne 0 ]; then
  echo "VERDETTO: REJECT — una o piu' config non battono il buy&hold."
  echo "NON promuovere a live con capitale reale."
  exit 1
fi
echo "VERDETTO: PASS — tutte le config validate hanno alpha >= 0."
