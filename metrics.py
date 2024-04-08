from __future__ import annotations
from udapi.core.document import Document
from udapi.core.node import Node

from typing import Iterator, Tuple, List

from math import log2

from utils import StringBuildable


class Metric(StringBuildable):
    def __init__(self):
        pass

    def apply(self, doc: Document) -> float:
        raise NotImplementedError(f"Please define your metric's ({self.__class__.__name__}) apply method.")

    @staticmethod
    def get_word_counts(doc: Document, use_lemma=False, filter_punct=True) -> Iterator[Tuple[str, int]]:
        filtered_nodes = Metric.filter_nodes_on_upos(doc.nodes, ['PUNCT'] if filter_punct else [])
        all_words = Metric.get_node_texts(filtered_nodes, use_lemma)
        unique_words = set(all_words)
        counts = map(lambda x: all_words.count(x), unique_words)
        return zip(unique_words, counts)

    @staticmethod
    def filter_nodes_on_upos(nodes: Iterator[Node], values_to_exclude: Iterator[str]) -> List[Node]:
        return [node for node in nodes if node.upos not in values_to_exclude]

    @staticmethod
    def get_node_texts(nodes: Iterator[Node], use_lemma=False):
        return [node.form if not use_lemma else node.lemma for node in nodes]


class HapaxCount(Metric):
    @StringBuildable.parse_string_args(use_lemma=bool)
    def __init__(self, use_lemma=True):
        super().__init__()
        self.use_lemma = use_lemma

    def apply(self, doc: Document) -> float:
        counts = [item[1] for item in super().get_word_counts(doc, self.use_lemma)]
        return counts.count(1)

    @classmethod
    def id(cls):
        return "num_hapax"


class Entropy(Metric):
    @StringBuildable.parse_string_args(use_lemma=bool)
    def __init__(self, use_lemma=True):
        Metric.__init__(self)
        self.use_lemma = use_lemma

    def apply(self, doc: Document) -> float:
        counts = [item[1] for item in self.get_word_counts(doc, self.use_lemma)]
        n_words = sum(counts)
        probs = map(lambda x: x/n_words, counts)
        return -sum(prob * log2(prob) for prob in probs)

    @classmethod
    def id(cls):
        return "entropy"
