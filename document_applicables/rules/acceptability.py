from __future__ import annotations

from typing import Literal

from udapi.core.node import Node

from document_applicables.rules import Rule, util, Color, derinet_lexicon


class AcceptabilityRule(Rule):
    foreground_color: Color = Color(255, 15, 50)
    rule_id: Literal['acceptability'] = 'acceptability'


class RuleDoubleComparison(AcceptabilityRule):
    """Capture constructions with a comparison auxiliary modifying a head with a non-positive degree of comparison.

    Inspiration: Sgall & Panevová (2014, p. 67).
    """

    rule_id: Literal['RuleDoubleComparison'] = 'RuleDoubleComparison'
    cz_human_readable_name: str = 'Dvojí stupňování'
    en_human_readable_name: str = 'Double comparison'
    cz_doc: str = (
        'Konstrukce typu „více světlejší“ jsou odchylka od normy. Vhodná alternativa by byla „více světlý“. '
        + 'Srov. Sgall & Panevová (2014, s. 67).'
    )
    en_doc: str = (
        'Constructions such as “více světlejší” deviate from the norm. A good alternative would be “více světlý”. '
        + 'Cf. Sgall & Panevová (2014, p. 67).'
    )
    # TODO: is there a conventional terminology?
    cz_paricipants: dict[str, str] = {'head': 'Nadbytečný 2./3. stupeň', 'modifier': 'Pomocný výraz'}
    en_paricipants: dict[str, str] = {'head': 'Redundant comparative/superlative', 'modifier': 'Auxiliary'}

    def process_node(self, node: Node):
        if (
            node.lemma in ('více', 'méně', 'míň')
            and 'Degree' in node.feats
            and node.feats['Degree'] != 'Pos'
            and (parent := node.parent)
            and node.udeprel == 'advmod'
            and 'Degree' in parent.feats
            and parent.feats['Degree'] == node.feats['Degree']
        ):
            self.annotate_node('head', parent)
            self.annotate_node('modifier', node)
            self.advance_application_id()


class RuleWrongValencyCase(AcceptabilityRule):
    """Capture wrong case usage with certain valency dependencies.

    Inspiration: Sgall & Panevová (2014, p. 85).
    """

    rule_id: Literal['RuleWrongValencyCase'] = 'RuleWrongValencyCase'
    cz_human_readable_name: str = 'Vazba se špatným pádem'
    en_human_readable_name: str = 'Wrong case usage'
    cz_doc: str = 'Srov. Sgall & Panevová (2014, s. 85).'
    en_doc: str = 'Cf. Sgall & Panevová (2014, p. 85).'
    cz_paricipants: dict[str, str] = {
        'accusative': 'Akuzativ',
        'del_preposition': 'Nadbytečná předložka',
        'preposition': 'Předložka',
        'req_accusative': 'Lépe 4. pád',
        'req_dative': 'Lépe 3. pád',
        'req_genitive': 'Lépe 2. pád',
        'req_na': 'Chybí předložka „na“',
        'req_o_locative': 'Chybí předložka „o” s 6. pádem',
        'verb': 'Řídící sloveso',
    }
    en_paricipants: dict[str, str] = {
        'accusative': 'Accusative',
        'del_preposition': 'Redundant preposition',
        'preposition': 'Preposition',
        'req_accusative': 'Better with accusative',
        'req_dative': 'Better with dative',
        'req_genitive': 'Better with genitive',
        'req_na': 'Missing preposition „na“',
        'req_o_locative': 'Missing preposition „o“ with locative',
        'verb': 'Governing verb',
    }

    def process_node(self, node: Node):
        # pokoušeli se zabránit takové důsledky
        if node.lemma in ('zabránit', 'zabraňovat') and (
            accs := [a for a in node.children if a.udeprel == 'obj' and 'Case' in a.feats and a.feats['Case'] == 'Acc']
        ):
            for acc in accs:
                if not bool([c for c in acc.children if c.udeprel == 'case']):
                    self.annotate_node('verb', node)
                    self.annotate_node('req_dative', acc)
                    self.advance_application_id()

        # pokoušeli se zamezit takovým důsledkům
        elif node.lemma in ('zamezit', 'zamezovat') and (
            dats := [d for d in node.children if d.udeprel == 'obl' and 'Case' in d.feats and d.feats['Case'] == 'Dat']
        ):
            for dat in dats:
                if not bool([c for c in dat.children if c.udeprel == 'case']):
                    self.annotate_node('verb', node)
                    self.annotate_node('req_accusative', dat)
                    self.advance_application_id()

        # nemusíte zodpovědět na tyto otázky
        elif node.lemma in ('zodpovědět', 'zodpovídat') and (
            accs := [a for a in node.children if a.udeprel == 'obl' and 'Case' in a.feats and a.feats['Case'] == 'Acc']
        ):
            for acc in accs:
                if (cases := [c for c in acc.children if c.udeprel == 'case']) and cases[0].lemma == 'na':
                    self.annotate_node('verb', node)
                    self.annotate_node('accusative', acc)
                    self.annotate_node('del_preposition', cases[0])
                    self.advance_application_id()

        # nemusíte odpovědět tyto otázky
        elif node.lemma in ('odpovědět', 'odpovídat') and (
            accs := [a for a in node.children if a.udeprel == 'obj' and 'Case' in a.feats and a.feats['Case'] == 'Acc']
        ):
            for acc in accs:
                cases = [c for c in acc.children if c.udeprel == 'case']

                if not bool(cases):
                    self.annotate_node('verb', node)
                    self.annotate_node('req_na', acc)
                    self.advance_application_id()

                elif cases[0].lemma != 'na':
                    self.annotate_node('verb', node)
                    self.annotate_node('accusative', acc)
                    self.annotate_node('req_na', cases[0])
                    self.advance_application_id()

        # hovořit/mluvit něco
        elif node.lemma in ('hovořit', 'mluvit') and (
            accs := [a for a in node.children if a.udeprel == 'obj' and 'Case' in a.feats and a.feats['Case'] == 'Acc']
        ):
            for acc in accs:
                if not bool([c for c in acc.children if c.udeprel == 'case']):
                    self.annotate_node('verb', node)
                    self.annotate_node('req_o_locative', acc)
                    self.advance_application_id()

        # mimo + !ACC
        elif (
            node.lemma == 'mimo'
            and node.udeprel == 'case'
            and 'Case' in (noun := node.parent).feats
            and noun.feats['Case'] != 'Acc'
        ):
            self.annotate_node('preposition', node)
            self.annotate_node('req_accusative', noun)
            self.advance_application_id()

        # kromě + !GEN
        # not sure if UDPipe is able to parse kromě with any other case than GEN
        elif (
            node.lemma == 'kromě'
            and node.udeprel == 'case'
            and 'Case' in (noun := node.parent).feats
            and noun.feats['Case'] != 'Gen'
        ):
            self.annotate_node('preposition', node)
            self.annotate_node('req_genitive', noun)
            self.advance_application_id()


