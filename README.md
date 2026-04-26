# Resumidor de texto (.txt, .docx, .pdf etc)

<img align="center" height="480" width="1000" alt="GIF" src="https://github.com/Yextep/Resu/assets/114537444/126d6e99-30ae-4715-90ae-efa4444d2370"/>


Herramienta offline en Python para extraer texto y generar resúmenes sin IA generativa ni APIs externas. Usa técnicas clásicas de procesamiento de texto: TF-IDF, TextRank, MMR, extracción de palabras clave, heurísticas por secciones y análisis léxico de tono.

## Formatos soportados

- Word OpenXML: `.docx`, `.docm`, `.dotx`
- Word legado: `.doc`, `.dot` usando LibreOffice o antiword si están instalados
- Texto: `.txt`, `.md`, `.rtf`, `.html`, `.htm`
- Lectura: `.pdf`, `.epub`

## Instalación

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### Dependencias del sistema para OCR y Word legado

OCR de PDF escaneado:
                                                                       - Instala Tesseract OCR.
- Instala Poppler para que `pdf2image` pueda convertir páginas PDF a imágenes.

Word `.doc` / `.dot` legado:

- Recomendado: instala LibreOffice y asegúrate de que el comando `soffice` o `libreoffice` esté en el PATH.
- Alternativa Linux/macOS: `antiword`.

## Uso interactivo

```bash
python resumidor_pro.py
```

El menú permite elegir archivo(s), modo de resumen, OCR opcional, formato de salida y carpeta destino.

## Uso por comandos

Resumen por tiempo disponible:

```bash
python resumidor_pro.py documento.pdf --mode time --minutes 5 --ocr --format md
```

Resumen por cantidad de palabras:

```bash
python resumidor_pro.py informe.docx --mode words --words 450
```

Resumen para principiante:

```bash
python resumidor_pro.py informe.pdf --mode persona --persona principiante --words 400
```

Resumen por ángulo de interés:

```bash
python resumidor_pro.py contrato.pdf --mode query --query "cláusulas de rescisión y multas" --words 500
```

Comparativo de varios archivos:

```bash
python resumidor_pro.py fuente1.pdf fuente2.epub fuente3.docx --mode comparative --words 800
```

Informe completo:

```bash
python resumidor_pro.py documento.md --mode full --format html
```

## Modos incluidos

- `time`: ajusta extensión por minutos y palabras por minuto.
- `words`: resumen por cantidad objetivo de palabras.
- `persona`: adapta selección y estructura para `principiante`, `neutral` o `experto`.
- `hierarchical`: titular, 3 puntos clave, resumen ejecutivo y resumen por secciones.
- `query`: enfoque por tema, cláusula, pregunta o ángulo de interés.
- `comparative`: síntesis comparativa de varios documentos, puntos comunes, aportes únicos y posibles contradicciones.
- `sentiment`: tono y sentimiento con léxico local.
- `faq`: preguntas frecuentes generadas desde palabras clave.
- `simple`: explicación simple basada en frases claras del documento.
- `concept`: mapa conceptual Mermaid y tabla de términos.
- `full`: informe con varios módulos combinados.

## Limitaciones honestas

Este proyecto no usa IA generativa. Por eso no "entiende" como un LLM ni redacta paráfrasis profundas. En su lugar, selecciona, ordena y estructura las mejores frases del documento. Las contradicciones, el tono y las palabras clave son heurísticas: útiles para exploración, no una verificación jurídica, científica o contable definitiva.
