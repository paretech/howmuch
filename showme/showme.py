import argparse
import asyncio
import logging
import pathlib
import os
import sys

import showme.crawling as crawling
import showme.reporting as reporting

LOGGER = logging.getLogger(__name__)
LOGGER.addHandler(logging.NullHandler())

def config_logging(level):
    logging.basicConfig(
        format="%(asctime)s %(levelname)s:%(name)s: %(message)s",
        level=level,
        datefmt="%H:%M:%S",
        stream=sys.stderr,
    )

# @TODO: Rename to build command line arguments
def _command_line_parser():
    """Command line parser and argument definition"""
    parser = argparse.ArgumentParser(description="Quickly get product properties")
    parser.add_argument('categories', type=str, nargs='*',
                        help='the category to query (e.g. "men|clearance")')
    parser.add_argument('-d', '--domain', help='Domain of website', required=True,
                        default=os.getenv('SHOWME_DOMAIN'), type=str)
    parser.add_argument('-o', '--outfile', type=str, nargs='?', default=None, required=False,
                        help='CSV output file')
    parser.add_argument('-v', '--verbose', action='count', dest='level', default=0,
                        help='Verbose logging (repeat for more verbose)')
    parser.add_argument('-q', '--quiet', action='store_const', const=0, dest='level', default=1,
                        help='Only log errors')
    return parser


# @TODO: Rename to main?
def _command_line():
    """Call the command line parser and process arguments"""
    parser = _command_line_parser()
    args = parser.parse_args()

    log_levels = [logging.ERROR, logging.WARN, logging.INFO, logging.DEBUG]
    log_level = log_levels[min(args.level, len(log_levels) - 1)]
    config_logging(level=log_level)

    if not args.categories:
        print('No categories specified.')
        print('Use --help for command line help')
        return

    if not args.domain:
        print('No domain specified.')
        print('Use --help for command line help')
        return

    loop = asyncio.get_event_loop()
    loop.set_debug(True)

    import signal

    crawler = crawling.Crawler(args.categories, domain=args.domain, outfile=args.outfile)

    # Python 3.7 on Windows does not support signals, supposedly 3.8 will.
    try:
        loop.run_until_complete(crawler.crawl())
    except KeyboardInterrupt:
        sys.stderr.flush()
        print('\nProcess Interrupted\n')
        LOGGER.info('Process interrupted')
    finally:
        LOGGER.info("That's All Folks!")
        reporting.report(crawler)
        # loop.stop()
        loop.close()

if __name__ == '__main__':
    _command_line()
