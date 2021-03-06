#!/usr/bin/env python3

import argparse
import gzip
import sys
import os
import tempfile
import base64
import subprocess

from lru import LRU
from sentence_splitter import SentenceSplitter, SentenceSplitterException
from loomchild.segmenter import LoomchildSegmenter
import glob
from warcio.archiveiterator import ArchiveIterator
from warcio.warcwriter import WARCWriter

l = LRU(100000) # A cache with size of 100K documents in memory
header = "--header" in sys.argv

parser = argparse.ArgumentParser(prog=os.path.basename(sys.argv[0]), formatter_class=argparse.ArgumentDefaultsHelpFormatter, description="Reconstructs sentences from deferred crawling standoff annotations from Bitextor", epilog="Report bugs to: https://github.com/bitextor/deferred-crawling/issues")

# Mandatory parameters
# Input file
parser.add_argument('bitextor_output', type=str, help="Tab-separated files with deferred crawling standoff annotations to be reconstructed")
# Source language
parser.add_argument("srclang", type=str, help="Source language (SL) of the input")
# Target language
parser.add_argument("trglang", type=str, help="Target language (TL) of the input")

# Optional positional group
groupO = parser.add_argument_group('optional positional arguments')
groupO.add_argument("warcfile", nargs='?', type=str, help="WARC file used to retrieve documents. If a document is not found, then wget will try to download it")
# Optional parameter
parser.add_argument("--sentence_splitter", choices=["loomchild", "moses"], default="loomchild", help="Sentence splitter")
parser.add_argument("--limit_sentences", type=int, help="Limit number of fully reconstructed sentence pairs")
# Optional indexes and header
parser.add_argument("--header", action='store_true', help="If set, the input file will be expected to contain a header and it will be printed")
parser.add_argument("--src_url_idx", type=int if not header else str, default=0 if not header else "src_url", help="Source URL index")
parser.add_argument("--trg_url_idx", type=int if not header else str, default=1 if not header else "trg_url", help="Target URL index")
parser.add_argument("--src_deferred_idx", type=int if not header else str, default=5 if not header else "src_deferred_hash", help="Source sentence deferred index")
parser.add_argument("--trg_deferred_idx", type=int if not header else str, default=6 if not header else "trg_deferred_hash", help="Target sentence deferred index")

args = parser.parse_args()

with gzip.open(args.bitextor_output, 'rt') as bitextor_output:
    src_deferred_idx = args.src_deferred_idx
    trg_deferred_idx = args.trg_deferred_idx
    src_url_idx = args.src_url_idx
    trg_url_idx = args.trg_url_idx

    if args.header:
        header = next(bitextor_output).strip().split('\t')

        src_deferred_idx = header.index(src_deferred_idx)
        trg_deferred_idx = header.index(trg_deferred_idx)
        src_url_idx = header.index(src_url_idx)
        trg_url_idx = header.index(trg_url_idx)

        print('\t'.join(header))

    reconst_count = 0  # Let's count how many sentences have been fully reconstructed (both source and target are not empty)
    for line in bitextor_output:
        # Parse bitextor ".sent.gz" line with deferred crawling annotations
        parts_line = line.rstrip('\n').split('\t')
        deferredhash1 = parts_line[src_deferred_idx]
        deferredhash2 = parts_line[trg_deferred_idx]
        url1 = parts_line[src_url_idx]
        url2 = parts_line[trg_url_idx]
        reconst_parts_line = []  # Store the content of the reconstructed line in another list for a post processing checks and counts
        reconst_parts_line += [url1,url2]
        
        # For source and target language
        for url, deferredhash, langcode in [(url1,deferredhash1,args.srclang), (url2,deferredhash2,args.trglang)]:
            if url not in l: # If we don't crawled or retrieved the document where this sentence is located
                l[url]=dict() # Init the cache if the url didn't exist with a Python dictionary, which will store the deferred annotation and the actual sentence
                fp = tempfile.NamedTemporaryFile(suffix=".warc.gz") # File to store the WARC records/documents that match their URL
                if args.warcfile: # if an already crawled WARC is given by argument, let's look for the content of the url from the line we are actually iterating on
                    writer = WARCWriter(fp, gzip=True)
                    for record in ArchiveIterator(open(args.warcfile,'rb')):
                        if url == record.rec_headers.get_header('WARC-Target-URI'):
                            writer.write_record(record)
                else: # download the url with wget
                    with tempfile.TemporaryDirectory() as tempcrawling:
                        subprocess.run(["wget", url, "-P", tempcrawling, "-o", "/dev/null", "--warc-file", ".".join(fp.name.split('.')[:-2])])

                with tempfile.TemporaryDirectory() as tempprocess:
                    # Process the downloaded document the same way Bitextor does in Paracrawl (warc2text + Moses sentence splitter Python port)
                    subprocess.run(["warc2text", "-o", tempprocess, fp.name], stderr=subprocess.DEVNULL)
                    fp.close()
                    splitter = None
                    if args.sentence_splitter == "moses":
                        try:
                            splitter = SentenceSplitter(language=langcode).split
                        except SentenceSplitterException as e:
                            sys.stderr.write(str(e)+"\n")
                            splitter = SentenceSplitter(language='en').split
                    elif args.sentence_splitter == "loomchild":
                        splitter = LoomchildSegmenter(langcode).get_document_segmentation
                    else:
                        sys.stderr.write(f"Unknown splitter: {args.sentence_splitter}\n")

                    for filename in glob.glob(tempprocess + "/*/text.gz"):
                        with gzip.open(filename, 'r') as f:
                            segments = splitter(base64.b64decode(f.read()).decode('utf8'))
                            segments = [s.strip() for s in segments if s.strip() != '']

                            for segment in segments:
                                # Then calculate the MurmurHash for each sentence from the downloaded document like Bitextor does, and then store it in the cache
                                l[url][subprocess.run(["mmhsum"], stdout=subprocess.PIPE, input=segment, encoding='utf8').stdout.rstrip('\n')]=segment
    
            # Print the reconstructed sentences
            list_sentences = []
            for partdeferredhash in deferredhash.split('#')[0].split('+'):
                try:
                    list_sentences.append(l[url][partdeferredhash])
                except KeyError: # if the sentence hasn't been found
                    list_sentences.append('')
            reconst_parts_line.append(" ".join(list_sentences))
        reconst_parts_line += parts_line[4:]


        # Take some counts to limit the processing in case --limit_sentences is set
        if reconst_parts_line[2] and reconst_parts_line[3]:
            reconst_count += 1
        print("\t".join(reconst_parts_line))

        if args.limit_sentences and args.limit_sentences <= reconst_count:
            break

