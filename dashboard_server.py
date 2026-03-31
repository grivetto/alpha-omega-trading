from flask import Flask, render_template_string
import os

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Nuvola Orbital Command</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');
        
        :root {
            --neon-green: #00ffcc;
            --neon-pink: #ff00ff;
            --neon-red: #ff3333;
            --neon-yellow: #ffff00;
            --bg-dark: #050505;
            --panel-bg: rgba(0, 255, 204, 0.03);
        }

        body {
            background-color: var(--bg-dark);
            color: var(--neon-green);
            font-family: 'Share Tech Mono', monospace;
            margin: 0;
            padding: 20px;
            overflow-x: hidden;
            background-image: 
                linear-gradient(rgba(0, 255, 204, 0.1) 1px, transparent 1px),
                linear-gradient(90deg, rgba(0, 255, 204, 0.1) 1px, transparent 1px);
            background-size: 20px 20px;
        }

        h1, h2, h3 {
            text-align: center;
            text-transform: uppercase;
            letter-spacing: 2px;
        }

        .header-title {
            color: var(--neon-pink);
            text-shadow: 0 0 10px var(--neon-pink), 0 0 20px var(--neon-pink);
            font-size: 2.5em;
            margin-bottom: 5px;
        }

        .subtitle {
            color: #555;
            font-size: 1em;
            margin-top: 0;
            letter-spacing: 4px;
        }

        .container {
            max-width: 1400px;
            margin: 30px auto;
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 25px;
        }

        .panel {
            border: 1px solid var(--neon-green);
            background: var(--panel-bg);
            padding: 20px;
            box-shadow: 0 0 15px rgba(0, 255, 204, 0.1) inset;
            position: relative;
            backdrop-filter: blur(5px);
        }

        .panel::before {
            content: '';
            position: absolute;
            top: -2px; left: -2px; right: -2px; bottom: -2px;
            border: 2px solid transparent;
            background: linear-gradient(45deg, var(--neon-green), transparent, var(--neon-pink)) border-box;
            -webkit-mask: linear-gradient(#fff 0 0) padding-box, linear-gradient(#fff 0 0);
            -webkit-mask-composite: destination-out;
            mask-composite: exclude;
            z-index: -1;
            opacity: 0.5;
        }

        .title {
            font-size: 1.5em;
            margin-bottom: 20px;
            color: var(--neon-pink);
            text-shadow: 0 0 8px var(--neon-pink);
            border-bottom: 1px dashed var(--neon-pink);
            padding-bottom: 10px;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .status-ok { color: var(--neon-green); text-shadow: 0 0 8px var(--neon-green); font-weight: bold; }
        .status-warn { color: var(--neon-yellow); text-shadow: 0 0 8px var(--neon-yellow); font-weight: bold; }
        .status-err { color: var(--neon-red); text-shadow: 0 0 8px var(--neon-red); font-weight: bold; }
        
        .list-group {
            display: flex;
            flex-direction: column;
            gap: 15px;
        }

        .list-item {
            border-left: 3px solid var(--neon-green);
            padding-left: 15px;
            background: rgba(0, 0, 0, 0.4);
            padding-top: 10px;
            padding-bottom: 10px;
        }

        .item-header {
            font-size: 1.1em;
            color: #fff;
            margin-bottom: 5px;
        }

        .item-details {
            font-size: 0.9em;
            color: #aaa;
        }
        
        /* Table Styles */
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
            font-size: 0.95em;
        }
        th, td {
            border: 1px solid rgba(0, 255, 204, 0.3);
            padding: 12px;
            text-align: left;
        }
        th {
            background: rgba(255, 0, 255, 0.1);
            color: var(--neon-pink);
            font-weight: normal;
            letter-spacing: 1px;
        }
        tr:nth-child(even) {
            background: rgba(0, 255, 204, 0.02);
        }

        /* Animations */
        .scanline {
            width: 100%;
            height: 150px;
            background: linear-gradient(0deg, rgba(0,0,0,0) 0%, rgba(0,255,204,0.1) 50%, rgba(0,0,0,0) 100%);
            opacity: 0.5;
            position: fixed;
            bottom: 100%;
            animation: scanline 8s linear infinite;
            pointer-events: none;
            z-index: 999;
        }
        @keyframes scanline {
            0% { bottom: 100%; }
            100% { bottom: -150px; }
        }
        
        .blink { animation: blinker 2s linear infinite; }
        @keyframes blinker { 50% { opacity: 0; } }

        .glow-pulse { animation: pulse 2s infinite; }
        @keyframes pulse {
            0% { box-shadow: 0 0 5px var(--neon-green); }
            50% { box-shadow: 0 0 20px var(--neon-green); }
            100% { box-shadow: 0 0 5px var(--neon-green); }
        }
        
        .footer {
            text-align: center;
            margin-top: 40px;
            font-size: 0.85em;
            color: #444;
            border-top: 1px solid #222;
            padding-top: 20px;
        }
    </style>
</head>
<body>
    <div class="scanline"></div>
    
    <div class="header-title">
        <span class="blink">🔴</span> NUVOLA ORBITAL COMMAND <span class="blink">🔴</span>
    </div>
    <div class="subtitle">v9.0.0 - QUANTITATIVE WARFARE ARCHITECTURE</div>
    
    <div class="container">
        
        <!-- SQUADRE D'ASSALTO -->
        <div class="panel">
            <div class="title">⚔️ SQUADRE D'ASSALTO (HFT)</div>
            <div class="list-group">
                <div class="list-item">
                    <div class="item-header"><strong>SQUADRA_ALPHA</strong> (Scalper su Binance)</div>
                    <div class="item-details">
                        [ <span class="status-ok">ENGAGED</span> ] | APM: 450 | PnL 24h: +1.24% | Latency: 4ms
                    </div>
                </div>
                <div class="list-item">
                    <div class="item-header"><strong>SQUADRA_DELTA</strong> (Order Flow Analysis)</div>
                    <div class="item-details">
                        [ <span class="status-warn">STANDBY</span> ] | Flow Imbalance: 0.8 | Awaiting Volatility Breakout
                    </div>
                </div>
                <div class="list-item">
                    <div class="item-header"><strong>SQUADRA_GAMMA</strong> (Pairs Trading su Bitget)</div>
                    <div class="item-details">
                        [ <span class="status-ok">ENGAGED</span> ] | Spread: 0.45% | Z-Score: 2.1 | Hedged
                    </div>
                </div>
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <div class="title">🔺 PROTOCOLLO TRINITY</div>
            <div style="text-align: center; margin-bottom: 15px; font-weight: bold; color: var(--neon-green); text-shadow: 0 0 8px var(--neon-green);">
                ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
            </div>
            <div class="list-group">
                <div class="list-item">
                    <div class="item-header"><strong>LO STROZZINO</strong> (Funding Arb)</div>
                    <div class="item-details">
                        [ <span class="status-ok">ONLINE / BKG</span> ] | Est. Yield: 18.5% APR | Exposure: Delta Neutral
                    </div>
                </div>
                <div class="list-item">
                    <div class="item-header"><strong>IL CONTABILE</strong> (DCA Accumulation)</div>
                    <div class="item-details">
                        [ <span class="status-ok">ONLINE / BKG</span> ] | Next execution: 4h 12m | Vault: Secured
                    </div>
                </div>
                <div class="list-item">
                    <div class="item-header"><strong>L'ANGELO CUSTODE</strong> (MEV Arbitrum)</div>
                    <div class="item-details">
                        [ <span class="status-ok">ONLINE / BKG</span> ] | Intercepts: 14 (1h) | Gas optimized: 12 Gwei
                    </div>
                </div>
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel" style="grid-column: 1 / span 2;">
            <div class="title">📊 METRICHE DI MERCATO & INTEL (LIVE FEED)</div>
            <table>
                <thead>
                    <tr>
                        <th>ASSET PAIR</th>
                        <th>MODULE / ORACLE</th>
                        <th>SENTIMENT / SCORE</th>
                        <th>TACTICAL ACTION</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>BTC/USDT</td>
                        <td>The Oracle (Binance Depth)</td>
                        <td><span class="status-ok">85/100 (STRONG BULL)</span></td>
                        <td>ACCUMULATE</td>
                    </tr>
                    <tr>
                        <td>ETH/USDT</td>
                        <td>Whale Tracker (On-Chain)</td>
                        <td><span class="status-warn">45/100 (NEUTRAL)</span></td>
                        <td>HOLD POSITION</td>
                    </tr>
                    <tr>
                        <td>SOL/USDT</td>
                        <td>The Oracle (Twitter Sentiment)</td>
                        <td><span class="status-err">20/100 (BEARISH)</span></td>
                        <td>SHORT-HEDGE</td>
                    </tr>
                    <tr>
                        <td>LINK/USDT</td>
                        <td>SQUADRA_DELTA (Order Flow)</td>
                        <td><span class="status-ok">72/100 (BULLISH)</span></td>
                        <td>SCALP LONG</td>
                    </tr>
                </tbody>
            </table>
        </div>
        
    </div>
    
    <div class="footer">
        SYSTEM STATUS: <span class="status-ok">NOMINAL</span> | UPTIME: 99.999% | CORE TEMP: 42°C | ACTIVE THREADS: 128
    </div>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    # Riavvia il server con host 0.0.0.0
    app.run(host='0.0.0.0', port=5000, debug=False)
