from flask import Flask, render_template_string
import random
import time
import threading

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ORBITAL COMMAND [NUVOLA DASHBOARD]</title>
    <style>
        :root {
            --neon-green: #39ff14;
            --neon-blue: #00ffff;
            --neon-pink: #ff00ff;
            --neon-red: #ff003c;
            --dark-bg: #050505;
            --panel-bg: rgba(10, 20, 30, 0.85);
        }
        
        @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            background-color: var(--dark-bg);
            color: var(--neon-blue);
            font-family: 'Share Tech Mono', monospace;
            background-image: 
                linear-gradient(rgba(0, 255, 255, 0.05) 1px, transparent 1px),
                linear-gradient(90deg, rgba(0, 255, 255, 0.05) 1px, transparent 1px);
            background-size: 20px 20px;
            overflow-x: hidden;
            padding: 20px;
        }

        h1, h2, h3 {
            text-transform: uppercase;
            letter-spacing: 2px;
        }

        .header {
            text-align: center;
            padding: 20px 0;
            text-shadow: 0 0 10px var(--neon-blue), 0 0 20px var(--neon-blue);
            border-bottom: 2px solid var(--neon-blue);
            margin-bottom: 30px;
            animation: pulse 2s infinite;
        }

        .container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
        }

        .panel {
            background-color: var(--panel-bg);
            border: 1px solid var(--neon-blue);
            box-shadow: inset 0 0 10px rgba(0, 255, 255, 0.2), 0 0 15px rgba(0, 255, 255, 0.2);
            padding: 20px;
            position: relative;
            border-radius: 5px;
            transition: all 0.3s ease;
        }

        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; width: 100%; height: 2px;
            background: linear-gradient(90deg, transparent, var(--neon-blue), transparent);
        }

        .panel:hover {
            box-shadow: inset 0 0 15px rgba(0, 255, 255, 0.4), 0 0 25px rgba(0, 255, 255, 0.4);
            border-color: var(--neon-green);
        }

        .panel-title {
            color: var(--neon-pink);
            border-bottom: 1px dashed var(--neon-pink);
            padding-bottom: 10px;
            margin-bottom: 15px;
            text-shadow: 0 0 5px var(--neon-pink);
            font-size: 1.2em;
        }

        .item {
            margin-bottom: 15px;
            padding: 10px;
            background: rgba(0, 0, 0, 0.5);
            border-left: 3px solid var(--neon-blue);
        }

        .item-title {
            font-weight: bold;
            color: #fff;
            margin-bottom: 5px;
            display: flex;
            justify-content: space-between;
        }

        .status-online {
            color: var(--neon-green);
            text-shadow: 0 0 5px var(--neon-green);
            animation: blink 1.5s infinite;
        }

        .status-active {
            color: var(--neon-blue);
            text-shadow: 0 0 5px var(--neon-blue);
        }

        .metric-value {
            font-size: 1.1em;
            color: var(--neon-green);
        }

        .progress-bar {
            width: 100%;
            height: 5px;
            background: #222;
            margin-top: 5px;
            overflow: hidden;
            position: relative;
        }

        .progress {
            height: 100%;
            background: var(--neon-blue);
            box-shadow: 0 0 10px var(--neon-blue);
            transition: width 0.5s ease;
        }

        .metrics-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
        }

        .metric-box {
            background: rgba(0, 255, 255, 0.05);
            border: 1px solid rgba(0, 255, 255, 0.3);
            padding: 10px;
            text-align: center;
        }

        .metric-box.alert {
            border-color: var(--neon-red);
            color: var(--neon-red);
            animation: blink-fast 1s infinite;
        }

        /* Animations */
        @keyframes pulse {
            0% { text-shadow: 0 0 5px var(--neon-blue); }
            50% { text-shadow: 0 0 20px var(--neon-blue), 0 0 30px var(--neon-blue); }
            100% { text-shadow: 0 0 5px var(--neon-blue); }
        }

        @keyframes blink {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }

        @keyframes blink-fast {
            0%, 100% { opacity: 1; box-shadow: inset 0 0 10px var(--neon-red); }
            50% { opacity: 0.2; box-shadow: none; }
        }

        /* CRT Scanline Effect */
        .scanlines {
            position: fixed;
            top: 0; left: 0; width: 100vw; height: 100vh;
            background: linear-gradient(
                rgba(18, 16, 16, 0) 50%, 
                rgba(0, 0, 0, 0.25) 50%), 
                linear-gradient(90deg, rgba(255, 0, 0, 0.06), rgba(0, 255, 0, 0.02), rgba(0, 0, 255, 0.06));
            background-size: 100% 4px, 3px 100%;
            pointer-events: none;
            z-index: 9999;
        }
    </style>
