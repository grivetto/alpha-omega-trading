from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Nuvola Orbital Command</title>
    <style>
        :root {
            --neon-cyan: #0ff;
            --neon-magenta: #f0f;
            --neon-green: #0f0;
            --neon-yellow: #ff0;
            --bg-color: #050510;
            --panel-bg: rgba(10, 15, 25, 0.85);
            --grid-line: rgba(0, 255, 255, 0.1);
        }
        body {
            background-color: var(--bg-color);
            color: #e0e0e0;
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 30px;
            background-image: 
                linear-gradient(var(--grid-line) 1px, transparent 1px),
                linear-gradient(90deg, var(--grid-line) 1px, transparent 1px);
            background-size: 30px 30px;
            overflow-x: hidden;
        }
        /* CRT overlay effect */
        body::after {
            content: " ";
            display: block;
            position: absolute;
            top: 0; left: 0; bottom: 0; right: 0;
            background: linear-gradient(rgba(18, 16, 16, 0) 50%, rgba(0, 0, 0, 0.25) 50%), linear-gradient(90deg, rgba(255, 0, 0, 0.06), rgba(0, 255, 0, 0.02), rgba(0, 0, 255, 0.06));
            z-index: 2;
            background-size: 100% 2px, 3px 100%;
            pointer-events: none;
        }
        h1, h2, h3 {
            text-transform: uppercase;
            letter-spacing: 3px;
            margin-top: 0;
        }
        .header {
            text-align: center;
            color: var(--neon-cyan);
            text-shadow: 0 0 5px var(--neon-cyan), 0 0 15px var(--neon-cyan), 0 0 30px var(--neon-cyan);
            border-bottom: 2px solid var(--neon-cyan);
            padding-bottom: 15px;
            margin-bottom: 40px;
            animation: text-flicker 3s infinite alternate;
            position: relative;
            z-index: 10;
        }
        @keyframes text-flicker {
            0%, 19%, 21%, 23%, 25%, 54%, 56%, 100% { text-shadow: 0 0 5px var(--neon-cyan), 0 0 15px var(--neon-cyan), 0 0 30px var(--neon-cyan); opacity: 1; }
            20%, 24%, 55% { text-shadow: none; opacity: 0.5; }
        }
        .container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
            gap: 30px;
            position: relative;
            z-index: 10;
        }
        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-magenta);
            box-shadow: 0 0 15px rgba(255, 0, 255, 0.15), inset 0 0 20px rgba(255, 0, 255, 0.05);
            padding: 20px;
            border-radius: 4px;
            position: relative;
            overflow: hidden;
            transition: all 0.3s ease;
        }
        .panel:hover {
            box-shadow: 0 0 25px rgba(255, 0, 255, 0.3), inset 0 0 30px rgba(255, 0, 255, 0.1);
            transform: translateY(-2px);
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: -100%; width: 50%; height: 2px;
            background: linear-gradient(90deg, transparent, var(--neon-magenta), transparent);
            animation: scanline 4s linear infinite;
        }
        @keyframes scanline {
            0% { left: -100%; }
            100% { left: 200%; }
        }
        .panel h2 {
            color: var(--neon-magenta);
            border-bottom: 1px dashed var(--neon-magenta);
            padding-bottom: 10px;
            font-size: 1.3em;
            text-shadow: 0 0 8px rgba(255, 0, 255, 0.6);
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        .status-online { color: var(--neon-green); text-shadow: 0 0 8px var(--neon-green); font-weight: bold; }
        .status-standby { color: var(--neon-yellow); text-shadow: 0 0 8px var(--neon-yellow); font-weight: bold; }
        ul { list-style-type: none; padding: 0; margin: 0; }
        li { 
            margin-bottom: 20px; 
            border-left: 3px solid var(--neon-cyan); 
            padding-left: 15px; 
            background: rgba(0, 255, 255, 0.03);
            padding-top: 10px;
            padding-bottom: 10px;
            border-radius: 0 4px 4px 0;
        }
        .entity-name {
            font-size: 1.1em;
            color: #fff;
            text-shadow: 0 0 4px #fff;
            letter-spacing: 1px;
        }
        .metric-box {
            background: rgba(0, 255, 255, 0.05);
            border: 1px solid var(--neon-cyan);
            padding: 15px;
            margin-top: 15px;
            text-align: center;
            font-size: 1.1em;
            box-shadow: inset 0 0 15px rgba(0, 255, 255, 0.15);
            border-radius: 3px;
            position: relative;
        }
        .metric-box::after {
            content: ''; position: absolute; top: 0; left: 0; right: 0; bottom: 0;
            box-shadow: 0 0 10px var(--neon-cyan); opacity: 0.5; pointer-events: none;
        }
        .blink { animation: blinker 1.5s cubic-bezier(0.5, 0, 1, 1) infinite alternate; }
        @keyframes blinker { to { opacity: 0.3; } }
        
        .progress-bar {
            width: 100%;
            background-color: #222;
            border: 1px solid var(--neon-cyan);
            height: 20px;
            margin-top: 10px;
            position: relative;
        }
        .progress-fill {
            height: 100%;
            background-color: var(--neon-cyan);
            width: 82%;
            box-shadow: 0 0 10px var(--neon-cyan);
            animation: load 2s ease-out;
        }
        @keyframes load { from { width: 0; } }
        
        .trinity-active {
            border-color: var(--neon-green);
            box-shadow: 0 0 20px rgba(0, 255, 0, 0.2), inset 0 0 15px rgba(0, 255, 0, 0.1);
        }
        .trinity-active h2 {
            color: var(--neon-green);
            border-bottom-color: var(--neon-green);
            text-shadow: 0 0 8px rgba(0, 255, 0, 0.6);
        }
        .trinity-active::before {
            background: linear-gradient(90deg, transparent, var(--neon-green), transparent);
        }
        .data-stream {
            font-size: 0.8em;
            color: #888;
            height: 60px;
            overflow: hidden;
            border-top: 1px solid #333;
            margin-top: 15px;
            padding-top: 10px;
            font-family: monospace;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🛰️ NUVOLA ORBITAL COMMAND 🛰️</h1>
        <p style="font-size: 1.2em; letter-spacing: 2px;">
            SYSTEM STATUS: <span class="status-online blink">ONLINE</span> &nbsp;|&nbsp; UPLINK: <span style="color:var(--neon-cyan)">SECURE (AES-256)</span>
        </p>
        <div style="margin-top: 15px; font-size: 1.1em; color: var(--neon-green); text-shadow: 0 0 10px var(--neon-green); border: 1px solid var(--neon-green); display: inline-block; padding: 10px 20px; background: rgba(0, 255, 0, 0.1); border-radius: 5px;">
            <span class="blink">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</span>
        </div>
    </div>

    <div class="container">
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO <span style="font-size: 0.6em; color: #fff;">[ HFT CORE ]</span></h2>
            <ul>
                <li>
                    <strong class="entity-name">SQUADRA_ALPHA</strong> 🐺<br>
                    <span style="color: #aaa;">Role:</span> Scalper (Binance)<br>
                    <span style="color: #aaa;">Status:</span> <span class="status-online">ENGAGING TARGETS</span><br>
                    <div style="margin-top: 8px; font-size: 0.9em; color: var(--neon-cyan);">
                        > Win Rate: 68.4% | Latency: 12ms | PnL: +$420.50
                    </div>
                </li>
                <li>
                    <strong class="entity-name">SQUADRA_DELTA</strong> 🦅<br>
                    <span style="color: #aaa;">Role:</span> Order Flow Analysis<br>
                    <span style="color: #aaa;">Status:</span> <span class="status-online">MONITORING</span><br>
                    <div style="margin-top: 8px; font-size: 0.9em; color: var(--neon-cyan);">
                        > Imbalance detected: BTC/USDT (Bid side heavy)
                    </div>
                </li>
                <li>
                    <strong class="entity-name">SQUADRA_GAMMA</strong> 🐍<br>
                    <span style="color: #aaa;">Role:</span> Pairs Trading (Bitget)<br>
                    <span style="color: #aaa;">Status:</span> <span class="status-standby">AWAITING SPREAD</span><br>
                    <div style="margin-top: 8px; font-size: 0.9em; color: var(--neon-yellow);">
                        > ETH/BTC Spread: 0.42% (Target: >0.5%)
                    </div>
                </li>
            </ul>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel trinity-active">
            <h2>🔺 PROTOCOLLO TRINITY <span class="blink" style="font-size: 0.6em; color: #fff;">[ BACKGROUND ]</span></h2>
            <div class="metric-box" style="color: var(--neon-green); border-color: var(--neon-green); box-shadow: inset 0 0 15px rgba(0, 255, 0, 0.2); margin-bottom: 20px;">
                <span class="blink">⚙️ CORE PROTOCOLS ONLINE AND YIELDING</span>
            </div>
            <ul>
                <li style="border-left-color: var(--neon-green); background: rgba(0, 255, 0, 0.03);">
                    <strong class="entity-name">Lo Strozzino</strong> 🕴️<br>
                    <span style="color: #aaa;">Role:</span> Funding Rate Arbitrage<br>
                    <span style="color: #aaa;">Status:</span> <span class="status-online">HARVESTING</span><br>
                    <div style="margin-top: 8px; font-size: 0.9em; color: var(--neon-green);">
                        > Capturing premium on SOL-PERP (APR: 24.5%)
                    </div>
                </li>
                <li style="border-left-color: var(--neon-green); background: rgba(0, 255, 0, 0.03);">
                    <strong class="entity-name">Il Contabile</strong> 🧮<br>
                    <span style="color: #aaa;">Role:</span> Dynamic DCA<br>
                    <span style="color: #aaa;">Status:</span> <span class="status-online">ACCUMULATING</span><br>
                    <div style="margin-top: 8px; font-size: 0.9em; color: var(--neon-green);">
                        > Spot assets securing... Next buy in 4h 12m
                    </div>
                </li>
                <li style="border-left-color: var(--neon-green); background: rgba(0, 255, 0, 0.03);">
                    <strong class="entity-name">L'Angelo Custode</strong> 🛡️<br>
                    <span style="color: #aaa;">Role:</span> MEV Protection & Arb (Arbitrum)<br>
                    <span style="color: #aaa;">Status:</span> <span class="status-online">GUARDING</span><br>
                    <div style="margin-top: 8px; font-size: 0.9em; color: var(--neon-green);">
                        > Mempool scanning active. 0 front-runs detected.
                    </div>
                </li>
            </ul>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <h2>📊 METRICHE DI MERCATO <span style="font-size: 0.6em; color: #fff;">[ LIVE FEED ]</span></h2>
            
            <p style="margin-bottom: 5px; margin-top: 10px;">
                <strong style="color: var(--neon-cyan);">The Oracle</strong> 🔮 <span style="color:#aaa; font-size:0.9em;">(Binance Sentiment)</span>:
            </p>
            <div class="metric-box" style="color: var(--neon-green); border-color: var(--neon-green); box-shadow: inset 0 0 15px rgba(0, 255, 0, 0.2);">
                <div style="font-size: 1.2em; font-weight: bold; text-shadow: 0 0 5px var(--neon-green);">BULLISH CONFIDENCE: 82%</div>
                <div class="progress-bar" style="border-color: var(--neon-green);">
                    <div class="progress-fill" style="width: 82%; background-color: var(--neon-green); box-shadow: 0 0 10px var(--neon-green);"></div>
                </div>
            </div>
            
            <p style="margin-bottom: 5px; margin-top: 25px;">
                <strong style="color: var(--neon-magenta);">Whale Tracker</strong> 🐋 <span style="color:#aaa; font-size:0.9em;">(On-Chain)</span>:
            </p>
            <div class="metric-box" style="border-color: var(--neon-magenta); box-shadow: inset 0 0 15px rgba(255, 0, 255, 0.15);">
                <div style="color: #fff;">ALERT: <span style="color: var(--neon-yellow);">1,250 BTC</span> moved to Kraken</div>
                <div style="margin-top: 5px; font-size: 0.85em; color: var(--neon-magenta);">Probable impact: SELL PRESSURE DETECTED</div>
            </div>
            
            <div class="data-stream" id="data-stream">
                01010011 01011001 01010011 01010100 01000101 01001101<br>
                LOADING MARKET DATA...<br>
                PARSING ORDERBOOKS... [OK]<br>
                CALCULATING LIQUIDITY POOLS... [OK]
            </div>
            <script>
                // Simple script to make the data stream look alive
                const stream = document.getElementById('data-stream');
                const lines = [
                    "FETCHING BINANCE TICKER...",
                    "ANALYZING ORDER FLOW IMBALANCE...",
                    "DETECTED SPOOFING ON BITFINEX.",
                    "ARBITRUM RPC LATENCY: 45ms",
                    "CALCULATING FUNDING RATES...",
                    "UPDATING NEURAL WEIGHTS...",
                    "SYNDICATING DATA FEEDS..."
                ];
                setInterval(() => {
                    const newLine = document.createElement('div');
                    newLine.textContent = "> " + lines[Math.floor(Math.random() * lines.length)];
                    stream.appendChild(newLine);
                    if (stream.childNodes.length > 5) {
                        stream.removeChild(stream.firstChild);
                    }
                }, 2000);
            </script>
        </div>
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
