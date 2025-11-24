from __future__ import annotations

from typing import Literal, Iterable
from collections import Counter
import math

from udapi.core.node import Node

from document_applicables.rules import Rule
from document_applicables.rules.util.communication import Color
from document_applicables.rules.util.grammar_semantics import (
    is_finite_verb,
    is_aux,
    is_named_entity,
    NEregister,
    is_adposition,
)
from document_applicables.rules.util.structure_info import is_clause_root
from document_applicables.rules.util.structure_retrieval import (
    get_clause,
    get_phrase_heads,
    get_surrounding_bundles_serialize,
    remove_punct_sym,
)
from document_applicables.rules.util.structure_modif import rules_applied
from document_applicables.rules.util.external_tools import vallex_get_lexeme, get_derinet


class ClusterRule(Rule):
    foreground_color: Color = Color(245, 171, 0)
    rule_id: Literal['cluster'] = 'cluster'


class RuleTooFewVerbs(ClusterRule):
    """Capture sentences containing too few verbs.

    Inspiration: Šamánková & Kubíková (2022, p. 37).

    Attributes:
        min_verb_frac (float): the lowest (# of verbs / # of words) fraction value \
            for the sentence to not be considered an issue.
        finite_only (bool): count only finite verbs.
    """

    rule_id: Literal['RuleTooFewVerbs'] = 'RuleTooFewVerbs'
    min_verb_frac: float = 0.06
    finite_only: bool = False

    cz_human_readable_name: str = 'Nedostatek sloves'
    en_human_readable_name: str = 'Too few verbs'
    cz_doc: str = 'Rozdělte větu/souvětí do více vět. Srov. Šamánková & Kubíková (2022, s. 37).'
    en_doc: str = 'Add more clauses to the sentence. Cf. Šamánková & Kubíková (2022, p. 37).'
    cz_paricipants: dict[str, str] = {'verb': 'Sloveso'}
    en_paricipants: dict[str, str] = {'verb': 'Verb'}

    def is_verb(self, node):
        return (is_finite_verb(node) if self.finite_only else node.upos in ('VERB', 'AUX')) and not (
            node.form.lower() == 'srov' and node.feats['Abbr'] == 'Yes'
        )

    def process_node(self, node):
        if node.udeprel == 'root':
            sentence = get_clause(node, without_punctuation=True, node_is_root=True)

            if not sentence:
                return

            # count each lexeme only once
            verbs = [
                nd
                for nd in sentence
                if self.is_verb(nd)
                and not (
                    is_aux(nd, grammatical_only=True)
                    and (
                        self.is_verb(nd.parent)
                        or [
                            preceding_nd
                            for preceding_nd in nd.parent.descendants(preceding_only=True)
                            if preceding_nd != nd and is_aux(preceding_nd, grammatical_only=True)
                        ]
                    )
                )
            ]

            if (min_frac := len(verbs) / max(len(get_phrase_heads(sentence)), 1)) < self.min_verb_frac:
                self.annotate_node('verb', *verbs)

                self.annotate_measurement('min_verb_frac', min_frac, *verbs)
                self.annotate_parameter('min_verb_frac', self.min_verb_frac, *verbs)
                self.annotate_parameter('finite_only', self.finite_only, *verbs)

                self.advance_application_id()


