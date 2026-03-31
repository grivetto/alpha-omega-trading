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
    <title>ORBITAL COMMAND // NUVOLA_SYS</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');

        :root {
            --neon-green: #00ff00;
            --neon-cyan: #00ffff;
            --neon-red: #ff003c;
            --neon-purple: #b026ff;
            --neon-yellow: #fcee0a;
            --bg-color: #020202;
            --panel-bg: rgba(0, 20, 0, 0.4);
            --grid-line: rgba(0, 255, 0, 0.1);
        }

        * {
            box-sizing: border-box;
        }

        body {
            background-color: var(--bg-color);
            background-image: 
                linear-gradient(var(--grid-line) 1px, transparent 1px),
                linear-gradient(90deg, var(--grid-line) 1px, transparent 1px);
            background-size: 20px 20px;
            color: var(--neon-green);
            font-family: 'Share Tech Mono', monospace;
            margin: 0;
            padding: 20px;
            overflow-x: hidden;
            text-shadow: 0 0 2px var(--neon-green);
        }

        .crt::before {
            content: " ";
            display: block;
            position: absolute;
            top: 0;
            left: 0;
            bottom: 0;
            right: 0;
            background: linear-gradient(rgba(18, 16, 16, 0) 50%, rgba(0, 0, 0, 0.25) 50%), linear-gradient(90deg, rgba(255, 0, 0, 0.06), rgba(0, 255, 0, 0.02), rgba(0, 0, 255, 0.06));
            z-index: 2;
            background-size: 100% 2px, 3px 100%;
            pointer-events: none;
        }

        h1 {
            text-align: center;
            font-size: 3em;
            letter-spacing: 10px;
            color: var(--neon-cyan);
            text-shadow: 0 0 10px var(--neon-cyan), 0 0 20px var(--neon-cyan);
            border-bottom: 2px solid var(--neon-cyan);
            padding-bottom: 10px;
            margin-bottom: 30px;
            text-transform: uppercase;
        }

        .container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 25px;
            position: relative;
            z-index: 1;
        }

        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-green);
            padding: 20px;
            box-shadow: inset 0 0 20px rgba(0, 255, 0, 0.1), 0 0 10px rgba(0, 255, 0, 0.2);
            position: relative;
            backdrop-filter: blur(3px);
        }

        .panel::before, .panel::after {
            content: '';
            position: absolute;
            width: 20px; height: 20px;
            border: 2px solid var(--neon-cyan);
            transition: all 0.3s;
        }

        .panel::before { top: -2px; left: -2px; border-right: none; border-bottom: none; }
        .panel::after { bottom: -2px; right: -2px; border-left: none; border-top: none; }

        .panel:hover {
            box-shadow: inset 0 0 30px rgba(0, 255, 0, 0.2), 0 0 20px rgba(0, 255, 0, 0.4);
        }

        .panel h2 {
            font-size: 1.5em;
            margin-top: 0;
            color: var(--neon-yellow);
            text-shadow: 0 0 8px var(--neon-yellow);
            border-bottom: 1px solid var(--neon-yellow);
            padding-bottom: 10px;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .status-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12px;
            border-bottom: 1px dashed rgba(0, 255, 0, 0.3);
            padding-bottom: 8px;
            font-size: 1.1em;
        }

        .status-row .label { 
            font-weight: bold; 
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .badge {
            padding: 2px 8px;
            border-radius: 3px;
            font-size: 0.8em;
            font-weight: bold;
            letter-spacing: 1px;
            animation: pulse 2s infinite;
        }

        .badge.online { background: rgba(0, 255, 0, 0.2); border: 1px solid var(--neon-green); color: var(--neon-green); text-shadow: 0 0 5px var(--neon-green); }
        .badge.active { background: rgba(0, 255, 255, 0.2); border: 1px solid var(--neon-cyan); color: var(--neon-cyan); text-shadow: 0 0 5px var(--neon-cyan); animation: pulse-cyan 2s infinite; }
        .badge.warning { background: rgba(252, 238, 10, 0.2); border: 1px solid var(--neon-yellow); color: var(--neon-yellow); text-shadow: 0 0 5px var(--neon-yellow); }
        .badge.danger { background: rgba(255, 0, 60, 0.2); border: 1px solid var(--neon-red); color: var(--neon-red); text-shadow: 0 0 5px var(--neon-red); }

        @keyframes pulse { 0%, 100% { box-shadow: 0 0 5px var(--neon-green); } 50% { box-shadow: 0 0 15px var(--neon-green); } }
        @keyframes pulse-cyan { 0%, 100% { box-shadow: 0 0 5px var(--neon-cyan); } 50% { box-shadow: 0 0 15px var(--neon-cyan); } }

        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 15px;
            margin-top: 20px;
        }

        .metric-card {
            background: rgba(0, 0, 0, 0.6);
            border: 1px solid rgba(0, 255, 255, 0.3);
            padding: 10px;
            text-align: center;
            border-left: 3px solid var(--neon-cyan);
        }

        .metric-card .title {
            font-size: 0.8em;
            color: #aaa;
            text-transform: uppercase;
            margin-bottom: 5px;
        }

        .metric-card .value {
            font-size: 1.4em;
            color: var(--neon-cyan);
            text-shadow: 0 0 5px var(--neon-cyan);
            font-weight: bold;
        }

        .terminal {
            background: rgba(0, 0, 0, 0.8);
            border: 1px solid var(--neon-green);
            padding: 10px;
            height: 180px;
            overflow-y: hidden;
            font-size: 0.9em;
            margin-top: 15px;
            position: relative;
        }
        
        .terminal::before {
            content: "SYS.LOG";
            position: absolute;
            top: 2px;
            right: 5px;
            font-size: 0.7em;
            color: rgba(0, 255, 0, 0.5);
        }

        .log-line { margin: 4px 0; border-left: 2px solid rgba(0,255,0,0.3); padding-left: 8px; }
        .log-time { color: var(--neon-purple); margin-right: 10px; }
        .log-src { color: var(--neon-yellow); margin-right: 10px; }

        .progress-bar {
            width: 100%;
            height: 10px;
            background: rgba(0,0,0,0.5);
            border: 1px solid var(--neon-green);
            margin-top: 5px;
            position: relative;
            overflow: hidden;
        }

        .progress-fill {
            height: 100%;
            background: var(--neon-green);
            box-shadow: 0 0 10px var(--neon-green);
            width: 50%;
            transition: width 0.5s ease;
        }

        .radar {
            width: 100px;
            height: 100px;
            border-radius: 50%;
            border: 2px solid var(--neon-green);
            position: relative;
            margin: 0 auto;
            background: rgba(0, 255, 0, 0.05);
            overflow: hidden;
        }

        .radar::before {
            content: '';
            position: absolute;
            top: 50%; left: 50%;
            width: 50%; height: 2px;
            background: var(--neon-green);
            transform-origin: 0 50%;
            animation: scan 2s linear infinite;
            box-shadow: 0 0 10px var(--neon-green);
        }

        @keyframes scan {
            100% { transform: rotate(360deg); }
        }

    </style>
