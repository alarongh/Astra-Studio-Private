from __future__ import annotations

import ast
import re
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class PythonLibrary:
    import_name: str
    pip_name: str
    display_name: str
    category: str
    description: str
    safe: bool = True
    size: str = "normal"
    aliases: tuple[str, ...] = ()
    warning: str = ""
    experimental: bool = False

    def as_record(self) -> dict:
        warning = self.warning
        if not warning and self.size == "large":
            warning = "Библиотека может устанавливаться несколько минут и занимать много места."
        return {
            "import": self.import_name,
            "package": self.pip_name,
            "import_name": self.import_name,
            "pip_name": self.pip_name,
            "display_name": self.display_name,
            "category": self.category,
            "description": self.description,
            "safe": self.safe,
            "size": self.size,
            "heavy": self.size == "large",
            "warning": warning,
            "aliases": list(self.aliases),
            "experimental": self.experimental,
        }


_LIBRARY_DEFINITIONS: list[PythonLibrary] = [
    # Astra / service packages
    PythonLibrary("PyInstaller", "pyinstaller", "PyInstaller", "Сборка EXE", "Сборка Python-скриптов в EXE.", warning="Создаёт исполняемые файлы. Собирайте только свой код."),
    PythonLibrary("PySide6", "PySide6", "PySide6", "GUI", "Оконные приложения на Qt.", size="large"),
    PythonLibrary("pytest", "pytest", "pytest", "Тестирование", "Запуск тестов Python-кода."),
    PythonLibrary("colorama", "colorama", "colorama", "Учебные", "Цветной вывод в консоли."),
    PythonLibrary("sqlalchemy", "SQLAlchemy", "SQLAlchemy", "Базы данных", "Работа с базами данных через ORM."),

    # Data Science / math
    PythonLibrary("numpy", "numpy", "NumPy", "Math / Data Science", "Массивы, матрицы и численные вычисления."),
    PythonLibrary("pandas", "pandas", "Pandas", "Data Science", "Таблицы, CSV/Excel, анализ данных."),
    PythonLibrary("scipy", "scipy", "SciPy", "Scientific Computing", "Научные вычисления, оптимизация, иерархическая кластеризация.", size="large"),
    PythonLibrary("sklearn", "scikit-learn", "Scikit-learn", "Machine Learning", "Машинное обучение: классификация, регрессия, кластеризация.", size="large", aliases=("scikit_learn", "scikit-learn")),
    PythonLibrary("statsmodels", "statsmodels", "Statsmodels", "Data Science", "Статистические модели и эконометрика."),
    PythonLibrary("sympy", "sympy", "SymPy", "Math / Data Science", "Символьная математика."),
    PythonLibrary("joblib", "joblib", "joblib", "Machine Learning", "Кэширование и параллельные вычисления, часто используется вместе со scikit-learn."),

    # Visualization
    PythonLibrary("matplotlib", "matplotlib", "Matplotlib", "Visualization", "Графики и визуализация данных."),
    PythonLibrary("seaborn", "seaborn", "Seaborn", "Visualization", "Статистические графики поверх Matplotlib."),
    PythonLibrary("plotly", "plotly", "Plotly", "Visualization", "Интерактивные графики.", size="large"),

    # Images
    PythonLibrary("PIL", "Pillow", "Pillow", "Изображения", "Работа с изображениями: открытие, сохранение, преобразование.", aliases=("pillow",)),
    PythonLibrary("cv2", "opencv-python", "OpenCV", "Изображения", "Компьютерное зрение и обработка изображений.", size="large", aliases=("opencv", "opencv_python")),

    # Web / parsing
    PythonLibrary("requests", "requests", "Requests", "Web / парсинг", "HTTP-запросы."),
    PythonLibrary("bs4", "beautifulsoup4", "BeautifulSoup4", "Web / парсинг", "Парсинг HTML/XML.", aliases=("beautifulsoup4", "beautifulsoup")),
    PythonLibrary("lxml", "lxml", "lxml", "Web / парсинг", "Быстрый XML/HTML-парсер."),
    PythonLibrary("html5lib", "html5lib", "html5lib", "Web / парсинг", "HTML5-парсер."),

    # Documents / Excel / reports
    PythonLibrary("openpyxl", "openpyxl", "openpyxl", "Документы / Excel", "Чтение и запись Excel .xlsx."),
    PythonLibrary("docx", "python-docx", "python-docx", "Документы / Excel", "Создание и редактирование Word .docx.", aliases=("python_docx", "python-docx")),
    PythonLibrary("pptx", "python-pptx", "python-pptx", "Документы / Excel", "Создание и редактирование PowerPoint .pptx.", aliases=("python_pptx", "python-pptx")),
    PythonLibrary("reportlab", "reportlab", "ReportLab", "Документы / Excel", "Генерация PDF-отчётов."),
    PythonLibrary("fpdf", "fpdf2", "fpdf2", "Документы / Excel", "Простая генерация PDF.", aliases=("fpdf2",)),

    # Automation / GUI
    PythonLibrary("pyperclip", "pyperclip", "pyperclip", "Автоматизация", "Работа с буфером обмена."),
    PythonLibrary("pynput", "pynput", "pynput", "Автоматизация", "Управление клавиатурой и мышью.", warning="Может имитировать нажатия клавиш."),
    PythonLibrary("pyautogui", "pyautogui", "PyAutoGUI", "Автоматизация", "Автоматизация мыши, клавиатуры и скриншотов.", warning="Может управлять мышью и клавиатурой."),

    # Games / web apps
    PythonLibrary("pygame", "pygame", "pygame", "Игры / учебные проекты", "2D-игры и мультимедиа."),
    PythonLibrary("flask", "flask", "Flask", "Web-приложения", "Лёгкий web-фреймворк."),
    PythonLibrary("fastapi", "fastapi", "FastAPI", "Web-приложения", "Современный web/API-фреймворк."),
    PythonLibrary("uvicorn", "uvicorn", "Uvicorn", "Web-приложения", "ASGI-сервер для FastAPI и других приложений."),

    # Configs / env
    PythonLibrary("dotenv", "python-dotenv", "python-dotenv", "Конфиги / env", "Загрузка переменных окружения из .env.", aliases=("python_dotenv", "python-dotenv")),
    PythonLibrary("yaml", "PyYAML", "PyYAML", "Конфиги / env", "Чтение и запись YAML-конфигов.", aliases=("pyyaml",)),

    # Audio
    PythonLibrary("pydub", "pydub", "pydub", "Аудио", "Базовая работа с аудиофайлами."),
    PythonLibrary("soundfile", "soundfile", "soundfile", "Аудио", "Чтение и запись аудиофайлов."),

    # Heavy / experimental: visible in registry, but never installed as default set.
    PythonLibrary("torch", "torch", "PyTorch", "Экспериментальные / тяжёлые", "Глубокое обучение. Очень крупный пакет.", safe=False, size="large", experimental=True, warning="Не устанавливается автоматически. Очень тяжёлый пакет."),
    PythonLibrary("tensorflow", "tensorflow", "TensorFlow", "Экспериментальные / тяжёлые", "Глубокое обучение. Очень крупный пакет.", safe=False, size="large", experimental=True, warning="Не устанавливается автоматически. Используйте только при понимании требований."),
    PythonLibrary("jax", "jax", "JAX", "Экспериментальные / тяжёлые", "Численные вычисления и ML на ускорителях.", safe=False, size="large", experimental=True, warning="Не устанавливается автоматически. Используйте только при понимании требований."),
    PythonLibrary("transformers", "transformers", "Transformers", "Экспериментальные / тяжёлые", "Модели NLP/LLM. Может тянуть крупные зависимости.", safe=False, size="large", experimental=True, warning="Не устанавливается автоматически. Используйте только при понимании требований."),
]

