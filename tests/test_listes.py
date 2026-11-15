"""0.4.3 : listes numérotées (« ordre de préparation ») gardées avec leur texte dans l'EPUB."""
from __future__ import annotations

import markdown as md

from app.fabrication import nettoyer, reparer_listes


def html(texte: str) -> str:
    return md.markdown(nettoyer(texte, 1, set()), extensions=["tables", "footnotes", "toc", "sane_lists"])


def test_numero_seul_puis_son_texte():
    h = html("## Ordre de préparation\n\n1.\n\nLes sirops et les jus.\n\n2.\n\nLes spiritueux.\n\n3.\n\nLa glace, à la fin.\n\n72")
    assert "<li>Les sirops et les jus.</li>" in h and "<li>La glace, à la fin.</li>" in h
    assert h.count("<li>") == 3 and "72" not in h and "<ol>" in h


def test_numeros_en_colonne_puis_les_textes():
    h = html("## Ordre de préparation\n\n1.\n2.\n3.\n\nLes sirops et les jus.\n\nLes spiritueux.\n\nLa glace, à la fin.\n\nUn dernier mot.")
    assert "<li>Les sirops et les jus.</li>" in h and "<li>Les spiritueux.</li>" in h and "<li>La glace, à la fin.</li>" in h
    assert "<p>Un dernier mot.</p>" in h


def test_numero_sans_point():
    h = html("1 Verser le gin dans le verre.\n2 Ajouter le vermouth.\n3 Remuer longuement.")
    assert h.count("<li>") == 3 and "<li>Ajouter le vermouth.</li>" in h


def test_ce_qui_n_est_pas_une_liste_reste_tel_quel():
    ingredients = "1 trait d'amer\n2 cl de sirop"
    assert reparer_listes(ingredients) == ingredients            # des ingrédients, pas des étapes
    page_seule = "Un paragraphe.\n\n72"
    assert reparer_listes(page_seule) == page_seule              # un numéro de page n'est pas une liste
    bonne = "1. Verser.\n2. Remuer."
    assert reparer_listes(bonne) == bonne
