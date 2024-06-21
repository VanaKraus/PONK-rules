from document_applicables.metrics import Metric, MetricsWrapper
from document_applicables.rules import Rule, RuleAPIWrapper, RuleBlockWrapper
from udapi.core.document import Document
from fastapi import HTTPException
from server.profiles import profiles


def select_profile(profile_str: str) -> (list[Metric] | None , list[Rule] | None):
    # return appropriate set of rules and metrics based on the profiles selected
    # for now, just return the defaults
    print(f'Profile {profile_str} has been selected.')
    return profiles.get(profile_str) or (None, None)


def unwrap_metric_list(metric_wrapper_list: list[MetricsWrapper] | None):
    if metric_wrapper_list is None:
        return metric_wrapper_list
    return [item.metric for item in metric_wrapper_list]


def unwrap_rule_list(rule_wrapper_list: list[RuleAPIWrapper] | None):
    if rule_wrapper_list is None:
        return rule_wrapper_list
    return [item.rule for item in rule_wrapper_list]


def compute_metrics(metric_list: list[Metric] | None, doc: Document) -> list[dict[str, float]]:
    if metric_list is None:
        # return all available metrics
        metric_list = [subclass() for subclass in Metric.get_final_children()]
    return [{metric.metric_id: metric.apply(doc)} for metric in metric_list]


def apply_rules(rule_list: list[Rule] | None, doc: Document) -> str:
    if rule_list is None:
        rule_list = [rule() for rule in Rule.get_final_children()]
    for rule in rule_list:
        RuleBlockWrapper(rule).run(doc)
    return doc.to_conllu_string()


def try_build_conllu_from_string(conllu_string: str) -> Document:
    doc = Document()
    try:
        doc.from_conllu_string(string=conllu_string)
    except ValueError:
        raise HTTPException(status_code=422, detail='Conllu string validation failed.')
    return doc
