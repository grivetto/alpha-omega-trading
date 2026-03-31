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
        @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');

        :root {
            --bg: #050505;
            --neon-green: #0f0;
            --neon-blue: #0ff;
            --neon-pink: #f0f;
            --neon-red: #f00;
            --neon-yellow: #ff0;
            --panel-bg: rgba(10, 15, 20, 0.85);
            --border: #112233;
            --font-main: 'Share Tech Mono', monospace;
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
                linear-gradient(rgba(0, 255, 255, 0.03) 1px, transparent 1px),
                linear-gradient(90deg, rgba(0, 255, 255, 0.03) 1px, transparent 1px);
            background-size: 20px 20px;
        }
        
        /* Scanlines */
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
            z-index: 9999;
        }

        h1 {
            color: var(--neon-blue);
            text-shadow: 0 0 10px var(--neon-blue), 0 0 20px var(--neon-blue), 0 0 40px var(--neon-blue);
            text-align: center;
            letter-spacing: 8px;
            border-bottom: 2px solid var(--neon-blue);
            padding-bottom: 15px;
            margin-bottom: 40px;
            font-size: 3rem;
            text-transform: uppercase;
            position: relative;
        }
        
        h1::after {
            content: 'SYSTEM SECURED [ENCRYPTED]';
            position: absolute;
            right: 10px;
            bottom: -25px;
            font-size: 0.9rem;
            color: var(--neon-green);
            text-shadow: 0 0 5px var(--neon-green);
            letter-spacing: 3px;
            animation: pulse 2s infinite;
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
            border: 1px solid var(--neon-blue);
            box-shadow: inset 0 0 20px rgba(0, 255, 255, 0.05), 0 0 15px rgba(0, 255, 255, 0.2);
            padding: 30px;
            position: relative;
            backdrop-filter: blur(8px);
            transition: all 0.3s ease;
        }
        
        .panel:hover {
            box-shadow: inset 0 0 30px rgba(0, 255, 255, 0.1), 0 0 30px rgba(0, 255, 255, 0.5);
            border-color: var(--neon-pink);
        }

        /* Cyberpunk corners */
        .panel::before, .panel::after {
            content: '';
            position: absolute;
            width: 40px; height: 40px;
            pointer-events: none;
        }
        .panel::before {
            top: -2px; left: -2px;
            border-top: 3px solid var(--neon-pink);
            border-left: 3px solid var(--neon-pink);
            box-shadow: -5px -5px 15px rgba(255,0,255,0.5);
        }
        .panel::after {
            bottom: -2px; right: -2px;
            border-bottom: 3px solid var(--neon-pink);
            border-right: 3px solid var(--neon-pink);
            box-shadow: 5px 5px 15px rgba(255,0,255,0.5);
        }

        .panel-title {
            color: var(--neon-yellow);
            text-shadow: 0 0 10px var(--neon-yellow);
            border-bottom: 1px dashed rgba(255, 255, 0, 0.5);
            padding-bottom: 10px;
            margin-top: 0;
            margin-bottom: 25px;
            font-size: 1.6rem;
            text-transform: uppercase;
            letter-spacing: 3px;
            display: flex;
            align-items: center;
        }
        .panel-title span { margin-right: 15px; font-size: 1.8rem; }

        .status-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
            background: rgba(0, 0, 0, 0.6);
            border-left: 4px solid var(--neon-blue);
            padding: 12px 20px;
            font-size: 1.2rem;
            transition: all 0.2s;
            position: relative;
            overflow: hidden;
        }
        .status-item::before {
            content: '';
            position: absolute;
            top: 0; left: -100%; width: 100%; height: 100%;
            background: linear-gradient(90deg, transparent, rgba(0,255,255,0.2), transparent);
            transition: 0.5s;
        }
        .status-item:hover::before { left: 100%; }
        .status-item:hover {
            border-left-color: var(--neon-pink);
            transform: translateX(8px);
        }

        .status-label {
            color: #fff;
            display: flex;
            align-items: center;
        }
        .status-label span { margin-right: 12px; font-size: 1.4rem; }
        
        .status-desc {
            display: block;
            font-size: 0.85rem;
            color: #888;
            margin-top: 5px;
            letter-spacing: 1px;
        }

        .badge {
            padding: 5px 12px;
            border-radius: 2px;
            font-weight: bold;
            font-size: 1rem;
            letter-spacing: 2px;
            text-shadow: 0 0 8px rgba(255,255,255,0.8);
            text-transform: uppercase;
        }

        .online { background: rgba(0, 255, 0, 0.15); color: var(--neon-green); border: 1px solid var(--neon-green); box-shadow: 0 0 15px rgba(0, 255, 0, 0.4); }
        .offline { background: rgba(255, 0, 0, 0.15); color: var(--neon-red); border: 1px solid var(--neon-red); box-shadow: 0 0 15px rgba(255, 0, 0, 0.4); }
        .active { background: rgba(0, 255, 255, 0.15); color: var(--neon-blue); border: 1px solid var(--neon-blue); box-shadow: 0 0 15px rgba(0, 255, 255, 0.4); }
        .warning { background: rgba(255, 255, 0, 0.15); color: var(--neon-yellow); border: 1px solid var(--neon-yellow); box-shadow: 0 0 15px rgba(255, 255, 0, 0.4); }

        .pulse { animation: pulse 1.5s infinite; }
        @keyframes pulse {
            0% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.8; transform: scale(0.98); box-shadow: 0 0 25px currentColor; }
            100% { opacity: 1; transform: scale(1); }
        }

        .blink { animation: blink 1s step-end infinite; }
        @keyframes blink { 50% { opacity: 0; } }
        
        .glitch-hover:hover {
            animation: glitch-anim 0.3s linear infinite;
        }
        @keyframes glitch-anim {
            0% { transform: translate(0) }
            20% { transform: translate(-2px, 2px) }
            40% { transform: translate(-2px, -2px) }
            60% { transform: translate(2px, 2px) }
            80% { transform: translate(2px, -2px) }
            100% { transform: translate(0) }
        }

        .data-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
        }

        .data-box {
            border: 1px solid var(--border);
            padding: 20px;
            text-align: center;
            background: linear-gradient(180deg, rgba(0,0,0,0.9) 0%, rgba(10,20,30,0.9) 100%);
            position: relative;
            overflow: hidden;
            box-shadow: 0 0 10px rgba(0,0,0,0.5);
        }
        
        .data-box::before {
            content: '';
            position: absolute;
            top: 0; left: 0;
            width: 100%; height: 2px;
            background: var(--neon-blue);
            box-shadow: 0 0 15px var(--neon-blue);
            transform: scaleX(0);
            transform-origin: left;
            transition: transform 0.4s cubic-bezier(0.2, 1, 0.3, 1);
        }
        .data-box:hover::before { transform: scaleX(1); }

        .data-label {
            font-size: 0.85rem;
            color: #777;
            margin-bottom: 10px;
            text-transform: uppercase;
            letter-spacing: 2px;
        }

        .data-value {
            font-size: 2.2rem;
            color: var(--neon-blue);
            text-shadow: 0 0 15px var(--neon-blue);
            font-weight: bold;
            letter-spacing: 2px;
        }
        
        .value-green { color: var(--neon-green); text-shadow: 0 0 15px var(--neon-green); }
        .value-pink { color: var(--neon-pink); text-shadow: 0 0 15px var(--neon-pink); }
        
        .progress-bar {
            height: 6px;
            background: #111;
            margin-top: 10px;
            border-radius: 3px;
            overflow: hidden;
            position: relative;
            border: 1px solid #333;
        }
        
        .progress-fill {
            height: 100%;
            background: var(--neon-blue);
            box-shadow: 0 0 15px var(--neon-blue);
            width: 75%;
            position: relative;
        }
        .progress-fill::after {
            content: '';
            position: absolute;
            top: 0; right: 0;
            width: 10px; height: 100%;
            background: #fff;
            box-shadow: 0 0 15px #fff;
        }

        .chart-container {
            height: 120px;
            width: 100%;
            margin-top: 25px;
            border: 1px dashed var(--border);
            position: relative;
            background: rgba(0,0,0,0.7);
            overflow: hidden;
        }
        
        .chart-line {
            position: absolute;
            bottom: 0;
            width: 200%;
            height: 60%;
            border-top: 2px solid var(--neon-pink);
            box-shadow: 0 -3px 15px rgba(255, 0, 255, 0.5);
            background: linear-gradient(0deg, rgba(255,0,255,0.15) 0%, transparent 100%);
            clip-path: polygon(0 100%, 0 50%, 5% 40%, 10% 60%, 15% 30%, 20% 70%, 25% 20%, 30% 50%, 35% 10%, 40% 40%, 45% 20%, 50% 60%, 55% 30%, 60% 80%, 65% 40%, 70% 20%, 75% 50%, 80% 10%, 85% 60%, 90% 30%, 95% 70%, 100% 40%, 100% 100%);
            animation: chart-move 30s linear infinite;
        }
        
        @keyframes chart-move {
            0% { transform: translateX(0); }
            100% { transform: translateX(-50%); }
        }
        
        .log-terminal {
            background: #000;
            border: 1px solid var(--neon-green);
            box-shadow: 0 0 20px rgba(0,255,0,0.1);
            height: 200px;
            margin-top: 35px;
            padding: 15px;
            font-size: 1rem;
            color: var(--neon-green);
            overflow-y: auto;
            position: relative;
        }
        
        .log-terminal p { margin: 8px 0; opacity: 0.8; font-family: 'Share Tech Mono', monospace; }
        .log-terminal p:last-child { opacity: 1; text-shadow: 0 0 8px var(--neon-green); }
        .log-prefix { color: #555; margin-right: 15px; }
        .log-warn { color: var(--neon-yellow); text-shadow: 0 0 8px var(--neon-yellow); }
        .log-err { color: var(--neon-red); text-shadow: 0 0 8px var(--neon-red); }
        
        .trinity-banner {
            text-align: center; 
            margin-bottom: 40px; 
            font-size: 1.5rem; 
            border: 2px solid var(--neon-green); 
            padding: 15px; 
            background: rgba(0, 255, 0, 0.05); 
            color: var(--neon-green); 
            text-shadow: 0 0 10px var(--neon-green); 
            letter-spacing: 4px; 
            font-weight: bold; 
            box-shadow: inset 0 0 20px rgba(0,255,0,0.1), 0 0 30px rgba(0,255,0,0.2);
            position: relative;
            overflow: hidden;
        }
        .trinity-banner::after {
            content: '';
            position: absolute;
            top: 0; left: -100%; width: 50%; height: 100%;
            background: linear-gradient(90deg, transparent, rgba(0,255,0,0.2), transparent);
            animation: scan 3s infinite;
        }
        @keyframes scan {
            100% { left: 200%; }
        }

        .footer {
            margin-top: 60px; 
            text-align: center; 
            font-size: 1rem; 
            color: #666;
            border-top: 1px dashed var(--border);
            padding-top: 25px;
            letter-spacing: 3px;
            padding-bottom: 30px;
        }
    </style>
</head>
<body>
    <div class="scanlines"></div>

    <h1><span class="blink">>></span> ORBITAL COMMAND <span class="blink"><<</span></h1>

    <div class="trinity-banner">
        <span class="pulse">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</span>
    </div>

    <div class="container">
        
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <h2 class="panel-title"><span>⚔️</span> SQUADRE D'ASSALTO (HFT)</h2>
            
            <div class="status-item glitch-hover">
                <div class="status-label">
                    <span>⚡</span> 
                    <div>
                        [SQUADRA_ALPHA]
                        <span class="status-desc">Scalper HFT // Target: Binance Spot</span>
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
                <div class="chart-line"></div>
            </div>
            <div style="text-align: right; font-size: 0.8rem; color: #888; margin-top: 8px; letter-spacing: 1px;">HFT EXECUTION FREQUENCY (ms)</div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel" style="border-color: var(--neon-green);">
            <h2 class="panel-title" style="color: var(--neon-green); border-bottom-color: rgba(0, 255, 0, 0.5);"><span>🛡️</span> PROTOCOLLO TRINITY</h2>
            
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
            
            <div style="margin-top: 30px;">
                <div style="font-size: 0.9rem; color: #bbb; display: flex; justify-content: space-between; letter-spacing: 1px;">
                    <span>TRINITY CPU LOAD</span>
                    <span style="color: var(--neon-green); font-weight: bold; text-shadow: 0 0 5px var(--neon-green);">42.69%</span>
                </div>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: 42.69%; background: var(--neon-green); box-shadow: 0 0 15px var(--neon-green);"></div>
                </div>
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel" style="border-color: var(--neon-yellow);">
            <h2 class="panel-title" style="color: var(--neon-yellow); border-bottom-color: rgba(255, 255, 0, 0.5);"><span>📊</span> METRICHE DI MERCATO</h2>
            
            <div class="data-grid">
                <div class="data-box glitch-hover">
                    <div class="data-label">The Oracle (Sentiment)</div>
                    <div class="data-value value-green blink">GREED</div>
                    <div style="font-size: 0.8rem; color: #888; margin-top: 8px;">Binance Index: 88/100</div>
                </div>
                
                <div class="data-box glitch-hover">
                    <div class="data-label">Whale Tracker</div>
                    <div class="data-value value-green">+$420.6M</div>
                    <div style="font-size: 0.8rem; color: #888; margin-top: 8px;">Net Inflow (24h)</div>
                </div>
                
                <div class="data-box glitch-hover">
                    <div class="data-label">Liquidation Map</div>
                    <div class="data-value value-pink">SQUEEZE</div>
                    <div style="font-size: 0.8rem; color: #888; margin-top: 8px;">Risk Zone: 69,420</div>
                </div>
                
                <div class="data-box glitch-hover">
                    <div class="data-label">System Latency</div>
                    <div class="data-value">12<span style="font-size: 1.2rem;">ms</span></div>
                    <div style="font-size: 0.8rem; color: #888; margin-top: 8px;">Ping to Binance</div>
                </div>
            </div>
            
            <div style="margin-top: 25px;">
                <div style="font-size: 0.9rem; color: #bbb; display: flex; justify-content: space-between; letter-spacing: 1px;">
                    <span>MARKET VOLATILITY INDEX</span>
                    <span style="color: var(--neon-pink); font-weight: bold; text-shadow: 0 0 5px var(--neon-pink);">HIGH (85%)</span>
                </div>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: 85%; background: var(--neon-pink); box-shadow: 0 0 15px var(--neon-pink);"></div>
                </div>
            </div>
        </div>
    </div>
    
    <div class="container" style="margin-top: 30px; grid-template-columns: 1fr;">
        <div class="log-terminal">
            <div style="position: absolute; top: 0; right: 15px; color: #222; font-weight: bold; font-size: 2.5rem; letter-spacing: 5px;">SYS.LOG</div>
            <p><span class="log-prefix">[04:57:01 SYS]</span> Initializing NUVOLA OS v4.2.0...</p>
            <p><span class="log-prefix">[04:57:02 NET]</span> Connecting to Binance WebSocket... <span class="value-green">ESTABLISHED</span></p>
            <p><span class="log-prefix">[04:57:02 NET]</span> Connecting to Arbitrum RPC... <span class="value-green">ESTABLISHED</span></p>
            <p><span class="log-prefix">[04:57:03 HFT]</span> SQUADRA_ALPHA deployed. Capital allocated: 10,000 USDT.</p>
            <p><span class="log-prefix">[04:57:04 TRINITY]</span> Lo Strozzino scanning for funding discrepancies on Bybit/Binance...</p>
            <p><span class="log-prefix log-warn">[04:57:05 WARN]</span> High volatility detected on BTC/USDT. Tightening HFT stop-losses.</p>
            <p><span class="log-prefix">[04:57:06 MEV]</span> L'Angelo Custode observing mempool txs.</p>
            <p><span class="log-prefix">[04:57:07 SYS]</span> <span class="blink">Waiting for next market tick...</span></p>
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
