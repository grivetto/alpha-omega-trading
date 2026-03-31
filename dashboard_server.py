from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ORBITAL COMMAND | NUVOLA</title>
    <style>
        body {
            background-color: #050505;
            color: #0f0;
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            background-image: 
                radial-gradient(circle at 50% 50%, #0a1a0a 0%, #000 100%),
                linear-gradient(rgba(0, 255, 0, 0.03) 1px, transparent 1px),
                linear-gradient(90deg, rgba(0, 255, 0, 0.03) 1px, transparent 1px);
            background-size: 100% 100%, 20px 20px, 20px 20px;
        }
        h1, h2, h3 {
            text-transform: uppercase;
            text-shadow: 0 0 10px #0f0;
            border-bottom: 1px solid #0f0;
            padding-bottom: 5px;
            margin-top: 0;
        }
        .container {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            max-width: 1200px;
            margin: auto;
        }
        .panel {
            border: 1px solid #0f0;
            padding: 20px;
            box-shadow: 0 0 15px rgba(0, 255, 0, 0.2) inset, 0 0 10px #0f0;
            background: rgba(0, 20, 0, 0.7);
            position: relative;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; width: 100%; height: 2px;
            background: #0f0;
            box-shadow: 0 0 10px #0f0;
        }
        .trinity { color: #0ff; text-shadow: 0 0 10px #0ff; border-color: #0ff; box-shadow: 0 0 15px rgba(0, 255, 255, 0.2) inset, 0 0 10px #0ff; }
        .trinity h2, .trinity .panel::before { border-color: #0ff; background: #0ff; box-shadow: 0 0 10px #0ff; }
        .metrics { color: #f0f; text-shadow: 0 0 10px #f0f; border-color: #f0f; box-shadow: 0 0 15px rgba(255, 0, 255, 0.2) inset, 0 0 10px #f0f; }
        .metrics h2, .metrics .panel::before { border-color: #f0f; background: #f0f; box-shadow: 0 0 10px #f0f; }
        
        .status-online { color: #0f0; animation: blink 1s infinite; font-weight: bold; }
        .status-active { color: #0ff; animation: pulse 2s infinite; font-weight: bold; }
        
        @keyframes blink { 0% { opacity: 1; text-shadow: 0 0 10px #0f0; } 50% { opacity: 0.4; text-shadow: none; } 100% { opacity: 1; text-shadow: 0 0 10px #0f0; } }
        @keyframes pulse { 0% { text-shadow: 0 0 5px #0ff; } 50% { text-shadow: 0 0 20px #0ff; } 100% { text-shadow: 0 0 5px #0ff; } }
        
        ul { list-style-type: none; padding-left: 0; margin: 0; }
        li { margin-bottom: 12px; padding: 10px; background: rgba(0,0,0,0.6); border-left: 3px solid; transition: all 0.2s ease; }
        li:hover { transform: translateX(5px); background: rgba(20,20,20,0.8); }
        .squad-li { border-color: #0f0; }
        .trinity-li { border-color: #0ff; }
        .metric-li { border-color: #f0f; display: flex; justify-content: space-between; border-left: none; border-bottom: 1px dashed #f0f; padding: 5px 0;}
        .metric-li:hover { transform: none; background: transparent; text-shadow: 0 0 15px #f0f; }
    </style>
</head>
<body>
    <h1 style="text-align: center; font-size: 2.5em; letter-spacing: 5px;">🛰️ ORBITAL COMMAND 🛰️</h1>
    <p style="text-align: center; font-size: 1.2em; margin-bottom: 15px;">[SYSTEM NUVOLA ONLINE - CORE V_2.4.0] <span class="status-online">● LIVE & SECURE</span></p>
    <div style="text-align: center; margin-bottom: 30px; font-size: 1.3em; font-weight: bold; padding: 10px; border: 1px dashed #0ff; color: #0ff; background: rgba(0, 255, 255, 0.1); display: inline-block; position: relative; left: 50%; transform: translateX(-50%); box-shadow: 0 0 10px #0ff;">
        ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
    </div>

    <div class="container">
        <!-- SQUADRE D'ASSALTO -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <ul>
                <li class="squad-li">
                    <strong>[SQUADRA_ALPHA]</strong> ⚡ Binance Scalper<br>
                    <span style="font-size: 0.9em; color: #888;">High-Frequency Order Book Snipping</span><br>
                    Status: <span class="status-active">ENGAGED</span> | Ping: 12ms | PnL: <span style="color:#0f0">+$142.50</span> (1h)
                </li>
                <li class="squad-li">
                    <strong>[SQUADRA_DELTA]</strong> 🌊 Order Flow<br>
                    <span style="font-size: 0.9em; color: #888;">Liquidity Trap & VWAP execution</span><br>
                    Status: <span class="status-active">SCANNING</span> | Depth: 50 levels | Targets: 3
                </li>
                <li class="squad-li">
                    <strong>[SQUADRA_GAMMA]</strong> ⚖️ Bitget Pairs<br>
                    <span style="font-size: 0.9em; color: #888;">Statistical Arbitrage / Cointegration</span><br>
                    Status: <span class="status-active">ARBITRAGE</span> | Spread: 0.45% | Active: BTC/ETH
                </li>
            </ul>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel trinity">
            <h2>🔺 PROTOCOLLO TRINITY</h2>
            <ul>
                <li class="trinity-li">
                    <strong>🕴️ Lo Strozzino</strong> (Funding Arb)<br>
                    <span style="font-size: 0.9em; color: #888;">Spot/Perp Delta Neutral</span><br>
                    Status: <span class="status-online">BACKGROUND ONLINE</span> | APR: 14.2%
                </li>
                <li class="trinity-li">
                    <strong>💼 Il Contabile</strong> (DCA)<br>
                    <span style="font-size: 0.9em; color: #888;">Smart Accumulation Matrix</span><br>
                    Status: <span class="status-online">BACKGROUND ONLINE</span> | Next Buy: 4h 20m
                </li>
                <li class="trinity-li">
                    <strong>👼 L'Angelo Custode</strong> (MEV Arbitrum)<br>
                    <span style="font-size: 0.9em; color: #888;">Sandwich / Front-run Protection</span><br>
                    Status: <span class="status-online">BACKGROUND ONLINE</span> | Mempool: Monitoring
                </li>
            </ul>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel metrics" style="grid-column: span 2;">
            <h2>📊 METRICHE DI MERCATO & INTEL</h2>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 30px;">
                <div>
                    <h3>👁️ The Oracle (Binance Sentiment)</h3>
                    <ul>
                        <li class="metric-li"><span>Fear/Greed Index:</span> <span>67 [GREED]</span></li>
                        <li class="metric-li"><span>Long/Short Ratio:</span> <span>1.14</span></li>
                        <li class="metric-li"><span>Order Book Imbalance:</span> <span>+5.2% (Bids)</span></li>
                        <li class="metric-li"><span>Funding Rate (BTC):</span> <span>0.01%</span></li>
                    </ul>
                </div>
                <div>
                    <h3>🐋 Whale Tracker</h3>
                    <ul>
                        <li class="metric-li"><span>Recent Anomaly:</span> <span>1500 BTC -> Coinbase</span></li>
                        <li class="metric-li"><span>Exchange Netflow:</span> <span>-$450M (24h)</span></li>
                        <li class="metric-li"><span>Stablecoin Minting:</span> <span>+$1B (Tether)</span></li>
                        <li class="metric-li"><span>DEX Large Swaps:</span> <span>$12M USDC -> WETH</span></li>
                    </ul>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        // Matrix style random char effect on titles
        setInterval(() => {
            const els = document.querySelectorAll('strong');
            if(els.length > 0) {
                const randomEl = els[Math.floor(Math.random() * els.length)];
                randomEl.style.opacity = '0.5';
                setTimeout(() => randomEl.style.opacity = '1', 100);
            }
        }, 2000);
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    # Running on standard local port, easy to access
    app.run(host='0.0.0.0', port=5000, debug=False)
