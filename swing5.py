from binance.client import Client
from telbot import sendText
from signals import makeSignal
from utils import format_date, log,getIsTest
from data import fetch_klines

UP_TREND = "U"
DOWN_TREND = "D"
NO_TREND = None


def get_MA(df, rolling=50):
    ma = df['Close'].rolling(rolling).mean()
    return ma


def get_EMA(df, rolling=50):
    ema = df['Close'].ewm(span=rolling, adjust=False).mean()
    return ema


def get_data(test=False,**configs):
    swing5 = fetch_klines(configs['pair'], interval=configs['interval'], limit=configs['limit'],test=test)
    if configs.get('scale'):
        for d in ['Open', 'Close', 'High', 'Low']:
            swing5[d] = swing5[d] * 0.001
    swing5 = get_standard_MAs(swing5,configs)
    if configs['ignore_count'] > 0:
        swing5 = swing5.iloc[:-configs['ignore_count']]
    return swing5

def get_hourly(swing5,configs):
    swing5 = swing5.copy()
    hourly = swing5.resample("1H").agg(
        {'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum', 'Open Time': 'first'})
    hourly = get_standard_MAs(hourly,configs)
    merge = swing5.merge(hourly, how='left', right_on=hourly['Open Time'].dt.strftime('%d_%b_%Y %H'),
                         left_on=swing5['Open Time'].dt.strftime('%d_%b_%Y %H'))

    swing5['MA_50H'] = merge['MA_50_y'].values
    hourly['Candle'] = hourly['Open']<hourly['Close']
    return swing5,hourly


def get_standard_MAs(df,configs):
    df['MA_50'] = get_MA(df, 50)
    df['EMA_MIN'] = get_EMA(df, configs['EMA_MIN'])
    df['EMA_MAX'] = get_EMA(df, configs['EMA_MAX'])
    return df

def get_configs(**c):
    configs= {
        "pair": 'BTCUSDT',
        "EMA_MIN": 8,
        "EMA_MAX": 21,
        "interval": Client.KLINE_INTERVAL_5MINUTE,
        "limit": 720,
        "market_type": "Futures",
        "analyze_span_size": 5,
        "ignore_count": 0
    }
    if c is not None:
        configs.update(c)
    return configs

def analyze(**c):
    configs = get_configs(**c)
    swing5 = get_data(**configs)
    result = strategy(swing5=swing5, configs=configs)
    if not getIsTest() and result:
        sendText("Signal {} at {} \n {} \nSIG:{}".format(configs['pair'],format_date(), swing5.iloc[-1]['Open Time'], str(result)))
    return result, swing5, configs


def strategy(swing5, configs):
    # find time slice
    swing5,hourly = get_hourly(swing5,configs)
    lastHour = hourly.iloc[-1]
    hourlyTrend = getTrend(hourly[-1:], 'EMA_MAX')
    #
    if hourlyTrend is None:
         log("No Trend For Hourly Time Frame")
         return None

    result =None
    last= swing5.iloc[-1]
    span = swing5[-configs['analyze_span_size']:]

    trend21 = getTrend(span,"EMA_MAX")
    log("Check Trend EMA_MAX",trend21)
    if trend21!=NO_TREND and checkCoverage(hourly[-configs['analyze_span_size']:],True):
        trend8 = getTrend(span,"EMA_MIN")
        log("Check Trend EMA_MIN",configs['EMA_MIN'],trend8)
        if trend8 == NO_TREND:
            tolerance = atr(swing5, 14)[-1] / 5
            log("Check candle kind ",configs['EMA_MIN'], trend8, last['Candle'])
            if trend21 == UP_TREND and last['Candle'] and checkCoverage(span) and span['High'].argmax() != configs['analyze_span_size']-1:
                log("Check EMAs Order for Buy")
                if last["EMA_MIN"] > last['EMA_MAX']:
                        log("Check validation")
                        log("Buy Signal Calculation")
                        entry = span['High'].max() + tolerance
                        stop =max( span['Low'].min(),last['EMA_MAX'])
                        profit = entry + (3 * (entry - stop))
                        saving_profit = entry + (entry - stop)

                        if last['MA_50H'] > entry:
                            profit = min(profit, last['MA_50H'])

                        #stop=max(stop,span[:-1]["EMA_MAX"].max())
                        result = makeSignal("Buy", entry, stop - (tolerance), saving_profit, profit, last, tolerance, configs)
                        if result and result['ratio'] < 1.5:
                            result = None
            elif trend21 == DOWN_TREND and not last['Candle'] and checkCoverage(span) and span['Low'].argmin() != configs['analyze_span_size']-1:
                log("Check EMAs Order for Sell")
                if last["EMA_MIN"] < last['EMA_MAX']:
                        log("Check validation")
                        log("Sell Signal Calculation")
                        entry = span['Low'].min() - tolerance
                        stop =min( span['High'].max(),last['EMA_MAX'])
                        profit = entry + (3 * (entry - stop))
                        saving_profit = entry + (entry - stop)

                        if last['MA_50H'] < entry:
                            profit = max(profit, last['MA_50H'])

                        #stop= min(stop,span[:-1]["EMA_MAX"].min())

                        result = makeSignal("Sell", entry, stop+ (tolerance), saving_profit, profit, last, tolerance,configs)
                        if result and result['ratio'] < 1.5:
                            result = None

    return result

def checkCoverage(span,default=False):
    series = span['Candle']
    d = series.iloc[-1]
    idx= None
    idy= None
    for index,data in series[::-1].items():
        if data == d:
            if idy is not None:
                break
            idx = index
        else:
            idy = index
    if idx is None:
        return default
    x = span[idx:]
    y = span[idy:idx]
    if d:
        r = x['Close'].max() >= y['Open'].max()
    else:
        r = x['Close'].min() <= y['Open'].min()
    return r


def getTrend(data, col):
    trend = "NONE"
    for i,row in data.iterrows():
        if row['Low'] < row[col] and row['High'] < row[col]:
            if trend == UP_TREND:
                return NO_TREND
            trend = DOWN_TREND
        elif row['Low'] > row[col] and row['High'] > row[col]:
            if trend==DOWN_TREND:
                return NO_TREND
            trend= UP_TREND
        else:
            return NO_TREND

    return trend or NO_TREND


def wwma(values, n):
    """
     J. Welles Wilder's EMA
    """
    return values.ewm(alpha=1 / n, adjust=False).mean()


def atr(df, n=14):
    data = df.copy()
    high = data["High"]
    low = data["Low"]
    close = data["Close"]
    data['tr0'] = abs(high - low)
    data['tr1'] = abs(high - close.shift())
    data['tr2'] = abs(low - close.shift())
    tr = data[['tr0', 'tr1', 'tr2']].max(axis=1)
    atr = wwma(tr, n)
    return atr

if __name__=='__main__':
    configs=get_configs()
    import pandas as pd
    span = pd.DataFrame({"Candle":[False,False,False,False,False,False,False,False,True],'High':range(1,10),'Low':range(1,10)})
    print(span)
    print(checkCoverage(span))