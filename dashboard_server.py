import os
from flask import Flask, render_template_string

app = Flask(__name__)

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Nuvola | Orbital Command</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&family=Share+Tech+Mono&display=swap');
        
        :root {
            --neon-green: #39ff14;
            --neon-pink: #ff00ff;
            --neon-blue: #00ffff;
            --neon-red: #ff073a;
            --neon-yellow: #faff00;
            --neon-purple: #9d00ff;
            --bg-dark: #050505;
            --panel-bg: rgba(10, 15, 20, 0.85);
            --grid-color: rgba(0, 255, 255, 0.07);
        }
        body {
            background-color: var(--bg-dark);
            color: var(--neon-green);
            font-family: 'Share Tech Mono', monospace;
            margin: 0;
            padding: 2vw;
            background-image: 
                linear-gradient(var(--grid-color) 1px, transparent 1px),
                linear-gradient(90deg, var(--grid-color) 1px, transparent 1px);
            background-size: 40px 40px;
            overflow-x: hidden;
        }
        
        /* CRT Overlay effect */
        body::after {
            content: " ";
            display: block;
            position: fixed;
            top: 0;
            left: 0;
            bottom: 0;
            right: 0;
            background: linear-gradient(rgba(18, 16, 16, 0) 50%, rgba(0, 0, 0, 0.25) 50%), linear-gradient(90deg, rgba(255, 0, 0, 0.06), rgba(0, 255, 0, 0.02), rgba(0, 0, 255, 0.06));
            z-index: 2;
            background-size: 100% 2px, 3px 100%;
            pointer-events: none;
        }
        
        /* Glitch Title */
        h1 { 
            text-align: center; 
            text-transform: uppercase; 
            letter-spacing: 12px; 
            font-size: 3em;
            font-family: 'Orbitron', sans-serif;
            font-weight: 900;
            color: #fff;
            text-shadow: 
                0 0 5px #fff,
                0 0 20px var(--neon-blue),
                0 0 40px var(--neon-blue),
                0 0 80px var(--neon-blue);
            margin-bottom: 50px;
            position: relative;
            z-index: 10;
        }
        
        .container { 
            display: grid; 
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); 
            gap: 40px; 
            max-width: 1600px; 
            margin: auto; 
            position: relative;
            z-index: 10;
        }
        
        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-blue);
            padding: 30px;
            border-radius: 4px;
            box-shadow: 
                0 0 20px rgba(0, 255, 255, 0.15),
                inset 0 0 30px rgba(0, 255, 255, 0.05);
            position: relative;
            backdrop-filter: blur(10px);
            overflow: hidden;
        }

        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; width: 100%; height: 3px;
            background: var(--neon-blue);
            box-shadow: 0 0 15px var(--neon-blue);
        }
        
        .panel.pink-panel { border-color: var(--neon-pink); box-shadow: 0 0 20px rgba(255, 0, 255, 0.15), inset 0 0 30px rgba(255, 0, 255, 0.05); }
        .panel.pink-panel::before { background: var(--neon-pink); box-shadow: 0 0 15px var(--neon-pink); }

        .panel.full-width { grid-column: 1 / -1; }
        
        .panel h2 {
            font-family: 'Orbitron', sans-serif;
            color: var(--neon-blue);
            border-bottom: 2px dashed rgba(0, 255, 255, 0.5);
            padding-bottom: 15px;
            text-shadow: 0 0 15px var(--neon-blue);
            margin-top: 0;
            font-size: 1.6em;
            letter-spacing: 3px;
            display: flex;
            align-items: center;
        }
        
        .panel.pink-panel h2 { color: var(--neon-pink); border-bottom-color: rgba(255, 0, 255, 0.5); text-shadow: 0 0 15px var(--neon-pink); }
        
        .squad-card {
            background: rgba(0, 0, 0, 0.5);
            border: 1px solid rgba(0, 255, 255, 0.3);
            margin: 20px 0;
            padding: 15px;
            border-left: 4px solid var(--neon-green);
            position: relative;
            transition: all 0.3s ease;
        }
        
        .squad-card:hover {
            background: rgba(0, 255, 255, 0.05);
            box-shadow: inset 0 0 15px rgba(0, 255, 255, 0.2);
            transform: translateX(5px);
        }

        .squad-card.trinity {
            border-color: rgba(255, 0, 255, 0.3);
            border-left: 4px solid var(--neon-purple);
        }
        .squad-card.trinity:hover {
            background: rgba(255, 0, 255, 0.05);
            box-shadow: inset 0 0 15px rgba(255, 0, 255, 0.2);
        }

        .squad-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
            font-weight: bold;
            font-size: 1.2em;
        }

        .trinity-header { color: var(--neon-pink); text-shadow: 0 0 10px var(--neon-pink); }

        .status-badge {
            font-size: 0.8em;
            padding: 3px 8px;
            border-radius: 2px;
            letter-spacing: 1px;
            animation: pulse-op 2s infinite;
        }

        .bg-green { background: rgba(57, 255, 20, 0.2); color: var(--neon-green); border: 1px solid var(--neon-green); }
        .bg-yellow { background: rgba(250, 255, 0, 0.2); color: var(--neon-yellow); border: 1px solid var(--neon-yellow); }
        .bg-purple { background: rgba(157, 0, 255, 0.2); color: var(--neon-purple); border: 1px solid var(--neon-purple); }

        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 10px;
            margin-top: 10px;
            font-size: 0.9em;
        }

        .metric-box {
            background: rgba(255, 255, 255, 0.03);
            padding: 8px;
            border: 1px dashed rgba(255, 255, 255, 0.1);
            text-align: center;
        }

        .metric-val {
            display: block;
            font-size: 1.3em;
            margin-top: 5px;
            font-weight: bold;
        }

        .val-green { color: var(--neon-green); text-shadow: 0 0 8px var(--neon-green); }
        .val-red { color: var(--neon-red); text-shadow: 0 0 8px var(--neon-red); }
        .val-blue { color: var(--neon-blue); text-shadow: 0 0 8px var(--neon-blue); }

        table { 
            width: 100%; 
            border-collapse: collapse; 
            margin-top: 25px; 
            background: rgba(0,0,0,0.4);
            border: 1px solid rgba(0,255,255,0.2);
        }
        
        th, td { 
            padding: 18px 15px; 
            text-align: left; 
            border-bottom: 1px solid rgba(0, 255, 255, 0.1);
        }
        
        th { 
            color: var(--neon-blue); 
            background-color: rgba(0, 255, 255, 0.1);
            text-transform: uppercase;
            letter-spacing: 2px;
            font-family: 'Orbitron', sans-serif;
            font-size: 0.9em;
        }
        
        tr:hover td { background-color: rgba(0, 255, 255, 0.08); }
        tr td:first-child { font-weight: bold; color: #fff; letter-spacing: 1px; }

        .terminal-box {
            background: #000;
            border: 1px solid #333;
            padding: 15px;
            margin-top: 20px;
            height: 150px;
            overflow: hidden;
            font-family: 'Share Tech Mono', monospace;
            color: #aaa;
            position: relative;
        }

        .terminal-box::before {
            content: "SYSTEM LOGS // DECRYPTING...";
            display: block;
            color: var(--neon-blue);
            margin-bottom: 10px;
            border-bottom: 1px solid #333;
            padding-bottom: 5px;
        }

        .log-line {
            margin: 5px 0;
            opacity: 0;
            animation: fadeIn 0.1s forwards;
        }

        .log-line:nth-child(1) { animation-delay: 0.5s; }
        .log-line:nth-child(2) { animation-delay: 1.2s; }
        .log-line:nth-child(3) { animation-delay: 2.1s; }
        .log-line:nth-child(4) { animation-delay: 2.8s; }
        .log-line:nth-child(5) { animation-delay: 3.5s; }

        @keyframes pulse-op { 0%, 100% { opacity: 1; } 50% { opacity: 0.6; } }
        @keyframes fadeIn { to { opacity: 1; } }

        /* Loader */
        .radar {
            position: absolute;
            top: 20px; right: 20px;
            width: 40px; height: 40px;
            border-radius: 50%;
            border: 1px solid var(--neon-blue);
            box-shadow: 0 0 10px var(--neon-blue);
            overflow: hidden;
        }
        .radar::before {
            content: '';
            position: absolute;
            top: 50%; left: 50%;
            width: 50%; height: 50%;
            background: conic-gradient(transparent 270deg, var(--neon-blue));
            transform-origin: 0 0;
            animation: radar-spin 2s linear infinite;
        }
        @keyframes radar-spin { 100% { transform: rotate(360deg); } }

    </style>
</head>
<body>
    <h1>🛰️ ORBITAL COMMAND 🛰️</h1>
    
    <div class="container">
        
        <!-- SEZIONE 1: SQUADRE D'ASSALTO -->
        <div class="panel">
            <div class="radar"></div>
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            
            <div class="squad-card">
                <div class="squad-header">
                    <span>⚡ SQUADRA_ALPHA <span style="font-size:0.7em; color:#888;">// Scalper Binance</span></span>
                    <span class="status-badge bg-green">SYS_ONLINE</span>
                </div>
                <div class="metrics-grid">
                    <div class="metric-box">EXEC LATENCY<span class="metric-val val-green">1.2ms</span></div>
                    <div class="metric-box">WIN RATE<span class="metric-val val-blue">68.4%</span></div>
                    <div class="metric-box">PnL 24h<span class="metric-val val-green">+3.42%</span></div>
                </div>
            </div>

            <div class="squad-card">
                <div class="squad-header">
                    <span>🌊 SQUADRA_DELTA <span style="font-size:0.7em; color:#888;">// Order Flow</span></span>
                    <span class="status-badge bg-green">READING TAPE</span>
                </div>
                <div class="metrics-grid">
                    <div class="metric-box">TAPE SPD<span class="metric-val val-blue">4.2k/s</span></div>
                    <div class="metric-box">IMBALANCE<span class="metric-val val-green">LONG</span></div>
                    <div class="metric-box">VWAP DEV<span class="metric-val val-red">-0.8%</span></div>
                </div>
            </div>

            <div class="squad-card" style="border-left-color: var(--neon-yellow);">
                <div class="squad-header">
                    <span>⚖️ SQUADRA_GAMMA <span style="font-size:0.7em; color:#888;">// Pairs Bitget</span></span>
                    <span class="status-badge bg-yellow">SYS_STANDBY</span>
                </div>
                <div class="metrics-grid">
                    <div class="metric-box">TARGET PAIR<span class="metric-val" style="color:#aaa;">BTC/ETH</span></div>
                    <div class="metric-box">CURR Z-SCORE<span class="metric-val val-yellow" style="color:var(--neon-yellow);">1.84</span></div>
                    <div class="metric-box">TRIGGER<span class="metric-val" style="color:#aaa;">> 2.0</span></div>
                </div>
            </div>
        </div>
        
        <!-- SEZIONE 2: PROTOCOLLO TRINITY -->
        <div class="panel pink-panel">
            <div class="radar" style="border-color: var(--neon-pink); box-shadow: 0 0 10px var(--neon-pink);">
                <style>.pink-panel .radar::before { background: conic-gradient(transparent 270deg, var(--neon-pink)); }</style>
            </div>
            <h2>🛡️ PROTOCOLLO TRINITY</h2>
            
            <div style="background: rgba(255,0,255,0.05); border: 1px solid var(--neon-pink); padding: 15px; margin-bottom: 20px; text-align: center; box-shadow: 0 0 15px rgba(255,0,255,0.2);">
                <span style="color: var(--neon-pink); font-family: 'Orbitron'; letter-spacing: 2px; font-weight: bold; text-shadow: 0 0 10px var(--neon-pink);">
                    ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
                </span>
            </div>

            <div class="squad-card trinity">
                <div class="squad-header trinity-header">
                    <span>🦇 LO STROZZINO <span style="font-size:0.7em; color:#888;">// Funding Arb</span></span>
                    <span class="status-badge bg-purple">ACTIVE</span>
                </div>
                <div class="metrics-grid">
                    <div class="metric-box">STRATEGY<span class="metric-val" style="color:#ddd;">Delta Ntrl</span></div>
                    <div class="metric-box">CURR APR<span class="metric-val val-green">18.5%</span></div>
                    <div class="metric-box">CAP DEPLOYED<span class="metric-val val-blue">$45.2K</span></div>
                </div>
            </div>

            <div class="squad-card trinity">
                <div class="squad-header trinity-header">
                    <span>🧮 IL CONTABILE <span style="font-size:0.7em; color:#888;">// Smart DCA</span></span>
                    <span class="status-badge bg-purple">ACTIVE</span>
                </div>
                <div class="metrics-grid">
                    <div class="metric-box">ASSET<span class="metric-val" style="color:#ddd;">BTC</span></div>
                    <div class="metric-box">AVG ENTRY<span class="metric-val val-blue">$65,210</span></div>
                    <div class="metric-box">NEXT BUY<span class="metric-val val-yellow">-4h 12m</span></div>
                </div>
            </div>

            <div class="squad-card trinity">
                <div class="squad-header trinity-header">
                    <span>👼 L'ANGELO CUSTODE <span style="font-size:0.7em; color:#888;">// MEV Arbitrum</span></span>
                    <span class="status-badge bg-purple">PROTECTING</span>
                </div>
                <div class="metrics-grid">
                    <div class="metric-box">NETWORK<span class="metric-val" style="color:#ddd;">Arbitrum</span></div>
                    <div class="metric-box">TX SAVED<span class="metric-val val-green">14</span></div>
                    <div class="metric-box">SLIPPAGE PRVNT<span class="metric-val val-green">+$420</span></div>
                </div>
            </div>
        </div>
        
        <!-- SEZIONE 3: METRICHE DI MERCATO -->
        <div class="panel full-width">
            <h2>🌐 GLOBAL SENSORS & METRICS (The Oracle & Whale Tracker)</h2>
            
            <table>
                <thead>
                    <tr>
                        <th>Asset Target</th>
                        <th>Sentiment (The Oracle)</th>
                        <th>Whale Flow (24h)</th>
                        <th>Liq. Heatmap</th>
                        <th>Algorithmic Signal</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>BTC/USDT</td>
                        <td><span style="color:var(--neon-green); text-shadow:0 0 8px var(--neon-green);">BULLISH [0.82] 🟢</span></td>
                        <td><span style="color:var(--neon-green);">▲ + 1,200 BTC Inflow</span></td>
                        <td>$67,500 (Heavy)</td>
                        <td><strong style="color:var(--neon-green);">LONG (Conf: 87%)</strong></td>
                    </tr>
                    <tr>
                        <td>ETH/USDT</td>
                        <td><span style="color:#fff; text-shadow:0 0 8px #fff;">NEUTRAL [0.51] ⚪</span></td>
                        <td><span style="color:var(--neon-red);">▼ - 300 ETH Outflow</span></td>
                        <td>$3,400 (Avg)</td>
                        <td><strong style="color:#aaa;">HOLD (Conf: 54%)</strong></td>
                    </tr>
                    <tr>
                        <td>SOL/USDT</td>
                        <td><span style="color:var(--neon-red); text-shadow:0 0 8px var(--neon-red);">EXTREME GREED [0.94] 🔴</span></td>
                        <td><span style="color:var(--neon-green);">▲ + 15,000 SOL Inflow</span></td>
                        <td>$185.00 (Danger)</td>
                        <td><strong style="color:var(--neon-red);">SHORT SCALP (Conf: 92%)</strong></td>
                    </tr>
                    <tr>
                        <td>INJ/USDT</td>
                        <td><span style="color:var(--neon-green); text-shadow:0 0 8px var(--neon-green);">ACCUMULATION [0.72] 🟢</span></td>
                        <td><span style="color:var(--neon-green);">▲ + 45,000 INJ Inflow</span></td>
                        <td>$32.50 (Light)</td>
                        <td><strong style="color:var(--neon-green);">SPOT DCA (Conf: 78%)</strong></td>
                    </tr>
                </tbody>
            </table>

            <div class="terminal-box">
                <div class="log-line">[SYS] Connecting to secure socket... OK</div>
                <div class="log-line">[ORACLE] Ingesting 14.2M tweets & news articles... DONE</div>
                <div class="log-line">[WHALE_TRACKER] Parsing mempool for anomalous Tx sizes > 1000 BTC... SCANNING</div>
                <div class="log-line">[HFT_ENGINE] Updating latency matrices... Ping to Binance API: 1.15ms</div>
                <div class="log-line">[TRINITY] L'Angelo Custode successfully routed transaction via private RPC.</div>
            </div>
        </div>

    </div>

    <script>
        // Simple matrix raining code effect background
        const canvas = document.createElement('canvas');
        canvas.style.position = 'fixed';
        canvas.style.top = '0';
        canvas.style.left = '0';
        canvas.style.width = '100vw';
        canvas.style.height = '100vh';
        canvas.style.zIndex = '-1';
        canvas.style.opacity = '0.05';
        document.body.appendChild(canvas);

        const ctx = canvas.getContext('2d');
        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;

        const letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789@#$%^&*';
        const fontSize = 14;
        const columns = canvas.width / fontSize;
        const drops = Array(Math.floor(columns)).fill(1);

        function draw() {
            ctx.fillStyle = 'rgba(0, 0, 0, 0.05)';
            ctx.fillRect(0, 0, canvas.width, canvas.height);
            ctx.fillStyle = '#0f0';
            ctx.font = fontSize + 'px monospace';

            for (let i = 0; i < drops.length; i++) {
                const text = letters[Math.floor(Math.random() * letters.length)];
                ctx.fillText(text, i * fontSize, drops[i] * fontSize);
                if (drops[i] * fontSize > canvas.height && Math.random() > 0.975) {
                    drops[i] = 0;
                }
                drops[i]++;
            }
        }
        setInterval(draw, 50);
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
