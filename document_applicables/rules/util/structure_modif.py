'''Utilities for text modification'''

import re

from udapi.core.node import Node
from udapi.core.dualdict import DualDict

from document_applicables import rules


def rules_applied(node: Node) -> set[str]:
    rule_annotations = [m.split(':') for m in node.misc if m.startswith(f'{rules.RULE_ANNOTATION_PREFIX}:')]
    return {annotation[1] for annotation in rule_annotations}


def get_rule_annotations(
    node: Node, rule_id: str, application_id: str | None = None, flag: str | None = None
) -> set[str]:
    """Returns a set of annotations made to a given node by a given rule.

    Args:
        node (Node):
        rule_id (str):
        application_id (str | None, optional): Application ID of the rule.
            If None is given, all applications are searched. Defaults to None.
        flag (str | None, optional): Flag to search.
            If None is given, only annotations without any flag are searched. Defaults to None.

    Returns:
        set (str): Set of the annotations given.
    """
    pattern = rules.RULE_ANNOTATION_PREFIX + r':[_A-Za-z]+:' + (application_id if application_id else r'[0-9a-f]{8}')
    if flag:
        pattern += f':{flag}'

    res = set()

    for k, v in node.misc.items():
        if re.match(pattern, k):
            res |= {v}

    return res


def get_removing_rules(node, descendants=False) -> set[str]:
    return {
        mtch[1]
        for nd in (node.descendants if descendants else [node])
        for m in nd.misc
        if (mtch := re.match(rules.RULE_ANNOTATION_PREFIX + r':([_A-Za-z]+:[0-9a-f]{8}):remove', m))
    }


def get_rebinding_rules(node, descendants=False) -> set[str]:
    return {
        mtch[1]
        for nd in (node.descendants if descendants else [node])
        for m in nd.misc
        if (mtch := re.match(rules.RULE_ANNOTATION_PREFIX + r':([_A-Za-z]+:[0-9a-f]{8}):rebind', m))
    }


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


def node_serializable(node: Node, **kwargs) -> dict[str, str]:
    return {
        'form': node.form,
        'lemma': node.lemma,
        'upos': node.upos,
        'xpos': node.xpos,
        'feats': str(node.feats),
        'parent': node.parent.ord if node.parent else None,
        'deprel': node.deprel,
        'deps': str(node.deps),
        'misc': str(node.misc),
        **kwargs,
    }
