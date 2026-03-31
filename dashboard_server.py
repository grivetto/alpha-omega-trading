from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NUVOLA ORBITAL COMMAND</title>
    <style>
        :root {
            --neon-green: #39ff14;
            --neon-blue: #0ff;
            --neon-pink: #ff00ff;
            --bg-color: #050505;
            --panel-bg: #111;
        }
        body {
            background-color: var(--bg-color);
            color: var(--neon-green);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            overflow-x: hidden;
        }
        h1, h2, h3 {
            text-transform: uppercase;
            text-shadow: 0 0 10px var(--neon-green);
            margin-top: 0;
        }
        .header {
            text-align: center;
            border-bottom: 2px solid var(--neon-green);
            padding-bottom: 10px;
            margin-bottom: 20px;
            animation: flicker 3s infinite;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
        }
        .panel {
            background-color: var(--panel-bg);
            border: 1px solid var(--neon-green);
            border-radius: 5px;
            padding: 15px;
            box-shadow: 0 0 15px rgba(57, 255, 20, 0.2);
            position: relative;
            overflow: hidden;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; height: 2px;
            background: var(--neon-green);
            box-shadow: 0 0 10px var(--neon-green);
        }
        .squad-alpha { border-color: var(--neon-pink); }
        .squad-alpha::before { background: var(--neon-pink); box-shadow: 0 0 10px var(--neon-pink); }
        .squad-alpha h2 { color: var(--neon-pink); text-shadow: 0 0 10px var(--neon-pink); }
        
        .squad-delta { border-color: var(--neon-blue); }
        .squad-delta::before { background: var(--neon-blue); box-shadow: 0 0 10px var(--neon-blue); }
        .squad-delta h2 { color: var(--neon-blue); text-shadow: 0 0 10px var(--neon-blue); }

        .status-online { color: #0f0; text-shadow: 0 0 5px #0f0; animation: blink 2s infinite; }
        .status-active { color: var(--neon-blue); text-shadow: 0 0 5px var(--neon-blue); }
        .status-warning { color: yellow; text-shadow: 0 0 5px yellow; }

        ul { list-style-type: none; padding: 0; }
        li { margin-bottom: 10px; padding-bottom: 5px; border-bottom: 1px dashed #333; }
        
        .metric-value { font-size: 1.5em; font-weight: bold; }
        
        @keyframes flicker {
            0%, 19%, 21%, 23%, 25%, 54%, 56%, 100% { opacity: 1; }
            20%, 22%, 24%, 55% { opacity: 0.5; }
        }
        @keyframes blink {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.3; }
        }
        @keyframes scroll {
            0% { transform: translateY(0); }
            100% { transform: translateY(-70%); }
        }
        .log-container {
            height: 150px;
            overflow: hidden;
            background: #000;
            border: 1px solid #333;
            padding: 10px;
            font-size: 0.9em;
            color: #ccc;
        }
        .log-stream {
            animation: scroll 15s linear infinite;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🛰️ ORBITAL COMMAND 🛰️</h1>
        <p>SYSTEM STATUS: <span class="status-online">ONLINE</span> | UPLINK: SECURE | LOCATION: NUVOLA NODE</p>
        <p style="font-weight: bold; color: var(--neon-green); text-shadow: 0 0 5px var(--neon-green);">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</p>
    </div>

    <div class="grid">
        <!-- ASSAULT SQUADS -->
        <div class="panel squad-alpha">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <ul>
                <li>
                    <strong>SQUADRA_ALPHA</strong> [Binance Scalper] <br>
                    Status: <span class="status-active">ENGAGED</span><br>
                    Targets: BTC/USDT, ETH/USDT
                </li>
                <li>
                    <strong>SQUADRA_DELTA</strong> [Order Flow] <br>
                    Status: <span class="status-active">MONITORING</span><br>
                    Targets: SOL/USDT, AVAX/USDT
                </li>
                <li>
                    <strong>SQUADRA_GAMMA</strong> [Bitget Pairs Trading] <br>
                    Status: <span class="status-warning">REBALANCING</span><br>
                    Spread: +0.45%
                </li>
            </ul>
        </div>

        <!-- PROTOCOL TRINITY -->
        <div class="panel">
            <h2>🛡️ PROTOCOLLO TRINITY</h2>
            <ul>
                <li>
                    <strong>Lo Strozzino</strong> [Funding Arb] <br>
                    Status: <span class="status-online">ACTIVE IN BACKGROUND</span><br>
                    Yield est.: 18.5% APY
                </li>
                <li>
                    <strong>Il Contabile</strong> [DCA Engine] <br>
                    Status: <span class="status-online">ACTIVE IN BACKGROUND</span><br>
                    Next execution: 04:00 UTC
                </li>
                <li>
                    <strong>L'Angelo Custode</strong> [MEV Arbitrum] <br>
                    Status: <span class="status-online">ACTIVE IN BACKGROUND</span><br>
                    Mempool scanning...
                </li>
            </ul>
        </div>

        <!-- MARKET METRICS -->
        <div class="panel squad-delta">
            <h2>📊 METRICHE DI MERCATO</h2>
            <ul>
                <li>
                    <strong>👁️ THE ORACLE</strong> [Binance Sentiment]<br>
                    Index: <span class="metric-value status-active">74</span> (GREED)<br>
                    Trend: Bullish Divergence
                </li>
                <li>
                    <strong>🐳 WHALE TRACKER</strong> [On-chain Flows]<br>
                    Inflow 24h: <span class="metric-value" style="color:#0f0">+4,500 BTC</span><br>
                    Outflow 24h: <span class="metric-value" style="color:red">-1,200 BTC</span>
                </li>
                <li>
                    <strong>⚡ NETWORK CONGESTION</strong><br>
                    Gas Base Fee: 14 gwei
                </li>
            </ul>
        </div>
        
        <!-- LIVE TERMINAL -->
        <div class="panel">
            <h2>💻 TACTICAL LOGS</h2>
            <div class="log-container">
                <div class="log-stream">
                    [SYS] Boot sequence initiated...<br>
                    [ALPHA] Executing limit order on BTC/USDT @ 68,450<br>
                    [TRINITY] Rebalancing funding rates across perp markets...<br>
                    [GAMMA] Short leg filled on Bitget.<br>
                    [SYS] Ping to Binance API: 12ms<br>
                    [ORACLE] Sentiment spike detected on altcoins.<br>
                    [WHALE] Large transfer: 50M USDT to Coinbase.<br>
                    [DELTA] Analyzing orderbook imbalance...<br>
                    [SYS] Node health nominal. Memory: 45%.<br>
                    [ANGELO] Transaction simulated. Profit too low, skipped.<br>
                    [ALPHA] Order filled. Profit: +$12.50<br>
                    [SYS] Awaiting new commands...<br>
                </div>
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
    app.run(host='0.0.0.0', port=5000, debug=False)
