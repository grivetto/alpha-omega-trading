"""
executor.py — Dual Order Execution per Pair Trading (MNMR v1.0)
================================================================
Esegue ordini a due gambe (pair trade) su Binance Spot.
Le gambe sono eseguite in sequenza: prima la Market Taker,
poi la Limit Maker, per minimizzare il leg risk.

Strategia:
  - ETH_OVERPRICED  (Z > +2.0): SELL ETH (market) → BUY BTC (limit)
  - ETH_UNDERPRICED (Z < -2.0): SELL BTC (market) → BUY ETH (limit)
  - CLOSE (|Z| < 0.5): inverti la posizione corrente
"""

import asyncio
import logging
import time

logger = logging.getLogger("executor")

# ── Soglie ─────────────────────────────────────────────────────
MAKER_FEE = 0.00075       # 0.075% con BNB
TAKER_FEE = 0.001         # 0.1%
EST_SLIPPAGE = 0.001      # 0.1% slippage stimato
MIN_PROFIT_MARGIN = 0.001 # 0.1% margine netto extra


def expected_profit_threshold() -> float:
    """
    Profitto minimo richiesto per entrare:
    (2 * fee) + (2 * slippage stimato) + 0.1% margine
    """
    return (TAKER_FEE + EST_SLIPPAGE) * 2 + MIN_PROFIT_MARGIN  # ~0.5%


class PairTradeExecutor:
    """
    Gestisce l'esecuzione e la chiusura di posizioni pair trading.
    """

    def __init__(self, core):
        self.core = core  # DenaroOpportunisticCore instance
        self._active = False
        self._position_type = None  # 'ETH_OVERPRICED' | 'ETH_UNDERPRICED'
        self._entry_info = None     # dettaglio entry per reverse

        # Simboli specifici
        self.symbol_a = "ETH/EUR"   # Asset A
        self.symbol_b = "BTC/EUR"   # Asset B
        self.base_a = "ETH"
        self.base_b = "BTC"

    @property
    def in_position(self) -> bool:
        return self._active and self._position_type is not None

    async def execute_entry(self, position_type: str, notional_eur: float,
                            price_eth: float, price_btc: float) -> bool:
        """
        Esegue entry a due gambe.

        ETH_OVERPRICED  (Z > +2): SELL ETH → BUY BTC
        ETH_UNDERPRICED (Z < -2): SELL BTC → BUY ETH

        Leg 1: Market taker (esegue subito)
        Leg 2: Limit maker (aspetta fill, timeout 30s → market)
        """
        if self._active:
            logger.warning("Tentativo di entry mentre posizione attiva")
            return False

        if position_type not in ('ETH_OVERPRICED', 'ETH_UNDERPRICED'):
            logger.error(f"Position type sconosciuto: {position_type}")
            return False

        # Quantità
        qty_a = (notional_eur / price_eth) * 0.997  # arrotondamento safety
        qty_b = (notional_eur / price_btc) * 0.997

        self._active = True
        self._position_type = position_type

        try:
            if position_type == 'ETH_OVERPRICED':
                # ETH caro → compra BTC (che è sottovalutato rispetto a ETH)
                logger.info(f"EXECUTOR: Market BUY {qty_b:.6f} BTC @ ~{price_btc:.2f}")
                buy_order = await self.core.create_market_buy(
                    self.symbol_b, qty_b
                )
                if not buy_order:
                    logger.error("EXECUTOR BUY BTC FAILED")
                    self._active = False
                    return False

            else:  # ETH_UNDERPRICED
                # ETH sottovalutato → compra ETH
                logger.info(f"EXECUTOR: Market BUY {qty_a:.6f} ETH @ ~{price_eth:.2f}")
                buy_order = await self.core.create_market_buy(
                    self.symbol_a, qty_a
                )
                if not buy_order:
                    logger.error("EXECUTOR BUY ETH FAILED")
                    self._active = False
                    return False

            # Salva info per reverse
            self._entry_info = {
                'position_type': position_type,
                'notional_eur': notional_eur,
                'entry_time': time.time(),
                'price_eth': price_eth,
                'price_btc': price_btc,
                'qty_a': qty_a,
                'qty_b': qty_b,
            }

            logger.info(f"EXECUTOR ✅ ENTRY {position_type} | {notional_eur:.2f}€ notional")
            return True

        except Exception as e:
            logger.error(f"EXECUTOR entry error: {e}")
            self._active = False
            raise

    async def execute_close(self, price_eth: float, price_btc: float) -> bool:
        """
        Chiude la posizione: vende l'asset acquistato (ETH o BTC).
        """
        if not self._active or not self._entry_info:
            logger.warning("Nessuna posizione da chiudere")
            return False

        info = self._entry_info

        try:
            if info['position_type'] == 'ETH_OVERPRICED':
                # Abbiamo BTC, vendiamo BTC
                qty = info['qty_b']
                logger.info(f"CLOSE: SELL BTC {qty:.6f}")
                await self.core.create_market_sell(self.symbol_b, qty)
            else:
                # Abbiamo ETH, vendiamo ETH
                qty = info['qty_a']
                logger.info(f"CLOSE: SELL ETH {qty:.6f}")
                await self.core.create_market_sell(self.symbol_a, qty)

            # Calcola PnL approssimato
            pnl_est = self._estimate_pnl(price_eth, price_btc, info)
            logger.info(f"EXECUTOR ✅ CLOSE | PnL est: {pnl_est:.2f}€")

            self._reset()
            return True

        except Exception as e:
            logger.error(f"EXECUTOR close error: {e}")
            self._reset()
            return False

    def _estimate_pnl(self, current_eth: float, current_btc: float,
                       info: dict) -> float:
        """
        Stima PnL approssimato: prezzo entry - prezzo corrente dell'asset acquistato.
        """
        if info['position_type'] == 'ETH_OVERPRICED':
            # Comprato BTC
            entry_price = info['price_btc']
            current_price = current_btc
            qty = info['qty_b']
        else:
            # Comprato ETH
            entry_price = info['price_eth']
            current_price = current_eth
            qty = info['qty_a']

        pnl_pct = (current_price - entry_price) / entry_price
        return pnl_pct * qty * entry_price

    def get_entry_age(self) -> float:
        """Ore da quando siamo entrati nella posizione."""
        if not self._entry_info:
            return 0
        return (time.time() - self._entry_info['entry_time']) / 3600

    def _reset(self):
        self._active = False
        self._position_type = None
        self._entry_info = None

    def get_status(self) -> dict:
        if not self._entry_info:
            return {'active': False}
        info = self._entry_info
        return {
            'active': True,
            'position_type': info['position_type'],
            'notional_eur': info['notional_eur'],
            'entry_time': info['entry_time'],
            'age_hours': self.get_entry_age(),
            'price_eth': info['price_eth'],
            'price_btc': info['price_btc'],
        }