class RuleTooManyNegations(ClusterRule):
    """Capture sentences with too many negations.

    Inspiration: Šamánková & Kubíková (2022, pp. 40-41), Šváb (2021, p. 33).

    Attributes:
        max_negation_frac (float): the highest (# of negations / # of words with polarity) \
            fraction value for the sentence to not be considered an issue.
        max_allowable_negations (int): the highest # of negations in the sentence for the rule \
            to remain inhibited. This is to allow for double negation in Czech.
    """

    rule_id: Literal['RuleTooManyNegations'] = 'RuleTooManyNegations'
    max_negation_frac: float = 0.25
    max_allowable_negations: int = 3
    max_right_context_size: int = 40
    max_right_bundles_count: int = 1

    _step: int = 4

    cz_human_readable_name: str = 'Přemíra negací'
    en_human_readable_name: str = 'Too many negations'
    cz_doc: str = (
        'Negativní formulace zamlžují sdělení a natahují text. '
        + 'Srov. Šamánková & Kubíková (2022, s. 40–41), Šváb (2021, s. 33).'
    )
    en_doc: str = (
        'Negative formulations blur the message and prolong the text. '
        + 'Šamánková & Kubíková (2022, pp. 40–41), Šváb (2021, p. 33).'
    )
    cz_paricipants: dict[str, str] = {'negative': 'Negativní výraz'}
    en_paricipants: dict[str, str] = {'negative': 'Negative expression'}

    def process_node(self, node):
        if self.rule_id not in rules_applied(node) and (self._is_positive(node) or self._is_negative(node)):
            context = [
                n
                for n in get_surrounding_bundles_serialize(node, 0, self.max_right_bundles_count, no_punct_sym=True)
                if not n.precedes(node)
            ][: self.max_right_context_size + 1]

            if [n for n in context if self.rule_id in rules_applied(n)]:
                return

            while len(context) > self.max_allowable_negations:
                positives = [nd for nd in context if self._is_positive(nd)]
                negatives = [nd for nd in context if self._is_negative(nd)]

                no_pos, no_neg = len(positives), len(negatives)

                if (
                    no_neg > self.max_allowable_negations
                    and (max_neg_frac := no_neg / (no_pos + no_neg)) > self.max_negation_frac
                ):
                    self.annotate_node('negative', *negatives)

                    self.annotate_measurement('max_negation_frac', max_neg_frac, *negatives)
                    self.annotate_measurement('max_allowable_negations', no_neg, *negatives)
                    self.annotate_parameter('max_negation_frac', self.max_negation_frac, *negatives)
                    self.annotate_parameter('max_allowable_negations', self.max_allowable_negations, *negatives)

                    self.advance_application_id()

                    break

                context = context[: -self._step]

    @classmethod
    def _is_positive(cls, node) -> bool:
        # the aim is to capture (positives and) pronouns denoting an entity (not asking for it or relating it)
        return (
            (node.feats['Polarity'] == 'Pos')
            or (node.feats['PronType'] in ('Prs', 'Dem', 'Tot', 'Ind'))
            or node.lemma in ('dostatek')
        )

    @classmethod
    def _is_negative(cls, node) -> bool:
        return (
            (node.feats['Polarity'] == 'Neg')
            or (node.feats['PronType'] == 'Neg')
            or node.lemma in ('ne', 'nikoli', 'nejen', 'nedostatek')
        ) and not cls._overrride_polarity(node)

    @classmethod
    def _overrride_polarity(cls, node) -> bool:
        """Whether the node is morphologically a negative one but should not be considered such,
        e.g. because it expresses a term or because it doesn't usually occur in its positive variant."""
        return node.lemma in ('zletilý', 'stranný', 'zákonný', 'zákonně', 'vinný', 'zbytný') or (
            node.lemma == 'zaopatřený' and node.parent.lemma == 'dítě'
        )


