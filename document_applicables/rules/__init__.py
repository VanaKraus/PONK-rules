from __future__ import annotations

from numbers import Number
from typing import Literal, Any, Union
import os

import sys

from derinet.lexicon import Lexicon
from udapi.core.block import Block
from udapi.core.node import Node
from udapi.core.document import Document
from pydantic import BaseModel, Field

from document_applicables import Documentable
from document_applicables.rules import util


RULE_ANNOTATION_PREFIX = 'PonkApp1'


print('rules: loading DeriNet', file=sys.stderr)

derinet_lexicon = Lexicon()
# FIXME: choose a better path
derinet_lexicon.load('_local/derinet-2-3.tsv')

print('rules: DeriNet loaded', file=sys.stderr)


class Rule(Documentable):
    detect_only: bool = True
    process_id: str = Field(default_factory=lambda: os.urandom(4).hex(), hidden=True)
    modified_roots: set[Any] = Field(default=set(), hidden=True)  # FIXME: This should not be Any, but rather Root
    application_count: int = Field(default=0, hidden=True)
    average_measured_values: dict[str, float] = Field(default={}, hidden=True)
    measured_values: dict[str, list[float]] = Field(default={}, hidden=True)

    def model_post_init(self, __context: Any) -> None:
        self.process_id = Rule.get_application_id()

    @staticmethod
    def get_application_id():
        return os.urandom(4).hex()

    @classmethod
    def id(cls):
        return cls.__name__

    def annotate_node(self, annotation: str, *node: Node, flag: str | None = None):
        key = f"{RULE_ANNOTATION_PREFIX}:{self.__class__.id()}:{self.process_id}"
        if flag:
            key += f":{flag}"
        super().annotate_node(key, annotation, *node)

    def do_measurement_calculations(self, m_name: str, m_value: float):
        self.average_measured_values[m_name] = (
            (self.average_measured_values.get(m_name) or 0) * self.application_count + m_value
        ) / (self.application_count + 1)
        self.measured_values[m_name] = (self.measured_values.get(m_name) or []) + [m_value]
        # FIXME: this is slow, but probably not relevant

    def annotate_measurement(self, m_name: str, m_value: Number, *node):
        self.annotate_node(str(m_value), *node, flag=f"measur:{m_name}")
        self.do_measurement_calculations(m_name=m_name, m_value=m_value)

    def annotate_parameter(self, p_name: str, p_value: Number, *node):
        self.annotate_node(str(p_value), *node, flag=f"param:{p_name}")

    def after_process_document(self, document):
        for root in self.modified_roots:
            root.text = root.compute_text()

    def advance_application_id(self):
        self.process_id = self.get_application_id()
        self.application_count += 1

    def reset_application_count(self):
        self.application_count = 0
        self.average_measured_values = {}
        self.measured_values = {}

    def process_node(self, node: Node):
        raise NotImplementedError('A rule is expected to have a \'process_node\' method.')


class RuleDoubleAdpos(Rule):
    """Capture coordinations where both elements could be headed by a preposition \
    but only the first is.

    Supports transformations.

    Inspiration: Sgall & Panevová (2014, p. 77).

    Attributes:
        max_allowable_distance (int): how far apart the coordination elements can be \
            to not be considered an issue (elements separated by one token only would \
            have distance of 2).
    """

    rule_id: Literal['RuleDoubleAdpos'] = 'RuleDoubleAdpos'
    max_allowable_distance: int = 4

    def process_node(self, node: Node):
        if node.deprel != 'conj' or node.parent.parent is None:  # in case parent_adpos doesn't have a parent
            return  # nothing we can do for this node, bail

        coord_el2 = node

        # find an adposition present in the coordination
        for parent_adpos in [nd for nd in coord_el2.siblings if nd.udeprel == "case" and nd.upos == "ADP"]:
            coord_el1 = parent_adpos.parent

            # check that the two coordination elements have the same case
            if coord_el2.feats["Case"] != coord_el1.feats["Case"]:
                continue

            # check that the two coordination elements aren't too close to each-other
            if (dst := coord_el2.ord - coord_el1.ord) <= self.max_allowable_distance:
                continue

            # check that the second coordination element doesn't already have an adposition
            if not [nd for nd in coord_el2.children if nd.lemma == parent_adpos.lemma] and not [
                nd for nd in coord_el2.children if nd.upos == "ADP"
            ]:
                cconj = ([None] + [c for c in coord_el2.children if c.deprel in ('cc', 'punct') and c.lemma != '.'])[-1]

                if not self.detect_only:
                    correction = util.clone_node(
                        parent_adpos,
                        coord_el2,
                        filter_misc_keys=r"^(?!Rule).*",
                        include_subtree=True,
                    )

                    correction.form = parent_adpos.form.lower()
                    if cconj:
                        correction.shift_after_subtree(cconj)
                    else:
                        correction.shift_before_node(coord_el2.descendants(add_self=True)[0])

                    for node_to_annotate in correction.descendants(add_self=True):

                        self.annotate_node('add', node_to_annotate)

                if cconj:
                    self.annotate_node('cconj', cconj)
                    self.annotate_measurement('max_allowable_distance', dst, cconj, parent_adpos, coord_el1, coord_el2)
                    self.annotate_parameter(
                        'max_allowable_distance', self.max_allowable_distance, cconj, parent_adpos, coord_el1, coord_el2
                    )
                self.annotate_node('orig_adpos', parent_adpos)
                self.annotate_node('coord_el1', coord_el1)
                self.annotate_node('coord_el2', coord_el2)

                self.advance_application_id()

                if not self.detect_only:
                    self.modified_roots.add(cconj.root)


class RulePassive(Rule):
    """Capture be-passives.

    Inspiration: Šamánková & Kubíková (2022, pp. 39-40), Šváb (2023, p. 27).
    """

    rule_id: Literal['RulePassive'] = 'RulePassive'

    def process_node(self, node):
        if node.deprel == 'aux:pass':
            parent = node.parent

            self.annotate_node('aux', node)
            self.annotate_node('participle', parent)

            self.advance_application_id()


