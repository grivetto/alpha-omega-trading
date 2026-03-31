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
        :root {
            --bg-color: #050510;
            --neon-blue: #00f3ff;
            --neon-pink: #ff00ea;
            --neon-green: #39ff14;
            --neon-red: #ff073a;
            --neon-yellow: #fefe33;
            --font-main: 'Courier New', Courier, monospace;
        }

        body {
            background-color: var(--bg-color);
            color: var(--neon-blue);
            font-family: var(--font-main);
            margin: 0;
            padding: 20px;
            overflow-x: hidden;
        }

        /* Scanline effect */
        body::before {
            content: " ";
            display: block;
            position: fixed;
            top: 0;
            left: 0;
            bottom: 0;
            right: 0;
            background: linear-gradient(rgba(18, 16, 16, 0) 50%, rgba(0, 0, 0, 0.25) 50%), linear-gradient(90deg, rgba(255, 0, 0, 0.06), rgba(0, 255, 0, 0.02), rgba(0, 0, 255, 0.06));
            z-index: 2;
            background-size: 100% 2px, 3px 100%;
            pointer-events: none;
        }

        h1, h2, h3 {
            text-transform: uppercase;
            text-shadow: 0 0 5px var(--neon-blue), 0 0 10px var(--neon-blue);
            margin-bottom: 10px;
        }

        .header {
            text-align: center;
            border-bottom: 2px solid var(--neon-blue);
            padding-bottom: 15px;
            margin-bottom: 30px;
            box-shadow: 0 5px 15px rgba(0, 243, 255, 0.2);
        }

        .header h1 {
            font-size: 2.5em;
            letter-spacing: 5px;
            color: #fff;
            text-shadow: 0 0 10px var(--neon-blue), 0 0 20px var(--neon-blue), 0 0 40px var(--neon-blue);
        }

        .container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
        }

        .panel {
            background: rgba(0, 20, 40, 0.6);
            border: 1px solid var(--neon-blue);
            padding: 15px;
            box-shadow: inset 0 0 10px rgba(0, 243, 255, 0.1), 0 0 10px rgba(0, 243, 255, 0.2);
            position: relative;
        }

        .panel::after {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; bottom: 0;
            border: 1px solid var(--neon-blue);
            box-shadow: 0 0 8px var(--neon-blue);
            pointer-events: none;
            opacity: 0.5;
        }

        .panel h2 {
            color: var(--neon-pink);
            text-shadow: 0 0 5px var(--neon-pink);
            border-bottom: 1px dashed var(--neon-pink);
            padding-bottom: 5px;
            font-size: 1.2em;
        }

        .status-online {
            color: var(--neon-green);
            text-shadow: 0 0 5px var(--neon-green);
            animation: blink 1.5s infinite;
        }

        .status-offline {
            color: var(--neon-red);
            text-shadow: 0 0 5px var(--neon-red);
        }

        .status-standby {
            color: var(--neon-yellow);
            text-shadow: 0 0 5px var(--neon-yellow);
        }

        @keyframes blink {
            0% { opacity: 1; }
            50% { opacity: 0.5; }
            100% { opacity: 1; }
        }

        .data-row {
            display: flex;
            justify-content: space-between;
            margin: 8px 0;
            border-bottom: 1px solid rgba(0, 243, 255, 0.2);
            padding-bottom: 2px;
        }

        .data-label {
            font-weight: bold;
        }

        .data-value {
            font-family: monospace;
        }

        .glitch {
            animation: glitch-anim 2s infinite linear alternate-reverse;
        }

        @keyframes glitch-anim {
            0% { clip: rect(10px, 9999px, 44px, 0); transform: skew(0.5deg); }
            5% { clip: rect(70px, 9999px, 14px, 0); transform: skew(0.1deg); }
            10% { clip: rect(31px, 9999px, 81px, 0); transform: skew(0.3deg); }
            15% { clip: rect(1px, 9999px, 55px, 0); transform: skew(0.4deg); }
            20% { clip: rect(89px, 9999px, 11px, 0); transform: skew(0.2deg); }
            25% { clip: rect(44px, 9999px, 92px, 0); transform: skew(0.5deg); }
            30% { clip: rect(2px, 9999px, 33px, 0); transform: skew(0.1deg); }
            35% { clip: rect(56px, 9999px, 78px, 0); transform: skew(0.3deg); }
            40% { clip: rect(12px, 9999px, 4px, 0); transform: skew(0.4deg); }
            45% { clip: rect(98px, 9999px, 22px, 0); transform: skew(0.2deg); }
            50% { clip: rect(34px, 9999px, 66px, 0); transform: skew(0.5deg); }
            55% { clip: rect(77px, 9999px, 88px, 0); transform: skew(0.1deg); }
            60% { clip: rect(15px, 9999px, 5px, 0); transform: skew(0.3deg); }
            65% { clip: rect(61px, 9999px, 49px, 0); transform: skew(0.4deg); }
            70% { clip: rect(82px, 9999px, 95px, 0); transform: skew(0.2deg); }
            75% { clip: rect(27px, 9999px, 18px, 0); transform: skew(0.5deg); }
            80% { clip: rect(48px, 9999px, 72px, 0); transform: skew(0.1deg); }
            85% { clip: rect(9px, 9999px, 39px, 0); transform: skew(0.3deg); }
            90% { clip: rect(85px, 9999px, 63px, 0); transform: skew(0.4deg); }
            95% { clip: rect(52px, 9999px, 21px, 0); transform: skew(0.2deg); }
            100% { clip: rect(37px, 9999px, 86px, 0); transform: skew(0.5deg); }
        }

        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
        }
        th, td {
            text-align: left;
            padding: 5px;
            border-bottom: 1px solid rgba(0, 243, 255, 0.3);
        }
        th {
            color: var(--neon-yellow);
        }
    </style>
