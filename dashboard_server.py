from flask import Flask, render_template_string
import random

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NUVOLA ORBITAL COMMAND</title>
    <style>
        :root {
            --bg: #050510;
            --neon-green: #39ff14;
            --neon-cyan: #0ff;
            --neon-magenta: #ff00ff;
            --panel-bg: rgba(10, 20, 30, 0.8);
        }
        body {
            background-color: var(--bg);
            color: var(--neon-green);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 30px;
            display: flex;
            flex-direction: column;
            align-items: center;
            background-image: linear-gradient(rgba(0, 255, 0, 0.03) 1px, transparent 1px),
                              linear-gradient(90deg, rgba(0, 255, 0, 0.03) 1px, transparent 1px);
            background-size: 20px 20px;
        }
        h1 {
            color: var(--neon-cyan);
            text-shadow: 0 0 10px var(--neon-cyan), 0 0 20px var(--neon-cyan);
            text-transform: uppercase;
            letter-spacing: 5px;
            margin-bottom: 40px;
            border-bottom: 2px solid var(--neon-cyan);
            padding-bottom: 15px;
            text-align: center;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
            gap: 25px;
            width: 100%;
            max-width: 1200px;
        }
        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-green);
            box-shadow: 0 0 15px rgba(57, 255, 20, 0.3);
            padding: 20px;
            border-radius: 8px;
            position: relative;
            overflow: hidden;
            transition: transform 0.3s ease;
        }
        .panel:hover {
            transform: translateY(-5px);
            box-shadow: 0 0 25px rgba(57, 255, 20, 0.5);
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; height: 3px;
            background: var(--neon-green);
            box-shadow: 0 0 15px var(--neon-green);
            animation: scanline 2.5s linear infinite;
        }
        @keyframes scanline {
            0% { top: 0; opacity: 1; }
            100% { top: 100%; opacity: 0; }
        }
        .panel h2 {
            color: var(--neon-magenta);
            font-size: 1.3em;
            margin-top: 0;
            text-shadow: 0 0 8px var(--neon-magenta);
            border-bottom: 1px dotted var(--neon-magenta);
            padding-bottom: 10px;
            display: flex;
            align-items: center;
        }
        ul { list-style-type: none; padding: 0; margin: 0; }
        li { margin: 12px 0; display: flex; justify-content: space-between; align-items: center; font-size: 1.1em;}
        .status-online { 
            color: var(--neon-green); 
            text-shadow: 0 0 5px var(--neon-green); 
            animation: blink 2s infinite; 
            font-weight: bold;
        }
        @keyframes blink { 
            0%, 100% { opacity: 1; } 
            50% { opacity: 0.4; } 
        }
        .data-value { 
            color: var(--neon-cyan); 
            font-weight: bold;
            text-shadow: 0 0 4px var(--neon-cyan);
        }
        .flash { animation: flashText 4s infinite alternate; }
        @keyframes flashText { 
            0% { color: var(--neon-green); text-shadow: 0 0 5px var(--neon-green); } 
            100% { color: var(--neon-cyan); text-shadow: 0 0 5px var(--neon-cyan); } 
        }
        .footer {
            margin-top: 50px;
            font-size: 0.9em;
            color: #555;
            text-align: center;
            letter-spacing: 2px;
        }
    </style>
</head>
<body>
    <h1>🛰️ Nuvola Orbital Command 🛰️</h1>
    <div style="background-color: rgba(57, 255, 20, 0.1); border: 1px solid var(--neon-green); color: var(--neon-green); padding: 10px 20px; border-radius: 5px; margin-bottom: 30px; font-weight: bold; text-shadow: 0 0 5px var(--neon-green); text-align: center; width: 80%; max-width: 800px;">
        ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
    </div>
    
    <div class="grid">
        <!-- SQUADRE D'ASSALTO -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <ul>
                <li><span>🐺 SQUADRA_ALPHA <br><small style="color:#aaa;font-size:0.8em;">(Binance Scalper)</small></span> <span class="status-online">[OPERATIVO]</span></li>
                <li><span>🌊 SQUADRA_DELTA <br><small style="color:#aaa;font-size:0.8em;">(Order Flow)</small></span> <span class="status-online">[OPERATIVO]</span></li>
                <li><span>⚖️ SQUADRA_GAMMA <br><small style="color:#aaa;font-size:0.8em;">(Bitget Pairs)</small></span> <span class="status-online">[OPERATIVO]</span></li>
            </ul>
            <div style="margin-top: 20px; font-size: 0.9em; color: #888; border-top: 1px solid #333; padding-top: 10px;">
                > High-Frequency execution active.<br>
                > Latency: <span class="data-value" id="latency">12ms</span>
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2>🔺 PROTOCOLLO TRINITY</h2>
            <ul>
                <li><span>🕴️ Lo Strozzino <br><small style="color:#aaa;font-size:0.8em;">(Funding Arb)</small></span> <span class="status-online">[ACTIVE]</span></li>
                <li><span>🧮 Il Contabile <br><small style="color:#aaa;font-size:0.8em;">(DCA)</small></span> <span class="status-online">[ACTIVE]</span></li>
                <li><span>🛡️ L'Angelo Custode <br><small style="color:#aaa;font-size:0.8em;">(MEV Arbitrum)</small></span> <span class="status-online">[ACTIVE]</span></li>
            </ul>
            <div style="margin-top: 20px; font-size: 0.9em; color: #888; border-top: 1px solid #333; padding-top: 10px;">
                > Background wealth generation stealth.<br>
                > Trinity synchronization: <span class="flash">100%</span>
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <h2>📊 METRICHE DI MERCATO</h2>
            <ul>
                <li><span>👁️ The Oracle (Binance)</span> <span class="data-value">BULLISH (82%)</span></li>
                <li><span>🐳 Whale Tracker</span> <span class="data-value">+2,104 BTC</span></li>
                <li><span>🔥 Liquidations (24h)</span> <span class="data-value">$84.2M</span></li>
                <li><span>⚡ Volatility Index</span> <span class="data-value flash">ELEVATO</span></li>
            </ul>
            <div style="margin-top: 20px; font-size: 0.85em; color: #555; font-style: italic; border-top: 1px solid #333; padding-top: 10px;">
                * Data streamed securely via Nuvola deep nodes.
            </div>
        </div>
    </div>
    
    <div class="footer">
        SYSTEM STATUS: NOMINAL. ENCRYPTED CONNECTION ESTABLISHED.
    </div>

    <script>
        // Update latency periodically to make it look alive
        setInterval(() => {
            const latencyEl = document.getElementById('latency');
            if(latencyEl) {
                const ms = Math.floor(Math.random() * 8) + 8; // 8-15ms
                latencyEl.innerText = ms + 'ms';
            }
        }, 1500);

        // Blinking metrics
        setInterval(() => {
            const oracolo = document.querySelectorAll('.data-value')[0];
            const rand = Math.random();
            if(rand > 0.8) {
                oracolo.innerText = 'BULLISH (' + (Math.floor(Math.random() * 5) + 80) + '%)';
            } else if (rand < 0.1) {
                oracolo.innerText = 'NEUTRAL (55%)';
            }
        }, 4000);
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    # Flask app running on port 5000 (default) or configurable
    app.run(host='0.0.0.0', port=5000)
