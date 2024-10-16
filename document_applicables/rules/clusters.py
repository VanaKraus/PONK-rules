from __future__ import annotations

from typing import Literal

from udapi.core.node import Node

from document_applicables.rules import Rule, util, Color


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

    def is_verb(self, node):
        return util.is_finite_verb(node) if self.finite_only else node.upos in ('VERB', 'AUX')

    def process_node(self, node):
        if node.udeprel == 'root':
            sentence = util.get_clause(node, without_punctuation=True, node_is_root=True)

            if not sentence:
                return

            # count each lexeme only once
            verbs = [
                nd
                for nd in sentence
                if self.is_verb(nd)
                and not (
                    util.is_aux(nd, grammatical_only=True)
                    and (
                        self.is_verb(nd.parent)
                        or [
                            preceding_nd
                            for preceding_nd in nd.parent.descendants(preceding_only=True)
                            if preceding_nd != nd and util.is_aux(preceding_nd, grammatical_only=True)
                        ]
                    )
                )
            ]

            if (min_frac := len(verbs) / len(sentence)) < self.min_verb_frac:
                self.annotate_node('verb', *verbs)

                self.annotate_measurement('min_verb_frac', min_frac, *verbs)
                self.annotate_parameter('min_verb_frac', self.min_verb_frac, *verbs)
                self.annotate_parameter('finite_only', self.finite_only, *verbs)

                self.advance_application_id()


class RuleTooManyNegations(ClusterRule):
    """Capture sentences with too many negations.

    Inspiration: Šamánková & Kubíková (2022, pp. 40-41), Šváb (2023, p. 33).

    Attributes:
        max_negation_frac (float): the highest (# of negations / # of words with polarity) \
            fraction value for the sentence to not be considered an issue.
        max_allowable_negations (int): the highest # of negations in the sentence for the rule \
            to remain inhibited. This is to allow for double negation in Czech.
    """

    rule_id: Literal['RuleTooManyNegations'] = 'RuleTooManyNegations'
    max_negation_frac: float = 0.1
    max_allowable_negations: int = 3

    def process_node(self, node):
        if node.udeprel == 'root':
            clause = util.get_clause(node, without_punctuation=True, node_is_root=True)

            positives = [nd for nd in clause if self._is_positive(nd)]
            negatives = [nd for nd in clause if self._is_negative(nd)]

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

    @staticmethod
    def _is_positive(node) -> bool:
        # the aim is to capture (positives and) pronouns denoting an entity (not asking for it or relating it)
        return ('Polarity' in node.feats and node.feats['Polarity'] == 'Pos') or (
            'PronType' in node.feats and node.feats['PronType'] in ('Prs', 'Dem', 'Tot', 'Ind')
        )

    @staticmethod
    def _is_negative(node) -> bool:
        return ('Polarity' in node.feats and node.feats['Polarity'] == 'Neg') or (
            'PronType' in node.feats and node.feats['PronType'] == 'Neg'
        )


class RuleTooManyNominalConstructions(ClusterRule):
    """Capture clauses with too many nominal constructions.

    Inspiration: Sgall & Panevová (2014, p. 41).

    Attributes:
        max_noun_frac (float): the highest (# of nouns / # of words) \
            fraction value for the clause to not be considered an issue.
        max_allowable_nouns (int): the highest # of nouns in the clause for the rule \
            to remain inhibited.
    """

    # TODO: consider reworking the rule similarly to RuleCaseRepetition. It would help with aligning more with Šváb.

    rule_id: Literal['RuleTooManyNominalConstructions'] = 'RuleTooManyNominalConstructions'
    max_noun_frac: float = 0.5
    max_allowable_nouns: int = 3

    def process_node(self, node: Node):
        if util.is_clause_root(node):
            clause = util.get_clause(node, without_subordinates=True, without_punctuation=True, node_is_root=True)

            nouns = [n for n in clause if n.upos == 'NOUN' and (n.ord == 1 or not util.is_named_entity(n))]

            if (l := len(nouns)) > self.max_allowable_nouns and float(l) / len(clause) > self.max_noun_frac:
                self.annotate_node('noun', *nouns)
                self.advance_application_id()


class RuleFunctionWordRepetition(ClusterRule):
    """Capture repeating function words.

    Inspiration: Sgall & Panevová (2014, p. 88).
    """

    rule_id: Literal['RuleFunctionWordRepetition'] = 'RuleFunctionWordRepetition'

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
    max_repetition_frac: float = 0.7

    _tracked_pos: list[str] = None

    def __init__(self, **data):
        super().__init__(**data)

        self._tracked_pos = ('NOUN', 'ADJ') if self.include_adjectives else ('NOUN')

    def process_node(self, node: Node):
        if node.upos in self._tracked_pos and 'Case' in node.feats:
            descendants = node.root.descendants()
            following_nodes = [node] + [
                d for d in descendants if d.ord > node.ord and d.upos not in ('PUNCT', 'ADP', 'CCONJ', 'SCONJ')
            ]

            while len(following_nodes) >= self.max_repetition_count:
                ne_reg = util.NEregister(node)

                same_case_nodes = [
                    n
                    for n in following_nodes
                    if n.upos in self._tracked_pos
                    and n.feats['Case'] == node.feats['Case']
                    and not ne_reg.is_registered_ne(n)
                ]

                if len(same_case_nodes) <= self.max_repetition_count:
                    break

                # if the rule has already been applied to all nodes in same_case_nodes, there's no point in continuing
                notes_already_visited = [n for n in same_case_nodes if self.__class__.id() in util.rules_applied(n)]
                if len(notes_already_visited) == len(same_case_nodes):
                    break

                if len(same_case_nodes) / len(following_nodes) > self.max_repetition_frac:
                    self.annotate_node('case_repetition', *same_case_nodes)
                    self.advance_application_id()
                    break

                following_nodes.pop()
