from flask import Flask, render_template_string
import os

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NUVOLA ORBITAL COMMAND</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');
        
        :root {
            --bg-color: #05050a;
            --neon-cyan: #0ff;
            --neon-magenta: #f0f;
            --neon-red: #f03;
            --neon-green: #3f3;
            --neon-yellow: #ff0;
            --neon-orange: #f90;
            --grid-color: rgba(0, 255, 255, 0.08);
            --panel-bg: rgba(5, 5, 12, 0.85);
            --panel-border: rgba(0, 255, 255, 0.4);
        }

        body {
            background-color: var(--bg-color);
            color: var(--neon-cyan);
            font-family: 'Share Tech Mono', monospace;
            margin: 0;
            padding: 30px 40px;
            overflow-x: hidden;
            background-image: 
                linear-gradient(var(--grid-color) 1px, transparent 1px),
                linear-gradient(90deg, var(--grid-color) 1px, transparent 1px);
            background-size: 40px 40px;
            position: relative;
        }

        body::before {
            content: "";
            display: block;
            position: fixed;
            top: 0; left: 0; bottom: 0; right: 0;
            background: linear-gradient(rgba(18, 16, 16, 0) 50%, rgba(0, 0, 0, 0.3) 50%), 
                        linear-gradient(90deg, rgba(255, 0, 0, 0.04), rgba(0, 255, 0, 0.02), rgba(0, 0, 255, 0.04));
            z-index: 999;
            background-size: 100% 3px, 4px 100%;
            pointer-events: none;
        }

        h1 {
            text-align: center;
            color: var(--neon-red);
            text-shadow: 0 0 5px var(--neon-red), 0 0 15px var(--neon-red), 0 0 30px var(--neon-red);
            font-size: 4em;
            letter-spacing: 15px;
            border-bottom: 4px solid var(--neon-red);
            padding-bottom: 15px;
            margin-bottom: 40px;
            animation: glitch 2.5s infinite;
            text-transform: uppercase;
            position: relative;
            box-shadow: 0 15px 15px -15px var(--neon-red);
        }

        h1::after {
            content: "NUVOLA TACTICAL QUANTITATIVE OVERWATCH";
            position: absolute;
            bottom: -35px;
            left: 50%;
            transform: translateX(-50%);
            font-size: 0.25em;
            color: var(--neon-cyan);
            text-shadow: 0 0 8px var(--neon-cyan);
            letter-spacing: 8px;
            white-space: nowrap;
        }

        .container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(450px, 1fr));
            gap: 40px;
            max-width: 1800px;
            margin: 0 auto;
        }

        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--panel-border);
            box-shadow: 0 0 20px rgba(0, 255, 255, 0.15), inset 0 0 30px rgba(0, 255, 255, 0.05);
            border-radius: 2px;
            padding: 30px;
            position: relative;
            backdrop-filter: blur(10px);
            transition: all 0.3s ease;
        }

        .panel::before, .panel::after {
            content: '';
            position: absolute;
            width: 30px; height: 30px;
        }
        .panel::before { top: -2px; left: -2px; border-top: 3px solid var(--neon-cyan); border-left: 3px solid var(--neon-cyan); }
        .panel::after { bottom: -2px; right: -2px; border-bottom: 3px solid var(--neon-cyan); border-right: 3px solid var(--neon-cyan); }

        .panel:hover {
            box-shadow: 0 0 30px rgba(0, 255, 255, 0.3), inset 0 0 40px rgba(0, 255, 255, 0.1);
            border-color: var(--neon-cyan);
        }

        .panel-title {
            font-size: 2em;
            color: #fff;
            margin-top: 0;
            border-bottom: 1px dashed var(--neon-cyan);
            padding-bottom: 15px;
            text-shadow: 0 0 15px var(--neon-cyan);
            display: flex;
            align-items: center;
            gap: 15px;
            text-transform: uppercase;
            letter-spacing: 2px;
        }

        .status {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin: 20px 0;
            padding: 15px 25px;
            background: rgba(0, 0, 0, 0.6);
            border-left: 5px solid;
            font-size: 1.3em;
            letter-spacing: 1px;
            position: relative;
            clip-path: polygon(0 0, 100% 0, 98% 100%, 0 100%);
        }

        .status::after {
            content: '';
            position: absolute;
            right: 25px;
            top: 50%;
            transform: translateY(-50%);
            width: 10px;
            height: 10px;
            border-radius: 50%;
        }

        .status.active { 
            border-color: var(--neon-green); color: var(--neon-green); 
            text-shadow: 0 0 10px var(--neon-green); 
            box-shadow: inset 0 0 15px rgba(51, 255, 51, 0.15);
        }
        .status.active::after { background-color: var(--neon-green); box-shadow: 0 0 15px var(--neon-green); animation: pulse 1s infinite; }

        .status.standby { 
            border-color: var(--neon-orange); color: var(--neon-orange); 
            text-shadow: 0 0 10px var(--neon-orange); 
            box-shadow: inset 0 0 15px rgba(255, 153, 0, 0.15);
        }
        .status.standby::after { background-color: var(--neon-orange); box-shadow: 0 0 15px var(--neon-orange); }

        .status.trinity { 
            border-color: var(--neon-magenta); color: var(--neon-magenta); 
            text-shadow: 0 0 10px var(--neon-magenta); 
            box-shadow: inset 0 0 15px rgba(255, 0, 255, 0.15);
        }
        .status.trinity::after { background-color: var(--neon-magenta); box-shadow: 0 0 15px var(--neon-magenta); animation: pulse 1.5s infinite; }

        .glow-text { font-weight: bold; }
        .blink { animation: blinker 1s steps(2, start) infinite; }
        .fast-blink { animation: blinker 0.4s steps(2, start) infinite; }
        
        @keyframes blinker { to { visibility: hidden; } }
        @keyframes pulse { 0% { opacity: 1; transform: translateY(-50%) scale(1); } 50% { opacity: 0.4; transform: translateY(-50%) scale(1.5); } 100% { opacity: 1; transform: translateY(-50%) scale(1); } }
        @keyframes glitch {
            0% { text-shadow: 0 0 5px var(--neon-red), 0 0 15px var(--neon-red); }
            2% { transform: translate(-4px, 2px); text-shadow: -4px 0 var(--neon-cyan), 4px 0 var(--neon-red); }
            4% { transform: translate(4px, -2px); text-shadow: 4px 0 var(--neon-cyan), -4px 0 var(--neon-red); }
            6% { transform: translate(0, 0); text-shadow: 0 0 5px var(--neon-red), 0 0 15px var(--neon-red); }
        }
        @keyframes scan {
            0% { top: -100px; opacity: 0; }
            50% { opacity: 1; }
            100% { top: 100%; opacity: 0; }
        }

        .metric-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 25px;
            margin-top: 30px;
        }

        .metric-box {
            background: rgba(0, 255, 255, 0.02);
            border: 1px solid rgba(0, 255, 255, 0.3);
            padding: 25px;
            text-align: center;
            color: var(--neon-cyan);
            box-shadow: inset 0 0 20px rgba(0, 255, 255, 0.05);
            position: relative;
            overflow: hidden;
            display: flex;
            flex-direction: column;
            justify-content: center;
        }

        .metric-box::after {
            content: '';
            position: absolute;
            left: 0; right: 0;
            height: 20px;
            background: linear-gradient(to bottom, rgba(0,255,255,0.2) 0%, transparent 100%);
            animation: scan 4s linear infinite;
        }

        .metric-box.alert {
            border-color: var(--neon-red);
            color: var(--neon-red);
            box-shadow: inset 0 0 20px rgba(255, 0, 51, 0.1);
        }
        .metric-box.alert::after { background: linear-gradient(to bottom, rgba(255,0,51,0.2) 0%, transparent 100%); animation: scan 2s linear infinite; }

        .metric-box.trinity-metric {
            border-color: var(--neon-magenta);
            color: var(--neon-magenta);
        }
        .metric-box.trinity-metric::after { background: linear-gradient(to bottom, rgba(255,0,255,0.2) 0%, transparent 100%); }

        .metric-label { font-size: 1em; letter-spacing: 3px; opacity: 0.9; margin-bottom: 15px; }
        .metric-value { font-size: 2.2em; font-weight: bold; text-shadow: 0 0 15px currentColor; }

        .progress-bar { width: 100%; height: 6px; background: rgba(255,255,255,0.1); margin-top: 20px; border-radius: 0; overflow: hidden; }
        .progress-fill { height: 100%; background: var(--neon-cyan); box-shadow: 0 0 15px var(--neon-cyan); }

        .sys-log {
            margin-top: 40px;
            background: rgba(0,0,0,0.8);
            border: 1px solid rgba(255,255,255,0.1);
            padding: 20px;
            font-size: 1.1em;
            color: #aaa;
            height: 180px;
            overflow: hidden;
            border-left: 4px solid #555;
            position: relative;
        }

        .log-line {
            margin: 8px 0;
            opacity: 0;
            animation: fadeIn 0.3s forwards;
            font-family: monospace;
        }
        
        .log-line .prefix { color: var(--neon-yellow); }
        .log-line .success { color: var(--neon-green); }
        .log-line .warn { color: var(--neon-orange); }
        .log-line .crit { color: var(--neon-red); }

        .log-line:nth-child(1) { animation-delay: 0.2s; }
        .log-line:nth-child(2) { animation-delay: 1.0s; }
        .log-line:nth-child(3) { animation-delay: 1.8s; }
        .log-line:nth-child(4) { animation-delay: 2.5s; }
        .log-line:nth-child(5) { animation-delay: 3.2s; }
        .log-line:nth-child(6) { animation-delay: 4.0s; }

        @keyframes fadeIn { to { opacity: 1; } }

    </style>
