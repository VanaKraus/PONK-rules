from __future__ import annotations

from typing import ClassVar
from collections import Counter

from udapi.core.node import Node

from document_applicables.rules import Rule
from document_applicables.rules.util.communication import Color
from document_applicables.rules.util.grammar_semantics import is_adposition, is_citation
from document_applicables.rules.util.structure_info import children_include, is_clause_root
from document_applicables.rules.util.structure_modif import get_removing_rules
from document_applicables.rules.util.structure_retrieval import get_clause
from document_applicables.rules.util.external_tools import vallex_get_lexeme, get_derinet


class PhrasesRule(Rule):
    foreground_color: Color = Color(230, 35, 203)
    rule_id: ClassVar[str] = 'phrases'


class RuleWeakMeaningWords(PhrasesRule):
    """Capture semantically weak words.

    Inspiration: Šamánková & Kubíková (2022, pp. 37-38 and p. 39), Sgall & Panevová (2014, p. 86), Šváb (2021, p. 32).
    """

    rule_id: ClassVar[str] = 'RuleWeakMeaningWords'

    cz_human_readable_name: str = 'Vyprázdněná slova'
    en_human_readable_name: str = 'Weak-meaning words'
    cz_doc: str = (
        'Vyvarujte se vyprázdněných slov. Srov. Sgall & Panevová (2014, s. 86), '
        + 'Šamánková & Kubíková (2022, s. 37–38 a s. 39), Šváb (2021, s. 32).'
    )
    en_doc: str = (
        'Avoid weak-meaning words. Cf. Sgall & Panevová (2014, p. 86), '
        + 'Šamánková & Kubíková (2022, pp. 37–38 and p. 39), Šváb (2021, p. 32).'
    )
    cz_paricipants: dict[str, str] = {'weak_meaning_word': 'Vyprázdněné slovo'}
    en_paricipants: dict[str, str] = {'weak_meaning_word': 'Weak-meaning word'}

    _weak_meaning_words: set[str] = {
        'dopadat',
        'zaměřit',
        'poukázat',
        'poukazovat',
        'ovlivnit',
        'ovlivňovat',
        'velmi',
        'uskutečnit',
        'uskutečňovat',
    }

    def model_post_init(self, __context):
        self._all_words = self._weak_meaning_words
        return super().model_post_init(__context)

    @staticmethod
    def _exception(node: Node) -> bool:
        match node.lemma:
            case 'uskutečnit' | 'uskutečňovat':
                return bool([n for n in node.children if n.form.lower() == 'se'])
        return False

    def process_node(self, node):
        if node.lemma in self._all_words and not self._exception(node) and not is_citation(node):
            self.annotate_node('weak_meaning_word', node)
            self.advance_application_id()


class RuleAbstractNouns(PhrasesRule):
    """Capture semantically weak abstract nouns.

    Inspiration: Šamánková & Kubíková (2022, p. 41).
    """

    rule_id: ClassVar[str] = 'RuleAbstractNouns'

    cz_human_readable_name: str = 'Vyprázdněná abstraktní jména'
    en_human_readable_name: str = 'Weak-meaning abstract nouns'
    cz_doc: str = 'Vyvarujte se vyprázdněných podstatných jmen. Srov. Šamánková & Kubíková (2022, s. 41).'
    en_doc: str = 'Avoid weak-meaning abstract nouns. Cf. Šamánková & Kubíková (2022, p. 41).'
    cz_paricipants: dict[str, str] = {'abstract_noun': 'Vyprázdněné abstraktní substantivum'}
    en_paricipants: dict[str, str] = {'abstract_noun': 'Weak-meaning abstract noun'}

    _abstract_nouns: set[str] = {
        'základ',
        'úvaha',
        'charakter',
        'stupeň',
        'aspekt',
        'okolnosti',
        'událost',
        'podmínky',
        'činnost',
        'postup',
        'podstata',
    }

    @staticmethod
    def _is_terminology(node: Node) -> bool:
        match node.lemma:
            case 'stupeň':
                # modifiers listed to exclude various elementary school grades.
                # might be useful to discriminate court instances, which would however require more sophistication
                return node.parent.lemma == 'soud' or children_include(node, {'první', 'druhý', '1', '2', 'I', 'II'})
            case 'činnost':
                return children_include(node, {'trestný', 'pracovní', 'výdělečný', 'rozhodovací', 'závislý'})
            case 'základ':
                return children_include(node, {'mzda', 'stavba'})
            case 'postup':
                return children_include(node, {'úřední', 'zákonný', 'pracovní'}) or [
                    n
                    for n in node.children
                    if n.deprel == 'nmod'
                    and (n.feats['Case'] == 'Gen' or n.feats['Abbr'] == 'Yes')
                    and not [a for a in n.children if a.deprel == 'case']
                ]
            case 'podstata':
                return children_include(node, {'skutkový'})
            case 'událost':
                return children_include(node, {'mimořádný', 'pojistný'})

        return False

    @staticmethod
    def _lexicalized(node: Node) -> bool:
        match node.lemma:
            case 'základ':
                return children_include(node, {'na'}) and children_include(node, {'jehož'})
            case 'úvaha':
                return node.feats['Case'] == 'Acc' and children_include(node, {'v'})

        return False

    def process_node(self, node):
        if (
            node.lemma in self._abstract_nouns
            and not is_adposition(node)
            and not self._is_terminology(node)
            and not self._lexicalized(node)
            and node.feats['Polarity'] != 'Neg'
            and node.feats['Abbr'] != 'Yes'
            and not is_citation(node)
        ):
            self.annotate_node('abstract_noun', node)
            self.advance_application_id()


