
import time
class NewsReactor:
    def __init__(self, eng, sym, capital, cfg):
        self.eng=eng;self.sym=sym;self.cap=capital;self.cfg=cfg;self.t=0;self.pnl=0.0;self.cd=0;self.ba=0.0;self.lp=0.0;self.lc=0.0
    def run(self):
        if time.time()<self.cd:return{}
        p=self.eng.price(self.sym)
        if p<=0:return{}
        o=self.eng.open_orders(self.sym)
        if any(x.get('side')=='SELL' for x in o if isinstance(x,dict)):return{}
        atr=self.eng.atr(self.sym)
        if not self.ba:self.ba=atr;self.lp=p;self.lc=time.time();return{}
        spike=atr/max(self.ba,0.0001);pc=(p-self.lp)/self.lp if self.lp else 0;el=time.time()-self.lc
        if spike>5 and abs(pc)>0.01 and el<120 and self.eng.balance('USDC')>=5:
            amt=min(self.cap*0.5,15)
            r=self.eng.market_buy_quote(self.sym,amt)
            if isinstance(r,dict) and 'executedQty' in r:
                qty=float(r['executedQty']);cost=float(r['cummulativeQuoteQty'])
                ep=cost/qty;self.eng.limit_sell(self.sym,qty*0.998,ep*1.015)
                self.t+=1;self.cd=time.time()+300
                return{'action':'NEWS_BUY','spike':spike,'qty':qty,'price':ep}
        self.ba=self.ba*0.98+atr*0.02;self.lp=p;self.lc=time.time()
        return{'price':p,'spike':spike,'pnl':self.pnl,'trades':self.t}
