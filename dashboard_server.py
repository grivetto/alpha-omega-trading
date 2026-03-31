from flask import Flask, render_template_string
import threading
import time
import random
import os

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NUVOLA ORBITAL COMMAND // V2.0</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&family=Rajdhani:wght@500;700&display=swap');
        :root {
            --neon-green: #00ff00;
            --neon-blue: #00f3ff;
            --neon-pink: #ff00ff;
            --neon-red: #ff003c;
            --neon-yellow: #fcee0a;
            --dark-bg: #030303;
            --panel-bg: rgba(5, 10, 5, 0.85);
            --border-glow: 0 0 10px rgba(0, 255, 0, 0.5);
        }
        
        body {
            background-color: var(--dark-bg);
            color: var(--neon-green);
            font-family: 'Rajdhani', sans-serif;
            margin: 0;
            padding: 20px;
            background-image: 
                radial-gradient(circle at 50% 50%, rgba(0, 50, 0, 0.2) 0%, transparent 60%),
                linear-gradient(rgba(0, 255, 0, 0.05) 1px, transparent 1px),
                linear-gradient(90deg, rgba(0, 255, 0, 0.05) 1px, transparent 1px);
            background-size: 100% 100%, 30px 30px, 30px 30px;
            overflow-x: hidden;
        }

        /* CRT Effect */
        body::after {
            content: " ";
            display: block;
            position: fixed;
            top: 0;
            left: 0;
            bottom: 0;
            right: 0;
            background: linear-gradient(rgba(18, 16, 16, 0) 50%, rgba(0, 0, 0, 0.25) 50%), linear-gradient(90deg, rgba(255, 0, 0, 0.06), rgba(0, 255, 0, 0.02), rgba(0, 0, 255, 0.06));
            z-index: 2;
            background-size: 100% 2px, 3px 100%;
            pointer-events: none;
        }

        h1, h2, h3 {
            font-family: 'Orbitron', sans-serif;
            margin: 0 0 15px 0;
            letter-spacing: 2px;
        }

        h1 {
            color: var(--neon-blue);
            text-shadow: 0 0 10px var(--neon-blue), 0 0 20px var(--neon-blue), 0 0 40px var(--neon-blue);
            text-align: center;
            font-size: 2.5em;
            border-bottom: 2px solid var(--neon-blue);
            padding-bottom: 10px;
            margin-bottom: 30px;
            text-transform: uppercase;
        }

        .header-status {
            display: flex;
            justify-content: space-between;
            font-size: 1.2em;
            margin-bottom: 30px;
            padding: 10px;
            background: rgba(0, 243, 255, 0.1);
            border: 1px solid var(--neon-blue);
            box-shadow: inset 0 0 15px rgba(0, 243, 255, 0.2);
            text-shadow: 0 0 5px var(--neon-blue);
            color: var(--neon-blue);
        }

        .container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 25px;
            position: relative;
            z-index: 3;
        }

        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-green);
            box-shadow: 0 0 15px rgba(0, 255, 0, 0.1), inset 0 0 20px rgba(0, 255, 0, 0.05);
            padding: 20px;
            position: relative;
            clip-path: polygon(0 0, 100% 0, 100% calc(100% - 20px), calc(100% - 20px) 100%, 0 100%);
        }

        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; width: 4px; height: 100%;
            background: var(--neon-green);
            box-shadow: 0 0 10px var(--neon-green);
        }

        .panel.accent-blue { border-color: var(--neon-blue); }
        .panel.accent-blue::before { background: var(--neon-blue); box-shadow: 0 0 10px var(--neon-blue); }
        .panel.accent-blue h2 { color: var(--neon-blue); text-shadow: 0 0 10px var(--neon-blue); border-bottom-color: var(--neon-blue); }

        .panel.accent-pink { border-color: var(--neon-pink); }
        .panel.accent-pink::before { background: var(--neon-pink); box-shadow: 0 0 10px var(--neon-pink); }
        .panel.accent-pink h2 { color: var(--neon-pink); text-shadow: 0 0 10px var(--neon-pink); border-bottom-color: var(--neon-pink); }

        h2 {
            font-size: 1.4em;
            color: var(--neon-green);
            text-shadow: 0 0 10px var(--neon-green);
            border-bottom: 1px dashed rgba(0, 255, 0, 0.5);
            padding-bottom: 8px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        .card {
            background: rgba(0, 0, 0, 0.6);
            border: 1px solid rgba(0, 255, 0, 0.3);
            margin-bottom: 15px;
            padding: 15px;
            transition: all 0.3s ease;
            position: relative;
            overflow: hidden;
        }

        .card:hover {
            border-color: var(--neon-green);
            box-shadow: 0 0 15px rgba(0, 255, 0, 0.3);
            transform: translateY(-2px);
        }

        .card-title {
            font-family: 'Orbitron', sans-serif;
            font-size: 1.1em;
            font-weight: bold;
            margin-bottom: 10px;
            display: flex;
            justify-content: space-between;
        }

        .badge {
            padding: 2px 8px;
            border-radius: 2px;
            font-size: 0.8em;
            font-weight: bold;
            text-transform: uppercase;
        }
        
        .badge-active { background: rgba(0, 255, 0, 0.2); border: 1px solid var(--neon-green); color: var(--neon-green); text-shadow: 0 0 5px var(--neon-green); animation: pulse 2s infinite; }
        .badge-warn { background: rgba(252, 238, 10, 0.2); border: 1px solid var(--neon-yellow); color: var(--neon-yellow); text-shadow: 0 0 5px var(--neon-yellow); }
        .badge-idle { background: rgba(0, 243, 255, 0.2); border: 1px solid var(--neon-blue); color: var(--neon-blue); text-shadow: 0 0 5px var(--neon-blue); }

        .data-row {
            display: flex;
            justify-content: space-between;
            margin: 5px 0;
            font-family: monospace;
            font-size: 1.1em;
        }

        .val-up { color: var(--neon-green); text-shadow: 0 0 5px var(--neon-green); }
        .val-down { color: var(--neon-red); text-shadow: 0 0 5px var(--neon-red); }
        
        .progress-bar {
            height: 4px;
            background: rgba(255, 255, 255, 0.1);
            margin-top: 10px;
            position: relative;
            overflow: hidden;
        }
        .progress-fill {
            height: 100%;
            background: var(--neon-green);
            box-shadow: 0 0 10px var(--neon-green);
            width: 0%;
            transition: width 0.5s ease;
        }

        /* Glitch Effect */
        .glitch { position: relative; }
        .glitch::before, .glitch::after {
            content: attr(data-text);
            position: absolute;
            top: 0; left: 0; width: 100%; height: 100%;
            background: var(--dark-bg);
        }
        .glitch::before {
            left: 2px;
            text-shadow: -1px 0 red;
            animation: glitch-anim-1 2s infinite linear alternate-reverse;
        }
        .glitch::after {
            left: -2px;
            text-shadow: -1px 0 blue;
            animation: glitch-anim-2 3s infinite linear alternate-reverse;
        }

        @keyframes pulse { 0% { opacity: 0.8; } 50% { opacity: 1; box-shadow: 0 0 10px currentColor; } 100% { opacity: 0.8; } }
        @keyframes glitch-anim-1 {
            0% { clip: rect(20px, 9999px, 85px, 0); }
            5% { clip: rect(72px, 9999px, 14px, 0); }
            10% { clip: rect(6px, 9999px, 50px, 0); }
            15% { clip: rect(31px, 9999px, 92px, 0); }
            20% { clip: rect(98px, 9999px, 7px, 0); }
            25% { clip: rect(40px, 9999px, 73px, 0); }
            30% { clip: rect(87px, 9999px, 19px, 0); }
            35% { clip: rect(15px, 9999px, 45px, 0); }
            40% { clip: rect(56px, 9999px, 88px, 0); }
            45% { clip: rect(3px, 9999px, 62px, 0); }
            50% { clip: rect(91px, 9999px, 24px, 0); }
            55% { clip: rect(28px, 9999px, 79px, 0); }
            60% { clip: rect(76px, 9999px, 11px, 0); }
            65% { clip: rect(49px, 9999px, 95px, 0); }
            70% { clip: rect(12px, 9999px, 36px, 0); }
            75% { clip: rect(82px, 9999px, 68px, 0); }
            80% { clip: rect(38px, 9999px, 8px, 0); }
            85% { clip: rect(65px, 9999px, 53px, 0); }
            90% { clip: rect(22px, 9999px, 81px, 0); }
            95% { clip: rect(95px, 9999px, 41px, 0); }
            100% { clip: rect(5px, 9999px, 29px, 0); }
        }
        @keyframes glitch-anim-2 {
            0% { clip: rect(15px, 9999px, 92px, 0); }
            5% { clip: rect(84px, 9999px, 26px, 0); }
            10% { clip: rect(37px, 9999px, 71px, 0); }
            15% { clip: rect(68px, 9999px, 9px, 0); }
            20% { clip: rect(11px, 9999px, 55px, 0); }
            25% { clip: rect(96px, 9999px, 33px, 0); }
            30% { clip: rect(42px, 9999px, 88px, 0); }
            35% { clip: rect(79px, 9999px, 17px, 0); }
            40% { clip: rect(24px, 9999px, 64px, 0); }
            45% { clip: rect(58px, 9999px, 4px, 0); }
            50% { clip: rect(5px, 9999px, 81px, 0); }
            55% { clip: rect(89px, 9999px, 48px, 0); }
            60% { clip: rect(31px, 9999px, 95px, 0); }
            65% { clip: rect(73px, 9999px, 22px, 0); }
            70% { clip: rect(46px, 9999px, 67px, 0); }
            75% { clip: rect(18px, 9999px, 8px, 0); }
            80% { clip: rect(92px, 9999px, 51px, 0); }
            85% { clip: rect(8px, 9999px, 76px, 0); }
            90% { clip: rect(61px, 9999px, 39px, 0); }
            95% { clip: rect(27px, 9999px, 83px, 0); }
            100% { clip: rect(54px, 9999px, 14px, 0); }
        }

        .market-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 1px;
            background: rgba(0, 255, 0, 0.2);
            border: 1px solid var(--neon-green);
        }
        .market-cell {
            background: rgba(0, 0, 0, 0.8);
            padding: 10px;
            text-align: center;
            font-family: monospace;
            font-size: 1.1em;
        }
        .market-header {
            background: rgba(0, 255, 0, 0.1);
            color: var(--neon-green);
            font-weight: bold;
            font-family: 'Orbitron', sans-serif;
            text-shadow: 0 0 5px var(--neon-green);
        }

        .terminal-logs {
            height: 150px;
            overflow-y: hidden;
            background: rgba(0,0,0,0.8);
            border: 1px solid var(--neon-green);
            padding: 10px;
            font-family: monospace;
            font-size: 0.9em;
            color: #aaa;
            box-shadow: inset 0 0 10px rgba(0,255,0,0.1);
        }
        .log-line { margin: 2px 0; }
        .log-time { color: var(--neon-blue); }
        .log-info { color: var(--neon-green); }
        .log-warn { color: var(--neon-yellow); }
        .log-err { color: var(--neon-red); }

        .sys-core {
            display: flex;
            justify-content: space-around;
            padding: 20px 0;
        }
        .core-ring {
            width: 80px;
            height: 80px;
            border-radius: 50%;
            border: 2px dashed var(--neon-blue);
            display: flex;
            align-items: center;
            justify-content: center;
            font-family: 'Orbitron';
            font-size: 1.2em;
            text-shadow: 0 0 5px var(--neon-blue);
            box-shadow: 0 0 15px rgba(0, 243, 255, 0.2), inset 0 0 10px rgba(0, 243, 255, 0.2);
            animation: spin-pulse 4s linear infinite;
        }
        .core-text { position: absolute; }
        @keyframes spin-pulse {
            0% { transform: rotate(0deg); box-shadow: 0 0 15px rgba(0, 243, 255, 0.2); }
            50% { transform: rotate(180deg); box-shadow: 0 0 30px rgba(0, 243, 255, 0.6); }
            100% { transform: rotate(360deg); box-shadow: 0 0 15px rgba(0, 243, 255, 0.2); }
        }

    </style>