PYTHON_LIBRARY_REGISTRY: list[dict] = [library.as_record() for library in _LIBRARY_DEFINITIONS]


def _normalize_key(name: str) -> str:
    return (name or "").strip().lower().replace("-", "_")


PYTHON_IMPORT_TO_PACKAGE: dict[str, dict] = {}
for item in PYTHON_LIBRARY_REGISTRY:
    keys = {
        item["import_name"],
        item["pip_name"],
        item["import"],
        item["package"],
        item["pip_name"].replace("-", "_"),
        item["package"].replace("-", "_"),
        *(item.get("aliases") or []),
    }
    for key in keys:
        if key:
            PYTHON_IMPORT_TO_PACKAGE[_normalize_key(key)] = item
            PYTHON_IMPORT_TO_PACKAGE[key.strip().lower()] = item

EXPLICIT_STDLIB_MODULES = {
    "os", "sys", "math", "random", "time", "datetime", "json", "csv", "pathlib", "subprocess",
    "threading", "multiprocessing", "queue", "re", "collections", "itertools", "functools", "typing",
    "tkinter", "sqlite3", "statistics", "decimal", "fractions", "urllib", "http", "email", "logging",
    "traceback", "shutil", "tempfile", "glob", "platform", "socket", "asyncio", "argparse", "copy",
    "dataclasses", "enum", "hashlib", "hmac", "inspect", "io", "pickle", "pprint", "string", "uuid",
    "zipfile", "tarfile", "gzip", "bz2", "lzma", "base64", "xml", "html", "unittest", "venv", "site",
}
PYTHON_STDLIB_MODULES = set(EXPLICIT_STDLIB_MODULES)
PYTHON_STDLIB_MODULES.update(getattr(sys, "stdlib_module_names", set()))
PYTHON_STDLIB_MODULES.update(sys.builtin_module_names)

