# Guida passo-passo — Ponte Hermes ↔ DeepSeek (Alpha-Omega)

## Cos'è
Ponte asincrono su file per lo scambio di dati/opinioni tra **Hermes AI** (su mc2) e l'**agente DeepSeek** (questa sessione). Nessuno dei due ha un'identità esterna: si incontrano sull'infrastruttura, precisamente su mc2.

| Elemento | Path su mc2 |
|---|---|
| **INBOX** (Hermes → DeepSeek) | `/home/sergio/hermes_bridge/inbox.md` |
| **OUTBOX** (DeepSeek → Hermes) | `/home/sergio/hermes_bridge/outbox.md` |
| Istruzioni per Hermes | `/home/sergio/hermes_bridge/README.md` |

## Prerequisiti (già completati)
1. Ponte creato su mc2: cartella `/home/sergio/hermes_bridge/` con `inbox.md`, `outbox.md`, `README.md` (file scrivibili, `chmod 666`).
2. mc2 raggiungibile da MARCODG1 con `ssh -p 2222 sergio@127.0.0.1`.
3. Hermes attivo (gateway HTTP `:8642`, canale **Telegram** DM di Sergio, id `277954993`).

## Flusso completo in 5 passi

### Passo 1 — Tu chiedi a Hermes di contattarmi (Telegram)
Invia a Hermes su Telegram questo messaggio (pronto all'uso):

> Hermes, contatta l'agente DeepSeek del progetto Alpha-Omega: scrivi il tuo messaggio in `/home/sergio/hermes_bridge/inbox.md` con formato `[AAAA-MM-GG HH:MM] testo`. Le sue risposte sono in `/home/sergio/hermes_bridge/outbox.md`.

### Passo 2 — Hermes scrive in INBOX
Hermes (o tu, via terminale su mc2) aggiunge il messaggio in coda:

```bash
printf '\n[%s] Ciao DeepSeek, sono Hermes. Test ponte.\n' "$(date '+%Y-%m-%d %H:%M')" >> /home/sergio/hermes_bridge/inbox.md
```

### Passo 3 — Io leggo e rispondo
- Tu mi scrivi qui nel pannello: **"controlla la inbox"**.
- Io leggo `inbox.md` via SSH (tunnel da MARCODG1), analizzo e **rispondo in `outbox.md`** (append, stesso formato `[AAAA-MM-GG HH:MM] testo`).

### Passo 4 — Hermes ti consegna la mia risposta
Su mc2, Hermes (o tu) esegue:

```bash
cat /home/sergio/hermes_bridge/outbox.md
hermes send -t telegram "📬 Nuova risposta di DeepSeek in /home/sergio/hermes_bridge/outbox.md"
```

### Passo 5 — Verifica del giro completo
1. Hermes scrive un messaggio di prova in `inbox.md`.
2. Tu mi dici "controlla la inbox".
3. Io rispondo in `outbox.md`.
4. Hermes ti consegna la risposta su Telegram.
→ Ponte verificato in **entrambe le direzioni**.

## Regole del ponte
- **Solo append, mai cancellare** i file (leggere la coda dall'ultimo timestamp letto).
- Formato riga: `[AAAA-MM-GG HH:MM] messaggio`.
- Separare i messaggi con una riga vuota.
- Se un file sparisce, ricrearlo con header `# Inbox Hermes -> DeepSeek` / `# Outbox DeepSeek -> Hermes`.

## Automazione opzionale (consigliata)
Cron su mc2 ogni minuto: se `outbox.md` risulta modificato dall'ultima notifica, invia su Telegram `hermes send -t telegram "📬 Nuova risposta di DeepSeek"`. Installabile su richiesta — elimina il Passo 4 manuale.

## Troubleshooting
| Problema | Verifica |
|---|---|
| Hermes non trova i file | `ls -la /home/sergio/hermes_bridge/` |
| `hermes send` non invia | `hermes send -t telegram "test ponte"`; controlla token in `~/.hermes/.env` |
| Telegram non riceve | canale configurato = DM id `277954993`; verifica che il bot sia avviato |
| File non scrivibili | `chmod 666 /home/sergio/hermes_bridge/*.md` |
