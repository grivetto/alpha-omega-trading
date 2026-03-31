from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Orbital Command | Nuvola</title>
    <style>
        :root {
            --bg-color: #050510;
            --neon-blue: #0ff;
            --neon-pink: #f0f;
            --neon-green: #39ff14;
            --neon-red: #ff3333;
            --neon-yellow: #fdf500;
            --text-color: #e0e0e0;
            --panel-bg: rgba(10, 10, 25, 0.8);
        }
        body {
            background-color: var(--bg-color);
            color: var(--text-color);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            background-image: linear-gradient(rgba(0, 255, 255, 0.05) 1px, transparent 1px),
                              linear-gradient(90deg, rgba(0, 255, 255, 0.05) 1px, transparent 1px);
            background-size: 20px 20px;
        }
        h1 {
            text-align: center;
            color: var(--neon-blue);
            text-shadow: 0 0 10px var(--neon-blue), 0 0 20px var(--neon-blue);
            text-transform: uppercase;
            letter-spacing: 5px;
            margin-bottom: 40px;
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
            box-shadow: inset 0 0 10px rgba(0, 255, 255, 0.2), 0 0 15px rgba(0, 255, 255, 0.1);
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
        .panel h2 {
            color: var(--neon-pink);
            text-shadow: 0 0 8px var(--neon-pink);
            border-bottom: 1px dashed var(--neon-pink);
            padding-bottom: 10px;
            margin-top: 0;
            font-size: 1.2em;
        }
        .status-item {
            display: flex;
            justify-content: space-between;
            margin: 15px 0;
            padding: 10px;
            background: rgba(0,0,0,0.5);
            border-left: 3px solid var(--neon-green);
        }
        .status-online { color: var(--neon-green); text-shadow: 0 0 5px var(--neon-green); font-weight: bold; }
        .status-offline { color: var(--neon-red); text-shadow: 0 0 5px var(--neon-red); }
        .status-standby { color: var(--neon-yellow); text-shadow: 0 0 5px var(--neon-yellow); }
        
        /* Animations */
        @keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
        .blink { animation: blink 2s infinite; }
        
        @keyframes scanline {
            0% { transform: translateY(-100%); }
            100% { transform: translateY(100vh); }
        }
        .scanline {
            position: fixed;
            top: 0; left: 0; width: 100%; height: 5px;
            background: rgba(0, 255, 255, 0.3);
            opacity: 0.5;
            animation: scanline 8s linear infinite;
            pointer-events: none;
            z-index: 9999;
        }

        table { width: 100%; border-collapse: collapse; margin-top: 10px; }
        th, td { border: 1px solid rgba(0, 255, 255, 0.3); padding: 8px; text-align: left; }
        th { color: var(--neon-blue); }
        
        .terminal {
            font-size: 0.9em;
            color: var(--neon-green);
            background: #000;
            padding: 10px;
            height: 150px;
            overflow-y: auto;
            border: 1px solid #333;
        }
    </style>
</head>
<body>
    <div class="scanline"></div>
    <h1>🛰️ ORBITAL COMMAND <span style="font-size: 0.5em; color: var(--text-color); text-shadow: none;">v3.0.0</span></h1>
    
    <div class="container">
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <div class="status-item">
                <span>🐺 SQUADRA_ALPHA (Scalping Binance)</span>
                <span class="status-online blink">ENGAGED [142ms]</span>
            </div>
            <div class="status-item">
                <span>🦅 SQUADRA_DELTA (Order Flow)</span>
                <span class="status-online">MONITORING</span>
            </div>
            <div class="status-item" style="border-left-color: var(--neon-yellow);">
                <span>🦈 SQUADRA_GAMMA (Pairs Bitget)</span>
                <span class="status-standby">AWAITING SIGNAL</span>
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2>🔺 PROTOCOLLO TRINITY</h2>
            <div style="text-align: center; margin-bottom: 15px; padding: 5px; background: rgba(0,255,255,0.1); border: 1px solid var(--neon-blue); color: var(--neon-blue); font-weight: bold; text-shadow: 0 0 5px var(--neon-blue);">
                ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
            </div>
            <div class="status-item">
                <span>🦇 Lo Strozzino (Funding Arb)</span>
                <span class="status-online blink">ACTIVE - YIELDING</span>
            </div>
            <div class="status-item">
                <span>💼 Il Contabile (DCA Engine)</span>
                <span class="status-online">SYNCED</span>
            </div>
            <div class="status-item">
                <span>🛡️ L'Angelo Custode (MEV Arb)</span>
                <span class="status-online">SNIPING TXs [Mempool]</span>
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <h2>📊 METRICHE DI MERCATO</h2>
            <table>
                <tr><th>Sensore</th><th>Stato/Valore</th></tr>
                <tr><td>👁️ The Oracle (Sentiment)</td><td class="status-online">BULLISH [78%]</td></tr>
                <tr><td>🐳 Whale Tracker</td><td><span style="color:var(--neon-pink)">1.2k BTC Moved</span></td></tr>
                <tr><td>⚡ Binance Latency</td><td>12ms</td></tr>
                <tr><td>⛽ Arbitrum Gas</td><td>0.1 gwei</td></tr>
            </table>
        </div>

        <!-- TERMINALE LOGS -->
        <div class="panel" style="grid-column: 1 / -1;">
            <h2>📟 COM-LINK LOGS</h2>
            <div class="terminal" id="term-logs">
                > [SYS] Inizializzazione Orbital Command... OK<br>
                > [SYS] Connessione a Nuvola Core... STABILITA<br>
                > [ALPHA] Eseguito ordine LONG BTC/USDT @ 69,420<br>
                > [TRINITY] Lo Strozzino ha incassato 1.2 USDT di funding rate.<br>
                > [ORACLE] Rilevato picco di volumi su ETH.<br>
                > [ANGELO] Transazione MEV protetta. Profitto: 0.05 ETH.<br>
            </div>
        </div>
    </div>
    
    <script>
        const logs = [
            "> [DELTA] Analisi order book in corso...",
            "> [ALPHA] Chiusura posizione LONG. PnL: +$14.50",
            "> [WHALE] Rilevato trasferimento anomalo su rete Tron.",
            "> [SYS] Aggiornamento pesi rete neurale completato."
        ];
        let logDiv = document.getElementById('term-logs');
        setInterval(() => {
            let newLog = logs[Math.floor(Math.random() * logs.length)];
            logDiv.innerHTML += newLog + "<br>";
            logDiv.scrollTop = logDiv.scrollHeight;
        }, 4000);
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