class RulePredSubjDistance(Rule):
    """Capture subjects that are too distant from their predicates \
        (or their auxiliaries/copulas when present).

    Inspiration: Šamánková & Kubíková (2022, pp. 53-54), Šváb (2023, pp. 21–22).

    Attributes:
        max_distance (int): how far apart the subject and the predicate can be \
            to not be considered an issue (subject and predicate right next to each other \
            would have distance of 1).
        include_clausal_subjects (bool): take clausal subjects into consideration. Token \
            from the clause closest to the predicate is considered for the distance measurement.
    """

    rule_id: Literal['RulePredSubjDistance'] = 'RulePredSubjDistance'
    max_distance: int = 6
    include_clausal_subjects: bool = False

    def process_node(self, node):
        if node.udeprel == 'nsubj' or (self.include_clausal_subjects and node.udeprel == 'csubj'):
            # locate predicate
            pred = node.parent

            # if the predicate is analytic, select the (non-conditional) auxiliary or the copula
            if finite_verbs := [
                nd for nd in pred.children if nd.udeprel == 'cop' or (nd.udeprel == 'aux' and nd.feats['Mood'] != 'Cnd')
            ]:
                pred = finite_verbs[0]

            # locate subject
            subj = node
            if node.udeprel == 'csubj':
                clause = util.get_clause(node, without_subordinates=True, without_punctuation=True, node_is_root=True)
                if node.ord < pred.ord:
                    subj = clause[-1]
                else:
                    subj = clause[0]

            if (max_dst := abs(subj.ord - pred.ord)) > self.max_distance:
                self.annotate_node('predicate_grammar', pred)
                self.annotate_node('subject', subj)

                self.annotate_measurement('max_distance', max_dst, pred, subj)
                self.annotate_parameter('max_distance', self.max_distance, pred, subj)
                self.annotate_parameter('include_clausal_subjects', self.include_clausal_subjects, pred, subj)

                self.advance_application_id()


class RulePredObjDistance(Rule):
    """Capture objects (both direct and indirect) that are too distant \
        from their parents.

    Inspiration: Šamánková & Kubíková (2022, pp. 53-54).

    Attributes:
        max_distance (int): how far apart the object and the parent can be \
            to not be considered an issue (object and its parent \
            right next to each other would have distance of 1).
    """

    rule_id: Literal['RulePredObjDistance'] = 'RulePredObjDistance'
    max_distance: int = 6

    def process_node(self, node):
        if node.deprel in ('obj', 'iobj'):
            parent = node.parent

            if (max_dst := abs(parent.ord - node.ord)) > self.max_distance:
                self.annotate_node('object', node)
                self.annotate_node('parent', parent)

                self.annotate_measurement('max_distance', max_dst, node, parent)
                self.annotate_parameter('max_distance', self.max_distance, node, parent)

                self.advance_application_id()


class RuleInfVerbDistance(Rule):
    """Capture infinitives that are too far from a verbal word they complement.

    Attributes:
        max_distance (int): how far apart the infinitive and the parent can be \
            to not be considered an issue (infinitive and its parent \
            right next to each other would have distance of 1).
    """

    rule_id: Literal['RuleInfVerbDistance'] = 'RuleInfVerbDistance'
    max_distance: int = 5

    def process_node(self, node):
        if (
            'VerbForm' in node.feats
            and (infinitive := node).feats['VerbForm'] == 'Inf'
            and 'VerbForm' in (verb := infinitive.parent).feats
        ):

            if (max_dst := abs(verb.ord - infinitive.ord)) > self.max_distance:
                self.annotate_node('infinitive', infinitive)
                self.annotate_node('verb', verb)

                self.annotate_measurement('max_distance', max_dst, infinitive, verb)
                self.annotate_parameter('max_distance', self.max_distance, infinitive, verb)

                self.advance_application_id()


class RuleMultiPartVerbs(Rule):
    """Capture multi-word verbal forms the parts of which (auxiliaries and clitics) \
        are too far apart from the root (content) token.

    Inspired by: Šamánková & Kubíková (2022, pp. 53-54).

    Attributes:
        max_distance (int): how far apart the auxiliary/clitic can be from the root \
            to not be considered an issue (auxiliary/clitic and the root \
            right next to each other would have distance of 1).
    """

    rule_id: Literal['RuleMultiPartVerbs'] = 'RuleMultiPartVerbs'
    max_distance: int = 5

    def process_node(self, node):
        # if node is an auxiliary and hasn't been marked as such yet
        if util.is_aux(node) and not {
            k: v for k, v in node.misc.items() if k.split(':')[0] == self.rule_id and v == 'aux'
        }:
            parent = node.parent

            # find remaining auxiliaries
            auxiliaries = {node}
            for child in parent.children:
                if util.is_aux(child) and not child in auxiliaries:
                    auxiliaries.add(child)

            # find if the verb is too spread out
            too_far_apart = False
            max_dst = 0
            for aux in auxiliaries:
                dst = abs(parent.ord - aux.ord)
                max_dst = max(max_dst, dst)
                too_far_apart |= dst > self.max_distance

            if too_far_apart:
                self.annotate_node('head', parent)
                self.annotate_node('aux', *auxiliaries)

                self.annotate_measurement('max_distance', max_dst, parent, *auxiliaries)
                self.annotate_parameter('max_distance', self.max_distance, parent, *auxiliaries)

                self.advance_application_id()


