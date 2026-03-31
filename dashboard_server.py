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
    <title>ORBITAL COMMAND | NUVOLA</title>
    <style>
        :root {
            --neon-blue: #00f3ff;
            --neon-purple: #bc13fe;
            --neon-red: #ff003c;
            --neon-green: #00ff66;
            --bg-dark: #050505;
            --bg-panel: rgba(10, 10, 15, 0.85);
        }
        
        body {
            background-color: var(--bg-dark);
            color: var(--neon-blue);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            background-image: 
                linear-gradient(rgba(0, 243, 255, 0.03) 1px, transparent 1px),
                linear-gradient(90deg, rgba(0, 243, 255, 0.03) 1px, transparent 1px);
            background-size: 20px 20px;
            overflow-x: hidden;
        }

        h1, h2, h3 {
            text-transform: uppercase;
            letter-spacing: 2px;
            margin-top: 0;
        }

        h1 {
            text-align: center;
            color: var(--neon-purple);
            text-shadow: 0 0 10px var(--neon-purple), 0 0 20px var(--neon-purple);
            border-bottom: 2px solid var(--neon-purple);
            padding-bottom: 10px;
            margin-bottom: 30px;
        }
        
        h2 {
            font-size: 1.2rem;
            border-bottom: 1px dashed var(--neon-blue);
            padding-bottom: 5px;
        }

        .container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            max-width: 1400px;
            margin: 0 auto;
        }

        .panel {
            background: var(--bg-panel);
            border: 1px solid var(--neon-blue);
            border-radius: 5px;
            padding: 15px;
            box-shadow: 0 0 10px rgba(0, 243, 255, 0.1), inset 0 0 10px rgba(0, 243, 255, 0.05);
            position: relative;
            overflow: hidden;
        }
        
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0;
            height: 2px;
            background: var(--neon-blue);
            box-shadow: 0 0 10px var(--neon-blue);
        }

        .status-indicator {
            display: inline-block;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            margin-right: 10px;
            box-shadow: 0 0 5px currentColor;
        }

        .status-online { color: var(--neon-green); background-color: var(--neon-green); animation: pulse 2s infinite; }
        .status-offline { color: var(--neon-red); background-color: var(--neon-red); }
        .status-standby { color: #ffaa00; background-color: #ffaa00; }

        @keyframes pulse {
            0% { opacity: 0.5; box-shadow: 0 0 2px currentColor; }
            50% { opacity: 1; box-shadow: 0 0 10px currentColor; }
            100% { opacity: 0.5; box-shadow: 0 0 2px currentColor; }
        }

        .team, .protocol {
            margin-bottom: 15px;
            padding: 10px;
            background: rgba(0, 243, 255, 0.05);
            border-left: 3px solid var(--neon-blue);
            transition: all 0.3s ease;
        }
        
        .team:hover, .protocol:hover {
            background: rgba(0, 243, 255, 0.1);
            transform: translateX(5px);
            border-color: var(--neon-purple);
        }

        .metric-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
            font-size: 0.9rem;
        }

        .metric-box {
            background: rgba(0,0,0,0.5);
            border: 1px solid rgba(0, 243, 255, 0.3);
            padding: 10px;
            text-align: center;
        }

        .metric-value {
            font-size: 1.5rem;
            color: var(--neon-green);
            font-weight: bold;
            text-shadow: 0 0 5px var(--neon-green);
            margin-top: 5px;
        }

        .red-value {
            color: var(--neon-red);
            text-shadow: 0 0 5px var(--neon-red);
        }

        .glitch {
            position: relative;
        }

        .glitch::before, .glitch::after {
            content: attr(data-text);
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: var(--bg-dark);
        }
        
        .glitch::before {
            left: 2px;
            text-shadow: -1px 0 red;
            clip: rect(44px, 450px, 56px, 0);
            animation: glitch-anim 5s infinite linear alternate-reverse;
        }

        .glitch::after {
            left: -2px;
            text-shadow: -1px 0 blue;
            clip: rect(44px, 450px, 56px, 0);
            animation: glitch-anim2 5s infinite linear alternate-reverse;
        }

        @keyframes glitch-anim {
            0% { clip: rect(21px, 9999px, 86px, 0); }
            5% { clip: rect(61px, 9999px, 80px, 0); }
            10% { clip: rect(43px, 9999px, 33px, 0); }
            15% { clip: rect(52px, 9999px, 98px, 0); }
            20% { clip: rect(29px, 9999px, 20px, 0); }
            25% { clip: rect(66px, 9999px, 81px, 0); }
            30% { clip: rect(72px, 9999px, 45px, 0); }
            35% { clip: rect(96px, 9999px, 91px, 0); }
            40% { clip: rect(32px, 9999px, 12px, 0); }
            45% { clip: rect(78px, 9999px, 63px, 0); }
            50% { clip: rect(25px, 9999px, 35px, 0); }
            55% { clip: rect(48px, 9999px, 50px, 0); }
            60% { clip: rect(89px, 9999px, 56px, 0); }
            65% { clip: rect(10px, 9999px, 71px, 0); }
            70% { clip: rect(17px, 9999px, 89px, 0); }
            75% { clip: rect(58px, 9999px, 19px, 0); }
            80% { clip: rect(85px, 9999px, 94px, 0); }
            85% { clip: rect(11px, 9999px, 68px, 0); }
            90% { clip: rect(7px, 9999px, 77px, 0); }
            95% { clip: rect(41px, 9999px, 30px, 0); }
            100% { clip: rect(54px, 9999px, 28px, 0); }
        }

        .footer {
            margin-top: 40px;
            text-align: center;
            font-size: 0.8rem;
            color: rgba(0, 243, 255, 0.5);
            border-top: 1px solid rgba(0, 243, 255, 0.2);
            padding-top: 10px;
        }
        
        .log-terminal {
            height: 150px;
            overflow-y: hidden;
            background: #000;
            padding: 10px;
            font-size: 0.8rem;
            color: #0f0;
            border: 1px inset #333;
        }
    </style>
