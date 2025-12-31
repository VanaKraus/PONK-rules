from __future__ import annotations

from typing import ClassVar, Callable

from udapi.core.node import Node

from document_applicables.rules import Rule
from document_applicables.rules.util.communication import Color
from document_applicables.rules.util.grammar_semantics import (
    is_adposition,
    is_finite_verb,
    is_animate,
    n_syncretic,
    n_syncretic_with,
    feat_overlap,
    is_citation,
)
from document_applicables.rules.util.structure_info import is_clause_root
from document_applicables.rules.util.structure_retrieval import (
    get_coord_element_phrase,
    get_clause,
    get_clause_root,
    get_surrounding_bundles_serialize,
    get_phrase_heads,
)
from document_applicables.rules.util.measurement import distance_from_list
from document_applicables.rules.util.external_tools import morphodita_generate


class AmbiguityRule(Rule):
    foreground_color: Color = Color(36, 194, 181)
    rule_id: ClassVar[str] = 'ambiguity'


class RuleDoubleAdpos(AmbiguityRule):
    """Capture coordinations where both elements could be headed by a preposition \
    but only the first is.

    Supports transformations.

    Inspiration: Sgall & Panevová (2014, p. 77).

    Attributes:
        max_allowable_distance (int): how far apart the coordination elements can be \
            to not be considered an issue (elements separated by one token only would \
            have distance of 2).
    """

    rule_id: ClassVar[str] = 'RuleDoubleAdpos'
    max_allowable_distance: int = 4

    cz_human_readable_name: str = 'Předložky v souřadných spojeních'
    en_human_readable_name: str = 'Prepositions in coordinations'
    cz_doc: str = (
        'Souřadné spojení může být nejednoznačné, pokud se předložka u druhého členu neopakuje. '
        + 'Např. „boj proti Izraeli a (proti) rozšíření amerického vlivu“. '
        + 'Srov. Sgall & Panevová (2014, s. 77).'
    )
    en_doc: str = (
        'A coordination can be ambiguous when the preposition isn\'t repeated. '
        + 'E.g. “boj proti Izraeli a (proti) rozšíření amerického vlivu”. '
        + 'Cf. Sgall & Panevová (2014, p. 77).'
    )
    cz_paricipants: dict[str, str] = {
        'orig_adpos': 'Předložka u prvního členu',
        'add': 'Předložka u druhého členu',
        'cconj': 'Spojka souřadicí',
        'coord_el': 'Člen spojení',
    }
    en_paricipants: dict[str, str] = {
        'orig_adpos': 'Preposition on the 1st element',
        'add': 'Preposition on the 2nd element',
        'cconj': 'Coordinate conjunction',
        'coord_el': 'Coordination element',
    }

    @classmethod
    def _adpositions(cls, node: Node) -> list[Node]:
        return [nd for nd in node.children if nd.udeprel == "case" and nd.upos == "ADP"]

    @classmethod
    def _has_adposition(cls, node: Node) -> bool:
        return bool(cls._adpositions(node))

    def process_node(self, node: Node):
        if self._has_adposition(node) and not is_citation(node):
            # get all tokens the node is coordinated with (i.e. the whole coordination)
            coordinations = [c for c in node.children if c.deprel == 'conj' and c.feats['Case'] == node.feats['Case']]

            phrase_heads = get_phrase_heads(node.root.descendants, keep=[node] + coordinations)

            # these will point to last element with an adposition throughout iterating
            ref_el, ref_adp = node, self._adpositions(node)[-1]

            # reference element and no-adposition elements following it
            coord_chain = [ref_el]

            def attempt_coord_chain_annotation():
                '''Check if annotation is desired and handle the process.'''
                # if tokens without an adposition visited previously
                if len(coord_chain) > 1:
                    adp_highlight = ref_adp.descendants(add_self=True)

                    # so that all elements of the coordination are highlighted,
                    # although the rule may only have been triggered by the last one
                    el_highlight = [c for c in [node] + coordinations if c >= coord_chain[0] and c <= coord_chain[-1]]
                    cconj_highlight = [nd for c in el_highlight for nd in c.children if nd.deprel == 'cc']

                    self.annotate_node('orig_adpos', *adp_highlight)
                    self.annotate_node('coord_el', *el_highlight)
                    self.annotate_node('cconj', *cconj_highlight)

                    self.annotate_parameter(
                        'max_allowable_distance',
                        self.max_allowable_distance,
                        *adp_highlight,
                        *el_highlight,
                        *cconj_highlight,
                    )
                    self.annotate_measurement(
                        'max_allowable_distance',
                        coord_chain[-1].ord - ref_el.ord,
                        *adp_highlight,
                        *el_highlight,
                        *cconj_highlight,
                    )

                    self.advance_application_id()

            for coord in coordinations:
                # token has an adposition
                if adps := self._adpositions(coord):
                    attempt_coord_chain_annotation()

                    # reset
                    ref_el, ref_adp = coord, adps[-1]
                    coord_chain = [ref_el]

                # token has no adposition and is too far from the reference element and isn't a citation
                elif (
                    distance_from_list(phrase_heads, ref_el, coord) > self.max_allowable_distance
                    and not is_citation(coord)
                    and ref_adp.lemma not in {'mezi', 'in'}  # exceptions
                ):
                    coord_chain += [coord]

            attempt_coord_chain_annotation()


