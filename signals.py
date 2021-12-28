import matplotlib.pyplot as plt
import mplfinance as mpf
from statics import TG_STATICS_GROUP
from telbot import bot, sendText,get_group_id
from utils import getDir,check_run_arg,log,is_production_stage,is_development_stage,proper_round,format_date,getIsTest
from models import Signal
from datetime import datetime,timedelta
import time
from trader import Trader
import numpy as np
plt.style.use('ggplot')

CANCEL='CANCEL'
NEW_PROFIT='NEW_PROFIT'
NEW_STOP='NEW_STOP'
ORDER= 'ORDER'
DUPLICATE= 'DUPLICATE'

def plot_strategy(data, result=None, limit=20):
    if is_production_stage():
        limit=5
    df = data.copy()[-limit:]
    ohlc = df[['Open', 'High', 'Low', 'Close', 'Volume']]
    ohlc.index = df['Open Time']
    ## create fig
    fig = mpf.figure(figsize=(10, 5), style='binance')
    ax = fig.add_subplot(5, 1, (1, 4))
    av = fig.add_subplot(5, 1, 5, sharex=ax)

    ## draw indicators
    if not is_production_stage():
        ax.plot(df['MA_50'].values, label="MA 50M", color='#c0392b', linestyle='dotted'),
        ax.plot(df['EMA_MIN'].values, label="EMA MIN", color='#f39c12', linestyle='dotted'),
        ax.plot(df['EMA_MAX'].values, label="EMA MAX", color='#8e44ad', linestyle='dotted'),
        if "MA_50H" in df:
            ax.plot(df['MA_50H'].values, label="MA 50H", color='brown')

    if result is not None:
        r = range(df.shape[0] - 1, df.shape[0] + 1, 1)
        ax.fill_between(r, [result['entry']] * 2, [result['stop']] * 2, color='r', alpha=0.5)
        ax.fill_between(r, [result['entry']] * 2, [result['profit']] * 2, color='g', alpha=0.5)
        ax.text(r[1]+0.5, result['entry'], color='#2c3e50', s='$' + str(proper_round(result['entry'])))
        ax.text(r[1]+0.5, result['stop'], color='r', s='$' + str(proper_round(result['stop'])))
        ax.text(r[1]+0.5, result['profit'], color='g', s='$' + str(proper_round(result['profit'])))
        ax.text(r[0]-0.5, result['profit'], color='#2c3e50', s='%' + str(result['percent']))
        ax.text(r[0]-0.5, result['stop'], color='#2c3e50', s='Ratio:' + str(result['ratio']))

    # plot candlestick
    mpf.plot(ohlc, ax=ax, volume=av, type='candlestick')
    ax.legend(loc="upper left")
    ax.axes.xaxis.set_visible(False)
    ax.set_title(result['pair'] + " " + result['market_type'])
    av.set_ylabel("Volume")
    ax.set_ylabel("Price in Binance")
    if is_development_stage():
        fig.suptitle("MB Trader / Loss Bot")
    else:
        fig.suptitle("Top Traders Signal")
    if getIsTest():
        plt.show()
    elif result:
        result['image'] = getDir('signals/imgs/{}_{}_{}.jpg'.format(result['open_time'], result['type'],round(result['stop'])))
        plt.savefig(result['image'], pil_kwargs={'quality': 65})
    return result

def alert_signals(signal) -> None:
    signal = round_signal(signal)
    with open(signal['image'],'rb') as photo:
        caption= ((u'🛑' if signal['type']=='Sell' else '🟢')+u'{type} {pair} \n 📍Entry:${entry}\n❌Stop Loss:${stop}\n☑️Saving Profit:${saving_profit}\n✅Take Profit:${profit}\nRatio:{ratio:0.2f}\nprofit Percent:{percent:0.2f}% \n' +
                 '‼️You must trade and take sole responsibility to evaluate all information provided by this platform and use it at your own risk.‼️\n'
                 'This platform is still beta.\n'+('{open_time}' if is_development_stage() else ""))\
            .format(**signal)
        r= bot.sendPhoto(get_group_id(),photo,caption)
        return r.message_id

def alert_entry(signal,price)-> None:
    Trader.new_order(signal,price)
    signal = round_signal(signal)
    send_alert(to=get_group_id(),t="📍Entry touched.\n Here we go!\n#{}".format(signal['pair']),reply_to_message_id=signal.get('message_id',None))

def alert_loss(signal)-> None:
    Trader.cancel_order(signal=signal)
    signal = round_signal(signal)
    send_alert(to=get_group_id(),t="❌Stop touched.\n Loss is part of trade!\n#{}".format(signal['pair']),reply_to_message_id=signal.get('message_id',None))

