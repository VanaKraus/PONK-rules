#!/usr/bin/env python3

from ufal.udpipe import Model, Pipeline

import sys
import os

if __name__ == "__main__":
    # TODO: unhardcodify
    model = Model.load("_local/czech-pdt-ud-2.5-191206.udpipe")
    pipeline = Pipeline(model, "tokenize", Pipeline.DEFAULT, Pipeline.DEFAULT, "conllu")

    if len(sys.argv) > 1:
        for arg in sys.argv[1:]:
            with open(arg, "r") as input_fs:
                counter = 1
                for line in input_fs:
                    if line.strip(" \n") == "":
                        continue

                    npath = os.path.join(
                        "conllu", os.path.splitext(arg)[0] + f"_{counter}.conllu"
                    )
                    if not os.path.isdir(dir := os.path.dirname(npath)):
                        os.makedirs(dir)
                    print(f"> {npath}", file=sys.stderr)

                    with open(npath, "w+") as output_fs:
                        print(pipeline.process(line), file=output_fs)

                    counter += 1
    else:
        string = ""
        for line in sys.stdin:
            string = " ".join([string, line])
        print(pipeline.process(string))