</head>
<body>

    <div class="header">
        <h1 class="glitch" data-text="ORBITAL COMMAND // NUVOLA">ORBITAL COMMAND // NUVOLA</h1>
        <p>📡 UPLINK ESTABLISHED | ENCRYPTION: QUANTUM | CLASSIFICATION: TOP SECRET</p>
    </div>

    <div class="container">
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <div class="data-row">
                <span class="data-label">🦅 SQUADRA_ALPHA (Binance Scalp)</span>
                <span class="data-value status-online">[ ENGAGED ]</span>
            </div>
            <div class="data-row">
                <span class="data-label">Latency</span>
                <span class="data-value">12 ms</span>
            </div>
            <div class="data-row">
                <span class="data-label">Win Rate (1H)</span>
                <span class="data-value" style="color: var(--neon-green);">68.4%</span>
            </div>
            <br>
            <div class="data-row">
                <span class="data-label">🎯 SQUADRA_DELTA (Order Flow)</span>
                <span class="data-value status-online">[ ACTIVE ]</span>
            </div>
            <div class="data-row">
                <span class="data-label">Imbalance Detect</span>
                <span class="data-value">High</span>
            </div>
            <div class="data-row">
                <span class="data-label">Executions (24H)</span>
                <span class="data-value">1,024</span>
            </div>
            <br>
            <div class="data-row">
                <span class="data-label">⚖️ SQUADRA_GAMMA (Bitget Pairs)</span>
                <span class="data-value status-standby">[ STANDBY ]</span>
            </div>
            <div class="data-row">
                <span class="data-label">Spread</span>
                <span class="data-value">0.15%</span>
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2>🔺 PROTOCOLLO TRINITY</h2>
            <div class="data-row" style="background: rgba(0, 255, 0, 0.1); padding: 5px; border: 1px dashed var(--neon-green); margin-bottom: 10px; text-align: center; justify-content: center;">
                <span class="data-label status-online">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</span>
            </div>
            <div class="data-row">
                <span class="data-label">🕴️ Lo Strozzino (Funding Arb)</span>
                <span class="data-value status-online">GATHERING</span>
            </div>
            <div class="data-row">
                <span class="data-label">Current Yield</span>
                <span class="data-value" style="color: var(--neon-green);">+14.2% APR</span>
            </div>
            <br>
            <div class="data-row">
                <span class="data-label">🧮 Il Contabile (Smart DCA)</span>
                <span class="data-value status-online">ACCUMULATING</span>
            </div>
            <div class="data-row">
                <span class="data-label">BTC Target</span>
                <span class="data-value">Next @ $92K</span>
            </div>
            <br>
            <div class="data-row">
                <span class="data-label">🛡️ L'Angelo Custode (Arbitrum MEV)</span>
                <span class="data-value status-online">PATROLLING</span>
            </div>
            <div class="data-row">
                <span class="data-label">Mempool Scans</span>
                <span class="data-value">845,210/min</span>
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <h2>👁️ METRICHE DI MERCATO</h2>
            <div class="data-row">
                <span class="data-label">🔮 The Oracle (Binance Sentiment)</span>
                <span class="data-value" style="color: var(--neon-yellow);">GREED (78)</span>
            </div>
            <div class="data-row">
                <span class="data-label">Liquidations (1H)</span>
                <span class="data-value" style="color: var(--neon-red);">-$42.5M</span>
            </div>
            <div class="data-row">
                <span class="data-label">🐳 Whale Tracker</span>
                <span class="data-value status-online">TRACKING</span>
            </div>
            <table>
                <tr>
                    <th>Asset</th>
                    <th>Volume Anomaly</th>
                    <th>Signal</th>
                </tr>
                <tr>
                    <td>BTC</td>
                    <td>+450%</td>
                    <td style="color: var(--neon-green);">BUY</td>
                </tr>
                <tr>
                    <td>ETH</td>
                    <td>+120%</td>
                    <td style="color: var(--neon-yellow);">HOLD</td>
                </tr>
                <tr>
                    <td>SOL</td>
                    <td>-80%</td>
                    <td style="color: var(--neon-red);">SELL</td>
                </tr>
            </table>
        </div>
        
        <!-- SYSTEM LOGS -->
        <div class="panel" style="grid-column: 1 / -1;">
            <h2>🖥️ SYSTEM LOGS / OVERRIDE</h2>
            <div style="height: 150px; overflow-y: scroll; font-size: 0.9em; border: 1px solid rgba(0,243,255,0.2); padding: 5px; background: rgba(0,0,0,0.5);">
                <p>> [SYS] Orbital Command Boot Sequence Initiated...</p>
                <p>> [SYS] Quantum Encryption Keys: VERIFIED.</p>
                <p>> [HFT] SQUADRA_ALPHA deployed to Binance WebSocket.</p>
                <p>> [TRINITY] Lo Strozzino recalculating perp funding rates...</p>
                <p>> [MEV] L'Angelo Custode successfully front-ran transaction 0x7f8... on Arbitrum.</p>
                <p class="status-online">> [SYS] All systems nominal. Ready to harvest.</p>
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
    # Run on port 5000 by default
    app.run(host='0.0.0.0', port=5000)