class RuleRelativisticExpressions(PhrasesRule):
    """Capture relativistic expressions.

    Inspiration: Šamánková & Kubíková (2022, p. 42).
    """

    rule_id: ClassVar[str] = 'RuleRelativisticExpressions'

    cz_human_readable_name: str = 'Relativizující výrazy'
    en_human_readable_name: str = 'Relativising expressions'
    cz_doc: str = (
        'Relativizujícími výrazy svá sdělení záměrně zpochybňujeme. '
        'Jakkoli jsou občas na místě, často se nadužívají. '
        'Srov. Šamánková & Kubíková (2022, s. 42).'
    )
    en_doc: str = (
        'Relativistic expressions are used to undermine confidence in one\'s own message. '
        'Although sometimes justified, they are often overused. '
        'Cf. Šamánková & Kubíková (2022, p. 42).'
    )
    cz_paricipants: dict[str, str] = {'relativistic_expression': 'Relativizující výraz'}
    en_paricipants: dict[str, str] = {'relativistic_expression': 'Relativistic expression'}

    # lemmas; when space-separated, nodes next-to-each-other with corresponding lemmas are looked for
    _expressions: list[list[str]] = [
        expr.split(' ') for expr in ['poněkud', 'jevit', 'patrně', 'do jistý míra', 'snad', 'jaksi', 'obdobně']
    ]

    def process_node(self, node):
        for expr in self._expressions:
            # node matches first lemma in the expression
            if node.lemma.lower() == expr[0]:
                nd_iterator, i = node, 0
                nodes = [nd_iterator]

                # see if next nodes match next lemmas in the expression
                while (nd_iterator := nd_iterator.next_node) and (i := i + 1) < len(expr):
                    if nd_iterator.lemma.lower() != expr[i]:
                        break
                    nodes += [nd_iterator]
                # success listener
                else:
                    for matching_node in nodes:
                        self.annotate_node('relativistic_expression', matching_node)
                    self.advance_application_id()


class RuleConfirmationExpressions(PhrasesRule):
    """Capture extreme-case expressions. They often violate the maxim of quantity \
        in needlessly confirming what the author is already expected to be 100% sure about.

    Inspiration: Šamánková & Kubíková (2022, p. 42).
    """

    rule_id: ClassVar[str] = 'RuleConfirmationExpressions'

    cz_human_readable_name: str = 'Utvrzující výrazy'
    en_human_readable_name: str = 'Confirmation expressions'
    cz_doc: str = 'Vyvarujte se zbytečných utvrzujících výrazů. Srov. Šamánková & Kubíková (2022, s. 42).'
    en_doc: str = 'Avoid redundant confirmation expressions. Cf. Šamánková & Kubíková (2022, p. 42).'
    cz_paricipants: dict[str, str] = {'confirmation_expression': 'Utvrzující výraz'}
    en_paricipants: dict[str, str] = {'confirmation_expression': 'Confirmation expression'}

    _expressions: list[str] = ['nepochybně', 'naprosto', 'rozhodně']

    def process_node(self, node):
        if (
            node.lemma in self._expressions
            and node.ord < node.parent.ord
            and ('Degree' not in node.feats or node.feats['Degree'] == 'Pos')
            and not is_citation(node)
        ):
            if not self.detect_only:
                self.annotate_action('remove', node)

            self.annotate_node('confirmation_expression', node)
            self.advance_application_id()


