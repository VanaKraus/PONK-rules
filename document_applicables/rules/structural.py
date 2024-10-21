from __future__ import annotations

from typing import Literal

from document_applicables.rules import Rule, util, Color


class StructuralRule(Rule):
    foreground_color: Color = Color(70, 12, 21)
    rule_id: Literal['structural'] = 'structural'


class RulePassive(StructuralRule):
    """Capture be-passives.

    Inspiration: Šamánková & Kubíková (2022, pp. 39-40), Šváb (2023, p. 27).
    """

    rule_id: Literal['RulePassive'] = 'RulePassive'

    cz_human_readable_name: str = 'Opisné pasivum'
    en_human_readable_name: str = 'Participial passive'
    cz_doc: str = (
        'Použijte činný rod („nařídíme další opatření“), případně zvratné pasivum („nařídí se další opatření“). '
        + 'Srov. Šamánková & Kubíková (2022, s. 39–40), Šváb (2023, s. 27).'
    )
    en_doc: str = (
        'Use the active voice (“nařídíme další opatření”) or the reflexive passive (“nařídí se další opatření”). '
        + 'Cf. Šamánková & Kubíková (2022, pp. 39–40), Šváb (2023, p. 27).'
    )
    cz_paricipants: dict[str, str] = {'aux': 'Pomocné sloveso', 'participle': 'Příčestí trpné'}
    en_paricipants: dict[str, str] = {'aux': 'Auxiliary verb', 'participle': 'Passive participle'}

    def process_node(self, node):
        if node.deprel == 'aux:pass':
            parent = node.parent

            self.annotate_node('aux', node)
            self.annotate_node('participle', parent)

            self.advance_application_id()


