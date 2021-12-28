from utils import log,is_production_stage,format_date
from swing5 import analyze
from signals import process_signal
from telbot import sendText
import sys

def test(pair="BTCUSDT"):
    i=0
    while True:
        log("-----------" * 6)
        log("ignore_count:", i)
        result,data,config=analyze(pair=pair, ignore_count=i)
        process_signal(result,data,config)
        if result:
            break
        i+=1

def get_pairs():
    pairs = ['BTCUSDT', 'ETHUSDT','BNBUSDT'] #, 'DOGEUSDT', 'XRPUSDT', 'ADAUSDT', 'SOLUSDT', 'MATICUSDT', 'LTCUSDT'
    return pairs

def start_analyze():
    pairs=get_pairs()
    l="Start Analyzing at {},{}".format(format_date(),pairs)
    log(l)
    sendText(l)
    args = sys.argv[1:]
    if '--test' in args:
        pairs = pairs[0:1]
        for pair in pairs:
            test(pair=pair)
            log("--------------" * 7)
    elif '--realtest' in args:
        for pair in pairs:
            test(pair=pair)
            log("--------------" * 7)
    else:
        for pair in pairs:
            process_signal(*analyze(pair=pair))
            log("--------------"*7)

if __name__ == '__main__':
    start_analyze()
