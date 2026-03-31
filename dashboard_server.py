import os
from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Nuvola Orbital Command // TERMINAL</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');
        
        :root {
            --bg: #030303;
            --neon-primary: #00ffff;
            --neon-secondary: #ff00ff;
            --neon-success: #00ff00;
            --neon-danger: #ff0033;
            --neon-warning: #ffcc00;
            --grid-color: rgba(0, 255, 255, 0.05);
            --scanline-color: rgba(0, 0, 0, 0.3);
        }

        body {
            background-color: var(--bg);
            color: var(--neon-primary);
            font-family: 'Share Tech Mono', monospace;
            margin: 0;
            padding: 20px;
            background-image: 
                linear-gradient(var(--grid-color) 1px, transparent 1px),
                linear-gradient(90deg, var(--grid-color) 1px, transparent 1px);
            background-size: 40px 40px;
            overflow-x: hidden;
            text-transform: uppercase;
        }

        body::after {
            content: " ";
            display: block;
            position: fixed;
            top: 0; left: 0; bottom: 0; right: 0;
            background: linear-gradient(
                to bottom,
                rgba(18, 16, 16, 0) 50%,
                var(--scanline-color) 50%
            );
            background-size: 100% 4px;
            z-index: 9999;
            pointer-events: none;
        }

        h1 {
            text-align: center;
            font-size: 3.5rem;
            color: #ffffff;
            text-shadow: 0 0 10px var(--neon-primary), 0 0 20px var(--neon-primary), 0 0 40px var(--neon-primary), 0 0 80px var(--neon-primary);
            margin-bottom: 5px;
            letter-spacing: 8px;
            animation: glitch 3s infinite;
        }

        @keyframes glitch {
            0% { text-shadow: 0 0 10px var(--neon-primary); }
            98% { text-shadow: 0 0 10px var(--neon-primary); }
            99% { text-shadow: -5px 0 0 var(--neon-danger), 5px 0 0 var(--neon-primary); }
            100% { text-shadow: 0 0 10px var(--neon-primary); }
        }

        .subtitle {
            text-align: center;
            color: var(--neon-secondary);
            font-size: 1.2rem;
            margin-bottom: 40px;
            text-shadow: 0 0 10px var(--neon-secondary);
            letter-spacing: 4px;
        }

        .trinity-status {
            text-align: center;
            color: var(--neon-success);
            font-size: 1.8rem;
            margin-bottom: 50px;
            text-shadow: 0 0 15px var(--neon-success);
            font-weight: bold;
            border: 2px dashed var(--neon-success);
            padding: 20px;
            width: fit-content;
            margin: 0 auto 50px auto;
            box-shadow: inset 0 0 30px rgba(0, 255, 0, 0.2);
            animation: pulse-border 2s infinite;
            background: rgba(0, 255, 0, 0.05);
        }

        @keyframes pulse-border {
            0% { box-shadow: inset 0 0 10px rgba(0, 255, 0, 0.1), 0 0 10px rgba(0,255,0,0.1); }
            50% { box-shadow: inset 0 0 40px rgba(0, 255, 0, 0.5), 0 0 30px rgba(0,255,0,0.4); }
            100% { box-shadow: inset 0 0 10px rgba(0, 255, 0, 0.1), 0 0 10px rgba(0,255,0,0.1); }
        }

        .container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(450px, 1fr));
            gap: 40px;
            max-width: 1800px;
            margin: 0 auto;
        }

        .panel {
            background: rgba(5, 5, 5, 0.9);
            border: 1px solid var(--neon-primary);
            box-shadow: 0 0 20px rgba(0, 255, 255, 0.15), inset 0 0 20px rgba(0, 255, 255, 0.1);
            padding: 30px;
            position: relative;
            overflow: hidden;
            border-radius: 4px;
        }

        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0;
            width: 100%; height: 4px;
            background: var(--neon-primary);
            box-shadow: 0 0 20px var(--neon-primary);
        }

        .panel h2 {
            font-size: 2rem;
            color: var(--neon-success);
            text-shadow: 0 0 15px var(--neon-success);
            border-bottom: 2px solid var(--neon-success);
            padding-bottom: 15px;
            margin-top: 0;
            display: flex;
            align-items: center;
            gap: 15px;
        }

        .row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 15px 0;
            border-bottom: 1px dashed rgba(0, 255, 255, 0.2);
            font-size: 1.3rem;
        }

        .row:last-child {
            border-bottom: none;
        }

        .label {
            color: #ffffff;
            text-shadow: 0 0 8px rgba(255,255,255,0.8);
            display: flex;
            flex-direction: column;
        }

        .label-desc {
            font-size: 0.75rem;
            color: #aaaaaa;
            text-shadow: none;
            margin-top: 5px;
        }

        .status {
            font-weight: bold;
            text-shadow: 0 0 15px currentColor;
            letter-spacing: 2px;
            padding: 5px 10px;
            border: 1px solid currentColor;
            border-radius: 3px;
            background: rgba(0,0,0,0.5);
        }

        .s-ok { color: var(--neon-success); }
        .s-warn { color: var(--neon-warning); }
        .s-err { color: var(--neon-danger); }
        .s-info { color: var(--neon-primary); }
        .s-purple { color: var(--neon-secondary); }

        .blink { animation: blinker 1.5s linear infinite; }
        .fast-blink { animation: blinker 0.5s linear infinite; }

        @keyframes blinker {
            50% { opacity: 0.3; }
        }

        .terminal-box {
            background: #000;
            border: 1px solid var(--neon-primary);
            color: var(--neon-success);
            padding: 20px;
            height: 180px;
            overflow-y: hidden;
            font-size: 1.1rem;
            margin-top: 25px;
            position: relative;
            box-shadow: inset 0 0 20px rgba(0,255,0,0.1);
            font-family: monospace;
            line-height: 1.4;
        }

        .terminal-box::before {
            content: 'TERMINAL OUTPUT';
            position: absolute;
            top: 0; right: 0;
            background: var(--neon-primary);
            color: #000;
            padding: 2px 10px;
            font-size: 0.8rem;
            font-weight: bold;
        }

        .terminal-box p { margin: 6px 0; }
        .terminal-box p::before { content: "> "; color: var(--neon-primary); }
        .terminal-box::after {
            content: "█";
            animation: blinker 1s infinite;
        }

        .trinity-core {
            border-color: var(--neon-secondary);
            box-shadow: 0 0 30px rgba(255, 0, 255, 0.2), inset 0 0 20px rgba(255, 0, 255, 0.1);
        }
        .trinity-core::before { background: var(--neon-secondary); box-shadow: 0 0 20px var(--neon-secondary); }
        .trinity-core h2 { color: var(--neon-secondary); text-shadow: 0 0 15px var(--neon-secondary); border-bottom-color: var(--neon-secondary); }

        .bar-bg {
            background: rgba(255,255,255,0.1);
            height: 12px;
            width: 100%;
            margin-top: 10px;
            border-radius: 2px;
            overflow: hidden;
            box-shadow: inset 0 0 8px #000;
            border: 1px solid rgba(255,255,255,0.2);
        }
        .bar-fill {
            height: 100%;
            background: var(--neon-primary);
            box-shadow: 0 0 15px var(--neon-primary);
            transition: width 0.5s ease-in-out;
        }
        
        .hud-overlay {
            position: fixed;
            top: 20px;
            right: 20px;
            border: 1px solid var(--neon-primary);
            padding: 15px;
            color: var(--neon-primary);
            font-size: 0.9rem;
            background: rgba(0,0,0,0.9);
            z-index: 100;
            box-shadow: 0 0 15px rgba(0, 255, 255, 0.2);
        }
        .hud-overlay span { color: #fff; }
    </style>
</head>
<body>
    <div class="hud-overlay">
        LATENCY: <span>14ms</span><br>
        UPLINK: <span class="s-ok blink">SECURE</span><br>
        NODES: <span>42 ONLINE</span><br>
        LOAD: <span>14.3%</span>
    </div>

    <h1>[ NUVOLA ORBITAL COMMAND ]</h1>
    <div class="subtitle blink">SYSTEM STATUS: NOMINAL // ALL HFT NODES CONNECTED // DEFCON 5</div>
    
    <div class="trinity-status">
        ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
        <div style="font-size: 0.6em; color: var(--neon-primary); margin-top: 10px; text-shadow: none;">[ LO STROZZINO // IL CONTABILE // L'ANGELO CUSTODE ]</div>
        <div style="font-size: 0.4em; color: #aaa; margin-top: 5px; text-shadow: none;">BACKGROUND SERVICES: 3/3 RUNNING</div>
    </div>

    <div class="container">
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <div class="row">
                <span class="label">🐺 SQUADRA_ALPHA <span class="label-desc">[BINANCE SCALPER // HIGH-FREQUENCY]</span></span>
                <span class="status s-ok blink">ENGAGED</span>
            </div>
            <div class="row">
                <span class="label">⚡ SQUADRA_DELTA <span class="label-desc">[ORDER FLOW // LIQUIDITY SNIPER]</span></span>
                <span class="status s-info">ACTIVE</span>
            </div>
            <div class="row">
                <span class="label">⚖️ SQUADRA_GAMMA <span class="label-desc">[BITGET PAIRS // STATISTICAL ARB]</span></span>
                <span class="status s-warn">ARBITRAGING</span>
            </div>
            <div class="terminal-box">
                <p>[SYS] ALPHA: Executing trailing buy BTC/USDT @ 62450.50</p>
                <p>[SYS] DELTA: High latency detected on tick stream. Adjusting quotes.</p>
                <p>[SYS] GAMMA: Spread reached 0.18%. Awaiting 0.20% target.</p>
                <p>[SYS] ALPHA: 0.5 BTC filled. Placing sell limit +0.15%.</p>
                <p>[SYS] ALL TEAMS: Sync heartbeat OK. Ping: 8ms.</p>
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel trinity-core">
            <h2>🔺 PROTOCOLLO TRINITY</h2>
            <div class="row">
                <span class="label">🕴️ Lo Strozzino <span class="label-desc">[FUNDING ARB // DELTA NEUTRAL]</span></span>
                <span class="status s-purple blink">HARVESTING</span>
            </div>
            <div class="row">
                <span class="label">🧮 Il Contabile <span class="label-desc">[DCA/VAULT // SMART ACCUMULATION]</span></span>
                <span class="status s-info">ACCUMULATING</span>
            </div>
            <div class="row">
                <span class="label">🛡️ L'Angelo Custode <span class="label-desc">[MEV ARBITRUM // SANDWICH PROTECTOR]</span></span>
                <span class="status s-ok">PROTECTING</span>
            </div>
            <div class="terminal-box" style="color: var(--neon-secondary); border-color: var(--neon-secondary); box-shadow: inset 0 0 20px rgba(255,0,255,0.15);">
                <p>[TRINITY] STROZZINO: Short PERP, Long SPOT (Est. APR: 19.4%)</p>
                <p>[TRINITY] CONTABILE: BTC Vault balance +0.0125 BTC.</p>
                <p>[TRINITY] ANGELO: Arbitrum mempool scan active. 0 threats detected.</p>
                <p>[TRINITY] Background daemons running gracefully.</p>
                <p>[TRINITY] Yield farming protocols synchronized.</p>
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <h2>📊 METRICHE DI MERCATO</h2>
            <div class="row">
                <span class="label">👁️ THE ORACLE <span class="label-desc">[BINANCE SENTIMENT ENGINE]</span></span>
                <span class="status s-warn">GREED (74/100)</span>
            </div>
            <div class="bar-bg"><div class="bar-fill" style="width: 74%; background: var(--neon-warning); box-shadow: 0 0 15px var(--neon-warning);"></div></div>
            
            <div class="row" style="margin-top: 20px;">
                <span class="label">🐋 WHALE TRACKER <span class="label-desc">[ON-CHAIN SURVEILLANCE]</span></span>
                <span class="status s-err fast-blink">ALERT: 8000 BTC -> CEX</span>
            </div>
            
            <div class="row" style="margin-top: 20px;">
                <span class="label">🌊 LIQUIDITY HEATMAP <span class="label-desc">[ORDERBOOK DEPTH]</span></span>
                <span class="status s-info">CONCENTRATED @ $65,500</span>
            </div>
            
            <div class="row" style="margin-top: 20px;">
                <span class="label">🔥 NETWORK GAS (ETH) <span class="label-desc">[BASE FEE]</span></span>
                <span class="status s-ok">14 GWEI</span>
            </div>
            
            <div class="terminal-box">
                <p>[DATA] ORACLE: Aggregating orderbook depth (L2)...</p>
                <p>[DATA] ORACLE: L/S Ratio currently 1.28.</p>
                <p>[DATA] WHALE: Monitoring Mt.Gox wallets...</p>
                <p>[DATA] HEATMAP: Significant bid wall at 61000.</p>
                <p>[DATA] Metrics stream synchronized perfectly.</p>
            </div>
        </div>
    </div>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
