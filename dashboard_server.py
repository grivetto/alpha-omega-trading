from flask import Flask, render_template_string
import os

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Nuvola | Orbital Command</title>
    <style>
        :root {
            --neon-green: #0f0;
            --neon-cyan: #0ff;
            --neon-magenta: #f0f;
            --bg-dark: #050505;
            --panel-bg: #111;
        }
        body {
            background-color: var(--bg-dark);
            color: var(--neon-green);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            display: flex;
            flex-direction: column;
            align-items: center;
        }
        h1 {
            text-shadow: 0 0 10px var(--neon-cyan);
            color: var(--neon-cyan);
            text-align: center;
            text-transform: uppercase;
            letter-spacing: 4px;
            border-bottom: 2px solid var(--neon-cyan);
            padding-bottom: 10px;
            width: 100%;
            max-width: 1200px;
        }
        .grid-container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
            width: 100%;
            max-width: 1200px;
            margin-top: 20px;
        }
        .panel {
            background-color: var(--panel-bg);
            border: 1px solid var(--neon-green);
            border-radius: 5px;
            padding: 15px;
            box-shadow: 0 0 15px rgba(0, 255, 0, 0.2);
            transition: all 0.3s ease;
        }
        .panel:hover {
            box-shadow: 0 0 25px rgba(0, 255, 0, 0.5);
        }
        .panel h2 {
            margin-top: 0;
            color: var(--neon-magenta);
            text-shadow: 0 0 8px var(--neon-magenta);
            font-size: 1.2em;
            border-bottom: 1px dashed var(--neon-magenta);
            padding-bottom: 5px;
        }
        .status-item {
            display: flex;
            justify-content: space-between;
            margin: 10px 0;
            padding: 5px;
            background: rgba(0, 255, 0, 0.05);
            border-left: 3px solid var(--neon-green);
        }
        .blink {
            animation: blinker 1.5s linear infinite;
        }
        @keyframes blinker {
            50% { opacity: 0; }
        }
        .online { color: var(--neon-green); text-shadow: 0 0 5px var(--neon-green); }
        .standby { color: #ffa500; text-shadow: 0 0 5px #ffa500; }
        .active { color: var(--neon-cyan); text-shadow: 0 0 5px var(--neon-cyan); }
        .alert { color: #f33; text-shadow: 0 0 5px #f33; }
        
        .terminal {
            font-size: 0.9em;
            color: #aaa;
        }
    </style>
</head>
<body>

    <h1>🛰️ ORBITAL COMMAND - NUVOLA DASHBOARD 🛰️</h1>

    <div class="grid-container">
        <!-- SQUADRE D'ASSALTO -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <div class="status-item">
                <span>🐺 SQUADRA_ALPHA <br><small class="terminal">[Scalper Binance]</small></span>
                <span class="active blink">ENGAGED</span>
            </div>
            <div class="status-item">
                <span>🦅 SQUADRA_DELTA <br><small class="terminal">[Order Flow]</small></span>
                <span class="standby">STANDBY</span>
            </div>
            <div class="status-item">
                <span>🦂 SQUADRA_GAMMA <br><small class="terminal">[Pairs Trading Bitget]</small></span>
                <span class="active blink">ENGAGED</span>
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2>⟁ PROTOCOLLO TRINITY</h2>
            <div class="status-item">
                <span>🕴️ Lo Strozzino <br><small class="terminal">[Funding Arb]</small></span>
                <span class="online">ONLINE</span>
            </div>
            <div class="status-item">
                <span>🧮 Il Contabile <br><small class="terminal">[DCA Accumulator]</small></span>
                <span class="online">ONLINE</span>
            </div>
            <div class="status-item">
                <span>🛡️ L'Angelo Custode <br><small class="terminal">[MEV Arbitrum]</small></span>
                <span class="online">ONLINE</span>
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <h2>📊 METRICHE DI MERCATO</h2>
            <div class="status-item">
                <span>👁️ The Oracle <br><small class="terminal">[Binance Sentiment]</small></span>
                <span class="active">BULLISH 68%</span>
            </div>
            <div class="status-item">
                <span>🐋 Whale Tracker <br><small class="terminal">[On-Chain Sonar]</small></span>
                <span class="alert blink">ALERT: +120k ETH</span>
            </div>
            <div class="status-item">
                <span>⚡ Latency Core <br><small class="terminal">[API RTT]</small></span>
                <span class="online">8ms</span>
            </div>
        </div>
    </div>
    
    <div style="margin-top: 30px; width: 100%; max-width: 1200px; text-align: left; color: #555;">
        <p>SYSTEM STATUS: <span class="online">NOMINAL</span> | CLEARANCE: <span style="color:var(--neon-magenta)">ALPHA-RED</span> | AUTO-COMPOUNDING: <span class="online">ACTIVE</span></p>
        <p style="color: var(--neon-cyan); font-weight: bold; font-size: 1.1em;">⚙️ PROTOCOLLO TRINITY: <span class="online blink">Online (DCA, Funding, MEV)</span></p>
    </div>

</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
