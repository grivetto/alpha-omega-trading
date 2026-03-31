from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ORBITAL COMMAND | NUVOLA</title>
    <style>
        :root {
            --neon-green: #39ff14;
            --neon-blue: #0ff;
            --neon-pink: #ff00ff;
            --bg-color: #050505;
            --panel-bg: rgba(10, 20, 10, 0.8);
        }
        body {
            background-color: var(--bg-color);
            color: #ddd;
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            background-image: 
                linear-gradient(rgba(0, 255, 0, 0.03) 1px, transparent 1px),
                linear-gradient(90deg, rgba(0, 255, 0, 0.03) 1px, transparent 1px);
            background-size: 20px 20px;
        }
        h1, h2, h3 {
            text-transform: uppercase;
            margin-top: 0;
        }
        .header-title {
            color: var(--neon-green);
            text-shadow: 0 0 5px var(--neon-green), 0 0 10px var(--neon-green);
            text-align: center;
            border-bottom: 2px solid var(--neon-green);
            padding-bottom: 10px;
            margin-bottom: 30px;
        }
        .container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
        }
        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-blue);
            box-shadow: 0 0 10px rgba(0, 255, 255, 0.2);
            padding: 15px;
            border-radius: 5px;
            position: relative;
            overflow: hidden;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; height: 2px;
            background: var(--neon-blue);
            box-shadow: 0 0 10px var(--neon-blue);
        }
        .panel.pink { border-color: var(--neon-pink); box-shadow: 0 0 10px rgba(255, 0, 255, 0.2); }
        .panel.pink::before { background: var(--neon-pink); box-shadow: 0 0 10px var(--neon-pink); }
        
        .panel.green { border-color: var(--neon-green); box-shadow: 0 0 10px rgba(57, 255, 20, 0.2); }
        .panel.green::before { background: var(--neon-green); box-shadow: 0 0 10px var(--neon-green); }

        .status {
            display: inline-block;
            width: 10px; height: 10px;
            border-radius: 50%;
            background: var(--neon-green);
            box-shadow: 0 0 8px var(--neon-green);
            margin-right: 10px;
            animation: blink 1.5s infinite alternate;
        }
        .status.offline { background: red; box-shadow: 0 0 8px red; animation: none; }
        
        @keyframes blink {
            from { opacity: 0.5; }
            to { opacity: 1; }
        }

        .item { margin-bottom: 15px; border-bottom: 1px dashed #333; padding-bottom: 10px; }
        .item:last-child { border-bottom: none; margin-bottom: 0; padding-bottom: 0; }
        .title { color: var(--neon-blue); font-weight: bold; }
        .pink .title { color: var(--neon-pink); }
        .green .title { color: var(--neon-green); }
        
        table { width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 0.9em; }
        th, td { text-align: left; padding: 5px; border-bottom: 1px solid #333; }
        th { color: var(--neon-blue); }
        
        .metrics-value { color: var(--neon-green); font-weight: bold; text-shadow: 0 0 5px var(--neon-green); }
        
        .scan-line {
            position: fixed;
            top: 0; left: 0; width: 100%; height: 5px;
            background: rgba(57, 255, 20, 0.3);
            opacity: 0.4;
            animation: scan 4s linear infinite;
            pointer-events: none;
            z-index: 9999;
        }
        
        @keyframes scan {
            0% { top: -10px; }
            100% { top: 100%; }
        }
    </style>
</head>
<body>
    <div class="scan-line"></div>
    <h1 class="header-title">🛰️ ORBITAL COMMAND | NUVOLA 🛰️</h1>
    
    <div style="text-align: center; margin-bottom: 20px; font-size: 1.2em; color: var(--neon-green); text-shadow: 0 0 5px var(--neon-green);">
        ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
    </div>
    
    <div class="container">
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel pink">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <div class="item">
                <span class="status"></span>
                <span class="title">SQUADRA_ALPHA</span>
                <div>🎯 Ruolo: Scalper su Binance</div>
                <div>⚡ Latenza: 12ms | PnL Oggi: <span class="metrics-value">+2.4%</span></div>
            </div>
            <div class="item">
                <span class="status"></span>
                <span class="title">SQUADRA_DELTA</span>
                <div>🌊 Ruolo: Order Flow Arbitrage</div>
                <div>📊 Volumi: Alto | PnL Oggi: <span class="metrics-value">+1.1%</span></div>
            </div>
            <div class="item">
                <span class="status"></span>
                <span class="title">SQUADRA_GAMMA</span>
                <div>⚖️ Ruolo: Pairs Trading (Bitget)</div>
                <div>🔗 Correlazione: 0.94 | PnL Oggi: <span class="metrics-value">+0.8%</span></div>
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel blue">
            <h2>🛡️ PROTOCOLLO TRINITY</h2>
            <div class="item">
                <span class="status"></span>
                <span class="title">Lo Strozzino</span>
                <div>💸 Ruolo: Funding Rate Arbitrage</div>
                <div>🏦 Posizioni: Market Neutral (Hedged)</div>
            </div>
            <div class="item">
                <span class="status"></span>
                <span class="title">Il Contabile</span>
                <div>📈 Ruolo: DCA Strategico</div>
                <div>📆 Frequenza: Oraria | Asset: BTC, ETH</div>
            </div>
            <div class="item">
                <span class="status"></span>
                <span class="title">L'Angelo Custode</span>
                <div>👼 Ruolo: MEV Searcher (Arbitrum)</div>
                <div>🚀 Frontrunning: Attivo | Flashloans: Pronti</div>
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel green">
            <h2>📡 METRICHE DI MERCATO</h2>
            <div class="item">
                <span class="title">👁️ THE ORACLE (Sentiment)</span>
                <table>
                    <tr><th>Asset</th><th>Sentiment</th><th>Score</th></tr>
                    <tr><td>BTC/USDT</td><td>Bullish 🟢</td><td>87/100</td></tr>
                    <tr><td>ETH/USDT</td><td>Neutral ⚪</td><td>52/100</td></tr>
                    <tr><td>SOL/USDT</td><td>Bearish 🔴</td><td>31/100</td></tr>
                </table>
            </div>
            <div class="item">
                <span class="title">🐋 WHALE TRACKER</span>
                <table>
                    <tr><th>Time</th><th>Tx</th><th>Size</th></tr>
                    <tr><td>10s ago</td><td>BINANCE IN</td><td class="metrics-value">450 BTC</td></tr>
                    <tr><td>2m ago</td><td>DEX SWAP</td><td class="metrics-value">12k ETH</td></tr>
                    <tr><td>5m ago</td><td>BITFINEX OUT</td><td class="metrics-value">800 BTC</td></tr>
                </table>
            </div>
        </div>
    </div>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