class RuleLongSentences(Rule):
    """Capture sentences that are too long.

    Inspiration: Šamánková & Kubíková (2022, p. 51), Šváb (2023, pp. 17–18).

    Attributes:
        max_length (int): how long the sentence can be to not be considered an issue.
        without_punctuation (bool): exclude punctuation from the count.
    """

    rule_id: Literal['RuleLongSentences'] = 'RuleLongSentences'
    max_length: int = 50
    without_punctuation: bool = False

    def process_node(self, node):
        if node.udeprel == 'root':
            descendants = util.get_clause(node, without_punctuation=self.without_punctuation, node_is_root=True)

            if not descendants:
                return

            # len(descendants) always >= 1 when add_self == True
            beginning, end = descendants[0], descendants[-1]

            if (max_length := end.ord - beginning.ord) >= self.max_length:
                self.annotate_node('long_sentence', *descendants)

                self.annotate_measurement('max_length', max_length, *descendants)
                self.annotate_parameter('max_length', self.max_length, *descendants)
                self.annotate_parameter('without_punctuation', self.without_punctuation, *descendants)

                self.advance_application_id()


class RulePredAtClauseBeginning(Rule):
    """Capture predicates (their finite tokens for multi-token predicates) \
        that are too far from the beginning of their clause.

    Inspiration: Šamánková & Kubíková (2022, pp. 53-54).

    Attributes:
        max_order (int): how far the predicate can be to not be considered an issue \
            (predicate right at the beginning of the clause would have order of 1).
    """

    rule_id: Literal['RulePredAtClauseBeginning'] = 'RulePredAtClauseBeginning'
    max_order: int = 5

    def process_node(self, node):
        # finite verbs or l-participles
        if util.is_finite_verb(node):
            pred_root = node.parent if util.is_aux(node) else node

            clause = util.get_clause(pred_root, without_subordinates=True, without_punctuation=True, node_is_root=True)

            clause_beginning = clause[0]

            # tokens forming the predicate, i.e. predicate root and potentially auxiliaries
            predicate_tokens = [pred_root] + [child for child in pred_root.children if util.is_aux(child)]
            # sort by order in the sentence
            predicate_tokens.sort(key=lambda a: a.ord)
            first_predicate_token = predicate_tokens[0]

            # add 1 to make the parameter 1-indexed instead of being 0-indexed
            if (max_ord := first_predicate_token.ord - clause_beginning.ord + 1) > self.max_order:
                self.annotate_node('clause_beginning', clause_beginning)
                self.annotate_node('predicate_beginning', first_predicate_token)

                self.annotate_measurement('max_order', max_ord, clause_beginning, first_predicate_token)
                self.annotate_parameter('max_order', self.max_order, clause_beginning, first_predicate_token)

                self.advance_application_id()


class RuleVerbalNouns(Rule):
    """Capture verbal nouns.

    Inspiration: Šamánková & Kubíková (2022, pp. 38-39), Šváb (2023, p. 30).
    """

    rule_id: Literal['RuleVerbalNouns'] = 'RuleVerbalNouns'

    def process_node(self, node):
        if 'VerbForm' in node.feats and node.feats['VerbForm'] == 'Vnoun':
            self.annotate_node('verbal_noun', node)
            self.advance_application_id()


class RuleTooFewVerbs(Rule):
    """Capture sentences containing too few verbs.

    Inspiration: Šamánková & Kubíková (2022, p. 37).

    Attributes:
        min_verb_frac (float): the lowest (# of verbs / # of words) fraction value \
            for the sentence to not be considered an issue.
        finite_only (bool): count only finite verbs.
    """

    rule_id: Literal['RuleTooFewVerbs'] = 'RuleTooFewVerbs'
    min_verb_frac: float = 0.06
    finite_only: bool = False

    def is_verb(self, node):
        return util.is_finite_verb(node) if self.finite_only else node.upos in ('VERB', 'AUX')

    def process_node(self, node):
        if node.udeprel == 'root':
            sentence = util.get_clause(node, without_punctuation=True, node_is_root=True)

            if not sentence:
                return

            # count each lexeme only once
            verbs = [
                nd
                for nd in sentence
                if self.is_verb(nd)
                and not (
                    util.is_aux(nd, grammatical_only=True)
                    and (
                        self.is_verb(nd.parent)
                        or [
                            preceding_nd
                            for preceding_nd in nd.parent.descendants(preceding_only=True)
                            if preceding_nd != nd and util.is_aux(preceding_nd, grammatical_only=True)
                        ]
                    )
                )
            ]

            if (min_frac := len(verbs) / len(sentence)) < self.min_verb_frac:
                self.annotate_node('verb', *verbs)

                self.annotate_measurement('min_verb_frac', min_frac, *verbs)
                self.annotate_parameter('min_verb_frac', self.min_verb_frac, *verbs)
                self.annotate_parameter('finite_only', self.finite_only, *verbs)

                self.advance_application_id()


class RuleTooManyNegations(Rule):
    """Capture sentences with too many negations.

    Inspiration: Šamánková & Kubíková (2022, pp. 40-41), Šváb (2023, p. 33).

    Attributes:
        max_negation_frac (float): the highest (# of negations / # of words with polarity) \
            fraction value for the sentence to not be considered an issue.
        max_allowable_negations (int): the highest # of negations in the sentence for the rule \
            to remain inhibited. This is to allow for double negation in Czech.
    """

    rule_id: Literal['RuleTooManyNegations'] = 'RuleTooManyNegations'
    max_negation_frac: float = 0.1
    max_allowable_negations: int = 3

    def process_node(self, node):
        if node.udeprel == 'root':
            clause = util.get_clause(node, without_punctuation=True, node_is_root=True)

            positives = [nd for nd in clause if self._is_positive(nd)]
            negatives = [nd for nd in clause if self._is_negative(nd)]

            no_pos, no_neg = len(positives), len(negatives)

            if (
                no_neg > self.max_allowable_negations
                and (max_neg_frac := no_neg / (no_pos + no_neg)) > self.max_negation_frac
            ):
                self.annotate_node('negative', *negatives)

                self.annotate_measurement('max_negation_frac', max_neg_frac, *negatives)
                self.annotate_measurement('max_allowable_negations', no_neg, *negatives)
                self.annotate_parameter('max_negation_frac', self.max_negation_frac, *negatives)
                self.annotate_parameter('max_allowable_negations', self.max_allowable_negations, *negatives)

                self.advance_application_id()

    @staticmethod
    def _is_positive(node) -> bool:
        # the aim is to capture (positives and) pronouns denoting an entity (not asking for it or relating it)
        return ('Polarity' in node.feats and node.feats['Polarity'] == 'Pos') or (
            'PronType' in node.feats and node.feats['PronType'] in ('Prs', 'Dem', 'Tot', 'Ind')
        )

    @staticmethod
    def _is_negative(node) -> bool:
        return ('Polarity' in node.feats and node.feats['Polarity'] == 'Neg') or (
            'PronType' in node.feats and node.feats['PronType'] == 'Neg'
        )


