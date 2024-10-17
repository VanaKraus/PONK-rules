from __future__ import annotations

from typing import Literal

from udapi.core.node import Node

from document_applicables.rules import Rule, Color


class PhrasesRule(Rule):
    foreground_color: Color = Color(5, 199, 147)
    rule_id: Literal['phrases'] = 'phrases'


class RuleWeakMeaningWords(PhrasesRule):
    """Capture semantically weak words.

    Inspiration: Šamánková & Kubíková (2022, pp. 37-38 and p. 39), Sgall & Panevová (2014, p. 86), Šváb (2023, p. 32).
    """

    rule_id: Literal['RuleWeakMeaningWords'] = 'RuleWeakMeaningWords'

    cz_human_readable_name: str = 'Vyprázdněná slova'
    en_human_readable_name: str = 'Weak-meaning words'
    cz_doc: str = (
        'Vyvarujte se vyprázdněných slov. Srov. Sgall & Panevová (2014, s. 86), '
        + 'Šamánková & Kubíková (2022, s. 37–38 a s. 39), Šváb (2023, s. 32).'
    )
    en_doc: str = (
        'Avoid weak-meaning words. Cf. Sgall & Panevová (2014, p. 86), '
        + 'Šamánková & Kubíková (2022, pp. 37–38 and p. 39), Šváb (2023, p. 32).'
    )
    cz_paricipants: dict[str, str] = {'weak_meaning_word': 'Vyprázdněné slovo'}
    en_paricipants: dict[str, str] = {'weak_meaning_word': 'Weak-meaning word'}

    _weak_meaning_words: list[str] = [
        'dopadat',
        'zaměřit',
        'poukázat',
        'poukazovat',
        'ovlivnit',
        'ovlivňovat',
        'provádět',
        'provést',
        'postup',
        'obdobně',
        'velmi',
        'uskutečnit',
        'uskutečňovat',
    ]

    def process_node(self, node):
        if node.lemma in self._weak_meaning_words:
            self.annotate_node('weak_meaning_word', node)
            self.advance_application_id()


class RuleAbstractNouns(PhrasesRule):
    """Capture semantically weak abstract nouns.

    Inspiration: Šamánková & Kubíková (2022, p. 41).
    """

    rule_id: Literal['RuleAbstractNouns'] = 'RuleAbstractNouns'

    cz_human_readable_name: str = 'Vyprázdněná abstraktní substantiva'
    en_human_readable_name: str = 'Weak-meaning abstract nouns'
    cz_doc: str = 'Vyvarujte se vyprázdněných podstatných jmen. Srov. Šamánková & Kubíková (2022, s. 41).'
    en_doc: str = 'Avoid weak-meaning abstract nouns. Cf. Šamánková & Kubíková (2022, p. 41).'
    cz_paricipants: dict[str, str] = {'abstract_noun': 'Vyprázdněné abstraktní substantivum'}
    en_paricipants: dict[str, str] = {'abstract_noun': 'Weak-meaning abstract noun'}

    _abstract_nouns: list[str] = [
        'základ',
        'situace',
        'úvaha',
        'charakter',
        'stupeň',
        'aspekt',
        'okolnosti',
        'událost',
        'snaha',
        'podmínky',
        'činnost',
    ]

    def process_node(self, node):
        if node.lemma in self._abstract_nouns:
            self.annotate_node('abstract_noun', node)
            self.advance_application_id()


