from flask import Flask, render_template_string
import datetime

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NUVOLA // ORBITAL COMMAND</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');
        :root {
            --bg: #050505;
            --text: #0f0;
            --neon-green: #39ff14;
            --neon-blue: #00f3ff;
            --neon-magenta: #ff00ff;
            --neon-red: #ff073a;
            --panel-bg: rgba(0, 20, 0, 0.6);
        }
        body {
            background-color: var(--bg);
            color: var(--text);
            font-family: 'Share Tech Mono', monospace;
            margin: 0;
            padding: 20px;
            background-image: 
                linear-gradient(rgba(0, 255, 0, 0.05) 1px, transparent 1px),
                linear-gradient(90deg, rgba(0, 255, 0, 0.05) 1px, transparent 1px);
            background-size: 30px 30px;
            overflow-x: hidden;
        }
        h1, h2, h3 {
            text-transform: uppercase;
            letter-spacing: 2px;
            margin-top: 0;
        }
        .header {
            text-align: center;
            border-bottom: 2px solid var(--neon-blue);
            padding-bottom: 15px;
            margin-bottom: 30px;
            text-shadow: 0 0 10px var(--neon-blue);
            color: var(--neon-blue);
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
            gap: 25px;
        }
        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-green);
            padding: 20px;
            box-shadow: inset 0 0 15px rgba(57, 255, 20, 0.1), 0 0 10px rgba(57, 255, 20, 0.3);
            position: relative;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; bottom: 0;
            box-shadow: 0 0 20px var(--neon-green);
            opacity: 0.3;
            pointer-events: none;
        }
        .panel.blue { border-color: var(--neon-blue); box-shadow: inset 0 0 15px rgba(0, 243, 255, 0.1), 0 0 10px rgba(0, 243, 255, 0.3); color: #fff; }
        .panel.blue::before { box-shadow: 0 0 20px var(--neon-blue); }
        .panel.magenta { border-color: var(--neon-magenta); box-shadow: inset 0 0 15px rgba(255, 0, 255, 0.1), 0 0 10px rgba(255, 0, 255, 0.3); color: #fff;}
        .panel.magenta::before { box-shadow: 0 0 20px var(--neon-magenta); }
        
        .status-indicator {
            display: inline-block;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            background-color: var(--neon-green);
            box-shadow: 0 0 12px var(--neon-green);
            animation: blink 1.5s infinite alternate;
            margin-right: 12px;
        }
        @keyframes blink {
            0% { opacity: 0.3; }
            100% { opacity: 1; }
        }
        .table-container {
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
            font-size: 0.9em;
        }
        .table-container th, .table-container td {
            border: 1px solid rgba(255, 255, 255, 0.2);
            padding: 10px;
            text-align: left;
        }
        .table-container th {
            background: rgba(255, 255, 255, 0.1);
        }
        .panel:not(.blue):not(.magenta) .table-container th { background: rgba(0, 255, 0, 0.1); border-color: rgba(0,255,0,0.3); color: var(--neon-green); }
        .panel:not(.blue):not(.magenta) .table-container td { border-color: rgba(0,255,0,0.3); }

        .glitch {
            animation: glitch 3s linear infinite;
        }
        @keyframes glitch {
            2%, 64% { transform: translate(2px,0) skew(0deg); }
            4%, 60% { transform: translate(-2px,0) skew(0deg); }
            62% { transform: translate(0,0) skew(5deg); }
        }
        .scanline {
            width: 100%;
            height: 150px;
            z-index: 10;
            position: fixed;
            pointer-events: none;
            background: linear-gradient(0deg, rgba(0,0,0,0) 0%, rgba(57,255,20,0.1) 50%, rgba(0,0,0,0) 100%);
            opacity: 0.2;
            animation: scanline 8s linear infinite;
            top: -150px;
            left: 0;
        }
        @keyframes scanline {
            0% { top: -150px; }
            100% { top: 100%; }
        }
        .progress-bar {
            height: 12px;
            background: #111;
            border: 1px solid var(--neon-green);
            margin-top: 5px;
            margin-bottom: 5px;
        }
        .progress-fill {
            height: 100%;
            background: var(--neon-green);
            box-shadow: 0 0 8px var(--neon-green);
        }
        .highlight-green { color: var(--neon-green); font-weight: bold; }
        .highlight-blue { color: var(--neon-blue); font-weight: bold; }
        .highlight-magenta { color: var(--neon-magenta); font-weight: bold; }
        .highlight-red { color: var(--neon-red); font-weight: bold; }
        hr { border: 0; border-top: 1px solid; opacity: 0.3; margin: 15px 0; }
    </style>
</head>
<body>
    <div class="scanline"></div>
    <div class="header">
        <h1 class="glitch">🚀 NUVOLA // ORBITAL COMMAND 🚀</h1>
        <p>SISTEMA QUANTITATIVO TATTICO ONLINE | [SYS.OP: NORMALE] | AUTORIZZAZIONE ALPHA</p>
        <div style="margin-top: 10px; font-size: 1.2em; font-weight: bold; color: var(--neon-green); text-shadow: 0 0 10px var(--neon-green); background: rgba(0,255,0,0.1); border: 1px solid var(--neon-green); padding: 5px; display: inline-block;">
            ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
        </div>
    </div>

    <div class="grid">
        <!-- 1) SQUADRE D'ASSALTO -->
        <div class="panel">
            <h2 style="color: var(--neon-green);"><span class="status-indicator"></span>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <hr style="border-color: var(--neon-green);">
            
            <p><strong>🐺 SQUADRA_ALPHA</strong> <span style="font-size:0.8em">[Scalper @ Binance]</span></p>
            <div class="progress-bar"><div class="progress-fill" style="width: 87%;"></div></div>
            <p style="font-size:0.9em">Status: <span class="highlight-green">ATTIVO</span> | PnL Oggi: <span class="highlight-green">+$420.69</span> | Latenza: 12ms</p>
            <br>
            
            <p><strong>🌊 SQUADRA_DELTA</strong> <span style="font-size:0.8em">[Order Flow]</span></p>
            <div class="progress-bar"><div class="progress-fill" style="width: 65%;"></div></div>
            <p style="font-size:0.9em">Status: <span class="highlight-green">ATTIVO</span> | Imbalance: LONG Bias | Latenza: 15ms</p>
            <br>
            
            <p><strong>⚖️ SQUADRA_GAMMA</strong> <span style="font-size:0.8em">[Pairs Trading @ Bitget]</span></p>
            <div class="progress-bar"><div class="progress-fill" style="width: 42%;"></div></div>
            <p style="font-size:0.9em">Status: <span class="highlight-green">ATTIVO</span> | Z-Score: +2.1 | Latenza: 28ms</p>
        </div>

        <!-- 2) PROTOCOLLO TRINITY -->
        <div class="panel blue">
            <h2 style="color: var(--neon-blue);"><span class="status-indicator" style="background-color: var(--neon-blue); box-shadow: 0 0 12px var(--neon-blue);"></span>👁️ PROTOCOLLO TRINITY</h2>
            <hr style="border-color: var(--neon-blue);">
            
            <p><strong>🦇 Lo Strozzino</strong> <span style="font-size:0.8em; color:#aaa;">[Funding Arb]</span></p>
            <p style="font-size:0.9em; color: #ccc;">Monitoraggio spread perpetui. Operatività background: 100%.</p>
            <p style="font-size:0.9em">APR Stimato: <span class="highlight-blue">18.4%</span></p>
            <br>
            
            <p><strong>🧮 Il Contabile</strong> <span style="font-size:0.8em; color:#aaa;">[DCA Accumulation]</span></p>
            <p style="font-size:0.9em; color: #ccc;">Accumulo BTC/ETH programmato in modalità stealth.</p>
            <p style="font-size:0.9em">Prossimo acquisto: <span class="highlight-blue">Tra 04h 12m</span></p>
            <br>
            
            <p><strong>🛡️ L'Angelo Custode</strong> <span style="font-size:0.8em; color:#aaa;">[MEV @ Arbitrum]</span></p>
            <p style="font-size:0.9em; color: #ccc;">Protezione liquidazioni e sniping opportunità flash.</p>
            <p style="font-size:0.9em">Tx Frontrunnate oggi: <span class="highlight-blue">7</span></p>
        </div>

        <!-- 3) METRICHE DI MERCATO -->
        <div class="panel magenta">
            <h2 style="color: var(--neon-magenta);"><span class="status-indicator" style="background-color: var(--neon-magenta); box-shadow: 0 0 12px var(--neon-magenta);"></span>📡 METRICHE DI MERCATO</h2>
            <hr style="border-color: var(--neon-magenta);">
            
            <p><strong>🔮 The Oracle</strong> <span style="font-size:0.8em; color:#aaa;">[Binance Sentiment]</span></p>
            <table class="table-container">
                <tr><th style="color: var(--neon-magenta); border-color: rgba(255,0,255,0.3);">ASSET</th><th style="color: var(--neon-magenta); border-color: rgba(255,0,255,0.3);">SENTIMENT</th><th style="color: var(--neon-magenta); border-color: rgba(255,0,255,0.3);">CONFIDENCE</th></tr>
                <tr><td style="border-color: rgba(255,0,255,0.3);">BTC/USDT</td><td class="highlight-green" style="border-color: rgba(255,0,255,0.3);">BULLISH</td><td style="border-color: rgba(255,0,255,0.3);">89%</td></tr>
                <tr><td style="border-color: rgba(255,0,255,0.3);">ETH/USDT</td><td class="highlight-green" style="border-color: rgba(255,0,255,0.3);">BULLISH</td><td style="border-color: rgba(255,0,255,0.3);">75%</td></tr>
                <tr><td style="border-color: rgba(255,0,255,0.3);">SOL/USDT</td><td class="highlight-red" style="border-color: rgba(255,0,255,0.3);">BEARISH</td><td style="border-color: rgba(255,0,255,0.3);">62%</td></tr>
            </table>
            <br>
            
            <p><strong>🐋 Whale Tracker</strong> <span style="font-size:0.8em; color:#aaa;">[On-Chain Flows]</span></p>
            <table class="table-container">
                <tr><th style="color: var(--neon-magenta); border-color: rgba(255,0,255,0.3);">NETWORK</th><th style="color: var(--neon-magenta); border-color: rgba(255,0,255,0.3);">VOL (24H)</th><th style="color: var(--neon-magenta); border-color: rgba(255,0,255,0.3);">ANOMALY</th></tr>
                <tr><td style="border-color: rgba(255,0,255,0.3);">Ethereum</td><td style="border-color: rgba(255,0,255,0.3);">$1.2B IN</td><td style="border-color: rgba(255,0,255,0.3);">BASSA</td></tr>
                <tr><td style="border-color: rgba(255,0,255,0.3);">Arbitrum</td><td style="border-color: rgba(255,0,255,0.3);">$400M OUT</td><td class="highlight-magenta" style="border-color: rgba(255,0,255,0.3);">ALTA</td></tr>
            </table>
        </div>
    </div>
    
    <div style="margin-top: 40px; text-align: center; color: #444; font-size: 0.85em;">
        >_ CONNESSIONE CRIPTATA // TERMINALE NUVOLA-OS // {{ timestamp }} // LOCALIZZAZIONE: MUNITO
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE, timestamp=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC"))

if __name__ == '__main__':
    # Run the Orbital Command Dashboard
    app.run(host='0.0.0.0', port=5000, debug=False)
