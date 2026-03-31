from flask import Flask, render_template_string
import threading

app = Flask(__name__)

HTML_CONTENT = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Nuvola // Orbital Command</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');
        body {
            background-color: #000;
            color: #0f0;
            font-family: 'Share Tech Mono', monospace;
            margin: 0;
            padding: 30px;
            overflow-x: hidden;
            text-shadow: 0 0 5px #0f0;
        }
        h1, h2, h3 { margin: 0; padding: 0; }
        .scanline {
            width: 100%; height: 10px; z-index: 9999; position: fixed; top: 0; left: 0;
            background: rgba(0,255,0,0.3); opacity: 0.1;
            animation: scanline 4s linear infinite; pointer-events: none;
        }
        @keyframes scanline {
            0% { top: -10px; }
            100% { top: 100%; }
        }
        .header {
            text-align: center; border-bottom: 1px solid #0f0;
            padding-bottom: 20px; margin-bottom: 30px;
            box-shadow: 0 10px 10px -10px #0f0;
        }
        .header h1 { font-size: 2.5em; text-transform: uppercase; color: #fff; text-shadow: 0 0 10px #fff, 0 0 20px #0f0; }
        .grid {
            display: grid; grid-template-columns: repeat(auto-fit, minmax(350px, 1fr)); gap: 30px;
        }
        .panel {
            border: 1px solid #0f0; background: rgba(0,20,0,0.8);
            padding: 20px; position: relative;
            box-shadow: 0 0 15px rgba(0, 255, 0, 0.2) inset;
            transition: all 0.3s;
        }
        .panel:hover {
            box-shadow: 0 0 30px rgba(0, 255, 0, 0.5) inset;
        }
        .panel::before {
            content: ''; position: absolute; top: -2px; left: -2px; right: -2px; bottom: -2px;
            background: linear-gradient(45deg, #0f0, transparent, #0f0);
            z-index: -1; filter: blur(10px); opacity: 0.5;
        }
        .panel-header {
            font-size: 1.5em; margin-bottom: 20px; border-bottom: 1px dashed #0f0;
            padding-bottom: 10px; color: #0ff; text-shadow: 0 0 10px #0ff;
            text-transform: uppercase;
        }
        .item { margin-bottom: 15px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #111; padding-bottom: 5px; }
        .item span { font-size: 1.1em; }
        .item small { color: #888; font-size: 0.8em; }
        
        .status-active { color: #0f0; text-shadow: 0 0 10px #0f0; animation: pulse 1.5s infinite; }
        .status-standby { color: #ff0; text-shadow: 0 0 10px #ff0; }
        .status-online { color: #f0f; text-shadow: 0 0 10px #f0f; }
        .status-alert { color: #f00; text-shadow: 0 0 10px #f00; animation: blink 0.5s infinite; }
        .value-cyan { color: #0ff; text-shadow: 0 0 10px #0ff; }
        
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.6; }
            100% { opacity: 1; }
        }
        @keyframes blink {
            0%, 100% { opacity: 1; }
            50% { opacity: 0; }
        }
        .footer { text-align: center; margin-top: 40px; font-size: 0.8em; color: #555; }
    </style>
</head>
<body>
    <div class="scanline"></div>
    <div class="header">
        <h1>[ 🌐 Orbital Command 🌐 ]</h1>
        <p>>_ SYSTEM: NUVOLA // TACTICAL QUANTITATIVE DASHBOARD v3.0 // UPLINK: SECURE</p>
        <p class="status-active" style="font-size: 1.2em; margin-top: 10px;">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</p>
    </div>
    
    <div class="grid">
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <div class="panel-header">⚔️ Squadre d'Assalto (HFT)</div>
            <div class="item">
                <span>🐺 SQUADRA_ALPHA <br><small>[Scalper su Binance]</small></span>
                <span class="status-active">[ ACTIVE ]</span>
            </div>
            <div class="item">
                <span>🦅 SQUADRA_DELTA <br><small>[Order Flow]</small></span>
                <span class="status-standby">[ STANDBY ]</span>
            </div>
            <div class="item">
                <span>🦊 SQUADRA_GAMMA <br><small>[Pairs Trading Bitget]</small></span>
                <span class="status-active">[ ACTIVE ]</span>
            </div>
            <div style="margin-top:20px; font-size: 0.9em; color: #666;">
                > Latency: 12ms | HFT Win Rate: 68.4%
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <div class="panel-header">💠 Protocollo Trinity</div>
            <div class="item">
                <span>🕴️ Lo Strozzino <br><small>[Funding Arb]</small></span>
                <span class="status-online">[ ONLINE ]</span>
            </div>
            <div class="item">
                <span>🧮 Il Contabile <br><small>[DCA Engine]</small></span>
                <span class="status-online">[ ONLINE ]</span>
            </div>
            <div class="item">
                <span>🛡️ L'Angelo Custode <br><small>[MEV Arbitrum]</small></span>
                <span class="status-online">[ ONLINE ]</span>
            </div>
            <div style="margin-top:20px; font-size: 0.9em; color: #666;">
                > Background daemons synchronized.
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <div class="panel-header">📡 Metriche di Mercato</div>
            <div class="item">
                <span>👁️ The Oracle <br><small>[Binance Sentiment]</small></span>
                <span class="status-alert">EXTREME GREED (88)</span>
            </div>
            <div class="item">
                <span>🐋 Whale Tracker <br><small>[On-chain Netflow]</small></span>
                <span class="value-cyan">+4,500 BTC INFLOW</span>
            </div>
            <div class="item">
                <span>⚡ Liquidity Map <br><small>[Orderbook Clusters]</small></span>
                <span class="status-standby">CLUSTER @ $72,500</span>
            </div>
            <div style="margin-top:20px; font-size: 0.9em; color: #666;">
                > Awaiting next block propagation...
            </div>
        </div>
    </div>
    
    <div class="footer">
        > END OF FEED // NUVOLA CORE v.4.0.1 // UNAUTHORIZED ACCESS PROHIBITED
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_CONTENT)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
