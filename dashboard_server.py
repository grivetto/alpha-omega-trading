from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ORBITAL COMMAND // NUVOLA NET</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&family=VT323&display=swap');
        
        :root {
            --neon-green: #0f0;
            --neon-red: #f00;
            --neon-blue: #0ff;
            --neon-purple: #f0f;
            --neon-yellow: #ff0;
            --bg-color: #050505;
            --panel-bg: rgba(10, 20, 10, 0.85);
            --grid-line: rgba(0, 255, 0, 0.1);
        }
        
        body {
            background-color: var(--bg-color);
            color: var(--neon-green);
            font-family: 'Orbitron', sans-serif;
            margin: 0;
            padding: 20px;
            background-image: 
                linear-gradient(var(--grid-line) 1px, transparent 1px),
                linear-gradient(90deg, var(--grid-line) 1px, transparent 1px);
            background-size: 30px 30px;
            overflow-x: hidden;
            text-shadow: 0 0 5px var(--neon-green);
        }

        /* CRT OVERLAY */
        body::after {
            content: " ";
            display: block;
            position: fixed;
            top: 0; left: 0; bottom: 0; right: 0;
            background: rgba(18, 16, 16, 0.1);
            opacity: 0;
            z-index: 2;
            pointer-events: none;
            animation: flicker 0.15s infinite;
        }

        .scanline {
            width: 100%; height: 100px; z-index: 9999; position: fixed;
            background: linear-gradient(0deg, transparent 0%, rgba(0,255,0,0.2) 50%, transparent 100%);
            opacity: 0.1; animation: scanline 8s linear infinite; pointer-events: none;
        }

        @keyframes scanline { 0% { top: -100px; } 100% { top: 100vh; } }
        @keyframes flicker { 0% { opacity: 0.05; } 50% { opacity: 0.1; } 100% { opacity: 0.05; } }

        h1, h2, h3 { margin: 0; padding: 0; text-transform: uppercase; }

        .header-container {
            border: 2px solid var(--neon-green);
            padding: 20px; margin-bottom: 30px; text-align: center;
            box-shadow: 0 0 15px var(--neon-green), inset 0 0 15px var(--neon-green);
            background: rgba(0, 255, 0, 0.05);
            position: relative;
        }
        
        .title {
            font-size: 3em; font-weight: 900; letter-spacing: 5px;
            animation: glitch 2s infinite; margin-bottom: 10px;
        }

        @keyframes glitch {
            0% { text-shadow: 2px 0 var(--neon-red), -2px 0 var(--neon-blue); }
            5% { text-shadow: -2px 0 var(--neon-red), 2px 0 var(--neon-blue); }
            10% { text-shadow: 2px 0 var(--neon-red), -2px 0 var(--neon-blue); }
            100% { text-shadow: 0 0 10px var(--neon-green); }
        }

        .sys-info { font-family: 'VT323', monospace; font-size: 1.5em; color: var(--neon-blue); }

        .grid {
            display: grid; grid-template-columns: repeat(auto-fit, minmax(450px, 1fr)); gap: 30px;
        }

        .panel {
            background: var(--panel-bg);
            border: 1px solid currentColor;
            padding: 20px;
            box-shadow: 0 0 20px rgba(0,255,0,0.2);
            position: relative;
            backdrop-filter: blur(5px);
        }
        
        .panel::before {
            content: ''; position: absolute; top: 0; left: 0; width: 100%; height: 4px;
            background: currentColor; box-shadow: 0 0 10px currentColor;
        }

        .p-hft { color: var(--neon-green); }
        .p-trinity { color: var(--neon-purple); }
        .p-metrics { color: var(--neon-blue); }

        .panel-title {
            font-size: 1.5em; margin-bottom: 20px; border-bottom: 1px dashed currentColor; padding-bottom: 10px;
            display: flex; justify-content: space-between;
        }

        .module {
            margin-bottom: 25px; padding: 15px; border: 1px solid rgba(255,255,255,0.1);
            background: rgba(0,0,0,0.5); transition: all 0.3s;
        }
        .module:hover { border-color: currentColor; box-shadow: inset 0 0 10px currentColor; }

        .mod-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; font-weight: bold; }
        
        .badge {
            padding: 4px 10px; font-size: 0.8em; font-family: 'VT323', monospace;
            border: 1px solid currentColor; animation: pulse 1.5s infinite; text-shadow: none;
        }

        @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.5; } 100% { opacity: 1; } }

        .data-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; font-family: 'VT323', monospace; font-size: 1.3em; }
        .d-label { color: #aaa; }
        .d-val { float: right; }

        .up { color: var(--neon-green); text-shadow: 0 0 8px var(--neon-green); }
        .down { color: var(--neon-red); text-shadow: 0 0 8px var(--neon-red); }
        .warn { color: var(--neon-yellow); text-shadow: 0 0 8px var(--neon-yellow); }

        .log-box {
            font-family: 'VT323', monospace; font-size: 1.2em; margin-top: 15px;
            padding: 10px; background: #000; border-left: 3px solid currentColor; color: #fff;
        }

        .blink { animation: blinker 1s linear infinite; }
        @keyframes blinker { 50% { opacity: 0; } }
    </style>
</head>
<body>
    <div class="scanline"></div>
    
    <div class="header-container">
        <div class="title">🛰️ NUVOLA // ORBITAL COMMAND</div>
        <div class="sys-info">
            <span class="blink">_</span> UPLINK: <span class="up">ESTABLISHED</span> || ENCRYPTION: QUANTUM-RESISTANT || HQ: ROME [LAT 41.9N / LON 12.5E]<br>
            SYS_CLOCK: <span id="clock" style="color:var(--neon-yellow)">00:00:00 UTC</span> || GLOBAL_STATUS: <span class="up">DEFCON 5 / ALL SYSTEMS NOMINAL</span><br>
            <span class="blink">▶</span> <span style="color:var(--neon-purple); font-weight:bold; text-shadow:0 0 10px var(--neon-purple);">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</span>
        </div>
    </div>

    <div class="grid">
        <!-- HFT SQUADRONS -->
        <div class="panel p-hft">
            <div class="panel-title"><span>⚔️ SQUADRE D'ASSALTO [HFT]</span> <span>⚡ LIVE</span></div>
            
            <div class="module">
                <div class="mod-header">
                    <span><span class="blink">▶</span> SQUADRA_ALPHA <small>[BINANCE SCALPER]</small></span>
                    <span class="badge" style="color:var(--neon-green)">ENGAGED</span>
                </div>
                <div class="data-grid">
                    <div><span class="d-label">LATENCY:</span> <span class="d-val">3.1ms</span></div>
                    <div><span class="d-label">WIN_RATE:</span> <span class="d-val up">71.2%</span></div>
                    <div><span class="d-label">ORDER_FLOW:</span> <span class="d-val" id="alpha-orders">204</span>/s</div>
                    <div><span class="d-label">SESSION PNL:</span> <span class="d-val up">+$3,850.40</span></div>
                </div>
                <div class="log-box">> [SYS] Executing micro-sweeps on BTC/USDT. Liquidity drain detected.</div>
            </div>

            <div class="module">
                <div class="mod-header">
                    <span><span class="blink">▶</span> SQUADRA_DELTA <small>[ORDER FLOW]</small></span>
                    <span class="badge" style="color:var(--neon-yellow)">MONITORING</span>
                </div>
                <div class="data-grid">
                    <div><span class="d-label">TARGET:</span> <span class="d-val">DERIBIT OPTS</span></div>
                    <div><span class="d-label">IMBALANCE:</span> <span class="d-val up">91% BULL</span></div>
                    <div><span class="d-label">CVD_DELTA:</span> <span class="d-val up">+890 BTC</span></div>
                    <div><span class="d-label">TOXICITY:</span> <span class="d-val down">HIGH</span></div>
                </div>
                <div class="log-box" style="color:var(--neon-yellow)">> [WARN] Institutional dark pool prints anomalies. Absorbing shock...</div>
            </div>

            <div class="module">
                <div class="mod-header">
                    <span><span class="blink">▶</span> SQUADRA_GAMMA <small>[PAIRS / BITGET]</small></span>
                    <span class="badge" style="color:var(--neon-blue)">STANDBY</span>
                </div>
                <div class="data-grid">
                    <div><span class="d-label">PAIR:</span> <span class="d-val">SOL/ETH</span></div>
                    <div><span class="d-label">Z-SCORE:</span> <span class="d-val" id="gamma-z">2.14</span></div>
                    <div><span class="d-label">TRIGGER:</span> <span class="d-val">2.50</span></div>
                    <div><span class="d-label">EXPOSURE:</span> <span class="d-val">$0.00</span></div>
                </div>
                <div class="log-box">> [SYS] Calculating statistical divergence. Ready for deployment.</div>
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel p-trinity">
            <div class="panel-title"><span>🔺 PROTOCOLLO TRINITY</span> <span>🔒 SECURED</span></div>
            
            <div class="module">
                <div class="mod-header">
                    <span><span class="blink">▶</span> LO STROZZINO <small>[FUNDING ARB]</small></span>
                    <span class="badge" style="color:var(--neon-purple)">YIELDING</span>
                </div>
                <div class="data-grid">
                    <div><span class="d-label">MODE:</span> <span class="d-val">DELTA-NEUTRAL</span></div>
                    <div><span class="d-label">CAPITAL:</span> <span class="d-val">$250,000</span></div>
                    <div><span class="d-label">SPREAD:</span> <span class="d-val up">+0.08% / 8H</span></div>
                    <div><span class="d-label">EST_APY:</span> <span class="d-val up">24.5%</span></div>
                </div>
                <div class="log-box">> [ARB] Short PERP / Long SPOT. Harvesting premium from over-leveraged longs.</div>
            </div>

            <div class="module">
                <div class="mod-header">
                    <span><span class="blink">▶</span> IL CONTABILE <small>[DCA ACCUMULATOR]</small></span>
                    <span class="badge" style="color:var(--neon-green)">ACTIVE</span>
                </div>
                <div class="data-grid">
                    <div><span class="d-label">ASSET:</span> <span class="d-val">BTC</span></div>
                    <div><span class="d-label">INTERVAL:</span> <span class="d-val">4H</span></div>
                    <div><span class="d-label">NEXT_BUY:</span> <span class="d-val" id="contabile-timer">01:45:12</span></div>
                    <div><span class="d-label">AVG_COST:</span> <span class="d-val">$60,105</span></div>
                </div>
                <div class="log-box">> [DCA] Executing silent accumulation. Routing to cold vault.</div>
            </div>

            <div class="module">
                <div class="mod-header">
                    <span><span class="blink">▶</span> L'ANGELO CUSTODE <small>[MEV ARBITRUM]</small></span>
                    <span class="badge" style="color:var(--neon-red)">HUNTING</span>
                </div>
                <div class="data-grid">
                    <div><span class="d-label">MEMPOOL:</span> <span class="d-val warn" id="mev-tx">1250</span> tx/s</div>
                    <div><span class="d-label">SANDWICH:</span> <span class="d-val">22</span> (24H)</div>
                    <div><span class="d-label">NETWORK:</span> <span class="d-val">ARBITRUM ONE</span></div>
                    <div><span class="d-label">GAS_GWEI:</span> <span class="d-val down">0.05</span></div>
                </div>
                <div class="log-box" style="color:var(--neon-red)">> [MEV] Scanning for high-slippage victims on Uniswap V3. Extracting value.</div>
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel p-metrics">
            <div class="panel-title"><span>📊 METRICHE DI MERCATO</span> <span>🌐 GLOBAL</span></div>
            
            <div class="module">
                <div class="mod-header">
                    <span><span class="blink">▶</span> THE ORACLE <small>[SENTIMENT AI]</small></span>
                    <span class="badge" style="color:var(--neon-blue)">ANALYZING</span>
                </div>
                <div class="data-grid">
                    <div><span class="d-label">INDEX:</span> <span class="d-val up">82 [EXTREME GREED]</span></div>
                    <div><span class="d-label">SOCIAL_VOL:</span> <span class="d-val up">+45%</span></div>
                    <div><span class="d-label">NLP_BIAS:</span> <span class="d-val up">HYPER-BULLISH</span></div>
                    <div><span class="d-label">FEAR:</span> <span class="d-val down">0%</span></div>
                </div>
                <div class="log-box">> [AI] Ingesting CT & Reddit. Retail euphoria at critical mass. Top signals flashing.</div>
            </div>

            <div class="module">
                <div class="mod-header">
                    <span><span class="blink">▶</span> WHALE TRACKER <small>[ON-CHAIN]</small></span>
                    <span class="badge" style="color:var(--neon-red)">ALERT</span>
                </div>
                <div class="data-grid">
                    <div><span class="d-label">LAST_TX:</span> <span class="d-val">45 SEC AGO</span></div>
                    <div><span class="d-label">VOLUME:</span> <span class="d-val warn">22,500 BTC</span></div>
                    <div><span class="d-label">ORIGIN:</span> <span class="d-val">UNKNOWN ENTITY</span></div>
                    <div><span class="d-label">DEST:</span> <span class="d-val down">BINANCE HOT</span></div>
                </div>
                <div class="log-box" style="color:var(--neon-yellow)">> [WARN] Colossal exchange inflow detected. Potential market dump imminent.</div>
            </div>

            <div class="module">
                <div class="mod-header">
                    <span><span class="blink">▶</span> NODE RESOURCES <small>[NUVOLA CORE]</small></span>
                    <span class="badge" style="color:var(--neon-green)">NOMINAL</span>
                </div>
                <div class="data-grid">
                    <div><span class="d-label">CPU_LOAD:</span> <span class="d-val" id="cpu-load">18.5%</span></div>
                    <div><span class="d-label">MEM_USE:</span> <span class="d-val" id="mem-load">6.2GB / 64GB</span></div>
                    <div><span class="d-label">NET_I/O:</span> <span class="d-val">2.5 Gbps</span></div>
                    <div><span class="d-label">TEMP:</span> <span class="d-val">45°C</span></div>
                </div>
                <div class="log-box">> [SYS] Hardware operating flawlessly. Cooling fans at 30%.</div>
            </div>
        </div>
    </div>

    <script>
        setInterval(() => {
            const now = new Date();
            document.getElementById('clock').innerText = now.toISOString().substring(11,19) + " UTC";
            
            document.getElementById('alpha-orders').innerText = Math.floor(Math.random() * 80) + 150;
            document.getElementById('gamma-z').innerText = (Math.random() * 0.5 + 1.8).toFixed(2);
            document.getElementById('mev-tx').innerText = Math.floor(Math.random() * 500) + 1000;
            
            document.getElementById('cpu-load').innerText = (Math.random() * 15 + 10).toFixed(1) + "%";
            document.getElementById('mem-load').innerText = (Math.random() * 0.8 + 5.5).toFixed(1) + "GB / 64GB";
        }, 1000);
        
        let timer = 3600 * 1 + 45 * 60 + 12;
        setInterval(() => {
            if(timer > 0) timer--;
            let h = Math.floor(timer / 3600).toString().padStart(2, '0');
            let m = Math.floor((timer % 3600) / 60).toString().padStart(2, '0');
            let s = (timer % 60).toString().padStart(2, '0');
            document.getElementById('contabile-timer').innerText = `${h}:${m}:${s}`;
        }, 1000);
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
