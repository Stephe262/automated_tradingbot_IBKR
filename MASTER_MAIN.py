from ib_insync import *
import email
import imaplib
import copy
import datetime
import slack
from pathlib import Path
from dotenv import load_dotenv
import pytz
import time
import pickle
import os
import ssl
ssl._create_default_https_context = ssl._create_unverified_context

#### Variables ####
# Number of Stocks Held Dictionary
num_stocks_held = {"account_id": 0, "account_id": 0, "account_id": 0, "account_id": 0}

# Dictionary to store the short_stocks being held and their Quantity and days held
short_stocks = {"account_id": [[None, None, None], [None, None, None]], "account_id": [[None, None, None], [None, None, None], [None, None, None],
                                                          [None, None, None], [None, None, None], [None, None, None]]}
# Dictionary to store the long stocks being held and their Quantity and days held so far
long_stocks = {"account_id": [[None, None, None], [None, None, None]], "account_id": [[None, None, None], [None, None, None]]}

# Funds per Account
total_funds = {"account_id": None, "account_id": None, "account_id": None, "account_id": None}

# New Tickers with their open price
new_ticker = {"account_id": [[None, None]], "account_id": [[None, None]], "account_id": [[None, None]],
              "account_id": [[None, None], [None, None], [None, None], [None, None], [None, None], [None, None]]}

# Load env file for Slack
env_path = Path('.') / '.env'
load_dotenv(dotenv_path=env_path)

# # Set the directory path to the desktop for Pickling
desktop_path = os.path.join(os.path.expanduser("~"), "Where the folder is stored")
folder_name = "name of your folder for your pickled objects"
folder_path = os.path.join(desktop_path, folder_name)

try:
    with open(os.path.join(folder_path, "short_stocks.pickle"), "rb") as f:
        short_stocks = pickle.load(f)
    with open(os.path.join(folder_path, "long_stocks.pickle"), "rb") as f:
        long_stocks = pickle.load(f)
except Exception as e:
    pass

# Connect to TWS
ib = IB()
ib.connect('127.0.0.1', 7497, clientId=1, timeout=1)

def handle_alerts(account_id, email_txt):
    def get_body(msg):
        if msg.is_multipart():
            return get_body(msg.get_payload(0))
        else:
            return msg.get_payload(None, True)

    imap_server = 'imap.gmail.com'
    email_address = "your_email"
    password = "gmail_password" #this is not your normal password
    mail = imaplib.IMAP4_SSL(imap_server)
    mail.login(email_address, password)
    mail.select("Inbox")
    key = "FROM"
    value = 'contact@genovest.com' #I use Genovest to create my trading strategies and then parse my emails every morning where I am notified which stocks to sell/buy

    # Get the latest email
    status, data = mail.search(None, key, value)
    mail_id_list = data[0].split()
    latest_email_id = mail_id_list[-1]
    status, data = mail.fetch(latest_email_id, "(RFC822)")
    raw = email.message_from_bytes(data[0][1])
    byte_body = (get_body(raw))
    string_body = byte_body.decode('utf-8')
    lines = string_body.split('\n')

    # Parse out ticker symbol
    count = 1
    for i, line in enumerate(lines):
        if email_txt in line:
            positions = int(lines[i + 1][11])
            while count <= positions:
                symbol = (lines[i + 1 + count])
                symbol = symbol.strip().split(" ")[0]
                new_ticker[account_id][count - 1][0] = symbol
                print(f'{symbol} for {email_txt}')
                if new_ticker[account_id][count - 1][0] is not None:
                    contract = Stock(symbol, "smart", "usd")
                    ib.qualifyContracts(contract)
                    bars = ib.reqHistoricalData(contract, endDateTime='', durationStr='30 S',
                                                barSizeSetting='1 secs', whatToShow='Trades', useRTH=False)
                    # convert to pandas dataframe:
                    df = util.df(bars)
                    todayOpen = df.iloc[0].open
                    print(f"Today\'s open for {symbol} is: ${todayOpen}")
                    new_ticker[account_id][count - 1][1] = todayOpen
                    count += 1
                else:
                    pass
        else:
            pass
          # These are my long strategy accounts
    if account_id == 'account_id' or account_id == 'account_id':
        total_stocks = 0
        for key, value in long_stocks.items():
            if key == account_id:
                for current_stock in value:
                    if current_stock[0] is not None:
                        total_stocks += 1
                # print(f"Total stocks held for {key} is {total_stocks}")
                num_stocks_held[key] = total_stocks
          # These are my short strategy accounts
    elif account_id == 'account_id' or account_id == 'account_id':
        total_stocks = 0
        for key, value in short_stocks.items():
            if key == account_id:
                for current_stock in value:
                    if current_stock[0] is not None:
                        total_stocks += 1
                # print(f"Total stocks held for {key} is {total_stocks}")
                num_stocks_held[key] = total_stocks

    # Account Function for funds
    def account_portfolio(account_id):
        funds = ib.accountValues(account_id)
        for x in range(len(funds)):
            data_name = str(funds[x][1])
            data_account_value = str(funds[x][2])
            if data_name == "TotalCashValue":
                if account_id == 'account_id':
                    data_account_value = float(data_account_value)
                    print(f'{email_txt} has: ${data_account_value}')
                    if num_stocks_held[account_id] == 6:
                        total_funds[account_id] = 0
                    else:
                        data_account_value = float(data_account_value)
                        total_funds[account_id] = round(data_account_value / (6 - num_stocks_held[account_id]), 2)
                else:
                    print(f'{email_txt} has: ${data_account_value}')
                    if num_stocks_held[account_id] == 2:
                        total_funds[account_id] = 0
                    else:
                        data_account_value = float(data_account_value)
                        total_funds[account_id] = round(data_account_value / (2 - num_stocks_held[account_id]), 2)
            pass
    # Run the function from above
    account_portfolio(account_id)

    def investing_strategy(account_id):
