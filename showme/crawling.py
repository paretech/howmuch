"""A simple web crawler -- class implementing crawling logic."""

import asyncio
from collections import namedtuple
import datetime
import logging
import time
import concurrent.futures

import aiohttp  # Install with "pip install aiohttp".

import showme.scraping

# @TODO: Remove debug imports
from pprint import pprint

LOGGER = logging.getLogger(__name__)

FetchStatistic = namedtuple('FetchStatistic',
                            ['url',
                             'next_url',
                             'status',
                             'exception',
                             'size',
                             'content_type',
                             'encoding',
                             'num_urls',
                             'num_new_urls'])


class Crawler:
    """Crawl a set of URLs.
    This manages two sets of URLs: 'urls' and 'done'.  'urls' is a set of
    URLs seen, and 'done' is a list of FetchStatistics.
    """
    def __init__(self, roots, domain, outfile, max_workers=20, max_tries=1, *, loop=None):
        self.t0 = time.time()
        self.t1 = None
        self.roots = roots
        self.domain = str(domain)
        self.outfile = str(datetime.datetime.fromtimestamp(self.t0).strftime("%Y-%m-%d_%H%M%S")) + '.csv'
        self.protocol = 'https'
        self.max_workers = max_workers
        self.q = asyncio.Queue()
        self.seen_products = set()
        self.done = []
        self.loop = loop or asyncio.get_event_loop()
        self.executor = None
        self.connector = None
        self.session = None
        self.tasks = list()
        self.root_domains = set()
        self.product_details = list()

    def make_absolute_url(self, url):
        if '://' in url:
            return url
        else:
            return f'{self.protocol}://{self.domain}{str(url)}'

    async def close(self):
        """Close web client session"""

        # https://aiohttp.readthedocs.io/en/stable/client_quickstart.html
        # asyncio.gather(*asyncio.all_tasks()).cancel()
        # heartbeat.cancel()
        await self.session.close()

    async def heartbeat(self, msg=None):
        # Ensure something running on loop https://bugs.python.org/issue23057
        while True:
            LOGGER.info('heartbeat...')
            await asyncio.sleep(1)

    def record_statistic(self, fetch_statistic):
        """Record statistics for completed and failed web requests"""
        self.done.append(fetch_statistic)

    async def process_category(self, category_code, current_page=0):
        """Extract product details for products with category code"""
        LOGGER.info(f'Processing {category_code} page {current_page}')
        category_page = await self.get_category_page(category_code, current_page)

        pages = list()
        if current_page is 0:
            total_pages = int(category_page['pagination']['numberOfPages'])
            LOGGER.info(f'{category_code} has {total_pages} pages')
            pages.extend(asyncio.create_task(self.process_category(category_code, page)) for page in range(1, total_pages))

        products = asyncio.create_task(self.process_products(category_page))
        return await asyncio.gather(*(products, *pages))

    async def get_category_page(self, category_code, current_page=0):
        """Get category page, request more pages, request product pages"""
        LOGGER.info(f'Getting  {category_code} page {current_page}')

        category_url = f'{self.protocol}://{self.domain}/**/c/{str(category_code)}/getCategoryPageData?'
        url_parameters = {'page': current_page, 'q': ':relevance'}

        async with self.session.get(category_url, params=url_parameters) as response:
            return await response.json()

    async def process_products(self, category_page):
        """Create tasks to request and process product pages given a category page"""
        current_page = category_page['pagination']['currentPage']
        category_code = category_page['categoryCode']

        new_product_urls, seen_product_urls = await self.get_product_urls(category_page)

        LOGGER.info(f'{category_code} page {current_page}, found {len(new_product_urls)} product links')
        LOGGER.info(f'{category_code} page {current_page}, ignoring {len(seen_product_urls)} product links')

        # @TODO: Request all these products please!
        tasks = (asyncio.create_task(self.process_product(product_url)) for product_url in new_product_urls)

        self.seen_products.update(new_product_urls)
        return await asyncio.gather(*tasks)

    async def get_product_urls(self, category_page):
        """Extract product URLs from getCategoryPageData results"""
        product_urls = await self.loop.run_in_executor(self.executor, showme.scraping.get_style_links, category_page['products'])
        product_urls = set(map(self.make_absolute_url, product_urls))
        return product_urls.difference(self.seen_products), product_urls.intersection(self.seen_products)

    async def process_product(self, product_url):
        """Process product detail page given an absolute product URL"""
        product_page = await self.get_product_page(product_url)
        LOGGER.info(f'Completed request for {product_url}')
        product_details = await self.get_product_details(product_page, product_url)
        self.product_details.extend(product_details)
        return product_details

    async def get_product_page(self, product_url):
        LOGGER.info(f'Getting {product_url}')
        async with self.session.get(product_url) as response:
            return await response.text()

    async def get_product_details(self, product_page, product_url):
        # @TODO: Throw blocking tasks (like beautiful soup) to pool executor.
        #   Extract product details given the requested product_page. The code segment below
        #   is from scrpaing.py from a previous (blocking) version of showme.

        product_details = await self.loop.run_in_executor(self.executor, showme.scraping.get_product_details, product_page, product_url)

        return product_details

    async def crawl(self):
        """Run the crawler until queues finished"""

        self.connector = aiohttp.TCPConnector(limit=10)
        self.session = aiohttp.ClientSession(connector=self.connector)
        heartbeat = asyncio.create_task(self.heartbeat())

        self.executor = concurrent.futures.ThreadPoolExecutor()

        try:
            self.t0 = time.time()
            self.tasks.extend((asyncio.create_task(self.process_category(root)) for root in self.roots))
            await asyncio.gather(*self.tasks)
            self.t1 = time.time()
            LOGGER.info('Queue stopped blocking, on with the show!')
            # print(heartbeat)
        finally:
            heartbeat.cancel()
            # asyncio.gather(*asyncio.all_tasks()).cancel()
            # asyncio.gather()
            self.executor.shutdown(wait=True)
            await self.session.close()
            # await self.session.close()
            # await self.session.close()