from flask import Flask

app = Flask(__name__)

HTML_CONTENT = """<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ORBITAL COMMAND | NUVOLA</title>
    <style>
        :root {
            --neon-green: #39ff14;
            --neon-blue: #00f3ff;
            --neon-pink: #ff00ff;
            --neon-yellow: #ffff00;
            --bg-color: #050505;
        }
        body {
            background-color: var(--bg-color);
            color: var(--neon-green);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 30px;
            text-transform: uppercase;
            background-image: linear-gradient(rgba(0, 255, 0, 0.03) 1px, transparent 1px),
            linear-gradient(90deg, rgba(0, 255, 0, 0.03) 1px, transparent 1px);
            background-size: 20px 20px;
        }
        h1 {
            color: var(--neon-blue);
            text-align: center;
            font-size: 2.5em;
            letter-spacing: 4px;
            text-shadow: 0 0 5px var(--neon-blue), 0 0 15px var(--neon-blue), 0 0 30px var(--neon-blue);
            margin-bottom: 5px;
        }
        .subtitle {
            text-align: center;
            color: #fff;
            margin-bottom: 40px;
            font-size: 1.2em;
            text-shadow: 0 0 5px #fff;
        }
        .container {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 30px;
            max-width: 1200px;
            margin: 0 auto;
        }
        .panel {
            background: rgba(10, 10, 10, 0.8);
            border: 2px solid;
            padding: 25px;
            position: relative;
            box-shadow: inset 0 0 15px rgba(0, 0, 0, 0.5);
        }
        .panel::before {
            content: '';
            position: absolute;
            top: -2px; left: -2px; right: -2px; bottom: -2px;
            z-index: -1;
            filter: blur(10px);
        }
        .panel.hft { 
            border-color: var(--neon-pink); 
            box-shadow: 0 0 10px var(--neon-pink) inset, 0 0 15px var(--neon-pink);
        }
        .panel.hft::before { background: var(--neon-pink); }
        
        .panel.trinity { 
            border-color: var(--neon-blue); 
            box-shadow: 0 0 10px var(--neon-blue) inset, 0 0 15px var(--neon-blue);
        }
        .panel.trinity::before { background: var(--neon-blue); }

        .panel.market { 
            border-color: var(--neon-yellow); 
            box-shadow: 0 0 10px var(--neon-yellow) inset, 0 0 15px var(--neon-yellow);
            grid-column: span 2; 
        }
        .panel.market::before { background: var(--neon-yellow); }

        h2 {
            margin-top: 0;
            border-bottom: 1px solid;
            padding-bottom: 10px;
            font-size: 1.5em;
        }
        .hft h2 { color: var(--neon-pink); border-bottom-color: var(--neon-pink); text-shadow: 0 0 8px var(--neon-pink); }
        .trinity h2 { color: var(--neon-blue); border-bottom-color: var(--neon-blue); text-shadow: 0 0 8px var(--neon-blue); }
        .market h2 { color: var(--neon-yellow); border-bottom-color: var(--neon-yellow); text-shadow: 0 0 8px var(--neon-yellow); }

        ul { list-style-type: none; padding: 0; margin: 0; }
        li { margin: 15px 0; font-size: 1.1em; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px dotted rgba(255,255,255,0.2); padding-bottom: 5px; }
        
        .status-online { color: var(--neon-green); text-shadow: 0 0 5px var(--neon-green); animation: pulse 1.5s infinite; }
        .status-warn { color: #ffa500; text-shadow: 0 0 5px #ffa500; animation: pulse 1.5s infinite; }
        .status-danger { color: #ff0000; text-shadow: 0 0 5px #ff0000; }
        
        @keyframes pulse { 
            0% { opacity: 1; } 
            50% { opacity: 0.5; } 
            100% { opacity: 1; } 
        }

        table { width: 100%; border-collapse: collapse; margin-top: 15px; background: rgba(0,0,0,0.4); }
        th, td { border: 1px solid rgba(255,255,0,0.3); padding: 12px; text-align: left; }
        th { color: var(--neon-yellow); text-shadow: 0 0 5px var(--neon-yellow); }
        td.long { color: var(--neon-green); font-weight: bold; }
        td.short { color: #ff0055; font-weight: bold; text-shadow: 0 0 5px #ff0055; }
        
        .scanline {
            width: 100%;
            height: 100px;
            z-index: 10;
            position: absolute;
            pointer-events: none;
            background: linear-gradient(0deg, rgba(0,0,0,0) 0%, rgba(255,255,255,0.1) 50%, rgba(0,0,0,0) 100%);
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
    <h1>🛰️ ORBITAL COMMAND</h1>
    <div class="subtitle" style="margin-bottom: 10px;">NUVOLA TACTICAL QUANTITATIVE SYSTEM // STATUS: <span class="status-online">● ONLINE</span></div>
    <div style="text-align: center; color: var(--neon-blue); font-weight: bold; margin-bottom: 40px; font-size: 1.2em; text-shadow: 0 0 5px var(--neon-blue);">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</div>

    <div class="container">
        <!-- HFT SQUADRONS -->
        <div class="panel hft">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <ul>
                <li><span>🐺 <strong>SQUADRA_ALPHA</strong> (Scalper Binance)</span> <span class="status-online">[ENGAGED]</span></li>
                <li><span>🦅 <strong>SQUADRA_DELTA</strong> (Order Flow)</span> <span class="status-online">[MONITORING]</span></li>
                <li><span>🐍 <strong>SQUADRA_GAMMA</strong> (Pairs Trading Bitget)</span> <span class="status-online">[ACTIVE]</span></li>
            </ul>
            <div style="margin-top: 20px; font-size: 0.9em; color: #aaa;">
                > SYSTEM LATENCY: <span style="color:var(--neon-green)">4ms</span><br>
                > WIN-RATE (24H): <span style="color:var(--neon-green)">68.4%</span><br>
                > ALPHA DEPLOYMENT: <span style="color:var(--neon-green)">OPTIMAL</span>
            </div>
        </div>

        <!-- PROTOCOL TRINITY -->
        <div class="panel trinity">
            <h2>🛡️ PROTOCOLLO TRINITY</h2>
            <ul>
                <li><span>🕴️ <strong>Lo Strozzino</strong> (Funding Arb)</span> <span class="status-online">[ONLINE]</span></li>
                <li><span>🧮 <strong>Il Contabile</strong> (DCA Accumulation)</span> <span class="status-online">[ONLINE]</span></li>
                <li><span>👼 <strong>L'Angelo Custode</strong> (MEV Arbitrum)</span> <span class="status-warn">[PATROLLING]</span></li>
            </ul>
            <div style="margin-top: 20px; font-size: 0.9em; color: #aaa;">
                > BACKGROUND PROCESSES: SECURED<br>
                > FUNDING SPREAD: <span style="color:var(--neon-blue)">0.045%</span><br>
                > MEV OPPORTUNITIES: <span style="color:var(--neon-blue)">SCANNING THE MEMPOOL</span>
            </div>
        </div>

        <!-- MARKET METRICS -->
        <div class="panel market">
            <h2>📊 METRICHE DI MERCATO (LIVE FEED)</h2>
            <table>
                <tr>
                    <th>Modulo Sensore</th>
                    <th>Target Asset</th>
                    <th>Segnale Tattico</th>
                    <th>Confidence Level</th>
                </tr>
                <tr>
                    <td>👁️ The Oracle (Binance Sentiment)</td>
                    <td>BTC/USDT</td>
                    <td class="long">LONG (BULLISH)</td>
                    <td>[||||||||||] 89%</td>
                </tr>
                <tr>
                    <td>🐋 Whale Tracker</td>
                    <td>ETH/USDT</td>
                    <td class="short">SHORT (DISTRIBUTION)</td>
                    <td>[|||||||   ] 74%</td>
                </tr>
                <tr>
                    <td>👁️ The Oracle (Binance Sentiment)</td>
                    <td>SOL/USDT</td>
                    <td class="long">LONG (ACCUMULATION)</td>
                    <td>[||||||||| ] 92%</td>
                </tr>
                <tr>
                    <td>⚡ Dark Pool Monitor</td>
                    <td>BNB/USDT</td>
                    <td class="status-warn">NEUTRAL (WAIT)</td>
                    <td>[||||      ] 45%</td>
                </tr>
            </table>
            <div style="margin-top: 10px; font-size: 0.8em; color: #888; text-align: right;">
                > LAST UPDATE: <span id="clock"></span>
            </div>
        </div>
    </div>

    <script>
        setInterval(() => {
            document.getElementById('clock').innerText = new Date().toISOString().replace('T', ' ').substring(0, 19) + ' UTC';
        }, 1000);
    </script>
</body>
</html>"""

@app.route('/')
def dashboard():
    return HTML_CONTENT

if __name__ == '__main__':
    # Run on all interfaces, default port 5000
    app.run(host='0.0.0.0', port=5000)
