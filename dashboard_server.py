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
            --neon-green: #39ff14;
            --neon-blue: #00f3ff;
            --neon-red: #ff003c;
            --neon-purple: #bc13fe;
            --neon-yellow: #fcee0a;
            --bg-dark: #080808;
            --panel-bg: rgba(12, 16, 24, 0.85);
        }
        
        * {
            box-sizing: border-box;
        }

        body {
            background-color: var(--bg-dark);
            color: var(--neon-green);
            font-family: 'Share Tech Mono', monospace;
            margin: 0;
            padding: 20px;
            background-image:
                linear-gradient(rgba(0, 255, 255, 0.03) 1px, transparent 1px),
                linear-gradient(90deg, rgba(0, 255, 255, 0.03) 1px, transparent 1px);
            background-size: 30px 30px;
            overflow-x: hidden;
            text-transform: uppercase;
        }

        h1, h2, h3 {
            margin-top: 0;
            text-shadow: 0 0 5px currentColor;
        }

        .header {
            text-align: center;
            border-bottom: 2px solid var(--neon-blue);
            padding-bottom: 20px;
            margin-bottom: 30px;
            color: var(--neon-blue);
            position: relative;
        }
        
        .header h1 {
            font-size: 2.5em;
            letter-spacing: 4px;
            animation: glitch 3s infinite;
        }

        .trinity-banner {
            color: var(--neon-yellow);
            font-weight: bold;
            border: 1px solid var(--neon-yellow);
            padding: 10px 20px;
            display: inline-block;
            box-shadow: 0 0 15px rgba(252, 238, 10, 0.4) inset, 0 0 15px rgba(252, 238, 10, 0.4);
            background: rgba(252, 238, 10, 0.1);
            letter-spacing: 2px;
            animation: pulse 2s infinite;
        }

        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(380px, 1fr));
            gap: 25px;
        }

        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-green);
            border-radius: 4px;
            padding: 20px;
            box-shadow: 0 0 15px rgba(57, 255, 20, 0.15) inset;
            position: relative;
            backdrop-filter: blur(5px);
            transition: all 0.3s ease;
        }

        .panel:hover {
            box-shadow: 0 0 20px rgba(57, 255, 20, 0.3) inset, 0 0 10px rgba(57, 255, 20, 0.5);
            transform: translateY(-2px);
        }

        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; height: 3px;
            background: var(--neon-green);
            box-shadow: 0 0 15px var(--neon-green);
        }

        .panel.hft { border-color: var(--neon-red); }
        .panel.hft::before { background: var(--neon-red); box-shadow: 0 0 15px var(--neon-red); }
        .panel.hft:hover { box-shadow: 0 0 20px rgba(255, 0, 60, 0.2) inset, 0 0 10px rgba(255, 0, 60, 0.5); }

        .panel.trinity { border-color: var(--neon-purple); }
        .panel.trinity::before { background: var(--neon-purple); box-shadow: 0 0 15px var(--neon-purple); }
        .panel.trinity:hover { box-shadow: 0 0 20px rgba(188, 19, 254, 0.2) inset, 0 0 10px rgba(188, 19, 254, 0.5); }

        .panel.metrics { border-color: var(--neon-blue); }
        .panel.metrics::before { background: var(--neon-blue); box-shadow: 0 0 15px var(--neon-blue); }
        .panel.metrics:hover { box-shadow: 0 0 20px rgba(0, 243, 255, 0.2) inset, 0 0 10px rgba(0, 243, 255, 0.5); }

        .status-online { color: var(--neon-green); text-shadow: 0 0 8px var(--neon-green); font-weight: bold; }
        .status-standby { color: var(--neon-yellow); text-shadow: 0 0 8px var(--neon-yellow); font-weight: bold; }
        .status-alert { color: var(--neon-red); text-shadow: 0 0 8px var(--neon-red); font-weight: bold; animation: blink 1s infinite; }

        .squad-item, .trinity-item, .metric-item {
            margin: 15px 0;
            padding: 15px;
            background: rgba(0, 0, 0, 0.4);
            border-left: 3px solid #555;
        }

        .panel.hft .squad-item { border-left-color: var(--neon-red); }
        .panel.trinity .trinity-item { border-left-color: var(--neon-purple); }
        .panel.metrics .metric-item { border-left-color: var(--neon-blue); }

        .metric-bar-bg {
            height: 12px;
            background: #111;
            margin-top: 8px;
            border-radius: 2px;
            border: 1px solid #333;
            overflow: hidden;
            position: relative;
        }

        .metric-fill {
            height: 100%;
            background: var(--neon-blue);
            box-shadow: 0 0 10px currentColor;
            transition: width 1s ease-in-out;
        }

        .details-row {
            display: flex;
            justify-content: space-between;
            font-size: 0.85em;
            color: #aaa;
            margin-top: 5px;
        }

        /* Animations */
        @keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }
        @keyframes pulse { 0% { opacity: 0.8; } 50% { opacity: 1; text-shadow: 0 0 20px var(--neon-yellow); } 100% { opacity: 0.8; } }
        @keyframes scanline { 0% { transform: translateY(-100vh); } 100% { transform: translateY(100vh); } }
        @keyframes glitch {
            0% { text-shadow: 0.05em 0 0 var(--neon-red), -0.05em -0.025em 0 var(--neon-blue), -0.025em 0.05em 0 var(--neon-green); }
            14% { text-shadow: 0.05em 0 0 var(--neon-red), -0.05em -0.025em 0 var(--neon-blue), -0.025em 0.05em 0 var(--neon-green); }
            15% { text-shadow: -0.05em -0.025em 0 var(--neon-red), 0.025em 0.025em 0 var(--neon-blue), -0.05em -0.05em 0 var(--neon-green); }
            49% { text-shadow: -0.05em -0.025em 0 var(--neon-red), 0.025em 0.025em 0 var(--neon-blue), -0.05em -0.05em 0 var(--neon-green); }
            50% { text-shadow: 0.025em 0.05em 0 var(--neon-red), 0.05em 0 0 var(--neon-blue), 0 -0.05em 0 var(--neon-green); }
            99% { text-shadow: 0.025em 0.05em 0 var(--neon-red), 0.05em 0 0 var(--neon-blue), 0 -0.05em 0 var(--neon-green); }
            100% { text-shadow: -0.025em 0 0 var(--neon-red), -0.025em -0.025em 0 var(--neon-blue), -0.025em -0.05em 0 var(--neon-green); }
        }

        .scanline {
            position: fixed;
            top: 0; left: 0; width: 100%; height: 8px;
            background: rgba(0, 243, 255, 0.15);
            box-shadow: 0 0 20px rgba(0, 243, 255, 0.4);
            animation: scanline 8s linear infinite;
            pointer-events: none;
            z-index: 9999;
        }

        .footer {
            text-align: center;
            margin-top: 50px;
            padding: 20px;
            border-top: 1px dashed #333;
            color: #555;
            font-size: 0.8em;
            letter-spacing: 1px;
        }
        
        .sys-log {
            font-size: 0.8em;
            color: #777;
            margin-top: 10px;
        }
    </style>
