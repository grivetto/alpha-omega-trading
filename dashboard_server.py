from flask import Flask, render_template_string
import time

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
            --bg-color: #050510;
            --grid-color: rgba(0, 255, 170, 0.1);
            --neon-green: #00ffaa;
            --neon-blue: #00e5ff;
            --neon-red: #ff0055;
            --neon-purple: #b000ff;
            --text-main: #e0f2fe;
            --panel-bg: rgba(10, 15, 30, 0.85);
            --border-glow: 0 0 10px rgba(0, 255, 170, 0.5);
        }
        
        body {
            background-color: var(--bg-color);
            background-image: 
                linear-gradient(var(--grid-color) 1px, transparent 1px),
                linear-gradient(90deg, var(--grid-color) 1px, transparent 1px);
            background-size: 30px 30px;
            color: var(--text-main);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            overflow-x: hidden;
        }

        h1, h2, h3 {
            text-transform: uppercase;
            letter-spacing: 2px;
            margin-top: 0;
        }

        h1 {
            color: var(--neon-blue);
            text-shadow: 0 0 15px var(--neon-blue);
            text-align: center;
            border-bottom: 2px solid var(--neon-blue);
            padding-bottom: 10px;
            margin-bottom: 30px;
            animation: pulse 2s infinite;
        }

        .container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
            max-width: 1400px;
            margin: 0 auto;
        }

        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-green);
            box-shadow: var(--border-glow);
            padding: 20px;
            border-radius: 5px;
            position: relative;
            overflow: hidden;
        }
        
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; height: 2px;
            background: linear-gradient(90deg, transparent, var(--neon-green), transparent);
            animation: scanline 3s linear infinite;
        }

        .panel.red { border-color: var(--neon-red); box-shadow: 0 0 10px rgba(255, 0, 85, 0.5); }
        .panel.red::before { background: linear-gradient(90deg, transparent, var(--neon-red), transparent); }
        .panel.red h2 { color: var(--neon-red); text-shadow: 0 0 10px var(--neon-red); }

        .panel.blue { border-color: var(--neon-blue); box-shadow: 0 0 10px rgba(0, 229, 255, 0.5); }
        .panel.blue::before { background: linear-gradient(90deg, transparent, var(--neon-blue), transparent); }
        .panel.blue h2 { color: var(--neon-blue); text-shadow: 0 0 10px var(--neon-blue); }

        .panel.purple { border-color: var(--neon-purple); box-shadow: 0 0 10px rgba(176, 0, 255, 0.5); }
        .panel.purple::before { background: linear-gradient(90deg, transparent, var(--neon-purple), transparent); }
        .panel.purple h2 { color: var(--neon-purple); text-shadow: 0 0 10px var(--neon-purple); }

        h2 {
            color: var(--neon-green);
            text-shadow: 0 0 10px var(--neon-green);
            border-bottom: 1px dashed rgba(255,255,255,0.2);
            padding-bottom: 10px;
        }

        .status-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin: 15px 0;
            padding: 10px;
            background: rgba(0,0,0,0.5);
            border-left: 3px solid var(--neon-green);
        }

        .status-row.offline { border-left-color: var(--neon-red); }
        .status-row.standby { border-left-color: var(--neon-blue); }

        .status-indicator {
            display: inline-block;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background-color: var(--neon-green);
            box-shadow: 0 0 8px var(--neon-green);
            animation: blink 1s infinite alternate;
        }

        .offline .status-indicator { background-color: var(--neon-red); box-shadow: 0 0 8px var(--neon-red); animation: none; }
        .standby .status-indicator { background-color: var(--neon-blue); box-shadow: 0 0 8px var(--neon-blue); animation: blink 2s infinite alternate; }

        .metric-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
        }

        .metric-box {
            background: rgba(0,0,0,0.6);
            padding: 15px;
            text-align: center;
            border: 1px solid rgba(255,255,255,0.1);
        }

        .metric-value {
            font-size: 1.5em;
            color: var(--neon-green);
            text-shadow: 0 0 5px var(--neon-green);
            font-weight: bold;
            margin-top: 5px;
        }
        
        .metric-value.negative { color: var(--neon-red); text-shadow: 0 0 5px var(--neon-red); }

        @keyframes scanline {
            0% { transform: translateX(-100%); }
            100% { transform: translateX(100%); }
        }

        @keyframes blink {
            0% { opacity: 0.3; }
            100% { opacity: 1; }
        }

        @keyframes pulse {
            0% { text-shadow: 0 0 10px var(--neon-blue); }
            50% { text-shadow: 0 0 25px var(--neon-blue), 0 0 5px white; }
            100% { text-shadow: 0 0 10px var(--neon-blue); }
        }

        .log-window {
            height: 150px;
            background: #000;
            color: #0f0;
            padding: 10px;
            font-size: 0.85em;
            overflow-y: auto;
            border: 1px inset #333;
            margin-top: 15px;
        }
    </style>
