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
            --bg-color: #020204;
            --neon-cyan: #00f3ff;
            --neon-magenta: #ff00ff;
            --neon-red: #ff0055;
            --neon-green: #00ff66;
            --neon-yellow: #ffcc00;
            --grid-color: rgba(0, 243, 255, 0.05);
            --panel-bg: rgba(2, 2, 8, 0.85);
        }

        body {
            background-color: var(--bg-color);
            color: var(--neon-cyan);
            font-family: 'Share Tech Mono', monospace;
            margin: 0;
            padding: 20px 40px;
            overflow-x: hidden;
            background-image: 
                linear-gradient(var(--grid-color) 1px, transparent 1px),
                linear-gradient(90deg, var(--grid-color) 1px, transparent 1px);
            background-size: 30px 30px;
            position: relative;
        }

        /* Scanline effect */
        body::before {
            content: " ";
            display: block;
            position: fixed;
            top: 0;
            left: 0;
            bottom: 0;
            right: 0;
            background: linear-gradient(rgba(18, 16, 16, 0) 50%, rgba(0, 0, 0, 0.25) 50%), linear-gradient(90deg, rgba(255, 0, 0, 0.06), rgba(0, 255, 0, 0.02), rgba(0, 0, 255, 0.06));
            z-index: 999;
            background-size: 100% 2px, 3px 100%;
            pointer-events: none;
            opacity: 0.6;
        }

        h1 {
            text-align: center;
            color: var(--neon-red);
            text-shadow: 0 0 10px var(--neon-red), 0 0 20px var(--neon-red), 0 0 40px var(--neon-red);
            font-size: 3.5em;
            letter-spacing: 12px;
            border-bottom: 3px solid var(--neon-red);
            padding-bottom: 20px;
            margin-bottom: 30px;
            animation: glitch 3s infinite;
            text-transform: uppercase;
            position: relative;
        }

        h1::after {
            content: "TACTICAL QUANTITATIVE OVERWATCH";
            position: absolute;
            bottom: -25px;
            left: 50%;
            transform: translateX(-50%);
            font-size: 0.3em;
            color: var(--neon-cyan);
            text-shadow: 0 0 5px var(--neon-cyan);
            letter-spacing: 5px;
        }

        .trinity-banner {
            text-align: center;
            margin-bottom: 40px;
            padding: 15px;
            border: 2px solid var(--neon-magenta);
            background: rgba(255, 0, 255, 0.05);
            color: var(--neon-magenta);
            font-size: 1.8em;
            text-shadow: 0 0 10px var(--neon-magenta);
            box-shadow: inset 0 0 20px rgba(255, 0, 255, 0.1), 0 0 20px rgba(255, 0, 255, 0.2);
            border-radius: 4px;
            letter-spacing: 4px;
            position: relative;
            overflow: hidden;
        }

        .trinity-banner::before {
            content: '';
            position: absolute;
            top: 0; left: -100%;
            width: 50%; height: 100%;
            background: linear-gradient(90deg, transparent, rgba(255, 0, 255, 0.4), transparent);
            animation: sweep 3s linear infinite;
        }

        .container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 30px;
            max-width: 1600px;
            margin: 0 auto;
        }

        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-cyan);
            box-shadow: 0 0 15px rgba(0, 243, 255, 0.1), inset 0 0 20px rgba(0, 243, 255, 0.05);
            border-radius: 4px;
            padding: 25px;
            position: relative;
            backdrop-filter: blur(5px);
            transition: all 0.3s ease;
        }

        .panel::before {
            content: '';
            position: absolute;
            top: -2px; left: -2px;
            width: 20px; height: 20px;
            border-top: 2px solid var(--neon-cyan);
            border-left: 2px solid var(--neon-cyan);
        }
        .panel::after {
            content: '';
            position: absolute;
            bottom: -2px; right: -2px;
            width: 20px; height: 20px;
            border-bottom: 2px solid var(--neon-cyan);
            border-right: 2px solid var(--neon-cyan);
        }

        .panel:hover {
            box-shadow: 0 0 25px rgba(0, 243, 255, 0.3), inset 0 0 30px rgba(0, 243, 255, 0.1);
            border-color: #fff;
        }

        .panel-title {
            font-size: 1.8em;
            color: #fff;
            margin-top: 0;
            border-bottom: 1px dashed var(--neon-cyan);
            padding-bottom: 12px;
            text-shadow: 0 0 10px var(--neon-cyan);
            display: flex;
            align-items: center;
            gap: 15px;
            text-transform: uppercase;
        }

        .status {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin: 18px 0;
            padding: 12px 20px;
            background: rgba(0, 0, 0, 0.8);
            border-left: 4px solid;
            font-size: 1.2em;
            letter-spacing: 1px;
            position: relative;
        }

        .status::after {
            content: '';
            position: absolute;
            right: 10px;
            top: 50%;
            transform: translateY(-50%);
            width: 8px;
            height: 8px;
            border-radius: 50%;
        }

        .status.active { 
            border-color: var(--neon-green); 
            color: var(--neon-green); 
            text-shadow: 0 0 8px var(--neon-green); 
            box-shadow: inset 0 0 10px rgba(0, 255, 102, 0.1);
        }
        .status.active::after { background-color: var(--neon-green); box-shadow: 0 0 10px var(--neon-green); animation: pulse 1s infinite; }

        .status.standby { 
            border-color: var(--neon-yellow); 
            color: var(--neon-yellow); 
            text-shadow: 0 0 8px var(--neon-yellow); 
            box-shadow: inset 0 0 10px rgba(255, 204, 0, 0.1);
        }
        .status.standby::after { background-color: var(--neon-yellow); box-shadow: 0 0 10px var(--neon-yellow); }

        .status.trinity { 
            border-color: var(--neon-magenta); 
            color: var(--neon-magenta); 
            text-shadow: 0 0 8px var(--neon-magenta); 
            box-shadow: inset 0 0 10px rgba(255, 0, 255, 0.1);
        }
        .status.trinity::after { background-color: var(--neon-magenta); box-shadow: 0 0 10px var(--neon-magenta); animation: pulse 2s infinite; }

        .glow-text { font-weight: bold; }
        
        .blink { animation: blinker 1.5s steps(2, start) infinite; }
        .fast-blink { animation: blinker 0.5s steps(2, start) infinite; }
        
        @keyframes blinker { to { visibility: hidden; } }
        @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.3; } 100% { opacity: 1; } }
        @keyframes sweep { 0% { left: -100%; } 100% { left: 200%; } }
        @keyframes glitch {
            0% { text-shadow: 0 0 10px var(--neon-red), 0 0 20px var(--neon-red); }
            2% { transform: translate(-3px, 1px); text-shadow: -3px 0 var(--neon-cyan), 3px 0 var(--neon-red); }
            4% { transform: translate(3px, -1px); text-shadow: 3px 0 var(--neon-cyan), -3px 0 var(--neon-red); }
            6% { transform: translate(0, 0); text-shadow: 0 0 10px var(--neon-red), 0 0 20px var(--neon-red); }
        }

        .metric-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-top: 20px;
        }

        .metric-box {
            background: rgba(0, 243, 255, 0.03);
            border: 1px solid var(--neon-cyan);
            padding: 20px;
            text-align: center;
            color: var(--neon-cyan);
            box-shadow: inset 0 0 15px rgba(0, 243, 255, 0.1);
            position: relative;
            overflow: hidden;
            display: flex;
            flex-direction: column;
            justify-content: center;
        }

        .metric-box.alert {
            border-color: var(--neon-red);
            color: var(--neon-red);
            box-shadow: inset 0 0 15px rgba(255, 0, 85, 0.1);
        }

        .metric-box::before {
            content: '';
            position: absolute;
            top: 0; left: 0; width: 100%; height: 2px;
            background: var(--neon-cyan);
            opacity: 0.5;
        }

        .metric-box.alert::before { background: var(--neon-red); }

        .metric-label {
            font-size: 0.9em;
            letter-spacing: 2px;
            opacity: 0.8;
            margin-bottom: 10px;
        }

        .metric-value {
            font-size: 1.8em;
            font-weight: bold;
            text-shadow: 0 0 10px currentColor;
        }

        .progress-bar {
            width: 100%;
            height: 4px;
            background: rgba(255,255,255,0.1);
            margin-top: 15px;
            border-radius: 2px;
            overflow: hidden;
        }

        .progress-fill {
            height: 100%;
            background: var(--neon-cyan);
            box-shadow: 0 0 10px var(--neon-cyan);
        }

        .footer {
            text-align: center;
            margin-top: 80px;
            color: #555;
            font-size: 1em;
            letter-spacing: 5px;
            border-top: 1px solid #333;
            padding-top: 20px;
        }

        .sys-log {
            margin-top: 30px;
            background: rgba(0,0,0,0.9);
            border: 1px solid #333;
            padding: 15px;
            font-size: 0.9em;
            color: #888;
            height: 100px;
            overflow: hidden;
            border-radius: 4px;
        }

        .log-line {
            margin: 5px 0;
            opacity: 0;
            animation: fadeIn 0.5s forwards;
        }
        
        .log-line:nth-child(1) { animation-delay: 0.5s; }
        .log-line:nth-child(2) { animation-delay: 1.5s; }
        .log-line:nth-child(3) { animation-delay: 2.5s; }
        .log-line:nth-child(4) { animation-delay: 3.5s; }

        @keyframes fadeIn { to { opacity: 1; } }

    </style>
