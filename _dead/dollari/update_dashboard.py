import re

file_path = '/home/sergio/denaro/dashboard_server.py'
with open(file_path, 'r') as f:
    content = f.read()

div_to_add = '\n            <div style="background-color: var(--neon-green); color: #000; padding: 12px; margin-bottom: 15px; text-align: center; font-weight: bold; font-size: 1.3em; border: 2px solid #fff; border-radius: 5px; animation: pulse 2s infinite;">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</div>'

content = content.replace('<h2 class="glow-text-green">💰 PATRIMONIO</h2>', '<h2 class="glow-text-green">💰 PATRIMONIO</h2>' + div_to_add, 1)

content += '\n# ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV) - Fase 2: 2026-04-01 17:24 UTC\n'

with open(file_path, 'w') as f:
    f.write(content)
