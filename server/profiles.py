import math

from document_applicables.rules import Rule
from document_applicables.rules.helpers import PostProcessRule
from document_applicables.metrics import Metric, MetricActivity, MetricARI, MetricVerbDistance, MetricMovingAverageTTR
from document_applicables.rules.helpers import CitDetectRule, HelperCleanupRule
from document_applicables.rules.acceptability import (
    RuleDoubleComparison,
    RuleWrongValencyCase,
    RuleWrongVerbonominalCase,
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
    RuleIncompleteConstruction,
)
from document_applicables.rules.fluency_orientation import (
    RuleTooFewVerbs,
    RuleTooManyNegations,
    RuleTooManyNominalConstructions,
    RuleCaseRepetition,
    RuleFunctionWordRepetition,
    RuleVerbalNouns,
    RuleLongSentences,
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
    RulePassive,
)
from document_applicables.rules.sentence_position import (
    RulePredSubjDistance,
    RulePredObjDistance,
    RuleInfVerbDistance,
    RuleMultiPartVerbs,
    RulePredTooFarInClause,
)


def get_minimal_rules() -> list[Rule]:
    return sorted(
        [
            RuleDoubleAdpos(max_allowable_distance=0),
            RulePassive(use_vallex=True),
            RulePredSubjDistance(max_distance=0),
            RulePredObjDistance(max_distance=0),
            RuleInfVerbDistance(max_distance=0),
            RuleMultiPartVerbs(max_distance=0),
            RuleLongSentences(max_length=0),
            RulePredTooFarInClause(max_order=0),
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
            RuleTooManyNominalConstructions(max_allowable_nouns=0, max_noun_frac=0, max_dismissable_span_length=0),
            # leaving max_repetition_frac out as any nouns (followed by other tokens)
            # would get flagged otherwise, distorting the measurement
            RuleCaseRepetition(max_repetition_count=0),
            RuleDoubleComparison(),
            RuleWrongValencyCase(),
            RuleWrongVerbonominalCase(),
            RuleIncompleteConstruction(),
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
        ],
        key=lambda x: x.rule_id,
    )


def get_noninstitutional_rules() -> list[Rule]:
    return [
        # --- fluency ----
        # RuleTooFewVerbs(min_verb_frac=0.169), # value counter-intuitive; replaced below
        # RuleTooFewVerbs(min_verb_frac=0.06),  # default value
        RuleTooFewVerbs(min_verb_frac=0.1),  # TODO: temporary adjustment to new measurement criteria
        RuleTooManyNominalConstructions(
            max_allowable_nouns=5,
            max_noun_frac=0.45,  # wouldn't catch anything with 0.728
            max_dismissable_span_length=15,
        ),
        RuleCaseRepetition(max_repetition_count=4, max_repetition_frac=0.65, include_adjectives=False),
        RuleTooManyNegations(
            max_allowable_negations=2,
            max_negation_frac=0.25,  # TODO: temporary adjustment to new measurement criteria
        ),
        RuleLongSentences(max_length=22, without_punctuation=True),
        # --- phrases and constructions ---
        RuleAbstractNouns(),
        RuleWeakMeaningWords(),
        RuleRedundantExpressions(),
        RuleTooLongExpressions(),
        RuleRelativisticExpressions(),
        RuleConfirmationExpressions(),
        RuleAnaphoricReferences(),
        RuleLiteraryStyle(),
        # RulePassive(use_vallex=True),
        RulePassive(use_vallex=False),
        # --- position in a sentence ---
        RulePredSubjDistance(
            max_distance=6,  # default value
        ),
        RulePredObjDistance(
            max_distance=6,  # default value
        ),
        RuleMultiPartVerbs(
            max_distance=5,  # default value
        ),
        RulePredTooFarInClause(
            # max_order=5,  # default value
            max_order=9,  # TODO: temporary adjustment
        ),
        RuleInfVerbDistance(max_distance=5),
        # --- ambiguity ---
        RuleDoubleAdpos(),  # counter-intuitive measurable effect
        RuleIncompleteConstruction(),
        # RuleVerbalNouns(), # hard to interpret
        # RuleGPpatinstr(), # questionable reliability
        # RuleGPcoordovs(), # effect size < 0.06
        # RuleGPdeverbaddr(), # no good/bad interval border difference
        # RuleGPdeverbsubj(), # no good/bad interval border difference
        # RuleGPadjective(), # effect size < 0.06
        # RuleGPpatbenperson(), # effect size < 0.06
        # RuleGPwordorder(), # effect size < 0.06
        # RuleAmbiguousRegards(), # unreliable
        # RuleDoubleComparison(), # unreliable + acceptability
        # RuleWrongValencyCase(), # unreliable + acceptability
        # RuleWrongVerbonominalCase(), # unreliable + acceptability
        # RuleFunctionWordRepetition(), # unreliable
        # RuleReflexivePassWithAnimSubj(),  # effect size < 0.06
    ]


def get_noninstitutional_metrics() -> list[Metric]:
    return [
        MetricARI(),
        MetricVerbDistance(),
        MetricActivity(),
        MetricMovingAverageTTR(
            cz_human_readable_name='Slovní bohatství',
            en_human_readable_name='Lexical diversity',
        ),
    ]


def set_rules_verbose(rules: list[Rule]) -> list[Rule]:
    for rule in rules:
        rule.verbose_annotation = True
    return rules


def set_rules_corrective(rules: list[Rule]) -> list[Rule]:
    for rule in rules:
        if isinstance(rule, PostProcessRule):
            rules.remove(rule)
        elif isinstance(rule, (RuleTooLongExpressions, RuleLiteraryStyle, RuleConfirmationExpressions)):
            rule.detect_only = False

    rules += [PostProcessRule()]

    return rules


def wrap_helpers(rules: list[Rule]) -> list[Rule]:
    return [CitDetectRule()] + rules + [HelperCleanupRule()]


def get(profile: str) -> tuple[list[Metric], list[Rule]]:
    match profile:
        case 'default_corrective':
            return (
                None,
                wrap_helpers(set_rules_corrective([rule() for rule in Rule.get_final_children()])),
            )
        case 'noninstitutional':
            return (
                get_noninstitutional_metrics(),
                wrap_helpers(get_noninstitutional_rules()),
            )
        case 'noninstitutional_corrective':
            return (
                get_noninstitutional_metrics(),
                wrap_helpers(set_rules_corrective(get_noninstitutional_rules())),
            )
        case 'minimal':
            return (
                None,  # default metrics
                wrap_helpers(get_minimal_rules()),
            )
        case 'minimal_verbose':
            return (
                None,  # default metrics
                wrap_helpers(set_rules_verbose(get_minimal_rules())),
            )
        case _:
            print(f'Profile "{profile}" doesn\'t exist.')
            return (None, None)
