'''Utilities for external tools handling'''

import json

from derinet.lexicon import Lexicon
from ufal.morphodita import Morpho, TaggedLemmasForms
from udapi.core.node import Node

_vallex = None
_morphodita: Morpho = None
_derinet: Lexicon = None


def get_morphodita() -> Morpho:
    global _morphodita

    if not _morphodita:
        print('Load MorphoDiTa dictionary')
        _morphodita = Morpho.load('_local/czech-morfflex2.0-pdtc1.0-220710/czech-morfflex2.0-220710.dict')

    return _morphodita


def morphodita_generate(lemma: str, tag_wildcard: str = '???????????????') -> list[dict[str, str]]:
    morphodita = get_morphodita()

    lemmas_forms = TaggedLemmasForms()
    morphodita.generate(lemma, tag_wildcard, Morpho.GUESSER, lemmas_forms)

    return [{f.tag: f.form for f in lf.forms} for lf in lemmas_forms]


def get_vallex() -> dict:
    global _vallex

    if not _vallex:
        print('Load VALLEX')
        with open('_local/vallex-verbs-4.5.json', 'r') as f:
            _vallex = json.load(f)

    return _vallex


def vallex_get_lexeme(lemma: str) -> dict:
    vallex = get_vallex()

    return [
        lx
        for lx in vallex['Lexemes']
        if lemma
        in [
            l.removesuffix(' (si)').removesuffix(' (se)')
            for val in lx['lemma']['data'].values()
            for l in val.split(' / ')
        ]
    ]


def get_derinet() -> Lexicon:
    # FIXME: this is temporary (deployment issues)
    return None

    global _derinet

    if not _derinet:
        print('Loading DeriNet')
        _derinet = Lexicon()
        _derinet.load('_local/derinet-2-3.tsv')

    return _derinet
