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


class SentenceCount(Metric):
    @StringBuildable.parse_string_args()
    def __init__(self):
        super().__init__()

    def apply(self, doc: Document) -> float:
        return len(doc.bundles)

    @classmethod
    def id(cls):
        return "sent_count"


class WordCount(Metric):
    @StringBuildable.parse_string_args(filter_punct=bool)
    def __init__(self, filter_punct=True):
        super().__init__()
        self.filter_punct = filter_punct

    def apply(self, doc: Document) -> float:
        return len(Metric.filter_nodes_on_upos(doc.nodes, ['PUNCT'] if self.filter_punct else []))

    @classmethod
    def id(cls):
        return "word_count"


class CharacterCount(Metric):
    @StringBuildable.parse_string_args(count_spaces=bool, filter_punct=bool)
    def __init__(self, count_spaces=False, filter_punct=True):
        super().__init__()
        self.count_spaces = count_spaces
        self.filter_punct = filter_punct

    def apply(self, doc: Document) -> float:
        filtered_nodes = Metric.filter_nodes_on_upos(doc.nodes, ['PUNCT'] if self.filter_punct else [])
        return sum(len(node.form) for node in filtered_nodes) + \
            (len(filtered_nodes) if self.count_spaces else 0)  # TODO:fix this via reading mics

    @classmethod
    def id(cls):
        return "char_count"


class CLI(Metric):
    @StringBuildable.parse_string_args(use_lemma=bool, count_spaces=bool,
                                       filter_punct=bool, coef_1=float,
                                       coef_2=float, const_1=float)
    def __init__(self, use_lemma=True, count_spaces=False, filter_punct=True,
                 coef_1=0.047, coef_2=0.286, const_1=12.9):
        super().__init__()
        self.use_lemma = use_lemma
        self.count_spaces = count_spaces
        self.filter_punct = filter_punct
        self.coef_1 = coef_1
        self.coef_2 = coef_2
        self.const_1 = const_1

    def apply(self, doc: Document) -> float:
        sents = SentenceCount().apply(doc)
        words = WordCount(self.filter_punct).apply(doc)
        chars = CharacterCount(self.count_spaces, self.filter_punct).apply(doc)
        return self.coef_1 * (chars/words) * 100 - self.coef_2 * (sents/words) * 100 - self.const_1

    @classmethod
    def id(cls):
        return "cli"


class ARI(Metric):
    @StringBuildable.parse_string_args(use_lemma=bool, count_spaces=bool,
                                       filter_punct=bool, coef_1=float,
                                       coef_2=float, const_1=19.49)
    def __init__(self, use_lemma=True, count_spaces=False, filter_punct=True,
                 coef_1=3.666, coef_2=0.631, const_1=19.49):
        super().__init__()
        self.use_lemma = use_lemma
        self.count_spaces = count_spaces
        self.filter_punct = filter_punct
        self.coef_1 = coef_1
        self.coef_2 = coef_2
        self.const_1 = const_1

    def apply(self, doc: Document) -> float:
        sents = SentenceCount().apply(doc)
        words = WordCount(self.filter_punct).apply(doc)
        chars = CharacterCount(self.count_spaces, self.filter_punct).apply(doc)
        return self.coef_1 * (chars/words) + self.coef_2 * (words/sents) - self.const_1

    @classmethod
    def id(cls):
        return "ari"


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
