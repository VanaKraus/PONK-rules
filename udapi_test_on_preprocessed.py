"""
Useful:
    - https://github.com/udapi/udapi-python/blob/master/tutorial/01-visualizing.ipynb
        - this is how I learn how to visit trees
    - https://ufal.mff.cuni.cz/~zeman/vyuka/deptreebanks/NPFL075-working-with-UD.pdf
        - udapy from bash but a python usage is briefly shown as well
    - https://universaldependencies.org/cs/dep/index.html
        - list of dependencies in Czech

repeat prepositions in coordinations: useful to develop on FrBo / nezakonny_uredni_postup 30

"""

import rules

from nltk.corpus import PlaintextCorpusReader as pcr
import udapi

import os

# print('lemma\twords\tudeprel\tupos\txpos')
# for node in doc[2].nodes:
#     print(type(node))
#     print(f"{getattr(node, 'lemma')}\t{node.words}\t{node.udeprel}\t{node.upos}\t{node.xpos}")

# print()

# for node in doc[2].nodes:
#     # if node.upos == 'CCONJ':
#     if util.node_is(node, ('upos', 'CCONJ')):
#         print(node)
#         for sibling in node.parent.siblings:
#             if util.node_is(sibling, ('udeprel', 'case'), ('upos', 'ADP')):
#             # if sibling.udeprel == 'case' and sibling.upos == 'ADP':
#                 print(f"\t{sibling}")


corpus_path = "/home/ivankraus/Documents/programming/PONK/rules/conllu/KUK_0.0/data/FrBo/articles/TXT"
corpus = pcr(corpus_path, r".*\.conllu")

cntr = {"double_adpos": 0}
for fname in corpus.fileids():
    fpath = os.path.join(corpus_path, fname)
    doc = udapi.Document(fpath)
    if rules.rule_double_adpos(doc.nodes):
        print(f"conllu document: {fpath}")
        cntr["double_adpos"] += 1

print(cntr)