def alert_stop_move(signal)-> None:
    Trader.move_stop(signal)
    signal = round_signal(signal)
    send_alert(to=get_group_id(),t='❌Stop Loss Changed to ${}.\n#{}'.format(signal['stop'],signal['pair']),reply_to_message_id=signal.get('message_id',None))

def alert_saving_profit(signal)-> None:
    Trader.save_profit(signal)
    signal = round_signal(signal)
    send_alert(to=get_group_id(),t="✅Saving Profit touched.\n 💰Taking a profit is always good!\n#{}".format(signal['pair']),reply_to_message_id=signal.get('message_id',None))

def alert_profit(signal)-> None:
    Trader.cancel_order(signal=signal)
    signal = round_signal(signal)
    send_alert(to=get_group_id(),t="🚀Take Profit touched.\n 💰Get Your Profit!\n#{}".format(signal['pair']),reply_to_message_id=signal.get('message_id',None))

def alert_new_profit(signal)-> None:
    Trader.new_profit(signal)
    signal = round_signal(signal)
    send_alert(to=get_group_id(),t="🚀🚀 New Target ${}\nPut Stop Loss to ${} \n So far so good! \n 🤑We have new target.\n 💰Why not make more profit? \n#{}".format(signal['profit'],signal['stop'],signal['pair']),reply_to_message_id=signal.get('message_id',None))

def alert_cancel(signal)-> None:
    Trader.cancel_order(signal=signal)
    signal = round_signal(signal)
    send_alert(to=get_group_id(),t="‼️ Canceled.\n#{}".format(signal['pair']),reply_to_message_id=signal.get('message_id',None))

def send_alert(**args):
    log(args['t'])
    if not getIsTest():
        sendText(**args,disable_notification=True)
        time.sleep(1)

def decision(prevs,next):
    for i, s in enumerate(prevs):
        if s.get('profit_check') or s.get('stop_check') or s.get('cancel_check') or s.get('duplicate_check'):
            continue
        if next['type'] != s['type']:
            if is_in_range(s['entry'],next['stop'],next['entry']):
                if (
                        (next['type']=='Buy' and next['entry']<s['stop']) or
                        (next['type']=='Sell' and next['entry']>s['stop'])
                ):
                    if s.get('entry_check'):
                        yield i,NEW_STOP
                        return
                    elif not s.get('cancel_check'):
                        yield i,CANCEL
                        return
        else:
            if s.get('saving_profit_check'):
                if (
                        (next['type'] == 'Buy' and next['entry'] <= s['profit']) or
                        (next['type'] == 'Sell' and next['entry'] >= s['profit'])
                ):
                    yield i,NEW_PROFIT
                    return
            if abs(s.get('entry') - next.get('entry')) < next.get('tolerance'):
                yield i,DUPLICATE
                return

def process_signal(signal,data,config):
    if not signal:
        return
    log("process signal:{}".format(signal))
    if not check_run_arg('--no-plot'):
        signal = plot_strategy(data,signal)
    signal['message_id'] = None
    signal.save()
    signals=list(Signal.find({
        '_id': {'$ne': signal["_id"]},
        'pair': signal['pair'],
        'market_type': signal['market_type'],
        'profit_check': {'$exists': False},
        'stop_check': {'$exists': False},
        'cancel_check': {'$exists': False},
        'duplicate_check': {'$exists': False},
    },sort=[['open_time',-1]]))
    for i,d in decision(signals,signal):
        s = signals[i]
        # if d == NEW_STOP:
        #     tolerance = s['tolerance']
        #     if signal['type'] == "Sell":
        #         tolerance *= -1
        #     s['old_stop'] = s['stop']
        #     s['modifier'] = signal['_id']
        #     s['stop'] = signal['entry'] - tolerance
        #     s.save()
        #     alert_stop_move(s)
        # elif d== NEW_PROFIT:
        #     s['old_profit'] = s['profit']
        #     s['modifier'] = signal['_id']
        #     s['profit'] = signal['profit'] - signal['tolerance']
        #     s.save()
        #     alert_new_profit(s)
        if d== CANCEL:
            s['cancel_check'] = True
            s.save()
            alert_cancel(s)
        else:#duplicate and new_profit
            log("Ignore Duplicate Signal :", s, signal)
            signal.duplicate_check = True
            signal.duplicated_id = s['_id']
            signal.save()
            return
    if not getIsTest():
        signal['message_id'] = alert_signals(signal)
    else:
        signal['message_id'] = None
    signal.save()

last_pair_prices={}