class RuleAmbiguousRegards(AmbiguityRule):
    """Capture comparative constructions (e.g. "znám lepšího právníka než dr. Novák" \
        [= I know a better lawyer than dr. Novák]) that are ambiguous as to what thematic \
        role the phrase after the comparative conjunction has.

    Inspiration: Sgall & Panevová (2014, pp. 77-78), Šamánková & Kubíková (2022, p. 41).
    """

    rule_id: ClassVar[str] = 'RuleAmbiguousRegards'

    cz_human_readable_name: str = 'Nejednoznačný zřetel'
    en_human_readable_name: str = 'Ambiguous regard'
    cz_doc: str = (
        'Srovnávací zřetel může být nejednoznačný. Např. „Znám lepšího právníka než dr. Novák“ '
        + 'může znamenat „než je/zná dr. Novák“. '
        + 'Srov. Sgall & Panevová (2014, s. 77–78), Šamánková & Kubíková (2022, s. 41).'
    )
    en_doc: str = (
        'A comparative regard can be ambiguous. E.g. “Znám lepšího právníka než dr. Novák” '
        + 'can mean both “než je/zná dr. Novák”. '
        + 'Cf. Sgall & Panevová (2014, pp. 77–78), Šamánková & Kubíková (2022, p. 41).'
    )
    # TODO: terminology
    cz_paricipants: dict[str, str] = {
        'comparative': 'Vlastnost',
        'landmark': 'Reference',
        'sconj': 'Podřadicí spojka',
        'trajector': 'Srovnávané',
    }
    en_paricipants: dict[str, str] = {
        'comparative': 'Property',
        'landmark': 'Reference',
        'sconj': 'Subordinate conjunction',
        'trajector': 'What is compared',
    }

    def process_node(self, node):
        if (
            (sconj := node).lemma == 'než'
            and not is_clause_root(landmark := node.parent)
            and not [c for c in landmark.children if is_adposition(c)]
            and (comparative := landmark.parent)
            and comparative.feats['Degree'] == 'Cmp'
            and comparative.parent
        ):
            # trajector should be a noun
            # if comparative.upos == 'ADJ', its parent should be a noun
            # otherwise it may be that comparative.parent is verbal; we try to find its object
            trajector = (
                comparative.parent
                if comparative.upos == 'ADJ'
                else ([c for c in comparative.parent.children if c.udeprel == 'obj'] + [None])[0]
            )

            if trajector and trajector.udeprel == 'obj':
                self.annotate_node('sconj', sconj)
                self.annotate_node('landmark', landmark)
                self.annotate_node('comparative', comparative)
                self.annotate_node('trajector', trajector)

                self.advance_application_id()


