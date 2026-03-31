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
        :root {
            --neon-green: #0f0;
            --neon-blue: #0ff;
            --neon-pink: #f0f;
            --dark-bg: #050505;
            --panel-bg: rgba(0, 20, 0, 0.8);
        }
        body {
            background-color: var(--dark-bg);
            color: var(--neon-green);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            background-image: linear-gradient(rgba(0, 255, 0, 0.03) 1px, transparent 1px),
                              linear-gradient(90deg, rgba(0, 255, 0, 0.03) 1px, transparent 1px);
            background-size: 20px 20px;
        }
        h1, h2, h3 {
            text-shadow: 0 0 5px var(--neon-green), 0 0 10px var(--neon-green);
            text-transform: uppercase;
            letter-spacing: 2px;
            margin-top: 0;
        }
        .header {
            text-align: center;
            border-bottom: 2px solid var(--neon-green);
            padding-bottom: 10px;
            margin-bottom: 20px;
            animation: flicker 4s infinite;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
            gap: 20px;
        }
        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-green);
            padding: 15px;
            box-shadow: inset 0 0 10px rgba(0, 255, 0, 0.2), 0 0 15px rgba(0, 255, 0, 0.2);
            position: relative;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; width: 100%; height: 2px;
            background: var(--neon-green);
            box-shadow: 0 0 10px var(--neon-green);
        }
        .status-indicator {
            display: inline-block;
            width: 10px; height: 10px;
            border-radius: 50%;
            background-color: var(--neon-green);
            box-shadow: 0 0 8px var(--neon-green);
            margin-right: 10px;
            animation: pulse 1.5s infinite;
        }
        .status-indicator.blue {
            background-color: var(--neon-blue);
            box-shadow: 0 0 8px var(--neon-blue);
        }
        .status-indicator.pink {
            background-color: var(--neon-pink);
            box-shadow: 0 0 8px var(--neon-pink);
        }
        .item {
            margin: 15px 0;
            border-bottom: 1px dashed rgba(0, 255, 0, 0.3);
            padding-bottom: 8px;
            font-size: 0.95em;
        }
        .value {
            float: right;
            font-weight: bold;
        }
        .blue-text { color: var(--neon-blue); text-shadow: 0 0 5px var(--neon-blue); }
        .pink-text { color: var(--neon-pink); text-shadow: 0 0 5px var(--neon-pink); }
        @keyframes pulse {
            0% { transform: scale(0.95); opacity: 0.5; }
            50% { transform: scale(1.2); opacity: 1; }
            100% { transform: scale(0.95); opacity: 0.5; }
        }
        @keyframes flicker {
            0%, 19%, 21%, 23%, 25%, 54%, 56%, 100% { opacity: 1; }
            20%, 22%, 24%, 55% { opacity: 0.5; }
        }
    </style>
    <script>
        setInterval(() => {
            document.querySelectorAll('.rand-val').forEach(el => {
                let val = parseFloat(el.getAttribute('data-base'));
                let noise = parseFloat(el.getAttribute('data-noise'));
                let change = (Math.random() - 0.5) * noise;
                el.innerText = (val + change).toFixed(2);
            });
        }, 1500);
    </script>
</head>
<body>
    <div class="header">
        <h1>🌐 ORBITAL COMMAND 🌐</h1>
        <p>SYSTEM STATUS: <span class="status-indicator"></span> ONLINE | SECURE QUANTUM UPLINK ESTABLISHED</p>
        <p style="color: var(--neon-blue); font-weight: bold; font-size: 1.1em; text-shadow: 0 0 8px var(--neon-blue);">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</p>
    </div>

    <div class="grid">
        <!-- PATRIMONIO -->
        <div class="panel">
            <h2>💰 PATRIMONIO</h2>
            <div class="item">
                <span class="status-indicator"></span> Total Balance
                <span class="value">$ <span class="rand-val" data-base="150000.00" data-noise="100">150000.00</span></span>
            </div>
            <div class="item">
                <p style="color: var(--neon-blue); font-weight: bold; font-size: 1.1em; text-shadow: 0 0 8px var(--neon-blue);">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</p>
            </div>
        </div>

        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <div class="item">
                <span class="status-indicator"></span> SQUADRA_ALPHA <span class="blue-text">[Scalper Binance]</span>
                <span class="value">ACTV - <span class="rand-val" data-base="42.50" data-noise="5">42.50</span> ops/min</span>
            </div>
            <div class="item">
                <span class="status-indicator"></span> SQUADRA_DELTA <span class="blue-text">[Order Flow]</span>
                <span class="value">ACTV - <span class="rand-val" data-base="15.20" data-noise="2">15.20</span> ops/min</span>
            </div>
            <div class="item">
                <span class="status-indicator"></span> SQUADRA_GAMMA <span class="blue-text">[Pairs Trading Bitget]</span>
                <span class="value">ACTV - <span class="rand-val" data-base="8.40" data-noise="1.5">8.40</span> ops/min</span>
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2>🔺 PROTOCOLLO TRINITY</h2>
            <div class="item">
                <span class="status-indicator blue"></span> Lo Strozzino <span class="pink-text">[Funding Arb]</span>
                <span class="value">BKGND - SYNCING</span>
            </div>
            <div class="item">
                <span class="status-indicator blue"></span> Il Contabile <span class="pink-text">[DCA]</span>
                <span class="value">BKGND - RUNNING</span>
            </div>
            <div class="item">
                <span class="status-indicator blue"></span> L'Angelo Custode <span class="pink-text">[MEV Arbitrum]</span>
                <span class="value">BKGND - WATCHING</span>
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <h2>📊 METRICHE DI MERCATO</h2>
            <div class="item">
                👁️ The Oracle <span class="blue-text">[Binance Sentiment]</span>
                <span class="value">BULLISH (<span class="rand-val" data-base="68.5" data-noise="3">68.5</span>%)</span>
            </div>
            <div class="item">
                🐋 Whale Tracker <span class="blue-text">[On-Chain Flow]</span>
                <span class="value">INFLOW: <span class="rand-val" data-base="1452.3" data-noise="50">1452.3</span> BTC</span>
            </div>
            <div class="item">
                ⚡ Network Latency <span class="blue-text">[Exchange API]</span>
                <span class="value"><span class="rand-val" data-base="12.4" data-noise="4">12.4</span> ms</span>
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
    app.run(host='0.0.0.0', port=5000, debug=False)
