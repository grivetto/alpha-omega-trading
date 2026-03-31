from flask import Flask, render_template_string
import os

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NUVOLA // ORBITAL COMMAND</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');
        
        :root {
            --neon-green: #39ff14;
            --neon-blue: #00ffff;
            --neon-pink: #ff00ff;
            --bg-color: #030305;
            --panel-bg: rgba(5, 5, 10, 0.8);
            --border-glow: 0 0 10px rgba(57, 255, 20, 0.5);
        }
        
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            background-color: var(--bg-color);
            background-image: 
                radial-gradient(circle at 50% 50%, rgba(0, 255, 255, 0.05) 0%, transparent 60%),
                linear-gradient(rgba(0, 255, 0, 0.02) 1px, transparent 1px),
                linear-gradient(90deg, rgba(0, 255, 0, 0.02) 1px, transparent 1px);
            background-size: 100% 100%, 20px 20px, 20px 20px;
            color: var(--neon-green);
            font-family: 'Share Tech Mono', monospace;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
            padding: 2rem;
            overflow-x: hidden;
        }

        h1 {
            color: var(--neon-blue);
            text-shadow: 0 0 10px var(--neon-blue), 0 0 20px rgba(0, 255, 255, 0.5);
            text-transform: uppercase;
            letter-spacing: 5px;
            border-bottom: 2px solid var(--neon-blue);
            padding-bottom: 15px;
            margin-bottom: 40px;
            width: 100%;
            text-align: center;
            font-size: 2.5rem;
            position: relative;
        }

        h1::after {
            content: '';
            position: absolute;
            bottom: -2px;
            left: 0;
            width: 100%;
            height: 2px;
            background: var(--neon-blue);
            box-shadow: 0 0 15px var(--neon-blue);
        }

        .dashboard-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
            gap: 30px;
            width: 100%;
            max-width: 1400px;
        }

        .panel {
            background-color: var(--panel-bg);
            border: 1px solid var(--neon-green);
            box-shadow: var(--border-glow);
            padding: 25px;
            border-radius: 4px;
            position: relative;
            backdrop-filter: blur(5px);
            transition: all 0.3s ease;
        }

        .panel:hover {
            box-shadow: 0 0 20px rgba(57, 255, 20, 0.8);
            transform: translateY(-2px);
        }

        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; bottom: 0;
            border: 1px solid var(--neon-green);
            opacity: 0.2;
            pointer-events: none;
        }

        .panel h2 {
            font-size: 1.4rem;
            color: var(--neon-pink);
            text-shadow: 0 0 8px var(--neon-pink);
            border-bottom: 1px dashed var(--neon-pink);
            padding-bottom: 10px;
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        ul {
            list-style: none;
        }

        li {
            margin-bottom: 15px;
            padding: 10px;
            background: rgba(0, 255, 0, 0.05);
            border-left: 3px solid var(--neon-green);
            display: flex;
            flex-direction: column;
            gap: 5px;
        }

        .team-name {
            font-weight: bold;
            font-size: 1.1rem;
            letter-spacing: 1px;
            color: #fff;
            text-shadow: 0 0 5px #fff;
        }

        .status {
            color: var(--neon-green);
            font-size: 0.9rem;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .status::before {
            content: '▶';
            font-size: 0.8rem;
        }

        .metric-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px 0;
            border-bottom: 1px solid rgba(0, 255, 255, 0.2);
        }

        .metric-label {
            color: #ccc;
            font-size: 0.95rem;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .metric-value {
            color: var(--neon-blue);
            text-shadow: 0 0 5px var(--neon-blue);
            font-weight: bold;
            font-size: 1.1rem;
        }

        .metric-value.warning {
            color: #ffaa00;
            text-shadow: 0 0 5px #ffaa00;
        }

        .metric-value.danger {
            color: #ff0000;
            text-shadow: 0 0 5px #ff0000;
            animation: blink 1s infinite;
        }

        .pulse-dot {
            height: 8px;
            width: 8px;
            background-color: var(--neon-green);
            border-radius: 50%;
            display: inline-block;
            box-shadow: 0 0 8px var(--neon-green);
            animation: pulse 1.5s infinite;
        }

        @keyframes pulse {
            0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(57, 255, 20, 0.7); }
            70% { transform: scale(1); box-shadow: 0 0 0 6px rgba(57, 255, 20, 0); }
            100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(57, 255, 20, 0); }
        }

        @keyframes blink {
            0%, 100% { opacity: 1; }
            50% { opacity: 0; }
        }

        .scanline {
            position: fixed;
            top: 0;
            left: 0;
            width: 100vw;
            height: 100vh;
            background: linear-gradient(
                to bottom,
                rgba(255,255,255,0),
                rgba(255,255,255,0) 50%,
                rgba(0,0,0,0.1) 50%,
                rgba(0,0,0,0.1)
            );
            background-size: 100% 4px;
            pointer-events: none;
            z-index: 999;
            opacity: 0.3;
        }

        footer {
            margin-top: 50px;
            color: rgba(57, 255, 20, 0.5);
            font-size: 0.8rem;
            letter-spacing: 2px;
            text-align: center;
        }
    </style>
