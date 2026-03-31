from flask import Flask, render_template_string
import os
import sys

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ORBITAL COMMAND // NUVOLA SYSTEM</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');
        
        :root {
            --bg-base: #020205;
            --neon-blue: #00f3ff;
            --neon-blue-dim: rgba(0, 243, 255, 0.2);
            --neon-pink: #ff007f;
            --neon-pink-dim: rgba(255, 0, 127, 0.2);
            --neon-green: #39ff14;
            --neon-green-dim: rgba(57, 255, 20, 0.2);
            --neon-yellow: #fffb00;
            --neon-red: #ff073a;
            --grid-color: rgba(0, 243, 255, 0.05);
            --panel-bg: rgba(5, 10, 20, 0.85);
        }
        
        * { box-sizing: border-box; }
        
        body {
            background-color: var(--bg-base);
            color: var(--neon-blue);
            font-family: 'Share Tech Mono', monospace;
            margin: 0;
            padding: 15px;
            overflow-x: hidden;
            background-image: 
                linear-gradient(var(--grid-color) 1px, transparent 1px),
                linear-gradient(90deg, var(--grid-color) 1px, transparent 1px);
            background-size: 30px 30px;
            position: relative;
        }

        /* CRT Scanline effect */
        body::after {
            content: " ";
            display: block;
            position: fixed;
            top: 0; left: 0; bottom: 0; right: 0;
            background: linear-gradient(rgba(18, 16, 16, 0) 50%, rgba(0, 0, 0, 0.25) 50%), linear-gradient(90deg, rgba(255, 0, 0, 0.06), rgba(0, 255, 0, 0.02), rgba(0, 0, 255, 0.06));
            z-index: 2;
            background-size: 100% 2px, 3px 100%;
            pointer-events: none;
        }

        .crt-flicker { animation: crtFlicker 0.15s infinite; }
        @keyframes crtFlicker { 0% { opacity: 0.95; } 100% { opacity: 1; } }

        h1, h2, h3, h4 { 
            margin: 0 0 10px 0; 
            text-transform: uppercase; 
            letter-spacing: 2px;
        }

        .glow-blue { text-shadow: 0 0 10px var(--neon-blue), 0 0 20px var(--neon-blue); color: var(--neon-blue); }
        .glow-pink { text-shadow: 0 0 10px var(--neon-pink), 0 0 20px var(--neon-pink); color: var(--neon-pink); }
        .glow-green { text-shadow: 0 0 10px var(--neon-green), 0 0 20px var(--neon-green); color: var(--neon-green); }
        .glow-red { text-shadow: 0 0 10px var(--neon-red), 0 0 20px var(--neon-red); color: var(--neon-red); }
        .glow-yellow { text-shadow: 0 0 10px var(--neon-yellow), 0 0 20px var(--neon-yellow); color: var(--neon-yellow); }

        .header {
            display: flex;
            justify-content: space-between;
            align-items: flex-end;
            border-bottom: 2px solid var(--neon-blue);
            padding-bottom: 10px;
            margin-bottom: 20px;
            box-shadow: 0 10px 20px -10px var(--neon-blue-dim);
            animation: pulse-border 2s infinite alternate;
        }

        .header-title { font-size: 2em; font-weight: bold; letter-spacing: 4px; }
        .sys-status { font-size: 0.9em; text-align: right; line-height: 1.4; }

        .dashboard-grid {
            display: grid;
            grid-template-columns: 1fr 1fr 1fr;
            grid-template-rows: auto auto;
            gap: 20px;
        }

        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-blue);
            box-shadow: inset 0 0 20px var(--neon-blue-dim), 0 0 15px var(--neon-blue-dim);
            padding: 15px;
            position: relative;
            backdrop-filter: blur(4px);
            z-index: 1;
        }

        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; width: 10px; height: 10px;
            border-top: 2px solid var(--neon-pink);
            border-left: 2px solid var(--neon-pink);
        }
        .panel::after {
            content: '';
            position: absolute;
            bottom: 0; right: 0; width: 10px; height: 10px;
            border-bottom: 2px solid var(--neon-pink);
            border-right: 2px solid var(--neon-pink);
        }

        .panel-title {
            font-size: 1.2em;
            border-bottom: 1px dashed var(--neon-blue-dim);
            padding-bottom: 5px;
            margin-bottom: 15px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .badge {
            font-size: 0.6em;
            padding: 2px 6px;
            border: 1px solid currentColor;
            border-radius: 2px;
            animation: blink 2s infinite;
        }

        .metric-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
            font-size: 0.9em;
            background: rgba(0, 0, 0, 0.3);
            padding: 4px 8px;
            border-left: 2px solid transparent;
            transition: 0.3s;
        }
        
        .metric-row:hover {
            border-left: 2px solid var(--neon-pink);
            background: var(--neon-blue-dim);
        }

        .terminal {
            background: #000;
            border: 1px solid var(--neon-green-dim);
            color: var(--neon-green);
            padding: 10px;
            height: 150px;
            overflow: hidden;
            font-size: 0.8em;
            display: flex;
            flex-direction: column-reverse;
            box-shadow: inset 0 0 10px var(--neon-green-dim);
        }

        .terminal span.time { color: #555; }
        .terminal span.warn { color: var(--neon-yellow); }
        .terminal span.err { color: var(--neon-red); }

        .progress-bar-bg { width: 100%; height: 6px; background: #111; border: 1px solid var(--neon-blue-dim); margin-top: 5px; }
        .progress-bar-fill { height: 100%; background: var(--neon-blue); box-shadow: 0 0 10px var(--neon-blue); transition: width 0.5s ease; }

        .btn-tactical {
            background: transparent;
            color: var(--neon-red);
            border: 1px solid var(--neon-red);
            padding: 8px 15px;
            cursor: pointer;
            font-family: 'Share Tech Mono', monospace;
            text-transform: uppercase;
            font-weight: bold;
            box-shadow: 0 0 10px rgba(255, 7, 58, 0.2);
            transition: all 0.2s;
            width: 100%;
            margin-top: 10px;
        }

        .btn-tactical:hover {
            background: var(--neon-red);
            color: #000;
            box-shadow: 0 0 20px rgba(255, 7, 58, 0.8);
        }

        /* Animations */
        @keyframes blink { 0%, 49% { opacity: 1; } 50%, 100% { opacity: 0; } }
        @keyframes pulse-border { 0% { border-color: rgba(0, 243, 255, 0.4); } 100% { border-color: rgba(0, 243, 255, 1); } }
        
        /* Grid spans */
        .span-2 { grid-column: span 2; }
        .span-3 { grid-column: span 3; }
        
        /* Tactical graph mock */
        .mock-graph {
            height: 60px;
            display: flex;
            align-items: flex-end;
            gap: 2px;
            margin-top: 10px;
            border-bottom: 1px solid var(--neon-blue-dim);
        }
        .graph-bar {
            flex: 1;
            background: var(--neon-blue);
            opacity: 0.7;
            animation: chartBar 1.5s infinite alternate ease-in-out;
        }
        @keyframes chartBar { 0% { height: 10%; } 100% { height: 90%; } }

    </style>
</head>
<body class="crt-flicker">

    <!-- HEADER -->
    <div class="header glow-blue">
        <div>
            <div class="header-title">🌐 NUVOLA // ORBITAL COMMAND 🌐</div>
            <div style="color: var(--neon-pink); margin-top: 5px;">> ROOT_ACCESS_GRANTED :: TACTICAL_OVERVIEW_ACTIVE</div>
        </div>
        <div class="sys-status">
            <span class="glow-green">STATUS: DEFCON 5 - NOMINAL</span><br>
            <span class="glow-yellow">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</span><br>
            TIME: <span id="sys-clock">00:00:00.000</span> UTC<br>
            UPTIME: 94:12:44 | PING: 12ms
        </div>
    </div>

    <div class="dashboard-grid">

        <!-- 1) SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <div class="panel-title glow-pink">
                <span>⚔️ SQUADRE D'ASSALTO (HFT)</span>
                <span class="badge glow-pink">ENGAGED</span>
            </div>
            
            <div class="metric-row">
                <span>🐺 SQUADRA_ALPHA <span style="font-size:0.7em;color:#888;">[Scalper@Binance]</span></span>
                <span class="glow-green">145.2 t/s</span>
            </div>
            <div class="progress-bar-bg"><div class="progress-bar-fill" style="width: 85%; background: var(--neon-green);"></div></div>
            <br>
            
            <div class="metric-row">
                <span>🦅 SQUADRA_DELTA <span style="font-size:0.7em;color:#888;">[Order Flow]</span></span>
                <span class="glow-blue">L2 SYNCED</span>
            </div>
            <div class="progress-bar-bg"><div class="progress-bar-fill" style="width: 100%;"></div></div>
            <br>

            <div class="metric-row">
                <span>🐍 SQUADRA_GAMMA <span style="font-size:0.7em;color:#888;">[Pairs@Bitget]</span></span>
                <span class="glow-yellow">SPREAD 0.4%</span>
            </div>
            <div class="progress-bar-bg"><div class="progress-bar-fill" style="width: 45%; background: var(--neon-yellow);"></div></div>
            
            <div style="margin-top: 15px; font-size: 0.8em; color: var(--neon-pink);">> LIVE EXECUTION FEED <span class="badge">REC</span></div>
            <div class="terminal" id="hft-terminal"></div>
        </div>

        <!-- 2) PROTOCOLLO TRINITY -->
        <div class="panel">
            <div class="panel-title glow-blue">
                <span>🔺 PROTOCOLLO TRINITY</span>
                <span class="badge glow-blue">DAEMON ONLINE</span>
            </div>

            <div class="metric-row">
                <span>🎩 Lo Strozzino <span style="font-size:0.7em;color:#888;">[Funding Arb]</span></span>
                <span class="glow-green">14.2% APY</span>
            </div>
            <div style="font-size:0.7em; color:var(--neon-blue-dim); margin-bottom: 10px;">> Position: $124,500 Hedged</div>

            <div class="metric-row">
                <span>🧮 Il Contabile <span style="font-size:0.7em;color:#888;">[DCA Core]</span></span>
                <span class="glow-blue">T-MINUS 04:12</span>
            </div>
            <div style="font-size:0.7em; color:var(--neon-blue-dim); margin-bottom: 10px;">> Next Allocation: 0.15 BTC</div>

            <div class="metric-row">
                <span>🛡️ L'Angelo Custode <span style="font-size:0.7em;color:#888;">[MEV@Arbitrum]</span></span>
                <span class="glow-yellow">SCANNING</span>
            </div>
            <div style="font-size:0.7em; color:var(--neon-blue-dim); margin-bottom: 15px;">> Mempool: 4,512 tx/s | Gas: 0.1 gwei</div>

            <div class="terminal" style="height: 100px;" id="trinity-terminal">
                <div>> [SYS] L'Angelo Custode: Flashbots bundle ready.</div>
                <div>> [SYS] Il Contabile: Funds verified.</div>
                <div>> [SYS] Lo Strozzino: Recalculating basis...</div>
            </div>

            <button class="btn-tactical">EMERGENCY KILLSWITCH // TRINITY</button>
        </div>

        <!-- 3) METRICHE DI MERCATO -->
        <div class="panel">
            <div class="panel-title glow-yellow">
                <span>📡 METRICHE DI MERCATO</span>
                <span class="badge glow-yellow">LIVE DATA</span>
            </div>

            <h4 class="glow-blue" style="font-size: 0.9em; border-bottom: 1px solid var(--neon-blue-dim);">👁️ THE ORACLE (Sentiment)</h4>
            <div class="metric-row">
                <span>F&G Index</span>
                <span class="glow-green" style="font-weight: bold;">65 (GREED)</span>
            </div>
            <div class="metric-row">
                <span>Binance L/S Ratio</span>
                <span class="glow-pink">1.42 (LONG BIAS)</span>
            </div>
            <div class="metric-row">
                <span>24h Liquidations</span>
                <span class="glow-red">$142.5M</span>
            </div>

            <h4 class="glow-pink" style="font-size: 0.9em; margin-top: 15px; border-bottom: 1px solid var(--neon-pink-dim);">🐋 WHALE TRACKER</h4>
            <div class="terminal" style="height: 110px; color: var(--neon-blue); border-color: var(--neon-blue-dim); box-shadow: inset 0 0 10px var(--neon-blue-dim);" id="whale-terminal">
                <div><span class="warn">[ALERT]</span> 50,000 ETH withdrawn from Binance</div>
                <div><span class="time">[03:15]</span> 1,200 BTC moved to Coinbase</div>
                <div><span class="err">[CRITICAL]</span> $500M USDT minted at Tether Treasury</div>
            </div>
            
            <div class="mock-graph">
                <!-- Javascript will generate bars -->
            </div>
        </div>
        
        <!-- FOOTER COMMAND LINE -->
        <div class="panel span-3" style="padding: 10px; display: flex; align-items: center; background: #000;">
            <span style="color: var(--neon-green); margin-right: 10px;">root@nuvola-orbital:~#</span>
            <span class="glow-blue" style="border-right: 10px solid var(--neon-blue); padding-right: 5px; animation: blink 1s infinite step-end;">tail -f /var/log/nuvola/orbital.log</span>
        </div>

    </div>

    <script>
        // Clock Update
        function updateClock() {
            const now = new Date();
            document.getElementById('sys-clock').innerText = now.toISOString().substring(11, 23);
            requestAnimationFrame(updateClock);
        }
        updateClock();

        // Random Graph Bars
        const graphContainer = document.querySelector('.mock-graph');
        for(let i=0; i<30; i++) {
            const bar = document.createElement('div');
            bar.className = 'graph-bar';
            bar.style.animationDelay = (Math.random() * 2) + 's';
            bar.style.animationDuration = (0.5 + Math.random()) + 's';
            graphContainer.appendChild(bar);
        }

        // HFT Terminal Simulator
        const pairs = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'AVAX/USDT', 'LINK/USDT'];
        const hftTerm = document.getElementById('hft-terminal');
        setInterval(() => {
            const pair = pairs[Math.floor(Math.random() * pairs.length)];
            const isBuy = Math.random() > 0.5;
            const amt = (Math.random() * 5).toFixed(3);
            const px = (Math.random() * 60000).toFixed(1);
            const timeStr = new Date().toISOString().substring(11, 19);
            
            const line = document.createElement('div');
            line.innerHTML = `<span class="time">[${timeStr}]</span> SQUADRA_ALPHA: <span class="${isBuy ? 'glow-green' : 'glow-red'}">${isBuy ? 'BUY' : 'SELL'}</span> ${amt} ${pair} @ ${px}`;
            
            hftTerm.prepend(line);
            if (hftTerm.children.length > 8) hftTerm.lastChild.remove();
        }, 400);

        // Whale Alert Simulator
        const whaleTerm = document.getElementById('whale-terminal');
        const whaleEvents = [
            "Unknown wallet transferred 4,500 BTC to Kraken",
            "Justin Sun deposited 120,000 ETH to Lido",
            "Alameda-labeled wallet active: 10M USDC moved",
            "Dormant address (11.5 yrs) moved 500 BTC",
            "Binance Cold Wallet #3 shifted 1B USDT"
        ];
        setInterval(() => {
            if(Math.random() > 0.7) {
                const event = whaleEvents[Math.floor(Math.random() * whaleEvents.length)];
                const timeStr = new Date().toISOString().substring(11, 16);
                const line = document.createElement('div');
                line.innerHTML = `<span class="time">[${timeStr}]</span> <span class="glow-pink">🐋 ${event}</span>`;
                whaleTerm.prepend(line);
                if (whaleTerm.children.length > 5) whaleTerm.lastChild.remove();
            }
        }, 3000);
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    # Force Flask to run quietly
    import logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    app.run(host='0.0.0.0', port=5000, threaded=True)
