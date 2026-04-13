import yfinance as yf
import time
tickers = ["AAPL", "MSFT", "AMZN", "GOOGL", "META", "TSLA", "BRK-B", "UNH", "JNJ", "JPM"]
start = time.time()
for t in tickers:
    _ = yf.Ticker(t).info
print(f"Time taken for 10 tickers: {time.time() - start:.2f} seconds")
