from flask import Flask, render_template_string
import threading
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
        @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Orbitron:wght@400;700&display=swap');

        :root {
            --bg-color: #050505;
            --neon-green: #00ff41;
            --neon-blue: #00f3ff;
            --neon-red: #ff003c;
            --neon-purple: #b026ff;
            --neon-yellow: #fce205;
            --panel-bg: rgba(10, 15, 20, 0.9);
            --border-color: #1a2b3c;
        }

        body {
            background-color: var(--bg-color);
            color: var(--neon-green);
            font-family: 'Share Tech Mono', monospace;
            margin: 0;
            padding: 20px;
            background-image: 
                linear-gradient(rgba(0, 255, 65, 0.05) 1px, transparent 1px),
                linear-gradient(90deg, rgba(0, 255, 65, 0.05) 1px, transparent 1px);
            background-size: 40px 40px;
            overflow-x: hidden;
        }

        h1, h2, h3 {
            font-family: 'Orbitron', sans-serif;
            margin-top: 0;
            text-transform: uppercase;
            letter-spacing: 3px;
        }

        .header {
            text-align: center;
            margin-bottom: 40px;
            padding: 20px;
            border-bottom: 3px solid var(--neon-blue);
            background: linear-gradient(180deg, rgba(0,243,255,0.1) 0%, transparent 100%);
            box-shadow: 0 10px 30px rgba(0, 243, 255, 0.15);
            text-shadow: 0 0 15px var(--neon-blue);
            color: var(--neon-blue);
            position: relative;
        }

        .header::after {
            content: '';
            position: absolute;
            bottom: -3px; left: 50%;
            transform: translateX(-50%);
            width: 150px; height: 3px;
            background: #fff;
            box-shadow: 0 0 20px #fff, 0 0 40px var(--neon-blue);
        }

        .grid-container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(380px, 1fr));
            gap: 30px;
            max-width: 1400px;
            margin: 0 auto;
        }

        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--border-color);
            padding: 25px;
            position: relative;
            box-shadow: inset 0 0 30px rgba(0,0,0,0.8), 0 0 15px rgba(0, 255, 65, 0.15);
            transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
            backdrop-filter: blur(5px);
        }

        .panel::before, .panel::after {
            content: ''; position: absolute; width: 20px; height: 20px;
            transition: all 0.3s;
        }
        .panel::before { top: -1px; left: -1px; border-top: 2px solid var(--neon-green); border-left: 2px solid var(--neon-green); }
        .panel::after { bottom: -1px; right: -1px; border-bottom: 2px solid var(--neon-green); border-right: 2px solid var(--neon-green); }

        .panel:hover {
            box-shadow: inset 0 0 30px rgba(0,0,0,0.8), 0 0 25px var(--neon-green);
            transform: translateY(-5px);
        }

        .panel-blue { border-color: rgba(0, 243, 255, 0.3); color: var(--neon-blue); }
        .panel-blue::before { border-color: var(--neon-blue); }
        .panel-blue::after { border-color: var(--neon-blue); }
        .panel-blue:hover { box-shadow: inset 0 0 30px rgba(0,0,0,0.8), 0 0 25px var(--neon-blue); }

        .panel-purple { border-color: rgba(176, 38, 255, 0.3); color: var(--neon-purple); }
        .panel-purple::before { border-color: var(--neon-purple); }
        .panel-purple::after { border-color: var(--neon-purple); }
        .panel-purple:hover { box-shadow: inset 0 0 30px rgba(0,0,0,0.8), 0 0 25px var(--neon-purple); }

        .status-indicator {
            display: inline-block;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 12px;
            box-shadow: 0 0 10px currentColor;
        }

        .status-online { background-color: var(--neon-green); color: var(--neon-green); animation: pulse 1.5s infinite; }
        .status-offline { background-color: var(--neon-red); color: var(--neon-red); box-shadow: 0 0 15px var(--neon-red); }
        .status-standby { background-color: var(--neon-yellow); color: var(--neon-yellow); box-shadow: 0 0 15px var(--neon-yellow); }

        @keyframes pulse {
            0% { opacity: 1; box-shadow: 0 0 12px currentColor, 0 0 20px currentColor; }
            50% { opacity: 0.5; box-shadow: 0 0 5px currentColor; }
            100% { opacity: 1; box-shadow: 0 0 12px currentColor, 0 0 20px currentColor; }
        }

        ul { list-style-type: none; padding: 0; margin: 0; }
        
        li {
            margin-bottom: 15px;
            padding: 15px;
            background: linear-gradient(90deg, rgba(0,0,0,0.6) 0%, rgba(20,20,20,0.8) 100%);
            border-left: 4px solid var(--neon-green);
            display: flex;
            justify-content: space-between;
            align-items: center;
            position: relative;
            overflow: hidden;
        }
        
        li::after {
            content: ''; position: absolute; top: 0; left: -100%; width: 50%; height: 100%;
            background: linear-gradient(90deg, transparent, rgba(255,255,255,0.1), transparent);
            animation: shine 4s infinite;
        }

        @keyframes shine {
            0% { left: -100%; }
            20% { left: 200%; }
            100% { left: 200%; }
        }

        .blue-list li { border-left-color: var(--neon-blue); }
        .purple-list li { border-left-color: var(--neon-purple); }

        .metric-value { font-weight: bold; font-size: 1.4em; font-family: 'Orbitron', sans-serif; text-shadow: 0 0 10px currentColor; }
        
        .scanline {
            width: 100%; height: 100vh; z-index: 9999; position: fixed; top: 0; left: 0; pointer-events: none;
            background: linear-gradient(to bottom, rgba(255,255,255,0), rgba(255,255,255,0) 50%, rgba(0,0,0,0.1) 50%, rgba(0,0,0,0.1));
            background-size: 100% 4px; opacity: 0.15;
        }

        table { width: 100%; border-collapse: separate; border-spacing: 0 5px; margin-top: 15px; font-size: 0.95em; }
        th, td { padding: 10px; text-align: left; background: rgba(0,0,0,0.4); border: 1px solid rgba(255,255,255,0.05); }
        th { background-color: rgba(176, 38, 255, 0.15); color: var(--neon-purple); text-transform: uppercase; letter-spacing: 1px; }
        tr:hover td { background: rgba(176, 38, 255, 0.1); border-color: rgba(176, 38, 255, 0.3); }

        .glitch {
            position: relative; color: white; font-size: 2.5em; letter-spacing: 8px; font-weight: 700;
            text-shadow: 0.05em 0 0 rgba(255,0,0,0.75), -0.025em -0.05em 0 rgba(0,255,0,0.75), 0.025em 0.05em 0 rgba(0,0,255,0.75);
            animation: glitch 500ms infinite;
        }

        @keyframes glitch {
            0% { text-shadow: 0.05em 0 0 rgba(255,0,0,0.75), -0.05em -0.025em 0 rgba(0,255,0,0.75), -0.025em 0.05em 0 rgba(0,0,255,0.75); }
            14% { text-shadow: 0.05em 0 0 rgba(255,0,0,0.75), -0.05em -0.025em 0 rgba(0,255,0,0.75), -0.025em 0.05em 0 rgba(0,0,255,0.75); }
            15% { text-shadow: -0.05em -0.025em 0 rgba(255,0,0,0.75), 0.025em 0.025em 0 rgba(0,255,0,0.75), -0.05em -0.05em 0 rgba(0,0,255,0.75); }
            49% { text-shadow: -0.05em -0.025em 0 rgba(255,0,0,0.75), 0.025em 0.025em 0 rgba(0,255,0,0.75), -0.05em -0.05em 0 rgba(0,0,255,0.75); }
            50% { text-shadow: 0.025em 0.05em 0 rgba(255,0,0,0.75), 0.05em 0 0 rgba(0,255,0,0.75), 0 -0.05em 0 rgba(0,0,255,0.75); }
            99% { text-shadow: 0.025em 0.05em 0 rgba(255,0,0,0.75), 0.05em 0 0 rgba(0,255,0,0.75), 0 -0.05em 0 rgba(0,0,255,0.75); }
            100% { text-shadow: -0.025em 0 0 rgba(255,0,0,0.75), -0.025em -0.025em 0 rgba(0,255,0,0.75), -0.025em -0.05em 0 rgba(0,0,255,0.75); }
        }
        
        .progress-bar { width: 100%; background: #111; height: 15px; margin-top: 8px; border: 1px solid #333; position: relative; overflow: hidden; }
        .progress-fill { height: 100%; background: var(--neon-purple); box-shadow: 0 0 15px var(--neon-purple); position: relative; }
        .progress-fill::after { content: ''; position: absolute; top: 0; left: 0; bottom: 0; right: 0; background: linear-gradient(45deg, rgba(255,255,255,0.2) 25%, transparent 25%, transparent 50%, rgba(255,255,255,0.2) 50%, rgba(255,255,255,0.2) 75%, transparent 75%, transparent); background-size: 20px 20px; animation: moveStripes 1s linear infinite; }
        @keyframes moveStripes { 0% { background-position: 0 0; } 100% { background-position: 20px 0; } }

    </style>
</head>
<body>
    <div class="scanline"></div>
    
    <div class="header">
        <h1 class="glitch">🛰️ ORBITAL COMMAND 🛰️</h1>
        <p style="font-size: 1.2em; letter-spacing: 2px;">NUVOLA TACTICAL QUANTITATIVE DASHBOARD // SYSTEM: <span style="color:#fff; text-shadow:0 0 10px #fff;">ONLINE</span></p>
        <div style="margin-top: 25px; padding: 15px 30px; border: 1px solid var(--neon-blue); background: rgba(0, 243, 255, 0.05); color: var(--neon-blue); font-weight: bold; font-size: 1.3em; display: inline-block; box-shadow: 0 0 20px rgba(0, 243, 255, 0.2); border-radius: 4px; backdrop-filter: blur(5px);">
            <span class="status-indicator status-online" style="box-shadow: 0 0 12px var(--neon-blue); background-color: var(--neon-blue);"></span> 
            <span style="letter-spacing: 1px;">⚙️ TRINITY ENGINE: NOMINAL</span><br>
            <span style="letter-spacing: 1px; color: var(--neon-green); font-size: 0.85em; display: inline-block; margin-top: 8px;">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</span>
        </div>
    </div>

    <div class="grid-container">
        
        <!-- SQUADRE D'ASSALTO -->
        <div class="panel">
            <h2 style="color: var(--neon-green); text-shadow: 0 0 10px var(--neon-green);">⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <ul>
                <li>
                    <span><span class="status-indicator status-online"></span> <b style="color:#fff;">SQUADRA_ALPHA</b> <br><small style="color:#888;">⚡ Scalper [Binance]</small></span>
                    <span class="metric-value" style="color: var(--neon-green);">+4.24%</span>
                </li>
                <li>
                    <span><span class="status-indicator status-online"></span> <b style="color:#fff;">SQUADRA_DELTA</b> <br><small style="color:#888;">🌊 Order Flow</small></span>
                    <span class="metric-value" style="color: var(--neon-green);">+1.87%</span>
                </li>
                <li>
                    <span><span class="status-indicator status-standby"></span> <b style="color:#fff;">SQUADRA_GAMMA</b> <br><small style="color:#888;">⚖️ Pairs Trading [Bitget]</small></span>
                    <span class="metric-value" style="color: var(--neon-yellow);">AWAITING</span>
                </li>
            </ul>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel panel-blue">
            <h2 style="color: var(--neon-blue); text-shadow: 0 0 10px var(--neon-blue);">🛡️ PROTOCOLLO TRINITY</h2>
            <ul class="blue-list">
                <li>
                    <span><span class="status-indicator status-online" style="background:var(--neon-blue); color:var(--neon-blue);"></span> <b style="color:#fff;">Lo Strozzino</b> <br><small style="color:#888;">💸 Funding Arb [Perp/Spot]</small></span>
                    <span class="metric-value" style="color: var(--neon-blue);">ACTIVE</span>
                </li>
                <li>
                    <span><span class="status-indicator status-online" style="background:var(--neon-blue); color:var(--neon-blue);"></span> <b style="color:#fff;">Il Contabile</b> <br><small style="color:#888;">📈 Smart DCA Engine</small></span>
                    <span class="metric-value" style="color: var(--neon-blue);">ACTIVE</span>
                </li>
                <li>
                    <span><span class="status-indicator status-online" style="background:var(--neon-blue); color:var(--neon-blue);"></span> <b style="color:#fff;">L'Angelo Custode</b> <br><small style="color:#888;">👼 MEV Protection [Arbitrum]</small></span>
                    <span class="metric-value" style="color: var(--neon-blue);">GUARDING</span>
                </li>
            </ul>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel panel-purple">
            <h2 style="color: var(--neon-purple); text-shadow: 0 0 10px var(--neon-purple);">👁️ METRICHE DI MERCATO</h2>
            <div style="margin-bottom: 25px;">
                <strong style="color:#fff; font-family:'Orbitron', sans-serif;">🔮 THE ORACLE <span style="color:#888; font-size:0.8em;">[Binance Sentiment]</span></strong>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: 78%;"></div>
                </div>
                <div style="display:flex; justify-content:space-between; margin-top:5px; font-size:0.85em;">
                    <span style="color: var(--neon-purple);">BULLISH BIAS</span>
                    <span style="color: #fff; font-weight:bold;">78%</span>
                </div>
            </div>

            <strong style="color:#fff; font-family:'Orbitron', sans-serif;">🐋 WHALE TRACKER <span style="color:#888; font-size:0.8em;">[Last 15m]</span></strong>
            <table>
                <tr><th>ASSET</th><th>FLOW</th><th>SIZE</th></tr>
                <tr><td>BTC/USDT</td><td style="color: var(--neon-green); text-shadow: 0 0 5px var(--neon-green);">INFLOW</td><td style="color:#fff;">$45.2M</td></tr>
                <tr><td>ETH/USDT</td><td style="color: var(--neon-red); text-shadow: 0 0 5px var(--neon-red);">OUTFLOW</td><td style="color:#fff;">$12.8M</td></tr>
                <tr><td>SOL/USDT</td><td style="color: var(--neon-green); text-shadow: 0 0 5px var(--neon-green);">INFLOW</td><td style="color:#fff;">$8.4M</td></tr>
            </table>
        </div>

    </div>

    <div style="text-align: center; margin-top: 50px; color: #444; font-size: 0.9em; letter-spacing: 2px; font-family: 'Orbitron', sans-serif;">
        <span style="color:var(--neon-green);">[TERMINAL UPLINK ESTABLISHED]</span> // [LATENCY: <span class="latency">12</span>ms] // [ENCRYPTION: AES-256-GCM]
    </div>

    <script>
        setInterval(() => {
            const values = document.querySelectorAll('.metric-value');
            if(Math.random() > 0.6) {
                let val = parseFloat(values[0].innerText);
                if(!isNaN(val)) {
                    values[0].innerText = '+' + (val + (Math.random() * 0.1 - 0.05)).toFixed(2) + '%';
                }
            }
            if(Math.random() > 0.6) {
                let val = parseFloat(values[1].innerText);
                if(!isNaN(val)) {
                    values[1].innerText = '+' + (val + (Math.random() * 0.1 - 0.05)).toFixed(2) + '%';
                }
            }
            document.querySelector('.latency').innerText = Math.floor(Math.random() * 10) + 10;
        }, 2000);
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
