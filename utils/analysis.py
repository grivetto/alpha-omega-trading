"""
analysis.py — Modulo di analisi statistica per la Squadra (MNMR v1.0)
===============================================================
Test di cointegrazione Engle-Granger + calcolo spread cointegrato + z-score.

Dipende da: statsmodels, numpy
"""

import numpy as np
from statsmodels.tsa.stattools import coint, adfuller
import statsmodels.api as sm
import logging

logger = logging.getLogger("analysis")

# ── Configurazione ─────────────────────────────────────────────
COINT_P_THRESHOLD = 0.05       # p-value per cointegrazione
Z_ENTRY = 2.0                   # soglia di ingresso
Z_EXIT = 0.5                    # soglia di uscita (mean reversion)
Z_EMERGENCY = 3.5               # stop-loss di divergenza
MIN_SAMPLE = 48                 # minimo campioni per test significativo
REFRESH_INTERVAL_HOURS = 24     # ricalcolo cointegrazione ogni 24h


class CointegrationEngine:
    """
    Motore di cointegrazione per pair trading (Engle-Granger).
    Calcola la relazione tra Asset_A e Asset_B, lo spread e lo z-score.
    """

    def __init__(self, p_threshold=COINT_P_THRESHOLD):
        self.p_threshold = p_threshold
        self._beta = None
        self._alpha = None
        self._spread_history = []
        self._last_coint_time = 0
        self._is_cointegrated = False
        self._last_p_value = 1.0

    def is_stale(self, now: float) -> bool:
        """Il test di cointegrazione è scaduto (>24h)?"""
        return (now - self._last_coint_time) > (REFRESH_INTERVAL_HOURS * 3600)

    def run_cointegration_test(self, prices_a: list, prices_b: list) -> dict:
        """
        Test di cointegrazione Engle-Granger completo.

        Argomenti:
            prices_a: List[float] — prezzi di chiusura Asset A (es. ETH)
            prices_b: List[float] — prezzi di chiusura Asset B (es. BTC)

        Returns:
            dict con: is_cointegrated, p_value, beta, alpha, z_score, spread
        """
        n = min(len(prices_a), len(prices_b))
        if n < MIN_SAMPLE:
            logger.warning(f"Campioni insufficienti per coint test: {n} < {MIN_SAMPLE}")
            return self._null_result()

        # Taglia alla stessa lunghezza
        a = np.array(prices_a[-n:])
        b = np.array(prices_b[-n:])

        # 1) Engle-Granger cointegration test
        _, p_value, _ = coint(a, b)

        # 2) Regressione OLS: Price_A = beta * Price_B + alpha
        X = sm.add_constant(b)
        model = sm.OLS(a, X).fit()
        self._beta = float(model.params[1])
        self._alpha = float(model.params[0])

        # 3) Spread = residui
        spread = a - (self._beta * b + self._alpha)

        # 4) ADF test sui residui (stazionarietà)
        adf_result = adfuller(spread, maxlag=1, autolag=None)
        adf_stat = float(adf_result[0])
        adf_pvalue = float(adf_result[1])

        # 5) Z-score dello spread
        spread_mean = float(np.mean(spread))
        spread_std = float(np.std(spread))
        current_z = (spread[-1] - spread_mean) / spread_std if spread_std > 0 else 0.0

        # Aggiorna stato interno
        self._is_cointegrated = p_value < self.p_threshold
        self._last_p_value = float(p_value)
        self._last_coint_time = __import__('time').time()
        self._spread_history = spread.tolist()[-96:]

        result = {
            'is_cointegrated': self._is_cointegrated,
            'p_value': float(p_value),
            'beta': self._beta,
            'alpha': self._alpha,
            'current_z': current_z,
            'spread_mean': spread_mean,
            'spread_std': spread_std,
            'spread': self._spread_history[-1] if self._spread_history else 0.0,
            'spread_history': self._spread_history,
            'adf_stat': adf_stat,
            'adf_pvalue': adf_pvalue,
            'sample_size': n,
        }

        logger.info(
            f"Cointegration test | p={p_value:.4f} | "
            f"{'✅ COINTEGRATED' if self._is_cointegrated else '❌ NOT COINTEGRATED'} | "
            f"β={self._beta:.4f} α={self._alpha:.2f} | "
            f"z={current_z:.2f} | ADF p={adf_pvalue:.4f}"
        )
        return result

    def compute_zscore(self, price_a: float, price_b: float) -> float:
        """
        Calcola z-score in tempo reale (senza ricalcolare cointegrazione).
        Usa gli ultimi beta/alpha salvati.
        """
        if self._beta is None or self._alpha is None or not self._spread_history:
            return 0.0

        current_spread = price_a - (self._beta * price_b + self._alpha)
        spread_mean = float(np.mean(self._spread_history))
        spread_std = float(np.std(self._spread_history))
        z = (current_spread - spread_mean) / spread_std if spread_std > 0 else 0.0

        # Aggiorna history rolling
        self._spread_history.append(current_spread)
        if len(self._spread_history) > 96:
            self._spread_history = self._spread_history[-96:]

        return z

    def get_status(self) -> dict:
        """Stato corrente del motore."""
        return {
            'cointegrated': self._is_cointegrated,
            'p_value': self._last_p_value,
            'beta': self._beta,
            'alpha': self._alpha,
            'last_test': self._last_coint_time,
            'spread_history_count': len(self._spread_history),
        }

    def _null_result(self) -> dict:
        return {
            'is_cointegrated': False,
            'p_value': 1.0,
            'beta': None,
            'alpha': None,
            'current_z': 0.0,
            'spread_mean': 0.0,
            'spread_std': 0.0,
            'spread': 0.0,
            'spread_history': [],
            'adf_stat': 0.0,
            'adf_pvalue': 1.0,
            'sample_size': 0,
        }
