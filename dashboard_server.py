import os
from flask import Flask, render_template_string

app = Flask(__name__)

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Orbital Command | Nuvola</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');
        
        :root {
            --neon-green: #39ff14;
            --neon-blue: #00f3ff;
            --neon-pink: #ff007f;
            --neon-yellow: #f0f000;
            --neon-red: #ff003c;
            --bg-dark: #020202;
            --panel-bg: rgba(5, 10, 15, 0.75);
            --grid-color: rgba(0, 243, 255, 0.08);
        }
        
        * {
            box-sizing: border-box;
        }

        body {
            background-color: var(--bg-dark);
            background-image: 
                linear-gradient(var(--grid-color) 1px, transparent 1px),
                linear-gradient(90deg, var(--grid-color) 1px, transparent 1px);
            background-size: 30px 30px;
            color: var(--neon-green);
            font-family: 'Share Tech Mono', 'Courier New', monospace;
            margin: 0;
            padding: 2vh 2vw;
            display: flex;
            flex-direction: column;
            align-items: center;
            min-height: 100vh;
            overflow-x: hidden;
        }

        .crt::before {
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

        h1 {
            color: var(--neon-blue);
            text-shadow: 0 0 5px var(--neon-blue), 0 0 15px var(--neon-blue), 0 0 30px var(--neon-blue);
            font-size: 3.5em;
            text-transform: uppercase;
            letter-spacing: 6px;
            border-bottom: 3px double var(--neon-blue);
            padding-bottom: 10px;
            width: 100%;
            text-align: center;
            margin-bottom: 30px;
            position: relative;
        }

        h1::after {
            content: 'NUVOLA NETWORKS INC.';
            position: absolute;
            bottom: -20px;
            right: 0;
            font-size: 0.3em;
            color: var(--neon-pink);
            letter-spacing: 2px;
            text-shadow: 0 0 10px var(--neon-pink);
        }

        .terminal-header {
            display: flex;
            justify-content: space-between;
            width: 100%;
            max-width: 1600px;
            font-size: 1.1em;
            color: var(--neon-yellow);
            margin-bottom: 10px;
            text-transform: uppercase;
            text-shadow: 0 0 5px var(--neon-yellow);
        }

        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 30px;
            width: 100%;
            max-width: 1600px;
            z-index: 1;
        }

        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-blue);
            box-shadow: 0 0 15px rgba(0, 243, 255, 0.15), inset 0 0 20px rgba(0, 243, 255, 0.05);
            padding: 25px;
            border-radius: 2px;
            position: relative;
            overflow: hidden;
            backdrop-filter: blur(4px);
            transition: all 0.3s ease;
        }

        .panel:hover {
            box-shadow: 0 0 25px rgba(0, 243, 255, 0.3), inset 0 0 30px rgba(0, 243, 255, 0.1);
            border-color: var(--neon-pink);
        }

        .panel::before {
            content: '';
            position: absolute;
            top: -100%; left: 0; right: 0; height: 2px;
            background: var(--neon-green);
            box-shadow: 0 0 15px var(--neon-green), 0 0 30px var(--neon-green);
            animation: scanline 4s linear infinite;
            opacity: 0.7;
        }

        @keyframes scanline {
            0% { top: -10%; }
            100% { top: 110%; }
        }

        .panel h2 {
            color: var(--neon-pink);
            text-shadow: 0 0 8px var(--neon-pink), 0 0 15px var(--neon-pink);
            margin-top: 0;
            border-bottom: 1px dashed var(--neon-pink);
            padding-bottom: 10px;
            font-size: 1.6em;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .trinity-banner {
            width: 100%;
            max-width: 1600px;
            text-align: center;
            margin-bottom: 30px;
            font-size: 1.5em;
            color: var(--neon-yellow);
            text-shadow: 0 0 10px var(--neon-yellow), 0 0 20px var(--neon-yellow);
            font-weight: bold;
            border: 2px dashed var(--neon-yellow);
            padding: 15px;
            background: rgba(240, 240, 0, 0.05);
            position: relative;
            overflow: hidden;
            z-index: 1;
            letter-spacing: 2px;
        }

        .trinity-banner::after {
            content: '';
            position: absolute;
            top: 0; left: -100%; width: 50%; height: 100%;
            background: linear-gradient(to right, transparent, rgba(240, 240, 0, 0.2), transparent);
            animation: shine 3s infinite;
        }

        @keyframes shine {
            100% { left: 200%; }
        }

        .item {
            margin: 18px 0;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid rgba(0, 243, 255, 0.2);
            padding-bottom: 10px;
            font-size: 1.2em;
        }

        .item:last-child {
            border-bottom: none;
        }

        .name {
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .subtext {
            display: block;
            font-size: 0.7em;
            color: rgba(255, 255, 255, 0.5);
            margin-top: 4px;
        }

        .status-box {
            padding: 4px 10px;
            border-radius: 2px;
            font-size: 0.9em;
            font-weight: bold;
            letter-spacing: 1px;
            border: 1px solid transparent;
        }

        .status-online {
            color: var(--bg-dark);
            background-color: var(--neon-green);
            box-shadow: 0 0 10px var(--neon-green);
            animation: pulse-green 2s infinite alternate;
        }

        .status-alert {
            color: var(--bg-dark);
            background-color: var(--neon-red);
            box-shadow: 0 0 10px var(--neon-red);
            animation: pulse-red 1s infinite alternate;
        }

        .status-active {
            color: var(--bg-dark);
            background-color: var(--neon-blue);
            box-shadow: 0 0 10px var(--neon-blue);
        }
        
        .status-warn {
            color: var(--bg-dark);
            background-color: var(--neon-yellow);
            box-shadow: 0 0 10px var(--neon-yellow);
        }

        @keyframes pulse-green {
            0% { opacity: 0.8; box-shadow: 0 0 5px var(--neon-green); }
            100% { opacity: 1; box-shadow: 0 0 15px var(--neon-green), 0 0 25px var(--neon-green); }
        }
        @keyframes pulse-red {
            0% { opacity: 0.8; box-shadow: 0 0 5px var(--neon-red); }
            100% { opacity: 1; box-shadow: 0 0 20px var(--neon-red), 0 0 30px var(--neon-red); }
        }

        .metric-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
            margin-top: 20px;
        }

        .metric-box {
            background: rgba(0, 0, 0, 0.5);
            border: 1px solid rgba(57, 255, 20, 0.3);
            padding: 15px;
            text-align: center;
        }

        .metric-value {
            font-size: 1.8em;
            color: var(--neon-green);
            text-shadow: 0 0 10px var(--neon-green);
            margin-top: 5px;
        }
        
        .metric-label {
            font-size: 0.8em;
            color: var(--neon-blue);
            text-transform: uppercase;
        }

        .glitch {
            position: relative;
        }
        .glitch::before, .glitch::after {
            content: attr(data-text);
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: var(--bg-dark);
        }
        .glitch::before {
            left: 2px;
            text-shadow: -1px 0 red;
            clip: rect(24px, 550px, 90px, 0);
            animation: glitch-anim-2 3s infinite linear alternate-reverse;
        }
        .glitch::after {
            left: -2px;
            text-shadow: -1px 0 blue;
            clip: rect(85px, 550px, 140px, 0);
            animation: glitch-anim 2.5s infinite linear alternate-reverse;
        }

        @keyframes glitch-anim {
            0% { clip: rect(15px, 9999px, 86px, 0); }
            5% { clip: rect(61px, 9999px, 12px, 0); }
            10% { clip: rect(28px, 9999px, 95px, 0); }
            15% { clip: rect(9px, 9999px, 47px, 0); }
            20% { clip: rect(72px, 9999px, 63px, 0); }
            25% { clip: rect(83px, 9999px, 14px, 0); }
            30% { clip: rect(17px, 9999px, 55px, 0); }
            35% { clip: rect(98px, 9999px, 20px, 0); }
            40% { clip: rect(3px, 9999px, 88px, 0); }
            45% { clip: rect(44px, 9999px, 32px, 0); }
            50% { clip: rect(66px, 9999px, 78px, 0); }
            55% { clip: rect(21px, 9999px, 91px, 0); }
            60% { clip: rect(55px, 9999px, 19px, 0); }
            65% { clip: rect(87px, 9999px, 43px, 0); }
            70% { clip: rect(12px, 9999px, 69px, 0); }
            75% { clip: rect(94px, 9999px, 5px, 0); }
            80% { clip: rect(31px, 9999px, 82px, 0); }
            85% { clip: rect(76px, 9999px, 37px, 0); }
            90% { clip: rect(8px, 9999px, 96px, 0); }
            95% { clip: rect(49px, 9999px, 25px, 0); }
            100% { clip: rect(63px, 9999px, 71px, 0); }
        }
        @keyframes glitch-anim-2 {
            0% { clip: rect(35px, 9999px, 16px, 0); }
            5% { clip: rect(91px, 9999px, 42px, 0); }
            10% { clip: rect(8px, 9999px, 75px, 0); }
            15% { clip: rect(59px, 9999px, 97px, 0); }
            20% { clip: rect(22px, 9999px, 53px, 0); }
            25% { clip: rect(73px, 9999px, 24px, 0); }
            30% { clip: rect(47px, 9999px, 85px, 0); }
            35% { clip: rect(88px, 9999px, 10px, 0); }
            40% { clip: rect(13px, 9999px, 68px, 0); }
            45% { clip: rect(64px, 9999px, 52px, 0); }
            50% { clip: rect(26px, 9999px, 38px, 0); }
            55% { clip: rect(81px, 9999px, 91px, 0); }
            60% { clip: rect(5px, 9999px, 29px, 0); }
            65% { clip: rect(97px, 9999px, 13px, 0); }
            70% { clip: rect(42px, 9999px, 59px, 0); }
            75% { clip: rect(14px, 9999px, 85px, 0); }
            80% { clip: rect(61px, 9999px, 2px, 0); }
            85% { clip: rect(26px, 9999px, 67px, 0); }
            90% { clip: rect(78px, 9999px, 46px, 0); }
            95% { clip: rect(19px, 9999px, 85px, 0); }
            100% { clip: rect(53px, 9999px, 31px, 0); }
        }

    </style>
</head>
<body class="crt">
    <div class="terminal-header">
        <span>[ UPLINK ESTABLISHED ]</span>
        <span class="glitch" data-text="AUTH: QUANTUM_ADMIN_01">AUTH: QUANTUM_ADMIN_01</span>
        <span>SYS.SEC: OVERRIDE</span>
    </div>

    <h1 class="glitch" data-text="🛰️ ORBITAL COMMAND">🛰️ ORBITAL COMMAND</h1>
    
    <div class="trinity-banner">
        ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)<br>
        <span style="font-size: 0.6em; color: rgba(255,255,255,0.7); font-weight: normal;">Running silent. Background execution verified.</span>
    </div>

    <div class="grid">
        <!-- HFT SQUADS -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <div class="item">
                <div class="name">
                    <span>🐺</span>
                    <div>
                        SQUADRA_ALPHA
                        <span class="subtext">Binance Scalper / High-Freq</span>
                    </div>
                </div>
                <div class="status-box status-online">ENGAGED</div>
            </div>
            <div class="item">
                <div class="name">
                    <span>⚡</span>
                    <div>
                        SQUADRA_DELTA
                        <span class="subtext">Order Flow & Tape Reading</span>
                    </div>
                </div>
                <div class="status-box status-active">ACTIVE</div>
            </div>
            <div class="item">
                <div class="name">
                    <span>⚖️</span>
                    <div>
                        SQUADRA_GAMMA
                        <span class="subtext">Pairs Trading (Bitget)</span>
                    </div>
                </div>
                <div class="status-box status-online">SYNCED</div>
            </div>
        </div>
        
        <!-- TRINITY PROTOCOL -->
        <div class="panel">
            <h2>🛡️ PROTOCOLLO TRINITY</h2>
            <div class="item">
                <div class="name">
                    <span>🧛</span>
                    <div>
                        Lo Strozzino
                        <span class="subtext">Funding Rate Arbitrage</span>
                    </div>
                </div>
                <div class="status-box status-online">RUNNING</div>
            </div>
            <div class="item">
                <div class="name">
                    <span>🧮</span>
                    <div>
                        Il Contabile
                        <span class="subtext">DCA & Rebalancing</span>
                    </div>
                </div>
                <div class="status-box status-online">RUNNING</div>
            </div>
            <div class="item">
                <div class="name">
                    <span>👼</span>
                    <div>
                        L'Angelo Custode
                        <span class="subtext">Arbitrum MEV Protection</span>
                    </div>
                </div>
                <div class="status-box status-online">RUNNING</div>
            </div>
        </div>

        <!-- MARKET METRICS -->
        <div class="panel">
            <h2>📊 METRICHE DI MERCATO</h2>
            <div class="item">
                <div class="name">
                    <span>👁️</span>
                    <div>
                        The Oracle
                        <span class="subtext">Binance Sentiment Index</span>
                    </div>
                </div>
                <div class="status-box status-active">BULLISH</div>
            </div>
            <div class="item">
                <div class="name">
                    <span>🐋</span>
                    <div>
                        Whale Tracker
                        <span class="subtext">Large Flows & Block Trades</span>
                    </div>
                </div>
                <div class="status-box status-alert">ALERT</div>
            </div>
            
            <div class="metric-grid">
                <div class="metric-box">
                    <div class="metric-label">Global Volatility</div>
                    <div class="metric-value">42.8%</div>
                </div>
                <div class="metric-box">
                    <div class="metric-label">Liquidations 24h</div>
                    <div class="metric-value" style="color: var(--neon-red); text-shadow: 0 0 10px var(--neon-red);">$184M</div>
                </div>
                <div class="metric-box">
                    <div class="metric-label">Alpha PnL (Session)</div>
                    <div class="metric-value">+2.45%</div>
                </div>
                <div class="metric-box">
                    <div class="metric-label">Network Latency</div>
                    <div class="metric-value" style="color: var(--neon-yellow); text-shadow: 0 0 10px var(--neon-yellow);">8ms</div>
                </div>
            </div>
        </div>
    </div>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
