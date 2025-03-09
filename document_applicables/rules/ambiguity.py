from __future__ import annotations

from typing import Literal

from udapi.core.node import Node

from document_applicables.rules import Rule, util, Color


# TODO: you don't need to ask if 'xxx' in feats when needing to access node.feats['xxx']


class AmbiguityRule(Rule):
    foreground_color: Color = Color(125, 25, 200)
    rule_id: Literal['ambiguity'] = 'ambiguity'


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

    rule_id: Literal['RuleDoubleAdpos'] = 'RuleDoubleAdpos'
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
        'coord_el1': 'První člen spojení',
        'coord_el2': 'Druhý člen spojení',
    }
    en_paricipants: dict[str, str] = {
        'orig_adpos': 'Preposition on the 1st element',
        'add': 'Preposition on the 2nd element',
        'cconj': 'Coordinate conjunction',
        'coord_el1': '1st element of the coordination',
        'coord_el2': '2nd element of the coordination',
    }

    def process_node(self, node: Node):
        if node.deprel != 'conj' or node.parent.parent is None:  # in case parent_adpos doesn't have a parent
            return  # nothing we can do for this node, bail

        coord_el2 = node

        # find an adposition present in the coordination
        for parent_adpos in [nd for nd in coord_el2.siblings if nd.udeprel == "case" and nd.upos == "ADP"]:
            coord_el1 = parent_adpos.parent
            parent_adpos_desc = parent_adpos.descendants(add_self=True)

            # check that the two coordination elements have the same case
            if coord_el2.feats["Case"] != coord_el1.feats["Case"]:
                continue

            # check that the two coordination elements aren't too close to each-other
            if (dst := coord_el2.ord - coord_el1.ord) <= self.max_allowable_distance:
                continue

            # check that the second coordination element doesn't already have an adposition
            if not [nd for nd in coord_el2.children if nd.lemma == parent_adpos.lemma] and not [
                nd for nd in coord_el2.children if nd.upos == "ADP"
            ]:
                cconj = ([None] + [c for c in coord_el2.children if c.deprel in ('cc', 'punct') and c.lemma != '.'])[-1]

                if not self.detect_only:
                    raise NotImplementedError('multi-word adposition handling not implemented')
                    correction = util.clone_node(
                        parent_adpos,
                        coord_el2,
                        filter_misc_keys=r"^(?!Rule).*",
                        include_subtree=True,
                    )

                    correction.form = parent_adpos.form.lower()
                    if cconj:
                        correction.shift_after_subtree(cconj)
                    else:
                        correction.shift_before_node(coord_el2.descendants(add_self=True)[0])

                    for node_to_annotate in correction.descendants(add_self=True):

                        self.annotate_node('add', node_to_annotate)

                cel1highlight = [d for d in util.get_coord_element_phrase(coord_el1) if d not in parent_adpos_desc]
                cel2highlight = util.get_coord_element_phrase(coord_el2)

                if cconj:
                    self.annotate_node('cconj', cconj)
                    self.annotate_measurement('max_allowable_distance', dst, cconj)
                    self.annotate_parameter('max_allowable_distance', self.max_allowable_distance, cconj)

                self.annotate_measurement(
                    'max_allowable_distance', dst, *parent_adpos_desc, *cel1highlight, *cel2highlight
                )
                self.annotate_parameter(
                    'max_allowable_distance',
                    self.max_allowable_distance,
                    *parent_adpos_desc,
                    *cel1highlight,
                    *cel2highlight,
                )
                self.annotate_node('orig_adpos', *parent_adpos_desc)
                self.annotate_node('coord_el1', *cel1highlight)
                self.annotate_node('coord_el2', *cel2highlight)

                self.advance_application_id()

                if not self.detect_only:
                    self.modified_roots.add(cconj.root)


