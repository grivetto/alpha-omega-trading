import os
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
            --neon-blue: #0ff;
            --neon-pink: #f0f;
            --neon-red: #ff003c;
            --bg-color: #020202;
            --panel-bg: rgba(10, 10, 10, 0.85);
            --grid-color: rgba(0, 255, 255, 0.1);
        }
        body {
            background-color: var(--bg-color);
            background-image: 
                linear-gradient(var(--grid-color) 1px, transparent 1px),
                linear-gradient(90deg, var(--grid-color) 1px, transparent 1px);
            background-size: 30px 30px;
            color: var(--neon-green);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            overflow-x: hidden;
        }
        h1 {
            text-align: center;
            color: var(--neon-blue);
            text-shadow: 0 0 10px var(--neon-blue), 0 0 20px var(--neon-blue);
            text-transform: uppercase;
            letter-spacing: 5px;
            font-size: 2.5rem;
            margin-bottom: 40px;
            border-bottom: 2px solid var(--neon-blue);
            padding-bottom: 15px;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
            gap: 25px;
            margin-top: 20px;
            position: relative;
            z-index: 2;
        }
        .panel {
            background-color: var(--panel-bg);
            border: 1px solid var(--neon-green);
            padding: 25px;
            border-radius: 8px;
            box-shadow: 0 0 15px rgba(57, 255, 20, 0.2), inset 0 0 20px rgba(57, 255, 20, 0.05);
            backdrop-filter: blur(5px);
            position: relative;
            overflow: hidden;
            transition: all 0.3s ease;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; height: 2px;
            background: var(--neon-green);
            box-shadow: 0 0 10px var(--neon-green);
        }
        .panel.trinity { border-color: var(--neon-pink); }
        .panel.trinity::before { background: var(--neon-pink); box-shadow: 0 0 10px var(--neon-pink); }
        .panel.trinity h2 { color: var(--neon-pink); text-shadow: 0 0 10px var(--neon-pink); border-bottom-color: var(--neon-pink); }
        
        .panel.market { border-color: var(--neon-blue); }
        .panel.market::before { background: var(--neon-blue); box-shadow: 0 0 10px var(--neon-blue); }
        .panel.market h2 { color: var(--neon-blue); text-shadow: 0 0 10px var(--neon-blue); border-bottom-color: var(--neon-blue); }
        
        .panel:hover {
            transform: translateY(-5px);
            box-shadow: 0 0 25px rgba(57, 255, 20, 0.4);
        }
        .panel.trinity:hover { box-shadow: 0 0 25px rgba(255, 0, 255, 0.4); }
        .panel.market:hover { box-shadow: 0 0 25px rgba(0, 255, 255, 0.4); }

        .panel h2 {
            color: var(--neon-green);
            text-shadow: 0 0 10px var(--neon-green);
            border-bottom: 1px dashed rgba(255,255,255,0.3);
            padding-bottom: 15px;
            margin-top: 0;
            font-size: 1.4rem;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
            padding: 10px;
            background: rgba(255, 255, 255, 0.03);
            border-radius: 4px;
            border-left: 3px solid transparent;
            transition: background 0.2s;
        }
        .row:hover {
            background: rgba(255, 255, 255, 0.08);
        }
        .row.active { border-left-color: var(--neon-green); }
        .row.standby { border-left-color: #ffaa00; }
        .row.warning { border-left-color: var(--neon-red); }

        .status {
            font-weight: bold;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .status.online { color: var(--neon-green); text-shadow: 0 0 5px var(--neon-green); animation: pulse 2s infinite; }
        .status.standby { color: #ffaa00; text-shadow: 0 0 5px #ffaa00; }
        .status.engaged { color: var(--neon-red); text-shadow: 0 0 8px var(--neon-red); animation: fast-pulse 0.5s infinite alternate; }
        
        @keyframes pulse {
            0% { opacity: 0.7; }
            50% { opacity: 1; text-shadow: 0 0 15px var(--neon-green); }
            100% { opacity: 0.7; }
        }
        @keyframes fast-pulse {
            0% { opacity: 0.8; }
            100% { opacity: 1; text-shadow: 0 0 20px var(--neon-red); }
        }

        .scanline {
            width: 100%;
            height: 10px;
            position: fixed;
            top: 0; left: 0;
            background: rgba(0, 255, 255, 0.3);
            box-shadow: 0 0 20px rgba(0, 255, 255, 0.5);
            opacity: 0.4;
            animation: scan 8s linear infinite;
            pointer-events: none;
            z-index: 100;
        }
        @keyframes scan {
            0% { top: -10px; }
            100% { top: 100vh; }
        }

        .crt::before {
            content: " ";
            display: block;
            position: fixed;
            top: 0; left: 0; bottom: 0; right: 0;
            background: linear-gradient(rgba(18, 16, 16, 0) 50%, rgba(0, 0, 0, 0.25) 50%), linear-gradient(90deg, rgba(255, 0, 0, 0.06), rgba(0, 255, 0, 0.02), rgba(0, 0, 255, 0.06));
            z-index: 2;
            background-size: 100% 2px, 3px 100%;
            pointer-events: none;
        }
        .blink-dot {
            display: inline-block;
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background-color: currentColor;
        }
        
        .metric-value { font-size: 1.2em; text-shadow: 0 0 5px currentColor; }
        .up { color: var(--neon-green); }
        .down { color: var(--neon-red); }
    </style>
</head>
<body class="crt">
    <div class="scanline"></div>
    
    <h1>🛰️ Nuvola Orbital Command 🛰️</h1>
    
    <div style="text-align: center; margin-bottom: 30px; font-size: 1.5rem; font-weight: bold; color: var(--neon-pink); border: 2px solid var(--neon-pink); padding: 15px; border-radius: 8px; background: rgba(255, 0, 255, 0.1); text-shadow: 0 0 10px var(--neon-pink); box-shadow: 0 0 15px rgba(255, 0, 255, 0.3);">
        ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
    </div>

    <div class="grid">
        <!-- HFT SQUADS -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <div class="row active">
                <span>[ALPHA] Scalper Binance</span>
                <span class="status engaged"><span class="blink-dot"></span> ENGAGED</span>
            </div>
            <div class="row active">
                <span>[DELTA] Order Flow</span>
                <span class="status engaged"><span class="blink-dot"></span> ENGAGED</span>
            </div>
            <div class="row standby">
                <span>[GAMMA] Pairs Trading Bitget</span>
                <span class="status standby"><span class="blink-dot"></span> STANDBY</span>
            </div>
            <div style="margin-top:20px; font-size: 0.8em; opacity: 0.7; text-align: right;">
                > TERMINAL_LINK_SECURE
            </div>
        </div>

        <!-- TRINITY PROTOCOL -->
        <div class="panel trinity">
            <h2>🛡️ PROTOCOLLO TRINITY</h2>
            <div class="row active">
                <span>🕴️ Lo Strozzino <br><small style="opacity:0.6; font-size: 0.8em;">(Funding Arb)</small></span>
                <span class="status online"><span class="blink-dot"></span> ONLINE</span>
            </div>
            <div class="row active">
                <span>🧮 Il Contabile <br><small style="opacity:0.6; font-size: 0.8em;">(DCA Module)</small></span>
                <span class="status online"><span class="blink-dot"></span> ONLINE</span>
            </div>
            <div class="row active">
                <span>👼 L'Angelo Custode <br><small style="opacity:0.6; font-size: 0.8em;">(MEV Arbitrum)</small></span>
                <span class="status online"><span class="blink-dot"></span> ONLINE</span>
            </div>
            <div style="margin-top:20px; font-size: 0.8em; opacity: 0.7; text-align: right;">
                > BACKGROUND_EXECUTION_ACTIVE
            </div>
        </div>

        <!-- MARKET METRICS -->
        <div class="panel market">
            <h2>📊 METRICHE DI MERCATO</h2>
            <div class="row">
                <span>👁️ The Oracle <br><small style="opacity:0.6; font-size: 0.8em;">(Binance Sentiment)</small></span>
                <span class="status up metric-value">BULLISH 🚀</span>
            </div>
            <div class="row">
                <span>🐋 Whale Tracker <br><small style="opacity:0.6; font-size: 0.8em;">(On-Chain Flows)</small></span>
                <span class="status up metric-value">+240M INFLOW 🌊</span>
            </div>
            <div class="row">
                <span>⚡ Latenza Nuvola <br><small style="opacity:0.6; font-size: 0.8em;">(Execution Node)</small></span>
                <span class="status online metric-value">4 ms 🟢</span>
            </div>
            <div style="margin-top:20px; font-size: 0.8em; opacity: 0.7; text-align: right;">
                > DATA_FEEDS_SYNCED
            </div>
        </div>
    </div>
    
    <div style="text-align: center; margin-top: 50px; font-size: 0.8rem; opacity: 0.5;">
        NUVOLA KERNEL v2.5.4 | SYSTEM NOMINAL | E2E ENCRYPTION ENABLED
    </div>

    <script>
        // Simple script to randomly update the latency to make it feel alive
        setInterval(() => {
            const latencies = ['4 ms', '5 ms', '3 ms', '7 ms', '4 ms'];
            const l = latencies[Math.floor(Math.random() * latencies.length)];
            const el = document.querySelectorAll('.metric-value')[2];
            if(el) el.innerHTML = l + ' 🟢';
        }, 2000);
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    # Run on all interfaces, port 5000 (adjust if needed)
    app.run(host='0.0.0.0', port=5000, debug=False)
