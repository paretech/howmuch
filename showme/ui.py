import asyncio
import datetime
import logging
import logging.config
import time
import threading
import tkinter as tk
import tkinter.ttk as ttk
import sys
import showme.crawling

LOGGER = logging.getLogger(__name__)

class Application(tk.Frame):
    def __init__(self, master=None, version=None):
        super().__init__(master)
        self.version = version
        self.thread = None
        self.running = None
        self.setup()

    def setup(self):
        self.master.minsize(500,75)
        self.master.columnconfigure(0, weight=1, minsize=500)
        self.master.rowconfigure(0, weight=1, minsize=50)
        self.master.title(f'Showme - a web crawler (v{self.version})')

        self.lfrm = tk.LabelFrame(
            text='Crawl category URL',
            padx=10,
            pady=10,
        )

        self.lfrm.grid(padx=5, pady=5, sticky='nsew')
        self.lfrm.columnconfigure(0, weight=10)
        self.lfrm.columnconfigure(1, weight=1)

        self.ent_url = tk.Entry(master=self.lfrm)
        self.ent_url.grid(row=0, column=0, sticky='nswe')

        self.btn_go = tk.Button(master=self.lfrm)
        self.btn_go["text"] = "Go"
        self.btn_go["command"] = self.cmd_go
        self.btn_go.grid(row=0, column=1, sticky='nswe')

        self.progress = ttk.Progressbar(master=self.lfrm, orient = tk.HORIZONTAL, value=0)
        self.progress.step(0)
        self.progress.config(mode='determinate')
        self.progress.grid(row=1, column=0, columnspan=2, sticky='nswe')

    def poll_thread(self):
        """
        Check every 200 ms if there is something new in the queue.
        """
        LOGGER.info('GUI poll threading Heartbeat')
        if self.running:
            if self.thread.is_alive():
                self.progress.step(amount=5.0)
                self.master.after(200, self.poll_thread)
            else:
                LOGGER.info('Threaded stoped')
                self.running = False
                self.btn_go['state'] = 'normal'
                self.progress.stop()


    def cmd_go(self):
        self.btn_go["state"] = "disabled"
        # self.progress.start()
        self.running = 1
        self.thread = threading.Thread(target=run_showme, args=[str(self.ent_url.get())])
        self.thread.start()
        self.poll_thread()

def config_logging(level):
    logging.basicConfig(
        format="%(asctime)s %(levelname)s:%(name)s: %(message)s",
        level=level,
        datefmt="%H:%M:%S",
        stream=sys.stderr,
    )

def run_showme(user_url):
    start_time = time.time()
    timestamp = str(datetime.datetime.fromtimestamp(start_time).strftime("%Y-%m-%d_%H%M%S"))

    try:
        crawler = showme.crawling.Crawler([user_url], timestamp+'.csv')
        asyncio.run(crawler.crawl(), debug=False)
    finally:
        stop_time = time.time()
        duration = stop_time - start_time
        LOGGER.info(f'Finished in {duration:.3} seconds')

LOGGING_CONFIG = { 
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': { 
        'standard': { 
            'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
        },
    },
    'handlers': { 
        'default': { 
            'level': 'DEBUG',
            'formatter': 'standard',
            'class': 'logging.StreamHandler',
            'stream': 'ext://sys.stdout',  # Default is stderr
        },
        'file': { 
            'level': 'DEBUG',
            'formatter': 'standard',
            'class': 'logging.FileHandler',
            'filename': 'showme.log',  # Default is stderr
            'mode': 'w',
        },
    },
    'loggers': { 
        '': {  # root logger
            'handlers': ['default', 'file'],
            'level': 'DEBUG',
            'propagate': False
        },
    } 
}

if __name__ == '__main__':
    logging.config.dictConfig(LOGGING_CONFIG)
    # config_logging(level=logging.DEBUG)
    app = Application(tk.Tk(), version=showme.__version__)
    app.mainloop()