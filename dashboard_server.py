from flask import Flask, render_template_string
import time
import random

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
            --neon-green: #0f0;
            --neon-cyan: #0ff;
            --neon-magenta: #f0f;
            --dark-bg: #050505;
            --panel-bg: #111;
        }
        body {
            background-color: var(--dark-bg);
            color: var(--neon-green);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            text-transform: uppercase;
            overflow-x: hidden;
        }
        h1, h2, h3 {
            text-shadow: 0 0 10px var(--neon-green);
            margin-top: 0;
        }
        h1 { text-align: center; border-bottom: 2px solid var(--neon-green); padding-bottom: 10px; font-size: 2.5em; letter-spacing: 5px; }
        .container {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-top: 20px;
        }
        .panel {
            background-color: var(--panel-bg);
            border: 1px solid var(--neon-cyan);
            box-shadow: 0 0 15px rgba(0, 255, 255, 0.2);
            padding: 20px;
            position: relative;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; width: 10px; height: 10px;
            border-top: 2px solid var(--neon-cyan);
            border-left: 2px solid var(--neon-cyan);
        }
        .panel::after {
            content: '';
            position: absolute;
            bottom: 0; right: 0; width: 10px; height: 10px;
            border-bottom: 2px solid var(--neon-cyan);
            border-right: 2px solid var(--neon-cyan);
        }
        .panel.magenta {
            border-color: var(--neon-magenta);
            box-shadow: 0 0 15px rgba(255, 0, 255, 0.2);
            color: var(--neon-magenta);
        }
        .panel.magenta h2 { text-shadow: 0 0 10px var(--neon-magenta); }
        .panel.magenta::before, .panel.magenta::after { border-color: var(--neon-magenta); }
        
        ul { list-style-type: none; padding: 0; }
        li { margin-bottom: 10px; border-left: 2px solid; padding-left: 10px; background: rgba(255,255,255,0.05); padding: 10px; }
        .status-online { color: #0f0; animation: blink 1.5s infinite; }
        .status-active { color: #0ff; }
        
        @keyframes blink { 0% { opacity: 1; } 50% { opacity: 0.4; } 100% { opacity: 1; } }
        @keyframes scanline {
            0% { transform: translateY(-100%); }
            100% { transform: translateY(100vh); }
        }
        .scanlines {
            position: fixed; top: 0; left: 0; width: 100vw; height: 100vh;
            background: linear-gradient(to bottom, rgba(255,255,255,0), rgba(255,255,255,0) 50%, rgba(0,0,0,0.2) 50%, rgba(0,0,0,0.2));
            background-size: 100% 4px;
            pointer-events: none; z-index: 100; opacity: 0.3;
        }
        .glitch-bar {
            width: 100%; height: 2px; background: var(--neon-cyan);
            position: absolute; top: 0; left: 0; opacity: 0.5;
            animation: scanline 8s linear infinite; pointer-events: none;
        }
        .grid-full { grid-column: 1 / -1; }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; }
        th, td { border: 1px solid rgba(0,255,255,0.3); padding: 8px; text-align: left; }
        th { color: var(--neon-cyan); }
    </style>
</head>
<body>
    <div class="scanlines"></div>
    <div class="glitch-bar"></div>
    
    <h1>👁️ NUVOLA // ORBITAL COMMAND 👁️</h1>
    <div style="text-align: center; margin-bottom: 20px; font-size: 1.2em; color: var(--neon-magenta); text-shadow: 0 0 10px var(--neon-magenta); border: 1px dashed var(--neon-magenta); padding: 10px; display: inline-block; left: 50%; position: relative; transform: translateX(-50%);">
        ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
    </div>
    
    <div class="container">
        <!-- SQUADRE D'ASSALTO -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <ul>
                <li style="border-color: var(--neon-green);">
                    <strong>[ ALPHA ]</strong> Scalper su Binance <br>
                    Stato: <span class="status-online">ENGAGED</span> | PNL 24h: <span id="pnl-alpha" style="color:#0f0;">+1.42%</span> | Latency: 12ms
                </li>
                <li style="border-color: var(--neon-cyan);">
                    <strong>[ DELTA ]</strong> Order Flow Analytics <br>
                    Stato: <span class="status-active">MONITORING</span> | Order Imbalance: 68% BUY | Latency: 8ms
                </li>
                <li style="border-color: var(--neon-magenta);">
                    <strong>[ GAMMA ]</strong> Pairs Trading su Bitget <br>
                    Stato: <span class="status-online">ARBITRAGING</span> | Spread: 0.15% | Latency: 24ms
                </li>
            </ul>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel magenta">
            <h2>🔺 PROTOCOLLO TRINITY</h2>
            <ul>
                <li style="border-color: var(--neon-magenta);">
                    <strong>💀 LO STROZZINO</strong> (Funding Arb)<br>
                    Stato: <span class="status-online">ONLINE [BACKGROUND]</span> | Posizione: SHORT $BTC | APR: 18.5%
                </li>
                <li style="border-color: var(--neon-magenta);">
                    <strong>🧮 IL CONTABILE</strong> (Smart DCA)<br>
                    Stato: <span class="status-online">ONLINE [BACKGROUND]</span> | Accumulo: $ETH / $SOL | Next Buy: -4h
                </li>
                <li style="border-color: var(--neon-magenta);">
                    <strong>👼 L'ANGELO CUSTODE</strong> (MEV Arbitrum)<br>
                    Stato: <span class="status-online">ONLINE [BACKGROUND]</span> | Flashbots: Connected | Block: <span id="block-num">1849201</span>
                </li>
            </ul>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel grid-full">
            <h2>📊 METRICHE DI MERCATO & INTEL</h2>
            <div style="display: flex; gap: 20px;">
                <div style="flex: 1;">
                    <h3 style="color: var(--neon-cyan);">🔮 THE ORACLE (Binance Sentiment)</h3>
                    <table>
                        <tr><th>Asset</th><th>Sentiment Score</th><th>Signal</th></tr>
                        <tr><td>BTC/USDT</td><td>82/100</td><td style="color:#0f0;">STRONG BUY</td></tr>
                        <tr><td>ETH/USDT</td><td>65/100</td><td style="color:#0f0;">BUY</td></tr>
                        <tr><td>SOL/USDT</td><td>40/100</td><td style="color:#fa0;">NEUTRAL</td></tr>
                    </table>
                </div>
                <div style="flex: 1;">
                    <h3 style="color: var(--neon-cyan);">🐋 WHALE TRACKER (On-Chain)</h3>
                    <table>
                        <tr><th>Time</th><th>Tx Value</th><th>Flow</th></tr>
                        <tr><td>Just now</td><td>$45.2M USDT</td><td>Exchange Inflow</td></tr>
                        <tr><td>- 2 min</td><td>1,200 BTC</td><td>Cold Wallet</td></tr>
                        <tr><td>- 5 min</td><td>10,000 ETH</td><td>DEX Swap</td></tr>
                    </table>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        // Randomize numbers slightly to simulate live dashboard
        setInterval(() => {
            const pnl = (Math.random() * 3).toFixed(2);
            document.getElementById('pnl-alpha').innerText = `+${pnl}%`;
            
            const block = parseInt(document.getElementById('block-num').innerText) + Math.floor(Math.random() * 3);
            document.getElementById('block-num').innerText = block;
        }, 3000);
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, threaded=True)