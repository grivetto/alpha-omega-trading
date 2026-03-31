from flask import Flask, render_template_string
import threading

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ORBITAL COMMAND | NUVOLA</title>
    <style>
        :root {
            --neon-blue: #00f3ff;
            --neon-pink: #ff00ff;
            --neon-green: #00ff00;
            --neon-red: #ff003c;
            --bg-color: #050505;
            --panel-bg: rgba(10, 10, 15, 0.85);
            --font-main: 'Courier New', Courier, monospace;
        }
        body {
            background-color: var(--bg-color);
            color: var(--neon-blue);
            font-family: var(--font-main);
            margin: 0;
            padding: 2% 5%;
            background-image: linear-gradient(rgba(0, 243, 255, 0.05) 1px, transparent 1px),
            linear-gradient(90deg, rgba(0, 243, 255, 0.05) 1px, transparent 1px);
            background-size: 30px 30px;
            overflow-x: hidden;
        }
        h1, h2, h3 {
            text-transform: uppercase;
            letter-spacing: 3px;
            margin-top: 0;
        }
        h1 {
            text-align: center;
            color: var(--neon-pink);
            text-shadow: 0 0 10px var(--neon-pink), 0 0 20px var(--neon-pink), 0 0 40px var(--neon-pink);
            border-bottom: 2px solid var(--neon-pink);
            padding-bottom: 15px;
            margin-bottom: 5px;
            animation: pulse-pink 2s infinite alternate;
        }
        .header-sub {
            text-align: center;
            font-weight: bold;
            margin-bottom: 30px;
            letter-spacing: 2px;
            text-shadow: 0 0 5px var(--neon-green);
        }
        
        @keyframes pulse-pink {
            from { text-shadow: 0 0 10px var(--neon-pink), 0 0 20px var(--neon-pink); }
            to { text-shadow: 0 0 15px var(--neon-pink), 0 0 30px var(--neon-pink), 0 0 40px var(--neon-pink); }
        }

        .grid-container {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 25px;
        }
        
        .panel {
            background-color: var(--panel-bg);
            border: 1px solid var(--neon-blue);
            box-shadow: inset 0 0 15px rgba(0, 243, 255, 0.1), 0 0 15px rgba(0, 243, 255, 0.2);
            padding: 20px;
            border-radius: 4px;
            position: relative;
            transition: all 0.3s ease;
        }
        .panel:hover {
            box-shadow: inset 0 0 20px rgba(0, 243, 255, 0.2), 0 0 25px rgba(0, 243, 255, 0.4);
        }
        
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; width: 100%; height: 3px;
            background: var(--neon-blue);
            box-shadow: 0 0 15px var(--neon-blue);
        }
        
        .panel.red { border-color: var(--neon-red); color: #fff; }
        .panel.red::before { background: var(--neon-red); box-shadow: 0 0 15px var(--neon-red); }
        .panel.red h2 { color: var(--neon-red); text-shadow: 0 0 10px var(--neon-red); }
        
        .panel.green { border-color: var(--neon-green); color: #fff; grid-column: span 2; }
        .panel.green::before { background: var(--neon-green); box-shadow: 0 0 15px var(--neon-green); }
        .panel.green h2 { color: var(--neon-green); text-shadow: 0 0 10px var(--neon-green); }
        
        .panel.blue { color: #fff; }
        .panel.blue h2 { color: var(--neon-blue); text-shadow: 0 0 10px var(--neon-blue); }

        .status {
            display: flex;
            align-items: center;
            margin-bottom: 12px;
            font-size: 1.1em;
            background: rgba(255,255,255,0.05);
            padding: 8px;
            border-radius: 3px;
            border-left: 3px solid transparent;
        }
        
        .status:hover {
            background: rgba(255,255,255,0.1);
        }

        .indicator {
            width: 12px; height: 12px;
            border-radius: 50%;
            margin-right: 15px;
            animation: blink 2s infinite;
        }
        .indicator.online { background-color: var(--neon-green); box-shadow: 0 0 10px var(--neon-green); animation-duration: 1s; }
        .indicator.standby { background-color: var(--neon-blue); box-shadow: 0 0 10px var(--neon-blue); animation-duration: 3s; }
        .indicator.alert { background-color: var(--neon-red); box-shadow: 0 0 10px var(--neon-red); animation: fast-blink 0.5s infinite; }
        
        @keyframes blink {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.3; }
        }
        @keyframes fast-blink {
            0%, 100% { opacity: 1; }
            50% { opacity: 0; }
        }

        .data-stream {
            font-size: 0.9em;
            color: #aaa;
            margin-top: 15px;
            padding: 10px;
            background: #000;
            border: 1px dashed #444;
            height: 100px;
            overflow-y: hidden;
            position: relative;
        }
        .data-stream::after {
            content: '';
            position: absolute;
            bottom: 0; left: 0; width: 100%; height: 30px;
            background: linear-gradient(transparent, #000);
        }
        
        .metrics-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
        }
        
        .metric-box {
            background: #000;
            padding: 15px;
            border: 1px solid #333;
            border-radius: 3px;
        }
        
        .scanline {
            width: 100%;
            height: 100px;
            z-index: 9999;
            position: absolute;
            pointer-events: none;
            background: linear-gradient(0deg, rgba(0, 0, 0, 0) 0%, rgba(0, 243, 255, 0.2) 50%, rgba(0, 0, 0, 0) 100%);
            opacity: 0.1;
            animation: scanline 8s linear infinite;
        }
        
        @keyframes scanline {
            0% { top: -100px; }
            100% { top: 100vh; }
        }
        
        b { color: var(--neon-blue); }
        .red b { color: var(--neon-red); }
        .green b { color: var(--neon-green); }
    </style>
</head>
<body>
    <div class="scanline"></div>
    <h1>🛰️ ORBITAL COMMAND 🛰️</h1>
    <div class="header-sub" style="color:var(--neon-green);">SYSTEM STATUS: ONLINE | SECURE QUANTITATIVE UPLINK ESTABLISHED</div>
    
    <div class="grid-container">
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel red">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <div class="status" style="border-left-color: var(--neon-green);">
                <div class="indicator online"></div> 
                <span><b>SQUADRA_ALPHA</b> [Scalper @ Binance] - ACTIVE (Win Rate: 68%)</span>
            </div>
            <div class="status" style="border-left-color: var(--neon-green);">
                <div class="indicator online"></div> 
                <span><b>SQUADRA_DELTA</b> [Order Flow] - ACTIVE (Volume: 1.2M)</span>
            </div>
            <div class="status" style="border-left-color: var(--neon-blue);">
                <div class="indicator standby"></div> 
                <span><b>SQUADRA_GAMMA</b> [Pairs Trading @ Bitget] - STANDBY (Awaiting Spread)</span>
            </div>
            <div class="data-stream">
> [SYS] Alpha executing 42 ops/min
> [SYS] Delta detecting heavy spoofing on BTC/USDT orderbook
> [SYS] Gamma monitoring ETH/SOL correlation matrix
> [SYS] Re-calibrating latency thresholds... [OK]
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel blue">
            <h2>🔺 PROTOCOLLO TRINITY</h2>
            <div class="status" style="border-left-color: var(--neon-green); border-bottom: 1px solid var(--neon-green); padding-bottom: 15px; margin-bottom: 15px;">
                <div class="indicator online"></div>
                <span style="color: var(--neon-green); font-size: 1.2em; font-weight: bold; text-shadow: 0 0 5px var(--neon-green);">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</span>
            </div>
            <div class="status" style="border-left-color: var(--neon-green);">
                <div class="indicator online"></div> 
                <span><b>Lo Strozzino</b> [Funding Arb] - ONLINE (APR: 18.4%)</span>
            </div>
            <div class="status" style="border-left-color: var(--neon-green);">
                <div class="indicator online"></div> 
                <span><b>Il Contabile</b> [DCA Engine] - ONLINE (Next buy: 4h 12m)</span>
            </div>
            <div class="status" style="border-left-color: var(--neon-green);">
                <div class="indicator online"></div> 
                <span><b>L'Angelo Custode</b> [MEV @ Arbitrum] - ONLINE (Guarding tx pool)</span>
            </div>
            <div class="data-stream">
> [TRINITY] Background Daemons Sync: OK
> [TRINITY] Core Temperature: Optimal
> [TRINITY] L'Angelo Custode successfully preempted toxic flow
> [TRINITY] Awaiting further directives...
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel green">
            <h2>📊 METRICHE DI MERCATO</h2>
            <div class="metrics-grid">
                <div class="metric-box">
                    <h3>👁️ THE ORACLE (Binance Sentiment)</h3>
                    <p>FEAR & GREED INDEX: <b style="font-size: 1.2em; color: var(--neon-green);">72 (GREED)</b></p>
                    <p>ORDERBOOK IMBALANCE: <b>+14% BID</b></p>
                    <p>AI PREDICTION (1H): <b style="color:var(--neon-green);">BULLISH</b></p>
                    <p>VOLATILITY INDEX: <b>MODERATE</b></p>
                </div>
                <div class="metric-box">
                    <h3>🐋 WHALE TRACKER</h3>
                    <div class="data-stream" style="border:none; height:auto; padding:0;">
<span style="color: var(--neon-red);">[ALERT]</span> 1,450 BTC moved to Coinbase (Possible Dump)
<span style="color: var(--neon-red);">[ALERT]</span> 40,000 ETH withdrawn from Binance
<span style="color: var(--neon-blue);">[INFO]</span> Accumulation detected on ARB (Wallet 0x7a...4b)
<span style="color: var(--neon-blue);">[INFO]</span> $50M USDC minted on Ethereum Network
                    </div>
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
    # Running on 5000 or any port
    app.run(host='0.0.0.0', port=5000, debug=False)
