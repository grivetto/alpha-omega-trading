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
        :root {
            --bg-color: #050505;
            --neon-green: #00ff00;
            --neon-blue: #00f3ff;
            --neon-pink: #ff00ff;
            --neon-red: #ff003c;
            --neon-orange: #ff8c00;
            --neon-purple: #b026ff;
            --text-main: #e0e0e0;
            --border-glow: 0 0 10px rgba(0, 243, 255, 0.5);
            --font-main: 'Courier New', Courier, monospace;
        }
        
        body {
            background-color: var(--bg-color);
            color: var(--text-main);
            font-family: var(--font-main);
            margin: 0;
            padding: 20px;
            background-image: 
                linear-gradient(rgba(0, 243, 255, 0.05) 1px, transparent 1px),
                linear-gradient(90deg, rgba(0, 243, 255, 0.05) 1px, transparent 1px);
            background-size: 20px 20px;
        }
        
        h1, h2, h3 {
            text-transform: uppercase;
            letter-spacing: 2px;
            margin-top: 0;
        }
        
        .header {
            text-align: center;
            padding: 20px;
            border-bottom: 2px solid var(--neon-blue);
            box-shadow: 0 5px 15px rgba(0, 243, 255, 0.2);
            margin-bottom: 30px;
            text-shadow: 0 0 10px var(--neon-blue);
        }
        
        .grid-container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
        }
        
        .panel {
            background: rgba(10, 10, 15, 0.8);
            border: 1px solid var(--neon-blue);
            border-radius: 5px;
            padding: 15px;
            box-shadow: var(--border-glow);
            position: relative;
            overflow: hidden;
        }
        
        .panel::before {
            content: '';
            position: absolute;
            top: 0;
            left: -100%;
            width: 100%;
            height: 2px;
            background: linear-gradient(90deg, transparent, var(--neon-blue));
            animation: scanline 3s linear infinite;
        }
        
        @keyframes scanline {
            0% { left: -100%; }
            100% { left: 100%; }
        }
        
        .panel-alpha { border-color: var(--neon-red); box-shadow: 0 0 10px rgba(255, 0, 60, 0.3); }
        .panel-alpha h2 { color: var(--neon-red); text-shadow: 0 0 5px var(--neon-red); }
        
        .panel-delta { border-color: var(--neon-orange); box-shadow: 0 0 10px rgba(255, 140, 0, 0.3); }
        .panel-delta h2 { color: var(--neon-orange); text-shadow: 0 0 5px var(--neon-orange); }
        
        .panel-gamma { border-color: var(--neon-purple); box-shadow: 0 0 10px rgba(176, 38, 255, 0.3); }
        .panel-gamma h2 { color: var(--neon-purple); text-shadow: 0 0 5px var(--neon-purple); }
        
        .panel-trinity { border-color: var(--neon-green); box-shadow: 0 0 10px rgba(0, 255, 0, 0.3); grid-column: 1 / -1; }
        .panel-trinity h2 { color: var(--neon-green); text-shadow: 0 0 5px var(--neon-green); }
        
        .panel-metrics { border-color: var(--neon-pink); box-shadow: 0 0 10px rgba(255, 0, 255, 0.3); grid-column: 1 / -1; }
        .panel-metrics h2 { color: var(--neon-pink); text-shadow: 0 0 5px var(--neon-pink); }
        
        .status-indicator {
            display: inline-block;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background-color: var(--neon-green);
            box-shadow: 0 0 8px var(--neon-green);
            margin-right: 10px;
            animation: pulse 1.5s infinite;
        }
        
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.4; }
            100% { opacity: 1; }
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
            font-size: 0.9em;
        }
        
        th, td {
            padding: 8px;
            text-align: left;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }
        
        th {
            color: var(--neon-blue);
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
        }
        .metric-value.negative {
            color: var(--neon-red);
        }
        
    </style>