class RuleWeakMeaningWords(Rule):
    """Capture semantically weak words.

    Inspiration: Šamánková & Kubíková (2022, pp. 37-38 and p. 39), Sgall & Panevová (2014, p. 86), Šváb (2023, p. 32).
    """

    rule_id: Literal['RuleWeakMeaningWords'] = 'RuleWeakMeaningWords'
    _weak_meaning_words: list[str] = [
        'dopadat',
        'zaměřit',
        'poukázat',
        'poukazovat',
        'ovlivnit',
        'ovlivňovat',
        'provádět',
        'provést',
        'postup',
        'obdobně',
        'velmi',
        'uskutečnit',
        'uskutečňovat',
    ]

    def process_node(self, node):
        if node.lemma in self._weak_meaning_words:
            self.annotate_node('weak_meaning_word', node)
            self.advance_application_id()


class RuleAbstractNouns(Rule):
    """Capture semantically weak abstract nouns.

    Inspiration: Šamánková & Kubíková (2022, p. 41).
    """

    rule_id: Literal['RuleAbstractNouns'] = 'RuleAbstractNouns'
    _abstract_nouns: list[str] = [
        'základ',
        'situace',
        'úvaha',
        'charakter',
        'stupeň',
        'aspekt',
        'okolnosti',
        'událost',
        'snaha',
        'podmínky',
        'činnost',
    ]

    def process_node(self, node):
        if node.lemma in self._abstract_nouns:
            self.annotate_node('abstract_noun', node)
            self.advance_application_id()


class RuleRelativisticExpressions(Rule):
    """Capture relativistic expressions.

    Inspiration: Šamánková & Kubíková (2022, p. 42).
    """

    rule_id: Literal['RuleRelativisticExpressions'] = 'RuleRelativisticExpressions'

    # lemmas; when space-separated, nodes next-to-each-other with corresponding lemmas are looked for
    _expressions: list[list[str]] = [
        expr.split(' ') for expr in ['poněkud', 'jevit', 'patrně', 'do jistý míra', 'snad', 'jaksi']
    ]

    def process_node(self, node):
        for expr in self._expressions:
            # node matches first lemma in the expression
            if node.lemma.lower() == expr[0]:
                nd_iterator, i = node, 0
                nodes = [nd_iterator]

                # see if next nodes match next lemmas in the expression
                while (nd_iterator := nd_iterator.next_node) and (i := i + 1) < len(expr):
                    if nd_iterator.lemma.lower() != expr[i]:
                        break
                    nodes += [nd_iterator]
                # success listener
                else:
                    for matching_node in nodes:
                        self.annotate_node('relativistic_expression', matching_node)
                        self.advance_application_id()


class RuleConfirmationExpressions(Rule):
    """Capture confirmation expressions. They often violate the maxim of quantity \
        in needlesly confirming what the author is already expected to be 100% sure about.

    Inspiration: Šamánková & Kubíková (2022, pp. 42-43).
    """

    rule_id: Literal['RuleConfirmationExpressions'] = 'RuleConfirmationExpressions'
    _expressions: list[str] = ['jednoznačně', 'jasně', 'nepochybně', 'naprosto', 'rozhodně']

    def process_node(self, node):
        if node.lemma in self._expressions:
            self.annotate_node('confirmation_expression', node)


class RuleRedundantExpressions(Rule):
    """Capture expressions that aren't needed to convey the message.

    Inspiration: Šamánková & Kubíková (2022, pp. 42-43).
    """

    rule_id: Literal['RuleRedundantExpressions'] = 'RuleRedundantExpressions'

    def process_node(self, node):
        match node.lemma:
            # je nutné zdůraznit
            case 'nutný':
                if (aux := [c for c in node.children if c.lemma == 'být']) and (
                    inf := [c for c in node.children if c.lemma == 'zdůraznit']
                ):
                    self.annotate_node('redundant_expression', node, aux[0], inf[0])
                    self.advance_application_id()

            # z uvedeného je zřejmé
            case 'zřejmý':
                if (aux := [c for c in node.children if c.lemma == 'být']) and (
                    adj := [
                        c for c in node.children if c.lemma == 'uvedený' and [a for a in c.children if a.lemma == 'z']
                    ]
                ):
                    # little dirty, I'd love to know if it's possible to retreive the adposition from the condition
                    # without it possible being overwritten if there are multiple cs that match c.lemma == 'uvedený'
                    adp = [a for a in adj[0].children if a.lemma == 'z']

                    self.annotate_node('redundant_expression', node, aux[0], adj[0], adp[0])
                    self.advance_application_id()

            # vyvstala otázka
            case 'vyvstat':
                if noun := [c for c in node.children if c.lemma == 'otázka']:
                    self.annotate_node('redundant_expression', node, noun[0])
                    self.advance_application_id()

            # nabízí se otázka
            case 'nabízet':
                if (expl := [c for c in node.children if c.deprel == 'expl:pass']) and (
                    noun := [c for c in node.children if c.lemma == 'otázka']
                ):
                    self.annotate_node('redundant_expression', node, expl[0], noun[0])
                    self.advance_application_id()

            # v neposlední řadě
            case 'řada':
                if (adj := [c for c in node.children if c.lemma == 'neposlední']) and (
                    adp := [c for c in node.children if c.lemma == 'v']
                ):
                    self.annotate_node('redundant_expression', node, adj[0], adp[0])
                    self.advance_application_id()

            # v kontextu věci
            case 'kontext':
                if (noun := [c for c in node.children if c.lemma == 'věc']) and (
                    adp := [c for c in node.children if c.lemma == 'v']
                ):
                    self.annotate_node('redundant_expression', node, noun[0], adp[0])
                    self.advance_application_id()

            # v rámci posuzování
            case 'posuzování':
                if adp := [
                    c for c in node.children if c.lemma == 'v' and [n for n in c.children if n.lemma == 'rámec']
                ]:
                    # little dirty, I'd love to know if it's possible to retreive the noun from the condition
                    # without it possible being overwritten if there are multiple cs that match c.lemma == 'v'
                    noun = [n for n in adp[0].children if n.lemma == 'rámec']

                    self.annotate_node('redundant_expression', node, adp[0], noun[0])
                    self.advance_application_id()


