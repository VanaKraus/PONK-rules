from document_applicables.metrics import Metric, MetricsWrapper
from document_applicables.rules import Rule, RuleAPIWrapper, RuleBlockWrapper

from udapi.core.document import Document
from udapi.core.node import Node

from fastapi import HTTPException, UploadFile
from server.profiles import profiles

from udapi.block.read.conllu import Conllu as ConlluReader
from io import TextIOBase, TextIOWrapper


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


def mattr_calculate(doc: Document) -> list[tuple[str, float]]:
    from document_applicables.metrics import MetricMovingAverageTypeTokenRatio
    from statistics import stdev
    print("hello\n\n\n")
    metric = MetricMovingAverageTypeTokenRatio(window_size=100)
    anot_key = metric.annotation_key
    mean_mattr = metric.apply(doc)
    mattr_per_token = [node.misc.get(anot_key) for node in doc.nodes if node.misc.get(anot_key)]
    print(mattr_per_token)
    mattr_sd = stdev(mattr_per_token)
    for node in doc.nodes:
        node_value = metric.get_node_annotation(anot_key, node)
        metric.annotate_node(anot_key,
                             (node_value - mean_mattr) / (2 * mattr_sd) if node_value else 0,
                             node)
    return [(node.form, node.misc[anot_key]) for node in doc.nodes]


def word_opacity_pair_to_html(word: str, opacity: float):
    red = 255 if opacity < 0 else 0
    green = 255 if opacity > 0 else 0
    opacity = abs(opacity)
    return f'<span style="background-color:rgba({red},{green},0,{opacity})">{word} </span>'


def build_visualization_html(doc: Document):
    html = ''
    for word, opacity in mattr_calculate(doc):
        html += word_opacity_pair_to_html(word, opacity) + '\n'
    return html


def build_doc_from_file(filehandle: TextIOBase) -> Document:
    reader = ConlluReader(filehandle=filehandle)
    doc = Document()
    reader.apply_on_document(doc)
    return doc


def build_doc_from_upload(file: UploadFile) -> Document:
    return build_doc_from_file(TextIOWrapper(file.file))
