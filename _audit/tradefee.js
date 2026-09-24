const fs = require('fs');
const path = require('path');

(async () => {
  // OKX public trade-fee endpoint: instType=SPOT, instId used as a sample
  const urls = [
    'https://eea.okx.com/api/v5/public/trade-fee?instType=SPOT&instId=BTC-EUR',
    'https://eea.okx.com/api/v5/public/trade-fee?instType=SPOT&instId=USDC-EUR',
    'https://eea.okx.com/api/v5/public/trade-fee?instType=SPOT&instId=BTC-USDC',
    'https://eea.okx.com/api/v5/public/trade-fee?instType=SWAP&instId=BTC-USD-SWAP'
  ];
  for (const u of urls) {
    try {
      const r = await fetch(u, { headers: { 'User-Agent': 'Mozilla/5.0', Accept: 'application/json' } });
      const t = await r.text();
      console.log(`${u}\n  -> ${r.status} ${t.slice(0, 600)}\n`);
    } catch (e) {
      console.log(`${u}\n  -> ERR ${e.message}\n`);
    }
  }
})();
