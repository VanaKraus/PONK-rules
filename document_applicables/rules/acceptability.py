from __future__ import annotations

from typing import Literal

from udapi.core.node import Node

from document_applicables.rules import (
    Rule,
    util,
    Color,
    # derinet_lexicon
)


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
        'Konstrukce typu „víc pečlivější“ jsou odchylka od normy. Vhodná alternativa je „víc pečlivý“. '
        + 'Srov. Sgall & Panevová (2014, s. 67).'
    )
    en_doc: str = (
        'Constructions such as „víc pečlivější“ deviate from the norm. A good alternative would be „víc pečlivý“. '
        + 'Cf. Sgall & Panevová (2014, p. 67).'
    )
    cz_paricipants = {'head': 'Základ', 'modifier': 'Pomocný výraz'}
    en_paricipants = {'head': 'Base meaning', 'modifier': 'Auxiliary'}

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

    def process_node(self, node: Node):
        # pokoušeli se zabránit takové důsledky
        if node.lemma in ('zabránit', 'zabraňovat') and (
            accs := [a for a in node.children if a.udeprel == 'obj' and 'Case' in a.feats and a.feats['Case'] == 'Acc']
        ):
            for acc in accs:
                if not bool([c for c in acc.children if c.udeprel == 'case']):
                    self.annotate_node('verb', node)
                    self.annotate_node('accusative', acc)
                    self.advance_application_id()

        # pokoušeli se zamezit takovým důsledkům
        elif node.lemma in ('zamezit', 'zamezovat') and (
            dats := [d for d in node.children if d.udeprel == 'obl' and 'Case' in d.feats and d.feats['Case'] == 'Dat']
        ):
            for dat in dats:
                if not bool([c for c in dat.children if c.udeprel == 'case']):
                    self.annotate_node('verb', node)
                    self.annotate_node('dative', dat)
                    self.advance_application_id()

        # nemusíte zodpovědět na tyto otázky
        elif node.lemma in ('zodpovědět', 'zodpovídat') and (
            accs := [a for a in node.children if a.udeprel == 'obl' and 'Case' in a.feats and a.feats['Case'] == 'Acc']
        ):
            for acc in accs:
                if (cases := [c for c in acc.children if c.udeprel == 'case']) and cases[0].lemma == 'na':
                    self.annotate_node('verb', node)
                    self.annotate_node('accusative', acc)
                    self.annotate_node('preposition', cases[0])
                    self.advance_application_id()

        # nemusíte odpovědět tyto otázky
        elif node.lemma in ('odpovědět', 'odpovídat') and (
            accs := [a for a in node.children if a.udeprel == 'obj' and 'Case' in a.feats and a.feats['Case'] == 'Acc']
        ):
            for acc in accs:
                cases = [c for c in acc.children if c.udeprel == 'case']

                if not bool(cases):
                    self.annotate_node('verb', node)
                    self.annotate_node('accusative', acc)
                    self.advance_application_id()

                elif cases[0].lemma != 'na':
                    self.annotate_node('verb', node)
                    self.annotate_node('accusative', acc)
                    self.annotate_node('preposition', cases[0])
                    self.advance_application_id()

        # hovořit/mluvit něco
        elif node.lemma in ('hovořit', 'mluvit') and (
            accs := [a for a in node.children if a.udeprel == 'obj' and 'Case' in a.feats and a.feats['Case'] == 'Acc']
        ):
            for acc in accs:
                if not bool([c for c in acc.children if c.udeprel == 'case']):
                    self.annotate_node('verb', node)
                    self.annotate_node('accusative', acc)
                    self.advance_application_id()

        # mimo + !ACC
        elif (
            node.lemma == 'mimo'
            and node.udeprel == 'case'
            and 'Case' in (noun := node.parent).feats
            and noun.feats['Case'] != 'Acc'
        ):
            self.annotate_node('preposition', node)
            self.annotate_node('not_accusative', noun)
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
            self.annotate_node('not_genitive', noun)
            self.advance_application_id()


class RuleWrongVerbonominalCase(AcceptabilityRule):
    """Capture wrong case usage in verbonominal predicates.

    Inspiration: Sgall & Panevová (2014, p. 42).
    """

    rule_id: Literal['RuleWrongVerbonominalCase'] = 'RuleWrongVerbonominalCase'

    def process_node(self, node: Node):
        if (
            node.lemma in ('pravda', 'škoda')
            and (cop := [c for c in node.children if c.deprel == 'cop'])
            and node.feats['Case'] == 'Ins'
        ):
            self.annotate_node('copula', *cop)
            self.annotate_node('instrumental', node)
            self.advance_application_id()


class RuleIncompleteConjunction(AcceptabilityRule):
    """Capture incomplete multi-token conjunctions.

    Inspiration: Sgall & Panevová (2014, p. 85).
    """

    rule_id: Literal['RuleIncompleteConjunction'] = 'RuleIncompleteConjunction'

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

    def process_node(self, node: Node):
        if (
            util.is_named_entity(node)
            and node.udeprel == 'nmod'
            and node.feats['Case'] == 'Gen'
            and len(node.children) == 0
        ):
            ###et_lexemes = derinet_lexicon.get_lexemes(node.lemma)
            dnet_lexemes = []
            if len(dnet_lexemes) > 0:
                dnet_lexeme = dnet_lexemes[0]
                possesives = [c for c in dnet_lexeme.children if 'Poss' in c.feats and c.feats['Poss'] == 'Yes']

                if possesives:
                    self.annotate_node('possesive_adj_exists', node)
                    self.advance_application_id()
                # TODO: what about gender ambiguity?
                elif node.parent.ord < node.ord and node.feats['Gender'] != 'Fem':
                    self.annotate_node('right_of_parent', node)
                    self.advance_application_id()