class RulePredSubjDistance(StructuralRule):
    """Capture subjects that are too distant from their predicates \
        (or their auxiliaries/copulas when present).

    Inspiration: Šamánková & Kubíková (2022, pp. 53–54), Šváb (2023, pp. 21–22).

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
    en_human_readable_name: str = 'Distance between subject and object'
    cz_doc: str = (
        'Umístěte přísudek a podmět blíž k sobě. Srov. Šamánková & Kubíková (2022, s. 53–54), Šváb (2023, s. 21–22).'
    )
    en_doc: str = (
        'Put the predicate and the subject closer together. '
        + 'Cf. Šamánková & Kubíková (2022, pp. 53–54), Šváb (2023, pp. 21–22).'
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
                clause = util.get_clause(node, without_subordinates=True, without_punctuation=True, node_is_root=True)
                if node.ord < pred.ord:
                    subj = clause[-1]
                else:
                    subj = clause[0]

            if (max_dst := abs(subj.ord - pred.ord)) > self.max_distance:
                self.annotate_node('predicate_grammar', pred)
                self.annotate_node('subject', subj)

                self.annotate_measurement('max_distance', max_dst, pred, subj)
                self.annotate_parameter('max_distance', self.max_distance, pred, subj)
                self.annotate_parameter('include_clausal_subjects', self.include_clausal_subjects, pred, subj)

                self.advance_application_id()


class RulePredObjDistance(StructuralRule):
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

            if (max_dst := abs(parent.ord - node.ord)) > self.max_distance:
                self.annotate_node('object', node)
                self.annotate_node('parent', parent)

                self.annotate_measurement('max_distance', max_dst, node, parent)
                self.annotate_parameter('max_distance', self.max_distance, node, parent)

                self.advance_application_id()


class RuleInfVerbDistance(StructuralRule):
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
    cz_doc: str = 'Umístěte infinitive blíž k řídícímu členu.'
    en_doc: str = 'Put the infinitive closer to its governing word.'
    cz_paricipants: dict[str, str] = {'infinitive': 'Infinitiv', 'verb': 'Řídící člen'}
    en_paricipants: dict[str, str] = {'infinitive': 'Infinitive', 'verb': 'Governing word'}

    def process_node(self, node):
        # FIXME: infinitival coordinations ("považuje za nadbytečné poučovat (...) a rekapitulovat")
        # FIXME: infinitive auxiliaries
        if (
            'VerbForm' in node.feats
            and (infinitive := node).feats['VerbForm'] == 'Inf'
            and 'VerbForm' in (verb := infinitive.parent).feats
        ):

            if (max_dst := abs(verb.ord - infinitive.ord)) > self.max_distance:
                self.annotate_node('infinitive', infinitive)
                self.annotate_node('verb', verb)

                self.annotate_measurement('max_distance', max_dst, infinitive, verb)
                self.annotate_parameter('max_distance', self.max_distance, infinitive, verb)

                self.advance_application_id()


class RuleMultiPartVerbs(StructuralRule):
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
        if util.is_aux(node) and not {
            k: v for k, v in node.misc.items() if k.split(':')[0] == self.rule_id and v == 'aux'
        }:
            parent = node.parent

            # find remaining auxiliaries
            auxiliaries = {node}
            for child in parent.children:
                if util.is_aux(child) and not child in auxiliaries:
                    auxiliaries.add(child)

            # find if the verb is too spread out
            too_far_apart = False
            max_dst = 0
            for aux in auxiliaries:
                dst = abs(parent.ord - aux.ord)
                max_dst = max(max_dst, dst)
                too_far_apart |= dst > self.max_distance

            if too_far_apart:
                self.annotate_node('head', parent)
                self.annotate_node('aux', *auxiliaries)

                self.annotate_measurement('max_distance', max_dst, parent, *auxiliaries)
                self.annotate_parameter('max_distance', self.max_distance, parent, *auxiliaries)

                self.advance_application_id()


class RuleLongSentences(StructuralRule):
    """Capture sentences that are too long.

    Inspiration: Šamánková & Kubíková (2022, p. 51), Šváb (2023, pp. 17–18).

    Attributes:
        max_length (int): how long the sentence can be to not be considered an issue.
        without_punctuation (bool): exclude punctuation from the count.
    """

    rule_id: Literal['RuleLongSentences'] = 'RuleLongSentences'
    max_length: int = 50
    without_punctuation: bool = False

    cz_human_readable_name: str = 'Příliš dlouhé věty'
    en_human_readable_name: str = 'Too long sentences'
    cz_doc: str = (
        'Rozdělte větu/souvětí do více vět/souvětí. Srov. Šamánková & Kubíková (2022, s. 51), Šváb (2023, s. 17–18).'
    )
    en_doc: str = (
        'Split the sentence into multiple sentences. Cf. Šamánková & Kubíková (2022, pp. 51), Šváb (2023, pp. 17–18).'
    )
    cz_paricipants: dict[str, str] = {'long_sentence': 'Dlouhá věta / dlouhé souvětí'}
    en_paricipants: dict[str, str] = {'long_sentence': 'Long sentence'}

    def process_node(self, node):
        if node.udeprel == 'root':
            descendants = util.get_clause(node, without_punctuation=self.without_punctuation, node_is_root=True)

            if not descendants:
                return

            # len(descendants) always >= 1 when add_self == True
            beginning, end = descendants[0], descendants[-1]

            if (max_length := end.ord - beginning.ord) >= self.max_length:
                self.annotate_node('long_sentence', *descendants)

                self.annotate_measurement('max_length', max_length, *descendants)
                self.annotate_parameter('max_length', self.max_length, *descendants)
                self.annotate_parameter('without_punctuation', self.without_punctuation, *descendants)

                self.advance_application_id()


class RulePredAtClauseBeginning(StructuralRule):
    """Capture predicates (their finite tokens for multi-token predicates) \
        that are too far from the beginning of their clause.

    Inspiration: Šamánková & Kubíková (2022, pp. 53–54).

    Attributes:
        max_order (int): how far the predicate can be to not be considered an issue \
            (predicate right at the beginning of the clause would have order of 1).
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

    def process_node(self, node):
        # finite verbs or l-participles
        if util.is_finite_verb(node):
            pred_root = node.parent if util.is_aux(node) else node

            clause = util.get_clause(pred_root, without_subordinates=True, without_punctuation=True, node_is_root=True)

            clause_beginning = clause[0]

            # tokens forming the predicate, i.e. predicate root and potentially auxiliaries
            predicate_tokens = [pred_root] + [child for child in pred_root.children if util.is_aux(child)]
            # sort by order in the sentence
            predicate_tokens.sort(key=lambda a: a.ord)
            first_predicate_token = predicate_tokens[0]

            # add 1 to make the parameter 1-indexed instead of being 0-indexed
            if (max_ord := first_predicate_token.ord - clause_beginning.ord + 1) > self.max_order:
                self.annotate_node('predicate', *predicate_tokens)

                self.annotate_measurement('max_order', max_ord, *predicate_tokens)
                self.annotate_parameter('max_order', self.max_order, *predicate_tokens)

                self.advance_application_id()


class RuleVerbalNouns(StructuralRule):
    """Capture verbal nouns.

    Inspiration: Šamánková & Kubíková (2022, pp. 38–39), Šváb (2023, p. 30).
    """

    rule_id: Literal['RuleVerbalNouns'] = 'RuleVerbalNouns'

    cz_human_readable_name: str = 'Podstatná jména slovesná'
    en_human_readable_name: str = 'Verbal nouns'
    cz_doc: str = (
        'Zvažte nahrazení podstatného jména slovesného větou. '
        + 'Srov. Šamánková & Kubíková (2022, s. 38–39), Šváb (2023, s. 30).'
    )
    en_doc: str = (
        'Consider replacing the verbal noun with a clause. '
        + 'Cf. Šamánková & Kubíková (2022, pp. 38–39), Šváb (2023, p. 30).'
    )
    cz_paricipants: dict[str, str] = {'verbal_noun': 'Podstatné jméno slovesné'}
    en_paricipants: dict[str, str] = {'verbal_noun': 'Verbal noun'}

    def process_node(self, node):
        if 'VerbForm' in node.feats and node.feats['VerbForm'] == 'Vnoun':
            self.annotate_node('verbal_noun', node)
            self.advance_application_id()
