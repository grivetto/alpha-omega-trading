# 46 — Mandato: 50 EUR sulla scommessa asimmetrica

Data: 2026-09-18. Decisione del proprietario: **50 EUR all'airdrop farm**.

## 46.1 Una correzione strutturale: un wallet, non venti

Il DESIGN prevede 20 wallet dallo stesso seed. Con 100 EUR erano 5 EUR a wallet;
con **50 EUR sarebbero 2,50 EUR a wallet**: sotto qualunque soglia di attivita'
utile, e con il rischio sybil massimo (20 wallet correlati per costruzione).

Con 50 EUR la forma giusta e' **1 wallet fatto bene**, eventualmente 2 in una
seconda fase. Non e' una riduzione di ambizione: e' l'unica configurazione in cui
50 EUR possono produrre attivita' on-chain credibile invece di venti tracce
irrilevanti e correlate.

Conseguenza da accettare: un wallet e' **un biglietto della lotteria**. Il caso
centrale resta 0. Il senso sta nella coda, non nella media. Se la strategia premia
l'ampiezza, un wallet non basta — ma con 50 EUR l'ampiezza non e' comprabile,
e comprarla finta e' il modo migliore per essere filtrati.

## 46.2 Stato dell'infrastruttura esistente

| pezzo | stato |
|---|---|
| WalletVault (eth_account HD + Fernet) | codice presente, **nessun vault creato** |
| .env | MNEMONIC e FERNET_KEY **presenti** |
| config.yaml | real_capital 100, max_wallets 20 (da riscrivere: 1 wallet, 50 EUR) |
| connettori chain | 28-36 righe = **stub, nessuna esecuzione reale** |
| servizi | disabled, mai avviati |
| activity.db | fermo al 25 luglio |

## 46.3 I bersagli, dopo la verifica di oggi

- **Scroll**: token gia' lanciato, airdrop distribuito (7% della supply). **Fuori.**
- **Linea**: distribuzione gia' avvenuta. **Fuori.**
- **Base**: l'unica ancora pre-token con speculazione viva ("calculator" che stima
  potenziale a 5 cifre). **E' il bersaglio.** Ma ha annunciato strumenti anti-bot
  on-chain e un requisito di **staking per gli account nuovi entro ottobre**: da
  verificare *prima* di finanziare, perche' cambia le azioni da fare.
- **Monad, Abstract, Hyperliquid**: da rivalutare uno per uno, non in blocco.

## 46.4 Regole del mandato

1. **Tetto di perdita: 50 EUR.** Nessun reintegro, nessuna ricarica, nessuna
   eccezione. Se finiscono, la scommessa e' finita.
2. **Un wallet con seed indipendente**, non il mnemonic condiviso del vault.
3. **Nessun protocollo fuori da TVL > 50M e contratti auditati.**
4. **Nessun movimento di denaro senza il via del proprietario.**
5. Ogni azione on-chain tracciata in activity.db con tx hash, gas e scopo.

## 46.5 Prossimi passi, in ordine

1. Verificare i requisiti Base (anti-bot, staking, finestra temporale) e decidere
   le azioni minime che qualificano.
2. Creare il wallet unico con seed nuovo e metterlo al sicuro.
3. Scrivere il layer di esecuzione on-chain reale: firma locale, invio, verifica,
   gestione gas, idempotenza. E' il 90% del lavoro e oggi non esiste.
4. Provare tutto in dry-run sulla chain scelta.
5. Solo dopo: prelevare i 50 EUR e iniziare.
