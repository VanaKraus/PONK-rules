from __future__ import annotations

from typing import Literal

from document_applicables.rules import Rule
from document_applicables.rules.util.communication import Color
from document_applicables.rules.util.grammar_semantics import is_aux, is_clitic, is_finite_verb
from document_applicables.rules.util.measurement import distance_from_list
from document_applicables.rules.util.structure_info import is_clause_root
from document_applicables.rules.util.structure_retrieval import get_phrase_heads, get_clause
from document_applicables.rules.util.structure_modif import rules_applied


class SentencePositionRule(Rule):
    foreground_color: Color = Color(33, 108, 237)
    rule_id: Literal['structural'] = 'structural'


class RulePredSubjDistance(SentencePositionRule):
    """Capture subjects that are too distant from their predicates \
        (or their auxiliaries/copulas when present).

    Inspiration: Šamánková & Kubíková (2022, pp. 53–54), Šváb (2021, pp. 21–22).

    Attributes:
        max_distance (int): how far apart the subject and the predicate can be \
            to not be considered an issue (subject and predicate right next to each other \
            would have distance of 1).
        include_clausal_subjects (bool): take clausal subjects into consideration. Token \
            from the clause closest to the predicate is considered for the distance measurement.
    """

    rule_id: Literal['RulePredSubjDistance'] = 'RulePredSubjDistance'
    max_distance: int = 6
    include_clausal_subjects: bool = False

    cz_human_readable_name: str = 'Vzdálenost mezi přísudkem a podmětem'
    en_human_readable_name: str = 'Distance between predicate and subject'
    cz_doc: str = (
        'Umístěte přísudek a podmět blíž k sobě. Srov. Šamánková & Kubíková (2022, s. 53–54), Šváb (2021, s. 21–22).'
    )
    en_doc: str = (
        'Put the predicate and the subject closer together. '
        + 'Cf. Šamánková & Kubíková (2022, pp. 53–54), Šváb (2021, pp. 21–22).'
    )
    cz_paricipants: dict[str, str] = {'predicate_grammar': 'Přísudek (funkční část)', 'subject': 'Podmět'}
    en_paricipants: dict[str, str] = {'predicate_grammar': 'Predicate (grammatical component)', 'subject': 'Subject'}

    def process_node(self, node):
        if node.udeprel == 'nsubj' or (self.include_clausal_subjects and node.udeprel == 'csubj'):
            # locate predicate
            pred = node.parent

            # if the predicate is analytic, select the (non-conditional) auxiliary or the copula
            if finite_verbs := [
                nd for nd in pred.children if nd.udeprel == 'cop' or (nd.udeprel == 'aux' and nd.feats['Mood'] != 'Cnd')
            ]:
                pred = finite_verbs[0]

            # locate subject
            subj = node
            if node.udeprel == 'csubj':
                raise NotImplementedError('Revise')
                clause = util.get_clause(node, without_subordinates=True, without_punctuation=True, node_is_root=True)
                if node.ord < pred.ord:
                    subj = clause[-1]
                else:
                    subj = clause[0]

            if (
                max_dst := distance_from_list(get_phrase_heads(node.root.descendants(), keep=(subj, pred)), subj, pred)
            ) > self.max_distance:
                self.annotate_node('predicate_grammar', pred)
                self.annotate_node('subject', subj)

                self.annotate_measurement('max_distance', max_dst, pred, subj)
                self.annotate_parameter('max_distance', self.max_distance, pred, subj)
                self.annotate_parameter('include_clausal_subjects', self.include_clausal_subjects, pred, subj)

                self.advance_application_id()


class RulePredObjDistance(SentencePositionRule):
    """Capture objects (both direct and indirect) that are too distant \
        from their parents.

    Inspiration: Šamánková & Kubíková (2022, pp. 53-54).

    Attributes:
        max_distance (int): how far apart the object and the parent can be \
            to not be considered an issue (object and its parent \
            right next to each other would have distance of 1).
    """

    rule_id: Literal['RulePredObjDistance'] = 'RulePredObjDistance'
    max_distance: int = 6

    cz_human_readable_name: str = 'Vzdálenost předmětu od řídícího členu'
    en_human_readable_name: str = 'Distance between an object and its governing word'
    cz_doc: str = 'Umístěte předmět blíž k řídícímu členu. Srov. Šamánková & Kubíková (2022, s. 53–54).'
    en_doc: str = 'Put the object closer to its governing word. Cf. Šamánková & Kubíková (2022, pp. 53–54).'
    cz_paricipants: dict[str, str] = {'object': 'Předmět', 'parent': 'Řídící člen'}
    en_paricipants: dict[str, str] = {'object': 'Object', 'parent': 'Governing word'}

    def process_node(self, node):
        if node.deprel in ('obj', 'iobj'):
            parent = node.parent

            if (
                max_dst := distance_from_list(
                    get_phrase_heads(node.root.descendants(), keep=(node, parent)), node, parent
                )
            ) > self.max_distance:
                self.annotate_node('object', node)
                self.annotate_node('parent', parent)

                self.annotate_measurement('max_distance', max_dst, node, parent)
                self.annotate_parameter('max_distance', self.max_distance, node, parent)

                self.advance_application_id()


