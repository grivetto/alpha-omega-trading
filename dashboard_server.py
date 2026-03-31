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
            --neon-cyan: #0ff;
            --neon-pink: #f0f;
            --neon-green: #39ff14;
            --bg-dark: #0a0a0a;
            --panel-bg: rgba(20, 20, 25, 0.9);
        }
        body {
            background-color: var(--bg-dark);
            color: var(--neon-cyan);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            overflow-x: hidden;
        }
        h1 {
            text-align: center;
            color: var(--neon-pink);
            text-shadow: 0 0 10px var(--neon-pink), 0 0 20px var(--neon-pink);
            font-size: 2.5em;
            margin-bottom: 30px;
            text-transform: uppercase;
            letter-spacing: 4px;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
        }
        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-cyan);
            border-radius: 5px;
            padding: 20px;
            box-shadow: 0 0 10px rgba(0, 255, 255, 0.2), inset 0 0 10px rgba(0, 255, 255, 0.1);
            position: relative;
            overflow: hidden;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; width: 100%; height: 2px;
            background: linear-gradient(90deg, transparent, var(--neon-cyan), transparent);
            animation: scanline 2s linear infinite;
        }
        @keyframes scanline {
            0% { transform: translateX(-100%); }
            100% { transform: translateX(100%); }
        }
        .panel-title {
            color: var(--neon-green);
            font-size: 1.2em;
            margin-bottom: 15px;
            text-shadow: 0 0 5px var(--neon-green);
            border-bottom: 1px dashed var(--neon-green);
            padding-bottom: 5px;
        }
        .item { margin-bottom: 10px; display: flex; justify-content: space-between; }
        .status-online { color: var(--neon-green); text-shadow: 0 0 5px var(--neon-green); animation: blink 1.5s infinite; }
        .status-active { color: var(--neon-cyan); text-shadow: 0 0 5px var(--neon-cyan); }
        @keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
        .glitch { animation: glitch 1s linear infinite; }
        @keyframes glitch {
            2%, 64% { transform: translate(2px,0) skew(0deg); }
            4%, 60% { transform: translate(-2px,0) skew(0deg); }
            62% { transform: translate(0,0) skew(5deg); }
        }
        table { width: 100%; border-collapse: collapse; }
        th, td { text-align: left; padding: 5px; border-bottom: 1px solid rgba(0, 255, 255, 0.2); }
        th { color: var(--neon-pink); }
    </style>
</head>
<body>
    <h1 class="glitch">🛰️ NUVOLA ORBITAL COMMAND 🛰️</h1>
    <div style="text-align: center; color: var(--neon-green); font-size: 1.2em; margin-bottom: 20px; text-shadow: 0 0 5px var(--neon-green); animation: blink 2s infinite;">
        ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
    </div>
    
    <div class="grid">
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <div class="panel-title">⚔️ SQUADRE D'ASSALTO (HFT)</div>
            <div class="item">
                <span>🐺 SQUADRA_ALPHA (Scalper Binance)</span>
                <span class="status-active">ENGAGED</span>
            </div>
            <div class="item">
                <span>⚡ SQUADRA_DELTA (Order Flow)</span>
                <span class="status-active">ANALYZING</span>
            </div>
            <div class="item">
                <span>⚖️ SQUADRA_GAMMA (Pairs Bitget)</span>
                <span class="status-active">ARBITRAGING</span>
            </div>
            <div style="margin-top: 15px; font-size: 0.8em; color: #888;">
                > High-Frequency routines operational.<br>
                > Latency: 12ms
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <div class="panel-title">🔺 PROTOCOLLO TRINITY</div>
            <div class="item">
                <span>🕴️ Lo Strozzino (Funding Arb)</span>
                <span class="status-online">ONLINE</span>
            </div>
            <div class="item">
                <span>🧮 Il Contabile (DCA Engine)</span>
                <span class="status-online">ONLINE</span>
            </div>
            <div class="item">
                <span>🛡️ L'Angelo Custode (MEV Arbitrum)</span>
                <span class="status-online">GUARDING</span>
            </div>
            <div style="margin-top: 15px; font-size: 0.8em; color: #888;">
                > Background wealth generation active.<br>
                > Risk protocol: STRICT
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <div class="panel-title">📊 METRICHE DI MERCATO</div>
            <table>
                <tr><th>Sensore</th><th>Valore</th><th>Stato</th></tr>
                <tr><td>🔮 The Oracle (Sentiment)</td><td>BULLISH</td><td class="status-online">SYNCED</td></tr>
                <tr><td>🐋 Whale Tracker</td><td>ACCUMULATING</td><td class="status-online">SYNCED</td></tr>
                <tr><td>💧 Liquidity Siphon</td><td>Stable</td><td class="status-active">DRAINING</td></tr>
            </table>
            <div style="margin-top: 15px; font-size: 0.8em; color: #888;">
                > Live data feeds established.<br>
                > Awaiting signal trigger...
            </div>
        </div>
    </div>
    
    <div style="text-align: center; margin-top: 40px; font-size: 0.8em; opacity: 0.5;">
        SYSTEM.UPTIME // ENCRYPTED CONNECTION // QUANTITATIVE MILITARY GRADE
    </div>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