class RuleReflexivePassWithAnimSubj(AmbiguityRule):
    """Capture reflexive passives used with animate subjects.

    Inspiration: Sgall & Panevová (2014, pp. 71-72).
    """

    rule_id: ClassVar[str] = 'RuleReflexivePassWithAnimSubj'

    cz_human_readable_name: str = 'Zvratné pasivum s životným podmětem'
    en_human_readable_name: str = 'Reflexive passive with an animate subject'
    cz_doc: str = (
        'Zvratné pasivum s životným podmětem může naznačovat, že je reflexivní samo sloveso. '
        + 'Např. věta „August Comte se označuje za jednoho ze zakladatelů“ naznačuje interpretaci '
        + '„August Comte sám sebe označuje za…“. Zde je lepší použít opisné pasivum („August Comte je označován…“). '
        + 'Srov. Sgall & Panevová (2014, s. 71–72).'
    )
    en_doc: str = (
        'Reflexive passive used with an animate subject suggests that the verb itself is reflexive. '
        + 'E.g. the sentence „August Comte se označuje za jednoho ze zakladatelů“ suggests that '
        + 'August Comte is also the object („August Comte sám sebe označuje za…“). Here it\'s better to use '
        + 'the participial passive („August Comte je označován…“). Cf. Sgall & Panevová (2014, pp. 71–72).'
    )
    cz_paricipants: dict[str, str] = {'refl_pass': 'Zvratné pasivum', 'subj': 'Podmět'}
    en_paricipants: dict[str, str] = {'refl_pass': 'Reflexive passive', 'subj': 'Subject'}

    def process_node(self, node: Node):
        if (
            node.deprel in ('expl:pass', 'obj')
            and node.form.lower() == 'se'
            and (verb := node.parent)
            and is_finite_verb(verb)
            and (subj := [s for s in verb.children if s.udeprel == 'nsubj'])
            and is_animate(subj[0])
        ):
            self.annotate_node('refl_pass', node, verb)
            self.annotate_node('subj', subj[0])
            self.advance_application_id()


class RuleIncompleteConstruction(AmbiguityRule):
    """Capture incomplete multi-token constructions.

    Inspiration: Sgall & Panevová (2014, p. 85).

    Attributes:
        max_right_context_length (int): within how many tokens (punctuation and symbols excluded) \
            the completion is looked for.
        max_right_bundles (int): within how many bundles (sentences) to the right the completeion \
            is looked for.
    """

    rule_id: ClassVar[str] = 'RuleIncompleteConstruction'
    max_right_context_length: int = 50
    max_right_bundles: int = 4

    cz_human_readable_name: str = 'Neúplná konstrukce'
    en_human_readable_name: str = 'Incomplete construction'
    cz_doc: str = (
        'Ujistěte se také, že od sebe části konstrukce nejsou příliš vzdálené. Srov. Sgall & Panevová (2014, s. 85).'
    )
    en_doc: str = (
        'Also make sure that the elements of the construction are not too far apart. Cf. Sgall & Panevová (2014, p. 85).'
    )
    cz_paricipants: dict[str, str] = {
        'jednak': 'Spojka „jednak“ vyžaduje i druhé „jednak“',
        'bud': 'Spojku „buď“ má následovat „nebo“ (příp. „anebo“)',
        'zaprve': 'Příslovce „zaprvé“ by mělo následovat „zadruhé“',
        'sice': 'Spojku „sice“ by mělo následovat „ale“',
        'na_jedne_strane': '„Na jedné/u straně/u“ by mělo následovat „na druhé/ou straně/u“',
    }
    en_paricipants: dict[str, str] = {
        'jednak': 'The conjunction “jednak” requires its second part (“jednak … jednak”)',
        'bud': 'The conjunction „buď“ should be followed by „nebo“ (or „anebo“)',
        'zaprve': 'The adverb “zaprvé” should be followed by “zadruhé”',
        'sice': 'The conjunction “sice” should be followed by “ale”',
        'na_jedne_strane': '“Na jedné/u straně/u” should be followed by “na druhé/ou straně/u”',
    }

    def _get_left_context(self, node: Node):
        return [
            c
            for c in get_surrounding_bundles_serialize(node, self.max_right_bundles, 0, no_punct_sym=True)
            if c.precedes(node)
        ][-self.max_right_context_length :]

    def _get_right_context(self, node: Node):
        return [
            c
            for c in get_surrounding_bundles_serialize(node, 0, self.max_right_bundles, no_punct_sym=True)
            if node.precedes(c)
        ][: self.max_right_context_length]

    def _trim_ctx_from_right(self, nodes: list[Node], criteria: Callable[[Node], bool]) -> list[Node]:
        matches_i = [i for i, n in enumerate(nodes) if criteria(n)]
        return nodes[: matches_i[0]] if matches_i else nodes

    def process_node(self, node: Node):
        def _is_na_jedne_strane(n: Node) -> bool:
            return n.lemma == 'strana' and [c.lemma for c in n.children] == ['na', 'jeden']

        if is_citation(node):
            return

        if node.lemma == 'jednak':
            right_context = self._get_right_context(node)

            # this is to check if it already is preceded by another "jednak"
            left_context = self._get_left_context(node)

            if not [c for c in left_context + right_context if c.lemma == 'jednak']:
                self.annotate_node('jednak', node)
                self.annotate_parameter('max_right_context_length', self.max_right_context_length, node)
                self.annotate_parameter('max_right_bundles', self.max_right_bundles, node)
                self.advance_application_id()

        elif node.lemma in ('buď', 'buďto') and node.upos == 'CCONJ':
            ptr, predecessors = node.parent, set()
            while ptr.parent:
                predecessors |= {ptr}
                ptr = ptr.parent

            if not [
                n
                for n in node.root.descendants()
                if n.lemma in ('nebo', 'anebo') and n.parent and n.parent.parent in predecessors
            ]:
                self.annotate_node('bud', node)
                self.annotate_parameter('max_right_context_length', self.max_right_context_length, node)
                self.annotate_parameter('max_right_bundles', self.max_right_bundles, node)
                self.advance_application_id()

        elif node.lemma == 'zaprvé':
            right_context = self._get_right_context(node)
            right_context = self._trim_ctx_from_right(right_context, lambda n: n.lemma == 'zaprvé')

            if not [t for t in right_context if t.lemma in ('zadruhé', 'zadruhý')]:
                self.annotate_node('zaprve', node)
                self.annotate_parameter('max_right_context_length', self.max_right_context_length, node)
                self.annotate_parameter('max_right_bundles', self.max_right_bundles, node)
                self.advance_application_id()

        elif node.lemma == 'sice' and node.deprel == 'cc':
            right_context = self._get_right_context(node)
            right_context = self._trim_ctx_from_right(right_context, lambda n: n.lemma == 'sice')

            if not [t for t in right_context if t.lemma in ('ale', 'však', 'avšak', 'zato', 'nicméně', 'ovšem')]:
                self.annotate_node('sice', node)
                self.annotate_parameter('max_right_context_length', self.max_right_context_length, node)
                self.annotate_parameter('max_right_bundles', self.max_right_bundles, node)
                self.advance_application_id()

        # na jedné/u straně/u — na druhé/ou straně/u
        elif _is_na_jedne_strane(node):
            right_context = self._get_right_context(node)
            right_context = self._trim_ctx_from_right(right_context, _is_na_jedne_strane)

            if not [
                n for n in right_context if n.lemma == 'strana' and [c.lemma for c in n.children] == ['na', 'druhý']
            ]:
                hghlght = node.children + [node]
                self.annotate_node('na_jedne_strane', *hghlght)
                self.annotate_parameter('max_right_context_length', self.max_right_context_length, *hghlght)
                self.annotate_parameter('max_right_bundles', self.max_right_bundles, *hghlght)
                self.advance_application_id()


