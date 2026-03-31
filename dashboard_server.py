import threading
import time
from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ORBITAL COMMAND // NUVOLA</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');

        :root {
            --neon-cyan: #0ff;
            --neon-green: #39ff14;
            --neon-pink: #ff00ff;
            --neon-red: #ff073a;
            --neon-yellow: #fce803;
            --bg-dark: #050505;
            --panel-bg: rgba(10, 10, 15, 0.85);
        }

        body {
            background-color: var(--bg-dark);
            color: var(--neon-cyan);
            font-family: 'Share Tech Mono', 'Courier New', monospace;
            margin: 0;
            padding: 30px;
            overflow-x: hidden;
            background-image: linear-gradient(0deg, rgba(0, 255, 255, 0.05) 1px, transparent 1px),
                              linear-gradient(90deg, rgba(0, 255, 255, 0.05) 1px, transparent 1px);
            background-size: 20px 20px;
        }

        h1, h2, h3 {
            text-transform: uppercase;
            letter-spacing: 3px;
            margin-top: 0;
        }

        h1 {
            text-align: center;
            font-size: 2.5em;
            text-shadow: 0 0 10px var(--neon-cyan), 0 0 20px var(--neon-cyan), 0 0 40px var(--neon-cyan);
            border-bottom: 2px solid var(--neon-cyan);
            padding-bottom: 15px;
            margin-bottom: 40px;
        }

        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 30px;
        }

        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-cyan);
            border-radius: 4px;
            padding: 20px;
            box-shadow: inset 0 0 15px rgba(0, 255, 255, 0.1), 0 0 15px rgba(0, 255, 255, 0.2);
            position: relative;
            backdrop-filter: blur(5px);
        }

        .panel::before {
            content: '';
            position: absolute;
            top: -2px; left: -2px; width: 30px; height: 30px;
            border-top: 2px solid var(--neon-cyan);
            border-left: 2px solid var(--neon-cyan);
        }
        .panel::after {
            content: '';
            position: absolute;
            bottom: -2px; right: -2px; width: 30px; height: 30px;
            border-bottom: 2px solid var(--neon-cyan);
            border-right: 2px solid var(--neon-cyan);
        }

        .panel-pink { border-color: var(--neon-pink); box-shadow: inset 0 0 15px rgba(255,0,255,0.1), 0 0 15px rgba(255,0,255,0.2); }
        .panel-pink::before, .panel-pink::after { border-color: var(--neon-pink); }
        .panel-pink h2 { color: var(--neon-pink); text-shadow: 0 0 10px var(--neon-pink); }

        .panel-green { border-color: var(--neon-green); box-shadow: inset 0 0 15px rgba(57,255,20,0.1), 0 0 15px rgba(57,255,20,0.2); }
        .panel-green::before, .panel-green::after { border-color: var(--neon-green); }
        .panel-green h2 { color: var(--neon-green); text-shadow: 0 0 10px var(--neon-green); }

        .status-online { color: var(--neon-green); text-shadow: 0 0 8px var(--neon-green); }
        .status-active { color: var(--neon-cyan); text-shadow: 0 0 8px var(--neon-cyan); }
        .status-warning { color: var(--neon-yellow); text-shadow: 0 0 8px var(--neon-yellow); }
        .status-danger { color: var(--neon-red); text-shadow: 0 0 8px var(--neon-red); }
        
        ul { list-style-type: none; padding: 0; margin: 0; }
        li { margin-bottom: 12px; border-bottom: 1px dashed rgba(255, 255, 255, 0.1); padding-bottom: 8px; font-size: 1.1em; display: flex; justify-content: space-between; align-items: center; }
        li:last-child { border-bottom: none; }
        
        .label { opacity: 0.8; }
        
        @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.4; } 100% { opacity: 1; } }
        .pulse { animation: pulse 1.5s infinite; }
        
        @keyframes scanline {
            0% { transform: translateY(-100%); }
            100% { transform: translateY(100vh); }
        }
        .scanline {
            position: fixed;
            top: 0; left: 0; width: 100vw; height: 100px;
            background: linear-gradient(to bottom, transparent, rgba(0, 255, 255, 0.1), transparent);
            pointer-events: none;
            animation: scanline 4s linear infinite;
            z-index: 9999;
        }
    </style>
</head>
<body>
    <div class="scanline"></div>
    <h1>🛰️ ORBITAL COMMAND // NUVOLA 🛰️</h1>
    
    <div class="grid">
        <!-- SEZIONE 1: SQUADRE D'ASSALTO -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <ul>
                <li>
                    <span class="label">🚀 SQUADRA_ALPHA (Binance Scalper)</span>
                    <span class="status-online pulse">[ENGAGED] +<span id="pnl-alpha">2.41</span>%</span>
                </li>
                <li>
                    <span class="label">🌊 SQUADRA_DELTA (Order Flow)</span>
                    <span class="status-active">Volumi: <span id="vol-delta">ELEVATI</span></span>
                </li>
                <li>
                    <span class="label">⚖️ SQUADRA_GAMMA (Pairs Bitget)</span>
                    <span class="status-warning">Spread: <span id="spread-gamma">0.85</span>%</span>
                </li>
            </ul>
        </div>
        
        <!-- SEZIONE 2: PROTOCOLLO TRINITY -->
        <div class="panel panel-pink">
            <h2>🔺 PROTOCOLLO TRINITY</h2>
            <div style="text-align: center; margin-bottom: 15px; font-weight: bold; color: var(--neon-green); text-shadow: 0 0 8px var(--neon-green); border: 1px solid var(--neon-green); padding: 10px;">
                ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
            </div>
            <ul>
                <li>
                    <span class="label">🦇 Lo Strozzino (Funding Arb)</span>
                    <span class="status-online pulse">[ONLINE BG]</span>
                </li>
                <li>
                    <span class="label">🧮 Il Contabile (DCA)</span>
                    <span class="status-active">[ACCUMULO ATTIVO]</span>
                </li>
                <li>
                    <span class="label">🛡️ L'Angelo Custode (MEV Arb)</span>
                    <span class="status-online">[MEMPOOL SECURE]</span>
                </li>
            </ul>
        </div>

        <!-- SEZIONE 3: METRICHE DI MERCATO -->
        <div class="panel panel-green">
            <h2>📊 METRICHE DI MERCATO</h2>
            <ul>
                <li>
                    <span class="label">👁️ The Oracle (Binance Sentiment)</span>
                    <span class="status-online">BULLISH [<span id="oracle-score">82</span>/100]</span>
                </li>
                <li>
                    <span class="label">🐋 Whale Tracker</span>
                    <span class="status-warning pulse">ATTENZIONE: +500 BTC SPOT</span>
                </li>
                <li>
                    <span class="label">⚡ Nuvola Core Latency</span>
                    <span class="status-online">12ms</span>
                </li>
            </ul>
        </div>
    </div>
    
    <script>
        // Simulazione fluttuazioni tattiche in tempo reale
        setInterval(() => {
            document.getElementById('pnl-alpha').innerText = (Math.random() * 5).toFixed(2);
            document.getElementById('spread-gamma').innerText = (Math.random() * 1.5 + 0.1).toFixed(2);
            document.getElementById('oracle-score').innerText = Math.floor(Math.random() * 20) + 70;
            
            const vols = ['ELEVATI', 'MODERATI', 'ESTREMI', 'CRITICI'];
            document.getElementById('vol-delta').innerText = vols[Math.floor(Math.random() * vols.length)];
        }, 2500);
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    # Esecuzione server
    app.run(host='0.0.0.0', port=5000, debug=False)