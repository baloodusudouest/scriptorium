"""Fiche du livre par l'ISBN (0.4.0) : repérer l'ISBN dans le texte lu, puis chercher la notice.

Ordre de recherche : catalogue général de la BnF (API SRU, Dublin Core, critère bib.fuzzyISBN qui retrouve
un livre par son ISBN-10, son ISBN-13 ou son EAN), puis Open Library. Lecture seule : rien n'est envoyé
d'autre que l'ISBN. La fiche trouvée est une proposition : elle n'est enregistrée qu'après validation.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET

import httpx

BNF = "https://catalogue.bnf.fr/api/SRU"
OPEN_LIBRARY = "https://openlibrary.org/api/books"
DC = "{http://purl.org/dc/elements/1.1/}"

# « ISBN 978-2-07-061275-8 », « ISBN : 2-07-036373-2 », « ISBN-13 9782070612758 », ou un EAN 978/979 nu
_ISBN_ANNONCE = re.compile(r"ISBN(?:[- ]?1[03])?\s*[:.]?\s*((?:97[89][\s\-‐–]?)?\d[\d\s\-‐–]{7,14}[\dXx])", re.IGNORECASE)
_EAN = re.compile(r"(?<!\d)(97[89](?:[\s\-‐–]?\d){10})(?!\d)")


class ErreurNotice(Exception):
    pass


def isbn13(brut: str) -> str | None:
    """ISBN-13 sans tiret si « brut » est un ISBN-10 ou -13 valide (clé de contrôle juste), sinon None."""
    s = re.sub(r"[^\dXx]", "", brut or "").upper()
    if len(s) == 10 and re.fullmatch(r"\d{9}[\dX]", s):
        somme = sum((10 - i) * (10 if c == "X" else int(c)) for i, c in enumerate(s))
        if somme % 11:
            return None
        s = "978" + s[:9]
        return s + str((10 - sum((1 if i % 2 == 0 else 3) * int(c) for i, c in enumerate(s)) % 10) % 10)
    if len(s) == 13 and s.isdigit() and s[:3] in ("978", "979"):
        cle = (10 - sum((1 if i % 2 == 0 else 3) * int(c) for i, c in enumerate(s[:12])) % 10) % 10
        return s if cle == int(s[12]) else None
    return None


def trouver_isbn(texte: str) -> list[str]:
    """Les ISBN valides du texte, dans l'ordre, sans doublon (ISBN-13)."""
    trouves: list[str] = []
    for m in [*_ISBN_ANNONCE.finditer(texte), *_EAN.finditer(texte)]:
        n = isbn13(m.group(1))
        if n and n not in trouves:
            trouves.append(n)
    return trouves


def lisible(isbn: str) -> str:
    """978-2-07-061275-8 n'est pas calculable sans les tables des agences : on garde « 978-2070612758 »."""
    return f"{isbn[:3]}-{isbn[3:]}" if len(isbn) == 13 else isbn


# ---------------------------------------------------------------- recherche

def _auteur_bnf(brut: str) -> str:
    """« Camus, Albert (1913-1960). Auteur du texte » → « Albert Camus »."""
    nom = re.sub(r"\s*\(.*$", "", brut).split(". ")[0].strip()
    if "," in nom:
        famille, prenom = [x.strip() for x in nom.split(",", 1)]
        nom = f"{prenom} {famille}".strip()
    return nom


def _bnf(isbn: str, client: httpx.Client) -> dict | None:
    r = client.get(BNF, params={"version": "1.2", "operation": "searchRetrieve", "recordSchema": "dublincore",
                                "maximumRecords": "1", "query": f'bib.fuzzyISBN all "{isbn}"'})
    r.raise_for_status()
    racine = ET.fromstring(r.content)
    titres = [e.text or "" for e in racine.iter(f"{DC}title")]
    if not titres:
        return None
    auteurs = [_auteur_bnf(e.text or "") for e in racine.iter(f"{DC}creator")]
    editeurs = [re.sub(r"\s*\([^)]*\)\s*$", "", e.text or "").strip() for e in racine.iter(f"{DC}publisher")]
    dates = [re.search(r"\d{4}", e.text or "") for e in racine.iter(f"{DC}date")]
    titre = re.split(r"\s+/\s+", titres[0])[0].strip()
    titre = re.sub(r"\s*\[[^\]]*\]\s*$", "", titre)          # « [Texte imprimé] »
    return {"titre": titre, "auteur": ", ".join(a for a in auteurs if a)[:200],
            "editeur": editeurs[0] if editeurs else "", "annee": next((d.group(0) for d in dates if d), ""),
            "isbn": isbn, "source": "BnF"}


def _open_library(isbn: str, client: httpx.Client) -> dict | None:
    r = client.get(OPEN_LIBRARY, params={"bibkeys": f"ISBN:{isbn}", "format": "json", "jscmd": "data"})
    r.raise_for_status()
    d = r.json().get(f"ISBN:{isbn}")
    if not d:
        return None
    titre = d.get("title", "")
    if d.get("subtitle"):
        titre = f"{titre} : {d['subtitle']}"
    annee = re.search(r"\d{4}", d.get("publish_date", "") or "")
    return {"titre": titre, "auteur": ", ".join(a.get("name", "") for a in d.get("authors", []))[:200],
            "editeur": (d.get("publishers") or [{}])[0].get("name", ""), "annee": annee.group(0) if annee else "",
            "isbn": isbn, "source": "Open Library"}


def chercher(isbn: str, client: httpx.Client | None = None) -> dict | None:
    """Notice du livre : BnF, puis Open Library. None si aucun des deux ne connaît l'ISBN.
    ErreurNotice si aucun des deux n'a pu être joint."""
    n = isbn13(isbn)
    if not n:
        raise ErreurNotice("ISBN invalide (clé de contrôle fausse).")
    propre = client is None
    client = client or httpx.Client(timeout=15, headers={"User-Agent": "Scriptorium (appli personnelle)"})
    pannes = []
    try:
        for source in (_bnf, _open_library):
            try:
                trouve = source(n, client)
            except (httpx.HTTPError, ET.ParseError, ValueError) as e:
                pannes.append(f"{source.__name__.strip('_')} : {e}")
                continue
            if trouve and trouve["titre"]:
                return trouve
    finally:
        if propre:
            client.close()
    if len(pannes) == 2:
        raise ErreurNotice("BnF et Open Library injoignables (" + " ; ".join(pannes) + ").")
    return None