class RuleGPcoordovs(AmbiguityRule):
    """Capture garden-path sentences where clause-coordinations appear as NP coordinations.

    Inspiration: Ceháková & Chromý (2023).
    """

    # Milada ztratila šálu a čepici ochotně věnovala vnučce.

    rule_id: ClassVar[str] = 'RuleGPcoordovs'

    cz_human_readable_name: str = 'Zavádějící spojení vět'
    en_human_readable_name: str = 'Misleading clause coordination'
    cz_doc: str = 'Souřadné spojení dvou vět vypadá jako spojení dvou jmenných frází. Srov. Ceháková & Chromý (2023).'
    en_doc: str = (
        'Coordination of two clauses looks as if it was connecting two nominal phrases. Cf. Ceháková & Chromý (2023).'
    )
    cz_paricipants: dict[str, str] = {'same_case': 'Stejný pád'}
    en_paricipants: dict[str, str] = {'same_case': 'Same case'}

    def process_node(self, node: Node):
        if (node.deprel in ('punct', 'cc')) and node.parent.deprel == 'conj' and is_clause_root(node.parent):
            sentence = node.root.descendants()

            if (
                node.ord > 1
                and node.ord < sentence[-1].ord
                and [n for n in sentence if n.ord == node.ord - 1][0].upos != 'PUNCT'
            ):
                previous = [n for n in sentence if n.ord < node.ord][-1]
                next = [n for n in sentence if n.ord > node.ord][0]

                if (
                    'Case' in previous.feats
                    and 'Case' in next.feats
                    and 'case' not in (previous.deprel, next.deprel)
                    and previous.feats['Case'] == next.feats['Case']
                    and not is_clause_root(previous)
                    and not is_clause_root(next)
                    and 'Rel' not in next.feats['PronType'].split(',')
                ):
                    self.annotate_node('same_case', previous, next)
                    self.advance_application_id()


