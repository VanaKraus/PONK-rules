from __future__ import annotations

from numbers import Number
import json
import re

from typing import Any, Literal
import os

# from derinet.lexicon import Lexicon
from udapi.core.block import Block
from udapi.core.node import Node
from udapi.core.document import Document
from pydantic import Field

from document_applicables import Documentable
from document_applicables.rules import util


from document_applicables.rules.util import Color

RULE_ANNOTATION_PREFIX = 'PonkApp1'


# print('rules: loading DeriNet', file=sys.stderr)

# derinet_lexicon = Lexicon()
# # FIXME: choose a better path
# derinet_lexicon.load('_local/derinet-2-3.tsv')

# print('rules: DeriNet loaded', file=sys.stderr)


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
        return cls.__name__

    def annotate_node(self, annotation: str, *node: Node, flag: str | None = None):
        key = f"{RULE_ANNOTATION_PREFIX}:{self.__class__.id()}:{self.process_id}"
        if flag:
            key += f":{flag}"
        super().annotate_node(key, annotation, *node)

    def annotate_action(self, action: Literal['remove', 'rebind'], *node: Node, value: str = '_'):
        if action not in ['remove', 'rebind']:
            raise ValueError(f'action required to be "remove" or "add"; "{action}" supplied')
        self.annotate_node(value, *node, flag=action)

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
        node_id = f'new_{os.urandom(4).hex()}'

        self.add_global_comment(
            json.dumps(
                {
                    'id': node_id,
                    'add_after': str(add_after),
                    'parent': parent,
                    'preserve_capitalization': preserve_capitalization,
                    'node': util.node_serializable(new_node),
                }
            ),
            root,
            key=f'{self.__class__.id()}:{self.process_id}:add',
        )

        return node_id

    def advance_application_id(self):
        self.process_id = self.get_application_id()
        self.application_count += 1

    def reset_application_count(self):
        self.application_count = 0
        self.average_measured_values = {}
        self.measured_values = {}

    def process_node(self, node: Node):
        raise NotImplementedError('A rule is expected to have a \'process_node\' method.')


class PostProcessRule(Rule):
    rule_id: Literal['_PostProcessRule'] = '_PostProcessRule'
    cz_doc: str = 'Dokument upraven'
    en_doc: str = 'Document amended'

    def _punctuation(self, node):
        # strip sentence-beginning punctuation if preceded by continuous removal commands
        removing_rules: set[str] = None

        for i, d in enumerate(node.root.descendants()):
            rules = {
                match[1]
                for key in d.misc
                if (match := re.match(RULE_ANNOTATION_PREFIX + r':([A-Za-z]+:[0-9a-f]{8}):remove', key))
            }

            if i == 0:
                removing_rules = rules
            elif d.upos == 'PUNCT':
                for r in removing_rules:
                    d.misc[f'{RULE_ANNOTATION_PREFIX}:{r}:remove'] = 'post-process'
            else:
                removing_rules = removing_rules.intersection(rules)
                if not removing_rules:
                    break

    def _capitalization(self, node):
        lines_new: list[str] = []
        capitalized = False  # whether an added capitalization candidate has been encountered

        for line in node.root.comment.split('\n'):
            if m := re.match(' ' + RULE_ANNOTATION_PREFIX + r':([A-Za-z]+):([0-9a-f]{8}):add = (.+)', line):
                rule = m[1]
                application = m[2]
                content = json.loads(m[3])

                # determine the first node in the sentence structure the rule application would have kept
                first = 0
                for d in node.descendants():
                    if [m for m in d.misc if m == f'{RULE_ANNOTATION_PREFIX}:{rule}:{application}:remove']:
                        first += 1
                    else:
                        break

                if content['add_after'] in [str(i) for i in range(first + 1)]:
                    if not capitalized:
                        if not content['preserve_capitalization']:
                            content['node']['form'] = content['node']['form'].capitalize()

                        capitalized = True
                    elif not content['preserve_capitalization']:
                        content['node']['form'] = content['node']['form'].lower()

                lines_new.append(f' {RULE_ANNOTATION_PREFIX}:{rule}:{application}:add = {json.dumps(content)}')
            else:
                lines_new.append(line)

        node.root.comment = '\n'.join(lines_new)

    def process_node(self, node):
        if node.udeprel == 'root':
            self._punctuation(node)
            self._capitalization(node)

            node.root.text = node.root.compute_text()


class RuleBlockWrapper(Block):
    def __init__(self, rule: Rule):
        Block.__init__(self)
        self.rule = rule

    def process_node(self, node: Node):
        return self.rule.process_node(node)

    def after_process_document(self, document: Document):
        return self.rule.after_process_document(document)
