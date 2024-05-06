from __future__ import annotations
import util

from udapi.core.block import Block
from udapi.core.node import Node
from udapi.core.root import Root
from udapi.core.document import Document
from typing import Literal, Any, Union

from utils import StringBuildable

from pydantic import BaseModel, Field

import os


class Rule(StringBuildable):
    detect_only: bool = True
    process_id: str = Field(default_factory=lambda: os.urandom(4).hex(), hidden=True)
    modified_roots: set[Any] = Field(default=set(), hidden=True)  # FIXME: This should not be Any, but rather Root

    def model_post_init(self, __context: Any) -> None:
        self.process_id = Rule.get_application_id()

    @staticmethod
    def get_application_id():
        return os.urandom(4).hex()

    @classmethod
    def id(cls):
        return cls.__name__

    def annotate_node(self, node: Node, annotation: str):
        node.misc[f"{self.__class__.id()}:{self.process_id}"] = f"{annotation}"

    def after_process_document(self, document):
        for root in self.modified_roots:
            root.text = root.compute_text()

    def advance_application_id(self):
        self.process_id = self.get_application_id()

    def process_node(self, node: Node):
        raise NotImplementedError('A rule is expected to have a \'process_node\' method.')


class RuleDoubleAdpos(Rule):
    rule_id: Literal['RuleDoubleAdpos'] = 'RuleDoubleAdpos'
    min_distance: int = 3

    def process_node(self, node: Node):
        if node.upos != "CCONJ":
            return  # nothing we can do for this node, bail

        cconj = node

        # find an adposition present in the coordination
        for parent_adpos in [nd for nd in cconj.parent.siblings if nd.udeprel == "case" and nd.upos == "ADP"]:
            coord_el1, coord_el2 = parent_adpos.parent, cconj.parent

            # check that the two coordination elements have the same case
            if coord_el2.feats["Case"] != coord_el1.feats["Case"]:
                continue

            # check that the two coordination elements aren't too close to eachother
            if coord_el2.ord - coord_el1.ord <= self.min_distance:
                continue

            # check that the second coordination element doesn't already have an adposition
            if not [nd for nd in cconj.siblings if nd.lemma == parent_adpos.lemma] and not [
                nd for nd in cconj.siblings if nd.upos == "ADP"
            ]:
                if not self.detect_only:
                    correction = util.clone_node(
                        parent_adpos,
                        coord_el2,
                        filter_misc_keys=r"^(?!Rule).*",
                        include_subtree=True,
                    )

                    correction.form = parent_adpos.form.lower()
                    correction.shift_after_node(cconj)

                    for node_to_annotate in correction.descendants(add_self=True):
                        self.annotate_node(node_to_annotate, 'add')

                self.annotate_node(cconj, 'cconj')
                self.annotate_node(parent_adpos, 'orig_adpos')
                self.annotate_node(coord_el1, 'coord_el1')
                self.annotate_node(coord_el2, 'coord_el2')

                self.advance_application_id()

                if not self.detect_only:
                    self.modified_roots.add(cconj.root)


class RulePassive(Rule):
    rule_id: Literal['RulePassive'] = 'RulePassive'

    def process_node(self, node):
        if node.deprel == 'aux:pass':
            parent = node.parent

            self.annotate_node(node, 'aux')
            self.annotate_node(parent, 'participle')

            self.advance_application_id()


class RulePredSubjDistance(Rule):
    rule_id: Literal['RulePredSubjDistance'] = 'RulePredSubjDistance'
    max_distance: int = 6

    def process_node(self, node):
        # locate subject
        if node.udeprel in ('nsubj', 'csubj'):

            # locate predicate
            pred = node.parent

            # if the predicate is analytic, select the (non-conditional) auxiliary or the copula
            if finite_verbs := [
                nd for nd in pred.children if nd.udeprel == 'cop' or (nd.udeprel == 'aux' and nd.feats['Mood'] != 'Cnd')
            ]:
                pred = finite_verbs[0]

            if abs(node.ord - pred.ord) > self.max_distance:
                self.annotate_node(pred, 'predicate_grammar')
                self.annotate_node(node, 'subject')

                self.advance_application_id()


class RulePredObjDistance(Rule):
    rule_id: Literal['RulePredObjDistance'] = 'RulePredObjDistance'
    max_distance: int = 6

    def process_node(self, node):
        if node.deprel in ('obj', 'iobj'):
            parent = node.parent

            if abs(parent.ord - node.ord) > self.max_distance:
                self.annotate_node(node, 'object')
                self.annotate_node(parent, 'parent')

                self.advance_application_id()


