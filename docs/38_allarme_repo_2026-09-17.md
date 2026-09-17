# 38 — Il codice che gira e' quello committato? Ora si vede (round 36)

## 38.1 Perche'

I nodi eseguono i **file del repo**. Una modifica non committata cambia il
comportamento VERO del sistema che muove denaro, senza lasciare traccia nella
storia: nessuno se ne accorge fino al prossimo riavvio — o mai. Il 2026-09-17 e'
successo due volte mentre il resto del lavoro era gia' committato
(`tools/fetch_universe.py` su nuvola, `tools/trend_4h_venue.py` su mc2), e in
un caso un `.gitignore` vecchio su mc2 aveva perfino smesso di ignorare
`backtest_data/` e `denaro/health/`.

## 38.2 Cosa

- `denaro/infra_repo.py`: per ogni macchina, `git rev-parse --short HEAD` e
  `git status --porcelain | wc -l`, con le coordinate ssh corrette per host.
  Se una macchina non risponde il valore e' **None (non lo so)**, mai un falso
  zero: "repo pulito" e "non raggiungibile" non devono confondersi.
- L'aggregator mette il blocco `repo` nel payload (`data["repo"]`).
- La dashboard, sotto ogni nodo, mostra `HEAD <commit> · REPO PULITO` in verde
  oppure `REPO: N MODIFICHE NON COMMITTATE` in rosso.

E' un controllo di **visibilita', non di auto-riparazione**: un repo sporco non
si "aggiusta" da solo (si cancellerebbe il lavoro di qualcuno).

## 38.3 Verifica

- **5 test** (`denaro/tests/test_infra_repo.py`): parsing, lettura fallita ->
  None, eccezione -> None, ssh con BatchMode, comando locale che cita il repo.
  Suite: **333 passed, 3 skipped**.
- Live (23:49 UTC): il payload dell'aggregator di MARCODG1 porta le tre macchine

      marcodg1 HEAD 71d0980 dirty 0
      mc2      HEAD 71d0980 dirty 1   <- la modifica non committata c'e' davvero
      nuvola   HEAD 71d0980 dirty 0

  cioe' la funzione ha trovato subito il caso reale: su mc2
  `tools/trend_4h_venue.py` risulta modificato rispetto al commit.
- Bug mio trovato e corretto nello stesso round: con l'aggregator in esecuzione
  su mc2 (non su MARCODG1) il marcodg1 aveva coordinate `None` e il blocco
  andava in errore (`cannot unpack non-iterable NoneType`) invece di leggere il
  repo remoto. Ora ogni macchina ha le sue coordinate ssh
  (`5345a4f`).

Commit: `71d0980` (funzione) e `5345a4f` (coordinate).