class RuleInfVerbDistance(SentencePositionRule):
    """Capture infinitives that are too far from a verbal word they complement.

    Attributes:
        max_distance (int): how far apart the infinitive and the parent can be \
            to not be considered an issue (infinitive and its parent \
            right next to each other would have distance of 1).
    """

    rule_id: Literal['RuleInfVerbDistance'] = 'RuleInfVerbDistance'
    max_distance: int = 5

    # TODO: terminology
    cz_human_readable_name: str = 'Vzdálenost infinitivu od řídícího členu'
    en_human_readable_name: str = 'Distance between an infinitive and its governing word'
    cz_doc: str = 'Umístěte infinitiv blíž k řídícímu členu.'
    en_doc: str = 'Put the infinitive closer to its governing word.'
    cz_paricipants: dict[str, str] = {'infinitive': 'Infinitiv', 'verb': 'Řídící člen'}
    en_paricipants: dict[str, str] = {'infinitive': 'Infinitive', 'verb': 'Governing word'}

    def process_node(self, node):
        if (
            (infinitive := node).feats['VerbForm'] == 'Inf'
            and 'VerbForm' in (verb := infinitive.parent).feats
            and not is_clause_root(infinitive)
            and infinitive.deprel not in ('conj', 'csubj')
            and infinitive.upos != 'AUX'
            # it mainly attributes the za+ACC argument to the ACC argument, behaving as an "epistemic copula" of sorts
            and verb.lemma != 'považovat'
        ):

            if (
                max_dst := distance_from_list(
                    get_phrase_heads(infinitive.root.descendants(), keep={verb, infinitive}), verb, infinitive
                )
            ) > self.max_distance:
                auxiliaries = [a for a in verb.children if a.deprel in ('aux', 'cop')]

                self.annotate_node('infinitive', infinitive)
                self.annotate_node('verb', verb, *auxiliaries)

                self.annotate_measurement('max_distance', max_dst, infinitive, verb, *auxiliaries)
                self.annotate_parameter('max_distance', self.max_distance, infinitive, verb, *auxiliaries)

                self.advance_application_id()


class RuleMultiPartVerbs(SentencePositionRule):
    """Capture multi-word verbal forms the parts of which (auxiliaries and clitics) \
        are too far apart from the root (content) token.

    Inspired by: Šamánková & Kubíková (2022, pp. 53–54).

    Attributes:
        max_distance (int): how far apart the auxiliary/clitic can be from the root \
            to not be considered an issue (auxiliary/clitic and the root \
            right next to each other would have distance of 1).
    """

    rule_id: Literal['RuleMultiPartVerbs'] = 'RuleMultiPartVerbs'
    max_distance: int = 5

    # TODO: terminology
    cz_human_readable_name: str = 'Roztroušené složené slovesné tvary'
    en_human_readable_name: str = 'Scattered compound verb forms'
    cz_doc: str = 'Umístěte části slovesného tvaru blíž k sobě. Srov. Šamánková & Kubíková (2022, s. 53–54).'
    en_doc: str = 'Put the parts of the verb form closer together. Cf. Šamánková & Kubíková (2022, pp. 53–54).'
    cz_paricipants: dict[str, str] = {'head': 'Hlavní část', 'aux': 'Pomocné slovo'}
    en_paricipants: dict[str, str] = {'head': 'Main part', 'aux': 'Auxiliary word'}

    def process_node(self, node):
        # if node is an auxiliary and hasn't been marked as such yet
        if (
            is_aux(node, grammatical_only=True)
            and not is_clitic(node)  # word order is very binding for clitics
            and not {k: v for k, v in node.misc.items() if k.split(':')[0] == self.rule_id and v == 'aux'}
        ):
            parent = node.parent
            if 'VerbForm' not in parent.feats:
                return

            # find remaining auxiliaries
            auxiliaries = {node}
            for child in parent.children:
                if is_aux(child, grammatical_only=True) and not child in auxiliaries:
                    auxiliaries.add(child)

            # find if the verb is too spread out
            sentence_wo_punct_sym = get_phrase_heads(node.root.descendants(), keep=(parent, *auxiliaries))

            too_far_apart = False
            max_dst = 0
            for aux in auxiliaries:
                dst = distance_from_list(sentence_wo_punct_sym, parent, aux)
                max_dst = max(max_dst, dst)
                too_far_apart |= dst > self.max_distance

            if too_far_apart:
                self.annotate_node('head', parent)
                self.annotate_node('aux', *auxiliaries)

                self.annotate_measurement('max_distance', max_dst, parent, *auxiliaries)
                self.annotate_parameter('max_distance', self.max_distance, parent, *auxiliaries)

                self.advance_application_id()


