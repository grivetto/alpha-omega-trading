import os
from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ORBITAL COMMAND - Nuvola Terminal</title>
    <style>
        :root {
            --neon-green: #0f0;
            --neon-blue: #0ff;
            --neon-red: #f00;
            --neon-purple: #b026ff;
            --bg-color: #050505;
            --panel-bg: rgba(10, 15, 20, 0.85);
        }
        
        body {
            background-color: var(--bg-color);
            color: var(--neon-green);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            overflow-x: hidden;
            background-image: 
                linear-gradient(rgba(0, 255, 0, 0.03) 1px, transparent 1px),
                linear-gradient(90deg, rgba(0, 255, 0, 0.03) 1px, transparent 1px);
            background-size: 20px 20px;
        }

        h1, h2, h3 {
            text-transform: uppercase;
            text-shadow: 0 0 10px currentColor;
            margin-top: 0;
        }
        
        h1 {
            color: var(--neon-blue);
            text-align: center;
            font-size: 2.5em;
            letter-spacing: 5px;
            border-bottom: 2px solid var(--neon-blue);
            padding-bottom: 15px;
            animation: pulse 2s infinite;
        }

        .container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
            margin-top: 30px;
        }

        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-green);
            border-radius: 5px;
            padding: 20px;
            box-shadow: 0 0 15px rgba(0, 255, 0, 0.1) inset;
            position: relative;
        }

        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0;
            height: 2px;
            background: var(--neon-green);
            box-shadow: 0 0 10px var(--neon-green);
        }
        
        .panel.blue { border-color: var(--neon-blue); color: var(--neon-blue); }
        .panel.blue::before { background: var(--neon-blue); box-shadow: 0 0 10px var(--neon-blue); }
        
        .panel.red { border-color: var(--neon-red); color: var(--neon-red); }
        .panel.red::before { background: var(--neon-red); box-shadow: 0 0 10px var(--neon-red); }
        
        .panel.purple { border-color: var(--neon-purple); color: var(--neon-purple); }
        .panel.purple::before { background: var(--neon-purple); box-shadow: 0 0 10px var(--neon-purple); }

        ul {
            list-style-type: none;
            padding: 0;
        }

        li {
            margin-bottom: 10px;
            display: flex;
            align-items: center;
        }

        .status {
            display: inline-block;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            margin-right: 10px;
            background-color: var(--neon-green);
            box-shadow: 0 0 8px var(--neon-green);
            animation: blink 1.5s infinite;
        }

        .status.offline {
            background-color: var(--neon-red);
            box-shadow: 0 0 8px var(--neon-red);
            animation: none;
        }

        .status.standby {
            background-color: #ff0;
            box-shadow: 0 0 8px #ff0;
        }

        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
        }

        th, td {
            border: 1px solid rgba(0, 255, 0, 0.3);
            padding: 8px;
            text-align: left;
        }

        th {
            background: rgba(0, 255, 0, 0.1);
        }

        .blue table th, .blue table td { border-color: rgba(0, 255, 255, 0.3); }
        .blue table th { background: rgba(0, 255, 255, 0.1); }

        .scanline {
            width: 100%;
            height: 100px;
            z-index: 10;
            position: absolute;
            pointer-events: none;
            background: linear-gradient(0deg, rgba(0,0,0,0) 0%, rgba(0,255,0,0.1) 50%, rgba(0,0,0,0) 100%);
            opacity: 0.1;
            animation: scan 6s linear infinite;
        }

        @keyframes pulse {
            0% { text-shadow: 0 0 5px var(--neon-blue); }
            50% { text-shadow: 0 0 20px var(--neon-blue), 0 0 30px var(--neon-blue); }
            100% { text-shadow: 0 0 5px var(--neon-blue); }
        }

        @keyframes blink {
            0% { opacity: 1; }
            50% { opacity: 0.4; }
            100% { opacity: 1; }
        }

        @keyframes scan {
            0% { top: -100px; }
            100% { top: 100%; }
        }

        .glitch-wrapper {
            position: relative;
        }
    </style>
</head>
<body>
    <div class="scanline"></div>
    <div class="glitch-wrapper">
        <h1>🛰️ ORBITAL COMMAND 🛰️</h1>
    </div>

    <div class="container">
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel red">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <ul>
                <li><span class="status"></span> <strong>SQUADRA_ALPHA</strong> 🐺 | Scalper (Binance) - [TARGET: BTC/USDT]</li>
                <li><span class="status standby"></span> <strong>SQUADRA_DELTA</strong> 🦅 | Order Flow - [AWAITING VOLATILITY]</li>
                <li><span class="status"></span> <strong>SQUADRA_GAMMA</strong> 🦂 | Pairs Trading (Bitget) - [HEDGE: ACTIVE]</li>
            </ul>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel purple">
            <h2>🔮 PROTOCOLLO TRINITY</h2>
            <p style="color: var(--neon-purple); text-shadow: 0 0 5px var(--neon-purple); font-weight: bold; margin-bottom: 15px;">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</p>
            <ul>
                <li><span class="status"></span> <strong>Lo Strozzino</strong> 🕴️ | Funding Arb - ONLINE</li>
                <li><span class="status"></span> <strong>Il Contabile</strong> 🧮 | DCA Engine - ONLINE</li>
                <li><span class="status"></span> <strong>L'Angelo Custode</strong> 🛡️ | MEV Protection (Arbitrum) - ONLINE</li>
            </ul>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel blue">
            <h2>📊 THE ORACLE (METRICHE)</h2>
            <table>
                <tr>
                    <th>Sensore</th>
                    <th>Stato / Valore</th>
                </tr>
                <tr>
                    <td>Binance Sentiment</td>
                    <td><span style="color: #0f0;">BULLISH (78%)</span></td>
                </tr>
                <tr>
                    <td>Whale Tracker</td>
                    <td>🚨 +4,500 BTC -> Coinbase</td>
                </tr>
                <tr>
                    <td>Fear & Greed</td>
                    <td>65 (Greed)</td>
                </tr>
            </table>
        </div>
    </div>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
