from varname import nameof
from bson.objectid import ObjectId
from mongo import Base


class Signal(Base):
    collection = 'signals'

    type = ['Sell', 'Buy']
    entry = 'float'
    stop = 'float'
    profit = 'float'
    tolerance = 'float'
    saving_profit = 'float'
    ratio = 'float'
    percent = 'float'
    current_price = 'float'
    market_type = ['Futures',"Spot"]
    open_time = 'float'
    old_profit = 'float'
    old_stop = 'float'
    entry_check = 'bool'
    stop_check = 'bool'
    cancel_check = 'bool'
    duplicate_check = 'bool'
    duplicated_id = 'object_id|nullable'
    saving_profit_check = 'bool'
    profit_check = 'bool'
    pair = 'str'
    image = 'str|nullable'
    message_id = 'int|nullable'
    modifier = 'object_id|nullable'


class Account(Base):
    collection = 'accounts'
    name = 'str'
    tg_id = 'int'
    exchange = ['Binance']
    publickey = 'str'
    privatekey = 'str'
    config = 'list|nullable'
    active = 'bool'


class Orders(Base):
    collection = 'orders'
    account_id = 'object_id'
    signal_id = 'object_id'
    order_ids = 'dict'
    status = 'str'
    pair = 'str'
    time = 'datetime'



if __name__ == '__main__':
    s = Signal()
    print(s.collection)
    print(s.entry)