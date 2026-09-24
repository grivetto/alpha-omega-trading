const fs = require('fs');
const path = require('path');
const out = path.join(__dirname, 'okx_instruments.json');

(async () => {
  const results = {};
  for (const instType of ['SPOT', 'SWAP']) {
    try {
      const res = await fetch(`https://eea.okx.com/api/v5/public/instruments?instType=${instType}`, {
        headers: { 'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json' }
      });
      const j = await res.json();
      results[instType] = { status: res.status, code: j.code, count: (j.data || []).length, data: j.data || [] };
    } catch (e) {
      results[instType] = { error: e.message };
    }
  }
  fs.writeFileSync(out, JSON.stringify(results, null, 1), 'utf8');

  for (const [k, v] of Object.entries(results)) {
    if (v.error) { console.log(`${k}: ERROR ${v.error}`); continue; }
    console.log(`${k}: status=${v.status} code=${v.code} n=${v.count}`);
    const all = v.data.map(d => d.instId);
    const eur = all.filter(s => /-EUR$/.test(s));
    const usdc = all.filter(s => /-USDC$/.test(s));
    const eurusdc = all.filter(s => /USDC-EUR|EUR-USDC/.test(s));
    console.log(`  pairs ending -EUR : ${eur.length}`);
    console.log(`  pairs ending -USDC: ${usdc.length}`);
    console.log(`  USDC/EUR or EUR/USDC: ${JSON.stringify(eurusdc)}`);
    console.log(`  sample -EUR: ${eur.slice(0, 30).join(', ')}`);
    if (k === 'SWAP') console.log(`  SWAP list: ${all.join(', ')}`);
  }
})();
