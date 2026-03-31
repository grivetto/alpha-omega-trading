from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NUVOLA ORBITAL COMMAND // HIGH FREQUENCY TRADING</title>
    <style>
        :root {
            --neon-green: #0f0;
            --neon-pink: #f0f;
            --neon-blue: #0ff;
            --neon-red: #f00;
            --neon-yellow: #ff0;
            --bg-base: #020202;
            --panel-bg: rgba(5, 10, 5, 0.85);
            --grid-color: rgba(0, 255, 0, 0.1);
        }
        
        * { box-sizing: border-box; }
        
        body {
            background-color: var(--bg-base);
            background-image: 
                linear-gradient(var(--grid-color) 1px, transparent 1px),
                linear-gradient(90deg, var(--grid-color) 1px, transparent 1px);
            background-size: 30px 30px;
            color: var(--neon-green);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            overflow-x: hidden;
        }

        /* CRT Overlay */
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

        h1.glitch {
            text-align: center;
            color: var(--neon-blue);
            text-shadow: 0 0 10px var(--neon-blue), 0 0 20px var(--neon-blue);
            font-size: 2.5rem;
            text-transform: uppercase;
            letter-spacing: 5px;
            margin-bottom: 40px;
            border-bottom: 2px solid var(--neon-blue);
            padding-bottom: 15px;
            position: relative;
        }

        .dashboard {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 25px;
            position: relative;
            z-index: 10;
        }

        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-green);
            box-shadow: inset 0 0 20px rgba(0, 255, 0, 0.1), 0 0 15px rgba(0, 255, 0, 0.3);
            border-radius: 4px;
            padding: 20px;
            position: relative;
            overflow: hidden;
        }

        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; height: 2px;
            background: var(--neon-green);
            box-shadow: 0 0 10px var(--neon-green);
        }

        .panel.pink::before { background: var(--neon-pink); box-shadow: 0 0 10px var(--neon-pink); }
        .panel.pink { border-color: var(--neon-pink); box-shadow: inset 0 0 20px rgba(255, 0, 255, 0.1), 0 0 15px rgba(255, 0, 255, 0.3); color: #fff;}
        .panel.pink h2 { color: var(--neon-pink); text-shadow: 0 0 8px var(--neon-pink); border-bottom-color: var(--neon-pink); }
        
        .panel.blue::before { background: var(--neon-blue); box-shadow: 0 0 10px var(--neon-blue); }
        .panel.blue { border-color: var(--neon-blue); box-shadow: inset 0 0 20px rgba(0, 255, 255, 0.1), 0 0 15px rgba(0, 255, 255, 0.3); color: #fff; }
        .panel.blue h2 { color: var(--neon-blue); text-shadow: 0 0 8px var(--neon-blue); border-bottom-color: var(--neon-blue); }

        h2 {
            margin-top: 0;
            font-size: 1.2rem;
            color: var(--neon-green);
            text-shadow: 0 0 8px var(--neon-green);
            border-bottom: 1px dashed var(--neon-green);
            padding-bottom: 10px;
            text-transform: uppercase;
            display: flex;
            justify-content: space-between;
        }

        .status-badge {
            font-size: 0.8rem;
            padding: 3px 8px;
            border-radius: 2px;
            background: rgba(0, 255, 0, 0.2);
            border: 1px solid var(--neon-green);
            animation: pulse 2s infinite;
        }

        .status-badge.bg-sync { background: rgba(0, 255, 255, 0.2); border-color: var(--neon-blue); animation: none; }

        /* Squadre / Teams styling */
        .team-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px 0;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }
        .team-info strong { font-size: 1.1rem; letter-spacing: 1px; }
        .team-info span { display: block; font-size: 0.8rem; color: #888; margin-top: 4px; }
        .team-stats { text-align: right; }
        .team-stats .pnl { color: var(--neon-green); font-weight: bold; text-shadow: 0 0 5px var(--neon-green); }
        .team-stats .pnl.negative { color: var(--neon-red); text-shadow: 0 0 5px var(--neon-red); }
        .team-stats .ping { font-size: 0.75rem; color: #aaa; }

        /* Trinity Background Processes */
        .process {
            margin: 15px 0;
            padding: 10px;
            background: rgba(0,0,0,0.5);
            border-left: 3px solid var(--neon-pink);
            position: relative;
        }
        .process::after {
            content: '[ RUNNING ]';
            position: absolute;
            right: 10px;
            top: 10px;
            font-size: 0.7rem;
            color: var(--neon-pink);
            animation: blink 1.5s infinite;
        }
        .process-title { font-weight: bold; color: #fff; display: flex; align-items: center; gap: 8px;}
        .process-desc { font-size: 0.8rem; color: #aaa; margin-top: 5px; }
        
        /* Loading bar */
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
            background: var(--neon-pink);
            width: 50%;
            box-shadow: 0 0 10px var(--neon-pink);
            animation: load 3s infinite ease-in-out;
        }

        /* Metrics */
        .terminal {
            background: #000;
            border: 1px solid #333;
            padding: 10px;
            font-size: 0.85rem;
            height: 140px;
            overflow: hidden;
            position: relative;
            color: var(--neon-blue);
        }
        .terminal p { margin: 5px 0; opacity: 0; animation: scrollUp 8s infinite linear; }
        .terminal p:nth-child(1) { animation-delay: 0s; }
        .terminal p:nth-child(2) { animation-delay: 2s; }
        .terminal p:nth-child(3) { animation-delay: 4s; }
        .terminal p:nth-child(4) { animation-delay: 6s; }
        
        .metric-row {
            display: flex;
            justify-content: space-between;
            margin-bottom: 10px;
            font-size: 0.9rem;
        }
        .metric-value { font-weight: bold; text-shadow: 0 0 5px currentColor; }
        .alert { color: var(--neon-yellow); animation: blink 1s infinite; }

        /* Animations */
        @keyframes pulse { 0% { box-shadow: 0 0 0 0 rgba(0, 255, 0, 0.4); } 70% { box-shadow: 0 0 0 10px rgba(0, 255, 0, 0); } 100% { box-shadow: 0 0 0 0 rgba(0, 255, 0, 0); } }
        @keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }
        @keyframes load { 0% { width: 10%; transform: translateX(0); } 50% { width: 80%; transform: translateX(10%); } 100% { width: 10%; transform: translateX(900%); } }
        @keyframes scrollUp { 0% { transform: translateY(100px); opacity: 0; } 10% { opacity: 1; } 80% { opacity: 1; } 100% { transform: translateY(-50px); opacity: 0; } }
        
        /* Footer */
        .sys-footer {
            margin-top: 40px;
            text-align: center;
            font-size: 0.8rem;
            color: #555;
            letter-spacing: 2px;
            border-top: 1px solid #222;
            padding-top: 15px;
            position: relative;
            z-index: 10;
        }
    </style>
</head>
<body>
    <h1 class="glitch">🛰️ ORBITAL COMMAND DASHBOARD 🛰️</h1>
    
    <div class="dashboard">
        <!-- 1. SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO <span class="status-badge">ENGAGED</span></h2>
            
            <div class="team-row">
                <div class="team-info">
                    <strong>🐺 SQUADRA_ALPHA</strong>
                    <span>[Scalper] Target: BINANCE_FUTURES</span>
                </div>
                <div class="team-stats">
                    <div class="pnl">+ $1,245.80</div>
                    <div class="ping">Lat: 8ms | Vol: High</div>
                </div>
            </div>
            
            <div class="team-row">
                <div class="team-info">
                    <strong>⚡ SQUADRA_DELTA</strong>
                    <span>[Order Flow] Target: BYBIT_USDT</span>
                </div>
                <div class="team-stats">
                    <div class="pnl">+ $432.10</div>
                    <div class="ping">Lat: 12ms | Vol: Med</div>
                </div>
            </div>
            
            <div class="team-row" style="border-bottom: none;">
                <div class="team-info">
                    <strong>⚖️ SQUADRA_GAMMA</strong>
                    <span>[Pairs Trading] Target: BITGET</span>
                </div>
                <div class="team-stats">
                    <div class="pnl negative">- $12.50</div>
                    <div class="ping">Lat: 15ms | Vol: Low</div>
                </div>
            </div>
        </div>

        <!-- 2. PROTOCOLLO TRINITY -->
        <div class="panel pink">
            <h2>🛡️ PROTOCOLLO TRINITY <span class="status-badge bg-sync">BACKGROUND</span></h2>
            <div style="text-align: center; margin-bottom: 15px; padding: 10px; border: 1px dashed var(--neon-pink); background: rgba(255,0,255,0.1); color: var(--neon-pink); text-shadow: 0 0 5px var(--neon-pink); font-weight: bold; font-size: 0.9rem; letter-spacing: 1px;">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</div>
            
            <div class="process">
                <div class="process-title">🦇 LO STROZZINO</div>
                <div class="process-desc">Funding Rate Arbitrage (Perp vs Spot)</div>
                <div class="progress-bar"><div class="progress-fill"></div></div>
            </div>
            
            <div class="process">
                <div class="process-title">🧮 IL CONTABILE</div>
                <div class="process-desc">Dynamic DCA Strategy & Rebalancing</div>
                <div class="progress-bar"><div class="progress-fill" style="animation-duration: 4s; animation-delay: 1s;"></div></div>
            </div>
            
            <div class="process">
                <div class="process-title">👼 L'ANGELO CUSTODE</div>
                <div class="process-desc">MEV Protection & Sniping (Arbitrum)</div>
                <div class="progress-bar"><div class="progress-fill" style="animation-duration: 2.5s; animation-delay: 0.5s;"></div></div>
            </div>
        </div>

        <!-- 3. METRICHE DI MERCATO -->
        <div class="panel blue">
            <h2>📊 METRICHE DI MERCATO <span class="status-badge" style="background: rgba(0,255,255,0.2); border-color: var(--neon-blue);">LIVE</span></h2>
            
            <div class="metric-row">
                <span>SYSTEM LATENCY:</span>
                <span class="metric-value">12 ms</span>
            </div>
            <div class="metric-row">
                <span>GLOBAL EXPOSURE:</span>
                <span class="metric-value" style="color: var(--neon-green)">14.2% (SAFE)</span>
            </div>
            <div class="metric-row alert">
                <span>🐋 WHALE TRACKER:</span>
                <span class="metric-value">> $50M INFLOW (BTC)</span>
            </div>
            
            <div style="margin-top: 15px; font-size: 0.8rem; color: #888;">🔮 THE ORACLE (Sentiment Engine)</div>
            <div class="terminal">
                <p>> Analyzing Binance order book...</p>
                <p>> Sentiment Shift Detected: BULLISH [78%]</p>
                <p>> Liquidations pending at $72,500...</p>
                <p>> SQUADRA_ALPHA engaging liquidity traps...</p>
                <p>> Analyzing ByBit order book...</p>
                <p>> Sentiment Shift Detected: NEUTRAL [55%]</p>
                <p>> Waiting for volume spike...</p>
            </div>
        </div>
    </div>
    
    <div class="sys-footer">
        SECURE CONNECTION ESTABLISHED // ALL QUANTITATIVE SYSTEMS NOMINAL // NUVOLA NETWORK v3.1.4 // ENCRYPTED
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
