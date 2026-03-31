from flask import Flask, render_template_string
import logging
import os

app = Flask(__name__)
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ORBITAL COMMAND | Nuvola Dashboard</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');
        
        :root {
            --bg-color: #020205;
            --primary: #0ff;
            --secondary: #f0f;
            --success: #39ff14;
            --warning: #ffb000;
            --danger: #ff003c;
            --panel-bg: rgba(2, 10, 20, 0.85);
            --grid-line: rgba(0, 255, 255, 0.05);
            --glow-primary: 0 0 10px var(--primary), 0 0 20px var(--primary);
            --glow-secondary: 0 0 10px var(--secondary), 0 0 20px var(--secondary);
            --glow-danger: 0 0 10px var(--danger), 0 0 20px var(--danger);
            --glow-success: 0 0 10px var(--success), 0 0 20px var(--success);
        }
        
        * {
            box-sizing: border-box;
        }

        body {
            background-color: var(--bg-color);
            color: var(--primary);
            font-family: 'Share Tech Mono', 'Courier New', monospace;
            margin: 0;
            padding: 20px;
            background-image: 
                linear-gradient(var(--grid-line) 1px, transparent 1px),
                linear-gradient(90deg, var(--grid-line) 1px, transparent 1px);
            background-size: 40px 40px;
            text-transform: uppercase;
            overflow-x: hidden;
        }

        /* Scanline overlay */
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

        h1, h2, h3 {
            margin-top: 0;
            letter-spacing: 2px;
        }
        
        h1 {
            color: var(--secondary);
            text-shadow: var(--glow-secondary);
            font-size: 2.5em;
            text-align: center;
            border-bottom: 2px solid var(--secondary);
            padding-bottom: 15px;
            margin-bottom: 10px;
        }

        h2 {
            color: var(--primary);
            text-shadow: var(--glow-primary);
            border-bottom: 1px solid var(--primary);
            padding-bottom: 5px;
            font-size: 1.4em;
        }

        .container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(450px, 1fr));
            gap: 25px;
            max-width: 1600px;
            margin: 0 auto;
            position: relative;
            z-index: 10;
        }

        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--primary);
            box-shadow: 0 0 15px rgba(0, 255, 255, 0.1), inset 0 0 20px rgba(0, 255, 255, 0.05);
            padding: 25px;
            border-radius: 4px;
            position: relative;
            backdrop-filter: blur(5px);
            transition: all 0.3s ease;
        }
        
        .panel:hover {
            box-shadow: 0 0 25px rgba(0, 255, 255, 0.3), inset 0 0 30px rgba(0, 255, 255, 0.1);
            border-color: #fff;
        }

        .panel::before, .panel::after {
            content: '';
            position: absolute;
            width: 15px;
            height: 15px;
            border: 2px solid var(--primary);
            transition: all 0.3s;
        }
        .panel::before { top: -2px; left: -2px; border-right: none; border-bottom: none; }
        .panel::after { bottom: -2px; right: -2px; border-left: none; border-top: none; }

        .header-status {
            text-align: center;
            margin-bottom: 30px;
            position: relative;
            z-index: 10;
        }

        .blink { animation: blinker 1.5s linear infinite; }
        @keyframes blinker { 50% { opacity: 0.3; } }
        
        .pulse { animation: pulse 2s infinite; }
        @keyframes pulse {
            0% { box-shadow: 0 0 0 0 rgba(57, 255, 20, 0.7); }
            70% { box-shadow: 0 0 0 10px rgba(57, 255, 20, 0); }
            100% { box-shadow: 0 0 0 0 rgba(57, 255, 20, 0); }
        }

        .status-badge {
            display: inline-block;
            padding: 5px 10px;
            border-radius: 3px;
            font-weight: bold;
            font-size: 0.9em;
            letter-spacing: 1px;
            text-shadow: none;
            color: #000;
        }
        
        .bg-online { background-color: var(--success); box-shadow: var(--glow-success); color: #000; }
        .bg-standby { background-color: var(--warning); color: #000; }
        .bg-offline { background-color: var(--danger); box-shadow: var(--glow-danger); color: #fff; }

        .text-online { color: var(--success); text-shadow: var(--glow-success); }
        .text-standby { color: var(--warning); }
        .text-offline { color: var(--danger); text-shadow: var(--glow-danger); }

        ul.item-list {
            list-style-type: none;
            padding: 0;
            margin: 0;
        }
        
        ul.item-list li {
            margin: 15px 0;
            padding: 15px;
            background: rgba(0, 255, 255, 0.03);
            border-left: 3px solid var(--primary);
            position: relative;
        }

        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-top: 15px;
        }

        .metric-card {
            background: rgba(0, 0, 0, 0.5);
            border: 1px dashed var(--primary);
            padding: 15px;
            text-align: center;
            position: relative;
            overflow: hidden;
        }

        .metric-value {
            font-size: 1.8em;
            color: var(--secondary);
            text-shadow: var(--glow-secondary);
            margin: 10px 0;
        }

        .metric-label {
            font-size: 0.8em;
            color: #aaa;
        }

        .progress-bar {
            height: 4px;
            background: #111;
            margin-top: 10px;
            border-radius: 2px;
            overflow: hidden;
        }
        
        .progress-fill {
            height: 100%;
            background: var(--primary);
            box-shadow: var(--glow-primary);
        }

        table.data-table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
            font-size: 0.9em;
        }
        
        table.data-table th, table.data-table td {
            border: 1px solid rgba(0, 255, 255, 0.2);
            padding: 12px;
            text-align: left;
        }
        
        table.data-table th {
            background: rgba(0, 255, 255, 0.1);
            color: var(--primary);
            text-shadow: 0 0 5px var(--primary);
        }
        
        table.data-table tr:hover {
            background: rgba(0, 255, 255, 0.05);
        }

        .terminal-output {
            background: #000;
            border: 1px solid #333;
            padding: 15px;
            height: 150px;
            overflow-y: hidden;
            font-size: 0.85em;
            color: #0f0;
            position: relative;
        }
        
        .terminal-output::after {
            content: '█';
            animation: blinker 1s step-end infinite;
        }
        
        .log-line {
            margin: 5px 0;
            opacity: 0.8;
        }

        .glitch {
            position: relative;
        }
        .glitch::before, .glitch::after {
            content: 'ORBITAL COMMAND';
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: var(--bg-color);
        }
        .glitch::before {
            left: 2px;
            text-shadow: -2px 0 #ff00c1;
            clip: rect(44px, 450px, 56px, 0);
            animation: glitch-anim 5s infinite linear alternate-reverse;
        }
        .glitch::after {
            left: -2px;
            text-shadow: -2px 0 #00fff9;
            clip: rect(44px, 450px, 56px, 0);
            animation: glitch-anim2 5s infinite linear alternate-reverse;
        }
        
        @keyframes glitch-anim {
            0% { clip: rect(10px, 9999px, 86px, 0); }
            5% { clip: rect(66px, 9999px, 14px, 0); }
            10% { clip: rect(98px, 9999px, 88px, 0); }
            15% { clip: rect(13px, 9999px, 4px, 0); }
            20% { clip: rect(68px, 9999px, 66px, 0); }
            100% { clip: rect(68px, 9999px, 66px, 0); }
        }
        @keyframes glitch-anim2 {
            0% { clip: rect(65px, 9999px, 100px, 0); }
            5% { clip: rect(52px, 9999px, 74px, 0); }
            10% { clip: rect(79px, 9999px, 85px, 0); }
            15% { clip: rect(75px, 9999px, 5px, 0); }
            20% { clip: rect(67px, 9999px, 61px, 0); }
            100% { clip: rect(67px, 9999px, 61px, 0); }
        }
    </style>
</head>
<body>
    <div class="header-status">
        <h1 class="glitch">🛰️ ORBITAL COMMAND 🛰️</h1>
        <p class="blink" style="color: var(--primary);">/// NUVOLA KERNEL V4.2.0 /// QUANTITATIVE WARFARE SYSTEM ONLINE ///</p>
        <div style="margin-top: 15px;">
            <span class="status-badge bg-online pulse">SYS: NOMINAL</span>
            <span class="status-badge bg-online" style="margin-left: 10px;">LATENCY: 8ms</span>
            <span class="status-badge bg-standby" style="margin-left: 10px;">API LIMIT: 42%</span>
            <span class="status-badge bg-online pulse" style="margin-left: 10px;">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</span>
        </div>
    </div>
    
    <div class="container">
        
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO <span style="font-size: 0.6em; color: #fff;">[HFT DIV.]</span></h2>
            <ul class="item-list">
                <li>
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <strong>[SQUADRA_ALPHA] ⚡ Scalper</strong>
                        <span class="status-badge bg-online">ENGAGED</span>
                    </div>
                    <div style="margin-top: 10px; font-size: 0.9em; color: #ccc;">
                        Venue: <b>Binance Spot</b> | Target: <b>BTC/USDT</b><br>
                        Win Rate: <span class="text-online">68.4%</span> | PNL (24h): <span class="text-online">+1.24%</span>
                        <div class="progress-bar"><div class="progress-fill" style="width: 85%; background: var(--success); box-shadow: var(--glow-success);"></div></div>
                    </div>
                </li>
                <li>
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <strong>[SQUADRA_DELTA] 🌊 Order Flow</strong>
                        <span class="status-badge bg-online">ENGAGED</span>
                    </div>
                    <div style="margin-top: 10px; font-size: 0.9em; color: #ccc;">
                        Venue: <b>Binance Futures</b> | Target: <b>ETH/USDT</b><br>
                        Volume Spike Detected | Active Orders: <b>14</b>
                        <div class="progress-bar"><div class="progress-fill" style="width: 60%;"></div></div>
                    </div>
                </li>
                <li>
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <strong>[SQUADRA_GAMMA] ⚖️ Pairs Trading</strong>
                        <span class="status-badge bg-standby">STANDBY</span>
                    </div>
                    <div style="margin-top: 10px; font-size: 0.9em; color: #ccc;">
                        Venue: <b>Bitget</b> | Target: <b>SOL/AVAX</b><br>
                        Current Spread: <b>0.15%</b> (Target: 0.25%) | Z-Score: 1.8
                        <div class="progress-bar"><div class="progress-fill" style="width: 30%; background: var(--warning); box-shadow: none;"></div></div>
                    </div>
                </li>
            </ul>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2>🔺 PROTOCOLLO TRINITY <span style="font-size: 0.6em; color: #fff;">[PASSIVE OPS]</span></h2>
            <ul class="item-list">
                <li>
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <strong>🕴️ Lo Strozzino <span style="color: #aaa; font-size: 0.8em;">(Funding Arb)</span></strong>
                        <span class="status-badge bg-online">GHOST MODE</span>
                    </div>
                    <div style="margin-top: 10px; font-size: 0.9em; color: #ccc;">
                        Monitoring 42 perpetual markets.<br>
                        Strategy: <b>Delta Neutral</b> | Est. APY: <span class="text-online">18.5%</span>
                    </div>
                </li>
                <li>
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <strong>🧮 Il Contabile <span style="color: #aaa; font-size: 0.8em;">(DCA / TWAP)</span></strong>
                        <span class="status-badge bg-online">GHOST MODE</span>
                    </div>
                    <div style="margin-top: 10px; font-size: 0.9em; color: #ccc;">
                        Accumulating <b>BTC</b> | VWAP divergence: -0.5%<br>
                        Next execution in: <span class="text-standby">4h 12m</span>
                    </div>
                </li>
                <li>
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <strong>👼 L'Angelo Custode <span style="color: #aaa; font-size: 0.8em;">(MEV Arbitrum)</span></strong>
                        <span class="status-badge bg-online">GHOST MODE</span>
                    </div>
                    <div style="margin-top: 10px; font-size: 0.9em; color: #ccc;">
                        Mempool scanning: <b>ACTIVE</b> | Node: RPC_Primary<br>
                        Flashbots connection: <b>SECURED</b> | Daily snipes: 2
                    </div>
                </li>
            </ul>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel" style="grid-column: 1 / -1;">
            <h2>📊 METRICHE DI MERCATO <span style="font-size: 0.6em; color: #fff;">[INTELLIGENCE]</span></h2>
            
            <div class="metrics-grid">
                <div class="metric-card">
                    <div class="metric-label">BTC FEAR & GREED</div>
                    <div class="metric-value">72</div>
                    <div class="text-online">GREED</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">GLOBAL LIQUIDITY</div>
                    <div class="metric-value">$6.2T</div>
                    <div class="text-standby">STABLE</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">VOLATILITY INDEX</div>
                    <div class="metric-value">42.1</div>
                    <div class="text-offline">HIGH</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">FUNDING RATE (AVG)</div>
                    <div class="metric-value">+0.015%</div>
                    <div class="text-online">BULLISH</div>
                </div>
            </div>

            <table class="data-table">
                <tr>
                    <th>DATA SOURCE</th>
                    <th>METRIC / SIGNAL</th>
                    <th>CURRENT VALUE</th>
                    <th>AI CONFIDENCE</th>
                </tr>
                <tr>
                    <td>👁️ THE ORACLE (Binance)</td>
                    <td>Long/Short Ratio (Top Traders)</td>
                    <td>1.45 <span class="text-online">↑</span></td>
                    <td><span class="text-online">88% (BULLISH)</span></td>
                </tr>
                <tr>
                    <td>👁️ THE ORACLE (Binance)</td>
                    <td>Taker Buy/Sell Volume Ratio</td>
                    <td>1.12 <span class="text-online">↑</span></td>
                    <td><span class="text-standby">65% (WEAK BUY)</span></td>
                </tr>
                <tr>
                    <td>🐳 WHALE TRACKER</td>
                    <td>Large TX Count (>100 BTC)</td>
                    <td>12 in last 1H</td>
                    <td><span class="text-standby">50% (NEUTRAL)</span></td>
                </tr>
                <tr>
                    <td>🐳 WHALE TRACKER</td>
                    <td>Exchange Netflow (24h)</td>
                    <td>-4,500 BTC <span class="text-danger">↓</span></td>
                    <td><span class="text-online">92% (STRONG BULL)</span></td>
                </tr>
            </table>
        </div>
        
        <!-- TERMINAL LOGS -->
        <div class="panel" style="grid-column: 1 / -1;">
            <h2>🖥️ SYSTEM LOGS <span style="font-size: 0.6em; color: #fff;">[LIVE FEED]</span></h2>
            <div class="terminal-output" id="term-log">
                <div class="log-line">[SYS] Initializing Orbital Command UI...</div>
                <div class="log-line">[SYS] Connecting to Nuvola Backend WSS... OK</div>
                <div class="log-line">[HFT] SQUADRA_ALPHA submitted limit order BUY 0.5 BTC @ 69,420</div>
                <div class="log-line text-standby">[WARN] Binance API rate limit at 42%. Throttling secondary requests.</div>
                <div class="log-line">[TRINITY] Lo Strozzino rebalancing perp exposure...</div>
                <div class="log-line">[MEV] Angelo Custode detected sandwich opportunity on SushiSwap (Arbitrum). Simulating...</div>
                <div class="log-line text-offline">[MEV] Simulation failed (insufficient margin). Aborting.</div>
                <div class="log-line">[ORACLE] Ingesting new sentiment data...</div>
            </div>
        </div>

    </div>
    
    <div style="text-align: center; margin-top: 30px; margin-bottom: 20px; font-size: 0.8em; color: rgba(0,255,255,0.4);">
        [ ORBITAL COMMAND TERMINAL ] // ENCRYPTION: AES-256-GCM // [ REFRESH INTERVAL: 15s ]
    </div>
    
    <script>
        // Auto refresh
        setTimeout(() => { window.location.reload(); }, 15000);
        
        // Fake log generator for visual effect
        const logs = [
            "[HFT] SQUADRA_DELTA updating trailing stop for ETH short...",
            "[SYS] Ping to Bitget: 24ms",
            "[TRINITY] Il Contabile calculated optimal TWAP slice: $420",
            "<span class='text-online'>[HFT] SQUADRA_ALPHA FILLED BUY 0.5 BTC @ 69,420</span>",
            "[WHALE] Alert: 1,000 BTC transferred from Coinbase to unknown wallet",
            "[ORACLE] Re-evaluating funding rate delta...",
            "<span class='text-standby'>[WARN] High slippage detected on AVAX pairs</span>"
        ];
        
        setInterval(() => {
            const term = document.getElementById('term-log');
            if(Math.random() > 0.4) {
                const randomLog = logs[Math.floor(Math.random() * logs.length)];
                const time = new Date().toISOString().split('T')[1].substring(0,8);
                term.innerHTML += `<div class="log-line">[${time}] ${randomLog}</div>`;
                term.scrollTop = term.scrollHeight;
                
                // Keep only last few lines
                while(term.children.length > 15) {
                    term.removeChild(term.firstChild);
                }
            }
        }, 2000);
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)