class RuleRedundantExpressions(PhrasesRule):
    """Capture expressions that aren't needed to convey the message.

    Inspiration: Šamánková & Kubíková (2022, pp. 42-43).
    """

    rule_id: ClassVar[str] = 'RuleRedundantExpressions'

    # up to how many first words of a sentence should still be considered its beginning
    # important for some of the cases
    _sent_beg: int = 10

    cz_human_readable_name: str = 'Slovní vata'
    en_human_readable_name: str = 'Redundant expressions'
    cz_doc: str = 'Srov. Šamánková & Kubíková (2022, s. 42–43).'
    en_doc: str = 'Cf. Šamánková & Kubíková (2022, pp. 42–43).'
    cz_paricipants: dict[str, str] = {'redundant_expression': 'Zbytečný výraz'}
    en_paricipants: dict[str, str] = {'redundant_expression': 'Redundant expression'}

    def process_node(self, node):
        if node.ord > self._sent_beg:
            return

        match node.lemma:
            # je nutné zdůraznit
            case 'nutný':
                if (aux := [c for c in node.children if c.lemma == 'být']) and (
                    inf := [c for c in node.children if c.lemma == 'zdůraznit']
                ):
                    self.annotate_node('redundant_expression', node, aux[0], inf[0])
                    self.advance_application_id()

            # z uvedeného je zřejmé
            case 'zřejmý':
                if (aux := [c for c in node.children if c.lemma == 'být']) and (
                    adj := [
                        c for c in node.children if c.lemma == 'uvedený' and [a for a in c.children if a.lemma == 'z']
                    ]
                ):
                    # little dirty, I'd love to know if it's possible to retreive the adposition from the condition
                    # without it possible being overwritten if there are multiple cs that match c.lemma == 'uvedený'
                    adp = [a for a in adj[0].children if a.lemma == 'z']

                    self.annotate_node('redundant_expression', node, aux[0], adj[0], adp[0])
                    self.advance_application_id()

            # vyvstala otázka
            case 'vyvstat':
                if noun := [c for c in node.children if c.lemma == 'otázka']:
                    self.annotate_node('redundant_expression', node, noun[0])
                    self.advance_application_id()

            # nabízí se otázka
            case 'nabízet':
                if (expl := [c for c in node.children if c.deprel == 'expl:pass']) and (
                    noun := [c for c in node.children if c.lemma == 'otázka']
                ):
                    self.annotate_node('redundant_expression', node, expl[0], noun[0])
                    self.advance_application_id()

            # v neposlední řadě
            case 'řada':
                if (adj := [c for c in node.children if c.lemma == 'neposlední']) and (
                    adp := [c for c in node.children if c.lemma == 'v']
                ):
                    self.annotate_node('redundant_expression', node, adj[0], adp[0])
                    self.advance_application_id()

            # v kontextu věci
            case 'kontext':
                if (noun := [c for c in node.children if c.lemma == 'věc']) and (
                    adp := [c for c in node.children if c.lemma == 'v']
                ):
                    self.annotate_node('redundant_expression', node, noun[0], adp[0])
                    self.advance_application_id()

            # v rámci posuzování
            case 'posuzování':
                if adp := [
                    c for c in node.children if c.lemma == 'v' and [n for n in c.children if n.lemma == 'rámec']
                ]:
                    # little dirty, I'd love to know if it's possible to retreive the noun from the condition
                    # without it possibly being overwritten if there are multiple cs that match c.lemma == 'v'
                    noun = [n for n in adp[0].children if n.lemma == 'rámec']

                    self.annotate_node('redundant_expression', node, adp[0], noun[0])
                    self.advance_application_id()

            # za situace když
            case 'situace':
                if (adp := [c for c in node.children if c.lemma == 'za']) and (
                    conj := [
                        c
                        for c in node.root.descendants(add_self=True)[node.ord + 1 : node.ord + 3]
                        if c.lemma == 'když'
                    ]
                ):
                    self.annotate_node('redundant_expression', node, *adp, *conj)
                    self.advance_application_id()

            # e.g. lze konstatovat, je nutné konstatovat, soud musí konstatovat
            # there are many variations
            case 'konstatovat':
                clause = get_clause(node, without_punctuation=True, without_subordinates=True)

                # ... so instead, we take every sentence-initial structure with "konstatovat"
                # where the verb isn't modified much
                if (
                    (not [n for n in clause if n.udeprel in ('obj', 'iobj', 'obl', 'advmod')])
                    and [n for n in clause if n.udeprel == 'root']
                    # exclude performative uses ("konstatuji")
                    and node.feats['Person'] != '1'
                    # exclude narrative descriptions of performative use (e.g. "(soud) konstatoval")
                    and node.feats['Tense'] != 'Past'
                ):
                    self.annotate_node('redundant_expression', *clause)
                    self.advance_application_id()

            case 'ostatně':
                self.annotate_node('redundant_expression', node)
                self.advance_application_id()


