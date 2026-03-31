from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ORBITAL COMMAND // NUVOLA</title>
    <style>
        :root {
            --neon-green: #0f0;
            --neon-cyan: #0ff;
            --neon-magenta: #f0f;
            --dark-bg: #050505;
        }
        body {
            background-color: var(--dark-bg);
            color: var(--neon-green);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            background-image: linear-gradient(rgba(0, 255, 0, 0.03) 1px, transparent 1px),
            linear-gradient(90deg, rgba(0, 255, 0, 0.03) 1px, transparent 1px);
            background-size: 20px 20px;
        }
        .glow-text {
            text-shadow: 0 0 5px var(--neon-green), 0 0 10px var(--neon-green);
        }
        h1, h2, h3 { 
            color: var(--neon-cyan); 
            text-shadow: 0 0 5px var(--neon-cyan), 0 0 15px var(--neon-cyan);
            text-transform: uppercase;
            letter-spacing: 2px;
        }
        .panel {
            border: 1px solid var(--neon-green);
            padding: 20px;
            margin: 15px 0;
            box-shadow: 0 0 15px inset rgba(0, 255, 0, 0.2), 0 0 10px rgba(0, 255, 0, 0.2);
            background: rgba(0, 20, 0, 0.7);
            position: relative;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; width: 10px; height: 10px;
            border-top: 2px solid var(--neon-cyan);
            border-left: 2px solid var(--neon-cyan);
        }
        .panel::after {
            content: '';
            position: absolute;
            bottom: 0; right: 0; width: 10px; height: 10px;
            border-bottom: 2px solid var(--neon-cyan);
            border-right: 2px solid var(--neon-cyan);
        }
        .status-online { color: var(--neon-green); animation: blinker 1.5s step-start infinite; }
        .status-active { color: var(--neon-magenta); text-shadow: 0 0 8px var(--neon-magenta); }
        .status-alert { color: #f00; text-shadow: 0 0 8px #f00; }
        
        @keyframes blinker { 50% { opacity: 0.3; } }
        @keyframes scanline {
            0% { transform: translateY(-100%); }
            100% { transform: translateY(100vh); }
        }
        .scanline {
            width: 100%;
            height: 100px;
            background: linear-gradient(0deg, rgba(0,255,0,0) 0%, rgba(0,255,0,0.1) 50%, rgba(0,255,0,0) 100%);
            opacity: 0.1;
            position: fixed;
            top: 0;
            left: 0;
            pointer-events: none;
            animation: scanline 6s linear infinite;
        }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); gap: 20px; }
        ul { list-style-type: none; padding-left: 0; }
        li { margin: 10px 0; border-left: 2px solid var(--neon-green); padding-left: 10px; }
        .progress-bar {
            width: 100%;
            height: 10px;
            background: #111;
            border: 1px solid var(--neon-green);
            margin-top: 5px;
        }
        .progress-fill {
            height: 100%;
            background: var(--neon-magenta);
            width: 78%;
            box-shadow: 0 0 10px var(--neon-magenta);
        }
    </style>
</head>
<body>
    <div class="scanline"></div>
    <h1 class="glow-text">🛰️ ORBITAL COMMAND // NUVOLA TERMINAL</h1>
    <p>SYSTEM UPLINK: <span class="status-online">ESTABLISHED</span> | ENCRYPTION: QUANTUM-AES256 | LATENCY: 12ms</p>
    <p><strong><span class="status-active">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</span></strong></p>
    <hr style="border-color: var(--neon-green); box-shadow: 0 0 5px var(--neon-green);">

    <div class="grid">
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <ul>
                <li>
                    <strong><span class="status-active">▶ SQUADRA_ALPHA</span></strong> [Scalper @ Binance]<br>
                    ↳ STATUS: <span class="status-online">ENGAGED</span> | PnL 24h: +4.2%<br>
                    <div class="progress-bar"><div class="progress-fill" style="width: 85%; background: var(--neon-green);"></div></div>
                </li>
                <li>
                    <strong><span class="status-active">▶ SQUADRA_DELTA</span></strong> [Order Flow]<br>
                    ↳ STATUS: <span class="status-online">HUNTING LIQUIDITY</span> | Vol: $1.2M<br>
                    <div class="progress-bar"><div class="progress-fill" style="width: 60%; background: var(--neon-cyan);"></div></div>
                </li>
                <li>
                    <strong><span class="status-active">▶ SQUADRA_GAMMA</span></strong> [Pairs Trading @ Bitget]<br>
                    ↳ STATUS: <span class="status-online">ARBITRAGE ACTIVE</span> | Spread: 0.15%<br>
                    <div class="progress-bar"><div class="progress-fill" style="width: 92%;"></div></div>
                </li>
            </ul>
        </div>

        <div class="panel">
            <h2>🛡️ PROTOCOLLO TRINITY (GHOST MODE)</h2>
            <ul>
                <li>
                    <span>🕴️ <strong>Lo Strozzino</strong></span> [Funding Arb]<br>
                    ↳ <span class="status-online">BACKGROUND ROUTINE ONLINE</span> // Yield: +18% APY
                </li>
                <li>
                    <span>🧮 <strong>Il Contabile</strong></span> [DCA Engine]<br>
                    ↳ <span class="status-online">BACKGROUND ROUTINE ONLINE</span> // Next buy: 04:22:10
                </li>
                <li>
                    <span>👼 <strong>L'Angelo Custode</strong></span> [MEV @ Arbitrum]<br>
                    ↳ <span class="status-online">BACKGROUND ROUTINE ONLINE</span> // Mempool sniper ready
                </li>
            </ul>
        </div>
    </div>

    <div class="panel">
        <h2>📊 METRICHE DI MERCATO (LIVE SENSOR FEED)</h2>
        <div class="grid">
            <div>
                <h3>🔮 The Oracle (Binance Sentiment)</h3>
                <p>
                    [+] FEAR & GREED INDEX: <span style="color: #ff0">72 (GREED)</span><br>
                    [+] BTC DOMINANCE: 52.4%<br>
                    [+] ORDERBOOK IMBALANCE: +14% BID<br>
                    [!] SIGNAL: <span class="status-online">BULLISH MOMENTUM DETECTED</span>
                </p>
            </div>
            <div>
                <h3>🐋 Whale Tracker Sonar</h3>
                <p>
                    <span class="status-alert">⚠️ ALERT:</span> 5,000 BTC moved to Coinbase Prime<br>
                    <span class="status-alert">⚠️ ALERT:</span> 50,000,000 USDT minted @ Tether Treasury<br>
                    [+] TRACKING STATUS: <span class="status-active">PINGING WALLETS...</span>
                </p>
            </div>
        </div>
    </div>
    
    <p style="text-align: center; margin-top: 30px; opacity: 0.5;">
        (c) 2026 NUVOLA QUANTITATIVE SYSTEMS // UNAUTHORIZED ACCESS WILL BE TERMINATED
    </p>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