class RuleRelativisticExpressions(PhrasesRule):
    """Capture relativistic expressions.

    Inspiration: Šamánková & Kubíková (2022, p. 42).
    """

    rule_id: Literal['RuleRelativisticExpressions'] = 'RuleRelativisticExpressions'

    cz_human_readable_name: str = 'Relativistické výrazy'
    en_human_readable_name: str = 'Relativistic expressions'
    cz_doc: str = 'Vyvarujte se relativizujících výrazů. Srov. Šamánková & Kubíková (2022, s. 42).'
    en_doc: str = 'Avoid relativistic expressions. Cf. Šamánková & Kubíková (2022, p. 42).'
    cz_paricipants: dict[str, str] = {'relativistic_expression': 'Relativizující výraz'}
    en_paricipants: dict[str, str] = {'relativistic_expression': 'Relativistic expression'}

    # lemmas; when space-separated, nodes next-to-each-other with corresponding lemmas are looked for
    _expressions: list[list[str]] = [
        expr.split(' ') for expr in ['poněkud', 'jevit', 'patrně', 'do jistý míra', 'snad', 'jaksi']
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
    """Capture confirmation expressions. They often violate the maxim of quantity \
        in needlesly confirming what the author is already expected to be 100% sure about.

    Inspiration: Šamánková & Kubíková (2022, p. 42).
    """

    rule_id: Literal['RuleConfirmationExpressions'] = 'RuleConfirmationExpressions'

    cz_human_readable_name: str = 'Utvrzující výrazy'
    en_human_readable_name: str = 'Confirmation expressions'
    cz_doc: str = 'Vyvarujte se zbytečných utvrzujících výrazů. Srov. Šamánková & Kubíková (2022, s. 42).'
    en_doc: str = 'Avoid redundant confirmation expressions. Cf. Šamánková & Kubíková (2022, p. 42).'
    cz_paricipants: dict[str, str] = {'confirmation_expression': 'Utvrzující výraz'}
    en_paricipants: dict[str, str] = {'confirmation_expression': 'Confirmation expression'}

    _expressions: list[str] = ['jednoznačně', 'jasně', 'nepochybně', 'naprosto', 'rozhodně']

    def process_node(self, node):
        if node.lemma in self._expressions:
            self.annotate_node('confirmation_expression', node)


class RuleRedundantExpressions(PhrasesRule):
    """Capture expressions that aren't needed to convey the message.

    Inspiration: Šamánková & Kubíková (2022, pp. 42-43).
    """

    rule_id: Literal['RuleRedundantExpressions'] = 'RuleRedundantExpressions'

    cz_human_readable_name: str = 'Slovní vata'
    en_human_readable_name: str = 'Redundant expressions'
    cz_doc: str = 'Srov. Šamánková & Kubíková (2022, s. 42–43).'
    en_doc: str = 'Cf. Šamánková & Kubíková (2022, pp. 42–43).'
    cz_paricipants: dict[str, str] = {'redundant_expression': 'Zbytečný výraz'}
    en_paricipants: dict[str, str] = {'redundant_expression': 'Redundant expression'}

    def process_node(self, node):
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
                    # without it possible being overwritten if there are multiple cs that match c.lemma == 'v'
                    noun = [n for n in adp[0].children if n.lemma == 'rámec']

                    self.annotate_node('redundant_expression', node, adp[0], noun[0])
                    self.advance_application_id()


class RuleTooLongExpressions(PhrasesRule):
    """Capture expressions that could be shortened.

    Inspiration: Šamánková & Kubíková (2022, p. 44), Šváb (2023, p. 118).
    """

    rule_id: Literal['RuleTooLongExpressions'] = 'RuleTooLongExpressions'

    cz_human_readable_name: str = 'Dlouhé výrazy'
    en_human_readable_name: str = 'Long expressions'
    cz_doc: str = 'Srov. Šamánková & Kubíková (2022, s. 44), Šváb (2023, s. 118).'
    en_doc: str = 'Cf. Šamánková & Kubíková (2022, p. 44), Šváb (2023, p. 118).'
    cz_paricipants: dict[str, str] = {
        'v_důsledku_toho': 'Lépe „proto“',
        'v_případě_že': 'Lépe „pokud“',
        'týkající_se': 'Lépe „o“',
        'za_účelem': 'Lépe „kvůli“',
        'jste_oprávněn': 'Lépe „můžete / máte právo“',
        'dát_do_nájmu': 'Lépe „pronajmout“',
        'prostřednictvím_kterého': 'Lépe „který umožňuje“',
        'jsou_uvedeny_v_příloze': 'Lépe „naleznete (v příloze)“',
        'za_podmínek_uvedených_ve_smlouvě': 'Lépe „podle (smlouvy)“',
    }
    en_paricipants: dict[str, str] = {
        'v_důsledku_toho': 'Better as “proto”',
        'v_případě_že': 'Better as “pokud”',
        'týkající_se': 'Better as “o”',
        'za_účelem': 'Better as “kvůli”',
        'jste_oprávněn': 'Better as “můžete / máte právo”',
        'dát_do_nájmu': 'Better as “pronajmout”',
        'prostřednictvím_kterého': 'Better as “který umožňuje”',
        'jsou_uvedeny_v_příloze': 'Better as “naleznete (v příloze)”',
        'za_podmínek_uvedených_ve_smlouvě': 'Better as “podle (smlouvy)”',
    }

    def process_node(self, node):
        match node.lemma:
            # v důsledku toho
            case 'důsledek':
                if (adp := node.parent).lemma == 'v' and adp.parent and (pron := adp.parent).upos in ('PRON', 'DET'):
                    self.annotate_node('v_důsledku_toho', node, adp, pron)
                    self.advance_application_id()

            # v případě, že
            case 'že':
                if (
                    node.parent.parent
                    and (noun := node.parent.parent).lemma == 'případ'
                    and (adp := [c for c in noun.children if c.lemma == 'v'])
                ):
                    self.annotate_node('v_případě_že', node, noun, *adp)
                    self.advance_application_id()
            # týkající se
            case 'týkající':
                if expl := [c for c in node.children if c.deprel == 'expl:pv']:
                    self.annotate_node('týkající_se', node, *expl)
                    self.advance_application_id()

            # za účelem
            case 'účel':
                if (adp := node.parent).lemma == 'za':
                    self.annotate_node('za_účelem', node, adp)
                    self.advance_application_id()

            # jste oprávněn
            case 'oprávněný':
                if aux := [c for c in node.children if c.upos == 'AUX']:
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

            # jsou uvedeny v příloze
            case 'uvedený':
                if (aux := [c for c in node.children if c.upos == 'AUX']) and (
                    nouns := [
                        c for c in node.children if c.upos == 'NOUN' and c.feats['Case'] == 'Loc' and c.deprel == 'obl'
                    ]
                ):
                    for noun in nouns:
                        if adp := [c for c in noun.children if c.lemma == 'v']:
                            self.annotate_node('jsou_uvedeny_v_příloze', node, *aux, noun, *adp)
                            self.advance_application_id()

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

    rule_id: Literal['RuleAnaphoricReferences'] = 'RuleAnaphoricReferences'

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
        match node.lemma:
            # co se týče výše uvedeného
            # ze shora uvedeného důvodu
            # z právě uvedeného je zřejmé
            case 'uvedený':
                if adv := [c for c in node.children if c.lemma in ('vysoko', 'shora', 'právě')]:
                    self.annotate_node('anaphoric_reference', node, *adv)
                    self.advance_application_id()

            # s ohledem na tuto skutečnost
            case 'skutečnost':
                if (det := [c for c in node.children if c.udeprel == 'det' and c.feats['PronType'] == 'Dem']) and (
                    adp := [c for c in node.children if c.udeprel == 'case']
                ):
                    self.annotate_node(
                        'anaphoric_reference', node, *det, *adp, *[desc for a in adp for desc in a.descendants()]
                    )
                    self.advance_application_id()

            # z logiky věci vyplývá
            case 'logika':
                if (noun := [c for c in node.children if c.lemma == 'věc']) and (
                    adp := [c for c in node.children if c.lemma == 'z']
                ):
                    self.annotate_node(
                        'anaphoric_reference', node, *noun, *adp, *[desc for a in adp for desc in a.descendants()]
                    )
                    self.advance_application_id()


class RuleLiteraryStyle(PhrasesRule):
    """Capture expressions associated with literary style.

    Inspiration: Sgall & Panevová (2014, pp. 42, 66–69, 79–82).
    """

    rule_id: Literal['RuleLiteraryStyle'] = 'RuleLiteraryStyle'

    cz_human_readable_name: str = 'Knižní styl'
    en_human_readable_name: str = 'Literary style'
    cz_doc: str = 'Srov. Sgall & Panevová (2014, s. 42, s. 66–69, s. 79–82).'
    en_doc: str = 'Cf. Sgall & Panevová (2014, p. 42, pp. 66–69, pp. 79–82).'
    cz_paricipants: dict[str, str] = {
        'být_vinnen_na_vině': 'Lépe „vinu má/mají“',
        'genitive_object': 'Zvažte 3. nebo 4. pád',
        'gen_obj_head': 'Řídící člen',
        'short_adjective_variant': 'Lépe složený tvar (např. „šťastný“ namísto „šťasten“)',
        'jej_je_pronoun_form': 'Lépe „ho/jeho”',
        'jej_je_pronoun_form': 'Lépe „něj“',
        'jenž': 'Lépe „který“',
        'conditional_conjunction': 'Lépe „když/pokud“',
        'causal_conjunction': 'Lépe „protože“',
    }
    en_paricipants: dict[str, str] = {
        'být_vinnen_na_vině': 'Better as „vinu má/mají“',
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
            and 'Variant' in node.feats
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
            and 'Case' in node.feats
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
            and 'Variant' in node.feats
            and node.feats['Variant'] == 'Short'
            and 'VerbForm' not in node.feats  # rule out passive participles
            and node.lemma not in ('rád', 'bosý')
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

        elif node.lemma == 'jenž':
            self.annotate_node('jenž', node)
            self.advance_application_id()

        # some subordinate conjunctions
        elif node.lemma in ('jestliže', 'pakliže', 'li') and node.upos == 'SCONJ':
            self.annotate_node('conditional_conjunction', node)
            self.advance_application_id()

        elif node.lemma in ('poněvadž', 'jelikož') and node.upos == 'SCONJ':
            self.annotate_node('causal_conjunction', node)
            self.advance_application_id()