######################################### LONG STRATEGY #########################################
        now = datetime.datetime.now()
        today = now.strftime("%Y%m%d")
        client = slack.WebClient(token=os.environ['SLACK_TOKEN'])
        if account_id == 'account_id' or account_id == 'account_id':
            for idx, (key1, value1) in enumerate(new_ticker.items()):
                if key1 == account_id:
                    for new_stock, new_stock_price in value1:
                        found_in_stocks = False
                        for idx, (key2, value2) in enumerate(long_stocks.items()):
                            if key2 == account_id:
                                for idx, values in enumerate(value2):
                                    if new_stock == values[0] and new_stock is not None:
                                        found_in_stocks = True
                                        # HOLD
                                        if new_stock is not None:
                                            print(f'HELD {new_stock}')
                                            # Post the message to Slack
                                            hold_message = f"HOLD {new_stock} and reset timer to 0 for {email_txt}"
                                            client.chat_postMessage(channel="#updates", text=hold_message)
                                            long_stocks[account_id][idx][2] = 0
                                            break
                        # BUY
                        if not found_in_stocks and new_stock is not None:
                            for key3, value3 in long_stocks.items():
                                if key3 == account_id:
                                    for idx, (ticker, quant, held) in enumerate(value3):
                                        if ticker is None:
                                            limit_price = round((new_ticker[account_id][0][1] * .9985), 2)
                                            total_quant = int((float(total_funds[account_id]) * .95) / limit_price)
                                            # BUY!
                                            contract = Stock(new_stock, 'SMART', 'USD')
                                            order = LimitOrder("BUY", totalQuantity=total_quant, account=account_id,
                                                               lmtPrice=limit_price)
                                            ib.qualifyContracts(contract)
                                            ib.placeOrder(contract=contract, order=order)
                                            # Post the message to Slack
                                            buy_message = f"BOUGHT {total_quant} shares of {new_stock} at ${limit_price} for {email_txt}"
                                            client.chat_postMessage(channel="#updates", text=buy_message)
                                            print(buy_message)
                                            # Assign New Values to Dicts
                                            long_stocks[account_id][idx][0] = new_stock
                                            long_stocks[account_id][idx][1] = total_quant
                                            long_stocks[account_id][idx][2] = 0
                                            break

            # CLOSE OR ADD DAY TO TIMER
            for key, value in long_stocks.items():
                if key == account_id:
                    for idx, (current_stock, current_stock_quantity, current_day_held) in enumerate(value):
                        if current_day_held == 2:
                            # CLOSE POSITION
                            total_quant = long_stocks[account_id][idx][1]
                            contract = Stock(current_stock, "smart", "usd")
                            ib.qualifyContracts(contract)
                            order = MarketOrder("SELL", totalQuantity=total_quant, account=account_id)
                            order.conditions = [TimeCondition(isMore=True, time=f'{today} 13:57:00 America/Denver')]
                            ib.placeOrder(contract, order)
                            close_message = f"CLOSING {total_quant} shares of {current_stock} " \
                                            f"at market price for {email_txt}"
                            client.chat_postMessage(channel="#updates", text=close_message)  # Slack Message
                            print(close_message)
                            # Reassign values to None
                            long_stocks[account_id][idx][0] = None
                            long_stocks[account_id][idx][1] = None
                            long_stocks[account_id][idx][2] = None
                        else:
                            if current_stock is not None:
                                # ADD DAY TO TIMER
                                long_stocks[account_id][idx][2] = long_stocks[account_id][idx][2]+1
                                timer_add_message = f"Added 1 day to the Hold Timer for {current_stock}"
                                client.chat_postMessage(channel="#updates", text=timer_add_message)
                                print(timer_add_message)
                            else:
                                pass