class RuleAmbiguousRegards(AmbiguityRule):
    """Capture regard constructions (e.g. [trajector] is greater than [landmark]) \
        that are ambiguous as to which word fills the [trajector] slot.

    Inspiration: Sgall & Panevová (2014, pp. 77-78), Šamánková & Kubíková (2022, p. 41).
    """

    rule_id: Literal['RuleAmbiguousRegards'] = 'RuleAmbiguousRegards'

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
            and not util.is_clause_root(landmark := node.parent)
            and not [c for c in landmark.children if util.is_adposition(c)]
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

    rule_id: Literal['RuleReflexivePassWithAnimSubj'] = 'RuleReflexivePassWithAnimSubj'

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
            and util.is_finite_verb(verb)
            and (subj := [s for s in verb.children if s.udeprel == 'nsubj'])
            and util.is_animate(subj[0])
        ):
            self.annotate_node('refl_pass', node, verb)
            self.annotate_node('subj', subj[0])
            self.advance_application_id()


class RuleGPcoordovs(Rule):
    """Capture garden-path sentences where clause-coordinations appear as NP coordinations.

    Inspiration: Ceháková & Chromý (2024).
    """

    # Milada ztratila šálu a čepici ochotně věnovala vnučce.

    rule_id: Literal['RuleGPcoordovs'] = 'RuleGPcoordovs'

    cz_human_readable_name: str = 'Zavádějící spojení vět'
    en_human_readable_name: str = 'Misleading clause coordination'
    cz_doc: str = 'Souřadné spojení dvou vět vypadá jako spojení dvou jmenných frází. Srov. Ceháková & Chromý (2024).'
    en_doc: str = (
        'Coordination of two clauses looks as if it was connecting two nominal phrases. Cf. Ceháková & Chromý (2024).'
    )
    cz_paricipants: dict[str, str] = {'same_case': 'Stejný pád'}
    en_paricipants: dict[str, str] = {'same_case': 'Same case'}

    def process_node(self, node: Node):
        if (node.deprel in ('punct', 'cc')) and node.parent.deprel == 'conj' and util.is_clause_root(node.parent):
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
                    and not util.is_clause_root(previous)
                    and not util.is_clause_root(next)
                    and 'Rel' not in next.feats['PronType'].split(',')
                ):
                    self.annotate_node('same_case', previous, next)


class RuleGPdeverbaddr(Rule):
    '''Capture garden-path sentences where a noun could potentially bind to multiple different tokens due to DAT–INS syncretism.

    Inspiration: Ceháková & Chromý (2024).
    '''

    # Michal ochotně podal správci podepsané formuláře organizátorovi zájezdu.

    cz_human_readable_name: str = 'Nejednoznačný syntaktický vztah'
    en_human_readable_name: str = 'Ambiguous syntactic relation'
    cz_doc: str = (
        'Slovo lze interpretovat jako 3. i jako 7. pád a podle toho může záviset na různých větných členech. '
        + 'Srov. Ceháková & Chromý (2024).'
    )
    en_doc: str = (
        'A noun could be interpreted both as dative or as instrumental and can thus depend on different words. '
        + 'Cf. Ceháková & Chromý (2024).'
    )
    cz_paricipants: dict[str, str] = {'sync': 'Nejednoznačně navázané slovo', 'possible_bind': 'Možný řídící člen'}
    en_paricipants: dict[str, str] = {'sync': 'Ambiguously connected word', 'possible_bind': 'Potential governing word'}

    rule_id: Literal['RuleGPdeverbaddr'] = 'RuleGPdeverbaddr'

    def process_node(self, node: Node):
        if (
            node.upos in ('NOUN', 'PROPN')
            and node.feats['Case'] in ('Dat', 'Ins')
            and not util.is_adposition(node)
            and util.is_animate(node)  # ADDR should be animate
            and not [c for c in node.children if util.is_adposition(c) or c.feats['Case'] == node.feats['Case']]
        ):
            clause_root = util.get_clause_root(node)
            clause = util.get_clause(clause_root, without_subordinates=True, node_is_root=True)

            if node.ord > clause_root.ord and (  # node after the predicate
                pbind := [  # nodes the node could possibly bind onto
                    t
                    for t in clause
                    if node.ord < t.ord and t.upos in ('NOUN', 'ADJ', 'VERB', 'ADV') and ('VerbForm' in t.feats)
                ]
            ):
                tag_wildcard = node.xpos[:3] + '?[37]' + node.xpos[5:]  # generate DAT and INS only
                paradigms = util.morphodita_generate(node.lemma, tag_wildcard)

                for p in paradigms:
                    for tag, form in p.items():
                        if (
                            (node.feats['Case'] == 'Dat' and tag[4] == '7')
                            or (node.feats['Case'] == 'Ins' and tag[4] == '3')
                        ) and node.form.lower() == form:
                            self.annotate_node('sync', node)
                            self.annotate_node('possible_bind', clause_root, *pbind)
                            self.advance_application_id()


