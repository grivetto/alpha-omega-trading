from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <title>ORBITAL COMMAND // NUVOLA</title>
    <style>
        :root {
            --neon-green: #0fa;
            --neon-blue: #0ff;
            --neon-purple: #f0f;
            --dark-bg: #050505;
            --panel-bg: #111;
        }
        body {
            background-color: var(--dark-bg);
            color: var(--neon-green);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            overflow-x: hidden;
        }
        h1, h2, h3 {
            text-transform: uppercase;
            text-shadow: 0 0 5px var(--neon-green), 0 0 10px var(--neon-green);
        }
        .glow-blue { color: var(--neon-blue); text-shadow: 0 0 5px var(--neon-blue), 0 0 10px var(--neon-blue); }
        .glow-purple { color: var(--neon-purple); text-shadow: 0 0 5px var(--neon-purple), 0 0 10px var(--neon-purple); }
        
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
            box-shadow: 0 0 10px rgba(0, 255, 170, 0.2);
            padding: 20px;
            border-radius: 5px;
            position: relative;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; height: 2px;
            background: var(--neon-green);
            box-shadow: 0 0 10px var(--neon-green);
        }
        .scanline {
            width: 100%;
            height: 100px;
            z-index: 9999;
            position: absolute;
            pointer-events: none;
            background: linear-gradient(to bottom, rgba(255,255,255,0), rgba(0, 255, 170, 0.2) 50%, rgba(0,0,0,0.1));
            opacity: 0.1;
            animation: scan 5s linear infinite;
        }
        @keyframes scan {
            0% { top: -100px; }
            100% { top: 100%; }
        }
        .blink { animation: blinker 1s linear infinite; }
        @keyframes blinker { 50% { opacity: 0; } }
        
        ul { list-style-type: none; padding-left: 0; }
        li { margin-bottom: 10px; border-left: 2px solid var(--neon-green); padding-left: 10px; }
        
        .status-online { color: #0f0; text-shadow: 0 0 5px #0f0; }
        .status-standby { color: #ff0; text-shadow: 0 0 5px #ff0; }
        .status-active { color: #f00; text-shadow: 0 0 5px #f00; animation: blinker 2s linear infinite;}
    </style>
</head>
<body>
    <div class="scanline"></div>
    <header style="text-align: center; margin-bottom: 40px; border-bottom: 1px dashed var(--neon-green); padding-bottom: 20px;">
        <h1>🛰️ ORBITAL COMMAND <span class="blink">_</span></h1>
        <p class="glow-blue">SISTEMA DI CONTROLLO NUVOLA V2.0 // STATUS: OPERATIVO</p>
        <div style="margin-top: 15px; padding: 10px; border: 1px solid var(--neon-green); background: rgba(0,255,170,0.1); display: inline-block; border-radius: 5px;">
            <h3 style="margin: 0; color: #fff; text-shadow: 0 0 5px #fff;">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</h3>
        </div>
    </header>

    <div class="container">
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <h2 class="glow-purple">⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <ul>
                <li>
                    <strong>SQUADRA_ALPHA</strong> [Scalper su Binance]<br>
                    <span class="status-active">▶ ENGAGED</span> | PnL: <span class="glow-blue">+2.4%</span> | Latency: 12ms
                </li>
                <li>
                    <strong>SQUADRA_DELTA</strong> [Order Flow]<br>
                    <span class="status-online">▶ ONLINE</span> | Analisi Book in corso...
                </li>
                <li>
                    <strong>SQUADRA_GAMMA</strong> [Pairs Trading su Bitget]<br>
                    <span class="status-standby">▶ STANDBY</span> | Ricerca divergenze...
                </li>
            </ul>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2 class="glow-blue">👁️ PROTOCOLLO TRINITY</h2>
            <ul>
                <li>
                    <strong>Lo Strozzino</strong> (Funding Arb)<br>
                    <span class="status-online">▶ BACKGROUND</span> | Yield: 18.5% APY
                </li>
                <li>
                    <strong>Il Contabile</strong> (DCA)<br>
                    <span class="status-online">▶ BACKGROUND</span> | Next Buy: 4h 12m
                </li>
                <li>
                    <strong>L'Angelo Custode</strong> (MEV Arbitrum)<br>
                    <span class="status-online">▶ BACKGROUND</span> | Mempool Scanning...
                </li>
            </ul>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel" style="grid-column: span 2;">
            <h2>📊 METRICHE DI MERCATO</h2>
            <div style="display: flex; justify-content: space-around; text-align: center;">
                <div>
                    <h3>The Oracle</h3>
                    <p class="glow-blue">Binance Sentiment</p>
                    <p style="font-size: 2em; margin:0;" class="status-online">BULLISH (72%)</p>
                </div>
                <div>
                    <h3>Whale Tracker</h3>
                    <p class="glow-purple">Large Transactions</p>
                    <p style="font-size: 2em; margin:0;" class="status-active">DETECTED: 1,500 BTC</p>
                </div>
                <div>
                    <h3>System Load</h3>
                    <p>Nuvola CPU / RAM</p>
                    <p style="font-size: 2em; margin:0;" class="status-standby">12% / 45%</p>
                </div>
            </div>
        </div>
    </div>
    
    <footer style="margin-top: 40px; text-align: center; opacity: 0.5; font-size: 0.8em;">
        [SECURE CONNECTION ESTABLISHED] // [ENCRYPTION LEVEL: MAXIMUM] // NO UNAUTHORIZED ACCESS
    </footer>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    # Start on port 5000 or any preferred port
    app.run(host='0.0.0.0', port=5000, debug=False)