######################################### SHORTING STRATEGY ###############################################
        else:
            for idx, (key1, value1) in enumerate(new_ticker.items()):
                if key1 == account_id:
                    for new_stock, new_stock_price in value1:
                        found_in_stocks = False
                        for idx, (key2, value2) in enumerate(short_stocks.items()):
                            if key2 == account_id:
                                for idx, values in enumerate(value2):
                                    if new_stock == values[0] and new_stock is not None:
                                        found_in_stocks = True
                                        # HOLD
                                        if new_stock is not None:
                                            print(f'HELD {new_stock}')
                                            # Post the message to Slack
                                            hold_message = f"HOLD {new_stock} and reset timer to 0 for {email_txt}"
                                            client.chat_postMessage(channel="#updates", text=hold_message)
                                            short_stocks[account_id][idx][2] = 0
                        # SHORT
                        if not found_in_stocks and new_stock is not None:
                            print(new_stock)
                            print(new_ticker[account_id])
                            for key3, value3 in short_stocks.items():
                                if key3 == account_id:
                                    for idx, (ticker, quant, held) in enumerate(value3):
                                        if ticker is None:
                                            price = [tick_price[1] for tick_price in new_ticker[account_id] if tick_price[0] == new_stock]
                                            print(price)
                                            limit_price = round((price[0] * 1.0015), 2)
                                            total_quant = int((float(total_funds[account_id]) * .95) / limit_price)
                                            # BUY!
                                            contract = Stock(new_stock, 'SMART', 'USD')
                                            order = LimitOrder("SELL", totalQuantity=total_quant, account=account_id,
                                                               lmtPrice=limit_price)
                                            ib.qualifyContracts(contract)
                                            ib.placeOrder(contract=contract, order=order)
                                            # Post the message to Slack
                                            short_message = f"SHORTED {total_quant} shares of {new_stock} at ${limit_price} for {email_txt}"
                                            client.chat_postMessage(channel="#updates", text=short_message)
                                            print(short_message)
                                            # Assign New Values to Dicts
                                            short_stocks[account_id][idx][0] = new_stock
                                            short_stocks[account_id][idx][1] = total_quant
                                            short_stocks[account_id][idx][2] = 0
                                            break

            # CLOSE OR ADD DAY TO TIMER
            for key, value in short_stocks.items():
                if key == account_id:
                    for idx, (current_stock, current_stock_quantity, current_day_held) in enumerate(value):
                        if current_day_held == 1:
                            # CLOSE POSITION
                            total_quant = short_stocks[account_id][idx][1]
                            contract = Stock(current_stock, "smart", "usd")
                            ib.qualifyContracts(contract)
                            order = MarketOrder("BUY", totalQuantity=total_quant, account=account_id)
                            order.conditions = [TimeCondition(isMore=True, time=f'{today} 13:57:00 America/Denver')]
                            ib.placeOrder(contract, order)
                            close_message = f"CLOSING {total_quant} shares of {current_stock} " \
                                            f"at market price for {email_txt}"
                            client.chat_postMessage(channel="#updates", text=close_message)  # Slack Message
                            print(close_message)
                            # Reassign values to None
                            short_stocks[account_id][idx][0] = None
                            short_stocks[account_id][idx][1] = None
                            short_stocks[account_id][idx][2] = None
                        else:
                            if current_stock is not None:
                                # ADD DAY TO TIMER
                                short_stocks[account_id][idx][2] = short_stocks[account_id][idx][2] + 1
                                timer_add_message = f"Added 1 day to the Hold Timer for {current_stock}"
                                client.chat_postMessage(channel="#updates", text=timer_add_message)
                                print(timer_add_message)
                            else:
                                pass
    # Call the function
    investing_strategy(account_id)

while True:
    now = datetime.datetime.now()
    if now.hour<=7 and (now.minute>=0 and now.minute<19):
        print('Sleeping 10 mins')
        time.sleep(600)
    elif now.hour==7 and now.minute<=28 and now.second<=50:
        print(f'sleep 1 min {now.hour}:{now.minute}:{now.second}')
        time.sleep(60)
    elif now.hour==7 and now.minute<=29 and now.second<=48:
        print(f'sleep 10 secs {now.hour}:{now.minute}:{now.second}')
        time.sleep(10)
    elif now.hour==7 and now.minute<=29 and now.second>=48:
        time.sleep(0.1)
    elif now.hour==7 and now.minute==30:
        time.sleep(2)
        print(f'Running Function at {now.hour}:{now.minute}:{now.second}:{now.microsecond}')
        handle_alerts("account_id", "name of your strategy within Genovest")
        handle_alerts("account_id", "name of your strategy within Genovest")
        handle_alerts("account_id", "name of your strategy within Genovest")
        handle_alerts("account_id", "name of your strategy within Genovest")

        with open(os.path.join(folder_path, "long_stocks.pickle"), "wb") as f:
            pickle.dump(long_stocks, f)

        with open(os.path.join(folder_path, "short_stocks.pickle"), "wb") as f:
            pickle.dump(short_stocks, f)

        action_taken_message = f'*****ACTION TAKEN IN ALL ACCOUNTS at {now.hour}:{now.minute}:{now.second}:{now.microsecond}'
        client = slack.WebClient(token=os.environ['SLACK_TOKEN'])
        # Post the message to Slack
        client.chat_postMessage(channel="#updates", text=action_taken_message)
        break
    else:
        print(f'Greater than 7:31AM')
        break
