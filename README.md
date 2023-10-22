# Resumidor de texto (.txt, .docx, .pdf)

Este script utiliza **gensim** para generar resúmenes de mejor calidad y también es capaz de procesar archivos **PDF** utilizando **pytesseract** para extraer texto de los documentos **PDF**. Al momento de ejecutarlo solicita al usuario la ubicación del archivo, sino está en una ruta en específico entonces asume que está en la ruta actual. Luego lista los archivos disponibles en esa ubicación, después permite al usuario seleccionar un archivo y luego resume ese archivo. El resúmen se guarda en un nuevo archivo de texto en la misma ubicación.

**Resu.py** permite al usuario ingresar la cantidad de sentencias que desea incluir en el resúmen, el resúmen se generará según el número de sentencias ingresadas por el usuario. Esto proporciona una mayor flexibilidad en la generación de resúmenes de documentos de texto.

<img align="center" height="480" width="1000" alt="GIF" src="https://github.com/Yextep/Resu/assets/114537444/126d6e99-30ae-4715-90ae-efa4444d2370"/>


## Instalación

Clonamos el repositorio
```bash
git clone https://github.com/Yextep/Resu
```
Accedemos a la carpeta
```bash
cd Resu
```
Instalamos requerimientos
```bash
pip install -r requeriments.txt
```
Ejecutamos el Script
```bash
python3 resu.py
```
