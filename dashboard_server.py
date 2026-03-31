from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ORBITAL COMMAND | NUVOLA</title>
    <style>
        :root {
            --bg: #020202;
            --neon-green: #0f0;
            --neon-cyan: #0ff;
            --neon-magenta: #f0f;
            --neon-red: #f03;
            --neon-yellow: #ff0;
            --panel-bg: rgba(5, 10, 5, 0.85);
            --grid-line: rgba(0, 255, 0, 0.1);
        }
        @font-face {
            font-family: 'Share Tech Mono';
            src: url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');
        }
        * { box-sizing: border-box; }
        body {
            background-color: var(--bg);
            background-image: 
                linear-gradient(var(--grid-line) 1px, transparent 1px),
                linear-gradient(90deg, var(--grid-line) 1px, transparent 1px);
            background-size: 20px 20px;
            color: var(--neon-green);
            font-family: 'Share Tech Mono', 'Courier New', monospace;
            margin: 0;
            padding: 20px;
            overflow-x: hidden;
        }
        body::after {
            content: "";
            position: fixed;
            top: 0; left: 0; width: 100vw; height: 100vh;
            background: linear-gradient(rgba(18, 16, 16, 0) 50%, rgba(0, 0, 0, 0.25) 50%);
            background-size: 100% 4px;
            z-index: 999;
            pointer-events: none;
        }
        .crt {
            animation: textShadow 1.6s infinite;
        }
        @keyframes textShadow {
            0% { text-shadow: 0.438px 0 1px rgba(0,30,255,0.5), -0.438px 0 1px rgba(255,0,80,0.3), 0 0 3px; }
            5% { text-shadow: 2.792px 0 1px rgba(0,30,255,0.5), -2.792px 0 1px rgba(255,0,80,0.3), 0 0 3px; }
            100% { text-shadow: 0.438px 0 1px rgba(0,30,255,0.5), -0.438px 0 1px rgba(255,0,80,0.3), 0 0 3px; }
        }
        h1, h2, h3 { margin: 0; padding: 0; text-transform: uppercase; }
        .header {
            text-align: center;
            border: 2px solid var(--neon-cyan);
            box-shadow: 0 0 15px var(--neon-cyan), inset 0 0 15px var(--neon-cyan);
            padding: 20px;
            margin-bottom: 30px;
            position: relative;
            background: rgba(0, 255, 255, 0.05);
        }
        .header h1 {
            color: var(--neon-cyan);
            font-size: 2.5em;
            letter-spacing: 5px;
            text-shadow: 0 0 10px var(--neon-cyan);
        }
        .header .subtitle {
            color: var(--neon-magenta);
            font-size: 1.2em;
            margin-top: 10px;
            letter-spacing: 2px;
            animation: pulse 2s infinite;
        }
        .container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 30px;
            position: relative;
            z-index: 10;
        }
        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-green);
            box-shadow: 0 0 15px rgba(0, 255, 0, 0.2);
            padding: 25px;
            position: relative;
            overflow: hidden;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; width: 100%; height: 2px;
            background: var(--neon-green);
            box-shadow: 0 0 10px var(--neon-green);
        }
        .panel.cyan { border-color: var(--neon-cyan); box-shadow: 0 0 15px rgba(0, 255, 255, 0.2); color: var(--neon-cyan); }
        .panel.cyan::before { background: var(--neon-cyan); box-shadow: 0 0 10px var(--neon-cyan); }
        .panel.magenta { border-color: var(--neon-magenta); box-shadow: 0 0 15px rgba(255, 0, 255, 0.2); color: var(--neon-magenta); }
        .panel.magenta::before { background: var(--neon-magenta); box-shadow: 0 0 10px var(--neon-magenta); }
        .panel.red { border-color: var(--neon-red); box-shadow: 0 0 15px rgba(255, 0, 51, 0.2); color: var(--neon-red); }
        .panel.red::before { background: var(--neon-red); box-shadow: 0 0 10px var(--neon-red); }
        
        .panel h2 {
            font-size: 1.5em;
            margin-bottom: 20px;
            border-bottom: 1px dashed inherit;
            padding-bottom: 10px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .panel ul { list-style: none; padding: 0; margin: 0; }
        .panel li {
            margin-bottom: 15px;
            padding: 10px;
            background: rgba(0, 0, 0, 0.6);
            border-left: 4px solid var(--neon-green);
            display: flex;
            flex-direction: column;
        }
        .panel.cyan li { border-left-color: var(--neon-cyan); }
        .panel.magenta li { border-left-color: var(--neon-magenta); }
        .panel.red li { border-left-color: var(--neon-red); }
        
        .item-header {
            display: flex;
            justify-content: space-between;
            font-weight: bold;
            margin-bottom: 5px;
        }
        .item-status { font-size: 0.85em; opacity: 0.9; }
        .item-metrics {
            display: flex;
            justify-content: space-between;
            font-size: 0.8em;
            margin-top: 5px;
            border-top: 1px dotted rgba(255,255,255,0.2);
            padding-top: 5px;
        }
        .pulse { animation: pulse 1.5s infinite; }
        @keyframes pulse {
            0%, 100% { opacity: 1; text-shadow: 0 0 10px currentColor; }
            50% { opacity: 0.5; text-shadow: none; }
        }
        .glitch { position: relative; }
        .glitch::before, .glitch::after {
            content: attr(data-text);
            position: absolute;
            top: 0; left: 0;
            width: 100%; height: 100%;
            background: var(--bg);
        }
        .glitch::before {
            left: 2px; text-shadow: -1px 0 red; clip: rect(24px, 550px, 90px, 0);
            animation: glitch-anim-2 3s infinite linear alternate-reverse;
        }
        .glitch::after {
            left: -2px; text-shadow: -1px 0 blue; clip: rect(85px, 550px, 140px, 0);
            animation: glitch-anim 2.5s infinite linear alternate-reverse;
        }
        @keyframes glitch-anim {
            0% { clip: rect(11px, 9999px, 86px, 0); }
            20% { clip: rect(61px, 9999px, 19px, 0); }
            40% { clip: rect(98px, 9999px, 66px, 0); }
            60% { clip: rect(13px, 9999px, 48px, 0); }
            80% { clip: rect(4px, 9999px, 96px, 0); }
            100% { clip: rect(57px, 9999px, 73px, 0); }
        }
        @keyframes glitch-anim-2 {
            0% { clip: rect(29px, 9999px, 83px, 0); }
            20% { clip: rect(55px, 9999px, 3px, 0); }
            40% { clip: rect(14px, 9999px, 63px, 0); }
            60% { clip: rect(89px, 9999px, 41px, 0); }
            80% { clip: rect(77px, 9999px, 16px, 0); }
            100% { clip: rect(22px, 9999px, 98px, 0); }
        }
        .terminal {
            background: #000;
            border: 1px solid currentColor;
            padding: 15px;
            font-size: 0.85em;
            margin-top: 20px;
            height: 150px;
            overflow-y: hidden;
            position: relative;
        }
        .terminal::after {
            content: '_';
            animation: blink 1s step-end infinite;
        }
        @keyframes blink { 50% { opacity: 0; } }
        .chart-bar {
            height: 4px;
            background: currentColor;
            margin-top: 3px;
            box-shadow: 0 0 5px currentColor;
        }
        .sys-footer {
            text-align: center;
            margin-top: 40px;
            font-size: 0.8em;
            color: rgba(255, 255, 255, 0.4);
            border-top: 1px solid rgba(255, 255, 255, 0.1);
            padding-top: 10px;
        }
    </style>
</head>
<body class="crt">
    <div class="header">
        <h1 class="glitch" data-text="ORBITAL COMMAND [NUVOLA]">ORBITAL COMMAND [NUVOLA]</h1>
        <div class="subtitle pulse">/// SECURE QUANTUM UPLINK ACTIVE /// PROTOCOLLO TRINITY ENGAGED ///</div>
        <div style="margin-top: 15px; font-size: 1.2em; color: var(--neon-yellow); font-weight: bold; border: 1px solid var(--neon-yellow); display: inline-block; padding: 5px 15px; background: rgba(255, 255, 0, 0.1);">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</div>
    </div>

    <div class="container">
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel cyan">
            <h2><span>⚔️ SQUADRE D'ASSALTO</span> <span class="pulse" style="font-size: 0.6em;">[HFT ENGAGED]</span></h2>
            <ul>
                <li>
                    <div class="item-header"><span>🐺 SQUADRA_ALPHA</span> <span class="item-status">BINANCE SCALPER</span></div>
                    <div class="item-metrics"><span>PING: 8ms</span> <span>WIN RATE: 68.4%</span> <span>PNL_1H: <span style="color:#0f0">+1.24%</span></span></div>
                    <div class="chart-bar" style="width: 75%;"></div>
                </li>
                <li>
                    <div class="item-header"><span>⚡ SQUADRA_DELTA</span> <span class="item-status pulse">ORDER FLOW SCAN</span></div>
                    <div class="item-metrics"><span>IMBALANCE: 72% BUY</span> <span>VOL: $4.2M/m</span> <span>STATE: ARMING</span></div>
                    <div class="chart-bar" style="width: 45%;"></div>
                </li>
                <li>
                    <div class="item-header"><span>⚖️ SQUADRA_GAMMA</span> <span class="item-status">BITGET PAIRS</span></div>
                    <div class="item-metrics"><span>SPREAD: 0.08%</span> <span>Z-SCORE: 2.1</span> <span>STATE: STANDBY</span></div>
                    <div class="chart-bar" style="width: 20%;"></div>
                </li>
            </ul>
            <div class="terminal" id="term-hft">
                > Initializing Alpha core... OK<br>
                > Delta routing matrices... SYNCED<br>
                > Gamma fetching historicals... DONE<br>
                > Awaiting market catalyst...
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel magenta">
            <h2><span>🛡️ PROTOCOLLO TRINITY</span> <span class="pulse" style="font-size: 0.6em;">[BACKSTAGE OPS]</span></h2>
            <ul>
                <li>
                    <div class="item-header"><span>🕴️ LO STROZZINO</span> <span class="item-status pulse">FUNDING ARBITRAGE</span></div>
                    <div class="item-metrics"><span>APR: 28.5%</span> <span>POS: $12,400</span> <span>EXTRACTING YIELD</span></div>
                    <div class="chart-bar" style="width: 85%;"></div>
                </li>
                <li>
                    <div class="item-header"><span>🧮 IL CONTABILE</span> <span class="item-status">DCA ENGINE</span></div>
                    <div class="item-metrics"><span>NEXT BUY: 03H 45M</span> <span>ACCUM: 0.45 BTC</span> <span>MONITORING</span></div>
                    <div class="chart-bar" style="width: 60%;"></div>
                </li>
                <li>
                    <div class="item-header"><span>👼 L'ANGELO CUSTODE</span> <span class="item-status pulse">MEV ARBITRUM</span></div>
                    <div class="item-metrics"><span>BLOCKS WON: 18</span> <span>GAS: 12 GWEI</span> <span>SHIELDING ROUTES</span></div>
                    <div class="chart-bar" style="width: 90%;"></div>
                </li>
            </ul>
            <div class="terminal" id="term-trinity">
                > Strozzino delta neutral hedge active.<br>
                > Contabile rebalancing thresholds.<br>
                > Angelo Custode detected sandwich bot... Bypassing.<br>
                > TRINITY CORE: NOMINAL
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel red">
            <h2><span>👁️ METRICHE GLOBALI</span> <span class="pulse" style="font-size: 0.6em;">[DATA FEED]</span></h2>
            <ul>
                <li>
                    <div class="item-header"><span>🔮 THE ORACLE</span> <span class="item-status">SENTIMENT ENGINE</span></div>
                    <div class="item-metrics"><span>GREED INDEX: 82</span> <span>TWITTER: BULLISH</span> <span>WARNING: OVERHEATED</span></div>
                    <div class="chart-bar" style="width: 82%;"></div>
                </li>
                <li>
                    <div class="item-header"><span>🐳 WHALE TRACKER</span> <span class="item-status pulse">ON-CHAIN RADAR</span></div>
                    <div class="item-metrics"><span>LARGE TX: 14/HR</span> <span>EXCHANGE INFLOW: HIGH</span> <span>TRACKING</span></div>
                    <div class="chart-bar" style="width: 95%;"></div>
                </li>
                <li>
                    <div class="item-header"><span>🌪️ LIQUIDITY MAP</span> <span class="item-status">ORDERBOOK DEPTH</span></div>
                    <div class="item-metrics"><span>ASK WALL: $72.5k</span> <span>BID SUPP: $68.2k</span> <span>SKEW: -1.2</span></div>
                    <div class="chart-bar" style="width: 50%;"></div>
                </li>
            </ul>
            <div class="terminal" id="term-market">
                > ALERT: 2,500 BTC moved to Binance Hot Wallet.<br>
                > ORACLE_PRED: 78% probability of long squeeze.<br>
                > VOLATILITY_INDEX: VIX spiking.<br>
                > SYSTEM RECOMMENDATION: TIGHTEN STOPS
            </div>
        </div>
    </div>
    
    <div class="sys-footer">
        NUVOLA KERNEL v10.4.1 // UNAUTHORIZED ACCESS WILL TRIGGER LETHAL COUNTERMEASURES // PROPERTY OF SERGIO
    </div>

    <script>
        const terms = ['term-hft', 'term-trinity', 'term-market'];
        const logs = [
            "Calculating optimal spread...",
            "Adjusting risk parameters...",
            "Ping to Exchange: 12ms",
            "Executing micro-hedge...",
            "Order filled at VWAP",
            "Scanning mempool...",
            "Re-evaluating neural weights...",
            "Data feed updated.",
            "WARNING: High latency detected in route B"
        ];
        
        setInterval(() => {
            const termId = terms[Math.floor(Math.random() * terms.length)];
            const term = document.getElementById(termId);
            const log = logs[Math.floor(Math.random() * logs.length)];
            term.innerHTML += `<br>> ${log}`;
            term.scrollTop = term.scrollHeight;
        }, 3000);
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
