from __future__ import annotations
import document_applicables.rules.util

from udapi.core.block import Block
from udapi.core.node import Node
from udapi.core.document import Document
from typing import Literal, Any, Union

from document_applicables import Documentable

from pydantic import BaseModel, Field

import os

RULE_ANNOTATION_PREFIX = 'PonkApp1'


class Rule(Documentable):
    detect_only: bool = True
    process_id: str = Field(default_factory=lambda: os.urandom(4).hex(), hidden=True)
    modified_roots: set[Any] = Field(default=set(), hidden=True)  # FIXME: This should not be Any, but rather Root
    application_count: int = Field(default=0, hidden=True)

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
        value = annotation

        for nd in node:
            nd.misc[key] = value

    def annotate_measurement(self, m_name: str, m_value, *node):
        self.annotate_node(str(m_value), *node, flag=f"measur:{m_name}")

    def annotate_parameter(self, p_name: str, p_value, *node):
        self.annotate_node(str(p_value), *node, flag=f"param:{p_name}")

    def after_process_document(self, document):
        for root in self.modified_roots:
            root.text = root.compute_text()

    def advance_application_id(self):
        self.process_id = self.get_application_id()
        self.application_count += 1

    def reset_application_count(self):
        self.application_count = 0

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
    max_allowable_distance: int = 3

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

                self.annotate_node('orig_adpos', parent_adpos)
                self.annotate_node('coord_el1', coord_el1)
                self.annotate_node('coord_el2', coord_el2)

                if cconj:
                    self.annotate_node('cconj', cconj)
                    self.annotate_measurement('max_allowable_distance', dst, cconj)
                    self.annotate_parameter('max_allowable_distance', self.max_allowable_distance, cconj)

                self.annotate_measurement('max_allowable_distance', dst, parent_adpos, coord_el1, coord_el2)
                self.annotate_parameter(
                    'max_allowable_distance', self.max_allowable_distance, parent_adpos, coord_el1, coord_el2
                )

                self.advance_application_id()

                if not self.detect_only:
                    self.modified_roots.add(cconj.root)


class RulePassive(Rule):
    """Capture be-passives.

    Inspiration: Šamánková & Kubíková (2022, pp. 39-40).
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

    Inspiration: Šamánková & Kubíková (2022, pp. 53-54).

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

    Inspiration: Šamánková & Kubíková (2022, p. 51).

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
                self.annotate_node('beginning', beginning)
                self.annotate_node('end', end)

                self.annotate_measurement('max_length', max_length, beginning, end)
                self.annotate_parameter('max_length', self.max_length, beginning, end)
                self.annotate_parameter('without_punctuation', self.without_punctuation, beginning, end)

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

            # if first_predicate_token has already been annotated by this rule
            if l := [k for k, _ in first_predicate_token.misc.items() if k.split(':')[0] == self.rule_id]:
                return

            # add 1 to make the parameter 1-indexed instead of being 0-indexed
            if (max_ord := first_predicate_token.ord - clause_beginning.ord + 1) > self.max_order:
                self.annotate_node('clause_beginning', clause_beginning)
                self.annotate_node('predicate_beginning', first_predicate_token)

                self.annotate_measurement('max_order', max_ord, clause_beginning, first_predicate_token)
                self.annotate_parameter('max_order', self.max_order, clause_beginning, first_predicate_token)

                self.advance_application_id()


class RuleVerbalNouns(Rule):
    """Capture verbal nouns.

    Inspiration: Šamánková & Kubíková (2022, pp. 38-39).
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
    min_verb_frac: float = 0.05
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

    Inspiration: Šamánková & Kubíková (2022, pp. 40-41).

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

            positives = [nd for nd in clause if 'Polarity' in nd.feats and nd.feats['Polarity'] == 'Pos']
            negatives = [nd for nd in clause if 'Polarity' in nd.feats and nd.feats['Polarity'] == 'Neg']

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


class RuleWeakMeaningWords(Rule):
    """Capture semantically weak words.

    Inspiration: Šamánková & Kubíková (2022, pp. 37-38 and p. 39).
    """

    rule_id: Literal['RuleWeakMeaningWords'] = 'RuleWeakMeaningWords'
    _weak_meaning_words: list[str] = ['dopadat', 'zaměřit', 'poukázat', 'ovlivnit', 'postup', 'obdobně', 'velmi']

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

    Inspiration: Šamánková & Kubíková (2022, p. 44).
    """

    rule_id: Literal['RuleTooLongExpressions'] = 'RuleTooLongExpressions'

    def process_node(self, node):
        match node.lemma:
            # v důsledku toho
            case 'důsledek':
                if (adp := node.parent).lemma == 'v' and adp.parent and (pron := adp.parent).upos in ('PRON', 'DET'):
                    self.annotate_node('too_long_expression', node, adp, pron)
                    self.advance_application_id()

            # v případě, že
            case 'že':
                if (
                    node.parent.parent
                    and (noun := node.parent.parent).lemma == 'případ'
                    and (adp := [c for c in noun.children if c.lemma == 'v'])
                ):
                    self.annotate_node('too_long_expression', node, noun, adp[0])
                    self.advance_application_id()
            # týkající se
            case 'týkající':
                if expl := [c for c in node.children if c.deprel == 'expl:pv']:
                    self.annotate_node('too_long_expression', node, expl[0])
                    self.advance_application_id()

            # za účelem
            case 'účel':
                if (adp := node.parent).lemma == 'za':
                    self.annotate_node('too_long_expression', node, adp)
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
