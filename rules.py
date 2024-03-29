import util

from udapi.core.block import Block
from udapi.core.node import Node

import os

# TODO: unify rule intervention marks
# TODO: generalize rule blocks (e.g. using an abstract-ish class). it could contain process_id generation, text recomputation etc.


class double_adpos_rule(Block):
    def process_node(self, node: Node):
        # TODO: multi-word adpositions
        # TODO: sometimes the structure isn't actually ambiguous and doesn't need to be ammended
        # TODO: sometimes the rule catches adpositions that shouldn't be repeated in the coordination

        process_id = os.urandom(4).hex()

        if node.upos == "CCONJ":
            cconj = node

            # find an adposition present in the coordination
            for parent_adpos in [
                nd
                for nd in cconj.parent.siblings
                if nd.udeprel == "case" and nd.upos == "ADP"
            ]:
                # check that the two coordination elements have the same case
                if cconj.parent.feats["Case"] != parent_adpos.parent.feats["Case"]:
                    continue

                # check that the second coordination element doesn't already have an adposition
                if not [
                    nd for nd in cconj.siblings if nd.lemma == parent_adpos.lemma
                ] and not [nd for nd in cconj.siblings if nd.upos == "ADP"]:
                    correction = util.clone_node(
                        parent_adpos,
                        cconj.parent,
                        filter_misc_keys=r"^(?!Rule).*",
                        form=parent_adpos.form.lower(),
                    )
                    correction.shift_after_node(cconj)

                    cconj.misc["RuleDoubleAdpos"] = f"{process_id},cconj"
                    parent_adpos.misc["RuleDoubleAdpos"] = f"{process_id},orig_adpos"
                    parent_adpos.parent.misc["RuleDoubleAdpos"] = (
                        f"{process_id},coord_el1"
                    )
                    cconj.parent.misc["RuleDoubleAdpos"] = f"{process_id},coord_el2"
                    correction.misc["RuleDoubleAdpos"] = f"{process_id},add"

                    cconj.root.text = cconj.root.compute_text()
