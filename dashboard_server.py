from flask import Flask, render_template_string
import threading
import time
import random

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ORBITAL COMMAND - Nuvola</title>
    <style>
        :root {
            --neon-blue: #0ff;
            --neon-pink: #f0f;
            --neon-green: #39ff14;
            --dark-bg: #0a0a0a;
            --panel-bg: rgba(10, 10, 10, 0.8);
            --border-glow: 0 0 10px var(--neon-blue), inset 0 0 10px var(--neon-blue);
        }
        
        body {
            background-color: var(--dark-bg);
            color: var(--neon-blue);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            background-image: 
                linear-gradient(rgba(0, 255, 255, 0.1) 1px, transparent 1px),
                linear-gradient(90deg, rgba(0, 255, 255, 0.1) 1px, transparent 1px);
            background-size: 20px 20px;
            overflow-x: hidden;
        }

        h1, h2, h3 {
            text-shadow: 0 0 5px var(--neon-blue);
            text-transform: uppercase;
            letter-spacing: 2px;
        }

        .header {
            text-align: center;
            padding: 20px;
            border: 1px solid var(--neon-blue);
            box-shadow: var(--border-glow);
            margin-bottom: 30px;
            background: var(--panel-bg);
            animation: pulse 2s infinite alternate;
        }

        .container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
        }

        .panel {
            border: 1px solid var(--neon-blue);
            padding: 20px;
            background: var(--panel-bg);
            box-shadow: 0 0 5px rgba(0,255,255,0.2);
            position: relative;
        }

        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; width: 10px; height: 10px;
            border-top: 2px solid var(--neon-pink);
            border-left: 2px solid var(--neon-pink);
        }
        
        .panel::after {
            content: '';
            position: absolute;
            bottom: 0; right: 0; width: 10px; height: 10px;
            border-bottom: 2px solid var(--neon-pink);
            border-right: 2px solid var(--neon-pink);
        }

        .status-online { color: var(--neon-green); text-shadow: 0 0 5px var(--neon-green); }
        .status-offline { color: #f00; text-shadow: 0 0 5px #f00; }
        .status-standby { color: #ff0; text-shadow: 0 0 5px #ff0; }

        .metric {
            display: flex;
            justify-content: space-between;
            margin: 10px 0;
            border-bottom: 1px dashed rgba(0,255,255,0.3);
            padding-bottom: 5px;
        }

        @keyframes pulse {
            0% { box-shadow: 0 0 10px var(--neon-blue), inset 0 0 10px var(--neon-blue); }
            100% { box-shadow: 0 0 20px var(--neon-blue), inset 0 0 20px var(--neon-blue); }
        }

        @keyframes scanline {
            0% { transform: translateY(-100%); }
            100% { transform: translateY(100vh); }
        }

        .scanline {
            position: fixed;
            top: 0; left: 0; width: 100%; height: 5px;
            background: rgba(0, 255, 255, 0.3);
            opacity: 0.5;
            animation: scanline 5s linear infinite;
            pointer-events: none;
            z-index: 9999;
        }
        
        .blink {
            animation: blinker 1s linear infinite;
        }
        
        @keyframes blinker {
            50% { opacity: 0; }
        }
    </style>
</head>
<body>
    <div class="scanline"></div>

    <div class="header">
        <h1>🛰️ ORBITAL COMMAND 🛰️</h1>
        <h3>NUVOLA SYSTEM CORE | STATUS: <span class="status-online blink">ONLINE</span></h3>
        <p>SYSTEM TIME: {{ time }} UTC</p>
        <h3 style="color: var(--neon-green); margin-top: 10px; border-top: 1px dashed var(--neon-green); padding-top: 10px;">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</h3>
    </div>

    <div class="container">
        <!-- SQUADRE D'ASSALTO -->
        <div class="panel" style="border-color: var(--neon-pink);">
            <h2 style="color: var(--neon-pink);">⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <div class="metric">
                <span>[ALPHA] Scalper (Binance)</span>
                <span class="status-online">ENGAGED</span>
            </div>
            <div class="metric">
                <span>[DELTA] Order Flow</span>
                <span class="status-online">MONITORING</span>
            </div>
            <div class="metric">
                <span>[GAMMA] Pairs Trading (Bitget)</span>
                <span class="status-standby">CALIBRATING</span>
            </div>
            <div style="margin-top: 15px; font-size: 0.8em; color: #888;">
                > Target acquisition active...<br>
                > Latency: 12ms
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel" style="border-color: var(--neon-green);">
            <h2 style="color: var(--neon-green);">🛡️ PROTOCOLLO TRINITY</h2>
            <div class="metric">
                <span>🎩 Lo Strozzino (Funding Arb)</span>
                <span class="status-online">ACTIVE</span>
            </div>
            <div class="metric">
                <span>💼 Il Contabile (DCA)</span>
                <span class="status-online">ACTIVE</span>
            </div>
            <div class="metric">
                <span>👼 L'Angelo Custode (MEV Arbitrum)</span>
                <span class="status-online">PATROLLING</span>
            </div>
            <div style="margin-top: 15px; font-size: 0.8em; color: #888;">
                > Background processes secured.<br>
                > Yield optimization stable.
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <h2>📊 METRICHE DI MERCATO</h2>
            <div class="metric">
                <span>👁️ The Oracle (Binance Sentiment)</span>
                <span>BULLISH [78%]</span>
            </div>
            <div class="metric">
                <span>🐋 Whale Tracker (Large TXs)</span>
                <span class="status-standby">DETECTED (3)</span>
            </div>
            <div class="metric">
                <span>⚡ Network Gwei (ETH)</span>
                <span>{{ gwei }}</span>
            </div>
            <div class="metric">
                <span>📈 BTC/USDT</span>
                <span class="status-online">{{ btc_price }}</span>
            </div>
        </div>
    </div>

    <script>
        // Auto-refresh every 5 seconds for that live dashboard feel
        setTimeout(function() {
            location.reload();
        }, 5000);
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    import datetime
    current_time = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    fake_gwei = random.randint(15, 45)
    fake_btc = f"${random.uniform(69000, 71000):.2f}"
    
    return render_template_string(
        HTML_TEMPLATE, 
        time=current_time, 
        gwei=fake_gwei, 
        btc_price=fake_btc
    )

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
