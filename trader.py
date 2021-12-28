from datetime import datetime

from binance import Client
import sys

from models import Signal, Account
from utils import check_run_arg,is_production_stage,log as base_log
from binance_f import RequestClient
from models import Orders,ObjectId
from telbot import sendText
from datetime import datetime
import json
import time

import logging
logger=logging.getLogger("Trader API")
logger.setLevel(logging.DEBUG)

def log(*s, sep=' | ', level=logging.INFO):
    base_log(*s,sep=sep,level=level,l=logger)

ALLOWED_TRADE_PAIRS=['BTCUSDT']#,'BNBUSDT','ETHUSDT'

class Trader():
    accounts = {}
    clients = {}
    precisions={}

    @classmethod
    def test(cls):
        signal = Signal()
        signal.delete_many({})
        signal[signal.entry] = 40000.0
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
        signal['_id']=ObjectId()
        order =cls.new_order(signal,signal[signal.entry])
        for i in range(3):
            log("wait {}".format(i+1))
            time.sleep(1)
        if order is not None:
            cls.cancel_order(orders=[order])

    @classmethod
    def seed_accounts(cls) -> None:
        Account.delete_many({})
        account = Account()
        account[account.name] = "mahmood"
        account[account.tg_id] = -1
        account[account.publickey] = ""
        account[account.privatekey] = ""
        account[account.active] = True
        account[account.exchange] = "Binance"
        account[account.config] = []
        # account[account.client]
        account.save()
        log('accounts seeded')

    @classmethod
    def get_accounts(cls):
        if not cls.accounts:
            accounts = Account.find({'active': True})
            for a in accounts:
                cls.accounts[str(a['_id'])]=a
                cls.clients[str(a['_id'])]=Client(a[a.publickey], a[a.privatekey])
        return cls.accounts

    @classmethod
    def new_order(cls, signal,market_price):
        if signal[signal.pair] not in ALLOWED_TRADE_PAIRS:
            log('ignore trade for {}'.format(signal[signal.pair]))
            return
        cls.get_accounts()
        if signal[signal.market_type] == "Futures":
            return cls.new_order_futures(signal,market_price)
        return None

    @classmethod
    def new_order_futures(cls, signal,market_price):
        if not cls.canTrade():
            return
        log("new order futures ")

        log(len(cls.clients))
        for key,client in cls.clients.items():
            account = cls.accounts[key]
            order = cls.make_futures_batch_order(account=account,signal=signal, client=client,market_price=market_price)
            return order
            # else:
            # cls.clients[i].

        return None

    @classmethod
    def get_symbol_precision(cls, symbol):
        if not cls.precisions:
            requestClient = RequestClient()
            # items = client.get_exchange_info()
            items = requestClient.get_exchange_information()
            for item in items.symbols:
                if item.symbol == symbol:
                    cls.precisions[symbol]= {
                        "pricePrecision":item.pricePrecision,
                        "quantityPrecision":item.quantityPrecision,
                    }
        return cls.precisions[symbol] if symbol in cls.precisions else {"pricePrecision":0,"quantityPrecision":0}

    @classmethod
    def make_futures_batch_order(cls,account,signal, client,market_price):
        try:
            res = client.futures_change_margin_type(symbol=signal[signal.pair], marginType='ISOLATED')
        except:
            log("no need change of margin type")

        precision = cls.get_symbol_precision(signal[signal.pair])
        coin_price_round_precision = precision['pricePrecision']
        coin_amount_round_precision = precision['quantityPrecision']

        leverage = cls.calculate_leverage(signal=signal, client=client)
        client.futures_change_leverage(symbol=signal[signal.pair], leverage=leverage)
        position_size = cls.calculate_position_size(signal=signal,market_price=market_price,precision=precision, client=client,leverage=leverage)
        coin_amount = float(round(position_size, coin_amount_round_precision))
        log("coin amount",coin_amount,"----","position_size",position_size)
        signal[signal.entry] = float(round(signal[signal.entry], coin_price_round_precision))
        signal[signal.stop] = float(round(signal[signal.stop], coin_price_round_precision))
        signal[signal.profit] = float(round(signal[signal.profit], coin_price_round_precision))
        signal[signal.saving_profit] = float(round(signal[signal.saving_profit], coin_price_round_precision))
        sendText('Binance COIN: {} {} {} at ${}'.format(signal['type'],coin_amount,signal['pair'],signal['entry']))
        if coin_amount == 0:
            log("not enough balance")
            return None
        if position_size*signal[signal.entry]<5:
            log("not enough balance for margin ")
            return None

        timestamp = int(datetime.now().timestamp())*1000
        orders=[
            #order
            {
                "symbol":signal[signal.pair],
                "side":cls.get_side(signal),
                "type": Client.FUTURE_ORDER_TYPE_MARKET,
                "quantity":coin_amount,
            },
            #stop loss
            {
                "symbol": signal[signal.pair],
                "side": cls.get_side(signal,True),
                "type": Client.FUTURE_ORDER_TYPE_STOP_MARKET,
                "closePosition": True,
                "stopPrice": signal[signal.stop],
            },
            #saving profit
            {
                "symbol": signal[signal.pair],
                "side": cls.get_side(signal, True),
                "type": Client.FUTURE_ORDER_TYPE_LIMIT,
                "reduceOnly": True,
                "quantity": round(coin_amount/2,coin_amount_round_precision),
                "price": signal[signal.saving_profit],
                "timeInForce":"GTC",
            },
            #profit
            {
                "symbol": signal[signal.pair],
                "side": cls.get_side(signal, True),
                "type": Client.FUTURE_ORDER_TYPE_TAKE_PROFIT_MARKET,
                "stopPrice": signal[signal.profit],
                "closePosition": True,
                "timeInForce": "GTC",
            }
        ]
        log('Trade Orders',orders)
        response = cls.futures_place_batch_order(client,orders)
        log("Trade Response",response)
        orderLabels= ['entry','stop','saving_profit','profit']
        orderIds= []
        hasError=False
        for i,r in enumerate(response):
            if r is not None and 'orderId' in r:
                orderIds.append(r['orderId'])
            else:
                hasError=True
        sendText('Binance Place Orders: {} for {}'.format(signal,dict(zip(orderLabels, orderIds))))
        order = Orders()
        order[order.account_id]=account['_id']
        order[order.signal_id]=signal['_id']
        order[order.order_ids]=dict(zip(orderLabels, orderIds))
        order[order.status]="entry_check"
        order[order.pair]=signal[signal.pair]
        order[order.time]=datetime.now()
        if hasError:
            log('Cancel due to error')
            cls.cancel_order(orders=[order])
            return None
        else:
            order.save()
        return order

    @classmethod
    def futures_place_batch_order(cls,client,orders):
        results=[]
        for order in orders:
            try:
                results.append(client.futures_create_order(**order))
            except Exception as e:
                results.append(None)
                sendText("error in order:"+str(order)+str(e))
                log("error in order:",order,e)
        return results

    @classmethod
    def get_side(cls,signal,reverse=False):
        r = signal['type']=="Buy"
        if reverse:
            r =not r
        if r:
            return "BUY"
        else:
            return "SELL"

    @classmethod
    def get_futures_usdt_balance(cls, client):
        balances = client.futures_account_balance()
        usdt_balance = 0
        for asset in balances:
            if asset['asset'] == 'USDT':
                return float(asset['balance'])
        return float(usdt_balance)

    @classmethod
    def calculate_position_size(cls, signal,precision,leverage,market_price, client):
        minimum = 0.1**precision['quantityPrecision']*2 #for risk free purpose
        usdt_balance = cls.get_futures_usdt_balance(client)
        if usdt_balance<(minimum*market_price/leverage):
            return 0
        asset_percent = 0.02
        cost = usdt_balance * asset_percent
        res = cost*leverage/market_price
        return max(res,minimum)

    @classmethod
    def calculate_leverage(cls, signal, client):
        return 20


    @classmethod
    def canTrade(cls):
        return not check_run_arg('--no-trade') and not check_run_arg('--test') and not check_run_arg('--realtest')

    @classmethod
    def change_margin_type(cls):
        return False

    @classmethod
    def move_stop(cls, signal):
        if not cls.canTrade():
            return

        precision = cls.get_symbol_precision(signal[signal.pair])
        coin_price_round_precision = precision['pricePrecision']
        coin_amount_round_precision = precision['quantityPrecision']
        orders = Orders.find({Orders.signal_id: signal['_id']})
        for order in orders:
            client = cls.clients[str(order[order.account_id])]
            o = {
                "symbol": signal[signal.pair],
                "side": cls.get_side(signal, True),
                "type": Client.FUTURE_ORDER_TYPE_STOP_MARKET,
                "closePosition": True,
                "reduceOnly": True,
                "stopPrice": round(signal[signal.stop],coin_amount_round_precision),
                "newOrderRespType": 'ACK',
                "timeInForce": 'GTC',
            }
            res = client.futures_create_order(**o)
            if order['order_ids']['stop'] >= 0:
                try:
                    client.futures_cancel_order(symbol=signal[signal.pair], orderId=order['order_ids']['stop'])
                except Exception as e:
                    log(e)
            if 'orderId' in res:
                order['order_ids']['stop'] = res['orderId']
            else:
                log('Trade error in Update Stop', res['msg'])
                order['order_ids']['stop'] = res['code']
            order.save()
        return True

    @classmethod
    def new_profit(cls, signal):
        if not cls.canTrade():
            return

        precision = cls.get_symbol_precision(signal[signal.pair])
        coin_price_round_precision = precision['pricePrecision']
        coin_amount_round_precision = precision['quantityPrecision']
        orders = Orders.find({Orders.signal_id: signal['_id']})
        for order in orders:
            client = cls.clients[str(order[order.account_id])]

            newSaving =signal[signal.saving_profit]
            if signal[signal.type]=='Buy':
                newSaving -= 0.01*newSaving
            else:
                newSaving += 0.01*newSaving
            o = [
                {
                    "symbol": signal[signal.pair],
                    "side": cls.get_side(signal, True),
                    "type": Client.FUTURE_ORDER_TYPE_STOP_MARKET,
                    "closePosition": True,
                    "reduceOnly": True,
                    "stopPrice": round(signal[signal.profit],coin_amount_round_precision),
                    "newOrderRespType": 'ACK',
                    "timeInForce": 'GTC',
                },
                {
                    "symbol": signal[signal.pair],
                    "side": cls.get_side(signal, True),
                    "type": Client.FUTURE_ORDER_TYPE_STOP_MARKET,
                    "closePosition": True,
                    "reduceOnly": True,
                    "stopPrice": round(newSaving,coin_amount_round_precision),
                    "newOrderRespType": 'ACK',
                    "timeInForce": 'GTC',
                }
            ]
            response = client.futures_place_batch_order(batchOrders=o)
            if order['order_ids']['stop'] >= 0:
                try:
                    client.futures_cancel_order(symbol=signal[signal.pair], orderId=order['order_ids']['stop'])
                except Exception as e:
                    log(e)
            orderIds=[]
            orderLabels=['stop','profit']
            for i, r in enumerate(response):
                if 'orderId' in r:
                    orderIds.append(r['orderId'])
                else:
                    log("Trader Error in {}".format(orderLabels[i]), r['msg'])
                    orderIds.append(r['code'])
            order[order.order_ids]=order[order.order_ids].update(dict(zip(orderLabels,orderIds)))
            order.save()
        return True

    @classmethod
    def save_profit(cls, signal):
        if not cls.canTrade():
            return
        orders = Orders.find({Orders.signal_id:signal['_id']})

        precision = cls.get_symbol_precision(signal[signal.pair])
        coin_price_round_precision = precision['pricePrecision']
        coin_amount_round_precision = precision['quantityPrecision']
        for order in orders:
            client = cls.clients[str(order[order.account_id])]
            newStop =signal[signal.entry]
            if signal[signal.type]=='Buy':
                newStop+=0.01*newStop
            else:
                newStop-=0.01*newStop
            newStop = round(newStop,coin_amount_round_precision)
            o={
                    "symbol": signal[signal.pair],
                    "side": cls.get_side(signal, True),
                    "type": Client.FUTURE_ORDER_TYPE_STOP_MARKET,
                    "closePosition": True,
                    "reduceOnly": True,
                    "stopPrice": newStop,
                    "newOrderRespType": 'ACK',
                    "timeInForce": 'GTC',
                }
            res= client.futures_create_order(**o)
            if order['order_ids']['stop'] >=0:
                try:
                    client.futures_cancel_order(symbol=signal[signal.pair],orderId=order['order_ids']['stop'])
                except Exception as e:
                    log(e)
            if 'orderId' in res:
                order['order_ids']['stop']= res['orderId']
            else:
                log('Trade error in Update Stop',res['msg'])
                order['order_ids']['stop'] = res['code']
            order.save()
        return True

    @classmethod
    def cancel_all_order(cls, signal=None,orders=None):
        if not cls.canTrade():
            return
        if signal:
            a = Signal.find({"pair": signal['pair']})
            orders = Orders.find({"_id": {"$in": [r['_id'] for r in a]}})
        elif not orders:
            orders=[]
        for order in orders:
            client = cls.clients[str(order[order.account_id])]
            ids =list(filter(lambda x:x>=0,order['order_ids'].values()))
            for id in ids:
                try:
                    client.futures_cancel_order(symbol=order['pair'], orderId=id)
                except Exception as e:
                    log("error in cancel order:", order['pair'], id, e)
        return True

    @classmethod
    def cancel_order(cls, signal=None,orders=None):
        if not cls.canTrade():
            return
        if signal:
            orders = Orders.find({"signal_id":signal._id})
        elif not orders:
            orders=[]
        for order in orders:
            client = cls.clients[str(order[order.account_id])]
            ids =list(filter(lambda x:x>=0,order['order_ids'].values()))
            for id in ids:
                try:
                    res = client.futures_cancel_order(symbol=order['pair'], orderId=id)
                    print("res",res)
                except Exception as e:
                    log("error in cancel order:", order['pair'], id, e)

        return True

    @classmethod
    def get_clients(cls):
        return cls.clients

    @classmethod
    def start_trade(cls):
        if not cls.canTrade():
            return
        cls.get_accounts()
        cls.get_symbol_precision("BTCUSDT")

if __name__ == '__main__':
    if check_run_arg('--seed-accounts'):
        Trader.seed_accounts()
    if check_run_arg('--test'):
        Trader.test()
    else:
        o = Orders.find_one({},sort=[['_id',-1]])

        print("o",o)
        Trader.get_accounts()
        Trader.cancel_order(orders=[o])
