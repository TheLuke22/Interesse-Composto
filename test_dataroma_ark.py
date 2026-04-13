import requests
from bs4 import BeautifulSoup
import pandas as pd

url = "https://www.dataroma.com/m/managers.php"
headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
r = requests.get(url, headers=headers)
soup = BeautifulSoup(r.text, 'html.parser')
for a in soup.find_all('a'):
    if 'ARK' in a.text.upper() or 'WOOD' in a.text.upper():
        print(a.text, a['href'])
