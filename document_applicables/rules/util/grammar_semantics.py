'''Utilities providing information about grammar and semantics'''

from udapi.core.node import Node
import document_applicables.rules.util.external_tools as utilet
import document_applicables.rules.util.structure_modif as utilsm
import document_applicables.rules.helpers as rulehelpers


def is_punct_sym(node: Node) -> bool:
    return node.upos in ('PUNCT', 'SYM')


def is_aux(node: Node, grammatical_only: bool = False) -> bool:
    if grammatical_only:
        return node.udeprel in ('aux', 'cop') or node.deprel == 'expl:pass'

    return node.udeprel in ('aux', 'expl', 'cop')


def is_clitic(node: Node) -> bool:
    return node.lemma in ('se')  # TODO: expand the list


def is_finite_verb(node: Node) -> bool:
    # Is marked as finite or an l-participle (e.g. "dělal")
    return (node.feats['VerbForm'] == 'Fin') or node.xpos[0:2] == 'Vp'


def is_adposition(node: Node) -> bool:
    return node.deprel in ('case', 'fixed')


def feat_overlap(n1: Node, n2: Node, feat_id: str) -> bool:
    n1_values = set(n1.feats[feat_id].split(','))
    n2_values = set(n2.feats[feat_id].split(','))

    return bool(n1_values.intersection(n2_values))


def is_named_entity(node: Node) -> bool:
    return 'NE' in node.misc


def is_citation(node: Node) -> bool:
    return rulehelpers.CitDetectRule.rule_id in utilsm.rules_applied(node)


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


def is_animate(node: Node) -> bool:
    return node.feats['Animacy'] == 'Anim' or node.feats['Gender'] == 'Fem' or is_named_entity(node)


def n_syncretic(node: Node, case1: str, case2: str, disregard_number: bool = False) -> bool:
    rng = [str(i) for i in range(1, 8)]
    if case1 not in rng or case2 not in rng:
        raise ValueError(f'{case1=} or {case2=} out of range')

    tag_wildcard = node.xpos[:3] + ('?' if disregard_number else node.xpos[3]) + f'[{case1}{case2}]' + node.xpos[5:]
    paradigms = utilet.morphodita_generate(node.lemma, tag_wildcard)

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
    paradigms = utilet.morphodita_generate(node.lemma, tag_wildcard)

    return node.form.lower() in (v for p in paradigms for v in p.values())
