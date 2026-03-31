from flask import Flask, render_template_string
import random
import time
import threading

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ORBITAL COMMAND // NUVOLA</title>
    <style>
        :root {
            --neon-green: #0fa;
            --neon-blue: #0ff;
            --neon-pink: #f0f;
            --bg-color: #050510;
            --panel-bg: rgba(10, 20, 30, 0.8);
            --border-color: rgba(0, 255, 255, 0.3);
        }
        body {
            background-color: var(--bg-color);
            color: var(--neon-green);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            overflow-x: hidden;
            background-image: 
                linear-gradient(rgba(0, 255, 255, 0.05) 1px, transparent 1px),
                linear-gradient(90deg, rgba(0, 255, 255, 0.05) 1px, transparent 1px);
            background-size: 20px 20px;
        }
        h1, h2, h3 {
            text-transform: uppercase;
            text-shadow: 0 0 10px var(--neon-blue);
            margin-top: 0;
        }
        .header {
            text-align: center;
            border-bottom: 2px solid var(--neon-blue);
            padding-bottom: 10px;
            margin-bottom: 30px;
            box-shadow: 0 10px 20px rgba(0,255,255,0.1);
        }
        .header h1 {
            color: var(--neon-blue);
            font-size: 2.5em;
            letter-spacing: 5px;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
        }
        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--border-color);
            border-radius: 5px;
            padding: 20px;
            box-shadow: inset 0 0 15px rgba(0,255,255,0.05), 0 0 10px rgba(0,255,255,0.1);
            position: relative;
            overflow: hidden;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; width: 100%; height: 2px;
            background: linear-gradient(90deg, transparent, var(--neon-blue), transparent);
            animation: scanline 3s linear infinite;
        }
        @keyframes scanline {
            0% { transform: translateX(-100%); }
            100% { transform: translateX(100%); }
        }
        .status-indicator {
            display: inline-block;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background-color: var(--neon-green);
            box-shadow: 0 0 10px var(--neon-green);
            margin-right: 10px;
            animation: pulse 1.5s infinite alternate;
        }
        @keyframes pulse {
            0% { opacity: 0.5; box-shadow: 0 0 5px var(--neon-green); }
            100% { opacity: 1; box-shadow: 0 0 15px var(--neon-green); }
        }
        .item {
            margin-bottom: 15px;
            padding: 10px;
            border: 1px dashed rgba(0, 255, 170, 0.3);
            background: rgba(0, 255, 170, 0.05);
        }
        .item-title {
            font-weight: bold;
            color: var(--neon-blue);
            display: flex;
            justify-content: space-between;
        }
        .item-desc {
            font-size: 0.9em;
            color: #aaa;
            margin-top: 5px;
        }
        .trinity .status-indicator {
            background-color: var(--neon-pink);
            box-shadow: 0 0 10px var(--neon-pink);
        }
        .trinity .item {
            border-color: rgba(255, 0, 255, 0.3);
            background: rgba(255, 0, 255, 0.05);
        }
        .trinity .item-title { color: var(--neon-pink); }
        
        table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.9em;
        }
        th, td {
            padding: 8px;
            text-align: left;
            border-bottom: 1px solid rgba(0,255,255,0.2);
        }
        th { color: var(--neon-blue); }
        .blink { animation: blinker 1s linear infinite; }
        @keyframes blinker { 50% { opacity: 0; } }
        
        .sys-info {
            position: fixed;
            bottom: 10px;
            right: 10px;
            font-size: 0.8em;
            color: #666;
            text-align: right;
        }
    </style>
