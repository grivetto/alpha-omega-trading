import os
from flask import Flask, render_template_string

app = Flask(__name__)

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Nuvola | Orbital Command</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');
        
        :root {
            --neon-green: #0f0;
            --neon-pink: #f0f;
            --neon-blue: #0ff;
            --neon-red: #f00;
            --neon-yellow: #ff0;
            --bg-dark: #020202;
            --panel-bg: rgba(10, 10, 10, 0.85);
            --grid-color: rgba(0, 255, 255, 0.05);
        }
        body {
            background-color: var(--bg-dark);
            color: var(--neon-green);
            font-family: 'Share Tech Mono', monospace;
            margin: 0;
            padding: 30px;
            background-image: 
                linear-gradient(var(--grid-color) 1px, transparent 1px),
                linear-gradient(90deg, var(--grid-color) 1px, transparent 1px);
            background-size: 30px 30px;
            overflow-x: hidden;
        }
        
        /* Glitch effect on title */
        h1 { 
            text-align: center; 
            text-transform: uppercase; 
            letter-spacing: 8px; 
            font-size: 2.5em;
            color: #fff;
            text-shadow: 
                0 0 10px var(--neon-blue),
                0 0 20px var(--neon-blue),
                0 0 40px var(--neon-blue);
            margin-bottom: 40px;
            position: relative;
        }
        
        h1::before, h1::after {
            content: "🛰️ ORBITAL COMMAND - NUVOLA 🛰️";
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: var(--bg-dark);
        }
        
        h1::before {
            left: 2px;
            text-shadow: -2px 0 red;
            animation: glitch-anim-1 2s infinite linear alternate-reverse;
        }
        h1::after {
            left: -2px;
            text-shadow: -2px 0 blue;
            animation: glitch-anim-2 3s infinite linear alternate-reverse;
        }
        
        @keyframes glitch-anim-1 {
            0% { clip: rect(20px, 9999px, 85px, 0); }
            5% { clip: rect(54px, 9999px, 20px, 0); }
            10% { clip: rect(10px, 9999px, 90px, 0); }
            100% { clip: rect(32px, 9999px, 12px, 0); }
        }
        @keyframes glitch-anim-2 {
            0% { clip: rect(12px, 9999px, 80px, 0); }
            5% { clip: rect(80px, 9999px, 22px, 0); }
            10% { clip: rect(40px, 9999px, 94px, 0); }
            100% { clip: rect(60px, 9999px, 40px, 0); }
        }

        .container { 
            display: grid; 
            grid-template-columns: 1fr 1fr; 
            gap: 30px; 
            max-width: 1400px; 
            margin: auto; 
        }
        
        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-blue);
            padding: 25px;
            border-radius: 8px;
            box-shadow: 
                0 0 15px rgba(0, 255, 255, 0.1),
                inset 0 0 20px rgba(0, 255, 255, 0.05);
            position: relative;
            backdrop-filter: blur(5px);
        }
        
        .panel::after {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; height: 2px;
            background: linear-gradient(90deg, transparent, var(--neon-blue), transparent);
            animation: scanline 4s linear infinite;
        }
        
        @keyframes scanline { 
            0% { transform: translateY(-10px); opacity: 0; }
            50% { opacity: 1; }
            100% { transform: translateY(400px); opacity: 0; }
        }
        
        .panel h2 {
            color: var(--neon-blue);
            border-bottom: 2px dashed rgba(0, 255, 255, 0.4);
            padding-bottom: 10px;
            text-shadow: 0 0 10px var(--neon-blue);
            margin-top: 0;
            font-size: 1.5em;
            letter-spacing: 2px;
        }
        
        .panel p {
            font-size: 1.1em;
            line-height: 1.6;
            margin: 15px 0;
            border-left: 3px solid rgba(0,255,0,0.3);
            padding-left: 10px;
        }
        
        .pink-glow { 
            color: var(--neon-pink) !important; 
            text-shadow: 0 0 10px var(--neon-pink) !important; 
            border-bottom: 2px dashed rgba(255, 0, 255, 0.4) !important; 
        }
        
        .status-on { 
            color: var(--neon-green); 
            text-shadow: 0 0 8px var(--neon-green);
            animation: pulse-green 2s infinite; 
            font-weight: bold; 
        }
        
        .status-standby { 
            color: var(--neon-yellow); 
            text-shadow: 0 0 8px var(--neon-yellow);
            animation: pulse-yellow 3s infinite; 
        }
        
        .status-active {
            color: var(--neon-pink);
            text-shadow: 0 0 8px var(--neon-pink);
            font-weight: bold;
        }
        
        @keyframes pulse-green { 0%, 100% { opacity: 1; text-shadow: 0 0 8px #0f0; } 50% { opacity: 0.7; text-shadow: 0 0 2px #0f0; } }
        @keyframes pulse-yellow { 0%, 100% { opacity: 1; text-shadow: 0 0 8px #ff0; } 50% { opacity: 0.5; text-shadow: none; } }
        
        table { 
            width: 100%; 
            border-collapse: separate; 
            border-spacing: 0;
            margin-top: 20px; 
            border: 1px solid rgba(0,255,255,0.3);
        }
        
        th, td { 
            padding: 15px; 
            text-align: left; 
            border-bottom: 1px solid rgba(0, 255, 255, 0.1);
        }
        
        th { 
            color: var(--neon-blue); 
            background-color: rgba(0, 255, 255, 0.05);
            text-transform: uppercase;
            letter-spacing: 1px;
            font-weight: bold;
        }
        
        td { color: #ddd; }
        
        tr:hover td {
            background-color: rgba(0, 255, 255, 0.05);
            color: #fff;
        }
        
        .indicator-green { color: var(--neon-green); text-shadow: 0 0 5px var(--neon-green); font-weight: bold; }
        .indicator-red { color: var(--neon-red); text-shadow: 0 0 5px var(--neon-red); font-weight: bold; }
        .indicator-white { color: #fff; text-shadow: 0 0 5px #fff; font-weight: bold; }
        
        .terminal-line {
            display: inline-block;
            overflow: hidden;
            white-space: nowrap;
            border-right: .15em solid orange;
            animation: typing 3.5s steps(40, end), blink-caret .75s step-end infinite;
        }
        
        @keyframes typing { from { width: 0 } to { width: 100% } }
        @keyframes blink-caret { from, to { border-color: transparent } 50% { border-color: orange; } }
    </style>
</head>
<body>
    <h1>🛰️ ORBITAL COMMAND - NUVOLA 🛰️</h1>
    <div class="container">
        <!-- SEZIONE 1: SQUADRE D'ASSALTO -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <p>⚡ <strong>SQUADRA_ALPHA</strong> (Scalper Binance): <br><span class="status-on">[SYS_ONLINE] 🟢 EXEC T: 1.2ms | PnL 24h: +3.4%</span></p>
            <p>🌊 <strong>SQUADRA_DELTA</strong> (Order Flow): <br><span class="status-on">[SYS_ONLINE] 🟢 READING TAPE | Imbalance: LONG</span></p>
            <p>⚖️ <strong>SQUADRA_GAMMA</strong> (Pairs Trading Bitget): <br><span class="status-standby">[SYS_STANDBY] 🟡 WAITING Z-SCORE > 2.0</span></p>
        </div>
        
        <!-- SEZIONE 2: PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2 class="pink-glow">🛡️ PROTOCOLLO TRINITY</h2>
            <div style="background: rgba(255,0,255,0.1); padding: 10px; margin-bottom: 15px; border: 1px dashed var(--neon-pink); text-align: center; color: var(--neon-pink); text-shadow: 0 0 8px var(--neon-pink);">
                ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
            </div>
            <p style="border-left-color: var(--neon-pink);">🦇 <strong>Lo Strozzino</strong> (Funding Arb): <br><span class="status-active">[ACTIVE] 🟣 HARVESTING YIELD | APR: 18.5%</span></p>
            <p style="border-left-color: var(--neon-pink);">🧮 <strong>Il Contabile</strong> (DCA): <br><span class="status-active">[ACTIVE] 🟣 ACCUMULATING BTC | Avg Entry: $65K</span></p>
            <p style="border-left-color: var(--neon-pink);">👼 <strong>L'Angelo Custode</strong> (MEV Arbitrum): <br><span class="status-active">[ACTIVE] 🟣 FRONT-RUNNING PROTECTED | Tx Saved: 14</span></p>
        </div>
        
        <!-- SEZIONE 3: METRICHE DI MERCATO -->
        <div class="panel" style="grid-column: span 2;">
            <h2>📊 METRICHE DI MERCATO (The Oracle & Whale Tracker)</h2>
            <table>
                <thead>
                    <tr>
                        <th>ASSET TARGET</th>
                        <th>SENTIMENT (The Oracle)</th>
                        <th>WHALE FLOW (24h)</th>
                        <th>ALGORITHMIC SIGNAL</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td><strong>BTC/USDT</strong></td>
                        <td class="indicator-green">BULLISH [0.82] 🟢</td>
                        <td class="indicator-green">▲ + 1,200 BTC Inflow</td>
                        <td class="indicator-green">LONG (Conf: 87%)</td>
                    </tr>
                    <tr>
                        <td><strong>ETH/USDT</strong></td>
                        <td class="indicator-white">NEUTRAL [0.51] ⚪</td>
                        <td class="indicator-red">▼ - 300 ETH Outflow</td>
                        <td class="indicator-white">HOLD (Conf: 54%)</td>
                    </tr>
                    <tr>
                        <td><strong>SOL/USDT</strong></td>
                        <td class="indicator-red">EXTREME GREED [0.94] 🔴</td>
                        <td class="indicator-green">▲ + 15,000 SOL Inflow</td>
                        <td class="indicator-red">SHORT SCALP (Conf: 92%)</td>
                    </tr>
                </tbody>
            </table>
            <div style="margin-top: 20px; color: #777; font-size: 0.9em; text-align: right;">
                <span class="terminal-line">> DATA STREAM: ENCRYPTED. CONNECTED TO THE ORACLE.</span>
            </div>
        </div>
    </div>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
