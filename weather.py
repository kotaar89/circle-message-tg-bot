import requests
from bs4 import BeautifulSoup


def parse_site():
    headers = {}
    response = requests.get("https://yandex.ru/pogoda/ru/kazan", None)
    soup = BeautifulSoup(response.text, 'html.parser')

    temp = soup.find('p', class_ = 'AppFactTemperature_content__Lx4p9 AppFactTemperature_content_bold__qXi_O')
    weather = soup.find('div', class_ = 'AppFact_warning__8kUUn')
    
    return(temp.text, weather.text)