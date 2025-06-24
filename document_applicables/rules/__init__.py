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
from udapi.core.dualdict import DualDict
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
                    'parent': parent,
                    'preserve_capitalization': preserve_capitalization,
                    'node': util.node_serializable(new_node),
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


class PostProcessRule(Rule):
    rule_id: Literal['_PostProcessRule'] = '_PostProcessRule'
    cz_doc: str = 'Dokument upraven'
    en_doc: str = 'Document amended'

    def _get_removing_rules(self, node) -> set[str]:
        return {
            mtch[1]
            for nd in node.descendants()
            for m in nd.misc
            if (mtch := re.match(RULE_ANNOTATION_PREFIX + r':([A-Za-z]+:[0-9a-f]{8}):remove', m))
        }

    def _get_after_correction_mockup(self, node, rule_application: str) -> list[Node | None]:
        nodes = node.root.descendants()
        mockup = [nd for nd in nodes if f'{RULE_ANNOTATION_PREFIX}:{rule_application}:remove' not in nd.misc]
        ids = [str(n.ord) for n in mockup]

        for comment in node.root.comment.split('\n'):
            match = re.match(r' ?' + RULE_ANNOTATION_PREFIX + ':' + rule_application + r':add = (.+)', comment)
            if not match:
                continue

            new_node = json.loads(match[1])
            add_after = new_node['add_after']

            if add_after == '0':
                ids.insert(0, new_node['id'])
                mockup.insert(0, None)
            else:
                for i in range(len(ids)):
                    if ids[i] == add_after:
                        ids.insert(i + 1, new_node['id'])
                        mockup.insert(i + 1, None)

        return mockup

    def _remove_as_rule(self, node, rule_application: str):
        node.misc[f'{RULE_ANNOTATION_PREFIX}:{rule_application}:remove'] = 'post-process'

    def _add_as_rule(self, new_node, root, add_after: str, parent: str, preserve_capitalization: bool = False):
        self.add_node()
        pass

    def _sentence_initial_punctuation(self, node):
        # strip sentence-beginning punctuation if preceded by continuous removal commands
        removing_rules: set[str] = self._get_removing_rules(node)

        for r in removing_rules:
            nodes_wo = self._get_after_correction_mockup(node, r)
            if nodes_wo and nodes_wo[0] and nodes_wo[0].upos == 'PUNCT' and nodes_wo[0].ord > 1:
                self._remove_as_rule(nodes_wo[0], r)

    def _after_coordination_punctuation(self, node):
        removing_rules = self._get_removing_rules(node)

        for rm_rule in removing_rules:
            nodes_wo = self._get_after_correction_mockup(node, rm_rule)
            if not nodes_wo:
                continue

            for i, n in enumerate(nodes_wo[1:]):  # nodes_wo[i] refers to the (i+1)th element here
                if (
                    n
                    and nodes_wo[i]
                    and n.upos == 'PUNCT'
                    and nodes_wo[i].deprel in ('cc', 'punct')
                    and n.ord - nodes_wo[i].ord > 1
                ):
                    self._remove_as_rule(n, rm_rule)

    def _punctuation_spacing(self, node):
        removing_rules = self._get_removing_rules(node)

        for rm_rule in removing_rules:
            nodes_wo = self._get_after_correction_mockup(node, rm_rule)
            if not nodes_wo:
                continue

            print(rm_rule)

            for i, n in enumerate(nodes_wo[:-1]):
                if (
                    n
                    and nodes_wo[i + 1]
                    and nodes_wo[i + 1].ord - n.ord > 1
                    and 'SpacesAfter' not in n.misc
                    and 'SpacesBefore' not in nodes_wo[i + 1].misc
                ):
                    if nodes_wo[i + 1].form in (',', ';', '.', '?', '!', ')', ']') and (
                        'SpaceAfter' not in n.misc or n.misc['SpaceAfter'] != 'No'
                    ):
                        correction = Node(
                            root=node.root,
                            form=n.form,
                            lemma=n.lemma,
                            upos=n.upos,
                            xpos=n.xpos,
                            feats=n.feats,
                            deprel=n.deprel,
                            misc=DualDict(dict(n.misc) | {'SpaceAfter': 'No'}),
                        )
                        self.add_node_as_rule(
                            rm_rule,
                            correction,
                            n.root,
                            str(n.ord),
                            (
                                n.misc[rebk]
                                if (rebk := f'{RULE_ANNOTATION_PREFIX}:{rm_rule}:rebind' in n.misc)
                                else str(n.parent.ord)
                            ),
                        )

                        self._remove_as_rule(n, rm_rule)

                    # this is a place to handle other space-around-punctuation logic

    def _capitalization(self, node):
        lines_new: list[str] = []

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

                if (
                    content['add_after'] in [str(i) for i in range(first + 1)]
                    and not content['preserve_capitalization']
                ):
                    content['node']['form'] = content['node']['form'].capitalize()

                lines_new.append(f' {RULE_ANNOTATION_PREFIX}:{rule}:{application}:add = {json.dumps(content)}')
            else:
                lines_new.append(line)

        node.root.comment = '\n'.join(lines_new)

    def process_node(self, node):
        if node.udeprel == 'root':
            self._sentence_initial_punctuation(node)
            self._after_coordination_punctuation(node)
            self._punctuation_spacing(node)
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
