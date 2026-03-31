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
            --neon-primary: #0ff;
            --neon-secondary: #f0f;
            --neon-success: #0f0;
            --neon-danger: #f00;
            --neon-warning: #ff0;
            --grid-color: rgba(0, 255, 255, 0.1);
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
            background-size: 20px 20px;
            overflow-x: hidden;
            text-transform: uppercase;
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
            background: linear-gradient(
                to bottom,
                rgba(18, 16, 16, 0) 50%,
                rgba(0, 0, 0, 0.25) 50%
            );
            background-size: 100% 4px;
            z-index: 50;
            pointer-events: none;
        }

        h1 {
            text-align: center;
            font-size: 2.5rem;
            color: #fff;
            text-shadow: 0 0 10px var(--neon-primary), 0 0 20px var(--neon-primary), 0 0 40px var(--neon-primary);
            margin-bottom: 5px;
            letter-spacing: 4px;
        }

        .subtitle {
            text-align: center;
            color: var(--neon-secondary);
            font-size: 1.2rem;
            margin-bottom: 40px;
            text-shadow: 0 0 5px var(--neon-secondary);
            letter-spacing: 2px;
        }

        .container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 25px;
            max-width: 1400px;
            margin: 0 auto;
        }

        .panel {
            background: rgba(0, 20, 20, 0.8);
            border: 1px solid var(--neon-primary);
            box-shadow: 0 0 15px rgba(0, 255, 255, 0.2), inset 0 0 10px rgba(0, 255, 255, 0.1);
            padding: 20px;
            position: relative;
            overflow: hidden;
        }

        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0;
            width: 100%; height: 2px;
            background: var(--neon-primary);
            box-shadow: 0 0 10px var(--neon-primary);
        }

        .panel h2 {
            font-size: 1.5rem;
            color: var(--neon-success);
            text-shadow: 0 0 8px var(--neon-success);
            border-bottom: 1px dashed var(--neon-success);
            padding-bottom: 10px;
            margin-top: 0;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 10px 0;
            border-bottom: 1px solid rgba(0, 255, 255, 0.2);
            font-size: 1.1rem;
        }

        .row:last-child {
            border-bottom: none;
        }

        .label {
            color: #fff;
            text-shadow: 0 0 4px rgba(255,255,255,0.5);
        }

        .status {
            font-weight: bold;
            text-shadow: 0 0 8px currentColor;
        }

        .s-ok { color: var(--neon-success); }
        .s-warn { color: var(--neon-warning); }
        .s-err { color: var(--neon-danger); }
        .s-info { color: var(--neon-primary); }
        .s-purple { color: var(--neon-secondary); }

        .blink {
            animation: blinker 1.5s linear infinite;
        }

        @keyframes blinker {
            50% { opacity: 0.3; }
        }

        .terminal-box {
            background: #000;
            border: 1px solid var(--neon-primary);
            color: var(--neon-success);
            padding: 10px;
            height: 120px;
            overflow-y: hidden;
            font-size: 0.9rem;
            margin-top: 15px;
            position: relative;
            box-shadow: inset 0 0 10px rgba(0,255,0,0.2);
        }

        .terminal-box p { margin: 2px 0; }
        
        .pulse-bg {
            animation: bgPulse 4s infinite alternate;
        }
        
        @keyframes bgPulse {
            0% { box-shadow: 0 0 10px rgba(0, 255, 255, 0.1), inset 0 0 10px rgba(0, 255, 255, 0.05); }
            100% { box-shadow: 0 0 25px rgba(0, 255, 255, 0.3), inset 0 0 20px rgba(0, 255, 255, 0.15); }
        }

        .trinity-core {
            border-color: var(--neon-secondary);
            box-shadow: 0 0 15px rgba(255, 0, 255, 0.2), inset 0 0 10px rgba(255, 0, 255, 0.1);
        }
        .trinity-core::before { background: var(--neon-secondary); box-shadow: 0 0 10px var(--neon-secondary); }
        .trinity-core h2 { color: var(--neon-secondary); text-shadow: 0 0 8px var(--neon-secondary); border-bottom-color: var(--neon-secondary); }

        /* Progress bars */
        .bar-bg {
            background: rgba(255,255,255,0.1);
            height: 8px;
            width: 100%;
            margin-top: 5px;
            border-radius: 4px;
            overflow: hidden;
        }
        .bar-fill {
            height: 100%;
            background: var(--neon-primary);
            box-shadow: 0 0 8px var(--neon-primary);
        }
    </style>