class RuleTooLongExpressions(PhrasesRule):
    """Capture expressions that could be shortened.

    Inspiration: Šamánková & Kubíková (2022, p. 44), Šváb (2021, p. 118).
    """

    rule_id: ClassVar[str] = 'RuleTooLongExpressions'

    cz_human_readable_name: str = 'Dlouhé výrazy'
    en_human_readable_name: str = 'Long expressions'
    cz_doc: str = 'Srov. Šamánková & Kubíková (2022, s. 44), Šváb (2021, s. 118).'
    en_doc: str = 'Cf. Šamánková & Kubíková (2022, p. 44), Šváb (2021, p. 118).'
    cz_paricipants: dict[str, str] = {
        'v_důsledku_toho': 'Lépe „proto“',
        'v_případě_že': 'Lépe „pokud“',
        'týkající_se': 'Lépe „o (něčem)“ (namísto „týkající se (něčeho)“)',
        'za_účelem': 'Lépe „kvůli (něčemu)“ nebo vedlejší věta s „aby“ (namísto „za účelem (něčeho)“)',
        'jste_oprávněn': 'Lépe „můžete / máte právo“ (namísto „jste oprávněn“)',
        'dát_do_nájmu': 'Lépe „pronajmout“ (namísto „dát do nájmu“)',
        'prostřednictvím_kterého': 'Lépe „který umožňuje“ (namísto „prostřednictvím kterého“)',
        'jsou_uvedeny_v_příloze': 'Lépe „naleznete (někde)“ (namísto „jsou uvedeny (někde)“)',
        'za_podmínek_uvedených_ve_smlouvě': 'Lépe „podle (něčeho)“ (namísto „za podmínek uvedených (v něčem)“)',
        'v_rámci': 'Lépe „při (něčem)“ (namísto „v rámci (něčeho)“)',
        'uděluje_vyjadřuje_souhlas': 'Lépe „souhlasí“ (namísto „uděluje/vyjadřuje souhlas“)',
        'ze_strany_banky': 'Lépe 7. pád („někým“) nebo činný rod („někdo dělal něco“); namísto „ze strany někoho“',
        'předmětný_závazek': 'Lépe „tento (závazek)“ (namísto „předmětný (závazek)“)',
    }
    en_paricipants: dict[str, str] = {
        'v_důsledku_toho': 'Better as “proto”',
        'v_případě_že': 'Better as “pokud”',
        'týkající_se': 'Better as “o (něčem)” (instead of “týkající se (něčeho)”)',
        'za_účelem': 'Better as “kvůli (něčemu)” or a dependent clause with “aby” (instead of “za účelem (něčeho)”)',
        'jste_oprávněn': 'Better as “můžete / máte právo” (instead of “jste oprávněn”)',
        'dát_do_nájmu': 'Better as “pronajmout” (instead of “dát do nájmu”)',
        'prostřednictvím_kterého': 'Better as “který umožňuje” (instead of “prostřednictvím kterého”)',
        'jsou_uvedeny_v_příloze': 'Better as “naleznete (někde)” (instead of “jsou uvedeny (někde)”)',
        'za_podmínek_uvedených_ve_smlouvě': 'Better as “podle (něčeho)” (instead of “za podmínek uvedených (v něčem)”)',
        'v_rámci': 'Better as “při (něčem)” (instead of “v rámci (něčeho)”)',
        'uděluje_vyjadřuje_souhlas': 'Better as “souhlasí” (instead of “uděluje/vyjadřuje souhlas”)',
        'ze_strany_banky': 'Better as instrumental (“někým”) or in active mood (“někdo dělal něco”); instead of “ze strany někoho”',
        'předmětný_závazek': 'Better as “tento (závazek)” (instead of “předmětný (závazek)”)',
    }

    def process_node(self, node):
        if is_citation(node):
            return

        match node.lemma:
            # v důsledku toho
            case 'důsledek':
                if (
                    (adp := node.parent).lemma == 'v'
                    and adp.parent
                    and (pron := adp.parent).upos in ('PRON', 'DET')
                    and len(pron.children) == 1  # modified by adp only
                ):
                    self.annotate_node('v_důsledku_toho', node, adp, pron)

                    if not self.detect_only:
                        correction = Node(
                            root=pron.parent.ord,
                            form='proto',
                            lemma='proto',
                            upos='CCONJ',
                            xpos='J^-------------',
                            deprel='cc',
                        )
                        self.add_node(
                            correction, node.root, pron.descendants(add_self=True)[0].ord - 1, pron.parent.ord
                        )

                        self.annotate_action('remove', *pron.descendants(add_self=True))

                    self.advance_application_id()

            # v případě, že
            case 'že':
                if (
                    node.parent.parent
                    and (noun := node.parent.parent).lemma == 'případ'
                    and (adp := [c for c in noun.children if c.lemma == 'v'])
                ):
                    self.annotate_node('v_případě_že', node, noun, *adp)

                    if not self.detect_only:
                        correction = Node(
                            root=node.parent.ord,
                            form='pokud',
                            lemma='pokud',
                            upos='SCONJ',
                            xpos='J,-------------',
                            deprel='mark',
                        )
                        self.add_node(correction, node.root, node.ord - 1, node.parent.ord)

                        self.annotate_action('remove', node, noun, *adp)
                        for c in noun.children:
                            if f'{self.id()}:{self.process_id}' not in get_removing_rules(c):
                                self.annotate_action('rebind', c, value=noun.parent.ord)

                    self.advance_application_id()

            # týkající se
            case 'týkající':
                if expl := [c for c in node.children if c.deprel == 'expl:pv']:
                    self.annotate_node('týkající_se', node, *expl)

                    # if not self.detect_only:
                    #     raise NotImplementedError('1. do not modify syntax directly\n2. fix case morphology')

                    #     obl_arg = [n for n in node.children if n.deprel == 'obl:arg'][0]
                    #     correction = obl_arg.create_child(
                    #         form='o', lemma='o', upos='ADP', xpos='RR--6----------', deprel='case'
                    #     )
                    #     correction.shift_before_subtree(obl_arg)

                    #     self.annotate_action('remove', node, *expl)
                    #     self.annotate_action('add', correction)

                    self.advance_application_id()

            # za účelem
            case 'účel':
                if (adp := node.parent).lemma == 'za' and adp.parent.lemma != 'ochrana':
                    self.annotate_node('za_účelem', node, adp)

                    # if not self.detect_only:
                    #     raise NotImplementedError('1. do not modify syntax directly\n2. fix case morphology')
                    #     correction = adp.parent.create_child(
                    #         form='kvůli', lemma='kvůli', upos='ADP', xpos='RR--3----------', deprel='case'
                    #     )
                    #     correction.shift_after_subtree(adp)

                    #     self.annotate_action('remove', node, adp)
                    #     self.annotate_action('add', correction)

                    self.advance_application_id()

            # jste oprávněn
            case 'oprávněný':
                if aux := [c for c in node.children if c.upos == 'AUX' and not is_clause_root(c)]:
                    self.annotate_node('jste_oprávněn', node, *aux)
                    self.advance_application_id()

            # uděluje/vyjadřuje souhlas
            case 'souhlas':
                if (verb := node.parent).lemma in ('udělovat', 'vyjadřovat') and node.udeprel == 'obj':
                    self.annotate_node('uděluje_vyjadřuje_souhlas', node, verb)
                    self.advance_application_id()

            # dát do nájmu
            case 'nájem':
                if (
                    node.feats['Case'] == 'Gen'
                    and (adp := [c for c in node.children if c.lemma == 'do'])
                    and (verb := node.parent).lemma == 'dát'
                ):
                    self.annotate_node('dát_do_nájmu', node, verb, *adp)
                    self.advance_application_id()

            # prostřednictvím kterého
            case 'prostřednictví':
                if node.upos == 'ADP' and (det := node.parent).upos == 'DET':
                    self.annotate_node('prostřednictvím_kterého', node, det)
                    self.advance_application_id()

            # # jsou uvedeny v příloze
            # # often used in argumentation, where the recommended replacement isn't felicitous
            # case 'uvedený':
            #     if (aux := [c for c in node.children if c.upos == 'AUX']) and (
            #         nouns := [
            #             c for c in node.children if c.upos == 'NOUN' and c.feats['Case'] == 'Loc' and c.deprel == 'obl'
            #         ]
            #     ):
            #         for noun in nouns:
            #             if adp := [c for c in noun.children if c.lemma == 'v']:
            #                 self.annotate_node('jsou_uvedeny_v_příloze', node, *aux, noun, *adp)
            #                 self.advance_application_id()

            # za podmínek uvedených ve smlouvě
            case 'podmínka':
                if (
                    node.feats['Case'] == 'Gen'
                    and (adp_za := [c for c in node.children if c.lemma == 'za'])
                    and (amods := [c for c in node.children if c.lemma == 'uvedený'])
                ):
                    for amod in amods:
                        if nouns := [
                            c
                            for c in amod.children
                            if c.upos == 'NOUN' and c.feats['Case'] == 'Loc' and c.deprel == 'obl'
                        ]:
                            for noun in nouns:
                                if adp_v := [c for c in noun.children if c.lemma == 'v']:
                                    self.annotate_node(
                                        'za_podmínek_uvedených_ve_smlouvě', node, *adp_za, amod, noun, *adp_v
                                    )
                                    self.advance_application_id()

            # v rámci
            case 'rámec':
                if node.deprel == 'fixed' and (adp := node.parent).lemma == 'v':
                    self.annotate_node('v_rámci', node, adp)
                    self.advance_application_id()

            # mluvený projev
            case 'mluvený':
                if (noun := node.parent).lemma == 'projev':
                    self.annotate_node('mluvený_projev', node, noun)
                    self.advance_application_id()

            # ze strany banky
            case 'strana':
                if node.deprel == 'fixed' and (adp := node.parent).lemma == 'z' and (head := adp.parent):
                    self.annotate_node('ze_strany_banky', node, adp, head)
                    self.advance_application_id()

            # předmětný závazek
            case 'předmětný':
                if node.deprel == 'amod' and (noun := node.parent).upos == 'NOUN':
                    self.annotate_node('předmětný_závazek', node, noun)
                    self.advance_application_id()


