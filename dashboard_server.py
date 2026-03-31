from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NUVOLA ORBITAL COMMAND</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&family=Share+Tech+Mono&display=swap');
        
        :root {
            --bg: #030305;
            --neon-green: #0f0;
            --neon-blue: #0ff;
            --neon-pink: #f0f;
            --neon-red: #f00;
            --neon-yellow: #ff0;
            --panel-bg: rgba(5, 15, 10, 0.7);
            --border-glow: 0 0 10px rgba(0, 255, 0, 0.5), inset 0 0 10px rgba(0, 255, 0, 0.2);
        }
        
        * {
            box-sizing: border-box;
        }

        body {
            background-color: var(--bg);
            color: var(--neon-green);
            font-family: 'Share Tech Mono', monospace;
            margin: 0;
            padding: 15px;
            text-transform: uppercase;
            overflow-x: hidden;
        }

        /* Scanline effect */
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

        h1.title {
            text-align: center;
            font-family: 'Orbitron', sans-serif;
            font-size: 2.5rem;
            color: #fff;
            text-shadow: 0 0 5px #fff, 0 0 15px var(--neon-blue), 0 0 30px var(--neon-blue);
            border-bottom: 2px solid var(--neon-blue);
            padding-bottom: 10px;
            margin-top: 0;
            animation: flicker 4s infinite;
            letter-spacing: 4px;
        }

        @keyframes flicker {
            0%, 19%, 21%, 23%, 25%, 54%, 56%, 100% { opacity: 1; text-shadow: 0 0 5px #fff, 0 0 15px var(--neon-blue), 0 0 30px var(--neon-blue); }
            20%, 24%, 55% { opacity: 0.8; text-shadow: none; }
        }

        .sys-status {
            text-align: center;
            font-size: 1.2rem;
            margin-bottom: 25px;
            letter-spacing: 2px;
            border: 1px solid var(--neon-green);
            padding: 10px;
            box-shadow: 0 0 15px rgba(0,255,0,0.3);
            background: rgba(0, 255, 0, 0.1);
        }

        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 25px;
            position: relative;
            z-index: 10;
        }

        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-green);
            box-shadow: var(--border-glow);
            padding: 20px;
            position: relative;
            clip-path: polygon(0 0, 100% 0, 100% calc(100% - 20px), calc(100% - 20px) 100%, 0 100%);
            transition: all 0.3s ease;
        }
        
        .panel:hover {
            box-shadow: 0 0 20px rgba(0, 255, 0, 0.8), inset 0 0 15px rgba(0, 255, 0, 0.4);
            transform: translateY(-2px);
        }

        .panel.danger {
            border-color: var(--neon-red);
            box-shadow: 0 0 10px rgba(255, 0, 0, 0.5), inset 0 0 10px rgba(255, 0, 0, 0.2);
            color: var(--neon-red);
        }

        .panel.danger h2 {
            color: #fff;
            border-bottom-color: var(--neon-red);
            text-shadow: 0 0 10px var(--neon-red);
        }

        .panel.info {
            border-color: var(--neon-blue);
            box-shadow: 0 0 10px rgba(0, 255, 255, 0.5), inset 0 0 10px rgba(0, 255, 255, 0.2);
            color: var(--neon-blue);
        }
        
        .panel.info h2 {
            color: #fff;
            border-bottom-color: var(--neon-blue);
            text-shadow: 0 0 10px var(--neon-blue);
        }

        .panel h2 {
            font-family: 'Orbitron', sans-serif;
            color: #fff;
            text-shadow: 0 0 10px var(--neon-green);
            font-size: 1.4rem;
            margin-top: 0;
            border-bottom: 2px solid var(--neon-green);
            padding-bottom: 10px;
            display: flex;
            justify-content: space-between;
        }

        .metric {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px 0;
            border-bottom: 1px dotted rgba(255,255,255,0.2);
            font-size: 1.1rem;
        }

        .metric:last-child {
            border-bottom: none;
        }

        .status-badge {
            padding: 3px 8px;
            border-radius: 2px;
            font-weight: bold;
            font-size: 0.9rem;
            letter-spacing: 1px;
            animation: pulse 2s infinite;
        }

        .bg-green { background: rgba(0, 255, 0, 0.2); border: 1px solid #0f0; color: #0f0; }
        .bg-red { background: rgba(255, 0, 0, 0.2); border: 1px solid #f00; color: #f00; }
        .bg-yellow { background: rgba(255, 255, 0, 0.2); border: 1px solid #ff0; color: #ff0; }
        .bg-blue { background: rgba(0, 255, 255, 0.2); border: 1px solid #0ff; color: #0ff; }
        .bg-pink { background: rgba(255, 0, 255, 0.2); border: 1px solid #f0f; color: #f0f; }

        @keyframes pulse {
            0% { box-shadow: 0 0 0 0 rgba(0, 255, 0, 0.4); }
            70% { box-shadow: 0 0 0 10px rgba(0, 255, 0, 0); }
            100% { box-shadow: 0 0 0 0 rgba(0, 255, 0, 0); }
        }

        .blink {
            animation: blinker 1s cubic-bezier(.5, 0, 1, 1) infinite alternate;
        }
        @keyframes blinker {  
            from { opacity: 1; }
            to { opacity: 0; }
        }

        .progress-container {
            width: 100px;
            background: rgba(255,255,255,0.1);
            height: 8px;
            border: 1px solid #333;
            margin-left: 10px;
        }
        
        .progress-bar {
            height: 100%;
            background: var(--neon-green);
            box-shadow: 0 0 5px var(--neon-green);
        }
        
        .progress-bar.red { background: var(--neon-red); box-shadow: 0 0 5px var(--neon-red); }
        .progress-bar.blue { background: var(--neon-blue); box-shadow: 0 0 5px var(--neon-blue); }

        .terminal {
            margin-top: 30px;
            background: #000;
            border: 1px solid #333;
            border-left: 4px solid var(--neon-pink);
            padding: 15px;
            height: 150px;
            overflow: hidden;
            position: relative;
            color: #aaa;
            font-size: 0.9rem;
        }

        .terminal::before {
            content: "SYSTEM.LOG";
            position: absolute;
            top: 0; right: 0;
            background: var(--neon-pink);
            color: #000;
            padding: 2px 8px;
            font-size: 0.7rem;
            font-weight: bold;
        }

        .log-line { margin: 5px 0; }
        .log-time { color: var(--neon-blue); margin-right: 10px; }
        .log-warn { color: var(--neon-yellow); }
        .log-err { color: var(--neon-red); }
        .log-ok { color: var(--neon-green); }

        /* Random data changing animation */
        .random-data::after {
            content: "0";
            animation: randomize 2s infinite steps(10);
        }
        @keyframes randomize {
            0% { content: " 1.24k"; }
            25% { content: " 1.27k"; }
            50% { content: " 1.19k"; }
            75% { content: " 1.30k"; }
            100% { content: " 1.24k"; }
        }

        .crypto-ticker {
            width: 100%;
            overflow: hidden;
            background: #000;
            border-bottom: 1px solid #333;
            padding: 5px 0;
            white-space: nowrap;
            position: fixed;
            bottom: 0;
            left: 0;
            z-index: 100;
            font-size: 0.8rem;
        }
        .ticker-content {
            display: inline-block;
            animation: ticker 20s linear infinite;
        }
        @keyframes ticker {
            0% { transform: translateX(100vw); }
            100% { transform: translateX(-100%); }
        }
        .up { color: var(--neon-green); }
        .down { color: var(--neon-red); }
    </style>
</head>
<body>
    <h1 class="title">🛰️ ORBITAL COMMAND 🛰️</h1>
    
    <div class="sys-status">
        <span class="blink">⚡ SYSTEM ONLINE ⚡</span> | UPTIME: 99.99%<br>
        <span style="color:var(--neon-blue); font-weight: bold;">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</span>
    </div>
    
    <div class="grid">
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO <span>[HFT]</span></h2>
            
            <div class="metric">
                <span>🔴 SQUADRA_ALPHA <br><small style="color:#666; font-size:0.7em;">[Scalper su Binance]</small></span>
                <span class="status-badge bg-red blink">ENGAGED</span>
            </div>
            
            <div class="metric">
                <span>🔵 SQUADRA_DELTA <br><small style="color:#666; font-size:0.7em;">[Order Flow Analytics]</small></span>
                <span class="status-badge bg-blue">MONITORING</span>
            </div>
            
            <div class="metric">
                <span>🟣 SQUADRA_GAMMA <br><small style="color:#666; font-size:0.7em;">[Pairs Trading su Bitget]</small></span>
                <span class="status-badge bg-pink">STANDBY</span>
            </div>

            <div class="metric" style="margin-top: 15px; border:none;">
                <span style="font-size: 0.8rem; color:#888;">CPU LOAD</span>
                <div class="progress-container"><div class="progress-bar red" style="width: 87%;"></div></div>
            </div>
            <div class="metric" style="border:none;">
                <span style="font-size: 0.8rem; color:#888;">MEMORY TENSION</span>
                <div class="progress-container"><div class="progress-bar" style="width: 42%;"></div></div>
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel info">
            <h2>🛡️ PROTOCOLLO TRINITY <span>[BGD]</span></h2>
            
            <div class="metric">
                <span>🦈 LO STROZZINO <br><small style="color:#666; font-size:0.7em;">[Funding Arb | Perpetual]</small></span>
                <span class="status-badge bg-blue">YIELDING 14%</span>
            </div>
            
            <div class="metric">
                <span>🧮 IL CONTABILE <br><small style="color:#666; font-size:0.7em;">[DCA Grid | Accumulation]</small></span>
                <span class="status-badge bg-green">ACCUMULATING</span>
            </div>
            
            <div class="metric">
                <span>👼 L'ANGELO CUSTODE <br><small style="color:#666; font-size:0.7em;">[MEV Arbitrum Flashbots]</small></span>
                <span class="status-badge bg-yellow blink">SNIPING</span>
            </div>

            <div class="metric" style="margin-top: 15px; border:none; justify-content: flex-start;">
                <span style="font-size: 0.8rem; color:#888;">TRINITY SYNC RATE:</span>
                <span style="margin-left: 10px; color: var(--neon-blue);" class="random-data"></span>
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel danger">
            <h2>📊 THE ORACLE <span>[METRICS]</span></h2>
            
            <div class="metric">
                <span>👁️ BINANCE SENTIMENT</span>
                <div style="text-align: right;">
                    <div style="color:var(--neon-red); font-weight:bold; font-size:1.2rem;">84</div>
                    <div style="font-size:0.6rem; color:#888;">EXTREME GREED</div>
                </div>
            </div>
            
            <div class="metric">
                <span>🐋 WHALE TRACKER</span>
                <span class="status-badge bg-red blink">ALERT: 12k BTC MOVED</span>
            </div>
            
            <div class="metric">
                <span>⚡ ORDER BOOK IMBALANCE</span>
                <span style="color: var(--neon-yellow);">68% BID HEAVY</span>
            </div>
            
            <div class="metric">
                <span>📡 LATENCY HUB</span>
                <span style="color: var(--neon-green);">8ms (Tokyo)</span>
            </div>
        </div>
    </div>
    
    <div class="terminal">
        <div class="log-line"><span class="log-time">[03:59:12]</span><span class="log-ok">INIT</span> Orbital Command modules initialized.</div>
        <div class="log-line"><span class="log-time">[03:59:15]</span><span class="log-info">SYS</span> Protcollo Trinity loaded successfully in background.</div>
        <div class="log-line"><span class="log-time">[03:59:18]</span><span class="log-ok">HFT</span> SQUADRA_ALPHA deployed. Strategy: Binance Scalp.</div>
        <div class="log-line"><span class="log-time">[03:59:22]</span><span class="log-warn">WARN</span> Whale alert detected via The Oracle. Adjusting risk parameters.</div>
        <div class="log-line"><span class="log-time">[03:59:45]</span><span class="log-ok">MEV</span> L'Angelo Custode intercepted pending tx on Arbitrum. Profit locked.</div>
        <div class="log-line blink" style="margin-top:10px; color:var(--neon-green);">> _ </div>
    </div>

    <div class="crypto-ticker">
        <div class="ticker-content">
            BTC/USDT 69420.50 <span class="up">▲ 1.2%</span> &nbsp;&nbsp;&nbsp;
            ETH/USDT 3850.25 <span class="up">▲ 0.8%</span> &nbsp;&nbsp;&nbsp;
            SOL/USDT 145.80 <span class="down">▼ 2.1%</span> &nbsp;&nbsp;&nbsp;
            ARB/USDT 1.85 <span class="up">▲ 5.4%</span> &nbsp;&nbsp;&nbsp;
            BNB/USDT 610.10 <span class="up">▲ 0.3%</span> &nbsp;&nbsp;&nbsp;
            ORACLE_IDX 84.00 <span class="up">▲ GREED</span>
        </div>
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
