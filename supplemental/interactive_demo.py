import rich
import requests
from udapi.core.document import Document
from document_applicables.metrics import Metric
import document_applicables.rules as rules
from pydantic import BaseModel
import os
API_URL = 'http://lindat.mff.cuni.cz/services/udpipe/api/process'

rich.print("Thle je interaktivní demo pro [underline]PONK-rulezzz[/underline]")
while True:
    req = requests.post(API_URL, data={'data': input('Dej text\n')}, params='tokenizer=&tagger=&parser=')
    os.system('clear')
    conllu_string = req.json()['result']
    doc = Document()
    doc.from_conllu_string(conllu_string)

    metrics = [metric() for metric in Metric.get_final_children()]
    metric_results = {metric.metric_id: metric.apply(doc) for metric in metrics}

    # class RuleJSONWrapper(BaseModel):
    #     rules: list[rules.RuleAPIWrapper]
    # parsed_rules = RuleJSONWrapper.parse_file('/home/arnold/Downloads/rule_list.json')
    # our_rules = [item.rule for item in parsed_rules.rules]
    # rules_and_names = {str(rule.model_dump()): rules.RuleBlockWrapper(rule) for rule in our_rules}


    for rule in rules.Rule.get_final_children():
        rules.RuleBlockWrapper(rule()).run(doc)
    # rule_results = {name: rule.rule.application_count for (name, rule) in rules_and_names.items()}
    #
    # for rule in rules_and_names.values():
    #     rule.rule.reset_application_count()

    to_print = []
    rules_applied_all = {}
    for node in doc.nodes:
        underline = False
        for misc in node.misc.keys():
            if 'Rule' in misc:
                underline = True
                break
        if underline:
            to_print.append(f'[underline red]{node.form}[/underline red]')
            #TADY TO KDYZTAK UMAZ
            rules_applied = set([misc for misc in node.misc.keys() if "Rule" in misc])
            rules_merged = {rule: (rules_applied_all.get(rule) or []) + [node.form] for rule in rules_applied}
            rules_applied_all.update(rules_merged)

        else:
            to_print.append(node.form)
    cons = rich.get_console()
    cons.print(*to_print, highlight=False)
    cons.print(metric_results)
    cons.print(rules_applied_all)
    print("\n\n")
    if input('Další? y/n') == 'n':
        break




