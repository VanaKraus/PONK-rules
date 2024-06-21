from __future__ import annotations
from udapi.core.document import Document
from udapi.core.node import Node

from typing import Iterator, Tuple, List, Literal, Union

from math import log2, sqrt
from statistics import mean

from document_applicables import Documentable

from pydantic import BaseModel, Field


class Metric(Documentable):
    """
    A base class for metrics.
    """
    def apply(self, doc: Document) -> float:
        raise NotImplementedError(f"Please define your metric's ({self.__class__.__name__}) apply method.")

    @staticmethod
    def get_word_counts(nodes: List[Node], use_lemma=False,
                        from_to: Tuple[int, int] | None = None) -> dict[str, int]:
        if from_to:
            nodes = nodes[from_to[0]:from_to[1]]
        all_words = Metric.get_node_texts(nodes, use_lemma)
        return Metric.count_occurrences_of_unique_texts(all_words)

    @staticmethod
    def count_occurrences_of_unique_texts(node_texts: List[str]):
        result = {}
        for text in node_texts:
            if result.get(text) is None:
                result[text] = 1
            else:
                result[text] += 1
        return result
    @staticmethod
    def filter_nodes_on_upos(nodes: Iterator[Node], values: List[str], negative=False) -> List[Node]:
        return [node for node in nodes if ((node.upos in values) != negative)]

    @staticmethod
    def negative_filter_nodes_on_upos(nodes: Iterator[Node], values_to_exclude: List[str]) -> List[Node]:
        return Metric.filter_nodes_on_upos(nodes, values_to_exclude, True)

    @staticmethod
    def filter_nodes_on_punct(nodes: Iterator[Node]):
        return Metric.negative_filter_nodes_on_upos(nodes, ['PUNCT'])

    @staticmethod
    def get_node_texts(nodes: Iterator[Node], use_lemma=False) -> List[str]:
        return [node.form if not use_lemma else node.lemma for node in nodes]

    @staticmethod
    def get_syllables_in_word(word: str) -> int:
        # FIXME: eeeeeh
        return sum([word.count(vocal) for vocal in ('a', 'e', 'i', 'o', 'u', 'y')])


class MetricPunctExcluding(Metric):
    filter_punct: bool = Field(default=True, description="Boolean controlling whether to exclude punctuation from the count.")

    def get_applicable_nodes(self, doc: Document) -> List[Node]:
        return self.filter_nodes_on_punct(doc.nodes) if self.filter_punct else doc.nodes


class MetricSentenceCount(Metric):
    """
    A metric for counting sentences.
    """
    metric_id: Literal['sent_count'] = 'sent_count'

    def apply(self, doc: Document) -> float:
        return len(doc.bundles)


class MetricWordCount(MetricPunctExcluding):
    """
    A metric for counting words.
    """
    metric_id: Literal['word_count'] = 'word_count'

    def apply(self, doc: Document) -> float:
        return len(self.get_applicable_nodes(doc))


class MetricSyllableCount(MetricPunctExcluding):
    """
    A metric for counting syllables.
    """
    metric_id: Literal['syllab_count'] = 'syllab_count'

    def apply(self, doc: Document) -> float:
        return sum(Metric.get_syllables_in_word(node.form) for node in self.get_applicable_nodes(doc))


class MetricCharacterCount(MetricPunctExcluding):
    """
    A metric for counting characters.
    """
    metric_id: Literal['char_count'] = 'char_count'
    count_spaces: bool = Field(default=False, description="Boolean controlling whether to include spaces in the count.")

    def apply(self, doc: Document) -> float:
        filtered_nodes = self.get_applicable_nodes(doc)
        return sum(len(node.form) for node in filtered_nodes) + \
            (len(filtered_nodes) if self.count_spaces else 0)  # TODO:fix this via reading mics


class MetricCLI(MetricPunctExcluding):
    """
    Coleman–Liau index. Measures readability in years of education necessary for successful understanding.

    The index is calculated according to this formula:

    (coef_1 * (chars / words) * 100) - (coef_2 * (sents / words) * 100) - const_1

    where chars is the number of characters in the text, words is the number of words and
    sents is the number of sentences.
    """
    metric_id: Literal['cli'] = 'cli'
    count_spaces: bool = Field(default=False, description="Boolean controlling whether to include spaces in the count.")

    coef_1: float = 0.047
    coef_2: float = 0.286
    const_1: float = 12.9

    def apply(self, doc: Document) -> float:
        sents = MetricSentenceCount().apply(doc)
        words = MetricWordCount(filter_punct=self.filter_punct).apply(doc)
        chars = MetricCharacterCount(count_spaces=self.count_spaces, filter_punct=self.filter_punct).apply(doc)
        return (self.coef_1 * (chars / words) * 100) - (self.coef_2 * (sents / words) * 100) - self.const_1


