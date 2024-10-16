from __future__ import annotations

from numbers import Number

from typing import Literal, Any, Union
import os

import sys

from derinet.lexicon import Lexicon
from udapi.core.block import Block
from udapi.core.node import Node
from udapi.core.document import Document
from pydantic import BaseModel, Field

from document_applicables import Documentable
from document_applicables.rules import util


from document_applicables.rules.util import Color

RULE_ANNOTATION_PREFIX = 'PonkApp1'


print('rules: loading DeriNet', file=sys.stderr)

derinet_lexicon = Lexicon()
# FIXME: choose a better path
derinet_lexicon.load('_local/derinet-2-3.tsv')

print('rules: DeriNet loaded', file=sys.stderr)


class Rule(Documentable):
    detect_only: bool = True
    background_color: Color | None = None
    foreground_color: Color | None = None
    cz_doc: str = "Popis pravidla"
    en_doc: str = "Rule description"
    cz_paricipants: dict[str, str] = Field(default_factory=dict)
    en_paricipants: dict[str, str] = Field(default_factory=dict)
    cz_human_readable_name: str = "Pravidlo"
    en_human_readable_name: str = "Rule"  # uses the internal name
    process_id: str = Field(default_factory=lambda: os.urandom(4).hex(), hidden=True)
    modified_roots: set[Any] = Field(default=set(), hidden=True)  # FIXME: This should not be Any, but rather Root
    application_count: int = Field(default=0, hidden=True)
    average_measured_values: dict[str, float] = Field(default={}, hidden=True)
    measured_values: dict[str, list[float]] = Field(default={}, hidden=True)

    def model_post_init(self, __context: Any) -> None:
        self.process_id = Rule.get_application_id()

    @staticmethod
    def get_application_id():
        return os.urandom(4).hex()

    @classmethod
    def id(cls):
        return cls.__name__

    def annotate_node(self, annotation: str, *node: Node, flag: str | None = None):
        key = f"{RULE_ANNOTATION_PREFIX}:{self.__class__.id()}:{self.process_id}"
        if flag:
            key += f":{flag}"
        super().annotate_node(key, annotation, *node)

    def do_measurement_calculations(self, m_name: str, m_value: float):
        self.average_measured_values[m_name] = (
            (self.average_measured_values.get(m_name) or 0) * self.application_count + m_value
        ) / (self.application_count + 1)
        self.measured_values[m_name] = (self.measured_values.get(m_name) or []) + [m_value]
        # FIXME: this is slow, but probably not relevant

    def annotate_measurement(self, m_name: str, m_value: Number, *node):
        self.annotate_node(str(m_value), *node, flag=f"measur:{m_name}")
        self.do_measurement_calculations(m_name=m_name, m_value=m_value)

    def annotate_parameter(self, p_name: str, p_value: Number, *node):
        self.annotate_node(str(p_value), *node, flag=f"param:{p_name}")

    def after_process_document(self, document):
        for root in self.modified_roots:
            root.text = root.compute_text()

    def advance_application_id(self):
        self.process_id = self.get_application_id()
        self.application_count += 1

    def reset_application_count(self):
        self.application_count = 0
        self.average_measured_values = {}
        self.measured_values = {}

    def process_node(self, node: Node):
        raise NotImplementedError('A rule is expected to have a \'process_node\' method.')


class RuleBlockWrapper(Block):
    def __init__(self, rule: Rule):
        Block.__init__(self)
        self.rule = rule

    def process_node(self, node: Node):
        return self.rule.process_node(node)

    def after_process_document(self, document: Document):
        return self.rule.after_process_document(document)


# tmp reimport of everythin
from .acceptability import (
    RuleDoubleComparison,
    RulePossessiveGenitive,
    RuleIncompleteConjunction,
    RuleWrongValencyCase,
    RuleWrongVerbonominalCase,
)
from .ambiguity import RuleAmbiguousRegards, RuleDoubleAdpos, RuleReflexivePassWithAnimSubj
from .clusters import (
    RuleTooManyNegations,
    RuleTooFewVerbs,
    RuleTooManyNominalConstructions,
    RuleCaseRepetition,
    RuleFunctionWordRepetition,
)
from .phrases import (
    RuleLiteraryStyle,
    RuleAbstractNouns,
    RuleAnaphoricReferences,
    RuleRedundantExpressions,
    RuleConfirmationExpressions,
    RuleRelativisticExpressions,
    RuleTooLongExpressions,
    RuleWeakMeaningWords,
)
from .structural import (
    RulePassive,
    RuleLongSentences,
    RuleVerbalNouns,
    RuleMultiPartVerbs,
    RuleInfVerbDistance,
    RulePredObjDistance,
    RulePredSubjDistance,
    RulePredAtClauseBeginning,
)


class RuleAPIWrapper(BaseModel):
    rule: Union[*Rule.get_final_children()] = Field(..., discriminator='rule_id')  # type: ignore
