from __future__ import annotations

import json
import re

from typing import ClassVar

from udapi.core.node import Node
from udapi.core.dualdict import DualDict

from document_applicables.rules.util.structure_modif import get_removing_rules, rules_applied

from . import Rule, RULE_ANNOTATION_PREFIX


class PostProcessRule(Rule):
    rule_id: ClassVar[str] = '_PostProcessRule'
    cz_doc: str = 'Dokument upraven'
    en_doc: str = 'Document amended'

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

    def _remove_as_rule(self, node, rule_application):
        self.annotate_action_as_rule(rule_application, 'remove', node, value='post-process')

    def _sentence_initial_punctuation(self, node):
        # strip sentence-beginning punctuation if preceded by continuous removal commands
        removing_rules: set[str] = get_removing_rules(node, descendants=True)

        for r in removing_rules:
            nodes_wo = self._get_after_correction_mockup(node, r)
            if nodes_wo and nodes_wo[0] and nodes_wo[0].upos == 'PUNCT' and nodes_wo[0].ord > 1:
                self._remove_as_rule(nodes_wo[0], r)

    def _after_coordination_punctuation(self, node):
        removing_rules = get_removing_rules(node, descendants=True)

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
        removing_rules = get_removing_rules(node, descendants=True)

        for rm_rule in removing_rules:
            nodes_wo = self._get_after_correction_mockup(node, rm_rule)
            if not nodes_wo:
                continue

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

                        rebk = f'{RULE_ANNOTATION_PREFIX}:{rm_rule}:rebind'
                        self.add_node_as_rule(
                            rm_rule,
                            correction,
                            n.root,
                            n.ord,
                            (n.misc[rebk] if rebk in n.misc else n.parent.ord),
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

    def _sort_global_comment(self, node):
        lines = node.root.comment.split('\n')
        node.root.comment = '\n'.join(
            [l for l in lines if not l.startswith(f' {RULE_ANNOTATION_PREFIX}')]
            + sorted([l for l in lines if l.startswith(f' {RULE_ANNOTATION_PREFIX}')])
        )

    def process_node(self, node):
        if node.udeprel == 'root':
            self._sentence_initial_punctuation(node)
            self._after_coordination_punctuation(node)
            # this is now handled by PONK itself
            # self._punctuation_spacing(node)
            self._capitalization(node)

            node.root.text = node.root.compute_text()

            self._sort_global_comment(node)


class CitDetectRule(Rule):
    rule_id: ClassVar[str] = '_CitDetectRule'

    _regex_beg: re.Pattern = None
    _regex_end: re.Pattern = None

    @property
    def regex_beg(self) -> re.Pattern:
        if not self._regex_beg:
            self._regex_beg = re.compile(r'["„“]')
        return self._regex_beg

    @property
    def regex_end(self) -> re.Pattern:
        if not self._regex_end:
            self._regex_end = re.compile(r'["“”]')
        return self._regex_end

    def process_node(self, node):
        if node.upos == 'PUNCT' and self.regex_beg.match(node.form) and self.__class__.id() not in rules_applied(node):
            following = node.root.descendants()

            for i in range(node.ord - 1, len(following)):
                self.annotate_node('cit', following[i])

                if self.regex_end.findall(following[i].form) and following[i] != node:
                    break


class HelperCleanupRule(Rule):
    rule_id: ClassVar[str] = '_HelperCleanupRule'

    def process_node(self, node):
        raise NotImplementedError('waiting for proper application removal capabilities')

        # because this needs to loop through RULES, not MISC KEYS
        # the desired misc keys here are of the form PonkApp1:<rule>:<application>
        for k in node.misc:
            if k.startswith('_'):
                del node.misc[k]
