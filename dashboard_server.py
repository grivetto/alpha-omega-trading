import os
from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Nuvola: Orbital Command</title>
    <style>
        :root {
            --bg-color: #050510;
            --neon-blue: #0ff;
            --neon-pink: #f0f;
            --neon-green: #0f0;
            --panel-bg: rgba(10, 20, 30, 0.85);
        }
        body {
            background-color: var(--bg-color);
            color: #fff;
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            background-image: linear-gradient(rgba(0, 255, 255, 0.05) 1px, transparent 1px),
                              linear-gradient(90deg, rgba(0, 255, 255, 0.05) 1px, transparent 1px);
            background-size: 20px 20px;
        }
        h1 {
            text-align: center;
            color: var(--neon-blue);
            text-transform: uppercase;
            text-shadow: 0 0 10px var(--neon-blue), 0 0 20px var(--neon-blue), 0 0 40px var(--neon-blue);
            letter-spacing: 4px;
            margin-bottom: 30px;
            animation: pulse 2s infinite alternate;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
            gap: 20px;
            max-width: 1200px;
            margin: 0 auto;
        }
        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-blue);
            border-radius: 5px;
            padding: 20px;
            box-shadow: inset 0 0 15px rgba(0, 255, 255, 0.1), 0 0 15px rgba(0, 255, 255, 0.2);
            position: relative;
            overflow: hidden;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: -100%; width: 50%; height: 2px;
            background: linear-gradient(90deg, transparent, var(--neon-blue));
            animation: scanline 3s linear infinite;
        }
        .panel h2 {
            color: var(--neon-pink);
            font-size: 1.2em;
            margin-top: 0;
            border-bottom: 1px dashed var(--neon-pink);
            padding-bottom: 10px;
            text-shadow: 0 0 5px var(--neon-pink);
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .status {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin: 10px 0;
            padding: 10px;
            background: rgba(0, 0, 0, 0.6);
            border-left: 3px solid var(--neon-green);
            transition: all 0.3s;
        }
        .status:hover {
            background: rgba(0, 255, 255, 0.1);
            transform: translateX(5px);
        }
        .status span.online {
            color: var(--neon-green);
            text-shadow: 0 0 5px var(--neon-green);
            animation: blink 2s infinite;
            font-weight: bold;
        }
        .metric {
            font-size: 0.9em;
            color: #aaa;
            line-height: 1.5;
        }
        .metric strong {
            color: #fff;
        }
        .glitch-text {
            color: var(--neon-blue);
            text-shadow: 2px 0 var(--neon-pink), -2px 0 var(--neon-green);
        }
        
        @keyframes scanline {
            100% { left: 200%; }
        }
        @keyframes blink {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        @keyframes pulse {
            0% { text-shadow: 0 0 10px var(--neon-blue), 0 0 20px var(--neon-blue); }
            100% { text-shadow: 0 0 20px var(--neon-blue), 0 0 40px var(--neon-blue), 0 0 60px var(--neon-blue); }
        }
        
        /* Custom scrollbar */
        ::-webkit-scrollbar {
            width: 8px;
        }
        ::-webkit-scrollbar-track {
            background: var(--bg-color);
        }
        ::-webkit-scrollbar-thumb {
            background: var(--neon-blue);
        }
    </style>
</head>
<body>
    <h1>🛰️ ORBITAL COMMAND // NUVOLA 🌐</h1>
    <div style="text-align: center; color: var(--neon-green); font-size: 1.2em; margin-bottom: 20px; font-weight: bold; text-shadow: 0 0 10px var(--neon-green); animation: blink 2s infinite;">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</div>
    
    <div class="grid">
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <div class="status">
                <span>🐺 <strong>SQUADRA_ALPHA</strong><br><small>Binance Scalper</small></span>
                <span class="online">● ONLINE [12ms]</span>
            </div>
            <div class="status">
                <span>🎯 <strong>SQUADRA_DELTA</strong><br><small>Order Flow Analytics</small></span>
                <span class="online">● ONLINE [18ms]</span>
            </div>
            <div class="status">
                <span>⚖️ <strong>SQUADRA_GAMMA</strong><br><small>Bitget Pairs Trading</small></span>
                <span class="online">● ONLINE [24ms]</span>
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel" style="border-color: var(--neon-pink); box-shadow: inset 0 0 15px rgba(255,0,255,0.1), 0 0 15px rgba(255,0,255,0.2);">
            <h2 style="color: var(--neon-blue); border-bottom-color: var(--neon-blue); text-shadow: 0 0 5px var(--neon-blue);">🔮 PROTOCOLLO TRINITY</h2>
            <div class="status" style="border-left-color: var(--neon-pink);">
                <span>🕴️ <strong>Lo Strozzino</strong><br><small>Funding Arbitrage</small></span>
                <span class="online" style="color: var(--neon-pink); text-shadow: 0 0 5px var(--neon-pink);">● ACTIVE [Yielding]</span>
            </div>
            <div class="status" style="border-left-color: var(--neon-pink);">
                <span>🧮 <strong>Il Contabile</strong><br><small>Smart DCA Engine</small></span>
                <span class="online" style="color: var(--neon-pink); text-shadow: 0 0 5px var(--neon-pink);">● ACTIVE [Accumulating]</span>
            </div>
            <div class="status" style="border-left-color: var(--neon-pink);">
                <span>👼 <strong>L'Angelo Custode</strong><br><small>MEV Arbitrum Protection</small></span>
                <span class="online" style="color: var(--neon-pink); text-shadow: 0 0 5px var(--neon-pink);">● ACTIVE [Shielded]</span>
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel" style="border-color: var(--neon-green); box-shadow: inset 0 0 15px rgba(0,255,0,0.1), 0 0 15px rgba(0,255,0,0.2);">
            <h2 style="color: var(--neon-green); border-bottom-color: var(--neon-green); text-shadow: 0 0 5px var(--neon-green);">📊 METRICHE DI MERCATO</h2>
            <div class="status" style="border-left-color: var(--neon-blue);">
                <div class="metric">
                    <span>👁️ <strong>The Oracle</strong> <small>(Binance Sentiment)</small></span><br>
                    <span style="color: var(--neon-green); font-weight: bold; text-shadow: 0 0 5px var(--neon-green);">[BULLISH] 78% Long Volume</span>
                </div>
            </div>
            <div class="status" style="border-left-color: var(--neon-blue);">
                <div class="metric">
                    <span>🐋 <strong>Whale Tracker</strong></span><br>
                    <span style="color: var(--neon-pink); font-weight: bold; text-shadow: 0 0 5px var(--neon-pink);">ALERT: 50M USDT > Binance</span>
                </div>
            </div>
            <div class="status" style="border-left-color: var(--neon-blue);">
                <div class="metric">
                    <span>⚡ <strong>System Integrity</strong></span><br>
                    <span class="glitch-text">API Ping: 12ms | DB Sync: 100% OK</span>
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
    # Start on port 5000 (default Flask) or an env port
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
