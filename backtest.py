from backtesting import Backtest, Strategy
from backtesting.lib import crossover
from backtesting.test import EURUSD

import pandas as pd
from swing5 import strategy,get_data,get_configs,get_standard_MAs
from signals import decision,DUPLICATE,NEW_STOP,NEW_PROFIT,CANCEL,check_collision
from utils import logger,check_run_arg
from trader import ALLOWED_TRADE_PAIRS
import logging
logger.setLevel(logging.WARNING)
import datetime


class EmaCross(Strategy):
    n1 = 8
    n2 = 21

    def init(self):
        close = self.data.Close
        self.ema1 = self.I(self.ema, close, self.n1)
        self.ema2 = self.I(self.ema, close, self.n2)

    def ema(self, s, n):
        return pd.Series(s).ewm(span=n, adjust=False).mean()

    def next(self):
        if crossover(self.ema1, self.ema2):
            self.buy()
        elif crossover(self.ema2, self.ema1):
            self.sell()

pd.options.mode.chained_assignment = None

configs=get_configs()
configs['limit']=1500
configs['scale']=0.0001
configs['pair']='BTCUSDT'
size=0.05

class TestStrategy(Strategy):
    ema_min_n = 8
    ema_max_n = 21

    def init(self):
        print("EMAS",self.ema_min_n,self.ema_max_n)
        configs.update({
            'EMA_MIN':self.ema_min_n,
            'EMA_MAX':self.ema_max_n,
        })
        self.ema_min= self.I(self.ema, self.data.Close, self.ema_min_n)
        self.ema_max= self.I(self.ema, self.data.Close, self.ema_max_n)
        self.ma50= self.I(self.ma, self.data.Close, 50)

    def ma(self,s,n):
        return pd.Series(s).rolling(n).mean()

    def ema(self,s,n):
        return pd.Series(s).ewm(span=n, adjust=False).mean()

    def next(self):
        data=self.data.df

        for o in self.orders:
            if o.sl and check_collision(data.iloc[-1], o.sl):
                o.cancel()

        signal = strategy(swing5=get_standard_MAs(data,configs),configs=configs)
        if signal:
            print("signal:", signal)
            ss=[{"entry":o.stop,"stop":o.sl,"profit":o.tp,"type":("Buy" if o.is_long else 'Sell'),'tolerance':1} for o in self.orders if o.stop and o.sl and o.tp]
            for i,d in decision(ss,signal):
                if d == CANCEL:
                    self.orders[i].close()
                elif d == DUPLICATE:
                    print("DUPLICATE")
                    return

            if signal['type']=='Buy':
                self.buy(size=size,stop=signal['entry'],sl=signal['stop'],tp=signal['profit'])
            elif signal['type']=='Sell':
                self.sell(size=size,stop=signal['entry'],sl=signal['stop'],tp=signal['profit'])

if __name__=='__main__':
    today = datetime.datetime.today()
    last = today - datetime.timedelta(days=365)
    DATA = get_data(test=check_run_arg('--test'), **configs)
    if check_run_arg('--cross'):
        bt = Backtest(DATA, EmaCross,
                      cash=10000, commission=.0004,
                      exclusive_orders=True)
        stats = bt.run()
        print(stats)
        bt.plot()
    else:
        if check_run_arg('--optimize'):
            DATA=DATA[-1500:]
            bt = Backtest(DATA, TestStrategy, commission=.0004, cash=10000)
            stats, heatmap = bt.optimize(
                ema_min_n=range(3, 50,1),
                ema_max_n=range(3, 50, 1),
                constraint=lambda p: p.ema_min_n < p.ema_max_n,
                maximize='Win Rate [%]' if check_run_arg('--winrate') else 'Equity Final [$]',
                random_state=7,
                max_tries=1000,
                return_heatmap=True)

            print(stats)
            print(heatmap.dropna().sort_values().iloc[-3:])
            heatmap.to_csv(configs['pair']+'_heatmap.csv')
        else:
            bt = Backtest(DATA, TestStrategy, commission=.0004, cash=10000)
            stats = bt.run()
            bt.plot()
            print(stats)

#15       83       138        75.000000
