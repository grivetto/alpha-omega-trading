from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ORBITAL COMMAND [NUVOLA]</title>
    <style>
        :root {
            --neon-blue: #00f3ff;
            --neon-pink: #ff00ea;
            --neon-green: #00ff66;
            --dark-bg: #090a0f;
            --panel-bg: rgba(16, 20, 30, 0.8);
            --grid-color: rgba(0, 243, 255, 0.1);
        }

        body {
            background-color: var(--dark-bg);
            color: var(--neon-blue);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            background-image: 
                linear-gradient(var(--grid-color) 1px, transparent 1px),
                linear-gradient(90deg, var(--grid-color) 1px, transparent 1px);
            background-size: 30px 30px;
        }

        h1 {
            text-align: center;
            color: var(--neon-pink);
            text-shadow: 0 0 10px var(--neon-pink), 0 0 20px var(--neon-pink);
            font-size: 2.5em;
            letter-spacing: 5px;
            text-transform: uppercase;
            border-bottom: 2px solid var(--neon-pink);
            padding-bottom: 10px;
            animation: flicker 2s infinite alternate;
        }

        .container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
            margin-top: 30px;
        }

        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-blue);
            border-radius: 5px;
            padding: 20px;
            box-shadow: inset 0 0 15px rgba(0, 243, 255, 0.2), 0 0 10px var(--neon-blue);
            transition: all 0.3s ease;
        }

        .panel:hover {
            box-shadow: inset 0 0 25px rgba(0, 243, 255, 0.4), 0 0 20px var(--neon-blue);
            transform: scale(1.02);
        }

        .panel h2 {
            margin-top: 0;
            color: var(--neon-green);
            text-shadow: 0 0 5px var(--neon-green);
            border-bottom: 1px dashed var(--neon-green);
            padding-bottom: 5px;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        ul {
            list-style-type: none;
            padding: 0;
        }

        li {
            margin: 10px 0;
            padding: 8px;
            background: rgba(0, 255, 102, 0.05);
            border-left: 3px solid var(--neon-green);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .status {
            font-weight: bold;
            animation: pulse 1.5s infinite;
        }

        .status.active { color: #00ff66; text-shadow: 0 0 5px #00ff66; }
        .status.standby { color: #ffaa00; text-shadow: 0 0 5px #ffaa00; }
        .status.offline { color: #ff0044; text-shadow: 0 0 5px #ff0044; }

        .metric-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
        }

        .metric-card {
            background: rgba(255, 0, 234, 0.05);
            border: 1px solid var(--neon-pink);
            padding: 10px;
            text-align: center;
            box-shadow: inset 0 0 10px rgba(255, 0, 234, 0.1);
        }

        .metric-val {
            font-size: 1.5em;
            color: #fff;
            text-shadow: 0 0 8px #fff;
            margin-top: 5px;
        }

        @keyframes pulse {
            0% { opacity: 0.7; }
            50% { opacity: 1; }
            100% { opacity: 0.7; }
        }

        @keyframes flicker {
            0%, 19%, 21%, 23%, 25%, 54%, 56%, 100% { text-shadow: 0 0 10px var(--neon-pink), 0 0 20px var(--neon-pink); opacity: 1; }
            20%, 24%, 55% { text-shadow: none; opacity: 0.5; }
        }

        .terminal {
            background: #000;
            border: 1px solid #333;
            padding: 10px;
            font-size: 0.8em;
            height: 150px;
            overflow-y: auto;
            margin-top: 20px;
            color: #aaa;
        }
        .terminal p { margin: 2px 0; }
        .log-time { color: var(--neon-blue); }
        .log-info { color: #ccc; }
        .log-warn { color: #ffaa00; }
        .log-err { color: #ff0044; }

    </style>
</head>
<body>

    <h1>🌐 ORBITAL COMMAND [NUVOLA] 🌐</h1>
    <div style="text-align: center; color: var(--neon-green); font-size: 1.2em; margin-bottom: 20px; text-shadow: 0 0 8px var(--neon-green); animation: pulse 2s infinite;">
        ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
    </div>

    <div class="container">
        <!-- SEZIONE 1: SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <ul>
                <li>
                    <span>⚡ SQUADRA_ALPHA <small>[Scalper su Binance]</small></span>
                    <span class="status active">ENGAGED</span>
                </li>
                <li>
                    <span>🌊 SQUADRA_DELTA <small>[Order Flow]</small></span>
                    <span class="status active">ENGAGED</span>
                </li>
                <li>
                    <span>⚖️ SQUADRA_GAMMA <small>[Pairs Trading Bitget]</small></span>
                    <span class="status standby">STANDBY</span>
                </li>
            </ul>
        </div>

        <!-- SEZIONE 2: PROTOCOLLO TRINITY -->
        <div class="panel" style="border-color: var(--neon-pink); box-shadow: inset 0 0 15px rgba(255, 0, 234, 0.2), 0 0 10px var(--neon-pink);">
            <h2 style="color: var(--neon-pink); border-bottom-color: var(--neon-pink); text-shadow: 0 0 5px var(--neon-pink);">🔺 PROTOCOLLO TRINITY</h2>
            <ul>
                <li style="border-left-color: var(--neon-pink); background: rgba(255, 0, 234, 0.05);">
                    <span>🕴️ Lo Strozzino <small>[Funding Arb]</small></span>
                    <span class="status active">ONLINE</span>
                </li>
                <li style="border-left-color: var(--neon-pink); background: rgba(255, 0, 234, 0.05);">
                    <span>🧮 Il Contabile <small>[DCA Protocol]</small></span>
                    <span class="status active">ONLINE</span>
                </li>
                <li style="border-left-color: var(--neon-pink); background: rgba(255, 0, 234, 0.05);">
                    <span>🛡️ L'Angelo Custode <small>[MEV Arbitrum]</small></span>
                    <span class="status active">ONLINE</span>
                </li>
            </ul>
        </div>

        <!-- SEZIONE 3: METRICHE DI MERCATO -->
        <div class="panel" style="border-color: #ffaa00; box-shadow: inset 0 0 15px rgba(255, 170, 0, 0.2), 0 0 10px #ffaa00;">
            <h2 style="color: #ffaa00; border-bottom-color: #ffaa00; text-shadow: 0 0 5px #ffaa00;">📊 METRICHE DI MERCATO</h2>
            <div class="metric-grid">
                <div class="metric-card" style="border-color: #ffaa00;">
                    <div style="font-size: 0.8em; color: #ffaa00;">🔮 The Oracle (Sentiment)</div>
                    <div class="metric-val" style="color: #ffaa00; text-shadow: 0 0 8px #ffaa00;">GREED (72)</div>
                </div>
                <div class="metric-card" style="border-color: #ffaa00;">
                    <div style="font-size: 0.8em; color: #ffaa00;">🐋 Whale Tracker (24h)</div>
                    <div class="metric-val" style="color: #ffaa00; text-shadow: 0 0 8px #ffaa00;">+ $1.2B INFLOW</div>
                </div>
                <div class="metric-card" style="border-color: #ffaa00;">
                    <div style="font-size: 0.8em; color: #ffaa00;">🎯 Target Profit (Daily)</div>
                    <div class="metric-val" style="color: #ffaa00; text-shadow: 0 0 8px #ffaa00;">142%</div>
                </div>
                <div class="metric-card" style="border-color: #ffaa00;">
                    <div style="font-size: 0.8em; color: #ffaa00;">🛰️ Latency (Avg)</div>
                    <div class="metric-val" style="color: #ffaa00; text-shadow: 0 0 8px #ffaa00;">14ms</div>
                </div>
            </div>
        </div>
    </div>

    <!-- TERMINALE LOGS -->
    <div class="terminal">
        <p><span class="log-time">[11:20:05]</span> <span class="log-info">SYSTEM: Initializing Orbital Command protocols...</span></p>
        <p><span class="log-time">[11:20:07]</span> <span class="log-info">NETWORK: Connected to Binance WebSocket (Stream ID: x91jf8)</span></p>
        <p><span class="log-time">[11:20:12]</span> <span class="log-warn">WARNING: High volatility detected in ETH/USDT orderbook.</span></p>
        <p><span class="log-time">[11:20:15]</span> <span class="log-info">ALPHA: Executed scalp long ETH (Size: 15.5) @ 3105.42</span></p>
        <p><span class="log-time">[11:20:22]</span> <span class="log-info">STROZZINO: Harvesting funding rate on SOL/USDT (+0.015%)</span></p>
        <p><span class="log-time">[11:20:30]</span> <span class="log-info">ANGELO: Block simulation successful. Yielding MEV strategy.</span></p>
        <p><span class="log-time">[11:21:00]</span> <span class="log-info">SYSTEM: Awaiting next command sequence...</span></p>
    </div>

    <script>
        // Simple auto-scroll for terminal if we were adding logs dynamically
        const terminal = document.querySelector('.terminal');
        terminal.scrollTop = terminal.scrollHeight;
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
