"""Showme, a simple web crawler -- class implementing reporting logic."""

import csv
import logging
import os

# @TODO: Remove debugging imports...
from pprint import pprint

LOGGER = logging.getLogger(__name__)

def report(crawler, *args, **kwargs):
    LOGGER.info(f'Showme took {crawler.t1-crawler.t0:.2f} seconds to execute')
    LOGGER.info(f'Showme processed {len(crawler.seen_products)} unique products')

    with open(crawler.outfile, 'w', newline='') as outfile:
        csvwriter = csv.writer(outfile, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL, lineterminator=os.linesep)
        csvwriter.writerows(crawler.product_details)