class RuleAnaphoricReferences(PhrasesRule):
    """Capture vague anaphoric references.

    Inspiration: Šamánková & Kubíková (2022, p. 42).
    """

    rule_id: ClassVar[str] = 'RuleAnaphoricReferences'

    cz_human_readable_name: str = 'Odkazovací výrazy'
    en_human_readable_name: str = 'Anaphoric references'
    cz_doc: str = (
        'Čtenář si musí domyslet, na kterou informaci pisatel odkazuje, a hrozí tak, že sdělení pochopí špatně. '
        + 'Místo odkazování shrnujte. Srov. Šamánková & Kubíková (2022, s. 42).'
    )
    en_doc: str = (
        'The reader has to guess which information the author is referring to and might misunderstand the message. '
        + 'Summarise instead of referring. Cf. Šamánková & Kubíková (2022, p. 42).'
    )
    cz_paricipants: dict[str, str] = {'anaphoric_reference': 'Odkazovací výraz'}
    en_paricipants: dict[str, str] = {'anaphoric_reference': 'Anaphoric reference'}

    def process_node(self, node):
        if is_citation(node):
            return

        match node.lemma:
            # co se týče výše uvedeného
            # ze shora uvedeného důvodu
            # z právě uvedeného je zřejmé
            case 'uvedený' | 'popsaný' | 'vyjmenovaný':
                if adv := [c for c in node.children if c.lemma in ('vysoko', 'shora', 'právě')]:
                    self.annotate_node('anaphoric_reference', node, *adv)
                    self.advance_application_id()

            # s ohledem na tuto skutečnost
            case 'skutečnost':
                if (det := [c for c in node.children if c.udeprel == 'det' and c.feats['PronType'] == 'Dem']) and (
                    adp := [c for c in node.children if c.udeprel == 'case']
                ):
                    self.annotate_node(
                        'anaphoric_reference', node, *det, *adp, *[desc for a in adp for desc in a.descendants]
                    )
                    self.advance_application_id()

            # z logiky věci vyplývá
            case 'logika':
                if (
                    (noun := [c for c in node.children if c.lemma == 'věc'])
                    and (adp := [c for c in node.children if c.lemma == 'z'])
                    and (vrb := node.parent).lemma in ('vyplývat', 'vyplynout', 'plynout')
                ):
                    self.annotate_node(
                        'anaphoric_reference', node, *noun, *adp, *[desc for a in adp for desc in a.descendants], vrb
                    )
                    self.advance_application_id()


