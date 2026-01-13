from __future__ import annotations

from numbers import Number
import json
import re

from typing import Any, Literal, ClassVar
import os

from udapi.core.block import Block
from udapi.core.node import Node
from udapi.core.document import Document
from pydantic import Field

from document_applicables import Documentable
from document_applicables.rules.util.communication import Color
from document_applicables.rules.util.structure_modif import get_removing_rules, node_serializable
from document_applicables.rules.util.grammar_semantics import is_punct_sym

RULE_ANNOTATION_PREFIX = 'PonkApp1'


class Rule(Documentable):
    detect_only: bool = True
    verbose_annotation: bool = False
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
        return cls.rule_id

    def rule_application_key(self) -> str:
        return f'{self.__class__.id()}:{self.process_id}'

    def annotate_node(self, annotation: str, *node: Node, flag: str | None = None):
        self.annotate_node_as_rule(self.rule_application_key(), annotation, *node, flag=flag)

    def annotate_node_as_rule(self, rule_application: str, annotation: str, *node: Node, flag: str | None = None):
        key = f"{RULE_ANNOTATION_PREFIX}:{rule_application}"
        if flag:
            key += f":{flag}"
        super().annotate_node(key, annotation, *node)

    def annotate_action_as_rule(
        self, rule_application: str, action: Literal['remove', 'rebind'], *node: Node, value: str = '_'
    ):
        if action not in ['remove', 'rebind']:
            raise ValueError(f'action required to be "remove" or "rebind"; "{action}" supplied')

        ruleapplmatch = re.search(r'^([_A-Za-z]+):([0-9a-f]{8})$', rule_application)
        if not ruleapplmatch:
            raise ValueError(f'invalid {rule_application=}')

        rule, application = ruleapplmatch[1], ruleapplmatch[2]

        if action == 'rebind':
            if value == '_':
                raise ValueError('rebind target not specified')

            for n in node:
                if rule_application in get_removing_rules(n):
                    return

        if action == 'remove':
            if rule != self.__class__.id() and value == '_':
                raise ValueError('value needs to be specified when removing for a different rule')

            rebk = f'{RULE_ANNOTATION_PREFIX}:{rule_application}:rebind'
            for n in node:
                if rebk in n.misc:
                    del n.misc[rebk]

        self.annotate_node_as_rule(rule_application, value, *node, flag=action)

    def annotate_action(self, action: Literal['remove', 'rebind'], *node: Node, value: str = '_'):
        self.annotate_action_as_rule(self.rule_application_key(), action, *node, value=value)

    def do_measurement_calculations(self, m_name: str, m_value: float):
        self.average_measured_values[m_name] = (
            (self.average_measured_values.get(m_name) or 0) * self.application_count + m_value
        ) / (self.application_count + 1)
        self.measured_values[m_name] = (self.measured_values.get(m_name) or []) + [m_value]
        # FIXME: this is slow, but probably not relevant

    def annotate_measurement(self, m_name: str, m_value: Number, *node):
        if self.verbose_annotation:
            self.annotate_node(str(m_value), *node, flag=f"measur:{m_name}")
            self.do_measurement_calculations(m_name=m_name, m_value=m_value)

    def annotate_parameter(self, p_name: str, p_value: Number, *node):
        if self.verbose_annotation:
            self.annotate_node(str(p_value), *node, flag=f"param:{p_name}")

    def after_process_document(self, document):
        for root in self.modified_roots:
            root.text = root.compute_text()

    def add_global_comment(self, value: str, *node: Node, key: str = None):
        comment = RULE_ANNOTATION_PREFIX + (f':{key}' if key else '') + ' = ' + value

        roots = list({n.root for n in node})
        for r in roots:
            r.add_comment(comment)

    def add_node_as_rule(
        self,
        rule_application: str,
        new_node: Node,
        root: Node,
        add_after: str | int,
        parent: str | int,
        preserve_capitalization: bool = False,
    ) -> str:
        node_id = f'new_{os.urandom(4).hex()}'

        self.add_global_comment(
            json.dumps(
                {
                    'id': node_id,
                    'add_after': str(add_after),
                    'parent': str(parent),
                    'preserve_capitalization': preserve_capitalization,
                    'node': node_serializable(new_node),
                }
            ),
            root,
            key=f'{rule_application}:add',
        )

        return node_id

    def add_node(
        self, new_node: Node, root: Node, add_after: str | int, parent: str | int, preserve_capitalization: bool = False
    ) -> str:
        """Add a comment describing the addition of a new node

        Args:
            new_node (Node): the node to be added
            root (Node): root of the tree the new node belongs to
            add_after (str | int): which node the new node should be shifted after;
                node order expected when shifting after an existing node,
                node ID expected when shifting after another newly added node
            parent (str | int): which node should be the parent of the new node;
                node order expected when expanding an existing node,
                node ID expected when expanding another newly added node
            preserve_capitalization (bool, optional): whether capitalization of the node form
                should remain unmodified. Defaults to False.

        Returns:
            str: ID of the new node; an 8-character HEX key
        """
        return self.add_node_as_rule(
            f'{self.__class__.id()}:{self.process_id}', new_node, root, add_after, parent, preserve_capitalization
        )

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
