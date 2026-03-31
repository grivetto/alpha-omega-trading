from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Nuvola Orbital Command</title>
    <style>
        :root {
            --neon-green: #0f0;
            --neon-blue: #0ff;
            --neon-red: #f00;
            --neon-purple: #b0f;
            --bg-color: #050505;
            --panel-bg: rgba(10, 20, 15, 0.8);
            --font-main: 'Courier New', Courier, monospace;
        }
        body {
            background-color: var(--bg-color);
            color: var(--neon-green);
            font-family: var(--font-main);
            margin: 0;
            padding: 20px;
            background-image: linear-gradient(rgba(0, 255, 0, 0.03) 1px, transparent 1px),
            linear-gradient(90deg, rgba(0, 255, 0, 0.03) 1px, transparent 1px);
            background-size: 20px 20px;
        }
        h1, h2, h3 {
            text-transform: uppercase;
            text-shadow: 0 0 5px currentColor, 0 0 10px currentColor;
            letter-spacing: 2px;
        }
        h1 { color: var(--neon-blue); text-align: center; border-bottom: 2px solid var(--neon-blue); padding-bottom: 10px; margin-bottom: 30px;}
        h2 { color: var(--neon-purple); border-bottom: 1px dashed var(--neon-purple); display: inline-block; padding-bottom: 5px;}
        
        .container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
        }
        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-green);
            box-shadow: 0 0 10px rgba(0, 255, 0, 0.2), inset 0 0 10px rgba(0, 255, 0, 0.1);
            padding: 20px;
            border-radius: 5px;
            position: relative;
            overflow: hidden;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: -100%; width: 50%; height: 100%;
            background: linear-gradient(to right, transparent, rgba(0,255,0,0.1), transparent);
            animation: scan 4s linear infinite;
        }
        @keyframes scan {
            100% { left: 200%; }
        }
        
        .status-indicator {
            display: inline-block;
            width: 10px; height: 10px;
            border-radius: 50%;
            background: var(--neon-green);
            box-shadow: 0 0 8px var(--neon-green);
            margin-right: 10px;
            animation: blink 1.5s infinite alternate;
        }
        @keyframes blink { 0% { opacity: 0.4; } 100% { opacity: 1; box-shadow: 0 0 15px currentColor; } }
        
        ul { list-style-type: none; padding: 0; }
        li { margin-bottom: 10px; padding: 10px; background: rgba(0,255,0,0.05); border-left: 3px solid var(--neon-green); }
        .red-indicator { background: var(--neon-red); box-shadow: 0 0 8px var(--neon-red); }
        .blue-indicator { background: var(--neon-blue); box-shadow: 0 0 8px var(--neon-blue); }
        
        .data-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
        .data-box { border: 1px solid rgba(0,255,255,0.3); padding: 10px; text-align: center; }
        .data-value { font-size: 1.5em; color: var(--neon-blue); text-shadow: 0 0 5px var(--neon-blue); margin-top: 5px;}
        
        .glitch { position: relative; }
    </style>
</head>
<body>
    <h1 class="glitch">🛰️ ORBITAL COMMAND // NUVOLA SYSTEM</h1>
    
    <div class="container">
        <!-- SQUADRE D'ASSALTO -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <ul>
                <li>
                    <span class="status-indicator"></span>
                    <strong>SQUADRA_ALPHA</strong> 🦅<br>
                    <small>Role: Scalper | Target: Binance</small>
                </li>
                <li>
                    <span class="status-indicator"></span>
                    <strong>SQUADRA_DELTA</strong> 🎯<br>
                    <small>Role: Order Flow | Status: Active Engagements</small>
                </li>
                <li>
                    <span class="status-indicator"></span>
                    <strong>SQUADRA_GAMMA</strong> ⚖️<br>
                    <small>Role: Pairs Trading | Target: Bitget</small>
                </li>
            </ul>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2>🛡️ PROTOCOLLO TRINITY</h2>
            <div style="margin-bottom: 15px; padding: 10px; border: 1px solid var(--neon-blue); background: rgba(0,255,255,0.1); text-align: center; font-weight: bold; color: var(--neon-blue); text-shadow: 0 0 5px var(--neon-blue);">
                ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
            </div>
            <ul>
                <li>
                    <span class="status-indicator blue-indicator"></span>
                    <strong>Lo Strozzino</strong> 💸<br>
                    <small>Funding Arb // Background Sync</small>
                </li>
                <li>
                    <span class="status-indicator blue-indicator"></span>
                    <strong>Il Contabile</strong> 🧮<br>
                    <small>DCA Engine // Accumulation Mode</small>
                </li>
                <li>
                    <span class="status-indicator blue-indicator"></span>
                    <strong>L'Angelo Custode</strong> 👼<br>
                    <small>MEV Arbitrum // Sentinel Mode</small>
                </li>
            </ul>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <h2>📊 METRICHE DI MERCATO</h2>
            <div class="data-grid">
                <div class="data-box">
                    <div>👁️ The Oracle (Binance Sentiment)</div>
                    <div class="data-value">BULL-87%</div>
                </div>
                <div class="data-box">
                    <div>🐋 Whale Tracker</div>
                    <div class="data-value">+12.4k BTC</div>
                </div>
                <div class="data-box">
                    <div>⚡ Network Latency</div>
                    <div class="data-value">12 ms</div>
                </div>
                <div class="data-box">
                    <div>🔥 Global Threat Level</div>
                    <div class="data-value" style="color:var(--neon-red); text-shadow: 0 0 5px var(--neon-red);">DEFCON 3</div>
                </div>
            </div>
        </div>
    </div>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
