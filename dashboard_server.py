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
    <title>ORBITAL COMMAND - NUVOLA DASHBOARD</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');
        
        :root {
            --neon-green: #39ff14;
            --neon-blue: #00f3ff;
            --neon-red: #ff003c;
            --neon-purple: #b026ff;
            --neon-yellow: #f2ff00;
            --bg-color: #030303;
            --panel-bg: rgba(5, 15, 10, 0.85);
            --border-color: #1a4a28;
            --font-main: 'Share Tech Mono', 'Courier New', monospace;
        }
        
        * {
            box-sizing: border-box;
        }
        
        body {
            background-color: var(--bg-color);
            color: var(--neon-green);
            font-family: var(--font-main);
            margin: 0;
            padding: 30px;
            background-image: 
                linear-gradient(rgba(0, 255, 0, 0.04) 1px, transparent 1px),
                linear-gradient(90deg, rgba(0, 255, 0, 0.04) 1px, transparent 1px);
            background-size: 30px 30px;
            position: relative;
            overflow-x: hidden;
        }
        
        /* CRT overlay effect */
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
        
        h1, h2, h3, h4 {
            text-transform: uppercase;
            margin-top: 0;
            font-weight: normal;
        }
        
        .header {
            text-align: center;
            border-bottom: 2px solid var(--neon-green);
            padding-bottom: 15px;
            margin-bottom: 40px;
            position: relative;
            box-shadow: 0 10px 30px rgba(57, 255, 20, 0.15);
        }
        
        .header h1 {
            font-size: 3.5em;
            letter-spacing: 8px;
            text-shadow: 0 0 10px var(--neon-green), 0 0 20px var(--neon-green);
            margin-bottom: 5px;
        }
        
        .header .status {
            color: var(--neon-blue);
            text-shadow: 0 0 5px var(--neon-blue), 0 0 15px var(--neon-blue);
            font-size: 1.2em;
            letter-spacing: 2px;
            animation: blink 3s infinite;
        }
        
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 30px;
            z-index: 5;
            position: relative;
        }
        
        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--border-color);
            border-radius: 4px;
            padding: 25px;
            box-shadow: inset 0 0 15px rgba(0, 255, 0, 0.05), 0 0 20px rgba(0, 0, 0, 0.9);
            position: relative;
            transition: all 0.3s ease;
        }
        
        .panel:hover {
            box-shadow: inset 0 0 20px rgba(0, 255, 0, 0.1), 0 0 25px rgba(0, 0, 0, 1);
            transform: translateY(-2px);
        }
        
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0;
            height: 3px;
            background: var(--neon-green);
            box-shadow: 0 0 15px var(--neon-green);
        }
        
        .panel.red::before { background: var(--neon-red); box-shadow: 0 0 15px var(--neon-red); }
        .panel.red h2 { color: var(--neon-red); text-shadow: 0 0 8px var(--neon-red); border-bottom: 1px solid rgba(255,0,60,0.3); padding-bottom: 10px; }
        
        .panel.blue::before { background: var(--neon-blue); box-shadow: 0 0 15px var(--neon-blue); }
        .panel.blue h2 { color: var(--neon-blue); text-shadow: 0 0 8px var(--neon-blue); border-bottom: 1px solid rgba(0,243,255,0.3); padding-bottom: 10px; }
        
        .panel.purple::before { background: var(--neon-purple); box-shadow: 0 0 15px var(--neon-purple); }
        .panel.purple h2 { color: var(--neon-purple); text-shadow: 0 0 8px var(--neon-purple); border-bottom: 1px solid rgba(176,38,255,0.3); padding-bottom: 10px; }
        
        .panel.yellow::before { background: var(--neon-yellow); box-shadow: 0 0 15px var(--neon-yellow); }
        .panel.yellow h2 { color: var(--neon-yellow); text-shadow: 0 0 8px var(--neon-yellow); border-bottom: 1px solid rgba(242,255,0,0.3); padding-bottom: 10px; }
        
        ul { list-style-type: none; padding: 0; margin: 0; }
        li { 
            margin-bottom: 15px; 
            padding: 12px; 
            border-left: 3px solid var(--neon-green); 
            background: rgba(0,255,0,0.03); 
            position: relative;
        }
        
        .panel.red li { border-left-color: var(--neon-red); background: rgba(255,0,60,0.03); }
        .panel.purple li { border-left-color: var(--neon-purple); background: rgba(176,38,255,0.03); }
        
        .status-badge {
            float: right;
            background: var(--neon-green);
            color: black;
            padding: 3px 8px;
            font-size: 0.8em;
            font-weight: bold;
            border-radius: 2px;
            letter-spacing: 1px;
            box-shadow: 0 0 5px var(--neon-green);
        }
        
        .status-badge.standby { 
            background: var(--neon-yellow); 
            box-shadow: 0 0 5px var(--neon-yellow); 
        }
        
        .status-badge.active { 
            background: var(--neon-red); 
            color: white;
            animation: pulse 1.5s infinite; 
            box-shadow: 0 0 5px var(--neon-red);
        }
        
        .status-badge.hunting {
            background: var(--neon-purple);
            color: white;
            animation: pulse-purple 1s infinite;
        }
        
        .details {
            display: block;
            margin-top: 8px;
            font-size: 0.85em;
            color: #aaa;
            line-height: 1.4;
        }
        
        .metric-value {
            font-weight: bold;
            color: white;
        }
        
        table { width: 100%; border-collapse: collapse; margin-top: 15px; text-align: left; }
        th, td { border-bottom: 1px solid rgba(255,255,255,0.1); padding: 12px 8px; }
        th { color: #888; font-size: 0.9em; letter-spacing: 1px; }
        tr:hover td { background: rgba(255,255,255,0.05); }
        
        .positive { color: var(--neon-green); text-shadow: 0 0 3px var(--neon-green); }
        .negative { color: var(--neon-red); text-shadow: 0 0 3px var(--neon-red); }
        .neutral { color: var(--neon-yellow); text-shadow: 0 0 3px var(--neon-yellow); }
        
        .progress-bar {
            width: 100%;
            height: 4px;
            background: #222;
            margin-top: 5px;
            border-radius: 2px;
            overflow: hidden;
        }
        
        .progress-fill {
            height: 100%;
            background: var(--neon-blue);
            box-shadow: 0 0 5px var(--neon-blue);
            width: 75%;
            animation: load 2s ease-in-out infinite alternate;
        }
        
        @keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0.6; text-shadow: none; } }
        @keyframes pulse { 0% { box-shadow: 0 0 0 0 rgba(255,0,60,0.8); } 70% { box-shadow: 0 0 0 8px rgba(255,0,60,0); } 100% { box-shadow: 0 0 0 0 rgba(255,0,60,0); } }
        @keyframes pulse-purple { 0% { box-shadow: 0 0 0 0 rgba(176,38,255,0.8); } 70% { box-shadow: 0 0 0 8px rgba(176,38,255,0); } 100% { box-shadow: 0 0 0 0 rgba(176,38,255,0); } }
        @keyframes load { 0% { width: 40%; } 100% { width: 90%; } }
        
        .scanline {
            width: 100%;
            height: 150px;
            z-index: 9999;
            position: fixed;
            pointer-events: none;
            background: linear-gradient(0deg, rgba(0,0,0,0) 0%, rgba(57,255,20,0.05) 50%, rgba(0,0,0,0) 100%);
            animation: scan 8s linear infinite;
            top: 0;
            left: 0;
        }
        @keyframes scan { 0% { top: -150px; } 100% { top: 100vh; } }
        
        .footer-metrics {
            margin-top: 40px;
            text-align: center;
            font-size: 0.9em;
            color: #555;
            border-top: 1px dashed #333;
            padding-top: 20px;
        }
        
        .terminal-cursor {
            display: inline-block;
            width: 10px;
            height: 1.2em;
            background-color: var(--neon-green);
            vertical-align: middle;
            animation: blink 1s step-end infinite;
        }
    </style>