def trigger_signals(pair,mark_price,market_type):
    key =pair+'_'+market_type
    if key not in last_pair_prices:
        last_pair_prices[key]=mark_price
        return
    lt = max(last_pair_prices[key],mark_price)
    gt = min(last_pair_prices[key],mark_price)
    signals=list(Signal.find({
        'pair': pair,
        'market_type':market_type,
        '$or':[
            {'stop': {'$lt': lt,'$gte':gt}},
            {'profit': {'$lt': lt,'$gte':gt}},
            {'saving_profit': {'$lt': lt,'$gte':gt}},
            {'entry': {'$lt': lt,'$gte':gt}},
        ],
        'profit_check': {'$exists': False},
        'stop_check': {'$exists': False},
        'cancel_check': {'$exists': False},
        'duplicate_check': {'$exists': False},
    },
    sort=[['open_time',-1]]))
    for signal in signals:
        set_signal_ticks(signal,{"Low":gt,"High":lt,"Price":mark_price},mark_price)
    last_pair_prices[key]=mark_price


def check_collision(candle,price):
    return candle['High'] >= price and candle['Low'] <= price

def is_in_range(p,l,h):
    return p <= max(l,h) and p>= min(l,h)

def set_signal_ticks(s,candle,price):
    if not s.get('entry_check'):
        if check_collision(candle, s['entry']):
            s["entry_check"] = True
            s.save()
            alert_entry(s,price)
            log('entry_check :{}', s)
    if check_collision(candle, s['stop']):
        if s.get('entry_check'):
            s["stop_check"] = True
            s.save()
            log('stop_check :{}', s)
            alert_loss(s)
        else:
            s["cancel_check"] = True
            s.save()
            log('cancel_check :{}', s)
            alert_cancel(s)
    if not s.get('saving_profit_check') and check_collision(candle, s.get('saving_profit')):
        s["saving_profit_check"] = True
        s.save()
        log('saving_profit_check :{}', s)
        alert_saving_profit(s)
    if not s.get('profit_check') and check_collision(candle, s['profit']):
        s["profit_check"] = True
        s.save()
        log('profit_check :{}', s)
        alert_profit(s)

def round_signal(signal):
    r =dict()
    for k,v in signal:
        if isinstance(v,float):
            r[k]=proper_round(v)
        else:
            r[k]=v
    return r

def makeSignal(type, entry, stop, saving_profit, profit, candle, tolerance, config):
    if abs(stop - entry)<tolerance:
        return None
    s = Signal()
    s['entry'] = entry
    s['stop'] = stop
    s['profit'] = profit
    s['type'] = type
    s['open_time'] = candle['Open Time']
    s['tolerance'] = tolerance
    s['saving_profit'] = saving_profit
    s['ratio'] = round(abs(entry - profit) / abs(stop - entry), 1)
    s['percent'] = round(abs(profit - entry) / entry, 4) * 100
    s['market_type'] = config['market_type']
    s['current_price'] = candle['Close']
    s['pair'] = config['pair']
    return s

def performance_static():
    statics = {}
    today = datetime.today()
    yesterday = today - timedelta(days=1)
    signal =Signal()
    total_signals=Signal.as_dataframe(Signal.find({
            'open_time':{'$gte':yesterday},
            signal.entry_check:True
        },sort=(('open_time',-1),)))

    losses =total_signals[total_signals[signal.stop_check] ==True]
    profits =total_signals[total_signals[signal.profit_check] ==True]

    statics['count']= len(total_signals)
    statics['wins']= len(profits)
    statics['stops']=len(losses)
    statics['entries']=len(total_signals[total_signals[signal.entry_check] ==True])
    statics['cancels']=len(total_signals[total_signals[signal.cancel_check] ==True])
    statics['saving_profits']=len(total_signals[total_signals[signal.saving_profit_check]==True])
    statics['new_profit']=len(total_signals[~total_signals[signal.old_profit].isna()])
    statics['new_stop']=len(total_signals[~total_signals[signal.old_stop].isna()])
    if statics['entries']>0:
        statics['win_rate']= round(statics['wins']/statics['entries'],2)*100
    if statics['entries']>0:
        statics['safe_win_rate']= round(statics['saving_profits']/statics['entries'],2)*100
    statics['total_loss']= proper_round(sum(abs(losses['entry']-losses['stop'])))
    statics['total_profit']= proper_round(sum(abs(profits['entry']-profits['profit'])))
    try:
        statics['sharp_ratio']=((statics['total_profit']-statics['total_loss'])/total_signals['current_price'].std())* np.sqrt(252)
        if statics['sharp_ratio']:
            statics['sharp_ratio']= proper_round(statics['sharp_ratio'])
    except:
        pass

    s = '\n'.join(["{}:{}".format(k.upper().replace('_',' '), v) for k,v in statics.items()])
    log("daily statics",s)
    r= sendText("#Daily_Analysis \n {:<20}\n{}".format(format_date(),s),to=TG_STATICS_GROUP)
    log("send result",r)

if __name__ =='__main__':
    #s = Signal.find_one(sort=(('open_time',-1)))
    #print("Last Signal",s.__dict__())
    if check_run_arg('--daily-check'):
        performance_static()

