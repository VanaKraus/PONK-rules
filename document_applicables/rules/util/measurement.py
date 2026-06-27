'''Utilities intended for measuring'''

from udapi.core.node import Node


def distance_from_list(nodes: list[Node], nodeA: Node, nodeB: Node) -> int:
    indexA = nodes.index(nodeA)
    indexB = nodes.index(nodeB)

    return abs(indexB - indexA)
