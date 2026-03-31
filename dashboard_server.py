import os
from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ORBITAL COMMAND // NUVOLA SYSTEM</title>
    <style>
        :root {
            --bg: #030305;
            --blue: #00f3ff;
            --pink: #ff00ea;
            --green: #00ff66;
            --yellow: #ffb800;
            --panel: rgba(5, 10, 15, 0.8);
            --scanline: rgba(0, 243, 255, 0.1);
        }
        
        * { box-sizing: border-box; }
        
        body {
            background-color: var(--bg);
            color: #fff;
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            background-image: 
                linear-gradient(var(--scanline) 1px, transparent 1px),
                linear-gradient(90deg, var(--scanline) 1px, transparent 1px);
            background-size: 30px 30px;
            overflow-x: hidden;
        }

        /* Scanline Overlay */
        body::after {
            content: "";
            position: fixed;
            top: 0; left: 0; width: 100vw; height: 100vh;
            background: linear-gradient(rgba(18, 16, 16, 0) 50%, rgba(0, 0, 0, 0.25) 50%), linear-gradient(90deg, rgba(255, 0, 0, 0.06), rgba(0, 255, 0, 0.02), rgba(0, 0, 255, 0.06));
            background-size: 100% 4px, 6px 100%;
            z-index: 1000;
            pointer-events: none;
        }

        .header {
            text-align: center;
            margin-bottom: 40px;
            border-bottom: 2px solid var(--blue);
            padding-bottom: 20px;
            position: relative;
        }
        
        .header::after {
            content: '';
            position: absolute;
            bottom: -2px; left: 0; width: 100%; height: 2px;
            background: var(--blue);
            box-shadow: 0 0 10px var(--blue), 0 0 20px var(--blue);
            animation: flicker 4s infinite alternate;
        }

        h1 {
            color: var(--blue);
            text-transform: uppercase;
            text-shadow: 0 0 10px var(--blue), 0 0 20px var(--blue);
            letter-spacing: 5px;
            margin: 0;
            font-size: 2.5em;
        }

        .subtitle {
            color: var(--green);
            font-size: 1.2em;
            margin-top: 10px;
            font-weight: bold;
            text-shadow: 0 0 10px var(--green);
            animation: pulse 2s infinite;
        }

        .dashboard-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 30px;
            max-width: 1400px;
            margin: 0 auto;
            position: relative;
            z-index: 10;
        }

        .panel {
            background: var(--panel);
            border: 1px solid #333;
            border-radius: 8px;
            padding: 25px;
            position: relative;
            backdrop-filter: blur(5px);
            transition: all 0.3s ease;
        }

        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; width: 100%; height: 100%;
            border-radius: 8px;
            pointer-events: none;
            box-shadow: inset 0 0 20px rgba(0, 0, 0, 0.8);
        }

        .panel.hft { border-color: var(--blue); box-shadow: 0 0 15px rgba(0, 243, 255, 0.1), inset 0 0 20px rgba(0, 243, 255, 0.05); }
        .panel.trinity { border-color: var(--pink); box-shadow: 0 0 15px rgba(255, 0, 234, 0.1), inset 0 0 20px rgba(255, 0, 234, 0.05); }
        .panel.metrics { border-color: var(--green); box-shadow: 0 0 15px rgba(0, 255, 102, 0.1), inset 0 0 20px rgba(0, 255, 102, 0.05); }

        .panel:hover { transform: translateY(-5px); }
        .panel.hft:hover { box-shadow: 0 0 25px rgba(0, 243, 255, 0.3), inset 0 0 20px rgba(0, 243, 255, 0.1); }
        .panel.trinity:hover { box-shadow: 0 0 25px rgba(255, 0, 234, 0.3), inset 0 0 20px rgba(255, 0, 234, 0.1); }
        .panel.metrics:hover { box-shadow: 0 0 25px rgba(0, 255, 102, 0.3), inset 0 0 20px rgba(0, 255, 102, 0.1); }

        .panel h2 {
            margin-top: 0;
            font-size: 1.4em;
            border-bottom: 1px solid #444;
            padding-bottom: 15px;
            display: flex;
            align-items: center;
            gap: 15px;
            letter-spacing: 2px;
        }

        .panel.hft h2 { color: var(--blue); border-bottom-color: var(--blue); text-shadow: 0 0 8px var(--blue); }
        .panel.trinity h2 { color: var(--pink); border-bottom-color: var(--pink); text-shadow: 0 0 8px var(--pink); }
        .panel.metrics h2 { color: var(--green); border-bottom-color: var(--green); text-shadow: 0 0 8px var(--green); }

        .item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 15px;
            margin: 15px 0;
            background: rgba(0, 0, 0, 0.7);
            border-left: 4px solid;
            border-radius: 4px;
            position: relative;
            overflow: hidden;
        }

        .item::after {
            content: '';
            position: absolute;
            top: 0; left: -100%; width: 50%; height: 100%;
            background: linear-gradient(90deg, transparent, rgba(255,255,255,0.05), transparent);
            animation: sweep 3s infinite linear;
        }

        .item.hft-item { border-left-color: var(--blue); }
        .item.trinity-item { border-left-color: var(--pink); }
        .item.metric-item { border-left-color: var(--green); }

        .item-title {
            font-weight: bold;
            font-size: 1.1em;
            margin-bottom: 5px;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .item-desc {
            font-size: 0.8em;
            color: #888;
        }

        .status-badge {
            padding: 5px 10px;
            border-radius: 3px;
            font-size: 0.8em;
            font-weight: bold;
            letter-spacing: 1px;
            animation: blink 2s infinite alternate;
        }

        .status-badge.online { color: #000; background: var(--green); box-shadow: 0 0 10px var(--green); }
        .status-badge.active { color: #000; background: var(--pink); box-shadow: 0 0 10px var(--pink); }
        .status-badge.warning { color: #000; background: var(--yellow); box-shadow: 0 0 10px var(--yellow); }

        .metric-data {
            text-align: right;
        }
        
        .metric-value {
            font-size: 1.2em;
            font-weight: bold;
            margin-bottom: 5px;
        }

        .glitch {
            position: relative;
        }
        .glitch::before, .glitch::after {
            content: attr(data-text);
            position: absolute;
            top: 0; left: 0;
            width: 100%; height: 100%;
            background: var(--bg);
        }
        .glitch::before {
            left: 2px;
            text-shadow: -1px 0 var(--pink);
            clip: rect(24px, 550px, 90px, 0);
            animation: glitch-anim-2 3s infinite linear alternate-reverse;
        }
        .glitch::after {
            left: -2px;
            text-shadow: -1px 0 var(--blue);
            clip: rect(85px, 550px, 140px, 0);
            animation: glitch-anim 2.5s infinite linear alternate-reverse;
        }

        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.6; }
        }
        @keyframes blink {
            0% { opacity: 0.8; }
            100% { opacity: 1; box-shadow: 0 0 15px currentColor; }
        }
        @keyframes sweep {
            100% { left: 200%; }
        }
        @keyframes flicker {
            0%, 100% { opacity: 1; }
            33% { opacity: 0.8; }
            66% { opacity: 0.9; }
        }
        @keyframes glitch-anim {
            0% { clip: rect(13px, 9999px, 86px, 0); }
            20% { clip: rect(44px, 9999px, 16px, 0); }
            40% { clip: rect(65px, 9999px, 92px, 0); }
            60% { clip: rect(21px, 9999px, 54px, 0); }
            80% { clip: rect(87px, 9999px, 31px, 0); }
            100% { clip: rect(11px, 9999px, 76px, 0); }
        }
        @keyframes glitch-anim-2 {
            0% { clip: rect(65px, 9999px, 100px, 0); }
            20% { clip: rect(12px, 9999px, 55px, 0); }
            40% { clip: rect(86px, 9999px, 22px, 0); }
            60% { clip: rect(34px, 9999px, 88px, 0); }
            80% { clip: rect(9px, 9999px, 45px, 0); }
            100% { clip: rect(77px, 9999px, 14px, 0); }
        }
    </style>
</head>
<body>

    <div class="header">
        <h1 class="glitch" data-text="ORBITAL COMMAND // NUVOLA">🛰️ ORBITAL COMMAND // NUVOLA 🌐</h1>
        <div class="subtitle">► SYSTEM OVERRIDE: ACTIVE | SECURE CONNECTION ESTABLISHED ◄</div>
        <div class="subtitle" style="color: var(--pink); margin-top: 15px; border: 1px solid var(--pink); display: inline-block; padding: 10px 20px; border-radius: 5px; box-shadow: 0 0 10px rgba(255,0,234,0.3); background: rgba(255,0,234,0.1);">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</div>
    </div>

    <div class="dashboard-grid">
        
        <!-- SQUADRE D'ASSALTO -->
        <div class="panel hft">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            
            <div class="item hft-item">
                <div>
                    <div class="item-title">🐺 SQUADRA_ALPHA</div>
                    <div class="item-desc">Binance Scalper // High Freq.</div>
                </div>
                <div class="status-badge online">ENGAGED [9ms]</div>
            </div>
            
            <div class="item hft-item">
                <div>
                    <div class="item-title">🎯 SQUADRA_DELTA</div>
                    <div class="item-desc">Order Flow // Liquidity Snipe</div>
                </div>
                <div class="status-badge online">ENGAGED [14ms]</div>
            </div>
            
            <div class="item hft-item">
                <div>
                    <div class="item-title">⚖️ SQUADRA_GAMMA</div>
                    <div class="item-desc">Bitget // Statistical Pairs</div>
                </div>
                <div class="status-badge online">ENGAGED [21ms]</div>
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel trinity">
            <h2>🔮 PROTOCOLLO TRINITY</h2>
            
            <div class="item trinity-item">
                <div>
                    <div class="item-title">🕴️ Lo Strozzino</div>
                    <div class="item-desc">Funding Rate Arbitrage (Delta Neutral)</div>
                </div>
                <div class="status-badge active">HARVESTING</div>
            </div>
            
            <div class="item trinity-item">
                <div>
                    <div class="item-title">🧮 Il Contabile</div>
                    <div class="item-desc">Smart DCA // Dynamic Accumulation</div>
                </div>
                <div class="status-badge active">DEPLOYED</div>
            </div>
            
            <div class="item trinity-item">
                <div>
                    <div class="item-title">👼 L'Angelo Custode</div>
                    <div class="item-desc">Arbitrum MEV // Frontrun Protection</div>
                </div>
                <div class="status-badge active">SHIELD ON</div>
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel metrics">
            <h2>📊 MARKET METRICS & INTEL</h2>
            
            <div class="item metric-item">
                <div>
                    <div class="item-title">👁️ THE ORACLE</div>
                    <div class="item-desc">Binance Sentiment Index</div>
                </div>
                <div class="metric-data">
                    <div class="metric-value" style="color: var(--green); text-shadow: 0 0 8px var(--green);">82% LONG</div>
                    <div class="item-desc">Extremely Bullish</div>
                </div>
            </div>
            
            <div class="item metric-item">
                <div>
                    <div class="item-title">🐋 WHALE TRACKER</div>
                    <div class="item-desc">On-Chain Anomalies</div>
                </div>
                <div class="metric-data">
                    <div class="metric-value" style="color: var(--yellow); text-shadow: 0 0 8px var(--yellow);">⚠ 120M USDT</div>
                    <div class="item-desc">-> Binance Hot Wallet</div>
                </div>
            </div>
            
            <div class="item metric-item">
                <div>
                    <div class="item-title">⚡ SYSTEM CORE</div>
                    <div class="item-desc">Network Integrity</div>
                </div>
                <div class="metric-data">
                    <div class="metric-value" style="color: var(--blue); text-shadow: 0 0 8px var(--blue);">100% UPTIME</div>
                    <div class="item-desc">Latency: &lt;15ms Avg</div>
                </div>
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
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
