from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NUVOLA ORBITAL COMMAND</title>
    <style>
        :root {
            --neon-green: #39ff14;
            --neon-red: #ff073a;
            --neon-blue: #0ff;
            --neon-purple: #bc13fe;
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
            text-shadow: 0 0 5px var(--neon-green), 0 0 10px var(--neon-green);
            margin-top: 0;
        }
        .glow-blue { color: var(--neon-blue); text-shadow: 0 0 5px var(--neon-blue); }
        .glow-red { color: var(--neon-red); text-shadow: 0 0 5px var(--neon-red); }
        .glow-purple { color: var(--neon-purple); text-shadow: 0 0 5px var(--neon-purple); }
        
        .dashboard {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }
        .panel {
            background-color: var(--panel-bg);
            border: 1px solid var(--neon-green);
            padding: 20px;
            box-shadow: inset 0 0 10px rgba(57, 255, 20, 0.2), 0 0 15px rgba(57, 255, 20, 0.3);
            border-radius: 5px;
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
        .panel.blue { border-color: var(--neon-blue); box-shadow: inset 0 0 10px rgba(0, 255, 255, 0.2), 0 0 15px rgba(0, 255, 255, 0.3); }
        .panel.blue::before { background: var(--neon-blue); box-shadow: 0 0 10px var(--neon-blue); }
        
        .panel.purple { border-color: var(--neon-purple); box-shadow: inset 0 0 10px rgba(188, 19, 254, 0.2), 0 0 15px rgba(188, 19, 254, 0.3); }
        .panel.purple::before { background: var(--neon-purple); box-shadow: 0 0 10px var(--neon-purple); }
        
        .panel.red { border-color: var(--neon-red); box-shadow: inset 0 0 10px rgba(255, 7, 58, 0.2), 0 0 15px rgba(255, 7, 58, 0.3); }
        .panel.red::before { background: var(--neon-red); box-shadow: 0 0 10px var(--neon-red); }
        
        .blink { animation: blinker 1.5s linear infinite; }
        .fast-blink { animation: blinker 0.5s linear infinite; }
        @keyframes blinker { 50% { opacity: 0; } }
        
        .scanline {
            width: 100%;
            height: 100px;
            z-index: 10;
            position: fixed;
            pointer-events: none;
            background: linear-gradient(0deg, rgba(0,0,0,0) 0%, rgba(57,255,20,0.1) 50%, rgba(0,0,0,0) 100%);
            opacity: 0.5;
            animation: scanline 8s linear infinite;
        }
        @keyframes scanline {
            0% { top: -100px; }
            100% { top: 100vh; }
        }
        
        ul { list-style-type: none; padding: 0; margin: 0; }
        li { margin-bottom: 15px; border-bottom: 1px dashed #333; padding-bottom: 10px; font-size: 0.95em; line-height: 1.4; }
        li:last-child { border-bottom: none; margin-bottom: 0; padding-bottom: 0; }
        
        .status-online { color: var(--neon-green); font-weight: bold; text-shadow: 0 0 5px var(--neon-green); }
        .status-active { color: var(--neon-blue); font-weight: bold; text-shadow: 0 0 5px var(--neon-blue); }
        .status-warning { color: #ffeb3b; font-weight: bold; text-shadow: 0 0 5px #ffeb3b; }
        .status-critical { color: var(--neon-red); font-weight: bold; text-shadow: 0 0 5px var(--neon-red); }
        
        .data-label { color: #888; font-size: 0.85em; }
        .data-value { font-family: monospace; font-size: 1.1em; }
    </style>
</head>
<body>
    <div class="scanline"></div>
    <header style="text-align: center; margin-bottom: 20px; border-bottom: 1px solid #333; padding-bottom: 20px;">
        <h1 style="font-size: 2.5em; letter-spacing: 5px;">🛰️ NUVOLA ORBITAL COMMAND 🛰️</h1>
        <p style="font-size: 1.2em; letter-spacing: 2px;">
            SYSTEM STATUS: <span class="status-online blink">ONLINE</span> &nbsp;|&nbsp; 
            UPLINK: <span class="status-active">SECURE</span> &nbsp;|&nbsp; 
            MODE: <span class="status-critical">QUANTITATIVE MILITARY</span>
        </p>
        <p style="font-size: 1.1em; letter-spacing: 1px; margin-top: 10px;" class="glow-purple">
            <strong>⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</strong>
        </p>
    </header>

    <div class="dashboard">
        <!-- SQUADRE D'ASSALTO -->
        <div class="panel red">
            <h2 class="glow-red">⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <ul>
                <li>
                    <strong style="font-size: 1.2em;">[ SQUADRA_ALPHA ]</strong> 🐺<br>
                    <span class="data-label">Target:</span> Binance Scalping (BTC/USDT)<br>
                    <span class="data-label">Status:</span> <span class="status-critical fast-blink">ENGAGED - IN COMBAT</span><br>
                    <span class="data-label">Metrics:</span> APM: <span class="data-value">342</span> | WinRate: <span class="data-value">68.4%</span>
                </li>
                <li>
                    <strong style="font-size: 1.2em;">[ SQUADRA_DELTA ]</strong> 🦅<br>
                    <span class="data-label">Target:</span> Order Flow Spoofing Detection<br>
                    <span class="data-label">Status:</span> <span class="status-active">MONITORING</span><br>
                    <span class="data-label">Intel:</span> Imbalance <span class="data-value">+4.2M USDT</span> (Buy Side Pressure)
                </li>
                <li>
                    <strong style="font-size: 1.2em;">[ SQUADRA_GAMMA ]</strong> 🐍<br>
                    <span class="data-label">Target:</span> Bitget Pairs Trading<br>
                    <span class="data-label">Status:</span> <span class="status-online">STANDBY - WAITING FOR DIVERGENCE</span><br>
                    <span class="data-label">Signal:</span> Spread Z-Score: <span class="data-value">1.84</span> (Target > 2.0)
                </li>
            </ul>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel purple">
            <h2 class="glow-purple">🔮 PROTOCOLLO TRINITY</h2>
            <ul>
                <li>
                    <strong style="font-size: 1.2em;">💼 Lo Strozzino</strong> (Funding Arb)<br>
                    <span class="data-label">Status:</span> <span class="status-online">YIELDING</span><br>
                    <span class="data-label">Performance:</span> Est. APY: <span class="data-value glow-green">24.5%</span> | Exposure: <span class="data-value">Delta-Neutral</span>
                </li>
                <li>
                    <strong style="font-size: 1.2em;">🧮 Il Contabile</strong> (DCA Accumulator)<br>
                    <span class="data-label">Status:</span> <span class="status-active blink">ACCUMULATING</span><br>
                    <span class="data-label">Holdings:</span> BTC Avg Entry: <span class="data-value">$62,450</span> | Next Buy Level: <span class="data-value">-2.5%</span>
                </li>
                <li>
                    <strong style="font-size: 1.2em;">🛡️ L'Angelo Custode</strong> (MEV Arbitrum)<br>
                    <span class="data-label">Status:</span> <span class="status-critical blink">HUNTING FRONT-RUNNERS</span><br>
                    <span class="data-label">Operations:</span> Mempool Scanned: <span class="data-value">1450 tx/s</span> | Snipes Today: <span class="data-value glow-green">3</span>
                </li>
            </ul>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel blue">
            <h2 class="glow-blue">📊 METRICHE DI MERCATO</h2>
            <ul>
                <li>
                    <strong style="font-size: 1.2em;">👁️ The Oracle</strong> (Binance Sentiment)<br>
                    <span class="data-label">Index:</span> Fear & Greed: <span class="data-value status-online">72 (Greed)</span><br>
                    <span class="data-label">Ratio:</span> Whale Long/Short: <span class="data-value">1.45</span> <span class="status-online">(Bullish Bias)</span>
                </li>
                <li>
                    <strong style="font-size: 1.2em;">🐋 Whale Tracker</strong><br>
                    <span class="data-label">Alert [T-2m]:</span> <span class="data-value status-warning">1500 BTC moved to Coinbase</span><br>
                    <span class="data-label">Alert [T-15m]:</span> <span class="data-value glow-blue">50M USDT minted at Tether Treasury</span>
                </li>
                <li>
                    <strong style="font-size: 1.2em;">⚡ Liquidity Heatmap</strong><br>
                    <span class="data-label">Resistance:</span> <span class="data-value">$72,000</span> (Thick ask wall detected)<br>
                    <span class="data-label">Support:</span> <span class="data-value">$65,500</span> (Dense bid clusters)
                </li>
            </ul>
        </div>
    </div>
    
    <footer style="margin-top: 40px; text-align: center; font-size: 0.7em; color: #444; border-top: 1px solid #222; padding-top: 10px;">
        <p>NUVOLA CORE v4.0.0 | ENCRYPTED CONNECTION | UNAUTHORIZED ACCESS WILL BE TERMINATED</p>
    </footer>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    # Run on port 5000 by default
    app.run(host='0.0.0.0', port=5000)
