import os
from flask import Flask, render_template_string

app = Flask(__name__)

HTML_CONTENT = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NUVOLA ORBITAL COMMAND</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');
        
        :root {
            --neon-green: #0f380f;
            --matrix-green: #39ff14;
            --neon-blue: #00f3ff;
            --neon-pink: #ff00ff;
            --neon-red: #ff003c;
            --neon-yellow: #fcee0a;
            --neon-purple: #b026ff;
            --bg-color: #050505;
            --panel-bg: rgba(10, 15, 12, 0.85);
            --grid-color: rgba(57, 255, 20, 0.08);
            --text-main: #39ff14;
        }

        * {
            box-sizing: border-box;
        }

        body {
            margin: 0;
            padding: 20px;
            background-color: var(--bg-color);
            color: var(--text-main);
            font-family: 'Share Tech Mono', monospace;
            background-image: 
                linear-gradient(var(--grid-color) 1px, transparent 1px),
                linear-gradient(90deg, var(--grid-color) 1px, transparent 1px);
            background-size: 40px 40px;
            overflow-x: hidden;
            text-transform: uppercase;
        }

        /* CRT Scanlines */
        body::after {
            content: " ";
            display: block;
            position: fixed;
            top: 0; left: 0; bottom: 0; right: 0;
            background: linear-gradient(rgba(18, 16, 16, 0) 50%, rgba(0, 0, 0, 0.25) 50%), 
                        linear-gradient(90deg, rgba(255, 0, 0, 0.06), rgba(0, 255, 0, 0.02), rgba(0, 0, 255, 0.06));
            z-index: 999;
            background-size: 100% 2px, 3px 100%;
            pointer-events: none;
        }

        /* Header / Title */
        .header-container {
            text-align: center;
            margin-bottom: 40px;
            position: relative;
            z-index: 10;
        }

        h1 {
            color: var(--neon-blue);
            font-size: 3.5em;
            letter-spacing: 10px;
            margin: 0;
            text-shadow: 0 0 10px var(--neon-blue), 0 0 20px var(--neon-blue), 0 0 40px var(--neon-blue), 0 0 80px var(--neon-blue);
            border-bottom: 2px solid var(--neon-blue);
            display: inline-block;
            padding-bottom: 10px;
            position: relative;
        }

        h1::before, h1::after {
            content: '';
            position: absolute;
            bottom: -2px;
            width: 30px;
            height: 4px;
            background: #fff;
            box-shadow: 0 0 15px #fff;
        }
        h1::before { left: 0; }
        h1::after { right: 0; }

        .sys-status {
            margin-top: 15px;
            font-size: 1.4em;
            color: var(--neon-yellow);
            text-shadow: 0 0 8px var(--neon-yellow);
            animation: pulse 2s infinite;
        }

        /* Layout Grid */
        .dashboard-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 30px;
            position: relative;
            z-index: 10;
            max-width: 1800px;
            margin: 0 auto;
        }

        @media (max-width: 1400px) {
            .dashboard-grid {
                grid-template-columns: repeat(2, 1fr);
            }
        }
        @media (max-width: 900px) {
            .dashboard-grid {
                grid-template-columns: 1fr;
            }
        }

        /* Panels */
        .panel {
            background: var(--panel-bg);
            border: 2px solid;
            border-radius: 8px;
            padding: 25px;
            position: relative;
            overflow: hidden;
            display: flex;
            flex-direction: column;
            gap: 20px;
            backdrop-filter: blur(8px);
            box-shadow: inset 0 0 20px rgba(0,0,0,0.8);
        }

        /* Glitch / Scanner line inside panels */
        .panel::after {
            content: '';
            position: absolute;
            top: -50%; left: -50%;
            width: 200%; height: 2px;
            background: inherit;
            opacity: 0.7;
            transform: rotate(30deg);
            animation: scan 3s linear infinite;
            box-shadow: 0 0 10px inherit;
        }

        @keyframes scan {
            0% { transform: translateY(-100px) rotate(30deg); }
            100% { transform: translateY(1200px) rotate(30deg); }
        }

        /* Specific Panel Colors */
        .panel.hft {
            border-color: var(--neon-red);
            box-shadow: 0 0 20px rgba(255, 0, 60, 0.2) inset, 0 0 15px rgba(255, 0, 60, 0.4);
        }
        .panel.hft h2 { color: var(--neon-red); text-shadow: 0 0 15px var(--neon-red); border-bottom: 2px dashed var(--neon-red); }

        .panel.trinity {
            border-color: var(--neon-purple);
            box-shadow: 0 0 20px rgba(176, 38, 255, 0.2) inset, 0 0 15px rgba(176, 38, 255, 0.4);
        }
        .panel.trinity h2 { color: var(--neon-purple); text-shadow: 0 0 15px var(--neon-purple); border-bottom: 2px dashed var(--neon-purple); }

        .panel.market {
            border-color: var(--neon-blue);
            box-shadow: 0 0 20px rgba(0, 243, 255, 0.2) inset, 0 0 15px rgba(0, 243, 255, 0.4);
        }
        .panel.market h2 { color: var(--neon-blue); text-shadow: 0 0 15px var(--neon-blue); border-bottom: 2px dashed var(--neon-blue); }

        h2 {
            margin: 0 0 15px 0;
            padding-bottom: 12px;
            font-size: 1.8em;
            letter-spacing: 3px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        /* Cards inside panels */
        .card {
            background: rgba(0, 0, 0, 0.7);
            border-left: 4px solid;
            padding: 15px;
            position: relative;
            transition: all 0.3s ease;
        }
        .card:hover {
            transform: translateX(10px) scale(1.02);
            background: rgba(20, 20, 20, 0.9);
            box-shadow: 0 0 15px rgba(255,255,255,0.1);
        }

        .hft .card { border-color: var(--neon-red); }
        .trinity .card { border-color: var(--neon-purple); }
        .market .card { border-color: var(--neon-blue); }

        .card h3 {
            margin: 0 0 10px 0;
            font-size: 1.3em;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .card p {
            margin: 6px 0;
            font-size: 1em;
            color: #d0d0d0;
            display: flex;
            justify-content: space-between;
            border-bottom: 1px solid rgba(255,255,255,0.05);
            padding-bottom: 4px;
        }
        .card p:last-child {
            border-bottom: none;
        }

        .highlight { color: #fff; text-shadow: 0 0 8px #fff; font-weight: bold; }
        .good { color: var(--matrix-green); text-shadow: 0 0 8px var(--matrix-green); font-weight: bold; }
        .bad { color: var(--neon-red); text-shadow: 0 0 8px var(--neon-red); font-weight: bold; }
        .warn { color: var(--neon-yellow); text-shadow: 0 0 8px var(--neon-yellow); font-weight: bold; }

        /* Status indicators */
        .indicator {
            display: inline-block;
            width: 14px;
            height: 14px;
            border-radius: 50%;
            margin-right: 10px;
        }
        .indicator.active { background: var(--matrix-green); box-shadow: 0 0 12px var(--matrix-green); animation: blink 1.5s infinite alternate; }
        .indicator.standby { background: var(--neon-yellow); box-shadow: 0 0 12px var(--neon-yellow); }
        .indicator.combat { background: var(--neon-red); box-shadow: 0 0 12px var(--neon-red); animation: fast-blink 0.2s infinite alternate; }

        .tag {
            font-size: 0.65em;
            padding: 3px 8px;
            border: 1px solid;
            border-radius: 3px;
            letter-spacing: 2px;
            background: rgba(0,0,0,0.5);
        }

        /* Animations */
        @keyframes blink { 0% { opacity: 0.5; } 100% { opacity: 1; } }
        @keyframes fast-blink { 0% { opacity: 0.1; } 100% { opacity: 1; } }
        @keyframes pulse { 0% { opacity: 0.8; text-shadow: 0 0 8px var(--neon-yellow); } 50% { opacity: 1; text-shadow: 0 0 25px var(--neon-yellow); } 100% { opacity: 0.8; text-shadow: 0 0 8px var(--neon-yellow); } }

        /* Terminal/Logs block */
        .terminal {
            font-family: 'Share Tech Mono', monospace;
            font-size: 0.9em;
            background: rgba(0,0,0,0.8);
            border: 1px solid rgba(0, 243, 255, 0.4);
            padding: 12px;
            height: 180px;
            overflow: hidden;
            position: relative;
            box-shadow: inset 0 0 10px rgba(0, 243, 255, 0.1);
        }
        .terminal p {
            margin: 4px 0;
            color: #aaa;
            border-bottom: none;
        }
        .terminal p.alert { color: var(--neon-red); text-shadow: 0 0 5px var(--neon-red); }
        .terminal p.info { color: var(--matrix-green); text-shadow: 0 0 5px var(--matrix-green); }
        .terminal p.warn { color: var(--neon-yellow); text-shadow: 0 0 5px var(--neon-yellow); }
        
        /* Grid specifically for Oracle */
        .oracle-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
            margin-top: 15px;
        }
        .oracle-box {
            background: rgba(0,243,255,0.08);
            border: 1px solid rgba(0,243,255,0.4);
            padding: 12px;
            text-align: center;
            transition: all 0.2s;
        }
        .oracle-box:hover {
            background: rgba(0,243,255,0.15);
            box-shadow: 0 0 15px rgba(0,243,255,0.3);
        }
        .oracle-box .val {
            font-size: 1.6em;
            font-weight: bold;
            margin-top: 8px;
            color: var(--neon-blue);
            text-shadow: 0 0 10px var(--neon-blue);
        }

    </style>
</head>
<body>

    <div class="header-container">
        <h1>🛰️ ORBITAL COMMAND 🛰️</h1>
        <div class="sys-status">
            <span class="indicator active"></span> UPLINK ESTABLISHED // QUANTUM CORE STABLE // TACTICAL OVERVIEW
        </div>
        <div class="sys-status" style="color:var(--neon-purple); font-weight:bold; margin-top:10px; animation: pulse 1.5s infinite; text-shadow: 0 0 10px var(--neon-purple);">
            ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
        </div>
    </div>

    <div class="dashboard-grid">
        
        <!-- PANEL 1: ASSAULT TEAMS -->
        <div class="panel hft">
            <h2>⚔️ SQUADRE D'ASSALTO <span class="tag" style="color:var(--neon-red); border-color:var(--neon-red);">HFT DIV</span></h2>
            
            <div class="card">
                <h3><span><span class="indicator combat"></span>🐺 SQUADRA_ALPHA</span> <span class="tag" style="color:var(--neon-red); box-shadow: 0 0 5px var(--neon-red);">ENGAGED</span></h3>
                <p><span>> TACTIC:</span> <span class="highlight">SCALPER BINANCE</span></p>
                <p><span>> LATENCY:</span> <span class="good">8ms</span></p>
                <p><span>> PNL (24H):</span> <span class="good">+2.14%</span></p>
                <p><span>> APEX TICK:</span> <span class="highlight">BTC/USDT</span></p>
                <p><span>> ALGO:</span> <span class="highlight">MOMENTUM IGNITION</span></p>
            </div>
            
            <div class="card">
                <h3><span><span class="indicator combat"></span>🦅 SQUADRA_DELTA</span> <span class="tag" style="color:var(--neon-red); box-shadow: 0 0 5px var(--neon-red);">ENGAGED</span></h3>
                <p><span>> TACTIC:</span> <span class="highlight">ORDER FLOW ANALYSIS</span></p>
                <p><span>> WIN RATE:</span> <span class="good">74.8%</span></p>
                <p><span>> VECTORS:</span> <span class="warn">3 (LNG: BTC, ETH | SHT: SOL)</span></p>
                <p><span>> IMBALANCE:</span> <span class="good">DETECTED [BID SIDE]</span></p>
            </div>
            
            <div class="card">
                <h3><span><span class="indicator active"></span>🐍 SQUADRA_GAMMA</span> <span class="tag" style="color:var(--matrix-green); box-shadow: 0 0 5px var(--matrix-green);">ARBITRAGE</span></h3>
                <p><span>> TACTIC:</span> <span class="highlight">PAIRS TRADING BITGET</span></p>
                <p><span>> SPREAD TARGET:</span> <span class="highlight">> 0.45%</span></p>
                <p><span>> PAIRS LOCKED:</span> <span class="highlight">18</span></p>
                <p><span>> STATUS:</span> <span class="good">EXECUTING MEAN REVERSION</span></p>
            </div>
        </div>

        <!-- PANEL 2: TRINITY PROTOCOL -->
        <div class="panel trinity">
            <h2>🔺 PROTOCOLLO TRINITY <span class="tag" style="color:var(--neon-purple); border-color:var(--neon-purple);">CORE OPS</span></h2>
            
            <div class="card">
                <h3><span><span class="indicator active" style="background:var(--neon-purple); box-shadow:0 0 12px var(--neon-purple);"></span>🕴️ LO STROZZINO</span> <span class="tag" style="color:var(--neon-purple)">YIELDING</span></h3>
                <p><span>> DIRECTIVE:</span> <span class="highlight">FUNDING ARB</span></p>
                <p><span>> NET EXPOSURE:</span> <span class="good">DELTA NEUTRAL</span></p>
                <p><span>> CURRENT APR:</span> <span class="highlight" style="color:var(--neon-purple); text-shadow: 0 0 8px var(--neon-purple);">22.1%</span></p>
                <p><span>> CAPITAL DEPLOYED:</span> <span class="highlight">89%</span></p>
            </div>
            
            <div class="card">
                <h3><span><span class="indicator active" style="background:var(--neon-purple); box-shadow:0 0 12px var(--neon-purple);"></span>🧮 IL CONTABILE</span> <span class="tag" style="color:var(--neon-purple)">ACCUMULATING</span></h3>
                <p><span>> DIRECTIVE:</span> <span class="highlight">SMART DCA ENGINE</span></p>
                <p><span>> ASSET:</span> <span class="highlight">BTC/ETH MATRIX</span></p>
                <p><span>> NEXT EXECUTION:</span> <span class="warn" id="dca-timer">04:12:05</span></p>
                <p><span>> EFFICIENCY:</span> <span class="good">OPTIMAL</span></p>
            </div>
            
            <div class="card">
                <h3><span><span class="indicator active" style="background:var(--neon-purple); box-shadow:0 0 12px var(--neon-purple);"></span>🛡️ L'ANGELO CUSTODE</span> <span class="tag" style="color:var(--neon-purple)">GUARDING</span></h3>
                <p><span>> DIRECTIVE:</span> <span class="highlight">MEV PROTECTION (ARBITRUM)</span></p>
                <p><span>> MEMPOOL SCAN:</span> <span class="highlight">ACTIVE (30ms INT)</span></p>
                <p><span>> TX SHIELDED (30D):</span> <span class="good">24</span></p>
                <p><span>> THREAT LEVEL:</span> <span class="good">MINIMAL</span></p>
            </div>
        </div>

        <!-- PANEL 3: MARKET METRICS -->
        <div class="panel market">
            <h2>📡 METRICHE DI MERCATO <span class="tag" style="color:var(--neon-blue); border-color:var(--neon-blue);">DATA LINK</span></h2>
            
            <div class="card">
                <h3>👁️ THE ORACLE <span style="font-size:0.6em; color:#aaa;">[BINANCE SENTIMENT]</span></h3>
                <div class="oracle-grid">
                    <div class="oracle-box">
                        <div style="font-size:0.7em; color:#aaa; letter-spacing:1px;">GLOBAL TREND</div>
                        <div class="val" style="color:var(--matrix-green); text-shadow:0 0 8px var(--matrix-green);">BULLISH</div>
                    </div>
                    <div class="oracle-box">
                        <div style="font-size:0.7em; color:#aaa; letter-spacing:1px;">FEAR & GREED</div>
                        <div class="val" style="color:var(--neon-yellow); text-shadow:0 0 8px var(--neon-yellow);">78</div>
                    </div>
                    <div class="oracle-box">
                        <div style="font-size:0.7em; color:#aaa; letter-spacing:1px;">L/S RATIO</div>
                        <div class="val" id="ls-ratio">1.52</div>
                    </div>
                    <div class="oracle-box">
                        <div style="font-size:0.7em; color:#aaa; letter-spacing:1px;">VOLATILITY</div>
                        <div class="val" style="color:var(--neon-red); text-shadow:0 0 8px var(--neon-red);">EXTREME</div>
                    </div>
                </div>
            </div>
            
            <div class="card">
                <h3>🐋 WHALE TRACKER <span style="font-size:0.6em; color:#aaa;">[LIVE ON-CHAIN FEED]</span></h3>
                <div class="terminal" id="whale-feed">
                    <p class="alert">[17:01:12] ALERT: 2,500 BTC -> Coinbase</p>
                    <p class="info">[16:58:05] INFO: 18,000 ETH -> Unknown DEX</p>
                    <p class="alert">[16:52:33] ALERT: 100M USDT -> Binance</p>
                    <p class="info">[16:45:10] INFO: 800 BTC -> Bitfinex</p>
                    <p class="warn">[16:35:22] WARN: 15M USDC -> Kraken (Anomalous)</p>
                    <p class="alert">[16:29:01] ALERT: 4,100 BTC -> Unknown Cold Wallet</p>
                </div>
            </div>
        </div>

    </div>

    <script>
        // LS Ratio fluttuante
        setInterval(() => {
            const ratios = ["1.52", "1.54", "1.51", "1.55", "1.50", "1.56"];
            document.getElementById('ls-ratio').innerText = ratios[Math.floor(Math.random() * ratios.length)];
        }, 1800);

        // DCA Timer decrement
        let dcaSeconds = 3 * 3600 + 45 * 60 + 12;
        setInterval(() => {
            if(dcaSeconds > 0) dcaSeconds--;
            let h = Math.floor(dcaSeconds / 3600).toString().padStart(2, '0');
            let m = Math.floor((dcaSeconds % 3600) / 60).toString().padStart(2, '0');
            let s = (dcaSeconds % 60).toString().padStart(2, '0');
            document.getElementById('dca-timer').innerText = `${h}:${m}:${s}`;
        }, 1000);

        // Finto terminale Whale Tracker
        const whaleLogs = [
            { type: 'alert', msg: "ALERT: 850 BTC -> Binance" },
            { type: 'info', msg: "INFO: 20M USDT -> OKX" },
            { type: 'alert', msg: "CRITICAL: 5,000 ETH -> Kraken" },
            { type: 'info', msg: "INFO: 25M USDC -> Bybit" },
            { type: 'alert', msg: "ALERT: 3,200 BTC -> Unknown Wallet" },
            { type: 'warn', msg: "WARN: Large slippage detected on UNI pool" },
            { type: 'info', msg: "INFO: 1,000 WBTC -> Aave Vault" }
        ];

        setInterval(() => {
            const feed = document.getElementById('whale-feed');
            const log = whaleLogs[Math.floor(Math.random() * whaleLogs.length)];
            const now = new Date();
            const timeStr = `${now.getHours().toString().padStart(2,'0')}:${now.getMinutes().toString().padStart(2,'0')}:${now.getSeconds().toString().padStart(2,'0')}`;
            
            const p = document.createElement('p');
            p.className = log.type;
            p.innerText = `[${timeStr}] ${log.msg}`;
            
            feed.prepend(p);
            if(feed.children.length > 7) {
                feed.removeChild(feed.lastChild);
            }
        }, 3500);
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_CONTENT)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5050, debug=False)
# PROTOCOLLO TRINITY UPDATE
