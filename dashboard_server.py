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
            --bg-color: #020202;
            --panel-bg: rgba(10, 15, 12, 0.85);
            --grid-color: rgba(57, 255, 20, 0.05);
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
            background-size: 30px 30px;
            overflow-x: hidden;
            text-transform: uppercase;
        }

        /* CRT Effect / Scanlines */
        body::after {
            content: " ";
            display: block;
            position: fixed;
            top: 0; left: 0; bottom: 0; right: 0;
            background: linear-gradient(rgba(18, 16, 16, 0) 50%, rgba(0, 0, 0, 0.25) 50%), 
                        linear-gradient(90deg, rgba(255, 0, 0, 0.06), rgba(0, 255, 0, 0.02), rgba(0, 0, 255, 0.06));
            z-index: 999;
            background-size: 100% 3px, 3px 100%;
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
            font-size: 3em;
            letter-spacing: 8px;
            margin: 0;
            text-shadow: 0 0 10px var(--neon-blue), 0 0 20px var(--neon-blue), 0 0 40px var(--neon-blue);
            border-bottom: 2px solid var(--neon-blue);
            display: inline-block;
            padding-bottom: 10px;
            position: relative;
        }

        h1::before, h1::after {
            content: '';
            position: absolute;
            bottom: -2px;
            width: 20px;
            height: 2px;
            background: #fff;
            box-shadow: 0 0 10px #fff;
        }
        h1::before { left: 0; }
        h1::after { right: 0; }

        .sys-status {
            margin-top: 15px;
            font-size: 1.2em;
            color: var(--neon-yellow);
            text-shadow: 0 0 5px var(--neon-yellow);
            animation: pulse 2s infinite;
        }

        /* Layout Grid */
        .dashboard-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 25px;
            position: relative;
            z-index: 10;
            max-width: 1600px;
            margin: 0 auto;
        }

        @media (max-width: 1200px) {
            .dashboard-grid {
                grid-template-columns: repeat(2, 1fr);
            }
        }
        @media (max-width: 800px) {
            .dashboard-grid {
                grid-template-columns: 1fr;
            }
        }

        /* Panels */
        .panel {
            background: var(--panel-bg);
            border: 1px solid;
            border-radius: 4px;
            padding: 20px;
            position: relative;
            overflow: hidden;
            display: flex;
            flex-direction: column;
            gap: 15px;
            backdrop-filter: blur(5px);
        }

        /* Glitch / Scanner line inside panels */
        .panel::after {
            content: '';
            position: absolute;
            top: -50%; left: -50%;
            width: 200%; height: 2px;
            background: inherit;
            opacity: 0.5;
            transform: rotate(30deg);
            animation: scan 4s linear infinite;
        }

        @keyframes scan {
            0% { transform: translateY(-100px) rotate(30deg); }
            100% { transform: translateY(1000px) rotate(30deg); }
        }

        /* Specific Panel Colors */
        .panel.hft {
            border-color: var(--neon-red);
            box-shadow: 0 0 15px rgba(255, 0, 60, 0.15) inset, 0 0 10px rgba(255, 0, 60, 0.3);
        }
        .panel.hft h2 { color: var(--neon-red); text-shadow: 0 0 10px var(--neon-red); border-bottom: 1px dashed var(--neon-red); }

        .panel.trinity {
            border-color: var(--neon-pink);
            box-shadow: 0 0 15px rgba(255, 0, 255, 0.15) inset, 0 0 10px rgba(255, 0, 255, 0.3);
        }
        .panel.trinity h2 { color: var(--neon-pink); text-shadow: 0 0 10px var(--neon-pink); border-bottom: 1px dashed var(--neon-pink); }

        .panel.market {
            border-color: var(--neon-blue);
            box-shadow: 0 0 15px rgba(0, 243, 255, 0.15) inset, 0 0 10px rgba(0, 243, 255, 0.3);
        }
        .panel.market h2 { color: var(--neon-blue); text-shadow: 0 0 10px var(--neon-blue); border-bottom: 1px dashed var(--neon-blue); }

        h2 {
            margin: 0 0 10px 0;
            padding-bottom: 10px;
            font-size: 1.6em;
            letter-spacing: 2px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        /* Cards inside panels */
        .card {
            background: rgba(0, 0, 0, 0.6);
            border-left: 3px solid;
            padding: 12px;
            position: relative;
            transition: all 0.2s ease;
        }
        .card:hover {
            transform: translateX(5px);
            background: rgba(20, 20, 20, 0.8);
        }

        .hft .card { border-color: var(--neon-red); }
        .trinity .card { border-color: var(--neon-pink); }
        .market .card { border-color: var(--neon-blue); }

        .card h3 {
            margin: 0 0 8px 0;
            font-size: 1.2em;
            display: flex;
            justify-content: space-between;
        }
        
        .card p {
            margin: 4px 0;
            font-size: 0.9em;
            color: #ccc;
            display: flex;
            justify-content: space-between;
        }

        .highlight { color: #fff; text-shadow: 0 0 5px #fff; }
        .good { color: var(--matrix-green); text-shadow: 0 0 5px var(--matrix-green); }
        .bad { color: var(--neon-red); text-shadow: 0 0 5px var(--neon-red); }
        .warn { color: var(--neon-yellow); text-shadow: 0 0 5px var(--neon-yellow); }

        /* Status indicators */
        .indicator {
            display: inline-block;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 8px;
        }
        .indicator.active { background: var(--matrix-green); box-shadow: 0 0 10px var(--matrix-green); animation: blink 1s infinite alternate; }
        .indicator.standby { background: var(--neon-yellow); box-shadow: 0 0 10px var(--neon-yellow); }
        .indicator.combat { background: var(--neon-red); box-shadow: 0 0 10px var(--neon-red); animation: fast-blink 0.3s infinite alternate; }

        .tag {
            font-size: 0.6em;
            padding: 2px 6px;
            border: 1px solid;
            border-radius: 2px;
            letter-spacing: 1px;
        }

        /* Animations */
        @keyframes blink { 0% { opacity: 0.4; } 100% { opacity: 1; } }
        @keyframes fast-blink { 0% { opacity: 0.2; } 100% { opacity: 1; } }
        @keyframes pulse { 0% { opacity: 0.8; text-shadow: 0 0 5px var(--neon-yellow); } 50% { opacity: 1; text-shadow: 0 0 20px var(--neon-yellow); } 100% { opacity: 0.8; text-shadow: 0 0 5px var(--neon-yellow); } }

        /* Terminal/Logs block */
        .terminal {
            font-family: monospace;
            font-size: 0.85em;
            background: #000;
            border: 1px solid #333;
            padding: 10px;
            height: 140px;
            overflow: hidden;
            position: relative;
        }
        .terminal p {
            margin: 2px 0;
            color: #888;
        }
        .terminal p.alert { color: var(--neon-red); }
        .terminal p.info { color: var(--neon-blue); }
        
        /* Grid specifically for Oracle */
        .oracle-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
            margin-top: 10px;
        }
        .oracle-box {
            background: rgba(0,243,255,0.05);
            border: 1px solid rgba(0,243,255,0.3);
            padding: 8px;
            text-align: center;
        }
        .oracle-box .val {
            font-size: 1.4em;
            font-weight: bold;
            margin-top: 5px;
            color: var(--neon-blue);
            text-shadow: 0 0 8px var(--neon-blue);
        }

    </style>
</head>
<body>

    <div class="header-container">
        <h1>🛰️ ORBITAL COMMAND</h1>
        <div class="sys-status">
            <span class="indicator active"></span> SYSTEM ONLINE // UPLINK ESTABLISHED // QUANTUM CORE STABLE
        </div>
        <div class="sys-status" style="color:var(--neon-pink); font-weight:bold; margin-top:10px; animation: pulse 2s infinite;">
            ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
        </div>
    </div>

    <div class="dashboard-grid">
        
        <!-- PANEL 1: ASSAULT TEAMS -->
        <div class="panel hft">
            <h2>⚔️ SQUADRE D'ASSALTO <span class="tag" style="color:var(--neon-red); border-color:var(--neon-red);">HFT DIV</span></h2>
            
            <div class="card">
                <h3><span><span class="indicator combat"></span>🐺 SQUADRA_ALPHA</span> <span class="tag" style="color:var(--neon-red)">ENGAGED</span></h3>
                <p><span>> MISSION:</span> <span class="highlight">SCALPER BINANCE</span></p>
                <p><span>> LATENCY:</span> <span class="good">12ms</span></p>
                <p><span>> PNL (24H):</span> <span class="good">+1.85%</span></p>
                <p><span>> APEX TICK:</span> <span class="highlight">BTC/USDT</span></p>
            </div>
            
            <div class="card">
                <h3><span><span class="indicator combat"></span>🦅 SQUADRA_DELTA</span> <span class="tag" style="color:var(--neon-red)">ENGAGED</span></h3>
                <p><span>> MISSION:</span> <span class="highlight">ORDER FLOW ANALYSIS</span></p>
                <p><span>> WIN RATE:</span> <span class="good">71.2%</span></p>
                <p><span>> ACTIVE VECTORS:</span> <span class="warn">3 (LNG: BTC, ETH | SHT: SOL)</span></p>
                <p><span>> BOOK IMBALANCE:</span> <span class="good">DETECTED</span></p>
            </div>
            
            <div class="card">
                <h3><span><span class="indicator standby"></span>🐍 SQUADRA_GAMMA</span> <span class="tag" style="color:var(--neon-yellow)">STANDBY</span></h3>
                <p><span>> MISSION:</span> <span class="highlight">PAIRS TRADING BITGET</span></p>
                <p><span>> SPREAD TARGET:</span> <span class="highlight">> 0.5%</span></p>
                <p><span>> PAIRS LOCKED:</span> <span class="highlight">14</span></p>
                <p><span>> STATUS:</span> <span class="warn">AWAITING VOLATILITY SPIKE</span></p>
            </div>
        </div>

        <!-- PANEL 2: TRINITY PROTOCOL -->
        <div class="panel trinity">
            <h2>🔺 TRINITY PROTOCOL <span class="tag" style="color:var(--neon-pink); border-color:var(--neon-pink);">CORE OPS</span></h2>
            
            <div class="card">
                <h3><span><span class="indicator active" style="background:var(--neon-pink); box-shadow:0 0 10px var(--neon-pink);"></span>🕴️ LO STROZZINO</span> <span class="tag" style="color:var(--neon-pink)">YIELDING</span></h3>
                <p><span>> DIRECTIVE:</span> <span class="highlight">FUNDING ARBITRAGE</span></p>
                <p><span>> NET EXPOSURE:</span> <span class="good">DELTA NEUTRAL</span></p>
                <p><span>> CURRENT APR:</span> <span class="highlight" style="color:var(--neon-pink); text-shadow: 0 0 5px var(--neon-pink);">18.4%</span></p>
                <p><span>> CAPITAL DEPLOYED:</span> <span class="highlight">84%</span></p>
            </div>
            
            <div class="card">
                <h3><span><span class="indicator active" style="background:var(--neon-pink); box-shadow:0 0 10px var(--neon-pink);"></span>🧮 IL CONTABILE</span> <span class="tag" style="color:var(--neon-pink)">ACCUMULATING</span></h3>
                <p><span>> DIRECTIVE:</span> <span class="highlight">DCA ENGINE</span></p>
                <p><span>> ASSET:</span> <span class="highlight">BTC/ETH MATRIX</span></p>
                <p><span>> NEXT EXECUTION:</span> <span class="warn" id="dca-timer">04:12:05</span></p>
                <p><span>> EFFICIENCY:</span> <span class="good">OPTIMAL</span></p>
            </div>
            
            <div class="card">
                <h3><span><span class="indicator active" style="background:var(--neon-pink); box-shadow:0 0 10px var(--neon-pink);"></span>🛡️ L'ANGELO CUSTODE</span> <span class="tag" style="color:var(--neon-pink)">GUARDING</span></h3>
                <p><span>> DIRECTIVE:</span> <span class="highlight">MEV PROTECTION (ARBITRUM)</span></p>
                <p><span>> MEMPOOL SCAN:</span> <span class="highlight">ACTIVE (50ms INT)</span></p>
                <p><span>> TX SHIELDED (30D):</span> <span class="good">17</span></p>
                <p><span>> THREAT LEVEL:</span> <span class="good">LOW</span></p>
            </div>
        </div>

        <!-- PANEL 3: MARKET METRICS -->
        <div class="panel market">
            <h2>📡 MARKET INTELLIGENCE <span class="tag" style="color:var(--neon-blue); border-color:var(--neon-blue);">DATA LINK</span></h2>
            
            <div class="card">
                <h3>👁️ THE ORACLE <span style="font-size:0.6em; color:#888;">(BINANCE SENTIMENT)</span></h3>
                <div class="oracle-grid">
                    <div class="oracle-box">
                        <div style="font-size:0.7em; color:#aaa;">GLOBAL TREND</div>
                        <div class="val" style="color:var(--matrix-green); text-shadow:0 0 5px var(--matrix-green);">BULLISH</div>
                    </div>
                    <div class="oracle-box">
                        <div style="font-size:0.7em; color:#aaa;">FEAR & GREED</div>
                        <div class="val">74</div>
                    </div>
                    <div class="oracle-box">
                        <div style="font-size:0.7em; color:#aaa;">L/S RATIO</div>
                        <div class="val" id="ls-ratio">1.45</div>
                    </div>
                    <div class="oracle-box">
                        <div style="font-size:0.7em; color:#aaa;">VOLATILITY</div>
                        <div class="val" style="color:var(--neon-red); text-shadow:0 0 5px var(--neon-red);">HIGH</div>
                    </div>
                </div>
            </div>
            
            <div class="card">
                <h3>🐋 WHALE TRACKER <span style="font-size:0.6em; color:#888;">(LIVE FEED)</span></h3>
                <div class="terminal" id="whale-feed">
                    <p class="alert">[16:54:12] ALERT: 1,500 BTC -> Coinbase</p>
                    <p class="info">[16:50:05] INFO: 12,000 ETH -> Unknown</p>
                    <p class="alert">[16:42:33] ALERT: 50M USDT -> Binance</p>
                    <p class="info">[16:30:10] INFO: 400 BTC -> Bitfinex</p>
                    <p class="info">[16:15:22] INFO: 8M USDC -> Kraken</p>
                    <p class="alert">[15:59:01] ALERT: 2,100 BTC -> Unknown</p>
                </div>
            </div>
        </div>

    </div>

    <script>
        // LS Ratio fluttuante
        setInterval(() => {
            const ratios = ["1.45", "1.46", "1.44", "1.47", "1.43", "1.48"];
            document.getElementById('ls-ratio').innerText = ratios[Math.floor(Math.random() * ratios.length)];
        }, 2500);

        // DCA Timer decrement
        let dcaSeconds = 4 * 3600 + 12 * 60 + 5;
        setInterval(() => {
            if(dcaSeconds > 0) dcaSeconds--;
            let h = Math.floor(dcaSeconds / 3600).toString().padStart(2, '0');
            let m = Math.floor((dcaSeconds % 3600) / 60).toString().padStart(2, '0');
            let s = (dcaSeconds % 60).toString().padStart(2, '0');
            document.getElementById('dca-timer').innerText = `${h}:${m}:${s}`;
        }, 1000);

        // Finto terminale Whale Tracker
        const whaleLogs = [
            { type: 'alert', msg: "ALERT: 500 BTC -> Binance" },
            { type: 'info', msg: "INFO: 10M USDT -> OKX" },
            { type: 'alert', msg: "CRITICAL: 3,000 ETH -> Kraken" },
            { type: 'info', msg: "INFO: 15M USDC -> Bybit" },
            { type: 'alert', msg: "ALERT: 1,200 BTC -> Unknown Wallet" }
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
            if(feed.children.length > 8) {
                feed.removeChild(feed.lastChild);
            }
        }, 5000);
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_CONTENT)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5050, debug=False)