class RuleHeadXcompDistance(Rule):
    rule_id: Literal['RuleHeadXcompDistance'] = 'RuleHeadXcompDistance'
    max_distance: int = 5

    def process_node(self, node):
        if node.deprel == 'xcomp':
            parent = node.parent

            if abs(parent.ord - node.ord) > self.max_distance:
                self.annotate_node(node, 'complement')
                self.annotate_node(parent, 'verb')

                self.advance_application_id()


class RuleMultiPartVerbs(Rule):
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
            for aux in auxiliaries:
                too_far_apart |= abs(parent.ord - aux.ord) > self.max_distance

            if too_far_apart:
                self.annotate_node(parent, 'head')
                for aux in auxiliaries:
                    self.annotate_node(aux, 'aux')

                self.advance_application_id()


class RuleLongSentences(Rule):
    rule_id: Literal['RuleLongSentences'] = 'RuleLongSentences'
    max_length: int = 50

    def process_node(self, node):
        if node.udeprel == 'root':
            descendants = util.get_clause(node, node_is_root=True)

            # len(descendants) always >= 1 when add_self == True
            beginning, end = descendants[0], descendants[-1]

            if end.ord - beginning.ord >= self.max_length:
                self.annotate_node(beginning, 'beginning')
                self.annotate_node(end, 'end')

                self.advance_application_id()


class RulePredAtClauseBeginning(Rule):
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

            if first_predicate_token.ord - clause_beginning.ord > self.max_order:
                self.annotate_node(clause_beginning, 'clause_beginning')
                self.annotate_node(first_predicate_token, 'predicate_beginning')

                self.advance_application_id()


class RuleVerbalNouns(Rule):
    rule_id: Literal['RuleVerbalNouns'] = 'RuleVerbalNouns'

    def process_node(self, node):
        if 'VerbForm' in node.feats and node.feats['VerbForm'] == 'Vnoun':
            self.annotate_node(node, 'verbal_noun')
            self.advance_application_id()


class RuleTooFewVerbs(Rule):
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

            if len(verbs) / len(sentence) < self.min_verb_frac:
                for verb in verbs:
                    self.annotate_node(verb, 'verb')

                self.advance_application_id()


class RuleTooManyNegations(Rule):
    rule_id: Literal['RuleTooManyNegations'] = 'RuleTooManyNegations'
    max_negation_frac: float = 0.1

    def process_node(self, node):
        if node.udeprel == 'root':
            clause = util.get_clause(node, without_punctuation=True, node_is_root=True)

            positives = [nd for nd in clause if 'Polarity' in nd.feats and nd.feats['Polarity'] == 'Pos']
            negatives = [nd for nd in clause if 'Polarity' in nd.feats and nd.feats['Polarity'] == 'Neg']

            no_pos, no_neg = len(positives), len(negatives)

            if no_neg > 2 and no_neg / (no_pos + no_neg) > self.max_negation_frac:
                for nd in negatives:
                    self.annotate_node(nd, 'negative')

                self.advance_application_id()


class RuleWeakMeaningWords(Rule):
    rule_id: Literal['RuleWeakMeaningWords'] = 'RuleWeakMeaningWords'
    _weak_meaning_words: list[str] = ['dopadat', 'zaměřit', 'poukázat', 'ovlivnit', 'postup', 'obdobně', 'velmi']

    def process_node(self, node):
        if node.lemma in self._weak_meaning_words:
            self.annotate_node(node, 'weak_meaning_word')
            self.advance_application_id()


class RuleAbstractNouns(Rule):
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
            self.annotate_node(node, 'abstract_noun')
            self.advance_application_id()


class RuleRelativisticExpression(Rule):
    rule_id: Literal['RuleRelativisticExpression'] = 'RuleRelativisticExpression'

    # lemmas; when space-separated, nodes next-to-eachother with corresponding lemmas are looked for
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
                        self.annotate_node(matching_node, 'relativistic_expression')
                        self.advance_application_id()


class RuleConfirmationExpression(Rule):
    rule_id: Literal['RuleConfirmationExpression'] = 'RuleConfirmationExpression'
    _expressions: list[str] = ['jednoznačně', 'jasně', 'nepochybně', 'naprosto', 'rozhodně']

    def process_node(self, node):
        if node.lemma in self._expressions:
            self.annotate_node(node, 'confirmation_expression')


