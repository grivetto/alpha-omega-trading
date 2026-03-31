from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Orbital Command | Nuvola</title>
    <style>
        :root {
            --neon-blue: #0ff;
            --neon-purple: #b026ff;
            --neon-green: #39ff14;
            --neon-red: #ff2a2a;
            --bg-color: #050505;
            --panel-bg: #111;
            --glow: 0 0 10px;
        }
        body {
            background-color: var(--bg-color);
            color: var(--neon-blue);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            text-transform: uppercase;
            overflow-x: hidden;
            background-image: 
                linear-gradient(rgba(0, 255, 255, 0.03) 1px, transparent 1px),
                linear-gradient(90deg, rgba(0, 255, 255, 0.03) 1px, transparent 1px);
            background-size: 20px 20px;
        }
        h1, h2, h3 {
            text-align: center;
            text-shadow: var(--glow) var(--neon-blue);
            letter-spacing: 2px;
            margin-bottom: 5px;
        }
        .header {
            border-bottom: 2px solid var(--neon-blue);
            padding-bottom: 10px;
            margin-bottom: 30px;
            animation: flicker 3s infinite alternate;
        }
        .container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
        }
        .panel {
            background-color: rgba(17, 17, 17, 0.8);
            border: 1px solid var(--neon-purple);
            border-radius: 5px;
            padding: 15px;
            box-shadow: var(--glow) var(--neon-purple);
            transition: all 0.3s ease;
            position: relative;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; height: 2px;
            background: linear-gradient(90deg, transparent, var(--neon-purple), transparent);
        }
        .panel:hover {
            box-shadow: 0 0 25px var(--neon-green);
            border-color: var(--neon-green);
        }
        .panel:hover h2 {
            text-shadow: var(--glow) var(--neon-green);
            color: var(--neon-green);
        }
        .status {
            float: right;
            color: var(--neon-green);
            text-shadow: 0 0 5px var(--neon-green);
            animation: pulse 1.5s infinite;
        }
        .status.offline {
            color: var(--neon-red);
            text-shadow: 0 0 5px var(--neon-red);
        }
        .metric {
            display: flex;
            justify-content: space-between;
            margin: 15px 0;
            border-bottom: 1px dashed #333;
            padding-bottom: 5px;
            font-size: 0.9em;
        }
        .metric span.label {
            display: flex;
            align-items: center;
        }
        .emoji { margin-right: 10px; font-size: 1.2em; }
        
        @keyframes pulse {
            0% { opacity: 0.7; }
            50% { opacity: 1; text-shadow: 0 0 15px var(--neon-green); }
            100% { opacity: 0.7; }
        }
        @keyframes flicker {
            0%, 19%, 21%, 23%, 25%, 54%, 56%, 100% { opacity: 1; text-shadow: var(--glow) var(--neon-blue); }
            20%, 24%, 55% { opacity: 0.4; text-shadow: none; }
        }
        
        .glitch-text {
            position: relative;
            font-size: 2.5em;
            font-weight: bold;
        }
        .progress-bar {
            width: 100%;
            background-color: #333;
            height: 4px;
            margin-top: 5px;
            border-radius: 2px;
            overflow: hidden;
        }
        .progress-fill {
            height: 100%;
            background-color: var(--neon-purple);
            width: 50%;
            box-shadow: 0 0 5px var(--neon-purple);
            animation: scan 2s infinite linear alternate;
        }
        @keyframes scan {
            0% { width: 10%; }
            100% { width: 90%; }
        }
    </style>
</head>
<body>
    <div class="header">
        <div class="glitch-text">🛰️ ORBITAL COMMAND 🛰️</div>
        <h3>NUVOLA SYSTEM CORE | STATUS: <span style="color:var(--neon-green)">ONLINE</span></h3>
        <h4 style="color: var(--neon-purple); text-shadow: var(--glow) var(--neon-purple); margin-top: 10px;">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</h4>
    </div>

    <div class="container">
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <h2 style="color: var(--neon-red); border-color: var(--neon-red);">⚔️ ASSAULT SQUADS (HFT)</h2>
            <div class="metric">
                <span class="label"><span class="emoji">🦅</span>SQUADRA_ALPHA (Binance Scalper)</span>
                <span class="status">ACTIVE [OP: 42]</span>
            </div>
            <div class="metric">
                <span class="label"><span class="emoji">🌊</span>SQUADRA_DELTA (Order Flow)</span>
                <span class="status">ACTIVE [VOL: 9.4M]</span>
            </div>
            <div class="metric">
                <span class="label"><span class="emoji">⚖️</span>SQUADRA_GAMMA (Bitget Pairs)</span>
                <span class="status">ACTIVE [SPR: 0.04%]</span>
            </div>
            <div class="progress-bar"><div class="progress-fill" style="background-color: var(--neon-red); box-shadow: 0 0 5px var(--neon-red);"></div></div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2 style="color: var(--neon-purple);">🔺 TRINITY PROTOCOL</h2>
            <div class="metric">
                <span class="label"><span class="emoji">🦈</span>Lo Strozzino (Funding Arb)</span>
                <span class="status">ONLINE [APR: 18.2%]</span>
            </div>
            <div class="metric">
                <span class="label"><span class="emoji">🧮</span>Il Contabile (DCA)</span>
                <span class="status">ONLINE [CYCLES: 14]</span>
            </div>
            <div class="metric">
                <span class="label"><span class="emoji">👼</span>L'Angelo Custode (Arbitrum MEV)</span>
                <span class="status">ONLINE [DEF: MAX]</span>
            </div>
            <div class="progress-bar"><div class="progress-fill"></div></div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <h2 style="color: var(--neon-blue);">📡 MARKET INTEL</h2>
            <div class="metric">
                <span class="label"><span class="emoji">👁️</span>The Oracle (Binance Sent)</span>
                <span style="color: #ff0; text-shadow: 0 0 5px #ff0;">BULLISH [72%]</span>
            </div>
            <div class="metric">
                <span class="label"><span class="emoji">🐳</span>Whale Tracker</span>
                <span style="color: var(--neon-red); text-shadow: 0 0 5px var(--neon-red); animation: pulse 1s infinite;">DETECTED [500 BTC]</span>
            </div>
            <div class="metric">
                <span class="label"><span class="emoji">⚡</span>Network Latency</span>
                <span class="status" id="latency">12ms</span>
            </div>
            <div class="progress-bar"><div class="progress-fill" style="background-color: var(--neon-blue); box-shadow: 0 0 5px var(--neon-blue); width: 100%; animation: none;"></div></div>
        </div>
    </div>
    
    <script>
        setInterval(() => {
            const latency = Math.floor(Math.random() * 8) + 8;
            document.getElementById('latency').innerText = latency + 'ms';
        }, 1500);
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
