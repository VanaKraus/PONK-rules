from __future__ import annotations

from typing import ClassVar, Iterable
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
    is_citation,
    is_modal_verb,
)
from document_applicables.rules.util.structure_info import is_clause_root, children_include
from document_applicables.rules.util.structure_retrieval import (
    get_clause,
    get_phrase_heads,
    get_surrounding_bundles_serialize,
    remove_punct_sym,
)
from document_applicables.rules.util.structure_modif import rules_applied


class FluencyOrientationRule(Rule):
    foreground_color: Color = Color(245, 171, 0)
    rule_id: ClassVar[str] = 'cluster'


class RuleTooFewVerbs(FluencyOrientationRule):
    """Capture sentences containing too few verbs.

    Inspiration: Šamánková & Kubíková (2022, p. 37).

    Attributes:
        min_verb_frac (float): the lowest (# of verbs / # of words) fraction value \
            for the sentence to not be considered an issue.
        finite_only (bool): count only finite verbs.
    """

    rule_id: ClassVar[str] = 'RuleTooFewVerbs'
    min_verb_frac: float = 0.06
    finite_only: bool = False

    cz_human_readable_name: str = 'Nedostatek sloves'
    en_human_readable_name: str = 'Too few verbs'
    cz_doc: str = 'Rozdělte větu/souvětí do více vět. Srov. Šamánková & Kubíková (2022, s. 37).'
    en_doc: str = 'Add more clauses to the sentence. Cf. Šamánková & Kubíková (2022, p. 37).'
    cz_paricipants: dict[str, str] = {'verb': 'Sloveso'}
    en_paricipants: dict[str, str] = {'verb': 'Verb'}

    def considered_as_verb(self, node):
        return (
            is_finite_verb(node) if self.finite_only else node.upos in ('VERB', 'AUX')
        ) and node.form.lower() not in ('srov', 'viz')

    def _verb_should_be_counted(self, node):
        return not (not is_clause_root(node) and is_modal_verb(node.parent)) and not (
            is_aux(node, grammatical_only=True)
            and (
                # parent already counted
                self.considered_as_verb(node.parent)
                # parent of the governing word (VERB or a participle) is a modal verb
                or (not is_clause_root(node.parent) and is_modal_verb(node.parent.parent))
                # or the parent has more auxiliaries, in which case only the first should be counted
                or [
                    preceding_nd
                    for preceding_nd in node.parent.children
                    if preceding_nd < node and is_aux(preceding_nd, grammatical_only=True)
                ]
            )
        )

    def process_node(self, node):
        if node.udeprel == 'root':
            sentence = get_clause(node, without_punctuation=True, node_is_root=True)

            if not sentence:
                return

            # count each lexeme only once
            verb_candidates = [nd for nd in sentence if self.considered_as_verb(nd)]
            verbs = {nd for nd in verb_candidates if self._verb_should_be_counted(nd)}
            dismissed_verbs = {nd for nd in verb_candidates if nd not in verbs}

            # language included in citations cannot be dealt with easily
            # but verbs occurring in citations should still be counted as verbs
            sentence_ref = [n for n in sentence if not is_citation(n) and n not in dismissed_verbs]

            if (min_frac := len(verbs) / max(len(get_phrase_heads(sentence_ref, keep=verbs)), 1)) < self.min_verb_frac:
                self.annotate_node('verb', *verbs)

                self.annotate_measurement('min_verb_frac', min_frac, *verbs)
                self.annotate_parameter('min_verb_frac', self.min_verb_frac, *verbs)
                self.annotate_parameter('finite_only', self.finite_only, *verbs)

                self.advance_application_id()


