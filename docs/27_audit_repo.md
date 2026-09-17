# 27 — Audit del repository (round 25)

Prima meta' dell'obiettivo: "riorganizzare completamente il repo git (branch,
junk tracciato, worktree, storia)". Verificata con numeri, non data per fatta.

## 27.1 Stato attuale

| voce | valore |
|---|---|
| branch locali | 1 (main) |
| branch remoti | 1 (origin/main) |
| tag | 21 |
| worktree | 1 |
| commit | 395 |
| merge commit in main | 5 |
| file tracciati | 287 |
| file generati/log/cache tracciati | **0** |
| file > 1 MB tracciati | 0 |
| segreti tracciati | 0 (solo .env.example) |
| dimensione .git | 11 MB |
| primo commit | 2026-05-02 |
| ultimo commit | 2026-09-18 |

## 27.2 Cosa era stato fatto e tiene

- **Un solo ramo**: main. Le altre linee (feature/dev/Harness139/Manus926/
  production-ready/v4/v6/consolidation) sono conservate come **tag archive/***,
  non come rami vivi: la storia non si perde, ma non ci sono rami da mantenere.
- **Tag versionati** (v2.0.0, v2.3.0, v3.0.0-denaro, v6-DeepSeek, v7-Brain)
  agganciati sulla linea di main, piu' Prod-Stable.
- **Un solo worktree**: nessuna copia di lavoro dimenticata.
- **Zero junk tracciato**: 287 file, nessun __pycache__, node_data, health,
  journal, log, sqlite o backup. Il .gitignore copre node_data/, .env,
  health/*.json (anche denaro/health/, che prima sfuggiva perche' il pattern
  era ancorato alla radice).
- **Zero segreti**: l'unico file che somiglia a un .env e' .env.example, che e'
  un template da versionare.

Verifica riproducibile: `git ls-files | grep -cE "(__pycache__|\.pyc$|node_data|/health/[^/]*\.json$|\.jsonl$|/logs/|\.log$|\.sqlite|\.db$|^\.env|\.bak$|\.tmp$)"`
restituisce 1, e quel 1 e' .env.example.

## 27.3 Un residuo nella storia, lasciato di proposito

Gli oggetti piu' grandi nella storia sono quattro CSV in una cartella poi
cancellata:

    _dead/dollari/backtester/data/ADA_USDT_1m.csv   2.3 MB
    _dead/dollari/backtester/data/SOL_USDT_1m.csv   2.1 MB
    _dead/dollari/backtester/data/DOT_USDT_1m.csv   2.1 MB
    _dead/dollari/backtester/data/LINK_USDT_1m.csv  1.9 MB

Sono circa **8 MB degli 11** di .git. **Non sono piu' tracciati** (0 file in
HEAD): vivono solo nella storia.

Toglierli richiederebbe una **riscrittura della storia** (git-filter-repo/BFG),
che cambia tutti gli hash, invalida i 21 tag, richiede un force-push e un
re-clone su tre macchine. Il guadagno e' 8 MB su un repository che non ha
problemi di dimensione; il rischio e' rompere la storia condivisa su un progetto
con piu' autori.

**Scelta: non si riscrive la storia.** Il residuo e' documentato e innocuo.

## 27.4 Guardrail aggiunto

`_dead/` era tracciabile (non coperto dal .gitignore). Aggiunto: se un domani
qualcuno ricreasse quella cartella, non finirebbe dentro git.
