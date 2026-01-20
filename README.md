# Document Auditor

**Document Auditor** es una herramienta basada en Streamlit para visualizar dependencias entre documentos legales y realizar auditorías de cumplimiento automatizadas. Permite cargar documentos de texto, visualizar sus relaciones en un grafo interactivo y verificar si cumplen con las obligaciones estipuladas en sus documentos rectores.

## Características Principales

### 1. Árbol de Dependencias (Grafo de Conocimiento)
- Visualización interactiva de documentos como nodos.
- Enlaces automáticos basados en referencias encontradas en el texto (ej. "Ley N° 31814").
- Interfaz "Drag & Drop" para explorar la red de documentos.

### 2. Lectura Inteligente y Auditoría
- **Análisis de Cumplimiento**: Extrae automáticamente "Reglas" (Obligaciones y Prohibiciones) de los documentos rectores.
- **Sistema de Semáforo**:
    - 🟢 **Cumple**: El documento auditado menciona o trata el tema de la regla.
    - 🟡 **Parcial/Ambiguo**: Coincidencia baja.
    - 🔴 **No Encontrado**: Posible incumplimiento o falta de mención.
    - ⚪ **Desconocido**: No se pudo determinar.

## Instalación

1.  Asegúrate de tener Python instalado.
2.  Instala las dependencias:
    ```bash
    pip install -r requirements.txt
    ```

## Uso

1.  Coloca tus archivos **.txt** en la carpeta `documentos`.
2.  Ejecuta la aplicación:
    ```bash
    streamlit run app.py
    ```
3.  En la barra lateral, haz clic en **"Escanear Documentos"** para procesar los archivos nuevos.
4.  Navega entre la vista de **Grafo** y la vista de **Auditoría**.

## Estructura del Proyecto

- `app.py`: Interfaz de usuario (Streamlit).
- `processor.py`: Lógica de extracción de texto, dependencias y reglas.
- `database.py`: Gestión de la base de datos SQLite.
- `documentos/`: Carpeta para los archivos fuente.
