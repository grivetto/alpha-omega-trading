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
        @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');

        :root {
            --neon-blue: #00f3ff;
            --neon-pink: #ff00ea;
            --neon-green: #00ff66;
            --neon-yellow: #ffaa00;
            --neon-red: #ff0044;
            --dark-bg: #050508;
            --panel-bg: rgba(8, 12, 18, 0.85);
            --grid-color: rgba(0, 243, 255, 0.05);
            --scanline: rgba(255, 255, 255, 0.02);
        }

        body {
            background-color: var(--dark-bg);
            color: var(--neon-blue);
            font-family: 'Share Tech Mono', monospace;
            margin: 0;
            padding: 20px;
            overflow-x: hidden;
            background-image: 
                linear-gradient(var(--grid-color) 1px, transparent 1px),
                linear-gradient(90deg, var(--grid-color) 1px, transparent 1px);
            background-size: 40px 40px;
            position: relative;
        }

        body::after {
            content: "";
            position: fixed;
            top: 0; left: 0; width: 100vw; height: 100vh;
            background: linear-gradient(to bottom, var(--scanline) 50%, transparent 50%);
            background-size: 100% 4px;
            pointer-events: none;
            z-index: 9999;
        }

        h1 {
            text-align: center;
            color: var(--neon-pink);
            text-shadow: 0 0 10px var(--neon-pink), 0 0 20px var(--neon-pink), 0 0 40px var(--neon-pink);
            font-size: 3em;
            letter-spacing: 8px;
            text-transform: uppercase;
            border-bottom: 2px solid var(--neon-pink);
            padding-bottom: 15px;
            margin-bottom: 5px;
            animation: flicker 3s infinite alternate;
        }

        .subtitle {
            text-align: center; 
            color: var(--neon-green); 
            font-size: 1.2em; 
            margin-bottom: 30px; 
            text-shadow: 0 0 8px var(--neon-green); 
            animation: pulse 2s infinite;
            letter-spacing: 2px;
        }

        .container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(380px, 1fr));
            gap: 25px;
            margin-top: 10px;
        }

        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-blue);
            border-radius: 4px;
            padding: 25px;
            box-shadow: inset 0 0 20px rgba(0, 243, 255, 0.1), 0 0 15px rgba(0, 243, 255, 0.3);
            position: relative;
            overflow: hidden;
            backdrop-filter: blur(5px);
        }

        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: -100%;
            width: 50%; height: 2px;
            background: linear-gradient(90deg, transparent, var(--neon-blue));
            animation: scan 4s infinite linear;
        }

        .panel-pink {
            border-color: var(--neon-pink);
            box-shadow: inset 0 0 20px rgba(255, 0, 234, 0.1), 0 0 15px rgba(255, 0, 234, 0.3);
        }
        .panel-pink::before { background: linear-gradient(90deg, transparent, var(--neon-pink)); }

        .panel-yellow {
            border-color: var(--neon-yellow);
            box-shadow: inset 0 0 20px rgba(255, 170, 0, 0.1), 0 0 15px rgba(255, 170, 0, 0.3);
        }
        .panel-yellow::before { background: linear-gradient(90deg, transparent, var(--neon-yellow)); }

        .panel h2 {
            margin-top: 0;
            color: var(--neon-blue);
            text-shadow: 0 0 8px var(--neon-blue);
            border-bottom: 1px dashed var(--neon-blue);
            padding-bottom: 10px;
            display: flex;
            align-items: center;
            gap: 12px;
            font-size: 1.5em;
            text-transform: uppercase;
        }

        .panel-pink h2 { color: var(--neon-pink); text-shadow: 0 0 8px var(--neon-pink); border-bottom-color: var(--neon-pink); }
        .panel-yellow h2 { color: var(--neon-yellow); text-shadow: 0 0 8px var(--neon-yellow); border-bottom-color: var(--neon-yellow); }

        ul {
            list-style-type: none;
            padding: 0;
            margin: 0;
        }

        li {
            margin: 15px 0;
            padding: 12px 15px;
            background: rgba(0, 243, 255, 0.05);
            border-left: 4px solid var(--neon-blue);
            display: flex;
            justify-content: space-between;
            align-items: center;
            transition: all 0.2s;
            position: relative;
        }

        li:hover {
            background: rgba(0, 243, 255, 0.15);
            transform: translateX(5px);
        }

        .panel-pink li { background: rgba(255, 0, 234, 0.05); border-left-color: var(--neon-pink); }
        .panel-pink li:hover { background: rgba(255, 0, 234, 0.15); }

        .agent-info {
            display: flex;
            flex-direction: column;
            gap: 4px;
        }

        .agent-name { font-size: 1.2em; font-weight: bold; letter-spacing: 1px; }
        .agent-desc { font-size: 0.85em; opacity: 0.8; }

        .status {
            font-weight: bold;
            padding: 4px 10px;
            border-radius: 2px;
            font-size: 0.9em;
            letter-spacing: 1px;
            border: 1px solid currentColor;
            box-shadow: 0 0 5px currentColor;
        }

        .status.active { color: var(--neon-green); text-shadow: 0 0 5px var(--neon-green); animation: blink 1.5s infinite; }
        .status.standby { color: var(--neon-yellow); text-shadow: 0 0 5px var(--neon-yellow); }
        .status.offline { color: var(--neon-red); text-shadow: 0 0 5px var(--neon-red); }

        .metric-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
            margin-top: 15px;
        }

        .metric-card {
            background: rgba(255, 170, 0, 0.05);
            border: 1px solid var(--neon-yellow);
            padding: 15px;
            text-align: center;
            box-shadow: inset 0 0 10px rgba(255, 170, 0, 0.1);
            position: relative;
        }

        .metric-card:hover { background: rgba(255, 170, 0, 0.1); }

        .metric-title { font-size: 0.9em; color: var(--neon-yellow); opacity: 0.9; text-transform: uppercase; letter-spacing: 1px;}
        .metric-val {
            font-size: 1.8em;
            color: #fff;
            text-shadow: 0 0 10px #fff, 0 0 20px var(--neon-yellow);
            margin-top: 8px;
            font-weight: bold;
        }

        .terminal {
            background: rgba(0, 0, 0, 0.8);
            border: 1px solid #333;
            border-top: 2px solid var(--neon-blue);
            padding: 15px;
            font-size: 0.9em;
            height: 200px;
            overflow-y: auto;
            margin-top: 30px;
            color: #ccc;
            box-shadow: 0 0 20px rgba(0, 0, 0, 0.8);
            position: relative;
        }
        
        .terminal::before {
            content: 'SYS.LOG // CLASSIFIED';
            position: absolute;
            top: 0; right: 0;
            background: var(--neon-blue);
            color: #000;
            padding: 2px 10px;
            font-size: 0.8em;
            font-weight: bold;
        }

        .terminal p { margin: 4px 0; border-bottom: 1px solid rgba(255,255,255,0.05); padding-bottom: 2px; }
        .log-time { color: var(--neon-blue); margin-right: 10px; }
        .log-info { color: #ccc; }
        .log-warn { color: var(--neon-yellow); }
        .log-err { color: var(--neon-red); }
        .log-success { color: var(--neon-green); }

        @keyframes pulse {
            0% { opacity: 0.7; }
            50% { opacity: 1; text-shadow: 0 0 15px var(--neon-green); }
            100% { opacity: 0.7; }
        }

        @keyframes flicker {
            0%, 19%, 21%, 23%, 25%, 54%, 56%, 100% { text-shadow: 0 0 10px var(--neon-pink), 0 0 20px var(--neon-pink), 0 0 40px var(--neon-pink); opacity: 1; }
            20%, 24%, 55% { text-shadow: none; opacity: 0.5; }
        }

        @keyframes scan {
            0% { left: -100%; }
            100% { left: 100%; }
        }

        @keyframes blink {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        
        .progress-bar {
            width: 100%;
            height: 4px;
            background: #222;
            margin-top: 8px;
            position: relative;
            overflow: hidden;
        }
        .progress-fill {
            height: 100%;
            background: var(--neon-blue);
            box-shadow: 0 0 10px var(--neon-blue);
        }
        .progress-fill.pink { background: var(--neon-pink); box-shadow: 0 0 10px var(--neon-pink); }

    </style>
</head>
<body>

    <h1>🚀 ORBITAL COMMAND</h1>
    <div class="subtitle">
        [ SYS.OP: TRINITY PROTOCOL ONLINE // HFT ASSAULT SQUADS: ENGAGED ]<br><br>
        <span style="color: var(--neon-pink); font-size: 1.1em; border: 1px solid var(--neon-pink); padding: 5px 15px; border-radius: 4px; box-shadow: 0 0 10px var(--neon-pink); text-shadow: 0 0 5px var(--neon-pink);">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</span>
    </div>

    <div class="container">
        <!-- SEZIONE 1: SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <ul>
                <li>
                    <div class="agent-info">
                        <span class="agent-name">⚡ SQUADRA_ALPHA</span>
                        <span class="agent-desc">[Scalper | Binance] L1 Orderbook</span>
                        <div class="progress-bar"><div class="progress-fill" style="width: 85%;"></div></div>
                    </div>
                    <span class="status active">ENGAGED</span>
                </li>
                <li>
                    <div class="agent-info">
                        <span class="agent-name">🌊 SQUADRA_DELTA</span>
                        <span class="agent-desc">[Order Flow | Bybit] Liquidity</span>
                        <div class="progress-bar"><div class="progress-fill" style="width: 92%;"></div></div>
                    </div>
                    <span class="status active">ENGAGED</span>
                </li>
                <li>
                    <div class="agent-info">
                        <span class="agent-name">⚖️ SQUADRA_GAMMA</span>
                        <span class="agent-desc">[Pairs Trading | Bitget] StatArb</span>
                        <div class="progress-bar"><div class="progress-fill" style="width: 15%; background: var(--neon-yellow); box-shadow: 0 0 10px var(--neon-yellow);"></div></div>
                    </div>
                    <span class="status standby">STANDBY</span>
                </li>
            </ul>
        </div>

        <!-- SEZIONE 2: PROTOCOLLO TRINITY -->
        <div class="panel panel-pink">
            <h2>🔺 PROTOCOLLO TRINITY</h2>
            <ul>
                <li>
                    <div class="agent-info">
                        <span class="agent-name">🕴️ Lo Strozzino</span>
                        <span class="agent-desc">[Funding Arb | Cross-Exchange]</span>
                        <div class="progress-bar"><div class="progress-fill pink" style="width: 100%;"></div></div>
                    </div>
                    <span class="status active">ONLINE</span>
                </li>
                <li>
                    <div class="agent-info">
                        <span class="agent-name">🧮 Il Contabile</span>
                        <span class="agent-desc">[DCA Protocol | Spot Accumulation]</span>
                        <div class="progress-bar"><div class="progress-fill pink" style="width: 100%;"></div></div>
                    </div>
                    <span class="status active">ONLINE</span>
                </li>
                <li>
                    <div class="agent-info">
                        <span class="agent-name">🛡️ L'Angelo Custode</span>
                        <span class="agent-desc">[MEV | Arbitrum Mempool Sniper]</span>
                        <div class="progress-bar"><div class="progress-fill pink" style="width: 100%;"></div></div>
                    </div>
                    <span class="status active">ONLINE</span>
                </li>
            </ul>
        </div>

        <!-- SEZIONE 3: METRICHE DI MERCATO -->
        <div class="panel panel-yellow">
            <h2>📊 METRICHE TATTICHE</h2>
            <div class="metric-grid">
                <div class="metric-card">
                    <div class="metric-title">🔮 The Oracle (Sentiment)</div>
                    <div class="metric-val">EXTREME GREED</div>
                    <div style="font-size: 0.8em; color: var(--neon-yellow); margin-top: 5px;">Index: 84/100</div>
                </div>
                <div class="metric-card">
                    <div class="metric-title">🐋 Whale Tracker (24H)</div>
                    <div class="metric-val" style="color: var(--neon-green); text-shadow: 0 0 10px var(--neon-green);">+ $2.4B</div>
                    <div style="font-size: 0.8em; color: var(--neon-green); margin-top: 5px;">NET INFLOW</div>
                </div>
                <div class="metric-card">
                    <div class="metric-title">🎯 Tactical PNL (Daily)</div>
                    <div class="metric-val" style="color: var(--neon-green); text-shadow: 0 0 10px var(--neon-green);">+ 12.8%</div>
                    <div style="font-size: 0.8em; color: #aaa; margin-top: 5px;">Realized Yield</div>
                </div>
                <div class="metric-card">
                    <div class="metric-title">🛰️ Network Latency</div>
                    <div class="metric-val" style="color: var(--neon-blue); text-shadow: 0 0 10px var(--neon-blue);">8 ms</div>
                    <div style="font-size: 0.8em; color: #aaa; margin-top: 5px;">Binance WS Colocation</div>
                </div>
            </div>
        </div>
    </div>

    <!-- TERMINALE LOGS -->
    <div class="terminal" id="terminal-logs">
        <p><span class="log-time">[11:20:05.142]</span> <span class="log-info">SYSTEM: Initializing Orbital Command protocols...</span></p>
        <p><span class="log-time">[11:20:07.881]</span> <span class="log-success">NETWORK: Connected to Binance WebSocket (Stream ID: 0x91jf8...a3)</span></p>
        <p><span class="log-time">[11:20:12.005]</span> <span class="log-warn">WARNING: High volatility spike detected in ETH/USDT orderbook.</span></p>
        <p><span class="log-time">[11:20:15.330]</span> <span class="log-success">ALPHA: Executed scalp long ETH (Size: 15.5) @ 3105.42. Order filled 2ms.</span></p>
        <p><span class="log-time">[11:20:22.910]</span> <span class="log-info">STROZZINO: Harvesting funding rate on SOL/USDT (+0.021%).</span></p>
        <p><span class="log-time">[11:20:30.405]</span> <span class="log-success">ANGELO: Arbitrum block #19482201 simulated. Yielding MEV strategy (+0.05 ETH).</span></p>
        <p><span class="log-time">[11:21:00.001]</span> <span class="log-info">SYSTEM: Awaiting next command sequence... scanning mempool.</span></p>
    </div>

    <script>
        const terminal = document.getElementById('terminal-logs');
        terminal.scrollTop = terminal.scrollHeight;
        
        // Falso streaming di log
        const logs = [
            '<span class="log-warn">DELTA: Tracking large limit order spoofing on BTC/USDT.</span>',
            '<span class="log-info">ORACLE: Sentiment shifted +2 points. Re-calibrating parameters.</span>',
            '<span class="log-success">CONTABILE: Executed daily DCA on BTC @ 64,200.</span>',
            '<span class="log-info">SYSTEM: Heartbeat OK. Latency stable at 8ms.</span>'
        ];
        
        let i = 0;
        setInterval(() => {
            if (i < logs.length) {
                const p = document.createElement('p');
                const now = new Date();
                const timeStr = `[${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}:${now.getSeconds().toString().padStart(2, '0')}.${now.getMilliseconds().toString().padStart(3, '0')}]`;
                p.innerHTML = `<span class="log-time">${timeStr}</span> ${logs[i]}`;
                terminal.appendChild(p);
                terminal.scrollTop = terminal.scrollHeight;
                i++;
            }
        }, 3500);
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
