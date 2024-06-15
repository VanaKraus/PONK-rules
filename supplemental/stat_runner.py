from document_applicables.metrics import Metric
from server.profiles import profiles
from document_applicables.rules import RuleBlockWrapper

from udapi.core.document import Document

import os
from pathlib import Path

from sys import argv

import requests

from csv import DictWriter

NUM_FILES_PER_FOLDER = 100
from statistics import stdev

ENCODING = 'utf-8'
CSV_SUFFIX = ''

dirs = argv[1:]
if not dirs:
    print('No args given.')
    exit(1)

for directory in dirs:
    MAIN_PATH = directory
    CONLLU_PATH = os.path.join('./conllu', MAIN_PATH)
    CSV_PATH = os.path.join('./output', MAIN_PATH.replace('/', '-') + CSV_SUFFIX + '.csv')
    API_URL = 'http://lindat.mff.cuni.cz/services/udpipe/api/process'

    files = os.listdir(MAIN_PATH)

    metrics = [metric() for metric in Metric.get_final_children()]

    rules = profiles['minimal'][1]
    names_of_meas = ['RuleDoubleAdpos:max_allowable_distance',
                     'RulePredSubjDistance:max_distance',
                     'RulePredObjDistance:max_distance', 'RuleInfVerbDistance:max_distance',
                     'RuleMultiPartVerbs:max_distance', 'RuleLongSentences:max_length',
                     'RulePredAtClauseBeginning:max_order', 'RuleTooFewVerbs:min_verb_frac',
                     'RuleTooManyNegations:max_negation_frac',
                     'RuleTooManyNegations:max_allowable_negations']

    names_of_sds = [name + ':sd' for name in names_of_meas]
    names_of_measurements = [name + ':meas' for name in names_of_meas]

    main_output = open(CSV_PATH, 'w')
    writer = DictWriter(main_output, fieldnames=['name'] +
                                                [metric.metric_id for metric in metrics] +
                                                [rule.rule_id for rule in rules] +
                                                names_of_meas + names_of_sds + names_of_measurements
                        )
    writer.writeheader()

    #os.makedirs(CONLLU_PATH)

    i = 0
    for filename in files:
        print(f'started processing {filename}')
        conllu_full_path = Path(CONLLU_PATH + filename + ".conllu")
        doc = Document()
        if not os.path.isfile(conllu_full_path):
            with open(MAIN_PATH + filename, 'rt', encoding=ENCODING) as file:
                #req = requests.post(API_URL, data={'data': 'Skákal pes přes oves.'}, params='tokenizer=&tagger=&parser=')
                req = requests.post(API_URL, data={'data': file.read()}, params='tokenizer=&tagger=&parser=')
                #print(req.request.params)
            conllu_string = req.json()['result']
            if not os.path.exists(conllu_full_path.parent):
                conllu_full_path.parent.mkdir(parents=True)
            with open(conllu_full_path, 'wt+') as conllu_filename:
                conllu_filename.write(conllu_string)
            doc.from_conllu_string(conllu_string)
        else:
            doc = Document(str(conllu_full_path))

        metric_results = {metric.metric_id: metric.apply(doc) for metric in metrics}

        for rule in rules:
            RuleBlockWrapper(rule).run(doc)
        rule_results = {rule.rule_id: rule.application_count for rule in rules}
        avg_measures = [{rule.rule_id + ':' + name: value for name, value in rule.average_measured_values.items()} for
                        rule in rules if rule.average_measured_values]
        sds = [{rule.rule_id + ':' + name + ':sd': stdev(value) for name, value in rule.measured_values.items()} for
               rule in rules if rule.average_measured_values]
        measurements = [{rule.rule_id + ':' + name + ':meas': value for name, value in rule.measured_values.items()} for
                        rule in rules if rule.average_measured_values]
        [rule_results.update(meas) for meas in avg_measures]
        [rule_results.update(sd) for sd in sds]
        [rule_results.update(meas) for meas in measurements]

        for rule in rules:
            rule.reset_application_count()

        writer.writerow({'name': filename} | metric_results | rule_results)

        print(f'done processing {filename}')

        i += 1
        print(f'{i}/{len(files)}')
        if i == NUM_FILES_PER_FOLDER:
            break

    main_output.close()
