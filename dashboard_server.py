from flask import Flask, render_template_string
import os

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NUVOLA ORBITAL COMMAND</title>
    <style>
        :root {
            --bg: #050505;
            --neon-green: #0f0;
            --neon-cyan: #0ff;
            --neon-magenta: #f0f;
            --neon-red: #ff003c;
            --text-main: #e0e0e0;
            --font: 'Courier New', Courier, monospace;
        }
        body {
            background-color: var(--bg);
            color: var(--text-main);
            font-family: var(--font);
            margin: 0;
            padding: 20px;
            overflow-x: hidden;
        }
        .scanlines {
            position: fixed;
            top: 0; left: 0; width: 100vw; height: 100vh;
            background: linear-gradient(to bottom, rgba(255,255,255,0), rgba(255,255,255,0) 50%, rgba(0,0,0,0.2) 50%, rgba(0,0,0,0.2));
            background-size: 100% 4px;
            pointer-events: none;
            z-index: 9999;
        }
        h1 {
            text-align: center;
            color: var(--neon-cyan);
            text-shadow: 0 0 10px var(--neon-cyan), 0 0 20px var(--neon-cyan);
            border-bottom: 2px solid var(--neon-cyan);
            padding-bottom: 10px;
            text-transform: uppercase;
            letter-spacing: 5px;
        }
        .container {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            max-width: 1200px;
            margin: 0 auto;
        }
        .panel {
            background: rgba(10, 20, 10, 0.8);
            border: 1px solid var(--neon-green);
            box-shadow: 0 0 10px rgba(0, 255, 0, 0.2), inset 0 0 10px rgba(0, 255, 0, 0.1);
            padding: 20px;
            border-radius: 5px;
            position: relative;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; width: 100%; height: 2px;
            background: var(--neon-green);
            box-shadow: 0 0 10px var(--neon-green);
        }
        .panel h2 {
            color: var(--neon-green);
            text-shadow: 0 0 5px var(--neon-green);
            margin-top: 0;
            border-bottom: 1px dashed var(--neon-green);
            padding-bottom: 5px;
            font-size: 1.2em;
        }
        .status-online { color: var(--neon-green); text-shadow: 0 0 5px var(--neon-green); font-weight: bold; animation: pulse 2s infinite; }
        .status-standby { color: var(--neon-cyan); text-shadow: 0 0 5px var(--neon-cyan); font-weight: bold; }
        .status-warning { color: var(--neon-magenta); text-shadow: 0 0 5px var(--neon-magenta); font-weight: bold; }
        
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.5; }
            100% { opacity: 1; }
        }
        
        ul { list-style-type: none; padding: 0; }
        li { margin-bottom: 10px; font-size: 0.9em; border-left: 2px solid var(--neon-cyan); padding-left: 10px; background: rgba(0, 255, 255, 0.05); }
        
        .grid-data {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 5px;
            font-size: 0.8em;
            margin-top: 10px;
        }
        .grid-data div {
            border: 1px solid rgba(0,255,255,0.3);
            padding: 5px;
            text-align: center;
            background: rgba(0,0,0,0.5);
        }
        .value { color: var(--neon-magenta); font-weight: bold; }
        
        /* Specific panel overrides */
        .panel.trinity { border-color: var(--neon-cyan); box-shadow: 0 0 10px rgba(0, 255, 255, 0.2); }
        .panel.trinity::before { background: var(--neon-cyan); box-shadow: 0 0 10px var(--neon-cyan); }
        .panel.trinity h2 { color: var(--neon-cyan); border-color: var(--neon-cyan); text-shadow: 0 0 5px var(--neon-cyan);}
        
        .panel.metrics { border-color: var(--neon-magenta); box-shadow: 0 0 10px rgba(255, 0, 255, 0.2); grid-column: span 2; }
        .panel.metrics::before { background: var(--neon-magenta); box-shadow: 0 0 10px var(--neon-magenta); }
        .panel.metrics h2 { color: var(--neon-magenta); border-color: var(--neon-magenta); text-shadow: 0 0 5px var(--neon-magenta);}
    </style>
