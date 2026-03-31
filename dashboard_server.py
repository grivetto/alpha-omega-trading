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
            --bg-color: #030303;
            --neon-green: #39ff14;
            --neon-blue: #0ff;
            --neon-red: #ff073a;
            --neon-purple: #bc13fe;
            --neon-yellow: #fefe33;
            --panel-bg: rgba(5, 10, 5, 0.85);
            --border-glow: 0 0 10px rgba(0, 255, 255, 0.5);
        }
        @font-face {
            font-family: 'Share Tech Mono';
            src: url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');
        }
        body {
            background-color: var(--bg-color);
            background-image: 
                linear-gradient(rgba(0, 255, 255, 0.03) 1px, transparent 1px),
                linear-gradient(90deg, rgba(0, 255, 255, 0.03) 1px, transparent 1px);
            background-size: 20px 20px;
            color: var(--neon-green);
            font-family: 'Share Tech Mono', 'Courier New', monospace;
            margin: 0;
            padding: 20px;
            overflow-x: hidden;
            text-shadow: 0 0 5px var(--neon-green);
        }
        .scanline {
            width: 100%;
            height: 100px;
            background: linear-gradient(0deg, rgba(57,255,20,0) 0%, rgba(57,255,20,0.15) 50%, rgba(57,255,20,0) 100%);
            opacity: 0.2;
            position: fixed;
            top: 0;
            left: 0;
            animation: scanline 8s linear infinite;
            pointer-events: none;
            z-index: 9999;
        }
        @keyframes scanline {
            0% { top: -100px; }
            100% { top: 100%; }
        }
        .crt-flicker {
            animation: flicker 0.15s infinite;
        }
        @keyframes flicker {
            0% { opacity: 0.95; }
            50% { opacity: 1; }
            100% { opacity: 0.98; }
        }
        h1 {
            text-align: center;
            color: var(--neon-blue);
            text-transform: uppercase;
            text-shadow: 0 0 15px var(--neon-blue), 0 0 30px var(--neon-blue);
            border-bottom: 2px solid var(--neon-blue);
            padding-bottom: 10px;
            letter-spacing: 8px;
            margin-bottom: 30px;
            font-size: 2.5em;
        }
        .subtitle {
            text-align: center;
            color: var(--neon-yellow);
            font-size: 1.2em;
            letter-spacing: 4px;
            margin-top: -20px;
            margin-bottom: 40px;
            text-shadow: 0 0 10px var(--neon-yellow);
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 30px;
            max-width: 1400px;
            margin: 0 auto;
        }
        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-green);
            box-shadow: 0 0 20px rgba(57, 255, 20, 0.15), inset 0 0 20px rgba(57, 255, 20, 0.1);
            padding: 25px;
            border-radius: 4px;
            position: relative;
            backdrop-filter: blur(10px);
            transition: all 0.3s ease;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: -2px; left: -2px; right: -2px; bottom: -2px;
            background: linear-gradient(45deg, var(--neon-green), transparent, var(--neon-green));
            z-index: -1;
            filter: blur(5px);
            opacity: 0.3;
        }
        .panel:hover {
            box-shadow: 0 0 30px rgba(57, 255, 20, 0.3), inset 0 0 30px rgba(57, 255, 20, 0.2);
            transform: translateY(-2px);
        }
        .panel h2 {
            margin-top: 0;
            font-size: 1.5em;
            color: var(--neon-purple);
            text-shadow: 0 0 10px var(--neon-purple);
            border-bottom: 1px dashed var(--neon-purple);
            padding-bottom: 10px;
            letter-spacing: 3px;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .panel.hft { border-color: var(--neon-red); }
        .panel.hft h2 { color: var(--neon-red); text-shadow: 0 0 10px var(--neon-red); border-bottom-color: var(--neon-red); }
        .panel.hft::before { background: linear-gradient(45deg, var(--neon-red), transparent, var(--neon-red)); }
        
        .panel.trinity { border-color: var(--neon-blue); }
        .panel.trinity h2 { color: var(--neon-blue); text-shadow: 0 0 10px var(--neon-blue); border-bottom-color: var(--neon-blue); }
        .panel.trinity::before { background: linear-gradient(45deg, var(--neon-blue), transparent, var(--neon-blue)); }
        
        ul { list-style-type: none; padding: 0; margin: 0; }
        li { 
            margin-bottom: 15px; 
            display: flex; 
            align-items: center; 
            justify-content: space-between; 
            border-bottom: 1px solid rgba(255,255,255,0.1); 
            padding-bottom: 15px; 
            background: rgba(0,0,0,0.4);
            padding: 10px;
            border-radius: 4px;
        }
        li:last-child { margin-bottom: 0; }
        
        .agent-name { font-size: 1.1em; color: #fff; text-shadow: 0 0 5px #fff; }
        .agent-role { font-size: 0.8em; color: #aaa; text-transform: uppercase; display: block; margin-top: 4px; letter-spacing: 1px; }
        
        .status-badge {
            padding: 4px 8px;
            border-radius: 3px;
            font-weight: bold;
            font-size: 0.85em;
            letter-spacing: 1px;
            text-align: right;
        }
        .status-online { color: var(--neon-green); border: 1px solid var(--neon-green); box-shadow: 0 0 10px rgba(57,255,20,0.3); animation: pulse-green 2s infinite; }
        .status-engaged { color: var(--neon-red); border: 1px solid var(--neon-red); box-shadow: 0 0 10px rgba(255,7,58,0.3); animation: pulse-red 1s infinite; }
        .status-sniping { color: #ff8c00; border: 1px solid #ff8c00; box-shadow: 0 0 10px rgba(255,140,0,0.3); animation: pulse-orange 1.5s infinite; }
        .status-hedged { color: var(--neon-purple); border: 1px solid var(--neon-purple); box-shadow: 0 0 10px rgba(188,19,254,0.3); }
        
        @keyframes pulse-green { 0%, 100% { box-shadow: 0 0 5px rgba(57,255,20,0.5); } 50% { box-shadow: 0 0 15px rgba(57,255,20,0.8); } }
        @keyframes pulse-red { 0%, 100% { box-shadow: 0 0 5px rgba(255,7,58,0.5); } 50% { box-shadow: 0 0 15px rgba(255,7,58,0.8); } }
        @keyframes pulse-orange { 0%, 100% { box-shadow: 0 0 5px rgba(255,140,0,0.5); } 50% { box-shadow: 0 0 15px rgba(255,140,0,0.8); } }
        
        .stat-detail { font-size: 0.7em; color: #ccc; display: block; margin-top: 3px; }
        
        .data-grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px; align-items: center; padding: 12px; background: rgba(0,0,0,0.3); margin-bottom: 8px; border-left: 3px solid var(--neon-green); }
        .data-grid.oracle { border-left-color: var(--neon-blue); }
        .data-grid.whale { border-left-color: var(--neon-purple); }
        .data-header { color: #888; font-size: 0.8em; text-transform: uppercase; letter-spacing: 2px; border-bottom: 1px solid #333; padding-bottom: 5px; margin-bottom: 10px; display: grid; grid-template-columns: 1fr 1fr 1fr; padding: 0 12px; }
        
        .blink { animation: blinker 1s linear infinite; }
        @keyframes blinker { 50% { opacity: 0; } }
        
        .progress-bar { width: 100%; height: 4px; background: #222; margin-top: 5px; border-radius: 2px; overflow: hidden; }
        .progress-fill { height: 100%; background: var(--neon-green); box-shadow: 0 0 5px var(--neon-green); }
        
    </style>
</head>
<body class="crt-flicker">
    <div class="scanline"></div>
    <h1>🛰️ ORBITAL COMMAND</h1>
    <div class="subtitle">NUVOLA SYSTEM CENTRAL // <span class="blink" style="color:var(--neon-green);">LIVE</span></div>
    
    <div style="text-align: center; margin-bottom: 30px; padding: 10px; border: 1px solid var(--neon-blue); color: var(--neon-blue); background: rgba(0, 255, 255, 0.1); border-radius: 4px; font-size: 1.2em; text-shadow: 0 0 5px var(--neon-blue), 0 0 10px var(--neon-blue); box-shadow: 0 0 10px rgba(0,255,255,0.2); font-weight: bold; letter-spacing: 2px;">
        ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
    </div>
    
    <div class="grid">
        <!-- SQUADRE D'ASSALTO -->
        <div class="panel hft">
            <h2>⚔️ SQUADRE D'ASSALTO <span style="font-size:0.5em; color:#fff; border:1px solid #fff; padding:2px 5px; border-radius:3px;">HFT / EXECUTION</span></h2>
            <ul>
                <li>
                    <div>
                        <span class="agent-name">🐺 SQUADRA_ALPHA</span>
                        <span class="agent-role">Scalper [Binance]</span>
                    </div>
                    <div class="status-badge status-engaged">ENGAGED<br><span class="stat-detail">[742 ops/s | Ping: 8ms]</span></div>
                </li>
                <li>
                    <div>
                        <span class="agent-name">🌊 SQUADRA_DELTA</span>
                        <span class="agent-role">Order Flow [Binance]</span>
                    </div>
                    <div class="status-badge status-sniping">SNIPING<br><span class="stat-detail">[Liq. Pools Active]</span></div>
                </li>
                <li>
                    <div>
                        <span class="agent-name">⚖️ SQUADRA_GAMMA</span>
                        <span class="agent-role">Pairs Trading [Bitget]</span>
                    </div>
                    <div class="status-badge status-hedged">HEDGED<br><span class="stat-detail">[∆ Neutral | Expo: $12k]</span></div>
                </li>
            </ul>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel trinity">
            <h2>🔺 PROTOCOLLO TRINITY <span style="font-size:0.5em; color:#fff; border:1px solid #fff; padding:2px 5px; border-radius:3px;">BACKGROUND OPS</span></h2>
            <ul>
                <li>
                    <div>
                        <span class="agent-name">🦈 Lo Strozzino</span>
                        <span class="agent-role">Funding Arb Engine</span>
                    </div>
                    <div class="status-badge status-online">ONLINE<br><span class="stat-detail">[Yielding | APR: 18.4%]</span></div>
                </li>
                <li>
                    <div>
                        <span class="agent-name">🧮 Il Contabile</span>
                        <span class="agent-role">DCA & Rebalancing</span>
                    </div>
                    <div class="status-badge status-online">ONLINE<br><span class="stat-detail">[Accumulating BTC/ETH]</span></div>
                </li>
                <li>
                    <div>
                        <span class="agent-name">👼 L'Angelo Custode</span>
                        <span class="agent-role">MEV Defense [Arbitrum]</span>
                    </div>
                    <div class="status-badge status-online">ONLINE<br><span class="stat-detail">[Guarding Mempool]</span></div>
                </li>
            </ul>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <h2>📡 METRICHE DI MERCATO <span style="font-size:0.5em; color:#fff; border:1px solid #fff; padding:2px 5px; border-radius:3px;">INTEL FEED</span></h2>
            <div class="data-header">
                <div>SENSOR</div><div>STATUS</div><div>DATA FEED</div>
            </div>
            
            <div class="data-grid oracle">
                <div style="color:var(--neon-blue); font-weight:bold; text-shadow:0 0 5px var(--neon-blue);">👁️ The Oracle</div>
                <div class="status-badge status-online" style="border:none; box-shadow:none; text-align:left;">SYNCED</div>
                <div style="font-size:0.85em;">BTC Sent: <span style="color:var(--neon-green); font-weight:bold; text-shadow:0 0 5px var(--neon-green);">BULLISH (82)</span>
                    <div class="progress-bar"><div class="progress-fill" style="width: 82%;"></div></div>
                </div>
            </div>
            
            <div class="data-grid whale">
                <div style="color:var(--neon-purple); font-weight:bold; text-shadow:0 0 5px var(--neon-purple);">🐋 Whale Tracker</div>
                <div class="status-badge status-engaged" style="border:none; box-shadow:none; text-align:left; animation:none; color:var(--neon-red);">ALERT</div>
                <div style="font-size:0.85em;">Tx: <span style="color:var(--neon-red); font-weight:bold; text-shadow:0 0 5px var(--neon-red);">12,000 ETH → CEX</span>
                    <div style="font-size:0.8em; color:#888;">2 mins ago</div>
                </div>
            </div>
            
            <div class="data-grid" style="border-left-color: var(--neon-yellow);">
                <div style="color:var(--neon-yellow); font-weight:bold; text-shadow:0 0 5px var(--neon-yellow);">⚡ System Core</div>
                <div style="font-size:0.85em; color:#aaa;">NOMINAL</div>
                <div style="font-size:0.85em; font-family:monospace;">
                    CPU: 12% | RAM: 4.2GB
                    <div class="progress-bar"><div class="progress-fill" style="width: 12%; background:var(--neon-yellow); box-shadow:0 0 5px var(--neon-yellow);"></div></div>
                </div>
            </div>
        </div>
    </div>
    
    <div style="text-align:center; margin-top:40px; color:#555; font-size:0.8em; letter-spacing:2px;">
        TERMINAL SECURE CONNECTION ESTABLISHED // ENCRYPTION LEVEL: QUANTUM // SYSTEM ID: NUVOLA-99
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
