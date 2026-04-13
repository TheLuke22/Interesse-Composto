import requests
from bs4 import BeautifulSoup
import pandas as pd

def get_holdings(manager_id):
    url = f"https://www.dataroma.com/m/holdings.php?m={manager_id}"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        return f"Failed: {response.status_code}"
    
    soup = BeautifulSoup(response.text, 'html.parser')
    table = soup.find('table')
    if not table:
        return "No table found"
    
    df = pd.read_html(str(table))[0]
    return df.head(10).to_string()

print("BRK:")
print(get_holdings('BRK'))
print("\nScion (Burry):")
print(get_holdings('SAM'))
