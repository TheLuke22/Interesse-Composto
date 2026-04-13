import yfinance as yf
import time
import concurrent.futures
import pandas as pd

# Get top 50 S&P tickers from wikipedia
table = pd.read_html('https://en.wikipedia.org/wiki/List_of_S%26P_500_companies')
df = table[0]
tickers = df['Symbol'].tolist()[:50]

def fetch_info(t):
    try:
        return yf.Ticker(t).info
    except:
        return {}
        
start = time.time()
with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
    results = list(executor.map(fetch_info, tickers))
    
print(f"Time taken for 50 tickers multithreaded: {time.time() - start:.2f} seconds")
