import argparse
import collections
import csv
import logging
import os
import pathlib
import sys

import bs4
import progressbar
import requests

LOGGER = logging.getLogger(__name__)
LOGGER.addHandler(logging.NullHandler())


def _command_line_parser():
    """Command line parser and argument definition"""
    parser = argparse.ArgumentParser(description="Quickly get product properties")
    parser.add_argument('categories', type=str, nargs='*',
                        help='the category to query (e.g. "men|clearance")')
    parser.add_argument('-d', '--domain', help='Domain of website',
                        default=os.getenv('SHOWME_DOMAIN'), type=str)
    parser.add_argument('-o', '--outfile', type=str, nargs='?', default=None,
                        help='CSV output file')
    parser.add_argument('-v', '--verbose', action='count', dest='level', default=0,
                        help='Verbose logging (repeat for more verbose)')
    parser.add_argument('-q', '--quiet', action='store_const', const=0, dest='level', default=1,
                        help='Only log errors')
    return parser


def _command_line():
    """Call the command line parser and process arguments"""
    parser = _command_line_parser()
    args = parser.parse_args()

    if args.outfile:
        progressbar.streams.wrap_stderr()
    log_levels = [logging.ERROR, logging.WARN, logging.INFO, logging.DEBUG]
    logging.basicConfig(level=log_levels[min(args.level, len(log_levels) - 1)])

    if not args.categories:
        print('Use --help for command line help')
        return

    if not args.domain:
        print('No domain specified.')
        print('Use --help for command line help')
        return

    styles = list()
    for category in args.categories:
        styles.extend(get_styles(args.domain, category))

    styles_links = get_style_links(styles)

    for link in progressbar.progressbar(styles_links, redirect_stdout=True):
        try:
            pdp_req = requests.get(absolute_url(args.domain, link))
            pdp_content = bs4.BeautifulSoup(pdp_req.content, 'lxml')

            swatch_data = pdp_swatch_sets(pdp_content, pdp_req.url)

            if not swatch_data:
                swatch_data = (pdp_single(pdp_content, pdp_req.url), )

            if not swatch_data:
                LOGGER.warning(f'No results found, {pdp_req.url}')

            pdp_write_styles(swatch_data, args.outfile)

        except Exception as err:
            LOGGER.error(f'{pdp_req.url}')
            raise


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


def pdp_write_styles(swatch_data, file):
    if file:
        with open(file, 'a', newline='') as csvfile:
            csvwriter = csv.writer(csvfile, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL, lineterminator=os.linesep)
            csvwriter.writerows(swatch_data)
    else:
        csv.writer(sys.stdout, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL, lineterminator=os.linesep)


def get_style_links(items, key='pListItem'):
    """Given an iterable of mapping type, return links by key."""
    return [bs4.BeautifulSoup(item[key], 'lxml').a.get('href') for item in items if key in item.keys()]


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
