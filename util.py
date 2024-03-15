from udapi.core.node import Node

import re
from collections.abc import Generator


def node_is(node: Node, *matches: tuple[str, str]) -> bool:
    for match in matches:
        if not re.search(match[1], getattr(node, match[0])):
            return False
    return True


def find_nodes(nodes: list[Node], *matches: tuple[str, str]) -> list[Node]:
    res = []
    for node in nodes:
        if node_is(node, *matches):
            res += [node]
    return res
