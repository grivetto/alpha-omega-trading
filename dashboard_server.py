import os
from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NUVOLA // ORBITAL COMMAND</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');
        
        :root {
            --neon-green: #39ff14;
            --neon-blue: #00f3ff;
            --neon-pink: #ff00ff;
            --neon-red: #ff003c;
            --neon-yellow: #fcee0a;
            --bg-dark: #070707;
            --panel-bg: rgba(10, 15, 12, 0.85);
            --grid-color: rgba(57, 255, 20, 0.1);
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            background-color: var(--bg-dark);
            color: var(--neon-green);
            font-family: 'Share Tech Mono', monospace;
            overflow-x: hidden;
            background-image: 
                linear-gradient(var(--grid-color) 1px, transparent 1px),
                linear-gradient(90deg, var(--grid-color) 1px, transparent 1px);
            background-size: 30px 30px;
            background-position: center center;
            padding: 2rem;
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

        h1, h2, h3 {
            text-transform: uppercase;
            letter-spacing: 0.1em;
        }

        h1 {
            color: var(--neon-blue);
            text-shadow: 0 0 10px var(--neon-blue), 0 0 20px var(--neon-blue), 0 0 40px var(--neon-blue);
            text-align: center;
            font-size: 3rem;
            margin-bottom: 2rem;
            border-bottom: 3px solid var(--neon-blue);
            padding-bottom: 1rem;
            position: relative;
        }

        .glitch-wrapper {
            position: relative;
        }

        .glitch::before, .glitch::after {
            content: "NUVOLA // ORBITAL COMMAND";
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: var(--bg-dark);
        }

        .glitch::before {
            left: 2px;
            text-shadow: -2px 0 var(--neon-red);
            clip: rect(24px, 550px, 90px, 0);
            animation: glitch-anim 3s infinite linear alternate-reverse;
        }

        .glitch::after {
            left: -2px;
            text-shadow: -2px 0 var(--neon-blue);
            clip: rect(85px, 550px, 140px, 0);
            animation: glitch-anim 2.5s infinite linear alternate-reverse;
        }

        @keyframes glitch-anim {
            0% { clip: rect(11px, 9999px, 83px, 0); }
            20% { clip: rect(64px, 9999px, 15px, 0); }
            40% { clip: rect(32px, 9999px, 50px, 0); }
            60% { clip: rect(78px, 9999px, 99px, 0); }
            80% { clip: rect(4px, 9999px, 22px, 0); }
            100% { clip: rect(93px, 9999px, 66px, 0); }
        }

        .dashboard-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 2rem;
            position: relative;
            z-index: 10;
        }

        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-green);
            box-shadow: 0 0 15px rgba(57, 255, 20, 0.2), inset 0 0 20px rgba(57, 255, 20, 0.05);
            padding: 1.5rem;
            position: relative;
            backdrop-filter: blur(5px);
        }

        .panel::before {
            content: '';
            position: absolute;
            top: -2px; left: -2px; right: -2px; bottom: -2px;
            z-index: -1;
            background: linear-gradient(45deg, var(--neon-green), var(--neon-blue), var(--neon-pink));
            background-size: 400%;
            animation: neon-border 12s linear infinite;
            opacity: 0.3;
        }

        @keyframes neon-border {
            0% { background-position: 0 0; }
            50% { background-position: 100% 0; }
            100% { background-position: 0 0; }
        }

        .panel h2 {
            color: var(--neon-pink);
            text-shadow: 0 0 8px var(--neon-pink);
            border-bottom: 1px solid var(--neon-pink);
            padding-bottom: 0.5rem;
            margin-bottom: 1.5rem;
            font-size: 1.5rem;
            display: flex;
            align-items: center;
        }

        .panel h2 span { margin-right: 10px; }

        .squad-list {
            list-style: none;
        }

        .squad-item {
            border-left: 4px solid var(--neon-green);
            background: rgba(57, 255, 20, 0.05);
            margin-bottom: 1rem;
            padding: 1rem;
            transition: all 0.3s;
        }

        .squad-item:hover {
            background: rgba(57, 255, 20, 0.15);
            box-shadow: 0 0 10px rgba(57, 255, 20, 0.4);
            transform: translateX(5px);
        }

        .squad-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 0.5rem;
        }

        .squad-name {
            font-size: 1.2rem;
            font-weight: bold;
            color: var(--neon-yellow);
            text-shadow: 0 0 5px var(--neon-yellow);
        }

        .squad-target {
            color: var(--neon-blue);
            font-size: 0.9rem;
        }

        .squad-role {
            font-size: 0.85rem;
            opacity: 0.8;
            margin-top: 5px;
        }

        .status-dot {
            height: 12px;
            width: 12px;
            border-radius: 50%;
            display: inline-block;
            box-shadow: 0 0 10px currentColor;
            animation: pulse 1.5s infinite alternate;
        }

        .status-active { background-color: var(--neon-green); color: var(--neon-green); }
        .status-standby { background-color: var(--neon-yellow); color: var(--neon-yellow); }
        .status-stealth { background-color: var(--neon-blue); color: var(--neon-blue); }

        @keyframes pulse {
            0% { opacity: 0.5; transform: scale(0.8); }
            100% { opacity: 1; transform: scale(1.2); }
        }

        .trinity-banner {
            background: rgba(0, 243, 255, 0.15);
            border: 1px dashed var(--neon-blue);
            color: var(--neon-blue);
            text-align: center;
            padding: 1rem;
            margin-bottom: 1.5rem;
            font-weight: bold;
            letter-spacing: 2px;
            text-shadow: 0 0 5px var(--neon-blue);
            animation: flicker 4s infinite;
        }

        @keyframes flicker {
            0%, 19%, 21%, 23%, 25%, 54%, 56%, 100% { opacity: 1; text-shadow: 0 0 5px var(--neon-blue); }
            20%, 24%, 55% { opacity: 0.4; text-shadow: none; }
        }

        .trinity-agent {
            display: flex;
            align-items: center;
            margin-bottom: 1rem;
            padding: 0.8rem;
            border: 1px solid rgba(0, 243, 255, 0.3);
            background: rgba(0, 0, 0, 0.5);
        }

        .agent-icon {
            font-size: 2rem;
            margin-right: 15px;
            filter: drop-shadow(0 0 5px var(--neon-blue));
        }

        .agent-details strong {
            color: var(--neon-blue);
            font-size: 1.1rem;
            display: block;
        }

        .metrics-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 1rem;
        }

        .metric-box {
            border: 1px solid var(--neon-yellow);
            padding: 1rem;
            text-align: center;
            background: rgba(252, 238, 10, 0.05);
            position: relative;
            overflow: hidden;
        }

        .metric-box::after {
            content: '';
            position: absolute;
            top: 0; left: -100%; width: 50%; height: 100%;
            background: linear-gradient(to right, transparent, rgba(252, 238, 10, 0.2), transparent);
            animation: sweep 3s linear infinite;
        }

        @keyframes sweep {
            0% { left: -100%; }
            100% { left: 200%; }
        }

        .metric-label {
            font-size: 0.8rem;
            color: #aaa;
            margin-bottom: 0.5rem;
            text-transform: uppercase;
        }

        .metric-value {
            font-size: 1.5rem;
            color: var(--neon-yellow);
            text-shadow: 0 0 8px var(--neon-yellow);
            font-weight: bold;
        }

        .oracle-box { border-color: var(--neon-pink); background: rgba(255, 0, 255, 0.05); }
        .oracle-box .metric-value { color: var(--neon-pink); text-shadow: 0 0 8px var(--neon-pink); }
        
        .whale-box { border-color: var(--neon-blue); background: rgba(0, 243, 255, 0.05); }
        .whale-box .metric-value { color: var(--neon-blue); text-shadow: 0 0 8px var(--neon-blue); }

        .terminal-output {
            margin-top: 2rem;
            background: #000;
            border: 1px solid #333;
            padding: 1rem;
            height: 150px;
            overflow-y: hidden;
            font-size: 0.85rem;
            color: #0f0;
            position: relative;
            z-index: 10;
        }
        
        .terminal-line { margin-bottom: 5px; opacity: 0; animation: typeIn 0.1s forwards; }
        .terminal-line:nth-child(1) { animation-delay: 0.2s; }
        .terminal-line:nth-child(2) { animation-delay: 0.8s; }
        .terminal-line:nth-child(3) { animation-delay: 1.5s; }
        .terminal-line:nth-child(4) { animation-delay: 2.1s; }
        .terminal-line:nth-child(5) { animation-delay: 2.9s; }

        @keyframes typeIn { to { opacity: 1; } }

    </style>
