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
    process_id: str = ''
    modified_roots: set[Any] = set()  # FIXME: This should not be Any, but rather Root

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


class rule_double_adpos(Rule):
    rule_id: Literal['rule_double_adpos'] = 'rule_double_adpos'

    # detect_only: bool = True

    def process_node(self, node: Node):
        # TODO: multi-word adpositions
        # TODO: sometimes the structure isn't actually ambiguous and doesn't need to be ammended
        # TODO: sometimes the rule catches adpositions that shouldn't be repeated in the coordination

        if node.upos != "CCONJ":
            return None  # nothing we can do for this node, bail

        cconj = node

        # find an adposition present in the coordination
        for parent_adpos in [
            nd for nd in cconj.parent.siblings if nd.udeprel == "case" and nd.upos == "ADP"
        ]:
            # check that the two coordination elements have the same case
            if cconj.parent.feats["Case"] != parent_adpos.parent.feats["Case"]:
                continue

            # check that the second coordination element doesn't already have an adposition
            if not [nd for nd in cconj.siblings if nd.lemma == parent_adpos.lemma] and not [
                nd for nd in cconj.siblings if nd.upos == "ADP"
            ]:
                if not self.detect_only:
                    correction = util.clone_node(
                        parent_adpos,
                        cconj.parent,
                        filter_misc_keys=r"^(?!rule_).*",
                        form=parent_adpos.form.lower(),
                    )
                    correction.shift_after_node(cconj)
                    self.annotate_node(correction, 'add')

                self.annotate_node(cconj, 'cconj')
                self.annotate_node(parent_adpos, 'orig_adpos')
                self.annotate_node(parent_adpos.parent, 'coord_el1')
                self.annotate_node(cconj.parent, 'coord_el2')

                self.advance_application_id()

                if not self.detect_only:
                    self.modified_roots.add(cconj.root)


class rule_passive(Rule):
    rule_id: Literal['rule_passive'] = 'rule_passive'

    def process_node(self, node):
        if node.deprel == 'aux:pass':
            parent = node.parent

            self.annotate_node(node, 'aux')
            self.annotate_node(parent, 'participle')

            self.advance_application_id()


class rule_pred_subj_distance(Rule):
    rule_id: Literal['rule_pred_subj_distance'] = 'rule_pred_subj_distance'
    max_distance: int = 6

    def process_node(self, node):
        # locate subject
        if node.udeprel in ('nsubj', 'csubj'):

            # locate predicate
            pred = node.parent

            # if the predicate is analytic, select the (non-conditional) auxiliary or the copula
            if finite_verbs := [
                nd
                for nd in pred.children
                if nd.udeprel == 'cop' or (nd.udeprel == 'aux' and nd.feats['Mood'] != 'Cnd')
            ]:
                pred = finite_verbs[0]

            if abs(node.ord - pred.ord) > self.max_distance:
                self.annotate_node(pred, 'predicate_grammar')
                self.annotate_node(node, 'subject')

                self.advance_application_id()


class rule_pred_obj_distance(Rule):
    rule_id: Literal['rule_pred_obj_distance'] = 'rule_pred_obj_distance'
    max_distance: int = 6

    def process_node(self, node):
        if node.deprel in ('obj', 'iobj'):
            parent = node.parent

            if abs(parent.ord - node.ord) > self.max_distance:
                self.annotate_node(node, 'object')
                self.annotate_node(parent, 'parent')

                self.advance_application_id()


class rule_head_xcomp_distance(Rule):
    rule_id: Literal['rule_head_xcomp_distance'] = 'rule_head_xcomp_distance'
    max_distance: int = 5

    def process_node(self, node):
        if node.deprel == 'xcomp':
            parent = node.parent

            if abs(parent.ord - node.ord) > self.max_distance:
                self.annotate_node(node, 'complement')
                self.annotate_node(parent, 'verb')

                self.advance_application_id()


class rule_multi_part_verbs(Rule):
    rule_id: Literal['rule_multi_part_verbs'] = 'rule_multi_part_verbs'
    max_distance: int = 5

    def process_node(self, node):
        # if node is an auxiliary and hasn't been marked as such yet
        if util.is_aux(node) and not {
            k: v
            for k, v in node.misc.items()
            if k.split(':')[0] == self.__class__.__name__ and v == 'aux'
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


class rule_long_sentences(Rule):
    rule_id: Literal['rule_long_sentences'] = 'rule_long_sentences'
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


class rule_pred_at_clause_beginning(Rule):
    rule_id: Literal['rule_pred_at_clause_beginning'] = 'rule_pred_at_clause_beginning'
    max_order: int = 5

    def process_node(self, node):
        # finite verbs or l-participles
        if util.is_finite_verb(node):
            pred_root = node.parent if util.is_aux(node) else node

            clause = util.get_clause(
                pred_root, without_subordinates=True, without_punctuation=True, node_is_root=True
            )

            clause_beginning = clause[0]

            # tokens forming the predicate, i.e. predicate root and potentially auxiliaries
            predicate_tokens = [pred_root] + [
                child for child in pred_root.children if util.is_aux(child)
            ]
            # sort by order in the sentence
            predicate_tokens.sort(key=lambda a: a.ord)
            first_predicate_token = predicate_tokens[0]

            # if first_predicate_token has already been annotated by this rule
            if l := [
                k
                for k, _ in first_predicate_token.misc.items()
                if k.split(':')[0] == self.__class__.__name__
            ]:
                return

            if first_predicate_token.ord - clause_beginning.ord > self.max_order:
                self.annotate_node(clause_beginning, 'clause_beginning')
                self.annotate_node(first_predicate_token, 'predicate_beginning')

                self.advance_application_id()


class rule_verbal_nouns(Rule):
    rule_id: Literal['rule_verbal_nouns'] = 'rule_verbal_nouns'

    def process_node(self, node):
        if 'VerbForm' in node.feats and node.feats['VerbForm'] == 'Vnoun':
            self.annotate_node(node, 'verbal_noun')
            self.advance_application_id()


class rule_too_few_verbs(Rule):
    rule_id: Literal['rule_too_few_verbs'] = 'rule_too_few_verbs'
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
                            if preceding_nd != nd
                            and util.is_aux(preceding_nd, grammatical_only=True)
                        ]
                    )
                )
            ]

            if len(verbs) / len(sentence) < self.min_verb_frac:
                for verb in verbs:
                    self.annotate_node(verb, 'verb')

                self.advance_application_id()


class rule_too_many_negations(Rule):
    rule_id: Literal['rule_too_many_negations'] = 'rule_too_many_negations'
    max_negation_frac: float = 0.1

    def process_node(self, node):
        if node.udeprel == 'root':
            clause = util.get_clause(node, without_punctuation=True, node_is_root=True)

            positives = [
                nd for nd in clause if 'Polarity' in nd.feats and nd.feats['Polarity'] == 'Pos'
            ]
            negatives = [
                nd for nd in clause if 'Polarity' in nd.feats and nd.feats['Polarity'] == 'Neg'
            ]

            no_pos, no_neg = len(positives), len(negatives)

            if no_neg > 2 and no_neg / (no_pos + no_neg) > self.max_negation_frac:
                for nd in negatives:
                    self.annotate_node(nd, 'negative')

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
    rule: Union[*Rule.get_final_children()] = Field(..., discriminator='rule_id')
