class CircuitBreakerOpen(Exception):
    pass


class TradingError(Exception):
    pass


class NetworkError(Exception):
    pass


class PositionError(Exception):
    pass


__all__ = ["CircuitBreakerOpen", "TradingError", "NetworkError", "PositionError"]