</head>
<body>
    <h1>[ NUVOLA ORBITAL COMMAND ]</h1>
    <div class="subtitle blink">SYSTEM STATUS: NOMINAL // ALL HFT NODES CONNECTED // DEFCON 5</div>
    <div style="text-align: center; color: #0f0; font-size: 1.2rem; margin-bottom: 30px; text-shadow: 0 0 8px #0f0; font-weight: bold; border: 1px dashed #0f0; padding: 10px; width: fit-content; margin-left: auto; margin-right: auto; box-shadow: inset 0 0 10px rgba(0, 255, 0, 0.2);">
        ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
    </div>

    <div class="container">
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel pulse-bg">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <div class="row">
                <span class="label">🐺 SQUADRA_ALPHA <span style="font-size:0.8em; color:#888;">[BINANCE SCALPER]</span></span>
                <span class="status s-ok blink">[ ENGAGED ]</span>
            </div>
            <div class="row">
                <span class="label">⚡ SQUADRA_DELTA <span style="font-size:0.8em; color:#888;">[ORDER FLOW]</span></span>
                <span class="status s-info">[ ACTIVE ]</span>
            </div>
            <div class="row">
                <span class="label">⚖️ SQUADRA_GAMMA <span style="font-size:0.8em; color:#888;">[BITGET PAIRS]</span></span>
                <span class="status s-warn">[ ARBITRAGING ]</span>
            </div>
            <div class="terminal-box">
                <p>> [SYS] ALPHA: Executing trailing buy BTC/USDT @ 62450.50...</p>
                <p>> [SYS] DELTA: High latency detected on tick stream. Adjusting quotes.</p>
                <p>> [SYS] GAMMA: Spread reached 0.18%. Awaiting 0.20% target.</p>
                <p>> [SYS] ALPHA: 0.5 BTC filled. Placing sell limit +0.15%.</p>
                <p>> [SYS] ALL TEAMS: Sync heartbeat OK.</p>
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel trinity-core pulse-bg">
            <h2>🔺 PROTOCOLLO TRINITY</h2>
            <div class="row">
                <span class="label">🕴️ Lo Strozzino <span style="font-size:0.8em; color:#888;">[FUNDING ARB]</span></span>
                <span class="status s-purple blink">[ HARVESTING ]</span>
            </div>
            <div class="row">
                <span class="label">🧮 Il Contabile <span style="font-size:0.8em; color:#888;">[DCA/VAULT]</span></span>
                <span class="status s-info">[ ACCUMULATING ]</span>
            </div>
            <div class="row">
                <span class="label">🛡️ L'Angelo Custode <span style="font-size:0.8em; color:#888;">[MEV ARBITRUM]</span></span>
                <span class="status s-ok">[ PROTECTING ]</span>
            </div>
            <div class="terminal-box" style="color: var(--neon-secondary); border-color: var(--neon-secondary); box-shadow: inset 0 0 10px rgba(255,0,255,0.2);">
                <p>> [TRINITY] STROZZINO: Short PERP, Long SPOT (Est. APR: 19.4%)</p>
                <p>> [TRINITY] CONTABILE: BTC Vault balance +0.0125 BTC.</p>
                <p>> [TRINITY] ANGELO: Arbitrum mempool scan active. 0 threats.</p>
                <p>> [TRINITY] Background daemons running gracefully.</p>
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel pulse-bg">
            <h2>📊 METRICHE DI MERCATO</h2>
            <div class="row">
                <span class="label">👁️ THE ORACLE <span style="font-size:0.8em; color:#888;">[BINANCE SENTIMENT]</span></span>
                <span class="status s-warn">GREED (74)</span>
            </div>
            <div class="bar-bg"><div class="bar-fill" style="width: 74%; background: var(--neon-warning); box-shadow: 0 0 8px var(--neon-warning);"></div></div>
            
            <div class="row" style="margin-top: 10px;">
                <span class="label">🐋 WHALE TRACKER <span style="font-size:0.8em; color:#888;">[ON-CHAIN]</span></span>
                <span class="status s-err blink">ALERT: 8000 BTC -> CEX</span>
            </div>
            
            <div class="row" style="margin-top: 10px;">
                <span class="label">🌊 LIQUIDITY HEATMAP</span>
                <span class="status s-info">CONCENTRATED @ $65,500</span>
            </div>
            
            <div class="row" style="margin-top: 10px;">
                <span class="label">🔥 NETWORK GAS (ETH)</span>
                <span class="status s-ok">14 GWEI</span>
            </div>
            
            <div class="terminal-box">
                <p>> [DATA] ORACLE: Aggregating orderbook depth (L2)...</p>
                <p>> [DATA] ORACLE: L/S Ratio currently 1.28.</p>
                <p>> [DATA] WHALE: Monitoring Mt.Gox wallets...</p>
                <p>> [DATA] Metrics stream synchronized.</p>
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