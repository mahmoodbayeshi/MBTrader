from datetime import datetime,timedelta
import logging
import os,sys
import json
import pandas as pd
import math
from telegram import Update, Bot

def get_bot_token():
    TELEGRAM_API_KEY = ""
    TELEGRAM_GROUP_ID = ""
    return TELEGRAM_API_KEY,TELEGRAM_GROUP_ID

logging.basicConfig()

def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    bot =Bot(get_bot_token()[0])
    bot.sendMessage(chat_id=199043618,text="Uncaught exception "+str(exc_type)+" "+str(exc_value)+"\n"+str(exc_traceback))
    logger.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

sys.excepthook = handle_exception
logger = logging.getLogger("Loss Bot")
logger.setLevel(logging.INFO)
#logger.error("Test Error Logging")
DATA_DIR_PREFIX='data/'

def makedirs():
    dirs=[]
    dirs=map(lambda x:DATA_DIR_PREFIX+x,dirs)
    for dir in dirs:
        os.makedirs(dir, exist_ok=True)

def getDir(path,createNotExist=True,prefix=True):
    if prefix:
        path=DATA_DIR_PREFIX+path
    if createNotExist:
        dir = os.path.dirname(path)
        os.makedirs(dir, exist_ok=True)
    return path

def get_staging():
    return os.getenv('stage','local')

def is_development_stage():
    return get_staging()=='development'

def is_production_stage():
    return get_staging()=='production'

def format_date(format="%b %d, %Y %H:%M:%S", date=None):
    if date is None:
        date =datetime.now()
    return date.strftime(format)

def round_date(date=None,minutes=5):
    if date is None:
        date =datetime.now()
    return date.replace(minute=math.floor(date.minute/minutes)*minutes,second=0)

def proper_round(n):
    c=2
    if n<1 and n>0:
        c+= round((1/n))
        if c>5:
            c=5
    elif n<10:
        c=3
    elif n<100:
        c=2
    elif n<1000:
        c=1
    else:
        c=None

    #print("n:",n,"C:",c)
    return round(n,c)

def to_date(date=None):
    if date is None:
        date =datetime.now()
    return pd.to_datetime(date)


def log(*s, sep=' | ', level=logging.INFO,l=None):
    if l is None:
        l = logger
    try:
        if getIsTest() or check_run_arg("--print-log"):
            print(*s, sep=sep),
        else:
            l.log(msg=sep.join(map(lambda x:str(x),s)),level=level)
    except Exception as e:
        l.error(e,exc_info=True)
        pass

def writeJsonl(file,data,mode='a',prefix=True):
    if not isinstance(data, list):
        data=[data]
    with open(getDir(file,prefix=prefix), mode) as outfile:
        for d in data:
            json.dump(d, outfile)
            outfile.write('\n')

def readJsonl(file,prefix=True):
    try:
        with open(getDir(file,prefix=prefix), 'r') as outfile:
            for l in outfile.readlines():
                yield json.loads(l)
    except Exception as e:
        log(str(e),level=logging.ERROR)
        return []

def writeJson(file,data,prefix=True):
    with open(getDir(file,prefix=prefix), 'w') as outfile:
       json.dump(data,outfile)

def readJson(file,prefix=True):
    try:
        with open(getDir(file,prefix=prefix), 'w') as outfile:
            return json.load(outfile)
    except Exception as e:
        log(str(e),level=logging.ERROR)
    return None

def check_run_arg(key):
    return key in sys.argv[1:]

def getIsTest():
    return check_run_arg('--test')
