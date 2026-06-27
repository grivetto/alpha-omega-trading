
import time
class WhaleTracker:
    def __init__(self, eng, sym, capital, cfg):
        self.eng=eng;self.sym=sym;self.cap=capital;self.cfg=cfg;self.t=0;self.pnl=0.0;self.cd=0
    def run(self):
        if time.time()<self.cd:return{}
        p=self.eng.price(self.sym)
        if p<=0:return{}
        o=self.eng.open_orders(self.sym)
        if any(x.get('side')=='SELL' for x in o if isinstance(x,dict)):return{}
        imb=self.eng.imbalance(self.sym)
        if imb>=self.cfg.get('imbalance_threshold',3.0) and self.eng.balance('USDC')>=5:
            amt=min(self.cap*0.3,12)
            r=self.eng.market_buy_quote(self.sym,amt)
            if isinstance(r,dict) and 'executedQty' in r:
                qty=float(r['executedQty']);cost=float(r['cummulativeQuoteQty'])
                ep=cost/qty;self.eng.limit_sell(self.sym,qty*0.998,ep*1.008)
                self.t+=1;self.cd=time.time()+20
                return{'action':'BUY','imbalance':imb,'qty':qty,'price':ep}
        return{'price':p,'imbalance':imb,'pnl':self.pnl,'trades':self.t}