class RuleTooManyNegations(FluencyOrientationRule):
    """Capture sentences with too many negations.

    Inspiration: Šamánková & Kubíková (2022, pp. 40-41), Šváb (2021, p. 33).

    Attributes:
        max_negation_frac (float): the highest (# of negations / # of words with polarity) \
            fraction value for the sentence to not be considered an issue.
        max_allowable_negations (int): the highest # of negations in the sentence for the rule \
            to remain inhibited. This is to allow for double negation in Czech.
    """

    rule_id: ClassVar[str] = 'RuleTooManyNegations'
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
        if self.rule_id not in rules_applied(node) and self._is_negative(node):
            context = [
                n
                for n in get_surrounding_bundles_serialize(node, 0, self.max_right_bundles_count, no_punct_sym=True)
                if not n.precedes(node)
            ][: self.max_right_context_size + 1]

            if [n for n in context if self.rule_id in rules_applied(n)]:
                return

            # save the pos and neg counts for each position in the context
            # so that they don't need to be recomputed each time
            pos_cnt = []
            neg_cnt = []
            # counting from the start of its respective sentence (bundle), this is the k-th negation
            neg_cnt_in_sentence = []

            for i, nd in enumerate(context):
                no_pos = pos_cnt[i - 1] if i > 0 else 0
                no_neg = neg_cnt[i - 1] if i > 0 else 0
                no_neg_in_sentence = neg_cnt_in_sentence[i - 1] if i > 0 and context[i - 1].root == nd.root else 0

                if self._is_positive(nd):
                    no_pos += 1
                elif self._is_negative(nd):
                    no_neg += 1
                    no_neg_in_sentence += 1

                pos_cnt.append(no_pos)
                neg_cnt.append(no_neg)
                neg_cnt_in_sentence.append(no_neg_in_sentence)

            # check that the left-most sentence doesn't contain only one negation given the current context
            for no_neg_in_sentence in neg_cnt_in_sentence:
                # contains more negations, things are fine
                if no_neg_in_sentence > 1:
                    break
                # sentence boundary reached and there was only one negation (otherwise we would've broken the loop)
                if no_neg_in_sentence == 0:
                    return

            span_length = len(context)

            while span_length > self.max_allowable_negations:
                no_pos, no_neg = pos_cnt[span_length - 1], neg_cnt[span_length - 1]
                no_neg_in_last_sentence = neg_cnt_in_sentence[span_length - 1]

                if (
                    no_neg_in_last_sentence > 1
                    and no_neg > self.max_allowable_negations
                    and (max_neg_frac := no_neg / (no_pos + no_neg)) > self.max_negation_frac
                ):
                    negatives_annotate = [n for n in context[:span_length] if self._is_negative(n)]

                    self.annotate_node('negative', *negatives_annotate)

                    self.annotate_measurement('max_negation_frac', max_neg_frac, *negatives_annotate)
                    self.annotate_measurement('max_allowable_negations', no_neg, *negatives_annotate)
                    self.annotate_parameter('max_negation_frac', self.max_negation_frac, *negatives_annotate)
                    self.annotate_parameter(
                        'max_allowable_negations', self.max_allowable_negations, *negatives_annotate
                    )

                    self.advance_application_id()

                    break

                span_length -= self._step

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
        match node.lemma:
            case 'zletilý' | 'stranný' | 'zákonný' | 'zákonně' | 'vinný' | 'zbytný':
                return True
            case 'zaopatřený':
                return node.parent.lemma == 'dítě'
            case 'přímý':
                return node.parent.lemma == 'diskriminace'
            case 'závislý':
                return node.parent.lemma == 'odborník' or (
                    node.parent.lemma == 'odborný' and node.parent.parent.lemma == 'komise'
                )

        return False


class RuleTooManyNominalConstructions(FluencyOrientationRule):
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

    rule_id: ClassVar[str] = 'RuleTooManyNominalConstructions'
    max_noun_frac: float = 0.45
    max_allowable_nouns: int = 5
    max_dismissable_span_length: int = 15

    @classmethod
    def _strip_of_coordinated_nouns(cls, nodes: Iterable[Node]) -> list[Node]:
        return [n for n in nodes if not (n.upos == 'NOUN' and n.deprel == 'conj')]

    @classmethod
    def _autosemantic_abbreviation(cls, node: Node) -> bool:
        """Returns True if `node` is an abbreviation"""
        if node.feats['Abbr'] != 'Yes' or node.form.upper() != node.form or len(node.form) <= 1:
            return False

        descendants = node.root.descendants
        directly_preceded_by_a_number = (
            node.ord > 1
            and descendants[node.ord - 2].feats['SpaceAfter'] == 'No'
            and descendants[node.ord - 2].feats['NumForm'] == 'Digit'
        )
        directly_followed_by_a_number = (
            node.ord < len(descendants)
            and node.feats['SpaceAfter'] == 'No'
            and descendants[node.ord].feats['NumForm'] == 'Digit'
        )

        return (not directly_preceded_by_a_number) and (not directly_followed_by_a_number)

    @classmethod
    def _filter(cls, nodes: Iterable[Node]) -> list[Node]:
        nodes = cls._strip_of_coordinated_nouns(nodes)
        nodes = [n for n in nodes if (n.feats['Abbr'] != 'Yes' or cls._autosemantic_abbreviation(n))]

        return nodes

    def process_node(self, node: Node):
        if is_clause_root(node):
            clause = get_clause(node, without_subordinates=True, without_punctuation=True, node_is_root=True)
            clause = [n for n in clause if not is_citation(n)]
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
                # coordinated nouns and most abbreviations are stripped from the measurements
                # the nouns are still kept for eventual highlighting though
                if (scl_len := len(self._filter(remove_punct_sym(subclause)))) > self.max_dismissable_span_length:
                    nouns = [n for n in subclause if n.upos == 'NOUN' and not is_named_entity(n)]

                    if (l := len(self._filter(nouns))) > self.max_allowable_nouns and (
                        noun_frac := float(l) / scl_len
                    ) > self.max_noun_frac:

                        self.annotate_parameter('max_noun_frac', self.max_noun_frac, *nouns)
                        self.annotate_measurement('max_noun_frac', noun_frac, *nouns)
                        self.annotate_parameter('max_allowable_nouns', self.max_allowable_nouns, *nouns)
                        self.annotate_measurement('max_allowable_nouns', l, *nouns)

                        self.annotate_node('noun', *nouns)
                        self.advance_application_id()


