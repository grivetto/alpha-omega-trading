from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <title>ORBITAL COMMAND | Nuvola</title>
    <style>
        :root {
            --bg: #050505;
            --neon-cyan: #0ff;
            --neon-pink: #f0f;
            --neon-green: #0f0;
            --neon-red: #f00;
            --neon-yellow: #ff0;
            --text-main: #d0d0d0;
            --panel-bg: rgba(5, 10, 15, 0.85);
            --grid-line: rgba(0, 255, 255, 0.1);
        }
        * { box-sizing: border-box; }
        body {
            background-color: var(--bg);
            color: var(--text-main);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            background-image: 
                linear-gradient(var(--grid-line) 1px, transparent 1px),
                linear-gradient(90deg, var(--grid-line) 1px, transparent 1px);
            background-size: 40px 40px;
            overflow-x: hidden;
            font-size: 14px;
        }
        
        /* Scanline Overlay */
        .scanlines {
            position: fixed;
            top: 0; left: 0; width: 100vw; height: 100vh;
            background: linear-gradient(to bottom, rgba(255,255,255,0), rgba(255,255,255,0) 50%, rgba(0,0,0,0.1) 50%, rgba(0,0,0,0.1));
            background-size: 100% 4px;
            pointer-events: none;
            z-index: 999;
        }

        h1 {
            text-align: center;
            color: var(--neon-cyan);
            text-shadow: 0 0 5px var(--neon-cyan), 0 0 15px var(--neon-cyan);
            font-size: 3em;
            letter-spacing: 10px;
            text-transform: uppercase;
            margin: 20px 0 40px 0;
            animation: textGlitch 3s infinite;
        }
        
        .sys-status {
            display: flex;
            justify-content: center;
            gap: 20px;
            margin-bottom: 30px;
        }
        .sys-badge {
            padding: 10px 20px;
            border: 1px solid;
            background: rgba(0,0,0,0.6);
            font-weight: bold;
            text-transform: uppercase;
            letter-spacing: 2px;
            box-shadow: inset 0 0 10px rgba(0,0,0,0.8);
        }
        .sys-badge.cyan { border-color: var(--neon-cyan); color: var(--neon-cyan); text-shadow: 0 0 8px var(--neon-cyan); box-shadow: 0 0 10px rgba(0,255,255,0.2); }
        .sys-badge.pink { border-color: var(--neon-pink); color: var(--neon-pink); text-shadow: 0 0 8px var(--neon-pink); box-shadow: 0 0 10px rgba(255,0,255,0.2); animation: pulsePink 2s infinite; }
        
        .dashboard-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 30px;
            max-width: 1600px;
            margin: 0 auto;
        }
        
        .panel {
            background: var(--panel-bg);
            border: 1px solid #333;
            padding: 25px;
            position: relative;
            backdrop-filter: blur(5px);
        }
        
        /* Corner brackets for military tech feel */
        .panel::before, .panel::after {
            content: ''; position: absolute; width: 20px; height: 20px; border: 2px solid transparent; pointer-events: none;
        }
        .panel::before { top: -1px; left: -1px; border-top-color: inherit; border-left-color: inherit; }
        .panel::after { bottom: -1px; right: -1px; border-bottom-color: inherit; border-right-color: inherit; }
        
        .panel.cyan { border-color: var(--neon-cyan); box-shadow: 0 0 20px rgba(0, 255, 255, 0.1); }
        .panel.pink { border-color: var(--neon-pink); box-shadow: 0 0 20px rgba(255, 0, 255, 0.1); }
        .panel.green { border-color: var(--neon-green); box-shadow: 0 0 20px rgba(0, 255, 0, 0.1); }
        
        .panel-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px dashed #444;
            padding-bottom: 15px;
            margin-bottom: 20px;
        }
        .panel h2 {
            margin: 0;
            font-size: 1.5em;
            letter-spacing: 2px;
            text-transform: uppercase;
        }
        .panel.cyan h2 { color: var(--neon-cyan); text-shadow: 0 0 8px var(--neon-cyan); }
        .panel.pink h2 { color: var(--neon-pink); text-shadow: 0 0 8px var(--neon-pink); }
        .panel.green h2 { color: var(--neon-green); text-shadow: 0 0 8px var(--neon-green); }
        
        .unit-card {
            background: rgba(0,0,0,0.4);
            border: 1px solid #222;
            padding: 15px;
            margin-bottom: 15px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            transition: all 0.3s;
        }
        .unit-card:hover { border-color: #555; background: rgba(0,0,0,0.8); }
        
        .unit-info strong { display: block; font-size: 1.2em; margin-bottom: 5px; color: #fff; }
        .unit-info span { color: #888; font-size: 0.85em; }
        
        .tag {
            padding: 4px 10px;
            border-radius: 2px;
            font-size: 0.75em;
            font-weight: bold;
            letter-spacing: 1px;
            text-align: center;
            min-width: 90px;
        }
        .tag.active { background: rgba(0,255,255,0.1); color: var(--neon-cyan); border: 1px solid var(--neon-cyan); animation: blinkCyan 2s infinite; }
        .tag.bg-proc { background: rgba(255,0,255,0.1); color: var(--neon-pink); border: 1px solid var(--neon-pink); }
        .tag.warning { background: rgba(255,255,0,0.1); color: var(--neon-yellow); border: 1px solid var(--neon-yellow); }
        .tag.good { background: rgba(0,255,0,0.1); color: var(--neon-green); border: 1px solid var(--neon-green); }
        
        .data-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
            margin-top: 20px;
        }
        .data-cell {
            background: #000;
            border: 1px solid #333;
            padding: 10px;
            text-align: center;
        }
        .data-label { color: #777; font-size: 0.8em; text-transform: uppercase; margin-bottom: 5px; display: block; }
        .data-val { font-size: 1.4em; font-weight: bold; }
        .data-val.cyan { color: var(--neon-cyan); text-shadow: 0 0 5px var(--neon-cyan); }
        .data-val.green { color: var(--neon-green); text-shadow: 0 0 5px var(--neon-green); }
        
        /* Terminal Log Area */
        .log-box {
            background: #000;
            border: 1px solid #333;
            height: 150px;
            overflow-y: hidden;
            padding: 10px;
            font-size: 0.85em;
            color: #aaa;
            margin-top: 20px;
        }
        .log-line { margin-bottom: 5px; }
        .log-time { color: #555; margin-right: 10px; }
        
        @keyframes textGlitch {
            0%, 100% { text-shadow: 0 0 5px var(--neon-cyan); transform: translate(0); }
            2% { text-shadow: -2px 0 var(--neon-red), 2px 0 var(--neon-cyan); transform: translate(-2px, 1px); }
            4% { text-shadow: 0 0 5px var(--neon-cyan); transform: translate(0); }
        }
        @keyframes pulsePink {
            0%, 100% { box-shadow: 0 0 10px rgba(255,0,255,0.2); }
            50% { box-shadow: 0 0 25px rgba(255,0,255,0.5); }
        }
        @keyframes blinkCyan {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.6; }
        }
    </style>
</head>
<body>
    <div class="scanlines"></div>
    
    <h1>[ ORBITAL COMMAND ]</h1>
    
    <div class="sys-status">
        <div class="sys-badge cyan">SYSTEM: NOMINAL</div>
        <div class="sys-badge pink">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</div>
        <div class="sys-badge cyan">UPLINK: SECURE</div>
    </div>
    
    <div class="dashboard-grid">
        
        <!-- SQUADRE D'ASSALTO -->
        <div class="panel cyan">
            <div class="panel-header">
                <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
                <div class="tag active">TACTICAL RUN</div>
            </div>
            
            <div class="unit-card">
                <div class="unit-info">
                    <strong>SQUADRA_ALPHA</strong>
                    <span>Binance Scalper | Latency: 8ms | 500x Lev</span>
                </div>
                <div class="tag active">ENGAGING</div>
            </div>
            <div class="unit-card">
                <div class="unit-info">
                    <strong>SQUADRA_DELTA</strong>
                    <span>Order Flow Analysis | Depth: 1000L</span>
                </div>
                <div class="tag active">MONITORING</div>
            </div>
            <div class="unit-card">
                <div class="unit-info">
                    <strong>SQUADRA_GAMMA</strong>
                    <span>Bitget Pairs Trading | Cointegration: 0.94</span>
                </div>
                <div class="tag active">ARBITRAGE</div>
            </div>
            
            <div class="data-grid">
                <div class="data-cell">
                    <span class="data-label">Alpha PNL (24h)</span>
                    <span class="data-val cyan" id="alpha-pnl">+$3,405.20</span>
                </div>
                <div class="data-cell">
                    <span class="data-label">Exec Rate</span>
                    <span class="data-val cyan">142 tps</span>
                </div>
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel pink">
            <div class="panel-header">
                <h2>🔺 PROTOCOLLO TRINITY</h2>
                <div class="tag bg-proc">BACKGROUND</div>
            </div>
            
            <div class="unit-card">
                <div class="unit-info">
                    <strong>Lo Strozzino 🧛‍♂️</strong>
                    <span>Funding Rate Arbitrage | Capital: Deployed</span>
                </div>
                <div class="tag bg-proc">ONLINE</div>
            </div>
            <div class="unit-card">
                <div class="unit-info">
                    <strong>Il Contabile 🧮</strong>
                    <span>Smart DCA Protocol | Vault: Secured</span>
                </div>
                <div class="tag bg-proc">ONLINE</div>
            </div>
            <div class="unit-card">
                <div class="unit-info">
                    <strong>L'Angelo Custode 🛡️</strong>
                    <span>MEV Arbitrum Protection | Mempool Shield</span>
                </div>
                <div class="tag bg-proc">ACTIVE</div>
            </div>
            
            <div class="log-box" id="trinity-log">
                <div class="log-line"><span class="log-time">[08:21:05]</span> [STROZZINO] Rebalancing funding on Bybit... OK</div>
                <div class="log-line"><span class="log-time">[08:21:12]</span> [CONTABILE] Accrued 0.005 BTC to cold storage.</div>
                <div class="log-line"><span class="log-time">[08:21:44]</span> [ANGELO] Sandwich attack deflected on ARB bridge.</div>
                <div class="log-line"><span class="log-time">[08:22:10]</span> [TRINITY] Synchronization complete.</div>
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel green">
            <div class="panel-header">
                <h2>📊 METRICHE DI MERCATO</h2>
                <div class="tag good">DATA SYNC</div>
            </div>
            
            <div class="unit-card">
                <div class="unit-info">
                    <strong>The Oracle 👁️</strong>
                    <span>Binance Sentiment Index | NLP Engine</span>
                </div>
                <div class="tag good">EXTREME GREED</div>
            </div>
            <div class="unit-card">
                <div class="unit-info">
                    <strong>Whale Tracker 🐋</strong>
                    <span>On-Chain Flow Anomaly Detection</span>
                </div>
                <div class="tag warning">ANOMALY DETECTED</div>
            </div>
            
            <div class="data-grid">
                <div class="data-cell">
                    <span class="data-label">Global Volatility</span>
                    <span class="data-val green" id="vol-metric">4.8%</span>
                </div>
                <div class="data-cell">
                    <span class="data-label">Whale Inflow</span>
                    <span class="data-val" style="color:var(--neon-yellow); text-shadow:0 0 5px var(--neon-yellow)">$1.2B</span>
                </div>
                <div class="data-cell">
                    <span class="data-label">Fear & Greed</span>
                    <span class="data-val green">88 / 100</span>
                </div>
                <div class="data-cell">
                    <span class="data-label">Network Load</span>
                    <span class="data-val green">Optimal</span>
                </div>
            </div>
        </div>

    </div>

    <script>
        // Live data simulation
        setInterval(() => {
            const pnl = (3400 + Math.random() * 50).toFixed(2);
            document.getElementById('alpha-pnl').innerText = `+$${pnl}`;
            
            if(Math.random() > 0.6) {
                const vol = (4.5 + Math.random() * 0.5).toFixed(2);
                document.getElementById('vol-metric').innerText = `${vol}%`;
            }
        }, 1500);

        // Fake log generator for Trinity
        const logs = [
            "[STROZZINO] Adjusting delta neutral position...",
            "[CONTABILE] Auditing vault balances...",
            "[ANGELO] Scanning mempool for toxic MEV...",
            "[TRINITY] Core heartbeat ACK.",
            "[STROZZINO] Funding rate capture successful."
        ];
        setInterval(() => {
            if(Math.random() > 0.7) {
                const logBox = document.getElementById('trinity-log');
                const time = new Date().toTimeString().split(' ')[0];
                const msg = logs[Math.floor(Math.random() * logs.length)];
                logBox.innerHTML += `<div class="log-line"><span class="log-time">[${time}]</span> ${msg}</div>`;
                logBox.scrollTop = logBox.scrollHeight;
            }
        }, 2000);
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
