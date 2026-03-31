from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Nuvola Orbital Command</title>
    <style>
        :root {
            --neon-green: #39ff14;
            --neon-red: #ff073a;
            --neon-blue: #0ff;
            --bg-color: #050505;
            --panel-bg: #111;
        }
        body {
            background-color: var(--bg-color);
            color: var(--neon-green);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            text-transform: uppercase;
        }
        h1, h2, h3 {
            text-shadow: 0 0 5px var(--neon-green), 0 0 10px var(--neon-green);
            text-align: center;
            border-bottom: 2px solid var(--neon-green);
            padding-bottom: 10px;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }
        .panel {
            background-color: var(--panel-bg);
            border: 1px solid var(--neon-green);
            padding: 15px;
            box-shadow: 0 0 10px rgba(57, 255, 20, 0.2);
            border-radius: 5px;
        }
        .panel h2 {
            color: var(--neon-blue);
            text-shadow: 0 0 5px var(--neon-blue);
            border-bottom: 1px solid var(--neon-blue);
            font-size: 1.2em;
        }
        .status-online {
            color: var(--neon-green);
            text-shadow: 0 0 5px var(--neon-green);
            animation: blink 2s infinite;
        }
        .status-warning {
            color: #ffea00;
            text-shadow: 0 0 5px #ffea00;
        }
        .status-offline {
            color: var(--neon-red);
            text-shadow: 0 0 5px var(--neon-red);
        }
        @keyframes blink {
            0% { opacity: 1; }
            50% { opacity: 0.5; }
            100% { opacity: 1; }
        }
        .metric {
            display: flex;
            justify-content: space-between;
            margin: 10px 0;
            border-bottom: 1px dashed #333;
            padding-bottom: 5px;
        }
        .log-box {
            height: 120px;
            overflow-y: hidden;
            font-size: 0.9em;
            color: #888;
            background: #000;
            padding: 10px;
            border: 1px solid #333;
            margin-top: 15px;
            font-family: 'Courier New', Courier, monospace;
        }
        .glow-text {
            animation: pulse 1.5s infinite;
        }
        @keyframes pulse {
            0% { text-shadow: 0 0 5px var(--neon-green); }
            50% { text-shadow: 0 0 20px var(--neon-green); }
            100% { text-shadow: 0 0 5px var(--neon-green); }
        }
    </style>
</head>
<body>
    <h1>🛰️ NUVOLA ORBITAL COMMAND 🛰️</h1>
    <div style="text-align: center; margin-bottom: 30px;">
        SYSTEM STATUS: <span class="status-online glow-text">DEFCON 5 - ALL SYSTEMS NOMINAL</span><br><br>
        <span class="status-online glow-text" style="font-size: 1.2em;">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</span>
    </div>

    <div class="grid">
        <!-- SQUADRE D'ASSALTO -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <div class="metric">
                <span>🐺 SQUADRA_ALPHA (Binance Scalper)</span>
                <span class="status-online">[ ENGAGED ]</span>
            </div>
            <div class="metric">
                <span>⚡ SQUADRA_DELTA (Order Flow)</span>
                <span class="status-online">[ ACTIVE ]</span>
            </div>
            <div class="metric">
                <span>⚖️ SQUADRA_GAMMA (Bitget Pairs)</span>
                <span class="status-online">[ ARBITRAGING ]</span>
            </div>
            <div class="log-box">
                > ALPHA: Executed buy BTC/USDT @ 62450.50<br>
                > DELTA: Detecting heavy spoofing on ETH book, adjusting quotes.<br>
                > GAMMA: Spread 0.15% - waiting for target 0.2%<br>
                > ALPHA: Trailing stop updated...
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2>🔺 PROTOCOLLO TRINITY</h2>
            <div class="metric">
                <span>🕴️ Lo Strozzino (Funding Arb)</span>
                <span class="status-online">[ HARVESTING ]</span>
            </div>
            <div class="metric">
                <span>🧮 Il Contabile (DCA)</span>
                <span class="status-online">[ ACCUMULATING ]</span>
            </div>
            <div class="metric">
                <span>🛡️ L'Angelo Custode (MEV Arbitrum)</span>
                <span class="status-online">[ PROTECTING ]</span>
            </div>
            <div class="log-box">
                > STROZZINO: Short PERP, Long SPOT (APR: 18.4%)<br>
                > CONTABILE: Next BTC DCA scheduled in 14h 22m<br>
                > ANGELO: Arbitrum mempool scanned. 0 front-run threats.<br>
                > TRINITY: SYNC COMPLETE.
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <h2>📊 THE ORACLE & WHALE TRACKER</h2>
            <div class="metric">
                <span>👁️ Binance Sentiment Index</span>
                <span style="color: var(--neon-green);">GREED (72)</span>
            </div>
            <div class="metric">
                <span>🐋 Whale Movement Alert</span>
                <span class="status-warning">5000 BTC -> Coinbase</span>
            </div>
            <div class="metric">
                <span>🌊 Liquidity Heatmap</span>
                <span>CONCENTRATED @ 65K</span>
            </div>
            <div class="metric">
                <span>🔥 Network Gas (ETH)</span>
                <span>12 GWEI</span>
            </div>
            <div class="log-box">
                > ORACLE: Aggregating orderbook depth...<br>
                > ORACLE: Long/Short ratio 1.24<br>
                > WHALE_TRACKER: Alert flagged. Monitoring addresses.<br>
                > SYSTEM: Awaiting commands...
            </div>
        </div>
    </div>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    # Esegue su 0.0.0.0 per essere accessibile dalla rete, porta 5000
    app.run(host='0.0.0.0', port=5000, debug=False)
