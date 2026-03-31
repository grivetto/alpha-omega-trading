import logging
from flask import Flask, render_template_string

# Disable werkzeug logging for silent run
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NUVOLA // ORBITAL COMMAND</title>
    <link href="https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap" rel="stylesheet">
    <style>
        :root {
            --neon-blue: #0ff;
            --neon-red: #f03;
            --neon-green: #0f0;
            --neon-purple: #b0f;
            --neon-yellow: #ff0;
            --dark-bg: #030303;
            --panel-bg: rgba(10, 15, 20, 0.85);
            --grid-line: rgba(0, 255, 255, 0.1);
        }
        
        * { box-sizing: border-box; }
        
        body {
            background-color: var(--dark-bg);
            background-image: 
                linear-gradient(var(--grid-line) 1px, transparent 1px),
                linear-gradient(90deg, var(--grid-line) 1px, transparent 1px);
            background-size: 30px 30px;
            color: var(--neon-blue);
            font-family: 'Share Tech Mono', monospace;
            margin: 0;
            padding: 20px;
            overflow-x: hidden;
        }

        /* Scanline effect */
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

        h1.header-title {
            color: #fff;
            text-align: center;
            font-size: 3rem;
            margin: 10px 0 30px;
            text-shadow: 0 0 10px var(--neon-blue), 0 0 20px var(--neon-blue), 0 0 40px var(--neon-purple);
            letter-spacing: 5px;
            text-transform: uppercase;
        }

        .header-title span {
            color: var(--neon-purple);
            animation: flicker 3s infinite alternate;
        }

        .sys-status {
            text-align: center;
            margin-bottom: 30px;
            font-size: 1.2rem;
            color: var(--neon-green);
            text-shadow: 0 0 5px var(--neon-green);
            display: flex;
            justify-content: center;
            gap: 20px;
        }

        .sys-status div {
            padding: 10px 20px;
            border: 1px solid var(--neon-green);
            background: rgba(0, 255, 0, 0.05);
            border-radius: 4px;
            box-shadow: inset 0 0 10px rgba(0, 255, 0, 0.2);
        }

        .grid-container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 25px;
            max-width: 1400px;
            margin: 0 auto;
            position: relative;
            z-index: 3;
        }

        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-blue);
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 0 15px rgba(0, 255, 255, 0.15), inset 0 0 20px rgba(0, 255, 255, 0.05);
            position: relative;
            overflow: hidden;
            transition: all 0.3s;
        }

        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; height: 3px;
            background: var(--neon-blue);
            box-shadow: 0 0 10px var(--neon-blue);
        }

        .panel.red::before { background: var(--neon-red); box-shadow: 0 0 10px var(--neon-red); }
        .panel.purple::before { background: var(--neon-purple); box-shadow: 0 0 10px var(--neon-purple); }
        .panel.yellow::before { background: var(--neon-yellow); box-shadow: 0 0 10px var(--neon-yellow); }

        .panel:hover {
            box-shadow: 0 0 25px rgba(0, 255, 255, 0.3), inset 0 0 30px rgba(0, 255, 255, 0.1);
            transform: translateY(-2px);
        }

        .panel h2 {
            margin-top: 0;
            font-size: 1.6rem;
            text-transform: uppercase;
            border-bottom: 1px solid rgba(255, 255, 255, 0.2);
            padding-bottom: 10px;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .panel.red h2 { color: var(--neon-red); text-shadow: 0 0 8px var(--neon-red); border-color: rgba(255, 0, 51, 0.3); }
        .panel.purple h2 { color: var(--neon-purple); text-shadow: 0 0 8px var(--neon-purple); border-color: rgba(187, 0, 255, 0.3); }
        .panel.blue h2 { color: var(--neon-blue); text-shadow: 0 0 8px var(--neon-blue); }

        ul { list-style: none; padding: 0; margin: 0; }
        li {
            padding: 12px 0;
            border-bottom: 1px dashed rgba(255,255,255,0.1);
            display: flex;
            flex-direction: column;
            gap: 5px;
        }
        li:last-child { border-bottom: none; }

        .item-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .item-title {
            font-size: 1.1rem;
            font-weight: bold;
            color: #fff;
        }

        .badge {
            padding: 3px 8px;
            border-radius: 3px;
            font-size: 0.8rem;
            font-weight: bold;
            animation: pulse-bg 2s infinite;
        }

        .badge.online { background: rgba(0, 255, 0, 0.2); color: var(--neon-green); border: 1px solid var(--neon-green); box-shadow: 0 0 5px var(--neon-green); }
        .badge.active { background: rgba(187, 0, 255, 0.2); color: var(--neon-purple); border: 1px solid var(--neon-purple); box-shadow: 0 0 5px var(--neon-purple); }

        .details {
            display: flex;
            justify-content: space-between;
            font-size: 0.9rem;
            color: rgba(255,255,255,0.7);
        }

        .metric-value {
            font-family: monospace;
            color: var(--neon-yellow);
            text-shadow: 0 0 4px var(--neon-yellow);
        }

        .val-up { color: var(--neon-green); text-shadow: 0 0 4px var(--neon-green); }
        .val-down { color: var(--neon-red); text-shadow: 0 0 4px var(--neon-red); }

        /* Progress bars */
        .bar-container {
            width: 100%;
            height: 6px;
            background: #222;
            border-radius: 3px;
            margin-top: 5px;
            overflow: hidden;
            position: relative;
        }

        .bar {
            height: 100%;
            background: var(--neon-blue);
            box-shadow: 0 0 8px var(--neon-blue);
            width: 50%;
            transition: width 0.5s ease;
        }
        .bar.alpha { background: var(--neon-red); box-shadow: 0 0 8px var(--neon-red); width: 85%; }
        .bar.delta { background: var(--neon-yellow); box-shadow: 0 0 8px var(--neon-yellow); width: 62%; }
        .bar.gamma { background: var(--neon-green); box-shadow: 0 0 8px var(--neon-green); width: 45%; }

        .terminal {
            background: #000;
            border: 1px solid #333;
            padding: 10px;
            font-size: 0.85rem;
            height: 150px;
            overflow-y: hidden;
            color: var(--neon-green);
            position: relative;
        }
        .terminal-lines {
            position: absolute;
            bottom: 10px;
            width: calc(100% - 20px);
        }
        .t-line { margin: 2px 0; opacity: 0.8; }
        .t-prefix { color: var(--neon-purple); margin-right: 8px; }

        @keyframes flicker {
            0%, 18%, 22%, 25%, 53%, 57%, 100% { text-shadow: 0 0 10px var(--neon-purple), 0 0 20px var(--neon-purple), 0 0 40px var(--neon-purple); opacity: 1; }
            20%, 24%, 55% { text-shadow: none; opacity: 0.5; }
        }

        @keyframes pulse-bg {
            0% { opacity: 0.8; }
            50% { opacity: 1; }
            100% { opacity: 0.8; }
        }
        
        .blink {
            animation: blinker 1s linear infinite;
        }
        @keyframes blinker {
            50% { opacity: 0; }
        }
    </style>
</head>
<body>
    <h1 class="header-title">🛰️ NUVOLA // <span>ORBITAL COMMAND</span></h1>
    
    <div class="sys-status">
        <div>SYS: <span class="metric-value">NOMINAL</span></div>
        <div>UPLINK: <span class="metric-value val-up blink">ESTABLISHED</span></div>
        <div>LATENCY: <span class="metric-value" id="latency-val">12ms</span></div>
        <div>GLOBAL PNL: <span class="metric-value val-up" id="global-pnl">+$4,230.50</span></div>
        <div style="border-color: var(--neon-purple); background: rgba(187, 0, 255, 0.05); box-shadow: inset 0 0 10px rgba(187, 0, 255, 0.2);">⚙️ PROTOCOLLO TRINITY: <span class="metric-value" style="color: var(--neon-purple); text-shadow: 0 0 4px var(--neon-purple);">Online (DCA, Funding, MEV)</span></div>
    </div>

    <div class="grid-container">
        
        <!-- SQUADRE D'ASSALTO -->
        <div class="panel red">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <ul>
                <li>
                    <div class="item-header">
                        <span class="item-title">🐺 SQUADRA_ALPHA</span>
                        <span class="badge online">ONLINE</span>
                    </div>
                    <div class="details">
                        <span>Role: Scalper Binance</span>
                        <span>Win Rate: <span class="metric-value">68.4%</span></span>
                    </div>
                    <div class="bar-container"><div class="bar alpha" id="bar-alpha"></div></div>
                    <div class="details" style="margin-top: 5px;">
                        <span>Load: <span class="metric-value" id="load-alpha">85%</span></span>
                        <span>Orders/sec: <span class="metric-value" id="ops-alpha">142</span></span>
                    </div>
                </li>
                <li>
                    <div class="item-header">
                        <span class="item-title">🦅 SQUADRA_DELTA</span>
                        <span class="badge online">ONLINE</span>
                    </div>
                    <div class="details">
                        <span>Role: Order Flow</span>
                        <span>Win Rate: <span class="metric-value">71.2%</span></span>
                    </div>
                    <div class="bar-container"><div class="bar delta" id="bar-delta"></div></div>
                    <div class="details" style="margin-top: 5px;">
                        <span>Load: <span class="metric-value" id="load-delta">62%</span></span>
                        <span>Orders/sec: <span class="metric-value" id="ops-delta">45</span></span>
                    </div>
                </li>
                <li>
                    <div class="item-header">
                        <span class="item-title">🦂 SQUADRA_GAMMA</span>
                        <span class="badge online">ONLINE</span>
                    </div>
                    <div class="details">
                        <span>Role: Pairs Trading Bitget</span>
                        <span>Win Rate: <span class="metric-value">59.8%</span></span>
                    </div>
                    <div class="bar-container"><div class="bar gamma" id="bar-gamma"></div></div>
                    <div class="details" style="margin-top: 5px;">
                        <span>Load: <span class="metric-value" id="load-gamma">45%</span></span>
                        <span>Spread: <span class="metric-value val-up">0.02%</span></span>
                    </div>
                </li>
            </ul>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel purple">
            <h2>🔺 PROTOCOLLO TRINITY</h2>
            <ul>
                <li>
                    <div class="item-header">
                        <span class="item-title">🕴️ Lo Strozzino</span>
                        <span class="badge active">BACKGROUND</span>
                    </div>
                    <div class="details">
                        <span>Target: Funding Arb</span>
                        <span>APR: <span class="metric-value val-up">24.5%</span></span>
                    </div>
                    <div class="details" style="margin-top: 5px;">
                        <span style="font-size: 0.8rem; color: #888;">Harvesting delta-neutral yield across perps.</span>
                    </div>
                </li>
                <li>
                    <div class="item-header">
                        <span class="item-title">🧮 Il Contabile</span>
                        <span class="badge active">BACKGROUND</span>
                    </div>
                    <div class="details">
                        <span>Target: DCA Engine</span>
                        <span>Next Buy: <span class="metric-value">04:12:00</span></span>
                    </div>
                    <div class="details" style="margin-top: 5px;">
                        <span style="font-size: 0.8rem; color: #888;">Averaging entries on BTC/ETH dips.</span>
                    </div>
                </li>
                <li>
                    <div class="item-header">
                        <span class="item-title">👼 L'Angelo Custode</span>
                        <span class="badge active">BACKGROUND</span>
                    </div>
                    <div class="details">
                        <span>Target: MEV Arbitrum</span>
                        <span>Snipes 24h: <span class="metric-value val-up">14</span></span>
                    </div>
                    <div class="details" style="margin-top: 5px;">
                        <span style="font-size: 0.8rem; color: #888;">Protecting and sandwiching where profitable.</span>
                    </div>
                </li>
            </ul>
            <div style="margin-top: 15px; border-top: 1px dashed rgba(187, 0, 255, 0.3); padding-top: 10px;">
                <div style="font-size: 0.9rem; margin-bottom: 5px;">TRINITY LOG_ <span class="blink">_</span></div>
                <div class="terminal">
                    <div class="terminal-lines" id="trinity-logs">
                        <div class="t-line"><span class="t-prefix">[SYS]</span> Trinity core initialized.</div>
                        <div class="t-line"><span class="t-prefix">[STR]</span> Funding rate spread detected: Bybit/Binance.</div>
                        <div class="t-line"><span class="t-prefix">[ANG]</span> Monitoring mempool on Arb One...</div>
                    </div>
                </div>
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel blue">
            <h2>📊 METRICHE DI MERCATO</h2>
            <ul>
                <li>
                    <div class="item-header">
                        <span class="item-title">👁️ The Oracle</span>
                    </div>
                    <div class="details" style="margin-top: 5px;">
                        <span>Binance Sentiment:</span>
                        <span class="metric-value val-up">BULLISH 78%</span>
                    </div>
                    <div class="bar-container" style="background:#311"><div class="bar" style="width: 78%; background: var(--neon-green); box-shadow: 0 0 8px var(--neon-green);"></div></div>
                </li>
                <li>
                    <div class="item-header">
                        <span class="item-title">🐋 Whale Tracker</span>
                    </div>
                    <div class="details" style="margin-top: 5px;">
                        <span>Net Flow 24h:</span>
                        <span class="metric-value val-up" id="whale-flow">+45.2M USDT</span>
                    </div>
                    <div class="details" style="margin-top: 5px; font-size: 0.8rem;">
                        <span>Last Alert:</span>
                        <span class="metric-value" style="color:var(--neon-blue)">1000 BTC moved to Coinbase</span>
                    </div>
                </li>
                <li>
                    <div class="item-header">
                        <span class="item-title">⚡ Liquidations (24h)</span>
                    </div>
                    <div class="details" style="margin-top: 5px;">
                        <span>Longs: <span class="metric-value val-down">$12.4M</span></span>
                        <span>Shorts: <span class="metric-value val-up">$48.1M</span></span>
                    </div>
                </li>
                <li>
                    <div class="item-header">
                        <span class="item-title">🧬 Fear & Greed Index</span>
                    </div>
                    <div class="details" style="margin-top: 5px;">
                        <span>Current Value:</span>
                        <span class="metric-value val-up" style="font-size: 1.2rem;">65 / GREED</span>
                    </div>
                </li>
            </ul>
        </div>

    </div>

    <script>
        // Simulation Script for alive dashboard effect
        setInterval(() => {
            // Update Latency
            document.getElementById('latency-val').innerText = Math.floor(Math.random() * 15 + 8) + 'ms';
            
            // Randomly update bars and loads
            ['alpha', 'delta', 'gamma'].forEach(squad => {
                let currentLoad = parseInt(document.getElementById(`load-${squad}`).innerText);
                let newLoad = Math.max(10, Math.min(98, currentLoad + (Math.random() * 20 - 10)));
                document.getElementById(`load-${squad}`).innerText = Math.floor(newLoad) + '%';
                document.getElementById(`bar-${squad}`).style.width = newLoad + '%';
                
                if (squad !== 'gamma') {
                    let currentOps = parseInt(document.getElementById(`ops-${squad}`).innerText);
                    let newOps = Math.max(10, currentOps + (Math.random() * 10 - 5));
                    document.getElementById(`ops-${squad}`).innerText = Math.floor(newOps);
                }
            });

            // Minor PNL fluctuation
            let el = document.getElementById('global-pnl');
            let pnlStr = el.innerText.replace(/[+$|,]/g, '');
            let pnl = parseFloat(pnlStr);
            pnl += (Math.random() * 50 - 20);
            let sign = pnl >= 0 ? '+' : '';
            el.innerText = sign + '$' + pnl.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2});
            if(pnl < 0) {
                el.classList.remove('val-up');
                el.classList.add('val-down');
            } else {
                el.classList.remove('val-down');
                el.classList.add('val-up');
            }
        }, 2000);

        // Simulated Logs
        const logMsgs = [
            "[CON] DCA executed BTC buy order @ market.",
            "[STR] Rebalancing funding hedge (Bybit).",
            "[ANG] Sandwich opportunity identified. Executing...",
            "[SYS] Memory optimized.",
            "[STR] Waiting for optimal spread...",
            "[ANG] Transaction confirmed. Profit: 0.04 ETH"
        ];
        
        setInterval(() => {
            const logsContainer = document.getElementById('trinity-logs');
            const newLog = document.createElement('div');
            newLog.className = 't-line';
            const msg = logMsgs[Math.floor(Math.random() * logMsgs.length)];
            const prefixMatch = msg.match(/^(\[[A-Z]+\])(.*)/);
            if (prefixMatch) {
                newLog.innerHTML = `<span class="t-prefix">${prefixMatch[1]}</span>${prefixMatch[2]}`;
            } else {
                newLog.innerText = msg;
            }
            
            logsContainer.appendChild(newLog);
            if (logsContainer.children.length > 6) {
                logsContainer.removeChild(logsContainer.children[0]);
            }
        }, 3500);
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