class RuleWrongVerbonominalCase(AcceptabilityRule):
    """Capture wrong case usage in verbonominal predicates.

    Inspiration: Sgall & Panevová (2014, p. 42).
    """

    rule_id: Literal['RuleWrongVerbonominalCase'] = 'RuleWrongVerbonominalCase'
    cz_human_readable_name: str = 'Špatný pád v přísudku'
    en_human_readable_name: str = 'Wrong case in the predicate'
    cz_doc: str = 'Srov. Sgall & Panevová (2014, s. 42).'
    en_doc: str = 'Cf. Sgall & Panevová (2014, p. 42).'
    cz_paricipants: dict[str, str] = {'copula': 'Spona', 'req_nominative': 'Lépe 1. pád'}
    en_paricipants: dict[str, str] = {'copula': 'Copula', 'req_nominative': 'Better with nominative'}

    def process_node(self, node: Node):
        if (
            node.lemma in ('pravda', 'škoda')
            and (cop := [c for c in node.children if c.deprel == 'cop'])
            and node.feats['Case'] == 'Ins'
        ):
            self.annotate_node('copula', *cop)
            self.annotate_node('req_nominative', node)
            self.advance_application_id()


class RuleIncompleteConjunction(AcceptabilityRule):
    """Capture incomplete multi-token conjunctions.

    Inspiration: Sgall & Panevová (2014, p. 85).
    """

    rule_id: Literal['RuleIncompleteConjunction'] = 'RuleIncompleteConjunction'
    # TODO: English terminology
    cz_human_readable_name: str = 'Neúplná složená spojka'
    en_human_readable_name: str = 'Incomplete analytic conjunction'
    cz_doc: str = 'Vazba se spojkou „jednak“ vyžaduje i druhé „jednak“. Srov. Sgall & Panevová (2014, s. 85).'
    en_doc: str = (
        'The conjunction “jednak” requires its second part (“jednak … jednak”). Cf. Sgall & Panevová (2014, p. 85).'
    )
    cz_paricipants: dict[str, str] = {'conj_part': 'Část spojky'}
    en_paricipants: dict[str, str] = {'conj_part': 'Part of the conjunction'}

    def process_node(self, node: Node):
        if node.lemma == 'jednak':
            conjunctions = [c for c in node.root.descendants() if c != node and c.lemma == 'jednak']

            if len(conjunctions) == 0:
                self.annotate_node('conj_part', node)
                self.advance_application_id()


class RulePossessiveGenitive(AcceptabilityRule):
    """Capture unnecessary or badly placed possessive genitives.

    Inspiration: Sgall & Panevová (2014, p. 91).
    """

    rule_id: Literal['RulePossessiveGenitive'] = 'RulePossessiveGenitive'
    cz_human_readable_name: str = 'Nevhodný genitiv přivlastňovací'
    en_human_readable_name: str = 'Inappropriate possessive genitive'
    cz_doc: str = (
        'Genitiv přivlastňovací se vyskytuje na nevhodné pozici nebo by šel nahradit. Srov. Sgall & Panevová (2014, s. 91).'
    )
    en_doc: str = (
        'The possessive genitive is positioned inappropriately or could be replaced. Cf. Sgall & Panevová (2014, p. 91).'
    )
    cz_paricipants: dict[str, str] = {
        'possesive_adj_exists': 'Tento genitiv je možné nahradit přídavným jménem přivlastňovacím',
        'req_left_of_parent': 'Lépe nalevo od řídícího členu',
    }
    en_paricipants: dict[str, str] = {
        'possesive_adj_exists': 'You can use a possessive adjective instead',
        'req_left_of_parent': 'Better left of the parent',
    }

    def process_node(self, node: Node):
        if (
            util.is_named_entity(node)
            and node.udeprel == 'nmod'
            and node.feats['Case'] == 'Gen'
            and len(node.children) == 0
        ):
            dnet_lexemes = derinet_lexicon.get_lexemes(node.lemma)
            if len(dnet_lexemes) > 0:
                dnet_lexeme = dnet_lexemes[0]
                possesives = [c for c in dnet_lexeme.children if 'Poss' in c.feats and c.feats['Poss'] == 'Yes']

                if possesives:
                    self.annotate_node('possesive_adj_exists', node)
                    self.advance_application_id()
                # TODO: what about gender ambiguity?
                elif node.parent.ord < node.ord and node.feats['Gender'] != 'Fem':
                    self.annotate_node('req_left_of_parent', node)
                    self.advance_application_id()
