import pandas as pd
import glob,os
import numpy as np
from binance.client import Client
from utils import format_date,getDir,round_date,log

client = None

def fetch_klines(pair,market_type="Futures", interval=Client.KLINE_INTERVAL_1HOUR, limit=50, startTime=None, endTime=None,test=False):
    log("TEST",test)
    global client
    if not client:
        client=Client("API_KEY", "API_PRIVATE_KEY")

    m = int(interval.replace('m','').replace('h',''))
    if test:
        data_cache_file = ('test/data/{}_{}_{}.csv'.format(interval,pair,market_type))
        print("TEST FILE:{}".format(data_cache_file))
    else:
        data_cache_file = getDir('prices/{}/{}/{}_{}_{}.csv'.format(pair,market_type,interval, limit if limit else str(startTime)+"#"+str(endTime), (format_date("%Y_%b_%d_%H_%M",round_date(minutes=m))), ))
    log("FETCH PAIR",pair)
    if os.path.exists(data_cache_file):
        df = pd.read_csv(data_cache_file)
    else:
        for filename in os.listdir(os.path.dirname(data_cache_file)):
            if filename.startswith('{}_{}'.format(interval,limit if limit else str(startTime)+"#"+str(endTime))):
                os.remove(os.path.dirname(data_cache_file)+'/'+filename)
        klines = np.array(
            client.futures_continous_klines(pair=pair, contractType="PERPETUAL", interval=interval, limit=limit,
                                            startTime=startTime, endTime=endTime))
        df = pd.DataFrame(klines, dtype=float, columns=('Open Time',
                                                        'Open',
                                                        'High',
                                                        'Low',
                                                        'Close',
                                                        'Volume',
                                                        'Close Time',
                                                        'Quote asset volume',
                                                        'Number of trades',
                                                        'Taker buy base asset volume',
                                                        'Taker buy quote asset volume',
                                                        'Ignore'))

        df.to_csv(data_cache_file, index=False)
    df['Open Time'] = pd.to_datetime(df['Open Time'], unit='ms')
    if 'CLose Time' in df.columns:
        df['Close Time'] = pd.to_datetime(df['Close Time'], unit='ms')
    df['Candle'] = df['Open']<df['Close']
    df.index = df['Open Time']
    return df

if __name__=='__main__':
    m = int(Client.KLINE_INTERVAL_5MINUTE.replace('m',''))
    print((format_date("%Y_%b_%d_%H_%M",round_date(minutes=m))))
