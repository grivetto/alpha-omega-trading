from flask import Flask, render_template_string
import random
from datetime import datetime

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ORBITAL COMMAND // NUVOLA</title>
    <style>
        :root {
            --bg-color: #050505;
            --panel-bg: rgba(10, 15, 20, 0.85);
            --neon-cyan: #00f3ff;
            --neon-magenta: #ff00ff;
            --neon-lime: #39ff14;
            --neon-red: #ff2a2a;
            --neon-yellow: #ffeb3b;
            --text-main: #e0e0e0;
            --text-muted: #888888;
            --font-mono: 'Courier New', Courier, monospace;
        }

        body {
            background-color: var(--bg-color);
            color: var(--text-main);
            font-family: var(--font-mono);
            margin: 0;
            padding: 20px;
            background-image: 
                linear-gradient(rgba(0, 243, 255, 0.03) 1px, transparent 1px),
                linear-gradient(90deg, rgba(0, 243, 255, 0.03) 1px, transparent 1px);
            background-size: 20px 20px;
            overflow-x: hidden;
        }

        /* CRT Effect */
        body::after {
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

        h1, h2, h3 {
            text-transform: uppercase;
            letter-spacing: 2px;
            margin-top: 0;
        }

        .header {
            text-align: center;
            padding: 20px;
            border-bottom: 2px solid var(--neon-cyan);
            box-shadow: 0 0 15px var(--neon-cyan);
            margin-bottom: 30px;
            position: relative;
            background: linear-gradient(90deg, transparent, rgba(0, 243, 255, 0.1), transparent);
        }

        .header h1 {
            color: var(--neon-cyan);
            text-shadow: 0 0 10px var(--neon-cyan), 0 0 20px var(--neon-cyan);
            animation: glitch 3s infinite;
        }

        .dashboard-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 25px;
            position: relative;
            z-index: 3;
        }

        .panel {
            background-color: var(--panel-bg);
            border: 1px solid var(--text-muted);
            padding: 20px;
            border-radius: 5px;
            box-shadow: 0 0 10px rgba(0,0,0,0.5);
            position: relative;
            overflow: hidden;
        }

        .panel::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 2px;
        }

        .panel.assault { border-color: var(--neon-red); box-shadow: inset 0 0 10px rgba(255, 42, 42, 0.1), 0 0 10px rgba(255, 42, 42, 0.2); }
        .panel.assault::before { background-color: var(--neon-red); box-shadow: 0 0 10px var(--neon-red); }
        .panel.assault h2 { color: var(--neon-red); text-shadow: 0 0 5px var(--neon-red); }

        .panel.trinity { border-color: var(--neon-magenta); box-shadow: inset 0 0 10px rgba(255, 0, 255, 0.1), 0 0 10px rgba(255, 0, 255, 0.2); }
        .panel.trinity::before { background-color: var(--neon-magenta); box-shadow: 0 0 10px var(--neon-magenta); }
        .panel.trinity h2 { color: var(--neon-magenta); text-shadow: 0 0 5px var(--neon-magenta); }

        .panel.metrics { border-color: var(--neon-lime); box-shadow: inset 0 0 10px rgba(57, 255, 20, 0.1), 0 0 10px rgba(57, 255, 20, 0.2); }
        .panel.metrics::before { background-color: var(--neon-lime); box-shadow: 0 0 10px var(--neon-lime); }
        .panel.metrics h2 { color: var(--neon-lime); text-shadow: 0 0 5px var(--neon-lime); }

        .status-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 10px 0;
            border-bottom: 1px dashed var(--text-muted);
        }

        .status-row:last-child {
            border-bottom: none;
        }

        .badge {
            padding: 4px 8px;
            font-size: 0.8em;
            font-weight: bold;
            border-radius: 3px;
            text-transform: uppercase;
        }
        
        .badge.online { background-color: rgba(57, 255, 20, 0.2); color: var(--neon-lime); border: 1px solid var(--neon-lime); }
        .badge.standby { background-color: rgba(255, 235, 59, 0.2); color: var(--neon-yellow); border: 1px solid var(--neon-yellow); }
        .badge.active { background-color: rgba(0, 243, 255, 0.2); color: var(--neon-cyan); border: 1px solid var(--neon-cyan); animation: pulse 2s infinite; }

        .data-value {
            font-weight: bold;
            font-size: 1.1em;
        }

        .positive { color: var(--neon-lime); }
        .negative { color: var(--neon-red); }
        .neutral { color: var(--neon-cyan); }

        /* Animations */
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.6; box-shadow: 0 0 10px currentColor; }
            100% { opacity: 1; }
        }

        @keyframes glitch {
            0% { text-shadow: 0.05em 0 0 #00fffc, -0.03em -0.04em 0 #fc00ff, 0.025em 0.04em 0 #fffc00; }
            15% { text-shadow: 0.05em 0 0 #00fffc, -0.03em -0.04em 0 #fc00ff, 0.025em 0.04em 0 #fffc00; }
            16% { text-shadow: -0.05em -0.025em 0 #00fffc, 0.025em 0.035em 0 #fc00ff, -0.05em -0.05em 0 #fffc00; }
            49% { text-shadow: -0.05em -0.025em 0 #00fffc, 0.025em 0.035em 0 #fc00ff, -0.05em -0.05em 0 #fffc00; }
            50% { text-shadow: 0.05em 0.035em 0 #00fffc, 0.03em 0 0 #fc00ff, 0 -0.04em 0 #fffc00; }
            99% { text-shadow: 0.05em 0.035em 0 #00fffc, 0.03em 0 0 #fc00ff, 0 -0.04em 0 #fffc00; }
            100% { text-shadow: -0.025em 0 0 #00fffc, -0.025em -0.025em 0 #fc00ff, -0.025em -0.05em 0 #fffc00; }
        }

        .blink {
            animation: blinker 1s linear infinite;
        }

        @keyframes blinker {
            50% { opacity: 0; }
        }
        
        .footer {
            margin-top: 40px;
            text-align: center;
            font-size: 0.8em;
            color: var(--text-muted);
            border-top: 1px solid #333;
            padding-top: 10px;
        }

    </style>
</head>
<body>

    <div class="header">
        <h1>NUVOLA // ORBITAL COMMAND</h1>
        <p>SYSTEM STATUS: <span class="neon-cyan blink">ENGAGED</span> | UPTIME: {{ uptime }} | SECURE CONNECTION</p>
    </div>

    <div style="text-align: center; margin-bottom: 20px; font-weight: bold; color: var(--neon-magenta); border: 1px dashed var(--neon-magenta); padding: 10px; background-color: rgba(255, 0, 255, 0.1); text-shadow: 0 0 5px var(--neon-magenta);">
        ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
    </div>

    <div class="dashboard-grid">
        
        <!-- SQUADRE D'ASSALTO -->
        <div class="panel assault">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <div class="status-row">
                <div>
                    <strong>SQUADRA_ALPHA</strong><br>
                    <span style="font-size: 0.8em; color: var(--text-muted);">Binance Scalper</span>
                </div>
                <div style="text-align: right;">
                    <span class="badge active">ENGAGED</span><br>
                    <span class="data-value positive">+1.24% <small>1H</small></span>
                </div>
            </div>
            <div class="status-row">
                <div>
                    <strong>SQUADRA_DELTA</strong><br>
                    <span style="font-size: 0.8em; color: var(--text-muted);">Order Flow Analysis</span>
                </div>
                <div style="text-align: right;">
                    <span class="badge online">MONITORING</span><br>
                    <span class="data-value neutral">FLAT</span>
                </div>
            </div>
            <div class="status-row">
                <div>
                    <strong>SQUADRA_GAMMA</strong><br>
                    <span style="font-size: 0.8em; color: var(--text-muted);">Pairs Trading (Bitget)</span>
                </div>
                <div style="text-align: right;">
                    <span class="badge active">ARBITRAGE</span><br>
                    <span class="data-value positive">+0.85% <small>1H</small></span>
                </div>
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel trinity">
            <h2>🔺 PROTOCOLLO TRINITY</h2>
            <div class="status-row">
                <div>
                    <strong>Lo Strozzino</strong> 🎩<br>
                    <span style="font-size: 0.8em; color: var(--text-muted);">Funding Rate Arbitrage</span>
                </div>
                <div style="text-align: right;">
                    <span class="badge online">ONLINE (BG)</span><br>
                    <span class="data-value positive">APR: 18.4%</span>
                </div>
            </div>
            <div class="status-row">
                <div>
                    <strong>Il Contabile</strong> 🧮<br>
                    <span style="font-size: 0.8em; color: var(--text-muted);">Dynamic DCA Module</span>
                </div>
                <div style="text-align: right;">
                    <span class="badge online">ONLINE (BG)</span><br>
                    <span class="data-value neutral">NEXT: 4h 12m</span>
                </div>
            </div>
            <div class="status-row">
                <div>
                    <strong>L'Angelo Custode</strong> 🛡️<br>
                    <span style="font-size: 0.8em; color: var(--text-muted);">MEV Protection (Arbitrum)</span>
                </div>
                <div style="text-align: right;">
                    <span class="badge standby">PATROLLING</span><br>
                    <span class="data-value neutral">TXs Shielded: 142</span>
                </div>
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel metrics">
            <h2>👁️ METRICHE DI MERCATO</h2>
            <div class="status-row">
                <div>
                    <strong>The Oracle</strong> 🔮<br>
                    <span style="font-size: 0.8em; color: var(--text-muted);">Binance Global Sentiment</span>
                </div>
                <div style="text-align: right;">
                    <span class="badge active">ANALYZING</span><br>
                    <span class="data-value positive">BULLISH (68%)</span>
                </div>
            </div>
            <div class="status-row">
                <div>
                    <strong>Whale Tracker</strong> 🐋<br>
                    <span style="font-size: 0.8em; color: var(--text-muted);">Large TXs On-Chain</span>
                </div>
                <div style="text-align: right;">
                    <span class="badge online">SCANNING</span><br>
                    <span class="data-value negative">INFLOW DETECTED</span>
                </div>
            </div>
            <div class="status-row">
                <div>
                    <strong>Liquidity Heatmap</strong> 🌡️<br>
                    <span style="font-size: 0.8em; color: var(--text-muted);">Orderbook Density</span>
                </div>
                <div style="text-align: right;">
                    <span class="data-value neutral">CLUSTER @ $69,420</span>
                </div>
            </div>
        </div>

    </div>

    <div class="footer">
        ORBITAL COMMAND NETWORK PROTOCOL V3.1 // CLASSIFIED // DATA REFRESH: LIVE
    </div>

    <script>
        // Fake dynamic updates to make it look alive
        setInterval(() => {
            const values = document.querySelectorAll('.positive, .negative');
            values.forEach(el => {
                if(Math.random() > 0.7 && el.innerText.includes('%')) {
                    let current = parseFloat(el.innerText.match(/[-+]?[0-9]*\.?[0-9]+/)[0]);
                    let change = (Math.random() * 0.1) - 0.05;
                    let newVal = (current + change).toFixed(2);
                    let prefix = newVal >= 0 ? '+' : '';
                    el.innerText = `${prefix}${newVal}% 1H`;
                }
            });
        }, 3000);
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    now = datetime.now()
    uptime_str = f"{now.hour:02d}H:{now.minute:02d}M:{now.second:02d}S"
    return render_template_string(HTML_TEMPLATE, uptime=uptime_str)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