class RuleGPpatinstr(Rule):
    '''Capture garden-path sentences where a noun could potentially bind to multiple different tokens due to ACC–INS syncretism.

    Inspiration: Ceháková & Chromý (2024).
    '''

    # Martin konečně navštívil pány vychvalované středisko v horách.

    cz_human_readable_name: str = 'Nejednoznačný syntaktický vztah'
    en_human_readable_name: str = 'Ambiguous syntactic relation'
    cz_doc: str = (
        'Slovo lze interpretovat jako 4. i jako 7. pád a podle toho může být různým větným členem. '
        + 'Srov. Ceháková & Chromý (2024).'
    )
    en_doc: str = (
        'A noun could be interpreted both as accusative or as instrumental and can thus serve different function. '
        + 'Cf. Ceháková & Chromý (2024).'
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

    rule_id: Literal['RuleGPpatinstr'] = 'RuleGPpatinstr'

    def process_node(self, node: Node):
        if (
            node.upos in ('NOUN', 'PROPN')
            and node.feats['Case'] in ('Acc', 'Ins')
            and not util.is_adposition(node)
            and not node.deprel == 'conj'
            and not [
                c
                for c in node.children
                if c.udeprel in ('case', 'conj')
                or (c.feats['Case'] == node.feats['Case'] and not util.n_syncretic(c, '4', '7'))
            ]
        ):
            clause_root = util.get_clause_root(node)
            clause = util.get_clause(clause_root, without_subordinates=True, node_is_root=True)

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
                        or util.is_adposition(po)
                        or po.deprel == 'conj'
                        or [c for c in po.children if util.is_adposition(c)]
                    ):
                        continue

                    if util.n_syncretic_with(po, '4', disregard_number=True):
                        potential_obj = po
                        break

                if potential_obj and util.n_syncretic(node, '4', '7'):
                    self.annotate_node('sync', node)
                    self.annotate_node('possible_bind', root_bind)
                    self.annotate_node('potential_obj', potential_obj)
                    self.advance_application_id()


