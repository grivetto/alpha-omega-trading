const fs = require('fs');
const path = require('path');

const urls = process.argv.slice(2);
const outDir = __dirname;

function htmlToText(html) {
  let s = html;
  // kill script/style/noscript blocks
  s = s.replace(/<script[\s\S]*?<\/script>/gi, ' ');
  s = s.replace(/<style[\s\S]*?<\/style>/gi, ' ');
  s = s.replace(/<noscript[\s\S]*?<\/noscript>/gi, ' ');
  s = s.replace(/<svg[\s\S]*?<\/svg>/gi, ' ');
  // block elements -> newline
  s = s.replace(/<\/(p|div|tr|li|h[1-6]|table|section|article|br)>/gi, '\n');
  s = s.replace(/<br\s*\/?>/gi, '\n');
  s = s.replace(/<\/t[dh]>/gi, ' | ');
  s = s.replace(/<[^>]+>/g, ' ');
  // entities
  s = s.replace(/&nbsp;/g, ' ').replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>')
       .replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&euro;/g, 'EUR');
  s = s.replace(/&#x([0-9a-f]+);/gi, (m, h) => String.fromCodePoint(parseInt(h, 16)));
  s = s.replace(/&#(\d+);/g, (m, d) => String.fromCodePoint(parseInt(d, 10)));
  // collapse
  s = s.split('\n').map(l => l.replace(/[ \t\u00a0]+/g, ' ').trim()).filter(l => l.length > 0).join('\n');
  s = s.replace(/\n{3,}/g, '\n\n');
  return s;
}

(async () => {
  for (const url of urls) {
    const name = url.replace(/^https?:\/\//, '').replace(/[^a-zA-Z0-9._-]+/g, '_').slice(0, 120) + '.txt';
    const out = path.join(outDir, name);
    try {
      const res = await fetch(url, {
        headers: {
          'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36',
          'Accept': 'text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8',
          'Accept-Language': 'en-US,en;q=0.9,it;q=0.8'
        },
        redirect: 'follow'
      });
      const body = await res.text();
      fs.writeFileSync(out, `URL: ${url}\nSTATUS: ${res.status}\nFINAL: ${res.url}\nBYTES: ${body.length}\n\n` + htmlToText(body), 'utf8');
      console.log(`OK ${res.status} ${body.length}b -> ${name}`);
    } catch (e) {
      fs.writeFileSync(out, `URL: ${url}\nERROR: ${e.message}\n`, 'utf8');
      console.log(`ERR ${url} :: ${e.message}`);
    }
  }
})();
