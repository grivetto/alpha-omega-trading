"""
Social Sentiment Engine — multi-source sentiment analysis per i trading bot.

v1.0: Fear & Greed Index + X/Twitter search + news web fallback.

Fonti:
  1. Fear & Greed Index (alternative.me) — market-wide, sempre disponibile, no API key
  2. X/Twitter search (xurl CLI) — solo se autenticato, cerca post recenti sul symbol
  3. News web fallback — se X non disponibile, cerca news headlines via RSS/siti

Ogni fonte restituisce un score normalizzato (-1 bearish, +1 bullish).
L'engine aggrega gli score disponibili in un unico sentiment score.
"""
import json
import logging
import os
import subprocess
import urllib.request
import urllib.error
from typing import Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# ── Sentiment keywords mapping ─────────────────────────────────────
# Parole chiave con peso positivo/negativo per analisi testi semplici
_BULLISH_WORDS = {
    "bullish", "moon", "pump", "rocket", "buy", "breakout", "green",
    "surge", "rally", "gain", "profit", "ATH", "hodl", "accumulate",
    "undervalued", "oversold", "support", "rebound", "strong",
    "upgrade", "positive", "growth", "adoption", "partnership",
    "institutional", "mainnet", "launch",
}
_BEARISH_WORDS = {
    "bearish", "dump", "crash", "sell", "rug", "scam", "red",
    "plunge", "decline", "loss", "drop", "correction", "capitulation",
    "overvalued", "overbought", "resistance", "weak", "downgrade",
    "negative", "fud", "fear", "panic", "selloff", "bear",
    "regulation", "ban", "hack", "exploit",
}


def _simple_text_score(text: str) -> float:
    """
    Analisi sentiment semplice basata su keyword matching.
    Ritorna score tra -1 e +1.

    Usata quando non abbiamo un LLM a disposizione per l'analisi.
    """
    text_lower = text.lower()
    words = set(text_lower.split())
    bullish_count = len(words & _BULLISH_WORDS)
    bearish_count = len(words & _BEARISH_WORDS)
    total = bullish_count + bearish_count
    if total == 0:
        return 0.0
    raw = (bullish_count - bearish_count) / min(total, 10)  # cap a 10 parole
    return max(-1.0, min(1.0, raw))


# ── Source 1: Fear & Greed Index ──────────────────────────────────

def _fetch_fear_greed() -> Optional[dict]:
    """
    Fetcha il Fear & Greed Index da alternative.me (gratuito, no API key).

    Returns:
        dict con {value, classification, score} oppure None
        score: mappato da 0-100 a -1 (extreme fear) .. +1 (extreme greed)
    """
    url = "https://api.alternative.me/fng/?limit=1"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "denaro-bot/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            if not data.get("data"):
                return None
            entry = data["data"][0]
            value = int(entry["value"])
            classification = entry.get("value_classification", "Unknown")
            # Mappa 0-100 → -1 .. +1
            score = (value - 50) / 50
            return {
                "value": value,
                "classification": classification,
                "score": round(max(-1.0, min(1.0, score)), 3),
            }
    except Exception as e:
        logger.warning(f"Fear & Greed fetch failed: {e}")
        return None


# ── Source 2: X/Twitter search (xurl CLI) ─────────────────────────

