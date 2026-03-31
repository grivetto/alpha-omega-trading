from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ORBITAL COMMAND // NUVOLA</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');

        :root {
            --neon-green: #39ff14;
            --neon-cyan: #00ffff;
            --neon-magenta: #ff00ff;
            --neon-yellow: #fefe33;
            --neon-red: #ff073a;
            --bg-color: #050505;
            --panel-bg: rgba(10, 10, 10, 0.85);
            --grid-color: rgba(0, 255, 255, 0.1);
        }
        
        body {
            background-color: var(--bg-color);
            background-image: 
                linear-gradient(var(--grid-color) 1px, transparent 1px),
                linear-gradient(90deg, var(--grid-color) 1px, transparent 1px);
            background-size: 30px 30px;
            color: var(--neon-green);
            font-family: 'Share Tech Mono', 'Courier New', monospace;
            margin: 0;
            padding: 20px;
            text-transform: uppercase;
            overflow-x: hidden;
        }

        h1 { 
            text-align: center; 
            color: var(--neon-cyan); 
            text-shadow: 0 0 10px var(--neon-cyan), 0 0 20px var(--neon-cyan); 
            font-size: 2.5rem;
            margin-bottom: 5px;
            letter-spacing: 4px;
        }

        .header-status {
            text-align: center;
            font-size: 1.2rem;
            margin-bottom: 30px;
            color: var(--neon-yellow);
            text-shadow: 0 0 5px var(--neon-yellow);
        }

        .container { 
            display: grid; 
            grid-template-columns: 1fr 1fr; 
            gap: 25px; 
            max-width: 1400px; 
            margin: 0 auto; 
        }

        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-cyan);
            padding: 20px;
            box-shadow: inset 0 0 15px rgba(0, 255, 255, 0.1), 0 0 15px rgba(0, 255, 255, 0.2);
            border-radius: 4px;
            position: relative;
            backdrop-filter: blur(5px);
        }
        
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0;
            width: 100%; height: 2px;
            background: var(--neon-cyan);
            box-shadow: 0 0 10px var(--neon-cyan);
        }

        .panel h2 { 
            color: var(--neon-magenta); 
            text-shadow: 0 0 8px var(--neon-magenta); 
            border-bottom: 1px dashed var(--neon-magenta); 
            padding-bottom: 10px; 
            margin-top: 0;
            font-size: 1.5rem;
            display: flex;
            justify-content: space-between;
        }

        .status-online { color: var(--neon-green); text-shadow: 0 0 5px var(--neon-green); font-weight: bold; }
        .status-warn { color: var(--neon-yellow); text-shadow: 0 0 5px var(--neon-yellow); font-weight: bold; }
        .status-danger { color: var(--neon-red); text-shadow: 0 0 5px var(--neon-red); font-weight: bold; }
        
        .blink { animation: blinker 1s linear infinite; }
        .fast-blink { animation: blinker 0.2s linear infinite; }
        @keyframes blinker { 50% { opacity: 0; } }

        table { width: 100%; border-collapse: separate; border-spacing: 0 8px; margin-top: 10px; }
        th, td { padding: 10px; text-align: left; background: rgba(0,0,0,0.5); }
        th { color: var(--neon-cyan); border-bottom: 1px solid var(--neon-cyan); background: transparent; }
        td:first-child { border-left: 2px solid var(--neon-cyan); }
        
        .metric-box {
            border: 1px solid var(--neon-green);
            padding: 15px;
            background: rgba(57, 255, 20, 0.05);
            margin-bottom: 10px;
            box-shadow: inset 0 0 10px rgba(57, 255, 20, 0.1);
        }

        .scanline {
            width: 100%;
            height: 100px;
            z-index: 9999;
            position: absolute;
            pointer-events: none;
            background: linear-gradient(0deg, rgba(0,0,0,0) 0%, rgba(0,255,255,0.2) 50%, rgba(0,0,0,0) 100%);
            opacity: 0.1;
            animation: scanline 8s linear infinite;
        }

        @keyframes scanline {
            0% { top: -100px; }
            100% { top: 100%; }
        }

        .progress-bar {
            width: 100%;
            height: 10px;
            background: #222;
            border: 1px solid #444;
            margin-top: 5px;
        }
        
        .progress-fill {
            height: 100%;
            background: var(--neon-green);
            box-shadow: 0 0 5px var(--neon-green);
            width: 85%;
            animation: pulse-width 2s infinite alternate;
        }
        
        @keyframes pulse-width {
            0% { width: 82%; }
            100% { width: 88%; }
        }
    </style>
