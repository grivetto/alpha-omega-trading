from flask import Flask, render_template_string
import logging

app = Flask(__name__)
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

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
            --neon-green: #39ff14;
            --neon-blue: #00f3ff;
            --neon-pink: #ff00ff;
            --neon-red: #ff003c;
            --neon-yellow: #fcee0a;
            --dark-bg: #030303;
            --panel-bg: rgba(10, 15, 20, 0.85);
            --grid-line: rgba(57, 255, 20, 0.1);
        }
        
        * { box-sizing: border-box; }

        body {
            background-color: var(--dark-bg);
            background-image: 
                linear-gradient(var(--grid-line) 1px, transparent 1px),
                linear-gradient(90deg, var(--grid-line) 1px, transparent 1px);
            background-size: 30px 30px;
            color: var(--neon-green);
            font-family: 'Share Tech Mono', monospace;
            margin: 0;
            padding: 2vh 2vw;
            overflow-x: hidden;
            text-transform: uppercase;
        }

        /* Scanline effect */
        body::after {
            content: " ";
            display: block;
            position: absolute;
            top: 0;
            left: 0;
            bottom: 0;
            right: 0;
            background: linear-gradient(rgba(18, 16, 16, 0) 50%, rgba(0, 0, 0, 0.25) 50%), linear-gradient(90deg, rgba(255, 0, 0, 0.06), rgba(0, 255, 0, 0.02), rgba(0, 0, 255, 0.06));
            z-index: 2;
            background-size: 100% 2px, 3px 100%;
            pointer-events: none;
        }

        h1, h2, h3 { margin: 0; font-weight: normal; }
        
        .header {
            text-align: center;
            border-bottom: 2px solid var(--neon-blue);
            padding-bottom: 10px;
            margin-bottom: 30px;
            position: relative;
            text-shadow: 0 0 10px var(--neon-blue), 0 0 20px var(--neon-blue);
        }
        
        .header h1 {
            color: var(--neon-blue);
            font-size: 2.5rem;
            letter-spacing: 4px;
        }
        
        .sys-status {
            color: var(--neon-yellow);
            font-size: 1.2rem;
            margin-top: 10px;
            text-shadow: 0 0 5px var(--neon-yellow);
        }

        .container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 30px;
            position: relative;
            z-index: 3;
        }

        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-green);
            padding: 20px;
            box-shadow: inset 0 0 20px rgba(57, 255, 20, 0.05), 0 0 15px rgba(57, 255, 20, 0.2);
            position: relative;
            clip-path: polygon(0 0, 100% 0, 100% calc(100% - 15px), calc(100% - 15px) 100%, 0 100%);
            transition: all 0.3s;
        }

        .panel::before {
            content: ''; position: absolute; top: 0; left: 0; width: 100%; height: 2px;
            background: var(--neon-green);
            box-shadow: 0 0 10px var(--neon-green);
        }

        .panel:hover {
            box-shadow: inset 0 0 30px rgba(57, 255, 20, 0.1), 0 0 25px rgba(57, 255, 20, 0.4);
        }

        .panel.trinity { 
            border-color: var(--neon-pink); 
            color: var(--neon-pink); 
            box-shadow: inset 0 0 20px rgba(255, 0, 255, 0.05), 0 0 15px rgba(255, 0, 255, 0.2);
        }
        .panel.trinity::before { background: var(--neon-pink); box-shadow: 0 0 10px var(--neon-pink); }
        .panel.trinity:hover { box-shadow: inset 0 0 30px rgba(255, 0, 255, 0.1), 0 0 25px rgba(255, 0, 255, 0.4); }

        .panel.market { 
            border-color: var(--neon-blue); 
            color: var(--neon-blue); 
            box-shadow: inset 0 0 20px rgba(0, 255, 255, 0.05), 0 0 15px rgba(0, 255, 255, 0.2);
        }
        .panel.market::before { background: var(--neon-blue); box-shadow: 0 0 10px var(--neon-blue); }
        .panel.market:hover { box-shadow: inset 0 0 30px rgba(0, 255, 255, 0.1), 0 0 25px rgba(0, 255, 255, 0.4); }

        .panel-header {
            display: flex;
            align-items: center;
            margin-bottom: 20px;
            border-bottom: 1px dashed currentColor;
            padding-bottom: 10px;
            text-shadow: 0 0 8px currentColor;
        }

        .panel-header h2 { font-size: 1.4rem; flex-grow: 1; }
        
        .stat-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
            padding: 8px;
            background: rgba(0,0,0,0.4);
            border-left: 3px solid currentColor;
            transition: background 0.2s;
        }
        
        .stat-row:hover { background: rgba(255,255,255,0.05); }
        
        .stat-title { font-size: 1rem; display: flex; align-items: center; gap: 10px; }
        .stat-subtitle { font-size: 0.7rem; opacity: 0.7; display: block; margin-top: 3px; }
        
        .stat-value {
            font-size: 1rem;
            font-weight: bold;
            padding: 4px 8px;
            background: rgba(0,0,0,0.8);
            border: 1px solid currentColor;
            box-shadow: 0 0 5px currentColor;
            text-shadow: 0 0 5px currentColor;
        }

        /* Animations */
        .blink { animation: blinker 1s linear infinite; }
        .blink-fast { animation: blinker 0.3s linear infinite; }
        @keyframes blinker { 50% { opacity: 0.3; } }

        .pulse-dot {
            width: 10px; height: 10px;
            background-color: currentColor;
            border-radius: 50%;
            display: inline-block;
            box-shadow: 0 0 8px currentColor;
            animation: pulse 1.5s infinite;
        }
        @keyframes pulse {
            0% { transform: scale(0.9); box-shadow: 0 0 0 0 rgba(currentColor, 0.7); }
            70% { transform: scale(1); box-shadow: 0 0 0 6px rgba(currentColor, 0); }
            100% { transform: scale(0.9); box-shadow: 0 0 0 0 rgba(currentColor, 0); }
        }

        .progress-bar {
            width: 100%;
            height: 4px;
            background: #222;
            margin-top: 5px;
            position: relative;
            overflow: hidden;
        }
        .progress-fill {
            height: 100%;
            background: currentColor;
            box-shadow: 0 0 10px currentColor;
        }
        .anim-fill {
            animation: loadBar 2s infinite alternate ease-in-out;
        }
        @keyframes loadBar { 0% { width: 10%; } 100% { width: 90%; } }

        .footer {
            margin-top: 40px;
            text-align: center;
            font-size: 0.8rem;
            color: #555;
            border-top: 1px dashed #333;
            padding-top: 20px;
        }
        
        /* Tactical Elements */
        .corner-br { position: absolute; bottom: 0; right: 0; width: 20px; height: 20px; border-bottom: 2px solid currentColor; border-right: 2px solid currentColor; }
        .corner-tl { position: absolute; top: 0; left: 0; width: 20px; height: 20px; border-top: 2px solid currentColor; border-left: 2px solid currentColor; }

    </style>