class RuleTooLongExpressions(Rule):
    """Capture expressions that could be shortened.

    Inspiration: Šamánková & Kubíková (2022, p. 44), Šváb (2023, p. 118)
    """

    rule_id: Literal['RuleTooLongExpressions'] = 'RuleTooLongExpressions'

    def process_node(self, node):
        match node.lemma:
            # v důsledku toho
            case 'důsledek':
                if (adp := node.parent).lemma == 'v' and adp.parent and (pron := adp.parent).upos in ('PRON', 'DET'):
                    self.annotate_node('v_důsledku_toho', node, adp, pron)
                    self.advance_application_id()

            # v případě, že
            case 'že':
                if (
                    node.parent.parent
                    and (noun := node.parent.parent).lemma == 'případ'
                    and (adp := [c for c in noun.children if c.lemma == 'v'])
                ):
                    self.annotate_node('v_případě_že', node, noun, *adp)
                    self.advance_application_id()
            # týkající se
            case 'týkající':
                if expl := [c for c in node.children if c.deprel == 'expl:pv']:
                    self.annotate_node('týkající_se', node, *expl)
                    self.advance_application_id()

            # za účelem
            case 'účel':
                if (adp := node.parent).lemma == 'za':
                    self.annotate_node('za_účelem', node, adp)
                    self.advance_application_id()

            # jste oprávněn
            case 'oprávněný':
                if aux := [c for c in node.children if c.upos == 'AUX']:
                    self.annotate_node('jste_oprávněn', node, *aux)
                    self.advance_application_id()

            # uděluje/vyjadřuje souhlas
            case 'souhlas':
                if (verb := node.parent).lemma in ('udělovat', 'vyjadřovat') and node.udeprel == 'obj':
                    self.annotate_node('uděluje_vyjadřuje_souhlas', node, verb)
                    self.advance_application_id()

            # dát do nájmu
            case 'nájem':
                if (
                    node.feats['Case'] == 'Gen'
                    and (adp := [c for c in node.children if c.lemma == 'do'])
                    and (verb := node.parent).lemma == 'dát'
                ):
                    self.annotate_node('dát_do_nájmu', node, verb, *adp)
                    self.advance_application_id()

            # prostřednictvím kterého
            case 'prostřednictví':
                if node.upos == 'ADP' and (det := node.parent).upos == 'DET':
                    self.annotate_node('prostřednictvím_kterého', node, det)
                    self.advance_application_id()

            # jsou uvedeny v příloze
            case 'uvedený':
                if (aux := [c for c in node.children if c.upos == 'AUX']) and (
                    nouns := [
                        c for c in node.children if c.upos == 'NOUN' and c.feats['Case'] == 'Loc' and c.deprel == 'obl'
                    ]
                ):
                    for noun in nouns:
                        if adp := [c for c in noun.children if c.lemma == 'v']:
                            self.annotate_node('jsou_uvedeny_v_příloze', node, *aux, noun, *adp)
                            self.advance_application_id()

            # za podmínek uvedených ve smlouvě
            case 'podmínka':
                if (
                    node.feats['Case'] == 'Gen'
                    and (adp_za := [c for c in node.children if c.lemma == 'za'])
                    and (amods := [c for c in node.children if c.lemma == 'uvedený'])
                ):
                    for amod in amods:
                        if nouns := [
                            c
                            for c in amod.children
                            if c.upos == 'NOUN' and c.feats['Case'] == 'Loc' and c.deprel == 'obl'
                        ]:
                            for noun in nouns:
                                if adp_v := [c for c in noun.children if c.lemma == 'v']:
                                    self.annotate_node(
                                        'za_podmínek_uvedených_ve_smlouvě', node, *adp_za, amod, noun, *adp_v
                                    )
                                    self.advance_application_id()

            # v rámci
            case 'rámec':
                if node.deprel == 'fixed' and (adp := node.parent).lemma == 'v':
                    self.annotate_node('v_rámci', node, adp)
                    self.advance_application_id()

            # mluvený projev
            case 'mluvený':
                if (noun := node.parent).lemma == 'projev':
                    self.annotate_node('mluvený_projev', node, noun)
                    self.advance_application_id()

            # ze strany banky
            case 'strana':
                if node.deprel == 'fixed' and (adp := node.parent).lemma == 'z' and (head := adp.parent):
                    self.annotate_node('ze_strany_banky', node, adp, head)
                    self.advance_application_id()

            # předmětný závazek
            case 'předmětný':
                if node.deprel == 'amod' and (noun := node.parent).upos == 'NOUN':
                    self.annotate_node('předmětný_závazek', node, noun)
                    self.advance_application_id()


