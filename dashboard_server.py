import os
from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Orbital Command | Nuvola</title>
    <style>
        :root {
            --bg-color: #050505;
            --neon-green: #0f0;
            --neon-blue: #0ff;
            --neon-red: #f00;
            --neon-purple: #f0f;
            --panel-bg: rgba(10, 20, 10, 0.8);
        }
        body {
            background-color: var(--bg-color);
            color: var(--neon-green);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            overflow-x: hidden;
        }
        .scanline {
            width: 100%;
            height: 100px;
            background: linear-gradient(0deg, rgba(0,255,0,0) 0%, rgba(0,255,0,0.1) 50%, rgba(0,255,0,0) 100%);
            opacity: 0.1;
            position: absolute;
            bottom: 100%;
            animation: scanline 10s linear infinite;
            pointer-events: none;
            z-index: 9999;
        }
        @keyframes scanline {
            0% { bottom: 100%; }
            100% { bottom: -100px; }
        }
        h1 {
            text-align: center;
            color: var(--neon-blue);
            text-transform: uppercase;
            text-shadow: 0 0 10px var(--neon-blue), 0 0 20px var(--neon-blue);
            border-bottom: 2px solid var(--neon-blue);
            padding-bottom: 10px;
            letter-spacing: 5px;
            margin-bottom: 40px;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
            gap: 25px;
            margin-top: 20px;
            max-width: 1200px;
            margin-left: auto;
            margin-right: auto;
        }
        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-green);
            box-shadow: 0 0 15px rgba(0, 255, 0, 0.2), inset 0 0 15px rgba(0, 255, 0, 0.1);
            padding: 25px;
            border-radius: 8px;
            position: relative;
            backdrop-filter: blur(5px);
            transition: all 0.3s ease;
        }
        .panel:hover {
            box-shadow: 0 0 25px rgba(0, 255, 0, 0.4), inset 0 0 20px rgba(0, 255, 0, 0.2);
        }
        .panel h2 {
            margin-top: 0;
            font-size: 1.3em;
            color: var(--neon-purple);
            text-shadow: 0 0 8px var(--neon-purple);
            border-bottom: 1px dashed var(--neon-purple);
            padding-bottom: 10px;
            letter-spacing: 2px;
        }
        .panel.blue { border-color: var(--neon-blue); box-shadow: 0 0 15px rgba(0, 255, 255, 0.2); }
        .panel.blue h2 { color: var(--neon-blue); text-shadow: 0 0 8px var(--neon-blue); border-bottom-color: var(--neon-blue); }
        .panel.blue:hover { box-shadow: 0 0 25px rgba(0, 255, 255, 0.4); }
        
        .panel.red { border-color: var(--neon-red); box-shadow: 0 0 15px rgba(255, 0, 0, 0.2); }
        .panel.red h2 { color: var(--neon-red); text-shadow: 0 0 8px var(--neon-red); border-bottom-color: var(--neon-red); }
        .panel.red:hover { box-shadow: 0 0 25px rgba(255, 0, 0, 0.4); }
        
        ul { list-style-type: none; padding: 0; margin: 0; }
        li { margin-bottom: 15px; display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid rgba(255,255,255,0.05); padding-bottom: 10px; }
        li:last-child { border-bottom: none; margin-bottom: 0; padding-bottom: 0; }
        
        .status-online { color: var(--neon-green); text-shadow: 0 0 8px var(--neon-green); animation: pulse 2s infinite; font-weight: bold; }
        .status-active { color: var(--neon-blue); text-shadow: 0 0 8px var(--neon-blue); font-weight: bold; }
        .status-warning { color: yellow; text-shadow: 0 0 8px yellow; }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; text-shadow: 0 0 8px var(--neon-green); }
            50% { opacity: 0.6; text-shadow: 0 0 2px var(--neon-green); }
        }
        
        .table-grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px; text-align: left; align-items: center; padding: 10px 0; border-bottom: 1px solid rgba(255,255,255,0.05); }
        .table-grid:last-child { border-bottom: none; }
        .table-header { color: #aaa; font-size: 0.85em; text-transform: uppercase; border-bottom: 1px solid #333; padding-bottom: 5px; }
        
        .glow-text { text-shadow: 0 0 5px currentColor; }
        .small-caps { font-size: 0.8em; color: #888; text-transform: uppercase; display: block; margin-top: 4px; }
    </style>
</head>
<body>
    <div class="scanline"></div>
    <h1>🛰️ Orbital Command <br><span style="font-size:0.5em; color: #888; text-shadow:none; letter-spacing: 2px;">Nuvola System Central</span></h1>
    
    <div style="text-align: center; margin-bottom: 30px; padding: 15px; border: 2px dashed var(--neon-blue); border-radius: 8px; background: rgba(0, 255, 255, 0.1); box-shadow: 0 0 15px rgba(0, 255, 255, 0.2);">
        <h3 style="margin: 0; color: var(--neon-blue); text-shadow: 0 0 10px var(--neon-blue); letter-spacing: 2px;">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</h3>
    </div>
    
    <div class="grid">
        <!-- SQUADRE D'ASSALTO -->
        <div class="panel red">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <ul>
                <li>
                    <span>🐺 <b>SQUADRA_ALPHA</b><span class="small-caps">Scalper [Binance]</span></span>
                    <span class="status-active glow-text">ENGAGED<br><span style="font-size:0.7em">[742 ops/s]</span></span>
                </li>
                <li>
                    <span>🌊 <b>SQUADRA_DELTA</b><span class="small-caps">Order Flow [Binance]</span></span>
                    <span class="status-active glow-text" style="color:#ff8c00; text-shadow:0 0 8px #ff8c00;">SNIPING<br><span style="font-size:0.7em">[Liq. Pools]</span></span>
                </li>
                <li>
                    <span>⚖️ <b>SQUADRA_GAMMA</b><span class="small-caps">Pairs Trading [Bitget]</span></span>
                    <span class="status-active glow-text" style="color:#ff00ff; text-shadow:0 0 8px #ff00ff;">HEDGED<br><span style="font-size:0.7em">[∆ Neutral]</span></span>
                </li>
            </ul>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel blue">
            <h2>🔺 PROTOCOLLO TRINITY</h2>
            <ul>
                <li>
                    <span>🦈 <b>Lo Strozzino</b><span class="small-caps">Funding Arb Engine</span></span>
                    <span class="status-online">ONLINE<br><span style="font-size:0.7em; font-weight:normal;">[Yielding]</span></span>
                </li>
                <li>
                    <span>🧮 <b>Il Contabile</b><span class="small-caps">DCA & Rebalancing</span></span>
                    <span class="status-online">ONLINE<br><span style="font-size:0.7em; font-weight:normal;">[Accumulating]</span></span>
                </li>
                <li>
                    <span>👼 <b>L'Angelo Custode</b><span class="small-caps">MEV Defense [Arbitrum]</span></span>
                    <span class="status-online">ONLINE<br><span style="font-size:0.7em; font-weight:normal;">[Guarding]</span></span>
                </li>
            </ul>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <h2>📡 METRICHE DI MERCATO</h2>
            <div class="table-grid table-header">
                <div>SENSOR</div><div>STATUS</div><div>DATA FEED</div>
            </div>
            <div class="table-grid">
                <div style="color:var(--neon-blue); font-weight:bold;">👁️ The Oracle</div>
                <div class="status-online" style="font-size:0.9em;">SYNCED</div>
                <div style="font-size:0.9em;">BTC Sentiment: <span style="color:var(--neon-green); font-weight:bold; text-shadow:0 0 5px var(--neon-green);">BULLISH</span></div>
            </div>
            <div class="table-grid">
                <div style="color:var(--neon-purple); font-weight:bold;">🐋 Whale Tracker</div>
                <div class="status-online" style="font-size:0.9em; animation-delay: 0.5s;">PING</div>
                <div style="font-size:0.9em;">Alert: <span style="color:var(--neon-red); font-weight:bold; text-shadow:0 0 5px var(--neon-red);">$84M Transferred</span></div>
            </div>
            <div class="table-grid">
                <div style="color:var(--neon-green); font-weight:bold;">⚡ Core Metrics</div>
                <div style="color:#aaa; font-size:0.9em;">NOMINAL</div>
                <div style="font-size:0.9em; font-family:monospace;">CPU: 12% | RAM: 4.2GB</div>
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
    # Listen on all interfaces, port 5000 by default
    app.run(host='0.0.0.0', port=5000)
