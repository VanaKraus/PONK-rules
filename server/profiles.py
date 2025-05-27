from document_applicables.rules import Rule
from document_applicables.metrics import Metric
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
        RulePredSubjDistance(max_distance=5),
        RulePredObjDistance(max_distance=4),
        RuleMultiPartVerbs(max_distance=4),
        RuleLongSentences(max_length=22),
        RulePredAtClauseBeginning(max_order=4),
        RuleVerbalNouns(),
        RuleTooFewVerbs(min_verb_frac=0.169),
        RuleTooManyNegations(
            max_allowable_negations=2,
            max_negation_frac=0.215,  # measurable effect counter-intuitive
        ),
        RuleWeakMeaningWords(),
        RuleAbstractNouns(),
        RuleRelativisticExpressions(),
        RuleConfirmationExpressions(),
        RuleRedundantExpressions(),
        RuleTooLongExpressions(),
        RuleAnaphoricReferences(),
        RuleTooManyNominalConstructions(max_allowable_nouns=5, max_noun_frac=0.728),
        RuleCaseRepetition(max_repetition_count=3),
        RuleGPcoordovs(),
        RuleGPdeverbaddr(),
        RuleGPpatinstr(),
        RuleGPdeverbsubj(),
        RuleGPadjective(),
        RuleGPpatbenperson(),
        RuleGPwordorder(),
        RuleReflexivePassWithAnimSubj(),
        RuleLiteraryStyle(),
        # RuleDoubleAdpos(max_allowable_distance=0), # counter-intuitive measurable effect
        # RuleInfVerbDistance(max_distance=0), # counter-intuitive measurable effect
        # RuleAmbiguousRegards(), # unreliable
        # RuleDoubleComparison(), # unreliable + acceptability
        # RuleWrongValencyCase(), # unreliable + acceptability
        # RuleWrongVerbonominalCase(), # unreliable + acceptability
        # RuleIncompleteConjunction(), # acceptability
        # RuleFunctionWordRepetition(), # unreliable
    ]


def get_noninstitutional_metrics() -> list[Metric]:
    raise NotImplementedError()


def set_rules_verbose(rules: list[Rule]) -> list[Rule]:
    for rule in rules:
        rule.verbose_annotation = True
    return rules


profiles = {
    'default': (None, None),
    'noninstitutional': (get_noninstitutional_metrics(), get_noninstitutional_rules()),
    'minimal': (
        None,  # default metrics
        get_minimal_rules(),
    ),
    'minimal_verbose': (
        None,  # default metrics
        set_rules_verbose(get_minimal_rules()),
    ),
}
