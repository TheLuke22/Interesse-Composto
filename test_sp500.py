import requests
import pandas as pd
import yfinance as yf
import time
import concurrent.futures

url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
html = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}).text
sp500 = pd.read_html(html)[0]['Symbol'].tolist()

def check_stock(t):
    try:
        info = yf.Ticker(t).info
        pe = info.get('trailingPE')
        return t, pe
    except Exception as e:
        return t, None

start = time.time()
with concurrent.futures.ThreadPoolExecutor(max_workers=20) as exe:
    res = list(exe.map(check_stock, sp500[:30])) # test just 30 with threads
print(f"Time for 30: {time.time()-start:.2f}s")
