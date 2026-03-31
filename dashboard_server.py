from flask import Flask, render_template_string
import os

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ORBITAL COMMAND | NUVOLA</title>
    <style>
        :root {
            --neon-green: #00ff41;
            --neon-blue: #00e5ff;
            --neon-pink: #ff00ff;
            --neon-red: #ff003c;
            --neon-yellow: #fcee0a;
            --bg-color: #020202;
            --panel-bg: rgba(0, 10, 0, 0.85);
            --glitch-offset: 3px;
        }
        
        * { box-sizing: border-box; }
        
        body {
            background-color: var(--bg-color);
            color: var(--neon-green);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            background-image: 
                linear-gradient(rgba(0, 255, 65, 0.05) 1px, transparent 1px),
                linear-gradient(90deg, rgba(0, 255, 65, 0.05) 1px, transparent 1px);
            background-size: 30px 30px;
            background-position: center;
            overflow-x: hidden;
            text-shadow: 0 0 5px var(--neon-green);
        }

        /* CRT Overlay */
        body::after {
            content: " ";
            display: block;
            position: fixed;
            top: 0; left: 0; bottom: 0; right: 0;
            background: rgba(18, 16, 16, 0.1);
            opacity: 0;
            z-index: 2;
            pointer-events: none;
            animation: flicker 0.15s infinite;
        }

        h1, h2, h3 {
            text-transform: uppercase;
            margin-top: 0;
            letter-spacing: 3px;
            font-weight: 800;
        }

        .header {
            text-align: center;
            border-bottom: 3px solid var(--neon-green);
            padding-bottom: 15px;
            margin-bottom: 40px;
            position: relative;
        }
        
        .header h1 {
            font-size: 3rem;
            margin-bottom: 5px;
            color: #fff;
            text-shadow: 
                0 0 10px #fff,
                0 0 20px #fff,
                0 0 40px var(--neon-green),
                0 0 80px var(--neon-green);
            animation: text-flicker 3s infinite alternate;
        }

        .trinity-badge {
            display: inline-block;
            margin-top: 15px;
            padding: 10px 20px;
            border: 2px dashed var(--neon-blue);
            color: var(--neon-blue);
            font-weight: bold;
            font-size: 1.4rem;
            text-shadow: 0 0 15px var(--neon-blue);
            box-shadow: inset 0 0 15px rgba(0, 229, 255, 0.3);
            animation: pulse-border 2s infinite;
        }

        .container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(380px, 1fr));
            gap: 30px;
            max-width: 1600px;
            margin: 0 auto;
        }

        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-green);
            box-shadow: 0 0 20px rgba(0, 255, 65, 0.15), inset 0 0 15px rgba(0, 255, 65, 0.1);
            padding: 25px;
            border-radius: 2px;
            position: relative;
            backdrop-filter: blur(4px);
            transition: transform 0.3s ease, box-shadow 0.3s ease;
        }
        
        .panel:hover {
            transform: translateY(-5px);
            box-shadow: 0 0 30px rgba(0, 255, 65, 0.3), inset 0 0 20px rgba(0, 255, 65, 0.2);
        }

        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; height: 3px;
            background: var(--neon-green);
            box-shadow: 0 0 15px var(--neon-green);
        }

        .panel.blue {
            border-color: var(--neon-blue);
            color: var(--neon-blue);
            text-shadow: 0 0 5px var(--neon-blue);
        }
        .panel.blue::before { background: var(--neon-blue); box-shadow: 0 0 15px var(--neon-blue); }
        .panel.blue .item { border-color: rgba(0, 229, 255, 0.3); }
        .panel.blue h2 { border-bottom-color: var(--neon-blue); text-shadow: 0 0 10px var(--neon-blue); }

        .panel.pink {
            border-color: var(--neon-pink);
            color: var(--neon-pink);
            text-shadow: 0 0 5px var(--neon-pink);
        }
        .panel.pink::before { background: var(--neon-pink); box-shadow: 0 0 15px var(--neon-pink); }
        .panel.pink .item { border-color: rgba(255, 0, 255, 0.3); }
        .panel.pink h2 { border-bottom-color: var(--neon-pink); text-shadow: 0 0 10px var(--neon-pink); }

        .panel h2 {
            border-bottom: 2px solid var(--neon-green);
            padding-bottom: 12px;
            text-shadow: 0 0 10px var(--neon-green);
            font-size: 1.5rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .item {
            margin-bottom: 25px;
            padding: 15px;
            background: rgba(0, 0, 0, 0.6);
            border: 1px solid rgba(0, 255, 65, 0.3);
            border-left: 4px solid var(--neon-green);
            position: relative;
        }
        
        .panel.blue .item { border-left-color: var(--neon-blue); }
        .panel.pink .item { border-left-color: var(--neon-pink); }

        .status {
            float: right;
            font-weight: 900;
            padding: 2px 8px;
            border-radius: 2px;
            background: #000;
            border: 1px solid currentColor;
            animation: blink 2s infinite;
            text-shadow: 0 0 8px currentColor;
            letter-spacing: 1px;
        }

        .status.online { color: var(--neon-green); border-color: var(--neon-green); }
        .status.active { color: var(--neon-blue); border-color: var(--neon-blue); }
        .status.hunting { color: var(--neon-pink); border-color: var(--neon-pink); }
        .status.danger { color: var(--neon-red); border-color: var(--neon-red); animation: fast-blink 0.5s infinite;}

        .bar-bg {
            background: #0a0a0a;
            height: 8px;
            width: 100%;
            margin-top: 12px;
            border: 1px solid #222;
            position: relative;
            overflow: hidden;
        }
        
        .bar-fill {
            height: 100%;
            background: var(--neon-green);
            width: 0%;
            box-shadow: 0 0 10px var(--neon-green);
            transition: width 0.4s cubic-bezier(0.4, 0, 0.2, 1);
            position: relative;
        }
        
        .bar-fill::after {
            content: '';
            position: absolute;
            top: 0; left: 0; bottom: 0; right: 0;
            background: linear-gradient(90deg, transparent, rgba(255,255,255,0.4), transparent);
            animation: shine 2s infinite;
        }

        .blue .bar-fill { background: var(--neon-blue); box-shadow: 0 0 10px var(--neon-blue); }
        .pink .bar-fill { background: var(--neon-pink); box-shadow: 0 0 10px var(--neon-pink); }
        .danger .bar-fill { background: var(--neon-red); box-shadow: 0 0 10px var(--neon-red); }

        .console-text {
            font-size: 0.9em;
            opacity: 0.9;
            margin-top: 10px;
            display: block;
            background: #000;
            padding: 8px;
            border: 1px dashed rgba(255,255,255,0.2);
            line-height: 1.4;
        }

        .metric-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
            margin-top: 15px;
            font-size: 0.85em;
        }
        
        .metric-box {
            background: rgba(0,0,0,0.8);
            border: 1px solid currentColor;
            padding: 8px;
            text-align: center;
        }
        
        .metric-val {
            font-size: 1.4em;
            font-weight: bold;
            display: block;
            margin-top: 4px;
        }

        /* Animations */
        @keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
        @keyframes fast-blink { 0%, 100% { opacity: 1; } 50% { opacity: 0; } }
        @keyframes flicker { 0% { opacity: 0.05; } 100% { opacity: 0.15; } }
        @keyframes text-flicker {
            0%, 19.999%, 22%, 62.999%, 64%, 64.999%, 70%, 100% { opacity: 1; text-shadow: 0 0 20px var(--neon-green); }
            20%, 21.999%, 63%, 63.999%, 65%, 69.999% { opacity: 0.4; text-shadow: none; }
        }
        @keyframes pulse-border {
            0% { box-shadow: inset 0 0 10px rgba(0, 229, 255, 0.2), 0 0 10px rgba(0, 229, 255, 0.2); }
            50% { box-shadow: inset 0 0 25px rgba(0, 229, 255, 0.6), 0 0 25px rgba(0, 229, 255, 0.6); }
            100% { box-shadow: inset 0 0 10px rgba(0, 229, 255, 0.2), 0 0 10px rgba(0, 229, 255, 0.2); }
        }
        @keyframes shine {
            0% { transform: translateX(-100%); }
            100% { transform: translateX(100%); }
        }

        .scanline {
            width: 100%;
            height: 150px;
            z-index: 9999;
            position: fixed;
            pointer-events: none;
            background: linear-gradient(0deg, rgba(0,0,0,0) 0%, rgba(0, 255, 65, 0.15) 50%, rgba(0,0,0,0) 100%);
            animation: scanline 6s linear infinite;
            top: -150px;
            left: 0;
        }
        @keyframes scanline { 0% { top: -150px; } 100% { top: 100vh; } }
        
        .live-indicator {
            display: inline-block;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background-color: var(--neon-red);
            box-shadow: 0 0 10px var(--neon-red);
            animation: fast-blink 1s infinite;
            margin-right: 10px;
        }
    </style>