LIBRARY_BUNDLES: dict[str, list[str]] = {
    "Учебный минимум": ["numpy", "matplotlib", "pandas"],
    "ИИ / машинное обучение": ["numpy", "pandas", "matplotlib", "scipy", "sklearn", "joblib"],
    "Анализ данных": ["numpy", "pandas", "matplotlib", "seaborn", "scipy", "statsmodels", "plotly"],
    "Документы и Excel": ["openpyxl", "docx", "pptx", "reportlab"],
    "Парсинг сайтов": ["requests", "bs4", "lxml", "html5lib"],
    "Автоматизация": ["pyperclip", "pynput", "pyautogui"],
}


def is_standard_module(module_name: str) -> bool:
    top = (module_name or "").split(".", 1)[0].strip()
    return bool(top and top in PYTHON_STDLIB_MODULES)


def package_record(module_or_package: str) -> dict | None:
    key = _normalize_key(module_or_package)
    if key in PYTHON_IMPORT_TO_PACKAGE:
        return PYTHON_IMPORT_TO_PACKAGE[key]
    return PYTHON_IMPORT_TO_PACKAGE.get(key.replace("_", "-"))


def top_level_module(name: str) -> str:
    return (name or "").split(".", 1)[0].strip()


def extract_python_imports(source_code: str) -> list[str]:
    """Return top-level modules imported in Python code.

    Supports import x, import x.y as z, from x.y import z. Imports inside any
    scope are included intentionally: a missing dependency is still a dependency.
    """
    modules: list[str] = []
    seen: set[str] = set()

    def add(name: str):
        top = top_level_module(name)
        if not top or top in seen:
            return
        seen.add(top)
        modules.append(top)

    try:
        tree = ast.parse(source_code or "")
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                # Relative imports refer to the current project/package, not to a PyPI dependency.
                # Treating `from .utils import x` as a missing third-party module can lead Astra
                # to offer an unrelated package installation.
                if node.level:
                    continue
                if node.module:
                    add(node.module)
        return modules
    except SyntaxError:
        # Fallback for incomplete code: enough to catch common forms before run.
        pass

    import_re = re.compile(r"^\s*import\s+([^#\n]+)", re.MULTILINE)
    from_re = re.compile(r"^\s*from\s+([A-Za-z_][\w.]*)\s+import\s+", re.MULTILINE)
    for match in import_re.finditer(source_code or ""):
        parts = match.group(1).split(",")
        for part in parts:
            add(part.strip().split()[0])
    for match in from_re.finditer(source_code or ""):
        add(match.group(1))
    return modules


def records_for_bundle(bundle_name: str) -> list[dict]:
    records: list[dict] = []
    for import_name in LIBRARY_BUNDLES.get(bundle_name, []):
        record = package_record(import_name)
        if record and record.get("safe", True):
            records.append(record)
    return records
