#!/usr/bin/env python3
"""Test CircularBuffer tipizzato (maxlen rigido + statistiche)."""
import unittest

from denaro.domain.circular import CircularBuffer


class TestCircularBuffer(unittest.TestCase):
    def test_maxlen_rigido(self):
        b = CircularBuffer(maxlen=5)
        for v in range(10):
            b.append(float(v))
        self.assertEqual(len(b), 5)
        self.assertEqual(b.to_list(), [5.0, 6.0, 7.0, 8.0, 9.0])
        self.assertTrue(b.is_full)

    def test_capacita_non_piena(self):
        b = CircularBuffer(maxlen=10)
        b.extend([1.0, 2.0, 3.0])
        self.assertEqual(len(b), 3)
        self.assertFalse(b.is_full)
        self.assertEqual(b.to_list(), [1.0, 2.0, 3.0])

    def test_mean_std(self):
        b = CircularBuffer(maxlen=100)
        b.extend([1.0, 2.0, 3.0, 4.0, 5.0])
        self.assertAlmostEqual(b.mean(), 3.0, places=9)
        self.assertAlmostEqual(b.std(), 1.5811388300841898, places=6)

    def test_min_max_sum(self):
        b = CircularBuffer(maxlen=10)
        b.extend([3.0, 1.0, 2.0])
        self.assertEqual(b.min(), 1.0)
        self.assertEqual(b.max(), 3.0)
        self.assertEqual(b.sum(), 6.0)

    def test_initial(self):
        b = CircularBuffer(maxlen=3, initial=[1.0, 2.0, 3.0, 4.0])
        self.assertEqual(b.to_list(), [2.0, 3.0, 4.0])

    def test_clear(self):
        b = CircularBuffer(maxlen=3, initial=[1.0, 2.0])
        b.clear()
        self.assertEqual(len(b), 0)
        self.assertEqual(b.last(), None)

    def test_last(self):
        b = CircularBuffer(maxlen=3)
        b.append(7.0)
        self.assertEqual(b.last(), 7.0)

    def test_invalid_maxlen(self):
        with self.assertRaises(ValueError):
            CircularBuffer(maxlen=0)

    def test_empty_statistics(self):
        b = CircularBuffer(maxlen=5)
        self.assertEqual(b.mean(), 0.0)
        self.assertEqual(b.std(), 0.0)
        self.assertEqual(b.sum(), 0.0)


if __name__ == "__main__":
    unittest.main()
