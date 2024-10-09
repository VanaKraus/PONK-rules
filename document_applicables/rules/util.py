from dataclasses import dataclass

from udapi.core.node import Node
from udapi.core.dualdict import DualDict

import re


def clone_node(
    node: Node, parent: Node, filter_misc_keys: str = None, include_subtree: bool = False, **override
) -> Node:
    res = parent.create_child(
        form=node.form,
        lemma=node.lemma,
        upos=node.upos,
        xpos=node.xpos,
        feats=node.feats,
        deprel=node.deprel,
        misc=node.misc,
    )

    if filter_misc_keys:
        res.misc = DualDict({k: v for k, v in node.misc.items() if re.search(filter_misc_keys, k)})

    for arg, val in override.items():
        setattr(res, arg, val)

    if include_subtree:
        for child in node.children:
            new_child = clone_node(child, res, filter_misc_keys, include_subtree, **override)
            if child.ord < node.ord:
                new_child.shift_before_node(res)
            else:
                new_child.shift_after_node(res)

    return res


def is_aux(node: Node, grammatical_only: bool = False) -> bool:
    if grammatical_only:
        return node.udeprel in ('aux', 'cop') or node.deprel == 'expl:pass'
    else:
        return node.udeprel in ('aux', 'expl', 'cop')


def is_finite_verb(node: Node) -> bool:
    return ('VerbForm' in node.feats and node.feats['VerbForm'] == 'Fin') or node.xpos[0:2] == 'Vp'


def is_clause_root(node: Node) -> bool:
    return is_finite_verb(node) or bool([nd for nd in node.children if is_aux(nd, grammatical_only=True)])


def get_clause_root(node: Node) -> Node:
    clause_root = node
    while not is_clause_root(clause_root):
        clause_root = clause_root.parent
    return clause_root


def get_clause(
    node: Node,
    without_subordinates: bool = False,
    without_punctuation: bool = False,
    node_is_root: bool = False,
) -> list[Node]:
    clause_root = node if node_is_root else get_clause_root(node)
    clause = clause_root.descendants(add_self=True)

    if without_subordinates:
        to_remove = []
        for nd in clause:
            if nd == clause_root:
                continue

            if is_clause_root(nd):
                to_remove += nd.descendants(add_self=True)

        clause = [nd for nd in clause if not nd in to_remove]

    if without_punctuation:
        clause = [nd for nd in clause if nd.upos != 'PUNCT']

    return clause

@dataclass(frozen=True, slots=True)
class Color:
   red: int
   green: int
   blue: int

   def __post_init__(self):
       for color in self.red, self.green, self.blue:
           if color > 255 or color < 0:
               raise ValueError("Color must be between 0 and 255")

class NotANounException(Exception):
    pass


class ClauseBeginningException(Exception):
    pass


def is_proper_noun(node: Node, clause_not_capitalized: bool = False, look_at_parents: bool = False) -> bool:
    return node.upos == 'PROPN'

    # if node.upos != 'NOUN':
    #     raise NotANounException(f'{node} is not a noun')
    # if not clause_not_capitalized and node.ord <= 1:
    #     raise ClauseBeginningException(f'{node} at the beginning of a clause')

    # result = node.form == node.form.capitalize()

    # if look_at_parents:
    #     try:
    #         result |= is_proper_noun(node.parent)
    #     except (NotANounException, ClauseBeginningException):
    #         pass

    # return result