</head>
<body>
    <h1 class="glitch" data-text="🛰️ NUVOLA ORBITAL COMMAND">🛰️ NUVOLA ORBITAL COMMAND</h1>
    
    <div class="header-status">
        <span>SYS: NUVOLA OS v4.2.0</span>
        <span style="color:var(--neon-yellow); text-shadow:0 0 5px var(--neon-yellow)">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</span>
        <span>LINK: <span style="color:var(--neon-green);text-shadow:0 0 5px var(--neon-green)">SECURE</span></span>
        <span>UPTIME: 99.999%</span>
        <span>LATENCY: 12ms</span>
    </div>

    <div class="container">
        <!-- ASSAULT TEAMS -->
        <div class="panel accent-pink">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT) <span>[ACTV: 3]</span></h2>
            
            <div class="card" style="border-color: var(--neon-pink);">
                <div class="card-title">
                    <span style="color: var(--neon-pink); text-shadow: 0 0 5px var(--neon-pink);">[01] SQUADRA_ALPHA</span>
                    <span class="badge badge-active" style="color:var(--neon-pink); border-color:var(--neon-pink);">ENGAGING</span>
                </div>
                <div class="data-row"><span>Type:</span> <span>Scalper @ Binance</span></div>
                <div class="data-row"><span>Target:</span> <span>BTC/USDT</span></div>
                <div class="data-row"><span>WinRate:</span> <span class="val-up">68.4% 🟢</span></div>
                <div class="data-row"><span>Alpha:</span> <span class="val-up">+0.84% / hr</span></div>
                <div class="progress-bar"><div class="progress-fill" style="width: 85%; background: var(--neon-pink); box-shadow: 0 0 10px var(--neon-pink);"></div></div>
            </div>

            <div class="card" style="border-color: var(--neon-yellow);">
                <div class="card-title">
                    <span style="color: var(--neon-yellow); text-shadow: 0 0 5px var(--neon-yellow);">[02] SQUADRA_DELTA</span>
                    <span class="badge badge-warn">AWAIT_VOL</span>
                </div>
                <div class="data-row"><span>Type:</span> <span>Order Flow @ Deribit</span></div>
                <div class="data-row"><span>Target:</span> <span>ETH Options</span></div>
                <div class="data-row"><span>Flow:</span> <span style="color: var(--neon-yellow);">Neutral 🟡</span></div>
                <div class="data-row"><span>Delta Exposure:</span> <span>0.00</span></div>
                <div class="progress-bar"><div class="progress-fill" style="width: 30%; background: var(--neon-yellow); box-shadow: 0 0 10px var(--neon-yellow);"></div></div>
            </div>

            <div class="card" style="border-color: var(--neon-blue);">
                <div class="card-title">
                    <span style="color: var(--neon-blue); text-shadow: 0 0 5px var(--neon-blue);">[03] SQUADRA_GAMMA</span>
                    <span class="badge badge-idle">ARB_SYNC</span>
                </div>
                <div class="data-row"><span>Type:</span> <span>Pairs Trading @ Bitget</span></div>
                <div class="data-row"><span>Target:</span> <span>SOL-PERP / SOL-SPOT</span></div>
                <div class="data-row"><span>Spread:</span> <span class="val-up">0.42% 🔵</span></div>
                <div class="data-row"><span>Capital Mngmt:</span> <span>Strict</span></div>
                <div class="progress-bar"><div class="progress-fill" style="width: 65%; background: var(--neon-blue); box-shadow: 0 0 10px var(--neon-blue);"></div></div>
            </div>
        </div>

        <!-- PROTOCOL TRINITY -->
        <div class="panel">
            <h2>🛡️ PROTOCOLLO TRINITY <span>[BACKGROUND: ONLINE]</span></h2>
            
            <div class="card">
                <div class="card-title">
                    <span>🦇 Lo Strozzino</span>
                    <span class="badge badge-active">DRAINING</span>
                </div>
                <div class="data-row"><span>Role:</span> <span>Funding Arb</span></div>
                <div class="data-row"><span>Premium Est:</span> <span class="val-up">0.024% / 8h</span></div>
                <div class="data-row"><span>Status:</span> <span>COLLECTING PREMIUMS 💰</span></div>
            </div>

            <div class="card">
                <div class="card-title">
                    <span>🧮 Il Contabile</span>
                    <span class="badge badge-active">ACCUMULATING</span>
                </div>
                <div class="data-row"><span>Role:</span> <span>Smart DCA</span></div>
                <div class="data-row"><span>Target Assets:</span> <span>BTC, ETH</span></div>
                <div class="data-row"><span>Status:</span> <span>BUYING DIPS 📊</span></div>
            </div>

            <div class="card">
                <div class="card-title">
                    <span>👼 L'Angelo Custode</span>
                    <span class="badge badge-active">SNIPING</span>
                </div>
                <div class="data-row"><span>Role:</span> <span>MEV @ Arbitrum</span></div>
                <div class="data-row"><span>Mempool Monitor:</span> <span class="val-up">Active</span></div>
                <div class="data-row"><span>Status:</span> <span>AWAITING TXS ⚡</span></div>
            </div>
            
            <div class="sys-core">
                <div style="position:relative; display:flex; justify-content:center; align-items:center;">
                    <div class="core-ring"></div>
                    <span class="core-text" style="color:var(--neon-blue);">CORE</span>
                </div>
            </div>
        </div>

        <!-- MARKET METRICS -->
        <div class="panel accent-blue" style="grid-column: 1 / -1;">
            <h2>📡 METRICHE DI MERCATO // THE ORACLE & WHALE TRACKER</h2>
            
            <div class="market-grid" id="market-data">
                <div class="market-cell market-header">ASSET</div>
                <div class="market-cell market-header">PRICE (USDT)</div>
                <div class="market-cell market-header">THE ORACLE (SENTIMENT)</div>
                <div class="market-cell market-header">WHALE TRACKER (FLOW)</div>

                <div class="market-cell">BTC-PERP</div>
                <div class="market-cell dyn-price val-up">68420.50</div>
                <div class="market-cell val-up">BULLISH [0.89]</div>
                <div class="market-cell val-up">+450M</div>

                <div class="market-cell">ETH-PERP</div>
                <div class="market-cell dyn-price val-down">3520.10</div>
                <div class="market-cell" style="color:var(--neon-yellow);">NEUTRAL [0.45]</div>
                <div class="market-cell val-down">-12M</div>

                <div class="market-cell">SOL-PERP</div>
                <div class="market-cell dyn-price val-up">185.30</div>
                <div class="market-cell" style="color:var(--neon-pink); text-shadow: 0 0 5px var(--neon-pink);">HYPER [0.95]</div>
                <div class="market-cell val-up">+85M</div>

                <div class="market-cell">ARB-PERP</div>
                <div class="market-cell dyn-price val-up">1.45</div>
                <div class="market-cell val-up">BULLISH [0.71]</div>
                <div class="market-cell val-up">+5M</div>
            </div>
            
            <h3 style="margin-top: 20px; color: var(--neon-green); font-size: 1.1em; border-bottom: 1px solid rgba(0,255,0,0.3); padding-bottom: 5px;">>_ SYSTEM LOGS</h3>
            <div class="terminal-logs" id="term-logs">
                <div class="log-line"><span class="log-time">[17:56:01]</span> <span class="log-info">SYS: Orbital Command Dashboard v2.0 initialized.</span></div>
                <div class="log-line"><span class="log-time">[17:56:05]</span> <span class="log-info">TRINITY: Lo Strozzino connected to funding rates stream.</span></div>
                <div class="log-line"><span class="log-time">[17:56:12]</span> <span class="log-info">HFT: SQUADRA_ALPHA engaged on BTC/USDT orderbook.</span></div>
                <div class="log-line"><span class="log-time">[17:56:45]</span> <span class="log-warn">HFT: SQUADRA_DELTA volatility threshold not met. Idling.</span></div>
                <div class="log-line"><span class="log-time">[17:57:02]</span> <span class="log-info">ORACLE: Sentiment update received. Bias: BULLISH.</span></div>
            </div>
        </div>
    </div>
    
    <script>
        // Fake dynamic updates
        setInterval(() => {
            const prices = document.querySelectorAll('.dyn-price');
            prices.forEach(priceEl => {
                let current = parseFloat(priceEl.innerText);
                let change = current * (Math.random() * 0.004 - 0.002);
                let newPrice = current + change;
                priceEl.innerText = newPrice.toFixed(2);
                if (change > 0) {
                    priceEl.className = 'market-cell dyn-price val-up';
                } else {
                    priceEl.className = 'market-cell dyn-price val-down';
                }
            });
            
            // Random progress bar fills
            document.querySelectorAll('.progress-fill').forEach(bar => {
                let currentW = parseFloat(bar.style.width);
                let newW = currentW + (Math.random() * 10 - 5);
                if(newW < 10) newW = 10;
                if(newW > 100) newW = 100;
                bar.style.width = newW + '%';
            });
            
            // Terminal logs
            const logs = document.getElementById('term-logs');
            const now = new Date();
            const timeStr = `[${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}:${now.getSeconds().toString().padStart(2, '0')}]`;
            const msgs = [
                '<span class="log-info">TRINITY: Il Contabile executed micro-buy (DCA).</span>',
                '<span class="log-warn">ORACLE: Minor whale wallet movement detected.</span>',
                '<span class="log-info">HFT: SQUADRA_ALPHA profitable scalp closed (+0.015%).</span>',
                '<span class="log-info">SYS: Mempool latency 12ms. Stable.</span>',
                '<span class="log-warn">HFT: SQUADRA_GAMMA adjusting spread parameters.</span>'
            ];
            const randomMsg = msgs[Math.floor(Math.random() * msgs.length)];
            logs.innerHTML += `<div class="log-line"><span class="log-time">${timeStr}</span> ${randomMsg}</div>`;
            logs.scrollTop = logs.scrollHeight;
            
            // Keep logs capped
            if (logs.children.length > 20) {
                logs.removeChild(logs.firstElementChild);
            }
            
        }, 1500);
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
