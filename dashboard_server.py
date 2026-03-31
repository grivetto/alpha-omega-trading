from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Nuvola Orbital Command</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');
        
        :root {
            --bg-color: #030305;
            --neon-green: #39ff14;
            --neon-blue: #00f3ff;
            --neon-pink: #ff00ff;
            --neon-red: #ff003c;
            --neon-orange: #ff8c00;
            --neon-purple: #b026ff;
            --neon-yellow: #faff00;
            --text-main: #e0e0e0;
            --border-glow: 0 0 10px rgba(0, 243, 255, 0.4);
            --font-main: 'Share Tech Mono', monospace;
        }
        
        body {
            background-color: var(--bg-color);
            color: var(--text-main);
            font-family: var(--font-main);
            margin: 0;
            padding: 20px;
            background-image: 
                linear-gradient(rgba(0, 243, 255, 0.03) 1px, transparent 1px),
                linear-gradient(90deg, rgba(0, 243, 255, 0.03) 1px, transparent 1px);
            background-size: 30px 30px;
            overflow-x: hidden;
        }
        
        h1, h2, h3 {
            text-transform: uppercase;
            letter-spacing: 2px;
            margin-top: 0;
            text-shadow: 0 0 5px currentColor;
        }
        
        .header {
            text-align: center;
            padding: 20px;
            border-bottom: 2px solid var(--neon-blue);
            box-shadow: 0 5px 25px rgba(0, 243, 255, 0.15);
            margin-bottom: 30px;
            text-shadow: 0 0 10px var(--neon-blue);
            position: relative;
        }
        
        .header::after {
            content: '';
            position: absolute;
            bottom: -2px;
            left: 0;
            width: 100%;
            height: 2px;
            background: var(--neon-blue);
            box-shadow: 0 0 15px var(--neon-blue), 0 0 30px var(--neon-blue);
        }

        .header h1 {
            color: var(--neon-blue);
            font-size: 2.5em;
            margin-bottom: 5px;
        }
        
        .grid-container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
            gap: 25px;
            max-width: 1400px;
            margin: 0 auto;
        }
        
        .panel {
            background: rgba(10, 10, 15, 0.85);
            border: 1px solid var(--neon-blue);
            border-radius: 4px;
            padding: 20px;
            box-shadow: var(--border-glow);
            position: relative;
            backdrop-filter: blur(4px);
            transition: all 0.3s ease;
        }

        .panel:hover {
            box-shadow: 0 0 20px currentColor;
            transform: translateY(-2px);
        }
        
        .panel::before {
            content: '';
            position: absolute;
            top: 0;
            left: -100%;
            width: 50%;
            height: 1px;
            background: linear-gradient(90deg, transparent, currentColor, transparent);
            animation: scanline 4s linear infinite;
            opacity: 0.7;
        }
        
        @keyframes scanline {
            0% { left: -100%; }
            100% { left: 200%; }
        }
        
        .panel-alpha { border-color: var(--neon-red); color: var(--neon-red); box-shadow: 0 0 15px rgba(255, 0, 60, 0.2); }
        .panel-alpha h2 { color: var(--neon-red); }
        
        .panel-delta { border-color: var(--neon-orange); color: var(--neon-orange); box-shadow: 0 0 15px rgba(255, 140, 0, 0.2); }
        .panel-delta h2 { color: var(--neon-orange); }
        
        .panel-gamma { border-color: var(--neon-purple); color: var(--neon-purple); box-shadow: 0 0 15px rgba(176, 38, 255, 0.2); }
        .panel-gamma h2 { color: var(--neon-purple); }
        
        .panel-trinity { border-color: var(--neon-green); color: var(--neon-green); box-shadow: 0 0 15px rgba(0, 255, 0, 0.2); grid-column: 1 / -1; }
        .panel-trinity h2 { color: var(--neon-green); text-align: center; font-size: 1.8em; }
        
        .panel-metrics { border-color: var(--neon-pink); color: var(--neon-pink); box-shadow: 0 0 15px rgba(255, 0, 255, 0.2); grid-column: 1 / -1; }
        .panel-metrics h2 { color: var(--neon-pink); text-align: center; font-size: 1.8em; }
        
        .status-indicator {
            display: inline-block;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            background-color: var(--neon-green);
            box-shadow: 0 0 10px var(--neon-green), 0 0 20px var(--neon-green);
            margin-right: 8px;
            animation: pulse 1.5s infinite;
            vertical-align: middle;
        }
        
        @keyframes pulse {
            0% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.4; transform: scale(0.8); }
            100% { opacity: 1; transform: scale(1); }
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
            font-size: 1.1em;
            color: var(--text-main);
        }
        
        th, td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }
        
        th {
            color: inherit;
            font-weight: bold;
            text-transform: uppercase;
            letter-spacing: 1px;
            border-bottom: 2px solid currentColor;
        }

        tr:hover td {
            background: rgba(255, 255, 255, 0.05);
        }
        
        .blink {
            animation: blinker 1s linear infinite;
        }
        
        @keyframes blinker {
            50% { opacity: 0; }
        }

        .metric-value {
            font-weight: bold;
            color: var(--neon-green);
            text-shadow: 0 0 5px var(--neon-green);
        }
        .metric-value.negative {
            color: var(--neon-red);
            text-shadow: 0 0 5px var(--neon-red);
        }
        .metric-value.neutral {
            color: var(--neon-yellow);
            text-shadow: 0 0 5px var(--neon-yellow);
        }

        .terminal-text {
            color: var(--text-main);
            margin: 5px 0;
            font-size: 1.1em;
        }

        .label {
            color: inherit;
            opacity: 0.8;
            display: inline-block;
            width: 120px;
        }
        
    </style>
