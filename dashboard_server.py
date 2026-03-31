from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Nuvola: Orbital Command</title>
    <style>
        :root {
            --neon-green: #0f0;
            --neon-cyan: #0ff;
            --neon-pink: #f0f;
            --dark-bg: #050505;
            --panel-bg: rgba(10, 20, 15, 0.8);
            --grid-line: rgba(0, 255, 0, 0.1);
        }
        body {
            background-color: var(--dark-bg);
            color: var(--neon-green);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            background-image: 
                linear-gradient(var(--grid-line) 1px, transparent 1px),
                linear-gradient(90deg, var(--grid-line) 1px, transparent 1px);
            background-size: 20px 20px;
            animation: scanline 10s linear infinite;
        }
        @keyframes scanline {
            0% { background-position: 0 0; }
            100% { background-position: 0 1000px; }
        }
        h1, h2, h3 {
            text-transform: uppercase;
            text-shadow: 0 0 10px var(--neon-green);
            letter-spacing: 2px;
        }
        .header {
            text-align: center;
            border-bottom: 2px solid var(--neon-cyan);
            padding-bottom: 10px;
            margin-bottom: 20px;
            box-shadow: 0 10px 10px -10px var(--neon-cyan);
        }
        .container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
        }
        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-green);
            border-radius: 5px;
            padding: 15px;
            box-shadow: 0 0 15px rgba(0, 255, 0, 0.2);
            transition: all 0.3s ease;
        }
        .panel:hover {
            box-shadow: 0 0 25px var(--neon-cyan);
            border-color: var(--neon-cyan);
        }
        .panel h2 {
            color: var(--neon-cyan);
            text-shadow: 0 0 5px var(--neon-cyan);
            border-bottom: 1px dashed var(--neon-cyan);
            padding-bottom: 5px;
            font-size: 1.2em;
        }
        .status-indicator {
            display: inline-block;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background-color: var(--neon-green);
            box-shadow: 0 0 10px var(--neon-green);
            animation: blink 1.5s infinite alternate;
            margin-right: 10px;
        }
        .status-warning {
            background-color: var(--neon-pink);
            box-shadow: 0 0 10px var(--neon-pink);
        }
        @keyframes blink {
            from { opacity: 0.5; }
            to { opacity: 1; }
        }
        ul {
            list-style-type: none;
            padding: 0;
        }
        li {
            margin-bottom: 10px;
            display: flex;
            align-items: center;
            border-left: 2px solid var(--neon-green);
            padding-left: 10px;
            background: rgba(0, 255, 0, 0.05);
            font-size: 0.9em;
        }
        .data-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
            margin-top: 10px;
        }
        .data-cell {
            background: rgba(0, 255, 255, 0.1);
            border: 1px solid var(--neon-cyan);
            padding: 10px;
            text-align: center;
            font-size: 0.9em;
            box-shadow: inset 0 0 5px rgba(0,255,255,0.2);
        }
        .data-cell span {
            font-size: 1.2em;
            font-weight: bold;
            display: block;
            margin-top: 5px;
        }
        .glitch {
            animation: glitch-anim 2s infinite;
        }
        @keyframes glitch-anim {
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
        <h1 class="glitch">🛰️ NUVOLA: ORBITAL COMMAND 🛰️</h1>
        <p>SISTEMA DI CONTROLLO QUANTITATIVO - LIVELLO DI AUTORIZZAZIONE: OMEGA</p>
        <div style="margin-top: 15px; padding: 10px; border: 1px solid var(--neon-green); background: rgba(0,255,0,0.1); display: inline-block; border-radius: 5px; box-shadow: 0 0 10px var(--neon-green);">
            <span class="status-indicator"></span>
            <b>⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</b>
        </div>
    </div>

    <div class="container">
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <ul>
                <li><span class="status-indicator"></span> <div><b>SQUADRA_ALPHA</b> (Scalper su Binance)<br> └─ Latenza: 12ms | PNL 24h: +$450.20</div></li>
                <li><span class="status-indicator"></span> <div><b>SQUADRA_DELTA</b> (Order Flow)<br> └─ Win Rate: 68% | Flusso anomalo BTC: Rilevato</div></li>
                <li><span class="status-indicator"></span> <div><b>SQUADRA_GAMMA</b> (Pairs Trading su Bitget)<br> └─ Posizione: Long/Short | Spread ARB/OP: 0.45%</div></li>
            </ul>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2>🔮 PROTOCOLLO TRINITY</h2>
            <p style="font-size:0.8em; opacity:0.8;">[Processi di ritrasmissione in background]</p>
            <ul>
                <li><span class="status-indicator"></span> <div><b>Lo Strozzino</b> (Funding Arb)<br> └─ Yield Mensile: 3.4% | Allineamento API: OK</div></li>
                <li><span class="status-indicator"></span> <div><b>Il Contabile</b> (DCA)<br> └─ Stato: ONLINE | Acquisto ETH a $3400 completato</div></li>
                <li><span class="status-indicator status-warning"></span> <div><b>L'Angelo Custode</b> (MEV Arbitrum)<br> └─ Scansione Mempool | Frontrun attempts: 42</div></li>
            </ul>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <h2>📊 METRICHE DI MERCATO (RADAR)</h2>
            <div class="data-grid">
                <div class="data-cell">
                    <b>The Oracle (Binance)</b>
                    <span style="color:var(--neon-cyan)">BULLISH 72%</span>
                </div>
                <div class="data-cell">
                    <b>Whale Tracker</b>
                    <span style="color:var(--neon-green)">+$240M Inflow</span>
                </div>
                <div class="data-cell">
                    <b>BTC Dominance</b>
                    <span style="color:var(--neon-green)">52.4% (Stabile)</span>
                </div>
                <div class="data-cell">
                    <b>Indice Paura/Avidità</b>
                    <span style="color:var(--neon-pink)">78 (Avidità)</span>
                </div>
            </div>
            <p style="margin-top:15px; font-size: 0.8em; text-align:center;">
                [Flusso dati da aggregatori esterni: Crittografato AES-256]
            </p>
        </div>
    </div>
    
    <div style="text-align: center; margin-top: 30px; font-size: 0.8em; opacity: 0.7;">
        NUVOLA CORE v9.2.1 | CONNESSO AL NODO CENTRALE | STATUS: OPERATIVO | TEMPO REALE
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
