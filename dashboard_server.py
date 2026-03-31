from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NUVOLA ORBITAL COMMAND</title>
    <style>
        :root {
            --bg-color: #050510;
            --text-main: #00ffcc;
            --text-alert: #ff0055;
            --text-warn: #ffaa00;
            --panel-bg: rgba(0, 20, 40, 0.8);
            --border-glow: 0 0 10px #00ffcc;
            --alert-glow: 0 0 15px #ff0055;
        }
        body {
            background-color: var(--bg-color);
            color: var(--text-main);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            background-image: radial-gradient(circle at 50% 50%, #0a0a2a 0%, #000 100%);
        }
        h1, h2, h3 {
            text-shadow: 0 0 8px var(--text-main);
            text-transform: uppercase;
            letter-spacing: 2px;
            margin-top: 0;
        }
        h1 {
            text-align: center;
            font-size: 2.5em;
            border-bottom: 2px solid var(--text-main);
            padding-bottom: 10px;
            margin-bottom: 30px;
            animation: pulse 2s infinite;
        }
        .grid-container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
        }
        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--text-main);
            box-shadow: var(--border-glow);
            padding: 20px;
            border-radius: 5px;
            position: relative;
            overflow: hidden;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; height: 2px;
            background: var(--text-main);
            box-shadow: 0 0 10px var(--text-main);
        }
        .status-online { color: #00ff00; text-shadow: 0 0 5px #00ff00; }
        .status-active { color: #00ffcc; text-shadow: 0 0 5px #00ffcc; }
        .status-standby { color: var(--text-warn); text-shadow: 0 0 5px var(--text-warn); }
        .status-alert { color: var(--text-alert); text-shadow: var(--alert-glow); animation: blink 1s infinite; }
        
        .squad-item, .protocol-item, .market-item {
            margin-bottom: 15px;
            padding: 10px;
            border-left: 3px solid var(--text-main);
            background: rgba(0, 255, 204, 0.05);
        }
        
        @keyframes pulse {
            0% { text-shadow: 0 0 8px var(--text-main); }
            50% { text-shadow: 0 0 20px var(--text-main), 0 0 30px #00aaff; }
            100% { text-shadow: 0 0 8px var(--text-main); }
        }
        @keyframes blink {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        .progress-bar {
            width: 100%;
            height: 10px;
            background: #111;
            margin-top: 5px;
            border: 1px solid #333;
        }
        .progress-fill {
            height: 100%;
            background: var(--text-main);
            box-shadow: 0 0 5px var(--text-main);
        }
        
        .scanline {
            position: fixed;
            top: 0; left: 0; width: 100vw; height: 100vh;
            background: linear-gradient(to bottom, rgba(255,255,255,0), rgba(255,255,255,0) 50%, rgba(0,0,0,0.1) 50%, rgba(0,0,0,0.1));
            background-size: 100% 4px;
            pointer-events: none;
            z-index: 9999;
        }
    </style>
</head>
<body>
    <div class="scanline"></div>
    <h1>🛰️ ORBITAL COMMAND - NUVOLA 🛰️</h1>
    <div style="text-align: center; margin-bottom: 20px; padding: 10px; border: 1px solid var(--text-main); background: rgba(0, 255, 204, 0.1); box-shadow: var(--border-glow); border-radius: 5px;">
        <h2 style="margin: 0; color: #00ff00; text-shadow: 0 0 5px #00ff00;">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</h2>
    </div>
    
    <div class="grid-container">
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <div class="squad-item">
                <strong>🐺 SQUADRA_ALPHA (Scalper)</strong> - Binance
                <br>Stato: <span class="status-active">INGAGGIATO</span>
                <br>PNL Sessione: <span class="status-online">+1.42%</span>
                <div class="progress-bar"><div class="progress-fill" style="width: 85%;"></div></div>
            </div>
            <div class="squad-item">
                <strong>🌊 SQUADRA_DELTA (Order Flow)</strong> - Multi-Ex
                <br>Stato: <span class="status-active">ANALISI FLUSSI</span>
                <br>Volumi Cacciati: <span class="status-online">450K USD</span>
                <div class="progress-bar"><div class="progress-fill" style="width: 60%;"></div></div>
            </div>
            <div class="squad-item">
                <strong>⚖️ SQUADRA_GAMMA (Pairs)</strong> - Bitget
                <br>Stato: <span class="status-standby">RICERCA SPREAD</span>
                <br>Correlazione Attuale: <span>0.89</span>
                <div class="progress-bar"><div class="progress-fill" style="width: 30%; background: var(--text-warn); box-shadow: 0 0 5px var(--text-warn);"></div></div>
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2>🛡️ PROTOCOLLO TRINITY</h2>
            <div class="protocol-item">
                <strong>🎩 Lo Strozzino</strong> (Funding Arb)
                <br>Stato: <span class="status-online">ONLINE [BACKGROUND]</span>
                <br>Yield Annuo Stimato: <span>22.4%</span>
            </div>
            <div class="protocol-item">
                <strong>🧮 Il Contabile</strong> (DCA Dinamico)
                <br>Stato: <span class="status-online">ONLINE [BACKGROUND]</span>
                <br>Prossimo Acquisto: <span>04h:12m:09s</span>
            </div>
            <div class="protocol-item">
                <strong>👼 L'Angelo Custode</strong> (MEV Arbitrum)
                <br>Stato: <span class="status-online">ONLINE [BACKGROUND]</span>
                <br>TX Front-runnate: <span>14 (Ultimo 24h)</span>
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <h2>📡 METRICHE DI MERCATO</h2>
            <div class="market-item">
                <strong>👁️ The Oracle (Binance Sentiment)</strong>
                <br>Indice Paura/Avidità: <span class="status-standby">68 (AVIDITA')</span>
                <br>Pressione Acquisto: <span class="status-active">ALTA</span>
            </div>
            <div class="market-item">
                <strong>🐳 Whale Tracker</strong>
                <br>Ultimo Movimento: <span class="status-alert">12,000 ETH -> Coinbase</span>
                <br>Rischio Dump: <span class="status-alert">CRITICO</span>
            </div>
            <div class="market-item">
                <strong>⚡ Latenza Rete / Esecuzione</strong>
                <br>Binance API: <span class="status-online">12ms</span>
                <br>Arbitrum RPC: <span class="status-online">45ms</span>
            </div>
        </div>
    </div>
    
    <script>
        setInterval(() => {
            const fills = document.querySelectorAll('.progress-fill');
            fills.forEach(fill => {
                let current = parseInt(fill.style.width);
                let change = Math.floor(Math.random() * 11) - 5;
                let next = Math.max(10, Math.min(100, current + change));
                fill.style.width = next + '%';
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
    app.run(host='0.0.0.0', port=5000)
