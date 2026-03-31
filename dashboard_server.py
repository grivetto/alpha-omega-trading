import os
from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Nuvola Orbital Command 🛰️</title>
    <style>
        :root {
            --neon-green: #0f0;
            --neon-cyan: #0ff;
            --neon-red: #f00;
            --bg-color: #050505;
            --panel-bg: rgba(0, 255, 0, 0.05);
            --border-glow: 0 0 10px #0f0;
        }

        body {
            margin: 0;
            padding: 20px;
            background-color: var(--bg-color);
            color: var(--neon-green);
            font-family: 'Courier New', Courier, monospace;
            text-transform: uppercase;
            overflow-x: hidden;
            background-image: linear-gradient(rgba(0, 255, 0, 0.03) 1px, transparent 1px),
            linear-gradient(90deg, rgba(0, 255, 0, 0.03) 1px, transparent 1px);
            background-size: 20px 20px;
        }

        /* Scanline effect */
        body::before {
            content: " ";
            display: block;
            position: absolute;
            top: 0;
            left: 0;
            bottom: 0;
            right: 0;
            background: linear-gradient(rgba(18, 16, 16, 0) 50%, rgba(0, 0, 0, 0.25) 50%), linear-gradient(90deg, rgba(255, 0, 0, 0.06), rgba(0, 255, 0, 0.02), rgba(0, 0, 255, 0.06));
            z-index: 2;
            background-size: 100% 2px, 3px 100%;
            pointer-events: none;
        }

        h1 {
            text-align: center;
            color: var(--neon-cyan);
            text-shadow: 0 0 15px var(--neon-cyan);
            letter-spacing: 5px;
            border-bottom: 2px solid var(--neon-cyan);
            padding-bottom: 10px;
            margin-bottom: 30px;
            animation: glitch 2s infinite;
        }

        .container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
            position: relative;
            z-index: 3;
        }

        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-green);
            border-radius: 5px;
            padding: 20px;
            box-shadow: var(--border-glow);
            position: relative;
            overflow: hidden;
        }

        .panel h2 {
            margin-top: 0;
            border-bottom: 1px dashed var(--neon-green);
            padding-bottom: 5px;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .panel h2 span {
            font-size: 1.2em;
        }

        .status-item {
            display: flex;
            justify-content: space-between;
            margin: 10px 0;
            padding: 5px 0;
            border-bottom: 1px solid rgba(0, 255, 0, 0.2);
        }

        .status-indicator {
            animation: blink 1s infinite alternate;
        }

        .status-ok { color: var(--neon-green); text-shadow: 0 0 5px var(--neon-green); }
        .status-bg { color: var(--neon-cyan); text-shadow: 0 0 5px var(--neon-cyan); }
        .status-warn { color: yellow; text-shadow: 0 0 5px yellow; }

        .terminal {
            background: #000;
            border: 1px solid var(--neon-green);
            padding: 10px;
            height: 150px;
            overflow-y: auto;
            margin-top: 20px;
            font-size: 0.9em;
        }

        .terminal-line { margin: 5px 0; }
        .terminal-prefix { color: var(--neon-cyan); }

        @keyframes blink {
            from { opacity: 1; }
            to { opacity: 0.5; }
        }

        @keyframes glitch {
            0% { text-shadow: 0.05em 0 0 rgba(255,0,0,.75), -0.05em -0.025em 0 rgba(0,255,0,.75), -0.025em 0.05em 0 rgba(0,0,255,.75); }
            14% { text-shadow: 0.05em 0 0 rgba(255,0,0,.75), -0.05em -0.025em 0 rgba(0,255,0,.75), -0.025em 0.05em 0 rgba(0,0,255,.75); }
            15% { text-shadow: -0.05em -0.025em 0 rgba(255,0,0,.75), 0.025em 0.025em 0 rgba(0,255,0,.75), -0.05em -0.05em 0 rgba(0,0,255,.75); }
            49% { text-shadow: -0.05em -0.025em 0 rgba(255,0,0,.75), 0.025em 0.025em 0 rgba(0,255,0,.75), -0.05em -0.05em 0 rgba(0,0,255,.75); }
            50% { text-shadow: 0.025em 0.05em 0 rgba(255,0,0,.75), 0.05em 0 0 rgba(0,255,0,.75), 0 -0.05em 0 rgba(0,0,255,.75); }
            99% { text-shadow: 0.025em 0.05em 0 rgba(255,0,0,.75), 0.05em 0 0 rgba(0,255,0,.75), 0 -0.05em 0 rgba(0,0,255,.75); }
            100% { text-shadow: -0.025em 0 0 rgba(255,0,0,.75), -0.025em -0.025em 0 rgba(0,255,0,.75), -0.025em -0.05em 0 rgba(0,0,255,.75); }
        }

        .stat-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
            margin-top: 15px;
        }

        .stat-box {
            border: 1px solid rgba(0, 255, 0, 0.4);
            padding: 10px;
            text-align: center;
            background: rgba(0, 0, 0, 0.5);
        }
        
        .stat-value {
            font-size: 1.5em;
            font-weight: bold;
            color: var(--neon-cyan);
            margin-top: 5px;
            text-shadow: 0 0 5px var(--neon-cyan);
        }
    </style>
