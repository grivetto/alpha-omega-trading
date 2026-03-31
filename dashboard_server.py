from flask import Flask, render_template_string

app = Flask(__name__)

HTML = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <title>Nuvola Orbital Command</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');
        body {
            background-color: #050505;
            color: #0f0;
            font-family: 'Share Tech Mono', monospace;
            margin: 0;
            padding: 20px;
            background-image: linear-gradient(rgba(0, 255, 0, 0.03) 1px, transparent 1px),
                              linear-gradient(90deg, rgba(0, 255, 0, 0.03) 1px, transparent 1px);
            background-size: 20px 20px;
        }
        h1, h2 { text-shadow: 0 0 10px #0f0; text-align: center; border-bottom: 2px solid #0f0; padding-bottom: 10px; margin-top: 0; }
        .container { max-width: 1200px; margin: auto; display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
        .panel {
            background: rgba(0, 20, 0, 0.8);
            border: 1px solid #0f0;
            padding: 20px;
            box-shadow: 0 0 15px rgba(0, 255, 0, 0.2);
            border-radius: 5px;
            position: relative;
            overflow: hidden;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: -100%; width: 50%; height: 100%;
            background: linear-gradient(to right, transparent, rgba(0, 255, 0, 0.1), transparent);
            animation: scan 4s infinite linear;
        }
        @keyframes scan { 100% { left: 200%; } }
        .status { display: flex; justify-content: space-between; margin-bottom: 12px; border-bottom: 1px dashed #060; padding-bottom: 5px; }
        .online { color: #0ff; text-shadow: 0 0 5px #0ff; }
        .active { color: #f0f; text-shadow: 0 0 5px #f0f; }
        .alert { color: #f00; text-shadow: 0 0 5px #f00; animation: blink 1s infinite; }
        @keyframes blink { 50% { opacity: 0; } }
        .grid-metric { display: grid; grid-template-columns: 1fr 1fr; gap: 15px; }
        .metric-box { border: 1px solid #060; padding: 15px; text-align: center; background: #000; box-shadow: inset 0 0 10px rgba(0,255,0,0.1); }
        .metric-title { font-size: 0.9em; color: #0a0; margin-bottom: 5px; }
        .metric-val { font-size: 1.8em; color: #0ff; text-shadow: 0 0 8px #0ff; }
        .footer { margin-top: 40px; text-align: center; color: #060; font-size: 0.8em; text-shadow: 0 0 2px #060; }
        .full-width { grid-column: span 2; }
    </style>
</head>
<body>
    <h1>🛰️ NUVOLA ORBITAL COMMAND 🛰️</h1>
    
    <div class="container">
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <div class="status"><span>🐺 SQUADRA_ALPHA <span style="color:#060;font-size:0.8em">(Scalper Binance)</span></span> <span class="active">[ INGAGGIATO ]</span></div>
            <div class="status"><span>🌊 SQUADRA_DELTA <span style="color:#060;font-size:0.8em">(Order Flow)</span></span> <span class="active">[ INGAGGIATO ]</span></div>
            <div class="status"><span>⚖️ SQUADRA_GAMMA <span style="color:#060;font-size:0.8em">(Pairs Bitget)</span></span> <span class="online">[ STANDBY ]</span></div>
            <p style="color:#0a0; font-size:0.9em;">>_ Sincronizzazione flussi ordini ad alta frequenza completata. Latenza ottimizzata.</p>
        </div>

        <div class="panel">
            <h2>🛡️ PROTOCOLLO TRINITY</h2>
            <div style="text-align: center; color: #ff0; font-weight: bold; margin-bottom: 15px; text-shadow: 0 0 5px #ff0;">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</div>
            <div class="status"><span>🧛 Lo Strozzino <span style="color:#060;font-size:0.8em">(Funding Arb)</span></span> <span class="online">[ ONLINE ]</span></div>
            <div class="status"><span>🧮 Il Contabile <span style="color:#060;font-size:0.8em">(DCA Strategico)</span></span> <span class="online">[ ONLINE ]</span></div>
            <div class="status"><span>👼 L'Angelo Custode <span style="color:#060;font-size:0.8em">(MEV Arbitrum)</span></span> <span class="online">[ ONLINE ]</span></div>
            <p style="color:#0a0; font-size:0.9em;">>_ Protocolli di accumulo e difesa capitale operativi in background.</p>
        </div>

        <div class="panel full-width">
            <h2>🐋🔮 METRICHE DI MERCATO</h2>
            <div class="grid-metric">
                <div class="metric-box">
                    <div class="metric-title">THE ORACLE (BINANCE SENTIMENT)</div>
                    <div class="metric-val active">BULLISH 78% 🟢</div>
                </div>
                <div class="metric-box">
                    <div class="metric-title">WHALE TRACKER</div>
                    <div class="metric-val alert">ANOMALIA RILEVATA ⚠️</div>
                </div>
                <div class="metric-box">
                    <div class="metric-title">LIQUIDITÀ GLOBALE (H24)</div>
                    <div class="metric-val">$ 2.45 B 💸</div>
                </div>
                <div class="metric-box">
                    <div class="metric-title">PING ORBITALE</div>
                    <div class="metric-val">12 ms ⚡</div>
                </div>
            </div>
        </div>
    </div>
    
    <div class="footer">
        SISTEMA NUVOLA QUANTITATIVE v4.2.0 | ENCRYPTED CONNECTION ESTABLISHED | CLOCK SYNC: 2026-03-31 05:16 UTC
    </div>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
