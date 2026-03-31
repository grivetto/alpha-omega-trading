from flask import Flask, render_template_string
import os

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ORBITAL COMMAND // Nuvola</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');

        :root {
            --neon-green: #39ff14;
            --neon-blue: #00f3ff;
            --neon-pink: #ff00ff;
            --neon-red: #ff073a;
            --bg-color: #020202;
            --panel-bg: rgba(10, 10, 10, 0.85);
            --border-glow: 0 0 10px rgba(57, 255, 20, 0.5);
        }

        body {
            background-color: var(--bg-color);
            color: var(--neon-green);
            font-family: 'Share Tech Mono', monospace;
            margin: 0;
            padding: 20px;
            overflow-x: hidden;
            background-image: 
                linear-gradient(rgba(0, 255, 0, 0.03) 1px, transparent 1px),
                linear-gradient(90deg, rgba(0, 255, 0, 0.03) 1px, transparent 1px);
            background-size: 20px 20px;
        }

        /* Scanline effect */
        body::before {
            content: " ";
            display: block;
            position: absolute;
            top: 0;
            left: 0;
            bottom: 0;
            right: 0;
            background: linear-gradient(rgba(18, 16, 16, 0) 50%, rgba(0, 0, 0, 0.25) 50%), linear-gradient(90deg, rgba(255, 0, 0, 0.06), rgba(0, 255, 0, 0.02), rgba(0, 0, 255, 0.06));
            z-index: 999;
            background-size: 100% 2px, 3px 100%;
            pointer-events: none;
            opacity: 0.3;
        }

        h1 {
            text-align: center;
            font-size: 2.5em;
            text-transform: uppercase;
            letter-spacing: 5px;
            text-shadow: 0 0 15px var(--neon-green), 0 0 25px var(--neon-green);
            margin-bottom: 30px;
            border-bottom: 2px solid var(--neon-green);
            padding-bottom: 10px;
        }

        .grid-container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 25px;
            max-width: 1400px;
            margin: 0 auto;
        }

        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-green);
            border-left: 5px solid var(--neon-green);
            padding: 20px;
            box-shadow: var(--border-glow);
            position: relative;
            transition: all 0.3s ease;
        }

        .panel:hover {
            box-shadow: 0 0 20px rgba(57, 255, 20, 0.8);
            transform: translateY(-2px);
        }

        .panel-header {
            font-size: 1.5em;
            margin-bottom: 15px;
            color: #fff;
            text-shadow: 0 0 10px #fff;
            text-transform: uppercase;
            display: flex;
            align-items: center;
            gap: 10px;
            border-bottom: 1px dashed rgba(57, 255, 20, 0.5);
            padding-bottom: 10px;
        }

        .panel-header.blue { color: var(--neon-blue); text-shadow: 0 0 10px var(--neon-blue); border-color: var(--neon-blue); }
        .panel-header.pink { color: var(--neon-pink); text-shadow: 0 0 10px var(--neon-pink); border-color: var(--neon-pink); }

        ul {
            list-style-type: none;
            padding: 0;
            margin: 0;
        }

        li {
            margin-bottom: 15px;
            padding: 10px;
            background: rgba(0, 255, 0, 0.05);
            border-left: 2px solid var(--neon-green);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .status {
            font-weight: bold;
            padding: 2px 8px;
            border-radius: 3px;
            font-size: 0.9em;
            letter-spacing: 1px;
            animation: pulse 2s infinite;
        }

        .status.active { background: rgba(57, 255, 20, 0.2); color: var(--neon-green); box-shadow: 0 0 10px var(--neon-green); }
        .status.bg { background: rgba(0, 243, 255, 0.2); color: var(--neon-blue); box-shadow: 0 0 10px var(--neon-blue); }
        .status.standby { background: rgba(255, 255, 255, 0.1); color: #ccc; animation: none; }
        .status.alert { background: rgba(255, 7, 58, 0.2); color: var(--neon-red); box-shadow: 0 0 10px var(--neon-red); animation: fast-pulse 1s infinite; }

        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.6; }
            100% { opacity: 1; }
        }

        @keyframes fast-pulse {
            0% { opacity: 1; }
            50% { opacity: 0.3; }
            100% { opacity: 1; }
        }

        .metrics-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
        }

        .metric-box {
            background: rgba(0, 0, 0, 0.5);
            border: 1px solid rgba(255, 0, 255, 0.3);
            padding: 15px;
            text-align: center;
        }

        .metric-value {
            font-size: 2em;
            color: var(--neon-pink);
            text-shadow: 0 0 10px var(--neon-pink);
            margin: 10px 0;
        }

        /* Glitch effect on title */
        .glitch {
            position: relative;
        }
        .glitch::before, .glitch::after {
            content: "🛰️ ORBITAL COMMAND // NUVOLA";
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: var(--bg-color);
        }
        .glitch::before {
            left: 2px;
            text-shadow: -2px 0 red;
            clip: rect(24px, 550px, 90px, 0);
            animation: glitch-anim-2 3s infinite linear alternate-reverse;
        }
        .glitch::after {
            left: -2px;
            text-shadow: -2px 0 blue;
            clip: rect(85px, 550px, 140px, 0);
            animation: glitch-anim 2.5s infinite linear alternate-reverse;
        }
        @keyframes glitch-anim { 0% { clip: rect(10px, 9999px, 86px, 0); } 100% { clip: rect(31px, 9999px, 81px, 0); } }
        @keyframes glitch-anim-2 { 0% { clip: rect(65px, 9999px, 100px, 0); } 100% { clip: rect(2px, 9999px, 50px, 0); } }
    </style>
