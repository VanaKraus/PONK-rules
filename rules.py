from __future__ import annotations
import util

from udapi.core.block import Block
from udapi.core.node import Node
from udapi.core.root import Root
from typing import Set

from utils import StringBuildable

import os


class Rule(Block, StringBuildable):
    def __init__(self, detect_only=True, **kwargs):
        Block.__init__(self, **kwargs)
        self.detect_only = detect_only
        self.process_id = Rule.get_application_id()
        self.modified_roots: Set[Root] = set()

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


class rule_double_adpos(Rule):
    @StringBuildable.parse_string_args(detect_only=bool)
    def __init__(self, detect_only=True):
        Rule.__init__(self, detect_only)

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
    @StringBuildable.parse_string_args(detect_only=bool)
    def __init__(self, detect_only=True):
        Rule.__init__(self, detect_only)

    def process_node(self, node):
        if node.deprel == 'aux:pass':
            parent = node.parent

            self.annotate_node(node, 'aux')
            self.annotate_node(parent, 'participle')

            self.advance_application_id()


class rule_pred_subj_distance(Rule):
    @StringBuildable.parse_string_args(detect_only=bool, max_distance=int)
    def __init__(self, detect_only=True, max_distance=6):
        Rule.__init__(self, detect_only)
        self.max_distance = max_distance

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
    @StringBuildable.parse_string_args(detect_only=bool, max_distance=int)
    def __init__(self, detect_only=True, max_distance=5):
        Rule.__init__(self, detect_only)
        self.max_distance = max_distance

    def process_node(self, node):
        if node.deprel in ('obj', 'iobj'):
            parent = node.parent

            if abs(parent.ord - node.ord) > self.max_distance:
                self.annotate_node(node, 'object')
                self.annotate_node(parent, 'parent')

                self.advance_application_id()


class rule_head_xcomp_distance(Rule):
    @StringBuildable.parse_string_args(detect_only=bool, max_distance=int)
    def __init__(self, detect_only=True, max_distance=5):
        Rule.__init__(self, detect_only)
        self.max_distance = max_distance

    def process_node(self, node):
        if node.deprel == 'xcomp':
            parent = node.parent

            if abs(parent.ord - node.ord) > self.max_distance:
                self.annotate_node(node, 'complement')
                self.annotate_node(parent, 'verb')

                self.advance_application_id()


class rule_multi_part_verbs(Rule):
    @StringBuildable.parse_string_args(detect_only=bool, max_distance=int)
    def __init__(self, detect_only=True, max_distance=5):
        Rule.__init__(self, detect_only)
        self.max_distance = max_distance

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
    @StringBuildable.parse_string_args(detect_only=bool, max_length=int)
    def __init__(self, detect_only=True, max_length=50):
        Rule.__init__(self, detect_only)
        self.max_length = max_length

    def process_node(self, node):
        if node.udeprel == 'root':
            descendants = node.descendants(add_self=True)

            # len(descendants) always >= 1 when add_self == True
            beginning, end = descendants[0], descendants[-1]

            if end.ord - beginning.ord >= self.max_length:
                self.annotate_node(beginning, 'beginning')
                self.annotate_node(end, 'end')

                self.advance_application_id()


class rule_pred_at_clause_beginning(Rule):
    @StringBuildable.parse_string_args(detect_only=bool, max_order=int)
    def __init__(self, detect_only=True, max_order=5):
        Rule.__init__(self, detect_only)
        self.max_order = max_order

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
    @StringBuildable.parse_string_args(detect_only=bool)
    def __init__(self, detect_only=True):
        Rule.__init__(self, detect_only)

    def process_node(self, node):
        if 'VerbForm' in node.feats and node.feats['VerbForm'] == 'Vnoun':
            self.annotate_node(node, 'verbal_noun')
            self.advance_application_id()


class rule_too_few_verbs(Rule):
    @StringBuildable.parse_string_args(detect_only=bool, min_verb_frac=float)
    def __init__(self, detect_only=True, min_verb_frac=0.05):
        Rule.__init__(self, detect_only)
        self.min_verb_frac = min_verb_frac

    def process_node(self, node):
        if node.udeprel == 'root':
            sentence = util.get_clause(node, without_punctuation=True, node_is_root=True)

            if not sentence:
                return

            # count each lexeme only once
            finite_verbs = [
                nd
                for nd in sentence
                if util.is_finite_verb(nd)
                and not (
                    util.is_aux(nd, grammatical_only=True)
                    and (
                        util.is_finite_verb(nd.parent)
                        or [
                            preceding_nd
                            for preceding_nd in nd.parent.descendants(preceding_only=True)
                            if preceding_nd != nd
                            and util.is_aux(preceding_nd, grammatical_only=True)
                        ]
                    )
                )
            ]

            if len(finite_verbs) / len(sentence) < self.min_verb_frac:
                for verb in finite_verbs:
                    self.annotate_node(verb, 'verb')

                self.advance_application_id()


class rule_too_many_negations(Rule):
    @StringBuildable.parse_string_args(detect_only=bool, max_negation_frac=float)
    def __init__(self, detect_only=True, max_negation_frac=0.1):
        Rule.__init__(self, detect_only)
        self.max_negation_frac = max_negation_frac

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
