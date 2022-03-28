from typing import List
import requests
import json
from requests.exceptions import HTTPError

def download(URL):
    """Downloads the content of the given Link and returns plain text"""
    try:
        header = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36'} 
        response = requests.get(URL, headers=header)
        # If the response was successful, no Exception will be raised
        response.raise_for_status()
    except HTTPError as http_err:
        print(f'HTTP Error: {http_err}')
    except Exception as err:
        print(f'Connection Error: {err}')
    else:
        #print('Connection Successful!')
        txt = response.content.decode("utf-8") 
        return txt

def download_zalando_json(URL):
    """Downloads the given Zalando Link and locates the relevant JSON Data. Returns JSON Data ready to parse."""
    txt = download(URL)
    try:
        str_index = txt.index('{"data":{"customer":{"sizeProfile')
        txt = txt[str_index+8:]
        str_index = txt.index('},"errors":[')
        txt = txt[:str_index+1]
        txt = '[' + txt + ']'
        return txt
    except:
        print('Error: Zalando JSON Data not found.')
   

def parse_available_sizes(raw_data):
    """Parses Zalando JSON and returns all Sizes that are currently available"""
    data = json.loads(raw_data)
    sold_units = []
    available_sizes = []  
    for items in data:
        sold_units.append(items["product"]["simplesWithStock"])
    for items in sold_units:
        for i in items:
         available_sizes.append(i["size"])
    return available_sizes

def parse_all_sizes(raw_data):
    """Parses Zalando JSON and returns all Sizes"""
    data = json.loads(raw_data)
    sold_units = []
    sold_sizes = []  
    for items in data:
        sold_units.append(items["product"]["simples"])
    for items in sold_units:
        for i in items:
         sold_sizes.append(i["size"])
    return sold_sizes

def find_soldout_items(all_sizes, available_sizes):
    """Finds the missing items in the available_sizes list compared to all sizes."""
    s = set(available_sizes)
    soldout_items = [x for x in all_sizes if x not in s]
    return soldout_items


def parse_name(raw_data):
    """Parses Zalando JSON and returns the Article Name"""
    data = json.loads(raw_data)
    for items in data:
        brand = items["product"]["brand"]["name"]
        name = items["product"]["name"]
    return brand + ' ' + name
    
def check_if_soldout(available_sizes, search_size) -> bool:
    """Checks if the desired size is in the available-sizes-list"""
    if search_size in available_sizes:
        return False
    else:
        return True

def test(URL, search_sizes: List):
    """Processes a Zalando Link and searches for the given Size(s)."""
    try:
        data = download_zalando_json(URL)
        all_sizes = parse_all_sizes(data)
        available_sizes = parse_available_sizes(data)
        print('Name: ' + parse_name(data))
        print('Sizes: ' + str(all_sizes))
        print('Available Sizes: ' + str(available_sizes))
        print('Sold out: ' + str(find_soldout_items(all_sizes,available_sizes)))
        for size in search_sizes: 
            if check_if_soldout(available_sizes, size):
                print("Size " + size + " not available.")
            else:
                print("Size " + size + " is available!")
        
    except:
        print ("Check not Successful. Try again later.")

#test("https://www.zalando.de/the-north-face-hooded-dress-zumu-freizeitkleid-black-th321c007-q11.html",['M','XS'])
