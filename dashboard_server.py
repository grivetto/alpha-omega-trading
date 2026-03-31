import os
from flask import Flask, render_template_string

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
            background-color: #050505;
            color: #0f0;
            font-family: 'Share Tech Mono', monospace;
            margin: 0;
            padding: 30px;
            overflow-x: hidden;
        }
        
        h1, h2, h3 { 
            color: #0ff; 
            text-shadow: 0 0 10px #0ff; 
            text-align: center; 
            margin-top: 0;
        }
        
        .header-title {
            font-size: 2.5em;
            letter-spacing: 5px;
            border-bottom: 2px solid #0ff;
            padding-bottom: 10px;
            margin-bottom: 20px;
            box-shadow: 0 10px 10px -10px #0ff;
        }
        
        .container { 
            display: flex; 
            flex-wrap: wrap; 
            gap: 30px; 
            justify-content: center; 
            margin-top: 40px;
        }
        
        .panel {
            border: 1px solid #0f0;
            box-shadow: 0 0 15px #0f0 inset, 0 0 15px #0f0;
            padding: 20px;
            width: 30%;
            min-width: 320px;
            background: rgba(0, 255, 0, 0.05);
            position: relative;
            transition: all 0.3s ease;
        }
        
        .panel:hover {
            box-shadow: 0 0 25px #0f0 inset, 0 0 25px #0f0;
            transform: scale(1.02);
        }
        
        .panel.trinity { 
            border-color: #f0f; 
            box-shadow: 0 0 15px #f0f inset, 0 0 15px #f0f; 
            background: rgba(255, 0, 255, 0.05); 
            color: #f0f;
        }
        .panel.trinity:hover { box-shadow: 0 0 25px #f0f inset, 0 0 25px #f0f; }
        .panel.trinity h2 { color: #f0f; text-shadow: 0 0 10px #f0f; }
        
        .panel.market { 
            border-color: #ff0; 
            box-shadow: 0 0 15px #ff0 inset, 0 0 15px #ff0; 
            background: rgba(255, 255, 0, 0.05); 
            color: #ff0;
        }
        .panel.market:hover { box-shadow: 0 0 25px #ff0 inset, 0 0 25px #ff0; }
        .panel.market h2 { color: #ff0; text-shadow: 0 0 10px #ff0; }
        
        .status-online { 
            color: #0f0; 
            text-shadow: 0 0 8px #0f0; 
            animation: blink 1.5s infinite; 
            font-weight: bold;
        }
        
        .status-standby { color: #fa0; text-shadow: 0 0 8px #fa0; }
        .status-active { color: #0ff; text-shadow: 0 0 8px #0ff; animation: pulse 2s infinite;}
        
        @keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
        @keyframes pulse { 0% { text-shadow: 0 0 5px #0ff; } 50% { text-shadow: 0 0 20px #0ff; } 100% { text-shadow: 0 0 5px #0ff; } }
        
        .data-row { 
            display: flex; 
            justify-content: space-between; 
            margin-bottom: 12px; 
            padding-bottom: 8px;
            border-bottom: 1px dashed rgba(0,255,0,0.3); 
            font-size: 1.1em;
        }
        .trinity .data-row { border-bottom: 1px dashed rgba(255,0,255,0.3); }
        .market .data-row { border-bottom: 1px dashed rgba(255,255,0,0.3); }
        
        .terminal-log {
            margin-top: 15px;
            font-size: 0.85em;
            opacity: 0.8;
            font-family: monospace;
            height: 40px;
            overflow: hidden;
        }
        
        /* CRT Scanline effect */
        body::after {
            content: " ";
            display: block;
            position: fixed;
            top: 0; left: 0; bottom: 0; right: 0;
            background: linear-gradient(rgba(18, 16, 16, 0) 50%, rgba(0, 0, 0, 0.25) 50%), linear-gradient(90deg, rgba(255, 0, 0, 0.06), rgba(0, 255, 0, 0.02), rgba(0, 0, 255, 0.06));
            z-index: 2;
            background-size: 100% 3px, 3px 100%;
            pointer-events: none;
        }
    </style>
</head>
<body>
    <h1 class="header-title">[ NUVOLA ORBITAL COMMAND ]</h1>
    <h3 style="color: #0f0; letter-spacing: 2px;">
        SYSTEM: <span class="status-online">ONLINE</span> | UPLINK: SECURE | ENCRYPTION: AES-256
    </h3>
    <h3 style="color: #f0f; letter-spacing: 2px; text-shadow: 0 0 10px #f0f;">
        ⚙️ PROTOCOLLO TRINITY: <span class="status-online" style="color: #f0f; text-shadow: 0 0 8px #f0f;">Online (DCA, Funding, MEV)</span>
    </h3>
    
    <div class="container">
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <div class="data-row">
                <span>🐺 SQUADRA_ALPHA <br><small>[Binance Scalper]</small></span> 
                <span class="status-online">ENGAGED</span>
            </div>
            <div class="data-row">
                <span>💧 SQUADRA_DELTA <br><small>[Order Flow]</small></span> 
                <span class="status-standby">STANDBY</span>
            </div>
            <div class="data-row">
                <span>⚖️ SQUADRA_GAMMA <br><small>[Bitget Pairs]</small></span> 
                <span class="status-active">ACTIVE</span>
            </div>
            <div class="terminal-log">
                > Initializing quant-models... OK<br>
                > High Frequency Trading protocols nominal.
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel trinity">
            <h2>🔮 PROTOCOLLO TRINITY</h2>
            <div class="data-row">
                <span>🏦 Lo Strozzino <br><small>[Funding Arb]</small></span> 
                <span class="status-online">HARVESTING</span>
            </div>
            <div class="data-row">
                <span>🧮 Il Contabile <br><small>[DCA Bot]</small></span> 
                <span class="status-online">ACCUMULATING</span>
            </div>
            <div class="data-row">
                <span>👼 L'Angelo Custode <br><small>[MEV Arbitrum]</small></span> 
                <span class="status-active">MONITORING MEMPOOL</span>
            </div>
            <div class="terminal-log">
                > Connecting to Web3 RPC... OK<br>
                > Background wealth generation active.
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel market">
            <h2>📡 METRICHE DI MERCATO</h2>
            <div class="data-row">
                <span>👁️ The Oracle <br><small>[Binance Sentiment]</small></span> 
                <span style="color: #0f0; font-weight: bold;">BULLISH [78%]</span>
            </div>
            <div class="data-row">
                <span>🐋 Whale Tracker <br><small>[Large TX Alerts]</small></span> 
                <span style="color: #0ff;">+450M USDT INFLOW</span>
            </div>
            <div class="data-row">
                <span>⚡ Network State <br><small>[ETH Gas]</small></span> 
                <span style="color: #fa0;">15 Gwei</span>
            </div>
            <div class="terminal-log">
                > Syncing blockchain states... OK<br>
                > Real-time data feeds connected.
            </div>
        </div>
    </div>
    
    <script>
        // Simple randomizing script to make the dashboard look alive
        setInterval(() => {
            const elements = document.querySelectorAll('.terminal-log');
            elements.forEach(el => {
                if(Math.random() > 0.8) {
                    el.style.opacity = Math.random() * 0.5 + 0.5;
                }
            });
        }, 500);
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    # Server runs on port 5000 by default
    app.run(host='0.0.0.0', port=5000, debug=False)
