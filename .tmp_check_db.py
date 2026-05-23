import sqlite3
c = sqlite3.connect('/home/sergio/denaro/denaro_memory.db')
c.row_factory = sqlite3.Row
tables = c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
print('Tables:', [t['name'] for t in tables])
for t in tables:
    n = t['name']
    cnt = c.execute('SELECT COUNT(*) FROM "{}"'.format(n)).fetchone()[0]
    print('  {}: {} rows'.format(n, cnt))
# Trade stats per bot
print('---')
for row in c.execute("""SELECT bot, side, COUNT(*) as cnt,
    ROUND(SUM(COALESCE(net_pnl,0)),4) as tot_pnl
    FROM trades GROUP BY bot, side ORDER BY bot, side""").fetchall():
    print('{:12s} {:4s} cnt={:4d} pnl={:+.4f}'.format(row['bot'], row['side'], row['cnt'], row['tot_pnl']))
total = c.execute("SELECT ROUND(SUM(COALESCE(net_pnl,0)),4) FROM trades").fetchone()[0]
print('TOTAL PnL:', '{:+.4f}'.format(total))
