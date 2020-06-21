import collections
import logging
import pathlib
import os
import requests
import bs4


LOGGER = logging.getLogger(__name__)


def get_product_details(product_page, product_url):
    pdp_content = bs4.BeautifulSoup(product_page, 'lxml')

    swatch_data = pdp_swatch_sets(pdp_content, product_url)

    if not swatch_data:
        swatch_data = (pdp_single(pdp_content, product_url),)

    if not swatch_data:
        LOGGER.warning(f'No results found, {product_url}')

    return swatch_data


def get_styles(domain, category):
    """Get list of products given domain and category"""
    req_parameters = {'page': 0, 'q': ':relevance'}
    req = requests.get(category_url(category, domain), req_parameters)
    req.raise_for_status()

    total_pages = int(req.json()['pagination']['numberOfPages'])
    styles = req.json()['products']

    for page in range(1, total_pages):
        req_parameters['page'] = page
        req = requests.get(category_url(category, domain), req_parameters)
        req.raise_for_status()
        LOGGER.info(req.json()['pagination'])

        styles.extend(req.json()['products'])

    LOGGER.info(count_keys(styles))
    return styles


def pdp_swatch_sets(soup, *args):
    swatch_data = list()
    title = remove_whitespace(soup.title.text)

    for swatch_set in soup.find_all(class_='swatch-set'):
        for swatch in swatch_set.find_all('button', class_='swatch'):
            price = (swatch_set.find(class_='price') or soup.find(class_='pdp-price')).text.split()[0]
            swatch_data.append((swatch['data-swatch-style-code'], title, swatch['data-swatch-name'], price, *args))

    return swatch_data


def pdp_single(soup, address, *args):
    style_code = address.split('/')[-1]
    title = remove_whitespace(soup.title.text)
    swatch_name = None
    price = soup.find(class_='pdp-price').text.split()[0]

    return (style_code, title, swatch_name, price, address, *args)


def get_style_links(items, key='pListItem'):
    """Given an iterable of mapping type, return links by key."""
    return [bs4.BeautifulSoup(item[key], 'lxml').a.get('href') for item in items if key in item.keys()]

def get_page_category_code(resp, id='pageCategoryCode'):
    '''Get '''
    return bs4.BeautifulSoup(resp, 'lxml').find(id=id)['value']

def category_url(category, domain, protocol='https'):
    """Category is the breadcrumb of a product list or grid view."""
    return f'{protocol}://{str(domain)}/**/c/main|{str(category)}/getCategoryPageData?'


def absolute_url(domain, relative, protocol='https'):
    return f'{protocol}://{str(domain)}{str(relative)}'


def swatch_url(code, domain, protocol='https'):
    """Given a swatch style code and domain, return link."""
    return f'{protocol}://{str(domain)}/ytbmainstorefront/p/{str(code)}/getSwatchInfo.json'


def count_keys(items):
    """Given an iterable of mapping type, return mapping counter of keys"""
    counter = collections.Counter()
    for item in items:
        counter += collections.Counter(item.keys())

    return counter


def remove_whitespace(string):
    return ' '.join(string.split())


def save_page(address):
    req = requests.get(address)
    file_name = address.split('/')[-1] + '.html'
    with open(file_name, 'w') as f:
        f.write(str(req.content))


def touch_file(file):
    pathlib.Path(file).touch()
    if not os.access(file, os.W_OK):
        LOGGER.error(f'File not writable, {file}')