</head>
<body>
    <h1>[⚡] ORBITAL COMMAND [⚡]</h1>
    
    <div class="trinity-banner blink">
        ⬡ PROTOCOLLO TRINITY: ATTIVO IN BACKGROUND ⬡<br>
        <span style="font-size: 0.8em; color: var(--neon-cyan);">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</span>
    </div>
    
    <div class="container">
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <h2 class="panel-title">⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <div class="status active">
                <span class="glow-text">🐺 SQUADRA_ALPHA</span>
                <span class="fast-blink">[DEPLOYED - Binance Scalper]</span>
            </div>
            <div class="status active">
                <span class="glow-text">🦅 SQUADRA_DELTA</span>
                <span class="fast-blink">[DEPLOYED - Order Flow]</span>
            </div>
            <div class="status standby">
                <span class="glow-text">🦂 SQUADRA_GAMMA</span>
                <span>[STANDBY - Bitget Pairs]</span>
            </div>
            
            <div class="progress-bar" style="margin-top: 25px;">
                <div class="progress-fill" style="width: 85%; background: var(--neon-green); box-shadow: 0 0 10px var(--neon-green);"></div>
            </div>
            <div style="text-align: right; font-size: 0.8em; margin-top: 5px; color: var(--neon-green);">COMBAT READINESS: 85%</div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2 class="panel-title">🛡️ PROTOCOLLO TRINITY</h2>
            <div class="status trinity">
                <span class="glow-text">🕴️ Lo Strozzino</span>
                <span class="blink">[SYNCED - Funding Arb]</span>
            </div>
            <div class="status trinity">
                <span class="glow-text">🧮 Il Contabile</span>
                <span class="blink">[SYNCED - DCA Core]</span>
            </div>
            <div class="status trinity">
                <span class="glow-text">👼 L'Angelo Custode</span>
                <span class="blink">[SYNCED - Arbitrum MEV]</span>
            </div>
            
            <div class="progress-bar" style="margin-top: 25px;">
                <div class="progress-fill" style="width: 100%; background: var(--neon-magenta); box-shadow: 0 0 10px var(--neon-magenta);"></div>
            </div>
            <div style="text-align: right; font-size: 0.8em; margin-top: 5px; color: var(--neon-magenta);">SYSTEM INTEGRITY: 100%</div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel" style="grid-column: 1 / -1;">
            <h2 class="panel-title">📊 METRICHE DI MERCATO STRATEGICHE</h2>
            <div class="metric-grid" style="grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));">
                
                <div class="metric-box alert">
                    <div class="metric-label">🔮 THE ORACLE (FEAR/GREED)</div>
                    <div class="metric-value blink">FEAR: 28</div>
                    <div class="progress-bar"><div class="progress-fill" style="width: 28%; background: var(--neon-red);"></div></div>
                </div>
                
                <div class="metric-box">
                    <div class="metric-label">🐋 WHALE TRACKER (NET FLOW)</div>
                    <div class="metric-value">+18.4M USD</div>
                    <div class="progress-bar"><div class="progress-fill" style="width: 75%;"></div></div>
                </div>
                
                <div class="metric-box">
                    <div class="metric-label">📈 BINANCE SENTIMENT</div>
                    <div class="metric-value">LONG 71.2%</div>
                    <div class="progress-bar"><div class="progress-fill" style="width: 71.2%;"></div></div>
                </div>
                
                <div class="metric-box">
                    <div class="metric-label">⚡ EXECUTION LATENCY</div>
                    <div class="metric-value fast-blink" style="color: var(--neon-green); text-shadow: 0 0 10px var(--neon-green);">8ms</div>
                    <div class="progress-bar"><div class="progress-fill" style="width: 8%; background: var(--neon-green);"></div></div>
                </div>

            </div>
            
            <div class="sys-log">
                <div class="log-line">> [SYS] Authenticating node NUVOLA-01... OK</div>
                <div class="log-line">> [ORACLE] Ingesting Binance orderbook data (Depth: 1000)... OK</div>
                <div class="log-line">> [TRINITY] Lo Strozzino: Found spread > 0.1% on ETH-PERP. Monitoring...</div>
                <div class="log-line">> [ALPHA] Executed 14 micro-trades in last 60s. PNL: +0.024%</div>
            </div>
        </div>
    </div>
    
    <div class="footer">
        SYS.CORE.V10.1.X // ENCRYPTED UPLINK ESTABLISHED // <span class="blink" style="color: var(--neon-cyan);">QUANTITATIVE OVERWATCH ACTIVE</span>
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
