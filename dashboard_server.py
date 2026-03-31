import os
from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ORBITAL COMMAND - Nuvola Dashboard</title>
    <style>
        :root {
            --bg-color: #050505;
            --panel-bg: rgba(10, 20, 15, 0.85);
            --neon-green: #00ff41;
            --neon-blue: #00d2ff;
            --neon-purple: #b100e8;
            --neon-red: #ff003c;
            --text-main: #e0e0e0;
            --border-color: #333;
        }

        body {
            background-color: var(--bg-color);
            color: var(--text-main);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            background-image: 
                linear-gradient(rgba(0, 255, 65, 0.05) 1px, transparent 1px),
                linear-gradient(90deg, rgba(0, 255, 65, 0.05) 1px, transparent 1px);
            background-size: 30px 30px;
            overflow-x: hidden;
        }

        h1 {
            color: var(--neon-green);
            text-align: center;
            text-shadow: 0 0 10px var(--neon-green), 0 0 20px var(--neon-green);
            letter-spacing: 5px;
            margin-bottom: 30px;
            font-size: 2.5em;
            text-transform: uppercase;
        }

        h1 span {
            color: var(--neon-blue);
            text-shadow: 0 0 10px var(--neon-blue);
        }

        .container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
            max-width: 1400px;
            margin: 0 auto;
        }

        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-blue);
            border-radius: 5px;
            padding: 20px;
            box-shadow: 0 0 15px rgba(0, 210, 255, 0.2) inset, 0 0 10px rgba(0, 210, 255, 0.4);
            position: relative;
            overflow: hidden;
        }

        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; width: 100%; height: 2px;
            background: var(--neon-blue);
            box-shadow: 0 0 10px var(--neon-blue);
        }

        .panel-hft {
            border-color: var(--neon-red);
            box-shadow: 0 0 15px rgba(255, 0, 60, 0.2) inset, 0 0 10px rgba(255, 0, 60, 0.4);
        }
        .panel-hft::before { background: var(--neon-red); box-shadow: 0 0 10px var(--neon-red); }

        .panel-trinity {
            border-color: var(--neon-purple);
            box-shadow: 0 0 15px rgba(177, 0, 232, 0.2) inset, 0 0 10px rgba(177, 0, 232, 0.4);
        }
        .panel-trinity::before { background: var(--neon-purple); box-shadow: 0 0 10px var(--neon-purple); }

        h2 {
            margin-top: 0;
            font-size: 1.3em;
            letter-spacing: 2px;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 10px;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .panel-hft h2 { color: var(--neon-red); text-shadow: 0 0 8px var(--neon-red); }
        .panel-trinity h2 { color: var(--neon-purple); text-shadow: 0 0 8px var(--neon-purple); }
        .panel-market h2 { color: var(--neon-blue); text-shadow: 0 0 8px var(--neon-blue); }

        ul { list-style: none; padding: 0; margin: 0; }
        li {
            padding: 12px 0;
            border-bottom: 1px solid rgba(255,255,255,0.05);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        li:last-child { border-bottom: none; }

        .status-badge {
            padding: 4px 8px;
            border-radius: 3px;
            font-size: 0.85em;
            font-weight: bold;
            animation: pulse 2s infinite;
        }

        .status-online { background: rgba(0, 255, 65, 0.2); color: var(--neon-green); border: 1px solid var(--neon-green); }
        .status-active { background: rgba(255, 0, 60, 0.2); color: var(--neon-red); border: 1px solid var(--neon-red); animation: pulse-fast 1s infinite; }
        .status-bg { background: rgba(177, 0, 232, 0.2); color: var(--neon-purple); border: 1px solid var(--neon-purple); }

        @keyframes pulse {
            0% { box-shadow: 0 0 0 0 rgba(0, 255, 65, 0.4); }
            70% { box-shadow: 0 0 0 5px rgba(0, 255, 65, 0); }
            100% { box-shadow: 0 0 0 0 rgba(0, 255, 65, 0); }
        }

        @keyframes pulse-fast {
            0% { box-shadow: 0 0 0 0 rgba(255, 0, 60, 0.5); }
            50% { box-shadow: 0 0 0 8px rgba(255, 0, 60, 0); }
            100% { box-shadow: 0 0 0 0 rgba(255, 0, 60, 0); }
        }

        .data-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
            margin-top: 15px;
        }
        .data-box {
            background: rgba(0,0,0,0.5);
            border: 1px solid #333;
            padding: 10px;
            text-align: center;
            border-radius: 4px;
        }
        .data-value {
            display: block;
            font-size: 1.5em;
            color: var(--neon-green);
            margin-top: 5px;
            font-weight: bold;
            text-shadow: 0 0 5px var(--neon-green);
        }

        .scanline {
            width: 100%;
            height: 100px;
            background: linear-gradient(0deg, rgba(0,0,0,0) 0%, rgba(0,255,65,0.1) 50%, rgba(0,0,0,0) 100%);
            opacity: 0.1;
            position: fixed;
            bottom: 100%;
            pointer-events: none;
            animation: scanline 8s linear infinite;
        }

        @keyframes scanline {
            0% { bottom: 100%; }
            100% { bottom: -100px; }
        }

        .name { font-weight: bold; letter-spacing: 1px; }
        .desc { font-size: 0.8em; color: #888; display: block; margin-top: 4px; }
        
        .sys-info {
            text-align: center;
            margin-top: 40px;
            color: #555;
            font-size: 0.9em;
        }
    </style>
</head>
<body>
    <div class="scanline"></div>
    
    <h1>🛰️ ORBITAL <span>COMMAND</span></h1>

    <div style="text-align: center; margin-bottom: 30px;">
        <span style="font-weight: bold; color: var(--neon-purple); border: 1px solid var(--neon-purple); padding: 10px 20px; display: inline-block; background: rgba(177, 0, 232, 0.1); border-radius: 5px; text-shadow: 0 0 5px var(--neon-purple); box-shadow: 0 0 10px rgba(177, 0, 232, 0.3);">
            ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
        </span>
    </div>

    <div class="container">
        
        <!-- SQUADRE D'ASSALTO -->
        <div class="panel panel-hft">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <ul>
                <li>
                    <div>
                        <span class="name">SQUADRA_ALPHA</span>
                        <span class="desc">Scalper su Binance - M1 TF</span>
                    </div>
                    <span class="status-badge status-active">ENGAGED</span>
                </li>
                <li>
                    <div>
                        <span class="name">SQUADRA_DELTA</span>
                        <span class="desc">Order Flow Imbalance</span>
                    </div>
                    <span class="status-badge status-active">ENGAGED</span>
                </li>
                <li>
                    <div>
                        <span class="name">SQUADRA_GAMMA</span>
                        <span class="desc">Pairs Trading su Bitget</span>
                    </div>
                    <span class="status-badge status-online">STANDBY</span>
                </li>
            </ul>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel panel-trinity">
            <h2>👁️ PROTOCOLLO TRINITY</h2>
            <ul>
                <li>
                    <div>
                        <span class="name">Lo Strozzino</span>
                        <span class="desc">Funding Rate Arbitrage (Perp/Spot)</span>
                    </div>
                    <span class="status-badge status-bg">BACKGROUND</span>
                </li>
                <li>
                    <div>
                        <span class="name">Il Contabile</span>
                        <span class="desc">DCA Accumulation Protocol</span>
                    </div>
                    <span class="status-badge status-bg">BACKGROUND</span>
                </li>
                <li>
                    <div>
                        <span class="name">L'Angelo Custode</span>
                        <span class="desc">MEV Arbitrum Mempool Sniper</span>
                    </div>
                    <span class="status-badge status-bg">BACKGROUND</span>
                </li>
            </ul>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel panel-market">
            <h2>📡 METRICHE DI MERCATO</h2>
            <div class="data-grid">
                <div class="data-box">
                    <span class="desc">The Oracle (Sentiment)</span>
                    <span class="data-value">BULLISH</span>
                </div>
                <div class="data-box">
                    <span class="desc">Whale Tracker (Inflow)</span>
                    <span class="data-value">+$42.5M</span>
                </div>
                <div class="data-box">
                    <span class="desc">Binance Volatility Index</span>
                    <span class="data-value">HIGH</span>
                </div>
                <div class="data-box">
                    <span class="desc">Global Liquidity Pool</span>
                    <span class="data-value">NOMINAL</span>
                </div>
            </div>
            <div style="margin-top: 15px; font-size: 0.85em; color: #777;">
                [+] Connessione socket dati criptata... STABILE<br>
                [+] Aggiornamento feed quantitativo... 14ms
            </div>
        </div>

    </div>

    <div class="sys-info">
        SYS_VER: O.C. v2.4.9-cyb | TERMINAL_ID: NUVOLA-99 | UPLINK: SECURE
    </div>

</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
