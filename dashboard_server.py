from flask import Flask, render_template_string
import os

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NUVOLA ORBITAL COMMAND</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');

        :root {
            --bg-color: #020202;
            --neon-green: #39ff14;
            --neon-blue: #00f3ff;
            --neon-pink: #ff003c;
            --neon-yellow: #fcee0a;
            --panel-bg: rgba(5, 5, 10, 0.85);
            --border-glow: 0 0 10px;
        }

        * {
            box-sizing: border-box;
        }

        body {
            background-color: var(--bg-color);
            color: var(--neon-blue);
            font-family: 'Share Tech Mono', monospace;
            margin: 0;
            padding: 20px;
            background-image: 
                linear-gradient(rgba(0, 243, 255, 0.03) 1px, transparent 1px),
                linear-gradient(90deg, rgba(0, 243, 255, 0.03) 1px, transparent 1px);
            background-size: 40px 40px;
            overflow-x: hidden;
        }

        /* Scanline Overlay */
        body::after {
            content: " ";
            display: block;
            position: fixed;
            top: 0;
            left: 0;
            bottom: 0;
            right: 0;
            background: linear-gradient(
                to bottom,
                rgba(18, 16, 16, 0) 50%,
                rgba(0, 0, 0, 0.25) 50%
            );
            background-size: 100% 4px;
            z-index: 9999;
            pointer-events: none;
        }

        h1, h2, h3 {
            text-transform: uppercase;
            margin: 0 0 15px 0;
        }

        .header {
            text-align: center;
            border-bottom: 2px solid var(--neon-blue);
            box-shadow: 0 5px 15px rgba(0, 243, 255, 0.2);
            padding-bottom: 15px;
            margin-bottom: 30px;
            animation: textFlicker 3s infinite alternate;
        }

        .header h1 {
            color: var(--neon-green);
            text-shadow: 0 0 10px var(--neon-green), 0 0 20px var(--neon-green);
            font-size: 2.5em;
            letter-spacing: 5px;
        }

        .header p {
            color: var(--neon-pink);
            font-size: 1.2em;
            letter-spacing: 2px;
            text-shadow: 0 0 5px var(--neon-pink);
        }

        .dashboard-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
            max-width: 1400px;
            margin: 0 auto;
        }

        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-blue);
            box-shadow: inset 0 0 20px rgba(0, 243, 255, 0.1), 0 0 15px rgba(0, 243, 255, 0.2);
            padding: 20px;
            position: relative;
            overflow: hidden;
        }

        .panel::before {
            content: '';
            position: absolute;
            top: 0;
            left: -100%;
            width: 50%;
            height: 2px;
            background: var(--neon-blue);
            box-shadow: 0 0 15px var(--neon-blue);
            animation: scan 4s linear infinite;
        }

        .panel.danger {
            border-color: var(--neon-pink);
            box-shadow: inset 0 0 20px rgba(255, 0, 60, 0.1), 0 0 15px rgba(255, 0, 60, 0.2);
        }
        .panel.danger h2 { color: var(--neon-pink); text-shadow: 0 0 10px var(--neon-pink); border-bottom: 1px solid var(--neon-pink); }
        .panel.danger::before { background: var(--neon-pink); box-shadow: 0 0 15px var(--neon-pink); }

        .panel.warning {
            border-color: var(--neon-yellow);
            box-shadow: inset 0 0 20px rgba(252, 238, 10, 0.1), 0 0 15px rgba(252, 238, 10, 0.2);
        }
        .panel.warning h2 { color: var(--neon-yellow); text-shadow: 0 0 10px var(--neon-yellow); border-bottom: 1px solid var(--neon-yellow); }
        .panel.warning::before { background: var(--neon-yellow); box-shadow: 0 0 15px var(--neon-yellow); }

        .panel.success h2 { color: var(--neon-green); text-shadow: 0 0 10px var(--neon-green); border-bottom: 1px solid var(--neon-green); }

        h2 {
            font-size: 1.4em;
            padding-bottom: 10px;
            border-bottom: 1px solid var(--neon-blue);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        /* Tables & Lists */
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
        }
        th, td {
            padding: 10px 5px;
            text-align: left;
            border-bottom: 1px solid rgba(0, 243, 255, 0.2);
        }
        th {
            color: rgba(255, 255, 255, 0.7);
            font-size: 0.9em;
        }
        tr:hover {
            background: rgba(0, 243, 255, 0.1);
        }

        .status {
            font-weight: bold;
            animation: pulse 2s infinite;
        }
        .status.online { color: var(--neon-green); text-shadow: 0 0 5px var(--neon-green); }
        .status.active { color: var(--neon-blue); text-shadow: 0 0 5px var(--neon-blue); }
        .status.standby { color: var(--neon-yellow); text-shadow: 0 0 5px var(--neon-yellow); }

        .trinity-card {
            border-left: 3px solid var(--neon-pink);
            background: rgba(255, 0, 60, 0.05);
            padding: 15px;
            margin-bottom: 15px;
            position: relative;
        }
        .trinity-card:last-child { margin-bottom: 0; }
        .trinity-card h3 {
            color: var(--neon-pink);
            font-size: 1.1em;
            margin-bottom: 5px;
        }
        .trinity-card .badge {
            position: absolute;
            top: 15px;
            right: 15px;
            font-size: 0.8em;
            border: 1px solid var(--neon-green);
            color: var(--neon-green);
            padding: 2px 5px;
            border-radius: 3px;
        }

        .metrics-wrapper {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
        }
        .metric-box {
            background: rgba(0, 0, 0, 0.5);
            border: 1px solid rgba(0, 243, 255, 0.3);
            padding: 15px;
            text-align: center;
            transition: all 0.3s ease;
        }
        .metric-box:hover {
            border-color: var(--neon-blue);
            box-shadow: inset 0 0 10px rgba(0, 243, 255, 0.2);
        }
        .metric-label {
            font-size: 0.8em;
            color: rgba(255, 255, 255, 0.6);
            margin-bottom: 5px;
            letter-spacing: 1px;
        }
        .metric-value {
            font-size: 1.5em;
            font-weight: bold;
            color: var(--neon-blue);
            text-shadow: 0 0 8px var(--neon-blue);
        }
        .metric-value.up { color: var(--neon-green); text-shadow: 0 0 8px var(--neon-green); }
        .metric-value.down { color: var(--neon-pink); text-shadow: 0 0 8px var(--neon-pink); }

        /* Animations */
        @keyframes scan {
            0% { left: -50%; }
            100% { left: 150%; }
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.6; }
        }
        @keyframes textFlicker {
            0%, 19%, 21%, 23%, 25%, 54%, 56%, 100% { opacity: 1; }
            20%, 22%, 24%, 55% { opacity: 0.5; }
        }

        .progress-bar {
            width: 100%;
            height: 4px;
            background: #222;
            margin-top: 5px;
            position: relative;
            overflow: hidden;
        }
        .progress-fill {
            height: 100%;
            background: var(--neon-blue);
            box-shadow: 0 0 5px var(--neon-blue);
            width: 0%;
        }

        .footer {
            text-align: center;
            margin-top: 40px;
            padding: 20px;
            border-top: 1px dashed rgba(0, 243, 255, 0.3);
            font-size: 0.85em;
            color: rgba(255, 255, 255, 0.5);
        }
    </style>