</head>
<body>
    <div class="header">
        <h1>🛰️ ORBITAL COMMAND: NUVOLA 🛰️</h1>
        <p>SYSTEM STATUS: <span class="status-indicator"></span> <span style="color: var(--neon-green);">ONLINE & FULLY OPERATIONAL</span></p>
        <p>⚙️ PROTOCOLLO TRINITY: <span style="color: var(--neon-green);">Online (DCA, Funding, MEV)</span></p>
    </div>

    <div class="grid-container">
        <!-- ASSAULT SQUADS -->
        <div class="panel panel-alpha">
            <h2>⚔️ SQUADRA_ALPHA</h2>
            <p><strong>Ruolo:</strong> Scalper (Binance)</p>
            <p><strong>Status:</strong> <span class="status-indicator"></span> ACTUATING</p>
            <p><strong>Target:</strong> BTC/USDT, ETH/USDT</p>
            <p><strong>Latency:</strong> 12ms</p>
            <p><strong>Trades (24h):</strong> 142</p>
            <p><strong>PnL:</strong> <span class="metric-value">+1.24%</span></p>
        </div>

        <div class="panel panel-delta">
            <h2>🌊 SQUADRA_DELTA</h2>
            <p><strong>Ruolo:</strong> Order Flow</p>
            <p><strong>Status:</strong> <span class="status-indicator"></span> SCANNING</p>
            <p><strong>Target:</strong> Altcoins Volume Spikes</p>
            <p><strong>Imbalance:</strong> <span class="metric-value">BULLISH (+450 BTC)</span></p>
            <p><strong>Active Positions:</strong> 3</p>
            <p><strong>PnL:</strong> <span class="metric-value">+3.80%</span></p>
        </div>

        <div class="panel panel-gamma">
            <h2>⚖️ SQUADRA_GAMMA</h2>
            <p><strong>Ruolo:</strong> Pairs Trading (Bitget)</p>
            <p><strong>Status:</strong> <span class="status-indicator"></span> HEDGING</p>
            <p><strong>Target:</strong> SOL/USDT vs APT/USDT</p>
            <p><strong>Spread:</strong> Z-Score -2.1</p>
            <p><strong>Exposure:</strong> Delta Neutral</p>
            <p><strong>PnL:</strong> <span class="metric-value">+0.45%</span></p>
        </div>

        <!-- PROTOCOL TRINITY -->
        <div class="panel panel-trinity">
            <h2>🔺 PROTOCOLLO TRINITY 🔺</h2>
            <table>
                <tr>
                    <th>Agente</th>
                    <th>Funzione</th>
                    <th>Stato</th>
                    <th>Ultima Azione</th>
                </tr>
                <tr>
                    <td>🕴️ <strong>Lo Strozzino</strong></td>
                    <td>Funding Arb</td>
                    <td><span class="status-indicator"></span> ESECUZIONE</td>
                    <td>Short Perp ETH (Binance) / Long Spot ETH (+0.03% apr)</td>
                </tr>
                <tr>
                    <td>🧮 <strong>Il Contabile</strong></td>
                    <td>Smart DCA</td>
                    <td><span class="status-indicator"></span> ATTESA</td>
                    <td>Acquisto 0.01 BTC @ 65,420 USDT effettuato.</td>
                </tr>
                <tr>
                    <td>👼 <strong>L'Angelo Custode</strong></td>
                    <td>MEV (Arbitrum)</td>
                    <td><span class="status-indicator"></span> SNIFFING MEMPOOL</td>
                    <td>Sandwich attack evitato su Uniswap V3.</td>
                </tr>
            </table>
        </div>

        <!-- MARKET METRICS -->
        <div class="panel panel-metrics">
            <h2>👁️ THE ORACLE & WHALE TRACKER 👁️</h2>
            <table>
                <tr>
                    <th>Metrica</th>
                    <th>Valore</th>
                    <th>Segnale</th>
                </tr>
                <tr>
                    <td>Binance Sentiment Index</td>
                    <td><span class="metric-value">78 / 100</span></td>
                    <td>GREED <span class="blink">⚠️</span></td>
                </tr>
                <tr>
                    <td>Whale Accumulation (24h)</td>
                    <td><span class="metric-value">+1,250 BTC</span></td>
                    <td>STRONG BUY</td>
                </tr>
                <tr>
                    <td>Exchange Inflows</td>
                    <td><span class="metric-value negative">-$450M</span></td>
                    <td>HOLD</td>
                </tr>
                <tr>
                    <td>CVD (Cumulative Volume Delta)</td>
                    <td><span class="metric-value">+45M</span></td>
                    <td>BULLISH</td>
                </tr>
            </table>
        </div>
    </div>
    
    <script>
        setInterval(() => {
            const elements = document.querySelectorAll('.metric-value');
            const idx = Math.floor(Math.random() * elements.length);
            const el = elements[idx];
            if(el.innerText.includes('%')) {
                let val = parseFloat(el.innerText);
                val += (Math.random() - 0.5) * 0.1;
                el.innerText = (val > 0 ? '+' : '') + val.toFixed(2) + '%';
                if(val < 0) {
                    el.classList.add('negative');
                } else {
                    el.classList.remove('negative');
                }
            }
        }, 3000);
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