</head>
<body>
    <div class="scanline"></div>
    
    <h1>🛰️ ORBITAL COMMAND // NUVOLA 🛰️</h1>
    <div class="header-status">
        [ <span class="blink status-online">SYSTEM ONLINE</span> ] &nbsp;&nbsp;//&nbsp;&nbsp; 
        UPTIME: <span id="uptime">99:99:99</span> &nbsp;&nbsp;//&nbsp;&nbsp;
        ENCRYPTION: AES-256-GCM
    </div>
    
    <div class="header-status" style="color: var(--neon-cyan); font-weight: bold; font-size: 1.5rem; text-shadow: 0 0 10px var(--neon-cyan); margin-top: -15px;">
        ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
    </div>

    <div class="container">
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <h2>
                <span>⚔️ SQUADRE D'ASSALTO</span>
                <span class="status-online" style="font-size: 0.8rem;">[ HFT ENGINE ACTIVE ]</span>
            </h2>
            <table>
                <tr><th>UNITÀ</th><th>STRATEGIA</th><th>STATO</th></tr>
                <tr>
                    <td>🐺 SQUADRA_ALPHA</td>
                    <td>Scalper [Binance]</td>
                    <td class="status-online">ENGAGED <span class="fast-blink" style="font-size: 0.7em">▶</span><br><span style="font-size: 0.8em; color: #888;">[<span id="tps1">78.4</span> TPS]</span></td>
                </tr>
                <tr>
                    <td>🦅 SQUADRA_DELTA</td>
                    <td>Order Flow [Bybit]</td>
                    <td class="status-online">DEPLOYED <span class="fast-blink" style="font-size: 0.7em">▶</span><br><span style="font-size: 0.8em; color: #888;">[LATENCY: 12ms]</span></td>
                </tr>
                <tr>
                    <td>🐍 SQUADRA_GAMMA</td>
                    <td>Pairs [Bitget]</td>
                    <td class="status-online">SYNCED <span class="fast-blink" style="font-size: 0.7em">▶</span><br><span style="font-size: 0.8em; color: #888;">[SPREAD: 0.15%]</span></td>
                </tr>
            </table>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2>
                <span>🔺 PROTOCOLLO TRINITY</span>
                <span class="status-online" style="font-size: 0.8rem;">[ BACKGROUND OPS ]</span>
            </h2>
            <table>
                <tr><th>AGENTE</th><th>RUOLO</th><th>STATO BACKGROUND</th></tr>
                <tr>
                    <td>🎩 Lo Strozzino</td>
                    <td>Funding Arb</td>
                    <td class="status-online">YIELDING<br><span style="font-size: 0.8em; color: var(--neon-cyan);">[APR: 18.4%]</span></td>
                </tr>
                <tr>
                    <td>🧮 Il Contabile</td>
                    <td>Smart DCA</td>
                    <td class="status-online">ACCUMULATING<br><span style="font-size: 0.8em; color: var(--neon-cyan);">[EPOCH 42/100]</span></td>
                </tr>
                <tr>
                    <td>🛡️ L'Angelo Custode</td>
                    <td>MEV [Arbitrum]</td>
                    <td class="status-warn">WATCHING...<br><span style="font-size: 0.8em; color: var(--neon-yellow);">[MEMPOOL SCAN]</span></td>
                </tr>
            </table>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel" style="grid-column: span 2; border-color: var(--neon-green);">
            <h2 style="color: var(--neon-green); border-bottom-color: var(--neon-green);">
                <span>📊 METRICHE DI MERCATO & INTEL</span>
                <span class="status-online" style="font-size: 0.8rem;">[ DATA STREAM: SECURE ]</span>
            </h2>
            
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px;">
                <!-- THE ORACLE -->
                <div class="metric-box">
                    <h3 style="color: var(--neon-cyan); margin-top: 0; text-shadow: 0 0 5px var(--neon-cyan);">🔮 THE ORACLE <span style="font-size: 0.7em; color: #888;">// BINANCE SENTIMENT</span></h3>
                    <p>BTC/USDT : <span class="status-online">BULLISH</span> [89.2% LONG]</p>
                    <div class="progress-bar"><div class="progress-fill" style="width: 89%; background: var(--neon-green); box-shadow: 0 0 5px var(--neon-green);"></div></div>
                    
                    <p style="margin-top: 15px;">ETH/USDT : <span style="color: #aaa;">NEUTRAL</span> [51.4% LONG]</p>
                    <div class="progress-bar"><div class="progress-fill" style="width: 51%; background: #aaa; box-shadow: 0 0 5px #aaa; animation: none;"></div></div>
                    
                    <p style="margin-top: 15px;">SOL/USDT : <span class="status-online">BULLISH</span> [72.8% LONG]</p>
                    <div class="progress-bar"><div class="progress-fill" style="width: 73%; background: var(--neon-green); box-shadow: 0 0 5px var(--neon-green); animation: none;"></div></div>
                </div>

                <!-- WHALE TRACKER -->
                <div class="metric-box" style="border-color: var(--neon-yellow); box-shadow: inset 0 0 10px rgba(254, 254, 51, 0.1);">
                    <h3 style="color: var(--neon-yellow); margin-top: 0; text-shadow: 0 0 5px var(--neon-yellow);">🐋 WHALE TRACKER <span style="font-size: 0.7em; color: #888;">// ON-CHAIN RADAR</span></h3>
                    
                    <div style="margin-bottom: 12px; border-left: 3px solid var(--neon-red); padding-left: 10px;">
                        <span class="status-danger blink">🚨 ALERT:</span> 5,000 BTC moved to Binance
                        <div style="font-size: 0.8em; color: #888;">T-MINUS: 12m ago | TX: 0x8f...3a9c</div>
                    </div>
                    
                    <div style="margin-bottom: 12px; border-left: 3px solid var(--neon-green); padding-left: 10px;">
                        <span class="status-online">🟢 FLOW:</span> Net Inflow +$45M (USDC)
                        <div style="font-size: 0.8em; color: #888;">NETWORK: Arbitrum | T-MINUS: 2h ago</div>
                    </div>
                    
                    <div style="border-left: 3px solid var(--neon-yellow); padding-left: 10px;">
                        <span class="status-warn">⚠️ DANGER:</span> High Leverage Longs
                        <div style="font-size: 0.8em; color: #888;">STATUS: Liquidations Imminent on Bybit</div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        // Fake dynamic data for tactical effect
        setInterval(() => {
            document.getElementById('tps1').innerText = (75 + Math.random() * 10).toFixed(1);
        }, 800);

        // Uptime counter
        let seconds = 0;
        setInterval(() => {
            seconds++;
            let hrs = Math.floor(seconds / 3600);
            let mins = Math.floor((seconds % 3600) / 60);
            let secs = seconds % 60;
            document.getElementById('uptime').innerText = 
                `${hrs.toString().padStart(2, '0')}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
        }, 1000);
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    # Running on standard port 5000, accessible externally
    app.run(host='0.0.0.0', port=5000)
