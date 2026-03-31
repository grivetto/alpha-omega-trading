import os
from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ORBITAL COMMAND // NUVOLA</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');
        
        :root {
            --bg-base: #020205;
            --neon-green: #39ff14;
            --neon-blue: #00f3ff;
            --neon-pink: #ff00ea;
            --neon-red: #ff073a;
            --neon-yellow: #fce803;
            --panel-bg: rgba(5, 10, 15, 0.85);
            --grid-color: rgba(0, 243, 255, 0.08);
            --border-glow: 0 0 10px rgba(0, 243, 255, 0.5);
        }
        
        * { box-sizing: border-box; }
        
        body {
            background-color: var(--bg-base);
            color: var(--neon-green);
            font-family: 'Share Tech Mono', monospace;
            margin: 0;
            padding: 2vw;
            background-image: 
                linear-gradient(var(--grid-color) 1px, transparent 1px),
                linear-gradient(90deg, var(--grid-color) 1px, transparent 1px);
            background-size: 40px 40px;
            overflow-x: hidden;
            display: flex;
            flex-direction: column;
            gap: 20px;
        }

        /* Glitch effect on header */
        .glitch-wrapper {
            text-align: center;
            margin-bottom: 20px;
            position: relative;
        }
        .glitch {
            font-size: 3rem;
            font-weight: bold;
            text-transform: uppercase;
            color: var(--neon-blue);
            text-shadow: 0 0 15px var(--neon-blue), 0 0 30px var(--neon-blue);
            position: relative;
            display: inline-block;
            letter-spacing: 4px;
        }
        .glitch::before, .glitch::after {
            content: "🛰️ ORBITAL COMMAND // NUVOLA";
            position: absolute;
            top: 0; left: 0; width: 100%; height: 100%;
            background: var(--bg-base);
        }
        .glitch::before {
            left: 2px;
            text-shadow: -2px 0 var(--neon-red);
            clip: rect(24px, 550px, 90px, 0);
            animation: glitch-anim 3s infinite linear alternate-reverse;
        }
        .glitch::after {
            left: -2px;
            text-shadow: -2px 0 var(--neon-green);
            clip: rect(85px, 550px, 140px, 0);
            animation: glitch-anim 2.5s infinite linear alternate-reverse;
        }
        
        @keyframes glitch-anim {
            0% { clip: rect(10px, 9999px, 81px, 0); }
            20% { clip: rect(62px, 9999px, 12px, 0); }
            40% { clip: rect(15px, 9999px, 89px, 0); }
            60% { clip: rect(78px, 9999px, 20px, 0); }
            80% { clip: rect(4px, 9999px, 72px, 0); }
            100% { clip: rect(45px, 9999px, 34px, 0); }
        }

        .status-bar {
            display: flex;
            justify-content: space-between;
            border-top: 1px solid var(--neon-blue);
            border-bottom: 1px solid var(--neon-blue);
            padding: 10px 20px;
            font-size: 1.1rem;
            color: var(--neon-blue);
            background: rgba(0, 243, 255, 0.05);
            text-shadow: 0 0 5px var(--neon-blue);
            text-transform: uppercase;
        }

        .blink { animation: blinker 1s linear infinite; }
        @keyframes blinker { 50% { opacity: 0; } }

        .dashboard-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 25px;
            width: 100%;
        }

        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-blue);
            border-radius: 4px;
            padding: 20px;
            position: relative;
            box-shadow: inset 0 0 20px rgba(0, 243, 255, 0.1), 0 0 10px rgba(0, 243, 255, 0.2);
            overflow: hidden;
        }
        
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: -100%;
            width: 50%; height: 2px;
            background: linear-gradient(90deg, transparent, var(--neon-blue), transparent);
            animation: scanline 4s linear infinite;
        }
        
        @keyframes scanline {
            0% { left: -100%; }
            100% { left: 200%; }
        }

        .panel h2 {
            margin-top: 0;
            padding-bottom: 10px;
            border-bottom: 1px dashed rgba(255,255,255,0.2);
            font-size: 1.5rem;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .assault-title { color: var(--neon-red); text-shadow: 0 0 8px var(--neon-red); border-color: var(--neon-red) !important; }
        .trinity-title { color: var(--neon-pink); text-shadow: 0 0 8px var(--neon-pink); border-color: var(--neon-pink) !important; }
        .metrics-title { color: var(--neon-yellow); text-shadow: 0 0 8px var(--neon-yellow); border-color: var(--neon-yellow) !important; }

        .row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px 0;
            border-bottom: 1px solid rgba(255,255,255,0.05);
        }
        .row:last-child { border-bottom: none; }

        .val-green { color: var(--neon-green); text-shadow: 0 0 5px var(--neon-green); }
        .val-red { color: var(--neon-red); text-shadow: 0 0 5px var(--neon-red); }
        .val-blue { color: var(--neon-blue); text-shadow: 0 0 5px var(--neon-blue); }
        .val-pink { color: var(--neon-pink); text-shadow: 0 0 5px var(--neon-pink); }

        .progress-bar {
            width: 100px;
            height: 8px;
            background: #111;
            border: 1px solid #333;
            border-radius: 4px;
            overflow: hidden;
            position: relative;
        }
        .progress-fill {
            height: 100%;
            background: var(--neon-green);
            box-shadow: 0 0 5px var(--neon-green);
            width: 0%;
        }

        .anim-fill-1 { animation: fillBar 3s ease-in-out infinite alternate; }
        .anim-fill-2 { animation: fillBar 4s ease-in-out infinite alternate-reverse; background: var(--neon-blue); box-shadow: 0 0 5px var(--neon-blue);}
        .anim-fill-3 { animation: fillBar 2.5s ease-in-out infinite alternate; background: var(--neon-pink); box-shadow: 0 0 5px var(--neon-pink);}
        
        @keyframes fillBar { 0% { width: 10%; } 100% { width: 95%; } }

        .log-box {
            background: rgba(0,0,0,0.5);
            border: 1px solid #333;
            padding: 10px;
            font-size: 0.85rem;
            color: #888;
            height: 100px;
            overflow: hidden;
            margin-top: 15px;
        }
        
        .log-entry { margin-bottom: 4px; }
        .log-time { color: var(--neon-blue); margin-right: 8px; }

        .radar {
            width: 60px; height: 60px;
            border-radius: 50%;
            border: 1px solid var(--neon-green);
            position: relative;
            background: radial-gradient(circle, rgba(57,255,20,0.1) 0%, transparent 70%);
            box-shadow: 0 0 10px var(--neon-green);
        }
        .radar::after {
            content: ''; position: absolute; top: 50%; left: 50%; width: 50%; height: 2px;
            background: var(--neon-green); transform-origin: left center;
            animation: radar-spin 2s linear infinite;
        }
        @keyframes radar-spin { 100% { transform: rotate(360deg); } }

    </style>
