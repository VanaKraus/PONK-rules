from document_applicables.metrics import Metric, MetricsWrapper
from document_applicables.rules import Rule, RuleAPIWrapper, RuleBlockWrapper

from udapi.core.document import Document
from udapi.core.node import Node

from fastapi import HTTPException, UploadFile
from server.profiles import profiles

from udapi.block.read.conllu import Conllu as ConlluReader
from io import TextIOBase, TextIOWrapper

import re


def select_profile(profile_str: str) -> (list[Metric], list[Rule]):
    # return appropriate set of rules and metrics based on the profiles selected
    # for now, just return the defaults
    print(f'Profile {profile_str} has been selected.')
    metrics, rules = profiles.get(profile_str) or (None, None)
    if metrics is None:
        # return all available metrics
        metrics = [metric() for metric in Metric.get_final_children()]
    if rules is None:
        rules = [rule() for rule in Rule.get_final_children()]
    return metrics, rules



def unwrap_metric_list(metric_wrapper_list: list[MetricsWrapper] | None) -> list[Metric]:
    if metric_wrapper_list is None:
        return [metric() for metric in Metric.get_final_children()]
    return [item.metric for item in metric_wrapper_list]


def unwrap_rule_list(rule_wrapper_list: list[RuleAPIWrapper] | None) -> list[Rule]:
    if rule_wrapper_list is None:
        return [rule() for rule in Rule.get_final_children()]
    return [item.rule for item in rule_wrapper_list]


def compute_metrics(metric_list: list[Metric], doc: Document) -> list[dict[str, float]]:
    return [{re.sub(r'([a-z])([A-Z])', r'\1 \2',
                    metric.__class__.__name__.removeprefix('Metric')): metric.apply(doc)}
            for metric in metric_list]


def apply_rules(rule_list: list[Rule], doc: Document) -> str:
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


def mattr_calculate(doc: Document, window_size: int) -> list[tuple[str, float]]:
    from document_applicables.metrics import MetricMovingAverageTypeTokenRatio
    from statistics import stdev
    metric = MetricMovingAverageTypeTokenRatio(window_size=window_size, annotate=True)
    anot_key = metric.annotation_key
    mean_mattr = metric.apply(doc)
    mattr_per_token = [metric.get_node_annotation(anot_key, node) for node in doc.nodes
                       if metric.get_node_annotation(anot_key, node)]
    mattr_sd = stdev(mattr_per_token)
    for node in doc.nodes:
        node_value = metric.get_node_annotation(anot_key, node)
        metric.annotate_node(anot_key,
                             (node_value - mean_mattr) / (2 * mattr_sd) if node_value else 0,
                             node)
    return [(node.form, node.misc[anot_key]) for node in doc.nodes]


def mamr_calculate(doc: Document, window_size: int) -> list[tuple[str, float]]:
    from document_applicables.metrics import MetricMovingAverageMorphologicalRichness
    from statistics import stdev
    metric = MetricMovingAverageMorphologicalRichness(window_size=window_size, annotate=True)
    def get_node_mamr(node: Node):
        anot1 = metric.get_node_annotation(anot_key1, node)
        anot2 = metric.get_node_annotation(anot_key2, node)
        return (anot1 - anot2) if anot1 and anot2 else None
    anot_key1 = metric.annotation_key1
    anot_key2 = metric.annotation_key2
    mean_mamr = metric.apply(doc)
    mamr_per_token = [get_node_mamr(node)
                      for node in doc.nodes
                      if get_node_mamr(node)]
    mamr_sd = stdev(mamr_per_token)
    for node in doc.nodes:
        node_value = get_node_mamr(node)
        metric.annotate_node('mamr',
                             (node_value - mean_mamr) / (2 * mamr_sd) if node_value else 0,
                             node)
    return [(node.form, node.misc['mamr']) for node in doc.nodes]


def word_opacity_pair_to_html(word: str, opacity: float):
    red = 255 if opacity < 0 else 0
    green = 255 if opacity > 0 else 0
    opacity = abs(opacity)
    return f'<span style="background-color:rgba({red},{green},0,{opacity})">{word} </span>'


def build_visualization_html(doc: Document, window_size: int):
    html = ''
    for word, opacity in mattr_calculate(doc, window_size):
        html += word_opacity_pair_to_html(word, opacity) + '\n'
    return html


def build_doc_from_file(filehandle: TextIOBase) -> Document:
    reader = ConlluReader(filehandle=filehandle)
    doc = Document()
    reader.apply_on_document(doc)
    return doc


def build_doc_from_upload(file: UploadFile) -> Document:
    return build_doc_from_file(TextIOWrapper(file.file))
