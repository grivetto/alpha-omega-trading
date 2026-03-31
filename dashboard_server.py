from flask import Flask, render_template_string
import os

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NUVOLA ORBITAL COMMAND // TACTICAL DASHBOARD</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');
        
        :root {
            --neon-blue: #0ff;
            --neon-pink: #f0f;
            --neon-green: #39ff14;
            --neon-yellow: #ffea00;
            --neon-red: #ff003c;
            --bg-dark: #05050a;
            --panel-bg: rgba(5, 10, 20, 0.85);
            --grid-color: rgba(0, 255, 255, 0.05);
        }
        
        * { box-sizing: border-box; }
        
        body {
            background-color: var(--bg-dark);
            color: var(--neon-blue);
            font-family: 'Share Tech Mono', monospace;
            margin: 0;
            padding: 20px;
            background-image: 
                linear-gradient(var(--grid-color) 1px, transparent 1px),
                linear-gradient(90deg, var(--grid-color) 1px, transparent 1px);
            background-size: 40px 40px;
            overflow-x: hidden;
            text-shadow: 0 0 5px rgba(0, 255, 255, 0.5);
        }
        
        /* CRT overlay effect */
        body::after {
            content: " ";
            display: block;
            position: fixed;
            top: 0; left: 0; bottom: 0; right: 0;
            background: linear-gradient(rgba(18, 16, 16, 0) 50%, rgba(0, 0, 0, 0.25) 50%), linear-gradient(90deg, rgba(255, 0, 0, 0.06), rgba(0, 255, 0, 0.02), rgba(0, 0, 255, 0.06));
            z-index: 2;
            background-size: 100% 2px, 3px 100%;
            pointer-events: none;
        }

        .scanline {
            width: 100%; height: 100px;
            z-index: 9999; position: fixed;
            pointer-events: none;
            background: linear-gradient(0deg, transparent 0%, rgba(0,255,255,0.2) 50%, transparent 100%);
            opacity: 0.1;
            animation: scanline 8s linear infinite;
        }
        @keyframes scanline {
            0% { top: -100px; }
            100% { top: 100vh; }
        }

        h1, h2, h3 {
            text-transform: uppercase;
            letter-spacing: 3px;
            margin-top: 0;
            font-weight: normal;
        }

        .header {
            text-align: center;
            padding: 20px;
            border: 2px solid var(--neon-blue);
            box-shadow: 0 0 20px rgba(0, 255, 255, 0.4), inset 0 0 20px rgba(0, 255, 255, 0.2);
            margin-bottom: 30px;
            background: linear-gradient(90deg, transparent, rgba(0,255,255,0.1), transparent);
            position: relative;
            z-index: 10;
        }
        
        .header h1 {
            color: var(--neon-blue);
            text-shadow: 0 0 10px var(--neon-blue), 0 0 20px var(--neon-blue);
            margin-bottom: 10px;
            font-size: 2.5em;
        }

        .status-bar {
            display: flex;
            justify-content: center;
            gap: 30px;
            font-size: 1.2em;
            margin-top: 15px;
        }

        .blink { animation: blink 1.5s infinite; }
        .blink-fast { animation: blink 0.5s infinite; }
        @keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }

        .text-green { color: var(--neon-green); text-shadow: 0 0 10px var(--neon-green); }
        .text-red { color: var(--neon-red); text-shadow: 0 0 10px var(--neon-red); }
        .text-pink { color: var(--neon-pink); text-shadow: 0 0 10px var(--neon-pink); }
        .text-yellow { color: var(--neon-yellow); text-shadow: 0 0 10px var(--neon-yellow); }

        .container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 30px;
            position: relative;
            z-index: 10;
        }

        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-blue);
            padding: 20px;
            position: relative;
            box-shadow: inset 0 0 15px rgba(0, 255, 255, 0.1);
            backdrop-filter: blur(4px);
            transition: all 0.3s;
        }
        
        .panel::before {
            content: '';
            position: absolute;
            top: -2px; left: -2px; right: -2px; bottom: -2px;
            background: linear-gradient(45deg, var(--neon-blue), transparent, var(--neon-pink));
            z-index: -1;
            opacity: 0.3;
        }

        .panel:hover {
            box-shadow: inset 0 0 30px rgba(0, 255, 255, 0.2), 0 0 20px rgba(0, 255, 255, 0.3);
            border-color: var(--neon-pink);
        }

        .panel h2 {
            color: var(--neon-blue);
            border-bottom: 1px solid var(--neon-blue);
            padding-bottom: 10px;
            display: flex;
            align-items: center;
            gap: 10px;
            font-size: 1.5em;
        }
        
        .panel.squads h2 { color: var(--neon-red); border-bottom-color: var(--neon-red); text-shadow: 0 0 10px var(--neon-red); }
        .panel.trinity h2 { color: var(--neon-pink); border-bottom-color: var(--neon-pink); text-shadow: 0 0 10px var(--neon-pink); }
        .panel.metrics h2 { color: var(--neon-yellow); border-bottom-color: var(--neon-yellow); text-shadow: 0 0 10px var(--neon-yellow); }

        .module {
            margin: 15px 0;
            padding: 15px;
            background: rgba(0, 0, 0, 0.6);
            border-left: 3px solid var(--neon-blue);
            position: relative;
        }
        
        .squads .module { border-left-color: var(--neon-red); }
        .trinity .module { border-left-color: var(--neon-pink); }
        .metrics .module { border-left-color: var(--neon-yellow); }

        .module::after {
            content: '';
            position: absolute;
            bottom: 0; right: 0;
            width: 10px; height: 10px;
            border-bottom: 2px solid;
            border-right: 2px solid;
            border-color: inherit;
        }

        .module-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
            font-size: 1.2em;
        }

        .module-title { font-weight: bold; letter-spacing: 1px; }
        .module-desc { font-size: 0.85em; color: #888; margin-bottom: 10px; }
        
        .status-badge {
            padding: 2px 8px;
            border-radius: 2px;
            font-size: 0.8em;
            background: rgba(57, 255, 20, 0.1);
            border: 1px solid var(--neon-green);
        }

        .data-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
            font-size: 0.9em;
        }

        .data-item {
            background: rgba(255, 255, 255, 0.05);
            padding: 5px 10px;
            border: 1px dotted rgba(0, 255, 255, 0.3);
        }

        .progress-bar {
            height: 4px;
            background: #222;
            margin-top: 8px;
            position: relative;
            overflow: hidden;
        }
        .progress-fill {
            height: 100%;
            background: var(--neon-blue);
            box-shadow: 0 0 10px var(--neon-blue);
        }
        .squads .progress-fill { background: var(--neon-red); box-shadow: 0 0 10px var(--neon-red); }
        .trinity .progress-fill { background: var(--neon-pink); box-shadow: 0 0 10px var(--neon-pink); }
        
        table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.9em;
            margin-top: 10px;
        }
        th, td {
            border: 1px solid rgba(255, 255, 255, 0.1);
            padding: 8px;
            text-align: left;
        }
        th { color: var(--neon-yellow); background: rgba(255, 234, 0, 0.05); }
        tr:hover { background: rgba(255, 255, 255, 0.05); }

    </style>