class RuleGPdeverbaddr(AmbiguityRule):
    '''Capture garden-path sentences where a noun could potentially bind to multiple different tokens due to DAT–INS homonymy.

    Inspiration: Ceháková & Chromý (2023).
    '''

    # Michal ochotně podal správci podepsané formuláře organizátorovi zájezdu.

    cz_human_readable_name: str = 'Nejednoznačný syntaktický vztah'
    en_human_readable_name: str = 'Ambiguous syntactic relation'
    cz_doc: str = (
        'Slovo lze interpretovat jako 3. i jako 7. pád a podle toho může záviset na různých větných členech. '
        + 'Srov. Ceháková & Chromý (2023).'
    )
    en_doc: str = (
        'A noun could be interpreted both as dative or as instrumental and can thus depend on different words. '
        + 'Cf. Ceháková & Chromý (2023).'
    )
    cz_paricipants: dict[str, str] = {'sync': 'Nejednoznačně navázané slovo', 'possible_bind': 'Možný řídící člen'}
    en_paricipants: dict[str, str] = {'sync': 'Ambiguously connected word', 'possible_bind': 'Potential governing word'}

    rule_id: ClassVar[str] = 'RuleGPdeverbaddr'

    def process_node(self, node: Node):
        if (
            node.upos in ('NOUN', 'PROPN')
            and node.feats['Case'] in ('Dat', 'Ins')
            and not is_adposition(node)
            and is_animate(node)  # ADDR should be animate
            and not [c for c in node.children if is_adposition(c) or c.feats['Case'] == node.feats['Case']]
        ):
            clause_root = get_clause_root(node)
            clause = get_clause(clause_root, without_subordinates=True, node_is_root=True)

            if node.ord > clause_root.ord and (  # node after the predicate
                pbind := [  # nodes the node could possibly bind onto
                    t
                    for t in clause
                    if node.ord < t.ord and t.upos in ('NOUN', 'ADJ', 'VERB', 'ADV') and ('VerbForm' in t.feats)
                ]
            ):
                tag_wildcard = node.xpos[:3] + '?[37]' + node.xpos[5:]  # generate DAT and INS only
                paradigms = morphodita_generate(node.lemma, tag_wildcard)

                for p in paradigms:
                    for tag, form in p.items():
                        if (
                            (node.feats['Case'] == 'Dat' and tag[4] == '7')
                            or (node.feats['Case'] == 'Ins' and tag[4] == '3')
                        ) and node.form.lower() == form:
                            self.annotate_node('sync', node)
                            self.annotate_node('possible_bind', clause_root, *pbind)
                            self.advance_application_id()


class RuleGPpatinstr(AmbiguityRule):
    '''Capture garden-path sentences where a noun could potentially bind to multiple different tokens due to ACC–INS homonymy.

    Inspiration: Ceháková & Chromý (2023).
    '''

    # Martin konečně navštívil pány vychvalované středisko v horách.

    cz_human_readable_name: str = 'Nejednoznačný syntaktický vztah'
    en_human_readable_name: str = 'Ambiguous syntactic relation'
    cz_doc: str = (
        'Slovo lze interpretovat jako 4. i jako 7. pád a podle toho může být různým větným členem. '
        + 'Srov. Ceháková & Chromý (2023).'
    )
    en_doc: str = (
        'A noun could be interpreted both as accusative or as instrumental and can thus serve different function. '
        + 'Cf. Ceháková & Chromý (2023).'
    )
    cz_paricipants: dict[str, str] = {
        'sync': 'Nejednoznačně navázané slovo',
        'possible_bind': 'Možný řídící člen',
        'potential_obj': 'Možný předmět ve 4. pádě',
    }
    en_paricipants: dict[str, str] = {
        'sync': 'Ambiguously connected word',
        'possible_bind': 'Potential governing word',
        'potential_obj': 'Potential accusative object',
    }

    rule_id: ClassVar[str] = 'RuleGPpatinstr'

    def process_node(self, node: Node):
        if (
            node.upos in ('NOUN', 'PROPN')
            and node.feats['Case'] in ('Acc', 'Ins')
            and not is_adposition(node)
            and not node.deprel == 'conj'
            and not [
                c
                for c in node.children
                if c.udeprel in ('case', 'conj')
                or (c.feats['Case'] == node.feats['Case'] and not n_syncretic(c, '4', '7'))
            ]
        ):
            clause_root = get_clause_root(node)
            clause = get_clause(clause_root, without_subordinates=True, node_is_root=True)

            root_bind = clause_root
            if xcomp := [c for c in root_bind.children if c.deprel == 'xcomp']:
                root_bind = xcomp[0]

            if node.ord > root_bind.ord and [  # node after the predicate
                o for o in root_bind.children if o.udeprel == 'obj'
            ]:  # has an object
                # check if there's a potential object after the node
                potential_obj = None

                for po in (t for t in clause if t.ord > node.ord):
                    if po.upos == 'VERB':
                        break

                    if (
                        'Case' not in po.feats
                        or is_adposition(po)
                        or po.deprel == 'conj'
                        or [c for c in po.children if is_adposition(c)]
                    ):
                        continue

                    if n_syncretic_with(po, '4', disregard_number=True):
                        potential_obj = po
                        break

                if potential_obj and n_syncretic(node, '4', '7'):
                    self.annotate_node('sync', node)
                    self.annotate_node('possible_bind', root_bind)
                    self.annotate_node('potential_obj', potential_obj)
                    self.advance_application_id()