class RuleGPdeverbsubj(Rule):
    '''Capture garden-path sentences where a noun could potentially bind to multiple different tokens due to NOM–INS syncretism.

    Inspiration: Ceháková & Chromý (2024).
    '''

    # Na středisku pracovali lékaři vyškolení maséři s akreditací.

    cz_human_readable_name: str = 'Nejednoznačný syntaktický vztah'
    en_human_readable_name: str = 'Ambiguous syntactic relation'
    cz_doc: str = (
        'Slovo lze interpretovat jako 1. i jako 7. pád a podle toho může záviset na různých větných členech. '
        + 'Srov. Ceháková & Chromý (2024).'
    )
    en_doc: str = (
        'A noun could be interpreted both as nominative or as instrumental and can thus depend on different words. '
        + 'Cf. Ceháková & Chromý (2024).'
    )
    cz_paricipants: dict[str, str] = {'sync': 'Nejednoznačně navázané slovo', 'possible_bind': 'Možný řídící člen'}
    en_paricipants: dict[str, str] = {'sync': 'Ambiguously connected word', 'possible_bind': 'Potential governing word'}

    rule_id: Literal['RuleGPdeverbsubj'] = 'RuleGPdeverbsubj'

    def process_node(self, node: Node):
        if (
            node.upos in ('NOUN', 'PROPN')
            and node.feats['Case'] in ('Nom', 'Ins')
            and node.udeprel not in ('fixed', 'case', 'conj')
            and not [c for c in node.children if c.udeprel in ('case', 'conj')]
        ):
            clause_root = util.get_clause_root(node)
            clause = util.get_clause(clause_root, without_subordinates=True, node_is_root=True)

            if node.ord > clause_root.ord and (  # node after the predicate
                pbind := [  # nodes the node could possibly bind onto
                    t
                    for t in clause
                    if node.ord < t.ord
                    # binding to VERB tends to be obvious, and binding to NOUN should be impossible
                    and t.upos in ('ADJ', 'ADV')
                    and ('VerbForm' in t.feats)
                    and not [c for c in t.children if util.is_adposition(c)]
                ]
            ):
                # check if there's a potential subject after the node
                potential_subj_present = False

                for potential_subj in clause:
                    if (
                        potential_subj.ord <= node.ord
                        or 'Case' not in potential_subj.feats
                        or util.is_adposition(potential_subj)
                        or [c for c in potential_subj.children if util.is_adposition(c)]
                    ):
                        continue

                    if util.n_syncretic_with(potential_subj, '1', disregard_number=True):
                        potential_subj_present = True
                        break

                if potential_subj_present and util.n_syncretic(node, '1', '7'):
                    self.annotate_node('sync', node)
                    self.annotate_node('possible_bind', clause_root, *pbind)
                    self.advance_application_id()


