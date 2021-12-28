from models import Signal
from datetime import datetime
from signals import trigger_signals
from utils import check_run_arg
import pandas as pd
import os
import numpy as np

def seed_signal():
    signal = Signal()
    signal.delete_many({})
    signal[signal.entry] = 33800.0
    signal[signal.stop] = 20000.0
    signal[signal.profit] = 45000.0
    signal[signal.type] = "Buy"
    signal[signal.open_time] = datetime.now()
    signal[signal.tolerance] = 24.85858327259383
    signal[signal.saving_profit] = 42000.0
    signal[signal.ratio] = 1.9
    signal[signal.percent] = 2.0
    signal[signal.market_type] = "Futures"
    signal[signal.current_price] = 39300.0
    signal[signal.pair] = "BTCUSDT"
    signal[signal.message_id] = None
    signal.save()

def resample_timeframe(path,to):
    test = pd.read_csv(path)
    base = pd.DataFrame({}, columns=['Open Time', 'Open', 'Close', 'High', "Low", 'Volume'])
    base['Open Time'] = pd.to_datetime(test['date'])
    base['Open'] = test['open']
    base['Close'] = test['close']
    base['High'] = test['high']
    base['Low'] = test['low']
    base['Volume'] = test['Volume BTC']
    base.index = base['Open Time']
    base.drop('Open Time', axis=1, inplace=True)
    base.index= base['Open Time']
    converted = base.resample(to).agg(
        {'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum', 'Open Time': 'first'})
    converted['Open Time'] = converted['Open Time'].astype(np.int64) // 10 ** 6
    converted.to_csv(os.path.dirname(path)+('/{}_{}'.format(to.lower(),'_'.join(os.path.basename(path).split('_')[1:]))),index=False)
    print("nas",converted['Open Time'].isna().sum())

if __name__ =='__main__':
    initial = 100
    profit = 0.05
    days = 12

    for i in range(days):
        initial+= initial*profit

    print("initial:",initial)
