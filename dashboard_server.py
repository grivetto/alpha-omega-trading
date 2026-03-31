from flask import Flask, render_template_string
import random
import time
import threading

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ORBITAL COMMAND // NUVOLA</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');
        
        :root {
            --matrix-green: #00ff41;
            --alert-red: #ff003c;
            --cyber-blue: #00f0ff;
            --neon-purple: #b026ff;
            --bg-base: #020202;
            --panel-bg: rgba(5, 10, 5, 0.75);
        }
        
        * { box-sizing: border-box; }
        
        body {
            background-color: var(--bg-base);
            color: var(--matrix-green);
            font-family: 'Share Tech Mono', monospace;
            margin: 0;
            padding: 2vw;
            background-image: 
                radial-gradient(circle at 50% 50%, rgba(0, 255, 65, 0.05) 0%, transparent 60%),
                linear-gradient(rgba(0, 255, 65, 0.03) 1px, transparent 1px),
                linear-gradient(90deg, rgba(0, 255, 65, 0.03) 1px, transparent 1px);
            background-size: 100vw 100vh, 20px 20px, 20px 20px;
            overflow-x: hidden;
            text-transform: uppercase;
        }

        /* CRT effects */
        body::before {
            content: " ";
            display: block;
            position: fixed;
            top: 0; left: 0; bottom: 0; right: 0;
            background: linear-gradient(rgba(18, 16, 16, 0) 50%, rgba(0, 0, 0, 0.25) 50%), linear-gradient(90deg, rgba(255, 0, 0, 0.06), rgba(0, 255, 0, 0.02), rgba(0, 0, 255, 0.06));
            z-index: 2;
            background-size: 100% 2px, 3px 100%;
            pointer-events: none;
        }

        .scanline {
            width: 100%;
            height: 100px;
            z-index: 9999;
            position: fixed;
            pointer-events: none;
            background: linear-gradient(0deg, rgba(0,0,0,0) 0%, rgba(0,255,65,0.2) 50%, rgba(0,0,0,0) 100%);
            opacity: 0.3;
            animation: scanline 6s linear infinite;
        }
        @keyframes scanline {
            0% { top: -100px; }
            100% { top: 100vh; }
        }

        h1, h2, h3 {
            margin: 0 0 15px 0;
            letter-spacing: 2px;
            text-shadow: 0 0 10px currentColor;
        }

        .header {
            text-align: center;
            border: 1px solid var(--matrix-green);
            padding: 20px;
            margin-bottom: 30px;
            background: rgba(0, 255, 65, 0.05);
            box-shadow: 0 0 20px rgba(0, 255, 65, 0.2), inset 0 0 20px rgba(0, 255, 65, 0.1);
            position: relative;
        }
        
        .header h1 {
            color: var(--matrix-green);
            font-size: 2.5em;
            animation: glitch 3s infinite;
        }

        @keyframes glitch {
            0% { text-shadow: 0.05em 0 0 var(--alert-red), -0.05em -0.025em 0 var(--cyber-blue); }
            14% { text-shadow: 0.05em 0 0 var(--alert-red), -0.05em -0.025em 0 var(--cyber-blue); }
            15% { text-shadow: -0.05em -0.025em 0 var(--alert-red), 0.025em 0.025em 0 var(--cyber-blue); }
            49% { text-shadow: -0.05em -0.025em 0 var(--alert-red), 0.025em 0.025em 0 var(--cyber-blue); }
            50% { text-shadow: 0.025em 0.05em 0 var(--alert-red), 0.05em 0 0 var(--cyber-blue); }
            99% { text-shadow: 0.025em 0.05em 0 var(--alert-red), 0.05em 0 0 var(--cyber-blue); }
            100% { text-shadow: -0.025em 0 0 var(--alert-red), -0.025em -0.025em 0 var(--cyber-blue); }
        }

        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 25px;
            position: relative;
            z-index: 3;
        }

        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--matrix-green);
            padding: 20px;
            box-shadow: 0 0 15px rgba(0, 255, 65, 0.1);
            backdrop-filter: blur(4px);
            position: relative;
        }

        /* Panel corners */
        .panel::before, .panel::after {
            content: ''; position: absolute; width: 15px; height: 15px; border: 2px solid transparent;
        }
        .panel::before { top: -1px; left: -1px; border-top-color: currentColor; border-left-color: currentColor; }
        .panel::after { bottom: -1px; right: -1px; border-bottom-color: currentColor; border-right-color: currentColor; }

        .panel.hft { color: var(--matrix-green); border-color: var(--matrix-green); }
        .panel.hft h2 { color: var(--matrix-green); border-bottom: 1px dashed var(--matrix-green); }
        
        .panel.trinity { color: var(--cyber-blue); border-color: var(--cyber-blue); }
        .panel.trinity h2 { color: var(--cyber-blue); border-bottom: 1px dashed var(--cyber-blue); }
        
        .panel.metrics { color: var(--neon-purple); border-color: var(--neon-purple); }
        .panel.metrics h2 { color: var(--neon-purple); border-bottom: 1px dashed var(--neon-purple); }

        .item {
            margin-bottom: 20px;
            padding-bottom: 15px;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }
        .item:last-child { border-bottom: none; margin-bottom: 0; padding-bottom: 0; }

        .item-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
            font-size: 1.1em;
            font-weight: bold;
        }

        .status-badge {
            padding: 2px 8px;
            font-size: 0.8em;
            border: 1px solid currentColor;
            background: rgba(0,0,0,0.5);
            animation: pulse 2s infinite;
        }

        @keyframes pulse {
            0% { box-shadow: 0 0 0 0 rgba(currentColor, 0.4); }
            70% { box-shadow: 0 0 0 6px rgba(currentColor, 0); }
            100% { box-shadow: 0 0 0 0 rgba(currentColor, 0); }
        }

        .data-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
            font-size: 0.9em;
            opacity: 0.9;
        }
        .data-label { color: #888; }
        .data-value { float: right; }
        
        .val-up { color: var(--matrix-green); text-shadow: 0 0 5px var(--matrix-green); }
        .val-down { color: var(--alert-red); text-shadow: 0 0 5px var(--alert-red); }
        .val-warn { color: #ffeb3b; text-shadow: 0 0 5px #ffeb3b; }

        .terminal-log {
            font-size: 0.8em;
            margin-top: 10px;
            padding: 8px;
            background: rgba(0,0,0,0.8);
            border-left: 2px solid currentColor;
            color: #ccc;
        }
        .blink { animation: blinker 1s linear infinite; }
        @keyframes blinker { 50% { opacity: 0; } }

    </style>
</head>
<body>
    <div class="scanline"></div>
    
    <div class="header">
        <h1>🛰️ ORBITAL COMMAND // NUVOLA TERMINAL</h1>
        <div>CONNECTION: <span class="val-up">SECURE_UPLINK_ACTIVE</span> | ENCRYPTION: MIL-SPEC AES-256-GCM</div>
        <div style="margin-top:10px; font-size: 0.9em; color: #888;">LAT/LON: 41.9028° N, 12.4964° E [ROME_HQ] | SYS_TIME: <span id="clock" class="cyber-blue">00:00:00</span></div>
        <div style="margin-top:15px; font-size: 1.2em; color: var(--cyber-blue); font-weight: bold; text-shadow: 0 0 8px var(--cyber-blue);">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</div>
    </div>

    <div class="grid">
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel hft">
            <h2>⚔️ SQUADRE D'ASSALTO [HFT]</h2>
            
            <div class="item">
                <div class="item-header">
                    <span><span class="blink">▶</span> SQUADRA_ALPHA [BINANCE SCALPER]</span>
                    <span class="status-badge" style="color:var(--matrix-green)">ENGAGED</span>
                </div>
                <div class="data-grid">
                    <div><span class="data-label">LATENCY:</span> <span class="data-value">4.2ms</span></div>
                    <div><span class="data-label">WIN_RATE:</span> <span class="data-value val-up">68.4%</span></div>
                    <div><span class="data-label">ORDERS/s:</span> <span class="data-value" id="alpha-orders">142</span></div>
                    <div><span class="data-label">SESSION PNL:</span> <span class="data-value val-up">+$1,450.20</span></div>
                </div>
                <div class="terminal-log">> Executing limit sweeps on BTC/USDT... Fill ratio 98%.</div>
            </div>

            <div class="item">
                <div class="item-header">
                    <span><span class="blink">▶</span> SQUADRA_DELTA [ORDER FLOW]</span>
                    <span class="status-badge" style="color:var(--matrix-green)">MONITORING</span>
                </div>
                <div class="data-grid">
                    <div><span class="data-label">TARGET:</span> <span class="data-value">DERIBIT OPTS</span></div>
                    <div><span class="data-label">IMBALANCE:</span> <span class="data-value val-up">82% BULL</span></div>
                    <div><span class="data-label">CVD_DELTA:</span> <span class="data-value val-up">+450 BTC</span></div>
                    <div><span class="data-label">TOXICITY:</span> <span class="data-value">LOW</span></div>
                </div>
                <div class="terminal-log">> Tracking institutional dark pool prints.</div>
            </div>

            <div class="item">
                <div class="item-header">
                    <span><span class="blink">▶</span> SQUADRA_GAMMA [PAIRS / BITGET]</span>
                    <span class="status-badge" style="color:var(--cyber-blue)">STANDBY</span>
                </div>
                <div class="data-grid">
                    <div><span class="data-label">PAIR:</span> <span class="data-value">ETH/SOL</span></div>
                    <div><span class="data-label">Z-SCORE:</span> <span class="data-value" id="gamma-z">1.92</span></div>
                    <div><span class="data-label">THRESHOLD:</span> <span class="data-value">2.50</span></div>
                    <div><span class="data-label">EXPOSURE:</span> <span class="data-value">$0.00</span></div>
                </div>
                <div class="terminal-log">> Awaiting statistical divergence...</div>
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel trinity">
            <h2>🔺 PROTOCOLLO TRINITY</h2>
            
            <div class="item">
                <div class="item-header">
                    <span><span class="blink">▶</span> LO STROZZINO [FUNDING ARB]</span>
                    <span class="status-badge" style="color:var(--cyber-blue)">YIELDING</span>
                </div>
                <div class="data-grid">
                    <div><span class="data-label">STRATEGY:</span> <span class="data-value">DELTA-NEUTRAL</span></div>
                    <div><span class="data-label">CAPITAL_ALLOC:</span> <span class="data-value">$150,000</span></div>
                    <div><span class="data-label">AVG_SPREAD:</span> <span class="data-value val-up">+0.06% / 8H</span></div>
                    <div><span class="data-label">EST_APY:</span> <span class="data-value val-up">18.5%</span></div>
                </div>
                <div class="terminal-log">> Short PERP / Long SPOT. Harvesting premium.</div>
            </div>

            <div class="item">
                <div class="item-header">
                    <span><span class="blink">▶</span> IL CONTABILE [DCA ACCUMULATOR]</span>
                    <span class="status-badge" style="color:var(--matrix-green)">ACTIVE</span>
                </div>
                <div class="data-grid">
                    <div><span class="data-label">ASSET:</span> <span class="data-value">BTC</span></div>
                    <div><span class="data-label">INTERVAL:</span> <span class="data-value">4H</span></div>
                    <div><span class="data-label">NEXT_EXEC:</span> <span class="data-value" id="contabile-timer">02:14:59</span></div>
                    <div><span class="data-label">AVG_COST:</span> <span class="data-value">$61,240</span></div>
                </div>
                <div class="terminal-log">> Routing accumulation to cold storage vault.</div>
            </div>

            <div class="item">
                <div class="item-header">
                    <span><span class="blink">▶</span> L'ANGELO CUSTODE [MEV ARBITRUM]</span>
                    <span class="status-badge" style="color:var(--alert-red)">HUNTING</span>
                </div>
                <div class="data-grid">
                    <div><span class="data-label">MEMPOOL_TX/s:</span> <span class="data-value val-warn" id="mev-tx">850</span></div>
                    <div><span class="data-label">SANDWICHES_24H:</span> <span class="data-value">14</span></div>
                    <div><span class="data-label">FLASHBOTS:</span> <span class="data-value">SYNCED</span></div>
                    <div><span class="data-label">GAS_GWEI:</span> <span class="data-value val-down">0.1</span></div>
                </div>
                <div class="terminal-log" style="color: var(--alert-red);">> Searching for slippage victims on Uniswap V3...</div>
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel metrics">
            <h2>📊 METRICHE DI MERCATO [GLOBAL]</h2>
            
            <div class="item">
                <div class="item-header">
                    <span><span class="blink">▶</span> THE ORACLE [SENTIMENT AI]</span>
                    <span class="status-badge" style="color:var(--neon-purple)">ANALYZING</span>
                </div>
                <div class="data-grid">
                    <div><span class="data-label">INDEX_SCORE:</span> <span class="data-value val-up">78 (GREED)</span></div>
                    <div><span class="data-label">SOCIAL_VOL:</span> <span class="data-value val-up">+24%</span></div>
                    <div><span class="data-label">NLP_BIAS:</span> <span class="data-value val-up">BULLISH</span></div>
                    <div><span class="data-label">FEAR_METRIC:</span> <span class="data-value val-down">LOW</span></div>
                </div>
                <div class="terminal-log">> Scraping Crypto Twitter & Reddit. Extreme retail euphoria detected. Proceed with caution.</div>
            </div>

            <div class="item">
                <div class="item-header">
                    <span><span class="blink">▶</span> WHALE TRACKER [ON-CHAIN]</span>
                    <span class="status-badge" style="color:var(--alert-red)">ALERT</span>
                </div>
                <div class="data-grid">
                    <div><span class="data-label">LAST_TX:</span> <span class="data-value">2 MINS AGO</span></div>
                    <div><span class="data-label">AMOUNT:</span> <span class="data-value val-warn">15,000 BTC</span></div>
                    <div><span class="data-label">FROM:</span> <span class="data-value">UNKNOWN WALLET</span></div>
                    <div><span class="data-label">TO:</span> <span class="data-value val-down">COINBASE HOT</span></div>
                </div>
                <div class="terminal-log" style="color: #ffeb3b;">> WARNING: Massive exchange inflow detected. Potential sell wall incoming.</div>
            </div>

            <div class="item">
                <div class="item-header">
                    <span><span class="blink">▶</span> NODE RESOURCES [NUVOLA]</span>
                    <span class="status-badge" style="color:var(--matrix-green)">NOMINAL</span>
                </div>
                <div class="data-grid">
                    <div><span class="data-label">CPU_LOAD:</span> <span class="data-value" id="cpu-load">12%</span></div>
                    <div><span class="data-label">MEM_USAGE:</span> <span class="data-value" id="mem-load">4GB / 32GB</span></div>
                    <div><span class="data-label">NET_RX/TX:</span> <span class="data-value">1.2 Gbps</span></div>
                    <div><span class="data-label">TEMP:</span> <span class="data-value">42°C</span></div>
                </div>
                <div class="terminal-log">> All core systems operating within optimal parameters.</div>
            </div>
        </div>
    </div>

    <script>
        // Fake dynamic data simulation for the dashboard
        setInterval(() => {
            document.getElementById('clock').innerText = new Date().toISOString().substring(11,19) + " UTC";
            
            document.getElementById('alpha-orders').innerText = Math.floor(Math.random() * 50) + 120;
            document.getElementById('gamma-z').innerText = (Math.random() * 0.4 + 1.8).toFixed(2);
            document.getElementById('mev-tx').innerText = Math.floor(Math.random() * 300) + 700;
            
            document.getElementById('cpu-load').innerText = (Math.random() * 10 + 10).toFixed(1) + "%";
            document.getElementById('mem-load').innerText = (Math.random() * 0.5 + 4.0).toFixed(1) + "GB / 32GB";
        }, 1000);
        
        // Contabile timer
        let timer = 3600 * 2 + 14 * 60 + 59; // 2h 14m 59s
        setInterval(() => {
            if(timer > 0) timer--;
            let h = Math.floor(timer / 3600).toString().padStart(2, '0');
            let m = Math.floor((timer % 3600) / 60).toString().padStart(2, '0');
            let s = (timer % 60).toString().padStart(2, '0');
            document.getElementById('contabile-timer').innerText = `${h}:${m}:${s}`;
        }, 1000);
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
