import requests
import time
import os
import json
import logging
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET

logging.basicConfig(level=logging.INFO, format='%(asctime)s - [NEWS SNIPER \U0001f4f0] - %(message)s',
                    handlers=[logging.FileHandler("NEWS_SNIPER.log"), logging.StreamHandler()])

# Dictionari di Sentiment Ponderato
BULLISH_KEYWORDS = ["approves", "approved", "partnership", "adopted", "legal tender",
                    "elon musk", "blackrock", "buys", "launch", "bullish", "ath", "breakout"]
BEARISH_KEYWORDS = ["hack", "hacked", "sec sues", "lawsuit", "bankrupt", "bankruptcy",
                    "arrested", "stolen", "crash", "bearish", "banned", "illegal", "fbi"]

# Crypto note e loro ticker Futures su Bitget
COIN_MAP = {
    "bitcoin": "BTC/USDT:USDT", "btc": "BTC/USDT:USDT",
    "ethereum": "ETH/USDT:USDT", "eth": "ETH/USDT:USDT",
    "solana": "SOL/USDT:USDT", "sol": "SOL/USDT:USDT",
    "dogecoin": "DOGE/USDT:USDT", "doge": "DOGE/USDT:USDT",
    "ripple": "XRP/USDT:USDT", "xrp": "XRP/USDT:USDT",
    "pepe": "PEPE/USDT:USDT", "wif": "WIF/USDT:USDT"
}

# Cache degli ultimi articoli visti per evitare spam
seen_articles = set()


def fetch_rss_feed(url):
    try:
        response = requests.get(url, timeout=10)
        root = ET.fromstring(response.content)
        articles = []
        for item in root.findall('.//item')[:5]:
            title = item.find('title').text
            link = item.find('link').text
            if link not in seen_articles:
                articles.append({"title": title, "link": link})
                seen_articles.add(link)
        return articles
    except Exception as e:
        return []


def analyze_and_act(title):
    title_lower = title.lower()

    # 1. Trova se si parla di una coin specifica
    target_coin = None
    for keyword, symbol in COIN_MAP.items():
        if keyword in title_lower:
            target_coin = symbol
            break

    if not target_coin:
        target_coin = "BTC/USDT:USDT"

    # 2. Analizza Sentiment
    is_bullish = any(word in title_lower for word in BULLISH_KEYWORDS)
    is_bearish = any(word in title_lower for word in BEARISH_KEYWORDS)

    if is_bullish and not is_bearish:
        logging.warning(f"\U0001f7e2 [BULLISH NEWS RILEVATA] - Titolo: '{title}' -> Preparazione LONG su {target_coin}")
        trigger_trade(target_coin, "buy", title)
    elif is_bearish and not is_bullish:
        logging.warning(f"\U0001f534 [BEARISH NEWS RILEVATA] - Titolo: '{title}' -> Preparazione SHORT / DEFCON su {target_coin}")
        trigger_trade(target_coin, "sell", title)
        if target_coin == "BTC/USDT:USDT":
            try:
                with open("/home/sergio/denaro/DEFCON.lock", "w") as f:
                    f.write("DEFCON_NEWS_PANIC")
            except Exception:
                pass


def trigger_trade(symbol, side, reason):
    """Passa il segnale ai bot operativi o agisce in proprio se abilitato."""
    try:
        from dotenv import load_dotenv
        load_dotenv('/home/sergio/denaro/.env')
        token = os.getenv('TELEGRAM_BOT_TOKEN')
        chat_id = os.getenv('TELEGRAM_CHAT_ID')

        emoji = "\U0001f7e2 LONG MASSICCIO" if side == "buy" else "\U0001f534 SHORT PESANTE"
        msg = (
            f"\U0001f4f0 *NEWS SENTIMENT SNIPER* \U0001f4f0\\n\\n"
            f"Ho appena intercettato una notizia bomba prima del mercato:\\n\\n"
            f"*Titolo:* {reason}\\n\\n"
            f"*Azione:* {emoji} su {symbol}!\\n"
            f"I bot si stanno riposizionando."
        )
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data={"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"}
        )

        config_path = "/home/sergio/denaro/trade_config.json"
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                config = json.load(f)
            config["news_sentiment_target"] = symbol
            config["news_sentiment_side"] = side
            with open(config_path, "w") as f:
                json.dump(config, f, indent=4)
    except Exception:
        pass


def run_sniper():
    logging.info("\U0001f4f0 NEWS SENTIMENT SNIPER INIZIALIZZATO. (Monitoring Cointelegraph & CoinDesk RSS).")

    feeds = [
        "https://cointelegraph.com/rss",
        "https://www.coindesk.com/arc/outboundfeeds/rss/"
    ]

    for feed in feeds:
        fetch_rss_feed(feed)

    while True:
        try:
            for feed in feeds:
                new_articles = fetch_rss_feed(feed)
                for article in new_articles:
                    logging.info(f"Scansione: {article['title']}")
                    analyze_and_act(article['title'])

            time.sleep(60)
            logging.info("\U0001f9e9 Heartbeat OK. Scansione RSS completata.")

        except Exception as e:
            logging.error(f"Errore News Loop: {e}")
            time.sleep(60)


if __name__ == '__main__':
    run_sniper()