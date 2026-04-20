import yfinance as yf
ticker = yf.Ticker("AAPL")
cf = ticker.cash_flow
if not cf.empty and 'Free Cash Flow' in cf.index:
    print("Dates:", list(cf.columns))
    print("FCF row:", cf.loc['Free Cash Flow'].dropna().values)
    print("iloc[0]:", cf.loc['Free Cash Flow'].dropna().iloc[0])
    
print("Info FCF:", ticker.info.get('freeCashflow'))
