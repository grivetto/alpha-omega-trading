from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>⚡ ORBITAL COMMAND ⚡</title>
    <style>
        :root {
            --bg-color: #050510;
            --neon-green: #00ff00;
            --neon-blue: #00f3ff;
            --neon-pink: #ff00ff;
            --neon-yellow: #fffb00;
            --border-color: rgba(0, 255, 0, 0.4);
        }
        
        body {
            background-color: var(--bg-color);
            color: var(--neon-green);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            overflow-x: hidden;
            background-image: 
                linear-gradient(rgba(0, 255, 0, 0.05) 1px, transparent 1px),
                linear-gradient(90deg, rgba(0, 255, 0, 0.05) 1px, transparent 1px);
            background-size: 20px 20px;
        }

        h1, h2, h3 {
            text-transform: uppercase;
            letter-spacing: 2px;
            margin-top: 0;
        }

        h1 {
            color: var(--neon-blue);
            text-shadow: 0 0 10px var(--neon-blue), 0 0 20px var(--neon-blue);
            text-align: center;
            border-bottom: 2px solid var(--neon-blue);
            padding-bottom: 10px;
            animation: flicker 4s infinite alternate;
        }

        .container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
            margin-top: 30px;
        }

        .panel {
            background: rgba(0, 20, 0, 0.6);
            border: 1px solid var(--neon-green);
            box-shadow: inset 0 0 10px rgba(0,255,0,0.2), 0 0 10px rgba(0,255,0,0.2);
            padding: 20px;
            position: relative;
        }
        
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0;
            width: 15px; height: 15px;
            border-top: 2px solid var(--neon-green);
            border-left: 2px solid var(--neon-green);
        }

        .panel::after {
            content: '';
            position: absolute;
            bottom: 0; right: 0;
            width: 15px; height: 15px;
            border-bottom: 2px solid var(--neon-green);
            border-right: 2px solid var(--neon-green);
        }

        .panel h2 {
            font-size: 1.2rem;
            border-bottom: 1px dashed var(--neon-green);
            padding-bottom: 5px;
            display: flex;
            justify-content: space-between;
        }

        .status {
            display: inline-block;
            width: 10px;
            height: 10px;
            background-color: var(--neon-green);
            border-radius: 50%;
            box-shadow: 0 0 8px var(--neon-green);
            animation: pulse 1.5s infinite;
        }

        .status.warning {
            background-color: var(--neon-yellow);
            box-shadow: 0 0 8px var(--neon-yellow);
        }

        .status.danger {
            background-color: var(--neon-pink);
            box-shadow: 0 0 8px var(--neon-pink);
        }

        .metric {
            display: flex;
            justify-content: space-between;
            margin-bottom: 10px;
            border-bottom: 1px solid rgba(0, 255, 0, 0.2);
        }

        .metric-value {
            font-weight: bold;
            color: var(--neon-blue);
        }

        ul {
            list-style-type: none;
            padding-left: 0;
        }

        li {
            margin-bottom: 15px;
            padding: 10px;
            background: rgba(0, 255, 0, 0.05);
            border-left: 3px solid var(--neon-green);
        }

        .grid-placeholder {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 5px;
            margin-top: 15px;
        }

        .cell {
            background: rgba(0, 50, 0, 0.8);
            border: 1px solid var(--border-color);
            padding: 10px;
            text-align: center;
            font-size: 0.8rem;
            animation: randomBlink 3s infinite alternate;
        }

        .cell-pink { color: var(--neon-pink); border-color: rgba(255, 0, 255, 0.5); }
        .cell-blue { color: var(--neon-blue); border-color: rgba(0, 243, 255, 0.5); }

        @keyframes pulse {
            0% { transform: scale(0.95); opacity: 0.8; }
            50% { transform: scale(1.1); opacity: 1; }
            100% { transform: scale(0.95); opacity: 0.8; }
        }

        @keyframes flicker {
            0%, 19%, 21%, 23%, 25%, 54%, 56%, 100% { text-shadow: 0 0 10px var(--neon-blue), 0 0 20px var(--neon-blue); opacity: 1; }
            20%, 24%, 55% { text-shadow: none; opacity: 0.4; }
        }
        
        @keyframes scanline {
            0% { transform: translateY(-100%); }
            100% { transform: translateY(100vh); }
        }

        .scanline {
            position: fixed;
            top: 0; left: 0; width: 100%; height: 5px;
            background: rgba(0, 255, 0, 0.3);
            opacity: 0.4;
            animation: scanline 8s linear infinite;
            pointer-events: none;
            z-index: 9999;
        }
        
        .sys-log {
            font-size: 0.8rem;
            color: #888;
            height: 100px;
            overflow: hidden;
            margin-top: 10px;
            border: 1px solid #333;
            padding: 5px;
        }

    </style>
