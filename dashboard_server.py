from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Nuvola Orbital Command</title>
    <style>
        :root {
            --bg-color: #050510;
            --neon-blue: #00f3ff;
            --neon-purple: #bc13fe;
            --neon-green: #00ff66;
            --neon-red: #ff003c;
            --text-main: #e0e0e0;
            --panel-bg: rgba(10, 10, 20, 0.8);
        }
        body {
            background-color: var(--bg-color);
            color: var(--text-main);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            background-image: radial-gradient(circle at 50% 50%, #1a1a2e 0%, #050510 100%);
        }
        h1, h2, h3 {
            text-transform: uppercase;
            letter-spacing: 2px;
        }
        .header {
            text-align: center;
            border-bottom: 2px solid var(--neon-blue);
            padding-bottom: 10px;
            margin-bottom: 30px;
            text-shadow: 0 0 10px var(--neon-blue);
        }
        .header h1 {
            margin: 0;
            font-size: 2.5em;
            color: var(--neon-blue);
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
        }
        .panel {
            background: var(--panel-bg);
            border: 1px solid #333;
            border-radius: 5px;
            padding: 15px;
            box-shadow: 0 0 15px rgba(0, 243, 255, 0.1);
            position: relative;
            overflow: hidden;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; height: 2px;
            background: linear-gradient(90deg, transparent, var(--neon-blue), transparent);
            animation: scan 2s linear infinite;
        }
        @keyframes scan {
            0% { transform: translateX(-100%); }
            100% { transform: translateX(100%); }
        }
        .panel-title {
            color: var(--neon-purple);
            border-bottom: 1px dashed #555;
            padding-bottom: 5px;
            margin-top: 0;
            text-shadow: 0 0 5px var(--neon-purple);
        }
        .status-online { color: var(--neon-green); text-shadow: 0 0 5px var(--neon-green); font-weight: bold; }
        .status-offline { color: var(--neon-red); text-shadow: 0 0 5px var(--neon-red); font-weight: bold; }
        .status-warning { color: #ffcc00; text-shadow: 0 0 5px #ffcc00; font-weight: bold; }
        
        ul { list-style-type: none; padding: 0; margin: 0; }
        li { margin-bottom: 10px; padding: 10px; background: rgba(0,0,0,0.5); border-left: 3px solid #555; transition: all 0.3s; }
        li:hover { background: rgba(255,255,255,0.05); transform: translateX(5px); }
        .hft-item { border-left-color: var(--neon-red); }
        .trinity-item { border-left-color: var(--neon-blue); }
        
        .metric-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
        .metric-box { background: rgba(255,255,255,0.05); padding: 10px; text-align: center; border: 1px solid #222; }
        .metric-value { font-size: 1.5em; color: var(--neon-green); margin-top: 5px; }
        
        .blink { animation: blinker 1.5s linear infinite; }
        @keyframes blinker { 50% { opacity: 0.3; } }
        
        .log-window { font-size: 0.8em; height: 120px; overflow-y: hidden; background: #000; padding: 10px; border: 1px solid #333; color: #0f0; font-family: 'Courier New', monospace; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🛰️ NUVOLA ORBITAL COMMAND</h1>
        <p class="blink" style="color: var(--neon-green);">[ SYSTEM ONLINE ] - SECURE UPLINK ESTABLISHED</p>
        <div style="background: rgba(0, 243, 255, 0.1); border: 1px solid var(--neon-blue); display: inline-block; padding: 10px 20px; border-radius: 5px; margin-top: 10px; font-weight: bold; text-shadow: 0 0 5px var(--neon-blue); color: var(--text-main);">
            ⚙️ PROTOCOLLO TRINITY: <span style="color: var(--neon-green); text-shadow: 0 0 5px var(--neon-green);">Online (DCA, Funding, MEV)</span>
        </div>
    </div>

    <div class="grid">
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <h2 class="panel-title">⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <ul>
                <li class="hft-item">
                    <strong>🦅 SQUADRA_ALPHA</strong> (Scalper - Binance)<br>
                    Status: <span class="status-online">ENGAGING TARGETS</span><br>
                    <small style="color: #aaa;">Latency: 12ms | Execs/min: 45</small>
                </li>
                <li class="hft-item">
                    <strong>🐺 SQUADRA_DELTA</strong> (Order Flow)<br>
                    Status: <span class="status-online">MONITORING L2</span><br>
                    <small style="color: #aaa;">Imbalance detected. Awaiting trigger.</small>
                </li>
                <li class="hft-item">
                    <strong>🦈 SQUADRA_GAMMA</strong> (Pairs Trading - Bitget)<br>
                    Status: <span class="status-online">ARBITRAGE ACTIVE</span><br>
                    <small style="color: #aaa;">Spread: 0.15% | Target: 0.20%</small>
                </li>
            </ul>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2 class="panel-title">🔺 PROTOCOLLO TRINITY</h2>
            <ul>
                <li class="trinity-item">
                    <strong>🕴️ Lo Strozzino</strong> (Funding Arb)<br>
                    Status: <span class="status-online">COLLECTING PREMIUMS</span><br>
                    <small style="color: #aaa;">Yield: +18.4% APY</small>
                </li>
                <li class="trinity-item">
                    <strong>🧮 Il Contabile</strong> (DCA)<br>
                    Status: <span class="status-online">ACCUMULATING</span><br>
                    <small style="color: #aaa;">Next buy in: 4h 12m</small>
                </li>
                <li class="trinity-item">
                    <strong>👼 L'Angelo Custode</strong> (MEV Arbitrum)<br>
                    Status: <span class="status-online">SHADOW MODE</span><br>
                    <small style="color: #aaa;">Scanning mempool for sandwiches...</small>
                </li>
            </ul>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <h2 class="panel-title">🌐 METRICHE & ORACLE</h2>
            <div class="metric-grid">
                <div class="metric-box">
                    <div style="font-size: 0.8em; color: #888;">🔮 The Oracle (Sentiment)</div>
                    <div class="metric-value">BULLISH 78%</div>
                </div>
                <div class="metric-box">
                    <div style="font-size: 0.8em; color: #888;">🐋 Whale Tracker</div>
                    <div class="metric-value status-warning blink">ALERT</div>
                </div>
                <div class="metric-box">
                    <div style="font-size: 0.8em; color: #888;">📊 Volatility Index</div>
                    <div class="metric-value" style="color: var(--neon-red)">HIGH</div>
                </div>
                <div class="metric-box">
                    <div style="font-size: 0.8em; color: #888;">⚡ Global Latency</div>
                    <div class="metric-value">24ms</div>
                </div>
            </div>
            <div style="margin-top: 15px;">
                <strong style="color: var(--neon-blue);">[LIVE TACTICAL FEED]</strong>
                <div class="log-window" id="log-window">
                    > Initializing connection to Binance WSS... OK<br>
                    > The Oracle predicts upward momentum.<br>
                    > SQUADRA_ALPHA executed BUY at market.<br>
                    > L'Angelo Custode preempted transaction 0x4a...2f<br>
                </div>
            </div>
        </div>
    </div>

    <script>
        const logs = [
            "> SQUADRA_GAMMA identified spread on BTC/USDT...",
            "> Lo Strozzino received funding fee: +12.45 USDT",
            "> WARNING: High volume detected on SOL...",
            "> Il Contabile executing DCA tier 2...",
            "> The Oracle sentiment shifted +2%",
            "> Orbital Command uplink latency spike: resolved.",
            "> SQUADRA_DELTA analyzing spoofing in order book...",
            "> L'Angelo Custode secured +0.02 ETH from frontrun",
            "> System memory optimization complete."
        ];
        const logWindow = document.getElementById('log-window');
        setInterval(() => {
            const newLog = logs[Math.floor(Math.random() * logs.length)];
            const time = new Date().toLocaleTimeString('it-IT');
            logWindow.innerHTML += `[${time}] ${newLog}<br>`;
            logWindow.scrollTop = logWindow.scrollHeight;
        }, 2500);
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