class RuleGPdeverbsubj(AmbiguityRule):
    '''Capture garden-path sentences where a noun could potentially bind to multiple different tokens due to NOM–INS homonymy.

    Inspiration: Ceháková & Chromý (2023).
    '''

    # Na středisku pracovali lékaři vyškolení maséři s akreditací.

    cz_human_readable_name: str = 'Nejednoznačný syntaktický vztah'
    en_human_readable_name: str = 'Ambiguous syntactic relation'
    cz_doc: str = (
        'Slovo lze interpretovat jako 1. i jako 7. pád a podle toho může záviset na různých větných členech. '
        + 'Srov. Ceháková & Chromý (2023).'
    )
    en_doc: str = (
        'A noun could be interpreted both as nominative or as instrumental and can thus depend on different words. '
        + 'Cf. Ceháková & Chromý (2023).'
    )
    cz_paricipants: dict[str, str] = {'sync': 'Nejednoznačně navázané slovo', 'possible_bind': 'Možný řídící člen'}
    en_paricipants: dict[str, str] = {'sync': 'Ambiguously connected word', 'possible_bind': 'Potential governing word'}
    cz_paricipants: dict[str, str] = {'sync': 'Nejednoznačně navázané slovo', 'possible_bind': 'Možný řídící člen'}
    en_paricipants: dict[str, str] = {'sync': 'Ambiguously connected word', 'possible_bind': 'Potential governing word'}

    rule_id: ClassVar[str] = 'RuleGPdeverbsubj'

    def process_node(self, node: Node):
        if (
            node.upos in ('NOUN', 'PROPN')
            and node.feats['Case'] in ('Nom', 'Ins')
            and node.udeprel not in ('fixed', 'case', 'conj')
            and not [c for c in node.children if c.udeprel in ('case', 'conj')]
        ):
            clause_root = get_clause_root(node)
            clause = get_clause(clause_root, without_subordinates=True, node_is_root=True)

            if node.ord > clause_root.ord and (  # node after the predicate
                pbind := [  # nodes the node could possibly bind onto
                    t
                    for t in clause
                    if node.ord < t.ord
                    # binding to VERB tends to be obvious, and binding to NOUN should be impossible
                    and t.upos in ('ADJ', 'ADV')
                    and ('VerbForm' in t.feats)
                    and not [c for c in t.children if is_adposition(c)]
                ]
            ):
                # check if there's a potential subject after the node
                potential_subj_present = False

                for potential_subj in clause:
                    if (
                        potential_subj.ord <= node.ord
                        or 'Case' not in potential_subj.feats
                        or is_adposition(potential_subj)
                        or [c for c in potential_subj.children if is_adposition(c)]
                    ):
                        continue

                    if n_syncretic_with(potential_subj, '1', disregard_number=True):
                        potential_subj_present = True
                        break

                if potential_subj_present and n_syncretic(node, '1', '7'):
                    self.annotate_node('sync', node)
                    self.annotate_node('possible_bind', clause_root, *pbind)
                    self.advance_application_id()


