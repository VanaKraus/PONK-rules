#!/usr/bin/env python3

import rules

import udapi

import sys

doc = udapi.Document()
doc.from_conllu_string(''.join(sys.stdin.readlines()))

for d in doc:
    if rules.double_adpos_rule(d.nodes):
        # print(' '.join([node.form for node in d.nodes]))
        d.draw()