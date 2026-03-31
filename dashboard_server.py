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
            --neon-cyan: #0ff;
            --neon-red: #ff073a;
            --neon-purple: #b026ff;
            --neon-yellow: #fcee0a;
            --bg-color: #050505;
            --panel-bg: rgba(10, 15, 10, 0.85);
            --grid-line: rgba(57, 255, 20, 0.08);
        }

        body {
            background-color: var(--bg-color);
            background-image: 
                linear-gradient(var(--grid-line) 1px, transparent 1px),
                linear-gradient(90deg, var(--grid-line) 1px, transparent 1px);
            background-size: 40px 40px;
            color: var(--neon-green);
            font-family: 'Share Tech Mono', monospace;
            margin: 0;
            padding: 30px;
            overflow-x: hidden;
            position: relative;
        }

        /* Scanlines */
        body::after {
            content: " ";
            display: block;
            position: fixed;
            top: 0; left: 0; bottom: 0; right: 0;
            background: linear-gradient(rgba(18, 16, 16, 0) 50%, rgba(0, 0, 0, 0.25) 50%), linear-gradient(90deg, rgba(255, 0, 0, 0.06), rgba(0, 255, 0, 0.02), rgba(0, 0, 255, 0.06));
            z-index: 100;
            background-size: 100% 2px, 3px 100%;
            pointer-events: none;
        }

        h1 {
            text-align: center;
            color: var(--neon-cyan);
            text-shadow: 0 0 5px var(--neon-cyan), 0 0 15px var(--neon-cyan), 0 0 30px var(--neon-cyan);
            letter-spacing: 10px;
            text-transform: uppercase;
            margin-bottom: 5px;
            font-size: 3em;
            border-bottom: 2px solid var(--neon-cyan);
            padding-bottom: 20px;
        }
        
        .subtitle {
            text-align: center;
            color: var(--neon-purple);
            letter-spacing: 5px;
            margin-bottom: 50px;
            text-shadow: 0 0 10px var(--neon-purple);
            font-size: 1.3em;
        }

        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 40px;
            position: relative;
            z-index: 10;
        }

        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-green);
            box-shadow: inset 0 0 20px rgba(57, 255, 20, 0.05), 0 0 15px rgba(57, 255, 20, 0.2);
            padding: 30px;
            position: relative;
            transition: all 0.3s ease;
            backdrop-filter: blur(5px);
        }
        
        .panel:hover {
            box-shadow: inset 0 0 30px rgba(57, 255, 20, 0.1), 0 0 25px rgba(57, 255, 20, 0.5);
            border-color: var(--neon-cyan);
        }

        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; width: 100%; height: 3px;
            background: var(--neon-green);
            box-shadow: 0 0 15px var(--neon-green);
        }

        .panel.cyber-red::before { background: var(--neon-red); box-shadow: 0 0 15px var(--neon-red); }
        .panel.cyber-red { border-color: var(--neon-red); }
        .panel.cyber-red:hover { box-shadow: inset 0 0 30px rgba(255, 7, 58, 0.1), 0 0 25px rgba(255, 7, 58, 0.5); border-color: #ff3366; }

        .panel.cyber-cyan::before { background: var(--neon-cyan); box-shadow: 0 0 15px var(--neon-cyan); }
        .panel.cyber-cyan { border-color: var(--neon-cyan); }
        .panel.cyber-cyan:hover { box-shadow: inset 0 0 30px rgba(0, 255, 255, 0.1), 0 0 25px rgba(0, 255, 255, 0.5); }

        .panel h2 {
            margin-top: 0;
            border-bottom: 1px dashed rgba(255,255,255,0.3);
            padding-bottom: 15px;
            font-size: 1.6em;
            display: flex;
            align-items: center;
            gap: 15px;
            text-transform: uppercase;
            letter-spacing: 2px;
            color: #fff;
            text-shadow: 0 0 5px #fff;
        }

        .status-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            padding: 15px;
            background: rgba(255, 255, 255, 0.03);
            border-left: 4px solid var(--neon-green);
            font-weight: bold;
            letter-spacing: 1px;
            position: relative;
            overflow: hidden;
            font-size: 1.1em;
        }

        .status-row::after {
            content: '';
            position: absolute;
            top: 0; left: -100%; width: 50%; height: 100%;
            background: linear-gradient(90deg, transparent, rgba(255,255,255,0.1), transparent);
            animation: scan 3s infinite linear;
        }

        @keyframes scan {
            0% { left: -100%; }
            100% { left: 200%; }
        }

        .status-row.active { border-color: var(--neon-green); color: var(--neon-green); text-shadow: 0 0 5px var(--neon-green); }
        .status-row.warning { border-color: var(--neon-yellow); color: var(--neon-yellow); text-shadow: 0 0 5px var(--neon-yellow); }
        .status-row.danger { border-color: var(--neon-red); color: var(--neon-red); text-shadow: 0 0 5px var(--neon-red); }
        .status-row.info { border-color: var(--neon-cyan); color: var(--neon-cyan); text-shadow: 0 0 5px var(--neon-cyan); }
        
        .blink { animation: blinker 1s linear infinite; }
        .blink-fast { animation: blinker 0.3s linear infinite; }
        @keyframes blinker { 50% { opacity: 0.2; } }
        
        .pulse { animation: pulse 2s infinite; }
        @keyframes pulse {
            0% { box-shadow: inset 0 0 0 0 rgba(57, 255, 20, 0.4); }
            70% { box-shadow: inset 0 0 0 10px rgba(57, 255, 20, 0); }
            100% { box-shadow: inset 0 0 0 0 rgba(57, 255, 20, 0); }
        }

        .bar-container {
            width: 100%;
            background: #222;
            height: 8px;
            margin-top: 8px;
            position: relative;
            border-radius: 2px;
            overflow: hidden;
        }
        
        .bar-fill {
            height: 100%;
            background: var(--neon-green);
            box-shadow: 0 0 10px var(--neon-green);
            animation: load 2s infinite alternate ease-in-out;
        }

        .bar-fill.red { background: var(--neon-red); box-shadow: 0 0 10px var(--neon-red); animation-duration: 0.8s; }
        .bar-fill.cyan { background: var(--neon-cyan); box-shadow: 0 0 10px var(--neon-cyan); animation-duration: 3s; }

        @keyframes load {
            0% { width: 40%; }
            100% { width: 95%; }
        }

        table { width: 100%; border-collapse: collapse; margin-top: 20px; font-size: 1em; }
        th, td { border: 1px solid rgba(57, 255, 20, 0.3); padding: 15px; text-align: left; }
        th { color: var(--neon-cyan); font-weight: bold; background: rgba(0, 255, 255, 0.08); text-transform: uppercase; letter-spacing: 2px; }
        td { color: #ddd; }
        
        .log-box {
            background: #000;
            border: 1px solid #333;
            padding: 15px;
            height: 150px;
            overflow: hidden;
            font-size: 0.9em;
            color: #888;
            margin-top: 25px;
            font-family: 'Share Tech Mono', monospace;
            box-shadow: inset 0 0 10px #000;
        }

        .log-box p { margin: 5px 0; border-bottom: 1px solid #111; padding-bottom: 3px;}
        .log-new { color: var(--neon-green); text-shadow: 0 0 3px var(--neon-green); }
        .log-warn { color: var(--neon-yellow); text-shadow: 0 0 3px var(--neon-yellow); }
        .log-err { color: var(--neon-red); text-shadow: 0 0 3px var(--neon-red); }

        .footer {
            margin-top: 60px;
            text-align: center;
            font-size: 1em;
            color: #555;
            letter-spacing: 4px;
            position: relative;
            z-index: 10;
        }
        
        .glitch {
            position: relative;
            display: inline-block;
        }
        .glitch::before, .glitch::after {
            content: attr(data-text);
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: var(--bg-color);
        }
        .glitch::before {
            left: 2px;
            text-shadow: -2px 0 var(--neon-red);
            clip: rect(24px, 550px, 90px, 0);
            animation: glitch-anim-2 3s infinite linear alternate-reverse;
        }
        .glitch::after {
            left: -2px;
            text-shadow: -2px 0 var(--neon-cyan);
            clip: rect(85px, 550px, 140px, 0);
            animation: glitch-anim 2.5s infinite linear alternate-reverse;
        }

        @keyframes glitch-anim {
            0% { clip: rect(13px, 9999px, 94px, 0); }
            20% { clip: rect(54px, 9999px, 12px, 0); }
            40% { clip: rect(121px, 9999px, 86px, 0); }
            60% { clip: rect(32px, 9999px, 102px, 0); }
            80% { clip: rect(76px, 9999px, 18px, 0); }
            100% { clip: rect(98px, 9999px, 45px, 0); }
        }
        @keyframes glitch-anim-2 {
            0% { clip: rect(65px, 9999px, 110px, 0); }
            20% { clip: rect(12px, 9999px, 87px, 0); }
            40% { clip: rect(98px, 9999px, 32px, 0); }
            60% { clip: rect(45px, 9999px, 115px, 0); }
            80% { clip: rect(21px, 9999px, 76px, 0); }
            100% { clip: rect(88px, 9999px, 14px, 0); }
        }
    </style>
</head>
<body>
    <h1 class="glitch" data-text="NUVOLA // ORBITAL COMMAND">NUVOLA // ORBITAL COMMAND</h1>
    <div class="subtitle">TACTICAL QUANTITATIVE ENGINE // V3.1.0-CYBER</div>
    
    <div class="grid">
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO [HFT]</h2>
            
            <div class="status-row active pulse">
                <div style="width: 100%">
                    <div style="display: flex; justify-content: space-between; margin-bottom: 5px;">
                        <span>🐺 SQUADRA_ALPHA <span style="color:#888;font-size:0.8em;">(BINANCE SCALPER)</span></span>
                        <span class="blink">[ ENGAGED ]</span>
                    </div>
                    <div class="bar-container"><div class="bar-fill" style="width: 85%;"></div></div>
                </div>
            </div>
            
            <div class="status-row warning">
                <div style="width: 100%">
                    <div style="display: flex; justify-content: space-between; margin-bottom: 5px;">
                        <span>⚡ SQUADRA_DELTA <span style="color:#888;font-size:0.8em;">(ORDER FLOW)</span></span>
                        <span>[ STANDBY ]</span>
                    </div>
                    <div class="bar-container"><div class="bar-fill cyan" style="width: 30%; animation: none;"></div></div>
                </div>
            </div>
            
            <div class="status-row danger">
                <div style="width: 100%">
                    <div style="display: flex; justify-content: space-between; margin-bottom: 5px;">
                        <span>⚖️ SQUADRA_GAMMA <span style="color:#888;font-size:0.8em;">(BITGET PAIRS)</span></span>
                        <span class="blink-fast">[ ARBITRAGE ]</span>
                    </div>
                    <div class="bar-container"><div class="bar-fill red" style="width: 65%;"></div></div>
                </div>
            </div>

            <div class="log-box">
                <p>> INIT HFT ENGINE...</p>
                <p class="log-new">> ALPHA: Executed buy 0.5 BTC @ 68,450</p>
                <p class="log-warn">> DELTA: Volatility below threshold. Waiting.</p>
                <p class="log-err">> GAMMA: Spread detected (BTC/USDT) - Executing...</p>
                <p>> SYNCING PORTFOLIO DATA...</p>
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel cyber-red">
            <h2>🔮 PROTOCOLLO TRINITY</h2>
            <div style="text-align: center; margin-bottom: 25px; color: var(--neon-green); font-weight: bold; font-size: 1.2em; border: 1px dashed var(--neon-green); padding: 15px; background: rgba(57,255,20,0.05); text-shadow: 0 0 5px var(--neon-green);">
                ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
            </div>
            
            <div class="status-row info">
                <span>🦇 Lo Strozzino <span style="font-size:0.8em;color:#aaa;">(Funding Arb)</span></span>
                <span class="blink">[ HARVESTING ]</span>
            </div>
            
            <div class="status-row active">
                <span>🧮 Il Contabile <span style="font-size:0.8em;color:#aaa;">(DCA)</span></span>
                <span>[ ACCUMULATING ]</span>
            </div>
            
            <div class="status-row danger pulse">
                <span>🛡️ L'Angelo Custode <span style="font-size:0.8em;color:#aaa;">(MEV Arbitrum)</span></span>
                <span class="blink-fast" style="text-shadow: 0 0 10px var(--neon-red);">[ SNIPING ]</span>
            </div>
            
            <table style="margin-top:25px; border-color: var(--neon-red);">
                <tr><th style="color:var(--neon-red); border-bottom: 2px solid var(--neon-red);">Daemon</th><th style="color:var(--neon-red); border-bottom: 2px solid var(--neon-red);">Uptime</th><th style="color:var(--neon-red); border-bottom: 2px solid var(--neon-red);">Yield/Action</th></tr>
                <tr><td>Strozzino</td><td>74h 12m</td><td style="color:var(--neon-green);">+0.04% / 8h</td></tr>
                <tr><td>Contabile</td><td>14d 05h</td><td style="color:var(--neon-cyan);">Next: 4h 12m</td></tr>
                <tr><td>Angelo Custode</td><td>System V</td><td style="color:var(--neon-red);" class="blink-fast">Scanning Tx...</td></tr>
            </table>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel cyber-cyan">
            <h2>📡 METRICHE DI MERCATO</h2>
            <table>
                <tr><th>Source</th><th>Metric</th><th>Live Data</th></tr>
                <tr>
                    <td>👁️ The Oracle</td>
                    <td>Binance Sentiment</td>
                    <td class="blink" style="color:var(--neon-green); font-weight:bold; text-shadow: 0 0 5px var(--neon-green);">EXTREME GREED (82)</td>
                </tr>
                <tr>
                    <td>🐋 Whale Tracker</td>
                    <td>24h Net Inflow</td>
                    <td style="color:var(--neon-red); font-weight:bold; text-shadow: 0 0 5px var(--neon-red);">+12,450 BTC 🚨</td>
                </tr>
                <tr>
                    <td>📉 Orderbook</td>
                    <td>Bid/Ask Imbalance</td>
                    <td style="color:var(--neon-yellow);">+4.2% (BULLISH)</td>
                </tr>
                <tr>
                    <td>⚡ Network</td>
                    <td>ETH Gas (Gwei)</td>
                    <td style="color:var(--neon-cyan);">14.2 ⛽</td>
                </tr>
                <tr>
                    <td>📊 Macro</td>
                    <td>DXY Index</td>
                    <td>103.45 (-0.2%)</td>
                </tr>
            </table>

            <div style="margin-top: 25px; border: 1px solid var(--neon-cyan); padding: 15px; background: rgba(0,255,255,0.05);">
                <div style="display:flex; justify-content:space-between; margin-bottom: 8px;">
                    <span style="color:var(--neon-cyan); font-weight:bold; font-size: 1.1em; text-shadow: 0 0 5px var(--neon-cyan);">GLOBAL LIQUIDITY INDEX</span>
                    <span style="color:var(--neon-cyan); font-size: 1.1em; font-weight: bold;">88.4%</span>
                </div>
                <div class="bar-container" style="height: 12px;"><div class="bar-fill cyan" style="width: 88%;"></div></div>
            </div>
        </div>
    </div>
    
    <div class="footer glitch" data-text="SYSTEM NOMINAL. CONNECTION SECURE. AUTHORIZED PERSONNEL ONLY.">
        SYSTEM NOMINAL. CONNECTION SECURE. AUTHORIZED PERSONNEL ONLY.
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    # Riavvia su porta 5000 (standard per flask, se necessario cambiarla)
    app.run(host='0.0.0.0', port=5000, debug=False)
