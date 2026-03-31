from flask import Flask, render_template_string
import os

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ORBITAL COMMAND // NUVOLA SYS</title>
    <style>
        :root {
            --bg: #020205;
            --neon-cyan: #00f3ff;
            --neon-pink: #ff003c;
            --neon-green: #39ff14;
            --neon-yellow: #fcee0a;
            --panel-bg: rgba(0, 243, 255, 0.03);
            --grid-color: rgba(0, 243, 255, 0.1);
        }

        * {
            box-sizing: border-box;
            font-family: 'Courier New', Courier, monospace;
        }

        body {
            background-color: var(--bg);
            color: var(--neon-cyan);
            margin: 0;
            padding: 20px;
            overflow-x: hidden;
            background-image: 
                linear-gradient(var(--grid-color) 1px, transparent 1px),
                linear-gradient(90deg, var(--grid-color) 1px, transparent 1px);
            background-size: 30px 30px;
            background-position: center center;
            animation: bg-pan 20s linear infinite;
        }

        @keyframes bg-pan {
            0% { background-position: 0 0; }
            100% { background-position: 30px 30px; }
        }

        h1, h2, h3 {
            text-transform: uppercase;
            letter-spacing: 3px;
            margin: 0 0 15px 0;
        }

        .glitch {
            position: relative;
            color: var(--neon-cyan);
            text-shadow: 0 0 5px var(--neon-cyan), 0 0 10px var(--neon-cyan);
            font-size: 2.5em;
            text-align: center;
            margin-bottom: 30px;
            border-bottom: 2px solid var(--neon-cyan);
            padding-bottom: 15px;
            animation: glitch-anim 2s infinite linear alternate-reverse;
        }

        @keyframes glitch-anim {
            0% { text-shadow: 2px 0 var(--neon-pink), -2px 0 var(--neon-yellow); }
            50% { text-shadow: -2px 0 var(--neon-pink), 2px 0 var(--neon-yellow); }
            100% { text-shadow: 2px 0 var(--neon-cyan), -2px 0 var(--neon-cyan); }
        }

        .dashboard-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 25px;
            max-width: 1600px;
            margin: 0 auto;
        }

        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-cyan);
            box-shadow: inset 0 0 20px rgba(0, 243, 255, 0.1), 0 0 15px rgba(0, 243, 255, 0.2);
            padding: 20px;
            position: relative;
            backdrop-filter: blur(2px);
        }

        .panel::after {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; height: 2px;
            background: var(--neon-cyan);
            box-shadow: 0 0 10px var(--neon-cyan);
            animation: scanline 4s linear infinite;
            opacity: 0.5;
        }

        @keyframes scanline {
            0% { top: 0; }
            100% { top: 100%; }
        }

        .status { font-weight: bold; }
        .status.online { color: var(--neon-green); text-shadow: 0 0 10px var(--neon-green); }
        .status.warning { color: var(--neon-yellow); text-shadow: 0 0 10px var(--neon-yellow); animation: blink 1s infinite; }
        .status.danger { color: var(--neon-pink); text-shadow: 0 0 10px var(--neon-pink); animation: blink 0.5s infinite; }

        @keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }

        table { width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 0.9em; }
        th, td { border: 1px solid rgba(0,243,255,0.2); padding: 12px; text-align: left; }
        th { background: rgba(0,243,255,0.1); color: var(--neon-cyan); }
        tr:hover { background: rgba(0,243,255,0.15); }

        .trinity-list { list-style: none; padding: 0; margin: 0; }
        .trinity-list li {
            padding: 15px;
            margin-bottom: 10px;
            border-left: 3px solid var(--neon-pink);
            background: rgba(255,0,60,0.05);
            position: relative;
        }
        .trinity-list li::before {
            content: '>';
            position: absolute;
            left: -15px;
            color: var(--neon-pink);
            text-shadow: 0 0 5px var(--neon-pink);
        }
        
        .trinity-name { color: var(--neon-pink); font-weight: bold; font-size: 1.1em; text-shadow: 0 0 5px var(--neon-pink); }
        .trinity-desc { color: #888; font-size: 0.85em; display: block; margin-top: 5px; }

        .metric-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
        }

        .metric-card {
            border: 1px solid var(--neon-yellow);
            padding: 15px;
            text-align: center;
            background: rgba(252, 238, 10, 0.05);
            box-shadow: inset 0 0 10px rgba(252, 238, 10, 0.1);
        }
        
        .metric-card.danger {
            border-color: var(--neon-pink);
            background: rgba(255, 0, 60, 0.05);
            box-shadow: inset 0 0 10px rgba(255, 0, 60, 0.1);
        }

        .m-val { font-size: 1.8em; font-weight: bold; text-shadow: 0 0 8px currentColor; margin: 10px 0; }
        .m-label { font-size: 0.7em; color: #888; letter-spacing: 2px; }

        .header-stats {
            display: flex;
            justify-content: center;
            gap: 30px;
            margin-bottom: 40px;
            font-size: 1.1em;
            background: rgba(0,0,0,0.5);
            padding: 15px;
            border-radius: 5px;
            border: 1px solid rgba(0,243,255,0.3);
        }

    </style>
</head>
<body>

    <h1 class="glitch">🛰️ ORBITAL COMMAND // NUVOLA</h1>
    
    <div class="header-stats">
        <span>SYS.CORE: <span class="status online">ONLINE</span></span>
        <span>DEFCON: <span class="status danger">2</span></span>
        <span>UPTIME: <span id="uptime" class="status online">00:00:00</span></span>
        <span>NETWORK: <span class="status warning">SECURE</span></span>
        <span>⚙️ PROTOCOLLO TRINITY: <span class="status online">Online (DCA, Funding, MEV)</span></span>
    </div>

    <div class="dashboard-grid">
        
        <!-- SQUADRE D'ASSALTO -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <table>
                <tr>
                    <th>UNITÀ</th>
                    <th>PROFILO</th>
                    <th>ZONA</th>
                    <th>STATO</th>
                </tr>
                <tr>
                    <td>🐺 SQUADRA_ALPHA</td>
                    <td>Scalper</td>
                    <td>Binance</td>
                    <td><span class="status warning">ENGAGED</span></td>
                </tr>
                <tr>
                    <td>🦅 SQUADRA_DELTA</td>
                    <td>Order Flow</td>
                    <td>Cross-CEX</td>
                    <td><span class="status online">STANDBY</span></td>
                </tr>
                <tr>
                    <td>🦂 SQUADRA_GAMMA</td>
                    <td>Pairs Trading</td>
                    <td>Bitget</td>
                    <td><span class="status danger">ARBITRAGE</span></td>
                </tr>
            </table>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2>🛡️ PROTOCOLLO TRINITY</h2>
            <ul class="trinity-list">
                <li>
                    <span class="trinity-name">🕴️ LO STROZZINO</span> 
                    <span class="status online" style="float:right;">[ATTIVO]</span>
                    <span class="trinity-desc">Funding Arb Engine | Yield stimato: 14.8% APY</span>
                </li>
                <li>
                    <span class="trinity-name">🧮 IL CONTABILE</span> 
                    <span class="status online" style="float:right;">[ATTIVO]</span>
                    <span class="trinity-desc">DCA Accumulator | Prossimo acquisto: 03h 14m</span>
                </li>
                <li>
                    <span class="trinity-name">👼 L'ANGELO CUSTODE</span> 
                    <span class="status warning" style="float:right;">[SCANNING]</span>
                    <span class="trinity-desc">MEV Arbitrum | Monitoraggio Mempool in corso...</span>
                </li>
            </ul>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel" style="grid-column: 1 / -1;">
            <h2>📊 METRICHE DI MERCATO // GLOBAL INTEL</h2>
            <div class="metric-grid">
                <div class="metric-card" style="color: var(--neon-yellow);">
                    <div class="m-label">THE ORACLE // BINANCE SENTIMENT</div>
                    <div class="m-val" id="oracle-val">GREED (78)</div>
                </div>
                <div class="metric-card danger" style="color: var(--neon-pink);">
                    <div class="m-label">WHALE TRACKER // 24H FLOW</div>
                    <div class="m-val">+ $842M IN</div>
                </div>
                <div class="metric-card" style="color: var(--neon-cyan); border-color: var(--neon-cyan);">
                    <div class="m-label">BTC DOMINANCE</div>
                    <div class="m-val" id="btc-dom">54.12%</div>
                </div>
                <div class="metric-card danger" style="color: var(--neon-pink);">
                    <div class="m-label">LIQUIDATION HEATMAP</div>
                    <div class="m-val">HEAVY @ $69.4K</div>
                </div>
            </div>
        </div>

    </div>

    <script>
        let sec = 0;
        setInterval(() => {
            sec++;
            let h = Math.floor(sec / 3600).toString().padStart(2, '0');
            let m = Math.floor((sec % 3600) / 60).toString().padStart(2, '0');
            let s = (sec % 60).toString().padStart(2, '0');
            document.getElementById('uptime').innerText = `${h}:${m}:${s}`;
            
            if(Math.random() > 0.7) {
                let dom = (54.10 + (Math.random() * 0.1 - 0.05)).toFixed(2);
                document.getElementById('btc-dom').innerText = `${dom}%`;
            }
            if(Math.random() > 0.8) {
                let sentiment = Math.floor(75 + Math.random() * 10);
                document.getElementById('oracle-val').innerText = `GREED (${sentiment})`;
            }
        }, 1000);
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