</head>
<body>
    <div class="scanline"></div>
    
    <h1>👁️ ORBITAL COMMAND 👁️<br><span style="font-size: 1rem; color: var(--neon-green); text-shadow: none;">SYSTEM.NUVOLA.ONLINE // UPTIME: 99.99%</span><br><span style="font-size: 1.2rem; color: var(--neon-blue); text-shadow: none; display: block; margin-top: 10px; padding: 5px; border: 1px solid var(--neon-blue); background: rgba(0, 243, 255, 0.1);">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</span></h1>

    <div class="container">
        <!-- SEZIONE 1: SQUADRE D'ASSALTO -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT) <span class="status"></span></h2>
            <ul>
                <li>
                    <strong>🐺 SQUADRA_ALPHA (Scalper Binance)</strong><br>
                    <span style="font-size: 0.9em; color: var(--neon-blue);">Status: ATTIVO // Mode: Aggressive</span>
                    <div class="metric"><span class="metric-label">Win Rate:</span> <span class="metric-value">72.4%</span></div>
                    <div class="metric"><span class="metric-label">Latency:</span> <span class="metric-value">12ms</span></div>
                </li>
                <li>
                    <strong>🌊 SQUADRA_DELTA (Order Flow)</strong><br>
                    <span style="font-size: 0.9em; color: var(--neon-yellow);">Status: MONITORAGGIO // Mode: Sniper</span>
                    <div class="metric"><span class="metric-label">Liquidity Targets:</span> <span class="metric-value" style="color: var(--neon-yellow);">3 Tracked</span></div>
                </li>
                <li>
                    <strong>⚖️ SQUADRA_GAMMA (Pairs Trading Bitget)</strong><br>
                    <span style="font-size: 0.9em; color: var(--neon-blue);">Status: ATTIVO // Mode: Neutral</span>
                    <div class="metric"><span class="metric-label">Spread:</span> <span class="metric-value">0.15%</span></div>
                    <div class="metric"><span class="metric-label">Active Pairs:</span> <span class="metric-value">4</span></div>
                </li>
            </ul>
        </div>

        <!-- SEZIONE 2: PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2>🛡️ PROTOCOLLO TRINITY <span class="status" style="background-color: var(--neon-blue); box-shadow: 0 0 8px var(--neon-blue);"></span></h2>
            <p style="font-size: 0.85em; color: #888;">Operazioni in background garantite.</p>
            <ul>
                <li style="border-color: var(--neon-pink);">
                    <strong>🧛 Lo Strozzino (Funding Arb)</strong><br>
                    <span style="font-size: 0.85em;">Cattura tassi di finanziamento perpetui. Rischio zero.</span>
                    <div class="metric"><span class="metric-label">Yield Est.:</span> <span class="metric-value" style="color: var(--neon-pink);">18.2% APY</span></div>
                </li>
                <li style="border-color: var(--neon-yellow);">
                    <strong>🧮 Il Contabile (DCA)</strong><br>
                    <span style="font-size: 0.85em;">Accumulo sistematico di asset hard. Nessuna emozione.</span>
                    <div class="metric"><span class="metric-label">Next Buy In:</span> <span class="metric-value" style="color: var(--neon-yellow);">04:12:09</span></div>
                </li>
                <li style="border-color: var(--neon-blue);">
                    <strong>👼 L'Angelo Custode (MEV Arbitrum)</strong><br>
                    <span style="font-size: 0.85em;">Protezione ed estrazione valore on-chain.</span>
                    <div class="metric"><span class="metric-label">Blocks Scanned:</span> <span class="metric-value" style="color: var(--neon-blue);">943,201</span></div>
                </li>
            </ul>
        </div>

        <!-- SEZIONE 3: METRICHE DI MERCATO -->
        <div class="panel">
            <h2>📈 METRICHE DI MERCATO <span class="status"></span></h2>
            
            <div style="margin-bottom: 20px;">
                <strong>🔮 The Oracle (Binance Sentiment)</strong>
                <div class="metric"><span class="metric-label">Indice di Paura/Avidità:</span> <span class="metric-value" style="color: var(--neon-pink);">78 (AVIDITA')</span></div>
                <div class="metric"><span class="metric-label">Retail Long/Short Ratio:</span> <span class="metric-value">2.41 (Sbilanciato)</span></div>
            </div>

            <strong>🐋 Whale Tracker (Flussi On-Chain)</strong>
            <div class="grid-placeholder">
                <div class="cell cell-blue">BTC<br>+400</div>
                <div class="cell cell-pink">ETH<br>-1200</div>
                <div class="cell">SOL<br>+10k</div>
                <div class="cell">USDT<br>+50M</div>
                <div class="cell cell-pink">LINK<br>-50k</div>
                <div class="cell cell-blue">AVAX<br>+2k</div>
                <div class="cell">ARB<br>+1M</div>
                <div class="cell cell-pink">PEPE<br>-1B</div>
            </div>
            
            <div class="sys-log">
                > [SYS] Connessione WebSocket stabilita.<br>
                > [ORACLE] Rilevata divergenza RSI su timeframe 15m.<br>
                > [WHALE] Allerta: Movimento 50M USDT su Binance.<br>
                > [TRINITY] Contabile eseguito blocco acquisto #441.<br>
                > [ALPHA] Ordine limite inserito: BTC/USDT @ 68,450.
            </div>
        </div>
    </div>
    
    <script>
        // Effetto log scorrevole finto
        const logs = [
            "> [SYS] Aggiornamento libro ordini...",
            "> [DELTA] Ricalibratura target liquidità...",
            "> [ANGELO] Sandwich attack evitato su SushiSwap.",
            "> [STROZZINO] Spread positivo rilevato su Bybit.",
            "> [SYS] Latenza rete: Ottimale (12ms)."
        ];
        const logContainer = document.querySelector('.sys-log');
        
        setInterval(() => {
            const randomLog = logs[Math.floor(Math.random() * logs.length)];
            logContainer.innerHTML += `<br>${randomLog}`;
            logContainer.scrollTop = logContainer.scrollHeight;
        }, 3000);
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    # Avvio su porta 5000 accessibile da tutte le interfacce
    app.run(host='0.0.0.0', port=5000, debug=False)