</head>
<body>
    <div class="scanlines"></div>
    <h1>🛰️ ORBITAL COMMAND // NUVOLA SYSTEM</h1>
    
    <div style="text-align: center; margin-bottom: 20px; font-size: 1.2em; border: 1px solid var(--neon-cyan); padding: 10px; background: rgba(0, 255, 255, 0.1); color: var(--neon-cyan); text-shadow: 0 0 5px var(--neon-cyan); border-radius: 5px;">
        <span class="status-online" style="animation: pulse 2s infinite;">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</span>
    </div>

    <div class="container">
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <ul>
                <li>
                    <strong>[α] SQUADRA_ALPHA</strong> (Scalper / Binance) <br>
                    STATUS: <span class="status-online">ENGAGED [ONLINE]</span><br>
                    <em>Latency: 12ms | Win Rate: 68.4%</em>
                </li>
                <li>
                    <strong>[δ] SQUADRA_DELTA</strong> (Order Flow) <br>
                    STATUS: <span class="status-online">SCANNING [ONLINE]</span><br>
                    <em>Imbalance Det: High | Volume: 4.2M</em>
                </li>
                <li>
                    <strong>[γ] SQUADRA_GAMMA</strong> (Pairs Trading / Bitget) <br>
                    STATUS: <span class="status-standby">STANDBY [AWAITING DIVERGENCE]</span><br>
                    <em>Z-Score: 1.84 (Threshold 2.0)</em>
                </li>
            </ul>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel trinity">
            <h2>🔺 PROTOCOLLO TRINITY</h2>
            <ul>
                <li>
                    <strong>🦇 Lo Strozzino</strong> (Funding Arb) <br>
                    STATUS: <span class="status-online">ACTIVE [BACKGROUND]</span><br>
                    <em>Yielding: +14.2% APR | Spread: 0.04%</em>
                </li>
                <li>
                    <strong>🧮 Il Contabile</strong> (Smart DCA) <br>
                    STATUS: <span class="status-online">ACTIVE [BACKGROUND]</span><br>
                    <em>Next execution: 04:12:00 | Asset: BTC</em>
                </li>
                <li>
                    <strong>🛡️ L'Angelo Custode</strong> (MEV / Arbitrum) <br>
                    STATUS: <span class="status-online">ACTIVE [BACKGROUND]</span><br>
                    <em>Mempool: Monitoring | Frontrun: Armed</em>
                </li>
            </ul>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel metrics">
            <h2>📊 METRICHE DI MERCATO GLOBALE</h2>
            <div class="grid-data">
                <div><strong>👁️ THE ORACLE</strong><br>Binance Sentiment<br><span class="value">EXTREME GREED (82)</span></div>
                <div><strong>🐋 WHALE TRACKER</strong><br>Net Flow (24h)<br><span class="value">+14,500 BTC</span></div>
                <div><strong>⚡ LIQUIDITY MAP</strong><br>Orderbook Imbalance<br><span class="value">BID HEAVY (64%)</span></div>
                <div><strong>🔥 BURN RATE</strong><br>Gas Base Fee<br><span class="value">14 Gwei</span></div>
                <div><strong>🔗 CROSS-CHAIN</strong><br>Bridge Volume<br><span class="value">$1.2B/Day</span></div>
                <div><strong>⚠️ VOLATILITY INDEX</strong><br>Deribit DVOL<br><span class="value">48.2 (ELEVATED)</span></div>
            </div>
        </div>
    </div>
    
    <div style="text-align: center; margin-top: 30px; font-size: 0.8em; color: #555;">
        [SYSTEM: NUVOLA OS v4.2.1] - ALL SYSTEMS NOMINAL - ENCRYPTION: AES-256
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
