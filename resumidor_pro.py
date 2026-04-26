#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Resumidor Pro
-------------
Herramienta offline, sin IA generativa ni APIs externas, para extraer texto y generar
resúmenes profesionales de documentos usando técnicas clásicas de PLN/IR:
TF-IDF, TextRank, MMR, heurísticas de secciones, palabras clave y análisis léxico.

Formatos soportados:
- Word OpenXML: .docx, .docm, .dotx
- Word legado: .doc, .dot mediante LibreOffice o antiword si están instalados
- Texto: .txt, .md, .rtf, .html, .htm
- Lectura: .pdf, .epub

Autor: base generada por ChatGPT para uso local/offline.
Licencia sugerida: MIT.
"""
from __future__ import annotations

import argparse
import dataclasses
import html
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

# -----------------------------------------------------------------------------
# UI: Rich si está disponible; fallback sencillo si no está instalado.
# -----------------------------------------------------------------------------
try:  # pragma: no cover - fallback manual
    from rich.console import Console
    from rich.panel import Panel
    from rich.prompt import Confirm, IntPrompt, Prompt
    from rich.table import Table
    from rich.text import Text

    RICH_AVAILABLE = True
except Exception:  # pragma: no cover
    RICH_AVAILABLE = False

    class Console:  # type: ignore
        def print(self, *args, **kwargs):
            print(*args)

        def rule(self, title: str = ""):
            print("\n" + "=" * 12 + f" {title} " + "=" * 12)

        def status(self, message: str):
            class Dummy:
                def __enter__(self_inner):
                    print(message)
                    return self_inner

                def __exit__(self_inner, exc_type, exc, tb):
                    return False

            return Dummy()

    class Prompt:  # type: ignore
        @classmethod
        def ask(cls, prompt: str, default: Optional[str] = None, choices=None):
            suffix = f" [{default}]" if default is not None else ""
            value = input(f"{prompt}{suffix}: ").strip()
            return value if value else default

    class IntPrompt:  # type: ignore
        @classmethod
        def ask(cls, prompt: str, default: Optional[int] = None, choices=None):
            while True:
                suffix = f" [{default}]" if default is not None else ""
                value = input(f"{prompt}{suffix}: ").strip()
                if not value and default is not None:
                    return default
                try:
                    return int(value)
                except ValueError:
                    print("Ingresa un número válido.")

    class Confirm:  # type: ignore
        @classmethod
        def ask(cls, prompt: str, default: bool = False):
            suffix = "S/n" if default else "s/N"
            value = input(f"{prompt} [{suffix}]: ").strip().lower()
            if not value:
                return default
            return value in {"s", "si", "sí", "y", "yes"}

    class Table:  # type: ignore
        def __init__(self, *args, **kwargs):
            self.rows = []

        def add_column(self, *args, **kwargs):
            pass

        def add_row(self, *args, **kwargs):
            self.rows.append(args)

    class Panel:  # type: ignore
        def __init__(self, renderable, title: str = ""):
            self.renderable = renderable
            self.title = title

        def __str__(self):
            return f"{self.title}\n{self.renderable}"


console = Console()

# -----------------------------------------------------------------------------
# Configuración general
# -----------------------------------------------------------------------------
SUPPORTED_EXTENSIONS = {
    ".docx", ".docm", ".dotx", ".doc", ".dot",
    ".txt", ".md", ".rtf", ".html", ".htm",
    ".pdf", ".epub",
}

OPENXML_EXTENSIONS = {".docx", ".docm", ".dotx"}
LEGACY_WORD_EXTENSIONS = {".doc", ".dot"}
TEXT_EXTENSIONS = {".txt", ".md"}
HTML_EXTENSIONS = {".html", ".htm"}

DEFAULT_WPM = 220  # configurable; se usa como supuesto local, no como verdad universal.
DEFAULT_SENTENCE_LIMIT = 1200

SPANISH_STOPWORDS = {
    "a", "acá", "ahí", "al", "algo", "algunas", "algunos", "ante", "antes", "aquel",
    "aquella", "aquellas", "aquello", "aquellos", "aquí", "arriba", "así", "atrás",
    "aun", "aunque", "bajo", "bien", "cada", "casi", "como", "con", "contra", "cual",
    "cuales", "cualquier", "cuando", "cuanta", "cuanto", "cuantos", "de", "dejar",
    "del", "demás", "demasiada", "demasiado", "dentro", "desde", "donde", "dos", "el",
    "él", "ella", "ellas", "ellos", "en", "encima", "entonces", "entre", "era", "erais",
    "eran", "eras", "eres", "es", "esa", "esas", "ese", "eso", "esos", "esta", "está",
    "estaba", "estaban", "estado", "estáis", "estamos", "están", "estar", "estas",
    "este", "esto", "estos", "estoy", "fue", "fueron", "fui", "fuimos", "ha", "haber",
    "había", "habían", "hace", "hacia", "han", "hasta", "hay", "la", "las", "le", "les",
    "lo", "los", "mas", "más", "me", "menos", "mi", "mis", "mientras", "muy", "nada",
    "ni", "no", "nos", "nosotras", "nosotros", "nuestra", "nuestro", "o", "os", "otra",
    "otras", "otro", "otros", "para", "pero", "poco", "por", "porque", "que", "qué", "se",
    "sea", "según", "ser", "si", "sí", "sin", "sobre", "sois", "solamente", "solo", "son",
    "su", "sus", "también", "tanto", "te", "tenéis", "tenemos", "tener", "tengo", "ti",
    "todo", "todos", "tras", "tu", "tus", "un", "una", "unas", "uno", "unos", "usted",
    "ustedes", "vosotras", "vosotros", "y", "ya",
}

ENGLISH_STOPWORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any",
    "are", "as", "at", "be", "because", "been", "before", "being", "below", "between",
    "both", "but", "by", "can", "did", "do", "does", "doing", "down", "during", "each",
    "few", "for", "from", "further", "had", "has", "have", "having", "he", "her", "here",
    "hers", "herself", "him", "himself", "his", "how", "i", "if", "in", "into", "is", "it",
    "its", "itself", "just", "me", "more", "most", "my", "myself", "no", "nor", "not", "now",
    "of", "off", "on", "once", "only", "or", "other", "our", "ours", "ourselves", "out", "over",
    "own", "same", "she", "should", "so", "some", "such", "than", "that", "the", "their",
    "theirs", "them", "themselves", "then", "there", "these", "they", "this", "those", "through",
    "to", "too", "under", "until", "up", "very", "was", "we", "were", "what", "when", "where",
    "which", "while", "who", "whom", "why", "with", "you", "your", "yours", "yourself",
    "yourselves",
}

GENERIC_VERBS_AND_FILLERS = {
    "puede", "pueden", "podemos", "busca", "buscan", "debe", "deben", "tiene", "tienen",
    "hacer", "realizar", "usar", "utilizar", "mediante", "forma", "manera", "adecuado",
    "adecuada", "adecuados", "adecuadas", "importante", "importantes", "relevante",
    "relevantes", "principal", "principales", "general", "generales", "dicho", "dicha",
    "dichos", "dichas", "incluye", "incluyen", "permite", "permiten", "buscando", "hacerlo",
    "also", "may", "might", "can", "could", "using", "used", "use", "include", "includes",
    "important", "relevant", "general", "main",
}

STOPWORDS = SPANISH_STOPWORDS | ENGLISH_STOPWORDS | GENERIC_VERBS_AND_FILLERS

POSITIVE_WORDS = {
    "excelente", "bueno", "beneficio", "beneficios", "mejora", "mejorar", "positivo",
    "optimista", "crecimiento", "éxito", "exitoso", "eficiente", "eficaz", "oportunidad",
    "aprobado", "rentable", "seguro", "sólido", "ventaja", "avance", "progreso",
    "excellent", "good", "benefit", "improve", "positive", "optimistic", "growth",
    "success", "successful", "efficient", "effective", "opportunity", "approved", "secure",
}
NEGATIVE_WORDS = {
    "malo", "deficiente", "riesgo", "riesgos", "problema", "problemas", "negativo",
    "pesimista", "pérdida", "perdida", "costoso", "caro", "error", "fallo", "fallas",
    "amenaza", "duda", "dudas", "preocupación", "preocupaciones", "incumplimiento",
    "multa", "multas", "rescisión", "cancelación", "crítico", "crisis", "retraso",
    "bad", "poor", "risk", "problem", "negative", "pessimistic", "loss", "costly",
    "error", "failure", "threat", "doubt", "concern", "breach", "penalty", "delay",
}
UNCERTAINTY_WORDS = {
    "podría", "podrían", "posible", "posiblemente", "probable", "probablemente", "quizás",
    "tal vez", "duda", "dudas", "incierto", "incertidumbre", "estimado", "aproximado",
    "could", "might", "may", "possible", "possibly", "probable", "probably", "perhaps",
    "uncertain", "uncertainty", "estimated", "approximate",
}
LEGAL_RISK_WORDS = {
    "cláusula", "clausula", "contrato", "rescisión", "rescision", "multa", "penalidad",
    "incumplimiento", "responsabilidad", "obligación", "obligacion", "garantía", "garantia",
    "plazo", "vigencia", "jurisdicción", "jurisdiccion", "confidencialidad", "indemnización",
}

DEFINITION_PATTERNS = re.compile(
    r"\b(es|son|se define|se refiere|consiste|significa|se entiende|denominad[oa]|llamad[oa])\b",
    flags=re.IGNORECASE,
)
CONCLUSION_PATTERNS = re.compile(
    r"\b(conclu|conclusi[oó]n|por tanto|por ende|en resumen|se recomienda|recomendamos|resultado|hallazgo|m[eé]trica|indicador|evidencia|therefore|conclusion|result|finding|metric|recommend)\b",
    flags=re.IGNORECASE,
)
NUMBER_PATTERN = re.compile(r"(?<!\w)(?:\$|€|£)?\d+(?:[.,]\d+)*(?:\s?%|\s?(?:millones|millon|mil|billion|million|k|m))?(?!\w)", re.IGNORECASE)
YEAR_PATTERN = re.compile(r"\b(?:19|20)\d{2}\b")
WORD_RE = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9]+(?:[-'][A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9]+)?")

# -----------------------------------------------------------------------------
# Modelos de datos
# -----------------------------------------------------------------------------
@dataclass
class ExtractOptions:
    ocr: bool = False
    ocr_lang: str = "spa+eng"
    ocr_dpi: int = 220
    max_ocr_pages: Optional[int] = None


@dataclass
class Section:
    title: str
    text: str
    index: int = 0


@dataclass
class Document:
    path: Path
    title: str
    text: str
    sections: List[Section] = field(default_factory=list)
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass
class SentenceUnit:
    text: str
    source: str
    section: str
    index: int
    section_index: int
    words: List[str]
    char_start: int = 0


@dataclass
class SummaryOptions:
    target_words: Optional[int] = None
    target_sentences: Optional[int] = None
    query: Optional[str] = None
    keywords: List[str] = field(default_factory=list)
    persona: str = "neutral"  # principiante, neutral, experto
    diversity: float = 0.72  # MMR lambda: más alto = más relevancia, menor = más diversidad
    preserve_order: bool = True
    max_sentences_pool: int = DEFAULT_SENTENCE_LIMIT


# -----------------------------------------------------------------------------
# Utilidades de texto
# -----------------------------------------------------------------------------
def normalize_whitespace(text: str, preserve_paragraphs: bool = True) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[\t\x0b\x0c]+", " ", text)
    text = re.sub(r"[ \u00a0]+", " ", text)
    if preserve_paragraphs:
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = "\n".join(line.strip() for line in text.splitlines())
    else:
        text = re.sub(r"\s+", " ", text).strip()
    return text.strip()


def strip_markdown(text: str) -> str:
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"^\s{0,3}#{1,6}\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s{0,3}>\s?", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*\d+[.)]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"[*_~]{1,3}", "", text)
    return normalize_whitespace(text)


def html_to_text(html_content: str) -> str:
    try:
        from bs4 import BeautifulSoup
    except Exception:
        # Fallback muy básico si no está beautifulsoup4.
        html_content = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", html_content)
        html_content = re.sub(r"(?s)<[^>]+>", " ", html_content)
        return normalize_whitespace(html.unescape(html_content))

    soup = BeautifulSoup(html_content, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return normalize_whitespace(soup.get_text("\n"))


def read_text_with_encoding(path: Path) -> str:
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "utf-8", "latin-1", "cp1252"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    try:
        from charset_normalizer import from_bytes

        result = from_bytes(raw).best()
        if result:
            return str(result)
    except Exception:
        pass
    return raw.decode("utf-8", errors="replace")


def words(text: str) -> List[str]:
    return WORD_RE.findall(text)


def normalize_term(term: str) -> str:
    return term.lower().strip("-_’'.,;:()[]{}¡!¿?\"“”‘’")


def content_terms(text: str) -> List[str]:
    terms = []
    for w in words(text):
        t = normalize_term(w)
        if len(t) < 3 or t in STOPWORDS:
            continue
        if t.isdigit():
            continue
        terms.append(t)
    return terms


def word_count(text: str) -> int:
    return len(words(text))


def average_word_length(tokens: Sequence[str]) -> float:
    if not tokens:
        return 0.0
    return sum(len(t) for t in tokens) / max(1, len(tokens))


def truncate_words(text: str, max_words: int) -> str:
    toks = words(text)
    if len(toks) <= max_words:
        return text.strip()
    # Corte conservador sobre espacios, no sobre el regex reconstruido.
    parts = text.split()
    return " ".join(parts[:max_words]).rstrip(" ,;:") + "…"


def ensure_period(text: str) -> str:
    text = text.strip()
    if text and text[-1] not in ".!?…":
        return text + "."
    return text


_ABBREVIATIONS = [
    "Sr.", "Sra.", "Srta.", "Dr.", "Dra.", "Ing.", "Lic.", "Prof.", "Ud.", "Uds.",
    "p.ej.", "ej.", "etc.", "vs.", "No.", "Nro.", "Art.", "Cap.", "Fig.", "pág.",
    "Pág.", "EE.UU.", "U.S.", "U.K.", "Mr.", "Mrs.", "Ms.", "Prof.", "Inc.", "Ltd.",
]


def split_sentences(text: str) -> List[str]:
    """Segmentador de oraciones offline, tolerante con español/inglés.

    Evita depender de modelos externos descargables. No es perfecto, pero es estable
    para CLI y documentos largos.
    """
    text = normalize_whitespace(text, preserve_paragraphs=False)
    if not text:
        return []

    protected = text
    placeholders: Dict[str, str] = {}
    for i, abbr in enumerate(_ABBREVIATIONS):
        key = f"<ABBR{i}>"
        placeholders[key] = abbr
        protected = protected.replace(abbr, abbr.replace(".", "<DOT>"))

    # Protege números decimales y dominios simples.
    protected = re.sub(r"(?<=\d)\.(?=\d)", "<DOT>", protected)
    protected = re.sub(r"\b([A-Za-z])\.(?=[A-Za-z]\.)", r"\1<DOT>", protected)

    parts = re.split(r"(?<=[.!?])\s+(?=[\"'“”‘’¿¡\(\[]?[A-ZÁÉÍÓÚÜÑ0-9])", protected)
    sentences = []
    for part in parts:
        part = part.replace("<DOT>", ".").strip()
        if not part:
            continue
        # Evita oraciones absurdamente largas: trocea por punto y coma si hace falta.
        if word_count(part) > 85 and ";" in part:
            sentences.extend([ensure_period(x.strip()) for x in part.split(";") if word_count(x) >= 4])
        else:
            sentences.append(ensure_period(part))
    return sentences


def detect_sections(text: str, title: str = "Documento") -> List[Section]:
    text = normalize_whitespace(text, preserve_paragraphs=True)
    if not text:
        return []

    heading_re = re.compile(
        r"^(?:#{1,6}\s+)?(?:\d+(?:\.\d+)*[.)]?\s+)?[A-ZÁÉÍÓÚÜÑ][\wÁÉÍÓÚÜÑáéíóúüñ ,:;()\-/]{2,95}$"
    )
    sections: List[Section] = []
    current_title = title
    buffer: List[str] = []

    lines = text.splitlines()
    for raw in lines:
        line = raw.strip()
        if not line:
            buffer.append("")
            continue
        is_heading = False
        if len(line) <= 100 and not line.endswith(('.', ',', ';')):
            if line.startswith("#") or heading_re.match(line):
                # Evita clasificar cualquier frase corta como título: exige pocas palabras o numeración/caps.
                wc = word_count(line)
                upper_ratio = sum(1 for c in line if c.isupper()) / max(1, sum(1 for c in line if c.isalpha()))
                starts_number = bool(re.match(r"^\d+(?:\.\d+)*[.)]?\s+", line))
                if wc <= 10 or upper_ratio > 0.55 or starts_number or line.startswith("#"):
                    is_heading = True
        if is_heading and word_count("\n".join(buffer)) >= 30:
            sections.append(Section(current_title.strip("# ") or title, normalize_whitespace("\n".join(buffer)), len(sections)))
            current_title = line.strip("# ")
            buffer = []
        elif is_heading and not buffer:
            current_title = line.strip("# ")
        else:
            buffer.append(line)

    remaining = normalize_whitespace("\n".join(buffer))
    if remaining:
        sections.append(Section(current_title.strip("# ") or title, remaining, len(sections)))

    if not sections:
        # Fallback: dividir en bloques aproximados de 900 palabras.
        toks = text.split()
        chunk_size = 900
        for i in range(0, len(toks), chunk_size):
            chunk = " ".join(toks[i:i + chunk_size])
            sections.append(Section(f"Parte {i // chunk_size + 1}", chunk, i // chunk_size))

    return sections


def sentence_units(documents: Sequence[Document], max_sentences_pool: int = DEFAULT_SENTENCE_LIMIT) -> List[SentenceUnit]:
    units: List[SentenceUnit] = []
    for doc in documents:
        sections = doc.sections or detect_sections(doc.text, doc.title)
        for section in sections:
            for sent in split_sentences(section.text):
                toks = content_terms(sent)
                wc = word_count(sent)
                if wc < 5 or wc > 120:
                    continue
                units.append(
                    SentenceUnit(
                        text=sent,
                        source=doc.title,
                        section=section.title,
                        index=len(units),
                        section_index=section.index,
                        words=toks,
                    )
                )
    # Para documentos gigantes, limitar el pool sin perder inicio/medio/final.
    if len(units) > max_sentences_pool:
        step = len(units) / max_sentences_pool
        units = [units[int(i * step)] for i in range(max_sentences_pool)]
        for idx, unit in enumerate(units):
            unit.index = idx
    return units


# -----------------------------------------------------------------------------
# Extractores
# -----------------------------------------------------------------------------
def extract_openxml_word(path: Path) -> str:
    """Extrae texto de .docx/.docm/.dotx sin depender de Microsoft Word.

    Lee el ZIP OpenXML directamente. Incluye documento principal, encabezados y pies.
    """
    if not zipfile.is_zipfile(path):
        raise ValueError(f"{path.name} no parece ser un archivo Word OpenXML válido.")

    xml_files: List[str] = []
    with zipfile.ZipFile(path) as zf:
        names = set(zf.namelist())
        for name in ["word/document.xml"]:
            if name in names:
                xml_files.append(name)
        xml_files += sorted(n for n in names if re.match(r"word/(header|footer)\d+\.xml$", n))

        paragraphs: List[str] = []
        ns_w = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
        for xml_name in xml_files:
            data = zf.read(xml_name)
            root = ET.fromstring(data)
            for p in root.iter(ns_w + "p"):
                fragments: List[str] = []
                for node in p.iter():
                    tag = node.tag.split("}")[-1]
                    if tag == "t" and node.text:
                        fragments.append(node.text)
                    elif tag == "tab":
                        fragments.append("\t")
                    elif tag in {"br", "cr"}:
                        fragments.append("\n")
                para = "".join(fragments).strip()
                if para:
                    paragraphs.append(para)
    return normalize_whitespace("\n".join(paragraphs))


def run_command_capture(cmd: List[str], timeout: int = 60) -> str:
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=timeout)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"Comando falló: {' '.join(cmd)}")
    return result.stdout


def extract_legacy_word(path: Path) -> str:
    """Extrae .doc/.dot con herramientas locales si existen.

    .doc y .dot son formatos binarios antiguos. Python puro no los lee de forma fiable.
    Esta función intenta antiword y luego LibreOffice headless.
    """
    antiword = shutil.which("antiword")
    if antiword:
        try:
            text = run_command_capture([antiword, str(path)], timeout=90)
            if word_count(text) > 5:
                return normalize_whitespace(text)
        except Exception:
            pass

    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if soffice:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            cmd = [
                soffice, "--headless", "--convert-to", "txt:Text", "--outdir", str(out_dir), str(path)
            ]
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=120)
            candidates = list(out_dir.glob("*.txt"))
            if candidates:
                return normalize_whitespace(read_text_with_encoding(candidates[0]))

    raise RuntimeError(
        f"No pude leer {path.name}. Para .doc/.dot instala LibreOffice o antiword, "
        "o convierte el archivo a .docx/.pdf."
    )


def extract_pdf(path: Path, options: ExtractOptions) -> Tuple[str, Dict[str, str]]:
    metadata: Dict[str, str] = {}
    text_parts: List[str] = []
    page_count = 0

    try:
        from pypdf import PdfReader
    except Exception as exc:
        raise RuntimeError("Falta la dependencia pypdf. Instala: pip install pypdf") from exc

    reader = PdfReader(str(path))
    page_count = len(reader.pages)
    metadata["pages"] = str(page_count)
    for i, page in enumerate(reader.pages, start=1):
        try:
            page_text = page.extract_text() or ""
        except Exception:
            page_text = ""
        if page_text.strip():
            text_parts.append(f"\n\n[Página {i}]\n{page_text}")

    extracted = normalize_whitespace("\n".join(text_parts))
    needs_ocr = page_count > 0 and word_count(extracted) < max(25, page_count * 12)

    if options.ocr and needs_ocr:
        try:
            from pdf2image import convert_from_path
            import pytesseract
        except Exception as exc:
            raise RuntimeError(
                "El PDF parece escaneado y se pidió OCR, pero faltan dependencias. "
                "Instala: pip install pdf2image pytesseract pillow. También necesitas Tesseract y Poppler en el sistema."
            ) from exc

        first = 1
        last = options.max_ocr_pages or page_count
        ocr_parts: List[str] = []
        # Procesar página por página evita consumir mucha RAM en PDFs grandes.
        for page_num in range(first, last + 1):
            images = convert_from_path(str(path), dpi=options.ocr_dpi, first_page=page_num, last_page=page_num)
            for image in images:
                page_text = pytesseract.image_to_string(image, lang=options.ocr_lang)
                if page_text.strip():
                    ocr_parts.append(f"\n\n[Página {page_num} OCR]\n{page_text}")
        ocr_text = normalize_whitespace("\n".join(ocr_parts))
        if word_count(ocr_text) > word_count(extracted):
            extracted = ocr_text
            metadata["ocr"] = "true"

    return extracted, metadata


def extract_epub(path: Path) -> str:
    try:
        import ebooklib
        from ebooklib import epub
    except Exception as exc:
        raise RuntimeError("Falta EbookLib. Instala: pip install EbookLib beautifulsoup4") from exc

    book = epub.read_epub(str(path))
    parts: List[str] = []
    for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
        try:
            content = item.get_content().decode("utf-8", errors="replace")
        except Exception:
            content = str(item.get_content())
        text = html_to_text(content)
        if text.strip():
            parts.append(text)
    return normalize_whitespace("\n\n".join(parts))


def extract_rtf(path: Path) -> str:
    try:
        from striprtf.striprtf import rtf_to_text
    except Exception as exc:
        raise RuntimeError("Falta striprtf. Instala: pip install striprtf") from exc
    return normalize_whitespace(rtf_to_text(read_text_with_encoding(path)))


def extract_document(path: Path, options: ExtractOptions) -> Document:
    path = Path(path).expanduser().resolve()
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"Archivo no encontrado: {path}")
    ext = path.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Formato no soportado: {ext}. Soportados: {', '.join(sorted(SUPPORTED_EXTENSIONS))}")

    metadata: Dict[str, str] = {"extension": ext}
    if ext in OPENXML_EXTENSIONS:
        text = extract_openxml_word(path)
    elif ext in LEGACY_WORD_EXTENSIONS:
        text = extract_legacy_word(path)
    elif ext == ".pdf":
        text, pdf_meta = extract_pdf(path, options)
        metadata.update(pdf_meta)
    elif ext == ".epub":
        text = extract_epub(path)
    elif ext == ".rtf":
        text = extract_rtf(path)
    elif ext in HTML_EXTENSIONS:
        text = html_to_text(read_text_with_encoding(path))
    elif ext == ".md":
        text = strip_markdown(read_text_with_encoding(path))
    else:
        text = normalize_whitespace(read_text_with_encoding(path))

    if word_count(text) < 10:
        raise RuntimeError(
            f"Se extrajo muy poco texto de {path.name}. Puede estar protegido, vacío, escaneado o requerir OCR/conversión."
        )
    sections = detect_sections(text, path.stem)
    return Document(path=path, title=path.stem, text=text, sections=sections, metadata=metadata)


# -----------------------------------------------------------------------------
# Motor de resumen clásico: TF-IDF + TextRank + MMR
# -----------------------------------------------------------------------------
def sentence_term_stats(units: Sequence[SentenceUnit]) -> Tuple[Dict[str, float], Dict[int, Counter]]:
    n = max(1, len(units))
    df: Counter = Counter()
    sent_tf: Dict[int, Counter] = {}
    for u in units:
        c = Counter(u.words)
        sent_tf[u.index] = c
        for term in c:
            df[term] += 1
    idf = {term: math.log((1 + n) / (1 + freq)) + 1 for term, freq in df.items()}
    return idf, sent_tf


def unit_vector(unit: SentenceUnit, idf: Dict[str, float]) -> Dict[str, float]:
    tf = Counter(unit.words)
    if not tf:
        return {}
    max_tf = max(tf.values()) or 1
    return {term: (freq / max_tf) * idf.get(term, 1.0) for term, freq in tf.items()}


def cosine_sparse(a: Dict[str, float], b: Dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    if len(a) > len(b):
        a, b = b, a
    dot = sum(value * b.get(term, 0.0) for term, value in a.items())
    if dot <= 0:
        return 0.0
    norm_a = math.sqrt(sum(v * v for v in a.values()))
    norm_b = math.sqrt(sum(v * v for v in b.values()))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def build_similarity_graph(vectors: List[Dict[str, float]], threshold: float = 0.08, max_neighbors: int = 12) -> List[List[Tuple[int, float]]]:
    n = len(vectors)
    graph: List[List[Tuple[int, float]]] = [[] for _ in range(n)]
    for i in range(n):
        sims: List[Tuple[int, float]] = []
        for j in range(n):
            if i == j:
                continue
            sim = cosine_sparse(vectors[i], vectors[j])
            if sim >= threshold:
                sims.append((j, sim))
        sims.sort(key=lambda x: x[1], reverse=True)
        graph[i] = sims[:max_neighbors]
    return graph


def pagerank(graph: List[List[Tuple[int, float]]], iterations: int = 35, damping: float = 0.85) -> List[float]:
    n = len(graph)
    if n == 0:
        return []
    ranks = [1.0 / n] * n
    incoming: List[List[Tuple[int, float]]] = [[] for _ in range(n)]
    out_weight = [sum(w for _, w in edges) for edges in graph]
    for i, edges in enumerate(graph):
        for j, w in edges:
            incoming[j].append((i, w))
    for _ in range(iterations):
        new = [(1.0 - damping) / n] * n
        for j in range(n):
            score = 0.0
            for i, w in incoming[j]:
                if out_weight[i] > 0:
                    score += ranks[i] * w / out_weight[i]
            new[j] += damping * score
        ranks = new
    max_rank = max(ranks) or 1.0
    return [r / max_rank for r in ranks]


def normalize_scores(scores: Dict[int, float]) -> Dict[int, float]:
    if not scores:
        return {}
    vals = list(scores.values())
    mn, mx = min(vals), max(vals)
    if abs(mx - mn) < 1e-12:
        return {k: 1.0 for k in scores}
    return {k: (v - mn) / (mx - mn) for k, v in scores.items()}


def base_sentence_scores(units: Sequence[SentenceUnit], options: SummaryOptions) -> Dict[int, float]:
    idf, _ = sentence_term_stats(units)
    query_terms = set(content_terms(options.query or ""))
    keyword_terms = set()
    for kw in options.keywords:
        keyword_terms.update(content_terms(kw))

    raw: Dict[int, float] = {}
    total = max(1, len(units))
    for pos, unit in enumerate(units):
        if not unit.words:
            raw[unit.index] = 0.0
            continue
        tf = Counter(unit.words)
        lexical = sum((freq / len(unit.words)) * idf.get(term, 1.0) for term, freq in tf.items())
        # Posición: en muchos documentos, inicio de sección e inicio/final global contienen más contexto.
        relative = pos / max(1, total - 1)
        position_boost = 0.0
        if relative < 0.12:
            position_boost += 0.20 * (1 - relative / 0.12)
        if relative > 0.88:
            position_boost += 0.08 * ((relative - 0.88) / 0.12)
        if pos == 0 or unit.section_index == 0:
            position_boost += 0.03

        q_boost = 0.0
        if query_terms:
            overlap = len(query_terms & set(unit.words)) / max(1, len(query_terms))
            q_boost += 0.65 * overlap
        if keyword_terms:
            overlap = len(keyword_terms & set(unit.words)) / max(1, len(keyword_terms))
            q_boost += 0.45 * overlap

        persona_boost = 0.0
        text_lower = unit.text.lower()
        wc = word_count(unit.text)
        avg_len = average_word_length(unit.words)
        if options.persona == "principiante":
            if DEFINITION_PATTERNS.search(unit.text):
                persona_boost += 0.18
            if wc <= 28:
                persona_boost += 0.08
            if avg_len <= 7.2:
                persona_boost += 0.05
            if NUMBER_PATTERN.search(unit.text) and wc > 45:
                persona_boost -= 0.05
        elif options.persona == "experto":
            if NUMBER_PATTERN.search(unit.text) or YEAR_PATTERN.search(unit.text):
                persona_boost += 0.18
            if CONCLUSION_PATTERNS.search(unit.text):
                persona_boost += 0.16
            if DEFINITION_PATTERNS.search(unit.text) and not NUMBER_PATTERN.search(unit.text):
                persona_boost -= 0.08
            if any(w in text_lower for w in ("introducción", "background", "antecedentes")):
                persona_boost -= 0.08

        raw[unit.index] = lexical + position_boost + q_boost + persona_boost
    return normalize_scores(raw)


def select_with_mmr(
    units: Sequence[SentenceUnit],
    vectors: List[Dict[str, float]],
    scores: Dict[int, float],
    target_words: Optional[int] = None,
    target_sentences: Optional[int] = None,
    diversity: float = 0.72,
) -> List[SentenceUnit]:
    if not units:
        return []
    remaining = set(range(len(units)))
    selected: List[int] = []
    selected_words = 0

    if target_sentences is None and target_words is None:
        target_sentences = max(3, min(12, math.ceil(len(units) * 0.12)))
    if target_words is not None:
        target_words = max(40, target_words)

    while remaining:
        best_i = None
        best_value = -10**9
        for i in remaining:
            rel = scores.get(units[i].index, 0.0)
            if selected:
                redundancy = max(cosine_sparse(vectors[i], vectors[j]) for j in selected)
            else:
                redundancy = 0.0
            value = diversity * rel - (1.0 - diversity) * redundancy
            # Penalizar frases demasiado largas cuando el presupuesto es breve.
            wc = word_count(units[i].text)
            if target_words is not None and target_words <= 450 and wc > 45:
                value -= 0.08
            if value > best_value:
                best_value = value
                best_i = i
        if best_i is None:
            break
        selected.append(best_i)
        remaining.remove(best_i)
        selected_words += word_count(units[best_i].text)

        if target_sentences is not None and len(selected) >= target_sentences:
            break
        if target_words is not None and selected_words >= target_words:
            break
        if len(selected) >= 80:  # guardrail para salidas enormes
            break

    return [units[i] for i in selected]


def summarize_documents(documents: Sequence[Document], options: SummaryOptions) -> List[SentenceUnit]:
    units = sentence_units(documents, options.max_sentences_pool)
    if not units:
        return []
    idf, _ = sentence_term_stats(units)
    vectors = [unit_vector(u, idf) for u in units]
    base_scores = base_sentence_scores(units, options)

    # TextRank agrega centralidad: frases conectadas con muchas frases importantes suben.
    graph = build_similarity_graph(vectors)
    rank_scores = pagerank(graph)
    combined: Dict[int, float] = {}
    for i, unit in enumerate(units):
        combined[unit.index] = 0.58 * base_scores.get(unit.index, 0.0) + 0.42 * rank_scores[i]

    selected = select_with_mmr(
        units=units,
        vectors=vectors,
        scores=combined,
        target_words=options.target_words,
        target_sentences=options.target_sentences,
        diversity=options.diversity,
    )
    if options.preserve_order:
        selected.sort(key=lambda u: u.index)
    return selected


def render_sentence_summary(selected: Sequence[SentenceUnit], include_sources: bool = False) -> str:
    if not selected:
        return "No se pudo generar resumen con suficiente contenido."
    paragraphs: List[str] = []
    current_source_section = None
    buffer: List[str] = []
    for unit in selected:
        key = (unit.source, unit.section)
        if include_sources and current_source_section is not None and key != current_source_section and buffer:
            paragraphs.append(" ".join(buffer))
            buffer = []
        if include_sources and key != current_source_section:
            buffer.append(f"[{unit.source} · {unit.section}] {unit.text}")
            current_source_section = key
        else:
            buffer.append(unit.text)
    if buffer:
        paragraphs.append(" ".join(buffer))
    return "\n\n".join(ensure_period(p) for p in paragraphs)


# -----------------------------------------------------------------------------
# Palabras clave, FAQ, jerárquico, sentimiento, comparación y visualización
# -----------------------------------------------------------------------------
def extract_keyphrases(text: str, top_n: int = 25, max_ngram: int = 3) -> List[Tuple[str, float]]:
    """Extrae términos y frases clave sin modelos externos.

    La generación de n-gramas se hace por oración para no mezclar encabezados o
    párrafos distintos, algo común en PDFs/Word convertidos a texto.
    """
    candidates: Counter = Counter()
    sentence_list = split_sentences(text)
    if not sentence_list:
        sentence_list = [text]

    for sent in sentence_list:
        tokens = [normalize_term(w) for w in words(sent)]
        tokens = [t for t in tokens if t and not t.isdigit()]
        for n in range(1, max_ngram + 1):
            for i in range(0, len(tokens) - n + 1):
                gram = tokens[i:i + n]
                if any(len(t) < 3 for t in gram):
                    continue
                if any(t in STOPWORDS for t in gram):
                    continue
                phrase = " ".join(gram)
                candidates[phrase] += 1

    scored: List[Tuple[str, float]] = []
    total = max(1, sum(candidates.values()))
    for phrase, freq in candidates.items():
        n = len(phrase.split())
        uniqueness = len(set(phrase.split())) / n
        score = (freq / total) * (1.0 + 0.30 * (n - 1)) * uniqueness * math.log(2 + freq)
        # Ligero boost a frases legales/técnicas si aparecen.
        if any(w in LEGAL_RISK_WORDS for w in phrase.split()):
            score *= 1.18
        scored.append((phrase, score))
    scored.sort(key=lambda x: (x[1], len(x[0])), reverse=True)

    # Filtra frases casi duplicadas: si "contrato servicio" ya está, no metas "servicio" salvo que sea muy fuerte.
    final: List[Tuple[str, float]] = []
    for phrase, score in scored:
        term_set = set(phrase.split())
        if any(term_set <= set(p.split()) for p, _ in final):
            continue
        if len(final) >= top_n:
            break
        final.append((phrase, score))
    return final


def automatic_glossary(text: str, phrases: Sequence[str], limit: int = 8) -> List[Tuple[str, str]]:
    sents = split_sentences(text)
    result: List[Tuple[str, str]] = []
    for phrase in phrases:
        p_terms = set(content_terms(phrase))
        if not p_terms:
            continue
        best = None
        best_score = -1.0
        for sent in sents:
            s_terms = set(content_terms(sent))
            overlap = len(p_terms & s_terms)
            if overlap == 0:
                continue
            score = overlap
            if DEFINITION_PATTERNS.search(sent):
                score += 2.0
            if word_count(sent) <= 36:
                score += 0.3
            if score > best_score:
                best_score = score
                best = sent
        if best:
            result.append((phrase, truncate_words(best, 34)))
        if len(result) >= limit:
            break
    return result


def make_headline(documents: Sequence[Document]) -> str:
    opts = SummaryOptions(target_sentences=1, persona="experto", diversity=0.9)
    selected = summarize_documents(documents, opts)
    if selected:
        sent = selected[0].text
        if word_count(sent) <= 24:
            return sent
        keyphrases = extract_keyphrases("\n".join(d.text for d in documents), top_n=3)
        if keyphrases:
            return f"Idea central: {keyphrases[0][0].capitalize()}."
        return truncate_words(sent, 20)
    return "No se detectó una idea central clara."


def hierarchical_summary(documents: Sequence[Document], persona: str = "neutral") -> str:
    full_text = "\n\n".join(d.text for d in documents)
    keyphrases = [p for p, _ in extract_keyphrases(full_text, top_n=18)]
    headline = make_headline(documents)
    bullets = summarize_documents(documents, SummaryOptions(target_sentences=3, persona=persona, diversity=0.82))
    executive = summarize_documents(documents, SummaryOptions(target_words=260, persona=persona, diversity=0.74))

    lines = [
        "# Resumen multinivel",
        "",
        "## Nivel 1 · Titular",
        headline,
        "",
        "## Nivel 2 · Tres puntos clave",
    ]
    for unit in bullets[:3]:
        lines.append(f"- {unit.text}")
    lines += ["", "## Nivel 3 · Resumen ejecutivo", render_sentence_summary(executive), ""]

    lines.append("## Nivel 4 · Resumen por secciones")
    for doc in documents:
        lines.append(f"\n### {doc.title}")
        sections = doc.sections or detect_sections(doc.text, doc.title)
        for section in sections[:24]:
            section_doc = Document(path=doc.path, title=doc.title, text=section.text, sections=[section])
            section_target = min(140, max(55, word_count(section.text) // 7))
            selected = summarize_documents([section_doc], SummaryOptions(target_words=section_target, persona=persona, diversity=0.78))
            if selected:
                lines.append(f"\n#### {section.title}")
                lines.append(render_sentence_summary(selected))
    if keyphrases:
        lines += ["", "## Palabras clave detectadas", ", ".join(keyphrases[:18])]
    return "\n".join(lines).strip()


def query_based_summary(documents: Sequence[Document], query: str, keywords: Optional[List[str]] = None, target_words: int = 320) -> str:
    keywords = keywords or []
    selected = summarize_documents(
        documents,
        SummaryOptions(target_words=target_words, query=query, keywords=keywords, persona="experto", diversity=0.68),
    )
    phrases = [p for p, _ in extract_keyphrases("\n".join(d.text for d in documents), top_n=20)]
    lines = [
        f"# Resumen por ángulo de interés",
        "",
        f"**Interés definido:** {query}",
        "",
        render_sentence_summary(selected, include_sources=len(documents) > 1),
    ]
    if keywords:
        lines += ["", "**Palabras clave priorizadas:** " + ", ".join(keywords)]
    if phrases:
        lines += ["", "**Términos relevantes detectados:** " + ", ".join(phrases[:12])]
    return "\n".join(lines).strip()


def persona_summary(documents: Sequence[Document], persona: str, target_words: int = 360) -> str:
    selected = summarize_documents(documents, SummaryOptions(target_words=target_words, persona=persona, diversity=0.72))
    text = "\n\n".join(d.text for d in documents)
    keyphrases = [p for p, _ in extract_keyphrases(text, top_n=14)]
    lines = [f"# Resumen para nivel: {persona}", "", render_sentence_summary(selected, include_sources=len(documents) > 1)]
    if persona == "principiante":
        glossary = automatic_glossary(text, keyphrases, limit=8)
        if glossary:
            lines += ["", "## Glosario automático basado en el documento"]
            for term, context in glossary:
                lines.append(f"- **{term}:** {context}")
    elif persona == "experto":
        metric_sentences = [s for s in split_sentences(text) if NUMBER_PATTERN.search(s) or CONCLUSION_PATTERNS.search(s)]
        if metric_sentences:
            lines += ["", "## Datos, métricas o conclusiones detectadas"]
            for sent in metric_sentences[:8]:
                lines.append(f"- {truncate_words(sent, 38)}")
    return "\n".join(lines).strip()


def sentiment_analysis(documents: Sequence[Document], top_n: int = 8) -> str:
    all_units = sentence_units(documents)
    rows = []
    total_pos = total_neg = total_unc = 0
    for unit in all_units:
        toks = set(content_terms(unit.text))
        pos = len(toks & POSITIVE_WORDS)
        neg = len(toks & NEGATIVE_WORDS)
        unc = sum(1 for w in UNCERTAINTY_WORDS if w in unit.text.lower())
        total_pos += pos
        total_neg += neg
        total_unc += unc
        score = pos - neg
        if pos or neg or unc:
            rows.append((abs(score) + unc * 0.7 + pos + neg, score, unc, unit))
    rows.sort(key=lambda x: x[0], reverse=True)
    total = total_pos + total_neg
    if total == 0:
        orientation = "neutral o descriptivo"
    elif total_pos > total_neg * 1.25:
        orientation = "mayormente positivo/optimista"
    elif total_neg > total_pos * 1.25:
        orientation = "mayormente negativo/preocupado"
    else:
        orientation = "mixto o equilibrado"
    lines = [
        "# Análisis de sentimiento y tono",
        "",
        f"**Lectura general:** tono {orientation}.",
        f"**Indicadores léxicos:** positivos={total_pos}, negativos={total_neg}, incertidumbre={total_unc}.",
        "",
        "## Frases que explican el tono",
    ]
    if rows:
        for _, score, unc, unit in rows[:top_n]:
            label = "positivo" if score > 0 else "negativo" if score < 0 else "incierto/neutral"
            if unc:
                label += ", con incertidumbre"
            lines.append(f"- **{label}** · {unit.source}: {unit.text}")
    else:
        lines.append("- No se detectaron suficientes palabras de tono con el léxico incluido.")
    return "\n".join(lines).strip()


def generate_faq(documents: Sequence[Document], questions: int = 10) -> str:
    full_text = "\n\n".join(d.text for d in documents)
    phrases = [p for p, _ in extract_keyphrases(full_text, top_n=max(questions * 2, 15))]
    lines = ["# Preguntas frecuentes generadas desde el documento", ""]
    used_answers = set()
    count = 0
    for phrase in phrases:
        selected = summarize_documents(
            documents,
            SummaryOptions(target_sentences=1, query=phrase, keywords=[phrase], persona="neutral", diversity=0.85),
        )
        if not selected:
            continue
        answer = selected[0].text
        if answer in used_answers:
            continue
        used_answers.add(answer)
        question = f"¿Qué dice el documento sobre {phrase}?"
        lines += [f"## {question}", answer, ""]
        count += 1
        if count >= questions:
            break
    if count == 0:
        lines.append("No se pudo generar FAQ con suficiente contenido.")
    return "\n".join(lines).strip()


def simple_explanation(documents: Sequence[Document], target_words: int = 260) -> str:
    selected = summarize_documents(
        documents,
        SummaryOptions(target_words=target_words, persona="principiante", diversity=0.76),
    )
    text = "\n\n".join(d.text for d in documents)
    keyphrases = [p for p, _ in extract_keyphrases(text, top_n=8)]
    lines = [
        "# Explicación simple",
        "",
        "## Idea principal",
        render_sentence_summary(selected),
    ]
    glossary = automatic_glossary(text, keyphrases, limit=5)
    if glossary:
        lines += ["", "## Palabras importantes explicadas con frases del documento"]
        for term, context in glossary:
            lines.append(f"- **{term}:** {context}")
    lines += [
        "",
        "> Nota: este modo no inventa analogías ni definiciones externas; simplifica seleccionando frases más claras del propio documento.",
    ]
    return "\n".join(lines).strip()


def cooccurring_terms(sentences: Sequence[str], main_term: str, all_terms: Sequence[str], limit: int = 4) -> List[str]:
    main_set = set(content_terms(main_term))
    counts: Counter = Counter()
    for sent in sentences:
        sent_terms = set(content_terms(sent))
        if not (main_set & sent_terms):
            continue
        for term in all_terms:
            if term == main_term:
                continue
            if set(content_terms(term)) & sent_terms:
                counts[term] += 1
    return [term for term, _ in counts.most_common(limit)]


def concept_map(documents: Sequence[Document]) -> str:
    text = "\n\n".join(d.text for d in documents)
    phrases = [p for p, _ in extract_keyphrases(text, top_n=18)]
    sentences = split_sentences(text)
    title = documents[0].title if len(documents) == 1 else "Documentos comparados"
    safe_title = re.sub(r"[^\wÁÉÍÓÚÜÑáéíóúüñ -]", "", title)[:45] or "Documento"

    lines = [
        "# Mapa conceptual",
        "",
        "```mermaid",
        "mindmap",
        f"  root(({safe_title}))",
    ]
    for phrase in phrases[:8]:
        node = phrase.replace(":", "").strip().capitalize()
        lines.append(f"    {node}")
        for child in cooccurring_terms(sentences, phrase, phrases, limit=3):
            lines.append(f"      {child.replace(':', '').strip().capitalize()}")
    lines.append("```")

    lines += ["", "## Tabla de términos clave", "", "| Término | Contexto representativo |", "|---|---|"]
    for phrase in phrases[:10]:
        selected = summarize_documents(documents, SummaryOptions(target_sentences=1, query=phrase, keywords=[phrase]))
        context = selected[0].text if selected else ""
        lines.append(f"| {phrase} | {context.replace('|', '/')} |")
    return "\n".join(lines).strip()


def comparative_summary(documents: Sequence[Document], target_words: int = 650) -> str:
    if len(documents) < 2:
        return "Se necesitan al menos dos documentos para el resumen comparativo."

    full_summary = summarize_documents(
        documents,
        SummaryOptions(target_words=target_words, persona="experto", diversity=0.62, preserve_order=False),
    )
    # Palabras clave por documento
    per_doc_phrases: Dict[str, List[str]] = {}
    for doc in documents:
        per_doc_phrases[doc.title] = [p for p, _ in extract_keyphrases(doc.text, top_n=18)]

    phrase_sets = {title: set(phrases) for title, phrases in per_doc_phrases.items()}
    common = set.intersection(*phrase_sets.values()) if phrase_sets else set()
    if not common:
        # Fallback por términos individuales
        term_sets = {title: set(content_terms(" ".join(phrases))) for title, phrases in per_doc_phrases.items()}
        common_terms = set.intersection(*term_sets.values()) if term_sets else set()
        common = set(list(common_terms)[:12])

    unique: Dict[str, List[str]] = {}
    for title, phrases in phrase_sets.items():
        others = set.union(*(s for t, s in phrase_sets.items() if t != title)) if len(phrase_sets) > 1 else set()
        unique[title] = [p for p in per_doc_phrases[title] if p not in others][:8]

    contradictions = detect_possible_contradictions(documents)

    lines = [
        "# Resumen comparativo de múltiples archivos",
        "",
        "## Síntesis integrada",
        render_sentence_summary(full_summary, include_sources=True),
        "",
        "## Puntos en común",
    ]
    if common:
        for item in list(common)[:12]:
            lines.append(f"- {item}")
    else:
        lines.append("- No se detectaron puntos comunes fuertes con las heurísticas actuales.")

    lines += ["", "## Aportes únicos por fuente"]
    for title, items in unique.items():
        lines.append(f"\n### {title}")
        if items:
            for item in items:
                lines.append(f"- {item}")
        else:
            lines.append("- No se detectaron términos únicos fuertes.")

    lines += ["", "## Posibles contradicciones o tensiones"]
    if contradictions:
        for item in contradictions[:10]:
            lines.append(f"- {item}")
    else:
        lines.append("- No se detectaron contradicciones evidentes con reglas léxicas/númericas.")

    lines += [
        "",
        "> Nota: la detección de contradicciones es heurística. Marca diferencias probables, no una verificación lógica perfecta.",
    ]
    return "\n".join(lines).strip()


def detect_possible_contradictions(documents: Sequence[Document]) -> List[str]:
    units = sentence_units(documents, max_sentences_pool=900)
    idf, _ = sentence_term_stats(units)
    vectors = [unit_vector(u, idf) for u in units]
    results: List[str] = []
    neg_re = re.compile(r"\b(no|nunca|sin|prohibid[oa]|rechazad[oa]|imposible|not|never|without|prohibited|rejected|impossible)\b", re.I)

    for i in range(len(units)):
        for j in range(i + 1, len(units)):
            if units[i].source == units[j].source:
                continue
            sim = cosine_sparse(vectors[i], vectors[j])
            if sim < 0.24:
                continue
            neg_i = bool(neg_re.search(units[i].text))
            neg_j = bool(neg_re.search(units[j].text))
            nums_i = set(NUMBER_PATTERN.findall(units[i].text))
            nums_j = set(NUMBER_PATTERN.findall(units[j].text))
            numeric_conflict = bool(nums_i and nums_j and nums_i != nums_j)
            neg_conflict = neg_i != neg_j
            if numeric_conflict or neg_conflict:
                reason = "cifras distintas" if numeric_conflict else "afirmación/negación"
                results.append(
                    f"**{reason}** entre *{units[i].source}* y *{units[j].source}*: “{truncate_words(units[i].text, 24)}” / “{truncate_words(units[j].text, 24)}”"
                )
            if len(results) >= 20:
                return results
    return results


# -----------------------------------------------------------------------------
# Salida
# -----------------------------------------------------------------------------
def safe_filename(name: str) -> str:
    name = re.sub(r"[^\wÁÉÍÓÚÜÑáéíóúüñ.-]+", "_", name, flags=re.UNICODE).strip("_")
    return name[:120] or "resumen"


def save_output(content: str, outdir: Path, base_name: str, fmt: str = "md", metadata: Optional[Dict] = None) -> Path:
    outdir.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    fmt = fmt.lower().lstrip(".")
    if fmt not in {"md", "txt", "json", "html"}:
        fmt = "md"
    filename = f"resumen_{safe_filename(base_name)}_{ts}.{fmt}"
    path = outdir / filename

    if fmt == "json":
        payload = {"created_at": ts, "content": content, "metadata": metadata or {}}
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    elif fmt == "html":
        html_content = markdownish_to_html(content)
        path.write_text(html_content, encoding="utf-8")
    else:
        path.write_text(content, encoding="utf-8")
    return path


def markdownish_to_html(content: str) -> str:
    # Conversor simple sin dependencias. Preserva bloques mermaid.
    escaped_lines = []
    in_code = False
    for line in content.splitlines():
        if line.startswith("```"):
            if not in_code:
                in_code = True
                escaped_lines.append("<pre><code>")
            else:
                in_code = False
                escaped_lines.append("</code></pre>")
            continue
        if in_code:
            escaped_lines.append(html.escape(line))
            continue
        if line.startswith("# "):
            escaped_lines.append(f"<h1>{html.escape(line[2:])}</h1>")
        elif line.startswith("## "):
            escaped_lines.append(f"<h2>{html.escape(line[3:])}</h2>")
        elif line.startswith("### "):
            escaped_lines.append(f"<h3>{html.escape(line[4:])}</h3>")
        elif line.startswith("- "):
            escaped_lines.append(f"<p>• {html.escape(line[2:])}</p>")
        elif not line.strip():
            escaped_lines.append("<br>")
        else:
            escaped_lines.append(f"<p>{html.escape(line)}</p>")
    return "<!doctype html><html><head><meta charset='utf-8'><title>Resumen</title></head><body>" + "\n".join(escaped_lines) + "</body></html>"


# -----------------------------------------------------------------------------
# Menú interactivo
# -----------------------------------------------------------------------------
def list_supported_files(directory: Path) -> List[Path]:
    return sorted([p for p in directory.iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS])


def print_file_table(files: Sequence[Path]) -> None:
    if RICH_AVAILABLE:
        table = Table(title="Archivos soportados encontrados")
        table.add_column("#", justify="right")
        table.add_column("Archivo")
        table.add_column("Tipo")
        table.add_column("Tamaño")
        for i, file in enumerate(files, start=1):
            size_kb = file.stat().st_size / 1024
            table.add_row(str(i), file.name, file.suffix.lower(), f"{size_kb:,.1f} KB")
        console.print(table)
    else:  # pragma: no cover
        print("Archivos soportados encontrados:")
        for i, file in enumerate(files, start=1):
            print(f"{i}. {file.name} ({file.suffix.lower()})")


def parse_selection(selection: str, max_index: int) -> List[int]:
    selection = selection.strip().lower()
    if selection in {"todo", "todos", "all", "*"}:
        return list(range(max_index))
    result = set()
    for part in re.split(r"[,\s]+", selection):
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            if a.isdigit() and b.isdigit():
                start, end = int(a), int(b)
                for idx in range(start, end + 1):
                    if 1 <= idx <= max_index:
                        result.add(idx - 1)
        elif part.isdigit():
            idx = int(part)
            if 1 <= idx <= max_index:
                result.add(idx - 1)
    return sorted(result)


def choose_files_interactive() -> List[Path]:
    raw_path = Prompt.ask("Ruta del archivo o carpeta", default=os.getcwd())
    path = Path(raw_path).expanduser().resolve()
    if path.is_file():
        return [path]
    if not path.exists() or not path.is_dir():
        raise FileNotFoundError(f"La ruta no existe o no es carpeta/archivo: {path}")
    files = list_supported_files(path)
    if not files:
        raise RuntimeError("No se encontraron archivos soportados en esa carpeta.")
    print_file_table(files)
    selection = Prompt.ask("Selecciona números separados por coma, rango 1-3 o 'todos'", default="1")
    indexes = parse_selection(selection, len(files))
    if not indexes:
        raise RuntimeError("No seleccionaste archivos válidos.")
    return [files[i] for i in indexes]


def choose_mode_interactive(multi_file: bool) -> str:
    modes = [
        ("1", "time", "Resumen por tiempo disponible"),
        ("2", "words", "Resumen por cantidad de palabras"),
        ("3", "persona", "Resumen por nivel de experiencia"),
        ("4", "hierarchical", "Resumen multinivel / jerárquico"),
        ("5", "query", "Resumen por ángulo de interés"),
        ("6", "keywords", "Resumen guiado por palabras clave"),
        ("7", "comparative", "Comparativo de múltiples archivos"),
        ("8", "sentiment", "Análisis de sentimiento y tono"),
        ("9", "faq", "Formato preguntas y respuestas"),
        ("10", "simple", "Explicación simple"),
        ("11", "concept", "Mapa conceptual y tabla"),
        ("12", "full", "Informe completo"),
    ]
    if RICH_AVAILABLE:
        table = Table(title="Modos de resumen")
        table.add_column("#", justify="right")
        table.add_column("Modo")
        table.add_column("Descripción")
        for num, mode, desc in modes:
            if mode == "comparative" and not multi_file:
                desc += " (requiere 2+ archivos)"
            table.add_row(num, mode, desc)
        console.print(table)
    else:  # pragma: no cover
        for num, mode, desc in modes:
            print(f"{num}. {mode} - {desc}")
    choice = Prompt.ask("Elige un modo", default="4")
    mapping = {num: mode for num, mode, _ in modes}
    return mapping.get(choice, choice.strip().lower())


def choose_minutes() -> float:
    options = [2, 5, 10, 30, 60, 120]
    if RICH_AVAILABLE:
        table = Table(title="Tiempo disponible")
        table.add_column("#")
        table.add_column("Minutos")
        for i, m in enumerate(options, start=1):
            label = f"{m} min" if m < 60 else f"{m // 60} hora" + ("s" if m > 60 else "")
            table.add_row(str(i), label)
        console.print(table)
    choice = IntPrompt.ask("Selecciona opción", default=2)
    if 1 <= choice <= len(options):
        return float(options[choice - 1])
    return float(choice)


def interactive() -> None:
    if RICH_AVAILABLE:
        console.print(Panel("[bold]Resumidor Pro[/bold]\nOffline, sin IA generativa, con NLP clásico y extracción multi-formato.", title="Inicio"))
    else:
        console.print("Resumidor Pro - Offline, sin IA generativa")

    files = choose_files_interactive()
    multi = len(files) > 1
    mode = choose_mode_interactive(multi)
    ocr = Confirm.ask("Usar OCR si un PDF parece escaneado", default=False)
    ocr_lang = Prompt.ask("Idioma OCR de Tesseract", default="spa+eng") if ocr else "spa+eng"
    out_fmt = Prompt.ask("Formato de salida", default="md", choices=["md", "txt", "json", "html"] if RICH_AVAILABLE else None)
    outdir_raw = Prompt.ask("Carpeta de salida", default=str(files[0].parent))
    outdir = Path(outdir_raw).expanduser().resolve()

    extract_options = ExtractOptions(ocr=ocr, ocr_lang=ocr_lang)
    documents: List[Document] = []
    with console.status("Extrayendo texto de documentos..."):
        for file in files:
            documents.append(extract_document(file, extract_options))

    content = run_mode_interactive(mode, documents)
    base_name = documents[0].title if len(documents) == 1 else f"comparativo_{len(documents)}_archivos"
    output_path = save_output(
        content,
        outdir=outdir,
        base_name=base_name,
        fmt=out_fmt,
        metadata={"files": [str(d.path) for d in documents], "mode": mode},
    )
    console.print(f"\n✅ Resumen guardado en: [bold]{output_path}[/bold]" if RICH_AVAILABLE else f"\nResumen guardado en: {output_path}")


def run_mode_interactive(mode: str, documents: Sequence[Document]) -> str:
    mode = mode.lower()
    if mode == "time":
        minutes = choose_minutes()
        wpm = IntPrompt.ask("Palabras por minuto a usar", default=DEFAULT_WPM)
        target_words = int(minutes * wpm)
        persona = Prompt.ask("Nivel de experiencia", default="neutral", choices=["principiante", "neutral", "experto"] if RICH_AVAILABLE else None)
        selected = summarize_documents(documents, SummaryOptions(target_words=target_words, persona=persona, diversity=0.72))
        return f"# Resumen para leer en {minutes:g} minutos\n\n**Presupuesto estimado:** {target_words} palabras con {wpm} ppm.\n\n" + render_sentence_summary(selected, include_sources=len(documents) > 1)

    if mode == "words":
        target_words = IntPrompt.ask("Cantidad objetivo de palabras", default=350)
        selected = summarize_documents(documents, SummaryOptions(target_words=target_words, diversity=0.72))
        return f"# Resumen de aproximadamente {target_words} palabras\n\n" + render_sentence_summary(selected, include_sources=len(documents) > 1)

    if mode == "persona":
        persona = Prompt.ask("Nivel", default="principiante", choices=["principiante", "neutral", "experto"] if RICH_AVAILABLE else None)
        target_words = IntPrompt.ask("Cantidad objetivo de palabras", default=380)
        return persona_summary(documents, persona, target_words=target_words)

    if mode == "hierarchical":
        persona = Prompt.ask("Nivel de lectura", default="neutral", choices=["principiante", "neutral", "experto"] if RICH_AVAILABLE else None)
        return hierarchical_summary(documents, persona=persona)

    if mode == "query":
        query = Prompt.ask("¿Qué tema, cláusula o ángulo quieres resumir?")
        target_words = IntPrompt.ask("Cantidad objetivo de palabras", default=420)
        return query_based_summary(documents, query=query, target_words=target_words)

    if mode == "keywords":
        all_text = "\n\n".join(d.text for d in documents)
        phrases = [p for p, _ in extract_keyphrases(all_text, top_n=20)]
        console.print("\nPalabras clave detectadas:")
        for i, phrase in enumerate(phrases, start=1):
            console.print(f"{i}. {phrase}")
        raw = Prompt.ask("Elige números/palabras clave separadas por coma", default="1,2,3")
        indexes = parse_selection(raw, len(phrases))
        chosen = [phrases[i] for i in indexes]
        if not chosen:
            chosen = [x.strip() for x in raw.split(",") if x.strip()]
        target_words = IntPrompt.ask("Cantidad objetivo de palabras", default=420)
        return query_based_summary(documents, query=", ".join(chosen), keywords=chosen, target_words=target_words)

    if mode == "comparative":
        return comparative_summary(documents)

    if mode == "sentiment":
        return sentiment_analysis(documents)

    if mode == "faq":
        q = IntPrompt.ask("Número de preguntas", default=10)
        return generate_faq(documents, questions=q)

    if mode == "simple":
        target_words = IntPrompt.ask("Cantidad objetivo de palabras", default=260)
        return simple_explanation(documents, target_words=target_words)

    if mode == "concept":
        return concept_map(documents)

    if mode == "full":
        return full_report(documents)

    return hierarchical_summary(documents)


def full_report(documents: Sequence[Document]) -> str:
    parts = [hierarchical_summary(documents), "\n---\n", sentiment_analysis(documents), "\n---\n", generate_faq(documents, questions=8), "\n---\n", concept_map(documents)]
    if len(documents) > 1:
        parts.insert(0, comparative_summary(documents))
        parts.insert(1, "\n---\n")
    return "\n\n".join(parts)


# -----------------------------------------------------------------------------
# CLI no interactiva
# -----------------------------------------------------------------------------
def run_cli(args: argparse.Namespace) -> Path:
    extract_options = ExtractOptions(
        ocr=args.ocr,
        ocr_lang=args.ocr_lang,
        ocr_dpi=args.ocr_dpi,
        max_ocr_pages=args.max_ocr_pages,
    )
    paths = [Path(p).expanduser().resolve() for p in args.paths]
    documents = [extract_document(p, extract_options) for p in paths]
    mode = args.mode

    if mode == "time":
        minutes = args.minutes or 5
        wpm = args.wpm or DEFAULT_WPM
        target_words = int(minutes * wpm)
        selected = summarize_documents(documents, SummaryOptions(target_words=target_words, persona=args.persona, diversity=args.diversity))
        content = f"# Resumen para leer en {minutes:g} minutos\n\n**Presupuesto estimado:** {target_words} palabras con {wpm} ppm.\n\n" + render_sentence_summary(selected, include_sources=len(documents) > 1)
    elif mode == "words":
        target = args.words or 350
        selected = summarize_documents(documents, SummaryOptions(target_words=target, persona=args.persona, diversity=args.diversity))
        content = f"# Resumen de aproximadamente {target} palabras\n\n" + render_sentence_summary(selected, include_sources=len(documents) > 1)
    elif mode == "persona":
        content = persona_summary(documents, args.persona, target_words=args.words or 380)
    elif mode == "hierarchical":
        content = hierarchical_summary(documents, persona=args.persona)
    elif mode == "query":
        if not args.query:
            raise ValueError("El modo query requiere --query")
        keywords = [x.strip() for x in (args.keywords or "").split(",") if x.strip()]
        content = query_based_summary(documents, args.query, keywords=keywords, target_words=args.words or 420)
    elif mode == "comparative":
        content = comparative_summary(documents, target_words=args.words or 650)
    elif mode == "sentiment":
        content = sentiment_analysis(documents)
    elif mode == "faq":
        content = generate_faq(documents, questions=args.questions)
    elif mode == "simple":
        content = simple_explanation(documents, target_words=args.words or 260)
    elif mode == "concept":
        content = concept_map(documents)
    elif mode == "full":
        content = full_report(documents)
    else:
        raise ValueError(f"Modo desconocido: {mode}")

    outdir = Path(args.outdir).expanduser().resolve() if args.outdir else paths[0].parent
    base_name = documents[0].title if len(documents) == 1 else f"comparativo_{len(documents)}_archivos"
    return save_output(content, outdir, base_name, args.format, metadata={"mode": mode, "files": [str(p) for p in paths]})


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Resumidor Pro offline: resúmenes extractivos multi-formato sin IA generativa.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("paths", nargs="*", help="Archivo(s) a procesar. Si se omite, abre menú interactivo.")
    parser.add_argument(
        "--mode",
        choices=["time", "words", "persona", "hierarchical", "query", "comparative", "sentiment", "faq", "simple", "concept", "full"],
        default=None,
        help="Modo de resumen. Si se omite, abre menú interactivo.",
    )
    parser.add_argument("--minutes", type=float, default=None, help="Minutos disponibles para leer en modo time.")
    parser.add_argument("--wpm", type=int, default=DEFAULT_WPM, help="Palabras por minuto para modo time.")
    parser.add_argument("--words", type=int, default=None, help="Cantidad objetivo de palabras.")
    parser.add_argument("--persona", choices=["principiante", "neutral", "experto"], default="neutral")
    parser.add_argument("--query", default=None, help="Interés o pregunta para modo query.")
    parser.add_argument("--keywords", default=None, help="Palabras clave separadas por coma para priorizar.")
    parser.add_argument("--questions", type=int, default=10, help="Número de preguntas en modo FAQ.")
    parser.add_argument("--diversity", type=float, default=0.72, help="MMR lambda: más alto prioriza relevancia, más bajo diversidad.")
    parser.add_argument("--ocr", action="store_true", help="Usar OCR si un PDF parece escaneado.")
    parser.add_argument("--ocr-lang", default="spa+eng", help="Idiomas Tesseract, por ejemplo spa, eng, spa+eng.")
    parser.add_argument("--ocr-dpi", type=int, default=220, help="DPI para OCR de PDF.")
    parser.add_argument("--max-ocr-pages", type=int, default=None, help="Límite de páginas OCR para PDFs enormes.")
    parser.add_argument("--format", choices=["md", "txt", "json", "html"], default="md", help="Formato de salida.")
    parser.add_argument("--outdir", default=None, help="Carpeta de salida.")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if not args.paths or not args.mode:
            interactive()
            return 0
        output = run_cli(args)
        console.print(f"✅ Resumen guardado en: {output}" if not RICH_AVAILABLE else f"✅ Resumen guardado en: [bold]{output}[/bold]")
        return 0
    except KeyboardInterrupt:
        console.print("\nOperación cancelada.")
        return 130
    except Exception as exc:
        if RICH_AVAILABLE:
            console.print(f"[bold red]Error:[/bold red] {exc}")
        else:
            print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