</head>
<body>
    <div class="scanline"></div>
    
    <div class="header">
        <h1>🛰️ ORBITAL COMMAND // NUVOLA</h1>
        <p>SYSTEM STATUS: <span class="status-online">OPTIMAL</span> &nbsp;|&nbsp; UPTIME: 99.99% &nbsp;|&nbsp; SEC-LEVEL: OMEGA</p>
        <div class="trinity-banner">
            ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
        </div>
        <div class="sys-log">Last Ping: 14:53 UTC | Node: NUVOLA-01 | Latency: 8ms</div>
    </div>

    <div class="grid">
        <!-- 1. SQUADRE D'ASSALTO (HFT) -->
        <div class="panel hft">
            <h2 style="color: var(--neon-red);">⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            
            <div class="squad-item">
                <div style="font-size: 1.1em; color: white;">🎯 SQUADRA_ALPHA <span style="font-size: 0.7em; color: #888;">[BINANCE SCALPER]</span></div>
                <div style="margin: 5px 0;">STATE: <span class="status-online">ENGAGING TARGETS</span></div>
                <div class="details-row">
                    <span>Win Rate: 68.4%</span>
                    <span>Exec Time: 12ms</span>
                </div>
                <div class="metric-bar-bg"><div class="metric-fill" style="width: 68%; background: var(--neon-red);"></div></div>
            </div>

            <div class="squad-item">
                <div style="font-size: 1.1em; color: white;">🌊 SQUADRA_DELTA <span style="font-size: 0.7em; color: #888;">[ORDER FLOW]</span></div>
                <div style="margin: 5px 0;">STATE: <span class="status-standby">MONITORING LOB</span></div>
                <div class="details-row">
                    <span>Imbalance: +4.2% (BULL)</span>
                    <span>Depth: 150 levels</span>
                </div>
                <div class="metric-bar-bg"><div class="metric-fill" style="width: 54%; background: var(--neon-yellow);"></div></div>
            </div>

            <div class="squad-item">
                <div style="font-size: 1.1em; color: white;">⚖️ SQUADRA_GAMMA <span style="font-size: 0.7em; color: #888;">[BITGET PAIRS]</span></div>
                <div style="margin: 5px 0;">STATE: <span class="status-online">ARBITRAGE ACTIVE</span></div>
                <div class="details-row">
                    <span>Spread: 0.15%</span>
                    <span>Vol: $1.2M/24h</span>
                </div>
                <div class="metric-bar-bg"><div class="metric-fill" style="width: 80%; background: var(--neon-red);"></div></div>
            </div>
        </div>

        <!-- 2. PROTOCOLLO TRINITY -->
        <div class="panel trinity">
            <h2 style="color: var(--neon-purple);">🔮 PROTOCOLLO TRINITY</h2>
            
            <div class="trinity-item">
                <div style="font-size: 1.1em; color: white;">🦇 Lo Strozzino <span style="font-size: 0.7em; color: #888;">[FUNDING ARB]</span></div>
                <div style="margin: 5px 0;">STATE: <span class="status-online">EXTRACTING YIELD</span></div>
                <div class="details-row">
                    <span>Target APY: 18.5%</span>
                    <span>Delta: Neutral</span>
                </div>
            </div>

            <div class="trinity-item">
                <div style="font-size: 1.1em; color: white;">💼 Il Contabile <span style="font-size: 0.7em; color: #888;">[DCA ENGINE]</span></div>
                <div style="margin: 5px 0;">STATE: <span class="status-online">ACCUMULATING</span></div>
                <div class="details-row">
                    <span>Asset: BTC/ETH</span>
                    <span>Next Exec: 15:00 UTC</span>
                </div>
            </div>

            <div class="trinity-item">
                <div style="font-size: 1.1em; color: white;">🛡️ L'Angelo Custode <span style="font-size: 0.7em; color: #888;">[MEV ARBITRUM]</span></div>
                <div style="margin: 5px 0;">STATE: <span class="status-standby">PATROLLING MEMPOOL</span></div>
                <div class="details-row">
                    <span>Flashbots: Ready</span>
                    <span>Gas Bid: Dynamic</span>
                </div>
            </div>
            
            <div style="text-align: center; margin-top: 15px;">
                <span class="status-online" style="font-size: 0.8em;">[ TRINITY BACKGROUND DAEMONS RUNNING ]</span>
            </div>
        </div>

        <!-- 3. METRICHE DI MERCATO -->
        <div class="panel metrics">
            <h2 style="color: var(--neon-blue);">📊 MARKET METRICS</h2>
            
            <div class="metric-item">
                <div style="font-size: 1.1em; color: white;">👁️ THE ORACLE <span style="font-size: 0.7em; color: #888;">[BINANCE SENTIMENT]</span></div>
                <div style="margin: 5px 0;">FEAR/GREED INDEX: <span style="color: var(--neon-green);">65 (GREED)</span></div>
                <div class="metric-bar-bg"><div class="metric-fill" style="width: 65%; background: var(--neon-green);"></div></div>
            </div>

            <div class="metric-item">
                <div style="font-size: 1.1em; color: white;">🐋 WHALE TRACKER <span style="font-size: 0.7em; color: #888;">[ON-CHAIN ALERTS]</span></div>
                <div style="margin: 5px 0;">LARGE TX VOL (24H): <span class="status-alert">ELEVATED !!</span></div>
                <div class="metric-bar-bg"><div class="metric-fill" style="width: 90%; background: var(--neon-red);"></div></div>
            </div>

            <div class="metric-item">
                <div style="font-size: 1.1em; color: white;">💧 GLOBAL LIQUIDITY <span style="font-size: 0.7em; color: #888;">[STABLECOIN FLOW]</span></div>
                <div style="margin: 5px 0;">NET FLOW: <span style="color: var(--neon-blue);">+$450M INFLOW</span></div>
                <div class="metric-bar-bg"><div class="metric-fill" style="width: 75%; background: var(--neon-blue);"></div></div>
            </div>
        </div>
    </div>

    <div class="footer">
        <div>[ &copy; 2026 QUANTITATIVE ASSAULT PROTOCOL ]</div>
        <div style="margin-top: 5px; color: #444;">UNAUTHORIZED ACCESS WILL RESULT IN IMMEDIATE LIQUIDATION</div>
    </div>

    <script>
        // Fake dynamic updates for metrics
        setInterval(() => {
            const bars = document.querySelectorAll('.metric-fill');
            bars.forEach(bar => {
                let currentWidth = parseFloat(bar.style.width);
                let fluctuation = (Math.random() * 4) - 2; // -2 to +2
                let newWidth = Math.max(10, Math.min(100, currentWidth + fluctuation));
                bar.style.width = newWidth + '%';
            });
        }, 3000);
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
