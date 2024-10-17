from __future__ import annotations

from typing import Literal

from udapi.core.node import Node

from document_applicables.rules import Rule, util, Color


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

                if cconj:
                    self.annotate_node('cconj', cconj)
                    self.annotate_measurement('max_allowable_distance', dst, cconj, parent_adpos, coord_el1, coord_el2)
                    self.annotate_parameter(
                        'max_allowable_distance', self.max_allowable_distance, cconj, parent_adpos, coord_el1, coord_el2
                    )
                self.annotate_node('orig_adpos', parent_adpos)
                self.annotate_node('coord_el1', coord_el1)
                self.annotate_node('coord_el2', coord_el2)

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
            and not [c for c in landmark.children if c.udeprel == 'case']
            and (comparative := landmark.parent)
            and 'Degree' in comparative.feats
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
            node.deprel == 'expl:pass'
            and (verb := node.parent)
            and (subj := [s for s in verb.children if s.udeprel == 'nsubj'])
            and 'Animacy' in subj[0].feats
            and subj[0].feats['Animacy'] == 'Anim'
        ):
            self.annotate_node('refl_pass', node, verb)
            self.annotate_node('subj', subj[0])
            self.advance_application_id()