</head>
<body>

    <div class="header">
        <h1>🚀 ORBITAL COMMAND // NUVOLA</h1>
        <p>SYSTEM UPLINK: <span class="blink" style="color:var(--neon-green)">ESTABLISHED</span> | UPTIME: 99.99% | ENCRYPTION: QUANTUM</p>
        <p style="color: var(--neon-pink); font-weight: bold; text-shadow: 0 0 5px var(--neon-pink);">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</p>
    </div>

    <div class="grid">
        <!-- SQUADRE D'ASSALTO -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <div class="item">
                <div class="item-title">
                    <span><span class="status-indicator"></span>SQUADRA_ALPHA</span>
                    <span>[BINANCE]</span>
                </div>
                <div class="item-desc">⚡ Scalper ad Alta Frequenza. Algoritmi predittivi su order book micro-strutturale.</div>
                <div style="margin-top:5px; font-size:0.8em;">Stato: <span style="color:var(--neon-green)">ENGAGED</span> | Ping: 12ms | WinRate: 74%</div>
            </div>
            <div class="item">
                <div class="item-title">
                    <span><span class="status-indicator"></span>SQUADRA_DELTA</span>
                    <span>[DERIBIT/BYBIT]</span>
                </div>
                <div class="item-desc">🌊 Order Flow Analysis. Tracciamento volumi istituzionali e sbilanciamenti (Imbalance).</div>
                <div style="margin-top:5px; font-size:0.8em;">Stato: <span style="color:var(--neon-green)">ENGAGED</span> | Ping: 18ms | Posizioni: 3 ATTIVE</div>
            </div>
            <div class="item">
                <div class="item-title">
                    <span><span class="status-indicator"></span>SQUADRA_GAMMA</span>
                    <span>[BITGET]</span>
                </div>
                <div class="item-desc">⚖️ Pairs Trading & Cointegration. Hedging dinamico beta-neutrale.</div>
                <div style="margin-top:5px; font-size:0.8em;">Stato: <span style="color:var(--neon-green)">ENGAGED</span> | Ping: 22ms | Z-Score: 2.14</div>
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel trinity">
            <h2>🔺 PROTOCOLLO TRINITY</h2>
            <div class="item">
                <div class="item-title">
                    <span><span class="status-indicator"></span>LO STROZZINO</span>
                    <span>[BACKGROUND]</span>
                </div>
                <div class="item-desc">💸 Funding Rate Arbitrage. Estrazione di rendimento passivo delta-neutral sui perpetual.</div>
                <div style="margin-top:5px; font-size:0.8em;">APR Stimato: <span style="color:var(--neon-pink)">18.4%</span> | Esposizione: 15K USD</div>
            </div>
            <div class="item">
                <div class="item-title">
                    <span><span class="status-indicator"></span>IL CONTABILE</span>
                    <span>[BACKGROUND]</span>
                </div>
                <div class="item-desc">📉 Dollar Cost Averaging (DCA) Intelligente. Accumulo strategico nei dip basato su RSI/MACD.</div>
                <div style="margin-top:5px; font-size:0.8em;">Fondi allocati: <span style="color:var(--neon-pink)">65%</span> | Prossimo Target: BTC @ 58k</div>
            </div>
            <div class="item">
                <div class="item-title">
                    <span><span class="status-indicator"></span>L'ANGELO CUSTODE</span>
                    <span>[BACKGROUND]</span>
                </div>
                <div class="item-desc">🛡️ MEV Searcher su Arbitrum. Liquidazioni e sandwiching difensivo sui DEX.</div>
                <div style="margin-top:5px; font-size:0.8em;">Mempool Scans: <span style="color:var(--neon-pink)">142/sec</span> | Flashbots: CONNESSO</div>
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <h2>👁️ METRICHE DI MERCATO</h2>
            <div style="margin-bottom: 15px;">
                <h3 style="color: var(--neon-blue); font-size:1.1em; border-bottom:1px solid rgba(0,255,255,0.3); padding-bottom:5px;">🔮 THE ORACLE (Sentiment)</h3>
                <table>
                    <tr><th>ASSET</th><th>SENTIMENT</th><th>CONFIDENZA</th></tr>
                    <tr><td>BTC/USDT</td><td style="color:#0fa">BULLISH</td><td>89%</td></tr>
                    <tr><td>ETH/USDT</td><td style="color:#0fa">MILD-BULL</td><td>65%</td></tr>
                    <tr><td>SOL/USDT</td><td style="color:#f00">BEARISH</td><td>72%</td></tr>
                </table>
            </div>
            
            <div>
                <h3 style="color: var(--neon-blue); font-size:1.1em; border-bottom:1px solid rgba(0,255,255,0.3); padding-bottom:5px;">🐋 WHALE TRACKER</h3>
                <div style="font-family: monospace; font-size: 0.8em; color: #aaa;">
                    <span style="color:var(--neon-pink)">[ALERT]</span> 15,000 BTC trasferiti in Coinbase<br>
                    <span style="color:var(--neon-green)">[INFO]</span> Accumulo anomalo su ARB (+12M $)<br>
                    <span style="color:var(--neon-green)">[INFO]</span> Prelievo Binance: 50,000 ETH<br>
                    <span style="color:var(--neon-pink)">[ALERT]</span> Spike Open Interest su DOGE (+40%)
                </div>
            </div>
            
            <div style="margin-top:20px; text-align:center;">
                <div style="width:100%; height:20px; border:1px solid var(--neon-blue); position:relative;">
                    <div style="width:85%; height:100%; background:var(--neon-blue); opacity:0.5;"></div>
                    <span style="position:absolute; top:2px; left:5px; font-size:0.8em; color:#fff;">CORE LOAD: 85%</span>
                </div>
            </div>
        </div>
    </div>

    <div class="sys-info">
        ORBITAL COMMAND NODE v4.2.0 | LATENCY: 14ms | 0xNUVOLA SECURE LINK
    </div>

    <script>
        // Simulate real-time updates for some numbers
        setInterval(() => {
            const elements = document.querySelectorAll('.blink-update');
            elements.forEach(el => {
                if(Math.random() > 0.5) {
                    el.style.opacity = '0.5';
                    setTimeout(() => el.style.opacity = '1', 100);
                }
            });
        }, 500);
    </script>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
