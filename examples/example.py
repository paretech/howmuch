import argparse
import asyncio
import logging
import pathlib
import os
import sys
import time
import random
from pprint import pprint


LOGGER = logging.getLogger(__name__)
LOGGER.addHandler(logging.NullHandler())

def config_logging(level):
    logging.basicConfig(
        format="%(asctime)s %(levelname)s:%(name)s: %(message)s",
        level=level,
        datefmt="%H:%M:%S",
        stream=sys.stderr,
    )

async def fetch(url, prams=None):
    delay = random.randint(1, 3)
    await asyncio.sleep(delay)
    if delay > 2:
        try:
            raise RuntimeError
        finally:
            LOGGER.info(f'{url} raised an exception')
    else:
        html = f'** Fetching {url} with delay = {delay}'
        return html

async def sink(value):
    LOGGER.info(value)


async def producer(q, n):
    for i in range(n):
        LOGGER.info('Producer Started')
        time_start = time.time()
        # delay = random.randint(1, 2)
        delay = 0
        await asyncio.sleep(delay)
        await q.put(i)
        elapsed_time = time.time() - time_start
        if elapsed_time > 3:
            LOGGER.warning('Producer took too long')
            raise ValueError(f'Producer took too long')
        LOGGER.info(f'Producer put {i} after {elapsed_time:.3} seconds, {q.qsize()} waiting.')
        


async def heartbeat():
    '''Workaround for signal issue on Python < 3.8'''
    while True:
        LOGGER.info("heartbeat")
        await asyncio.sleep(5)

async def worker(q):
    while True:
        LOGGER.info("Worker Waiting")
        time_start = time.time()
        value = await q.get()
        delay = random.randint(3, 4)
        await asyncio.sleep(delay)
        q.task_done()
        elapsed_time = time.time() - time_start
        # if elapsed_time > 4: 
        #     raise ValueError('Worker took too long')
        LOGGER.info(f'Worker got {value} after {elapsed_time:.3} seconds, {q.qsize()} waiting.')

async def main():
    q = asyncio.Queue(3)
    tasks = list()
    tasks.append(asyncio.create_task(heartbeat()))
    tasks.append(asyncio.create_task(worker(q)))

    # Wait for the producers to finish
    asyncio.create_task(producer(q, 20))
    await asyncio.sleep(1)
    # producer_results = await asyncio.gather(producer(q, 20), return_exceptions=True)
    # LOGGER.info('Producers Done!')
    # pprint(producer_results)

    # Wait for the workers to finish. What happens if worker throws an
    # exception and join blocks forever? Note good, can workers be made
    # more resilient? 
    await q.join()
    LOGGER.info('Workers Done!')

    LOGGER.info('Starting Cleanup')
    for task in tasks:
        task.cancel()

    # If any Task or Future from the aws sequence is cancelled, it is
    # treated as if it raised CancelledError – the gather() call is not
    # cancelled in this case. This is to prevent the cancellation of one
    # submitted Task/Future to cause other Tasks/Futures to be
    # cancelled.
    task_status = await asyncio.gather(*tasks, return_exceptions=True)
    pprint(task_status)
    LOGGER.info('Execution Complete')

if __name__ == '__main__':
    config_logging(level=logging.INFO)
    start_time = time.time()
    asyncio.run(main(), debug=False)
    stop_time = time.time()
    duration = stop_time - start_time
    LOGGER.info(f'Finished in {duration:.3} seconds')