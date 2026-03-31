from flask import Flask, render_template_string
import random
import time

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NUVOLA // ORBITAL COMMAND</title>
    <style>
        :root {
            --bg: #030305;
            --neon-green: #39ff14;
            --neon-blue: #00e5ff;
            --neon-pink: #ff007f;
            --neon-red: #ff3333;
            --neon-yellow: #fce803;
            --panel-bg: rgba(5, 10, 15, 0.85);
            --border: #1a2a3a;
            --font-main: 'Courier New', Courier, monospace;
        }
        
        * { box-sizing: border-box; }
        
        body {
            background-color: var(--bg);
            color: var(--neon-blue);
            font-family: var(--font-main);
            margin: 0;
            padding: 20px;
            overflow-x: hidden;
            background-image: 
                linear-gradient(rgba(0, 229, 255, 0.05) 1px, transparent 1px),
                linear-gradient(90deg, rgba(0, 229, 255, 0.05) 1px, transparent 1px);
            background-size: 30px 30px;
        }
        
        .scanlines {
            position: fixed;
            top: 0; left: 0; width: 100vw; height: 100vh;
            background: linear-gradient(
                to bottom,
                rgba(255,255,255,0),
                rgba(255,255,255,0) 50%,
                rgba(0,0,0,0.2) 50%,
                rgba(0,0,0,0.2)
            );
            background-size: 100% 4px;
            pointer-events: none;
            z-index: 999;
        }

        h1 {
            color: var(--neon-blue);
            text-shadow: 0 0 15px var(--neon-blue), 0 0 30px var(--neon-blue);
            text-align: center;
            letter-spacing: 6px;
            border-bottom: 2px solid var(--neon-blue);
            padding-bottom: 15px;
            margin-bottom: 40px;
            font-size: 2.5rem;
            text-transform: uppercase;
            position: relative;
        }
        
        h1::after {
            content: 'SYSTEM SECURED';
            position: absolute;
            right: 10px;
            bottom: -25px;
            font-size: 0.8rem;
            color: var(--neon-green);
            text-shadow: 0 0 5px var(--neon-green);
            letter-spacing: 2px;
            animation: pulse 2s infinite;
        }

        .container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(380px, 1fr));
            gap: 25px;
            max-width: 1400px;
            margin: 0 auto;
        }

        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-blue);
            box-shadow: inset 0 0 20px rgba(0, 229, 255, 0.05), 0 0 15px rgba(0, 229, 255, 0.2);
            padding: 25px;
            position: relative;
            backdrop-filter: blur(5px);
            transition: all 0.3s ease;
        }
        
        .panel:hover {
            box-shadow: inset 0 0 30px rgba(0, 229, 255, 0.1), 0 0 25px rgba(0, 229, 255, 0.4);
            border-color: var(--neon-pink);
        }

        .panel::before {
            content: '';
            position: absolute;
            top: -2px; left: -2px;
            width: 30px; height: 30px;
            border-top: 3px solid var(--neon-pink);
            border-left: 3px solid var(--neon-pink);
            box-shadow: -5px -5px 15px var(--neon-pink);
        }
        
        .panel::after {
            content: '';
            position: absolute;
            bottom: -2px; right: -2px;
            width: 30px; height: 30px;
            border-bottom: 3px solid var(--neon-pink);
            border-right: 3px solid var(--neon-pink);
            box-shadow: 5px 5px 15px var(--neon-pink);
        }

        .panel-title {
            color: var(--neon-yellow);
            text-shadow: 0 0 10px var(--neon-yellow);
            border-bottom: 1px dashed rgba(252, 232, 3, 0.5);
            padding-bottom: 10px;
            margin-top: 0;
            margin-bottom: 20px;
            font-size: 1.4rem;
            text-transform: uppercase;
            letter-spacing: 2px;
            display: flex;
            align-items: center;
        }
        
        .panel-title span { margin-right: 10px; }

        .status-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
            background: rgba(0, 0, 0, 0.4);
            border-left: 3px solid var(--neon-blue);
            padding: 10px 15px;
            font-size: 1.1rem;
            transition: all 0.2s;
        }
        
        .status-item:hover {
            background: rgba(0, 229, 255, 0.1);
            border-left-color: var(--neon-pink);
            transform: translateX(5px);
        }

        .status-label {
            color: #fff;
            display: flex;
            align-items: center;
        }
        
        .status-label span { margin-right: 8px; font-size: 1.2rem; }
        
        .status-desc {
            display: block;
            font-size: 0.75rem;
            color: #888;
            margin-top: 4px;
        }

        .badge {
            padding: 4px 10px;
            border-radius: 3px;
            font-weight: bold;
            font-size: 0.9rem;
            letter-spacing: 1px;
            text-shadow: 0 0 5px rgba(255,255,255,0.5);
        }

        .online { background: rgba(57, 255, 20, 0.2); color: var(--neon-green); border: 1px solid var(--neon-green); box-shadow: 0 0 10px rgba(57, 255, 20, 0.4); }
        .offline { background: rgba(255, 51, 51, 0.2); color: var(--neon-red); border: 1px solid var(--neon-red); box-shadow: 0 0 10px rgba(255, 51, 51, 0.4); }
        .active { background: rgba(0, 229, 255, 0.2); color: var(--neon-blue); border: 1px solid var(--neon-blue); box-shadow: 0 0 10px rgba(0, 229, 255, 0.4); }
        .warning { background: rgba(252, 232, 3, 0.2); color: var(--neon-yellow); border: 1px solid var(--neon-yellow); box-shadow: 0 0 10px rgba(252, 232, 3, 0.4); }

        .pulse { animation: pulse 2s infinite; }
        @keyframes pulse {
            0% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.7; transform: scale(0.98); }
            100% { opacity: 1; transform: scale(1); }
        }

        .blink { animation: blink 1s step-end infinite; }
        @keyframes blink { 50% { opacity: 0; } }
        
        .glitch-hover:hover {
            animation: glitch-anim 0.2s linear infinite;
        }
        @keyframes glitch-anim {
            0% { transform: translate(0) }
            20% { transform: translate(-2px, 1px) }
            40% { transform: translate(-1px, -1px) }
            60% { transform: translate(2px, 1px) }
            80% { transform: translate(1px, -1px) }
            100% { transform: translate(0) }
        }

        .data-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
        }

        .data-box {
            border: 1px solid var(--border);
            padding: 15px;
            text-align: center;
            background: linear-gradient(180deg, rgba(0,0,0,0.8) 0%, rgba(10,20,30,0.9) 100%);
            position: relative;
            overflow: hidden;
        }
        
        .data-box::before {
            content: '';
            position: absolute;
            top: 0; left: 0;
            width: 100%; height: 2px;
            background: var(--neon-blue);
            box-shadow: 0 0 10px var(--neon-blue);
            transform: scaleX(0);
            transform-origin: left;
            transition: transform 0.3s;
        }
        
        .data-box:hover::before { transform: scaleX(1); }

        .data-label {
            font-size: 0.75rem;
            color: #888;
            margin-bottom: 8px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }

        .data-value {
            font-size: 1.8rem;
            color: var(--neon-blue);
            text-shadow: 0 0 10px var(--neon-blue);
            font-weight: bold;
            font-family: 'Impact', sans-serif;
            letter-spacing: 1px;
        }
        
        .value-green { color: var(--neon-green); text-shadow: 0 0 10px var(--neon-green); }
        .value-pink { color: var(--neon-pink); text-shadow: 0 0 10px var(--neon-pink); }
        
        .matrix-bg {
            position: absolute;
            top: 0; left: 0; right: 0; bottom: 0;
            z-index: -1;
            opacity: 0.05;
            background: url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"><text x="10" y="20" fill="%2339ff14" font-family="monospace">1 0</text><text x="40" y="50" fill="%2339ff14" font-family="monospace">0 1</text><text x="70" y="80" fill="%2339ff14" font-family="monospace">1 1</text></svg>');
        }

        .footer {
            margin-top: 50px; 
            text-align: center; 
            font-size: 0.9em; 
            color: #555;
            border-top: 1px dashed var(--border);
            padding-top: 20px;
            letter-spacing: 2px;
        }
        
        .progress-bar {
            height: 4px;
            background: #111;
            margin-top: 8px;
            border-radius: 2px;
            overflow: hidden;
            position: relative;
        }
        
        .progress-fill {
            height: 100%;
            background: var(--neon-blue);
            box-shadow: 0 0 10px var(--neon-blue);
            width: 75%;
            position: relative;
        }
        
        .progress-fill::after {
            content: '';
            position: absolute;
            top: 0; right: 0;
            width: 5px; height: 100%;
            background: #fff;
            box-shadow: 0 0 10px #fff;
        }

        .chart-container {
            height: 100px;
            width: 100%;
            margin-top: 15px;
            border: 1px dashed var(--border);
            position: relative;
            background: rgba(0,0,0,0.5);
            overflow: hidden;
        }
        
        .chart-line {
            position: absolute;
            bottom: 0;
            width: 100%;
            height: 50%;
            border-top: 2px solid var(--neon-pink);
            box-shadow: 0 -2px 10px rgba(255, 0, 127, 0.4);
            background: linear-gradient(0deg, rgba(255,0,127,0.2) 0%, transparent 100%);
            clip-path: polygon(0 100%, 0 50%, 10% 40%, 20% 60%, 30% 30%, 40% 70%, 50% 20%, 60% 50%, 70% 10%, 80% 40%, 90% 20%, 100% 40%, 100% 100%);
            animation: chart-move 20s linear infinite;
        }
        
        @keyframes chart-move {
            0% { transform: translateX(0); }
            100% { transform: translateX(-50%); }
        }
        
        .log-terminal {
            background: #000;
            border: 1px solid var(--border);
            height: 150px;
            margin-top: 25px;
            padding: 10px;
            font-size: 0.8rem;
            color: var(--neon-green);
            overflow: hidden;
            position: relative;
        }
        
        .log-terminal p { margin: 5px 0; opacity: 0.8; }
        .log-terminal p:last-child { opacity: 1; text-shadow: 0 0 5px var(--neon-green); }
        .log-prefix { color: #888; margin-right: 10px; }
        .log-warn { color: var(--neon-yellow); }
        .log-err { color: var(--neon-red); }
    </style>
</head>
<body>
    <div class="scanlines"></div>
    <div class="matrix-bg"></div>

    <h1><span class="blink">>></span> ORBITAL COMMAND <span class="blink"><<</span></h1>

    <div style="text-align: center; margin-bottom: 30px; font-size: 1.2rem; border: 1px solid var(--neon-green); padding: 10px; background: rgba(57, 255, 20, 0.1); color: var(--neon-green); text-shadow: 0 0 5px var(--neon-green); letter-spacing: 2px; font-weight: bold; box-shadow: 0 0 15px rgba(57, 255, 20, 0.2);">
        <span class="pulse">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</span>
    </div>

    <div class="container">
        
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <h2 class="panel-title"><span>⚔️</span> SQUADRE D'ASSALTO (HFT)</h2>
            
            <div class="status-item glitch-hover">
                <div class="status-label">
                    <span>💥</span> 
                    <div>
                        [SQUADRA_ALPHA]
                        <span class="status-desc">Scalper // Target: Binance Spot</span>
                    </div>
                </div>
                <span class="badge online pulse">ENGAGED</span>
            </div>
            
            <div class="status-item glitch-hover">
                <div class="status-label">
                    <span>🌊</span> 
                    <div>
                        [SQUADRA_DELTA]
                        <span class="status-desc">Order Flow // Liquidity Snipe</span>
                    </div>
                </div>
                <span class="badge online pulse">ENGAGED</span>
            </div>
            
            <div class="status-item glitch-hover">
                <div class="status-label">
                    <span>⚖️</span> 
                    <div>
                        [SQUADRA_GAMMA]
                        <span class="status-desc">Pairs Trading // Target: Bitget Futures</span>
                    </div>
                </div>
                <span class="badge online pulse">ENGAGED</span>
            </div>
            
            <div class="chart-container">
                <div class="chart-line" style="width: 200%;"></div>
            </div>
            <div style="text-align: right; font-size: 0.7rem; color: #666; margin-top: 5px;">HFT FREQUENCY (ms)</div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2 class="panel-title" style="color: var(--neon-green); border-bottom-color: rgba(57, 255, 20, 0.5);"><span>🛡️</span> PROTOCOLLO TRINITY</h2>
            
            <div class="status-item">
                <div class="status-label">
                    <span>🕴️</span> 
                    <div>
                        Lo Strozzino
                        <span class="status-desc">Funding Rate Arbitrage // Background</span>
                    </div>
                </div>
                <span class="badge active">ONLINE</span>
            </div>
            
            <div class="status-item">
                <div class="status-label">
                    <span>🧮</span> 
                    <div>
                        Il Contabile
                        <span class="status-desc">Smart DCA // Auto-Accumulation</span>
                    </div>
                </div>
                <span class="badge active">ONLINE</span>
            </div>
            
            <div class="status-item">
                <div class="status-label">
                    <span>👼</span> 
                    <div>
                        L'Angelo Custode
                        <span class="status-desc">MEV Protection // Target: Arbitrum</span>
                    </div>
                </div>
                <span class="badge active">ONLINE</span>
            </div>
            
            <div style="margin-top: 20px;">
                <div style="font-size: 0.8rem; color: #aaa; display: flex; justify-content: space-between;">
                    <span>TRINITY CPU LOAD</span>
                    <span style="color: var(--neon-green);">42%</span>
                </div>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: 42%; background: var(--neon-green); box-shadow: 0 0 10px var(--neon-green);"></div>
                </div>
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <h2 class="panel-title" style="color: var(--neon-blue); border-bottom-color: rgba(0, 229, 255, 0.5);"><span>📊</span> METRICHE DI MERCATO</h2>
            
            <div class="data-grid">
                <div class="data-box glitch-hover">
                    <div class="data-label">The Oracle (Sentiment)</div>
                    <div class="data-value value-green blink">EXTREME GREED</div>
                    <div style="font-size: 0.7rem; color: #666; margin-top: 5px;">Binance Index: 88/100</div>
                </div>
                
                <div class="data-box glitch-hover">
                    <div class="data-label">Whale Tracker</div>
                    <div class="data-value value-green">+$420.69M</div>
                    <div style="font-size: 0.7rem; color: #666; margin-top: 5px;">Net Inflow (24h)</div>
                </div>
                
                <div class="data-box glitch-hover">
                    <div class="data-label">Liquidation Map</div>
                    <div class="data-value value-pink">SHORT SQUEEZE</div>
                    <div style="font-size: 0.7rem; color: #666; margin-top: 5px;">Risk Zone: 69,420</div>
                </div>
                
                <div class="data-box glitch-hover">
                    <div class="data-label">System Latency</div>
                    <div class="data-value">12<span style="font-size: 1rem;">ms</span></div>
                    <div style="font-size: 0.7rem; color: #666; margin-top: 5px;">Ping to Exchange</div>
                </div>
            </div>
            
            <div style="margin-top: 15px;">
                <div style="font-size: 0.8rem; color: #aaa; display: flex; justify-content: space-between;">
                    <span>VOLATILITY INDEX</span>
                    <span style="color: var(--neon-pink);">HIGH (85%)</span>
                </div>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: 85%; background: var(--neon-pink); box-shadow: 0 0 10px var(--neon-pink);"></div>
                </div>
            </div>
        </div>
    </div>
    
    <div class="container" style="margin-top: 25px; grid-template-columns: 1fr;">
        <div class="log-terminal">
            <div style="position: absolute; top: 0; right: 10px; color: #333; font-weight: bold; font-size: 2rem;">SYS.LOG</div>
            <p><span class="log-prefix">[SYS]</span> Initializing NUVOLA OS v4.2.0...</p>
            <p><span class="log-prefix">[NET]</span> Connecting to Binance WebSocket... OK</p>
            <p><span class="log-prefix">[HFT]</span> SQUADRA_ALPHA deployed. Capital allocated: 10,000 USDT.</p>
            <p><span class="log-prefix">[TRINITY]</span> Lo Strozzino scanning for funding discrepancies...</p>
            <p><span class="log-prefix log-warn">[WARN]</span> High volatility detected on BTC/USDT. Tightening stop-losses.</p>
            <p><span class="log-prefix">[SYS]</span> <span class="blink">Waiting for next market tick...</span></p>
        </div>
    </div>
    
    <div class="footer">
        NUVOLA OS v4.2.0 | ENCRYPTION: AES-256-GCM | TERMINAL ACCESS: <span class="value-green blink">GRANTED</span> | ORBITAL COMMAND: ONLINE
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
