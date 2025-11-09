'''Utilities for providing information on text structure'''

from udapi.core.node import Node
import document_applicables.rules.util.grammar_semantics as utilgs


def descendants_include(node: Node, lemmas: set) -> bool:
    return len(lemmas.intersection({n.lemma for n in node.descendants()})) > 0


def is_clause_root(node: Node) -> bool:
    return utilgs.is_finite_verb(node) or bool(
        [nd for nd in node.children if utilgs.is_aux(nd, grammatical_only=True) and utilgs.is_finite_verb(nd)]
    )
