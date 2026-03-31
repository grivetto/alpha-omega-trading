import os
from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ORBITAL COMMAND // NUVOLA</title>
    <style>
        :root {
            --neon-green: #0f0;
            --neon-red: #f00;
            --neon-cyan: #0ff;
            --neon-purple: #f0f;
            --bg-color: #050505;
            --panel-bg: rgba(10, 20, 10, 0.8);
        }
        body {
            background-color: var(--bg-color);
            color: var(--neon-green);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            text-transform: uppercase;
            background-image: 
                linear-gradient(0deg, transparent 24%, rgba(0, 255, 0, .05) 25%, rgba(0, 255, 0, .05) 26%, transparent 27%, transparent 74%, rgba(0, 255, 0, .05) 75%, rgba(0, 255, 0, .05) 76%, transparent 77%, transparent), 
                linear-gradient(90deg, transparent 24%, rgba(0, 255, 0, .05) 25%, rgba(0, 255, 0, .05) 26%, transparent 27%, transparent 74%, rgba(0, 255, 0, .05) 75%, rgba(0, 255, 0, .05) 76%, transparent 77%, transparent);
            background-size: 50px 50px;
        }
        h1, h2, h3 {
            text-shadow: 0 0 5px var(--neon-green), 0 0 10px var(--neon-green);
            margin-top: 0;
            letter-spacing: 2px;
        }
        .header {
            text-align: center;
            border-bottom: 2px solid var(--neon-green);
            padding-bottom: 10px;
            margin-bottom: 20px;
            box-shadow: 0 10px 10px -10px var(--neon-green);
        }
        .container {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            max-width: 1200px;
            margin: 0 auto;
        }
        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-green);
            padding: 15px;
            box-shadow: inset 0 0 15px rgba(0, 255, 0, 0.2);
            position: relative;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; height: 2px;
            background: var(--neon-green);
            box-shadow: 0 0 10px var(--neon-green);
        }
        .status-online { color: var(--neon-cyan); text-shadow: 0 0 5px var(--neon-cyan); }
        .status-active { color: var(--neon-red); text-shadow: 0 0 8px var(--neon-red); animation: blink 1s infinite; }
        .status-idle { color: #ff0; text-shadow: 0 0 5px #ff0; }
        
        @keyframes blink { 
            0% { opacity: 1; } 
            50% { opacity: 0.3; } 
            100% { opacity: 1; } 
        }
        
        ul { list-style-type: none; padding: 0; }
        li { margin-bottom: 15px; border-bottom: 1px dashed rgba(0,255,0,0.3); padding-bottom: 10px; }
        
        .grid-data { 
            display: grid; 
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); 
            gap: 15px; 
            font-size: 0.9em; 
            margin-top: 15px;
        }
        .data-box { 
            border: 1px solid var(--neon-cyan); 
            padding: 15px; 
            text-align: center; 
            background: rgba(0, 255, 255, 0.05);
            box-shadow: inset 0 0 10px rgba(0, 255, 255, 0.1), 0 0 5px rgba(0, 255, 255, 0.2); 
        }
        .data-box strong {
            display: block;
            margin-bottom: 8px;
            font-size: 1.1em;
            color: var(--neon-cyan);
            text-shadow: 0 0 5px var(--neon-cyan);
        }
        .val {
            display: block;
            margin-top: 10px;
            font-size: 1.2em;
            font-weight: bold;
        }
        .glitch { animation: glitch 4s infinite; display: inline-block; }
        @keyframes glitch {
            0% { transform: translate(0) }
            2% { transform: translate(-2px, 2px) }
            4% { transform: translate(-2px, -2px) }
            6% { transform: translate(2px, 2px) }
            8% { transform: translate(2px, -2px) }
            10% { transform: translate(0) }
            100% { transform: translate(0) }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1 class="glitch">🛰️ ORBITAL COMMAND // NUVOLA_OS v9.4 🛰️</h1>
        <p>SISTEMA DI CONTROLLO QUANTITATIVO GLOBALE - ACCESSO AUTORIZZATO</p>
        <h3 style="color: var(--neon-cyan); text-shadow: 0 0 10px var(--neon-cyan); margin-top: 10px;">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</h3>
    </div>

    <div class="container">
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <ul>
                <li>
                    <strong>🐺 SQUADRA ALPHA</strong> [Scalping: Binance] <br>
                    <span class="status-active">▶ ENGAGED</span> <br> 
                    <small>Target: BTC/USDT | Freq: 120ms | WinRate: 64.2%</small>
                </li>
                <li>
                    <strong>⚡ SQUADRA DELTA</strong> [Order Flow] <br>
                    <span class="status-online">▶ STANDBY</span> <br> 
                    <small>Analisi Book: Attiva | Spoofing detection: ON</small>
                </li>
                <li>
                    <strong>🦂 SQUADRA GAMMA</strong> [Pairs Trading: Bitget] <br>
                    <span class="status-active">▶ ENGAGED</span> <br> 
                    <small>Spread ETH/SOL: 0.045 | Z-Score: 2.1 | Posizione: Inverted</small>
                </li>
            </ul>
        </div>

        <div class="panel">
            <h2>🛡️ PROTOCOLLO TRINITY</h2>
            <ul>
                <li>
                    <strong>🧛‍♂️ LO STROZZINO</strong> [Funding Arb] <br>
                    <span class="status-online">▶ ONLINE - BACKGROUND</span> <br> 
                    <small>Long Spot / Short Perp | Yield Corrente: +18.4% APY</small>
                </li>
                <li>
                    <strong>🧮 IL CONTABILE</strong> [Accumulo DCA] <br>
                    <span class="status-idle">▶ IDLE - WAITING SCHEDULE</span> <br> 
                    <small>Prossimo acquisto: 14:00 UTC | Asset Target: BTC, SOL</small>
                </li>
                <li>
                    <strong>👼 L'ANGELO CUSTODE</strong> [MEV: Arbitrum] <br>
                    <span class="status-online">▶ ONLINE - SCANNING</span> <br> 
                    <small>Mempool watcher attivo | Snipe gas: 0.05 Gwei | Sandwich: Off</small>
                </li>
            </ul>
        </div>

        <div class="panel" style="grid-column: 1 / -1;">
            <h2>📊 METRICHE DI MERCATO & INTEL</h2>
            <div class="grid-data">
                <div class="data-box">
                    <strong>👁️ THE ORACLE</strong>
                    Binance Sentiment Index<br>
                    <span class="val status-active">EXTREME GREED (88)</span>
                </div>
                <div class="data-box">
                    <strong>🐋 WHALE TRACKER</strong>
                    Inflow/Outflow 24h<br>
                    <span class="val status-online">+4,250 BTC (Cold Storage)</span>
                </div>
                <div class="data-box">
                    <strong>🩸 LIQUIDATION MAP</strong>
                    Cluster a rischio critico<br>
                    <span class="val" style="color:var(--neon-red); text-shadow: 0 0 8px var(--neon-red);">$72,400 (Shorts)</span>
                </div>
            </div>
        </div>
    </div>
    <script>
        // Random tech noise effect on numbers
        setInterval(() => {
            const elements = document.querySelectorAll('.val');
            if (Math.random() > 0.9) {
                elements.forEach(el => {
                    if(Math.random() > 0.5) {
                        el.style.opacity = Math.random() * 0.5 + 0.5;
                        setTimeout(() => el.style.opacity = 1, 150);
                    }
                });
            }
        }, 300);
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    # Ensure directory exists just in case
    os.makedirs(os.path.dirname(os.path.abspath(__file__)), exist_ok=True)
    app.run(host='0.0.0.0', port=5000)
