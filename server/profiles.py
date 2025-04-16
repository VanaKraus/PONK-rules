from document_applicables.rules import Rule
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


def set_rules_verbose(rules: list[Rule]) -> list[Rule]:
    for rule in rules:
        rule.verbose_annotation = True
    return rules


profiles = {
    'default': (None, None),
    'minimal': (
        None,  # default metrics
        get_minimal_rules(),
    ),
    'minimal_verbose': (
        None,  # default metrics
        set_rules_verbose(get_minimal_rules()),
    ),
}
