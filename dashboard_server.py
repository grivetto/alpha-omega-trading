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
        @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');
        
        :root {
            --bg: #050505;
            --neon-cyan: #0ff;
            --neon-magenta: #f0f;
            --neon-green: #39ff14;
            --neon-red: #ff073a;
            --panel-bg: rgba(10, 20, 30, 0.8);
        }
        
        body {
            background-color: var(--bg);
            color: var(--neon-cyan);
            font-family: 'Share Tech Mono', monospace;
            margin: 0;
            padding: 20px;
            background-image: 
                linear-gradient(rgba(0, 255, 255, 0.05) 1px, transparent 1px),
                linear-gradient(90deg, rgba(0, 255, 255, 0.05) 1px, transparent 1px);
            background-size: 20px 20px;
            overflow-x: hidden;
        }

        h1, h2 {
            text-align: center;
            text-shadow: 0 0 10px var(--neon-cyan), 0 0 20px var(--neon-cyan);
            text-transform: uppercase;
            letter-spacing: 2px;
        }

        .container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            max-width: 1400px;
            margin: 0 auto;
        }

        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-cyan);
            border-radius: 5px;
            padding: 20px;
            box-shadow: 0 0 15px rgba(0, 255, 255, 0.2);
            position: relative;
            overflow: hidden;
        }
        
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; height: 2px;
            background: var(--neon-cyan);
            box-shadow: 0 0 10px var(--neon-cyan);
        }

        .panel.magenta { border-color: var(--neon-magenta); box-shadow: 0 0 15px rgba(255, 0, 255, 0.2); color: #fff;}
        .panel.magenta::before { background: var(--neon-magenta); box-shadow: 0 0 10px var(--neon-magenta); }
        
        .panel.green { border-color: var(--neon-green); box-shadow: 0 0 15px rgba(57, 255, 20, 0.2); color: #fff;}
        .panel.green::before { background: var(--neon-green); box-shadow: 0 0 10px var(--neon-green); }

        .status-indicator {
            display: inline-block;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background-color: var(--neon-green);
            box-shadow: 0 0 10px var(--neon-green);
            animation: pulse 1.5s infinite;
        }
        
        .status-warning { background-color: #ffb400; box-shadow: 0 0 10px #ffb400; }
        .status-danger { background-color: var(--neon-red); box-shadow: 0 0 10px var(--neon-red); }

        @keyframes pulse {
            0% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.5; transform: scale(1.2); }
            100% { opacity: 1; transform: scale(1); }
        }

        .scanline {
            width: 100%;
            height: 100px;
            background: linear-gradient(0deg, rgba(0,0,0,0) 0%, rgba(0,255,255,0.2) 50%, rgba(0,0,0,0) 100%);
            opacity: 0.1;
            position: absolute;
            bottom: 100%;
            animation: scanline 8s linear infinite;
            pointer-events: none;
            z-index: 10;
        }

        @keyframes scanline {
            0% { bottom: 100%; }
            100% { bottom: -100px; }
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
        }
        
        th, td {
            padding: 8px;
            text-align: left;
            border-bottom: 1px solid rgba(0, 255, 255, 0.2);
        }
        
        .glitch {
            animation: glitch 2s linear infinite;
        }

        @keyframes glitch {
            2%, 64% { transform: translate(2px,0) skew(0deg); }
            4%, 60% { transform: translate(-2px,0) skew(0deg); }
            62% { transform: translate(0,0) skew(5deg); }
        }
        
        .value-up { color: var(--neon-green); text-shadow: 0 0 5px var(--neon-green); }
        .value-down { color: var(--neon-red); text-shadow: 0 0 5px var(--neon-red); }
    </style>
</head>
<body>
    <div class="scanline"></div>
    <h1 class="glitch">🛰️ NUVOLA ORBITAL COMMAND 🛰️</h1>
    <h2>/// TACTICAL QUANTITATIVE DASHBOARD ///</h2>
    <div style="text-align: center; margin-bottom: 20px; color: var(--neon-magenta); font-weight: bold; font-size: 1.2em; text-shadow: 0 0 5px var(--neon-magenta);">
        ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
    </div>
    
    <div class="container">
        <!-- SQUADRE D'ASSALTO -->
        <div class="panel">
            <h3>⚔️ SQUADRE D'ASSALTO (HFT)</h3>
            <table>
                <tr>
                    <td><span class="status-indicator"></span> 🔴 <b>SQUADRA_ALPHA</b></td>
                    <td>Binance Scalper</td>
                    <td class="value-up">ACTIVE</td>
                </tr>
                <tr>
                    <td><span class="status-indicator"></span> 🔵 <b>SQUADRA_DELTA</b></td>
                    <td>Order Flow</td>
                    <td class="value-up">SYNCED</td>
                </tr>
                <tr>
                    <td><span class="status-indicator status-warning"></span> 🟢 <b>SQUADRA_GAMMA</b></td>
                    <td>Bitget Pairs</td>
                    <td style="color: #ffb400;">AWAITING</td>
                </tr>
            </table>
            <p style="font-size: 0.8em; margin-top: 15px; color: #888;">> Latency: 12ms | Executions/sec: 43.2</p>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel magenta">
            <h3>🔺 PROTOCOLLO TRINITY</h3>
            <table>
                <tr>
                    <td><span class="status-indicator"></span> 🧛 <b>Lo Strozzino</b></td>
                    <td>Funding Arb</td>
                    <td>Yield: <span class="value-up">+14.2%</span></td>
                </tr>
                <tr>
                    <td><span class="status-indicator"></span> 🧮 <b>Il Contabile</b></td>
                    <td>DCA Protocol</td>
                    <td>Accumulation: <span class="value-up">ON</span></td>
                </tr>
                <tr>
                    <td><span class="status-indicator"></span> 🛡️ <b>L'Angelo Custode</b></td>
                    <td>MEV Arbitrum</td>
                    <td>Guarding: <span class="value-up">SECURE</span></td>
                </tr>
            </table>
            <p style="font-size: 0.8em; margin-top: 15px; color: #ccc;">> Background daemons operational.</p>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel green">
            <h3>📊 METRICHE DI MERCATO</h3>
            <table>
                <tr>
                    <td>👁️ <b>The Oracle</b></td>
                    <td>Binance Sentiment</td>
                    <td class="value-down">BEARISH (42)</td>
                </tr>
                <tr>
                    <td>🐋 <b>Whale Tracker</b></td>
                    <td>Large Txs (>1M)</td>
                    <td class="value-up">DETECTED (3)</td>
                </tr>
                <tr>
                    <td>⚡ <b>Network Gas</b></td>
                    <td>ETH Base Fee</td>
                    <td>12 gwei</td>
                </tr>
            </table>
            <div style="margin-top: 15px; height: 40px; border: 1px solid var(--neon-green); padding: 5px; font-size: 0.7em; overflow: hidden; display: flex; align-items: center;">
                <marquee scrollamount="5" style="color: var(--neon-green);">
                    [SYS] Oracle feed updated... [WHALE] 12,000 ETH moved to Binance... [HFT] Alpha executed 450 trades in last 60s... [SYS] All systems nominal.
                </marquee>
            </div>
        </div>
    </div>
    
    <div style="text-align: center; margin-top: 40px; font-size: 0.8em; color: #555;">
        SERVER TIME: <span id="clock"></span> | CONNECTION: SECURE
    </div>
    
    <script>
        setInterval(() => {
            document.getElementById('clock').innerText = new Date().toISOString();
        }, 1000);
        document.getElementById('clock').innerText = new Date().toISOString();
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