</head>
<body>
    <div class="glitch-wrapper">
        <h1 class="glitch" data-text="NUVOLA // ORBITAL COMMAND">NUVOLA // ORBITAL COMMAND</h1>
    </div>

    <div class="dashboard-grid">
        
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <h2><span>⚔️</span> SQUADRE D'ASSALTO (HFT)</h2>
            <ul class="squad-list">
                <li class="squad-item">
                    <div class="squad-header">
                        <span class="squad-name">SQUADRA_ALPHA</span>
                        <div class="status-dot status-active"></div>
                    </div>
                    <div class="squad-target">🎯 TARGET: Binance</div>
                    <div class="squad-role">⚡ ROLE: High-Frequency Scalper</div>
                    <div class="squad-role">📊 STATS: 142 tx/min | PNL: +0.42%</div>
                </li>
                <li class="squad-item" style="border-left-color: var(--neon-yellow);">
                    <div class="squad-header">
                        <span class="squad-name" style="color: var(--neon-yellow);">SQUADRA_DELTA</span>
                        <div class="status-dot status-standby"></div>
                    </div>
                    <div class="squad-target">🌊 TARGET: Order Flow</div>
                    <div class="squad-role">🧠 ROLE: Liquidity Absorption</div>
                    <div class="squad-role">📊 STATS: Active Engagements: 3</div>
                </li>
                <li class="squad-item" style="border-left-color: var(--neon-blue);">
                    <div class="squad-header">
                        <span class="squad-name" style="color: var(--neon-blue);">SQUADRA_GAMMA</span>
                        <div class="status-dot status-stealth"></div>
                    </div>
                    <div class="squad-target">⚖️ TARGET: Bitget</div>
                    <div class="squad-role">🔗 ROLE: Statistical Pairs Trading</div>
                    <div class="squad-role">📊 STATS: Z-Score: 2.4 | Spread: 0.18%</div>
                </li>
            </ul>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2><span>🛡️</span> PROTOCOLLO TRINITY</h2>
            
            <div class="trinity-banner">
                ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
            </div>

            <div class="trinity-agent">
                <div class="agent-icon">🕴️</div>
                <div class="agent-details">
                    <strong>Lo Strozzino</strong>
                    <span style="color: #aaa; font-size: 0.85rem;">Funding Rate Arbitrage // Harvesting</span>
                    <div style="margin-top: 5px; font-size: 0.8rem; color: var(--neon-green);">APY: 34.2% | Exposure: Hedged</div>
                </div>
            </div>

            <div class="trinity-agent">
                <div class="agent-icon">🧮</div>
                <div class="agent-details">
                    <strong>Il Contabile</strong>
                    <span style="color: #aaa; font-size: 0.85rem;">DCA Engine // Accumulation Mode</span>
                    <div style="margin-top: 5px; font-size: 0.8rem; color: var(--neon-green);">Assets: BTC, ETH | Frequency: 4h</div>
                </div>
            </div>

            <div class="trinity-agent">
                <div class="agent-icon">👼</div>
                <div class="agent-details">
                    <strong>L'Angelo Custode</strong>
                    <span style="color: #aaa; font-size: 0.85rem;">MEV Arbitrum // Sentinel Mode</span>
                    <div style="margin-top: 5px; font-size: 0.8rem; color: var(--neon-green);">Protecting Mempool | Front-runs: 0</div>
                </div>
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <h2><span>📊</span> METRICHE DI MERCATO</h2>
            
            <div class="metrics-grid">
                <div class="metric-box oracle-box">
                    <div class="metric-label">👁️ The Oracle (Binance)</div>
                    <div class="metric-value">BULL 87%</div>
                    <div style="font-size: 0.7rem; color: #fff; margin-top: 5px;">SENTIMENT INDEX</div>
                </div>
                
                <div class="metric-box whale-box">
                    <div class="metric-label">🐋 Whale Tracker</div>
                    <div class="metric-value">+14.2K BTC</div>
                    <div style="font-size: 0.7rem; color: #fff; margin-top: 5px;">NET EXCHANGE FLOW (24H)</div>
                </div>
                
                <div class="metric-box">
                    <div class="metric-label">⚡ Execution Latency</div>
                    <div class="metric-value">12ms</div>
                    <div style="font-size: 0.7rem; color: #fff; margin-top: 5px;">API TO ENDPOINT</div>
                </div>
                
                <div class="metric-box" style="border-color: var(--neon-red); background: rgba(255,0,0,0.05);">
                    <div class="metric-label">🔥 Global Threat Level</div>
                    <div class="metric-value" style="color: var(--neon-red); text-shadow: 0 0 10px var(--neon-red);">DEFCON 3</div>
                    <div style="font-size: 0.7rem; color: #fff; margin-top: 5px;">VOLATILITY ALERT</div>
                </div>
            </div>

            <div class="terminal-output">
                <div class="terminal-line">> Initializing NUVOLA Core... OK</div>
                <div class="terminal-line">> Connecting to Binance Websocket... CONNECTED</div>
                <div class="terminal-line">> Syncing Protocollo Trinity modules... SYNCED</div>
                <div class="terminal-line">> [WARN] High volatility detected on BTC/USDT pair.</div>
                <div class="terminal-line">> Adjusting SQUADRA_ALPHA risk parameters... DONE.</div>
            </div>
        </div>

    </div>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
