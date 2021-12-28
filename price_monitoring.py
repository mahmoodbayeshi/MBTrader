import logging
from binance_f import SubscriptionClient
from binance_f.model import SubscribeMessageType
from binance_f.exception.binanceapiexception import BinanceApiException
from analyze import get_pairs
from signals import trigger_signals
from utils import log,is_production_stage
from trader import Trader

logger = logging.getLogger("binance-futures")
logger.setLevel(level=logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)

sub_client = SubscriptionClient()


def callback(data_type: 'SubscribeMessageType', event: 'any'):
    if data_type == SubscribeMessageType.RESPONSE:
        #print("Event ID: ", event)
        pass
    elif  data_type == SubscribeMessageType.PAYLOAD:
        item = event
        # if item.symbol == 'BTCUSDT':
        #     log(item.symbol,item.markPrice)
        trigger_signals(pair=item.symbol,mark_price=item.markPrice,market_type="Futures")
    else:
        #print("Unknown Data:")
        pass


def error(e: 'BinanceApiException'):
    log("Price Monitoring",e.error_code + e.error_message)

def start_monitoring():
    Trader.start_trade()
    for pair in get_pairs():
        sub_client.subscribe_mark_price_event(pair.lower(),callback,error)

if __name__ == '__main__':
    start_monitoring()