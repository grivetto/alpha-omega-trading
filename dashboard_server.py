from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NUVOLA || ORBITAL COMMAND</title>
    <style>
        :root {
            --neon-blue: #00f3ff;
            --neon-pink: #ff00ff;
            --neon-green: #39ff14;
            --dark-bg: #0a0a0c;
            --panel-bg: rgba(10, 20, 30, 0.85);
        }
        body {
            background-color: var(--dark-bg);
            color: var(--neon-blue);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            background-image: linear-gradient(rgba(0, 243, 255, 0.05) 1px, transparent 1px),
            linear-gradient(90deg, rgba(0, 243, 255, 0.05) 1px, transparent 1px);
            background-size: 20px 20px;
        }
        h1, h2, h3 {
            text-transform: uppercase;
            text-shadow: 0 0 10px var(--neon-blue);
            margin-top: 0;
            letter-spacing: 2px;
        }
        .header {
            text-align: center;
            border-bottom: 2px solid var(--neon-blue);
            padding-bottom: 20px;
            margin-bottom: 30px;
            box-shadow: 0 10px 20px -10px rgba(0, 243, 255, 0.3);
        }
        .grid-container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(380px, 1fr));
            gap: 25px;
        }
        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-blue);
            border-radius: 4px;
            padding: 20px;
            box-shadow: inset 0 0 15px rgba(0, 243, 255, 0.1), 0 0 15px rgba(0, 243, 255, 0.2);
            position: relative;
            overflow: hidden;
            transition: all 0.3s ease;
        }
        .panel:hover {
            box-shadow: inset 0 0 20px rgba(0, 243, 255, 0.2), 0 0 20px rgba(0, 243, 255, 0.4);
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; width: 100%; height: 3px;
            background: var(--neon-blue);
            box-shadow: 0 0 15px var(--neon-blue);
        }
        .panel.pink::before { background: var(--neon-pink); box-shadow: 0 0 15px var(--neon-pink); border-color: var(--neon-pink); }
        .panel.green::before { background: var(--neon-green); box-shadow: 0 0 15px var(--neon-green); border-color: var(--neon-green); }
        
        .status-online { color: var(--neon-green); text-shadow: 0 0 8px var(--neon-green); font-weight: bold; }
        .status-standby { color: #ffeb3b; text-shadow: 0 0 8px #ffeb3b; font-weight: bold; }
        .status-alert { color: var(--neon-pink); text-shadow: 0 0 8px var(--neon-pink); font-weight: bold; }
        
        ul { list-style-type: none; padding: 0; margin: 0; }
        li { margin-bottom: 15px; border-bottom: 1px dashed rgba(0, 243, 255, 0.2); padding-bottom: 10px;}
        li:last-child { border-bottom: none; margin-bottom: 0; padding-bottom: 0; }
        
        .data-row {
            display: flex;
            justify-content: space-between;
            font-size: 0.95em;
            margin-top: 5px;
            color: #ccc;
        }
        .data-row span:last-child {
            color: #fff;
        }
        
        .blink { animation: blinker 1.5s linear infinite; }
        @keyframes blinker { 50% { opacity: 0; } }

        .glitch {
            position: relative;
            animation: glitch 2s infinite;
        }
        
        .log-container {
            font-family: 'Courier New', Courier, monospace;
            font-size: 0.85em;
            color: #888;
            height: 150px;
            overflow-y: hidden;
            background: #000;
            padding: 10px;
            border: 1px solid #333;
            border-radius: 3px;
        }
        .log-entry { margin-bottom: 4px; }
        .log-time { color: var(--neon-blue); margin-right: 10px; }
    </style>
</head>
<body>
    <div class="header">
        <h1 class="glitch">🌐 NUVOLA // ORBITAL COMMAND 🌐</h1>
        <p>SYSTEM STATUS: <span class="status-online blink">NOMINAL</span> &nbsp;&nbsp;|&nbsp;&nbsp; UPLINK: <span style="color: #fff;">SECURE</span> &nbsp;&nbsp;|&nbsp;&nbsp; LATENCY: <span style="color: var(--neon-green);">12ms</span></p>
        <p style="font-weight: bold; border: 1px dashed var(--neon-green); display: inline-block; padding: 5px 15px; margin-top: 10px; color: var(--neon-green); background: rgba(57, 255, 20, 0.1);">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</p>
    </div>

    <div class="grid-container">
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel pink" style="border-color: rgba(255, 0, 255, 0.3);">
            <h2 style="color: var(--neon-pink); text-shadow: 0 0 10px var(--neon-pink);">⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <ul>
                <li>
                    <strong style="font-size: 1.1em; color: #fff;">[🐺 SQUADRA_ALPHA]</strong> <span style="color: #aaa;">- Scalper</span>
                    <div class="data-row"><span>Target:</span><span>Binance Spot</span></div>
                    <div class="data-row"><span>Status:</span><span class="status-online">ENGAGED</span></div>
                    <div class="data-row"><span>Win Rate (24h):</span><span style="color: var(--neon-green);">71.4%</span></div>
                </li>
                <li>
                    <strong style="font-size: 1.1em; color: #fff;">[🦅 SQUADRA_DELTA]</strong> <span style="color: #aaa;">- Order Flow</span>
                    <div class="data-row"><span>Target:</span><span>Multi-Exchange</span></div>
                    <div class="data-row"><span>Status:</span><span class="status-standby">SCANNING</span></div>
                    <div class="data-row"><span>Order Imbalance:</span><span style="color: var(--neon-green);">+14.2M USD</span></div>
                </li>
                <li>
                    <strong style="font-size: 1.1em; color: #fff;">[🦂 SQUADRA_GAMMA]</strong> <span style="color: #aaa;">- Pairs Trading</span>
                    <div class="data-row"><span>Target:</span><span>Bitget Futures</span></div>
                    <div class="data-row"><span>Status:</span><span class="status-online">ACTIVE</span></div>
                    <div class="data-row"><span>Spread Delta:</span><span>0.18%</span></div>
                </li>
            </ul>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel green" style="border-color: rgba(57, 255, 20, 0.3);">
            <h2 style="color: var(--neon-green); text-shadow: 0 0 10px var(--neon-green);">🔺 PROTOCOLLO TRINITY</h2>
            <ul>
                <li>
                    <strong style="font-size: 1.1em; color: #fff;">[🕴️ Lo Strozzino]</strong> <span style="color: #aaa;">- Funding Arb</span>
                    <div class="data-row"><span>Objective:</span><span>Delta Neutral Yield</span></div>
                    <div class="data-row"><span>Status:</span><span class="status-online">EXTRACTING</span></div>
                    <div class="data-row"><span>Current APR:</span><span style="color: var(--neon-green);">18.5%</span></div>
                </li>
                <li>
                    <strong style="font-size: 1.1em; color: #fff;">[🧮 Il Contabile]</strong> <span style="color: #aaa;">- Smart DCA</span>
                    <div class="data-row"><span>Objective:</span><span>Accumulation</span></div>
                    <div class="data-row"><span>Status:</span><span class="status-standby">WAITING FOR DIP</span></div>
                    <div class="data-row"><span>Next Buy Est:</span><span>1h 45m</span></div>
                </li>
                <li>
                    <strong style="font-size: 1.1em; color: #fff;">[👼 L'Angelo Custode]</strong> <span style="color: #aaa;">- MEV</span>
                    <div class="data-row"><span>Network:</span><span>Arbitrum One</span></div>
                    <div class="data-row"><span>Status:</span><span class="status-online blink">PROTECTING</span></div>
                    <div class="data-row"><span>Sandwiches Thwarted:</span><span>42</span></div>
                </li>
            </ul>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <h2>📊 METRICHE DI MERCATO</h2>
            <ul>
                <li>
                    <strong style="font-size: 1.1em; color: #fff;">[👁️ The Oracle]</strong> <span style="color: #aaa;">- Market Sentiment</span>
                    <div class="data-row"><span>Fear & Greed:</span><span style="color: #ffeb3b;">68 (GREED)</span></div>
                    <div class="data-row"><span>Binance L/S Ratio:</span><span>1.54</span></div>
                    <div class="data-row"><span>Volatility Index:</span><span>Moderate</span></div>
                </li>
                <li>
                    <strong style="font-size: 1.1em; color: #fff;">[🐋 Whale Tracker]</strong> <span style="color: #aaa;">- On-chain Alerts</span>
                    <div class="data-row"><span>Status:</span><span class="status-online">MONITORING</span></div>
                    <div class="data-row"><span>Last Alert:</span><span class="status-alert blink">DETECTED</span></div>
                    <div class="data-row"><span>Flow:</span><span>12,000 ETH -> Coinbase</span></div>
                </li>
            </ul>
        </div>
        
        <!-- SYSTEM TERMINAL -->
        <div class="panel">
            <h2>⚙️ TACTICAL FEED</h2>
            <div class="log-container">
                <div class="log-entry"><span class="log-time">[15:19:02]</span> SYSTEM: Orbital Command dashboard re-initialized.</div>
                <div class="log-entry"><span class="log-time">[15:19:05]</span> ALPHA: Executed scalp on BTC/USDT. PnL: +$14.20</div>
                <div class="log-entry"><span class="log-time">[15:19:30]</span> CUSTODE: Scanned block 19348102 on Arbitrum.</div>
                <div class="log-entry"><span class="log-time">[15:20:12]</span> ORACLE: Inflow spike detected on major CEXs.</div>
                <div class="log-entry"><span class="log-time">[15:21:00]</span> STROZZINO: Rebalancing short positions across Bybit/Binance.</div>
                <div class="log-entry"><span class="log-time">[15:21:15]</span> <span class="blink">_</span></div>
            </div>
        </div>
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
