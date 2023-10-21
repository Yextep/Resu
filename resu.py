import os
import docx2txt
import PyPDF2
import pytesseract
from nltk import sent_tokenize
from gensim.summarization import summarize

# Función para resumir un documento de texto
def summarize_text(text, num_sentences):
    text = ' '.join(text.split())  # Eliminar espacios en blanco y saltos de línea
    sentences = sent_tokenize(text)
    if num_sentences >= len(sentences):
        return ' '.join(sentences)
    summary = ' '.join(sentences[:num_sentences])
    return summary

# Asegurarse de que el párrafo termine en un punto.
def ensure_ending_period(paragraph):
    if paragraph and paragraph[-1] != '.':
        paragraph += '.'
    return paragraph

# Preguntar al usuario la ubicación del archivo
file_path = input("Por favor, ingrese la ubicación del archivo (o deje en blanco si está en la ruta actual): ").strip()

if not file_path:
    file_path = os.getcwd()

# Listar los archivos en la ubicación proporcionada
files = [f for f in os.listdir(file_path) if f.endswith(('.docx', '.pdf', '.txt'))]

if not files:
    print("No se encontraron archivos .docx, .pdf o .txt en la ubicación proporcionada.")
else:
    # Mostrar los archivos disponibles para que el usuario seleccione
    print("Archivos disponibles:")
    for i, file in enumerate(files):
        print(f"{i + 1}. {file}")

    # Pedir al usuario que seleccione un archivo
    selected_index = None
    while selected_index is None:
        user_input = input("Por favor, seleccione el número del archivo que desea resumir: ")
        if user_input.isdigit():
            selected_index = int(user_input) - 1
        else:
            print("Por favor, ingrese un número válido.")

    if 0 <= selected_index < len(files):
        selected_file = files[selected_index]
        file_extension = os.path.splitext(selected_file)[-1]

        # Preguntar al usuario cuántas sentencias desea incluir en el resumen
        num_sentences = int(input("Por favor, ingrese la cantidad de sentencias para el resumen: "))

        # Leer y resumir el contenido del archivo
        if file_extension == '.docx':
            text = docx2txt.process(os.path.join(file_path, selected_file))
            summary = summarize_text(text, num_sentences)
        elif file_extension == '.pdf':
            pdf_path = os.path.join(file_path, selected_file)
            pdf_text = ''
            with open(pdf_path, 'rb') as pdf_file:
                pdf_reader = PyPDF2.PdfFileReader(pdf_file)
                for page in range(pdf_reader.numPages):
                    pdf_text += pdf_reader.getPage(page).extractText()
            summary = summarize_text(pdf_text, num_sentences)
        elif file_extension == '.txt':
            with open(os.path.join(file_path, selected_file), 'r', encoding='utf-8') as file:
                text = file.read()
                summary = summarize_text(text, num_sentences)

        # Separar el resumen en tres párrafos con dos líneas en blanco
        summary_paragraphs = summary.split('. ')
        paragraph_size = len(summary_paragraphs) // 3
        paragraphs = [" ".join(summary_paragraphs[i:i + paragraph_size]) for i in range(0, len(summary_paragraphs), paragraph_size)]

        # Asegurarse de que el último carácter de cada párrafo sea un punto (.)
        paragraphs = [ensure_ending_period(paragraph) for paragraph in paragraphs]

        # Unir los párrafos con dos líneas en blanco
        final_summary = "\n\n".join(paragraphs)

        # Guardar el resumen en un nuevo archivo de texto
        output_file = f"resumen_{selected_file}"
        with open(os.path.join(file_path, output_file), 'w', encoding='utf-8') as file:
            file.write(final_summary)

        print(f"El resumen se ha guardado en '{output_file}'.")

    else:
        print("Número de archivo seleccionado fuera de rango.")
