'''Utilities for external tools handling'''

from ufal.morphodita import Morpho, TaggedLemmasForms


# FIXME: agree on how to deal with MorphoDiTa
_morphodita: Morpho = None


def _get_morphodita() -> Morpho:
    global _morphodita

    if _morphodita is None:
        print('Load MorphoDiTa dictionary')
        _morphodita = Morpho.load('_local/czech-morfflex2.0-pdtc1.0-220710/czech-morfflex2.0-220710.dict')

    return _morphodita


def morphodita_generate(lemma: str, tag_wildcard: str = '???????????????') -> list[dict[str, str]]:
    morphodita = _get_morphodita()

    lemmas_forms = TaggedLemmasForms()
    morphodita.generate(lemma, tag_wildcard, Morpho.GUESSER, lemmas_forms)

    return [{f.tag: f.form for f in lf.forms} for lf in lemmas_forms]