</head>
<body>
    <h1>[⚡] ORBITAL COMMAND</h1>
    
    <div class="container">
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <h2 class="panel-title">⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <div class="status active">
                <span class="glow-text">🐺 SQUADRA_ALPHA</span>
                <span class="fast-blink">[ON - BINANCE SCALPER]</span>
            </div>
            <div class="status active">
                <span class="glow-text">🦅 SQUADRA_DELTA</span>
                <span class="fast-blink">[ON - ORDER FLOW]</span>
            </div>
            <div class="status standby">
                <span class="glow-text">🦂 SQUADRA_GAMMA</span>
                <span>[STBY - BITGET PAIRS]</span>
            </div>
            
            <div class="progress-bar" style="margin-top: 35px;">
                <div class="progress-fill" style="width: 85%; background: var(--neon-green); box-shadow: 0 0 15px var(--neon-green);"></div>
            </div>
            <div style="text-align: right; font-size: 0.9em; margin-top: 8px; color: var(--neon-green);">ASSAULT READINESS: 85%</div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2 class="panel-title">🛡️ PROTOCOLLO TRINITY</h2>
            <div style="color: var(--neon-cyan); font-weight: bold; font-size: 1.2em; text-align: center; padding-bottom: 15px; text-shadow: 0 0 5px var(--neon-cyan);">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</div>
            <div class="status trinity">
                <span class="glow-text">🕴️ Lo Strozzino</span>
                <span class="blink">[SYNC - FUNDING ARB]</span>
            </div>
            <div class="status trinity">
                <span class="glow-text">🧮 Il Contabile</span>
                <span class="blink">[SYNC - DCA CORE]</span>
            </div>
            <div class="status trinity">
                <span class="glow-text">👼 L'Angelo Custode</span>
                <span class="blink">[SYNC - ARBITRUM MEV]</span>
            </div>
            
            <div class="progress-bar" style="margin-top: 35px;">
                <div class="progress-fill" style="width: 100%; background: var(--neon-magenta); box-shadow: 0 0 15px var(--neon-magenta);"></div>
            </div>
            <div style="text-align: right; font-size: 0.9em; margin-top: 8px; color: var(--neon-magenta);">TRINITY INTEGRITY: 100%</div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel" style="grid-column: 1 / -1;">
            <h2 class="panel-title">📊 METRICHE DI MERCATO STRATEGICHE</h2>
            <div class="metric-grid">
                
                <div class="metric-box alert">
                    <div class="metric-label">🔮 THE ORACLE (SENTIMENT)</div>
                    <div class="metric-value blink">FEAR: 22</div>
                    <div class="progress-bar"><div class="progress-fill" style="width: 22%; background: var(--neon-red);"></div></div>
                </div>
                
                <div class="metric-box">
                    <div class="metric-label">🐋 WHALE TRACKER (NET 24H)</div>
                    <div class="metric-value" style="color: var(--neon-green);">+42.7M USD</div>
                    <div class="progress-bar"><div class="progress-fill" style="width: 85%; background: var(--neon-green);"></div></div>
                </div>
                
                <div class="metric-box trinity-metric">
                    <div class="metric-label">📈 FUNDING RATE (ETH/USDT)</div>
                    <div class="metric-value">0.0145%</div>
                    <div class="progress-bar"><div class="progress-fill" style="width: 65%; background: var(--neon-magenta);"></div></div>
                </div>
                
                <div class="metric-box">
                    <div class="metric-label">⚡ HFT EXECUTION LATENCY</div>
                    <div class="metric-value fast-blink" style="color: var(--neon-cyan);">6ms</div>
                    <div class="progress-bar"><div class="progress-fill" style="width: 6%;"></div></div>
                </div>

            </div>
            
            <div class="sys-log">
                <div class="log-line"><span class="prefix">root@orbital:~#</span> init sequence start</div>
                <div class="log-line">> [SYS] Authenticating node NUVOLA-01... <span class="success">OK</span></div>
                <div class="log-line">> [ORACLE] Ingesting Binance orderbook data (Depth: 5000)... <span class="success">OK</span></div>
                <div class="log-line">> [TRINITY] Lo Strozzino: Found spread > 0.15% on SOL-PERP. <span class="warn">Monitoring...</span></div>
                <div class="log-line">> [ALPHA] Executed 27 micro-trades in last 60s. PNL: <span class="success">+0.041%</span></div>
                <div class="log-line">> [MEV] L'Angelo Custode routing via Arbitrum Flashbots... <span class="success">SECURED</span></div>
                <div class="log-line blink" style="margin-top:15px; color: var(--neon-cyan);">_</div>
            </div>
        </div>
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
