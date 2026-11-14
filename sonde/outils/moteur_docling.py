"""Docling (IBM), sur le processeur : analyse de la mise en page, tableaux, lecture par Tesseract en français."""
from __future__ import annotations

from pathlib import Path

from commun import traiter

_convertisseur = None


def _creer():
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import OcrMode, PdfPipelineOptions, TesseractCliOcrOptions
    from docling.document_converter import DocumentConverter, ImageFormatOption

    options = PdfPipelineOptions()
    options.do_ocr = True
    options.do_table_structure = True
    options.generate_picture_images = True   # découpe des illustrations
    options.images_scale = 2.0
    options.ocr_options = TesseractCliOcrOptions(lang=["fra", "eng"], mode=OcrMode.FULL_PAGE)
    return DocumentConverter(format_options={InputFormat.IMAGE: ImageFormatOption(pipeline_options=options)})


def lire(page: Path, sortie: Path) -> dict:
    global _convertisseur
    from docling_core.types.doc import ImageRefMode, PictureItem, TableItem

    if _convertisseur is None:
        _convertisseur = _creer()   # chargement des modèles : une seule fois
    doc = _convertisseur.convert(str(page)).document
    doc.save_as_markdown(sortie / "page.md", artifacts_dir=Path("images"), image_mode=ImageRefMode.REFERENCED)
    images = sum(1 for el, _ in doc.iterate_items() if isinstance(el, PictureItem))
    tableaux = sum(1 for el, _ in doc.iterate_items() if isinstance(el, TableItem))
    return {"images": images, "tableaux": tableaux}


if __name__ == "__main__":
    traiter("docling", lire)
