import os
import setuptools

import fastentrypoints
import showme

here = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setuptools.setup(
    name='showme',
    version=showme.__version__,
    description='Quickly get product properties.',
    long_description=long_description,
    long_description_content_type='text/markdown',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.7',
    ],
    keywords='scraper console command line',
    url='https://github.com/paretech/showme',
    license='Public Domain',
    packages=setuptools.find_packages(exclude=['contrib', 'docs', 'tests']),
    install_requires=[
        'requests',
        'beautifulsoup4',
        'lxml'
    ],
    entry_points={
        'console_scripts': [
            'showme = showme.showme:_command_line',
        ]
    },
)