</head>
<body>

    <h1>🌐 ORBITAL COMMAND | NUVOLA SYSTEM OVERVIEW 🌐</h1>

    <div class="container">
        
        <!-- SQUADRE D'ASSALTO -->
        <div class="panel red">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <div class="status-row">
                <span><span class="status-indicator"></span> <b>SQUADRA_ALPHA</b> (Binance Scalper)</span>
                <span style="color: var(--neon-green);">[ACTIVE]</span>
            </div>
            <div class="status-row standby">
                <span><span class="status-indicator"></span> <b>SQUADRA_DELTA</b> (Order Flow)</span>
                <span style="color: var(--neon-blue);">[MONITORING]</span>
            </div>
            <div class="status-row">
                <span><span class="status-indicator"></span> <b>SQUADRA_GAMMA</b> (Bitget Pairs)</span>
                <span style="color: var(--neon-green);">[ENGAGED]</span>
            </div>
            <div class="log-window" id="hft-logs">
                > ALPHA: Executing limit buy BTC/USDT @ 68,450.50<br>
                > GAMMA: Hedging ETH/SOL spread +1.2%<br>
                > DELTA: Whale alert 500 BTC moved to Coinbase<br>
                > ALPHA: Order filled. Trailing stop activated.<br>
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel blue">
            <h2>🔺 PROTOCOLLO TRINITY</h2>
            <div style="text-align: center; margin-bottom: 15px; padding: 10px; background: rgba(0, 255, 170, 0.2); border: 1px solid var(--neon-green); font-weight: bold; color: var(--text-main); text-shadow: 0 0 5px var(--neon-green);">
                ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
            </div>
            <div class="status-row">
                <span><span class="status-indicator"></span> <b>Lo Strozzino</b> (Funding Arb)</span>
                <span style="color: var(--neon-green);">[ONLINE]</span>
            </div>
            <div class="status-row">
                <span><span class="status-indicator"></span> <b>Il Contabile</b> (Smart DCA)</span>
                <span style="color: var(--neon-green);">[ONLINE]</span>
            </div>
            <div class="status-row">
                <span><span class="status-indicator"></span> <b>L'Angelo Custode</b> (MEV Arbitrum)</span>
                <span style="color: var(--neon-green);">[ONLINE]</span>
            </div>
            <div class="metric-grid" style="margin-top: 15px;">
                <div class="metric-box">
                    <div>Funding APR</div>
                    <div class="metric-value">+14.2%</div>
                </div>
                <div class="metric-box">
                    <div>MEV Blocks Won</div>
                    <div class="metric-value">42</div>
                </div>
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel purple">
            <h2>📡 THE ORACLE & METRICS</h2>
            <div class="metric-grid">
                <div class="metric-box">
                    <div>Binance Sentiment</div>
                    <div class="metric-value">BULLISH 🟢</div>
                </div>
                <div class="metric-box">
                    <div>Whale Flow (24h)</div>
                    <div class="metric-value negative">-1,240 BTC</div>
                </div>
                <div class="metric-box">
                    <div>Global Volatility</div>
                    <div class="metric-value" style="color: #ffaa00;">ELEVATED 🟡</div>
                </div>
                <div class="metric-box">
                    <div>System Latency</div>
                    <div class="metric-value" style="color: var(--neon-blue);">12ms</div>
                </div>
            </div>
            <div class="log-window" style="margin-top: 15px;">
                > ORACLE: Processing Twitter sentiment...<br>
                > ORACLE: Fear & Greed Index at 72.<br>
                > WHALE_TRACKER: Unknown wallet transferred 10M USDT to Binance.<br>
                > ORACLE: Liquidations map updated. Heavy resistance at 70k.<br>
            </div>
        </div>

    </div>

    <script>
        // Simple script to add some fake log scrolling
        setInterval(() => {
            const hftLogs = document.getElementById('hft-logs');
            const messages = [
                "> ALPHA: Adjusting bids...",
                "> GAMMA: Rebalancing delta...",
                "> SYSTEM: Ping Binance API: 8ms",
                "> DELTA: Orderbook imbalance detected (Bid > Ask)"
            ];
            const msg = messages[Math.floor(Math.random() * messages.length)];
            hftLogs.innerHTML += msg + '<br>';
            hftLogs.scrollTop = hftLogs.scrollHeight;
        }, 2500);
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    # Run on all interfaces, port 5000
    app.run(host='0.0.0.0', port=5000, debug=False)
