from __future__ import annotations
from udapi.core.document import Document

from typing import Iterator, Tuple, Callable

from math import log2

from utils import StringBuildable


class Metric(StringBuildable):
    def __init__(self):
        pass

    def apply(self, doc: Document) -> int:
        raise NotImplementedError(f"Please define your metric's ({self.__class__.__name__}) apply method.")

    def get_word_counts(self, doc: Document, use_lemma=False) -> Iterator[Tuple[str, int]]:
        all_words = list(node.form if not use_lemma else node.lemma for node in doc.nodes)
        unique_words = set(all_words)
        counts = map(lambda x: all_words.count(x), unique_words)
        return zip(unique_words, counts)


class HapaxCount(Metric):
    @StringBuildable.parse_string_args(use_lemma=bool)
    def __init__(self, use_lemma=True):
        super().__init__()
        self.use_lemma = use_lemma

    def apply(self, doc:Document) -> int:
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

    def apply(self, doc: Document) -> int:
        counts = [item[1] for item in self.get_word_counts(doc, self.use_lemma)]
        n_words = sum(counts)
        probs = map(lambda x: x/n_words, counts)
        return -sum(prob * log2(prob) for prob in probs)

    @classmethod
    def id(cls):
        return "entropy"