</head>
<body>
    <div class="scanline"></div>
    
    <h1><span class="pulse-dot" style="margin-right: 15px; width: 15px; height: 15px;"></span> ORBITAL COMMAND // NUVOLA</h1>
    
    <div style="width: 100%; max-width: 1400px; margin-bottom: 20px; padding: 15px; background: rgba(57, 255, 20, 0.1); border: 1px solid var(--neon-green); text-align: center; font-size: 1.2rem; font-weight: bold; text-shadow: 0 0 5px var(--neon-green); border-radius: 4px; box-shadow: 0 0 10px rgba(57, 255, 20, 0.3);">
        ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
    </div>

    <div class="dashboard-grid">
        <!-- SEZIONE 1: SQUADRE D'ASSALTO -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <ul>
                <li>
                    <span class="team-name">[SQUADRA_ALPHA] - Scalper</span>
                    <span class="status">ONLINE | Target: Binance | Ops: 342/min</span>
                </li>
                <li>
                    <span class="team-name">[SQUADRA_DELTA] - Order Flow</span>
                    <span class="status">ONLINE | Scanning DOM... | Depth: 100</span>
                </li>
                <li>
                    <span class="team-name">[SQUADRA_GAMMA] - Pairs Trading</span>
                    <span class="status">ONLINE | Target: Bitget | Spread Arb: 0.12%</span>
                </li>
            </ul>
        </div>

        <!-- SEZIONE 2: PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2>🛡️ PROTOCOLLO TRINITY</h2>
            <ul>
                <li>
                    <span class="team-name">🕵️ Lo Strozzino</span>
                    <span class="status">BACKGROUND | Funding Arb | APR: 14.5%</span>
                </li>
                <li>
                    <span class="team-name">🧮 Il Contabile</span>
                    <span class="status">BACKGROUND | DCA Matrix | Next Buy: 4h 12m</span>
                </li>
                <li>
                    <span class="team-name">👼 L'Angelo Custode</span>
                    <span class="status">BACKGROUND | MEV Arbitrum | Guarding...</span>
                </li>
            </ul>
        </div>

        <!-- SEZIONE 3: METRICHE DI MERCATO -->
        <div class="panel">
            <h2>📊 METRICHE DI MERCATO</h2>
            <div class="metric-row">
                <span class="metric-label">👁️ The Oracle (Binance Sentiment)</span>
                <span class="metric-value">BULLISH 78%</span>
            </div>
            <div class="metric-row">
                <span class="metric-label">🐋 Whale Tracker (Large TXs)</span>
                <span class="metric-value warning">DETECTED: 1.2k BTC</span>
            </div>
            <div class="metric-row">
                <span class="metric-label">⚡ Volatility Index</span>
                <span class="metric-value danger">ELEVATED</span>
            </div>
            <div class="metric-row">
                <span class="metric-label">🌐 Network Latency</span>
                <span class="metric-value">12ms</span>
            </div>
            <div class="metric-row">
                <span class="metric-label">🔋 System Load</span>
                <span class="metric-value">42%</span>
            </div>
        </div>
    </div>
    
    <footer>
        [ SYSTEM ONLINE ] -- [ CONNECTION SECURE ] -- [ AWAITING DIRECTIVES ]
    </footer>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    # Bind to all interfaces, port 5000 (adjust if needed)
    app.run(host='0.0.0.0', port=5000, debug=False)