def _search_x(symbol: str, max_results: int = 10) -> Optional[list[dict]]:
    """
    Cerca post recenti su X/Twitter su un symbol usando OAuth 1.0a diretto.

    Usa le credenziali salvate in utils/.x_creds.json (se presenti).
    Se credenziali assenti o crediti esauriti, ritorna None silenziosamente.

    Returns:
        Lista di dict {text, likes, retweets, created_at} oppure None
    """
    # Carica credenziali se presenti
    creds_path = os.path.join(os.path.dirname(__file__), ".x_creds.json")
    if not os.path.exists(creds_path):
        logger.debug("X creds file not found")
        return None

    try:
        with open(creds_path) as f:
            creds = json.load(f)
    except Exception as e:
        logger.debug(f"X creds load error: {e}")
        return None

    # Lista nera: se siamo stati rifiutati per crediti, non riprovare
    _X_CREDITS_EXHAUSTED = getattr(_search_x, "_credits_exhausted", False)
    if _X_CREDITS_EXHAUSTED:
        logger.debug("X credits previously exhausted, skipping")
        return None

    try:
        from requests_oauthlib import OAuth1
        import requests
        requests_available = True
    except ImportError:
        logger.debug("requests_oauthlib not installed")
        return None

    auth = OAuth1(
        creds["consumer_key"], creds["consumer_secret"],
        creds["access_token"], creds["access_token_secret"],
    )

    query = f"${symbol} crypto -is:retweet lang:en"
    try:
        r = requests.get(
            "https://api.x.com/2/tweets/search/recent",
            params={
                "query": query,
                "max_results": min(max_results, 10),
                "tweet.fields": "public_metrics,created_at,author_id",
            },
            auth=auth, timeout=15,
        )
    except Exception as e:
        logger.debug(f"X request error: {e}")
        return None

    if r.status_code == 402:
        # Credits depleted — ricorda per il resto della sessione
        _search_x._credits_exhausted = True
        logger.info("X API credits exhausted on Free tier, switching to news sources")
        return None

    if r.status_code != 200:
        logger.debug(f"X search returned {r.status_code}")
        return None

    try:
        data = r.json()
    except Exception:
        return None

    posts_raw = data.get("data", [])
    posts = []
    for post in posts_raw:
        posts.append({
            "text": post.get("text", ""),
            "id": post.get("id", ""),
            "author": post.get("author_id", ""),
            "likes": post.get("public_metrics", {}).get("like_count", 0),
            "retweets": post.get("public_metrics", {}).get("retweet_count", 0),
            "created_at": post.get("created_at", ""),
        })
    return posts


def _score_x_posts(posts: list[dict]) -> float:
    """
    Analizza i post X e produce un sentiment score aggregato.
    Pesa ogni post per engagement (likes + retweets).
    """
    if not posts:
        return 0.0

    total_weight = 0.0
    weighted_score = 0.0

    for post in posts:
        text = post.get("text", "")
        engagement = post.get("likes", 0) + post.get("retweets", 0) + 1  # +1 base
        post_score = _simple_text_score(text)
        weighted_score += post_score * engagement
        total_weight += engagement

    if total_weight == 0:
        return 0.0

    return max(-1.0, min(1.0, round(weighted_score / total_weight, 3)))


    # ── Source 3: Web news fallback ────────────────────────────────────

