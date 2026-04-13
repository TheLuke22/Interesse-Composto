import requests
from bs4 import BeautifulSoup
import pandas as pd

def find_managers():
    url = "https://www.dataroma.com/m/managers.php"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    r = requests.get(url, headers=headers)
    soup = BeautifulSoup(r.text, 'html.parser')
    managers = {}
    for a in soup.find_all('a'):
        text = a.text.upper()
        if 'ACKMAN' in text or 'PERSHING' in text:
            managers['Ackman'] = a['href']
        if 'DALIO' in text or 'BRIDGEWATER' in text:
            managers['Dalio'] = a['href']
        if 'DRUCKENMILLER' in text or 'DUQUESNE' in text:
            managers['Druckenmiller'] = a['href']
        if 'TEPPER' in text or 'APPALOOSA' in text:
            managers['Tepper'] = a['href']
    return managers

def get_holdings(manager_path):
    url = f"https://www.dataroma.com{manager_path}"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        return "Failed"
    
    soup = BeautifulSoup(response.text, 'html.parser')
    table = soup.find('table', {'id': 'grid'}) or soup.find('table')
    if not table:
        return "No table found"
    
    df = pd.read_html(str(table))[0]
    return df.head(6).to_string()

managers = find_managers()
print("Found Managers:", managers)
for name, path in managers.items():
    print(f"\n{name} holdings:")
    print(get_holdings(path))

