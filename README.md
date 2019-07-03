# showme

Quickly get product properties from your E-commerce website.

## Windows Installation
1. Open command prompt (⊞ Win + R, type CMD) and run the following commands

```sh
python -m venv venv
venv\scripts\activate
pip install git+https://github.com/paretech/showme
```

OR

1. [Download the zip version](https://github.com/paretech/showme/archive/master.zip) 
2. [Extract the zip on your computer](https://support.microsoft.com/en-us/help/14200/windows-compress-uncompress-zip-files)
3. Open command prompt (⊞ Win + R, type CMD) and run the following commands. 

*NOTE: commands that include values surrounded by <, > are intended to be replaced with values specific to your configuration.*

## Usage example

1. Open command prompt (⊞ Win + R, type CMD) and run the following commands

*NOTE: Depending on which method you used to install showme, you may need to change directory to that location first.*

```sh
venv\scripts\activate
showme "<category_string>" -d <url_of_your_site>
```

Progress bar during execution.

```sh
(venv) >showme "<category_string>" -d <url_of_your_site> -o test.csv
 67% (181 of 270) |#######################################                    | Elapsed Time: 0:02:20 ETA:   0:00:55
 ```
 
 Help
 
 ```sh
 (venv) >showme -h
usage: showme [-h] -d DOMAIN -o [OUTFILE] [-v] [-q]
              [categories [categories ...]]

Quickly get product properties

positional arguments:
  categories            the category to query (e.g. "men|clearance")

optional arguments:
  -h, --help            show this help message and exit
  -d DOMAIN, --domain DOMAIN
                        Domain of website
  -o [OUTFILE], --outfile [OUTFILE]
                        CSV output file
  -v, --verbose         Verbose logging (repeat for more verbose)
  -q, --quiet           Only log errors
  ```
 
 Note that both domain and outfile are required.
  
## Release History

* 0.0.0
    * Barely useful... List some links...

## Meta

[@paretech](https://twitter.com/paretech)

<https://github.com/paretech/>

## Contributing

1. Fork it (<https://github.com/paretech/showme>)
2. Create your feature branch (`git checkout -b feature/fooBar`)
3. Commit your changes (`git commit -am 'Add some fooBar'`)
4. Push to the branch (`git push origin feature/fooBar`)
5. Create a new Pull Request

<!-- Markdown link & img dfn's -->