class RuleRedundantExpression(Rule):
    rule_id: Literal['RuleRedundantExpression'] = 'RuleRedundantExpression'

    def _annotate(self, *nodes: Node):
        for nd in nodes:
            self.annotate_node(nd, 'redundant_expression')

    def process_node(self, node):
        match node.lemma:
            # je nutné zdůraznit
            case 'nutný':
                if (aux := [c for c in node.children if c.lemma == 'být']) and (
                    inf := [c for c in node.children if c.lemma == 'zdůraznit']
                ):
                    self._annotate(node, aux[0], inf[0])
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

                    self._annotate(node, aux[0], adj[0], adp[0])
                    self.advance_application_id()

            # vyvstala otázka
            case 'vyvstat':
                if noun := [c for c in node.children if c.lemma == 'otázka']:
                    self._annotate(node, noun[0])
                    self.advance_application_id()

            # nabízí se otázka
            case 'nabízet':
                if (expl := [c for c in node.children if c.deprel == 'expl:pass']) and (
                    noun := [c for c in node.children if c.lemma == 'otázka']
                ):
                    self._annotate(node, expl[0], noun[0])
                    self.advance_application_id()

            # v neposlední řadě
            case 'řada':
                if (adj := [c for c in node.children if c.lemma == 'neposlední']) and (
                    adp := [c for c in node.children if c.lemma == 'v']
                ):
                    self._annotate(node, adj[0], adp[0])
                    self.advance_application_id()

            # v kontextu věci
            case 'kontext':
                if (noun := [c for c in node.children if c.lemma == 'věc']) and (
                    adp := [c for c in node.children if c.lemma == 'v']
                ):
                    self._annotate(node, noun[0], adp[0])
                    self.advance_application_id()

            # v rámci posuzování
            case 'posuzování':
                if adp := [
                    c for c in node.children if c.lemma == 'v' and [n for n in c.children if n.lemma == 'rámec']
                ]:
                    # little dirty, I'd love to know if it's possible to retreive the noun from the condition
                    # without it possible being overwritten if there are multiple cs that match c.lemma == 'v'
                    noun = [n for n in adp[0].children if n.lemma == 'rámec']

                    self._annotate(node, adp[0], noun[0])
                    self.advance_application_id()


class RuleTooLongExpression(Rule):
    rule_id: Literal['RuleTooLongExpression'] = 'RuleTooLongExpression'

    def _annotate(self, *nodes: Node):
        for nd in nodes:
            self.annotate_node(nd, 'too_long_expression')

    def process_node(self, node):
        match node.lemma:
            # v důsledku toho
            case 'důsledek':
                if (adp := node.parent).lemma == 'v' and adp.parent and (pron := adp.parent).upos in ('PRON', 'DET'):
                    self._annotate(node, adp, pron)
                    self.advance_application_id()

            # v případě, že
            case 'že':
                if (
                    node.parent.parent
                    and (noun := node.parent.parent).lemma == 'případ'
                    and (adp := [c for c in noun.children if c.lemma == 'v'])
                ):
                    self._annotate(node, noun, adp[0])
                    self.advance_application_id()
            # týkající se
            case 'týkající':
                if expl := [c for c in node.children if c.deprel == 'expl:pv']:
                    self._annotate(node, expl[0])
                    self.advance_application_id()

            # za účelem
            case 'účel':
                if (adp := node.parent).lemma == 'za':
                    self._annotate(node, adp)
                    self.advance_application_id()


class RuleAnaphoricReference(Rule):
    rule_id: Literal['RuleAnaphoricReference'] = 'RuleAnaphoricReference'

    def _annotate(self, *nodes: Node):
        for node in nodes:
            self.annotate_node(node, 'anaphoric_reference')

    def process_node(self, node):
        match node.lemma:
            # co se týče výše uvedeného
            # ze shora uvedeného důvodu
            # z právě uvedeného je zřejmé
            case 'uvedený':
                if adv := [c for c in node.children if c.lemma in ('vysoko', 'shora', 'právě')]:
                    self._annotate(node, *adv)
                    self.advance_application_id()

            # s ohledem na tuto skutečnost
            case 'skutečnost':
                if (det := [c for c in node.children if c.udeprel == 'det' and c.feats['PronType'] == 'Dem']) and (
                    adp := [c for c in node.children if c.udeprel == 'case']
                ):
                    self._annotate(node, *det, *adp, *[desc for a in adp for desc in a.descendants()])
                    self.advance_application_id()

            # z logiky věci vyplývá
            case 'logika':
                if (noun := [c for c in node.children if c.lemma == 'věc']) and (
                    adp := [c for c in node.children if c.lemma == 'z']
                ):
                    self._annotate(node, *noun, *adp, *[desc for a in adp for desc in a.descendants()])
                    self.advance_application_id()


class RuleAmbiguousRegard(Rule):
    rule_id: Literal['RuleAmbiguousRegard'] = 'RuleAmbiguousRegard'

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
            # otherwise it's likely that comparative.upos == 'VERB'; we try to find its object
            trajector = (
                comparative.parent
                if comparative.upos == 'ADJ'
                else ([c for c in comparative.parent.children if c.udeprel == 'obj'] + [None])[0]
            )

            if trajector.udeprel == 'obj':
                self.annotate_node(sconj, 'sconj')
                self.annotate_node(landmark, 'landmark')
                self.annotate_node(comparative, 'comparative')
                self.annotate_node(trajector, 'trajector')

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