class RuleFunctionWordRepetition(FluencyOrientationRule):
    """Capture repeating function words.

    Inspiration: Sgall & Panevová (2014, p. 88).
    """

    rule_id: ClassVar[str] = 'RuleFunctionWordRepetition'

    cz_human_readable_name: str = 'Opakování gramatických slov'
    en_human_readable_name: str = 'Function word repetition'
    cz_doc: str = 'Srov. Sgall & Panevová (2014, s. 88).'
    en_doc: str = 'Cf. Sgall & Panevová (2014, p. 88).'
    cz_paricipants: dict[str, str] = {'repetition': 'Opakování'}
    en_paricipants: dict[str, str] = {'repetition': 'Repetition'}

    def process_node(self, node: Node):
        if node.upos in ('ADP', 'SCONJ', 'CCONJ') and (
            following_node := [n for n in node.root.descendants if n.ord == node.ord + 1 and n.lemma == node.lemma]
        ):
            self.annotate_node('repetition', node, *following_node)
            self.advance_application_id()


class RuleCaseRepetition(FluencyOrientationRule):
    """Capture spans of texts with high density of nouns (and adjectives) in the same case. Punctuation, \
    adpositions, and conjunctions are excluded from the count.

    Inspiration: Sgall & Panevová (2014, pp. 88-90).

    Attributes:
        include_adjetives (bool): include adjectives to the count.
        max_repetition_count (int): max number of one case occurences to not be considered an issue.
        max_repetition_frac (int): max (# of one case occurences / length of the span) to not be considered an issue.
    """

    rule_id: ClassVar[str] = 'RuleCaseRepetition'
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

            # FIXME: capturing adjectives even with !self.include_adjectives ??
            following_nodes = [node] + [
                d for d in descendants if d.ord > node.ord and d.upos not in ('PUNCT', 'ADP', 'CCONJ', 'SCONJ')
            ]

            # do not consider coordinations
            min_conj_ord = math.inf
            for n in following_nodes:
                if n != node and n.deprel == 'conj':  # TODO: but only if the conj is in the same case as node
                    min_conj_ord = min(min_conj_ord, n.ord)

                    for d in node.descendants(add_self=True):
                        if d in following_nodes:
                            following_nodes.remove(d)

            # if a gap greater than 3 nodes is found in following_nodes, keep only the left nodes
            for i, n in enumerate(following_nodes[:-1]):
                if following_nodes[i + 1].ord - n.ord > 3:
                    following_nodes = following_nodes[: i + 1]
                    break

            # only keep nodes that did not reach into coordinated phrases
            following_nodes = [n for n in following_nodes if n.ord < min_conj_ord]

            ne_reg = NEregister(node)
            same_case_nodes = [
                (
                    n
                    if n.upos in self._tracked_pos
                    and n.feats['Case'] == node.feats['Case']
                    and n.deprel != 'appos'
                    and not ne_reg.is_registered_ne(n)
                    and not is_citation(n)
                    else None
                )
                for n in following_nodes
            ]

            # how many same-case nodes from the same_case_nodes[0] until same_case_nodes[i] (incl.)
            no_same_case_nodes = []
            # if all same-case nodes have already been visited by another application of the rule
            all_scn_already_visited = []
            for i, scn in enumerate(same_case_nodes):
                no_same_case_nodes += [(no_same_case_nodes[i - 1] if i > 0 else 0) + (1 if scn else 0)]
                all_scn_already_visited += [
                    (all_scn_already_visited[i - 1] if i > 0 else True)
                    and ((scn is None) or self.__class__.id() in rules_applied(scn))
                ]

            ctx_size = len(following_nodes)

            while ctx_size >= self.max_repetition_count and ctx_size > 0:
                if not same_case_nodes[ctx_size - 1]:
                    ctx_size -= 1
                    continue

                if no_same_case_nodes[ctx_size - 1] <= self.max_repetition_count:
                    break

                # if the rule has already been applied to all nodes in same_case_nodes, there's no point in continuing
                if all_scn_already_visited[ctx_size - 1]:
                    break

                if (repetition_frac := no_same_case_nodes[ctx_size - 1] / ctx_size) > self.max_repetition_frac:
                    scn_annotate, NEs = [], set()
                    for i, n in enumerate(following_nodes):
                        NEs_n = set(n.misc['NE'].split('-'))
                        # ... so that all belonging NEs are highlighted
                        if (i < ctx_size and same_case_nodes[i]) or (
                            NEs.intersection(NEs_n) and n.feats['Case'] == node.feats['Case']
                        ):
                            scn_annotate += [n]
                            NEs |= NEs_n

                    self.annotate_parameter('max_repetition_count', self.max_repetition_count, *scn_annotate)
                    self.annotate_measurement('max_repetition_count', no_same_case_nodes[ctx_size - 1], *scn_annotate)
                    self.annotate_parameter('max_repetition_frac', self.max_repetition_frac, *scn_annotate)
                    self.annotate_measurement('max_repetition_frac', repetition_frac, *scn_annotate)
                    self.annotate_parameter('include_adjectives', self.include_adjectives, *scn_annotate)

                    self.annotate_node('case_repetition', *scn_annotate)
                    self.advance_application_id()
                    break

                ctx_size -= 1