class RuleTooManyNominalConstructions(ClusterRule):
    """Capture clauses with too many nominal constructions.

    Inspiration: Sgall & Panevová (2014, p. 41).

    Attributes:
        max_noun_frac (float): the highest (# of nouns / # of words) \
            fraction value for the clause to not be considered an issue.
        max_allowable_nouns (int): the highest # of nouns in the clause for the rule \
            to remain inhibited.
        max_dismissable_span_length (int): the highest span length for the rule to remain inhibited.
    """

    cz_human_readable_name: str = 'Přemíra podstatných jmen'
    en_human_readable_name: str = 'Too many nouns'
    cz_doc: str = 'Přemíra podstatných jmen snižuje přirozenost a čtivost textu. Srov. Sgall & Panevová (2014, s. 41).'
    en_doc: str = 'Extensive noun use makes the text less natural and readable. Cf. Sgall & Panevová (2014, p. 41).'
    cz_paricipants: dict[str, str] = {'noun': 'Podstatné jméno'}
    en_paricipants: dict[str, str] = {'noun': 'Noun'}

    rule_id: Literal['RuleTooManyNominalConstructions'] = 'RuleTooManyNominalConstructions'
    max_noun_frac: float = 0.45
    max_allowable_nouns: int = 5
    max_dismissable_span_length: int = 15

    def process_node(self, node: Node):
        if is_clause_root(node):
            clause = get_clause(node, without_subordinates=True, without_punctuation=True, node_is_root=True)
            clause_tmp = clause.copy()

            # separate into subclauses (spans) if an embedded clause is present
            subclauses = []
            for i, n in enumerate(clause[:-1]):
                # if three or more nodes are missing, there was probably an embedded clause
                if clause[i + 1].ord - n.ord > 3:
                    subclauses.append(clause[clause.index(clause_tmp[0]) : i + 1])
                    clause_tmp = clause[i + 1 :]
            subclauses.append(clause_tmp)

            for subclause in subclauses:
                # coordinated nouns are stripped from the measurements
                # the nouns are still kept for eventual highlighting though
                if (
                    scl_len := len(self._strip_of_coordinated_nouns(remove_punct_sym(subclause)))
                ) > self.max_dismissable_span_length:
                    nouns = [n for n in subclause if n.upos == 'NOUN' and not is_named_entity(n)]

                    if (l := len(self._strip_of_coordinated_nouns(nouns))) > self.max_allowable_nouns and (
                        noun_frac := float(l) / scl_len
                    ) > self.max_noun_frac:

                        self.annotate_parameter('max_noun_frac', self.max_noun_frac, *nouns)
                        self.annotate_measurement('max_noun_frac', noun_frac, *nouns)
                        self.annotate_parameter('max_allowable_nouns', self.max_allowable_nouns, *nouns)
                        self.annotate_measurement('max_allowable_nouns', l, *nouns)

                        self.annotate_node('noun', *nouns)
                        self.advance_application_id()

    @classmethod
    def _strip_of_coordinated_nouns(cls, nodes: Iterable[Node]) -> list[Node]:
        return [n for n in nodes if not (n.upos == 'NOUN' and n.deprel == 'conj')]


class RuleFunctionWordRepetition(ClusterRule):
    """Capture repeating function words.

    Inspiration: Sgall & Panevová (2014, p. 88).
    """

    rule_id: Literal['RuleFunctionWordRepetition'] = 'RuleFunctionWordRepetition'

    cz_human_readable_name: str = 'Opakování gramatických slov'
    en_human_readable_name: str = 'Function word repetition'
    cz_doc: str = 'Srov. Sgall & Panevová (2014, s. 88).'
    en_doc: str = 'Cf. Sgall & Panevová (2014, p. 88).'
    cz_paricipants: dict[str, str] = {'repetition': 'Opakování'}
    en_paricipants: dict[str, str] = {'repetition': 'Repetition'}

    def process_node(self, node: Node):
        if node.upos in ('ADP', 'SCONJ', 'CCONJ') and (
            following_node := [n for n in node.root.descendants() if n.ord == node.ord + 1 and n.lemma == node.lemma]
        ):
            self.annotate_node('repetition', node, *following_node)
            self.advance_application_id()


