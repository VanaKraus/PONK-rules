from __future__ import annotations
import util

from udapi.core.block import Block
from udapi.core.node import Node
from udapi.core.root import Root
from typing import Set

from utils import StringBuildable

import os


# TODO: unify rule intervention marks
# TODO: generalize rule blocks (e.g. using an abstract-ish class). it could contain process_id generation, text recomputation etc.


class Rule(Block, StringBuildable):
    def __init__(self, detect_only=True, **kwargs):
        Block.__init__(self, **kwargs)
        self.detect_only = detect_only
        self.process_id = Rule.get_application_id()
        self.modified_roots: Set[Root] = set()

    @staticmethod
    def get_application_id():
        return os.urandom(4).hex()

    def annotate_node(self, node: Node, annotation: str):
        node.misc[f"{self.__class__.id()}:{self.process_id}"] = f"{annotation}"

    def after_process_document(self, document):
        for root in self.modified_roots:
            root.text = root.compute_text()


class double_adpos_rule(Rule):
    @StringBuildable.parse_string_args(detect_only=bool)
    def __init__(self, detect_only=True):
        Rule.__init__(self, detect_only)

    @classmethod
    def id(cls):
        return "rule_double_adpos"

    def process_node(self, node: Node):
        # TODO: multi-word adpositions
        # TODO: sometimes the structure isn't actually ambiguous and doesn't need to be ammended
        # TODO: sometimes the rule catches adpositions that shouldn't be repeated in the coordination


        if node.upos != "CCONJ":
            return None #nothing we can do for this node, bail

        cconj = node

        # find an adposition present in the coordination
        for parent_adpos in [
            nd
            for nd in cconj.parent.siblings
            if nd.udeprel == "case" and nd.upos == "ADP"
        ]:
            # check that the two coordination elements have the same case
            if cconj.parent.feats["Case"] != parent_adpos.parent.feats["Case"]:
                continue

            # check that the second coordination element doesn't already have an adposition
            if not [
                nd for nd in cconj.siblings if nd.lemma == parent_adpos.lemma
            ] and not [nd for nd in cconj.siblings if nd.upos == "ADP"]:
                if not self.detect_only:
                    correction = util.clone_node(
                        parent_adpos,
                        cconj.parent,
                        filter_misc_keys=r"^(?!Rule).*",
                        form=parent_adpos.form.lower(),
                    )
                    correction.shift_after_node(cconj)
                    self.annotate_node(correction, 'add')

                self.annotate_node(cconj, 'cconj')
                self.annotate_node(parent_adpos, 'orig_adpos')
                self.annotate_node(parent_adpos.parent, 'coord_el1')
                self.annotate_node(cconj.parent, 'coord_el2')

                if not self.detect_only:
                    self.modified_roots.add(cconj.root)
