#!/usr/bin/env python3

from ufal.udpipe import Model, Pipeline
from argparse import ArgumentParser

import sys
import os

if __name__ == "__main__":
    # TODO: unhardcodify
    parser = ArgumentParser(prog='UDPipe Rules: Conllu Conversion',
                            description='Converts specified files to conllu format (or potentially others).',
                            )
    parser.add_argument('-m', '--model', help='Location of the model.', required=True)
    parser.add_argument('-c', '--conllu', default='conllu', help='Location of the conllu folder. Defaults to \'conllu\'.')
    parser.add_argument('-f', '--format', default='conllu', help='Specify the output format. Defaults to \'conllu\'')
    parser.add_argument('filename', nargs='*', help='Name of the file to process. '
                                                    'Can be specified multiple times. Defaults to stdin')
    args = parser.parse_args()

    conllu_location = args.conllu
    output_format = args.format
    model = Model.load(args.model)
    pipeline = Pipeline(model, "tokenize", Pipeline.DEFAULT, Pipeline.DEFAULT, output_format)
    

    if len(args.filename) == 0:
        #read from stdin
        string = ""
        for line in sys.stdin:
            string = " ".join([string, line])
        print(pipeline.process(string))
        exit(0)

    for filename in args.filename:
        #read files from cmdline
        with open(filename, "r") as input_fs:
            counter = 1
            for line in input_fs:
                if line.strip(" \n") == "":
                    continue

                npath = os.path.join(
                    conllu_location, os.path.splitext(filename)[0] + f"_{counter}.{output_format}"
                )
                if not os.path.isdir(dir := os.path.dirname(npath)):
                    os.makedirs(dir)
                print(f"> {npath}", file=sys.stderr)

                with open(npath, "w+") as output_fs:
                    print(pipeline.process(line), file=output_fs)

                counter += 1
