import os
from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NUVOLA // ORBITAL COMMAND</title>
    <style>
        :root {
            --neon-green: #0fa;
            --neon-pink: #f0f;
            --neon-blue: #0ff;
            --bg: #050505;
        }
        body {
            background-color: var(--bg);
            color: var(--neon-green);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 2rem;
            overflow-x: hidden;
        }
        h1 {
            text-align: center;
            color: var(--neon-blue);
            text-shadow: 0 0 10px var(--neon-blue), 0 0 20px var(--neon-blue);
            letter-spacing: 5px;
            animation: pulse 2s infinite alternate;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 2rem;
            margin-top: 3rem;
        }
        .panel {
            background: rgba(0, 255, 170, 0.05);
            border: 1px solid var(--neon-green);
            padding: 1.5rem;
            box-shadow: inset 0 0 10px rgba(0, 255, 170, 0.1), 0 0 15px rgba(0, 255, 170, 0.2);
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
        .panel h2 {
            color: var(--neon-pink);
            text-shadow: 0 0 8px var(--neon-pink);
            border-bottom: 1px dashed var(--neon-pink);
            padding-bottom: 0.5rem;
            margin-top: 0;
            font-size: 1.2rem;
        }
        p { margin: 0.8rem 0; font-size: 0.95rem; line-height: 1.4; }
        .status { font-weight: bold; }
        .blink { animation: blinker 1s linear infinite; }
        @keyframes blinker { 50% { opacity: 0; } }
        @keyframes pulse { from { text-shadow: 0 0 10px var(--neon-blue); } to { text-shadow: 0 0 20px var(--neon-blue), 0 0 30px var(--neon-blue); } }
        .highlight { color: #fff; text-shadow: 0 0 5px #fff; }
    </style>
</head>
<body>
    <h1>[ NUVOLA ORBITAL COMMAND ]</h1>
    
    <div class="grid">
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <p>🐺 <strong>SQUADRA_ALPHA</strong> [Scalper Binance]<br> > Stato: <span class="status blink highlight" style="color:var(--neon-green)">ENGAGED</span> | PnL: <span style="color:var(--neon-green)">+1.2%</span></p>
            <p>👁️ <strong>SQUADRA_DELTA</strong> [Order Flow]<br> > Stato: <span class="status blink highlight" style="color:var(--neon-blue)">SCANNING</span> | L2: <span style="color:var(--neon-blue)">SYNCED</span></p>
            <p>⚖️ <strong>SQUADRA_GAMMA</strong> [Pairs Trading Bitget]<br> > Stato: <span class="status blink highlight" style="color:var(--neon-pink)">ARBITRAGING</span> | Spread: <span style="color:var(--neon-pink)">0.45%</span></p>
        </div>
        
        <div class="panel">
            <h2>🛡️ PROTOCOLLO TRINITY</h2>
            <p style="text-align:center; font-weight:bold; color:var(--neon-green); border:1px solid var(--neon-green); padding:5px;">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</p>
            <p>🦇 <strong>Lo Strozzino</strong> [Funding Arb]<br> > Stato: <span class="status" style="color:var(--neon-blue)">ONLINE (BACKGROUND)</span></p>
            <p>🧮 <strong>Il Contabile</strong> [DCA]<br> > Stato: <span class="status" style="color:var(--neon-blue)">ONLINE (BACKGROUND)</span></p>
            <p>👼 <strong>L'Angelo Custode</strong> [MEV Arbitrum]<br> > Stato: <span class="status" style="color:var(--neon-blue)">ONLINE (BACKGROUND)</span></p>
        </div>
        
        <div class="panel">
            <h2>📊 METRICHE DI MERCATO</h2>
            <p>🔮 <strong>The Oracle</strong> [Binance Sentiment]<br> > Bias: <span class="highlight" style="color:var(--neon-green)">BULLISH 🚀</span> (Conf: 87%)</p>
            <p>🐳 <strong>Whale Tracker</strong><br> > Alert: <span class="highlight blink" style="color:var(--neon-pink)">LARGE TX DETECTED (12,450 ETH)</span></p>
            <p>⚡ <strong>Network Latency</strong><br> > Nuvola -> Binance: <span style="color:var(--neon-green)">12ms</span></p>
        </div>
    </div>
    
    <div style="margin-top: 2rem; text-align: center; font-size: 0.8rem; opacity: 0.5;">
        SYSTEM.NUVOLA.V2 // UNAUTHORIZED ACCESS STRICTLY PROHIBITED // ENCRYPTED CONNECTION
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