class RuleAnaphoricReferences(Rule):
    """Capture vague anaphoric references.

    Inspiration: Šamánková & Kubíková (2022, p. 42).
    """

    rule_id: Literal['RuleAnaphoricReferences'] = 'RuleAnaphoricReferences'

    def process_node(self, node):
        match node.lemma:
            # co se týče výše uvedeného
            # ze shora uvedeného důvodu
            # z právě uvedeného je zřejmé
            case 'uvedený':
                if adv := [c for c in node.children if c.lemma in ('vysoko', 'shora', 'právě')]:
                    self.annotate_node('anaphoric_reference', node, *adv)
                    self.advance_application_id()

            # s ohledem na tuto skutečnost
            case 'skutečnost':
                if (det := [c for c in node.children if c.udeprel == 'det' and c.feats['PronType'] == 'Dem']) and (
                    adp := [c for c in node.children if c.udeprel == 'case']
                ):
                    self.annotate_node(
                        'anaphoric_reference', node, *det, *adp, *[desc for a in adp for desc in a.descendants()]
                    )
                    self.advance_application_id()

            # z logiky věci vyplývá
            case 'logika':
                if (noun := [c for c in node.children if c.lemma == 'věc']) and (
                    adp := [c for c in node.children if c.lemma == 'z']
                ):
                    self.annotate_node(
                        'anaphoric_reference', node, *noun, *adp, *[desc for a in adp for desc in a.descendants()]
                    )
                    self.advance_application_id()


class RuleAmbiguousRegards(Rule):
    """Capture regard constructions (e.g. [trajector] is greater than [landmark]) \
        that are ambiguous as to which word fills the [trajector] slot.

    Inspiration: Sgall & Panevová (2014, pp. 77-78), Šamánková & Kubíková (2022, p. 41).
    """

    rule_id: Literal['RuleAmbiguousRegards'] = 'RuleAmbiguousRegards'

    def process_node(self, node):
        if (
            (sconj := node).lemma == 'než'
            and not util.is_clause_root(landmark := node.parent)
            and not [c for c in landmark.children if c.udeprel == 'case']
            and (comparative := landmark.parent)
            and 'Degree' in comparative.feats
            and comparative.feats['Degree'] == 'Cmp'
            and comparative.parent
        ):
            # trajector should be a noun
            # if comparative.upos == 'ADJ', its parent should be a noun
            # otherwise it may be that comparative.parent is verbal; we try to find its object
            trajector = (
                comparative.parent
                if comparative.upos == 'ADJ'
                else ([c for c in comparative.parent.children if c.udeprel == 'obj'] + [None])[0]
            )

            if trajector and trajector.udeprel == 'obj':
                self.annotate_node('sconj', sconj)
                self.annotate_node('landmark', landmark)
                self.annotate_node('comparative', comparative)
                self.annotate_node('trajector', trajector)

                self.advance_application_id()


class RuleLiteraryStyle(Rule):
    """Capture expressions associated with literary style.

    Inspiration: Sgall & Panevová (2014, pp. 42, 66–69, 79–82).
    """

    rule_id: Literal['RuleLiteraryStyle'] = 'RuleLiteraryStyle'

    def process_node(self, node: Node):
        # vinni jsou
        if (
            node.lemma == 'vinný'
            and 'Variant' in node.feats
            and node.feats['Variant'] == 'Short'
            and (auxiliaries := [c for c in node.children if c.upos == 'AUX'])
        ):
            self.annotate_node('být_vinnen', node, *auxiliaries)
            self.advance_application_id()

        # na vině jsou
        elif (
            node.form.lower() == 'vině'
            and (adps := [c for c in node.children if c.lemma == 'na'])
            and (parent := node.parent)
            and parent.lemma == 'být'
        ):
            self.annotate_node('být_na_vině', node, *adps, parent)
            self.advance_application_id()

        # genetive objects
        elif (
            node.deprel in ('obj', 'iobj', 'obl:arg')
            and 'Case' in node.feats
            and node.feats['Case'] == 'Gen'
            and (parent := node.parent)
            and parent.lemma
            in (
                'užít',
                'uživší',
                'užívat',
                'užívající',
                'využít',
                'využivší',
                'využívat',
                'využívající',
                'přát',
                'přející',
                'žádat',
                'žádající',
            )
            # filter out prepositional genitives
            # and genitives depending on a two-form-declination word
            and not [c for c in node.children if c.deprel == 'case' or 'NumType' in c.feats]
            # deverbative parents only
            and 'VerbForm' in parent.feats
        ):
            self.annotate_node('genitive_object', node)
            self.annotate_node('gen_obj_head', parent)
            self.advance_application_id()

        # short adjective forms
        elif (
            node.upos == 'ADJ'
            and 'Variant' in node.feats
            and node.feats['Variant'] == 'Short'
            and 'VerbForm' not in node.feats  # rule out passive participles
            and node.lemma not in ('rád', 'bosý')
        ):
            self.annotate_node('short_adjective_variant', node)
            self.advance_application_id()

        # pronoun "jej"
        elif (
            node.form.lower() == 'jej'
            and node.upos == 'PRON'
            and (node.feats['Case'] == 'Gen' or 'Neut' in node.feats['Gender'].split(','))
        ):
            self.annotate_node('jej_pronoun_form', node)
            self.advance_application_id()

        elif node.lemma in ('jenž', 'jehož'):
            self.annotate_node('jenž', node)
            self.advance_application_id()

        # some subordinate conjunctions
        elif node.lemma in ('jestliže', 'pakliže', 'li', 'poněvadž', 'jelikož') and node.upos == 'SCONJ':
            self.annotate_node('subordinate_conjunction', node)
            self.advance_application_id()


