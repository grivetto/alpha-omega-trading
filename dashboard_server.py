from flask import Flask, render_template_string
import threading

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NUVOLA ORBITAL COMMAND</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');
        
        :root {
            --neon-green: #0f0;
            --neon-cyan: #0ff;
            --neon-magenta: #f0f;
            --neon-red: #f00;
            --bg-color: #050505;
        }

        body {
            background-color: var(--bg-color);
            color: var(--neon-green);
            font-family: 'Share Tech Mono', monospace;
            margin: 0;
            padding: 20px;
            background-image: radial-gradient(var(--neon-green) 1px, transparent 1px);
            background-size: 50px 50px;
            background-position: 0 0;
            background-attachment: fixed;
            position: relative;
        }

        /* Overlay scanline effect */
        body::after {
            content: " ";
            display: block;
            position: fixed;
            top: 0;
            left: 0;
            bottom: 0;
            right: 0;
            background: linear-gradient(rgba(18, 16, 16, 0) 50%, rgba(0, 0, 0, 0.25) 50%), linear-gradient(90deg, rgba(255, 0, 0, 0.06), rgba(0, 255, 0, 0.02), rgba(0, 0, 255, 0.06));
            z-index: 2;
            background-size: 100% 2px, 3px 100%;
            pointer-events: none;
        }

        h1, h2, h3 { 
            text-shadow: 0 0 5px var(--neon-green), 0 0 10px var(--neon-green); 
            margin-top: 0; 
            letter-spacing: 2px;
        }
        
        .container { 
            max-width: 1200px; 
            margin: auto; 
            position: relative;
            z-index: 3;
        }
        
        .header { 
            border-bottom: 2px solid var(--neon-green); 
            padding-bottom: 20px; 
            margin-bottom: 30px; 
            text-align: center; 
        }

        .glow-red { color: var(--neon-red); text-shadow: 0 0 5px var(--neon-red), 0 0 10px var(--neon-red); border-color: var(--neon-red); }
        .glow-cyan { color: var(--neon-cyan); text-shadow: 0 0 5px var(--neon-cyan), 0 0 10px var(--neon-cyan); border-color: var(--neon-cyan); }
        .glow-magenta { color: var(--neon-magenta); text-shadow: 0 0 5px var(--neon-magenta), 0 0 10px var(--neon-magenta); border-color: var(--neon-magenta); }
        
        .panel {
            border: 1px solid var(--neon-green);
            box-shadow: inset 0 0 15px rgba(0, 255, 0, 0.2), 0 0 15px rgba(0, 255, 0, 0.2);
            padding: 20px;
            margin-bottom: 20px;
            background: rgba(0, 15, 0, 0.85);
            transition: all 0.3s ease;
        }

        .panel:hover {
            box-shadow: inset 0 0 25px rgba(0, 255, 0, 0.4), 0 0 25px rgba(0, 255, 0, 0.4);
        }

        .panel.red { border-color: var(--neon-red); box-shadow: inset 0 0 15px rgba(255, 0, 0, 0.2), 0 0 15px rgba(255, 0, 0, 0.2); }
        .panel.magenta { border-color: var(--neon-magenta); box-shadow: inset 0 0 15px rgba(255, 0, 255, 0.2), 0 0 15px rgba(255, 0, 255, 0.2); }
        .panel.cyan { border-color: var(--neon-cyan); box-shadow: inset 0 0 15px rgba(0, 255, 255, 0.2), 0 0 15px rgba(0, 255, 255, 0.2); }

        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(350px, 1fr)); gap: 30px; }
        
        .status-indicator { 
            display: inline-block; 
            width: 12px; 
            height: 12px; 
            border-radius: 50%; 
            background: var(--neon-green); 
            box-shadow: 0 0 8px var(--neon-green); 
            animation: blink 1.5s infinite; 
            margin-right: 8px;
        }
        
        .status-red { background: var(--neon-red); box-shadow: 0 0 8px var(--neon-red); }
        .status-magenta { background: var(--neon-magenta); box-shadow: 0 0 8px var(--neon-magenta); }
        .status-cyan { background: var(--neon-cyan); box-shadow: 0 0 8px var(--neon-cyan); }
        
        @keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }
        
        table { width: 100%; border-collapse: collapse; margin-top: 15px; font-size: 0.9em; }
        th, td { border: 1px solid var(--neon-green); padding: 10px; text-align: left; }
        th { background: rgba(0, 255, 0, 0.15); text-shadow: 0 0 2px var(--neon-green); }
        
        .panel.cyan th, .panel.cyan td { border-color: var(--neon-cyan); }
        .panel.cyan th { background: rgba(0, 255, 255, 0.15); text-shadow: 0 0 2px var(--neon-cyan); color: var(--neon-cyan); }

        hr { border: 0; border-top: 1px dashed var(--neon-green); margin: 15px 0; opacity: 0.5; }
        .hr-red { border-top-color: var(--neon-red); }
        .hr-magenta { border-top-color: var(--neon-magenta); }
        
        .metric-value { font-size: 1.2em; font-weight: bold; }
        
        .glitch {
            position: relative;
        }
        
        @keyframes crt-flicker {
            0% { opacity: 0.95; }
            5% { opacity: 0.85; }
            10% { opacity: 0.95; }
            15% { opacity: 1; }
            100% { opacity: 1; }
        }
        .header h1 { animation: crt-flicker 4s infinite; }

    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1 class="glow-cyan glitch">🛰️ ORBITAL COMMAND - NUVOLA 🛰️</h1>
            <p>SYSTEM STATUS: <span class="glow-cyan blink">ONLINE</span> &nbsp;|&nbsp; UPLINK: <span class="glow-cyan">SECURE</span> &nbsp;|&nbsp; LOCATION: <span class="glow-cyan">HQ</span></p>
            <p class="glow-magenta" style="font-size: 1.2em; border: 1px dashed var(--neon-magenta); padding: 5px; display: inline-block;">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</p>
        </div>

        <div class="grid">
            <!-- SQUADRE D'ASSALTO (HFT) -->
            <div class="panel red">
                <h2 class="glow-red">⚔️ SQUADRE D'ASSALTO (HFT)</h2>
                
                <p><span class="status-indicator status-red"></span> <b class="glow-red">SQUADRA_ALPHA</b> [Scalper Binance]</p>
                <p>STATUS: <span class="glow-cyan">ENGAGED</span> | PNL: <span class="glow-cyan metric-value">+1.24%</span> | LAT: 12ms</p>
                
                <hr class="hr-red">
                
                <p><span class="status-indicator status-red" style="animation-delay: 0.2s"></span> <b class="glow-red">SQUADRA_DELTA</b> [Order Flow]</p>
                <p>STATUS: <span class="glow-cyan">SCANNING</span> | IMBALANCE: <span class="glow-red">DETECTED (SHORT)</span></p>
                
                <hr class="hr-red">
                
                <p><span class="status-indicator status-red" style="animation-delay: 0.4s"></span> <b class="glow-red">SQUADRA_GAMMA</b> [Pairs Trading Bitget]</p>
                <p>STATUS: <span class="glow-cyan">HEDGED</span> | SPREAD: <span class="metric-value">0.45%</span> | COINT: HIGH</p>
            </div>

            <!-- PROTOCOLLO TRINITY -->
            <div class="panel magenta">
                <h2 class="glow-magenta">🛡️ PROTOCOLLO TRINITY (BKG)</h2>
                
                <p><span class="status-indicator status-magenta"></span> <b class="glow-magenta">LO STROZZINO</b> (Funding Arb)</p>
                <p>STATUS: ACTIVE | YIELD: <span class="glow-cyan metric-value">14.5% APY</span> | DELTA: NEUTRAL</p>
                
                <hr class="hr-magenta">
                
                <p><span class="status-indicator status-magenta" style="animation-delay: 0.3s"></span> <b class="glow-magenta">IL CONTABILE</b> (DCA)</p>
                <p>STATUS: <span class="glow-cyan">ACCUMULATING</span> | ASSETS: BTC, ETH | NEXT BUY: 4h 12m</p>
                
                <hr class="hr-magenta">
                
                <p><span class="status-indicator status-magenta" style="animation-delay: 0.6s"></span> <b class="glow-magenta">L'ANGELO CUSTODE</b> (MEV Arbitrum)</p>
                <p>STATUS: <span class="glow-red">MEMPOOL_SNIFFING</span> | FLASH_LOANS: <span class="glow-cyan">READY (10K ETH)</span></p>
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel cyan" style="margin-top: 10px;">
            <h2 class="glow-cyan">📊 METRICHE DI MERCATO</h2>
            <div class="grid">
                <div>
                    <h3 class="glow-cyan">🔮 THE ORACLE (Binance Sentiment)</h3>
                    <table>
                        <tr><th>ASSET</th><th>SENTIMENT</th><th>SIGNAL</th></tr>
                        <tr><td>BTC/USDT</td><td class="glow-cyan">BULLISH (82%)</td><td class="glow-cyan">LONG 🔼</td></tr>
                        <tr><td>ETH/USDT</td><td>NEUTRAL (55%)</td><td>HOLD ⏸️</td></tr>
                        <tr><td>SOL/USDT</td><td class="glow-red">BEARISH (30%)</td><td class="glow-red">SHORT 🔽</td></tr>
                        <tr><td>XRP/USDT</td><td class="glow-cyan">BULLISH (71%)</td><td class="glow-cyan">LONG 🔼</td></tr>
                    </table>
                </div>
                <div>
                    <h3 class="glow-cyan">🐋 WHALE TRACKER</h3>
                    <table>
                        <tr><th>TIME</th><th>SIZE</th><th>ACTION</th></tr>
                        <tr><td>10:00:12</td><td>500 BTC</td><td class="glow-cyan">INFLOW 📥</td></tr>
                        <tr><td>09:55:01</td><td>12,000 ETH</td><td class="glow-red">OUTFLOW 📤</td></tr>
                        <tr><td>09:42:33</td><td>1M SOL</td><td class="glow-cyan">INFLOW 📥</td></tr>
                        <tr><td>09:15:22</td><td>2,000 BTC</td><td class="glow-red">OUTFLOW 📤</td></tr>
                    </table>
                </div>
            </div>
        </div>
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    # Running on port 5000 or custom port
    app.run(host='0.0.0.0', port=5000, debug=False)
