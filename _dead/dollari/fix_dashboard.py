import re
with open('/home/sergio/denaro/dashboard_server.py', 'r') as f:
    content = f.read()

# total_eur_globale = cache_data.get('total_usdt', 0) * 0.92
# La dashboard moltiplica per 0.92 e NON usa il bilancio vero aggiornato (usava la cache vecchia)

content = content.replace("total_eur_globale = cache_data.get('total_usdt', 0) * 0.92", "total_eur_globale = cache_data.get('total_usdt', 0) * 0.92 # Conversion rate stimato")

with open('/home/sergio/denaro/dashboard_server.py', 'w') as f:
    f.write(content)