class RuleDoubleComparison(Rule):
    """Capture constructions with a comparison auxiliary modifying a head with a non-positive degree of comparison.

    Inspiration: Sgall & Panevová (2014, p. 67).
    """

    rule_id: Literal['RuleDoubleComparison'] = 'RuleDoubleComparison'

    def process_node(self, node: Node):
        if (
            node.lemma in ('více', 'méně', 'míň')
            and 'Degree' in node.feats
            and node.feats['Degree'] != 'Pos'
            and (parent := node.parent)
            and node.udeprel == 'advmod'
            and 'Degree' in parent.feats
            and parent.feats['Degree'] == node.feats['Degree']
        ):
            self.annotate_node('head', parent)
            self.annotate_node('modifier', node)
            self.advance_application_id()


class RuleTooManyNominalConstructions(Rule):
    """Capture clauses with too many nominal constructions.

    Inspiration: Sgall & Panevová (2014, p. 41).

    Attributes:
        max_noun_frac (float): the highest (# of nouns / # of words) \
            fraction value for the clause to not be considered an issue.
        max_allowable_nouns (int): the highest # of nouns in the clause for the rule \
            to remain inhibited.
    """

    # TODO: consider reworking the rule similarly to RuleCaseRepetition. It would help with aligning more with Šváb.

    rule_id: Literal['RuleTooManyNominalConstructions'] = 'RuleTooManyNominalConstructions'
    max_noun_frac: float = 0.5
    max_allowable_nouns: int = 3

    def process_node(self, node: Node):
        if util.is_clause_root(node):
            clause = util.get_clause(node, without_subordinates=True, without_punctuation=True, node_is_root=True)

            nouns = [n for n in clause if n.upos == 'NOUN' and (n.ord == 1 or not util.is_named_entity(n))]

            if (l := len(nouns)) > self.max_allowable_nouns and float(l) / len(clause) > self.max_noun_frac:
                self.annotate_node('noun', *nouns)
                self.advance_application_id()


class RuleReflexivePassWithAnimSubj(Rule):
    """Capture reflexive passives used with animate subjects.

    Inspiration: Sgall & Panevová (2014, pp. 71-72).
    """

    rule_id: Literal['RuleReflexivePassWithAnimSubj'] = 'RuleReflexivePassWithAnimSubj'

    def process_node(self, node: Node):
        if (
            node.deprel == 'expl:pass'
            and (verb := node.parent)
            and (subj := [s for s in verb.children if s.udeprel == 'nsubj'])
            and 'Animacy' in subj[0].feats
            and subj[0].feats['Animacy'] == 'Anim'
        ):
            self.annotate_node('refl_pass', node, verb)
            self.annotate_node('subj', subj[0])
            self.advance_application_id()


class RuleWrongValencyCase(Rule):
    """Capture wrong case usage with certain valency dependencies.

    Inspiration: Sgall & Panevová (2014, p. 85).
    """

    rule_id: Literal['RuleWrongValencyCase'] = 'RuleWrongValencyCase'

    def process_node(self, node: Node):
        # pokoušeli se zabránit takové důsledky
        if node.lemma in ('zabránit', 'zabraňovat') and (
            accs := [a for a in node.children if a.udeprel == 'obj' and 'Case' in a.feats and a.feats['Case'] == 'Acc']
        ):
            for acc in accs:
                if not bool([c for c in acc.children if c.udeprel == 'case']):
                    self.annotate_node('verb', node)
                    self.annotate_node('accusative', acc)
                    self.advance_application_id()

        # pokoušeli se zamezit takovým důsledkům
        elif node.lemma in ('zamezit', 'zamezovat') and (
            dats := [d for d in node.children if d.udeprel == 'obl' and 'Case' in d.feats and d.feats['Case'] == 'Dat']
        ):
            for dat in dats:
                if not bool([c for c in dat.children if c.udeprel == 'case']):
                    self.annotate_node('verb', node)
                    self.annotate_node('dative', dat)
                    self.advance_application_id()

        # nemusíte zodpovědět na tyto otázky
        elif node.lemma in ('zodpovědět', 'zodpovídat') and (
            accs := [a for a in node.children if a.udeprel == 'obl' and 'Case' in a.feats and a.feats['Case'] == 'Acc']
        ):
            for acc in accs:
                if (cases := [c for c in acc.children if c.udeprel == 'case']) and cases[0].lemma == 'na':
                    self.annotate_node('verb', node)
                    self.annotate_node('accusative', acc)
                    self.annotate_node('preposition', cases[0])
                    self.advance_application_id()

        # nemusíte odpovědět tyto otázky
        elif node.lemma in ('odpovědět', 'odpovídat') and (
            accs := [a for a in node.children if a.udeprel == 'obj' and 'Case' in a.feats and a.feats['Case'] == 'Acc']
        ):
            for acc in accs:
                cases = [c for c in acc.children if c.udeprel == 'case']

                if not bool(cases):
                    self.annotate_node('verb', node)
                    self.annotate_node('accusative', acc)
                    self.advance_application_id()

                elif cases[0].lemma != 'na':
                    self.annotate_node('verb', node)
                    self.annotate_node('accusative', acc)
                    self.annotate_node('preposition', cases[0])
                    self.advance_application_id()

        # hovořit/mluvit něco
        elif node.lemma in ('hovořit', 'mluvit') and (
            accs := [a for a in node.children if a.udeprel == 'obj' and 'Case' in a.feats and a.feats['Case'] == 'Acc']
        ):
            for acc in accs:
                if not bool([c for c in acc.children if c.udeprel == 'case']):
                    self.annotate_node('verb', node)
                    self.annotate_node('accusative', acc)
                    self.advance_application_id()

        # mimo + !ACC
        elif (
            node.lemma == 'mimo'
            and node.udeprel == 'case'
            and 'Case' in (noun := node.parent).feats
            and noun.feats['Case'] != 'Acc'
        ):
            self.annotate_node('preposition', node)
            self.annotate_node('not_accusative', noun)
            self.advance_application_id()

        # kromě + !GEN
        # not sure if UDPipe is able to parse kromě with any other case than GEN
        elif (
            node.lemma == 'kromě'
            and node.udeprel == 'case'
            and 'Case' in (noun := node.parent).feats
            and noun.feats['Case'] != 'Gen'
        ):
            self.annotate_node('preposition', node)
            self.annotate_node('not_genitive', noun)
            self.advance_application_id()


