from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ORBITAL COMMAND [NUVOLA]</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');

        :root {
            --neon-blue: #00f3ff;
            --neon-red: #ff003c;
            --neon-green: #00ff66;
            --neon-purple: #bd00ff;
            --neon-yellow: #fcee0a;
            --dark-bg: #030508;
            --grid-color: rgba(0, 243, 255, 0.08);
            --panel-bg: rgba(5, 10, 15, 0.85);
        }
        
        * {
            box-sizing: border-box;
        }

        body {
            background-color: var(--dark-bg);
            color: var(--neon-blue);
            font-family: 'Share Tech Mono', monospace;
            margin: 0;
            padding: 20px;
            background-image: 
                linear-gradient(var(--grid-color) 1px, transparent 1px),
                linear-gradient(90deg, var(--grid-color) 1px, transparent 1px);
            background-size: 30px 30px;
            overflow-x: hidden;
            text-transform: uppercase;
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
            background: linear-gradient(rgba(18, 16, 16, 0) 50%, rgba(0, 0, 0, 0.25) 50%), linear-gradient(90deg, rgba(255, 0, 0, 0.06), rgba(0, 255, 0, 0.02), rgba(0, 0, 255, 0.06));
            z-index: 2;
            background-size: 100% 2px, 3px 100%;
            pointer-events: none;
        }

        h1, h2, h3 {
            margin: 0 0 15px 0;
            font-weight: normal;
        }
        
        h1 {
            text-align: center;
            font-size: 2.8em;
            color: #fff;
            text-shadow: 0 0 5px #fff, 0 0 10px #fff, 0 0 20px var(--neon-blue), 0 0 40px var(--neon-blue), 0 0 80px var(--neon-blue);
            margin-bottom: 30px;
            border-bottom: 2px solid var(--neon-blue);
            padding-bottom: 15px;
            box-shadow: 0 15px 15px -15px var(--neon-blue);
            letter-spacing: 4px;
        }

        .alert-banner {
            text-align: center; 
            color: var(--neon-yellow); 
            text-shadow: 0 0 10px var(--neon-yellow); 
            font-size: 1.2em; 
            margin-bottom: 20px; 
            border: 1px dashed var(--neon-yellow); 
            padding: 10px; 
            background: rgba(252, 238, 10, 0.05);
            animation: pulse-alert 3s infinite;
        }

        .container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 25px;
            max-width: 1600px;
            margin: 0 auto;
            position: relative;
            z-index: 10;
        }

        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-blue);
            padding: 25px;
            border-radius: 2px;
            box-shadow: inset 0 0 20px rgba(0, 243, 255, 0.1), 0 0 10px rgba(0, 243, 255, 0.2);
            position: relative;
            backdrop-filter: blur(5px);
        }

        .panel::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 15px;
            height: 15px;
            border-top: 2px solid var(--neon-blue);
            border-left: 2px solid var(--neon-blue);
        }
        .panel::after {
            content: '';
            position: absolute;
            bottom: 0;
            right: 0;
            width: 15px;
            height: 15px;
            border-bottom: 2px solid var(--neon-blue);
            border-right: 2px solid var(--neon-blue);
        }

        .panel-title {
            color: var(--neon-blue);
            font-size: 1.4em;
            text-shadow: 0 0 8px var(--neon-blue);
            border-bottom: 1px dashed rgba(0, 243, 255, 0.5);
            padding-bottom: 8px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .status {
            display: inline-block;
            padding: 2px 6px;
            font-size: 0.75em;
            letter-spacing: 1px;
            border: 1px solid;
        }

        .status.online {
            color: var(--neon-green);
            border-color: var(--neon-green);
            box-shadow: 0 0 8px rgba(0, 255, 102, 0.4);
            animation: pulse-green 2s infinite;
        }
        
        .status.standby {
            color: var(--neon-yellow);
            border-color: var(--neon-yellow);
            box-shadow: 0 0 8px rgba(252, 238, 10, 0.4);
        }

        @keyframes pulse-green {
            0% { box-shadow: 0 0 5px rgba(0, 255, 102, 0.2); }
            50% { box-shadow: 0 0 15px rgba(0, 255, 102, 0.6); }
            100% { box-shadow: 0 0 5px rgba(0, 255, 102, 0.2); }
        }

        @keyframes pulse-alert {
            0% { border-color: rgba(252, 238, 10, 0.3); }
            50% { border-color: rgba(252, 238, 10, 1); }
            100% { border-color: rgba(252, 238, 10, 0.3); }
        }

        .unit-card {
            margin-top: 15px;
            padding: 12px;
            background: rgba(0, 0, 0, 0.6);
            border-left: 3px solid var(--neon-blue);
            transition: all 0.3s ease;
        }
        
        .unit-card:hover {
            background: rgba(0, 243, 255, 0.1);
            transform: translateX(5px);
        }

        .unit-header {
            display: flex;
            justify-content: space-between;
            margin-bottom: 5px;
            font-size: 1.1em;
            color: #fff;
        }

        .unit-details {
            display: grid;
            grid-template-columns: 1fr 1fr;
            font-size: 0.8em;
            color: #aaa;
            gap: 5px;
        }
        
        .unit-details span {
            color: var(--neon-blue);
        }

        /* Specific Panel Colors */
        .panel.trinity {
            border-color: var(--neon-purple);
            box-shadow: inset 0 0 20px rgba(189, 0, 255, 0.1), 0 0 10px rgba(189, 0, 255, 0.2);
        }
        .panel.trinity::before, .panel.trinity::after { border-color: var(--neon-purple); }
        .panel.trinity .panel-title { color: var(--neon-purple); text-shadow: 0 0 8px var(--neon-purple); border-bottom-color: rgba(189, 0, 255, 0.5); }
        .panel.trinity .unit-card { border-left-color: var(--neon-purple); }
        .panel.trinity .unit-card:hover { background: rgba(189, 0, 255, 0.1); }
        .panel.trinity .unit-details span { color: var(--neon-purple); }

        .metric-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
            margin-top: 15px;
        }

        .metric-box {
            background: rgba(0, 0, 0, 0.7);
            border: 1px solid rgba(0, 243, 255, 0.3);
            padding: 15px 10px;
            text-align: center;
            position: relative;
            overflow: hidden;
        }

        .metric-box::before {
            content: '';
            position: absolute;
            top: 0;
            left: -100%;
            width: 100%;
            height: 1px;
            background: linear-gradient(90deg, transparent, var(--neon-blue), transparent);
            animation: scan 3s linear infinite;
        }

        @keyframes scan {
            0% { left: -100%; top: 0; }
            50% { left: 100%; top: 100%; }
            100% { left: 100%; top: 100%; }
        }

        .metric-value {
            font-size: 1.6em;
            color: #fff;
            text-shadow: 0 0 10px var(--neon-blue);
            margin-bottom: 5px;
        }
        
        .metric-label {
            font-size: 0.75em;
            color: #888;
            letter-spacing: 1px;
        }

        .blink { animation: blinker 1s steps(2, start) infinite; }
        @keyframes blinker { to { visibility: hidden; } }

        .terminal-container {
            grid-column: 1 / -1;
            background: rgba(0, 0, 0, 0.9);
            border: 1px solid #333;
            border-top: 2px solid var(--neon-blue);
            height: 200px;
            padding: 15px;
            font-size: 0.85em;
            color: #0f0;
            overflow-y: auto;
            scrollbar-width: thin;
            scrollbar-color: var(--neon-blue) #111;
            font-family: 'Courier New', monospace;
            box-shadow: inset 0 0 20px rgba(0,0,0,1);
        }

        .terminal-container p { margin: 4px 0; }
        .term-time { color: #555; margin-right: 10px; }
        .term-tag.ops { color: var(--neon-blue); }
        .term-tag.warn { color: var(--neon-yellow); }
        .term-tag.err { color: var(--neon-red); }
        .term-tag.sys { color: #888; }
        .term-tag.trn { color: var(--neon-purple); }

        /* Tactical Radar */
        .radar {
            position: absolute;
            top: 15px;
            right: 15px;
            width: 40px;
            height: 40px;
            border-radius: 50%;
            border: 1px solid var(--neon-green);
            background: radial-gradient(circle, rgba(0,255,102,0.1) 0%, rgba(0,0,0,0) 70%);
            overflow: hidden;
        }
        .radar::after {
            content: '';
            position: absolute;
            top: 50%;
            left: 50%;
            width: 50%;
            height: 2px;
            background: var(--neon-green);
            transform-origin: left center;
            animation: radar-spin 2s linear infinite;
            box-shadow: 0 0 10px var(--neon-green);
        }
        @keyframes radar-spin { 100% { transform: rotate(360deg); } }

    </style>
</head>
<body>
    <h1><span style="color:var(--neon-blue)">//</span> ORBITAL COMMAND <span class="blink">_</span></h1>
    
    <div class="alert-banner">
        ⚠ GLOBAL OVERRIDE ACTIVE // PROTOCOLLO TRINITY SECURING BACKGROUND OPERATIONS
    </div>

    <div style="text-align: center; margin-bottom: 25px; padding: 15px; background: rgba(189, 0, 255, 0.1); border: 1px solid var(--neon-purple); color: #fff; font-size: 1.2em; text-shadow: 0 0 5px var(--neon-purple); box-shadow: 0 0 15px rgba(189, 0, 255, 0.2); animation: pulse-alert 3s infinite;">
        ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
    </div>

    <div class="container">
        <!-- SEZIONE 1: SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <div class="radar"></div>
            <h2 class="panel-title">⚔️ SQUADRE D'ASSALTO <span style="font-size:0.5em; color:#555">HFT_MODULE</span></h2>
            
            <div class="unit-card">
                <div class="unit-header">
                    <span>🐺 SQUADRA_ALPHA</span>
                    <span class="status online">ENGAGED</span>
                </div>
                <div class="unit-details">
                    <div>TARGET: <span>BINANCE [BTC/USDT]</span></div>
                    <div>STRATEGY: <span>SCALPING [ML]</span></div>
                    <div>LATENCY: <span>11.4ms</span></div>
                    <div>WIN RATE: <span style="color:var(--neon-green)">71.2%</span></div>
                </div>
            </div>

            <div class="unit-card" style="border-left-color: var(--neon-yellow);">
                <div class="unit-header">
                    <span>⚡ SQUADRA_DELTA</span>
                    <span class="status standby">STANDBY</span>
                </div>
                <div class="unit-details">
                    <div>TARGET: <span>GLOBAL_MEMPOOL</span></div>
                    <div>STRATEGY: <span>ORDER_FLOW</span></div>
                    <div>LIQUIDITY: <span style="color:var(--neon-yellow)">SEARCHING</span></div>
                    <div>UPTIME: <span>99.9%</span></div>
                </div>
            </div>

            <div class="unit-card">
                <div class="unit-header">
                    <span>⚖️ SQUADRA_GAMMA</span>
                    <span class="status online">ENGAGED</span>
                </div>
                <div class="unit-details">
                    <div>TARGET: <span>BITGET [ETH/USDT]</span></div>
                    <div>STRATEGY: <span>STAT_ARB</span></div>
                    <div>SPREAD: <span>0.18%</span></div>
                    <div>VOL_24H: <span>$842K</span></div>
                </div>
            </div>
        </div>

        <!-- SEZIONE 2: PROTOCOLLO TRINITY -->
        <div class="panel trinity">
            <h2 class="panel-title">🔺 PROTOCOLLO TRINITY <span style="font-size:0.5em; color:#555">CORE_OVERSEERS</span></h2>
            
            <div class="unit-card">
                <div class="unit-header">
                    <span>🕴️ LO STROZZINO</span>
                    <span class="status online" style="color:var(--neon-purple); border-color:var(--neon-purple); box-shadow: 0 0 8px rgba(189,0,255,0.4);">ACTIVE</span>
                </div>
                <div class="unit-details">
                    <div>ROLE: <span>FUNDING_ARB</span></div>
                    <div>TARGET: <span>PERP_MARKETS</span></div>
                    <div>YIELDING: <span>~16.4% APY</span></div>
                    <div>COLLECTED: <span>$1,420.50</span></div>
                </div>
            </div>

            <div class="unit-card">
                <div class="unit-header">
                    <span>🧮 IL CONTABILE</span>
                    <span class="status online" style="color:var(--neon-purple); border-color:var(--neon-purple); box-shadow: 0 0 8px rgba(189,0,255,0.4);">ACTIVE</span>
                </div>
                <div class="unit-details">
                    <div>ROLE: <span>SMART_DCA</span></div>
                    <div>ASSETS: <span>BTC, ETH, SOL</span></div>
                    <div>NEXT_EXEC: <span>in 04:12:00</span></div>
                    <div>PHASE: <span>ACCUMULATION</span></div>
                </div>
            </div>

            <div class="unit-card">
                <div class="unit-header">
                    <span>🛡️ L'ANGELO CUSTODE</span>
                    <span class="status online" style="color:var(--neon-purple); border-color:var(--neon-purple); box-shadow: 0 0 8px rgba(189,0,255,0.4);">ACTIVE</span>
                </div>
                <div class="unit-details">
                    <div>ROLE: <span>MEV_PROTECT</span></div>
                    <div>NETWORK: <span>ARBITRUM_ONE</span></div>
                    <div>SCANNED_TX: <span>1,850 / sec</span></div>
                    <div>ATTACKS_BLOCKED: <span>142</span></div>
                </div>
            </div>
        </div>

        <!-- SEZIONE 3: METRICHE DI MERCATO -->
        <div class="panel">
            <h2 class="panel-title">📊 METRICHE GLOBALI <span style="font-size:0.5em; color:#555">INTELLIGENCE</span></h2>
            
            <div class="metric-grid">
                <div class="metric-box">
                    <div class="metric-value" style="color:var(--neon-green)">BULL 72%</div>
                    <div class="metric-label">THE ORACLE (SENTIMENT)</div>
                </div>
                <div class="metric-box">
                    <div class="metric-value" style="color:var(--neon-blue)">+$2.1B</div>
                    <div class="metric-label">WHALE TRACKER (24H IN)</div>
                </div>
                <div class="metric-box">
                    <div class="metric-value" style="color:var(--neon-yellow)">VIX 48.5</div>
                    <div class="metric-label">GLOBAL VOLATILITY</div>
                </div>
                <div class="metric-box">
                    <div class="metric-value" style="color:var(--neon-red)">-$84.2M</div>
                    <div class="metric-label">LIQUIDATIONS (1H)</div>
                </div>
                <div class="metric-box" style="grid-column: 1 / -1; padding: 10px;">
                    <div style="font-size:0.8em; color:#aaa; margin-bottom:5px;">NETWORK CONGESTION (ETH)</div>
                    <div style="width:100%; height:10px; background:#111; border:1px solid #333;">
                        <div style="width:35%; height:100%; background:var(--neon-green); box-shadow:0 0 5px var(--neon-green);"></div>
                    </div>
                    <div style="font-size:0.7em; text-align:right; margin-top:3px;">14 GWEI // OPTIMAL</div>
                </div>
            </div>
        </div>

        <!-- TERMINALE LOG -->
        <div class="terminal-container" id="terminal">
            <p><span class="term-time">[00:00:00.000]</span> <span class="term-tag sys">[SYS]</span> System reboot initiated. Loading NUVOLA KERNEL v4.5.2-QUANT...</p>
            <p><span class="term-time">[00:00:00.120]</span> <span class="term-tag sys">[SYS]</span> Handshake with Binance, OKX, Bitget established. Avg Ping: 12ms.</p>
            <p><span class="term-time">[00:00:01.405]</span> <span class="term-tag trn">[TRN]</span> TRINITY PROTOCOL: All overseers online and locked.</p>
        </div>
    </div>

    <script>
        const terminal = document.getElementById('terminal');
        const logs = [
            { tag: 'ops', label: '[OPS]', text: 'SQUADRA_ALPHA: Executed micro-scalp BTC/USDT. PnL: +$12.40' },
            { tag: 'ops', label: '[OPS]', text: 'SQUADRA_GAMMA: Rebalancing portfolio weights on Bitget.' },
            { tag: 'warn', label: '[WRN]', text: 'SQUADRA_DELTA: Liquidity void detected at $64,100. Holding fire.' },
            { tag: 'trn', label: '[TRN]', text: 'LO STROZZINO: Funding rate spiked on SOL. Adjusting arb sizing.' },
            { tag: 'trn', label: '[TRN]', text: "L'ANGELO CUSTODE: Blocked sandwich attack on Uniswap V3 (Arb)." },
            { tag: 'sys', label: '[SYS]', text: 'THE ORACLE: Analyzing 15,000 new tweets. Sentiment stable.' },
            { tag: 'sys', label: '[SYS]', text: 'WHALE TRACKER: Alert! 5,000 ETH moved to Coinbase.' },
            { tag: 'trn', label: '[TRN]', text: 'IL CONTABILE: Verifying fiat on-ramp deposits for next epoch.' },
            { tag: 'err', label: '[ERR]', text: 'API RATE LIMIT WARNING: OKX WebSocket (Ignored, switching nodes)' },
        ];

        function getTimeString() {
            const now = new Date();
            const h = String(now.getHours()).padStart(2, '0');
            const m = String(now.getMinutes()).padStart(2, '0');
            const s = String(now.getSeconds()).padStart(2, '0');
            const ms = String(now.getMilliseconds()).padStart(3, '0');
            return `[${h}:${m}:${s}.${ms}]`;
        }

        function appendLog() {
            const log = logs[Math.floor(Math.random() * logs.length)];
            const p = document.createElement('p');
            p.innerHTML = `<span class="term-time">${getTimeString()}</span> <span class="term-tag ${log.tag}">${log.label}</span> ${log.text}`;
            terminal.appendChild(p);
            
            if (terminal.childElementCount > 50) {
                terminal.removeChild(terminal.firstChild);
            }
            terminal.scrollTop = terminal.scrollHeight;
            
            setTimeout(appendLog, Math.random() * 2500 + 500);
        }

        setTimeout(appendLog, 1000);
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    # Esegue su 0.0.0.0 porta 5000 in locale per Nuvola
    app.run(host='0.0.0.0', port=5000, debug=False)