class RulePredAtClauseBeginning(SentencePositionRule):
    """Capture predicates (their finite tokens for multi-token predicates) \
        that are too far from the beginning of their clause.

    Inspiration: Šamánková & Kubíková (2022, pp. 53–54).

    Attributes:
        max_order (int): how far the predicate can be to not be considered an issue \
            (predicate right at the beginning of the clause would have the order of 1).
        max_reverse_order (int): how far from the clause end can the predicate root \
            be to not be considered an issue (predicate root directly at the end \
            of the clause considered to have the order of 1).
    """

    cz_human_readable_name: str = 'Přísudek daleko ve větě'
    en_human_readable_name: str = 'Predicate far in the sentence'
    cz_doc: str = (
        'Pokud tím neporušíte plynulost textu, umistěte přísudek blíž k začátku věty. '
        + 'Srov. Šamánková & Kubíková (2022, s. 53–54).'
    )
    en_doc: str = (
        'If it does not break the flow of the text, place the predicate closer to the beginning of the sentence. '
        + 'Cf. Šamánková & Kubíková (2022, pp. 53–54).'
    )
    cz_paricipants: dict[str, str] = {'predicate': 'Přísudek'}
    en_paricipants: dict[str, str] = {'predicate': 'Predicate'}

    rule_id: Literal['RulePredAtClauseBeginning'] = 'RulePredAtClauseBeginning'
    max_order: int = 5
    max_reverse_order: int = 3

    def process_node(self, node):
        # finite verbs or l-participles
        if is_finite_verb(node) and (self.rule_id not in rules_applied(node)):
            pred_root = node.parent if is_aux(node) else node

            clause = get_clause(pred_root, without_subordinates=True, without_punctuation=True, node_is_root=True)

            # if all core arguments precede the predicate and it's close to the end of the clause,
            # it is likely deliberate
            core_args = [
                c
                for c in pred_root.children
                if c.udeprel in ('nsubj', 'obj', 'iobj', 'xcomp')
                or c.deprel in ('obl:agent', 'obl:arg')
                or (c.udeprel in ('csubj', 'ccomp') and not is_clause_root(c))
            ]
            # pred_root at the end of the clause and all core_args precede pred_root
            if (clause[-1].ord - pred_root.ord < self.max_reverse_order) and not [
                a for a in core_args if pred_root.ord < a.ord
            ]:
                return

            # tokens forming the predicate, i.e. predicate root and potentially auxiliaries
            predicate_tokens = [pred_root] + [child for child in pred_root.children if is_aux(child)]
            # sort by order in the sentence
            predicate_tokens.sort(key=lambda a: a.ord)
            first_predicate_token = predicate_tokens[0]

            phrases = get_phrase_heads(node.root.descendants(), keep=[first_predicate_token])

            clause_filter_intersect = [n for n in clause if n in phrases]
            if not clause_filter_intersect:
                return

            clause_beginning = clause_filter_intersect[0]

            # add 1 to make the parameter 1-indexed instead of being 0-indexed
            if (max_ord := distance_from_list(phrases, first_predicate_token, clause_beginning) + 1) > self.max_order:
                self.annotate_node('predicate', *predicate_tokens)

                self.annotate_measurement('max_order', max_ord, *predicate_tokens)
                self.annotate_parameter('max_order', self.max_order, *predicate_tokens)

                self.advance_application_id()