def _fetch_news_headlines(symbol: str) -> Optional[list[str]]:
    """
    Cerca news recenti sul symbol tramite RSS feeds crypto.
    Fallback quando X non è disponibile.

    Usa CoinPaprika + CryptoCompare + Google News RSS.
    """
    # CoinPaprika news API (gratuita, no key per richieste base)
    coin_map = {
        "BTC": "btc-bitcoin",
        "ETH": "eth-ethereum",
        "SOL": "sol-solana",
        "EUR": None,
    }
    base_symbol = symbol.split("/")[0] if "/" in symbol else symbol.upper()
    coin_id = coin_map.get(base_symbol)

    all_headlines = []

    # Source 3a: CoinPaprika events
    if coin_id:
        url = f"https://api.coinpaprika.com/v1/coins/{coin_id}/events"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "denaro-bot/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
                headlines = [
                    e.get("title", "") for e in data[:5]
                    if e.get("title")
                ]
                all_headlines.extend(headlines)
        except Exception as e:
            logger.debug(f"CoinPaprika news error: {e}")

    # Source 3b: CryptoCompare news (gratis, no key, 100 req/giorno)
    try:
        url = "https://min-api.cryptocompare.com/data/v2/news/?lang=EN&limit=5"
        if base_symbol:
            url += f"&categories={base_symbol}"
        req = urllib.request.Request(url, headers={"User-Agent": "denaro-bot/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            if data.get("Data"):
                for item in data["Data"]:
                    title = item.get("title", "")
                    keywords = item.get("keywords", "")
                    # Filtra solo se menziona il nostro symbol
                    if base_symbol.lower() in title.lower() or base_symbol.lower() in keywords.lower():
                        all_headlines.append(title)
    except Exception as e:
        logger.debug(f"CryptoCompare news error: {e}")

    # Source 3c: Fear & Greed news (include news links)
    try:
        url = "https://api.alternative.me/fng/?limit=5"
        req = urllib.request.Request(url, headers={"User-Agent": "denaro-bot/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            # F&G non dà headline testuali, ma possiamo usare la classification
            # come segnale aggiuntivo
    except Exception as e:
        logger.debug(f"F&G news error: {e}")

    return list(set(all_headlines)) if all_headlines else None


def _score_news(headlines: list[str]) -> float:
    """Analizza titoli news e produce sentiment score."""
    if not headlines:
        return 0.0

    scores = [_simple_text_score(h) for h in headlines]
    return round(sum(scores) / len(scores), 3)


# ── Sentiment Engine ───────────────────────────────────────────────
# Pattern ispirato dal video: anche i meme move di mercato sono mossi
# dal sentiment social, non solo dai dati tecnici.

class SentimentEngine:
    """
    Aggrega sentiment da multiple fonti in un unico score.

    Usage:
        engine = SentimentEngine()
        result = engine.analyze("SOL")
        # result = {
        #   "overall_score": 0.35,
        #   "sources": {
        #       "fear_greed": {"score": -0.38, "classification": "Fear"},
        #       "x_twitter": {"score": 0.5, "posts_count": 10},
        #       "news": {"score": 0.2, "headlines_count": 3},
        #   }
        # }
    """

    def __init__(self, enable_x: bool = True, enable_news: bool = True):
        self.enable_x = enable_x
        self.enable_news = enable_news

    def analyze(self, symbol: str) -> dict:
        """
        Esegue analisi sentiment su tutte le fonti disponibili.

        Args:
            symbol: Nome del symbol (es. "SOL", "ETH", "SOL/EUR")

        Returns:
            dict con overall_score, sources, timestamp
        """
        base_symbol = symbol.split("/")[0] if "/" in symbol else symbol.upper()
        sources = {}
        active_scores = []

        # Source 1: Fear & Greed (sempre)
        fg = _fetch_fear_greed()
        if fg:
            sources["fear_greed"] = {
                "score": fg["score"],
                "value": fg["value"],
                "classification": fg["classification"],
            }
            active_scores.append(("fear_greed", fg["score"], 0.3))

        # Source 2: X/Twitter
        if self.enable_x:
            posts = _search_x(base_symbol)
            if posts is not None:
                x_score = _score_x_posts(posts)
                sources["x_twitter"] = {
                    "score": x_score,
                    "posts_count": len(posts),
                    "sample_texts": [p["text"][:120] for p in posts[:3]],
                }
                active_scores.append(("x_twitter", x_score, 0.5))
                logger.info(f"X sentiment {base_symbol}: {x_score:.2f} da {len(posts)} post")
            else:
                logger.info(f"X/Twitter non disponibile per {base_symbol} (auth mancante o errore)")

        # Source 3: News
        if self.enable_news:
            headlines = _fetch_news_headlines(base_symbol)
            if headlines:
                news_score = _score_news(headlines)
                sources["news"] = {
                    "score": news_score,
                    "headlines_count": len(headlines),
                    "headlines": headlines,
                }
                active_scores.append(("news", news_score, 0.2))
                logger.info(f"News sentiment {base_symbol}: {news_score:.2f} da {len(headlines)} headlines")

        # Aggregation: weighted average
        if not active_scores:
            return {
                "overall_score": 0.0,
                "sources": sources,
                "available_sources": 0,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        total_weight = 0.0
        weighted = 0.0
        for name, score, weight in active_scores:
            weighted += score * weight
            total_weight += weight

        overall = round(weighted / total_weight, 3) if total_weight > 0 else 0.0

        return {
            "overall_score": overall,
            "sources": sources,
            "available_sources": len(active_sources := active_scores),
            "active_sources": [s[0] for s in active_scores],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


def sentiment_to_action(sentiment_score: float,
                        threshold_buy: float = 0.2,
                        threshold_sell: float = -0.2) -> str:
    """
    Converte un sentiment score in azione di trading.
    """
    if sentiment_score >= threshold_buy:
        return "BUY"
    elif sentiment_score <= threshold_sell:
        return "SELL"
    return "HOLD"


# ── CLI test ──────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(message)s")
    import sys
    symbol = sys.argv[1] if len(sys.argv) > 1 else "SOL"
    engine = SentimentEngine()
    result = engine.analyze(symbol)
    print(json.dumps(result, indent=2))
