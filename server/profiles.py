from document_applicables.rules import Rule, PostProcessRule
from document_applicables.metrics import Metric, MetricActivity, MetricARI, MetricVerbDistance, MetricMovingAverageTTR
from document_applicables.rules.acceptability import (
    RuleDoubleComparison,
    RuleWrongValencyCase,
    RuleWrongVerbonominalCase,
    RuleIncompleteConjunction,
)
from document_applicables.rules.ambiguity import (
    RuleDoubleAdpos,
    RuleAmbiguousRegards,
    RuleGPcoordovs,
    RuleGPdeverbaddr,
    RuleGPpatinstr,
    RuleGPdeverbsubj,
    RuleGPadjective,
    RuleGPpatbenperson,
    RuleGPwordorder,
    RuleReflexivePassWithAnimSubj,
)
from document_applicables.rules.clusters import (
    RuleTooFewVerbs,
    RuleTooManyNegations,
    RuleTooManyNominalConstructions,
    RuleCaseRepetition,
    RuleFunctionWordRepetition,
)
from document_applicables.rules.phrases import (
    RuleWeakMeaningWords,
    RuleAbstractNouns,
    RuleRelativisticExpressions,
    RuleConfirmationExpressions,
    RuleRedundantExpressions,
    RuleTooLongExpressions,
    RuleAnaphoricReferences,
    RuleLiteraryStyle,
)
from document_applicables.rules.structural import (
    RulePassive,
    RulePredSubjDistance,
    RulePredObjDistance,
    RuleInfVerbDistance,
    RuleMultiPartVerbs,
    RuleLongSentences,
    RulePredAtClauseBeginning,
    RuleVerbalNouns,
)


def get_minimal_rules() -> list[Rule]:
    return [
        RuleDoubleAdpos(max_allowable_distance=0),
        RulePassive(),
        RulePredSubjDistance(max_distance=0),
        RulePredObjDistance(max_distance=0),
        RuleInfVerbDistance(max_distance=0),
        RuleMultiPartVerbs(max_distance=0),
        RuleLongSentences(max_length=0),
        RulePredAtClauseBeginning(max_order=0),
        RuleVerbalNouns(),
        RuleTooFewVerbs(min_verb_frac=1),
        RuleTooManyNegations(max_allowable_negations=0, max_negation_frac=0),
        RuleWeakMeaningWords(),
        RuleAbstractNouns(),
        RuleRelativisticExpressions(),
        RuleConfirmationExpressions(),
        RuleRedundantExpressions(),
        RuleTooLongExpressions(),
        RuleAnaphoricReferences(),
        RuleAmbiguousRegards(),
        RuleTooManyNominalConstructions(max_allowable_nouns=0, max_noun_frac=0),
        # leaving max_repetition_frac out as any nouns (followed by other tokens)
        # would get flagged otherwise, distorting the measurement
        RuleCaseRepetition(max_repetition_count=0),
        RuleDoubleComparison(),
        RuleWrongValencyCase(),
        RuleWrongVerbonominalCase(),
        RuleIncompleteConjunction(),
        RuleGPcoordovs(),
        RuleGPdeverbaddr(),
        RuleGPpatinstr(),
        RuleGPdeverbsubj(),
        RuleGPadjective(),
        RuleGPpatbenperson(),
        RuleGPwordorder(),
        RuleReflexivePassWithAnimSubj(),
        RuleFunctionWordRepetition(),
        RuleLiteraryStyle(),
    ]


def get_noninstitutional_rules() -> list[Rule]:
    return [
        RulePassive(),
        RulePredSubjDistance(
            max_distance=5,  # effect size < 0.06
        ),
        RulePredObjDistance(max_distance=4),
        RuleMultiPartVerbs(max_distance=4),
        RuleLongSentences(max_length=22),
        RulePredAtClauseBeginning(
            max_order=4,  # effect size < 0.06
        ),
        # RuleTooFewVerbs(min_verb_frac=0.169), # value counter-intuitive; replaced below
        RuleTooFewVerbs(min_verb_frac=0.06),  # default value
        RuleTooManyNegations(
            max_allowable_negations=2,
            max_negation_frac=0.168,  # measurable effect counter-intuitive
        ),
        RuleWeakMeaningWords(),
        RuleAbstractNouns(),  # effect size < 0.06
        RuleRelativisticExpressions(),
        RuleConfirmationExpressions(),  # effect size < 0.06
        RuleRedundantExpressions(),
        RuleTooLongExpressions(),
        RuleAnaphoricReferences(),  # effect size < 0.06
        RuleTooManyNominalConstructions(max_allowable_nouns=5, max_noun_frac=0.728),
        RuleCaseRepetition(max_repetition_count=3),
        RuleLiteraryStyle(),
        # RuleVerbalNouns(), # hard to interpret
        # RuleGPpatinstr(), # questionable reliability
        # RuleGPcoordovs(), # effect size < 0.06
        # RuleGPdeverbaddr(), # no good/bad interval border difference
        # RuleGPdeverbsubj(), # no good/bad interval border difference
        # RuleGPadjective(), # effect size < 0.06
        # RuleGPpatbenperson(), # effect size < 0.06
        # RuleGPwordorder(), # effect size < 0.06
        # RuleDoubleAdpos(max_allowable_distance=0), # counter-intuitive measurable effect
        # RuleInfVerbDistance(max_distance=0), # counter-intuitive measurable effect # effect size < 0.06
        # RuleAmbiguousRegards(), # unreliable
        # RuleDoubleComparison(), # unreliable + acceptability
        # RuleWrongValencyCase(), # unreliable + acceptability
        # RuleWrongVerbonominalCase(), # unreliable + acceptability
        # RuleIncompleteConjunction(), # acceptability
        # RuleFunctionWordRepetition(), # unreliable
        # RuleReflexivePassWithAnimSubj(),  # effect size < 0.06
    ]


def get_noninstitutional_metrics() -> list[Metric]:
    return [
        MetricActivity(),
        MetricARI(),
        MetricVerbDistance(),
        MetricMovingAverageTTR(),
    ]


def set_rules_verbose(rules: list[Rule]) -> list[Rule]:
    for rule in rules:
        rule.verbose_annotation = True
    return rules


def set_rules_corrective(rules: list[Rule]) -> list[Rule]:
    for rule in rules:
        if isinstance(rule, PostProcessRule):
            rules.remove(rule)
        elif isinstance(rule, (RuleTooLongExpressions, RuleLiteraryStyle)):
            rule.detect_only = False

    rules += [PostProcessRule()]

    return rules


profiles = {
    'default': (None, None),
    'default_corrective': (
        None,
        set_rules_corrective([rule() for rule in Rule.get_final_children()]),
    ),
    'noninstitutional': (
        get_noninstitutional_metrics(),
        get_noninstitutional_rules(),
    ),
    'noninstitutional_corrective': (
        get_noninstitutional_metrics(),
        set_rules_corrective(get_noninstitutional_rules()),
    ),
    'minimal': (
        None,  # default metrics
        get_minimal_rules(),
    ),
    'minimal_verbose': (
        None,  # default metrics
        set_rules_verbose(get_minimal_rules()),
    ),
}
