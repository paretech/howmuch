import argparse
import asyncio
import logging
import pathlib
import os
import sys
import time
import random
import aiohttp
import urllib.parse
import showme.scraping
from collections import namedtuple
import csv
import datetime
from asyncio_throttle import Throttler

LOGGER = logging.getLogger(__name__)
LOGGER.addHandler(logging.NullHandler())

def config_logging(level):
    logging.basicConfig(
        format="%(asctime)s %(levelname)s:%(name)s: %(message)s",
        level=level,
        datefmt="%H:%M:%S",
        stream=sys.stderr,
    )

async def worker(q):
    while True:
        LOGGER.info("Worker Waiting")
        time_start = time.time()
        value = await q.get()
        delay = random.randint(3, 4)
        await asyncio.sleep(delay)
        q.task_done()
        elapsed_time = time.time() - time_start
        if elapsed_time > 4: 
            raise ValueError('Worker took too long')
        LOGGER.info(f'Worker got {value} after {elapsed_time:.3} seconds, {q.qsize()} waiting.')

class Job:
    def __init__(self, url, callback=None, json=False):
        self._url = urllib.parse.urlparse(url)
        self.callback = callback
        self.content = None
        self._json = json
        self.payload = dict()

    @property
    def url(self):
        return self._url.geturl()

    async def go(self):
        await self.callback(self)

class Crawler:
    def __init__(self, urls, outfile='test.csv'):  
        self.urls = urls 
        self.max_workers = 2
        self.request_queue_depth = 20
        self.request_queue = None
        self.seen_urls = set()
        self.seen_styles = set()

        self.session = None
        self.worker_tasks = None

        self.throttler = None
        # timestamp = str(datetime.datetime.fromtimestamp(time.time()).strftime("%Y-%m-%d_%H%M%S"))
        self.filename = str(outfile)
        self.csvfieldnames = ['name',  'color_name', 'productSKUCode', 'style', 'color', 'upc', 'price', 'list_price', 'sale_price', 'availability', 'desc', 'url']
        self.csvwriter = CSVScribe(self.filename, self.csvfieldnames)
        self.write_counter = 0

        self.product_total = 0
        self.product_remaining = 0
        self.percent_complete = 0.0

    async def close(self):
        await self.session.close()
        
    async def crawl(self):
        """Run the crawler until all work is done.
        
        This is the main execution coroutine for the crawler.
        """
        # Queues must be created inside event loop (i.e. don't place in __init__)
        self.request_queue = asyncio.Queue()

        # Clientsession should be created from async function (i.e. don't place in __init__)
        self.session = aiohttp.ClientSession()

        self.throttler = Throttler(rate_limit=10, period=1)

        for url in self.urls:
            await self.schedule(Job(url, self.stage1_request_category_data))

        self.worker_tasks = [asyncio.create_task(self.worker(name=i)) for i in range(self.max_workers)]

        # Only needed if Windows and Python version < 3.8 
        self.health_tasks = [asyncio.create_task(self.heartbeat()), ]

        # When all work is done, exit.
        await self.request_queue.join()
        for worker in self.worker_tasks:
            worker.cancel()

        await self.close()

    async def schedule(self, job):
        if job.url not in self.seen_urls:
            await self.request_queue.put(job)
            LOGGER.debug(f'Added item to queue, there are {self.request_queue.qsize()} jobs pending.')
        else:
            self.product_remaining -= 1
            LOGGER.warning(f'Skipping Seen URL: {job.url}')
            LOGGER.info(f'{self.product_remaining} of {self.product_total} complete')

    async def worker(self, *, name=''):
        if name != '':
            name = ' ' + str(name)
            
        LOGGER.info(f'Worker{name} started!')
        while True:
            LOGGER.debug(f'Worker{name} waiting...')
            job = await self.request_queue.get()
            LOGGER.debug(f'Got item from queue, there are {self.request_queue.qsize()} jobs remaining.')
            try:
                # # Download page and add new links to self.request_queue.
                job.content = await self.fetch(job)
                await job.go()
            except Exception as exc:
                LOGGER.exception(f'The coroutine raised an exception: {exc!r}')
                # raise exc
            finally:
                self.request_queue.task_done()

    async def heartbeat(self):
        '''Workaround for signal issue on Python < 3.8'''
        while True:
            workers = len(self.worker_tasks)
            stopped = [worker for worker in self.worker_tasks if worker.done()]
            faulted = [worker for worker in self.worker_tasks if isinstance(worker._exception, Exception)]
            LOGGER.debug("heartbeat")
            if stopped or faulted:
                LOGGER.warning(f'{len(stopped)}/{workers} workers stopped')
                LOGGER.error(f'{len(faulted)}/{workers} workers faulted')
                for worker in faulted:
                    worker.cancel()
            await asyncio.sleep(5)

    async def fetch(self, job): 
        async with self.throttler:
            async with self.session.get(job.url) as response:
                # assert str(response.url) == job.url
                if job._json:
                    return await response.json()

                return await response.read()

    async def stage1_request_category_data(self, job):
        '''Given job with URL and HTML, request category_page_data'''
        category = showme.scraping.get_page_category_code(job.content)
        path = f'/**/c/{category}/getCategoryPageData?'
        category_page_data_url = urllib.parse.urljoin(job.url, path)

        await self.schedule(Job(category_page_data_url, self.stage2_process_category_page, json=True))

    ProductURLDetails = namedtuple('URLDetails', ['none', 'language', 'title', 'type', 'code'])

    async def stage2_process_category_page(self, job):
        '''Queue remaining category and product pages
        
        Requires job.content to be JSON
        '''
        # If first page, queue remaining pages
        current_page = int(job.content['pagination']['currentPage'])
        
        last_page = int(job.content['pagination']['numberOfPages'])
        if current_page == 0:
            self.product_total += int(job.content['pagination']['totalNumberOfResults'])
            self.product_remaining += int(job.content['pagination']['totalNumberOfResults'])

        if (current_page == 0) and (current_page < last_page-1):
            params = {'page': 0, 'q': ':relevance'}
            for page in range(current_page+1, last_page):
                params['page'] = page
                category_page_data_url = replace_url_params(job._url, params).geturl()
                LOGGER.info(f'Requesting: {category_page_data_url}')
                await self.schedule(Job(category_page_data_url, self.stage2_process_category_page, json=True))

        # Parse product URLs and queue product requests
        products = showme.scraping.get_style_links(job.content['products'])
        product_details = [self.ProductURLDetails(*product.split('/')) for product in products]
        for item in product_details:
            style, color = item.code.split('-', maxsplit=1)
            if style in self.seen_styles:
                LOGGER.debug(f'Skipping stage 3 request for {item.code}, already requested style.')
                continue
            self.seen_styles.add(style)
            path = f'/en/p/{item.code}/detailSummary/getProductFeed2.json?currency=USD'
            product_detail_summary_url = urllib.parse.urljoin(job.url, path)
            LOGGER.info(f'Requesting: {product_detail_summary_url}')
            job = Job(product_detail_summary_url, self.stage3_process_product_page, json=True)
            job.payload = item
            await self.schedule(job)

    async def stage3_process_product_page(self, job):
        try:
            detail_summary = job.content
            for index, product_summary in enumerate(detail_summary):
                product_code = product_summary['productCode']

                if index == 0:
                    product_detail_path = f'/p/{product_code}/getProductDetail.json'
                    product_detail_url = urllib.parse.urljoin(job.url, product_detail_path)
                    product_detail = await self.fetch(Job(product_detail_url, json=True))

                product_url = urllib.parse.urljoin(job.url, f'/en/p/{product_code}')

                output = {
                    'url': product_url,
                    'name': product_detail.get('name'),
                    'color_name': product_summary.get('colorName'),
                    'price': product_summary.get('price'),
                    'list_price': product_summary.get('listPrice'),
                    'sale_price': product_summary.get('salePrice'),
                    }
                
                try:
                    for size in product_summary['sizes']:
                        size['style'], size['color'] = size['productSKUCode'].rsplit('-', maxsplit=1)
                        self.csvwriter({**output, **size})
                except KeyError as e:
                    LOGGER.warning(f'No Size information: {product_url}')
                    LOGGER.exception(e)
                    output['productSKUCode'] = product_summary.get('productSKUCode')
                    output['style'], output['color'], _ = output['productSKUCode'].split('-')
                    self.csvwriter(output)
                except ValueError as e:
                    LOGGER.warning(f'Unknown SKU Format: {size["productSKUCode"]}, {product_url}, {product_detail_url}')
                    LOGGER.exception(e)
        finally:
            self.product_remaining -= 1
            LOGGER.info(f'{self.product_remaining} of {self.product_total} complete')