</head>
<body>
    <div class="scanline"></div>
    
    <div class="header">
        <h1><span class="live-indicator"></span>ORBITAL COMMAND</h1>
        <p style="letter-spacing: 5px; opacity: 0.8;">/// NUVOLA TACTICAL OVERVIEW | CLASSIFIED QUANTITATIVE HUB ///</p>
        <div class="trinity-badge">
            ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
        </div>
    </div>

    <div class="container">
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <h2><span>⚔️ SQUADRE D'ASSALTO [HFT]</span> <span style="font-size: 0.6em; color: var(--neon-green);">SECURE</span></h2>
            
            <div class="item">
                <strong>[ 🐺 SQUADRA_ALPHA ]</strong> <span class="status online">ENGAGED</span>
                <br><small>Task: Binance High-Frequency Scalping | Engine: Rust Core</small>
                <div class="metric-grid">
                    <div class="metric-box">Latency <span class="metric-val" id="lat-alpha">12ms</span></div>
                    <div class="metric-box">Win Rate <span class="metric-val">71.4%</span></div>
                </div>
                <div class="bar-bg"><div class="bar-fill" style="width: 87%;"></div></div>
            </div>
            
            <div class="item">
                <strong>[ 🦅 SQUADRA_DELTA ]</strong> <span class="status active" style="color:var(--neon-green); border-color:var(--neon-green);">SPOOFING</span>
                <br><small>Task: Order Flow Manipulation / Imbalance | Exchange: Bybit</small>
                <div class="metric-grid">
                    <div class="metric-box">Volume 24h <span class="metric-val" style="color:var(--neon-yellow)">$8.4M</span></div>
                    <div class="metric-box">Orders/s <span class="metric-val" id="ops-delta">142</span></div>
                </div>
                <div class="bar-bg"><div class="bar-fill" style="width: 65%;"></div></div>
            </div>
            
            <div class="item">
                <strong>[ 🦂 SQUADRA_GAMMA ]</strong> <span class="status hunting" style="color:var(--neon-green); border-color:var(--neon-green);">HUNTING</span>
                <br><small>Task: Statistical Arbitrage / Pairs Trading | Exchange: Bitget</small>
                <div class="metric-grid">
                    <div class="metric-box">Active Pairs <span class="metric-val">14</span></div>
                    <div class="metric-box">Spread <span class="metric-val" id="spread-gamma">0.18%</span></div>
                </div>
                <div class="bar-bg"><div class="bar-fill" style="width: 42%;"></div></div>
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel blue">
            <h2><span>⚕️ PROTOCOLLO TRINITY</span> <span style="font-size: 0.6em;">BACKGROUND</span></h2>
            
            <div class="item">
                <strong>[ 🦇 Lo Strozzino ]</strong> <span class="status active">EXTRACTING</span>
                <br><small>Vector: Perpetual Funding Arbitrage Delta-Neutral</small>
                <div class="console-text">
                    > Shorting over-leveraged longs (DOGE/USDT)<br>
                    > Yield capture: <span style="color:var(--neon-blue); font-weight:bold;">+24.1% APY</span><br>
                    > Exposure hedge: 99.8% Perfect
                </div>
                <div class="bar-bg"><div class="bar-fill" style="width: 94%;"></div></div>
            </div>
            
            <div class="item">
                <strong>[ 🧮 Il Contabile ]</strong> <span class="status active">ACCUMULATING</span>
                <br><small>Vector: Dynamic DCA & Smart Reserves Routing</small>
                <div class="console-text">
                    > Purchasing BTC at support band ($61k)<br>
                    > Cold storage sweep scheduled in 04:12:00<br>
                    > Liquidity buffer: <span style="color:#0f0">OPTIMAL</span>
                </div>
                <div class="bar-bg"><div class="bar-fill" style="width: 100%;"></div></div>
            </div>
            
            <div class="item">
                <strong>[ 👼 L'Angelo Custode ]</strong> <span class="status hunting" style="color:var(--neon-blue); border-color:var(--neon-blue);">SNIPING</span>
                <br><small>Vector: Arbitrum MEV / Dark Forest Frontrunning</small>
                <div class="console-text">
                    > Mempool scanner active...<br>
                    > Pending victim tx detected (Slippage: 15%)<br>
                    > Deploying sandwich payload... <span style="color:var(--neon-pink)">[WAITING]</span>
                </div>
                <div class="bar-bg"><div class="bar-fill" style="width: 15%;"></div></div>
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel pink">
            <h2><span>📡 METRICHE DI MERCATO</span> <span style="font-size: 0.6em;">LIVE FEED</span></h2>
            
            <div class="item">
                <strong>[ 👁️ The Oracle ]</strong> <span class="status online" style="color:var(--neon-pink); border-color:var(--neon-pink);">SYNCED</span>
                <br><small>Source: Binance Orderbook + Global Sentiment NLP</small>
                <div class="console-text">
                    > Market Regime: <span style="color:#0f0; font-weight:bold; text-shadow:0 0 8px #0f0;">BULLISH TREND (82%)</span><br>
                    > Volatility Index: <span id="vol-idx">45.2</span> (Rising)<br>
                    > AI Sentiment: "Fear missing out accelerating."
                </div>
            </div>
            
            <div class="item">
                <strong>[ 🐳 Whale Tracker ]</strong> <span class="status danger">ALERT</span>
                <br><small>Source: On-Chain Heuristics (ETH/ERC-20)</small>
                <div class="console-text" style="border-color: var(--neon-red);">
                    > [WARNING] 25,000 ETH moved to Binance.<br>
                    > Entity: Unknown (Wallet 0x7aF...9c1)<br>
                    > Dump probability: <span style="color:var(--neon-red);">HIGH (DEFCON 2)</span>
                </div>
            </div>
            
            <div class="item">
                <strong>[ ⚡ NUVOLA CORE ]</strong> <span class="status online" style="color:var(--neon-pink); border-color:var(--neon-pink);">NOMINAL</span>
                <br><small>Infrastructure Health & Telemetry</small>
                <div class="metric-grid">
                    <div class="metric-box">CPU <span class="metric-val" id="cpu-load">14%</span></div>
                    <div class="metric-box">RAM <span class="metric-val" id="ram-load">12.4GB</span></div>
                    <div class="metric-box" style="grid-column: span 2;">Net Egress <span class="metric-val" id="net-speed">1.4 GB/s</span></div>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        // Cyberpunk dynamic data simulation
        setInterval(() => {
            // Bars
            document.querySelectorAll('.bar-fill').forEach(bar => {
                let current = parseFloat(bar.style.width) || 50;
                let jitter = (Math.random() - 0.5) * 8;
                let next = Math.max(5, Math.min(100, current + jitter));
                bar.style.width = next + '%';
            });
            
            // Random numbers for specific metrics
            if(Math.random() > 0.5) document.getElementById('lat-alpha').innerText = (10 + Math.random() * 5).toFixed(1) + 'ms';
            if(Math.random() > 0.7) document.getElementById('ops-delta').innerText = Math.floor(100 + Math.random() * 80);
            if(Math.random() > 0.6) document.getElementById('spread-gamma').innerText = (0.10 + Math.random() * 0.15).toFixed(2) + '%';
            if(Math.random() > 0.5) document.getElementById('vol-idx').innerText = (40 + Math.random() * 10).toFixed(1);
            if(Math.random() > 0.3) document.getElementById('cpu-load').innerText = Math.floor(10 + Math.random() * 25) + '%';
            if(Math.random() > 0.7) document.getElementById('net-speed').innerText = (1.0 + Math.random() * 0.8).toFixed(1) + ' GB/s';
            
        }, 1200);
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    # Usa la porta 5000 di default
    app.run(host='0.0.0.0', port=5000)