class RuleVerbalNouns(FluencyOrientationRule):
    """Capture verbal nouns.

    Inspiration: Šamánková & Kubíková (2022, pp. 38–39), Šváb (2021, p. 30).
    """

    rule_id: ClassVar[str] = 'RuleVerbalNouns'

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


class RuleLongSentences(FluencyOrientationRule):
    """Capture sentences that are too long.

    Inspiration: Šamánková & Kubíková (2022, p. 51), Šváb (2021, pp. 17–18).

    Attributes:
        max_length (int): how long the sentence can be to not be considered an issue.
        without_punctuation (bool): exclude punctuation from the count.
    """

    rule_id: ClassVar[str] = 'RuleLongSentences'
    max_length: int = 50
    without_punctuation: bool = False

    cz_human_readable_name: str = 'Příliš dlouhé věty'
    en_human_readable_name: str = 'Too long sentences'
    cz_doc: str = (
        'Rozdělte větu/souvětí do více vět/souvětí. Srov. Šamánková & Kubíková (2022, s. 51), Šváb (2021, s. 17–18).'
    )
    en_doc: str = (
        'Split the sentence into multiple sentences. Cf. Šamánková & Kubíková (2022, pp. 51), Šváb (2021, pp. 17–18).'
    )
    cz_paricipants: dict[str, str] = {'long_sentence': 'Dlouhá věta / dlouhé souvětí'}
    en_paricipants: dict[str, str] = {'long_sentence': 'Long sentence'}

    def process_node(self, node):
        if node.udeprel == 'root':
            descendants = get_clause(node, without_punctuation=self.without_punctuation, node_is_root=True)

            if not descendants:
                return

            phrases = get_phrase_heads(descendants)
            nocit_phrases = [n for n in phrases if not is_citation(n)]

            if (max_length := len(nocit_phrases)) > self.max_length:
                self.annotate_node('long_sentence', *descendants)

                self.annotate_measurement('max_length', max_length, *descendants)
                self.annotate_parameter('max_length', self.max_length, *descendants)
                self.annotate_parameter('without_punctuation', self.without_punctuation, *descendants)

                self.advance_application_id()
