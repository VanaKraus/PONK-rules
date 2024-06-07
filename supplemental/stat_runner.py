from pydantic import BaseModel
from document_applicables.metrics import Metric
import document_applicables.rules as rules

from udapi.core.document import Document

import os

import requests

from csv import DictWriter

MAIN_PATH = 'data/soudni_rozh/'
CONLLU_PATH = os.path.join('./conllu', MAIN_PATH)
CSV_PATH = './soudni_rozsh.csv'
API_URL = 'http://lindat.mff.cuni.cz/services/udpipe/api/process'


# PRVNICH PET V ORIGINALS
files = os.listdir(MAIN_PATH)

metrics = [metric() for metric in Metric.get_final_children()]

class RuleJSONWrapper(BaseModel):
    rules: list[rules.RuleAPIWrapper]


parsed_rules = RuleJSONWrapper.parse_file('/home/arnold/Downloads/rule_list.json')
our_rules = [item.rule for item in parsed_rules.rules]
rules_and_names = {str(rule.model_dump()): rules.RuleBlockWrapper(rule) for rule in our_rules}

main_output = open(CSV_PATH, 'a')
writer = DictWriter(main_output, fieldnames=['name'] +
                                            [metric.metric_id for metric in metrics] +
                                            list(rules_and_names.keys()))
writer.writeheader()

#os.makedirs(CONLLU_PATH)

i = 0
for filename in files:
    print(f'started processing {filename}')
    print(f'posted {filename} to api')
    with open(MAIN_PATH + filename, 'rt') as file:
        #req = requests.post(API_URL, data={'data': 'Skákal pes přes oves.'}, params='tokenizer=&tagger=&parser=')
        req = requests.post(API_URL, data={'data': file.read()}, params='tokenizer=&tagger=&parser=')
        #print(req.request.params)
    conllu_string = req.json()['result']
    print(f'got response for {filename}')
    with open(CONLLU_PATH + filename + ".conllu", 'wt+') as conllu_filename:
        conllu_filename.write(conllu_string)
    doc = Document()
    doc.from_conllu_string(conllu_string)

    print(f'measuring mertics for {filename}')
    metric_results = {metric.metric_id: metric.apply(doc) for metric in metrics}

    print(f'measuring rules for {filename}')
    for rule in rules_and_names.values():
        rule.run(doc)
    rule_results = {name: rule.rule.application_count for (name, rule) in rules_and_names.items()}

    for rule in rules_and_names.values():
        rule.rule.reset_application_count()

    writer.writerow({'name': filename} | metric_results | rule_results)

    print(f'done processing {filename}')

    i += 1
    print(f'{i}/{len(files)}')
    if i == 1000:
        break

main_output.close()