class MetricARI(MetricPunctExcluding):
    """
    Automatic readability index. Measures readability in years of education necessary for successful understanding.

    The index is calculated according to this formula:

    coef_1 * (chars / words) + coef_2 * (words / sents) - const_1

    where chars is the number of characters in the text, words is the number of words and
    sents is the number of sentences.
    """
    metric_id: Literal['ari'] = 'ari'
    count_spaces: bool = Field(default=False, description="Boolean controlling whether to include spaces in the count.")

    coef_1: float = 3.666
    coef_2: float = 0.631
    const_1: float = 19.49

    def apply(self, doc: Document) -> float:
        sents = MetricSentenceCount().apply(doc)
        words = MetricWordCount(filter_punct=self.filter_punct).apply(doc)
        chars = MetricCharacterCount(count_spaces=self.count_spaces, filter_punct=self.filter_punct).apply(doc)
        return self.coef_1 * (chars / words) + self.coef_2 * (words / sents) - self.const_1


class MetricHapaxCount(MetricPunctExcluding):
    """
    The count of words that appear in the text only once.
    """
    metric_id: Literal['num_hapax'] = 'num_hapax'
    use_lemma: bool = Field(default=True, description="Boolean controlling whether lemma should be used instead of word form for the calculation.")

    def apply(self, doc: Document) -> float:
        counts = list(self.get_word_counts(self.get_applicable_nodes(doc), self.use_lemma).values())
        return counts.count(1)


class MetricEntropy(MetricPunctExcluding):
    """
    Measures the entropy of the text, considering either lemmas or word forms.
    """
    metric_id: Literal['entropy'] = 'entropy'
    use_lemma: bool = Field(default=True, description="Boolean controlling whether lemma should be used instead of word form for the calculation.")

    def apply(self, doc: Document) -> float:
        counts = self.get_word_counts(self.get_applicable_nodes(doc), self.use_lemma).values()
        n_words = sum(counts)
        probs = map(lambda x: x / n_words, counts)
        return -sum(prob * log2(prob) for prob in probs)


class MetricTTR(MetricPunctExcluding):
    """
    Type-token ratio. Measures the ratio of types (lemmas) to tokens.
    """
    metric_id: Literal['ttr'] = 'ttr'

    def apply(self, doc: Document) -> float:
        counts = Metric.get_word_counts(self.get_applicable_nodes(doc), use_lemma=True)
        return len(counts) / sum(counts.values())


class MetricVerbDistance(Metric):
    """
    Measures the average distance between verbs.
    """
    # MAYBE TODO: should we include punct here?
    metric_id: Literal['verb_dist'] = 'verb_dist'
    include_inf: bool = True

    def apply(self, doc: Document) -> float:
        last_verb_index = 0
        total_distance = 0
        verbs = 0
        nodes = list(doc.nodes)
        # FIXME: iterate over trees
        for i in range(len(nodes)):
            node = nodes[i]
            if node.upos == 'VERB' and (self.include_inf or node.feats['VerbForm'] == 'Fin'):
                total_distance += max(0, (i - last_verb_index - 1))
                last_verb_index = i
                verbs += 1
        total_distance += len(nodes) - last_verb_index
        return total_distance / max(1, verbs)


class MetricActivity(Metric):
    """
    Measures the activity of the text, i.e. the ratio of (#verbs)/(#verbs + #adjectives).
    """
    metric_id: Literal['activity'] = 'activity'

    def apply(self, doc: Document) -> float:
        nodes = list(doc.nodes)
        return max(1, len(Metric.filter_nodes_on_upos(nodes, ['VERB']))) /\
            max(1, len(Metric.filter_nodes_on_upos(nodes, ['VERB', 'ADJ'])))


class MetricHPoint(MetricPunctExcluding):
    """
    Measures h-point, i.e. the index of the first non-function word when sorted by frequency.
    """
    metric_id: Literal['hpoint'] = 'hpoint'
    use_lemma: bool = Field(default=True, description="Boolean controlling whether lemma should be used instead of word form for the calculation.")

    def apply(self, doc: Document) -> float:
        counts = list(self.get_word_counts(self.get_applicable_nodes(doc), self.use_lemma).values())
        counts.sort(reverse=True)
        for i in range(len(counts)):
            if i + 1 == counts[i]:
                return counts[i]
            if i + 1 > counts[i]:
                i = i - 1
                j = i + 1
                fi = counts[i]
                fj = counts[j]
                return (fi * j - fj * i) / (j - i + fi - fj)
        return 0


