from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🛰️ NUVOLA ORBITAL COMMAND 🛰️</title>
    <style>
        :root {
            --neon-green: #39ff14;
            --neon-cyan: #0ff;
            --neon-magenta: #ff00ff;
            --bg-color: #020202;
            --panel-bg: #090909;
            --grid-color: rgba(0, 255, 255, 0.05);
        }
        body {
            background-color: var(--bg-color);
            background-image: 
                linear-gradient(var(--grid-color) 1px, transparent 1px),
                linear-gradient(90deg, var(--grid-color) 1px, transparent 1px);
            background-size: 20px 20px;
            color: var(--neon-green);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 30px;
            text-transform: uppercase;
        }
        h1 {
            text-align: center;
            font-size: 2.5em;
            text-shadow: 0 0 10px var(--neon-cyan), 0 0 20px var(--neon-cyan);
            color: var(--neon-cyan);
            border-bottom: 2px solid var(--neon-cyan);
            padding-bottom: 15px;
            letter-spacing: 5px;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 25px;
            margin-top: 30px;
        }
        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-green);
            box-shadow: 0 0 15px rgba(57, 255, 20, 0.2);
            padding: 20px;
            border-radius: 8px;
            position: relative;
            overflow: hidden;
            transition: all 0.3s ease;
        }
        .panel:hover {
            box-shadow: 0 0 25px rgba(57, 255, 20, 0.4);
            transform: translateY(-2px);
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; height: 2px;
            background: linear-gradient(90deg, transparent, var(--neon-green), transparent);
            animation: scan 2s linear infinite;
        }
        @keyframes scan {
            0% { transform: translateX(-100%); }
            100% { transform: translateX(100%); }
        }
        .panel h2 {
            color: var(--neon-magenta);
            text-shadow: 0 0 5px var(--neon-magenta);
            font-size: 1.4em;
            margin-top: 0;
            border-bottom: 1px dashed var(--neon-magenta);
            padding-bottom: 10px;
            letter-spacing: 2px;
        }
        ul { list-style-type: none; padding: 0; margin: 0; }
        li { 
            margin: 15px 0; 
            border-left: 2px solid var(--neon-green); 
            padding-left: 15px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: rgba(57, 255, 20, 0.05);
            padding: 10px;
            border-radius: 0 5px 5px 0;
        }
        .status-online { color: var(--neon-green); animation: pulse 1.5s infinite; text-shadow: 0 0 5px var(--neon-green); }
        .status-standby { color: #ffd700; text-shadow: 0 0 5px #ffd700; }
        .metric-value { color: var(--neon-cyan); font-weight: bold; text-shadow: 0 0 5px var(--neon-cyan); }
        
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.5; }
            100% { opacity: 1; }
        }

        .footer {
            text-align: center;
            margin-top: 40px;
            font-size: 0.9em;
            opacity: 0.6;
            color: var(--neon-cyan);
            letter-spacing: 3px;
        }
    </style>
</head>
<body>
    <h1>🛰️ NUVOLA ORBITAL COMMAND 🛰️</h1>
    <div class="grid">
        <!-- HFT SECTOR -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <ul>
                <li><span>[α] SQUADRA_ALPHA (Binance Scalper)</span> <span class="status-online">[ATTACCO ONLINE]</span></li>
                <li><span>[δ] SQUADRA_DELTA (Order Flow)</span> <span class="status-online">[FLUSSO ATTIVO]</span></li>
                <li><span>[γ] SQUADRA_GAMMA (Bitget Pairs)</span> <span class="status-standby">[STANDBY TATTICO]</span></li>
            </ul>
        </div>
        
        <!-- TRINITY SECTOR -->
        <div class="panel">
            <h2>🛡️ PROTOCOLLO TRINITY</h2>
            <div style="color: var(--neon-green); text-align: center; margin-bottom: 15px; font-weight: bold; border: 1px dashed var(--neon-green); padding: 5px;">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</div>
            <ul>
                <li><span>🕷️ Lo Strozzino (Funding Arb)</span> <span class="status-online">[YIELD ESTIRPATO]</span></li>
                <li><span>🧮 Il Contabile (DCA)</span> <span class="status-online">[ACCUMULO SILENTE]</span></li>
                <li><span>😇 L'Angelo Custode (MEV Arbitrum)</span> <span class="status-online">[PROTEZIONE MEV]</span></li>
            </ul>
        </div>

        <!-- MARKET METRICS -->
        <div class="panel">
            <h2>📊 METRICHE DI MERCATO</h2>
            <ul>
                <li><span>👁️ The Oracle (Binance Sentiment)</span> <span class="metric-value">BULLISH [78%]</span></li>
                <li><span>🐋 Whale Tracker (Large Flows)</span> <span class="metric-value">+4.2B USD ↗</span></li>
                <li><span>⚡ Global Execution Latency</span> <span class="metric-value">12.04 ms</span></li>
            </ul>
        </div>
    </div>
    <div class="footer">
        SYSTEM IDENT: NUVOLA-9 // SECURE CONNECTION ESTABLISHED // UPTIME: <span id="uptime">00:00:00</span>
    </div>

    <script>
        let seconds = 0;
        setInterval(() => {
            seconds++;
            let h = Math.floor(seconds / 3600).toString().padStart(2, '0');
            let m = Math.floor((seconds % 3600) / 60).toString().padStart(2, '0');
            let s = (seconds % 60).toString().padStart(2, '0');
            document.getElementById('uptime').innerText = `${h}:${m}:${s}`;
        }, 1000);
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    # Esecuzione in locale per test/sfondo
    app.run(host='0.0.0.0', port=5000, debug=False)
