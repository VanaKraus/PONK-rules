#!/usr/bin/env python3

import rules
import util

import udapi

import sys

doc = udapi.Document()
doc.from_conllu_string("".join(sys.stdin.readlines()))

dadp_rule = rules.double_adpos_rule()
cond_rule = rules.condition_rule()

dadp_rule.run(doc)
cond_rule.run(doc)

print(doc.to_conllu_string())

for d in doc:
    if [nd for nd in d.nodes if "RuleDoubleAdpos" in nd.misc]:
        d.draw(attributes="form,upos,deprel,misc")
