from flask import Flask, render_template_string
import threading
import logging

app = Flask(__name__)
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Nuvola Orbital Command</title>
    <style>
        :root {
            --neon-green: #39ff14;
            --neon-cyan: #00ffff;
            --neon-magenta: #ff00ff;
            --neon-red: #ff003c;
            --dark-bg: #050505;
            --panel-bg: #0f0f1a;
            --grid-color: rgba(0, 255, 255, 0.05);
        }
        
        @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');
        
        body {
            background-color: var(--dark-bg);
            color: var(--neon-cyan);
            font-family: 'Share Tech Mono', 'Courier New', monospace;
            margin: 0;
            padding: 30px;
            background-image: 
                linear-gradient(var(--grid-color) 1px, transparent 1px),
                linear-gradient(90deg, var(--grid-color) 1px, transparent 1px);
            background-size: 30px 30px;
            background-position: center center;
            overflow-x: hidden;
        }

        /* Glitch effect on header */
        h1 {
            text-align: center;
            color: #fff;
            font-size: 3em;
            margin-bottom: 5px;
            text-transform: uppercase;
            letter-spacing: 5px;
            text-shadow: 0 0 10px var(--neon-cyan), 0 0 20px var(--neon-cyan), 0 0 40px var(--neon-magenta);
            animation: glitch 1.5s infinite;
        }
        
        .sub-header {
            text-align: center;
            color: var(--neon-green);
            font-size: 1.2em;
            margin-bottom: 40px;
            letter-spacing: 2px;
            animation: pulse 2s infinite;
        }

        h2 {
            color: var(--neon-magenta);
            border-bottom: 2px solid var(--neon-magenta);
            padding-bottom: 10px;
            margin-top: 0;
            font-size: 1.5em;
            text-shadow: 0 0 5px var(--neon-magenta);
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 30px;
            max-width: 1400px;
            margin: 0 auto;
        }

        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-cyan);
            border-radius: 4px;
            padding: 20px;
            box-shadow: 0 0 15px rgba(0, 255, 255, 0.1), inset 0 0 20px rgba(0, 255, 255, 0.05);
            position: relative;
            overflow: hidden;
        }

        /* Scanning laser line */
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: -100%; width: 50%; height: 2px;
            background: linear-gradient(90deg, transparent, var(--neon-cyan), transparent);
            animation: scanline 4s linear infinite;
        }

        .status-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin: 15px 0;
            padding: 10px 15px;
            background: rgba(0, 255, 255, 0.03);
            border-left: 4px solid var(--neon-cyan);
            transition: all 0.3s ease;
        }

        .status-item:hover {
            background: rgba(0, 255, 255, 0.1);
            transform: translateX(5px);
        }

        .status-item.active { border-left-color: var(--neon-green); }
        .status-item.active .status { color: var(--neon-green); text-shadow: 0 0 8px var(--neon-green); font-weight: bold; }
        
        .status-item.alert { border-left-color: var(--neon-red); }
        .status-item.alert .status { color: var(--neon-red); text-shadow: 0 0 8px var(--neon-red); animation: pulse 1s infinite; }

        .name { font-size: 1.1em; }
        .metric { font-size: 1.2em; font-weight: bold; color: var(--neon-cyan); text-shadow: 0 0 5px var(--neon-cyan); }
        .metric-value { font-family: monospace; }

        /* Animations */
        @keyframes scanline {
            0% { left: -100%; top: 0; }
            50% { left: 100%; top: 0; }
            51% { left: 100%; top: 100%; }
            100% { left: -100%; top: 100%; }
        }

        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.5; }
            100% { opacity: 1; }
        }

        @keyframes glitch {
            0% { text-shadow: 2px 0 var(--neon-magenta), -2px 0 var(--neon-cyan); }
            5% { text-shadow: -2px 0 var(--neon-magenta), 2px 0 var(--neon-cyan); }
            10% { text-shadow: 2px 0 var(--neon-magenta), -2px 0 var(--neon-cyan); }
            15% { text-shadow: none; }
            100% { text-shadow: 0 0 10px var(--neon-cyan), 0 0 20px var(--neon-cyan); }
        }

        /* CRT Overlay effect */
        .crt::before {
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

    </style>
</head>
<body class="crt">
    <h1>🛰️ ORBITAL COMMAND 🛰️</h1>
    <div class="sub-header">>> SECURE CONNECTION ESTABLISHED | SYSTEM ONLINE | ALL PROTOCOLS ENGAGED <<<br>
    <span style="color: var(--neon-magenta); font-weight: bold; text-shadow: 0 0 10px var(--neon-magenta);">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</span></div>
    
    <div class="container">
        <!-- SEZIONE 1: SQUADRE D'ASSALTO -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <div class="status-item active">
                <span class="name">SQUADRA_ALPHA <span style="font-size:0.8em; color:#888;">[Binance Scalper]</span></span>
                <span class="status">🟢 ENGAGED</span>
            </div>
            <div class="status-item active">
                <span class="name">SQUADRA_DELTA <span style="font-size:0.8em; color:#888;">[Order Flow]</span></span>
                <span class="status">🟢 MONITORING</span>
            </div>
            <div class="status-item active">
                <span class="name">SQUADRA_GAMMA <span style="font-size:0.8em; color:#888;">[Bitget Pairs]</span></span>
                <span class="status">🟢 ARBITRAGE</span>
            </div>
            <div style="margin-top: 15px; font-size: 0.8em; color: #555; text-align: right;">UPTIME: 99.99% | LATENCY: 12ms</div>
        </div>

        <!-- SEZIONE 2: PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2>⚡ PROTOCOLLO TRINITY</h2>
            <div class="status-item active">
                <span class="name">Lo Strozzino <span style="font-size:0.8em; color:#888;">[Funding Arb]</span></span>
                <span class="status">🟢 YIELDING</span>
            </div>
            <div class="status-item active">
                <span class="name">Il Contabile <span style="font-size:0.8em; color:#888;">[DCA Matrix]</span></span>
                <span class="status">🟢 ACCUMULATING</span>
            </div>
            <div class="status-item active">
                <span class="name">L'Angelo Custode <span style="font-size:0.8em; color:#888;">[MEV Arbitrum]</span></span>
                <span class="status">🟢 SHIELDING</span>
            </div>
            <div style="margin-top: 15px; font-size: 0.8em; color: #555; text-align: right;">SMART CONTRACTS SYNCED</div>
        </div>

        <!-- SEZIONE 3: METRICHE DI MERCATO -->
        <div class="panel">
            <h2>📊 METRICHE DI MERCATO</h2>
            <div class="status-item">
                <span class="name">The Oracle <span style="font-size:0.8em; color:#888;">[Binance Sentiment]</span></span>
                <span class="metric" style="color: var(--neon-magenta);">BULLISH (78%)</span>
            </div>
            <div class="status-item">
                <span class="name">Whale Tracker <span style="font-size:0.8em; color:#888;">[Large TXs]</span></span>
                <span class="metric" style="color: var(--neon-cyan);">4 INFLOWS / 1 OUT</span>
            </div>
            <div class="status-item alert">
                <span class="name">Liquidity Heatmap <span style="font-size:0.8em; color:#888;">[BTC/USDT]</span></span>
                <span class="metric" style="color: var(--neon-red);">FLASH CRASH WARN</span>
            </div>
            <div style="margin-top: 15px; font-size: 0.8em; color: #555; text-align: right;">DATA STREAM ACTIVE</div>
        </div>
    </div>

    <script>
        // Fake dynamic updates to make it look alive
        setInterval(() => {
            const oracles = ['BULLISH (78%)', 'BULLISH (81%)', 'NEUTRAL (55%)', 'BULLISH (76%)'];
            const metrics = document.querySelectorAll('.metric');
            if(metrics.length > 0) {
                // Randomly slightly change the oracle text
                if (Math.random() > 0.7) {
                    metrics[0].innerText = oracles[Math.floor(Math.random() * oracles.length)];
                }
            }
        }, 3000);
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
