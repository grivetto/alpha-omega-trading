#!/usr/bin/env python3
"""Test del rate limiter (token bucket) — deterministici con `now` iniettato."""
import unittest

from denaro.infrastructure.rate_limiter import RateLimiterRegistry, TokenBucket


class TestTokenBucket(unittest.TestCase):
    def test_burst_iniziale_pieno(self):
        b = TokenBucket(capacity=10.0, refill_rate=5.0, now=0.0)
        # burst iniziale: tutti i token disponibili subito
        for _ in range(10):
            self.assertTrue(b.try_acquire(1.0, now=0.0))
        self.assertFalse(b.try_acquire(1.0, now=0.0))  # vuoto

    def test_refill_nel_tempo(self):
        b = TokenBucket(capacity=10.0, refill_rate=5.0, now=0.0)
        for _ in range(10):
            b.try_acquire(1.0, now=0.0)
        # dopo 1 secondo → 5 token rigenerati
        for _ in range(5):
            self.assertTrue(b.try_acquire(1.0, now=1.0))
        self.assertFalse(b.try_acquire(1.0, now=1.0))

    def test_wait_time(self):
        b = TokenBucket(capacity=1.0, refill_rate=1.0, now=0.0)
        b.try_acquire(1.0, now=0.0)
        # deficit di 1 token a rate 1/s → attesa 1s
        self.assertAlmostEqual(b.wait_time(1.0, now=0.0), 1.0, places=6)
        self.assertEqual(b.wait_time(1.0, now=2.0), 0.0)

    def test_acquire_multi_token(self):
        b = TokenBucket(capacity=10.0, refill_rate=1.0, now=0.0)
        self.assertTrue(b.try_acquire(5.0, now=0.0))
        self.assertFalse(b.try_acquire(6.0, now=0.0))
        self.assertTrue(b.try_acquire(5.0, now=0.0))

    def test_capacity_mai_superata(self):
        b = TokenBucket(capacity=10.0, refill_rate=5.0, now=0.0)
        b.try_acquire(1.0, now=0.0)
        # restano 9; dopo 10s il refill riporta al massimo 10 (non di piu')
        self.assertAlmostEqual(b.available, 9.0, places=6)
        b.wait_time(0, now=10.0)  # forza refill
        self.assertAlmostEqual(b.available, 10.0, places=6)

    def test_invalid_params(self):
        with self.assertRaises(ValueError):
            TokenBucket(0, 1.0)
        with self.assertRaises(ValueError):
            TokenBucket(1.0, 0)

    def test_registry(self):
        reg = RateLimiterRegistry()
        b = reg.register("okx", 10.0, 5.0)
        self.assertIs(reg.get("okx"), b)
        self.assertIsNone(reg.get("kraken"))
        self.assertIsNotNone(reg.async_bucket("okx"))
        self.assertIsNone(reg.async_bucket("kraken"))


if __name__ == "__main__":
    unittest.main()