class MetricAverageTokenLength(MetricPunctExcluding):
    """
    Measures the average length of tokens.
    """
    metric_id: Literal['atl'] = 'atl'


    def apply(self, doc: Document) -> float:
        total_tokens = MetricWordCount(filter_punct=self.filter_punct).apply(doc)
        total_chars = MetricCharacterCount(filter_punct=self.filter_punct).apply(doc)
        return total_chars / total_tokens


class MetricMovingAverageTypeTokenRatio(MetricPunctExcluding):
    """
    Measures Type-token ratio over chunks of text of length window_size and averages them.
    """
    metric_id: Literal['mattr'] = 'mattr'
    use_lemma: bool = Field(default=True, description="Boolean controlling whether lemma should be used instead of word form for the calculation.")

    window_size: int = 100

    annotation_key: str = Field(default='mattr', hidden=True)

    def add_to_annotation_list(self, value: float, node: Node):
        self.annotate_node(self.annotation_key,
                           (self.get_node_annotation(self.annotation_key, node) or []) + [value],
                           node)

    def calc_avg_value(self, node: Node):
        self.annotate_node(self.annotation_key,
                           mean(self.get_node_annotation(self.annotation_key, node)),
                           node)

    def apply(self, doc: Document) -> float:
        # FIXME: this is horribly slow
        # FIXEDME: this is now less slow
        total_words = MetricWordCount(filter_punct=self.filter_punct).apply(doc)
        big_sum = 0
        filtered_nodes = self.get_applicable_nodes(doc)
        filtered_texts = self.get_node_texts(filtered_nodes, self.use_lemma)

        for i in range(int(total_words) - self.window_size + 1):
            uniques = set(filtered_texts[i:i+self.window_size])
            count = len(uniques)
            big_sum += count
            for node in filtered_nodes[i:i+self.window_size]:
                self.add_to_annotation_list(count / self.window_size, node)

        if total_words >= self.window_size:
            for node in filtered_nodes:
                self.calc_avg_value(node)
        return big_sum / (self.window_size * (total_words - self.window_size + 1))


class MetricMovingAverageMorphologicalRichness(MetricPunctExcluding):
    """
    Measures the difference between MATTR using word forms and MATTR using lemmas for the same window size.
    """
    metric_id: Literal['mamr'] = 'mamr'

    window_size: int = 100

    annotation_key1: str = Field(default='mamr1', hidden=True)
    annotation_key2: str = Field(default='mamr2', hidden=True)

    def apply(self, doc: Document) -> float:
        return MetricMovingAverageTypeTokenRatio(use_lemma=False,
                                                 filter_punct=self.filter_punct,
                                                 window_size=self.window_size,
                                                 annotation_key=self.annotation_key1).apply(doc) - \
            MetricMovingAverageTypeTokenRatio(use_lemma=True,
                                              filter_punct=self.filter_punct,
                                              window_size=self.window_size,
                                              annotation_key=self.annotation_key2).apply(doc)


class MetricFleschReadingEase(MetricPunctExcluding):
    """
    Flesch reading ease index. Measures the difficulty of reading and comprehending the test on a scale from 0 to 100,
    with 100 being the easiest to understand and 0 being the hardest.

    The index is calculated according to this formula:

    const_1 - coef_1 * (words / sents) - coef_2 * (syllabs / words)

    where words is the number of words in the text, sents is the number of sentences and syllabs is the number of
    syllables
    """
    metric_id: Literal['fre'] = 'fre'
    count_spaces: bool = Field(default=False, description="Boolean controlling whether to include spaces in the count.")

    coef_1: float = 1.672
    coef_2: float = 62.18
    const_1: float = 206.935

    def apply(self, doc: Document) -> float:
        sents = MetricSentenceCount().apply(doc)
        words = MetricWordCount(filter_punct=self.filter_punct).apply(doc)
        syllabs = MetricSyllableCount(filter_punct=self.filter_punct).apply(doc)
        return self.const_1 - self.coef_1 * (words / sents) - self.coef_2 * (syllabs / words)