</head>
<body>
    <div class="header">
        <h1>[:: ORBITAL COMMAND_NUVOLA ::]</h1>
        <div class="sys-status">
            <span class="pulse-dot" style="color: var(--neon-yellow);"></span> UPLINK SECURE | CLUSTER NORMAL | LATENCY: <span id="ping" class="blink">12ms</span><br>
            <span style="color: var(--neon-pink); font-size: 1rem; margin-top: 5px; display: inline-block;">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</span>
        </div>
    </div>

    <div class="container">
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <div class="corner-tl"></div><div class="corner-br"></div>
            <div class="panel-header">
                <h2>⚔️ SQUADRE D'ASSALTO <br><span style="font-size:0.6em; opacity:0.8;">HFT / EXECUTION</span></h2>
            </div>
            
            <div class="stat-row">
                <div class="stat-title">
                    <span class="pulse-dot"></span> 
                    <div>SQUADRA_ALPHA<span class="stat-subtitle">Scalper [Binance]</span></div>
                </div>
                <div class="stat-value blink">ENGAGED</div>
            </div>
            <div class="progress-bar"><div class="progress-fill" style="width: 85%;"></div></div>

            <div class="stat-row" style="margin-top: 15px;">
                <div class="stat-title">
                    <span class="pulse-dot"></span> 
                    <div>SQUADRA_DELTA<span class="stat-subtitle">Order Flow [DOM]</span></div>
                </div>
                <div class="stat-value" style="color: var(--neon-yellow); border-color: var(--neon-yellow);">SCANNING</div>
            </div>
            <div class="progress-bar"><div class="progress-fill anim-fill" style="background: var(--neon-yellow);"></div></div>

            <div class="stat-row" style="margin-top: 15px;">
                <div class="stat-title">
                    <span class="pulse-dot"></span> 
                    <div>SQUADRA_GAMMA<span class="stat-subtitle">Pairs [Bitget]</span></div>
                </div>
                <div class="stat-value">SPREAD 0.04%</div>
            </div>
            <div class="progress-bar"><div class="progress-fill" style="width: 45%;"></div></div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel trinity">
            <div class="corner-tl"></div><div class="corner-br"></div>
            <div class="panel-header">
                <h2>🔺 PROTOCOLLO TRINITY <br><span style="font-size:0.6em; opacity:0.8;">BACKGROUND DAEMONS</span></h2>
            </div>
            
            <div class="stat-row">
                <div class="stat-title">
                    <span class="pulse-dot"></span> 
                    <div>LO STROZZINO<span class="stat-subtitle">Funding Arb</span></div>
                </div>
                <div class="stat-value">APR 19.2%</div>
            </div>

            <div class="stat-row">
                <div class="stat-title">
                    <span class="pulse-dot"></span> 
                    <div>IL CONTABILE<span class="stat-subtitle">DCA Engine</span></div>
                </div>
                <div class="stat-value">WAIT 3h:12m</div>
            </div>

            <div class="stat-row">
                <div class="stat-title">
                    <span class="pulse-dot"></span> 
                    <div>L'ANGELO CUSTODE<span class="stat-subtitle">MEV Arbitrum</span></div>
                </div>
                <div class="stat-value blink" style="color: var(--neon-blue); border-color: var(--neon-blue);">MEMPOOL SYNC</div>
            </div>
            
            <div style="margin-top: 15px; font-size: 0.8rem; text-align: center; border: 1px dashed var(--neon-pink); padding: 5px;">
                TRINITY LOCK: <span class="blink">SECURE</span> // OVERRIDE: FALSE
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel market">
            <div class="corner-tl"></div><div class="corner-br"></div>
            <div class="panel-header">
                <h2>📊 THE ORACLE <br><span style="font-size:0.6em; opacity:0.8;">QUANTITATIVE METRICS</span></h2>
            </div>
            
            <div class="stat-row">
                <div class="stat-title">
                    <span>👁️</span> 
                    <div>SENTIMENT<span class="stat-subtitle">Binance NLP</span></div>
                </div>
                <div class="stat-value" style="color: var(--neon-green);">BULLISH [82]</div>
            </div>

            <div class="stat-row">
                <div class="stat-title">
                    <span>🐳</span> 
                    <div>WHALE TRACKER<span class="stat-subtitle">On-Chain Flow</span></div>
                </div>
                <div class="stat-value" style="color: var(--neon-red); border-color: var(--neon-red);">-1,240 BTC</div>
            </div>

            <div class="stat-row">
                <div class="stat-title">
                    <span>⚡</span> 
                    <div>VIX CRYPTO<span class="stat-subtitle">Volatility Index</span></div>
                </div>
                <div class="stat-value blink">ELEVATED</div>
            </div>
            
            <div class="progress-bar" style="height: 10px; margin-top: 20px; border: 1px solid var(--neon-blue);">
                <div class="progress-fill" style="width: 78%; background: linear-gradient(90deg, var(--neon-blue), var(--neon-pink));"></div>
            </div>
            <div style="font-size: 0.7rem; text-align: right; margin-top: 5px;">MARKET HEATMAP: 78%</div>
        </div>
    </div>
    
    <div class="footer">
        <p>ORBITAL_COMMAND // v3.1.4 // <span id="clock"></span> // RESTRICTED ACCESS</p>
    </div>

    <script>
        setInterval(() => {
            const now = new Date();
            document.getElementById('clock').innerText = now.toISOString();
            document.getElementById('ping').innerText = Math.floor(Math.random() * 20 + 5) + 'ms';
        }, 1000);
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
