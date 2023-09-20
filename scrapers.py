import requests
from bs4 import BeautifulSoup
import json
import warnings
warnings.filterwarnings('ignore')
import pandas as pd
from unidecode import unidecode
import numpy as np
from IPython.display import Image, display, HTML

user_agent_list = ['Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.0.0 Safari/537.36',
                   'Chrome/79.0.3945.130']

def clean_string(string):
    return unidecode(''.join([i for i in string if i.isalpha()]).lower())

def format_query_url(brand, model, size_range, material, maxprice, condition, page_number):
    brand = brand.replace(' ', '')
    model = (brand + ' ' + model).replace(' ', '+')
    page_number = '&showpage={}'.format(page_number)

    condition = '&usedOrNew={}'.format(condition)   if condition != '' else ''
    maxprice = '&priceTo={}'.format(maxprice)       if maxprice != '' else ''

    material = 3 if material == 'gold' else 4 if material == 'steel' else ''
    material = '&caseMaterials={}'.format(material) if material != '' else ''

    sizes = ''

    if len(size_range) == 0:
        sizes = ''
    else:
        if len(size_range) == 1: size_range[1] = size_range[0]

        for i in np.arange(size_range[0], size_range[1] + 1):
            sizes += '&caseDiameter={}'.format(i)

    url = f'https://www.chrono24.com.br/{brand}/index.htm?'\
        f'{sizes}{material}dosearch=true&pageSize=120query={model}{page_number}{condition}{maxprice}'
    return url


def search_watch(brand, model, size_range, material, maxprice, condition, page_number):
    model_brand = brand + ' ' + model
    url = 'https://www.chrono24.com.br/{}/index.htm?'\
        'caseDiameter=34&caseDiameter=35&caseDiameter=36&'\
        'caseMaterials=3'\
        'dosearch=true&pageSize=120'\
        '&query={}&showpage={}&usedOrNew={}&priceTo={}'.format(
        brand.replace(' ', ''), model_brand.replace(' ', '+'), page_number, condition, maxprice)
    
    url = format_query_url(brand, model, size_range, material, maxprice, condition, page_number)
    headers = {
        'User-Agent': user_agent_list[0],
        'Accept-Language': 'en-US,en;q=0.9'}

    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        return (response)
    else:
        print(f"Failed to retrieve content. Status code: {response.status_code}")


def extract_html_element(response, element):
    soup = BeautifulSoup(response.text, 'html.parser')
    script_element = soup.find('script', {'type': element})
    if script_element:
        return(script_element.string)
    else:
        print("Script element not found.")


def convert_string_to_json(string):
    try:
        json_data = json.loads(string)
        return(json_data)
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON: {e}")


def format_search_results_to_dataframe(json_data):

    offer_frame = pd.DataFrame()
    for offer_ in json_data['@graph'][1]['offers']:
        offer = offer_.copy()
        if 'image' in offer: offer['image'] = offer['image']['contentUrl']
        else: offer['image'] = ''
        s = pd.DataFrame(offer, index = [0])
        offer_frame = pd.concat([offer_frame, s], axis=0)
        
    offer_frame.availability = offer_frame.availability.apply(lambda x: str(x).split('/')[-1])
    offer_frame = offer_frame[offer_frame.price.isna() == False]
    offer_frame = offer_frame[offer_frame.availability == 'InStock']
    offer_frame = offer_frame[offer_frame['@type'] == 'Offer']
    offer_frame = offer_frame.drop(['@type', 'availability'], axis=1)
    offer_frame.price = offer_frame.price.astype(int)

    return offer_frame.sort_values('price')


def get_page(brand, model, size_range, material, maxprice, condition, page_number):
    response = search_watch(brand, model, size_range, material, maxprice, condition, page_number)
    html_element = extract_html_element(response, element = 'application/ld+json')
    json_data = convert_string_to_json(html_element)
    offer_frame = format_search_results_to_dataframe(json_data)
    return offer_frame


def get_offer_information(url):
    headers = {
        'User-Agent': user_agent_list[0],
        'Accept-Language': 'en-US,en;q=0.9'}

    response = requests.get(url, headers=headers)
    text = response.text
    soup = BeautifulSoup(text, 'html.parser')
    data_dict = {}

    for row in soup.find_all('tr'):
        cells = row.find_all('td')
        if len(cells) == 2:
            key = cells[0].strong.text.strip()
            value = cells[1].text.strip()
            data_dict[key] = value

    out = pd.DataFrame(data_dict, index = [0])
    out['url'] = url
    return out

def clean_frame(df, max_price, model):
    df['clean_name'] = df.name.apply(clean_string)
    df = df[df.clean_name.str.contains(clean_string(model))]
    df = df[df.price <= max_price].drop('clean_name', axis=1)
    return df


def search_multiple_pages(brand, model, size_range, material, maxprice, condition, max_pages = 1000, clean_by_name = False):
    offer_frame = pd.DataFrame()
    page_number = 1
    while True:

        new_rows =  get_page(brand, model, size_range, material, maxprice, condition, page_number)
        if clean_by_name: new_rows = clean_frame(new_rows.copy(), maxprice, model)
        new_rows['page'] = page_number
        previous_size = offer_frame.shape[0]
        offer_frame = pd.concat([offer_frame, new_rows])
        offer_frame = offer_frame.drop_duplicates(['url'], keep = 'first')

        if previous_size == offer_frame.shape[0]: break
        if page_number == max_pages: break

        page_number += 1

    return offer_frame.sort_values('price')




def show_deals(queries, max_price, max_results = 12):
    for query in queries:

        brand = query['brand']
        model = query['model']
        size_range = query['size_range'] if 'size_range' in query else []
        material = query['material'] if 'material' in query else ''
        condition = query['condition'] if 'condition' in query else ''

        results = search_multiple_pages(brand, model, size_range, material, max_price, condition, clean_by_name = True).head(max_results)
        bounds = np.arange(0, max_results + 1, 4)
        for i in range(len(bounds) - 1):
            a = bounds[i]
            b = bounds[i + 1]
            results_ = results.iloc[a:b]
            html_code = """
            <div style="display: flex; align-items: flex-start;">
                """
            # Iterate through the image URLs and create clickable images with text below them
            for row in results_.iloc:
                html_code += f"""
                <div style="flex: 1; margin-right: 10px;">
                    <a href="{row.url}" target="_blank">
                        <img src="{row.image}" style="height: 200px; width: auto" />
                    </a>
                    <div style="margin-top: 10px;">
                        <p>R${row.price}, {row['name'][:30]}</p>
                    </div>
                </div>
                """

            html_code += """
            </div>
            """

            display(HTML(html_code))
