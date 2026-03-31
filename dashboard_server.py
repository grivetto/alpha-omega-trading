from flask import Flask, render_template_string
import os

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
            --bg: #050505;
            --neon-green: #0f0;
            --neon-cyan: #0ff;
            --neon-magenta: #f0f;
            --neon-red: #f00;
            --panel-bg: rgba(10, 20, 10, 0.8);
            --border-color: rgba(0, 255, 0, 0.3);
        }
        body {
            background-color: var(--bg);
            color: var(--neon-green);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            overflow-x: hidden;
        }
        h1, h2, h3 {
            text-transform: uppercase;
            letter-spacing: 2px;
            margin-top: 0;
        }
        .glow-text {
            text-shadow: 0 0 5px var(--neon-green), 0 0 10px var(--neon-green);
        }
        .glow-cyan {
            color: var(--neon-cyan);
            text-shadow: 0 0 5px var(--neon-cyan), 0 0 10px var(--neon-cyan);
        }
        .glow-magenta {
            color: var(--neon-magenta);
            text-shadow: 0 0 5px var(--neon-magenta), 0 0 10px var(--neon-magenta);
        }
        .glow-red {
            color: var(--neon-red);
            text-shadow: 0 0 5px var(--neon-red), 0 0 10px var(--neon-red);
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
            border: 1px solid var(--border-color);
            border-radius: 5px;
            padding: 15px;
            box-shadow: inset 0 0 10px rgba(0,255,0,0.1), 0 0 15px rgba(0,255,0,0.2);
            position: relative;
            overflow: hidden;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: -100%;
            width: 50%; height: 2px;
            background: var(--neon-green);
            animation: scanline 3s linear infinite;
        }
        @keyframes scanline {
            0% { left: -100%; }
            100% { left: 200%; }
        }
        .status-dot {
            display: inline-block;
            width: 10px; height: 10px;
            background-color: var(--neon-green);
            border-radius: 50%;
            margin-right: 10px;
            box-shadow: 0 0 8px var(--neon-green);
            animation: blink 1.5s infinite;
        }
        .status-dot.red { background-color: var(--neon-red); box-shadow: 0 0 8px var(--neon-red); }
        .status-dot.cyan { background-color: var(--neon-cyan); box-shadow: 0 0 8px var(--neon-cyan); }
        .status-dot.magenta { background-color: var(--neon-magenta); box-shadow: 0 0 8px var(--neon-magenta); }
        @keyframes blink {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.3; }
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
            font-size: 0.9em;
        }
        th, td {
            border-bottom: 1px solid rgba(0, 255, 0, 0.2);
            padding: 8px;
            text-align: left;
        }
        th {
            color: var(--neon-cyan);
        }
        .header {
            text-align: center;
            margin-bottom: 30px;
            border-bottom: 2px solid var(--neon-green);
            padding-bottom: 10px;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1 class="glow-text">🚀 NUVOLA ORBITAL COMMAND 🚀</h1>
        <p class="glow-cyan">SYSTEM_STATUS: <span class="status-dot"></span>ONLINE | SECURE_UPLINK_ESTABLISHED</p>
        <p class="glow-magenta" style="font-weight: bold; border: 1px solid var(--neon-magenta); padding: 5px; display: inline-block; box-shadow: 0 0 10px var(--neon-magenta);">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</p>
    </div>

    <div class="container">
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <h2 class="glow-red">⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <table>
                <tr>
                    <th>UNIT</th>
                    <th>TARGET/STRAT</th>
                    <th>STATUS</th>
                </tr>
                <tr>
                    <td><span class="glow-red">ALPHA</span></td>
                    <td>Binance Scalper</td>
                    <td><span class="status-dot red"></span>ENGAGED</td>
                </tr>
                <tr>
                    <td><span class="glow-red">DELTA</span></td>
                    <td>Order Flow</td>
                    <td><span class="status-dot red"></span>ENGAGED</td>
                </tr>
                <tr>
                    <td><span class="glow-red">GAMMA</span></td>
                    <td>Bitget Pairs</td>
                    <td><span class="status-dot red" style="animation-duration: 2s;"></span>STANDBY</td>
                </tr>
            </table>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2 class="glow-magenta">🔮 PROTOCOLLO TRINITY</h2>
            <p>> BACKGROUND_DAEMONS_ACTIVE: 3/3</p>
            <ul>
                <li><span class="status-dot magenta"></span> <b>Lo Strozzino:</b> Funding Arb [SYS_NOMINAL]</li>
                <li><span class="status-dot magenta"></span> <b>Il Contabile:</b> DCA Accumulation [SYNCED]</li>
                <li><span class="status-dot magenta"></span> <b>L'Angelo Custode:</b> MEV Arbitrum [HUNTING]</li>
            </ul>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <h2 class="glow-cyan">📡 METRICHE DI MERCATO</h2>
            <p>> AWAITING_ORACLE_TELEMETRY...</p>
            <table>
                <tr>
                    <th>SENSOR</th>
                    <th>READING</th>
                    <th>CONFIDENCE</th>
                </tr>
                <tr>
                    <td>The Oracle (Binance Sentiment)</td>
                    <td>BULLISH_BIAS (0.78)</td>
                    <td>89%</td>
                </tr>
                <tr>
                    <td>Whale Tracker</td>
                    <td>LARGE_INFLOW_DETECTED</td>
                    <td>94%</td>
                </tr>
            </table>
        </div>
        
        <!-- SYSTEM LOGS -->
        <div class="panel">
            <h2 class="glow-green">🖥️ TERMINAL_LOGS</h2>
            <div style="font-size: 0.8em; opacity: 0.8;">
                <p>> [SYS] Initiating Orbital Command refactoring...</p>
                <p>> [SYS] Cyberpunk UI injected successfully.</p>
                <p>> [ALPHA] Executing limit order @ 63,450...</p>
                <p>> [ANGELO] Front-run opportunity detected. Yield: 0.05 ETH.</p>
                <p>> [STROZZINO] Rebalancing perp exposure...</p>
                <p class="glow-green">> [SYS] Awaiting next directive.</p>
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
    # Try port 8080 if 5000 is used
    try:
        app.run(host='0.0.0.0', port=5000)
    except OSError:
        app.run(host='0.0.0.0', port=8080)
