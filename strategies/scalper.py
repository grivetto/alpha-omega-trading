
import numpy as np, pandas as pd
from loguru import logger
from core.engine import Settings, TradeDB, settings
from strategies.base import BaseStrategy, Side, Signal
_FEE = 0.00075
class ScalperStrategy(BaseStrategy):
    def __init__(self, ex, db, s=settings):
        super().__init__("Scalper", ex, s.scalper_symbol, s.scalper_capital); self.db = db
    async def on_candle(self, ohlcv):
        if self.is_paused or not ohlcv or len(ohlcv) < 50: return []
        df = pd.DataFrame(ohlcv, columns=["t","o","h","l","c","v"])
        c, h, l = df["c"], df["h"], df["l"]
        e21 = c.ewm(span=21, adjust=False).mean()
        delta = c.diff(); g = delta.clip(lower=0); l2 = -delta.clip(upper=0)
        ag = g.ewm(com=6, adjust=False).mean(); al = l2.ewm(com=6, adjust=False).mean()
        rs = 100 - (100 / (1 + ag / al.replace(0, np.finfo(float).tiny)))
        tr = pd.concat([h-l,(h-c.shift(1)).abs(),(l-c.shift(1)).abs()],axis=1).max(axis=1)
        a = tr.rolling(14).mean()
        cp = float(c.iloc[-1]); cr = float(rs.iloc[-1]); ca = float(a.iloc[-1])
        await self._check_sl(cp)
        sigs = []; hp = len(self._positions) > 0
        # LONG: oversold (works in any trend, wider SL)
        if cr < 40 and not hp:
            tp = round(cp + 2.5*ca, 6); sl = round(cp - 2.0*ca, 6)
            if (tp-cp)/cp >= _FEE*3:
                am = await self._size(cp, sl)
                if am > 0: sigs.append(Signal(Side.BUY, self.symbol, am, cp, tp, sl, "OvS r%.0f" % cr))
        # SHORT: overbought
        if cr > 60 and not hp and not sigs:
            tp = round(cp - 2.5*ca, 6); sl = round(cp + 2.0*ca, 6)
            if (cp-tp)/cp >= _FEE*3:
                am = await self._size(cp, sl, True)
                if am > 0: sigs.append(Signal(Side.SELL, self.symbol, am, cp, tp, sl, "OvB r%.0f" % cr))
        return sigs
    async def _size(self, entry, sl, short=False):
        qc = await self.get_quote_capital(); pre, ma, mc = self.exchange.get_market_precision_and_limits(self.symbol)
        risk = qc * 0.02; rpu = abs(entry-sl)
        if rpu <= 0: return 0.0
        sz = risk/rpu; ms = mc/entry
        if sz < ms: sz = ms*1.05
        f = min(sz, (qc*0.40)/entry)
        if f < ma: f = ma
        try:
            b = await self.exchange.fetch_balance(); p = self.symbol.split("/")
            if short:
                fb = float(b["free"].get(p[0].upper(),0)); f = min(f, fb*0.98)
            else:
                q = p[1].upper() if len(p)>=2 else "EUR"
                fb = float(b["free"].get(q,0)); f = min(f, (fb*0.98)/entry)
        except: pass
        r = round(f, pre); 
        if r < ma: r = round(f+10**(-pre), pre)
        return 0.0 if r*entry < mc else r
    async def _check_sl(self, price):
        for oid, pos in list(self._positions.items()):
            if not pos.sl_price or not pos.tp_order_id: continue
            if pos.side==Side.BUY and price<=pos.sl_price: await self._exec_sl(oid,pos,"sell")
            elif pos.side==Side.SELL and price>=pos.sl_price: await self._exec_sl(oid,pos,"buy")
    async def _exec_sl(self, oid, pos, side):
        try: await self.exchange.cancel_order(pos.tp_order_id,pos.symbol)
        except: pass
        try:
            b=await self.exchange.fetch_balance(); p=self.symbol.split("/")
            if side=="sell":
                actual=float(b["free"].get(p[0].upper(),0))*0.98
            else:
                q=p[1].upper() if len(p)>=2 else "EUR"
                actual=(float(b["free"].get(q,0))*0.98)/(pos.entry_price or 1)
            amt = min(actual,pos.amount) if actual>0 else pos.amount
            if amt<=0: return
            ex=await self.exchange.create_order(symbol=pos.symbol,order_type="market",side=side,amount=amt)
            ep=float(ex.get("price",pos.sl_price)) if not self.exchange.dry_run else pos.sl_price
            g=(ep-pos.entry_price)*amt if pos.side==Side.BUY else (pos.entry_price-ep)*amt
            fees=(pos.entry_price+ep)*amt*_FEE; n=g-fees
            logger.critical("SL EXECUTED PnL=%.4f" % n)
            self.db.save_trade(pos.symbol,side,ep,amt,amt*ep,fees,n,self.name)
            del self._positions[oid]
        except Exception as e: logger.error("SL FAIL: %s" % str(e))
    async def on_order_update(self, order):
        oid,st=order.get("id",""),order.get("status","")
        if st!="closed": return
        if oid in self._positions:
            pos=self._positions[oid]
            if not pos.tp_order_id:
                try:
                    filled=float(order.get("filled",pos.amount) or pos.amount)
                    pos.amount=min(filled,pos.amount) if filled>0 else pos.amount
                    ts="sell" if pos.side==Side.BUY else "buy"
                    to=await self.exchange.create_order(symbol=pos.symbol,order_type="limit",side=ts,amount=pos.amount,price=pos.tp_price)
                    pos.tp_order_id=to["id"]
                    logger.info("Entry filled TP @ %.4f" % pos.tp_price)
                except Exception as e: logger.critical("TP fail: %s" % str(e))
            return
        for eo,pos in list(self._positions.items()):
            if oid==pos.tp_order_id:
                ep=float(order.get("price",pos.tp_price) or pos.tp_price)
                g=(ep-pos.entry_price)*pos.amount if pos.side==Side.BUY else (pos.entry_price-ep)*pos.amount
                fees=(pos.entry_price+ep)*pos.amount*_FEE; n=g-fees
                logger.info("TP FILLED PnL=%.4f" % n)
                self.db.save_trade(pos.symbol,"TP",ep,pos.amount,pos.amount*ep,fees,n,self.name)
                del self._positions[eo]; return
    async def shutdown(self):
        for oid,pos in list(self._positions.items()):
            if not pos.tp_order_id:
                try: await self.exchange.cancel_order(oid,pos.symbol)
                except: pass
            else:
                try: await self.exchange.cancel_order(pos.tp_order_id,pos.symbol)
                except: pass
                try: await self.exchange.create_order(symbol=pos.symbol,order_type="market",side="sell" if pos.side==Side.BUY else "buy",amount=pos.amount)
                except: pass
        self._positions.clear()