class RuleGPadjective(Rule):
    '''Capture garden-path sentences where a noun could potentially bind to multiple different tokens due to DAT–LOC syncretism.

    Inspiration: Ceháková & Chromý (2024).
    '''

    # Michal ochotně podal správci podepsané formuláře organizátorovi zájezdu.

    cz_human_readable_name: str = 'Nejednoznačný syntaktický vztah'
    en_human_readable_name: str = 'Ambiguous syntactic relation'
    cz_doc: str = (
        'Slovo lze interpretovat jako 3. i jako 6. pád a podle toho může záviset na různých větných členech. '
        + 'Srov. Ceháková & Chromý (2024).'
    )
    en_doc: str = (
        'A noun could be interpreted both as dative or as locative and can thus depend on different words. '
        + 'Cf. Ceháková & Chromý (2024).'
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

    rule_id: Literal['RuleGPadjective'] = 'RuleGPadjective'

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
            clause = util.get_clause(node, without_subordinates=True)

            if sync := [n for n in clause if n.ord == node.ord + 1 and util.n_syncretic(n, '3', '6')]:
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


class RuleGPpatbenperson(Rule):
    '''Capture garden-path sentences where a noun could potentially be interpreted as a patient or a benefactor \
        due to DAT–ACC syncretism.

    Inspiration: Ceháková & Chromý (2024).
    '''

    # Bohouš nakopl zákaznici ve frontě igelitku s nákupem.

    cz_human_readable_name: str = 'Nejednoznačný syntaktický vztah'
    en_human_readable_name: str = 'Ambiguous syntactic relation'
    cz_doc: str = (
        'Slovo lze interpretovat jako 3. i jako 4. pád a podle toho může být jiným větným členem. '
        + 'Srov. Ceháková & Chromý (2024).'
    )
    en_doc: str = (
        'A noun could be interpreted both as dative or as accusative and can thus serve different function. '
        + 'Cf. Ceháková & Chromý (2024).'
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

    rule_id: Literal['RuleGPpatbenperson'] = 'RuleGPpatbenperson'

    def process_node(self, node: Node):
        if (
            node.upos in ('NOUN', 'PROPN')
            and node.feats['Case'] in ('Acc', 'Dat')
            and not util.is_adposition(node)
            and util.is_animate(node)
            and not [
                c
                for c in node.children
                if c.udeprel in ('case', 'conj')
                or (c.feats['Case'] == node.feats['Case'] and not util.n_syncretic(c, '3', '4'))
            ]
        ):
            clause_root = util.get_clause_root(node)
            clause = util.get_clause(clause_root, without_subordinates=True, node_is_root=True)

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
                    if c.feats['Case'] == o.feats['Case'] and util.n_syncretic(c, '3', '4', disregard_number=True)
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
                        or util.is_adposition(po)
                        or [c for c in po.children if util.is_adposition(c)]
                    ):
                        continue

                    if util.n_syncretic_with(po, '4', disregard_number=True) and not [
                        c
                        for c in po.children
                        if c.feats['Case'] == po.feats['Case']
                        and not util.n_syncretic_with(c, '4', disregard_number=True)
                    ]:
                        potential_obj = po
                        break

                if potential_obj and util.n_syncretic(node, '4', '3'):
                    self.annotate_node('sync', node)
                    self.annotate_node('possible_bind', root_bind)
                    self.annotate_node('potential_obj', potential_obj)
                    self.advance_application_id()


class RuleGPwordorder(Rule):
    '''Capture garden-path sentences where an object noun could potentially be interpreted as an object due to NOM–ACC syncretism.

    Inspiration: Ceháková & Chromý (2024).
    '''

    # Chalífát úspěšně dobyl až generál s armádou žoldnéřů.

    cz_human_readable_name: str = 'Nejednoznačný syntaktický vztah'
    en_human_readable_name: str = 'Ambiguous syntactic relation'
    cz_doc: str = (
        'Slovo v předmětu lze interpretovat i jako 1. pád a může proto vypadat jako podmět. '
        + 'Srov. Ceháková & Chromý (2024).'
    )
    en_doc: str = (
        'An object noun could be interpreted as nominative and thus can appear to be the subject '
        + 'Cf. Ceháková & Chromý (2024).'
    )
    cz_paricipants: dict[str, str] = {'obj': 'Nejednoznačný předmět', 'nsubj': 'Podmět', 'fin_verb': 'Určité sloveso'}
    en_paricipants: dict[str, str] = {'obj': 'Ambiguous object', 'nsubj': 'Subject', 'fin_verb': 'Finite verb'}

    rule_id: Literal['RuleGPwordorder'] = 'RuleGPwordorder'

    def process_node(self, node: Node):
        if (
            node.upos in ('NOUN', 'PROPN')
            and node.udeprel == 'obj'
            and (util.is_clause_root(node.parent) or node.parent.udeprel == 'xcomp')
            and not [
                c
                for c in node.children
                if c.udeprel in ('case', 'conj')
                or (
                    c.feats['Case'] == node.feats['Case']
                    and not [cc for cc in c.children if util.is_adposition(cc)]
                    and not util.n_syncretic_with(c, '1')
                )
            ]
        ):
            clause = util.get_clause(node, without_subordinates=True)
            finite = [t for t in clause if util.is_finite_verb(t)]

            # node before the subject
            if (
                finite
                and (util.feat_overlap(node, finite[0], 'Gender') or 'Gender' not in finite[0].feats)
                and util.feat_overlap(node, finite[0], 'Number')
                and (nsubj := [c for c in clause if c.udeprel == 'nsubj'])
            ):
                if (
                    node.ord < nsubj[0].ord
                    and util.n_syncretic_with(nsubj[0], '1', disregard_number=True)
                    and util.n_syncretic(node, '1', '4', disregard_number=True)
                ):
                    self.annotate_node('obj', node)
                    self.annotate_node('nsubj', *nsubj)
                    self.annotate_node('fin_verb', *finite)
                    self.advance_application_id()
