import util

# TODO: unify return format (preferably something better than a boolean)


def double_adpos_rule(nodes):
    # TODO: multi-word adpositions
    # TODO: sometimes the structure isn't actually ambiguous
    iss = False

    for cconj in util.find_nodes(nodes, ("upos", "CCONJ")):
        for parent_adpos in util.find_nodes(
            cconj.parent.siblings, ("udeprel", "case"), ("upos", "ADP")
        ):
            if cconj.parent.feats["Case"] != parent_adpos.parent.feats["Case"]:
                continue

            if not util.find_nodes(
                cconj.siblings, ("lemma", f"^{parent_adpos.lemma}$")
            ) and not util.find_nodes(cconj.siblings, ("upos", "ADP")):
                iss = True
                print(
                    f"Issue: {parent_adpos.form} {parent_adpos.parent.form} {cconj.form} {cconj.parent.form}"
                )
                correction = cconj.parent.create_child(
                    form=parent_adpos.form, lemma=parent_adpos.lemma
                )
                correction.shift_after_node(cconj)

    return iss
