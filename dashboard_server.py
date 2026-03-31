from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Nuvola Orbital Command [v3.0.0]</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&family=Rajdhani:wght@500;700&display=swap');
        
        :root {
            --bg-base: #020205;
            --neon-green: #00ff41;
            --neon-blue: #00f3ff;
            --neon-red: #ff003c;
            --neon-orange: #ff6600;
            --neon-purple: #bc13fe;
            --neon-yellow: #fcee0a;
            --text-main: #d3d3d3;
            --font-display: 'Orbitron', sans-serif;
            --font-data: 'Rajdhani', sans-serif;
            --grid-line: rgba(0, 243, 255, 0.05);
        }
        
        * { box-sizing: border-box; }
        
        body {
            background-color: var(--bg-base);
            color: var(--text-main);
            font-family: var(--font-data);
            margin: 0;
            padding: 20px;
            background-image: 
                linear-gradient(var(--grid-line) 1px, transparent 1px),
                linear-gradient(90deg, var(--grid-line) 1px, transparent 1px);
            background-size: 40px 40px;
            overflow-x: hidden;
        }
        
        .scanline {
            position: fixed;
            top: 0; left: 0; width: 100vw; height: 100vh;
            background: linear-gradient(to bottom, rgba(255,255,255,0), rgba(255,255,255,0) 50%, rgba(0,0,0,0.1) 50%, rgba(0,0,0,0.1));
            background-size: 100% 4px;
            pointer-events: none;
            z-index: 9999;
            opacity: 0.3;
        }

        h1, h2, h3 {
            font-family: var(--font-display);
            text-transform: uppercase;
            letter-spacing: 2px;
            margin: 0 0 15px 0;
        }
        
        .header {
            text-align: center;
            padding: 25px;
            border: 1px solid var(--neon-blue);
            box-shadow: 0 0 20px rgba(0, 243, 255, 0.2), inset 0 0 20px rgba(0, 243, 255, 0.1);
            margin-bottom: 40px;
            position: relative;
            background: linear-gradient(180deg, rgba(0, 243, 255, 0.05) 0%, transparent 100%);
            border-radius: 2px;
        }
        
        .header h1 {
            color: var(--neon-blue);
            font-size: 3em;
            text-shadow: 0 0 10px var(--neon-blue), 0 0 20px var(--neon-blue);
            margin-bottom: 10px;
            font-weight: 900;
        }
        
        .glitch-effect {
            animation: glitch 3s infinite;
        }
        
        @keyframes glitch {
            0% { text-shadow: 2px 0 var(--neon-red), -2px 0 var(--neon-blue); }
            5% { text-shadow: -2px 0 var(--neon-red), 2px 0 var(--neon-blue); }
            10% { text-shadow: 2px 0 var(--neon-red), -2px 0 var(--neon-blue); }
            15% { text-shadow: none; }
            100% { text-shadow: none; }
        }

        .container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(380px, 1fr));
            gap: 30px;
            max-width: 1600px;
            margin: 0 auto;
        }
        
        .panel {
            background: rgba(2, 2, 5, 0.9);
            border: 1px solid;
            border-radius: 2px;
            padding: 25px;
            position: relative;
            backdrop-filter: blur(5px);
            transition: all 0.3s ease;
            overflow: hidden;
        }
        
        .panel::before {
            content: ''; position: absolute; top: 0; left: 0; width: 100%; height: 2px;
            background: currentColor; opacity: 0.8;
            box-shadow: 0 0 10px currentColor, 0 0 20px currentColor;
        }

        .panel:hover {
            transform: translateY(-5px) scale(1.01);
            z-index: 10;
        }
        
        /* Thematic Panels */
        .p-alpha { border-color: var(--neon-red); color: var(--neon-red); box-shadow: 0 0 15px rgba(255, 0, 60, 0.15); }
        .p-delta { border-color: var(--neon-orange); color: var(--neon-orange); box-shadow: 0 0 15px rgba(255, 102, 0, 0.15); }
        .p-gamma { border-color: var(--neon-purple); color: var(--neon-purple); box-shadow: 0 0 15px rgba(188, 19, 254, 0.15); }
        
        .p-trinity { 
            border-color: var(--neon-green); 
            color: var(--neon-green); 
            box-shadow: 0 0 20px rgba(0, 255, 65, 0.15); 
            grid-column: 1 / -1; 
            background: linear-gradient(90deg, rgba(0, 255, 65, 0.05) 0%, transparent 50%, rgba(0, 255, 65, 0.05) 100%);
        }
        
        .p-metrics { 
            border-color: var(--neon-blue); 
            color: var(--neon-blue); 
            box-shadow: 0 0 20px rgba(0, 243, 255, 0.15); 
            grid-column: 1 / -1; 
        }

        .panel-title {
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
            padding-bottom: 15px;
            margin-bottom: 20px;
        }

        .data-row {
            display: flex;
            justify-content: space-between;
            font-size: 1.25em;
            margin-bottom: 12px;
            border-bottom: 1px dashed rgba(255, 255, 255, 0.05);
            padding-bottom: 5px;
        }
        
        .data-label { opacity: 0.7; color: var(--text-main); font-weight: 500; }
        .data-val { font-family: var(--font-display); font-weight: 700; text-shadow: 0 0 8px currentColor; }
        
        .val-pos { color: var(--neon-green); text-shadow: 0 0 8px var(--neon-green); }
        .val-neg { color: var(--neon-red); text-shadow: 0 0 8px var(--neon-red); }
        .val-neu { color: var(--neon-yellow); text-shadow: 0 0 8px var(--neon-yellow); }

        .indicator {
            display: inline-block; width: 10px; height: 10px; border-radius: 50%;
            margin-right: 10px; box-shadow: 0 0 10px currentColor;
            animation: pulse 2s infinite;
        }
        
        @keyframes pulse {
            0% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.3; transform: scale(0.8); }
            100% { opacity: 1; transform: scale(1); }
        }

        table { width: 100%; border-collapse: collapse; font-size: 1.2em; color: var(--text-main); }
        th, td { padding: 15px; text-align: left; border-bottom: 1px solid rgba(255, 255, 255, 0.1); }
        th { font-family: var(--font-display); color: inherit; letter-spacing: 1px; border-bottom: 2px solid currentColor; }
        tr:hover td { background: rgba(255, 255, 255, 0.05); }

        .tag {
            padding: 3px 8px; border-radius: 2px; font-size: 0.8em; font-family: var(--font-display);
            border: 1px solid currentColor; background: rgba(0,0,0,0.5);
        }

        .sys-log {
            font-family: monospace; font-size: 0.9em; opacity: 0.8;
            color: var(--neon-blue); margin-top: 15px; padding: 10px;
            background: rgba(0,0,0,0.5); border-left: 3px solid var(--neon-blue);
        }

    </style>
