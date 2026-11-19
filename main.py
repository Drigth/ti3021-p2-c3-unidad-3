import requests


url = 'https://midas.minsal.cl/farmacia_v2/WS/getLocalesTurnos.php'


respuesta = requests.get(url)
farmacias = respuesta.json()

for farmacia in farmacias:
     print(farmacia["local_nombre"],farmacia["comuna_nombre"])