class RuleWrongVerbonominalCase(Rule):
    """Capture wrong case usage in verbonominal predicates.

    Inspiration: Sgall & Panevová (2014, p. 42).
    """

    rule_id: Literal['RuleWrongVerbonominalCase'] = 'RuleWrongVerbonominalCase'

    def process_node(self, node: Node):
        if (
            node.lemma in ('pravda', 'škoda')
            and (cop := [c for c in node.children if c.deprel == 'cop'])
            and node.feats['Case'] == 'Ins'
        ):
            self.annotate_node('copula', *cop)
            self.annotate_node('instrumental', node)
            self.advance_application_id()


class RuleIncompleteConjunction(Rule):
    """Capture incomplete multi-token conjunctions.

    Inspiration: Sgall & Panevová (2014, p. 85).
    """

    rule_id: Literal['RuleIncompleteConjunction'] = 'RuleIncompleteConjunction'

    def process_node(self, node: Node):
        if node.lemma == 'jednak':
            conjunctions = [c for c in node.root.descendants() if c != node and c.lemma == 'jednak']

            if len(conjunctions) == 0:
                self.annotate_node('conj_part', node)
                self.advance_application_id()


class RuleFunctionWordRepetition(Rule):
    """Capture repeating function words.

    Inspiration: Sgall & Panevová (2014, p. 88).
    """

    rule_id: Literal['RuleFunctionWordRepetition'] = 'RuleFunctionWordRepetition'

    def process_node(self, node: Node):
        if node.upos in ('ADP', 'SCONJ', 'CCONJ') and (
            following_node := [n for n in node.root.descendants() if n.ord == node.ord + 1 and n.lemma == node.lemma]
        ):
            self.annotate_node('repetition', node, *following_node)
            self.advance_application_id()


class RuleCaseRepetition(Rule):
    """Capture spans of texts with high density of nouns (and adjectives) in the same case. Punctuation, \
    adpositions, and conjunctions are excluded from the count.

    Inspiration: Sgall & Panevová (2014, pp. 88-90).

    Attributes:
        include_adjetives (bool): include adjectives to the count.
        max_repetition_count (int): max number of one case occurences to not be considered an issue.
        max_repetition_frac (int): max (# of one case occurences / length of the span) to not be considered an issue.
    """

    rule_id: Literal['RuleCaseRepetition'] = 'RuleCaseRepetition'
    include_adjectives: bool = True
    max_repetition_count: int = 4
    max_repetition_frac: float = 0.7

    _tracked_pos: list[str] = None

    def __init__(self, **data):
        super().__init__(**data)

        self._tracked_pos = ('NOUN', 'ADJ') if self.include_adjectives else ('NOUN')

    def process_node(self, node: Node):
        if node.upos in self._tracked_pos and 'Case' in node.feats:
            descendants = node.root.descendants()
            following_nodes = [node] + [
                d for d in descendants if d.ord > node.ord and d.upos not in ('PUNCT', 'ADP', 'CCONJ', 'SCONJ')
            ]

            while len(following_nodes) >= self.max_repetition_count:
                ne_reg = util.NEregister(node)

                same_case_nodes = [
                    n
                    for n in following_nodes
                    if n.upos in self._tracked_pos
                    and n.feats['Case'] == node.feats['Case']
                    and not ne_reg.is_registered_ne(n)
                ]

                if len(same_case_nodes) <= self.max_repetition_count:
                    break

                # if the rule has already been applied to all nodes in same_case_nodes, there's no point in continuing
                notes_already_visited = [n for n in same_case_nodes if self.__class__.id() in util.rules_applied(n)]
                if len(notes_already_visited) == len(same_case_nodes):
                    break

                if len(same_case_nodes) / len(following_nodes) > self.max_repetition_frac:
                    self.annotate_node('case_repetition', *same_case_nodes)
                    self.advance_application_id()
                    break

                following_nodes.pop()


class RulePossessiveGenitive(Rule):
    """Capture unnecessary or badly placed possessive genitives.

    Inspiration: Sgall & Panevová (2014, p. 91).
    """

    rule_id: Literal['RulePossessiveGenitive'] = 'RulePossessiveGenitive'

    def process_node(self, node: Node):
        if (
            util.is_named_entity(node)
            and node.udeprel == 'nmod'
            and node.feats['Case'] == 'Gen'
            and len(node.children) == 0
        ):
            dnet_lexemes = derinet_lexicon.get_lexemes(node.lemma)
            if len(dnet_lexemes) > 0:
                dnet_lexeme = dnet_lexemes[0]
                possesives = [c for c in dnet_lexeme.children if 'Poss' in c.feats and c.feats['Poss'] == 'Yes']

                if possesives:
                    self.annotate_node('possesive_adj_exists', node)
                    self.advance_application_id()
                # TODO: what about gender ambiguity?
                elif node.parent.ord < node.ord and node.feats['Gender'] != 'Fem':
                    self.annotate_node('right_of_parent', node)
                    self.advance_application_id()


class RuleBlockWrapper(Block):
    def __init__(self, rule: Rule):
        Block.__init__(self)
        self.rule = rule

    def process_node(self, node: Node):
        return self.rule.process_node(node)

    def after_process_document(self, document: Document):
        return self.rule.after_process_document(document)


class RuleAPIWrapper(BaseModel):
    rule: Union[*Rule.get_final_children()] = Field(..., discriminator='rule_id')  # type: ignore
