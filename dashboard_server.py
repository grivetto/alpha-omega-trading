from flask import Flask

app = Flask(__name__)

HTML_CONTENT = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NUVOLA // ORBITAL COMMAND</title>
    <style>
        :root {
            --neon-green: #0fa;
            --neon-blue: #0ff;
            --neon-pink: #f0f;
            --neon-yellow: #ff0;
            --neon-red: #f00;
            --bg-color: #050505;
            --panel-bg: rgba(10, 15, 20, 0.85);
            --grid-color: rgba(0, 255, 255, 0.05);
        }
        
        body {
            background-color: var(--bg-color);
            color: var(--neon-green);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 30px;
            background-image: 
                linear-gradient(var(--grid-color) 1px, transparent 1px),
                linear-gradient(90deg, var(--grid-color) 1px, transparent 1px);
            background-size: 30px 30px;
            overflow-x: hidden;
        }

        /* Scanline effect */
        body::after {
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
            font-size: 2.5em;
            color: var(--neon-blue);
            text-shadow: 0 0 10px var(--neon-blue), 0 0 20px var(--neon-blue), 0 0 40px var(--neon-blue);
            letter-spacing: 8px;
            border-bottom: 2px solid var(--neon-blue);
            padding-bottom: 15px;
            margin-bottom: 40px;
            text-transform: uppercase;
        }

        .header-sub {
            text-align: center;
            color: var(--neon-pink);
            font-weight: bold;
            font-size: 1.2em;
            margin-top: -20px;
            margin-bottom: 40px;
            text-shadow: 0 0 8px var(--neon-pink);
            animation: pulse 2s infinite;
        }

        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }

        .dashboard-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 30px;
            position: relative;
            z-index: 10;
        }

        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-blue);
            box-shadow: 0 0 15px rgba(0, 255, 255, 0.1), inset 0 0 20px rgba(0, 255, 255, 0.05);
            padding: 25px;
            border-radius: 5px;
            position: relative;
            overflow: hidden;
            transition: all 0.3s ease;
            backdrop-filter: blur(5px);
        }

        .panel:hover {
            box-shadow: 0 0 25px rgba(0, 255, 255, 0.4), inset 0 0 30px rgba(0, 255, 255, 0.2);
            transform: translateY(-3px) scale(1.01);
        }

        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; height: 4px;
            background: var(--neon-blue);
            box-shadow: 0 0 15px var(--neon-blue);
        }

        /* Themed Panels */
        .panel.hft { border-color: var(--neon-red); }
        .panel.hft::before { background: var(--neon-red); box-shadow: 0 0 20px var(--neon-red); }
        .panel.hft:hover { box-shadow: 0 0 25px rgba(255, 0, 0, 0.4); }

        .panel.trinity { border-color: var(--neon-pink); }
        .panel.trinity::before { background: var(--neon-pink); box-shadow: 0 0 20px var(--neon-pink); }
        .panel.trinity:hover { box-shadow: 0 0 25px rgba(255, 0, 255, 0.4); }

        .panel.metrics { border-color: var(--neon-green); }
        .panel.metrics::before { background: var(--neon-green); box-shadow: 0 0 20px var(--neon-green); }
        .panel.metrics:hover { box-shadow: 0 0 25px rgba(0, 255, 170, 0.4); }

        h2 {
            margin-top: 0;
            font-size: 1.4em;
            color: #fff;
            text-shadow: 0 0 8px #fff;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid rgba(255,255,255,0.2);
            padding-bottom: 15px;
            text-transform: uppercase;
        }

        .badge {
            font-size: 0.6em;
            padding: 4px 8px;
            border: 1px solid;
            border-radius: 3px;
            animation: blink 1.5s infinite;
            letter-spacing: 1px;
        }

        .badge.active { color: var(--neon-green); border-color: var(--neon-green); box-shadow: 0 0 10px var(--neon-green); }
        .badge.warning { color: var(--neon-yellow); border-color: var(--neon-yellow); box-shadow: 0 0 10px var(--neon-yellow); animation: blink 0.8s infinite; }
        .badge.danger { color: var(--neon-red); border-color: var(--neon-red); box-shadow: 0 0 10px var(--neon-red); }

        @keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }

        .item-list { list-style-type: none; padding: 0; margin-bottom: 25px;}
        .item-list li { 
            margin-bottom: 15px; 
            font-size: 1.05em; 
            border-bottom: 1px solid rgba(255,255,255,0.05); 
            padding-bottom: 10px; 
            display: flex; 
            justify-content: space-between; 
            align-items: center; 
        }
        
        .item-name { font-weight: bold; color: #fff; }
        .item-desc { display: block; font-size: 0.75em; color: #888; margin-top: 4px; }
        
        .value { font-weight: bold; letter-spacing: 1px; text-align: right; }
        .panel.hft .value { color: var(--neon-red); text-shadow: 0 0 8px var(--neon-red); }
        .panel.trinity .value { color: var(--neon-pink); text-shadow: 0 0 8px var(--neon-pink); }
        .panel.metrics .value { color: var(--neon-green); text-shadow: 0 0 8px var(--neon-green); }

        .terminal {
            height: 160px;
            overflow-y: auto;
            font-size: 0.85em;
            color: #0fa;
            background: rgba(0, 0, 0, 0.8);
            padding: 15px;
            border: 1px solid #333;
            border-radius: 4px;
            font-family: monospace;
            box-shadow: inset 0 0 15px rgba(0, 0, 0, 1);
        }
        
        .terminal span.ts { color: #555; margin-right: 8px; }
        .terminal span.src { color: #fff; margin-right: 8px; font-weight: bold; }
        
        .terminal.hft-term { color: #f88; }
        .terminal.trinity-term { color: #f8f; }
        .terminal.metrics-term { color: #8f8; }

        ::-webkit-scrollbar { width: 8px; }
        ::-webkit-scrollbar-track { background: #050505; border-left: 1px solid #222; }
        ::-webkit-scrollbar-thumb { background: #333; border-radius: 4px; }
        ::-webkit-scrollbar-thumb:hover { background: var(--neon-blue); }

        /* Glitch effect for title */
        .glitch {
            position: relative;
        }
        .glitch::before, .glitch::after {
            content: "🛰️ ORBITAL COMMAND // NUVOLA ☁️";
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: var(--bg-color);
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

        @keyframes glitch-anim-1 {
            0% { clip: rect(20px, 9999px, 85px, 0); }
            20% { clip: rect(60px, 9999px, 15px, 0); }
            40% { clip: rect(10px, 9999px, 50px, 0); }
            60% { clip: rect(80px, 9999px, 20px, 0); }
            80% { clip: rect(30px, 9999px, 90px, 0); }
            100% { clip: rect(50px, 9999px, 40px, 0); }
        }
        @keyframes glitch-anim-2 {
            0% { clip: rect(15px, 9999px, 90px, 0); }
            20% { clip: rect(70px, 9999px, 10px, 0); }
            40% { clip: rect(20px, 9999px, 40px, 0); }
            60% { clip: rect(90px, 9999px, 30px, 0); }
            80% { clip: rect(40px, 9999px, 80px, 0); }
            100% { clip: rect(60px, 9999px, 50px, 0); }
        }

    </style>
</head>
<body>

    <h1 class="glitch">🛰️ ORBITAL COMMAND // NUVOLA ☁️</h1>
    <div class="header-sub">>>> ALL SYSTEMS NOMINAL /// QUANTITATIVE ENGAGEMENT AUTHORIZED <<<</div>

    <div style="text-align: center; margin-bottom: 30px; z-index: 10; position: relative;">
        <span style="border: 1px solid var(--neon-pink); color: var(--neon-pink); padding: 10px 20px; border-radius: 4px; box-shadow: 0 0 15px rgba(255, 0, 255, 0.3); background: rgba(10, 15, 20, 0.8); font-weight: bold; font-size: 1.1em; letter-spacing: 1px;">
            ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
        </span>
    </div>

    <div class="dashboard-grid">

        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel hft">
            <h2>⚔️ SQUADRE D'ASSALTO <span class="badge danger">LIVE: HFT</span></h2>
            <ul class="item-list">
                <li>
                    <div>
                        <span class="item-name">🐺 SQUADRA_ALPHA</span>
                        <span class="item-desc">Binance Scalper / High Freq</span>
                    </div>
                    <span class="value">+3.2% / 24h</span>
                </li>
                <li>
                    <div>
                        <span class="item-name">🌊 SQUADRA_DELTA</span>
                        <span class="item-desc">Order Flow Imbalance</span>
                    </div>
                    <span class="value">ACTIVE (4 POS)</span>
                </li>
                <li>
                    <div>
                        <span class="item-name">⚖️ SQUADRA_GAMMA</span>
                        <span class="item-desc">Pairs Trading (Bitget)</span>
                    </div>
                    <span class="value">HEDGING [BTC/ETH]</span>
                </li>
            </ul>
            <div class="terminal hft-term">
                <span class="ts">[11:03:12]</span> <span class="src">[ALPHA]</span> ORDER FILLED: LONG BTC/USDT @ 64,250.00 [SIZE: 0.5]<br>
                <span class="ts">[11:03:08]</span> <span class="src">[DELTA]</span> Detecting spoofing on Binance ETH/USDT order book.<br>
                <span class="ts">[11:02:45]</span> <span class="src">[GAMMA]</span> Rebalancing delta neutral portfolio. Z-Score > 2.0.<br>
                <span class="ts">[11:00:00]</span> <span class="src">[SYS]</span> Latency to Binance API: 12ms. Execution nominal.<br>
                <span class="ts">[10:59:30]</span> <span class="src">[ALPHA]</span> Closed LONG BTC/USDT. PNL: +$145.20<br>
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel trinity">
            <h2>🔺 PROTOCOLLO TRINITY <span class="badge active">BACKGROUND ON</span></h2>
            <ul class="item-list">
                <li>
                    <div>
                        <span class="item-name">🦈 Lo Strozzino</span>
                        <span class="item-desc">Funding Rate Arbitrage</span>
                    </div>
                    <span class="value">16.8% APY</span>
                </li>
                <li>
                    <div>
                        <span class="item-name">🧮 Il Contabile</span>
                        <span class="item-desc">DCA Accumulation Matrix</span>
                    </div>
                    <span class="value">ACCUMULATING</span>
                </li>
                <li>
                    <div>
                        <span class="item-name">👼 L'Angelo Custode</span>
                        <span class="item-desc">MEV Searcher (Arbitrum)</span>
                    </div>
                    <span class="value">SCANNING MEMPOOL</span>
                </li>
            </ul>
            <div class="terminal trinity-term">
                <span class="ts">[11:03:00]</span> <span class="src">[STROZZINO]</span> Funding rate spread detected (Bybit vs Binance).<br>
                <span class="ts">[11:02:15]</span> <span class="src">[ANGELO]</span> Sandwich opportunity found. TX submitted to flashbots.<br>
                <span class="ts">[08:00:01]</span> <span class="src">[CONTABILE]</span> Daily DCA executed: +0.025 BTC, +0.5 ETH.<br>
                <span class="ts">[10:55:00]</span> <span class="src">[STROZZINO]</span> Collecting funding fees. +$32.50 accrued.<br>
                <span class="ts">[10:50:20]</span> <span class="src">[ANGELO]</span> Mempool gas spike. Adjusting priority fee.<br>
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel metrics">
            <h2>📊 METRICHE GLOBALI <span class="badge warning">SYNCED: ORACLE</span></h2>
            <ul class="item-list">
                <li>
                    <div>
                        <span class="item-name">🔮 The Oracle</span>
                        <span class="item-desc">Binance Sentiment / ML</span>
                    </div>
                    <span class="value">GREED (82/100)</span>
                </li>
                <li>
                    <div>
                        <span class="item-name">🐋 Whale Tracker</span>
                        <span class="item-desc">On-chain Flow Monitoring</span>
                    </div>
                    <span class="value">HEAVY OUTFLOW</span>
                </li>
                <li>
                    <div>
                        <span class="item-name">⚡ Network Gas</span>
                        <span class="item-desc">Ethereum Mainnet Gwei</span>
                    </div>
                    <span class="value">14 GWEI</span>
                </li>
                <li>
                    <div>
                        <span class="item-name">🎯 Orbital Win Rate</span>
                        <span class="item-desc">Rolling 7-Day Performance</span>
                    </div>
                    <span class="value">71.4% (WIN)</span>
                </li>
            </ul>
            <div class="terminal metrics-term">
                <span class="ts">[11:03:10]</span> <span class="src">[ORACLE]</span> Model retraining completed. Loss: 0.042.<br>
                <span class="ts">[11:02:50]</span> <span class="src">[WHALE]</span> ALERT: 2,500 BTC moved off Coinbase Pro.<br>
                <span class="ts">[11:01:00]</span> <span class="src">[SYS]</span> VIX proxy indicates low volatility regime.<br>
                <span class="ts">[11:00:00]</span> <span class="src">[ORACLE]</span> Sentiment shift detected: Retail entering Longs.<br>
                <span class="ts">[10:50:00]</span> <span class="src">[WHALE]</span> Monitoring Top 100 USDT wallets for activity.<br>
            </div>
        </div>

    </div>

    <!-- Background glowing orbs -->
    <div style="position: absolute; top: -100px; left: -100px; width: 400px; height: 400px; background: radial-gradient(circle, rgba(0,255,255,0.1) 0%, transparent 70%); z-index: 1; pointer-events: none;"></div>
    <div style="position: absolute; bottom: -100px; right: -100px; width: 500px; height: 500px; background: radial-gradient(circle, rgba(255,0,255,0.1) 0%, transparent 70%); z-index: 1; pointer-events: none;"></div>

</body>
</html>
"""

@app.route('/')
def index():
    return HTML_CONTENT

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
