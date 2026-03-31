from flask import Flask, render_template_string

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
            --neon-green: #39ff14;
            --neon-blue: #0ff;
            --neon-pink: #ff00ff;
            --dark-bg: #050505;
            --panel-bg: rgba(10, 20, 10, 0.8);
            --border: 1px solid var(--neon-green);
        }
        body {
            background-color: var(--dark-bg);
            color: var(--neon-green);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            display: flex;
            flex-direction: column;
            gap: 20px;
            text-transform: uppercase;
        }
        h1 {
            text-align: center;
            color: var(--neon-blue);
            text-shadow: 0 0 10px var(--neon-blue), 0 0 20px var(--neon-blue);
            margin: 0;
            font-size: 2.5rem;
            letter-spacing: 5px;
        }
        .header-status {
            text-align: center;
            font-size: 0.9rem;
            color: var(--neon-pink);
            animation: blink 2s infinite;
        }
        @keyframes blink {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
        }
        .panel {
            background: var(--panel-bg);
            border: var(--border);
            border-radius: 5px;
            padding: 15px;
            box-shadow: inset 0 0 15px rgba(57, 255, 20, 0.2), 0 0 10px rgba(57, 255, 20, 0.3);
            position: relative;
            overflow: hidden;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: -100%;
            width: 100%; height: 2px;
            background: var(--neon-blue);
            animation: scanline 4s linear infinite;
        }
        @keyframes scanline {
            100% { left: 100%; }
        }
        .panel-header {
            font-size: 1.2rem;
            border-bottom: 1px dashed var(--neon-green);
            padding-bottom: 10px;
            margin-bottom: 15px;
            color: var(--neon-blue);
            display: flex;
            justify-content: space-between;
        }
        .item {
            margin-bottom: 15px;
            padding: 10px;
            border-left: 3px solid var(--neon-pink);
            background: rgba(255, 0, 255, 0.05);
        }
        .item h3 { margin: 0 0 5px 0; font-size: 1rem; color: #fff; text-shadow: 0 0 5px #fff; }
        .status {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 3px;
            font-size: 0.8rem;
            font-weight: bold;
        }
        .status.active { background: var(--neon-green); color: #000; box-shadow: 0 0 8px var(--neon-green); }
        .status.standby { background: #ffaa00; color: #000; box-shadow: 0 0 8px #ffaa00; }
        .status.stealth { background: var(--neon-blue); color: #000; box-shadow: 0 0 8px var(--neon-blue); }
        
        table { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
        th, td { padding: 8px; text-align: left; border-bottom: 1px solid rgba(57, 255, 20, 0.3); }
        th { color: var(--neon-pink); }
        tr:hover { background: rgba(57, 255, 20, 0.1); }
        .positive { color: var(--neon-green); }
        .negative { color: #ff3333; }
    </style>
</head>
<body>
    <h1>🛰️ ORBITAL COMMAND // NUVOLA</h1>
    <div class="header-status">🔴 LIVE LINK ESTABLISHED // SECURE CONNECTION ACTIVATED</div>
    <div style="text-align: center; font-size: 1.2rem; color: var(--neon-green); margin-top: 10px; border: 1px solid var(--neon-green); padding: 10px; background: rgba(57, 255, 20, 0.1);">
        ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
    </div>

    <div class="grid">
        <!-- SEZIONE 1: SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <div class="panel-header">
                <span>⚔️ SQUADRE D'ASSALTO (HFT)</span>
                <span class="status active">DEPLOYED</span>
            </div>
            <div class="item">
                <h3>🐺 SQUADRA_ALPHA</h3>
                <div>Mission: Scalping su Binance</div>
                <div>Status: <span class="status active">ENGAGING</span></div>
                <div style="margin-top:5px; font-size:0.8rem;">Last Action: Long BTC/USDT @ 69420 (+0.4%)</div>
            </div>
            <div class="item">
                <h3>🦅 SQUADRA_DELTA</h3>
                <div>Mission: Order Flow Analysis</div>
                <div>Status: <span class="status standby">MONITORING</span></div>
                <div style="margin-top:5px; font-size:0.8rem;">Target: Aggregation nodes detected.</div>
            </div>
            <div class="item">
                <h3>🐍 SQUADRA_GAMMA</h3>
                <div>Mission: Pairs Trading su Bitget</div>
                <div>Status: <span class="status active">ARB-ACTIVE</span></div>
                <div style="margin-top:5px; font-size:0.8rem;">Pair: ETH/BTC Spread 0.052 (+1.2%)</div>
            </div>
        </div>

        <!-- SEZIONE 2: PROTOCOLLO TRINITY -->
        <div class="panel">
            <div class="panel-header">
                <span>🔺 PROTOCOLLO TRINITY</span>
                <span class="status stealth">GHOST_MODE</span>
            </div>
            <div class="item">
                <h3>🎩 LO STROZZINO</h3>
                <div>Role: Funding Arbitrage</div>
                <div>Status: <span class="status stealth">SILENT_RUN</span></div>
                <div style="margin-top:5px; font-size:0.8rem;">Yield: +0.01% / 8h (Perp/Spot Arb)</div>
            </div>
            <div class="item">
                <h3>💼 IL CONTABILE</h3>
                <div>Role: DCA Strategist</div>
                <div>Status: <span class="status stealth">BACKGROUND</span></div>
                <div style="margin-top:5px; font-size:0.8rem;">Accumulation: Active on Dips > 5%</div>
            </div>
            <div class="item">
                <h3>👼 L'ANGELO CUSTODE</h3>
                <div>Role: MEV Arbitrum</div>
                <div>Status: <span class="status stealth">PROTECTING</span></div>
                <div style="margin-top:5px; font-size:0.8rem;">MemPool: Scanning pending TXs...</div>
            </div>
        </div>

        <!-- SEZIONE 3: METRICHE DI MERCATO -->
        <div class="panel" style="grid-column: 1 / -1;">
            <div class="panel-header">
                <span>📊 METRICHE DI MERCATO & ORACLE</span>
                <span class="status active">DATA_FEED_OK</span>
            </div>
            <div style="display: flex; gap: 20px; flex-wrap: wrap;">
                <div style="flex: 1; min-width: 300px;">
                    <h3 style="color: var(--neon-blue); border-bottom: 1px solid; padding-bottom: 5px;">👁️ THE ORACLE (Binance Sentiment)</h3>
                    <table>
                        <tr><th>Asset</th><th>Sentiment Score</th><th>Order Imbalance</th><th>Signal</th></tr>
                        <tr><td>BTC</td><td><span class="positive">82/100 (BULL)</span></td><td>+14.5M USDT</td><td>BUY</td></tr>
                        <tr><td>ETH</td><td>65/100 (NEUTRAL)</td><td>-2.1M USDT</td><td>HOLD</td></tr>
                        <tr><td>SOL</td><td><span class="negative">31/100 (BEAR)</span></td><td>-8.9M USDT</td><td>SHORT</td></tr>
                    </table>
                </div>
                <div style="flex: 1; min-width: 300px;">
                    <h3 style="color: var(--neon-pink); border-bottom: 1px solid; padding-bottom: 5px;">🐋 WHALE TRACKER</h3>
                    <table>
                        <tr><th>Time</th><th>Action</th><th>Amount</th><th>Tx Hash</th></tr>
                        <tr><td>12:42</td><td>Transfer (Exchange)</td><td>1,500 BTC</td><td>0x8f...2a1b</td></tr>
                        <tr><td>12:35</td><td>DEX Swap</td><td>45,000 ETH</td><td>0x1c...99d1</td></tr>
                        <tr><td>12:15</td><td>Liquidated (Short)</td><td>$2.4M SOL</td><td>N/A</td></tr>
                    </table>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        // Glitch effect on header
        setInterval(() => {
            const h1 = document.querySelector('h1');
            if(Math.random() > 0.95) {
                h1.style.textShadow = `0 0 10px #f0f, ${Math.random()*10 - 5}px ${Math.random()*10 - 5}px 0 #0ff`;
                setTimeout(() => {
                    h1.style.textShadow = '0 0 10px var(--neon-blue), 0 0 20px var(--neon-blue)';
                }, 100);
            }
        }, 200);
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5050, debug=False)