class RuleGPadjective(AmbiguityRule):
    '''Capture garden-path sentences where a noun could potentially bind to multiple different tokens due to DAT–LOC homonymy.

    Inspiration: Ceháková & Chromý (2023).
    '''

    # Michal ochotně podal správci podepsané formuláře organizátorovi zájezdu.

    cz_human_readable_name: str = 'Nejednoznačný syntaktický vztah'
    en_human_readable_name: str = 'Ambiguous syntactic relation'
    cz_doc: str = (
        'Slovo lze interpretovat jako 3. i jako 6. pád a podle toho může záviset na různých větných členech. '
        + 'Srov. Ceháková & Chromý (2023).'
    )
    en_doc: str = (
        'A noun could be interpreted both as dative or as locative and can thus depend on different words. '
        + 'Cf. Ceháková & Chromý (2023).'
    )
    cz_paricipants: dict[str, str] = {
        'prep': 'Pádová předložka',
        'sync': 'Nejednoznačně navázané slovo',
        'possible_bind': 'Možný řídící člen',
    }
    en_paricipants: dict[str, str] = {
        'prep': 'Case preposition',
        'sync': 'Ambiguously connected word',
        'possible_bind': 'Potential governing word',
    }

    rule_id: ClassVar[str] = 'RuleGPadjective'

    @staticmethod
    def _scope_beginning(node: Node) -> bool:
        return node.deprel == 'case' and node.feats['Case'] == 'Loc'

    @staticmethod
    def _build_parent_list(node: Node, add_self: bool = False) -> list[Node]:
        res = [node] if add_self else []

        while node.parent:
            node = node.parent
            res += [node]

        return res

    @classmethod
    def _coordination_within_scope(cls, n1: Node, n2: Node, scope: list[Node]) -> bool:
        if n1.ord >= n2.ord:
            raise ValueError(f'n1 must preceed n2')

        scopeset = set(scope)
        n1_parents = set(cls._build_parent_list(n1, add_self=True)).intersection(scopeset)
        n2_parents = set(cls._build_parent_list(n2)).intersection(scopeset)

        return bool(n1_parents.intersection(n2_parents)) and bool(
            [c for c in n2_parents.union(n1_parents) if c.udeprel == 'conj']
        )

    def process_node(self, node: Node):
        if self._scope_beginning(node):
            clause = get_clause(node, without_subordinates=True)

            if sync := [n for n in clause if n.ord == node.ord + 1 and n_syncretic(n, '3', '6')]:
                scope = sync[0].parent.descendants(add_self=True)

                for i, s in enumerate(scope):
                    if s == node:
                        scope = scope[i:]
                        break

                for i, s in enumerate(scope):
                    if s.ord > node.ord and self._scope_beginning(s):
                        scope = scope[:i]
                        break

                if bind := [
                    n
                    for n in clause
                    if n.ord > node.ord + 1
                    and n in scope
                    and n.upos == 'ADJ'
                    and n.xpos[4] == '6'
                    and n.parent not in sync + [s.parent for s in sync]
                    and not self._coordination_within_scope(sync[0], n, scope)
                ]:
                    self.annotate_node('prep', node)
                    self.annotate_node('sync', *sync)
                    self.annotate_node('possible_bind', *bind)

                    self.advance_application_id()