</head>
<body>
    <div class="scanline"></div>

    <div class="header">
        <h1 class="glitch-effect">🛰️ ORBITAL COMMAND 🛰️</h1>
        <div style="font-size: 1.4em; color: var(--neon-green); text-shadow: 0 0 10px var(--neon-green);">
            <span class="indicator" style="background: var(--neon-green);"></span> SYSTEM ONLINE // CLUSTER NUVOLA // UPTIME: 99.999%
        </div>
        <div style="font-size: 1.2em; color: var(--neon-blue); text-shadow: 0 0 8px var(--neon-blue); margin-top: 10px; font-weight: bold;">
            ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
        </div>
        <div class="sys-log">
            > INITIALIZING NEURAL LINKS... OK<br>
            > CONNECTING TO LIQUIDITY POOLS... OK<br>
            > PROTOCOLLO TRINITY ENGAGED
        </div>
    </div>

    <div class="container">
        <!-- HFT SQUADS -->
        <div class="panel p-alpha">
            <div class="panel-title">
                <h2>⚔️ SQUADRA_ALPHA</h2>
                <span class="tag">SCALPER : BINANCE</span>
            </div>
            <div class="data-row"><span class="data-label">Status</span><span class="data-val val-neg"><span class="indicator" style="background:var(--neon-red);"></span>ACTUATING</span></div>
            <div class="data-row"><span class="data-label">Target</span><span class="data-val text-main">BTC/USDT, ETH/USDT</span></div>
            <div class="data-row"><span class="data-label">Latency</span><span class="data-val val-pos">8 ms</span></div>
            <div class="data-row"><span class="data-label">Executions (24h)</span><span class="data-val val-neu" id="exe-alpha">3,492</span></div>
            <div class="data-row"><span class="data-label">Realized PnL</span><span class="data-val val-pos" id="pnl-alpha">+2.45%</span></div>
        </div>

        <div class="panel p-delta">
            <div class="panel-title">
                <h2>🌊 SQUADRA_DELTA</h2>
                <span class="tag">ORDER FLOW</span>
            </div>
            <div class="data-row"><span class="data-label">Status</span><span class="data-val val-neu"><span class="indicator" style="background:var(--neon-orange);"></span>SCANNING</span></div>
            <div class="data-row"><span class="data-label">Vector</span><span class="data-val text-main">Altcoin Volatility Spikes</span></div>
            <div class="data-row"><span class="data-label">Imbalance Vector</span><span class="data-val val-pos">BULLISH (+850 BTC)</span></div>
            <div class="data-row"><span class="data-label">Active Positions</span><span class="data-val val-neu">4</span></div>
            <div class="data-row"><span class="data-label">Floating PnL</span><span class="data-val val-pos" id="pnl-delta">+5.12%</span></div>
        </div>

        <div class="panel p-gamma">
            <div class="panel-title">
                <h2>⚖️ SQUADRA_GAMMA</h2>
                <span class="tag">PAIRS TRADING : BITGET</span>
            </div>
            <div class="data-row"><span class="data-label">Status</span><span class="data-val"><span class="indicator" style="background:var(--neon-purple);"></span>HEDGING</span></div>
            <div class="data-row"><span class="data-label">Active Pair</span><span class="data-val text-main">SOL-PERP / APT-PERP</span></div>
            <div class="data-row"><span class="data-label">Spread Z-Score</span><span class="data-val val-neg">-2.85</span></div>
            <div class="data-row"><span class="data-label">Exposure</span><span class="data-val val-neu">Delta Neutral (0.01)</span></div>
            <div class="data-row"><span class="data-label">Yield (Est)</span><span class="data-val val-pos" id="pnl-gamma">+1.05%</span></div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel p-trinity">
            <div class="panel-title" style="justify-content: center;">
                <h2>🔺 PROTOCOLLO TRINITY 🔺</h2>
            </div>
            <table>
                <tr>
                    <th>Daemon</th>
                    <th>Directive</th>
                    <th>Network Status</th>
                    <th>Last Operation Log</th>
                </tr>
                <tr>
                    <td><span style="font-size:1.2em">🕴️</span> <strong>Lo Strozzino</strong></td>
                    <td>Funding Arbitrage</td>
                    <td class="val-pos"><span class="indicator" style="background:var(--neon-green);"></span> EXECUTING</td>
                    <td>Short Perp ETH (Binance) / Long Spot ETH (+0.04% APR locked)</td>
                </tr>
                <tr>
                    <td><span style="font-size:1.2em">🧮</span> <strong>Il Contabile</strong></td>
                    <td>Smart DCA</td>
                    <td class="val-neu"><span class="indicator" style="background:var(--neon-yellow);"></span> STANDBY</td>
                    <td>Awaiting optimal VWAP dip. Next threshold: 62,100 USDT.</td>
                </tr>
                <tr>
                    <td><span style="font-size:1.2em">👼</span> <strong>L'Angelo Custode</strong></td>
                    <td>MEV Arbitrum</td>
                    <td class="val-pos" style="color:var(--neon-blue)"><span class="indicator" style="background:var(--neon-blue);"></span> MEMPOOL SNIFFING</td>
                    <td>Sandwich attack thwarted on Uniswap V3 (TX: 0x8a9f...2b1c). Saved 0.5 ETH.</td>
                </tr>
            </table>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel p-metrics">
            <div class="panel-title" style="justify-content: center;">
                <h2>👁️ GLOBAL MARKET METRICS 👁️</h2>
            </div>
            <table>
                <tr>
                    <th>Data Source</th>
                    <th>Metric Value</th>
                    <th>AI Signal / Override</th>
                </tr>
                <tr>
                    <td><strong>The Oracle</strong> (Binance Sentiment)</td>
                    <td class="val-neu" id="sentiment">82 / 100</td>
                    <td class="val-neg glitch-effect">EXTREME GREED ⚠️</td>
                </tr>
                <tr>
                    <td><strong>Whale Tracker</strong> (24h Flow)</td>
                    <td class="val-pos">+2,450 BTC</td>
                    <td class="val-pos">STRONG BUY</td>
                </tr>
                <tr>
                    <td><strong>CEX Reserves</strong> (Net Outflow)</td>
                    <td class="val-neg">-$850M</td>
                    <td class="val-neu">ACCUMULATION PHASE</td>
                </tr>
                <tr>
                    <td><strong>CVD</strong> (Cumulative Volume Delta)</td>
                    <td class="val-pos">+95M USDT</td>
                    <td class="val-pos">BULLISH DIVERGENCE</td>
                </tr>
            </table>
        </div>
    </div>

    <script>
        // Simulate real-time updates
        const updateVal = (id, variance) => {
            const el = document.getElementById(id);
            if(el) {
                let val = parseFloat(el.innerText);
                val += (Math.random() - 0.5) * variance;
                el.innerText = (val >= 0 ? '+' : '') + val.toFixed(2) + '%';
                el.className = 'data-val ' + (val < 0 ? 'val-neg' : 'val-pos');
            }
        };

        setInterval(() => {
            updateVal('pnl-alpha', 0.15);
            updateVal('pnl-delta', 0.25);
            updateVal('pnl-gamma', 0.05);
        }, 1500);

        setInterval(() => {
            const el = document.getElementById('exe-alpha');
            if(el) el.innerText = (parseInt(el.innerText.replace(',','')) + Math.floor(Math.random() * 3)).toLocaleString();
        }, 800);
        
        setInterval(() => {
            const el = document.getElementById('sentiment');
            if(el && Math.random() > 0.7) {
                let s = parseInt(el.innerText);
                s += (Math.random() > 0.5 ? 1 : -1);
                el.innerText = Math.max(0, Math.min(100, s)) + ' / 100';
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
