'''Utilities for node retrieval from the structure'''

from typing import Iterable

from udapi.core.bundle import Bundle
from udapi.core.node import Node

import document_applicables.rules.util.structure_info as utilsi
import document_applicables.rules.util.grammar_semantics as utilgs


def get_clause_root(node: Node) -> Node:
    clause_root = node
    while not utilsi.is_clause_root(clause_root):
        if clause_root.parent is None:
            # print('Warning: failed to identify clause root')
            return clause_root

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

            if utilsi.is_clause_root(nd):
                to_remove += nd.descendants(add_self=True)

        clause = [nd for nd in clause if not nd in to_remove]

    if without_punctuation:
        clause = [nd for nd in clause if nd.upos != 'PUNCT']

    return clause


def get_coord_element_phrase(node: Node) -> list[Node]:
    res = node.descendants
    to_remove = []

    if len(res) > 0 and res[0].upos == 'PUNCT':
        res.pop(0)

    for d in res:
        if d.deprel == 'conj':
            to_remove += d.descendants(add_self=True)

    return [d for d in res if d not in to_remove] + [node]


def get_surrounding_bundles(node: Node, no_prev: int, no_next: int, exclude_self: bool = False) -> list[Bundle]:
    bundles = node.root.document.bundles
    current_bundle_idx = bundles.index(node.root.bundle)

    first_idx = max(current_bundle_idx - no_prev, 0)
    last_idx = min(current_bundle_idx + no_next, len(bundles) - 1)

    res = bundles[first_idx : last_idx + 1]
    if exclude_self:
        res.remove(node.root.bundle)

    return res


def serialize_bundles(*bundle: Bundle) -> list[Node]:
    return [n for b in bundle for n in b.nodes]


def get_surrounding_bundles_serialize(
    node: Node, no_prev: int, no_next: int, exclude_self: bool = False, no_punct_sym: bool = False
) -> list[Node]:
    res = serialize_bundles(*get_surrounding_bundles(node, no_prev, no_next, exclude_self))
    return remove_punct_sym(res) if no_punct_sym else res


def remove_punct_sym(nodes: list[Node], keep: Iterable[Node] = []) -> list[Node]:
    return [n for n in nodes if not utilgs.is_punct_sym(n) or n in keep]


def get_phrase_heads(nodes: list[Node], keep: Iterable[Node] = []) -> list[Node]:
    """Retrieve only such nodes that would be considered phrase heads.
    So far, this simply removes adjectival modifiers and adpositions from the list
    and counts only tokens passing the `remove_punct_sym` filter."""
    return [
        n
        for n in remove_punct_sym(nodes, keep=keep)
        if not (
            n.deprel in ('amod', 'det', 'case', 'fixed', 'mark', 'cc') and n.feats['Case'] == n.parent.feats['Case']
        )
        or n in keep
    ]
