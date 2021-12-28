import logging

from telegram import Update, Bot
from telegram.ext import Updater, CommandHandler, CallbackContext
import logging, os
from utils import is_production_stage, is_development_stage, get_staging, log, getIsTest,get_bot_token
from models import Account
from binance import Client

TELEGRAM_API_KEY,TELEGRAM_GROUP_ID=get_bot_token()

logger = logging.getLogger("MBTrader Bot")

bot = Bot(TELEGRAM_API_KEY)


# Define a few command handlers. These usually take the two arguments update and
# context.
def start(update: Update, context: CallbackContext) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    update.message.reply_markdown_v2(
        fr'Hi {user.mention_markdown_v2()}\!',
    )


def get_account(update: Update) :
    """Send a message when the command /balance is issued.
         Returns:
            :class:`models.Account`: On success, instance representing the user account.
            :none: On Failure, instance representing the user account.
        """
    user = update.effective_user
    account = Account.find_one({"tg_id":user.id})
    if account is None:
        update.message.reply_markdown_v2(
            fr'your account not found!',
        )
        return None
    return account


def get_balance(update: Update, context: CallbackContext) -> None:
    """Send a message when the command /balance is issued."""
    account = get_account(update)
    if account is not None:
        client = Client(account[account.publickey], account[account.privatekey])
        balances = client.futures_account_balance()
        usdt_balance = "unknown"
        for asset in balances:
            if asset['asset'] == 'USDT':
                usdt_balance= (asset['balance'])
        update.message.reply_text(
            fr'your futures balance is ${usdt_balance}!',
        )

def tg_updater() -> None:
    """Start the bot."""

    sendText("STAGING:" + get_staging())
    # Create the Updater and pass it your bot's token.
    updater = Updater(TELEGRAM_API_KEY)

    # Get the dispatcher to register handlers
    dispatcher = updater.dispatcher

    # on different commands - answer in Telegram
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("balance", get_balance))

    # on non command i.e message - echo the message on Telegram
    # dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, echo))

    # Start the Bot
    updater.start_polling()

    # Run the bot until you press Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()


def sendText(t="i'm alive", to=199043618, reply_to_message_id=None, disable_notification=False):
    try:
        if not getIsTest():
            return bot.sendMessage(to, t, reply_to_message_id=reply_to_message_id,
                                   disable_notification=disable_notification)
    except:
        log("error in sending message to {}".format(to))


def get_group_id():
    return TELEGRAM_GROUP_ID

if __name__ == '__main__':
    tg_updater()