</head>
<body>
    <div class="scanline"></div>
    
    <div class="header">
        <h1>[ NUVOLA ORBITAL COMMAND ]</h1>
        <div class="status-bar">
            <div>CORE: <span class="text-green blink">ONLINE_V10.X</span></div>
            <div>UPLINK: <span class="text-blue">SECURE_TUNNEL</span></div>
            <div>DEFCON: <span class="text-yellow blink-fast">LEVEL 3</span></div>
        </div>
        <div style="margin-top: 15px; font-size: 1.1em; color: var(--neon-pink); text-shadow: 0 0 10px var(--neon-pink); font-weight: bold;">
            ⚙️ PROTOCOLLO TRINITY: <span class="text-green blink">Online (DCA, Funding, MEV)</span>
        </div>
    </div>

    <div class="container">
        
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel squads">
            <h2>⚔️ SQUADRE D'ASSALTO [HFT]</h2>
            
            <div class="module">
                <div class="module-header">
                    <span class="module-title text-red">🐺 SQUADRA_ALPHA</span>
                    <span class="status-badge text-green blink">ENGAGED</span>
                </div>
                <div class="module-desc">BINANCE SCALPER // MICRO-ARBITRAGE DRIVER</div>
                <div class="data-grid">
                    <div class="data-item">LATENCY: <span class="text-green">8ms</span></div>
                    <div class="data-item">WIN RATE: <span class="text-blue">68.4%</span></div>
                    <div class="data-item">EXEC/MIN: <span class="text-yellow">245</span></div>
                    <div class="data-item">TARGET: <span class="text-pink">BTC/USDT</span></div>
                </div>
                <div class="progress-bar"><div class="progress-fill" style="width: 85%; animation: scanline 2s infinite alternate;"></div></div>
            </div>

            <div class="module">
                <div class="module-header">
                    <span class="module-title text-red">🌊 SQUADRA_DELTA</span>
                    <span class="status-badge text-blue">MONITORING</span>
                </div>
                <div class="module-desc">ORDER FLOW TRACKER // LIQUIDITY SWEEP DETECTOR</div>
                <div class="data-grid">
                    <div class="data-item">LATENCY: <span class="text-green">14ms</span></div>
                    <div class="data-item">SPOOFS: <span class="text-red blink">DETECTED</span></div>
                    <div class="data-item">VOL PROFILE: <span class="text-blue">IMBALANCE</span></div>
                    <div class="data-item">TRIGGER: <span class="text-yellow">AWAITING</span></div>
                </div>
                <div class="progress-bar"><div class="progress-fill" style="width: 45%;"></div></div>
            </div>

            <div class="module">
                <div class="module-header">
                    <span class="module-title text-red">⚖️ SQUADRA_GAMMA</span>
                    <span class="status-badge text-green blink">ACTIVE</span>
                </div>
                <div class="module-desc">BITGET PAIRS TRADING // STAT-ARB SYNTHETICS</div>
                <div class="data-grid">
                    <div class="data-item">LATENCY: <span class="text-green">22ms</span></div>
                    <div class="data-item">Z-SCORE: <span class="text-red">2.41</span></div>
                    <div class="data-item">PAIR: <span class="text-pink">ETH/SOL</span></div>
                    <div class="data-item">EXPOSURE: <span class="text-blue">HEDGED</span></div>
                </div>
                <div class="progress-bar"><div class="progress-fill" style="width: 60%;"></div></div>
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel trinity">
            <h2>🛡️ PROTOCOLLO TRINITY</h2>
            <div style="margin-bottom: 15px; font-size: 0.9em; color: var(--neon-pink); border: 1px dashed var(--neon-pink); padding: 5px; text-align: center;">
                [ BACKGROUND DAEMONS RUNNING IN CLOAK MODE ]
            </div>
            
            <div class="module">
                <div class="module-header">
                    <span class="module-title text-pink">🧛‍♂️ LO STROZZINO</span>
                    <span class="status-badge text-green">HARVESTING</span>
                </div>
                <div class="module-desc">FUNDING ARBITRAGE // PERPETUAL SWAP PREMIUM EXTRACTOR</div>
                <div class="data-grid">
                    <div class="data-item">YIELD APY: <span class="text-green">18.2%</span></div>
                    <div class="data-item">POS: <span class="text-blue">DELTA-NEUTRAL</span></div>
                </div>
            </div>

            <div class="module">
                <div class="module-header">
                    <span class="module-title text-pink">🧮 IL CONTABILE</span>
                    <span class="status-badge text-blue">ACCUMULATING</span>
                </div>
                <div class="module-desc">DCA ENGINE // TWAP SCHEDULER</div>
                <div class="data-grid">
                    <div class="data-item">NEXT BUY: <span class="text-yellow">14:00Z</span></div>
                    <div class="data-item">SLIPPAGE: <span class="text-green">&lt; 0.05%</span></div>
                </div>
            </div>

            <div class="module">
                <div class="module-header">
                    <span class="module-title text-pink">👼 L'ANGELO CUSTODE</span>
                    <span class="status-badge text-green blink">DEFENDING</span>
                </div>
                <div class="module-desc">MEV ARBITRUM // FRONT-RUNNING PROTECTION</div>
                <div class="data-grid">
                    <div class="data-item">TX SHIELD: <span class="text-green">ACTIVE</span></div>
                    <div class="data-item">BLOCKED TXS: <span class="text-yellow">1,042</span></div>
                </div>
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel metrics">
            <h2>📡 METRICHE DI MERCATO</h2>
            
            <div class="module">
                <div class="module-header">
                    <span class="module-title text-yellow">👁️ THE ORACLE</span>
                    <span class="status-badge text-blue">SYNCED</span>
                </div>
                <div class="module-desc">BINANCE SENTIMENT ENGINE</div>
                <table>
                    <tr><th>METRIC</th><th>VALUE</th><th>SIGNAL</th></tr>
                    <tr><td>FEAR/GREED</td><td><span class="text-red">82 (EXTR. GREED)</span></td><td><span class="text-red blink">SELL ZONE</span></td></tr>
                    <tr><td>L/S RATIO</td><td><span id="ls-ratio" class="text-green">1.45</span></td><td><span class="text-blue">BULL BIAS</span></td></tr>
                    <tr><td>VOLATILITY</td><td><span class="text-yellow">48.2 (VIX)</span></td><td><span class="text-yellow">ELEVATED</span></td></tr>
                </table>
            </div>

            <div class="module">
                <div class="module-header">
                    <span class="module-title text-yellow">🐋 WHALE TRACKER</span>
                    <span class="status-badge text-green blink">SCANNING</span>
                </div>
                <div class="module-desc">ON-CHAIN FLOW ANALYSIS</div>
                <table>
                    <tr><th>ASSET</th><th>24H DELTA</th><th>ALERT STATUS</th></tr>
                    <tr><td>BTC</td><td><span class="text-green">+54,110</span></td><td><span class="text-green">INFLOW</span></td></tr>
                    <tr><td>ETH</td><td><span class="text-red">-105,300</span></td><td><span class="text-red blink">EXCHANGE OUTFLOW</span></td></tr>
                    <tr><td>SOL</td><td><span class="text-green">+12,500K</span></td><td><span class="text-yellow">ACCUMULATION</span></td></tr>
                </table>
            </div>
            
            <div style="margin-top: 20px; text-align: center; border-top: 1px dotted var(--neon-yellow); padding-top: 10px;">
                <span class="text-blue blink-fast">&gt;&gt; AWAITING NEW DIRECTIVES &lt;&lt;</span>
            </div>
        </div>
    </div>

    <script>
        // Matrix style random numbers for live effect
        setInterval(() => {
            const ls = (1.40 + (Math.random() * 0.1)).toFixed(2);
            document.getElementById('ls-ratio').innerText = ls;
        }, 2000);
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
