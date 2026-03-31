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
        @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');
        body {
            background-color: #050508;
            color: #00ffcc;
            font-family: 'Share Tech Mono', monospace;
            margin: 0;
            padding: 30px;
            overflow-x: hidden;
            background-image: 
                linear-gradient(rgba(0, 255, 204, 0.03) 1px, transparent 1px),
                linear-gradient(90deg, rgba(0, 255, 204, 0.03) 1px, transparent 1px);
            background-size: 20px 20px;
        }
        h1 {
            text-align: center;
            color: #ff0055;
            text-shadow: 0 0 5px #ff0055, 0 0 15px #ff0055, 0 0 30px #ff0055;
            font-size: 3em;
            letter-spacing: 8px;
            border-bottom: 2px solid #ff0055;
            padding-bottom: 15px;
            margin-bottom: 40px;
            animation: glitch 2s infinite;
            text-transform: uppercase;
        }
        .container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 30px;
            max-width: 1400px;
            margin: 0 auto;
        }
        .panel {
            background: rgba(5, 5, 10, 0.8);
            border: 1px solid #00ffcc;
            box-shadow: 0 0 15px rgba(0, 255, 204, 0.15), inset 0 0 20px rgba(0, 255, 204, 0.05);
            border-radius: 4px;
            padding: 25px;
            position: relative;
            backdrop-filter: blur(5px);
            transition: all 0.3s ease;
        }
        .panel:hover {
            box-shadow: 0 0 25px rgba(0, 255, 204, 0.3), inset 0 0 30px rgba(0, 255, 204, 0.1);
            border-color: #fff;
        }
        .panel-title {
            font-size: 1.6em;
            color: #fff;
            margin-top: 0;
            border-bottom: 1px dashed #00ffcc;
            padding-bottom: 12px;
            text-shadow: 0 0 8px #00ffcc;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .status {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin: 15px 0;
            padding: 10px 15px;
            background: rgba(0, 0, 0, 0.6);
            border-left: 4px solid;
            font-size: 1.1em;
            letter-spacing: 1px;
        }
        .status.active { border-color: #00ffaa; color: #00ffaa; text-shadow: 0 0 5px #00ffaa; }
        .status.standby { border-color: #ffaa00; color: #ffaa00; text-shadow: 0 0 5px #ffaa00; }
        .status.trinity { border-color: #cc00ff; color: #cc00ff; text-shadow: 0 0 5px #cc00ff; }
        
        .glow-text { font-weight: bold; }
        .blink { animation: blinker 1.5s steps(2, start) infinite; }
        .fast-blink { animation: blinker 0.5s steps(2, start) infinite; }
        
        @keyframes blinker { to { visibility: hidden; } }
        @keyframes glitch {
            0% { text-shadow: 0 0 5px #ff0055, 0 0 15px #ff0055; }
            2% { transform: translate(-2px, 1px); text-shadow: -2px 0 #00ffcc, 2px 0 #ff0055; }
            4% { transform: translate(2px, -1px); text-shadow: 2px 0 #00ffcc, -2px 0 #ff0055; }
            6% { transform: translate(0, 0); text-shadow: 0 0 5px #ff0055, 0 0 15px #ff0055; }
        }
        
        .metric-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
            margin-top: 15px;
        }
        .metric-box {
            background: rgba(255, 0, 85, 0.05);
            border: 1px solid #ff0055;
            padding: 15px;
            text-align: center;
            color: #ff0055;
            box-shadow: inset 0 0 10px rgba(255, 0, 85, 0.1);
            position: relative;
            overflow: hidden;
        }
        .metric-box::after {
            content: '';
            position: absolute;
            top: -50%; left: -50%;
            width: 200%; height: 200%;
            background: linear-gradient(to bottom, rgba(255,255,255,0) 0%, rgba(255,255,255,0.03) 50%, rgba(255,255,255,0) 100%);
            transform: rotate(45deg);
            animation: scanline 4s linear infinite;
        }
        @keyframes scanline {
            0% { transform: translateY(-100%) rotate(45deg); }
            100% { transform: translateY(100%) rotate(45deg); }
        }
        .metric-value {
            font-size: 1.4em;
            font-weight: bold;
            margin-top: 8px;
            text-shadow: 0 0 8px #ff0055;
        }
        .footer {
            text-align: center;
            margin-top: 60px;
            color: #444;
            font-size: 0.9em;
            letter-spacing: 3px;
        }
    </style>
</head>
<body>
    <h1>[⚡] ORBITAL COMMAND [⚡]</h1>
    
    <div style="text-align: center; margin-bottom: 30px; padding: 15px; border: 2px solid #cc00ff; background: rgba(204, 0, 255, 0.1); color: #cc00ff; font-size: 1.5em; text-shadow: 0 0 10px #cc00ff; box-shadow: 0 0 20px rgba(204, 0, 255, 0.2); border-radius: 5px;" class="blink">
        ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
    </div>
    
    <div class="container">
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <h2 class="panel-title">⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <div class="status active">
                <span class="glow-text">🐺 SQUADRA_ALPHA</span>
                <span class="blink">[ENGAGED - Binance Scalper]</span>
            </div>
            <div class="status active">
                <span class="glow-text">🦅 SQUADRA_DELTA</span>
                <span class="blink">[ENGAGED - Order Flow]</span>
            </div>
            <div class="status standby">
                <span class="glow-text">🦂 SQUADRA_GAMMA</span>
                <span>[STANDBY - Bitget Pairs]</span>
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2 class="panel-title">🛡️ PROTOCOLLO TRINITY</h2>
            <div class="status trinity">
                <span class="glow-text">🕴️ Lo Strozzino</span>
                <span class="blink">[ONLINE - Funding Arb]</span>
            </div>
            <div class="status trinity">
                <span class="glow-text">🧮 Il Contabile</span>
                <span class="blink">[ONLINE - DCA Core]</span>
            </div>
            <div class="status trinity">
                <span class="glow-text">👼 L'Angelo Custode</span>
                <span class="blink">[ONLINE - Arbitrum MEV]</span>
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <h2 class="panel-title">📊 METRICHE DI MERCATO</h2>
            <div class="metric-grid">
                <div class="metric-box">
                    <div>🔮 THE ORACLE</div>
                    <div class="metric-value blink">FEAR: 32</div>
                </div>
                <div class="metric-box">
                    <div>🐋 WHALE TRACKER</div>
                    <div class="metric-value">+14.2M (1H)</div>
                </div>
                <div class="metric-box">
                    <div>📈 BINANCE SENTIMENT</div>
                    <div class="metric-value">LONG 68.4%</div>
                </div>
                <div class="metric-box">
                    <div>⚡ LATENCY</div>
                    <div class="metric-value fast-blink" style="color:#00ffcc; text-shadow:0 0 5px #00ffcc;">12ms</div>
                </div>
            </div>
        </div>
    </div>
    
    <div class="footer">
        SYS.CORE.V9.4.1 // UPLINK ESTABLISHED // <span class="blink">QUANTITATIVE OVERWATCH ACTIVE</span>
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