</head>
<body>

    <h1>🛰️ Nuvola Orbital Command 🛰️</h1>

    <div style="text-align: center; margin-bottom: 20px; font-size: 1.2em; border: 1px solid var(--neon-cyan); padding: 10px; background: rgba(0, 255, 255, 0.1); box-shadow: 0 0 10px var(--neon-cyan); animation: blink 2s infinite alternate; text-shadow: 0 0 5px var(--neon-cyan);">
        ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
    </div>

    <div class="container">
        <!-- SEZIONE 1: SQUADRE D'ASSALTO -->
        <div class="panel">
            <h2><span>⚔️</span> SQUADRE D'ASSALTO (HFT)</h2>
            <div class="status-item">
                <span>[ALPHA] Binance Scalper</span>
                <span class="status-ok status-indicator">ONLINE 🟢</span>
            </div>
            <div class="status-item">
                <span>[DELTA] Order Flow Tracker</span>
                <span class="status-ok status-indicator">ONLINE 🟢</span>
            </div>
            <div class="status-item">
                <span>[GAMMA] Bitget Pairs Trading</span>
                <span class="status-ok status-indicator">ONLINE 🟢</span>
            </div>
            <div class="stat-grid">
                <div class="stat-box">
                    <div>WIN RATE HFT</div>
                    <div class="stat-value">68.4%</div>
                </div>
                <div class="stat-box">
                    <div>LATENCY</div>
                    <div class="stat-value">12ms</div>
                </div>
            </div>
        </div>

        <!-- SEZIONE 2: PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2><span>🛡️</span> PROTOCOLLO TRINITY</h2>
            <div class="status-item">
                <span>Lo Strozzino [Funding Arb]</span>
                <span class="status-bg status-indicator">BACKGROUND 🔄</span>
            </div>
            <div class="status-item">
                <span>Il Contabile [DCA Mngmt]</span>
                <span class="status-bg status-indicator">BACKGROUND 🔄</span>
            </div>
            <div class="status-item">
                <span>L'Angelo Custode [MEV Arbitrum]</span>
                <span class="status-bg status-indicator">BACKGROUND 🔄</span>
            </div>
            <div class="stat-grid">
                <div class="stat-box">
                    <div>UPTIME TRINITY</div>
                    <div class="stat-value">99.9%</div>
                </div>
                <div class="stat-box">
                    <div>YIELD EST.</div>
                    <div class="stat-value">18% APY</div>
                </div>
            </div>
        </div>

        <!-- SEZIONE 3: METRICHE DI MERCATO -->
        <div class="panel">
            <h2><span>📊</span> METRICHE DI MERCATO</h2>
            <div class="status-item">
                <span>The Oracle [Binance Sentiment]</span>
                <span class="status-ok status-indicator">BULLISH 🟢</span>
            </div>
            <div class="status-item">
                <span>Whale Tracker [On-Chain]</span>
                <span class="status-warn status-indicator">WHALE DETECTED 🐋</span>
            </div>
            
            <div class="terminal" id="terminal">
                <div class="terminal-line"><span class="terminal-prefix">root@nuvola:~$</span> initializing data streams...</div>
                <div class="terminal-line"><span class="terminal-prefix">root@nuvola:~$</span> connecting to binance wss... SUCCESS</div>
                <div class="terminal-line"><span class="terminal-prefix">root@nuvola:~$</span> tracking order blocks... ACTIVE</div>
            </div>
        </div>
    </div>

    <script>
        // Simple terminal animation
        const terminal = document.getElementById('terminal');
        const messages = [
            "fetching orderbook depth...",
            "analyzing volume delta...",
            "whale transfer 5000 BTC to Coinbase",
            "liquidations hitting $50M on short side",
            "recalibrating SQUADRA_ALPHA risk params...",
            "MEV searcher (Angelo Custode) active on Arbitrum..."
        ];

        setInterval(() => {
            const msg = messages[Math.floor(Math.random() * messages.length)];
            const div = document.createElement('div');
            div.className = 'terminal-line';
            div.innerHTML = `<span class="terminal-prefix">sys@oracle:~$</span> ${msg}`;
            terminal.appendChild(div);
            if(terminal.children.length > 20) {
                terminal.removeChild(terminal.firstChild);
            }
            terminal.scrollTop = terminal.scrollHeight;
        }, 3000);
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    # Riavvia il server sulla porta 5000 (modificabile se necessario)
    app.run(host='0.0.0.0', port=5000, debug=False)