</head>
<body>

    <h1 class="glitch" data-text="🛰️ ORBITAL COMMAND | NUVOLA CORE 🛰️">🛰️ ORBITAL COMMAND | NUVOLA CORE 🛰️</h1>

    <div style="text-align: center; margin-bottom: 20px; font-weight: bold; color: var(--neon-green); font-size: 1.2rem; background: rgba(0, 255, 102, 0.1); padding: 10px; border: 1px dashed var(--neon-green); box-shadow: 0 0 10px rgba(0, 255, 102, 0.2);">
        ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
    </div>

    <div class="container">
        
        <!-- SQUADRE D'ASSALTO -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            
            <div class="team">
                <div><span class="status-indicator status-online"></span> <b>SQUADRA_ALPHA</b> [Scalper]</div>
                <div style="font-size: 0.85em; color: #aaa; margin-top: 5px;">Target: Binance | Latency: 12ms | Win Rate: 68.4%</div>
            </div>
            
            <div class="team">
                <div><span class="status-indicator status-online"></span> <b>SQUADRA_DELTA</b> [Order Flow]</div>
                <div style="font-size: 0.85em; color: #aaa; margin-top: 5px;">Target: Bybit/Binance | Spoof Detect: Active</div>
            </div>

            <div class="team">
                <div><span class="status-indicator status-standby"></span> <b>SQUADRA_GAMMA</b> [Pairs Trading]</div>
                <div style="font-size: 0.85em; color: #aaa; margin-top: 5px;">Target: Bitget | Z-Score: 1.4 (Waiting > 2.0)</div>
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2>🔺 PROTOCOLLO TRINITY</h2>
            
            <div class="protocol">
                <div><span class="status-indicator status-online"></span> <b>Lo Strozzino</b> (Funding Arb)</div>
                <div style="font-size: 0.85em; color: #aaa; margin-top: 5px;">Yield: +14.2% APR | Margin Risk: Low</div>
            </div>

            <div class="protocol">
                <div><span class="status-indicator status-online"></span> <b>Il Contabile</b> (DCA & Rebalance)</div>
                <div style="font-size: 0.85em; color: #aaa; margin-top: 5px;">Portfolio Sync: 100% | Next Buy: 4h 12m</div>
            </div>

            <div class="protocol">
                <div><span class="status-indicator status-online"></span> <b>L'Angelo Custode</b> (MEV)</div>
                <div style="font-size: 0.85em; color: #aaa; margin-top: 5px;">Chain: Arbitrum | Mempool Scanned: 1.2M tx</div>
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <h2>👁️ METRICHE DI MERCATO</h2>
            
            <div class="metric-grid">
                <div class="metric-box">
                    <div>THE ORACLE (Sentiment)</div>
                    <div class="metric-value">BULL-84</div>
                </div>
                <div class="metric-box">
                    <div>WHALE TRACKER (Netflow)</div>
                    <div class="metric-value">+$42M</div>
                </div>
                <div class="metric-box">
                    <div>VOLATILITY INDEX</div>
                    <div class="metric-value red-value">HIGH</div>
                </div>
                <div class="metric-box">
                    <div>GLOBAL LIQUIDITY</div>
                    <div class="metric-value">STABLE</div>
                </div>
            </div>
            
            <h3 style="margin-top: 20px; font-size: 1rem;">SYSTEM LOGS</h3>
            <div class="log-terminal">
                > [SYS] Initializing Orbital Command... OK<br>
                > [NET] Connecting to Binance WebSocket... OK<br>
                > [ALPHA] Executed long BTCUSDT @ 68,421.50... WIN (+0.12%)<br>
                > [ORACLE] Alert: Whale transfer 5000 BTC to Coinbase.<br>
                > [MEV] Snipe attempt on Arbitrum... FAILED (Outbid).<br>
                > [SYS] All systems nominal. Awaiting orders.
            </div>
        </div>

    </div>

    <div class="footer">
        NUVOLA CLUSTER // TERMINAL v3.1.4 // SECURE CONNECTION ENABLED
    </div>

    <script>
        // Simple random metric updates for visual effect
        setInterval(() => {
            const oracleVals = ['BULL-84', 'BULL-82', 'NEUTRAL', 'BEAR-12'];
            const nets = ['+$42M', '+$12M', '-$5M', '+$89M'];
            document.querySelectorAll('.metric-value')[0].innerText = oracleVals[Math.floor(Math.random()*oracleVals.length)];
            document.querySelectorAll('.metric-value')[1].innerText = nets[Math.floor(Math.random()*nets.length)];
        }, 5000);
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
# TRINITY PROTOCOL PHASE 2: ONLINE
