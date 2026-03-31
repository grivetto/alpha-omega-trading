from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ORBITAL COMMAND - NUVOLA DASHBOARD</title>
    <style>
        :root {
            --neon-green: #0f0;
            --neon-blue: #0ff;
            --neon-pink: #f0f;
            --bg-color: #050505;
            --panel-bg: rgba(10, 20, 15, 0.8);
        }
        body {
            background-color: var(--bg-color);
            color: var(--neon-green);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            overflow-x: hidden;
        }
        h1, h2, h3 {
            text-transform: uppercase;
            text-shadow: 0 0 10px var(--neon-green);
            letter-spacing: 2px;
        }
        h1 { text-align: center; font-size: 2.5em; border-bottom: 2px solid var(--neon-green); padding-bottom: 10px; }
        .container { display: flex; flex-wrap: wrap; gap: 20px; justify-content: space-around; }
        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-green);
            box-shadow: 0 0 15px rgba(0, 255, 0, 0.2);
            padding: 20px;
            border-radius: 5px;
            flex: 1 1 300px;
            min-width: 300px;
            position: relative;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; bottom: 0;
            border: 2px solid transparent;
            background: linear-gradient(45deg, var(--neon-green), var(--neon-blue), var(--neon-pink)) border-box;
            -webkit-mask: linear-gradient(#fff 0 0) padding-box, linear-gradient(#fff 0 0);
            -webkit-mask-composite: destination-out;
            mask-composite: exclude;
            z-index: -1;
            opacity: 0.5;
            animation: pulse 2s infinite alternate;
        }
        @keyframes pulse {
            0% { opacity: 0.3; }
            100% { opacity: 0.8; }
        }
        .status-online { color: var(--neon-green); text-shadow: 0 0 5px var(--neon-green); }
        .status-active { color: var(--neon-blue); text-shadow: 0 0 5px var(--neon-blue); }
        .status-warning { color: var(--neon-pink); text-shadow: 0 0 5px var(--neon-pink); }
        .blink { animation: blinker 1s linear infinite; }
        @keyframes blinker { 50% { opacity: 0; } }
        ul { list-style-type: none; padding: 0; }
        li { margin-bottom: 10px; border-bottom: 1px dashed rgba(0,255,0,0.3); padding-bottom: 5px; }
        .emoji { font-size: 1.2em; margin-right: 10px; }
        .metric-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
        .metric-box { border: 1px solid var(--neon-blue); padding: 10px; text-align: center; }
        .metric-val { font-size: 1.5em; color: var(--neon-blue); text-shadow: 0 0 8px var(--neon-blue); }
    </style>
</head>
<body>
    <h1><span class="emoji">🛰️</span> ORBITAL COMMAND <span class="blink">_</span></h1>
    <div style="text-align: center; font-size: 1.2em; margin-bottom: 20px; color: var(--neon-blue); text-shadow: 0 0 5px var(--neon-blue);">
        <strong>⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</strong>
    </div>
    <div class="container">
        <!-- SQUADRE D'ASSALTO -->
        <div class="panel">
            <h2><span class="emoji">⚔️</span> SQUADRE D'ASSALTO (HFT)</h2>
            <ul>
                <li><span class="emoji">🐺</span> <strong>SQUADRA_ALPHA</strong><br/>
                    Target: Binance Scalper <br/>
                    Status: <span class="status-active">ENGAGING TARGETS [ACTIVE]</span><br/>
                    Win Rate: 78.4% | Ping: 12ms
                </li>
                <li><span class="emoji">🌊</span> <strong>SQUADRA_DELTA</strong><br/>
                    Target: Order Flow Analysis <br/>
                    Status: <span class="status-online">MONITORING LIQUIDITY [ONLINE]</span><br/>
                    Imbalance: +4.2M Buy
                </li>
                <li><span class="emoji">⚖️</span> <strong>SQUADRA_GAMMA</strong><br/>
                    Target: Bitget Pairs Trading <br/>
                    Status: <span class="status-active">ARBITRAGE EXEC [ACTIVE]</span><br/>
                    Spread: 0.15% (BTC/ETH)
                </li>
            </ul>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2><span class="emoji">🔺</span> PROTOCOLLO TRINITY</h2>
            <ul>
                <li><span class="emoji">🕴️</span> <strong>Lo Strozzino</strong><br/>
                    Role: Funding Rate Arbitrage <br/>
                    Status: <span class="status-online">COLLECTING PREMIUMS [ONLINE]</span><br/>
                    Est. APY: 24.5%
                </li>
                <li><span class="emoji">🧮</span> <strong>Il Contabile</strong><br/>
                    Role: Smart DCA Engine <br/>
                    Status: <span class="status-online">ACCUMULATING [ONLINE]</span><br/>
                    Next Buy: 04h 12m
                </li>
                <li><span class="emoji">👼</span> <strong>L'Angelo Custode</strong><br/>
                    Role: MEV Protection (Arbitrum) <br/>
                    Status: <span class="status-active">SHIELD UP [ACTIVE]</span><br/>
                    Attacks Blocked: 14
                </li>
            </ul>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <h2><span class="emoji">👁️</span> METRICHE DI MERCATO</h2>
            <div class="metric-grid">
                <div class="metric-box">
                    <div>THE ORACLE (Binance Sentiment)</div>
                    <div class="metric-val status-active">BULLISH 72%</div>
                </div>
                <div class="metric-box">
                    <div>WHALE TRACKER (Net Flow)</div>
                    <div class="metric-val status-warning">+ $142.5M</div>
                </div>
                <div class="metric-box">
                    <div>GLOBAL VOLATILITY INDEX</div>
                    <div class="metric-val status-online" id="volatility">MODERATE (42)</div>
                </div>
                <div class="metric-box">
                    <div>SYSTEM LOAD (Nuvola)</div>
                    <div class="metric-val status-online" id="sysload">14.2% CPU</div>
                </div>
            </div>
            <p style="margin-top: 20px; font-size: 0.9em; opacity: 0.7;">
                <span class="blink">>></span> SIGNAL FEED: Tracking 15,402 active wallets... Anomalous flow detected on ERC-20 subnet... Resolving...
            </p>
        </div>
    </div>
    
    <script>
        setInterval(() => {
            const vols = [41, 42, 43, 44, 40];
            const loads = [14.1, 14.2, 14.5, 13.9, 15.0];
            document.getElementById('volatility').innerText = "MODERATE (" + vols[Math.floor(Math.random()*vols.length)] + ")";
            document.getElementById('sysload').innerText = loads[Math.floor(Math.random()*loads.length)].toFixed(1) + "% CPU";
        }, 3000);
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
