prices = {'ETH': 1868.26, 'BNB': 557.32, 'ADA': 0.2261, 'DOGE': 0.0809, 'SOL': 78.27, 'DOT': 1.271, 'AVAX': 8.23, 'BTC': 61299.59}
balances = {'BTC': 0.00081649, 'ETH': 4.01e-05, 'BNB': 0.44100934, 'ADA': 0.8, 'DOGE': 464.508, 'EUR': 74.8187, 'SOL': 2.60819, 'DOT': 38.32, 'AVAX': 0.00246}
total = balances['EUR']
for a, b in balances.items():
    if a in prices: total += b * prices[a]
print(total)