class MetricFleschKincaidGradeLevel(MetricPunctExcluding):
    """
    Flesch-Kincaid grade level index. Measures readability in years of education necessary for successful understanding.

    The index is calculated according to this formula:

    coef_1 * (words / sents) + coef_2 * (syllabs / words) - const_1

    where words is the number of words in the text, sents is the number of sentences and syllabs is the number of
    syllables
    """
    metric_id: Literal['fkgl'] = 'fkgl'
    count_spaces: bool = Field(default=False, description="Boolean controlling whether to include spaces in the count.")

    coef_1: float = 0.52
    coef_2: float = 9.133
    const_1: float = 16.393

    def apply(self, doc: Document) -> float:
        sents = MetricSentenceCount().apply(doc)
        words = MetricWordCount(filter_punct=self.filter_punct).apply(doc)
        syllabs = MetricSyllableCount(filter_punct=self.filter_punct).apply(doc)
        return self.coef_1 * (words / sents) + self.coef_2 * (syllabs / words) - self.const_1


class PolysyllabicMetric(MetricPunctExcluding):
    """
    A base class for metrics utilizing a threshold of syllabic length.
    """
    syllab_threshold: int = 3

    def _is_word_complex(self, word: str):
        return Metric.get_syllables_in_word(word) > self.syllab_threshold


class MetricGunningFog(PolysyllabicMetric):
    """
    Gunning fog index. Measures readability in years of education necessary for successful understanding.

    The index is calculated according to this formula:

    coef_1 * ((words/sents) + coef_2 * (complex_words/words))

    where words is the number of words in the text, sents is the number of sentences and complex_words is the number of
    words longer than the syllabic threshold.
    """
    metric_id: Literal['gf'] = 'gf'

    coef_1: float = 0.4
    coef_2: float = 100

    def apply(self, doc: Document) -> float:
        sents = MetricSentenceCount().apply(doc)
        words = MetricWordCount(filter_punct=self.filter_punct).apply(doc)
        complex_words = len([node for node in doc.nodes if self._is_word_complex(node.form)])
        return self.coef_1 * ((words/sents) + self.coef_2 * (complex_words/words))


# Modified version of SMOG. We do not rely on sampling
class MetricSMOG(PolysyllabicMetric):
    """
    SMOG index. Measures readability in years of education necessary for successful understanding.

    The index is calculated according to this formula:

    coef_1 * sqrt(complex_words * 90) / sents + const_1

    where words is the number of words in the text, sents is the number of sentences and complex_words is the number of
    words longer than the syllabic threshold.

    The formula for this metric is modified, as the original relied on random sampling from the text.
    """
    metric_id: Literal['smog'] = 'smog'
    coef_1: float = 1.043
    const_1: float = 3.1291

    def apply(self, doc: Document) -> float:
        sents = MetricSentenceCount().apply(doc)
        complex_words = len([node for node in self.get_applicable_nodes(doc) if self._is_word_complex(node.form)])
        return self.coef_1 * sqrt(complex_words * 90) / sents + self.const_1


# class MetricAvgPredSubDist(Metric):
#     metric_id: Literal['avg_pred_sub'] = 'avg_pred_sub'
#     include_clausal_subjects: bool = False
#
#     # YUCK
#     def _get_pred_subj_dist(self, tree):
#         import util
#         for node in tree.descendants:
#             if node.udeprel == 'nsubj' or (self.include_clausal_subjects and node.udeprel == 'csubj'):
#                 # locate predicate
#                 pred = node.parent
#
#                 # if the predicate is analytic, select the (non-conditional) auxiliary or the copula
#                 if finite_verbs := [
#                     nd for nd in pred.children if nd.udeprel == 'cop' or (nd.udeprel == 'aux' and nd.feats['Mood'] != 'Cnd')
#                 ]:
#                     pred = finite_verbs[0]
#
#                 # locate subject
#                 subj = node
#                 if node.udeprel == 'csubj':
#                     clause = util.get_clause(node, without_subordinates=True, without_punctuation=True, node_is_root=True)
#                     if node.ord < pred.ord:
#                         subj = clause[-1]
#                     else:
#                         subj = clause[0]
#
#                 return abs(subj.ord - pred.ord)
#         return None
#
#     def apply(self, doc: Document) -> float:
#         total_sents = len(doc.bundles)
#         total_dist = 0
#         for bundle in doc.bundles:
#             if not 0 < len(bundle.trees) < 2:
#                 raise ValueError('Too many trees in a bundle :(')
#             tree = bundle.trees[0]
#             dist = self._get_pred_subj_dist(tree)
#             if dist:
#                 total_dist += dist
#             else:
#                 ... # really dont know what should happen if this is the case
#         return total_dist / total_sents

class MetricsWrapper(BaseModel):
    metric: Union[*Metric.get_final_children()] = Field(..., discriminator='metric_id')


class DocMetricHandler:
    def __init__(self, doc: Document):
        self.doc = doc