class RuleLiteraryStyle(PhrasesRule):
    """Capture expressions associated with literary style.

    Inspiration: Sgall & Panevová (2014, pp. 42, 66–69, 79–82).
    """

    rule_id: ClassVar[str] = 'RuleLiteraryStyle'

    cz_human_readable_name: str = 'Knižní styl'
    en_human_readable_name: str = 'Literary style'
    cz_doc: str = 'Srov. Sgall & Panevová (2014, s. 42, s. 66–69, s. 79–82).'
    en_doc: str = 'Cf. Sgall & Panevová (2014, p. 42, pp. 66–69, pp. 79–82).'
    cz_paricipants: dict[str, str] = {
        'být_vinnen_na_vině': 'Lépe „vinu má/mají“ (namísto „je vinnen / na vině“)',
        'genitive_object': 'Zvažte 3. nebo 4. pád',
        'gen_obj_head': 'Řídící člen',
        'short_adjective_variant': 'Lépe složený tvar (např. „šťastný“ namísto „šťasten“)',
        'jej_pronoun_form': 'Lépe zájmeno „ho/jeho”',
        'ne_pronoun_form': 'Lépe zájmeno „něj“',
        'jenž': 'Lépe zájmeno „který“',
        'conditional_conjunction': 'Lépe „když/pokud“',
        'causal_conjunction': 'Lépe „protože“',
    }
    en_paricipants: dict[str, str] = {
        'být_vinnen_na_vině': 'Better as „vinu má/mají“ (instead of “je vinnen / na vině”)',
        'genitive_object': 'Consider using accusative or dative',
        'gen_obj_head': 'Governing word',
        'short_adjective_variant': 'Better use the long form (e.g. “šťastný” instead of “šťasten”)',
        'jej_pronoun_form': 'Better use “ho/jeho”',
        'ne_pronoun_form': 'Better use “něj”',
        'jenž': 'Better use “který”',
        'conditional_conjunction': 'Better use “když/pokud”',
        'causal_conjunction': 'Better use “protože”',
    }

    def process_node(self, node: Node):
        # vinni jsou
        if (
            node.lemma == 'vinný'
            and node.feats['Variant'] == 'Short'
            and (auxiliaries := [c for c in node.children if c.upos == 'AUX'])
        ):
            self.annotate_node('být_vinnen_na_vině', node, *auxiliaries)
            self.advance_application_id()

        # na vině jsou
        elif (
            node.form.lower() == 'vině'
            and (adps := [c for c in node.children if c.lemma == 'na'])
            and (parent := node.parent)
            and parent.lemma == 'být'
        ):
            self.annotate_node('být_vinnen_na_vině', node, *adps, parent)
            self.advance_application_id()

        # genetive objects
        elif (
            node.deprel in ('obj', 'iobj', 'obl:arg')
            and node.feats['Case'] == 'Gen'
            and (parent := node.parent)
            and parent.lemma
            in (
                'užít',
                'uživší',
                'užívat',
                'užívající',
                'využít',
                'využivší',
                'využívat',
                'využívající',
                'přát',
                'přející',
                'žádat',
                'žádající',
            )
            # filter out prepositional genitives
            # and genitives depending on a two-form-declination word
            and not [c for c in node.children if c.deprel == 'case' or 'NumType' in c.feats]
            # deverbative parents only
            and 'VerbForm' in parent.feats
        ):
            self.annotate_node('genitive_object', node)
            self.annotate_node('gen_obj_head', parent)
            self.advance_application_id()

        # short adjective forms
        elif (
            node.upos == 'ADJ'
            and node.feats['Variant'] == 'Short'
            and 'VerbForm' not in node.feats  # rule out passive participles
            and node.lemma not in ('rád', 'bosý', 'povinný')
        ):
            self.annotate_node('short_adjective_variant', node)
            self.advance_application_id()

        # pronoun "jej"
        elif (
            node.form.lower() in ('jej', 'je')
            and node.upos == 'PRON'
            and (node.feats['Case'] == 'Gen' or 'Neut' in node.feats['Gender'].split(','))
        ):
            self.annotate_node('jej_pronoun_form', node)
            self.advance_application_id()

        # pronoun "ně"
        elif (
            node.form.lower() == 'ně'
            and node.upos == 'PRON'
            and node.feats['Number'] == 'Sing'
            and 'Neut' in node.feats['Gender'].split(',')
        ):
            self.annotate_node('ne_pronoun_form', node)
            self.advance_application_id()

        elif node.lemma == 'jenž' and node.feats['Case'] == 'Nom':
            self.annotate_node('jenž', node)
            self.advance_application_id()

        # some subordinate conjunctions
        elif node.lemma in ('jestliže', 'pakliže', 'li') and node.upos == 'SCONJ':
            self.annotate_node('conditional_conjunction', node)

            if not self.detect_only and node.lemma in ('jestliže', 'pakliže'):
                correction = Node(
                    root=node.parent.ord,
                    form='pokud',
                    lemma='pokud',
                    upos=node.upos,
                    xpos=node.xpos,
                    deprel=node.deprel,
                )
                self.add_node(correction, node.root, node.ord - 1, node.parent.ord)

                self.annotate_action('remove', node)

            self.advance_application_id()

        elif node.lemma in ('poněvadž', 'jelikož') and node.upos == 'SCONJ':
            self.annotate_node('causal_conjunction', node)

            if not self.detect_only:
                correction = Node(
                    root=node.parent.ord,
                    form='protože',
                    lemma='protože',
                    upos=node.upos,
                    xpos=node.xpos,
                    deprel=node.deprel,
                )
                self.add_node(correction, node.root, node.ord - 1, node.parent.ord)

                self.annotate_action('remove', node)

            self.advance_application_id()


