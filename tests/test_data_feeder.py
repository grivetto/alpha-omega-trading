"""Tests for Denaro v3 Data Feeder."""

import pytest
from unittest.mock import MagicMock
from denaro_v3.config import APIConfig
from denaro_v3.data_feeder import DataFeeder


@pytest.fixture
def mock_exchange():
    ex = MagicMock()
    ex.fetch_balance.return_value = {
        "USDC": {"free": 100.0, "used": 0.0, "total": 100.0},
        "SOL": {"free": 0.5, "used": 0.0, "total": 0.5},
    }
    ex.fetch_ticker.return_value = {"last": 100.0}
    ex.fetch_ohlcv.return_value = [[0, 0, 100, 99, 99.5, 10] for _ in range(15)]
    ex.fetch_open_orders.return_value = []
    return ex


@pytest.fixture
def feeder(mock_exchange):
    return DataFeeder(mock_exchange, APIConfig())


class TestCaching:
    def test_balance_is_cached(self, feeder, mock_exchange):
        b1 = feeder.get_balance()
        b2 = feeder.get_balance()
        assert b1 == b2
        # Should only fetch once
        assert mock_exchange.fetch_balance.call_count == 1

    def test_ticker_is_cached(self, feeder, mock_exchange):
        t1 = feeder.get_ticker("SOL/USDC")
        t2 = feeder.get_ticker("SOL/USDC")
        assert t1 == t2
        assert mock_exchange.fetch_ticker.call_count == 1

    def test_ohlcv_is_cached(self, feeder, mock_exchange):
        o1 = feeder.get_ohlcv("SOL/USDC")
        o2 = feeder.get_ohlcv("SOL/USDC")
        assert o1 == o2
        assert mock_exchange.fetch_ohlcv.call_count == 1


class TestInvalidation:
    def test_trade_invalidates_balance(self, feeder, mock_exchange):
        feeder.get_balance()
        feeder.on_trade_executed()
        feeder.get_balance()
        assert mock_exchange.fetch_balance.call_count == 2

    def test_trade_invalidates_orders(self, feeder, mock_exchange):
        feeder.get_open_orders("SOL/USDC")
        feeder.on_trade_executed()
        feeder.get_open_orders("SOL/USDC")
        assert mock_exchange.fetch_open_orders.call_count == 2


class TestBalanceHelpers:
    def test_free_balance(self, feeder):
        assert feeder.get_free_balance("USDC") == 100.0
        assert feeder.get_free_balance("SOL") == 0.5

    def test_total_balance(self, feeder):
        assert feeder.get_total_balance("USDC") == 100.0