</head>
<body class="crt">
    <h1>🛰️ ORBITAL COMMAND // NUVOLA_SYS 🛰️</h1>
    
    <div class="container">
        
        <!-- HFT SQUADS -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            
            <div class="status-row">
                <span class="label">🎯 SQUADRA_ALPHA <span style="font-size: 0.7em; color: #aaa;">(Scalper Binance)</span></span>
                <span class="badge online">ENGAGED</span>
            </div>
            <div class="progress-bar"><div class="progress-fill" style="width: 85%;"></div></div>
            
            <div class="status-row" style="margin-top: 15px;">
                <span class="label">🌊 SQUADRA_DELTA <span style="font-size: 0.7em; color: #aaa;">(Order Flow)</span></span>
                <span class="badge online">ENGAGED</span>
            </div>
            <div class="progress-bar"><div class="progress-fill" style="width: 62%;"></div></div>
            
            <div class="status-row" style="margin-top: 15px;">
                <span class="label">⚖️ SQUADRA_GAMMA <span style="font-size: 0.7em; color: #aaa;">(Pairs Bitget)</span></span>
                <span class="badge online">ENGAGED</span>
            </div>
            <div class="progress-bar"><div class="progress-fill" style="width: 90%;"></div></div>

            <div class="terminal" id="hft-logs">
                <div class="log-line"><span class="log-time">[18:45:02]</span> <span class="log-src">ALPHA</span> Executing limit buy BTC @ 64321.5</div>
                <div class="log-line"><span class="log-time">[18:45:05]</span> <span class="log-src">DELTA</span> Order book imbalance detected (Bid heavy)</div>
                <div class="log-line"><span class="log-time">[18:45:08]</span> <span class="log-src">GAMMA</span> Spread widening BTC/ETH. Rebalancing.</div>
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2>🛡️ PROTOCOLLO TRINITY</h2>
            
            <div style="background: rgba(0, 255, 255, 0.1); border: 1px solid var(--neon-cyan); padding: 10px; text-align: center; margin-bottom: 20px; font-weight: bold; color: var(--neon-cyan); box-shadow: inset 0 0 10px rgba(0, 255, 255, 0.2);">
                ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
            </div>

            <div class="status-row">
                <span class="label">🦇 Lo Strozzino <span style="font-size: 0.7em; color: #aaa;">(Funding Arb)</span></span>
                <span class="badge active">ACTIVE</span>
            </div>
            <div class="status-row">
                <span class="label">🧮 Il Contabile <span style="font-size: 0.7em; color: #aaa;">(DCA)</span></span>
                <span class="badge active">ACTIVE</span>
            </div>
            <div class="status-row">
                <span class="label">👼 L'Angelo Custode <span style="font-size: 0.7em; color: #aaa;">(MEV Arbitrum)</span></span>
                <span class="badge active">ACTIVE</span>
            </div>
            
            <div class="metrics-grid">
                <div class="metric-card">
                    <div class="title">Est. Trinity APR</div>
                    <div class="value">42.8%</div>
                </div>
                <div class="metric-card">
                    <div class="title">Capital Protected</div>
                    <div class="value">100.0%</div>
                </div>
                <div class="metric-card">
                    <div class="title">Arb Opportunities</div>
                    <div class="value">14/hr</div>
                </div>
                <div class="metric-card">
                    <div class="title">MEV Flashbots</div>
                    <div class="value">SYNCED</div>
                </div>
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <h2>📊 METRICHE DI MERCATO</h2>
            
            <div class="status-row">
                <span class="label">👁️ The Oracle <span style="font-size: 0.7em; color: #aaa;">(Binance Sentiment)</span></span>
                <span class="badge warning">BULLISH [78%]</span>
            </div>
            <div class="status-row">
                <span class="label">🐳 Whale Tracker <span style="font-size: 0.7em; color: #aaa;">(On-chain)</span></span>
                <span class="badge danger">ANOMALY DETECTED</span>
            </div>

            <div class="metrics-grid">
                <div class="metric-card" style="border-left-color: var(--neon-green);">
                    <div class="title">BTC/USDT</div>
                    <div class="value" id="btc-price" style="color: var(--neon-green);">64,592.10</div>
                </div>
                <div class="metric-card" style="border-left-color: var(--neon-green);">
                    <div class="title">ETH/USDT</div>
                    <div class="value" id="eth-price" style="color: var(--neon-green);">3,481.50</div>
                </div>
                <div class="metric-card" style="border-left-color: var(--neon-yellow);">
                    <div class="title">Global Volatility</div>
                    <div class="value" style="color: var(--neon-yellow);">HIGH</div>
                </div>
                <div class="metric-card" style="border-left-color: var(--neon-red);">
                    <div class="title">Network Latency</div>
                    <div class="value" id="ping" style="color: var(--neon-red);">12ms</div>
                </div>
            </div>

            <div style="margin-top: 20px; display: flex; justify-content: space-around; align-items: center;">
                <div class="radar"></div>
                <div style="text-align: right; font-size: 0.8em; color: #888;">
                    SCANNING MEMPOOL...<br>
                    INTERCEPTING TXs...<br>
                    UPTIME: 99.999%
                </div>
            </div>

        </div>
    </div>

    <script>
        function updateTime() {
            const now = new Date();
            return now.toTimeString().split(' ')[0];
        }

        // Simulate dynamic values
        setInterval(() => {
            // Update BTC
            const btcEl = document.getElementById('btc-price');
            let btc = parseFloat(btcEl.innerText.replace(',', ''));
            btc += (Math.random() * 20 - 10);
            btcEl.innerText = btc.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2});
            
            // Update ETH
            const ethEl = document.getElementById('eth-price');
            let eth = parseFloat(ethEl.innerText.replace(',', ''));
            eth += (Math.random() * 5 - 2.5);
            ethEl.innerText = eth.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2});

            // Update Ping
            document.getElementById('ping').innerText = Math.floor(Math.random() * 10 + 8) + 'ms';

            // Logs
            const logs = document.getElementById('hft-logs');
            const events = [
                { src: 'ALPHA', msg: 'Scalp filled +0.02% (Speed: 4ms)' },
                { src: 'DELTA', msg: 'Liquidations mapped at 64k zone' },
                { src: 'GAMMA', msg: 'Rebalancing pairs on Bitget. Spread tight.' },
                { src: 'SYS', msg: 'Syncing RPC nodes...' },
                { src: 'ORACLE', msg: 'Sentiment shift detected: +2% Longs' }
            ];
            
            if (Math.random() > 0.4) {
                const ev = events[Math.floor(Math.random() * events.length)];
                const newLog = document.createElement('div');
                newLog.className = 'log-line';
                newLog.innerHTML = `<span class="log-time">[${updateTime()}]</span> <span class="log-src">${ev.src}</span> ${ev.msg}`;
                
                logs.prepend(newLog);
                if(logs.children.length > 8) logs.removeChild(logs.lastChild);
            }

            // Random progress bars
            document.querySelectorAll('.progress-fill').forEach(bar => {
                let current = parseFloat(bar.style.width);
                current += (Math.random() * 10 - 5);
                if(current > 100) current = 100;
                if(current < 20) current = 20;
                bar.style.width = current + '%';
            });

        }, 1500);
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
