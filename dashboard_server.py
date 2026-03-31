from flask import Flask, render_template_string
import threading
import time

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Nuvola Orbital Command 🌌</title>
    <style>
        :root {
            --neon-green: #39ff14;
            --neon-blue: #0ff;
            --neon-pink: #ff00ff;
            --neon-red: #ff3131;
            --bg-color: #0a0a0a;
            --panel-bg: rgba(15, 15, 20, 0.85);
            --border-color: #1a1a2e;
        }
        body {
            background-color: var(--bg-color);
            color: var(--neon-green);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            background-image: 
                linear-gradient(rgba(0, 255, 0, 0.03) 1px, transparent 1px),
                linear-gradient(90deg, rgba(0, 255, 0, 0.03) 1px, transparent 1px);
            background-size: 20px 20px;
        }
        h1, h2, h3 {
            text-transform: uppercase;
            text-shadow: 0 0 10px currentColor;
        }
        h1 {
            color: var(--neon-blue);
            text-align: center;
            border-bottom: 2px solid var(--neon-blue);
            padding-bottom: 10px;
            letter-spacing: 3px;
            animation: flicker 3s infinite;
        }
        .grid-container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }
        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-green);
            border-radius: 5px;
            padding: 15px;
            box-shadow: 0 0 15px rgba(57, 255, 20, 0.2) inset;
            position: relative;
            overflow: hidden;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; height: 2px;
            background: var(--neon-green);
            box-shadow: 0 0 10px var(--neon-green);
        }
        .panel.blue {
            border-color: var(--neon-blue);
            color: var(--neon-blue);
            box-shadow: 0 0 15px rgba(0, 255, 255, 0.2) inset;
        }
        .panel.blue::before { background: var(--neon-blue); box-shadow: 0 0 10px var(--neon-blue); }
        .panel.pink {
            border-color: var(--neon-pink);
            color: var(--neon-pink);
            box-shadow: 0 0 15px rgba(255, 0, 255, 0.2) inset;
        }
        .panel.pink::before { background: var(--neon-pink); box-shadow: 0 0 10px var(--neon-pink); }
        
        .status-indicator {
            display: inline-block;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background-color: var(--neon-green);
            box-shadow: 0 0 8px var(--neon-green);
            margin-right: 10px;
            animation: pulse 1.5s infinite;
        }
        .status-indicator.offline {
            background-color: var(--neon-red);
            box-shadow: 0 0 8px var(--neon-red);
            animation: none;
        }
        .data-row {
            display: flex;
            justify-content: space-between;
            margin: 8px 0;
            border-bottom: 1px dashed rgba(255, 255, 255, 0.1);
            padding-bottom: 4px;
        }
        .glitch {
            position: relative;
        }
        .glitch::before, .glitch::after {
            content: attr(data-text);
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
        }
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.4; }
            100% { opacity: 1; }
        }
        @keyframes flicker {
            0%, 19.999%, 22%, 62.999%, 64%, 64.999%, 70%, 100% { opacity: 1; text-shadow: 0 0 15px currentColor; }
            20%, 21.999%, 63%, 63.999%, 65%, 69.999% { opacity: 0.4; text-shadow: none; }
        }
        .typing {
            overflow: hidden;
            white-space: nowrap;
            border-right: 2px solid;
            animation: typing 3.5s steps(40, end), blink-caret .75s step-end infinite;
        }
        @keyframes typing { from { width: 0 } to { width: 100% } }
        @keyframes blink-caret { from, to { border-color: transparent } 50% { border-color: currentColor; } }
    </style>
</head>
<body>

    <h1 class="glitch" data-text="🚀 NUVOLA ORBITAL COMMAND 🚀">🚀 NUVOLA ORBITAL COMMAND 🚀</h1>
    <p class="typing">>_ INIZIALIZZAZIONE SISTEMI QUANTITATIVI... [OK]</p>
    <div style="background: rgba(57, 255, 20, 0.1); border: 1px solid var(--neon-green); padding: 10px; text-align: center; margin: 10px 0; font-weight: bold; text-shadow: 0 0 5px var(--neon-green);">
        ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
    </div>
    
    <div class="grid-container">
        
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <div class="data-row">
                <span><span class="status-indicator"></span>🐺 SQUADRA_ALPHA</span>
                <span>[SCALPER: BINANCE]</span>
            </div>
            <div class="data-row" style="color: #aaa; font-size: 0.85em;">
                <span>🎯 Target: BTC/USDT | PNL Oggi: +$420.69</span>
            </div>
            <div class="data-row">
                <span><span class="status-indicator"></span>🦅 SQUADRA_DELTA</span>
                <span>[ORDER FLOW]</span>
            </div>
            <div class="data-row" style="color: #aaa; font-size: 0.85em;">
                <span>🎯 Analisi CVD & Liquidity Voids | Latency: 12ms</span>
            </div>
            <div class="data-row">
                <span><span class="status-indicator"></span>🦂 SQUADRA_GAMMA</span>
                <span>[PAIRS TRADING]</span>
            </div>
            <div class="data-row" style="color: #aaa; font-size: 0.85em;">
                <span>🎯 ETH/SOL Spread: 0.045 | Piattaforma: Bitget</span>
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel blue">
            <h2>🔮 PROTOCOLLO TRINITY</h2>
            <div class="data-row">
                <span><span class="status-indicator"></span>🕴️ LO STROZZINO</span>
                <span>[FUNDING ARB]</span>
            </div>
            <div class="data-row" style="color: #aaa; font-size: 0.85em;">
                <span>💰 Yield: 24.5% APY | Esposizione Delta Neutral</span>
            </div>
            <div class="data-row">
                <span><span class="status-indicator"></span>🧮 IL CONTABILE</span>
                <span>[SMART DCA]</span>
            </div>
            <div class="data-row" style="color: #aaa; font-size: 0.85em;">
                <span>📉 Accumulo Algoritmico | Zscore: -2.1</span>
            </div>
            <div class="data-row">
                <span><span class="status-indicator"></span>👼 L'ANGELO CUSTODE</span>
                <span>[MEV ARBITRUM]</span>
            </div>
            <div class="data-row" style="color: #aaa; font-size: 0.85em;">
                <span>⚡ Flashbots | Tx Inviate: 1337 | Frontrun EV: +$50</span>
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel pink">
            <h2>📊 METRICHE DI MERCATO</h2>
            <div class="data-row">
                <span>👁️ THE ORACLE (Sentiment)</span>
                <span>BULLISH [78%]</span>
            </div>
            <div class="data-row">
                <span>🐋 WHALE TRACKER</span>
                <span>ACCUMULO MASSIVO</span>
            </div>
            <div class="data-row">
                <span>🔥 FEAR & GREED</span>
                <span>65 [GREED]</span>
            </div>
            <div class="data-row">
                <span>🌊 LIQUIDITY HEATMAP</span>
                <span>$72K CLUSTER</span>
            </div>
            <div style="margin-top: 15px; border: 1px solid var(--neon-pink); padding: 5px; text-align: center;">
                <span style="animation: pulse 2s infinite;">[ SCANNING MEMPOOL... ]</span>
            </div>
        </div>

    </div>
    
    <div style="margin-top: 20px; text-align: center; color: #555; font-size: 0.8em;">
        SYSTEM UPTIME: 99.99% | CORE TEMP: 45°C | CONNECTION: ENCRYPTED
    </div>

    <script>
        setInterval(() => {
        }, 3000);
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
