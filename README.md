# Deferred crawling
Reconstructs sentences using deferred crawling standoff annotations from Bitextor

## Install
Check that you have `wget` installed in your system and in your path:

```
wget --version
```

If not installed, simply use your preferred package manager to get it installed.

The reconstructor script is written in Python and it has some dependencies. Install them with:

```
pip install -r requirements.txt
```

Also, it depends on Bitextor tool `warc2text`. Follow the README.md instructions inside the folder "warc2text" to properly download, install and compile.

## Usage

This is an example to reconstruct a Bitextor standoff annotated output obtained from an English-Greek domain:

```
python3 deferred-annotation-reconstructor.py path-to-bitextor-output/en-el.deduped.txt.gz en el > outputdeferred
```

To reproduce Paracrawl results, you also need to perform Bifixer:

```
python3 deferred-annotation-reconstructor.py path-to-bitextor-output/en-el.deduped.txt.gz en el | python3 path-to-bifixer/bifixer/bifixer.py --sdeferredcol 6 --tdeferredcol 7 --ignore_duplicates - - en el > outputdeferred
```

And, in case you already have a WARC file with the crawl data, you can replace `wget` calls to recrawl with that WARC data using:

```
python3 deferred-annotation-reconstructor.py path-to-bitextor-output/en-el.deduped.txt.gz en el path-to-data/warc/primeminister.warc.gz | python3 path-to-bifixer/bifixer/bifixer.py --sdeferredcol 6 --tdeferredcol 7 --ignore_duplicates - - en el > outputdeferred
```

For more options, check `--help` command.

![Connecting Europe Facility](https://raw.githubusercontent.com/bitextor/bitextor/master/img/logo_en_cef273x39_nonalpha.png)

All documents and software contained in this repository reflect only the authors' view. The Innovation and Networks Executive Agency of the European Union is not responsible for any use that may be made of the information it contains.
