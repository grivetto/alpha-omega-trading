# Dashboard pubblica (denaro.grivetto.eu)

Sorgente della dashboard servita da mc2 su `/var/www/denaro/index.html`
(Cloudflare → `denaro.grivetto.eu`). I dati arrivano da `data/combined.json`,
rigenerato ogni 5 minuti da `tools/gen_dashboard.py` (via aggregatore MARCODG1
`:8912`; il file aggiornato è su mc2 in `/var/www/denaro/data/combined.json`).

Deploy di una modifica: copiare `index.html` in `/var/www/denaro/index.html`
su mc2, poi ricaricare la pagina e verificare (nessun build).

Cronologia recente:
- 03/10/2026 — rimosse le etichette Kraken (account chiuso); subline "OKX …" condizionale.
  I prezzi DOGE/USDC ora sono valorizzati a monte nel generatore (`completa_prezzi`),
  quindi il totale include hedge del canary e stablecoin (≈ +13 € rispetto a prima).
