# Airdrop Farm — €100 Budget

## Filosofia

Asymmetric bet: perdi al massimo €100, puoi guadagnare €1.5K–80K.
Nessun guadagno giornaliero — è una scommessa a 6-12 mesi.
Cinque strategie parallele, un solo orchestrator.

## Budget (12 mesi)

| Strategia | Budget | Dettaglio |
|-----------|--------|-----------|
| **Airdrop farming** | €47 | Gas 4 chain × 10 wallet × 4 tx/m × 12m (€28) + VPS Hetzner CAX11 €4/m × 6m (€19) |
| **Hyperliquid points** | €30 | Bridge Arbitrum→Hyperliquid ($2) + stake/LP/trading ($28) |
| **Yield fondi inattivi** | €10 | Aave/Lido supply su idle balance |
| **Monad activity** | €8 | Gas su Monad mainnet (penny tx) per retroactive airdrop S2 |
| **Launchpad MEXC** | €5 | BNB/MX su exchange per IDO |
| **TOTALE** | **€100** | |

## Wallet: 20 indipendenti

- **Singolo seed BIP39 master** + passphrase opzionale
- Derivation path: `m/44'/60'/0'/0/{0..19}`
- Wallet 0-9 → Airdrop farming (4 chain)
- Wallet 10-12 → Hyperliquid points
- Wallet 13-15 → Monad mainnet activity (MON già airdroppato, farm per Season 2)
- Wallet 16-19 → Riserva / Launchpad
- Seed cifrata **Fernet (AES-256-CBC)** su file, decrypt solo in RAM per firma

## Chain per Airdrop Farming

| # | Chain | Tipo | Token? | TVL | Gas/tx |
|---|-------|------|--------|-----|--------|
| 1 | Base | L2 OP Stack | ❌ No | $3B+ | $0.01 |
| 2 | Scroll | zkEVM | ❌ No | medium | $0.02 |
| 3 | Abstract | L2 Consumer | ❌ No | $23M | $0.01 |
| 4 | Linea | zkEVM Consensys | ❌ No | medium | $0.02 |

> **Monad ESCLUSO**: token MON già lanciato (24 nov 2025, airdrop 3.3B MON). Usato come chain economica per yield/activity (Strategia 4), non airdrop.

## Azioni per wallet (Airdrop) — 3-4/mese

| Azione | Frequenza | Protocolli |
|--------|-----------|------------|
| Swap | 1-2/mese | Uniswap, Sushi, Aerodrome, PancakeSwap |
| Bridge | 0-1/mese | Across, Stargate, Hop |
| LP (add/remove) | 1/mese | Curve, Balancer, Aerodrome, Velodrome |
| Stake/unstake | 0.5/mese | Lido, EigenLayer, Symbiotic |
| NFT mint/collect | 0.5/mese | Zora, Manifold |
| Governance vote | 0-1/mese | Snapshot |

## Strategia 2: Hyperliquid Points (Season 3)

- Capitale: €30 (~$32)
- Bridge: Arbitrum → Hyperliquid ($1-2)
- Azioni: Stake HYPE (2.22% APY), LP KittenSwap feUSD/USDT (2-5x multiplier), Liminal delta-neutral, Spot/Perps organico, .hl domain (140x)
- Yield reale 2-4% APY mentre accumuli punti
- HYPE già tokenizzato ma Season 3 points danno fee discount + potenziali reward

## Strategia 3: Yield su Fondi Inattivi

- Idle balance dei wallet mainnet → auto-deposit in Aave v3 (stable) o Lido (stETH)
- 3-5% APY stablecoin, 2-3% ETH
- Withdraw automatico quando serve gas per azione successiva

## Strategia 4: Monad Mainnet Activity

- MON già lanciato, ma Monad fa Season 2/staking rewards
- Gas bassissimo (pennies) → 10 tx/mese costo irrisorio
- 3 wallet (13-15) fanno: DEX swap, LP su Curvance/Marginfi, bridge via Relay
- Se Monad fa Season 2 retroactive → si qualificano

## Strategia 5: Launchpad MEXC

- €5 in MX token su MEXC
- Partecipazione automatica a nuovi IDO

## Architettura

```
airdrop-farm/
├── core/
│   ├── wallet_vault.py      # BIP39 seed → 20 wallet, Fernet encrypt
│   ├── config.yaml          # Configurazione centralizzata
│   └── orchestrator.py      # Main loop, scheduler centrale
├── strategies/
│   ├── base_strategy.py     # Classe astratta Strategy
│   ├── airdrop/
│   │   ├── engine.py        # Poisson timing, action selection
│   │   ├── actions.py       # swap, bridge, LP, stake, mint, vote
│   │   └── sybil.py         # Anti-detection patterns
│   ├── points/
│   │   └── hyperliquid.py   # Stake HYPE, LP KittenSwap, Liminal
│   ├── yield/
│   │   └── auto_lend.py     # Aave supply / Lido stake idle balance
│   └── monad/
│       └── activity.py      # DEX swap, LP, bridge su Monad
├── chains/
│   ├── base_connector.py    # Classe astratta
│   ├── base.py
│   ├── scroll.py
│   ├── abstract.py
│   ├── linea.py
│   ├── monad.py
│   └── hyperliquid.py
├── activity/
│   ├── models.py            # SQLAlchemy models
│   └── tracker.py           # Log tx, gas, points, yield
├── monitoring/
│   └── telegram_bot.py      # Alert real-time + report
├── tests/
├── main.py
├── requirements.txt
└── .env.example
```

## Principi Tecnici

1. **Isolamento wallet**: nessun wallet condivide tx con un altro della stessa strategy
2. **Poisson timing**: `random.expovariate(1/mean_hours)`, clamp [8h, 90h]
3. **Seed singolo BIP39**, 20 wallet con derivation path diverso
4. **Fernet encrypt** seed su file, decrypt solo in RAM durante firma
5. **Idempotenza**: ogni azione controlla nonce + stato on-chain prima di firmare
6. **Circuit breaker**: gas > 5x baseline → salta azioni su quella chain
7. **Telegram alert**: wallet senza gas, 3 failure, gas spike, report ore 8

## Timeline

| Data | Milestone |
|------|-----------|
| **23 lug** | Codice completo, test funzionanti |
| **24-26 lug** | Testnet su tutte le chain |
| **5 ago** | €100 su Kraken → bridge Base |
| **6 ago** | Deploy VPS, avvio orchestrator |
| **6 ago – 6 feb 27** | Farming attivo, monitor Telegram |

## Rischi e Mitigazione

| Rischio | Prob | Mitigazione |
|---------|------|-------------|
| Nessun airdrop | 30% | Budget cappato, 4 chain diverse |
| Sybil detection | 20% | Poisson timing, azioni diverse, isolamento wallet |
| Chain morta | 10% | 4 chain, rebalance automatico |
| Smart contract exploit | 3% | Solo protocolli audited + TVL > $50M |
| Hyperliquid points inutili | 25% | Yield reale 2-4% compensa |

## Ritorno Atteso (12 mesi)

| Scenario | Prob | Netto |
|----------|------|-------|
| Peggiore (tutto fallisce) | 15% | −€100 |
| Solo yield + launchpad | 15% | +€50–200 |
| 1 airdrop chain + punti | 25% | +€1K–5K |
| 2 airdrop chain + punti | 25% | +€5K–15K |
| 3+ airdrop + tutto allinea | 20% | +€15K–80K |

**Valore atteso: ~€7.000** con rischio massimo **€100**.

---

*23 luglio 2026 — Monad rimosso da airdrop (token già lanciato), 4 chain tokenless verificate.*
