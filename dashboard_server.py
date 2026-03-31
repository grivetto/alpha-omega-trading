from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NUVOLA ORBITAL COMMAND</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');
        
        :root {
            --bg: #050510;
            --neon-green: #39ff14;
            --neon-cyan: #00f3ff;
            --neon-pink: #ff00ff;
            --neon-red: #ff3333;
            --neon-yellow: #ffff00;
            --panel-bg: rgba(0, 20, 40, 0.6);
            --grid-line: rgba(0, 255, 255, 0.1);
        }

        body {
            background-color: var(--bg);
            color: var(--neon-cyan);
            font-family: 'Share Tech Mono', monospace;
            margin: 0;
            padding: 20px;
            background-image: 
                linear-gradient(var(--grid-line) 1px, transparent 1px),
                linear-gradient(90deg, var(--grid-line) 1px, transparent 1px);
            background-size: 30px 30px;
            overflow-x: hidden;
        }

        /* CRT Effect */
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

        h1 {
            text-align: center;
            color: var(--neon-pink);
            text-shadow: 0 0 10px var(--neon-pink), 0 0 20px var(--neon-pink);
            letter-spacing: 5px;
            text-transform: uppercase;
            margin-bottom: 30px;
            font-size: 2.5em;
            animation: pulse 2s infinite;
        }

        .container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            max-width: 1200px;
            margin: 0 auto;
            position: relative;
            z-index: 10;
        }

        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-cyan);
            border-radius: 5px;
            padding: 20px;
            box-shadow: 0 0 15px rgba(0, 243, 255, 0.2) inset;
            transition: all 0.3s ease;
        }

        .panel:hover {
            box-shadow: 0 0 25px rgba(0, 243, 255, 0.5) inset, 0 0 10px var(--neon-cyan);
        }

        .panel-header {
            font-size: 1.2em;
            color: var(--neon-yellow);
            border-bottom: 1px solid var(--neon-yellow);
            padding-bottom: 10px;
            margin-bottom: 15px;
            text-shadow: 0 0 5px var(--neon-yellow);
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        .item {
            margin-bottom: 15px;
            padding: 10px;
            background: rgba(0, 0, 0, 0.5);
            border-left: 3px solid var(--neon-green);
        }
        
        .item.alert { border-left-color: var(--neon-red); }
        .item.info { border-left-color: var(--neon-cyan); }

        .item-title {
            font-weight: bold;
            color: var(--neon-green);
            margin-bottom: 5px;
        }
        .item.alert .item-title { color: var(--neon-red); text-shadow: 0 0 5px var(--neon-red); }
        .item.info .item-title { color: var(--neon-cyan); }

        .status {
            float: right;
            font-size: 0.8em;
            padding: 2px 6px;
            border-radius: 3px;
        }
        .status.online { background: rgba(57, 255, 20, 0.2); color: var(--neon-green); border: 1px solid var(--neon-green); }
        .status.active { background: rgba(0, 243, 255, 0.2); color: var(--neon-cyan); border: 1px solid var(--neon-cyan); animation: blink 1s infinite; }

        @keyframes pulse {
            0% { opacity: 0.8; }
            50% { opacity: 1; text-shadow: 0 0 15px var(--neon-pink), 0 0 30px var(--neon-pink); }
            100% { opacity: 0.8; }
        }

        @keyframes blink {
            0% { opacity: 1; }
            50% { opacity: 0.5; }
            100% { opacity: 1; }
        }
        
        .data-row {
            display: flex;
            justify-content: space-between;
            font-size: 0.9em;
            margin-top: 5px;
            color: #aaa;
        }
        
        .data-value {
            color: #fff;
        }

    </style>
</head>
<body>

    <h1>🛰️ ORBITAL COMMAND 🛰️</h1>

    <div style="text-align: center; margin-bottom: 30px; border: 2px solid var(--neon-cyan); padding: 15px; background: rgba(0, 243, 255, 0.1); border-radius: 5px; box-shadow: 0 0 10px var(--neon-cyan); max-width: 800px; margin-left: auto; margin-right: auto;">
        <h2 style="margin: 0; color: var(--neon-green); text-shadow: 0 0 5px var(--neon-green); font-size: 1.5em;">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</h2>
        <p style="margin: 10px 0 0 0; color: #fff; font-size: 1.2em;">STATUS PATRIMONIO: <span style="color: var(--neon-yellow);">$ ---,---.--</span></p>
    </div>

    <div class="container">
        
        <!-- SQUADRE D'ASSALTO -->
        <div class="panel">
            <div class="panel-header">
                <span>⚔️ SQUADRE D'ASSALTO (HFT)</span>
                <span class="status active">ENGAGED</span>
            </div>
            
            <div class="item">
                <div class="item-title">🐺 SQUADRA_ALPHA <span class="status online">ONLINE</span></div>
                <div>Target: Binance Scalping</div>
                <div class="data-row"><span>Win Rate:</span> <span class="data-value">72.4%</span></div>
                <div class="data-row"><span>Latency:</span> <span class="data-value">12ms</span></div>
            </div>

            <div class="item">
                <div class="item-title">⚡ SQUADRA_DELTA <span class="status online">ONLINE</span></div>
                <div>Target: Order Flow Analysis</div>
                <div class="data-row"><span>Imbalance:</span> <span class="data-value" style="color:var(--neon-green)">+450 BTC (Buy)</span></div>
                <div class="data-row"><span>Spoofing Alert:</span> <span class="data-value">NONE</span></div>
            </div>

            <div class="item">
                <div class="item-title">⚖️ SQUADRA_GAMMA <span class="status online">ONLINE</span></div>
                <div>Target: Pairs Trading (Bitget)</div>
                <div class="data-row"><span>Active Pair:</span> <span class="data-value">BTC/ETH</span></div>
                <div class="data-row"><span>Spread Z-Score:</span> <span class="data-value" style="color:var(--neon-red)">+2.1σ</span></div>
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <div class="panel-header">
                <span>🛡️ PROTOCOLLO TRINITY</span>
                <span class="status online">SYS_NOMINAL</span>
            </div>
            
            <div class="item info">
                <div class="item-title">🕴️ LO STROZZINO <span class="status active">HUNTING</span></div>
                <div>Target: Funding Rate Arbitrage</div>
                <div class="data-row"><span>Spread:</span> <span class="data-value">0.05%</span></div>
                <div class="data-row"><span>Position:</span> <span class="data-value">Hedged ($10k)</span></div>
            </div>

            <div class="item info">
                <div class="item-title">🧮 IL CONTABILE <span class="status online">STANDBY</span></div>
                <div>Target: Smart DCA</div>
                <div class="data-row"><span>Next Buy:</span> <span class="data-value">BTC @ $62,100</span></div>
                <div class="data-row"><span>RSI 1H:</span> <span class="data-value">42</span></div>
            </div>

            <div class="item info">
                <div class="item-title">👼 L'ANGELO CUSTODE <span class="status online">GUARDING</span></div>
                <div>Target: MEV Protection (Arbitrum)</div>
                <div class="data-row"><span>Mempool:</span> <span class="data-value">Scanning...</span></div>
                <div class="data-row"><span>Tx Blocked:</span> <span class="data-value">12</span></div>
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <div class="panel-header">
                <span>📊 METRICHE DI MERCATO</span>
                <span class="status active">STREAMING</span>
            </div>
            
            <div class="item alert">
                <div class="item-title">👁️ THE ORACLE <span class="status online">SYNCED</span></div>
                <div>Target: Global Sentiment (Binance)</div>
                <div class="data-row"><span>Fear & Greed:</span> <span class="data-value" style="color:var(--neon-yellow)">65 (Greed)</span></div>
                <div class="data-row"><span>Funding Avg:</span> <span class="data-value">+0.01%</span></div>
            </div>

            <div class="item alert">
                <div class="item-title">🐳 WHALE TRACKER <span class="status active">ALERT</span></div>
                <div>Target: On-Chain Flow</div>
                <div class="data-row"><span>Large Tx:</span> <span class="data-value" style="color:var(--neon-red)">1,500 BTC -> Coinbase</span></div>
                <div class="data-row"><span>Exchange Net:</span> <span class="data-value">+$45M</span></div>
            </div>
            
            <div style="margin-top: 20px; text-align: center;">
                <canvas id="fakeChart" width="280" height="100"></canvas>
            </div>
        </div>

    </div>

    <script>
        const canvas = document.getElementById('fakeChart');
        const ctx = canvas.getContext('2d');
        let data = Array.from({length: 20}, () => Math.random() * 50 + 25);
        
        function drawChart() {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            
            ctx.strokeStyle = 'rgba(0, 243, 255, 0.1)';
            ctx.lineWidth = 1;
            for(let i=0; i<canvas.width; i+=20) {
                ctx.beginPath(); ctx.moveTo(i, 0); ctx.lineTo(i, canvas.height); ctx.stroke();
            }
            for(let i=0; i<canvas.height; i+=20) {
                ctx.beginPath(); ctx.moveTo(0, i); ctx.lineTo(canvas.width, i); ctx.stroke();
            }
            
            ctx.beginPath();
            ctx.strokeStyle = '#39ff14';
            ctx.lineWidth = 2;
            const step = canvas.width / (data.length - 1);
            
            for(let i=0; i<data.length; i++) {
                const x = i * step;
                const y = canvas.height - data[i];
                if(i === 0) ctx.moveTo(x, y);
                else ctx.lineTo(x, y);
            }
            ctx.stroke();
            
            data.shift();
            data.push(Math.random() * 50 + 25);
            
            setTimeout(drawChart, 500);
        }
        
        drawChart();
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
