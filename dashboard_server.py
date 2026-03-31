from flask import Flask, render_template_string

app = Flask(__name__)

HTML = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ORBITAL COMMAND | Nuvola Dashboard</title>
    <style>
        :root { --neon-green: #39ff14; --neon-blue: #0ff; --neon-red: #ff073a; --bg: #050505; --panel: #111; }
        body { background-color: var(--bg); color: var(--neon-green); font-family: 'Courier New', Courier, monospace; margin: 0; padding: 20px; overflow-x: hidden; }
        h1, h2 { text-transform: uppercase; text-shadow: 0 0 10px var(--neon-green); border-bottom: 1px solid var(--neon-green); padding-bottom: 5px; margin-bottom: 15px;}
        h1 { text-align: center; font-size: 2.5em; letter-spacing: 5px; color: var(--neon-blue); text-shadow: 0 0 15px var(--neon-blue); border-bottom: 2px solid var(--neon-blue); margin-top: 10px; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; margin-top: 20px; }
        .panel { background: var(--panel); border: 1px solid var(--neon-green); padding: 15px; box-shadow: 0 0 10px rgba(57, 255, 20, 0.2); border-radius: 5px; }
        .panel:hover { box-shadow: 0 0 20px rgba(57, 255, 20, 0.6); }
        .status-online { color: var(--neon-green); animation: blink 2s infinite; font-weight: bold; }
        .status-active { color: var(--neon-blue); text-shadow: 0 0 5px var(--neon-blue); }
        .data-row { display: flex; justify-content: space-between; margin: 8px 0; border-bottom: 1px dashed #333; padding-bottom: 2px; }
        @keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
        .emoji { font-size: 1.2em; }
        .subtitle { text-align: center; margin-bottom: 30px; font-weight: bold; text-shadow: 0 0 5px var(--neon-green); }
    </style>
</head>
<body>
    <h1>🛰️ ORBITAL COMMAND 🛰️</h1>
    <div class="subtitle">[ SYSTEM SECURE ] | [ UPLINK ACTIVE ] | [ QUANTUM ENGINE: NOMINAL ]</div>
    <div style="text-align: center; color: var(--neon-blue); font-weight: bold; margin-bottom: 20px; font-size: 1.2em; text-shadow: 0 0 10px var(--neon-blue);">
        ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
    </div>

    <div class="grid">
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <div class="data-row"><span>SQUADRA_ALPHA <span class="emoji">⚡</span> (Scalper - Binance)</span> <span class="status-online">[ ENGAGED ]</span></div>
            <div class="data-row"><span>> Latency:</span> <span>12ms</span></div>
            <div class="data-row"><span>> 1h PnL:</span> <span style="color:var(--neon-green);">+4.2%</span></div>
            <br>
            <div class="data-row"><span>SQUADRA_DELTA <span class="emoji">🌊</span> (Order Flow)</span> <span class="status-online">[ ENGAGED ]</span></div>
            <div class="data-row"><span>> Imbalance:</span> <span>Long Bias (68%)</span></div>
            <div class="data-row"><span>> 1h PnL:</span> <span style="color:var(--neon-green);">+1.8%</span></div>
            <br>
            <div class="data-row"><span>SQUADRA_GAMMA <span class="emoji">⚖️</span> (Pairs - Bitget)</span> <span class="status-online">[ ENGAGED ]</span></div>
            <div class="data-row"><span>> Spread Z-Score:</span> <span>-2.1 (Reverting)</span></div>
            <div class="data-row"><span>> 1h PnL:</span> <span style="color:var(--neon-green);">+0.9%</span></div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2 style="color: var(--neon-blue); text-shadow: 0 0 10px var(--neon-blue); border-color: var(--neon-blue);">🛡️ PROTOCOLLO TRINITY</h2>
            <div class="data-row"><span>Lo Strozzino <span class="emoji">🧛</span> (Funding Arb)</span> <span class="status-active">[ STEALTH ]</span></div>
            <div class="data-row"><span>> Target:</span> <span>SOL/USDT Perp</span></div>
            <div class="data-row"><span>> APY Capture:</span> <span>42.5%</span></div>
            <br>
            <div class="data-row"><span>Il Contabile <span class="emoji">🧮</span> (DCA)</span> <span class="status-active">[ STEALTH ]</span></div>
            <div class="data-row"><span>> Next Buy:</span> <span>BTC @ $61,200</span></div>
            <div class="data-row"><span>> Status:</span> <span>Accumulating</span></div>
            <br>
            <div class="data-row"><span>L'Angelo Custode <span class="emoji">👼</span> (MEV Arbitrum)</span> <span class="status-active">[ STEALTH ]</span></div>
            <div class="data-row"><span>> Mempool:</span> <span>Scanning</span></div>
            <div class="data-row"><span>> Last Snipe:</span> <span>4m ago (0.12 ETH)</span></div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <h2 style="color: var(--neon-red); text-shadow: 0 0 10px var(--neon-red); border-color: var(--neon-red);">📡 METRICHE DI MERCATO</h2>
            <div class="data-row"><span>The Oracle <span class="emoji">👁️</span> (Binance Sentiment)</span> <span class="status-online">[ SYNCED ]</span></div>
            <div class="data-row"><span>> Global Fear/Greed:</span> <span>74 (Greed)</span></div>
            <div class="data-row"><span>> AI Signal:</span> <span>BULLISH CONVERGENCE</span></div>
            <br>
            <div class="data-row"><span>Whale Tracker <span class="emoji">🐋</span></span> <span class="status-online">[ SYNCED ]</span></div>
            <div class="data-row"><span>> Large TXs (24h):</span> <span>1,240 (Net Inflow)</span></div>
            <div class="data-row"><span>> Alert:</span> <span>5000 BTC moved to Coinbase</span></div>
        </div>
    </div>
    
    <div style="margin-top: 30px; text-align: center; font-size: 0.8em; color: #555;">
        ORBITAL COMMAND v3.0 | UNAUTHORIZED ACCESS WILL BE NEUTRALIZED
    </div>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
