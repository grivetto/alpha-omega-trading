from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ORBITAL COMMAND - NUVOLA</title>
    <style>
        :root {
            --neon-green: #0f0;
            --neon-cyan: #0ff;
            --neon-magenta: #f0f;
            --bg-color: #050505;
            --panel-bg: #0a0a0a;
            --border-color: #333;
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
            text-shadow: 0 0 10px currentColor;
            margin-top: 0;
        }
        .header {
            text-align: center;
            border-bottom: 2px solid var(--neon-cyan);
            padding-bottom: 20px;
            margin-bottom: 30px;
            box-shadow: 0 10px 20px -10px var(--neon-cyan);
        }
        .header h1 {
            color: var(--neon-cyan);
            font-size: 3em;
            letter-spacing: 5px;
        }
        .blink {
            animation: blinker 1.5s linear infinite;
        }
        @keyframes blinker {
            50% { opacity: 0; }
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
        }
        .panel {
            background-color: var(--panel-bg);
            border: 1px solid var(--border-color);
            border-left: 4px solid var(--neon-green);
            padding: 20px;
            position: relative;
            box-shadow: 0 0 15px rgba(0, 255, 0, 0.1);
            transition: all 0.3s ease;
        }
        .panel:hover {
            box-shadow: 0 0 25px rgba(0, 255, 0, 0.3);
            border-left: 4px solid var(--neon-cyan);
        }
        .panel.magenta { border-left-color: var(--neon-magenta); color: #ddd; }
        .panel.magenta:hover { box-shadow: 0 0 25px rgba(255, 0, 255, 0.3); }
        .panel.cyan { border-left-color: var(--neon-cyan); color: #ddd; }
        .panel.cyan:hover { box-shadow: 0 0 25px rgba(0, 255, 255, 0.3); }
        
        .status-indicator {
            display: inline-block;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background-color: var(--neon-green);
            box-shadow: 0 0 8px var(--neon-green);
            margin-right: 10px;
        }
        .status-indicator.active { animation: pulse 1s infinite; }
        @keyframes pulse {
            0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(0, 255, 0, 0.7); }
            70% { transform: scale(1); box-shadow: 0 0 0 10px rgba(0, 255, 0, 0); }
            100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(0, 255, 0, 0); }
        }
        ul { list-style-type: none; padding: 0; }
        li { margin-bottom: 15px; border-bottom: 1px dashed #333; padding-bottom: 5px; display: flex; justify-content: space-between; align-items: center; }
        .tag { font-size: 0.8em; padding: 2px 5px; background: #222; border-radius: 3px; border: 1px solid #444; }
        .value { color: var(--neon-cyan); font-weight: bold; }
        
        .scanline {
            width: 100%;
            height: 100px;
            z-index: 9999;
            position: absolute;
            pointer-events: none;
            background: linear-gradient(0deg, rgba(0,0,0,0) 0%, rgba(0,255,0,0.1) 50%, rgba(0,0,0,0) 100%);
            opacity: 0.1;
            animation: scanline 6s linear infinite;
        }
        @keyframes scanline {
            0% { top: -100px; }
            100% { top: 100%; }
        }
    </style>
</head>
<body>
    <div class="scanline"></div>
    <div class="header">
        <h1>🛰️ ORBITAL COMMAND</h1>
        <p class="blink" style="color: var(--neon-magenta);">[ SYSTEM SECURED - PROTOCOLLO ONLINE ]</p>
        <div style="color: var(--neon-cyan); font-weight: bold; font-size: 1.2em; border: 1px solid var(--neon-cyan); display: inline-block; padding: 10px; margin-top: 10px; box-shadow: 0 0 10px var(--neon-cyan);">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</div>
    </div>

    <div class="grid">
        <!-- HFT SQUADS -->
        <div class="panel">
            <h2 style="color: var(--neon-green);">⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <ul>
                <li>
                    <div>
                        <span class="status-indicator active"></span>
                        <strong>SQUADRA_ALPHA</strong> <span class="tag">Binance Scalper</span>
                    </div>
                    <span class="value">ACTIVE (Latency: 12ms)</span>
                </li>
                <li>
                    <div>
                        <span class="status-indicator active"></span>
                        <strong>SQUADRA_DELTA</strong> <span class="tag">Order Flow</span>
                    </div>
                    <span class="value">AWAITING VOLATILITY</span>
                </li>
                <li>
                    <div>
                        <span class="status-indicator active"></span>
                        <strong>SQUADRA_GAMMA</strong> <span class="tag">Bitget Pairs</span>
                    </div>
                    <span class="value">HEDGED</span>
                </li>
            </ul>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel magenta">
            <h2 style="color: var(--neon-magenta);">🧬 PROTOCOLLO TRINITY</h2>
            <ul>
                <li>
                    <div>
                        <span class="status-indicator active" style="background-color: var(--neon-magenta); box-shadow: 0 0 8px var(--neon-magenta);"></span>
                        <strong>Lo Strozzino</strong> <span class="tag">Funding Arb</span>
                    </div>
                    <span class="value" style="color: var(--neon-magenta);">BACKGROUND YIELD</span>
                </li>
                <li>
                    <div>
                        <span class="status-indicator active" style="background-color: var(--neon-magenta); box-shadow: 0 0 8px var(--neon-magenta);"></span>
                        <strong>Il Contabile</strong> <span class="tag">DCA Master</span>
                    </div>
                    <span class="value" style="color: var(--neon-magenta);">ACCUMULATING</span>
                </li>
                <li>
                    <div>
                        <span class="status-indicator active" style="background-color: var(--neon-magenta); box-shadow: 0 0 8px var(--neon-magenta);"></span>
                        <strong>L'Angelo Custode</strong> <span class="tag">MEV Arbitrum</span>
                    </div>
                    <span class="value" style="color: var(--neon-magenta);">WATCHING MEMPOOL</span>
                </li>
            </ul>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel cyan">
            <h2 style="color: var(--neon-cyan);">📊 METRICHE DI MERCATO</h2>
            <ul>
                <li>
                    <div><strong>The Oracle</strong> <span class="tag">Binance Sentiment</span></div>
                    <span class="value" id="oracle-val">BULLISH 68%</span>
                </li>
                <li>
                    <div><strong>Whale Tracker</strong> <span class="tag">Large Txs</span></div>
                    <span class="value" id="whale-val">12 ANOMALIES DETECTED</span>
                </li>
                <li>
                    <div><strong>Global Liquidity Index</strong> <span class="tag">Macro</span></div>
                    <span class="value">STABLE</span>
                </li>
            </ul>
        </div>
    </div>
    
    <script>
        setInterval(() => {
            const oracleVals = ['BULLISH 68%', 'BULLISH 72%', 'NEUTRAL 51%', 'BEARISH 44%', 'BULLISH 89%'];
            document.getElementById('oracle-val').innerText = oracleVals[Math.floor(Math.random() * oracleVals.length)];
            
            const anomalies = Math.floor(Math.random() * 20);
            document.getElementById('whale-val').innerText = anomalies + ' ANOMALIES DETECTED';
        }, 3000);
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