def replace_url_params(url, params):
    # https://stackoverflow.com/questions/2506379/add-params-to-given-url-in-python
    assert isinstance(params, dict)
    return url._replace(query=urllib.parse.urlencode(params))

class CSVScribe:
    def __init__(self, filename, fields):
        self.filename = filename
        self.dict_writer_parameters = {'fieldnames': fields, 'delimiter': ',', 'quotechar': '"', 'quoting': csv.QUOTE_MINIMAL, 'lineterminator': os.linesep}
        with open(self.filename, 'w', newline='') as file:
            csvwriter = csv.DictWriter(file, **self.dict_writer_parameters)
            csvwriter.writeheader()

    def __call__(self, row):
        try:
            with open(self.filename, 'a', newline='') as file:
                csvwriter = csv.DictWriter(file, **self.dict_writer_parameters)
                csvwriter.writerow(row)
        except ValueError as e:
            LOGGER.warning(e)

if __name__ == '__main__':
    config_logging(level=logging.INFO)
    start_time = time.time()
    timestamp = str(datetime.datetime.fromtimestamp(start_time).strftime("%Y-%m-%d_%H%M%S"))
    try:
        urls = []
        crawler = Crawler(urls, timestamp+'.csv')
        asyncio.run(crawler.crawl(), debug=True)
    finally:
        stop_time = time.time()
        duration = stop_time - start_time
        LOGGER.info(f'Finished in {duration:.3} seconds')