</head>
<body>
    <div class="scanline"></div>
    
    <div class="header">
        <h1>🛰️ ORBITAL COMMAND</h1>
        <p class="status">>>> UPLINK_ESTABLISHED | SYSTEM_NOMINAL | QUANTUM_ENCRYPTION_ACTIVE <<<</p>
        <h3 style="color: var(--neon-blue); margin-top: 15px; font-size: 1.2em;">
            [CORE_V4.2.9] LATENCY: <span class="positive">8ms</span> | NODES: <span class="positive">12/12</span> ONLINE
        </h3>
        <h3 style="color: var(--neon-purple); margin-top: 10px; font-size: 1.3em; text-shadow: 0 0 10px var(--neon-purple); border: 1px solid var(--neon-purple); padding: 5px; display: inline-block; background: rgba(176,38,255,0.1);">
            ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
        </h3>
    </div>

    <div class="grid">
        <!-- SQUADRE D'ASSALTO -->
        <div class="panel red">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <ul>
                <li>
                    <strong>SQUADRA_ALPHA</strong> [Binance Scalper]
                    <span class="status-badge active">ENGAGED</span>
                    <span class="details">
                        > Target: <span class="metric-value">BTC/USDT</span><br>
                        > Win Rate (1h): <span class="positive">68.4%</span> | PnL: <span class="positive">+$412.50</span><br>
                        > Execution Latency: <span class="metric-value">12ms</span> API / <span class="metric-value">4ms</span> WS
                    </span>
                    <div class="progress-bar"><div class="progress-fill" style="background: var(--neon-red); box-shadow: 0 0 5px var(--neon-red); width: 85%; animation: none;"></div></div>
                </li>
                <li>
                    <strong>SQUADRA_DELTA</strong> [Order Flow]
                    <span class="status-badge">ONLINE</span>
                    <span class="details">
                        > Target: <span class="metric-value">ETH/USDT</span><br>
                        > Status: <span class="metric-value">Monitoring Orderbook Imbalance</span><br>
                        > Delta Volume: <span class="positive">+1,450 ETH</span> (Buy pressure)
                    </span>
                    <div class="progress-bar"><div class="progress-fill" style="width: 45%;"></div></div>
                </li>
                <li>
                    <strong>SQUADRA_GAMMA</strong> [Bitget Pairs Trading]
                    <span class="status-badge standby">STANDBY</span>
                    <span class="details">
                        > Pairs: <span class="metric-value">SOL-PERP / APT-PERP</span><br>
                        > Spread: <span class="neutral">1.45 std dev</span> (Target: 2.0)<br>
                        > Status: <span class="metric-value">Awaiting mean reversion trigger</span>
                    </span>
                    <div class="progress-bar"><div class="progress-fill" style="background: var(--neon-yellow); box-shadow: 0 0 5px var(--neon-yellow); width: 25%; animation: none;"></div></div>
                </li>
            </ul>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel purple">
            <h2>🛡️ PROTOCOLLO TRINITY</h2>
            <ul>
                <li>
                    <strong>🎩 Lo Strozzino</strong> [Funding Arb]
                    <span class="status-badge">HARVESTING</span>
                    <span class="details">
                        > Strategy: <span class="metric-value">Delta-Neutral Cash & Carry</span><br>
                        > Active Markets: <span class="metric-value">14</span> | Exposure: <span class="metric-value">$125,000</span><br>
                        > Avg APR: <span class="positive">+18.4%</span> | 24h Yield: <span class="positive">+$63.01</span>
                    </span>
                </li>
                <li>
                    <strong>🧮 Il Contabile</strong> [DCA Matrix]
                    <span class="status-badge">ONLINE</span>
                    <span class="details">
                        > Phase: <span class="metric-value">Accumulation (Bear/Crab)</span><br>
                        > Targets: <span class="metric-value">BTC (60%), ETH (30%), SOL (10%)</span><br>
                        > Next Execution: <span class="metric-value">T-Minus 04h 12m 45s</span>
                    </span>
                </li>
                <li>
                    <strong>👼 L'Angelo Custode</strong> [MEV Arbitrum]
                    <span class="status-badge hunting">HUNTING</span>
                    <span class="details">
                        > Protocol: <span class="metric-value">Flashbots / Arbitrum Sequencer</span><br>
                        > Strategies: <span class="metric-value">Sandwich, Liquidations, Dex Arb</span><br>
                        > Mempool Scans/sec: <span class="metric-value">4,500</span> | Flashloans: <span class="positive">READY</span>
                    </span>
                </li>
            </ul>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel blue">
            <h2>📊 METRICHE DI MERCATO</h2>
            <table>
                <tr>
                    <th>MODULO SENSORI</th>
                    <th>STATO / LETTURA</th>
                    <th>TREND</th>
                </tr>
                <tr>
                    <td>👁️ The Oracle (Binance Sentiment)</td>
                    <td class="positive">BULLISH (78/100)</td>
                    <td class="positive">↗ UP</td>
                </tr>
                <tr>
                    <td>🐋 Whale Tracker (On-Chain)</td>
                    <td class="negative">LARGE OUTFLOW ($45M)</td>
                    <td class="negative">↘ ALERT</td>
                </tr>
                <tr>
                    <td>⚡ Network Gwei (ETH Mainnet)</td>
                    <td class="metric-value">15.4 (Low)</td>
                    <td class="neutral">→ FLAT</td>
                </tr>
                <tr>
                    <td>💧 Liquidity Siphon (DEX Vol)</td>
                    <td class="positive">+2.4M USD (24h)</td>
                    <td class="positive">↗ UP</td>
                </tr>
                <tr>
                    <td>🔥 Funding Heatmap</td>
                    <td class="metric-value">Overheated (Alts)</td>
                    <td class="negative">↘ CAUTION</td>
                </tr>
            </table>
            
            <div style="margin-top: 20px; padding: 10px; background: rgba(0,0,0,0.5); border: 1px solid #333; font-size: 0.85em;">
                <span style="color: #888;">[SYSTEM_LOG]</span> <span style="color: var(--neon-green);">Establishing WebSocket multiplex stream... OK</span><br>
                <span style="color: #888;">[SYSTEM_LOG]</span> <span style="color: var(--neon-green);">Syncing Orderbooks (Binance, Bybit, Bitget)... OK</span><br>
                <span style="color: #888;">[SYSTEM_LOG]</span> <span style="color: var(--neon-blue);">Awaiting execution triggers</span><span class="terminal-cursor"></span>
            </div>
        </div>
    </div>
    
    <div class="footer-metrics">
        ORBITAL COMMAND v4.2.9 // UNAUTHORIZED ACCESS WILL BE MET WITH LETHAL QUANTS // MEMORY USAGE: 45% // CPU: 12% // 
        <span style="color: var(--neon-green);">CONNECTION: SECURE</span>
    </div>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