class RulePassive(PhrasesRule):
    """Capture be-passives.

    Inspiration: Šamánková & Kubíková (2022, pp. 39-40), Šváb (2021, p. 27).

    Arguments:
        overt_agent_only (bool): only highlight passives with an overt agent.
        use_vallex (bool): use Vallex and DeriNet to lookup valency frames.
    """

    rule_id: ClassVar[str] = 'RulePassive'
    overt_agent_only: bool = True
    use_vallex: bool = False

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
        # nodes that are potentially overt passive agents
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

        vallex_lexemes = []
        if self.use_vallex:
            # look up the verb in VALLEX
            derinet = get_derinet()
            deri_parents = [lx.parent.lemma if lx.parent else None for lx in derinet.get_lexemes(participle.lemma)]
            vallex_lexemes = [l for dp in deri_parents if dp for l in vallex_get_lexeme(dp)]

        # if there's a VALLEX entry
        if self.use_vallex and len(vallex_lexemes) > 0:
            # the following is a compromise: formally, UD provide no way of distinguishing
            # "toalety_PAT nebyly opatřeny záchodovým prkýnkem_EFF"
            # from "poplatek_PAT byl zaplacen osobou_ACT" (cf. "zaplacen majetkem_EFF");
            # it's safer to greenlight the annotation only if all frames clearly indicate overt ACT,
            # but it creates false negatives.

            # dict[LU-ID, <given current ACT candidates, there's certainly an overt ACT>]
            clearly_overt_act: dict[str, bool] = dict()

            # if the frames of all LUs will suggest that there's too few slots for all the candidates,
            # the candidates likely contain an overt ACT

            for lexeme in vallex_lexemes:
                for lu in lexeme['lexical_units']:
                    # if the LU doesn't have a passive alternation, it can be skipped
                    # since UDPipe assures us that we're dealing with a passive alternation
                    if 'diat' in lu and not [diat for diat in lu['diat']['data'] if diat['type'] == 'passive']:
                        continue

                    forms = [
                        form.replace('adj-', '')  # let's not care about POS now
                        for frame_element in lu['frame']['elements']
                        for form in frame_element['forms']
                    ]
                    forms_cntr = Counter(forms)

                    clearly_overt_act[lu['id']] = (
                        len(act_candidates_ins) > forms_cntr['7'] or len(act_candidates_od_gen) > forms_cntr['od+2']
                    )

            # if none of the LUs disqualifies the candidates from being interpreted as overt ACTs
            # and at least one LU with a passive alternation has been found in VALLEX
            return all(clearly_overt_act.values()) and len(clearly_overt_act) > 0

        # if no VALLEX entry for the verb
        else:
            return bool(act_candidates_ins) or bool(act_candidates_od_gen)

    def process_node(self, node):
        if node.deprel == 'aux:pass':
            parent = node.parent

            if (not self.overt_agent_only) or self._overt_agent_decision(parent, node):
                self.annotate_node('aux', node)
                self.annotate_node('participle', parent)

                self.advance_application_id()
