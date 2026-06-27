
import time
class Scalper:
    def __init__(self, eng, sym, capital, cfg):
        self.eng=eng;self.sym=sym;self.cap=capital;self.cfg=cfg;self.ep=0.0;self.h=0.0;self.t=0;self.pnl=0.0;self.ba=0.0
    def run(self):
        p=self.eng.price(self.sym)
        if p<=0:return{}
        self.h=max(self.h,p)
        o=self.eng.open_orders(self.sym)
        if any(x.get('side')=='SELL' for x in o if isinstance(x,dict)):return{}
        atr=self.eng.atr(self.sym)
        if not self.ba:self.ba=atr
        drop=(self.h-p)/self.h if self.h else 0
        usdc=self.eng.balance('USDC')
        if drop>=self.cfg.get('entry_drop',0.008) and usdc>=5:
            amt=min(self.cap*0.4,15)
            r=self.eng.market_buy_quote(self.sym,amt)
            if isinstance(r,dict) and 'executedQty' in r:
                qty=float(r['executedQty']);cost=float(r['cummulativeQuoteQty'])
                self.ep=cost/qty;self.eng.limit_sell(self.sym,qty*0.998,self.ep*1.004)
                self.t+=1;self.h=p
                return{'action':'BUY','qty':qty,'price':self.ep}
        self.ba=self.ba*0.95+atr*0.05
        return{'price':p,'drop':drop,'pnl':self.pnl,'trades':self.t}
