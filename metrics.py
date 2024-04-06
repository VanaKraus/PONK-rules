from __future__ import annotations
from udapi.core.document import Document

from typing import Iterator, Tuple, Callable

from math import log2


class Metric:
    def __init__(self):
        pass

    def apply(self, doc: Document) -> int:
        raise NotImplementedError("Please define your metric")

    @staticmethod
    def id():
        raise NotImplementedError("Please give your metric an id")

    def get_word_counts(self, doc: Document, use_lemma=False) -> Iterator[Tuple[str, int]]:
        all_words = list(node.form if not use_lemma else node.lemma for node in doc.nodes)
        unique_words = set(all_words)
        counts = map(lambda x: all_words.count(x), unique_words)
        return zip(unique_words, counts)

    @staticmethod
    def get_metrics() -> dict[str, type]:
        return {sub.id(): sub for sub in Metric.__subclasses__()}

    @staticmethod
    def build_from_string(string: str) -> Metric:
        metric_id, args = string.split(':')[0], string.split(':')[1:]
        args = {arg.split('=')[0]: arg.split('=')[1:] for arg in args}
        return Metric.get_metrics()[metric_id](**args)


class HapaxCount(Metric):
    def __init__(self, use_lemma="True"):
        super().__init__()
        self.use_lemma = use_lemma == "True"

    def apply(self, doc:Document) -> int:
        counts = [item[1] for item in super().get_word_counts(doc, self.use_lemma)]
        return counts.count(1)

    @staticmethod
    def id():
        return "num_hapax"


class Entropy(Metric):
    def __init__(self, use_lemma="True"):
        Metric.__init__(self)
        self.use_lemma = use_lemma == "True"

    def apply(self, doc: Document) -> int:
        counts = [item[1] for item in self.get_word_counts(doc, self.use_lemma)]
        n_words = sum(counts)
        probs = map(lambda x: x/n_words, counts)
        return -sum(prob * log2(prob) for prob in probs)

    @staticmethod
    def id():
        return "entropy"
