from udapi.core.node import Node
from udapi.core.dualdict import DualDict

import re


def clone_node(node: Node, parent: Node, filter_misc_keys: str = None, **override) -> Node:
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

    return res