</head>
<body>

    <div class="header">
        <h1>🛰️ NUVOLA ORBITAL COMMAND 🛰️</h1>
        <p>[ SISTEMA CENTRALE DI CONTROLLO QUANTITATIVO ]</p>
        <div style="margin-top: 15px; font-size: 1.2em; color: var(--neon-green); text-shadow: 0 0 10px var(--neon-green); border: 1px solid var(--neon-green); display: inline-block; padding: 10px 20px; border-radius: 5px; background: rgba(57, 255, 20, 0.1);">
            ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
        </div>
    </div>

    <div class="dashboard-grid">

        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel success">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT) <span class="status online">[ACTIVE]</span></h2>
            <table>
                <thead>
                    <tr>
                        <th>UNITÀ</th>
                        <th>STRATEGIA</th>
                        <th>STATO</th>
                        <th>P&L (24h)</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>🐺 SQUADRA_ALPHA</td>
                        <td>Binance Scalper</td>
                        <td><span class="status online">ENGAGED</span></td>
                        <td class="status online">+4.2%</td>
                    </tr>
                    <tr>
                        <td>🦅 SQUADRA_DELTA</td>
                        <td>Order Flow</td>
                        <td><span class="status active">MONITORING</span></td>
                        <td class="status active">+1.8%</td>
                    </tr>
                    <tr>
                        <td>🐍 SQUADRA_GAMMA</td>
                        <td>Bitget Pairs</td>
                        <td><span class="status standby">ARBITRAGE</span></td>
                        <td class="status online">+2.5%</td>
                    </tr>
                </tbody>
            </table>
            <div style="margin-top: 15px;">
                <div class="metric-label">SYS.LOAD (ALPHA)</div>
                <div class="progress-bar"><div class="progress-fill" style="width: 85%; background: var(--neon-green);"></div></div>
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel danger">
            <h2>🔮 PROTOCOLLO TRINITY <span class="status active">[BACKGROUND]</span></h2>
            
            <div class="trinity-card">
                <span class="badge">RUNNING</span>
                <h3>🕴️ Lo Strozzino (Funding Arb)</h3>
                <div class="metric-label">Target: Binance / Bybit | APY: <span style="color:var(--neon-green)">18.4%</span></div>
                <div class="progress-bar"><div class="progress-fill" style="width: 100%; background: var(--neon-pink);"></div></div>
            </div>

            <div class="trinity-card">
                <span class="badge">RUNNING</span>
                <h3>🧮 Il Contabile (DCA)</h3>
                <div class="metric-label">Target: BTC/ETH | Fase: Accumulo Strategico</div>
                <div class="progress-bar"><div class="progress-fill" style="width: 45%; background: var(--neon-pink);"></div></div>
            </div>

            <div class="trinity-card">
                <span class="badge">RUNNING</span>
                <h3>👼 L'Angelo Custode (MEV Arbitrum)</h3>
                <div class="metric-label">Target: Mempool | Protezione Frontrun Attiva</div>
                <div class="progress-bar"><div class="progress-fill" style="width: 100%; background: var(--neon-pink);"></div></div>
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel warning" style="grid-column: 1 / -1;">
            <h2>📊 METRICHE DI MERCATO (ORACLE & WHALE TRACKER) <span class="status active">[LIVE SYNC]</span></h2>
            <div class="metrics-wrapper" style="grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));">
                
                <div class="metric-box">
                    <div class="metric-label">👁️ THE ORACLE (BINANCE)</div>
                    <div class="metric-value up">BULLISH 78%</div>
                    <div class="metric-label" style="margin-top: 5px;">Sentiment Score</div>
                </div>

                <div class="metric-box">
                    <div class="metric-label">🐋 WHALE TRACKER (1H)</div>
                    <div class="metric-value down">-1,450 BTC</div>
                    <div class="metric-label" style="margin-top: 5px;">Netflow Out</div>
                </div>

                <div class="metric-box">
                    <div class="metric-label">⚡ VOLATILITÀ SISTEMA</div>
                    <div class="metric-value down">ELEVATA</div>
                    <div class="metric-label" style="margin-top: 5px;">[CRITICAL] VIX Proxy</div>
                </div>

                <div class="metric-box">
                    <div class="metric-label">🛡️ LIQUIDITÀ SCUDO</div>
                    <div class="metric-value up">1.2M USDT</div>
                    <div class="metric-label" style="margin-top: 5px;">Reserva Tattica</div>
                </div>

                <div class="metric-box">
                    <div class="metric-label">📡 LATTENZA RETE</div>
                    <div class="metric-value">12ms</div>
                    <div class="metric-label" style="margin-top: 5px;">Ping to Binance (Tokyo)</div>
                </div>
                
            </div>
        </div>

    </div>

    <div class="footer">
        [ SYS.UPTIME: 99.99% ] | [ SECURE.CONNECTION: ESTABLISHED ] | [ ENCRYPTION: AES-256-GCM ] <br>
        > WAITING FOR COMMAND INPUT..._
    </div>

    <script>
        // Fake dynamic updates for immersion
        setInterval(() => {
            const progressBars = document.querySelectorAll('.progress-fill:not([style*="100%"])');
            progressBars.forEach(bar => {
                let current = parseInt(bar.style.width) || 0;
                current = (current + Math.random() * 5) % 100;
                bar.style.width = current + '%';
            });
        }, 2000);
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    # Production-ready tweak for simple local dashboard
    app.run(host='0.0.0.0', port=port)
