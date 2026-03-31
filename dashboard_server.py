from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ORBITAL COMMAND | NUVOLA</title>
    <style>
        :root {
            --bg: #050505;
            --neon-green: #39ff14;
            --neon-blue: #00f3ff;
            --neon-red: #ff003c;
            --neon-purple: #b026ff;
            --panel-bg: rgba(10, 10, 15, 0.85);
            --border-glow: 0 0 10px rgba(0, 243, 255, 0.3);
        }
        body {
            background-color: var(--bg);
            color: var(--neon-green);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            background-image: linear-gradient(rgba(0, 243, 255, 0.05) 1px, transparent 1px),
            linear-gradient(90deg, rgba(0, 243, 255, 0.05) 1px, transparent 1px);
            background-size: 20px 20px;
        }
        h1, h2, h3 {
            text-transform: uppercase;
            letter-spacing: 2px;
            text-shadow: 0 0 5px var(--neon-green);
            margin-top: 0;
        }
        h1 { color: var(--neon-blue); text-shadow: 0 0 15px var(--neon-blue); text-align: center; }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }
        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-blue);
            box-shadow: var(--border-glow);
            padding: 20px;
            border-radius: 5px;
            position: relative;
            overflow: hidden;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; height: 3px;
            background: var(--neon-blue);
            box-shadow: 0 0 15px var(--neon-blue);
        }
        .panel.red::before { background: var(--neon-red); box-shadow: 0 0 15px var(--neon-red); }
        .panel.purple::before { background: var(--neon-purple); box-shadow: 0 0 15px var(--neon-purple); }
        
        .status-online { color: var(--neon-green); text-shadow: 0 0 5px var(--neon-green); font-weight: bold;}
        .status-active { color: var(--neon-blue); text-shadow: 0 0 5px var(--neon-blue); font-weight: bold; animation: pulse 1.5s infinite;}
        .status-warning { color: var(--neon-red); text-shadow: 0 0 5px var(--neon-red); font-weight: bold; animation: pulse 0.5s infinite;}
        
        @keyframes pulse {
            0% { opacity: 0.7; }
            50% { opacity: 1; }
            100% { opacity: 0.7; }
        }
        
        .metric { display: flex; justify-content: space-between; margin-bottom: 12px; border-bottom: 1px dashed rgba(57, 255, 20, 0.3); padding-bottom: 4px; font-size: 0.95em;}
        .metric:last-child { border-bottom: none; }
        .value { font-weight: bold; }
        .up { color: var(--neon-green); }
        .down { color: var(--neon-red); }
        
        .glitch-wrapper { text-align: center; margin-bottom: 30px; border-bottom: 1px solid var(--neon-blue); padding-bottom: 20px; }
        .glitch { font-size: 3em; font-weight: bold; position: relative; display: inline-block; margin-bottom: 10px;}
        .terminal-header { color: #fff; opacity: 0.7; font-size: 0.8em; margin-bottom: 20px; }
    </style>
</head>
<body>
    <div class="terminal-header">
        root@nuvola:~/orbital_command# ./dashboard.sh<br>
        [INIT] Booting Nuvola Command Center... OK<br>
        [INIT] Connecting to exchange APIs... OK
    </div>
    <div class="glitch-wrapper">
        <h1 class="glitch">🌐 ORBITAL COMMAND 🌐</h1>
        <div>SYSTEM STATUS: <span class="status-active">ONLINE & OPERATIONAL</span> | UPTIME: 99.99%</div>
        <div style="margin-top: 15px; padding: 10px; border: 1px dashed var(--neon-purple); color: var(--neon-purple); text-shadow: 0 0 5px var(--neon-purple); display: inline-block;">
            ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
        </div>
    </div>

    <div class="grid">
        <!-- SQUADRE D'ASSALTO -->
        <div class="panel red" style="border-color: var(--neon-red);">
            <h2 style="color: var(--neon-red); text-shadow: 0 0 10px var(--neon-red);">⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <div class="metric">
                <span>🐺 SQUADRA_ALPHA (Binance Scalper)</span>
                <span class="status-active">[ ENGAGED ]</span>
            </div>
            <div class="metric">
                <span>> 1h Win Rate:</span>
                <span class="value up">68.4%</span>
            </div>
            <div class="metric">
                <span>> Open Positions:</span>
                <span class="value">4 (BTC, SOL, INJ, RNDR)</span>
            </div>
            <br>
            <div class="metric">
                <span>🦅 SQUADRA_DELTA (Order Flow)</span>
                <span class="status-active">[ SCANNING ]</span>
            </div>
            <div class="metric">
                <span>> Imbalance Target:</span>
                <span class="value down">BTC/USDT Short</span>
            </div>
            <br>
            <div class="metric">
                <span>🐍 SQUADRA_GAMMA (Bitget Pairs)</span>
                <span class="status-online">[ STANDBY ]</span>
            </div>
            <div class="metric">
                <span>> Monitored Spread (BTC/ETH):</span>
                <span class="value">0.0521</span>
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel purple" style="border-color: var(--neon-purple);">
            <h2 style="color: var(--neon-purple); text-shadow: 0 0 10px var(--neon-purple);">👁️ PROTOCOLLO TRINITY</h2>
            <div class="metric">
                <span>🦇 Lo Strozzino (Funding Arb)</span>
                <span class="status-active">[ ACTIVE ]</span>
            </div>
            <div class="metric">
                <span>> Current Yield est. (APR):</span>
                <span class="value up">18.2%</span>
            </div>
            <div class="metric">
                <span>> Delta Neutral Exposure:</span>
                <span class="value">$12,500</span>
            </div>
            <br>
            <div class="metric">
                <span>🧮 Il Contabile (DCA)</span>
                <span class="status-active">[ ACTIVE ]</span>
            </div>
            <div class="metric">
                <span>> Next Buy Cycle in:</span>
                <span class="value">04:12:05</span>
            </div>
            <br>
            <div class="metric">
                <span>🛡️ L'Angelo Custode (MEV Arb)</span>
                <span class="status-active">[ ACTIVE ]</span>
            </div>
            <div class="metric">
                <span>> Chain:</span>
                <span class="value">Arbitrum One</span>
            </div>
            <div class="metric">
                <span>> Frontruns prevented:</span>
                <span class="value up">14</span>
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <h2 style="color: var(--neon-blue); text-shadow: 0 0 10px var(--neon-blue);">📡 METRICHE DI MERCATO</h2>
            <div class="metric">
                <span>🔮 THE ORACLE (Binance Sentiment)</span>
                <span class="status-active">[ ANALYZING ]</span>
            </div>
            <div class="metric">
                <span>> Fear & Greed Index:</span>
                <span class="value">78 (EXTREME GREED)</span>
            </div>
            <div class="metric">
                <span>> Long/Short Ratio:</span>
                <span class="value up">1.45</span>
            </div>
            <br>
            <div class="metric">
                <span>🐳 WHALE TRACKER</span>
                <span class="status-active">[ LISTENING ]</span>
            </div>
            <div class="metric">
                <span>> Large Tx (15m):</span>
                <span class="status-warning">⚠️ $45.2M BTC MOVED</span>
            </div>
            <div class="metric">
                <span>> Exchange Netflow (24h):</span>
                <span class="value down">-1200 BTC (Outflow)</span>
            </div>
            <div class="metric">
                <span>> Stablecoin Minting:</span>
                <span class="value up">+$100M (Tether)</span>
            </div>
        </div>
    </div>
    
    <script>
        // Fake data flickering to simulate live quantitative analysis
        setInterval(() => {
            const values = document.querySelectorAll('.value.up, .value.down');
            if (values.length > 0) {
                const el = values[Math.floor(Math.random() * values.length)];
                el.style.opacity = '0.3';
                setTimeout(() => el.style.opacity = '1', 150);
            }
        }, 1500);
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