class RuleCaseRepetition(ClusterRule):
    """Capture spans of texts with high density of nouns (and adjectives) in the same case. Punctuation, \
    adpositions, and conjunctions are excluded from the count.

    Inspiration: Sgall & Panevová (2014, pp. 88-90).

    Attributes:
        include_adjetives (bool): include adjectives to the count.
        max_repetition_count (int): max number of one case occurences to not be considered an issue.
        max_repetition_frac (int): max (# of one case occurences / length of the span) to not be considered an issue.
    """

    rule_id: Literal['RuleCaseRepetition'] = 'RuleCaseRepetition'
    include_adjectives: bool = True
    max_repetition_count: int = 4
    max_repetition_frac: float = 0.8

    cz_human_readable_name: str = 'Opakování pádů'
    en_human_readable_name: str = 'Case repetition'
    cz_doc: str = 'Srov. Sgall & Panevová (2014, s. 88–90).'
    en_doc: str = 'Cf. Sgall & Panevová (2014, pp. 88–90).'
    cz_paricipants: dict[str, str] = {'case_repetition': 'Opakování pádů'}
    en_paricipants: dict[str, str] = {'case_repetition': 'Case repetition'}
    _tracked_pos: list[str] = None

    def __init__(self, **data):
        super().__init__(**data)

        self._tracked_pos = ('NOUN', 'ADJ') if self.include_adjectives else ('NOUN')

    def process_node(self, node: Node):
        if node.upos in self._tracked_pos and 'Case' in node.feats:
            descendants = get_clause(node, without_punctuation=True, without_subordinates=True)

            following_nodes = [node] + [
                d for d in descendants if d.ord > node.ord and d.upos not in ('PUNCT', 'ADP', 'CCONJ', 'SCONJ')
            ]

            # do not consider coordinations
            min_conj_ord = math.inf
            for n in following_nodes:
                if n != node and n.deprel == 'conj':
                    min_conj_ord = min(min_conj_ord, n.ord)

                    for d in node.descendants(add_self=True):
                        if d in following_nodes:
                            following_nodes.remove(d)

            for i, n in enumerate(following_nodes[:-1]):
                if following_nodes[i + 1].ord - n.ord > 3:
                    following_nodes = following_nodes[: i + 1]
                    break

            following_nodes = [n for n in following_nodes if n.ord < min_conj_ord]

            while len(following_nodes) >= self.max_repetition_count:
                ne_reg = NEregister(node)

                same_case_nodes = [
                    n
                    for n in following_nodes
                    if n.upos in self._tracked_pos
                    and n.feats['Case'] == node.feats['Case']
                    and n.deprel != 'appos'
                    and not ne_reg.is_registered_ne(n)
                ]

                if len(same_case_nodes) <= self.max_repetition_count:
                    break

                # if the rule has already been applied to all nodes in same_case_nodes, there's no point in continuing
                notes_already_visited = [n for n in same_case_nodes if self.__class__.id() in rules_applied(n)]
                if len(notes_already_visited) == len(same_case_nodes):
                    break

                if (repetition_frac := len(same_case_nodes) / len(following_nodes)) > self.max_repetition_frac:
                    self.annotate_parameter('max_repetition_count', self.max_repetition_count, *same_case_nodes)
                    self.annotate_measurement('max_repetition_count', len(same_case_nodes), *same_case_nodes)
                    self.annotate_parameter('max_repetition_frac', self.max_repetition_frac, *same_case_nodes)
                    self.annotate_measurement('max_repetition_frac', repetition_frac, *same_case_nodes)
                    self.annotate_parameter('include_adjectives', self.include_adjectives, *same_case_nodes)

                    self.annotate_node('case_repetition', *same_case_nodes)
                    self.advance_application_id()
                    break

                following_nodes.pop()