class RuleGPpatbenperson(AmbiguityRule):
    '''Capture garden-path sentences where a noun could potentially be interpreted as a patient or a benefactor \
        due to DAT–ACC homonymy.

    Inspiration: Ceháková & Chromý (2023).
    '''

    # Bohouš nakopl zákaznici ve frontě igelitku s nákupem.

    cz_human_readable_name: str = 'Nejednoznačný syntaktický vztah'
    en_human_readable_name: str = 'Ambiguous syntactic relation'
    cz_doc: str = (
        'Slovo lze interpretovat jako 3. i jako 4. pád a podle toho může být jiným větným členem. '
        + 'Srov. Ceháková & Chromý (2023).'
    )
    en_doc: str = (
        'A noun could be interpreted both as dative or as accusative and can thus serve different function. '
        + 'Cf. Ceháková & Chromý (2023).'
    )
    cz_paricipants: dict[str, str] = {
        'sync': 'Nejednoznačné slovo',
        'possible_bind': 'Možný řídící člen',
        'potential_obj': 'Možný předmět ve 4. pádě',
    }
    en_paricipants: dict[str, str] = {
        'sync': 'Ambiguous word',
        'possible_bind': 'Potential governing word',
        'potential_obj': 'Potential accusative object',
    }

    rule_id: ClassVar[str] = 'RuleGPpatbenperson'

    def process_node(self, node: Node):
        if (
            node.upos in ('NOUN', 'PROPN')
            and node.feats['Case'] in ('Acc', 'Dat')
            and not is_adposition(node)
            and is_animate(node)
            and not [
                c
                for c in node.children
                if c.udeprel in ('case', 'conj')
                or (c.feats['Case'] == node.feats['Case'] and not n_syncretic(c, '3', '4'))
            ]
        ):
            clause_root = get_clause_root(node)
            clause = get_clause(clause_root, without_subordinates=True, node_is_root=True)

            root_bind = clause_root
            if xcomp := [c for c in root_bind.children if c.deprel == 'xcomp']:
                root_bind = xcomp[0]

            if node.ord > root_bind.ord and [  # node after the predicate
                o
                for o in root_bind.children
                if o.udeprel == 'obj'
                and not [
                    c
                    for c in o.children
                    if c.feats['Case'] == o.feats['Case'] and n_syncretic(c, '3', '4', disregard_number=True)
                ]  # has an object
            ]:
                # check if there's a potential object after the node
                potential_obj = None

                for po in (c for c in clause if c.ord > node.ord):
                    # nodes after another verb probably won't be objects of the previous verb
                    if po.upos == 'VERB':
                        break

                    if (
                        'Case' not in po.feats
                        or (po.upos == 'ADJ' and po.parent.upos == 'NOUN')
                        or po.deprel in ('case', 'conj')
                        or is_adposition(po)
                        or [c for c in po.children if is_adposition(c)]
                    ):
                        continue

                    if n_syncretic_with(po, '4', disregard_number=True) and not [
                        c
                        for c in po.children
                        if c.feats['Case'] == po.feats['Case'] and not n_syncretic_with(c, '4', disregard_number=True)
                    ]:
                        potential_obj = po
                        break

                if potential_obj and n_syncretic(node, '4', '3'):
                    self.annotate_node('sync', node)
                    self.annotate_node('possible_bind', root_bind)
                    self.annotate_node('potential_obj', potential_obj)
                    self.advance_application_id()


class RuleGPwordorder(AmbiguityRule):
    '''Capture garden-path sentences where an object noun could potentially be interpreted as an object due to NOM–ACC homonymy.

    Inspiration: Ceháková & Chromý (2023).
    '''

    # Chalífát úspěšně dobyl až generál s armádou žoldnéřů.

    cz_human_readable_name: str = 'Nejednoznačný syntaktický vztah'
    en_human_readable_name: str = 'Ambiguous syntactic relation'
    cz_doc: str = (
        'Slovo v předmětu lze interpretovat i jako 1. pád a může proto vypadat jako podmět. '
        + 'Srov. Ceháková & Chromý (2023).'
    )
    en_doc: str = (
        'An object noun could be interpreted as nominative and thus can appear to be the subject '
        + 'Cf. Ceháková & Chromý (2023).'
    )
    cz_paricipants: dict[str, str] = {'obj': 'Nejednoznačný předmět', 'nsubj': 'Podmět', 'fin_verb': 'Určité sloveso'}
    en_paricipants: dict[str, str] = {'obj': 'Ambiguous object', 'nsubj': 'Subject', 'fin_verb': 'Finite verb'}

    rule_id: ClassVar[str] = 'RuleGPwordorder'

    def process_node(self, node: Node):
        if (
            node.upos in ('NOUN', 'PROPN')
            and node.udeprel == 'obj'
            and (is_clause_root(node.parent) or node.parent.udeprel == 'xcomp')
            and not [
                c
                for c in node.children
                if c.udeprel in ('case', 'conj')
                or (
                    c.feats['Case'] == node.feats['Case']
                    and not [cc for cc in c.children if is_adposition(cc)]
                    and not n_syncretic_with(c, '1')
                )
            ]
        ):
            clause = get_clause(node, without_subordinates=True)
            finite = [t for t in clause if is_finite_verb(t)]

            # node before the subject
            if (
                finite
                and (feat_overlap(node, finite[0], 'Gender') or 'Gender' not in finite[0].feats)
                and feat_overlap(node, finite[0], 'Number')
                and (nsubj := [c for c in clause if c.udeprel == 'nsubj'])
            ):
                if (
                    node.ord < nsubj[0].ord
                    and n_syncretic_with(nsubj[0], '1', disregard_number=True)
                    and n_syncretic(node, '1', '4', disregard_number=True)
                ):
                    self.annotate_node('obj', node)
                    self.annotate_node('nsubj', *nsubj)
                    self.annotate_node('fin_verb', *finite)
                    self.advance_application_id()