</head>
<body>

    <h1 class="glitch">🛰️ ORBITAL COMMAND // NUVOLA</h1>

    <div class="grid-container">
        
        <!-- SQUADRE D'ASSALTO -->
        <div class="panel" style="border-left-color: var(--neon-red);">
            <div class="panel-header" style="color: var(--neon-red); border-color: var(--neon-red); text-shadow: 0 0 10px var(--neon-red);">
                ⚔️ SQUADRE D'ASSALTO (HFT)
            </div>
            <ul>
                <li>
                    <div>
                        <strong>🐺 SQUADRA_ALPHA</strong><br>
                        <span style="font-size: 0.8em; color: #888;">Binance Scalper // Latency: 12ms</span>
                    </div>
                    <span class="status active">ENGAGED</span>
                </li>
                <li>
                    <div>
                        <strong>🌊 SQUADRA_DELTA</strong><br>
                        <span style="font-size: 0.8em; color: #888;">Order Flow Analysis // Volatility: HIGH</span>
                    </div>
                    <span class="status active">ENGAGED</span>
                </li>
                <li>
                    <div>
                        <strong>⚖️ SQUADRA_GAMMA</strong><br>
                        <span style="font-size: 0.8em; color: #888;">Pairs Trading Bitget // Awaiting Diff</span>
                    </div>
                    <span class="status standby">STANDBY</span>
                </li>
            </ul>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel" style="border-left-color: var(--neon-blue);">
            <div class="panel-header blue">
                🛡️ PROTOCOLLO TRINITY
            </div>
            <div style="text-align: center; margin-bottom: 15px; padding: 10px; border: 1px solid var(--neon-green); background: rgba(57, 255, 20, 0.1); color: var(--neon-green); text-shadow: 0 0 5px var(--neon-green); font-weight: bold; letter-spacing: 1px; border-radius: 4px;">
                ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
            </div>
            <ul>
                <li style="border-left-color: var(--neon-blue); background: rgba(0, 243, 255, 0.05);">
                    <div>
                        <strong>🦇 Lo Strozzino</strong><br>
                        <span style="font-size: 0.8em; color: #888;">Funding Arb // Yield: +14.2% APY</span>
                    </div>
                    <span class="status bg">BACKGROUND_ON</span>
                </li>
                <li style="border-left-color: var(--neon-blue); background: rgba(0, 243, 255, 0.05);">
                    <div>
                        <strong>🧮 Il Contabile</strong><br>
                        <span style="font-size: 0.8em; color: #888;">DCA Matrix // Accumulation Phase</span>
                    </div>
                    <span class="status bg">BACKGROUND_ON</span>
                </li>
                <li style="border-left-color: var(--neon-blue); background: rgba(0, 243, 255, 0.05);">
                    <div>
                        <strong>👼 L'Angelo Custode</strong><br>
                        <span style="font-size: 0.8em; color: #888;">MEV Arbitrum Protection // Slippage: 0.1%</span>
                    </div>
                    <span class="status bg">BACKGROUND_ON</span>
                </li>
            </ul>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel" style="grid-column: 1 / -1; border-left-color: var(--neon-pink);">
            <div class="panel-header pink">
                📡 METRICHE DI MERCATO & SENSORI QUANTITATIVI
            </div>
            <div class="metrics-grid">
                <div class="metric-box">
                    <div style="font-size: 1.2em; color: #fff;">👁️ THE ORACLE</div>
                    <div style="font-size: 0.9em; color: #888;">Binance Sentiment Analysis</div>
                    <div class="metric-value" style="color: var(--neon-red); text-shadow: 0 0 10px var(--neon-red);">EXTREME GREED</div>
                    <div style="display: flex; justify-content: space-between; margin-top: 15px; font-size: 0.9em;">
                        <span>Long/Short: <span style="color: var(--neon-green)">1.84</span></span>
                        <span>Fear Index: <span style="color: var(--neon-red)">89/100</span></span>
                    </div>
                </div>
                <div class="metric-box">
                    <div style="font-size: 1.2em; color: #fff;">🐋 WHALE TRACKER</div>
                    <div style="font-size: 0.9em; color: #888;">On-Chain Anomaly Detection</div>
                    <div class="metric-value" style="color: var(--neon-blue); text-shadow: 0 0 10px var(--neon-blue); font-size: 1.5em; padding-top: 10px;">
                        ALERT_LEVEL: YELLOW
                    </div>
                    <div style="margin-top: 15px; font-size: 0.9em; color: #ccc;">
                        Last Ping: <span style="color: var(--neon-pink)">10,450 BTC</span> -> Binance Deposit
                        <br>
                        <span class="status alert" style="display: inline-block; margin-top: 5px; font-size: 0.8em;">MONITORING IMPACT</span>
                    </div>
                </div>
            </div>
        </div>

    </div>

    <script>
        // Simple script to make random data flicker for effect
        setInterval(() => {
            const lsRatio = (1.80 + Math.random() * 0.1).toFixed(2);
            document.querySelector('.metric-box span span').innerText = lsRatio;
        }, 3000);
    </script>
</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    # Run server on all interfaces, port 5050 (or similar)
    # Using 5000 as default
    app.run(host='0.0.0.0', port=5000, debug=False)