class RulePassive(ClusterRule):
    """Capture be-passives.

    Inspiration: Šamánková & Kubíková (2022, pp. 39-40), Šváb (2021, p. 27).

    Arguments:
        overt_agent_only (bool): only highlight passives with an overt agent.
    """

    rule_id: Literal['RulePassive'] = 'RulePassive'
    overt_agent_only: bool = True

    cz_human_readable_name: str = 'Opisné pasivum'
    en_human_readable_name: str = 'Participial passive'
    cz_doc: str = (
        'Použijte činný rod („nařídíme další opatření“), případně zvratné pasivum („nařídí se další opatření“). '
        + 'Srov. Šamánková & Kubíková (2022, s. 39–40), Šváb (2021, s. 27).'
    )
    en_doc: str = (
        'Use the active voice (“nařídíme další opatření”) or the reflexive passive (“nařídí se další opatření”). '
        + 'Cf. Šamánková & Kubíková (2022, pp. 39–40), Šváb (2021, p. 27).'
    )
    cz_paricipants: dict[str, str] = {'aux': 'Pomocné sloveso', 'participle': 'Příčestí trpné'}
    en_paricipants: dict[str, str] = {'aux': 'Auxiliary verb', 'participle': 'Passive participle'}

    def _overt_agent_decision(self, participle, aux) -> bool:
        act_candidates_ins = [
            n
            for n in participle.children
            if n.deprel == 'obl:arg' and n.feats['Case'] == 'Ins' and not [c for c in n.children if is_adposition(c)]
        ]
        act_candidates_od_gen = [
            n
            for n in participle.children
            if n.deprel == 'obl:arg' and n.feats['Case'] == 'Gen' and [c for c in n.children if c.lemma == 'od']
        ]

        derinet = get_derinet()
        deri_parents = [lx.parent.lemma for lx in derinet.get_lexemes(participle.lemma)]
        # FIXME: sometimes lexemes are identified including their auxiliaries
        # TODO: TEST
        vallex_lexemes = [vallex_get_lexeme(l) for l in deri_parents]

        # if there's a VALLEX entry
        if len(vallex_lexemes) > 0:
            # dict[LU-ID, <given current ACT candidates, there's certainly an overt ACT>]
            clearly_overt_act: dict[str, bool] = dict()

            for lexeme in vallex_lexemes:
                for lu in lexeme['lexical_units']:
                    # if the LU doesn't have a passive alternation, it can be skipped
                    # since UDPipe assures us that we're dealing with a passive alternation
                    if not [diat for diat in lu['diat']['data'] if diat['type'] == 'passive']:
                        continue

                    forms = [form for frame_element in lu['frame']['elements'] for form in frame_element['forms']]
                    forms_cntr = Counter(forms)

                    clearly_overt_act[
                        lu['id'],
                        len(act_candidates_ins) > forms_cntr['7'] or len(act_candidates_od_gen) > forms_cntr['od+2'],
                    ]

            # if none of the LUs disqualifies the candidates from being interpreted as overt ACTs
            # and at least one LU with a passive alternation has been found in VALLEX
            return all(clearly_overt_act.values()) and len(clearly_overt_act) > 0

        else:
            return (
                act_candidates_ins
                # "být shledán/uznán nějakým (např. nedostatečným)"
                and participle.lemma not in ('shledaný', 'uznaný')
            ) or act_candidates_od_gen

    def process_node(self, node):
        if node.deprel == 'aux:pass':
            parent = node.parent

            if (not self.overt_agent_only) or self._overt_agent_decision(parent, node):
                self.annotate_node('aux', node)
                self.annotate_node('participle', parent)

                self.advance_application_id()


class RuleVerbalNouns(ClusterRule):
    """Capture verbal nouns.

    Inspiration: Šamánková & Kubíková (2022, pp. 38–39), Šváb (2021, p. 30).
    """

    rule_id: Literal['RuleVerbalNouns'] = 'RuleVerbalNouns'

    cz_human_readable_name: str = 'Podstatná jména slovesná'
    en_human_readable_name: str = 'Verbal nouns'
    cz_doc: str = (
        'Zvažte nahrazení podstatného jména slovesného větou. '
        + 'Srov. Šamánková & Kubíková (2022, s. 38–39), Šváb (2021, s. 30).'
    )
    en_doc: str = (
        'Consider replacing the verbal noun with a clause. '
        + 'Cf. Šamánková & Kubíková (2022, pp. 38–39), Šváb (2021, p. 30).'
    )
    cz_paricipants: dict[str, str] = {'verbal_noun': 'Podstatné jméno slovesné'}
    en_paricipants: dict[str, str] = {'verbal_noun': 'Verbal noun'}

    @classmethod
    def _is_terminology(cls, node: Node) -> bool:
        return node.lemma in ('usnesení', 'rozhodnutí', 'dovolání', 'odvolání')

    def process_node(self, node):
        if node.feats['VerbForm'] == 'Vnoun' and not self._is_terminology(node):
            self.annotate_node('verbal_noun', node)
            self.advance_application_id()
