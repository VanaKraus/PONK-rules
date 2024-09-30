import re

from udapi.core.node import Node
from udapi.core.dualdict import DualDict

# FIXME: cyclic import
from document_applicables import rules


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


class NEregister:
    '''Keeps track of named entities visited.'''

    _reg: set[str] = {}

    def __init__(self, *node):
        for nd in node:
            self.is_registered_ne(nd)

    def is_registered_ne(self, node) -> bool:
        """Checks if the node is a named entity and if it has already been visited. If the node is \
            a not-yet-visited NE, the NE code gets registered.

        Args:
            node

        Returns:
            bool: returns True if the node is an already-visited NE. Returns False if the node isn't a NE, \
                or if the NE hasn't been visited yet.
        """

        if not is_named_entity(node):
            return False

        result = False

        for code in node.misc['NE'].split('-'):
            if code in self._reg:
                result |= True
            else:
                if len(self._reg) == 0:
                    self._reg = {code}
                else:
                    self._reg |= {code}

        return result


def is_named_entity(node: Node) -> bool:
    return 'NE' in node.misc


def rules_applied(node: Node) -> set[str]:
    rule_annotations = [m.split(':') for m in node.misc if m.startswith(f'{rules.RULE_ANNOTATION_PREFIX}:')]
    return {annotation[1] for annotation in rule_annotations}