</head>
<body>
    <div class="header">
        <h1>🛰️ ORBITAL COMMAND: NUVOLA 🛰️</h1>
        <p class="terminal-text">SYSTEM STATUS: <span class="status-indicator"></span> <span style="color: var(--neon-green); text-shadow: 0 0 5px var(--neon-green);">ONLINE & FULLY OPERATIONAL</span></p>
        <p class="terminal-text">📍 LOCATION: NUVOLA CLUSTER | ⏱ UPTIME: <span id="uptime">99.99%</span></p>
        <p class="terminal-text" style="color: var(--neon-green); font-weight: bold; margin-top: 10px;">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</p>
    </div>

    <div class="grid-container">
        <!-- ASSAULT SQUADS -->
        <div class="panel panel-alpha">
            <h2>⚔️ SQUADRA_ALPHA</h2>
            <div class="terminal-text"><span class="label">Ruolo:</span> Scalper (Binance)</div>
            <div class="terminal-text"><span class="label">Status:</span> <span class="status-indicator" style="background:var(--neon-red); box-shadow:0 0 10px var(--neon-red)"></span> ACTUATING</div>
            <div class="terminal-text"><span class="label">Target:</span> BTC/USDT, ETH/USDT</div>
            <div class="terminal-text"><span class="label">Latency:</span> <span class="metric-value">12ms</span></div>
            <div class="terminal-text"><span class="label">Trades (24h):</span> <span class="metric-value neutral" id="trades-alpha">142</span></div>
            <div class="terminal-text"><span class="label">PnL:</span> <span class="metric-value" id="pnl-alpha">+1.24%</span></div>
        </div>

        <div class="panel panel-delta">
            <h2>🌊 SQUADRA_DELTA</h2>
            <div class="terminal-text"><span class="label">Ruolo:</span> Order Flow</div>
            <div class="terminal-text"><span class="label">Status:</span> <span class="status-indicator" style="background:var(--neon-orange); box-shadow:0 0 10px var(--neon-orange)"></span> SCANNING</div>
            <div class="terminal-text"><span class="label">Target:</span> Altcoins Vol Spikes</div>
            <div class="terminal-text"><span class="label">Imbalance:</span> <span class="metric-value">BULLISH (+450 BTC)</span></div>
            <div class="terminal-text"><span class="label">Active Pos:</span> <span class="metric-value neutral">3</span></div>
            <div class="terminal-text"><span class="label">PnL:</span> <span class="metric-value" id="pnl-delta">+3.80%</span></div>
        </div>

        <div class="panel panel-gamma">
            <h2>⚖️ SQUADRA_GAMMA</h2>
            <div class="terminal-text"><span class="label">Ruolo:</span> Pairs Trading (Bitget)</div>
            <div class="terminal-text"><span class="label">Status:</span> <span class="status-indicator" style="background:var(--neon-purple); box-shadow:0 0 10px var(--neon-purple)"></span> HEDGING</div>
            <div class="terminal-text"><span class="label">Target:</span> SOL vs APT</div>
            <div class="terminal-text"><span class="label">Spread Z:</span> <span class="metric-value negative">-2.10</span></div>
            <div class="terminal-text"><span class="label">Exposure:</span> <span class="metric-value neutral">Delta Neutral</span></div>
            <div class="terminal-text"><span class="label">PnL:</span> <span class="metric-value" id="pnl-gamma">+0.45%</span></div>
        </div>

        <!-- PROTOCOL TRINITY -->
        <div class="panel panel-trinity">
            <h2>🔺 PROTOCOLLO TRINITY 🔺</h2>
            <table>
                <tr>
                    <th>Agente (Daemon)</th>
                    <th>Funzione</th>
                    <th>Stato Rete</th>
                    <th>Ultima Azione / Log</th>
                </tr>
                <tr>
                    <td>🕴️ <strong>Lo Strozzino</strong></td>
                    <td>Funding Arbitrage</td>
                    <td><span class="status-indicator"></span> ESECUZIONE</td>
                    <td class="terminal-text">Short Perp ETH (Bin) / Long Spot ETH (+0.03% apr)</td>
                </tr>
                <tr>
                    <td>🧮 <strong>Il Contabile</strong></td>
                    <td>Smart DCA</td>
                    <td><span class="status-indicator" style="background:var(--neon-yellow); box-shadow:0 0 10px var(--neon-yellow)"></span> ATTESA</td>
                    <td class="terminal-text">Acquisto 0.01 BTC @ 65,420 USDT effettuato.</td>
                </tr>
                <tr>
                    <td>👼 <strong>L'Angelo Custode</strong></td>
                    <td>MEV (Arbitrum)</td>
                    <td><span class="status-indicator" style="background:var(--neon-blue); box-shadow:0 0 10px var(--neon-blue)"></span> SNIFFING MEMPOOL</td>
                    <td class="terminal-text">Sandwich attack evitato su Uniswap V3 (TX: 0x8a9f...2b1c).</td>
                </tr>
            </table>
        </div>

        <!-- MARKET METRICS -->
        <div class="panel panel-metrics">
            <h2>👁️ THE ORACLE & WHALE TRACKER 👁️</h2>
            <table>
                <tr>
                    <th>Sorgente Dati</th>
                    <th>Valore / Metrica</th>
                    <th>Segnale IA</th>
                </tr>
                <tr>
                    <td>The Oracle (Binance Sentiment)</td>
                    <td><span class="metric-value neutral" id="sentiment">78 / 100</span></td>
                    <td style="color: var(--neon-red); text-shadow: 0 0 5px var(--neon-red);">GREED <span class="blink">⚠️</span></td>
                </tr>
                <tr>
                    <td>Whale Tracker (24h Flow)</td>
                    <td><span class="metric-value">+1,250 BTC</span></td>
                    <td style="color: var(--neon-green); text-shadow: 0 0 5px var(--neon-green);">STRONG BUY</td>
                </tr>
                <tr>
                    <td>CEX Reserve (Inflows)</td>
                    <td><span class="metric-value negative">-$450M</span></td>
                    <td style="color: var(--neon-yellow); text-shadow: 0 0 5px var(--neon-yellow);">HOLD / ACCUMULATE</td>
                </tr>
                <tr>
                    <td>CVD (Cumulative Vol Delta)</td>
                    <td><span class="metric-value">+45M</span></td>
                    <td style="color: var(--neon-green); text-shadow: 0 0 5px var(--neon-green);">BULLISH</td>
                </tr>
            </table>
        </div>
    </div>
    
    <script>
        // Simulate real-time dashboard flickering and data updates
        setInterval(() => {
            const ids = ['pnl-alpha', 'pnl-delta', 'pnl-gamma'];
            const id = ids[Math.floor(Math.random() * ids.length)];
            const el = document.getElementById(id);
            if(el) {
                let val = parseFloat(el.innerText);
                val += (Math.random() - 0.5) * 0.1;
                el.innerText = (val >= 0 ? '+' : '') + val.toFixed(2) + '%';
                if(val < 0) {
                    el.className = 'metric-value negative';
                } else {
                    el.className = 'metric-value';
                }
            }
        }, 2000);

        setInterval(() => {
            const tradesEl = document.getElementById('trades-alpha');
            if(tradesEl && Math.random() > 0.7) {
                let trades = parseInt(tradesEl.innerText);
                tradesEl.innerText = trades + 1;
            }
        }, 3500);
        
        setInterval(() => {
            const sentimentEl = document.getElementById('sentiment');
            if(sentimentEl && Math.random() > 0.8) {
                let sent = parseInt(sentimentEl.innerText);
                sent += (Math.random() > 0.5 ? 1 : -1);
                sentimentEl.innerText = sent + ' / 100';
            }
        }, 5000);
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    print("Avvio Nuvola Orbital Command su http://0.0.0.0:5000")
    app.run(host='0.0.0.0', port=5000, debug=False)