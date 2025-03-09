from dataclasses import dataclass
import re
from dataclasses import dataclass

from udapi.core.node import Node
from udapi.core.dualdict import DualDict
from ufal.morphodita import Morpho, TaggedLemmasForms

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
    # Is marked as finite or an l-participle (e.g. "dělal")
    return (node.feats['VerbForm'] == 'Fin') or node.xpos[0:2] == 'Vp'


def is_adposition(node: Node) -> bool:
    return node.deprel in ('case', 'fixed')


def is_clause_root(node: Node) -> bool:
    return is_finite_verb(node) or bool([nd for nd in node.children if is_aux(nd, grammatical_only=True)])


def descendants_include(node: Node, lemmas: set) -> bool:
    return len(lemmas.intersection({n.lemma for n in node.descendants()})) > 0


def get_clause_root(node: Node) -> Node:
    clause_root = node
    while not is_clause_root(clause_root):
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

            if is_clause_root(nd):
                to_remove += nd.descendants(add_self=True)

        clause = [nd for nd in clause if not nd in to_remove]

    if without_punctuation:
        clause = [nd for nd in clause if nd.upos != 'PUNCT']

    return clause


def get_coord_element_phrase(node: Node) -> list[Node]:
    res = node.descendants()
    to_remove = []

    if len(res) > 0 and res[0].upos == 'PUNCT':
        res.pop(0)

    for d in res:
        if d.deprel == 'conj':
            to_remove += d.descendants(add_self=True)

    return [d for d in res if d not in to_remove] + [node]


def feat_overlap(n1: Node, n2: Node, feat_id: str) -> bool:
    n1_values = set(n1.feats[feat_id].split(','))
    n2_values = set(n2.feats[feat_id].split(','))

    return bool(n1_values.intersection(n2_values))


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


def is_animate(node: Node) -> bool:
    return node.feats['Animacy'] == 'Anim' or node.feats['Gender'] == 'Fem' or is_named_entity(node)


# FIXME: agree on how to deal with MorphoDiTa
_morphodita: Morpho = None


def _get_morphodita() -> Morpho:
    global _morphodita

    if _morphodita is None:
        print('Load MorphoDiTa dictionary')
        _morphodita = Morpho.load('_local/czech-morfflex2.0-pdtc1.0-220710/czech-morfflex2.0-220710.dict')

    return _morphodita


def morphodita_generate(lemma: str, tag_wildcard: str = '???????????????') -> list[dict[str, str]]:
    morphodita = _get_morphodita()

    lemmas_forms = TaggedLemmasForms()
    morphodita.generate(lemma, tag_wildcard, Morpho.GUESSER, lemmas_forms)

    return [{f.tag: f.form for f in lf.forms} for lf in lemmas_forms]


def n_syncretic(node: Node, case1: str, case2: str, disregard_number: bool = False) -> bool:
    rng = [str(i) for i in range(1, 8)]
    if case1 not in rng or case2 not in rng:
        raise ValueError(f'{case1=} or {case2=} out of range')

    tag_wildcard = node.xpos[:3] + ('?' if disregard_number else node.xpos[3]) + f'[{case1}{case2}]' + node.xpos[5:]
    paradigms = morphodita_generate(node.lemma, tag_wildcard)

    for p in paradigms:
        # if the paradigm is actually syncretic; sometimes UDPipe assigns a wrong case based on context
        if len(p) == len(set(p.values())):
            continue

        for tag, form in p.items():
            if (
                (node.xpos[4] == case1 and tag[4] == case2) or (node.xpos[4] == case2 and tag[4] == case1)
            ) and node.form.lower() == form:
                return True

    return False


def n_syncretic_with(node: Node, case: str, disregard_number: bool = False) -> bool:
    rng = (f'{i}' for i in range(1, 8))
    if case not in rng:
        raise ValueError('case out of range')

    tag_wildcard = node.xpos[:3] + ('?' if disregard_number else node.xpos[3]) + case + node.xpos[5:]
    paradigms = morphodita_generate(node.lemma, tag_wildcard)

    return node.form.lower() in (v for p in paradigms for v in p.values())


def rules_applied(node: Node) -> set[str]:
    rule_annotations = [m.split(':') for m in node.misc if m.startswith(f'{rules.RULE_ANNOTATION_PREFIX}:')]
    return {annotation[1] for annotation in rule_annotations}


@dataclass(frozen=True, slots=True)
class Color:
    red: int
    green: int
    blue: int

    def __post_init__(self):
        for color in self.red, self.green, self.blue:
            if color > 255 or color < 0:
                raise ValueError("Color must be between 0 and 255")
