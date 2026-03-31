from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ORBITAL COMMAND // NUVOLA</title>
    <style>
        :root {
            --bg-color: #050510;
            --text-color: #0f0;
            --neon-blue: #00f3ff;
            --neon-pink: #ff00ff;
            --neon-red: #ff003c;
            --border-color: #00f3ff;
        }
        body {
            background-color: var(--bg-color);
            color: var(--text-color);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            text-transform: uppercase;
            overflow-x: hidden;
        }
        h1, h2, h3 {
            text-shadow: 0 0 10px currentColor;
            margin: 0 0 15px 0;
        }
        .header {
            text-align: center;
            border-bottom: 2px solid var(--neon-blue);
            padding-bottom: 20px;
            margin-bottom: 30px;
            box-shadow: 0 10px 20px -10px var(--neon-blue);
            animation: pulse 2s infinite;
        }
        .header h1 {
            color: var(--neon-blue);
            font-size: 2.5em;
            letter-spacing: 5px;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
        }
        .panel {
            background: rgba(0, 20, 40, 0.5);
            border: 1px solid var(--neon-blue);
            border-radius: 5px;
            padding: 20px;
            box-shadow: inset 0 0 15px rgba(0, 243, 255, 0.2), 0 0 10px rgba(0, 243, 255, 0.3);
            position: relative;
            overflow: hidden;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; height: 2px;
            background: linear-gradient(90deg, transparent, var(--neon-blue), transparent);
            animation: scanline 3s linear infinite;
        }
        .panel h2 {
            color: var(--neon-pink);
            border-bottom: 1px dashed var(--neon-pink);
            padding-bottom: 10px;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .status-indicator {
            display: inline-block;
            width: 10px; height: 10px;
            border-radius: 50%;
            background-color: #0f0;
            box-shadow: 0 0 8px #0f0;
            animation: blink 1s infinite alternate;
            margin-right: 10px;
        }
        .item {
            margin: 10px 0;
            padding: 10px;
            background: rgba(0, 0, 0, 0.5);
            border-left: 3px solid var(--neon-blue);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .item.danger { border-left-color: var(--neon-red); }
        .item.warning { border-left-color: #ffaa00; }
        
        .data-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
            font-size: 0.9em;
        }
        .data-cell {
            background: rgba(255, 255, 255, 0.05);
            padding: 8px;
            text-align: right;
        }
        .data-cell span { float: left; color: #888; }
        
        @keyframes pulse {
            0% { box-shadow: 0 10px 20px -10px var(--neon-blue); }
            50% { box-shadow: 0 10px 30px -5px var(--neon-blue); }
            100% { box-shadow: 0 10px 20px -10px var(--neon-blue); }
        }
        @keyframes blink {
            0% { opacity: 0.3; }
            100% { opacity: 1; }
        }
        @keyframes scanline {
            0% { transform: translateY(-100%); }
            100% { transform: translateY(500px); }
        }
        .log-box {
            height: 150px;
            overflow-y: auto;
            background: #000;
            border: 1px solid #333;
            padding: 10px;
            font-size: 0.8em;
            color: #aaa;
        }
        .log-line { margin: 2px 0; }
        .log-line span.time { color: var(--neon-blue); margin-right: 10px; }
        
        /* Glitch effect */
        .glitch {
            position: relative;
            color: var(--neon-blue);
        }
        .glitch::before, .glitch::after {
            content: attr(data-text);
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: var(--bg-color);
        }
        .glitch::before {
            left: 2px;
            text-shadow: -1px 0 red;
            clip: rect(24px, 550px, 90px, 0);
            animation: glitch-anim-2 3s infinite linear alternate-reverse;
        }
        .glitch::after {
            left: -2px;
            text-shadow: -1px 0 blue;
            clip: rect(85px, 550px, 140px, 0);
            animation: glitch-anim 2.5s infinite linear alternate-reverse;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1 class="glitch" data-text="🚀 NUVOLA ORBITAL COMMAND 🚀">🚀 NUVOLA ORBITAL COMMAND 🚀</h1>
        <p>SYSTEM ONLINE. UPLINK SECURE. QUANTUM ENCRYPTION ACTIVE.</p>
        <div style="color: #0f0; font-weight: bold; border: 1px solid #0f0; padding: 10px; display: inline-block; margin-top: 10px; box-shadow: 0 0 10px #0f0; background: rgba(0, 255, 0, 0.1);">
            ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
        </div>
    </div>

    <div class="grid">
        <!-- SQUADRE D'ASSALTO -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            
            <div class="item">
                <div>
                    <span class="status-indicator"></span>
                    <strong>SQUADRA_ALPHA</strong> 🐺<br>
                    <small>Binance Scalper // L1 Orderbook</small>
                </div>
                <div style="color: var(--neon-blue)">ACTIVE</div>
            </div>
            
            <div class="item danger">
                <div>
                    <span class="status-indicator" style="background: var(--neon-red); box-shadow: 0 0 8px var(--neon-red);"></span>
                    <strong>SQUADRA_DELTA</strong> 🦅<br>
                    <small>Order Flow // Imbalance Det.</small>
                </div>
                <div style="color: var(--neon-red)">ENGAGED</div>
            </div>
            
            <div class="item">
                <div>
                    <span class="status-indicator"></span>
                    <strong>SQUADRA_GAMMA</strong> 🐍<br>
                    <small>Bitget Pairs Trading // StatArb</small>
                </div>
                <div style="color: var(--neon-blue)">MONITORING</div>
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2>⚕️ PROTOCOLLO TRINITY</h2>
            
            <div class="item">
                <div>
                    <span class="status-indicator"></span>
                    <strong>LO STROZZINO</strong> 🏦<br>
                    <small>Funding Arb // Perpetual Yield</small>
                </div>
                <div style="color: #0f0">+14.2% APR</div>
            </div>
            
            <div class="item">
                <div>
                    <span class="status-indicator"></span>
                    <strong>IL CONTABILE</strong> 🧮<br>
                    <small>DCA Engine // Smart Accumulation</small>
                </div>
                <div style="color: #0f0">SYNCED</div>
            </div>
            
            <div class="item warning">
                <div>
                    <span class="status-indicator" style="background: #ffaa00; box-shadow: 0 0 8px #ffaa00;"></span>
                    <strong>L'ANGELO CUSTODE</strong> 👼<br>
                    <small>MEV Arbitrum // Flashbots Protect</small>
                </div>
                <div style="color: #ffaa00">HUNTING</div>
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <h2>📊 METRICHE DI MERCATO</h2>
            
            <div class="data-grid">
                <div class="data-cell"><span>THE ORACLE (Sentiment):</span> <b style="color: #0f0">GREED 78</b></div>
                <div class="data-cell"><span>WHALE TRACKER:</span> <b style="color: var(--neon-red)">SELL WALL @ 72k</b></div>
                <div class="data-cell"><span>LIQUIDITY MAP:</span> <b>NOMINAL</b></div>
                <div class="data-cell"><span>VOLATILITY INDEX:</span> <b style="color: #ffaa00">ELEVATED</b></div>
                <div class="data-cell"><span>NETWORK LATENCY:</span> <b>12ms</b></div>
                <div class="data-cell"><span>API RATE LIMITS:</span> <b>98% REMAINING</b></div>
            </div>
            
            <h3 style="margin-top: 15px; font-size: 1em; color: #aaa;">SYSTEM LOGS</h3>
            <div class="log-box" id="syslogs">
                <div class="log-line"><span class="time">[03:00:12]</span> [SYS] Initialization complete.</div>
                <div class="log-line"><span class="time">[03:01:45]</span> [STROZZINO] Rebalanced short funding.</div>
                <div class="log-line"><span class="time">[03:04:10]</span> [GAMMA] Detected spread anomaly on SOL/USDT.</div>
                <div class="log-line"><span class="time">[03:05:22]</span> [ORACLE] Sentiment shifting to extreme greed.</div>
                <div class="log-line"><span class="time">[03:07:05]</span> [ANGELO] Front-run attempted. Shield active.</div>
                <div class="log-line"><span class="time">[03:08:00]</span> [DELTA] Liquidations detected. Absorbing flow.</div>
            </div>
        </div>
    </div>

    <script>
        // Simulate live logs
        const logs = [
            "[ALPHA] Executed scalp long on ETH.",
            "[SYS] API Ping 14ms.",
            "[WHALE] 500 BTC moved to Binance.",
            "[GAMMA] Adjusting hedge ratio.",
            "[CONTABILE] DCA purchase executed.",
            "[ANGELO] Block #234988 scanned. No MEV."
        ];
        const logBox = document.getElementById('syslogs');
        setInterval(() => {
            const now = new Date();
            const timeStr = `[${now.getUTCHours().toString().padStart(2, '0')}:${now.getUTCMinutes().toString().padStart(2, '0')}:${now.getUTCSeconds().toString().padStart(2, '0')}]`;
            const msg = logs[Math.floor(Math.random() * logs.length)];
            const div = document.createElement('div');
            div.className = 'log-line';
            div.innerHTML = `<span class="time">${timeStr}</span> ${msg}`;
            logBox.appendChild(div);
            logBox.scrollTop = logBox.scrollHeight;
        }, 3500);
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