</head>
<body>

    <div class="glitch-wrapper">
        <div class="glitch">🛰️ ORBITAL COMMAND // NUVOLA</div>
    </div>

    <div class="status-bar">
        <span>SYS: <span class="val-green blink">ONLINE</span></span>
        <span>LATENCY: <span class="val-blue">14ms</span></span>
        <span>UPTIME: <span class="val-pink">94.2%</span></span>
        <span>DEFCON: <span class="val-green">5</span></span>
    </div>

    <div class="status-bar" style="justify-content: center; color: var(--neon-pink); border-color: var(--neon-pink); box-shadow: 0 0 10px rgba(255,0,234,0.2);">
        <span>⚙️ PROTOCOLLO TRINITY: <span class="blink" style="color: var(--neon-green);">Online (DCA, Funding, MEV)</span></span>
    </div>

    <div class="dashboard-grid">
        
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <h2 class="assault-title">⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            
            <div class="row">
                <div>
                    <strong>🐺 SQUADRA_ALPHA</strong> <br>
                    <small>Role: Binance Scalper</small>
                </div>
                <div style="text-align: right;">
                    <span class="val-green blink">[ ENGAGED ]</span><br>
                    <small class="val-blue">WinRate: 68.4%</small>
                </div>
            </div>
            
            <div class="row">
                <div>
                    <strong>🌊 SQUADRA_DELTA</strong> <br>
                    <small>Role: Order Flow Arbitrage</small>
                </div>
                <div style="text-align: right;">
                    <span class="val-green">[ ACTIVE ]</span><br>
                    <small class="val-blue">Vol: $1.2M/24h</small>
                </div>
            </div>
            
            <div class="row">
                <div>
                    <strong>⚖️ SQUADRA_GAMMA</strong> <br>
                    <small>Role: Pairs Trading (Bitget)</small>
                </div>
                <div style="text-align: right;">
                    <span class="val-yellow" style="color:var(--neon-yellow); text-shadow:0 0 5px var(--neon-yellow);">[ STANDBY ]</span><br>
                    <small class="val-blue">Awaiting Spread</small>
                </div>
            </div>

            <div class="log-box">
                <div class="log-entry"><span class="log-time">07:42:11</span> > ALPHA: Executed buy order BTC/USDT @ 69,420</div>
                <div class="log-entry"><span class="log-time">07:42:35</span> > DELTA: Imbalance detected on Bybit. Routing...</div>
                <div class="log-entry"><span class="log-time">07:43:01</span> > GAMMA: Spread deviation normal. Holding.</div>
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2 class="trinity-title">👁️ PROTOCOLLO TRINITY</h2>
            
            <div class="row">
                <div>
                    <strong>🧛 Lo Strozzino</strong> <br>
                    <small>Funding Rate Arb</small>
                </div>
                <div style="display: flex; align-items: center; gap: 10px;">
                    <div class="progress-bar"><div class="progress-fill anim-fill-1"></div></div>
                    <span class="val-pink blink">SYPHONING</span>
                </div>
            </div>
            
            <div class="row">
                <div>
                    <strong>🧮 Il Contabile</strong> <br>
                    <small>Smart DCA Engine</small>
                </div>
                <div style="display: flex; align-items: center; gap: 10px;">
                    <div class="progress-bar"><div class="progress-fill anim-fill-2"></div></div>
                    <span class="val-pink">ACCUMULATING</span>
                </div>
            </div>
            
            <div class="row">
                <div>
                    <strong>🛡️ L'Angelo Custode</strong> <br>
                    <small>Arbitrum MEV Protection</small>
                </div>
                <div style="display: flex; align-items: center; gap: 10px;">
                    <div class="progress-bar"><div class="progress-fill anim-fill-3"></div></div>
                    <span class="val-pink">GUARDING</span>
                </div>
            </div>

            <div class="log-box" style="border-color: rgba(255,0,234,0.3);">
                <div class="log-entry" style="color: var(--neon-pink);"><span class="log-time" style="color: #fff;">SYS</span> > TRINITY BACKGROUND DAEMONS ONLINE.</div>
                <div class="log-entry"><span class="log-time">SYS</span> > Lo Strozzino: +0.02% yield captured.</div>
                <div class="log-entry"><span class="log-time">SYS</span> > Il Contabile: Next DCA trigger in 14m 20s.</div>
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <h2 class="metrics-title">📊 METRICHE DI MERCATO</h2>
            
            <div class="row">
                <div style="display: flex; align-items: center; gap: 15px;">
                    <div class="radar"></div>
                    <div>
                        <strong>🔮 The Oracle</strong> <br>
                        <small>Binance Sentiment Matrix</small>
                    </div>
                </div>
                <div style="text-align: right;">
                    <span class="val-red blink">FEAR [ 28 ] ⚠️</span><br>
                    <small style="color: #888;">Short Bias</small>
                </div>
            </div>
            
            <div class="row">
                <div>
                    <strong>🐋 Whale Tracker</strong> <br>
                    <small>On-Chain Sonar</small>
                </div>
                <div style="text-align: right;">
                    <span class="val-blue">LARGE MOVES</span><br>
                    <small class="val-red">> 5K BTC moved</small>
                </div>
            </div>
            
            <div class="row">
                <div>
                    <strong>💸 Global Liquidity</strong> <br>
                    <small>Aggregated Orderbooks</small>
                </div>
                <div style="text-align: right;">
                    <span class="val-green">OPTIMAL</span><br>
                    <small class="val-blue">Depth: Tier 1</small>
                </div>
            </div>

        </div>

    </div>

    <div style="text-align: center; margin-top: 20px; font-size: 0.8rem; color: #555; letter-spacing: 2px;">
        TERMINAL v4.2.0 // UNAUTHORIZED ACCESS WILL BE LETHAL // GHOST IN THE SHELL PROTOCOL ACTIVE
    </div>

</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