</head>
<body>
    <div class="scanlines"></div>
    
    <div class="header">
        <h1>🌐 ORBITAL COMMAND 🌐</h1>
        <p>System Status: <span class="status-online">NOMINAL</span> | Sync: ACTIVE | Uptime: 99.99%</p>
        <div style="margin-top: 15px; padding: 10px; border: 1px solid var(--neon-green); display: inline-block; background: rgba(57, 255, 20, 0.1); box-shadow: 0 0 10px rgba(57, 255, 20, 0.2);">
            <span style="color: var(--neon-green); font-weight: bold; text-shadow: 0 0 5px var(--neon-green);">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</span>
        </div>
    </div>

    <div class="container">
        <!-- SEZIONE 1: SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <h2 class="panel-title">⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            
            <div class="item">
                <div class="item-title">
                    <span>🐺 SQUADRA_ALPHA</span>
                    <span class="status-online">ENGAGED</span>
                </div>
                <p>Ruolo: Scalper su Binance</p>
                <div class="metrics-grid" style="margin-top: 10px;">
                    <div class="metric-box">
                        <small>Win Rate</small><br>
                        <span class="metric-value" id="alpha-wr">68.4%</span>
                    </div>
                    <div class="metric-box">
                        <small>Trades/min</small><br>
                        <span class="metric-value" id="alpha-tpm">142</span>
                    </div>
                </div>
            </div>

            <div class="item" style="border-left-color: var(--neon-pink);">
                <div class="item-title">
                    <span>⚡ SQUADRA_DELTA</span>
                    <span class="status-online">ENGAGED</span>
                </div>
                <p>Ruolo: Order Flow Exploitation</p>
                <div class="progress-bar">
                    <div class="progress" style="width: 85%; background: var(--neon-pink); box-shadow: 0 0 10px var(--neon-pink);"></div>
                </div>
                <small style="color: #aaa;">Imbalance Detection: Alta</small>
            </div>

            <div class="item" style="border-left-color: var(--neon-green);">
                <div class="item-title">
                    <span>⚖️ SQUADRA_GAMMA</span>
                    <span class="status-online">ACTIVE</span>
                </div>
                <p>Ruolo: Pairs Trading su Bitget</p>
                <p><small>Spread BTC/ETH: <span class="metric-value" id="gamma-spread">0.0542</span></small></p>
            </div>
        </div>

        <!-- SEZIONE 2: PROTOCOLLO TRINITY -->
        <div class="panel" style="border-color: var(--neon-pink);">
            <h2 class="panel-title" style="color: var(--neon-blue); border-bottom-color: var(--neon-blue);">🔺 PROTOCOLLO TRINITY</h2>
            
            <div class="item">
                <div class="item-title">
                    <span>🦈 LO STROZZINO</span>
                    <span class="status-active">BACKGROUND</span>
                </div>
                <p>Funding Rate Arbitrage</p>
                <small>Harvesting yield from PERP vs SPOT</small>
                <div class="progress-bar">
                    <div class="progress" style="width: 100%; background: var(--neon-green); box-shadow: 0 0 10px var(--neon-green);"></div>
                </div>
            </div>

            <div class="item">
                <div class="item-title">
                    <span>🧮 IL CONTABILE</span>
                    <span class="status-active">BACKGROUND</span>
                </div>
                <p>Dynamic DCA Engine</p>
                <small>Accumulation Mode: ON (Dip Buyer)</small>
                <div class="progress-bar">
                    <div class="progress" style="width: 45%; background: var(--neon-blue);"></div>
                </div>
            </div>

            <div class="item">
                <div class="item-title">
                    <span>👼 L'ANGELO CUSTODE</span>
                    <span class="status-active">BACKGROUND</span>
                </div>
                <p>MEV Arbitrum Protection</p>
                <small>Front-running the front-runners. Mempool secured.</small>
                <div class="progress-bar">
                    <div class="progress" style="width: 100%; background: #fff; box-shadow: 0 0 10px #fff;"></div>
                </div>
            </div>
        </div>

        <!-- SEZIONE 3: METRICHE DI MERCATO -->
        <div class="panel" style="border-color: var(--neon-green);">
            <h2 class="panel-title" style="color: var(--neon-green); border-bottom-color: var(--neon-green);">👁️ METRICHE DI MERCATO</h2>
            
            <div class="item">
                <div class="item-title">
                    <span>🔮 THE ORACLE</span>
                    <span class="status-online">SYNCED</span>
                </div>
                <p>Binance Sentiment Analysis</p>
                <div class="metrics-grid" style="margin-top: 10px;">
                    <div class="metric-box">
                        <small>Fear & Greed</small><br>
                        <span class="metric-value" style="color: var(--neon-pink);" id="oracle-fg">74 (Greed)</span>
                    </div>
                    <div class="metric-box">
                        <small>Long/Short Ratio</small><br>
                        <span class="metric-value" id="oracle-ls">1.24</span>
                    </div>
                </div>
            </div>

            <div class="item">
                <div class="item-title">
                    <span>🐋 WHALE TRACKER</span>
                    <span class="status-online">SCANNING</span>
                </div>
                <p>On-Chain Movement Detection</p>
                <div class="metric-box alert" id="whale-alert" style="margin-top: 10px;">
                    🚨 ALERT: 5,420 BTC moved to Coinbase 🚨
                </div>
                <div class="progress-bar">
                    <div class="progress" style="width: 100%; background: var(--neon-red); box-shadow: 0 0 10px var(--neon-red);"></div>
                </div>
            </div>
            
            <div class="item">
                <div class="item-title">
                    <span>📡 NETWORK LATENCY</span>
                    <span class="status-active">OPTIMAL</span>
                </div>
                <div class="metrics-grid">
                    <div>Binance: <span style="color: var(--neon-green);">12ms</span></div>
                    <div>Bitget: <span style="color: var(--neon-green);">18ms</span></div>
                    <div>Arbitrum: <span style="color: var(--neon-green);">45ms</span></div>
                </div>
            </div>
        </div>
    </div>

    <script>
        // Simple script to make numbers flicker/update for the cyberpunk feel
        setInterval(() => {
            // Update Trades per min
            const tpm = document.getElementById('alpha-tpm');
            let currentTpm = parseInt(tpm.innerText);
            tpm.innerText = currentTpm + Math.floor(Math.random() * 5) - 2;

            // Update Spread
            const spread = document.getElementById('gamma-spread');
            let currentSpread = parseFloat(spread.innerText);
            spread.innerText = (currentSpread + (Math.random() * 0.002 - 0.001)).toFixed(4);
            
            // Randomly flash whale alert
            const alertBox = document.getElementById('whale-alert');
            if (Math.random() > 0.8) {
                alertBox.style.display = 'block';
                const amounts = [1200, 3450, 8900, 5420, 10500];
                const exchanges = ['Coinbase', 'Binance', 'Kraken', 'Unknown Wallet'];
                alertBox.innerText = `🚨 ALERT: ${amounts[Math.floor(Math.random()*amounts.length)].toLocaleString()} BTC moved to ${exchanges[Math.floor(Math.random()*exchanges.length)]} 🚨`;
            }
        }, 2500);
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    # Esegue su 0.0.0.0 per permettere accesso esterno, porta 5000 di default
    app.run(host='0.0.0.0', port=5000, debug=False)
