"""Custom exceptions for the multi-agent trading system."""


class DenaroError(Exception):
    """Base exception for all Denaro system errors."""
    pass


class LLMInferenceError(DenaroError):
    """Raised when the LLM endpoint fails or returns an unexpected response."""
    def __init__(self, message: str, endpoint: str = "", status_code: int = 0):
        self.endpoint = endpoint
        self.status_code = status_code
        super().__init__(f"[{endpoint}] {message} (HTTP {status_code})")


class LLMTimeoutError(LLMInferenceError):
    """Raised when the LLM endpoint times out."""
    def __init__(self, endpoint: str = "", timeout: int = 0):
        super().__init__(f"LLM endpoint timed out after {timeout}s", endpoint=endpoint)


class RiskVetoError(DenaroError):
    """Raised when the Risk Manager vetoes an execution."""
    def __init__(self, symbol: str, reason: str):
        self.symbol = symbol
        self.reason = reason
        super().__init__(f"[{symbol}] Risk veto: {reason}")


class ExchangeConnectionError(DenaroError):
    """Raised when the exchange connection fails."""
    def __init__(self, exchange: str, message: str):
        self.exchange = exchange
        super().__init__(f"[{exchange}] Connection error: {message}")


class InvalidMarketStateError(DenaroError):
    """Raised when market data is insufficient or malformed."""
    pass


class AgentCommunicationError(DenaroError):
    """Raised when inter-agent message passing fails."""
    def __init__(self, source: str, target: str, message: str):
        super().__init__(f"[{source}->{target}] {message}")
