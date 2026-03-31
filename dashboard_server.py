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
        :root {
            --bg-color: #050505;
            --neon-green: #0fa;
            --neon-blue: #0ff;
            --neon-pink: #f0f;
            --neon-red: #f03;
            --panel-bg: rgba(10, 20, 15, 0.8);
        }
        body {
            background-color: var(--bg-color);
            color: var(--neon-green);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 40px;
            overflow-x: hidden;
            background-image: linear-gradient(rgba(0, 255, 0, 0.03) 1px, transparent 1px),
            linear-gradient(90deg, rgba(0, 255, 0, 0.03) 1px, transparent 1px);
            background-size: 20px 20px;
        }
        h1, h2, h3 {
            text-transform: uppercase;
            text-shadow: 0 0 10px var(--neon-green);
            margin-bottom: 10px;
        }
        .header {
            text-align: center;
            border-bottom: 2px solid var(--neon-blue);
            padding-bottom: 20px;
            margin-bottom: 30px;
            box-shadow: 0 5px 15px rgba(0, 255, 255, 0.2);
            animation: pulse 2s infinite;
        }
        @keyframes pulse {
            0% { box-shadow: 0 5px 15px rgba(0, 255, 255, 0.1); }
            50% { box-shadow: 0 5px 25px rgba(0, 255, 255, 0.5); }
            100% { box-shadow: 0 5px 15px rgba(0, 255, 255, 0.1); }
        }
        .grid-container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 30px;
        }
        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-green);
            border-radius: 5px;
            padding: 20px;
            box-shadow: inset 0 0 15px rgba(0, 255, 170, 0.2);
            position: relative;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; height: 3px;
            background: var(--neon-green);
            box-shadow: 0 0 10px var(--neon-green);
        }
        .panel.blue { border-color: var(--neon-blue); color: var(--neon-blue); }
        .panel.blue::before { background: var(--neon-blue); box-shadow: 0 0 10px var(--neon-blue); }
        .panel.blue h2 { text-shadow: 0 0 10px var(--neon-blue); }
        
        .panel.pink { border-color: var(--neon-pink); color: var(--neon-pink); }
        .panel.pink::before { background: var(--neon-pink); box-shadow: 0 0 10px var(--neon-pink); }
        .panel.pink h2 { text-shadow: 0 0 10px var(--neon-pink); }

        .status {
            display: inline-block;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            background-color: var(--neon-green);
            box-shadow: 0 0 8px var(--neon-green);
            margin-right: 12px;
            animation: blink 1.5s infinite;
        }
        .status.offline { background-color: var(--neon-red); box-shadow: 0 0 8px var(--neon-red); }
        .status.warning { background-color: yellow; box-shadow: 0 0 8px yellow; }
        
        @keyframes blink {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.4; }
        }
        .data-row {
            display: flex;
            justify-content: space-between;
            border-bottom: 1px dashed rgba(255,255,255,0.2);
            padding: 8px 0;
            font-size: 1.1em;
        }
        .data-label { opacity: 0.9; }
        .data-value { font-weight: bold; }
        .glitch {
            position: relative;
            color: white;
            text-shadow: 0.05em 0 0 rgba(255,0,0,0.75), -0.025em -0.05em 0 rgba(0,255,0,0.75), 0.025em 0.05em 0 rgba(0,0,255,0.75);
            animation: glitch 500ms infinite;
        }
        @keyframes glitch {
            0% { text-shadow: 0.05em 0 0 rgba(255,0,0,0.75), -0.05em -0.025em 0 rgba(0,255,0,0.75), -0.025em 0.05em 0 rgba(0,0,255,0.75); }
            14% { text-shadow: 0.05em 0 0 rgba(255,0,0,0.75), -0.05em -0.025em 0 rgba(0,255,0,0.75), -0.025em 0.05em 0 rgba(0,0,255,0.75); }
            15% { text-shadow: -0.05em -0.025em 0 rgba(255,0,0,0.75), 0.025em 0.025em 0 rgba(0,255,0,0.75), -0.05em -0.05em 0 rgba(0,0,255,0.75); }
            49% { text-shadow: -0.05em -0.025em 0 rgba(255,0,0,0.75), 0.025em 0.025em 0 rgba(0,255,0,0.75), -0.05em -0.05em 0 rgba(0,0,255,0.75); }
            50% { text-shadow: 0.025em 0.05em 0 rgba(255,0,0,0.75), 0.05em 0 0 rgba(0,255,0,0.75), 0 -0.05em 0 rgba(0,0,255,0.75); }
            99% { text-shadow: 0.025em 0.05em 0 rgba(255,0,0,0.75), 0.05em 0 0 rgba(0,255,0,0.75), 0 -0.05em 0 rgba(0,0,255,0.75); }
            100% { text-shadow: -0.025em 0 0 rgba(255,0,0,0.75), -0.025em -0.025em 0 rgba(0,255,0,0.75), -0.025em -0.05em 0 rgba(0,0,255,0.75); }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🛰️ ORBITAL COMMAND 🛰️</h1>
        <p>NUVOLA QUANTITATIVE DASHBOARD v3.0 // SYSTEM: <span class="glitch">ONLINE</span></p>
        <h3 style="color: var(--neon-blue); text-shadow: 0 0 10px var(--neon-blue);">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</h3>
    </div>

    <div class="grid-container">
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <div class="data-row">
                <span class="data-label"><span class="status"></span>SQUADRA_ALPHA <small>(Binance Scalper)</small></span>
                <span class="data-value" id="alpha-val">ACTIVE | PnL: +2.4%</span>
            </div>
            <div class="data-row">
                <span class="data-label"><span class="status"></span>SQUADRA_DELTA <small>(Order Flow)</small></span>
                <span class="data-value">ACTIVE | VOL: High</span>
            </div>
            <div class="data-row">
                <span class="data-label"><span class="status"></span>SQUADRA_GAMMA <small>(Bitget Pairs)</small></span>
                <span class="data-value" id="gamma-val">ACTIVE | Spread: 0.12%</span>
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel blue">
            <h2>🛡️ PROTOCOLLO TRINITY</h2>
            <div class="data-row">
                <span class="data-label"><span class="status"></span>Lo Strozzino <small>(Funding Arb)</small></span>
                <span class="data-value" id="strozzino-val">ONLINE | APR: 18.5%</span>
            </div>
            <div class="data-row">
                <span class="data-label"><span class="status"></span>Il Contabile <small>(DCA)</small></span>
                <span class="data-value">ONLINE | Next Buy: 4h</span>
            </div>
            <div class="data-row">
                <span class="data-label"><span class="status"></span>L'Angelo Custode <small>(MEV Arb)</small></span>
                <span class="data-value" id="angelo-val">ONLINE | Tx Mined: 42</span>
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel pink">
            <h2>📊 METRICHE DI MERCATO</h2>
            <div class="data-row">
                <span class="data-label">👁️ The Oracle (Sentiment)</span>
                <span class="data-value glitch" style="font-size: 1.2em;">BULLISH (68/100)</span>
            </div>
            <div class="data-row">
                <span class="data-label">🐋 Whale Tracker</span>
                <span class="data-value">INFLOW +450 BTC</span>
            </div>
            <div class="data-row">
                <span class="data-label">⚡ Network Congestion</span>
                <span class="data-value" id="gwei-val">24 Gwei</span>
            </div>
        </div>
    </div>
    
    <script>
        // Simulate real-time quantitative dashboard action
        setInterval(() => {
            document.getElementById('alpha-val').innerText = `ACTIVE | PnL: +${(2.4 + (Math.random() - 0.5) * 0.4).toFixed(2)}%`;
            document.getElementById('gamma-val').innerText = `ACTIVE | Spread: ${(0.12 + (Math.random() - 0.5) * 0.05).toFixed(3)}%`;
            if(Math.random() > 0.8) {
                let txs = parseInt(document.getElementById('angelo-val').innerText.split(': ')[1]);
                document.getElementById('angelo-val').innerText = `ONLINE | Tx Mined: ${txs + 1}`;
            }
            if(Math.random() > 0.7) {
                document.getElementById('gwei-val').innerText = `${Math.floor(20 + Math.random() * 15)} Gwei`;
            }
        }, 1500);
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
