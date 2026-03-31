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
    <title>ORBITAL COMMAND - NUVOLA DASHBOARD</title>
    <style>
        :root {
            --neon-blue: #0ff;
            --neon-pink: #f0f;
            --neon-green: #39ff14;
            --dark-bg: #0a0a0c;
            --panel-bg: rgba(10, 20, 30, 0.85);
        }
        body {
            background-color: var(--dark-bg);
            color: #fff;
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            background-image: 
                linear-gradient(rgba(0, 255, 255, 0.05) 1px, transparent 1px),
                linear-gradient(90deg, rgba(0, 255, 255, 0.05) 1px, transparent 1px);
            background-size: 20px 20px;
        }
        h1, h2, h3 {
            text-transform: uppercase;
            letter-spacing: 2px;
        }
        h1 {
            color: var(--neon-blue);
            text-shadow: 0 0 10px var(--neon-blue), 0 0 20px var(--neon-blue);
            text-align: center;
            border-bottom: 2px solid var(--neon-blue);
            padding-bottom: 10px;
        }
        .container {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            max-width: 1400px;
            margin: 0 auto;
        }
        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-blue);
            border-radius: 5px;
            padding: 20px;
            box-shadow: 0 0 15px rgba(0, 255, 255, 0.2) inset;
            position: relative;
            overflow: hidden;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; height: 2px;
            background: linear-gradient(90deg, transparent, var(--neon-blue), transparent);
            animation: scanline 2s linear infinite;
        }
        @keyframes scanline {
            0% { transform: translateX(-100%); }
            100% { transform: translateX(100%); }
        }
        .title-pink {
            color: var(--neon-pink);
            text-shadow: 0 0 8px var(--neon-pink);
            border-bottom: 1px dashed var(--neon-pink);
            padding-bottom: 5px;
        }
        .title-green {
            color: var(--neon-green);
            text-shadow: 0 0 8px var(--neon-green);
            border-bottom: 1px dashed var(--neon-green);
            padding-bottom: 5px;
        }
        .status-online {
            color: var(--neon-green);
            font-weight: bold;
            animation: blink 1.5s infinite;
        }
        .status-active {
            color: var(--neon-blue);
            font-weight: bold;
        }
        @keyframes blink {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        ul { list-style-type: none; padding: 0; }
        li {
            margin-bottom: 10px;
            padding: 10px;
            background: rgba(0, 0, 0, 0.5);
            border-left: 3px solid var(--neon-blue);
        }
        .squad-alpha { border-left-color: #ff3333; }
        .squad-delta { border-left-color: #33ff33; }
        .squad-gamma { border-left-color: #3333ff; }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
        }
        th, td {
            border: 1px solid rgba(0, 255, 255, 0.3);
            padding: 8px;
            text-align: left;
        }
        th { color: var(--neon-blue); }
        .data-value { color: var(--neon-green); font-family: monospace; }
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 10px;
        }
        .metric-box {
            background: rgba(0,0,0,0.6);
            border: 1px solid var(--neon-pink);
            padding: 15px;
            text-align: center;
        }
        .metric-box span { display: block; font-size: 1.5em; color: var(--neon-pink); text-shadow: 0 0 5px var(--neon-pink); }
    </style>
</head>
<body>
    <h1>🌐 ORBITAL COMMAND 🌐</h1>
    <p style="text-align: center; color: #888;">[ SYSTEM ONLINE - UPLINK SECURE - NUVOLA QUANTITATIVE ENGINE ]</p>
    <div style="text-align: center; margin-bottom: 20px; padding: 10px; background: rgba(0, 255, 0, 0.1); border: 1px solid var(--neon-green); border-radius: 5px; color: var(--neon-green); font-weight: bold; text-shadow: 0 0 5px var(--neon-green);">
        ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
    </div>
    
    <div class="container">
        <!-- SEZIONE 1: SQUADRE D'ASSALTO -->
        <div class="panel">
            <h2 class="title-pink">⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <ul>
                <li class="squad-alpha">
                    <strong>🐺 SQUADRA_ALPHA</strong> (Scalper su Binance)<br>
                    Stato: <span class="status-active">INGAGGIATO</span> | Latenza: 12ms | PnL: +2.4%
                </li>
                <li class="squad-delta">
                    <strong>🦅 SQUADRA_DELTA</strong> (Order Flow)<br>
                    Stato: <span class="status-active">ATTENDIBILE</span> | Latenza: 18ms | Order Imbalance: Bullish
                </li>
                <li class="squad-gamma">
                    <strong>🐍 SQUADRA_GAMMA</strong> (Pairs Trading su Bitget)<br>
                    Stato: <span class="status-active">ALLINEATO</span> | Latenza: 25ms | Spread Z-Score: 1.8
                </li>
            </ul>
        </div>

        <!-- SEZIONE 2: PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2 class="title-green">🔺 PROTOCOLLO TRINITY</h2>
            <p>Sottosistemi operativi in background:</p>
            <ul>
                <li>
                    <strong>🕴️ Lo Strozzino</strong> (Funding Arb)<br>
                    Stato: <span class="status-online">ONLINE</span> | APR Est. 18.5%
                </li>
                <li>
                    <strong>🧮 Il Contabile</strong> (DCA Accumulator)<br>
                    Stato: <span class="status-online">ONLINE</span> | Prossimo acquisto in: 04:12:33
                </li>
                <li>
                    <strong>👼 L'Angelo Custode</strong> (MEV Arbitrum)<br>
                    Stato: <span class="status-online">ONLINE</span> | Flashbots RPC connesso | TX protette: 142
                </li>
            </ul>
        </div>

        <!-- SEZIONE 3: METRICHE DI MERCATO -->
        <div class="panel" style="grid-column: 1 / -1;">
            <h2 style="color: #fff; border-bottom: 1px solid #fff;">📊 DATI TATTICI & METRICHE</h2>
            <div class="metrics-grid">
                <div class="metric-box" style="border-color: var(--neon-blue);">
                    👁️ THE ORACLE (Sentiment)
                    <span style="color: var(--neon-blue); text-shadow: 0 0 5px var(--neon-blue);">BULLISH (78/100)</span>
                </div>
                <div class="metric-box" style="border-color: var(--neon-green);">
                    🐳 WHALE TRACKER
                    <span style="color: var(--neon-green); text-shadow: 0 0 5px var(--neon-green);">+1,450 BTC INFLOW</span>
                </div>
                <div class="metric-box">
                    ⚡ LIQUIDITY MAP
                    <span>VOLATILE</span>
                </div>
                <div class="metric-box" style="border-color: #ff3333;">
                    🔥 GLOBAL RISK
                    <span style="color: #ff3333; text-shadow: 0 0 5px #ff3333;">DEFCON 3</span>
                </div>
            </div>
            
            <h3 style="margin-top: 20px; font-size: 1em; color: var(--neon-blue);">LIVE ORDER BOOK (SIMULATED)</h3>
            <table>
                <tr><th>Coppia</th><th>Bid</th><th>Ask</th><th>Spread</th></tr>
                <tr><td>BTC/USDT</td><td class="data-value">64,210.50</td><td class="data-value">64,210.60</td><td>0.10</td></tr>
                <tr><td>ETH/USDT</td><td class="data-value">3,450.25</td><td class="data-value">3,450.30</td><td>0.05</td></tr>
                <tr><td>SOL/USDT</td><td class="data-value">145.80</td><td class="data-value">145.82</td><td>0.02</td></tr>
            </table>
        </div>
    </div>

    <script>
        // Simulazione di aggiornamenti in tempo reale
        setInterval(() => {
            const values = document.querySelectorAll('.data-value');
            values.forEach(el => {
                let val = parseFloat(el.innerText.replace(',', ''));
                val += (Math.random() - 0.5) * 5;
                el.innerText = val.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2});
            });
        }, 2000);
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    # Esegue su 0.0.0.0 porta 5000 (o un'altra porta)
    app.run(host='0.0.0.0', port=5000)
