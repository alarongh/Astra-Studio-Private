import ast
from bisect import bisect_right
import datetime
import html
import json
import keyword
import os
import py_compile
import re
import shutil
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

try:
    from PySide6.QtCore import (
        Qt,
        QSize,
        QRect,
        QProcess,
        QProcessEnvironment,
        QRegularExpression,
        QByteArray,
        QUrl,
        QTimer,
        QStandardPaths,
        QStringListModel,
    )
    from PySide6.QtGui import (
        QColor,
        QDesktopServices,
        QFont,
        QFontDatabase,
        QKeySequence,
        QPainter,
        QShortcut,
        QSyntaxHighlighter,
        QTextCharFormat,
        QTextCursor,
        QTextFormat,
        QIcon,
        QPixmap,
    )
    from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
    from PySide6.QtWidgets import (
        QApplication,
        QDialog,
        QFileDialog,
        QFileSystemModel,
        QFrame,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QMainWindow,
        QMessageBox,
        QPlainTextEdit,
        QTextEdit,
        QPushButton,
        QComboBox,
        QSplitter,
        QStatusBar,
        QTabWidget,
        QTreeView,
        QVBoxLayout,
        QWidget,
        QSlider,
        QCheckBox,
        QProgressBar,
        QStackedWidget,
        QScrollArea,
        QSizePolicy,
        QTableWidget,
        QTableWidgetItem,
        QHeaderView,
        QAbstractItemView,
        QGraphicsBlurEffect,
        QInputDialog,
        QTreeWidget,
        QTreeWidgetItem,
        QMenu,
        QToolTip,
        QCompleter,
    )
except ImportError as exc:
    print("PySide6 не установлен.")
    print("Установи зависимости: python -m pip install -r requirements.txt")
    raise exc

from core.task_manager import ProcessTaskSpec, TaskManager
from core.lsp_transport import LspManager
from core.lsp_protocol import uri_to_path
from core.lsp_servers import install_plan_for_language
from core.lsp_features import (
    apply_text_edits,
    hover_text,
    normalize_completion_items,
    normalize_document_symbols,
    normalize_locations,
    normalize_workspace_edit,
    signature_help_text,
    workspace_edit_has_resource_operations,
)
from core.python_environment import detect_project_environment
from core.quality_tools import (
    formatter_command,
    formatter_tool_for_language,
    install_plan_for_quality_tool,
    linter_command,
    linter_tool_for_language,
    parse_linter_output,
)
from core.language_completion import CompletionItem, CompletionTextEdit, completion_query
from core.java_runtime import discover_java_runtime, java_arguments, javac_arguments, java_version
from core.project_commands import COMMAND_KEYS, detect_project_commands, merge_project_commands, normalize_commands
from core.project_doctor import inspect_project
from core.staffedup_health import apply_safe_staffedup_fixes, inspect_staffedup_project
from core.ai_context import (
    CONTEXT_FILENAME,
    DEFAULT_MAX_FILE_BYTES,
    ProjectRoot,
    build_project_context,
    build_project_tree,
    format_problem_records,
    format_selected_text_with_line_numbers,
    is_sensitive_context_path,
    normalize_roots,
    project_path_label,
    truncate_output,
    write_project_context,
)
from core.project_paths import portable_attached_folders, portable_project_path
from core.window_behavior import apply_topmost_hint
from core.project_templates import (
    create_project_from_template,
    get_project_template,
    project_template_choices,
    rendered_template_files,
)
from core.test_explorer import (
    build_test_command,
    detect_test_adapters,
    discover_tests,
    parse_test_output,
    restore_test_run,
)
from core.git_tools import (
    GitRepositoryState,
    commit_command,
    diff_command,
    git_executable,
    parse_porcelain_v2_z,
    parse_repo_root,
    probe_repository_command,
    pull_command,
    push_command,
    stage_command,
    status_command,
    unstage_command,
)
from core.log_file import append_utf8_bom_log, ensure_utf8_bom_log
from core.app_updates import (
    configured_manifest_url,
    is_newer_release,
    parse_update_manifest,
    verify_update_archive,
    windows_update_script,
)
from core.python_library_registry import (
    LIBRARY_BUNDLES,
    PYTHON_IMPORT_TO_PACKAGE,
    PYTHON_LIBRARY_REGISTRY,
    extract_python_imports,
    is_standard_module,
    package_record,
    records_for_bundle,
)


APP_NAME = "Astra Studio"
APP_VERSION = "Release 3.13"
WINDOWS_APP_USER_MODEL_ID = "Astra.Studio.Alaron"
APP_DIR_NAME = "AstralStudio"
DEFAULT_LANGUAGE = "Python"
DEFAULT_THEME = "Astra: Корона кода"
DEFAULT_ACCENT = "Astra красно-синий"
DEFAULT_PRESET_WALLPAPER = "Astra Cyber Ritual"
DEFAULT_GLOBAL_FONT = "Системный (Segoe UI)"
ANGEL_404_THEME = "Angel 404: Фиолетовый сбой"
ANGEL_404_ACCENT = "Angel 404 неон"
ANGEL_404_WALLPAPER = "Angel 404"
SHORTCUT_ICON_OPTIONS = {
    "Astra 3.13 — красно-синий": "assets/astra.ico",
    "Angel 404 — фиолетовый неон": "assets/astra_angel404.ico",
    "Astra Legacy — тёмная корона": "assets/legacy_astra.ico",
}
FALLBACK_BACKGROUND = "#1E1E1E"
CURSOR_MARKER = "§CURSOR§"

PYTHON_TEMPLATE = '''def main():
    print("Hello, Astra Studio")


if __name__ == "__main__":
    main()
'''

CPP_TEMPLATE = '''// Astra Studio — стартовый шаблон C++.
// Для запуска нужен установленный компилятор g++ или clang++.

#include <iostream>
#include <string>

using namespace std;

int main() {
    string name;
    cout << "Введите имя: ";
    getline(cin, name);

    cout << "Привет, " << name << "!" << endl;
    cout << "C++ программа успешно запущена из Astra Studio." << endl;
    return 0;
}
'''

JAVA_TEMPLATE = '''// Astra Studio — стартовый шаблон Java.
// Для запуска нужен установленный JDK: javac и java.

import java.util.Scanner;

public class Main {
    public static void main(String[] args) {
        Scanner scanner = new Scanner(System.in);

        System.out.print("Введите имя: ");
        String name = scanner.nextLine();

        System.out.println("Привет, " + name + "!");
        System.out.println("Java программа успешно запущена из Astra Studio.");
    }
}
'''

HTML_TEMPLATE = '''<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Astra Studio</title>
    <link rel="stylesheet" href="style.css">
</head>
<body>
    <main class="card">
        <p class="eyebrow">Astra Studio</p>
        <h1>Привет, разработчик!</h1>
        <p>Это стартовый HTML-шаблон. Нажми F5, чтобы открыть страницу в браузере.</p>
        <button>Начать</button>
    </main>
</body>
</html>
'''

CSS_TEMPLATE = '''/* Astra Studio — стартовый шаблон CSS. */

:root {
    --bg: #080d16;
    --card: #101b2d;
    --text: #eef4ff;
    --muted: #7c8ba3;
    --accent: #ff2d6f;
}

* {
    box-sizing: border-box;
}

body {
    min-height: 100vh;
    margin: 0;
    display: grid;
    place-items: center;
    background: radial-gradient(circle at 20% 10%, #17233a, var(--bg) 55%);
    color: var(--text);
    font-family: Inter, Segoe UI, Arial, sans-serif;
}

.card {
    width: min(520px, 92vw);
    padding: 42px;
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 28px;
    background: rgba(16, 27, 45, 0.82);
    box-shadow: 0 24px 90px rgba(0, 0, 0, 0.38);
}

.eyebrow {
    color: var(--accent);
    letter-spacing: 0.18em;
    text-transform: uppercase;
    font-weight: 800;
}

button {
    margin-top: 18px;
    padding: 12px 18px;
    border: 0;
    border-radius: 14px;
    background: var(--accent);
    color: var(--bg);
    font-weight: 900;
}
'''


JAVASCRIPT_TEMPLATE = '''// Astra Studio — стартовый шаблон JavaScript.
// Для запуска нужен Node.js, если хочешь выполнять JS вне браузера.

function greet(name) {
    return `Привет, ${name}!`;
}

const name = "alaron";
console.log(greet(name));
console.log("JavaScript файл готов к запуску из Astra Studio.");
'''

CSHARP_TEMPLATE = '''// Astra Studio — стартовый шаблон C#.
// Для запуска нужен .NET SDK.

using System;

class Program
{
    static void Main(string[] args)
    {
        Console.Write("Введите имя: ");
        string? name = Console.ReadLine();

        Console.WriteLine($"Привет, {name}!");
        Console.WriteLine("C# программа успешно запущена из Astra Studio.");
    }
}
'''

SQL_TEMPLATE = '''-- Astra Studio — стартовый шаблон SQL.
-- SQL-файлы редактируются и проверяются как текст; подключение к СУБД настраивается отдельно.

SELECT column_name
FROM table_name
WHERE condition;
'''


TYPESCRIPT_TEMPLATE = '''// Astra Studio — стартовый шаблон TypeScript.
// Для запуска рекомендуется Node.js + tsx; для проверки — TypeScript (tsc).

interface User {
    name: string;
    role: string;
}

function greet(user: User): string {
    return `Привет, ${user.name}! Роль: ${user.role}.`;
}

const user: User = { name: "StaffedUp", role: "developer" };
console.log(greet(user));
'''

LUAU_TEMPLATE = '''-- Astra Studio — стартовый шаблон Luau.
-- Luau используется в Roblox. Для локального запуска нужен Luau CLI.

local function greet(name: string): string
    return `Привет, {name}!`
end

print(greet("StaffedUp"))
'''

GDSCRIPT_TEMPLATE = '''# Astra Studio — стартовый шаблон GDScript для Godot 4.x.
extends Node

func _ready() -> void:
    print("Привет из Astra Studio + Godot!")
'''

PHP_TEMPLATE = '''<?php
// Astra Studio — стартовый шаблон PHP.

function greet(string $name): string {
    return "Привет, {$name}!";
}

echo greet("StaffedUp") . PHP_EOL;
'''

POWERSHELL_TEMPLATE = '''# Astra Studio — стартовый шаблон PowerShell.
param(
    [string]$Name = "StaffedUp"
)

Write-Host "Привет, $Name!"
'''

JSON_TEMPLATE = '''{
  "name": "astra-project",
  "version": "1.0.0",
  "enabled": true
}
'''

YAML_TEMPLATE = '''name: astra-project
version: 1.0.0
enabled: true
'''

MARKDOWN_TEMPLATE = '''# Новый документ

Создан в Astra Studio.

## Задачи

- [ ] Первая задача
'''

TOML_TEMPLATE = '''name = "astra-project"
version = "1.0.0"
enabled = true
'''

XML_TEMPLATE = '''<?xml version="1.0" encoding="UTF-8"?>
<project>
    <name>Astra Studio</name>
    <team>StaffedUp</team>
</project>
'''

SHELL_TEMPLATE = '''#!/usr/bin/env bash
set -euo pipefail

echo "Привет из Astra Studio"
'''

DOCKERFILE_TEMPLATE = '''FROM python:3.12-slim

WORKDIR /app
COPY . .

CMD ["python", "main.py"]
'''

ENTER_TYPER_TEMPLATE = r'''# Astra Studio Template: Имитация ввода
# Скрипт имитирует нажатия клавиш. Используйте его только в своих окнах и с понятной целью.

import time
import random
import sys
from dataclasses import dataclass
from typing import Optional

from pynput.keyboard import Controller, Key

try:
    import pyperclip as clipboard
except ImportError:
    print("Ошибка: требуется библиотека 'pyperclip'.")
    print("Установите её командой:")
    print("python -m pip install pyperclip")
    sys.exit(1)


@dataclass
class TypingConfig:
    start_delay: float = 5.0
    min_delay: float = 0.06
    max_delay: float = 0.15
    long_delay_chance: float = 0.10
    long_delay_min: float = 0.30
    long_delay_max: float = 0.80
    typos_enabled: bool = False
    typo_chance: float = 0.03
    fix_typos: bool = True
    convert_four_spaces_to_tab: bool = True
    fix_delay_min: float = 0.20
    fix_delay_max: float = 0.40
    newline_delay_min: float = 0.40
    newline_delay_max: float = 0.90


class EnterTyper:
    def __init__(self):
        self.keyboard = Controller()
        self.cached_text = ""
        self.config = TypingConfig()
        self.key_map = {
            "q": "w", "w": "e", "e": "r", "r": "t", "t": "y", "y": "u", "u": "i", "i": "o", "o": "p",
            "a": "s", "s": "d", "d": "f", "f": "g", "g": "h", "h": "j", "j": "k", "k": "l",
            "z": "x", "x": "c", "c": "v", "v": "b", "b": "n", "n": "m",
            "й": "ц", "ц": "у", "у": "к", "к": "е", "е": "н", "н": "г", "г": "ш", "ш": "щ", "щ": "з", "з": "х",
            "ф": "ы", "ы": "в", "в": "а", "а": "п", "п": "р", "р": "о", "о": "л", "л": "д", "д": "ж", "ж": "э",
            "я": "ч", "ч": "с", "с": "м", "м": "и", "и": "т", "т": "ь", "ь": "б", "б": "ю",
        }

    def ask_yes_no(self, text: str, default: bool) -> bool:
        default_text = "Y/n" if default else "y/N"
        while True:
            answer = input(f"{text} [{default_text}]: ").strip().lower()
            if not answer:
                return default
            if answer in ("y", "yes", "д", "да"):
                return True
            if answer in ("n", "no", "н", "нет"):
                return False
            print("Введите y/n или да/нет.")

    def ask_float(self, text: str, default: float, min_value: Optional[float] = None, max_value: Optional[float] = None) -> float:
        while True:
            answer = input(f"{text} [{default}]: ").strip().replace(",", ".")
            if not answer:
                return default
            try:
                value = float(answer)
                if min_value is not None and value < min_value:
                    print(f"Значение не может быть меньше {min_value}.")
                    continue
                if max_value is not None and value > max_value:
                    print(f"Значение не может быть больше {max_value}.")
                    continue
                return value
            except ValueError:
                print("Введите число.")

    def choose_config_mode(self) -> str:
        print("=== РЕЖИМ НАСТРОЕК ===")
        print("1. Дефолтные настройки — безопасные значения без лишних вопросов")
        print("2. Расширенные настройки — задержки, опечатки и дополнительные параметры")
        while True:
            answer = input("Выберите режим [1/2, по умолчанию 1]: ").strip().lower()
            if answer in ("", "1", "default", "дефолт", "д"):
                return "default"
            if answer in ("2", "advanced", "расширенные", "р"):
                return "advanced"
            print("Введите 1 для дефолтных настроек или 2 для расширенных.")

    def configure(self):
        print("=== НАСТРОЙКА ПЕЧАТИ ===")
        mode = self.choose_config_mode()
        if mode == "default":
            print("Используются дефолтные настройки: безопасная скорость, Tab вместо 4 пробелов, опечатки выключены.")
            print()
            return

        print("=== РАСШИРЕННЫЕ НАСТРОЙКИ ===")
        self.config.typos_enabled = self.ask_yes_no("Включить опечатки?", self.config.typos_enabled)
        if self.config.typos_enabled:
            typo_percent = self.ask_float("Шанс опечатки в процентах, рекомендованная", self.config.typo_chance * 100, min_value=0, max_value=100)
            self.config.typo_chance = typo_percent / 100
            self.config.fix_typos = self.ask_yes_no("Исправлять опечатки через Backspace?", self.config.fix_typos)
        self.config.convert_four_spaces_to_tab = self.ask_yes_no("Заменять каждые 4 пробела на Tab?", self.config.convert_four_spaces_to_tab)
        self.config.start_delay = self.ask_float("Какую задержку перед началом печати вы хотите поставить, рекомендованная", self.config.start_delay, min_value=0)
        self.config.min_delay = self.ask_float("Какую минимальную задержку между символами вы хотите поставить, рекомендованная", self.config.min_delay, min_value=0)
        self.config.max_delay = self.ask_float("Какую максимальную задержку между символами вы хотите поставить, рекомендованная", self.config.max_delay, min_value=0)
        if self.config.max_delay < self.config.min_delay:
            print("Максимальная задержка была меньше минимальной — значения автоматически выровнены.")
            self.config.max_delay = self.config.min_delay
        print()

    def capture_clipboard(self) -> bool:
        try:
            content = clipboard.paste()
            if not content or not content.strip():
                return False
            self.cached_text = content
            return True
        except Exception as error:
            print(f"Ошибка чтения буфера обмена: {error}")
            return False

    def normalize_clipboard_text(self):
        text = self.cached_text

        # Приводим переносы строк к единому виду
        text = text.replace("\r\n", "\n").replace("\r", "\n")

        # Заменяем каждые 4 подряд идущих пробела на один символ табуляции
        if self.config.convert_four_spaces_to_tab:
            text = text.replace("    ", "\t")

        self.cached_text = text

    def get_human_delay(self) -> float:
        if random.random() < self.config.long_delay_chance:
            return random.uniform(self.config.long_delay_min, self.config.long_delay_max)
        return random.uniform(self.config.min_delay, self.config.max_delay)

    def get_wrong_char(self, char: str) -> Optional[str]:
        lower = char.lower()
        if lower not in self.key_map:
            return None
        wrong_char = self.key_map[lower]
        return wrong_char.upper() if char.isupper() else wrong_char

    def type_char(self, char: str):
        try:
            self.keyboard.type(char)
        except Exception:
            try:
                self.keyboard.press(char)
                self.keyboard.release(char)
            except Exception:
                pass

    def press_key(self, key):
        self.keyboard.press(key)
        self.keyboard.release(key)

    def countdown(self):
        full_seconds = int(self.config.start_delay)
        for i in range(full_seconds, 0, -1):
            print(f"\r[>] Начало печати через {i} сек... ", end="", flush=True)
            time.sleep(1)
        extra_delay = self.config.start_delay - full_seconds
        if extra_delay > 0:
            time.sleep(extra_delay)
        print("\r[>] Печать начинается! ")

    def print_current_settings(self):
        print("=== ТЕКУЩИЕ НАСТРОЙКИ ===")
        print(f"Символов в тексте: {len(self.cached_text)}")
        print(f"Задержка перед стартом: {self.config.start_delay} сек.")
        print(f"Опечатки: {'включены' if self.config.typos_enabled else 'выключены'}")
        print(f"Замена 4 пробелов на Tab: {'включена' if self.config.convert_four_spaces_to_tab else 'выключена'}")
        if self.config.typos_enabled:
            print(f"Шанс опечатки: {self.config.typo_chance * 100:.1f}%")
            print(f"Исправление опечаток: {'да' if self.config.fix_typos else 'нет'}")
        print("=========================")
        print()

    def handle_typo(self, char: str) -> bool:
        if not self.config.typos_enabled or not char.isalpha() or random.random() >= self.config.typo_chance:
            return False
        wrong_char = self.get_wrong_char(char)
        if not wrong_char:
            return False
        self.type_char(wrong_char)
        if self.config.fix_typos:
            time.sleep(random.uniform(self.config.fix_delay_min, self.config.fix_delay_max))
            self.press_key(Key.backspace)
            time.sleep(self.get_human_delay())
            return False
        return True

    def simulate_typing(self):
        if not self.cached_text:
            print("Текст не был сохранен в память.")
            return
        self.print_current_settings()
        print("[!] Текст сохранен в память.")
        print("[!] Переключитесь в редактор кода или текстовое поле.")
        print("[!] Установите курсор в нужное место.")
        print("[!] Проверьте раскладку клавиатуры RU/EN.")
        print("[!] Нажмите Enter в этом окне для начала.")
        input()
        print(f"\n[>] У вас есть {self.config.start_delay} сек. на переключение окна...")
        self.countdown()
        print("\n[>] Для экстренной остановки нажмите Ctrl+C")
        time.sleep(0.3)
        try:
            total = len(self.cached_text)
            for index, char in enumerate(self.cached_text, start=1):
                if char == "\n":
                    self.press_key(Key.enter)
                    time.sleep(random.uniform(self.config.newline_delay_min, self.config.newline_delay_max))
                    continue
                if char == "\t":
                    self.press_key(Key.tab)
                    time.sleep(self.get_human_delay())
                    continue
                typo_was_left = self.handle_typo(char)
                if not typo_was_left:
                    self.type_char(char)
                time.sleep(self.get_human_delay())
                if index % 50 == 0 or index == total:
                    percent = index / total * 100
                    print(f"\r[>] Напечатано: {index}/{total} символов ({percent:.1f}%)", end="", flush=True)
            print("\n[>] Ввод завершен.")
        except KeyboardInterrupt:
            print("\n[!] Ввод прерван пользователем.")

    def run(self):
        print("=== ENTER TYPER RU/EN ===")
        print("1. Скопируйте нужный текст в буфер обмена.")
        print("2. Запустите этот скрипт.")
        print("3. Настройте режим печати.")
        print("4. Переключитесь в нужное окно после команды.")
        print("=========================")
        print()
        if not self.capture_clipboard():
            print("Буфер обмена пуст или недоступен.")
            print("Скопируйте текст и запустите скрипт заново.")
            return
        self.configure()
        self.normalize_clipboard_text()
        self.simulate_typing()


if __name__ == "__main__":
    try:
        typer = EnterTyper()
        typer.run()
    except KeyboardInterrupt:
        print("\nСкрипт завершен пользователем.")
    except Exception as error:
        print(f"\nКритическая ошибка: {error}")
        print("Попробуйте запустить скрипт от имени администратора.")
'''

# Python library registry is kept in core/python_library_registry.py.
# It stores import-name -> pip-name mapping, categories, safety flags and bundles.


ASTRA_WALLPAPERS = {
    "Astra Neon Core": "assets/wallpapers/astra_neon_core.png",
    "Astra Deep Space": "assets/wallpapers/astra_deep_space.png",
    "Astra Classic": "assets/wallpapers/astra_blue_horizon.png",
    "Astra Eclipse": "assets/wallpapers/astra_eclipse.png",
    "Astra Crown Night": "assets/wallpapers/astra_crown_night.png",
    "Astra Sakura Dusk": "assets/wallpapers/astra_sakura_dusk.png",
    "Astra Cyber Ritual": "assets/wallpapers/astra_cyber_ritual.png",
    "Astra Crimson Prayer": "assets/wallpapers/astra_crimson_prayer.png",
    ANGEL_404_WALLPAPER: "assets/wallpapers/angel_404.png",
}

GLOBAL_FONT_OPTIONS = {
    DEFAULT_GLOBAL_FONT: "",
    "Minecraft Rus": "assets/fonts/minecraft.ttf",
}

LANGUAGES = {
    "Python": {"extension": ".py", "template": PYTHON_TEMPLATE, "filters": "Python (*.py)", "extensions": [".py"]},
    "C++": {"extension": ".cpp", "template": CPP_TEMPLATE, "filters": "C++ (*.cpp *.cc *.cxx *.hpp *.h)", "extensions": [".cpp", ".cc", ".cxx", ".hpp", ".h"]},
    "Java": {"extension": ".java", "template": JAVA_TEMPLATE, "filters": "Java (*.java)", "extensions": [".java"]},
    "HTML": {"extension": ".html", "template": HTML_TEMPLATE, "filters": "HTML (*.html *.htm)", "extensions": [".html", ".htm"]},
    "CSS": {"extension": ".css", "template": CSS_TEMPLATE, "filters": "CSS (*.css)", "extensions": [".css"]},
    "JavaScript": {"extension": ".js", "template": JAVASCRIPT_TEMPLATE, "filters": "JavaScript (*.js *.mjs *.cjs *.jsx)", "extensions": [".js", ".mjs", ".cjs", ".jsx"]},
    "TypeScript": {"extension": ".ts", "template": TYPESCRIPT_TEMPLATE, "filters": "TypeScript (*.ts *.tsx *.mts *.cts)", "extensions": [".ts", ".tsx", ".mts", ".cts"]},
    "Luau": {"extension": ".luau", "template": LUAU_TEMPLATE, "filters": "Luau / Lua (*.luau *.lua)", "extensions": [".luau", ".lua"]},
    "GDScript": {"extension": ".gd", "template": GDSCRIPT_TEMPLATE, "filters": "GDScript (*.gd)", "extensions": [".gd"]},
    "PHP": {"extension": ".php", "template": PHP_TEMPLATE, "filters": "PHP (*.php)", "extensions": [".php"]},
    "PowerShell": {"extension": ".ps1", "template": POWERSHELL_TEMPLATE, "filters": "PowerShell (*.ps1 *.psm1 *.psd1)", "extensions": [".ps1", ".psm1", ".psd1"]},
    "C#": {"extension": ".cs", "template": CSHARP_TEMPLATE, "filters": "C# (*.cs)", "extensions": [".cs"]},
    "SQL": {"extension": ".sql", "template": SQL_TEMPLATE, "filters": "SQL (*.sql)", "extensions": [".sql"]},
    "JSON": {"extension": ".json", "template": JSON_TEMPLATE, "filters": "JSON (*.json *.jsonc)", "extensions": [".json", ".jsonc"]},
    "YAML": {"extension": ".yaml", "template": YAML_TEMPLATE, "filters": "YAML (*.yaml *.yml)", "extensions": [".yaml", ".yml"]},
    "Markdown": {"extension": ".md", "template": MARKDOWN_TEMPLATE, "filters": "Markdown (*.md *.markdown)", "extensions": [".md", ".markdown"]},
    "TOML": {"extension": ".toml", "template": TOML_TEMPLATE, "filters": "TOML (*.toml)", "extensions": [".toml"]},
    "XML": {"extension": ".xml", "template": XML_TEMPLATE, "filters": "XML (*.xml *.xsd *.svg)", "extensions": [".xml", ".xsd", ".svg"]},
    "Shell": {"extension": ".sh", "template": SHELL_TEMPLATE, "filters": "Shell (*.sh *.bash)", "extensions": [".sh", ".bash"]},
    "Dockerfile": {"extension": "", "template": DOCKERFILE_TEMPLATE, "filters": "Dockerfile (Dockerfile*)", "extensions": []},
}

# The other language implementations remain available internally and can still
# open existing files. Release 3.13 intentionally exposes only the languages
# being polished in the current acceptance cycle.
VISIBLE_LANGUAGES = ("Java", "Python", "C++", "JavaScript", "HTML", "CSS")

SPECIAL_FILENAMES_TO_LANGUAGE = {
    "dockerfile": "Dockerfile",
    "containerfile": "Dockerfile",
    ".env": "Shell",
}

EXTENSION_TO_LANGUAGE = {
    ext: language for language, meta in LANGUAGES.items() for ext in meta["extensions"]
}

PROJECT_FILE_FILTERS = [
    "*.py", "*.cpp", "*.cc", "*.cxx", "*.hpp", "*.h", "*.java",
    "*.html", "*.htm", "*.css", "*.js", "*.mjs", "*.cjs", "*.jsx", "*.ts", "*.tsx", "*.mts", "*.cts",
    "*.luau", "*.lua", "*.gd", "*.php", "*.ps1", "*.psm1", "*.psd1", "*.cs", "*.sql",
    "*.json", "*.jsonc", "*.yaml", "*.yml", "*.md", "*.markdown", "*.toml", "*.xml", "*.xsd", "*.svg",
    "*.sh", "*.bash", "*.txt", "Dockerfile", "Dockerfile.*", "Containerfile", "Containerfile.*", ".env", ".env.*",
]



SNIPPETS = {
    "C++": [
        {"language": "cpp", "trigger": "main", "label": "main()", "insertText": "int main() {\n    §CURSOR§\n    return 0;\n}", "description": "Точка входа C++", "cursorTarget": ""},
        {"language": "cpp", "trigger": "include", "label": "#include", "insertText": "#include <iostream>§CURSOR§", "description": "Подключение библиотеки", "cursorTarget": "iostream"},
        {"language": "cpp", "trigger": "cout", "label": "std::cout", "insertText": "std::cout << §CURSOR§ << std::endl;", "description": "Вывод в консоль", "cursorTarget": ""},
        {"language": "cpp", "trigger": "cin", "label": "std::cin", "insertText": "std::cin >> §CURSOR§;", "description": "Ввод из консоли", "cursorTarget": ""},
        {"language": "cpp", "trigger": "if", "label": "if", "insertText": "if (condition) {\n    §CURSOR§\n}", "description": "Условный оператор", "cursorTarget": "condition"},
        {"language": "cpp", "trigger": "ife", "label": "if / else", "insertText": "if (condition) {\n    §CURSOR§\n} else {\n    \n}", "description": "Условие с альтернативой", "cursorTarget": "condition"},
        {"language": "cpp", "trigger": "for", "label": "for", "insertText": "for (int i = 0; i < n; i++) {\n    §CURSOR§\n}", "description": "Индексный цикл", "cursorTarget": "n"},
        {"language": "cpp", "trigger": "forr", "label": "range-based for", "insertText": "for (const auto& item : items) {\n    §CURSOR§\n}", "description": "Цикл по контейнеру", "cursorTarget": "item"},
        {"language": "cpp", "trigger": "while", "label": "while", "insertText": "while (condition) {\n    §CURSOR§\n}", "description": "Цикл с условием", "cursorTarget": "condition"},
        {"language": "cpp", "trigger": "switch", "label": "switch", "insertText": "switch (value) {\n    case 1:\n        §CURSOR§\n        break;\n    default:\n        break;\n}", "description": "Выбор по значению", "cursorTarget": "value"},
        {"language": "cpp", "trigger": "try", "label": "try / catch", "insertText": "try {\n    §CURSOR§\n} catch (const std::exception& e) {\n    std::cerr << e.what() << std::endl;\n}", "description": "Обработка ошибок", "cursorTarget": ""},
        {"language": "cpp", "trigger": "class", "label": "class", "insertText": "class ClassName {\npublic:\n    ClassName() = default;\n\nprivate:\n    §CURSOR§\n};", "description": "Класс", "cursorTarget": "ClassName"},
        {"language": "cpp", "trigger": "struct", "label": "struct", "insertText": "struct StructName {\n    §CURSOR§\n};", "description": "Структура", "cursorTarget": "StructName"},
        {"language": "cpp", "trigger": "func", "label": "function", "insertText": "ReturnType functionName() {\n    §CURSOR§\n}", "description": "Определение функции", "cursorTarget": "functionName"},
        {"language": "cpp", "trigger": "lambda", "label": "lambda", "insertText": "[&](auto value) {\n    §CURSOR§\n}", "description": "Лямбда-функция", "cursorTarget": "value"},
        {"language": "cpp", "trigger": "vector", "label": "std::vector", "insertText": "std::vector<Type> values;§CURSOR§", "description": "Динамический массив", "cursorTarget": "Type"},
        {"language": "cpp", "trigger": "unique", "label": "std::make_unique", "insertText": "auto value = std::make_unique<Type>(§CURSOR§);", "description": "Уникальный smart pointer", "cursorTarget": "Type"},
        {"language": "cpp", "trigger": "shared", "label": "std::make_shared", "insertText": "auto value = std::make_shared<Type>(§CURSOR§);", "description": "Разделяемый smart pointer", "cursorTarget": "Type"},
        {"language": "cpp", "trigger": "namespace", "label": "namespace", "insertText": "namespace name {\n    §CURSOR§\n}", "description": "Пространство имён", "cursorTarget": "name"},
        {"language": "cpp", "trigger": "return", "label": "return", "insertText": "return §CURSOR§;", "description": "Возврат значения", "cursorTarget": ""},
    ],
    "Python": [
        {"language": "python", "trigger": "print", "label": "print()", "insertText": "print(§CURSOR§)", "description": "Вывод", "cursorTarget": ""},
        {"language": "python", "trigger": "input", "label": "input()", "insertText": "input(\"§CURSOR§\")", "description": "Ввод", "cursorTarget": ""},
        {"language": "python", "trigger": "if", "label": "if", "insertText": "if condition:\n    §CURSOR§", "description": "Условие", "cursorTarget": "condition"},
        {"language": "python", "trigger": "ife", "label": "if / else", "insertText": "if condition:\n    §CURSOR§\nelse:\n    ", "description": "Условие с else", "cursorTarget": "condition"},
        {"language": "python", "trigger": "for", "label": "for range", "insertText": "for i in range(n):\n    §CURSOR§", "description": "Цикл по диапазону", "cursorTarget": "n"},
        {"language": "python", "trigger": "forin", "label": "for in", "insertText": "for item in items:\n    §CURSOR§", "description": "Цикл по коллекции", "cursorTarget": "item"},
        {"language": "python", "trigger": "while", "label": "while", "insertText": "while condition:\n    §CURSOR§", "description": "Цикл с условием", "cursorTarget": "condition"},
        {"language": "python", "trigger": "def", "label": "def", "insertText": "def function_name():\n    §CURSOR§", "description": "Функция", "cursorTarget": "function_name"},
        {"language": "python", "trigger": "class", "label": "class", "insertText": "class ClassName:\n    def __init__(self):\n        §CURSOR§", "description": "Класс", "cursorTarget": "ClassName"},
        {"language": "python", "trigger": "try", "label": "try / except", "insertText": "try:\n    §CURSOR§\nexcept Exception as exc:\n    print(exc)", "description": "Обработка ошибок", "cursorTarget": ""},
        {"language": "python", "trigger": "with", "label": "with open", "insertText": "with open(\"file.txt\", \"r\", encoding=\"utf-8\") as file:\n    §CURSOR§", "description": "Контекстный менеджер", "cursorTarget": "file.txt"},
        {"language": "python", "trigger": "import", "label": "import", "insertText": "import §CURSOR§", "description": "Импорт модуля", "cursorTarget": ""},
        {"language": "python", "trigger": "main", "label": "if __name__", "insertText": "if __name__ == \"__main__\":\n    main()§CURSOR§", "description": "Запуск main", "cursorTarget": "main"},
    ],
    "JavaScript": [
        {"language": "javascript", "trigger": "log", "label": "console.log", "insertText": "console.log(§CURSOR§);", "description": "Вывод в консоль", "cursorTarget": ""},
        {"language": "javascript", "trigger": "if", "label": "if", "insertText": "if (condition) {\n    §CURSOR§\n}", "description": "Условие", "cursorTarget": "condition"},
        {"language": "javascript", "trigger": "ife", "label": "if / else", "insertText": "if (condition) {\n    §CURSOR§\n} else {\n    \n}", "description": "Условие с else", "cursorTarget": "condition"},
        {"language": "javascript", "trigger": "for", "label": "for", "insertText": "for (let i = 0; i < n; i++) {\n    §CURSOR§\n}", "description": "Цикл", "cursorTarget": "n"},
        {"language": "javascript", "trigger": "while", "label": "while", "insertText": "while (condition) {\n    §CURSOR§\n}", "description": "Цикл с условием", "cursorTarget": "condition"},
        {"language": "javascript", "trigger": "function", "label": "function", "insertText": "function functionName() {\n    §CURSOR§\n}", "description": "Функция", "cursorTarget": "functionName"},
        {"language": "javascript", "trigger": "arrow", "label": "arrow function", "insertText": "const functionName = () => {\n    §CURSOR§\n};", "description": "Стрелочная функция", "cursorTarget": "functionName"},
        {"language": "javascript", "trigger": "class", "label": "class", "insertText": "class ClassName {\n    constructor() {\n        §CURSOR§\n    }\n}", "description": "Класс", "cursorTarget": "ClassName"},
        {"language": "javascript", "trigger": "try", "label": "try / catch", "insertText": "try {\n    §CURSOR§\n} catch (error) {\n    console.error(error);\n}", "description": "Обработка ошибок", "cursorTarget": ""},
        {"language": "javascript", "trigger": "import", "label": "import", "insertText": "import { name } from \"module\";§CURSOR§", "description": "Импорт", "cursorTarget": "name"},
        {"language": "javascript", "trigger": "async", "label": "async function", "insertText": "async function functionName() {\n    §CURSOR§\n}", "description": "Асинхронная функция", "cursorTarget": "functionName"},
        {"language": "javascript", "trigger": "await", "label": "await", "insertText": "await §CURSOR§", "description": "Ожидание Promise", "cursorTarget": ""},
    ],
    "Java": [
        {"language": "java", "trigger": "class", "label": "class", "insertText": "public class Main {\n    §CURSOR§\n}", "description": "Класс", "cursorTarget": "Main"},
        {"language": "java", "trigger": "main", "label": "main", "insertText": "public static void main(String[] args) {\n    §CURSOR§\n}", "description": "Точка входа", "cursorTarget": ""},
        {"language": "java", "trigger": "sout", "label": "System.out.println", "insertText": "System.out.println(§CURSOR§);", "description": "Вывод", "cursorTarget": ""},
        {"language": "java", "trigger": "scanner", "label": "Scanner", "insertText": "Scanner scanner = new Scanner(System.in);\nString input = scanner.nextLine();§CURSOR§", "description": "Ввод", "cursorTarget": "input"},
        {"language": "java", "trigger": "if", "label": "if", "insertText": "if (condition) {\n    §CURSOR§\n}", "description": "Условие", "cursorTarget": "condition"},
        {"language": "java", "trigger": "ife", "label": "if / else", "insertText": "if (condition) {\n    §CURSOR§\n} else {\n    \n}", "description": "Условие с else", "cursorTarget": "condition"},
        {"language": "java", "trigger": "for", "label": "for", "insertText": "for (int i = 0; i < n; i++) {\n    §CURSOR§\n}", "description": "Цикл", "cursorTarget": "n"},
        {"language": "java", "trigger": "while", "label": "while", "insertText": "while (condition) {\n    §CURSOR§\n}", "description": "Цикл", "cursorTarget": "condition"},
        {"language": "java", "trigger": "switch", "label": "switch", "insertText": "switch (value) {\n    case 1:\n        §CURSOR§\n        break;\n    default:\n        break;\n}", "description": "Выбор", "cursorTarget": "value"},
        {"language": "java", "trigger": "try", "label": "try / catch", "insertText": "try {\n    §CURSOR§\n} catch (Exception e) {\n    System.out.println(e.getMessage());\n}", "description": "Ошибки", "cursorTarget": ""},
        {"language": "java", "trigger": "method", "label": "method", "insertText": "public static void methodName() {\n    §CURSOR§\n}", "description": "Метод", "cursorTarget": "methodName"},
        {"language": "java", "trigger": "return", "label": "return", "insertText": "return §CURSOR§;", "description": "Возврат", "cursorTarget": ""},
        {"language": "java", "trigger": "import", "label": "import", "insertText": "import java.util.Scanner;§CURSOR§", "description": "Импорт", "cursorTarget": "java.util.Scanner"},
    ],
    "C#": [
        {"language": "csharp", "trigger": "using", "label": "using System", "insertText": "using System;§CURSOR§", "description": "Подключение пространства имён", "cursorTarget": "System"},
        {"language": "csharp", "trigger": "class", "label": "class Program", "insertText": "class Program\n{\n    §CURSOR§\n}", "description": "Класс", "cursorTarget": "Program"},
        {"language": "csharp", "trigger": "main", "label": "static Main", "insertText": "static void Main(string[] args)\n{\n    §CURSOR§\n}", "description": "Точка входа", "cursorTarget": ""},
        {"language": "csharp", "trigger": "cw", "label": "Console.WriteLine", "insertText": "Console.WriteLine(§CURSOR§);", "description": "Вывод", "cursorTarget": ""},
        {"language": "csharp", "trigger": "cr", "label": "Console.ReadLine", "insertText": "string? input = Console.ReadLine();§CURSOR§", "description": "Ввод", "cursorTarget": "input"},
        {"language": "csharp", "trigger": "if", "label": "if", "insertText": "if (condition)\n{\n    §CURSOR§\n}", "description": "Условие", "cursorTarget": "condition"},
        {"language": "csharp", "trigger": "ife", "label": "if / else", "insertText": "if (condition)\n{\n    §CURSOR§\n}\nelse\n{\n    \n}", "description": "Ветвление", "cursorTarget": "condition"},
        {"language": "csharp", "trigger": "for", "label": "for", "insertText": "for (int i = 0; i < n; i++)\n{\n    §CURSOR§\n}", "description": "Индексный цикл", "cursorTarget": "n"},
        {"language": "csharp", "trigger": "foreach", "label": "foreach", "insertText": "foreach (var item in items)\n{\n    §CURSOR§\n}", "description": "Цикл по коллекции", "cursorTarget": "item"},
        {"language": "csharp", "trigger": "while", "label": "while", "insertText": "while (condition)\n{\n    §CURSOR§\n}", "description": "Цикл", "cursorTarget": "condition"},
        {"language": "csharp", "trigger": "switch", "label": "switch", "insertText": "switch (value)\n{\n    case 1:\n        §CURSOR§\n        break;\n    default:\n        break;\n}", "description": "Выбор", "cursorTarget": "value"},
        {"language": "csharp", "trigger": "try", "label": "try / catch", "insertText": "try\n{\n    §CURSOR§\n}\ncatch (Exception ex)\n{\n    Console.WriteLine(ex.Message);\n}", "description": "Обработка ошибок", "cursorTarget": ""},
        {"language": "csharp", "trigger": "fn", "label": "method", "insertText": "static void MethodName()\n{\n    §CURSOR§\n}", "description": "Метод", "cursorTarget": "MethodName"},
        {"language": "csharp", "trigger": "ret", "label": "return", "insertText": "return §CURSOR§;", "description": "Возврат", "cursorTarget": ""},
        {"language": "csharp", "trigger": "var", "label": "var", "insertText": "var name = value;§CURSOR§", "description": "Переменная", "cursorTarget": "name"},
    ],
    "HTML": [
        {"language": "html", "trigger": "html:5", "label": "HTML5 document", "insertText": "<!DOCTYPE html>\n<html lang=\"ru\">\n<head>\n    <meta charset=\"UTF-8\">\n    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n    <title>Document</title>\n</head>\n<body>\n    §CURSOR§\n</body>\n</html>", "description": "Полный HTML-документ", "cursorTarget": "Document"},
        {"language": "html", "trigger": "div", "label": "div", "insertText": "<div class=\"container\">\n    §CURSOR§\n</div>", "description": "Контейнер", "cursorTarget": "container"},
        {"language": "html", "trigger": "span", "label": "span", "insertText": "<span>§CURSOR§</span>", "description": "Строчный контейнер", "cursorTarget": ""},
        {"language": "html", "trigger": "a", "label": "link", "insertText": "<a href=\"#\">§CURSOR§</a>", "description": "Ссылка", "cursorTarget": "#"},
        {"language": "html", "trigger": "img", "label": "image", "insertText": "<img src=\"image.png\" alt=\"§CURSOR§\">", "description": "Изображение", "cursorTarget": "image.png"},
        {"language": "html", "trigger": "form", "label": "form", "insertText": "<form action=\"#\" method=\"post\">\n    §CURSOR§\n</form>", "description": "Форма", "cursorTarget": "#"},
        {"language": "html", "trigger": "input", "label": "input", "insertText": "<input type=\"text\" name=\"name\" id=\"name\">§CURSOR§", "description": "Поле ввода", "cursorTarget": "name"},
        {"language": "html", "trigger": "button", "label": "button", "insertText": "<button type=\"button\">§CURSOR§</button>", "description": "Кнопка", "cursorTarget": ""},
        {"language": "html", "trigger": "ul", "label": "ul", "insertText": "<ul>\n    <li>§CURSOR§</li>\n</ul>", "description": "Список", "cursorTarget": ""},
        {"language": "html", "trigger": "table", "label": "table", "insertText": "<table>\n    <tr>\n        <th>Title</th>\n    </tr>\n    <tr>\n        <td>§CURSOR§</td>\n    </tr>\n</table>", "description": "Таблица", "cursorTarget": "Title"},
        {"language": "html", "trigger": "script", "label": "script", "insertText": "<script src=\"script.js\"></script>§CURSOR§", "description": "Подключение JS", "cursorTarget": "script.js"},
        {"language": "html", "trigger": "link", "label": "link css", "insertText": "<link rel=\"stylesheet\" href=\"style.css\">§CURSOR§", "description": "Подключение CSS", "cursorTarget": "style.css"},
        {"language": "html", "trigger": "comment", "label": "comment", "insertText": "<!-- §CURSOR§ -->", "description": "Комментарий", "cursorTarget": ""},
    ],
    "CSS": [
        {"language": "css", "trigger": ".", "label": ".class", "insertText": ".class-name {\n    §CURSOR§\n}", "description": "Селектор класса", "cursorTarget": "class-name"},
        {"language": "css", "trigger": "#", "label": "#id", "insertText": "#element-id {\n    §CURSOR§\n}", "description": "Селектор id", "cursorTarget": "element-id"},
        {"language": "css", "trigger": "body", "label": "body", "insertText": "body {\n    §CURSOR§\n}", "description": "Стили body", "cursorTarget": ""},
        {"language": "css", "trigger": "flex", "label": "flex", "insertText": ".container {\n    display: flex;\n    §CURSOR§\n}", "description": "Flex-контейнер", "cursorTarget": "container"},
        {"language": "css", "trigger": "grid", "label": "grid", "insertText": ".container {\n    display: grid;\n    grid-template-columns: repeat(3, 1fr);\n    gap: 1rem;\n    §CURSOR§\n}", "description": "Grid-контейнер", "cursorTarget": "container"},
        {"language": "css", "trigger": "media", "label": "@media", "insertText": "@media (max-width: 768px) {\n    §CURSOR§\n}", "description": "Медиа-запрос", "cursorTarget": "768px"},
        {"language": "css", "trigger": "hover", "label": ":hover", "insertText": ".button:hover {\n    §CURSOR§\n}", "description": "Состояние hover", "cursorTarget": "button"},
        {"language": "css", "trigger": "keyframes", "label": "@keyframes", "insertText": "@keyframes animationName {\n    from { opacity: 0; }\n    to { opacity: 1; }\n}\n§CURSOR§", "description": "Анимация", "cursorTarget": "animationName"},
        {"language": "css", "trigger": "import", "label": "@import", "insertText": "@import url(\"styles.css\");§CURSOR§", "description": "Импорт CSS", "cursorTarget": "styles.css"},
        {"language": "css", "trigger": "root", "label": ":root", "insertText": ":root {\n    --accent: #ff2d6f;\n    §CURSOR§\n}", "description": "CSS-переменные", "cursorTarget": "--accent"},
        {"language": "css", "trigger": "reset", "label": "reset", "insertText": "* {\n    box-sizing: border-box;\n    margin: 0;\n    padding: 0;\n}\n§CURSOR§", "description": "Базовый сброс", "cursorTarget": ""},
    ],
    "SQL": [
        {"language": "sql", "trigger": "select", "label": "SELECT", "insertText": "SELECT column_name\nFROM table_name;§CURSOR§", "description": "Базовая выборка", "cursorTarget": "column_name"},
        {"language": "sql", "trigger": "selw", "label": "SELECT WHERE", "insertText": "SELECT column_name\nFROM table_name\nWHERE condition;§CURSOR§", "description": "Выборка с условием", "cursorTarget": "condition"},
        {"language": "sql", "trigger": "insert", "label": "INSERT", "insertText": "INSERT INTO table_name (column1, column2)\nVALUES (value1, value2);§CURSOR§", "description": "Добавление строки", "cursorTarget": "table_name"},
        {"language": "sql", "trigger": "update", "label": "UPDATE", "insertText": "UPDATE table_name\nSET column1 = value1\nWHERE condition;§CURSOR§", "description": "Обновление", "cursorTarget": "condition"},
        {"language": "sql", "trigger": "delete", "label": "DELETE", "insertText": "DELETE FROM table_name\nWHERE condition;§CURSOR§", "description": "Удаление", "cursorTarget": "condition"},
        {"language": "sql", "trigger": "create", "label": "CREATE TABLE", "insertText": "CREATE TABLE table_name (\n    id INT PRIMARY KEY,\n    name VARCHAR(255)\n);§CURSOR§", "description": "Создание таблицы", "cursorTarget": "table_name"},
        {"language": "sql", "trigger": "join", "label": "JOIN", "insertText": "SELECT a.column_name, b.column_name\nFROM table_a a\nJOIN table_b b ON a.id = b.a_id;§CURSOR§", "description": "Соединение таблиц", "cursorTarget": "a.column_name"},
        {"language": "sql", "trigger": "leftjoin", "label": "LEFT JOIN", "insertText": "SELECT a.column_name, b.column_name\nFROM table_a a\nLEFT JOIN table_b b ON a.id = b.a_id;§CURSOR§", "description": "Левое соединение", "cursorTarget": "a.column_name"},
        {"language": "sql", "trigger": "group", "label": "GROUP BY", "insertText": "SELECT column_name, COUNT(*)\nFROM table_name\nGROUP BY column_name;§CURSOR§", "description": "Группировка", "cursorTarget": "column_name"},
        {"language": "sql", "trigger": "order", "label": "ORDER BY", "insertText": "SELECT column_name\nFROM table_name\nORDER BY column_name ASC;§CURSOR§", "description": "Сортировка", "cursorTarget": "column_name"},
        {"language": "sql", "trigger": "case", "label": "CASE", "insertText": "CASE\n    WHEN condition THEN result\n    ELSE other_result\nEND§CURSOR§", "description": "Выражение выбора", "cursorTarget": "condition"},
        {"language": "sql", "trigger": "count", "label": "COUNT", "insertText": "COUNT(§CURSOR§)", "description": "Агрегатная функция", "cursorTarget": "*"},
    ],
}

THEMES = {
    "Astra: Корона кода": {
        "bg": "#020407",
        "bg2": "#070b12",
        "panel": "#090d15",
        "panel2": "#0d1420",
        "editor": "#050911",
        "console": "#03060b",
        "text": "#f2f7ff",
        "muted": "#79889d",
        "border": "#1b2636",
        "line": "#111a27",
        "selection": "#1d3046",
        "keyword": "#ff2d4f",
        "string": "#63e7ff",
        "comment": "#66758a",
        "number": "#ffb35c",
        "function": "#69e5ff",
        "class": "#f5f7ff",
    },
    "Токио: Сакура в тумане": {
        "bg": "#090a10",
        "bg2": "#11121c",
        "panel": "#11131d",
        "panel2": "#171827",
        "editor": "#0b0c14",
        "console": "#070810",
        "text": "#f4eef7",
        "muted": "#9a8ca4",
        "border": "#332536",
        "line": "#191622",
        "selection": "#332139",
        "keyword": "#ff6aa8",
        "string": "#d9b8ff",
        "comment": "#746678",
        "number": "#ffc0d7",
        "function": "#b4a7ff",
        "class": "#ffd3e6",
    },
    "Аниме: Сумеречный ангел": {
        "bg": "#060913",
        "bg2": "#0b1020",
        "panel": "#0c1222",
        "panel2": "#10182c",
        "editor": "#060b16",
        "console": "#030711",
        "text": "#eef6ff",
        "muted": "#8394b3",
        "border": "#1b2a48",
        "line": "#101a30",
        "selection": "#20365f",
        "keyword": "#83b8ff",
        "string": "#d8c3ff",
        "comment": "#687b9a",
        "number": "#f0d28a",
        "function": "#b4d9ff",
        "class": "#ffffff",
    },
    "Кибер: Зелёный сбой": {
        "bg": "#020706",
        "bg2": "#04110e",
        "panel": "#061410",
        "panel2": "#081d17",
        "editor": "#020b09",
        "console": "#010504",
        "text": "#eafff7",
        "muted": "#6f9588",
        "border": "#0e3b2f",
        "line": "#08251e",
        "selection": "#0d4738",
        "keyword": "#00ff9c",
        "string": "#78ffd4",
        "comment": "#52786d",
        "number": "#b8ff5c",
        "function": "#26ffd1",
        "class": "#d9fff2",
    },
    "Мистик: Красный ритуал": {
        "bg": "#080203",
        "bg2": "#140405",
        "panel": "#120507",
        "panel2": "#1d080b",
        "editor": "#090204",
        "console": "#040102",
        "text": "#fff1f1",
        "muted": "#a17b7f",
        "border": "#491019",
        "line": "#24070d",
        "selection": "#55101b",
        "keyword": "#ff073a",
        "string": "#ff9aa8",
        "comment": "#7c4e57",
        "number": "#ffbf69",
        "function": "#ff5b75",
        "class": "#ffe5e9",
    },
    "Небо: Холодное сияние": {
        "bg": "#eaf4ff",
        "bg2": "#dfefff",
        "panel": "#f6fbff",
        "panel2": "#edf6ff",
        "editor": "#fbfdff",
        "console": "#eef7ff",
        "text": "#102033",
        "muted": "#60758d",
        "border": "#bdd3ea",
        "line": "#e3eef9",
        "selection": "#cde7ff",
        "keyword": "#316bff",
        "string": "#007a9c",
        "comment": "#7890a8",
        "number": "#a15c00",
        "function": "#0066cc",
        "class": "#4340a5",
    },
    "VHS: Розовый закат": {
        "bg": "#100712",
        "bg2": "#1a0b1f",
        "panel": "#190c22",
        "panel2": "#24102f",
        "editor": "#120716",
        "console": "#08030b",
        "text": "#fff1fb",
        "muted": "#a989b0",
        "border": "#3b2146",
        "line": "#21102a",
        "selection": "#442152",
        "keyword": "#ff4db8",
        "string": "#ffd166",
        "comment": "#806685",
        "number": "#ff9f1c",
        "function": "#e0aaff",
        "class": "#ffcad4",
    },
    "Ночные виджеты": {
        "bg": "#080d16",
        "bg2": "#0b1220",
        "panel": "#0e1726",
        "panel2": "#101b2d",
        "editor": "#090f1a",
        "console": "#070b12",
        "text": "#eef4ff",
        "muted": "#7c8ba3",
        "border": "#1a2738",
        "line": "#131f30",
        "selection": "#26384f",
        "keyword": "#ff5c8a",
        "string": "#8cffd2",
        "comment": "#65758f",
        "number": "#ffd166",
        "function": "#7dd3fc",
        "class": "#f9a8d4",
    },
    "Графитовый моно": {
        "bg": "#0a0a0d",
        "bg2": "#101015",
        "panel": "#15151c",
        "panel2": "#1a1a23",
        "editor": "#0d0d12",
        "console": "#08080c",
        "text": "#f2f2f5",
        "muted": "#9a9aa6",
        "border": "#2b2b36",
        "line": "#20202a",
        "selection": "#31313f",
        "keyword": "#ff4d6d",
        "string": "#9ef01a",
        "comment": "#6c757d",
        "number": "#fcbf49",
        "function": "#4cc9f0",
        "class": "#c77dff",
    },
    "Светлая бумага": {
        "bg": "#eef2f7",
        "bg2": "#f8fafc",
        "panel": "#ffffff",
        "panel2": "#f1f5f9",
        "editor": "#ffffff",
        "console": "#f8fafc",
        "text": "#0f172a",
        "muted": "#64748b",
        "border": "#cbd5e1",
        "line": "#e2e8f0",
        "selection": "#dbeafe",
        "keyword": "#d81b60",
        "string": "#00897b",
        "comment": "#78909c",
        "number": "#f57c00",
        "function": "#1565c0",
        "class": "#7b1fa2",
    },
    "Готика: Багровая корона": {
        "bg": "#050507",
        "bg2": "#10080b",
        "panel": "#0b0b10",
        "panel2": "#141016",
        "editor": "#07070b",
        "console": "#030305",
        "text": "#f7f1f1",
        "muted": "#8d7d82",
        "border": "#2a1016",
        "line": "#170b0f",
        "selection": "#311017",
        "keyword": "#ff284f",
        "string": "#d4c3a2",
        "comment": "#6d5960",
        "number": "#d6a75c",
        "function": "#e7e0d2",
        "class": "#ff6b87",
    },
    "Готика: Чёрный собор": {
        "bg": "#030404",
        "bg2": "#0a0a0b",
        "panel": "#0d0d0f",
        "panel2": "#151518",
        "editor": "#050506",
        "console": "#020203",
        "text": "#e7e7e7",
        "muted": "#7e7e86",
        "border": "#242428",
        "line": "#111114",
        "selection": "#2a2a2f",
        "keyword": "#c9c9d1",
        "string": "#9c8f78",
        "comment": "#5e5e66",
        "number": "#a8925d",
        "function": "#d8d8df",
        "class": "#ffffff",
    },
    "Готика: Алая исповедь": {
        "bg": "#090202",
        "bg2": "#160506",
        "panel": "#100508",
        "panel2": "#1b080d",
        "editor": "#0a0305",
        "console": "#050102",
        "text": "#fff2f2",
        "muted": "#a07b7b",
        "border": "#431018",
        "line": "#22060b",
        "selection": "#4c101a",
        "keyword": "#ff003c",
        "string": "#f5d0d0",
        "comment": "#7d4b51",
        "number": "#ffb86b",
        "function": "#ff687f",
        "class": "#fff0f0",
    },
    "Готика: Серебряный грех": {
        "bg": "#07080a",
        "bg2": "#101216",
        "panel": "#0f1115",
        "panel2": "#171a20",
        "editor": "#090b0f",
        "console": "#05060a",
        "text": "#f1f4f8",
        "muted": "#8c96a3",
        "border": "#2f3742",
        "line": "#151922",
        "selection": "#29303a",
        "keyword": "#d6dde8",
        "string": "#a8c6ff",
        "comment": "#67707c",
        "number": "#c9a66b",
        "function": "#7dd3fc",
        "class": "#e5e7eb",
    },
    "Готика: Неоновая бездна": {
        "bg": "#03070b",
        "bg2": "#07131a",
        "panel": "#071018",
        "panel2": "#0b1721",
        "editor": "#03080d",
        "console": "#020508",
        "text": "#effcff",
        "muted": "#6f8a96",
        "border": "#102d3a",
        "line": "#09202b",
        "selection": "#113847",
        "keyword": "#00e5ff",
        "string": "#ff315d",
        "comment": "#5f7580",
        "number": "#d4af37",
        "function": "#8ff6ff",
        "class": "#ff7a99",
    },
    ANGEL_404_THEME: {
        "bg": "#030108",
        "bg2": "#09031a",
        "panel": "#0b0616",
        "panel2": "#160827",
        "editor": "#07030f",
        "console": "#030106",
        "text": "#f7eeff",
        "muted": "#a48bbd",
        "border": "#48206a",
        "line": "#1a0a2b",
        "selection": "#4b176d",
        "keyword": "#ec42ff",
        "string": "#b88cff",
        "comment": "#806399",
        "number": "#ff8cf4",
        "function": "#c85cff",
        "class": "#f4c9ff",
    },
}

ACCENTS = {
    "Astra красно-синий": "#18d9ff",
    "Сакура": "#ff77b7",
    "Дымный фиолетовый": "#9b5cff",
    "Кибер-зелёный": "#00ff9c",
    "Небесный лёд": "#66bfff",
    "Ритуальный красный": "#ff073a",
    "Неон циан": "#00e5ff",
    "Сигнальный розовый": "#ff2d6f",
    "Лаймовый импульс": "#8cff66",
    "Янтарная сетка": "#ffbd4a",
    "Фиолетовый луч": "#a78bfa",
    "Кровавый алый": "#e60026",
    "Готическое золото": "#c9a66b",
    "Холодное серебро": "#d6dde8",
    "Ледяной синий": "#00aaff",
    ANGEL_404_ACCENT: "#d42cff",
}



def _safe_mkdir(path: Path) -> Path:
    """Create a folder without letting Windows permission errors break startup."""
    path = Path(path)
    try:
        path.mkdir(parents=True, exist_ok=True)
        return path
    except OSError:
        fallback = Path(tempfile.gettempdir()) / APP_DIR_NAME
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback


def app_data_dir() -> Path:
    # Release 2.1: never store mutable application data near the unpacked program folder.
    # This prevents Windows permission prompts like “request permission from another user”.
    candidates = []
    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        candidates.append(Path(local_appdata) / APP_DIR_NAME)
    candidates.append(Path.home() / "AppData" / "Local" / APP_DIR_NAME)
    candidates.append(Path.home() / ".astra_studio")  # legacy location from 1.x
    for candidate in candidates:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            return candidate
        except OSError:
            continue
    return _safe_mkdir(Path(tempfile.gettempdir()) / APP_DIR_NAME)


def documents_root_dir() -> Path:
    # Respect redirected/localized Windows Documents folders (OneDrive, domain
    # policies, etc.) instead of assuming %USERPROFILE%\Documents. Keep the
    # historical "Astral Studio" subfolder name for 2.x data compatibility.
    documents = ""
    try:
        documents = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
    except Exception:
        documents = ""
    base_documents = Path(documents) if documents else Path(os.environ.get("USERPROFILE", str(Path.home()))) / "Documents"
    return _safe_mkdir(base_documents / "Astral Studio")


def default_projects_dir() -> Path:
    return _safe_mkdir(documents_root_dir() / "Projects")


def default_builds_dir() -> Path:
    return _safe_mkdir(documents_root_dir() / "Builds")


def can_write_to_directory(path: Path) -> bool:
    path = Path(path)
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".astral_write_test.tmp"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True
    except OSError:
        return False


def project_root_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def resource_path(relative_path: str) -> Path:
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        return Path(bundle_root) / relative_path
    return project_root_dir() / relative_path


def _path_items(value: str) -> list[str]:
    return [item.strip('"') for item in value.split(os.pathsep) if item.strip('"')]


def prepend_runtime_path(folder: Path | str):
    folder = Path(folder)
    if not folder.exists():
        return
    folder_str = str(folder)
    current_items = _path_items(os.environ.get("PATH", ""))
    try:
        folder_resolved = folder.resolve()
    except OSError:
        folder_resolved = folder
    for item in current_items:
        try:
            if Path(item).exists() and Path(item).resolve() == folder_resolved:
                return
        except OSError:
            continue
    os.environ["PATH"] = folder_str + os.pathsep + os.environ.get("PATH", "")


def refresh_runtime_paths():
    if os.name != "nt":
        return
    candidates = [
        Path(r"C:\msys64\ucrt64\bin"),
        Path(r"C:\msys64\mingw64\bin"),
        Path(r"C:\msys64\clang64\bin"),
        Path(r"C:\Program Files\nodejs"),
        Path(r"C:\Program Files\Git\cmd"),
        Path(r"C:\Program Files\Git\bin"),
        Path(r"C:\Program Files\PowerShell\7"),
        Path(r"C:\Program Files\LLVM\bin"),
        Path.home() / ".dotnet" / "tools",
    ]
    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        candidates.append(Path(local_appdata) / "Microsoft" / "WinGet" / "Links")
    appdata = os.environ.get("APPDATA")
    if appdata:
        # Global npm tools such as tsc/tsx are normally exposed here on Windows.
        candidates.append(Path(appdata) / "npm")
    for variable in ("JAVA_HOME", "JDK_HOME"):
        java_home = os.environ.get(variable)
        if java_home:
            candidates.append(Path(java_home) / "bin")
    java_runtime = discover_java_runtime()
    if java_runtime is not None:
        candidates.append(java_runtime.home / "bin")
    for folder in candidates:
        prepend_runtime_path(folder)


def infer_language_from_path(path: Path | None, fallback: str = DEFAULT_LANGUAGE) -> str:
    if not path:
        return fallback
    name = path.name.lower()
    if name in SPECIAL_FILENAMES_TO_LANGUAGE:
        return SPECIAL_FILENAMES_TO_LANGUAGE[name]
    if name.startswith(".env"):
        return "Shell"
    if name.startswith("dockerfile") or name.startswith("containerfile"):
        return "Dockerfile"
    return EXTENSION_TO_LANGUAGE.get(path.suffix.lower(), fallback)


def _strip_jsonc_comments(text: str) -> str:
    """Remove // and /* */ comments outside JSON strings while preserving line breaks."""
    out: list[str] = []
    i = 0
    in_string = False
    escaped = False
    while i < len(text):
        ch = text[i]
        nxt = text[i + 1] if i + 1 < len(text) else ""
        if in_string:
            out.append(ch)
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            i += 1
            continue
        if ch == '"':
            in_string = True
            out.append(ch)
            i += 1
            continue
        if ch == "/" and nxt == "/":
            i += 2
            while i < len(text) and text[i] not in "\r\n":
                i += 1
            continue
        if ch == "/" and nxt == "*":
            i += 2
            while i < len(text):
                if text[i] == "*" and i + 1 < len(text) and text[i + 1] == "/":
                    i += 2
                    break
                # Keep newlines so parser line numbers remain useful.
                if text[i] in "\r\n":
                    out.append(text[i])
                i += 1
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def _strip_jsonc_trailing_commas(text: str) -> str:
    """Remove commas before ]/} outside strings."""
    out: list[str] = []
    i = 0
    in_string = False
    escaped = False
    while i < len(text):
        ch = text[i]
        if in_string:
            out.append(ch)
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            i += 1
            continue
        if ch == '"':
            in_string = True
            out.append(ch)
            i += 1
            continue
        if ch == ",":
            j = i + 1
            while j < len(text) and text[j].isspace():
                j += 1
            if j < len(text) and text[j] in "]}":
                i += 1
                continue
        out.append(ch)
        i += 1
    return "".join(out)


def loads_jsonc(text: str):
    return json.loads(_strip_jsonc_trailing_commas(_strip_jsonc_comments(text)))




def _read_text_utf8_or_cp1251(path: Path) -> tuple[str, str]:
    """Read source/config text without silently replacing legacy CP1251 bytes."""
    path = Path(path)
    try:
        return path.read_text(encoding="utf-8"), "utf-8"
    except UnicodeDecodeError:
        return path.read_text(encoding="cp1251"), "cp1251"


def _decode_process_output(data: bytes, preferred_encoding: str | None = None) -> str:
    """Decode subprocess output without turning common Windows text into �.

    Astra requests UTF-8 from processes it controls, but third-party CLIs and the
    classic Windows shell can still emit a legacy code page. Prefer UTF-8 and use
    conservative Windows fallbacks only when strict UTF-8 decoding fails.
    """
    if not data:
        return ""
    encodings = []
    if preferred_encoding:
        encodings.append(preferred_encoding)
    encodings.extend(("utf-8", "cp866", "cp1251") if os.name == "nt" else ("utf-8",))
    for encoding in encodings:
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")

def compiler_path(*names: str) -> str | None:
    refresh_runtime_paths()
    for name in names:
        path = shutil.which(name)
        if path:
            return path

    if os.name == "nt":
        common_dirs = [
            Path(r"C:\msys64\ucrt64\bin"),
            Path(r"C:\msys64\mingw64\bin"),
            Path(r"C:\msys64\clang64\bin"),
        ]
        adoptium = Path(r"C:\Program Files\Eclipse Adoptium")
        if adoptium.exists():
            common_dirs.extend(sorted(adoptium.glob("jdk-*\bin"), reverse=True))
        for folder in common_dirs:
            for name in names:
                candidate = folder / name
                if candidate.exists():
                    prepend_runtime_path(folder)
                    return str(candidate)
    return None


def project_tool_path(start: Path | str, *names: str) -> str | None:
    """Find a project-local Node tool shim before falling back to the global PATH."""
    current = Path(start)
    try:
        current = current.resolve()
    except OSError:
        pass
    if current.is_file():
        current = current.parent
    for folder in (current, *current.parents):
        bin_dir = folder / "node_modules" / ".bin"
        for name in names:
            candidates = [name]
            if os.name == "nt" and not Path(name).suffix:
                candidates = [f"{name}.cmd", f"{name}.exe", name]
            for candidate_name in candidates:
                candidate = bin_dir / candidate_name
                if candidate.is_file():
                    return str(candidate)
        # Stop at the active Astra project root when possible; do not scan
        # arbitrary parent workspaces above it just because they contain node_modules.
        if (folder / "astral.project.json").is_file():
            break
    return compiler_path(*names)


def python_command() -> tuple[str | None, list[str]]:
    if not getattr(sys, "frozen", False):
        return sys.executable, []
    launcher = compiler_path("py.exe", "py")
    if launcher:
        return launcher, ["-3"]
    python = compiler_path("python.exe", "python")
    if python:
        # Windows App Execution Aliases can make `where/python` succeed even when
        # Python is not installed. Treat the Microsoft Store stub as unavailable.
        normalized = str(python).replace("/", "\\").lower()
        if "\\windowsapps\\python" not in normalized:
            return python, []
    if os.name == "nt":
        # A freshly installed Python may already exist on disk while the parent
        # Explorer/Astra process still has the old PATH. Find common official
        # python.org/WinGet locations so a restart is not required just to run code.
        candidates: list[Path] = []
        local_appdata = os.environ.get("LOCALAPPDATA")
        if local_appdata:
            base = Path(local_appdata) / "Programs" / "Python"
            if base.exists():
                candidates.extend(sorted(base.glob("Python*/python.exe"), reverse=True))
        program_files = Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
        if program_files.exists():
            candidates.extend(sorted(program_files.glob("Python*/python.exe"), reverse=True))
        for candidate in candidates:
            if candidate.is_file():
                return str(candidate), []
    return None, []


class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.code_editor = editor

    def sizeHint(self):
        return QSize(self.code_editor.line_number_area_width(), 0)

    def paintEvent(self, event):
        self.code_editor.line_number_area_paint_event(event)




class NoWheelComboBox(QComboBox):
    """QComboBox без случайной смены значения колесом мыши.

    Используется только для выбора языка файла: прокрутка боковой панели
    не должна случайно менять язык текущего файла.
    """

    def wheelEvent(self, event):
        if self.view().isVisible():
            super().wheelEvent(event)
        else:
            event.ignore()


class CodeHighlighter(QSyntaxHighlighter):
    def __init__(self, document, theme, language_name=DEFAULT_LANGUAGE):
        super().__init__(document)
        self.set_theme(theme, language_name)

    def set_theme(self, theme, language_name=None):
        if language_name is not None:
            self.language_name = language_name
        self.theme = theme
        self.rules = []

        def fmt(color, bold=False, italic=False):
            char_format = QTextCharFormat()
            char_format.setForeground(QColor(color))
            if bold:
                char_format.setFontWeight(QFont.Weight.Bold)
            if italic:
                char_format.setFontItalic(True)
            return char_format

        keyword_format = fmt(theme["keyword"], bold=True)
        string_format = fmt(theme["string"])
        comment_format = fmt(theme["comment"], italic=True)
        number_format = fmt(theme["number"])
        function_format = fmt(theme["function"], bold=True)
        class_format = fmt(theme["class"], bold=True)

        language = getattr(self, "language_name", DEFAULT_LANGUAGE)

        if language == "Python":
            words = keyword.kwlist + ["True", "False", "None"]
            for word in words:
                self.rules.append((QRegularExpression(rf"\b{word}\b"), keyword_format, 0))
            self.rules.extend([
                (QRegularExpression(r"#[^\n]*"), comment_format, 0),
                (QRegularExpression(r'"[^"\\]*(\\.[^"\\]*)*"'), string_format, 0),
                (QRegularExpression(r"'[^'\\]*(\\.[^'\\]*)*'"), string_format, 0),
                (QRegularExpression(r"\b[0-9]+(\.[0-9]+)?\b"), number_format, 0),
                (QRegularExpression(r"\bdef\s+([A-Za-z_][A-Za-z0-9_]*)"), function_format, 1),
                (QRegularExpression(r"\bclass\s+([A-Za-z_][A-Za-z0-9_]*)"), class_format, 1),
            ])
        elif language == "C++":
            words = [
                "alignas", "alignof", "and", "auto", "bool", "break", "case", "catch", "char",
                "class", "const", "constexpr", "continue", "default", "delete", "do", "double",
                "else", "enum", "explicit", "export", "extern", "false", "float", "for", "friend",
                "if", "inline", "int", "long", "namespace", "new", "noexcept", "nullptr", "operator",
                "private", "protected", "public", "return", "short", "signed", "sizeof", "static",
                "struct", "switch", "template", "this", "throw", "true", "try", "typedef", "typename",
                "union", "unsigned", "using", "virtual", "void", "volatile", "while", "include",
            ]
            for word in words:
                self.rules.append((QRegularExpression(rf"\b{word}\b"), keyword_format, 0))
            self.rules.extend([
                (QRegularExpression(r"//[^\n]*"), comment_format, 0),
                (QRegularExpression(r"/\*.*\*/"), comment_format, 0),
                (QRegularExpression(r'"[^"\\]*(\\.[^"\\]*)*"'), string_format, 0),
                (QRegularExpression(r"'[^'\\]*(\\.[^'\\]*)*'"), string_format, 0),
                (QRegularExpression(r"#[a-zA-Z_]+"), keyword_format, 0),
                (QRegularExpression(r"\b[0-9]+(\.[0-9]+)?\b"), number_format, 0),
                (QRegularExpression(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\("), function_format, 1),
                (QRegularExpression(r"\b(class|struct)\s+([A-Za-z_][A-Za-z0-9_]*)"), class_format, 2),
            ])
        elif language == "Java":
            words = [
                "abstract", "assert", "boolean", "break", "byte", "case", "catch", "char", "class",
                "const", "continue", "default", "do", "double", "else", "enum", "extends", "final",
                "finally", "float", "for", "goto", "if", "implements", "import", "instanceof", "int",
                "interface", "long", "native", "new", "package", "private", "protected", "public",
                "return", "short", "static", "strictfp", "super", "switch", "synchronized", "this",
                "throw", "throws", "transient", "try", "void", "volatile", "while", "true", "false", "null",
            ]
            for word in words:
                self.rules.append((QRegularExpression(rf"\b{word}\b"), keyword_format, 0))
            self.rules.extend([
                (QRegularExpression(r"//[^\n]*"), comment_format, 0),
                (QRegularExpression(r"/\*.*\*/"), comment_format, 0),
                (QRegularExpression(r'"[^"\\]*(\\.[^"\\]*)*"'), string_format, 0),
                (QRegularExpression(r"'[^'\\]*(\\.[^'\\]*)*'"), string_format, 0),
                (QRegularExpression(r"\b[0-9]+(\.[0-9]+)?\b"), number_format, 0),
                (QRegularExpression(r"\bclass\s+([A-Za-z_][A-Za-z0-9_]*)"), class_format, 1),
                (QRegularExpression(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\("), function_format, 1),
            ])
        elif language == "HTML":
            self.rules.extend([
                (QRegularExpression(r"</?[A-Za-z][A-Za-z0-9:-]*"), keyword_format, 0),
                (QRegularExpression(r"\b[A-Za-z:-]+(?=\=)"), function_format, 0),
                (QRegularExpression(r'"[^"\\]*(\\.[^"\\]*)*"'), string_format, 0),
                (QRegularExpression(r"'[^'\\]*(\\.[^'\\]*)*'"), string_format, 0),
                (QRegularExpression(r"<!--.*-->"), comment_format, 0),
                (QRegularExpression(r"<!DOCTYPE[^>]*>"), class_format, 0),
            ])
        elif language == "CSS":
            words = [
                "display", "grid", "flex", "block", "inline", "position", "absolute", "relative",
                "fixed", "sticky", "color", "background", "margin", "padding", "border", "font",
                "width", "height", "min", "max", "transition", "transform", "animation", "hover",
                "root", "media", "import", "keyframes",
            ]
            for word in words:
                self.rules.append((QRegularExpression(rf"\b{word}\b"), keyword_format, 0))
            self.rules.extend([
                (QRegularExpression(r"/\*.*\*/"), comment_format, 0),
                (QRegularExpression(r"#[0-9A-Fa-f]{3,8}\b"), number_format, 0),
                (QRegularExpression(r"\.[A-Za-z_][A-Za-z0-9_-]*"), class_format, 0),
                (QRegularExpression(r"#[A-Za-z_][A-Za-z0-9_-]*"), class_format, 0),
                (QRegularExpression(r"--[A-Za-z_][A-Za-z0-9_-]*"), function_format, 0),
                (QRegularExpression(r'"[^"\\]*(\\.[^"\\]*)*"'), string_format, 0),
                (QRegularExpression(r"'[^'\\]*(\\.[^'\\]*)*'"), string_format, 0),
                (QRegularExpression(r"\b[0-9]+(\.[0-9]+)?(px|rem|em|vh|vw|%)?\b"), number_format, 0),
            ])
        elif language == "JavaScript":
            words = [
                "break", "case", "catch", "class", "const", "continue", "debugger", "default", "delete",
                "do", "else", "export", "extends", "false", "finally", "for", "function", "if", "import",
                "in", "instanceof", "let", "new", "null", "return", "super", "switch", "this", "throw",
                "true", "try", "typeof", "var", "void", "while", "with", "async", "await", "from", "of",
            ]
            for word in words:
                self.rules.append((QRegularExpression(rf"\b{word}\b"), keyword_format, 0))
            self.rules.extend([
                (QRegularExpression(r"//[^\n]*"), comment_format, 0),
                (QRegularExpression(r"/\*.*\*/"), comment_format, 0),
                (QRegularExpression(r'"[^"\\]*(\\.[^"\\]*)*"'), string_format, 0),
                (QRegularExpression(r"'[^'\\]*(\\.[^'\\]*)*'"), string_format, 0),
                (QRegularExpression(r"`[^`\\]*(\\.[^`\\]*)*`"), string_format, 0),
                (QRegularExpression(r"\b[0-9]+(\.[0-9]+)?\b"), number_format, 0),
                (QRegularExpression(r"\b(function|class)\s+([A-Za-z_][A-Za-z0-9_]*)"), class_format, 2),
                (QRegularExpression(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\("), function_format, 1),
            ])
        elif language == "TypeScript":
            words = [
                "abstract", "any", "as", "asserts", "async", "await", "boolean", "break", "case", "catch",
                "class", "const", "constructor", "continue", "declare", "default", "delete", "do", "else", "enum",
                "export", "extends", "false", "finally", "for", "from", "function", "get", "if", "implements",
                "import", "in", "infer", "instanceof", "interface", "keyof", "let", "module", "namespace", "never",
                "new", "null", "number", "object", "of", "override", "private", "protected", "public", "readonly",
                "return", "satisfies", "set", "static", "string", "super", "switch", "symbol", "this", "throw", "true",
                "try", "type", "typeof", "undefined", "unknown", "var", "void", "while", "with", "yield",
            ]
            for word in words:
                self.rules.append((QRegularExpression(rf"\b{word}\b"), keyword_format, 0))
            self.rules.extend([
                (QRegularExpression(r"//[^\n]*"), comment_format, 0),
                (QRegularExpression(r"/\*.*\*/"), comment_format, 0),
                (QRegularExpression(r'"[^"\\]*(\\.[^"\\]*)*"'), string_format, 0),
                (QRegularExpression(r"'[^'\\]*(\\.[^'\\]*)*'"), string_format, 0),
                (QRegularExpression(r"`[^`\\]*(\\.[^`\\]*)*`"), string_format, 0),
                (QRegularExpression(r"\b[0-9]+(\.[0-9]+)?\b"), number_format, 0),
                (QRegularExpression(r"\b(interface|class|type|enum)\s+([A-Za-z_][A-Za-z0-9_]*)"), class_format, 2),
                (QRegularExpression(r"\b(function)\s+([A-Za-z_][A-Za-z0-9_]*)"), function_format, 2),
            ])
        elif language == "Luau":
            words = [
                "and", "break", "continue", "do", "else", "elseif", "end", "export", "false", "for", "function",
                "if", "in", "local", "nil", "not", "or", "repeat", "return", "then", "true", "type", "typeof", "until", "while",
            ]
            for word in words:
                self.rules.append((QRegularExpression(rf"\b{word}\b"), keyword_format, 0))
            self.rules.extend([
                (QRegularExpression(r"--[^\n]*"), comment_format, 0),
                (QRegularExpression(r'"[^"\\]*(\\.[^"\\]*)*"'), string_format, 0),
                (QRegularExpression(r"'[^'\\]*(\\.[^'\\]*)*'"), string_format, 0),
                (QRegularExpression(r"`[^`]*`"), string_format, 0),
                (QRegularExpression(r"\b[0-9]+(\.[0-9]+)?\b"), number_format, 0),
                (QRegularExpression(r"\bfunction\s+([A-Za-z_][A-Za-z0-9_:.]*)"), function_format, 1),
            ])
        elif language == "GDScript":
            words = [
                "and", "as", "assert", "await", "break", "class", "class_name", "const", "continue", "elif", "else",
                "enum", "extends", "false", "for", "func", "if", "in", "is", "match", "not", "null", "or", "pass",
                "preload", "return", "self", "signal", "static", "super", "true", "var", "while", "yield",
            ]
            for word in words:
                self.rules.append((QRegularExpression(rf"\b{word}\b"), keyword_format, 0))
            self.rules.extend([
                (QRegularExpression(r"#[^\n]*"), comment_format, 0),
                (QRegularExpression(r'"[^"\\]*(\\.[^"\\]*)*"'), string_format, 0),
                (QRegularExpression(r"'[^'\\]*(\\.[^'\\]*)*'"), string_format, 0),
                (QRegularExpression(r"\b[0-9]+(\.[0-9]+)?\b"), number_format, 0),
                (QRegularExpression(r"\bfunc\s+([A-Za-z_][A-Za-z0-9_]*)"), function_format, 1),
                (QRegularExpression(r"\bclass_name\s+([A-Za-z_][A-Za-z0-9_]*)"), class_format, 1),
            ])
        elif language == "PHP":
            words = [
                "abstract", "and", "array", "as", "break", "callable", "case", "catch", "class", "clone", "const", "continue",
                "declare", "default", "do", "echo", "else", "elseif", "empty", "endfor", "endforeach", "endif", "endswitch",
                "endwhile", "enum", "extends", "false", "final", "finally", "fn", "for", "foreach", "function", "global", "goto",
                "if", "implements", "include", "include_once", "instanceof", "interface", "isset", "match", "namespace", "new", "null",
                "or", "private", "protected", "public", "readonly", "require", "require_once", "return", "static", "switch", "throw",
                "trait", "true", "try", "use", "var", "while", "xor", "yield",
            ]
            for word in words:
                self.rules.append((QRegularExpression(rf"\b{word}\b", QRegularExpression.PatternOption.CaseInsensitiveOption), keyword_format, 0))
            self.rules.extend([
                (QRegularExpression(r"//[^\n]*"), comment_format, 0),
                (QRegularExpression(r"#[^\n]*"), comment_format, 0),
                (QRegularExpression(r"/\*.*\*/"), comment_format, 0),
                (QRegularExpression(r'"[^"\\]*(\\.[^"\\]*)*"'), string_format, 0),
                (QRegularExpression(r"'[^'\\]*(\\.[^'\\]*)*'"), string_format, 0),
                (QRegularExpression(r"\$[A-Za-z_][A-Za-z0-9_]*"), function_format, 0),
                (QRegularExpression(r"\b[0-9]+(\.[0-9]+)?\b"), number_format, 0),
            ])
        elif language == "PowerShell":
            words = [
                "begin", "break", "catch", "class", "continue", "data", "do", "dynamicparam", "else", "elseif", "end", "enum",
                "exit", "filter", "finally", "for", "foreach", "from", "function", "if", "in", "param", "process", "return", "switch",
                "throw", "trap", "try", "until", "using", "while",
            ]
            for word in words:
                self.rules.append((QRegularExpression(rf"\b{word}\b", QRegularExpression.PatternOption.CaseInsensitiveOption), keyword_format, 0))
            self.rules.extend([
                (QRegularExpression(r"#[^\n]*"), comment_format, 0),
                (QRegularExpression(r'"[^"\\]*(\\.[^"\\]*)*"'), string_format, 0),
                (QRegularExpression(r"'[^']*'"), string_format, 0),
                (QRegularExpression(r"\$[A-Za-z_][A-Za-z0-9_:]*"), function_format, 0),
                (QRegularExpression(r"-[A-Za-z][A-Za-z0-9-]*"), keyword_format, 0),
                (QRegularExpression(r"\b[0-9]+(\.[0-9]+)?\b"), number_format, 0),
            ])
        elif language == "JSON":
            self.rules.extend([
                (QRegularExpression(r'"([^"\\]|\\.)*"(?=\s*:)'), function_format, 0),
                (QRegularExpression(r'"([^"\\]|\\.)*"'), string_format, 0),
                (QRegularExpression(r"\b(true|false|null)\b"), keyword_format, 0),
                (QRegularExpression(r"-?\b[0-9]+(\.[0-9]+)?([eE][+-]?[0-9]+)?\b"), number_format, 0),
            ])
        elif language == "YAML":
            self.rules.extend([
                (QRegularExpression(r"#[^\n]*"), comment_format, 0),
                (QRegularExpression(r"^[\s-]*([A-Za-z0-9_.-]+)(?=\s*:)") , function_format, 1),
                (QRegularExpression(r'"[^"\\]*(\\.[^"\\]*)*"'), string_format, 0),
                (QRegularExpression(r"'[^']*'"), string_format, 0),
                (QRegularExpression(r"\b(true|false|null|yes|no|on|off)\b", QRegularExpression.PatternOption.CaseInsensitiveOption), keyword_format, 0),
                (QRegularExpression(r"-?\b[0-9]+(\.[0-9]+)?\b"), number_format, 0),
            ])
        elif language == "TOML":
            self.rules.extend([
                (QRegularExpression(r"#[^\n]*"), comment_format, 0),
                (QRegularExpression(r"^\s*\[[^\]]+\]"), class_format, 0),
                (QRegularExpression(r"^\s*([A-Za-z0-9_.-]+)(?=\s*=)"), function_format, 1),
                (QRegularExpression(r'"[^"\\]*(\\.[^"\\]*)*"'), string_format, 0),
                (QRegularExpression(r"'[^']*'"), string_format, 0),
                (QRegularExpression(r"\b(true|false)\b"), keyword_format, 0),
                (QRegularExpression(r"-?\b[0-9]+(\.[0-9]+)?\b"), number_format, 0),
            ])
        elif language in {"XML", "Dockerfile", "Shell", "Markdown"}:
            if language == "XML":
                self.rules.extend([
                    (QRegularExpression(r"</?[A-Za-z_][A-Za-z0-9_.:-]*"), keyword_format, 0),
                    (QRegularExpression(r"\b[A-Za-z_:.-]+(?=\=)"), function_format, 0),
                    (QRegularExpression(r'"[^"\\]*(\\.[^"\\]*)*"'), string_format, 0),
                    (QRegularExpression(r"<!--.*-->"), comment_format, 0),
                ])
            elif language == "Markdown":
                self.rules.extend([
                    (QRegularExpression(r"^#{1,6}\s+.*$"), class_format, 0),
                    (QRegularExpression(r"`[^`]+`"), string_format, 0),
                    (QRegularExpression(r"\*\*[^*]+\*\*"), keyword_format, 0),
                    (QRegularExpression(r"^\s*[-*+]\s+"), function_format, 0),
                ])
            else:
                comment_marker = r"#[^\n]*"
                self.rules.append((QRegularExpression(comment_marker), comment_format, 0))
                self.rules.append((QRegularExpression(r'"[^"\\]*(\\.[^"\\]*)*"'), string_format, 0))
                self.rules.append((QRegularExpression(r"'[^']*'"), string_format, 0))
                if language == "Dockerfile":
                    for word in ["FROM", "RUN", "CMD", "LABEL", "EXPOSE", "ENV", "ADD", "COPY", "ENTRYPOINT", "VOLUME", "USER", "WORKDIR", "ARG", "ONBUILD", "STOPSIGNAL", "HEALTHCHECK", "SHELL"]:
                        self.rules.append((QRegularExpression(rf"^\s*{word}\b", QRegularExpression.PatternOption.CaseInsensitiveOption), keyword_format, 0))
                else:
                    for word in ["if", "then", "else", "elif", "fi", "for", "while", "do", "done", "case", "esac", "function", "in"]:
                        self.rules.append((QRegularExpression(rf"\b{word}\b"), keyword_format, 0))
        elif language == "C#":
            words = [
                "abstract", "as", "base", "bool", "break", "byte", "case", "catch", "char", "checked",
                "class", "const", "continue", "decimal", "default", "delegate", "do", "double", "else",
                "enum", "event", "explicit", "extern", "false", "finally", "fixed", "float", "for", "foreach",
                "goto", "if", "implicit", "in", "int", "interface", "internal", "is", "lock", "long", "namespace",
                "new", "null", "object", "operator", "out", "override", "params", "private", "protected", "public",
                "readonly", "ref", "return", "sbyte", "sealed", "short", "sizeof", "stackalloc", "static", "string",
                "struct", "switch", "this", "throw", "true", "try", "typeof", "uint", "ulong", "unchecked", "unsafe",
                "ushort", "using", "virtual", "void", "volatile", "while", "var", "async", "await",
            ]
            for word in words:
                self.rules.append((QRegularExpression(rf"\b{word}\b"), keyword_format, 0))
            self.rules.extend([
                (QRegularExpression(r"//[^\n]*"), comment_format, 0),
                (QRegularExpression(r"/\*.*\*/"), comment_format, 0),
                (QRegularExpression(r'"[^"\\]*(\\.[^"\\]*)*"'), string_format, 0),
                (QRegularExpression(r"'[^'\\]*(\\.[^'\\]*)*'"), string_format, 0),
                (QRegularExpression(r"\b[0-9]+(\.[0-9]+)?\b"), number_format, 0),
                (QRegularExpression(r"\b(class|struct|interface)\s+([A-Za-z_][A-Za-z0-9_]*)"), class_format, 2),
                (QRegularExpression(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\("), function_format, 1),
            ])
        elif language == "SQL":
            words = [
                "SELECT", "FROM", "WHERE", "JOIN", "INNER", "LEFT", "RIGHT", "FULL", "ON", "GROUP", "BY",
                "HAVING", "ORDER", "ASC", "DESC", "INSERT", "INTO", "VALUES", "UPDATE", "SET", "DELETE",
                "CREATE", "TABLE", "ALTER", "DROP", "PRIMARY", "KEY", "FOREIGN", "REFERENCES", "CASE", "WHEN",
                "THEN", "ELSE", "END", "COUNT", "SUM", "AVG", "MIN", "MAX", "DISTINCT", "AS", "LIMIT",
                "AND", "OR", "NOT", "NULL", "IS", "LIKE", "BETWEEN", "IN",
            ]
            for word in words:
                self.rules.append((QRegularExpression(rf"\b{word}\b", QRegularExpression.PatternOption.CaseInsensitiveOption), keyword_format, 0))
            self.rules.extend([
                (QRegularExpression(r"--[^\n]*"), comment_format, 0),
                (QRegularExpression(r"/\*.*\*/"), comment_format, 0),
                (QRegularExpression(r'"[^"\\]*(\\.[^"\\]*)*"'), string_format, 0),
                (QRegularExpression(r"'[^'\\]*(\\.[^'\\]*)*'"), string_format, 0),
                (QRegularExpression(r"\b[0-9]+(\.[0-9]+)?\b"), number_format, 0),
            ])
        self.rehighlight()

    def highlightBlock(self, text):
        for pattern, char_format, group in self.rules:
            iterator = pattern.globalMatch(text)
            while iterator.hasNext():
                match = iterator.next()
                start = match.capturedStart(group)
                length = match.capturedLength(group)
                if start >= 0 and length > 0:
                    self.setFormat(start, length, char_format)


class CodeEditor(QPlainTextEdit):
    def __init__(self, theme, language_name=DEFAULT_LANGUAGE, parent=None, font_point_size=12, font_family=""):
        super().__init__(parent)
        self.theme = theme
        self.language_name = language_name
        self.file_path = None
        self.file_encoding = "utf-8"
        self.untitled_name = f"без имени{LANGUAGES[language_name]['extension']}"
        self.highlighter = CodeHighlighter(self.document(), theme, language_name)
        self.line_number_area = LineNumberArea(self)
        self.tab_size = 4
        self.indent_size = 4
        self.insert_spaces = language_name in {"Python", "GDScript", "YAML"}
        self.font_point_size = max(8, min(32, int(font_point_size)))
        self.font_family = str(font_family or "").strip()
        self.completion_enabled = True
        self.completion_show_snippets = True
        self.completion_accept_tab = True
        self.active_snippet = None
        self.active_token = ""
        self.dismissed_token = ""
        self.last_seen_token = ""
        self.completion_hint = QLabel(self.viewport())
        self.completion_hint.setObjectName("SnippetHint")
        self.completion_hint.setVisible(False)
        self.completion_hint.setWordWrap(False)
        self._apply_completion_hint_style()
        self._builtin_completion_query = None
        self._builtin_completion_items: dict[str, CompletionItem] = {}
        self._builtin_tab_cycle_active = False
        self._builtin_tab_cycle_index = -1
        self._builtin_completion_model = QStringListModel(self)
        self._builtin_completer = QCompleter(self._builtin_completion_model, self)
        self._builtin_completer.setWidget(self)
        self._builtin_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._builtin_completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self._builtin_completer.popup().setToolTip("Tab — выбрать следующий · Space — вставить выбранный")
        self._builtin_completer.activated.connect(self._insert_builtin_completion)
        self._builtin_completion_timer = QTimer(self)
        self._builtin_completion_timer.setSingleShot(True)
        self._builtin_completion_timer.setInterval(140)
        self._builtin_completion_timer.timeout.connect(self._refresh_builtin_completion)

        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        self.cursorPositionChanged.connect(self.highlight_current_line)
        self.cursorPositionChanged.connect(self.update_completion_hint)
        self.cursorPositionChanged.connect(self._schedule_builtin_completion)
        self.textChanged.connect(self.update_completion_hint)
        self.textChanged.connect(self._schedule_builtin_completion)

        self.apply_editor_font_settings()
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)

        self.update_line_number_area_width(0)
        self.highlight_current_line()


    def apply_editor_font_settings(self):
        if self.font_family:
            font = QFont(self.font_family)
        else:
            font = QFont()
            try:
                font.setFamilies(["Cascadia Code", "Consolas", "Courier New", "monospace"])
            except Exception:
                font = QFont("Consolas")
            font.setStyleHint(QFont.StyleHint.Monospace)
            font.setFixedPitch(True)
        font.setPointSize(self.font_point_size)
        self.setFont(font)
        self.document().setDefaultFont(font)
        self.viewport().setFont(font)
        self.refresh_tab_stop_distance()

    def refresh_tab_stop_distance(self):
        space_width = self.fontMetrics().horizontalAdvance(" ")
        if space_width <= 0:
            space_width = 8
        self.setTabStopDistance(float(space_width * max(1, int(self.tab_size))))
        self.update_line_number_area_width(0)

    def set_editor_font_size(self, point_size: int):
        self.font_point_size = max(8, min(32, int(point_size)))
        self.apply_editor_font_settings()
        self.highlight_current_line()
        self.viewport().update()

    def set_editor_font_family(self, family: str):
        self.font_family = str(family or "").strip()
        self.apply_editor_font_settings()
        self._apply_completion_hint_style()
        self.highlight_current_line()
        self.viewport().update()

    def set_indent_options(self, tab_size: int = 4, indent_size: int = 4, insert_spaces: bool = False):
        self.tab_size = max(1, min(12, int(tab_size)))
        self.indent_size = max(1, min(12, int(indent_size)))
        self.insert_spaces = bool(insert_spaces)
        self.refresh_tab_stop_distance()

    def set_theme(self, theme):
        self.theme = theme
        self.highlighter.set_theme(theme, self.language_name)
        self.apply_editor_font_settings()
        self._apply_completion_hint_style()
        self.highlight_current_line()
        self.line_number_area.update()

    def set_language(self, language_name):
        self.language_name = language_name
        self.highlighter.set_theme(self.theme, language_name)
        self.hide_completion_hint()
        self._hide_builtin_completion()
        self.update_completion_hint()

    def line_number_area_width(self):
        digits = len(str(max(1, self.blockCount())))
        metrics = self.fontMetrics()
        # Leave room for wide custom glyphs and high-DPI fonts. A too-narrow
        # viewport margin was the reason leading digits appeared to disappear.
        return max(36, metrics.horizontalAdvance("9" * digits) + metrics.horizontalAdvance("00"))

    def update_line_number_area_width(self, _):
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def update_line_number_area(self, rect, dy):
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(
                0,
                rect.y(),
                self.line_number_area.width(),
                rect.height(),
            )

        if rect.contains(self.viewport().rect()):
            self.update_line_number_area_width(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        content_rect = self.contentsRect()
        self.line_number_area.setGeometry(
            QRect(
                content_rect.left(),
                content_rect.top(),
                self.line_number_area_width(),
                content_rect.height(),
            )
        )

    def line_number_area_paint_event(self, event):
        painter = QPainter(self.line_number_area)
        painter.fillRect(event.rect(), QColor(self.theme["panel"]))
        painter.setPen(QColor(self.theme["muted"]))

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + int(self.blockBoundingRect(block).height())

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)
                painter.drawText(
                    0,
                    top,
                    self.line_number_area.width() - 8,
                    self.fontMetrics().height(),
                    Qt.AlignmentFlag.AlignRight,
                    number,
                )
            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())
            block_number += 1

    def highlight_current_line(self):
        selections = []
        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()
            selection.format.setBackground(QColor(self.theme["line"]))
            selection.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            selections.append(selection)
        self.setExtraSelections(selections)

    def set_completion_options(self, enabled: bool, show_snippets: bool, accept_tab: bool):
        self.completion_enabled = bool(enabled)
        self.completion_show_snippets = bool(show_snippets)
        self.completion_accept_tab = bool(accept_tab)
        if not (self.completion_enabled and self.completion_show_snippets):
            self.hide_completion_hint()
        else:
            self.update_completion_hint()
        if not self.completion_enabled:
            self._hide_builtin_completion()
        else:
            self._schedule_builtin_completion()

    def _apply_completion_hint_style(self):
        if not hasattr(self, "completion_hint"):
            return
        hint_family = self.font_family.replace('"', '') if self.font_family else "Segoe UI"
        self.completion_hint.setStyleSheet(f"""
        QLabel#SnippetHint {{
            background: {self.theme['panel2']};
            color: {self.theme['text']};
            border: 1px solid {self.theme['accent']};
            border-radius: 9px;
            padding: 6px 9px;
            font-family: "{hint_family}", "Segoe UI", Arial;
            font-size: 12px;
            font-weight: 700;
        }}
        """)

    def _current_token_info(self) -> tuple[str, int, int]:
        cursor = self.textCursor()
        line = cursor.block().text()
        end = cursor.positionInBlock()
        start = end
        allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_:#.-")
        while start > 0 and line[start - 1] in allowed:
            start -= 1
        return line[start:end], start, end

    def _scan_line_for_comment_or_string(self, text: str, markers: tuple[str, ...], quotes: tuple[str, ...] = ("'", '"', '`')) -> bool:
        quote = None
        escaped = False
        i = 0
        while i < len(text):
            ch = text[i]
            if escaped:
                escaped = False
                i += 1
                continue
            if ch == "\\":
                escaped = True
                i += 1
                continue
            if quote:
                if ch == quote:
                    quote = None
                i += 1
                continue
            for marker in markers:
                if text.startswith(marker, i):
                    return True
            if ch in quotes:
                quote = ch
            i += 1
        return bool(quote)

    def _inside_multiline_comment_on_line(self, prefix: str, open_marker: str, close_marker: str) -> bool:
        return prefix.rfind(open_marker) > prefix.rfind(close_marker)

    def is_inside_string_or_comment(self) -> bool:
        cursor = self.textCursor()
        line_prefix = cursor.block().text()[:cursor.positionInBlock()]
        language = self.language_name
        if language == "Python":
            return self._scan_line_for_comment_or_string(line_prefix, ("#",), ("'", '"'))
        if language == "SQL":
            return (
                self._scan_line_for_comment_or_string(line_prefix, ("--",), ("'", '"'))
                or self._inside_multiline_comment_on_line(line_prefix, "/*", "*/")
            )
        if language == "HTML":
            return (
                self._scan_line_for_comment_or_string(line_prefix, tuple(), ("'", '"'))
                or self._inside_multiline_comment_on_line(line_prefix, "<!--", "-->")
            )
        if language in {"C++", "Java", "JavaScript", "C#", "CSS"}:
            markers = ("//",) if language != "CSS" else tuple()
            return (
                self._scan_line_for_comment_or_string(line_prefix, markers, ("'", '"', '`'))
                or self._inside_multiline_comment_on_line(line_prefix, "/*", "*/")
            )
        return False

    def find_snippet_for_token(self, token: str):
        snippets = SNIPPETS.get(self.language_name, [])
        if not token or not snippets:
            return None
        exact = [item for item in snippets if item["trigger"].lower() == token.lower()]
        if exact:
            return exact[0]
        return None

    def _schedule_builtin_completion(self):
        if not hasattr(self, "_builtin_completion_timer"):
            return
        if not self.completion_enabled:
            self._hide_builtin_completion()
            return
        self._builtin_completion_timer.start()

    def _hide_builtin_completion(self):
        if hasattr(self, "_builtin_completer"):
            self._builtin_completer.popup().hide()
        self._builtin_completion_query = None
        self._builtin_completion_items = {}
        self._builtin_tab_cycle_active = False
        self._builtin_tab_cycle_index = -1

    def _refresh_builtin_completion(self):
        if not self.completion_enabled or self.hasFocus() is False:
            self._hide_builtin_completion()
            return
        cursor = self.textCursor()
        query = completion_query(self.language_name, self.toPlainText(), cursor.position())
        if query is None or not query.items:
            self._hide_builtin_completion()
            return
        token, _start, _end = self._current_token_info()
        if self.active_snippet and self.active_snippet.get("trigger", "").lower() == token.lower():
            self._hide_builtin_completion()
            return
        labels: list[str] = []
        item_map: dict[str, CompletionItem] = {}
        for item in query.items:
            display = f"{item.label}    {item.detail}" if item.detail else item.label
            if display in item_map:
                continue
            labels.append(display)
            item_map[display] = item
        if not labels:
            self._hide_builtin_completion()
            return
        self._builtin_completion_query = query
        self._builtin_completion_items = item_map
        self._builtin_tab_cycle_active = False
        self._builtin_tab_cycle_index = -1
        self._builtin_completion_model.setStringList(labels)
        self._builtin_completer.setCompletionPrefix(query.prefix)
        popup = self._builtin_completer.popup()
        popup.setCurrentIndex(self._builtin_completer.completionModel().index(0, 0))
        popup.setMinimumWidth(min(620, max(280, self.viewport().width() // 2)))
        self._builtin_completer.complete(self.cursorRect())

    def _cycle_builtin_completion(self) -> bool:
        """Select suggestions with Tab without inserting them immediately.

        The first Tab arms row zero, later presses advance and wrap around.  The
        selected text is committed by Space (with a trailing space), Enter or a
        mouse click.
        """
        if not self._builtin_completion_items:
            return False
        model = self._builtin_completer.completionModel()
        count = model.rowCount()
        if count <= 0:
            return False
        if not self._builtin_tab_cycle_active:
            self._builtin_tab_cycle_active = True
            self._builtin_tab_cycle_index = 0
        else:
            self._builtin_tab_cycle_index = (self._builtin_tab_cycle_index + 1) % count
        index = model.index(self._builtin_tab_cycle_index, 0)
        popup = self._builtin_completer.popup()
        popup.setCurrentIndex(index)
        popup.scrollTo(index)
        return index.isValid()

    def _accept_current_builtin_completion(self, trailing_space: bool = False) -> bool:
        index = self._builtin_completer.popup().currentIndex()
        if not index.isValid():
            return False
        if not self._insert_builtin_completion(str(index.data())):
            return False
        if trailing_space:
            cursor = self.textCursor()
            cursor.insertText(" ")
            self.setTextCursor(cursor)
        return True

    def _insert_builtin_completion(self, display: str):
        query = self._builtin_completion_query
        item = self._builtin_completion_items.get(str(display))
        if query is None or item is None:
            return False
        edits = [*item.additional_edits, CompletionTextEdit(query.start, query.end, item.insert_text)]
        final_position = query.start + len(item.insert_text)
        for edit in item.additional_edits:
            if edit.start <= query.start:
                final_position += len(edit.new_text) - (edit.end - edit.start)
        cursor = self.textCursor()
        cursor.beginEditBlock()
        for edit in sorted(edits, key=lambda value: (value.start, value.end), reverse=True):
            cursor.setPosition(edit.start)
            cursor.setPosition(edit.end, QTextCursor.MoveMode.KeepAnchor)
            cursor.insertText(edit.new_text)
        cursor.endEditBlock()
        cursor.setPosition(final_position)
        self.setTextCursor(cursor)
        self._hide_builtin_completion()
        self.setFocus()
        return True

    def update_completion_hint(self):
        if not hasattr(self, "completion_hint"):
            return
        if not (self.completion_enabled and self.completion_show_snippets):
            self.hide_completion_hint()
            return
        token, _start, _end = self._current_token_info()
        if token != self.last_seen_token:
            self.dismissed_token = ""
            self.last_seen_token = token
        if not token or token == self.dismissed_token or self.is_inside_string_or_comment():
            self.hide_completion_hint()
            return
        snippet = self.find_snippet_for_token(token)
        if not snippet:
            self.hide_completion_hint()
            return
        self.active_snippet = snippet
        self.active_token = token
        display_label = snippet['label']
        if self.language_name == "C++" and self._cpp_has_using_namespace_std():
            display_label = display_label.replace("std::", "")
        self.completion_hint.setText(f"Tab → {snippet['trigger']} · {display_label} — {snippet['description']}   Esc закрыть")
        self.completion_hint.adjustSize()
        rect = self.cursorRect()
        x = min(rect.left(), max(8, self.viewport().width() - self.completion_hint.width() - 8))
        y = rect.bottom() + 8
        if y + self.completion_hint.height() > self.viewport().height():
            y = max(8, rect.top() - self.completion_hint.height() - 8)
        self.completion_hint.move(x, y)
        self.completion_hint.raise_()
        self.completion_hint.show()

    def hide_completion_hint(self):
        if hasattr(self, "completion_hint"):
            self.completion_hint.hide()
        self.active_snippet = None
        self.active_token = ""

    def dismiss_completion_hint(self):
        if self.active_token:
            self.dismissed_token = self.active_token
        self.hide_completion_hint()

    def _snippet_text_with_current_indent(self, raw_text: str) -> tuple[str, int | None]:
        cursor = self.textCursor()
        line = cursor.block().text()
        current_indent = re.match(r"\s*", line).group(0)
        marker_index = raw_text.find(CURSOR_MARKER)
        clean = raw_text.replace(CURSOR_MARKER, "")
        if current_indent:
            clean = clean.replace("\n", "\n" + current_indent)
            if marker_index >= 0:
                before_marker = raw_text[:marker_index].replace(CURSOR_MARKER, "")
                marker_index = len(before_marker.replace("\n", "\n" + current_indent))
        return clean, marker_index if marker_index >= 0 else None

    def _cpp_has_using_namespace_std(self) -> bool:
        if self.language_name != "C++":
            return False
        text = self.toPlainText()
        return re.search(r"^\s*using\s+namespace\s+std\s*;?", text, re.MULTILINE) is not None

    def _resolve_context_insert_text(self, snippet: dict) -> str:
        text = snippet.get("insertText", "")
        if self.language_name != "C++":
            return text
        trigger = snippet.get("trigger", "")
        has_using_std = self._cpp_has_using_namespace_std()
        if has_using_std:
            replacements = {
                "std::cout": "cout",
                "std::cin": "cin",
                "std::cerr": "cerr",
                "std::endl": "endl",
                "std::string": "string",
                "std::getline": "getline",
                "std::exception": "exception",
            }
            for old_text, new_text in replacements.items():
                text = text.replace(old_text, new_text)
            if trigger == "main" and "using namespace std;" not in text:
                text = text.replace("#include <string>\n\n", "#include <string>\n\nusing namespace std;\n\n")
        else:
            if trigger == "main" and "using namespace std;" in text:
                text = text.replace("\nusing namespace std;\n", "")
                text = text.replace("\n    string name;", "\n    std::string name;")
                text = text.replace("cout <<", "std::cout <<")
                text = text.replace("cin", "std::cin")
                text = text.replace("getline(", "std::getline(")
                text = text.replace(" << endl", " << std::endl")
        return text

    def insert_active_snippet(self):
        if not self.active_snippet:
            return False
        token, start, end = self._current_token_info()
        if not token:
            return False
        cursor = self.textCursor()
        block_start = cursor.block().position()
        insertion_start = block_start + start
        snippet = self.active_snippet
        raw_insert_text = self._resolve_context_insert_text(snippet)
        insert_text, marker_index = self._snippet_text_with_current_indent(raw_insert_text)
        cursor.beginEditBlock()
        cursor.setPosition(insertion_start)
        cursor.setPosition(block_start + end, QTextCursor.MoveMode.KeepAnchor)
        cursor.removeSelectedText()
        cursor.insertText(insert_text)
        cursor.endEditBlock()

        final_cursor = self.textCursor()
        if marker_index is not None:
            final_cursor.setPosition(insertion_start + marker_index)
        else:
            target = snippet.get("cursorTarget") or ""
            target_index = insert_text.find(target) if target else -1
            if target_index >= 0:
                final_cursor.setPosition(insertion_start + target_index)
                final_cursor.setPosition(insertion_start + target_index + len(target), QTextCursor.MoveMode.KeepAnchor)
            else:
                final_cursor.setPosition(insertion_start + len(insert_text))
        self.setTextCursor(final_cursor)
        self.hide_completion_hint()
        return True

    def keyPressEvent(self, event):
        popup = self._builtin_completer.popup() if hasattr(self, "_builtin_completer") else None
        if popup is not None and popup.isVisible():
            if event.key() == Qt.Key.Key_Escape:
                self._hide_builtin_completion()
                event.accept()
                return
            if event.key() == Qt.Key.Key_Tab and self.completion_accept_tab:
                if self._cycle_builtin_completion():
                    event.accept()
                    return
            if event.key() == Qt.Key.Key_Space and self._builtin_tab_cycle_active:
                if self._accept_current_builtin_completion(trailing_space=True):
                    event.accept()
                    return
            if event.key() in {Qt.Key.Key_Return, Qt.Key.Key_Enter}:
                if self._accept_current_builtin_completion():
                    event.accept()
                    return
        if event.key() == Qt.Key.Key_Escape and self.completion_hint.isVisible():
            self.dismiss_completion_hint()
            event.accept()
            return
        if event.key() == Qt.Key.Key_Tab and self.completion_accept_tab and self.completion_hint.isVisible():
            if self.insert_active_snippet():
                event.accept()
                return
        if event.key() == Qt.Key.Key_Tab and self.insert_spaces:
            self.textCursor().insertText(" " * max(1, int(self.indent_size)))
            event.accept()
            return
        super().keyPressEvent(event)



class InteractiveConsole(QPlainTextEdit):
    """Console that keeps historical output read-only while allowing inline stdin.

    Only the live input region at the bottom is editable. Program/terminal output is
    inserted before that region, so asynchronous output cannot destroy what the user
    is currently typing.
    """

    def __init__(self, parent=None, prompt: str = ""):
        super().__init__(parent)
        self._prompt = str(prompt or "")
        self._submit_callback = None
        self._input_start = 0
        self._prompt_start = 0
        self._history: list[str] = []
        self._history_index: int | None = None
        self.setReadOnly(False)
        self.setUndoRedoEnabled(False)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self._install_prompt("")

    def set_submit_callback(self, callback):
        self._submit_callback = callback

    def _document_end(self) -> int:
        return max(0, self.document().characterCount() - 1)

    def _current_input(self) -> str:
        cursor = QTextCursor(self.document())
        cursor.setPosition(max(0, min(self._document_end(), int(self._input_start))))
        cursor.movePosition(QTextCursor.MoveOperation.End, QTextCursor.MoveMode.KeepAnchor)
        return cursor.selectedText().replace("\u2029", "\n")

    def current_input(self) -> str:
        return self._current_input()

    def _remove_live_input(self) -> str:
        buffer = self._current_input()
        cursor = self.textCursor()
        cursor.setPosition(max(0, min(self._document_end(), int(self._prompt_start))))
        cursor.movePosition(QTextCursor.MoveOperation.End, QTextCursor.MoveMode.KeepAnchor)
        cursor.removeSelectedText()
        self.setTextCursor(cursor)
        return buffer

    def _install_prompt(self, buffer: str = ""):
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.setTextCursor(cursor)
        self._prompt_start = cursor.position()
        if self._prompt:
            cursor.insertText(self._prompt)
        self._input_start = cursor.position()
        if buffer:
            cursor.insertText(str(buffer))
        self.setTextCursor(cursor)
        self.ensureCursorVisible()

    def append_output(self, text: str):
        text = str(text or "")
        buffer = self._remove_live_input()
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        if text:
            cursor.insertText(text)
        self.setTextCursor(cursor)
        self._install_prompt(buffer)

    def appendPlainText(self, text: str):
        text = str(text or "")
        if not text.endswith("\n"):
            text += "\n"
        self.append_output(text)

    def insertPlainText(self, text: str):
        # Programmatic writes in Astra are output, not user edits.
        self.append_output(str(text or ""))

    def setPlainText(self, text: str):
        QPlainTextEdit.setPlainText(self, str(text or ""))
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.setTextCursor(cursor)
        if self.toPlainText() and not self.toPlainText().endswith("\n"):
            QPlainTextEdit.insertPlainText(self, "\n")
        self._install_prompt("")

    def clear(self):
        QPlainTextEdit.clear(self)
        self._history_index = None
        self._install_prompt("")

    def set_input_text(self, text: str):
        self._replace_input(str(text or ""))

    def _replace_input(self, text: str):
        cursor = self.textCursor()
        cursor.setPosition(max(0, min(self._document_end(), int(self._input_start))))
        cursor.movePosition(QTextCursor.MoveOperation.End, QTextCursor.MoveMode.KeepAnchor)
        cursor.removeSelectedText()
        cursor.insertText(text)
        self.setTextCursor(cursor)
        self.ensureCursorVisible()

    def _clamp_edit_cursor(self):
        cursor = self.textCursor()
        if cursor.hasSelection() and cursor.selectionStart() < self._input_start:
            cursor.clearSelection()
            cursor.movePosition(QTextCursor.MoveOperation.End)
        elif cursor.position() < self._input_start:
            cursor.movePosition(QTextCursor.MoveOperation.End)
        self.setTextCursor(cursor)

    def _submit_current_input(self):
        text = self._current_input()
        if text.strip():
            if not self._history or self._history[-1] != text:
                self._history.append(text)
            if len(self._history) > 200:
                self._history = self._history[-200:]
        self._history_index = None
        # Freeze the submitted line into history, create the next live prompt,
        # then let asynchronous/synchronous output insert itself before it.
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText("\n")
        self.setTextCursor(cursor)
        self._prompt_start = cursor.position()
        self._input_start = cursor.position()
        self._install_prompt("")
        if callable(self._submit_callback):
            self._submit_callback(text)

    def _history_move(self, delta: int):
        if not self._history:
            return
        if self._history_index is None:
            self._history_index = len(self._history)
        self._history_index = max(0, min(len(self._history), self._history_index + delta))
        text = "" if self._history_index == len(self._history) else self._history[self._history_index]
        self._replace_input(text)

    def keyPressEvent(self, event):
        key = event.key()
        modifiers = event.modifiers()
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._submit_current_input()
            event.accept()
            return
        if key == Qt.Key.Key_Up and not (modifiers & Qt.KeyboardModifier.ShiftModifier):
            self._history_move(-1)
            event.accept()
            return
        if key == Qt.Key.Key_Down and not (modifiers & Qt.KeyboardModifier.ShiftModifier):
            self._history_move(1)
            event.accept()
            return
        if key == Qt.Key.Key_Home:
            cursor = self.textCursor()
            cursor.setPosition(self._input_start)
            self.setTextCursor(cursor)
            event.accept()
            return
        if key == Qt.Key.Key_Backspace:
            cursor = self.textCursor()
            if not cursor.hasSelection() and cursor.position() <= self._input_start:
                event.accept()
                return
        if key == Qt.Key.Key_Left:
            cursor = self.textCursor()
            if not cursor.hasSelection() and cursor.position() <= self._input_start:
                event.accept()
                return
        # Copy/select operations may inspect history, but any real edit is forced
        # back into the live input area.
        copy_only = (modifiers & Qt.KeyboardModifier.ControlModifier) and key in (Qt.Key.Key_C, Qt.Key.Key_A)
        navigation = key in (Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_End, Qt.Key.Key_PageUp, Qt.Key.Key_PageDown)
        if not copy_only and not navigation:
            self._clamp_edit_cursor()
        super().keyPressEvent(event)



class AstralMessageBox(QDialog):
    class StandardButton:
        Ok = 0x00000400
        Yes = 0x00004000
        No = 0x00010000
        Cancel = 0x00400000

    class ButtonRole:
        AcceptRole = 0
        RejectRole = 1
        DestructiveRole = 2
        ActionRole = 3

    class Icon:
        Information = "info"
        Warning = "warning"
        Critical = "error"
        Question = "question"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._parent_window = parent
        self._title = "Astra Studio"
        self._text = ""
        self._informative_text = ""
        self._icon = self.Icon.Information
        self._clicked_button = None
        self._button_values = {}
        self.setModal(True)
        self.setMinimumWidth(420)
        self.setWindowTitle(self._title)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(20, 20, 20, 18)
        self._layout.setSpacing(12)
        self._title_label = QLabel(self._title)
        self._title_label.setObjectName("DialogTitle")
        self._title_label.setWordWrap(True)
        self._text_label = QLabel()
        self._text_label.setObjectName("DialogText")
        self._text_label.setWordWrap(True)
        self._info_label = QLabel()
        self._info_label.setObjectName("DialogInfo")
        self._info_label.setWordWrap(True)
        self._buttons_layout = QHBoxLayout()
        self._buttons_layout.addStretch(1)
        self._layout.addWidget(self._title_label)
        self._layout.addWidget(self._text_label)
        self._layout.addWidget(self._info_label)
        self._layout.addLayout(self._buttons_layout)
        self._apply_style()

    def _theme_value(self, key: str, fallback: str) -> str:
        parent = self._parent_window
        if parent is not None and hasattr(parent, "theme"):
            return parent.theme.get(key, fallback)
        return fallback

    def _accent(self) -> str:
        parent = self._parent_window
        if parent is not None and hasattr(parent, "theme"):
            return parent.theme.get("accent", "#18d9ff")
        return "#18d9ff"

    def _apply_style(self):
        bg = self._theme_value("panel", "#090d15")
        panel = self._theme_value("panel2", "#0d1420")
        text = self._theme_value("text", "#f2f7ff")
        muted = self._theme_value("muted", "#79889d")
        border = self._theme_value("border", "#1b2636")
        accent = self._accent()
        parent = self._parent_window
        ui_font = max(10, min(22, int(getattr(parent, "ui_font_size", 13))))
        self.setStyleSheet(f"""
        QDialog {{
            background: {bg};
            border: 1px solid {border};
        }}
        QLabel#DialogTitle {{
            color: {accent};
            font-size: 16px;
            font-weight: 900;
        }}
        QLabel#DialogText {{
            color: {text};
            font-size: {ui_font}px;
            line-height: 150%;
        }}
        QLabel#DialogInfo {{
            color: {muted};
            font-size: 12px;
            line-height: 145%;
        }}
        QPushButton {{
            background: {panel};
            color: {text};
            border: 1px solid {border};
            border-radius: 11px;
            padding: 8px 14px;
            min-width: 88px;
            font-weight: 700;
        }}
        QPushButton:hover {{
            border-color: {accent};
            color: {accent};
        }}
        QPushButton#PrimaryButton {{
            background: {accent};
            color: #020407;
            border: 0;
            font-weight: 900;
        }}
        """)

    def setIcon(self, icon):
        self._icon = icon

    def setWindowTitle(self, title):
        self._title = title
        super().setWindowTitle(title)
        if hasattr(self, "_title_label"):
            self._title_label.setText(title)

    def setText(self, text):
        self._text = text
        self._text_label.setText(text)

    def setInformativeText(self, text):
        self._informative_text = text
        self._info_label.setText(text)
        self._info_label.setVisible(bool(text))

    def addButton(self, text, role):
        button = QPushButton(text)
        if role == self.ButtonRole.AcceptRole:
            button.setObjectName("PrimaryButton")
        self._buttons_layout.addWidget(button)
        self._button_values[button] = role
        button.clicked.connect(lambda: self._finish(button))
        return button

    def clickedButton(self):
        return self._clicked_button

    def _finish(self, button):
        self._clicked_button = button
        self.accept()

    def exec(self):
        if not self._button_values:
            self.addButton("OK", self.ButtonRole.AcceptRole)
        self._apply_style()
        return super().exec()

    @classmethod
    def _button_specs(cls, buttons: int, default: int | None = None):
        mapping = [
            (cls.StandardButton.Yes, "Да", cls.ButtonRole.AcceptRole),
            (cls.StandardButton.No, "Нет", cls.ButtonRole.RejectRole),
            (cls.StandardButton.Cancel, "Отмена", cls.ButtonRole.RejectRole),
            (cls.StandardButton.Ok, "OK", cls.ButtonRole.AcceptRole),
        ]
        specs = [(value, text, role) for value, text, role in mapping if buttons & value]
        if not specs:
            specs = [(cls.StandardButton.Ok, "OK", cls.ButtonRole.AcceptRole)]
        return specs

    @classmethod
    def _show(cls, parent, title, text, icon="info", buttons=None, default_button=None):
        dialog = cls(parent)
        dialog.setIcon(icon)
        dialog.setWindowTitle(title)
        dialog.setText(text)
        if buttons is None:
            buttons = cls.StandardButton.Ok
        value_by_button = {}
        for value, label, role in cls._button_specs(buttons, default_button):
            btn = dialog.addButton(label, role)
            value_by_button[btn] = value
            if value == default_button:
                btn.setObjectName("PrimaryButton")
        dialog.exec()
        clicked = dialog.clickedButton()
        if clicked is not None:
            return value_by_button.get(clicked, cls.StandardButton.Ok)
        # Closing the dialog with Esc/× must never be interpreted as implicit consent.
        if buttons & cls.StandardButton.Cancel:
            return cls.StandardButton.Cancel
        if buttons & cls.StandardButton.No:
            return cls.StandardButton.No
        if buttons & cls.StandardButton.Ok:
            return cls.StandardButton.Ok
        return default_button or cls.StandardButton.Ok

    @classmethod
    def information(cls, parent, title, text, *args, **kwargs):
        return cls._show(parent, title, text, cls.Icon.Information, cls.StandardButton.Ok)

    @classmethod
    def warning(cls, parent, title, text, buttons=None, default_button=None, *args, **kwargs):
        return cls._show(parent, title, text, cls.Icon.Warning, buttons or cls.StandardButton.Ok, default_button)

    @classmethod
    def critical(cls, parent, title, text, *args, **kwargs):
        return cls._show(parent, title, text, cls.Icon.Critical, cls.StandardButton.Ok)

    @classmethod
    def question(cls, parent, title, text, buttons=None, default_button=None, *args, **kwargs):
        return cls._show(parent, title, text, cls.Icon.Question, buttons or (cls.StandardButton.Yes | cls.StandardButton.No), default_button)


QMessageBox = AstralMessageBox

class AstraStudio(QMainWindow):
    def __init__(self):
        super().__init__()
        self.run_process = None
        self.terminal_process = None
        self.install_process = None
        self.update_network = QNetworkAccessManager(self)
        self._app_update_reply = None
        self._app_download_reply = None
        self._app_download_file = None
        self._app_download_path = None
        self._app_download_manifest = None
        self._pending_update_command = None
        self.task_manager = TaskManager(self)
        self.active_task_context = {}
        self.untitled_counter = 1
        self.compiled_binary_path = None
        self.data_dir = app_data_dir()
        self.temp_dir = Path(tempfile.gettempdir()) / APP_DIR_NAME
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.build_dir = self.temp_dir / "build"
        self.build_dir.mkdir(parents=True, exist_ok=True)
        self.user_builds_dir = default_builds_dir()
        self.internal_workspace_dir = self.data_dir / "workspace"
        self.internal_workspace_dir.mkdir(parents=True, exist_ok=True)
        self.workspace_dir = self.internal_workspace_dir
        self.settings_path = self.data_dir / "settings.json"
        legacy_settings_path = Path.home() / ".astra_studio" / "settings.json"
        if not self.settings_path.exists() and legacy_settings_path.exists():
            try:
                self.settings_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(legacy_settings_path, self.settings_path)
            except OSError:
                pass

        self.current_project_config_path = ""
        self.current_project_name = "Рабочая папка"
        self.project_main_folder = self.workspace_dir
        self.attached_project_folders = []
        self.recent_projects = []
        self.project_python_interpreter = ""
        self.project_commands = {key: "" for key in COMMAND_KEYS}
        self.project_staffedup_meta: dict[str, object] = {}
        self.test_explorer_last_run = None
        self.test_explorer_discovered = []
        self.test_explorer_adapters = []
        self.test_explorer_active_adapter = ""
        self.git_repo_root: Path | None = None
        self.git_state: GitRepositoryState | None = None
        self.git_available = False
        self.git_last_diff_path = ""
        self.git_last_diff_staged = False
        self.editor_tab_size = 4
        self.editor_indent_size = 4
        self.editor_insert_spaces = True
        self.ui_font_size = 13
        self.editor_font_size = 12
        self.console_font_size = 10
        self.global_font_name = DEFAULT_GLOBAL_FONT
        self.global_font_family = "Segoe UI"
        self._application_font_ids = {}
        self.logo_frame_blur_percent = 18
        self.logo_frame_transparency_percent = 42

        self.current_theme_name = DEFAULT_THEME
        self.current_accent_name = DEFAULT_ACCENT
        self.current_language_name = DEFAULT_LANGUAGE
        self.transparency_enabled = False
        self.window_opacity_percent = 92
        self.always_on_top_enabled = False
        self.autocomplete_enabled = True
        self.show_snippets_enabled = True
        self.accept_tab_enabled = True
        self.format_on_save_enabled = False
        self.custom_wallpaper_path = ""
        self.preset_wallpaper_name = DEFAULT_PRESET_WALLPAPER
        self.wallpaper_enabled = True
        self.wallpaper_all_windows = True
        self.wallpaper_dim_percent = 55
        self.wallpaper_blur_px = 25
        self.disable_console_wallpaper = False
        self.editor_bg_transparency_percent = 0
        self.console_bg_transparency_percent = 15
        self.settings_bg_transparency_percent = 15
        self.project_bg_transparency_percent = 15
        self.aux_bg_transparency_percent = 15
        self.editor_blur_percent = 20
        self.console_blur_percent = 20
        self.settings_blur_percent = 20
        self.project_blur_percent = 20
        self.save_window_sizes_enabled = True
        self.saved_geometry_hex = ""
        self.saved_root_splitter_sizes = []
        self.saved_main_splitter_sizes = []
        self.saved_vertical_splitter_sizes = []
        self.python_auto_install_enabled = True
        self.python_install_always_ask = True
        self.python_unknown_auto_install_enabled = False
        self.open_install_log_enabled = True
        self.ignored_missing_modules = set()
        self.exe_build_mode = "Консольное приложение"
        self.cpp_using_namespace_std_enabled = True
        self.last_run_language = ""
        self.last_run_source_path = None
        self.last_missing_python_module = ""
        self.log_path = self.data_dir / "astra_studio.log"
        self._ensure_log_utf8_bom()
        self._load_settings()
        self._load_global_font_family()
        self._apply_application_font()
        # LSP servers are persistent processes and must not use the single-slot
        # TaskManager reserved for builds/installations. Create the manager only
        # after settings restore the actual workspace/project root. Release 3.1
        # layers document sync, diagnostics and interactive editor features on it.
        self.lsp_manager = LspManager(
            self.data_dir / "lsp_servers.json",
            self.workspace_dir,
            self,
        )
        self.quality_diagnostics = {}
        self._queued_lsp_requests = {}
        self._lsp_request_serial = 0
        self.lsp_manager.logMessage.connect(
            lambda language, message: self.write_log(f"[LSP:{language}] {message}")
        )
        self.lsp_manager.permanentFailure.connect(
            lambda language, message: self.write_log(f"[LSP:{language}] FAILED: {message}")
        )
        self.lsp_manager.diagnosticsPublished.connect(self._on_lsp_diagnostics_published)
        self.lsp_manager.diagnosticsReset.connect(self._on_lsp_diagnostics_reset)
        self.lsp_manager.interactiveResult.connect(self._on_lsp_interactive_result)
        self.lsp_manager.stateChanged.connect(self._on_lsp_state_changed)
        self.lsp_manager.initialized.connect(self._on_lsp_initialized)
        self.theme = dict(THEMES[self.current_theme_name])
        self.theme["accent"] = ACCENTS[self.current_accent_name]

        self.setWindowTitle(f"{APP_NAME} — {APP_VERSION}")
        self.resize(1480, 840)
        self.setMinimumSize(980, 640)

        self._ensure_workspace_examples()
        self._build_ui()
        self._setup_shortcuts()
        self.apply_theme()
        self._restore_saved_geometry()
        self.apply_window_opacity()
        if self.always_on_top_enabled:
            QTimer.singleShot(0, self.apply_always_on_top)
        if self.current_project_config_path and Path(self.current_project_config_path).exists():
            self.open_project_config(Path(self.current_project_config_path))
        if not hasattr(self, "tabs") or self.tabs.count() == 0:
            self.new_from_template()
        self.start_terminal()

    def _restore_saved_geometry(self):
        if not self.save_window_sizes_enabled or not self.saved_geometry_hex:
            return
        try:
            self.restoreGeometry(QByteArray.fromHex(self.saved_geometry_hex.encode("ascii")))
        except Exception as exc:
            self.write_exception_log("Не удалось восстановить размер окна", exc)

    def _load_global_font_family(self) -> str:
        asset = GLOBAL_FONT_OPTIONS.get(self.global_font_name, "")
        if not asset:
            self.global_font_family = "Segoe UI"
            return self.global_font_family
        font_path = resource_path(asset)
        cache_key = str(font_path.resolve())
        font_id = self._application_font_ids.get(cache_key)
        if font_id is None:
            font_id = QFontDatabase.addApplicationFont(str(font_path)) if font_path.is_file() else -1
            self._application_font_ids[cache_key] = font_id
        families = QFontDatabase.applicationFontFamilies(font_id) if font_id >= 0 else []
        if families:
            self.global_font_family = families[0]
        else:
            self.global_font_family = "Segoe UI"
            self.write_log(f"Не удалось загрузить шрифт интерфейса: {font_path}")
        return self.global_font_family

    def _selected_custom_font_family(self) -> str:
        return self.global_font_family if self.global_font_name != DEFAULT_GLOBAL_FONT else ""

    def _font_css_stack(self, *, code: bool = False) -> str:
        family = self._selected_custom_font_family().replace('"', "")
        if family:
            return f'"{family}", "Segoe UI", Arial'
        if code:
            return '"Cascadia Code", "Consolas", "Courier New", monospace'
        return '"Segoe UI", Arial'

    def _apply_application_font(self):
        app = QApplication.instance()
        if app is None:
            return
        font = QFont(self.global_font_family)
        font.setPointSize(max(8, min(22, int(self.ui_font_size))))
        app.setFont(font)

    def _load_settings(self):
        if not self.settings_path.exists():
            return
        try:
            data = json.loads(self.settings_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        theme = data.get("theme")
        accent = data.get("accent")
        language = data.get("language")
        workspace = data.get("workspace")
        transparency_enabled = data.get("transparency_enabled")
        opacity_percent = data.get("opacity_percent")
        always_on_top = data.get("always_on_top")
        autocomplete_enabled = data.get("autocomplete_enabled")
        show_snippets_enabled = data.get("show_snippets_enabled")
        accept_tab_enabled = data.get("accept_tab_enabled")
        format_on_save_enabled = data.get("format_on_save_enabled")
        custom_wallpaper_path = data.get("custom_wallpaper_path")
        preset_wallpaper = data.get("preset_wallpaper")
        wallpaper_enabled = data.get("wallpaper_enabled")
        wallpaper_all_windows = data.get("wallpaper_all_windows")
        wallpaper_dim_percent = data.get("wallpaper_dim_percent")
        wallpaper_blur_px = data.get("wallpaper_blur_px")
        disable_console_wallpaper = data.get("disable_console_wallpaper")
        editor_bg_transparency_percent = data.get("editor_bg_transparency_percent")
        console_bg_transparency_percent = data.get("console_bg_transparency_percent")
        settings_bg_transparency_percent = data.get("settings_bg_transparency_percent")
        project_bg_transparency_percent = data.get("project_bg_transparency_percent")
        aux_bg_transparency_percent = data.get("aux_bg_transparency_percent")
        editor_blur_percent = data.get("editor_blur_percent")
        console_blur_percent = data.get("console_blur_percent")
        settings_blur_percent = data.get("settings_blur_percent")
        project_blur_percent = data.get("project_blur_percent")
        save_window_sizes_enabled = data.get("save_window_sizes_enabled")
        saved_geometry_hex = data.get("window_geometry")
        saved_root_splitter_sizes = data.get("root_splitter_sizes")
        saved_main_splitter_sizes = data.get("main_splitter_sizes")
        saved_vertical_splitter_sizes = data.get("vertical_splitter_sizes")
        python_auto_install_enabled = data.get("python_auto_install_enabled")
        python_install_always_ask = data.get("python_install_always_ask")
        python_unknown_auto_install_enabled = data.get("python_unknown_auto_install_enabled")
        open_install_log_enabled = data.get("open_install_log_enabled")
        ignored_missing_modules = data.get("ignored_missing_modules")
        exe_build_mode = data.get("exe_build_mode")
        cpp_using_namespace_std_enabled = data.get("cpp_using_namespace_std_enabled")
        current_project_config_path = data.get("current_project_config_path")
        recent_projects = data.get("recent_projects")
        editor_tab_size = data.get("editor_tab_size")
        editor_indent_size = data.get("editor_indent_size")
        editor_insert_spaces = data.get("editor_insert_spaces")
        ui_font_size = data.get("ui_font_size")
        editor_font_size = data.get("editor_font_size")
        console_font_size = data.get("console_font_size")
        global_font_name = data.get("global_font_name")
        logo_frame_blur_percent = data.get("logo_frame_blur_percent")
        logo_frame_transparency_percent = data.get("logo_frame_transparency_percent")
        if theme in THEMES:
            self.current_theme_name = theme
        if accent in ACCENTS:
            self.current_accent_name = accent
        if language in LANGUAGES:
            self.current_language_name = language
        if isinstance(transparency_enabled, bool):
            self.transparency_enabled = transparency_enabled
        if isinstance(opacity_percent, int):
            self.window_opacity_percent = max(35, min(100, opacity_percent))
        if isinstance(always_on_top, bool):
            self.always_on_top_enabled = always_on_top
        if isinstance(autocomplete_enabled, bool):
            self.autocomplete_enabled = autocomplete_enabled
        if isinstance(show_snippets_enabled, bool):
            self.show_snippets_enabled = show_snippets_enabled
        if isinstance(accept_tab_enabled, bool):
            self.accept_tab_enabled = accept_tab_enabled
        if isinstance(format_on_save_enabled, bool):
            self.format_on_save_enabled = format_on_save_enabled
        if isinstance(custom_wallpaper_path, str) and custom_wallpaper_path:
            wallpaper = Path(custom_wallpaper_path)
            if wallpaper.exists() and wallpaper.is_file():
                self.custom_wallpaper_path = str(wallpaper)
        if preset_wallpaper in ASTRA_WALLPAPERS:
            self.preset_wallpaper_name = preset_wallpaper
        if isinstance(wallpaper_enabled, bool):
            self.wallpaper_enabled = wallpaper_enabled
        if isinstance(wallpaper_all_windows, bool):
            self.wallpaper_all_windows = wallpaper_all_windows
        if isinstance(wallpaper_dim_percent, int):
            self.wallpaper_dim_percent = max(0, min(85, wallpaper_dim_percent))
        if isinstance(wallpaper_blur_px, int):
            self.wallpaper_blur_px = max(0, min(100, wallpaper_blur_px))
        if isinstance(disable_console_wallpaper, bool):
            self.disable_console_wallpaper = disable_console_wallpaper
        if isinstance(editor_bg_transparency_percent, int):
            self.editor_bg_transparency_percent = max(0, min(100, editor_bg_transparency_percent))
        if isinstance(console_bg_transparency_percent, int):
            self.console_bg_transparency_percent = max(0, min(100, console_bg_transparency_percent))
        if isinstance(settings_bg_transparency_percent, int):
            self.settings_bg_transparency_percent = max(0, min(100, settings_bg_transparency_percent))
        if isinstance(project_bg_transparency_percent, int):
            self.project_bg_transparency_percent = max(0, min(100, project_bg_transparency_percent))
        if isinstance(aux_bg_transparency_percent, int):
            self.aux_bg_transparency_percent = max(0, min(100, aux_bg_transparency_percent))
        if isinstance(editor_blur_percent, int):
            self.editor_blur_percent = max(0, min(100, editor_blur_percent))
        if isinstance(console_blur_percent, int):
            self.console_blur_percent = max(0, min(100, console_blur_percent))
        if isinstance(settings_blur_percent, int):
            self.settings_blur_percent = max(0, min(100, settings_blur_percent))
        if isinstance(project_blur_percent, int):
            self.project_blur_percent = max(0, min(100, project_blur_percent))
        if isinstance(save_window_sizes_enabled, bool):
            self.save_window_sizes_enabled = save_window_sizes_enabled
        if isinstance(saved_geometry_hex, str):
            self.saved_geometry_hex = saved_geometry_hex
        if isinstance(saved_root_splitter_sizes, list):
            self.saved_root_splitter_sizes = saved_root_splitter_sizes
        if isinstance(saved_main_splitter_sizes, list):
            self.saved_main_splitter_sizes = saved_main_splitter_sizes
        if isinstance(saved_vertical_splitter_sizes, list):
            self.saved_vertical_splitter_sizes = saved_vertical_splitter_sizes
        if isinstance(python_auto_install_enabled, bool):
            self.python_auto_install_enabled = python_auto_install_enabled
        if isinstance(python_install_always_ask, bool):
            self.python_install_always_ask = python_install_always_ask
        if isinstance(python_unknown_auto_install_enabled, bool):
            self.python_unknown_auto_install_enabled = python_unknown_auto_install_enabled
        if isinstance(open_install_log_enabled, bool):
            self.open_install_log_enabled = open_install_log_enabled
        if isinstance(ignored_missing_modules, list):
            self.ignored_missing_modules = set(str(item).lower() for item in ignored_missing_modules)
        if isinstance(exe_build_mode, str) and exe_build_mode in ("Консольное приложение", "Оконное приложение"):
            self.exe_build_mode = exe_build_mode
        if isinstance(cpp_using_namespace_std_enabled, bool):
            self.cpp_using_namespace_std_enabled = cpp_using_namespace_std_enabled
        if isinstance(current_project_config_path, str):
            self.current_project_config_path = current_project_config_path
        if isinstance(recent_projects, list):
            self.recent_projects = [str(item) for item in recent_projects if isinstance(item, str)]
        if isinstance(editor_tab_size, int):
            self.editor_tab_size = max(1, min(12, editor_tab_size))
        if isinstance(editor_indent_size, int):
            self.editor_indent_size = max(1, min(12, editor_indent_size))
        if isinstance(editor_insert_spaces, bool):
            self.editor_insert_spaces = editor_insert_spaces
        if isinstance(ui_font_size, int):
            self.ui_font_size = max(10, min(22, ui_font_size))
        if isinstance(editor_font_size, int):
            self.editor_font_size = max(8, min(32, editor_font_size))
        if isinstance(console_font_size, int):
            self.console_font_size = max(8, min(28, console_font_size))
        if global_font_name in GLOBAL_FONT_OPTIONS:
            self.global_font_name = global_font_name
        if isinstance(logo_frame_blur_percent, int):
            self.logo_frame_blur_percent = max(0, min(100, logo_frame_blur_percent))
        if isinstance(logo_frame_transparency_percent, int):
            self.logo_frame_transparency_percent = max(0, min(100, logo_frame_transparency_percent))
        if workspace:
            path = Path(workspace)
            if path.exists() and path.is_dir() and can_write_to_directory(path):
                self.workspace_dir = path
                self.project_main_folder = path

    def _save_settings(self):
        data = {
            "theme": self.current_theme_name,
            "accent": self.current_accent_name,
            "language": self.current_language_name,
            "workspace": str(self.workspace_dir),
            "transparency_enabled": self.transparency_enabled,
            "opacity_percent": self.window_opacity_percent,
            "always_on_top": self.always_on_top_enabled,
            "autocomplete_enabled": self.autocomplete_enabled,
            "show_snippets_enabled": self.show_snippets_enabled,
            "accept_tab_enabled": self.accept_tab_enabled,
            "format_on_save_enabled": self.format_on_save_enabled,
            "custom_wallpaper_path": self.custom_wallpaper_path,
            "preset_wallpaper": self.preset_wallpaper_name,
            "wallpaper_enabled": self.wallpaper_enabled,
            "wallpaper_all_windows": self.wallpaper_all_windows,
            "wallpaper_dim_percent": self.wallpaper_dim_percent,
            "wallpaper_blur_px": self.wallpaper_blur_px,
            "disable_console_wallpaper": self.disable_console_wallpaper,
            "editor_bg_transparency_percent": self.editor_bg_transparency_percent,
            "console_bg_transparency_percent": self.console_bg_transparency_percent,
            "settings_bg_transparency_percent": self.settings_bg_transparency_percent,
            "project_bg_transparency_percent": self.project_bg_transparency_percent,
            "aux_bg_transparency_percent": self.aux_bg_transparency_percent,
            "editor_blur_percent": self.editor_blur_percent,
            "console_blur_percent": self.console_blur_percent,
            "settings_blur_percent": self.settings_blur_percent,
            "project_blur_percent": self.project_blur_percent,
            "save_window_sizes_enabled": self.save_window_sizes_enabled,
            "window_geometry": bytes(self.saveGeometry().toHex()).decode("ascii") if self.save_window_sizes_enabled else "",
            "root_splitter_sizes": self.root_splitter.sizes() if self.save_window_sizes_enabled and hasattr(self, "root_splitter") else [],
            "main_splitter_sizes": self.main_splitter.sizes() if self.save_window_sizes_enabled and hasattr(self, "main_splitter") else [],
            "vertical_splitter_sizes": self.vertical_splitter.sizes() if self.save_window_sizes_enabled and hasattr(self, "vertical_splitter") else [],
            "python_auto_install_enabled": self.python_auto_install_enabled,
            "python_install_always_ask": self.python_install_always_ask,
            "python_unknown_auto_install_enabled": self.python_unknown_auto_install_enabled,
            "open_install_log_enabled": self.open_install_log_enabled,
            "ignored_missing_modules": sorted(self.ignored_missing_modules),
            "exe_build_mode": self.exe_build_mode,
            "cpp_using_namespace_std_enabled": self.cpp_using_namespace_std_enabled,
            "current_project_config_path": self.current_project_config_path,
            "recent_projects": self.recent_projects[:10],
            "editor_tab_size": self.editor_tab_size,
            "editor_indent_size": self.editor_indent_size,
            "editor_insert_spaces": self.editor_insert_spaces,
            "ui_font_size": self.ui_font_size,
            "editor_font_size": self.editor_font_size,
            "console_font_size": self.console_font_size,
            "global_font_name": self.global_font_name,
            "logo_frame_blur_percent": self.logo_frame_blur_percent,
            "logo_frame_transparency_percent": self.logo_frame_transparency_percent,
        }
        try:
            self.settings_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError:
            pass

    def _ensure_workspace_examples(self):
        """Create starter files only in Astra's internal workspace.

        Never create or rewrite files inside a user-selected project/workspace.
        """
        examples = {
            "example.py": PYTHON_TEMPLATE,
            "example.cpp": CPP_TEMPLATE,
            "Main.java": JAVA_TEMPLATE,
            "index.html": HTML_TEMPLATE,
            "style.css": CSS_TEMPLATE,
            "script.js": JAVASCRIPT_TEMPLATE,
            "script.ts": TYPESCRIPT_TEMPLATE,
            "script.luau": LUAU_TEMPLATE,
            "script.gd": GDSCRIPT_TEMPLATE,
            "index.php": PHP_TEMPLATE,
            "script.ps1": POWERSHELL_TEMPLATE,
            "Program.cs": CSHARP_TEMPLATE,
            "query.sql": SQL_TEMPLATE,
            "config.json": JSON_TEMPLATE,
            "config.yaml": YAML_TEMPLATE,
            "README.md": MARKDOWN_TEMPLATE,
        }
        target_dir = self.internal_workspace_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        for filename, text in examples.items():
            path = target_dir / filename
            if path.exists():
                continue
            try:
                path.write_text(text, encoding="utf-8")
            except OSError as exc:
                self.write_exception_log(f"Не удалось создать стартовый пример: {filename}", exc)

    def _build_ui(self):
        root = QWidget()
        root.setObjectName("Root")
        self.root = root
        self.setCentralWidget(root)
        self.background_label = QLabel(root)
        self.background_label.setObjectName("BackgroundWallpaper")
        # Keep wallpapers at their native pixel size. Resizing the IDE now only
        # changes the centered crop and never rescales widgets or the image.
        self.background_label.setScaledContents(False)
        self.background_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.background_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.background_label.lower()
        self.wallpaper_dim_overlay = QWidget(root)
        self.wallpaper_dim_overlay.setObjectName("WallpaperDimOverlay")
        self.wallpaper_dim_overlay.lower()
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(14, 14, 14, 14)
        root_layout.setSpacing(12)

        self.sidebar_scroll = QScrollArea()
        self.sidebar_scroll.setObjectName("SidebarScroll")
        self.sidebar_scroll.setWidgetResizable(True)
        self.sidebar_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.sidebar_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.sidebar_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.sidebar_scroll.setMinimumWidth(236)
        self.sidebar_scroll.setMaximumWidth(306)
        self.sidebar_scroll.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)

        self.sidebar = QFrame()
        self.sidebar.setObjectName("Sidebar")
        self.sidebar.setMinimumWidth(216)
        self.sidebar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.MinimumExpanding)
        side_layout = QVBoxLayout(self.sidebar)
        side_layout.setContentsMargins(14, 18, 14, 18)
        side_layout.setSpacing(9)
        self.sidebar_scroll.setWidget(self.sidebar)

        self.logo_card = QFrame()
        self.logo_card.setObjectName("LogoCard")
        self.logo_card.setMinimumHeight(88)
        self.logo_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        logo_card_layout = QVBoxLayout(self.logo_card)
        logo_card_layout.setContentsMargins(12, 10, 12, 10)
        logo_card_layout.setSpacing(4)
        self.logo = QLabel()
        self.logo.setObjectName("Logo")
        self.logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.logo.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        title_pixmap = QPixmap(str(resource_path("assets/astra_studio_title.png")))
        if not title_pixmap.isNull():
            self.logo.setPixmap(title_pixmap.scaledToHeight(52, Qt.TransformationMode.SmoothTransformation))
            self.logo.setMinimumHeight(56)
        else:
            self.logo.setText("Astra Studio")
        self.subtitle = QLabel("среда для кода · alaron")
        self.subtitle.setObjectName("Subtitle")
        self.subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_card_layout.addWidget(self.logo)
        logo_card_layout.addWidget(self.subtitle)

        self.sidebar_shell = QFrame()
        self.sidebar_shell.setObjectName("SidebarShell")
        self.sidebar_shell.setMinimumWidth(236)
        self.sidebar_shell.setMaximumWidth(306)
        self.sidebar_shell.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        sidebar_shell_layout = QVBoxLayout(self.sidebar_shell)
        sidebar_shell_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_shell_layout.setSpacing(8)
        sidebar_shell_layout.addWidget(self.logo_card)
        sidebar_shell_layout.addWidget(self.sidebar_scroll, 1)

        self.language_card = QFrame()
        self.language_card.setObjectName("LanguageCard")
        self.language_card.setMinimumHeight(88)
        self.language_card.setMinimumWidth(0)
        self.language_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        language_layout = QVBoxLayout(self.language_card)
        language_layout.setContentsMargins(12, 10, 12, 12)
        language_layout.setSpacing(7)
        self.language_title = QLabel("ЯЗЫК ФАЙЛА")
        self.language_title.setObjectName("SectionTitle")
        self.language_combo = NoWheelComboBox()
        self.language_combo.setMinimumHeight(36)
        self.language_combo.setMinimumWidth(0)
        self.language_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.language_combo.addItems(VISIBLE_LANGUAGES)
        self.language_combo.setCurrentText(self.current_language_name)
        language_layout.addWidget(self.language_title)
        language_layout.addWidget(self.language_combo)

        self.btn_nav_editor = QPushButton("▦  Скрыть боковую панель")
        self.btn_nav_installer = QPushButton("⚙  Установщик")
        self.btn_nav_settings = QPushButton("◈  Настройки")
        self.btn_nav_developer = QPushButton("✦  О проекте")
        self.btn_nav_python_libs = QPushButton("▧  Библиотеки Python")
        self.btn_nav_lsp = QPushButton("⌁  LSP / Outline")
        self.btn_installer = self.btn_nav_installer

        self.btn_run = QPushButton("▶  Запустить   F5")
        self.btn_run.setObjectName("PrimaryButton")
        self.btn_compile = QPushButton("◆  Проверить код")
        self.btn_format = QPushButton("↹  Форматировать   Shift+Alt+F")
        self.btn_lint = QPushButton("✓  Lint текущего файла")
        self.btn_build_exe = QPushButton("⧉  Собрать EXE")
        self.btn_stop = QPushButton("■  Остановить")
        self.btn_new = QPushButton("+  Создать файл")
        self.btn_enter_typer = QPushButton("⌨  Имитация ввода")
        self.btn_enter_typer.setObjectName("TemplateButton")
        self.btn_open = QPushButton("⌁  Открыть файл")
        self.btn_save = QPushButton("✓  Сохранить")
        self.btn_save_as = QPushButton("⇢  Сохранить как")
        self.btn_open_folder = QPushButton("▣  Открыть папку")
        self.btn_create_project = QPushButton("✦  Создать проект")
        self.btn_open_project = QPushButton("⌁  Открыть проект")
        self.btn_add_project_folder = QPushButton("+  Добавить папку")
        self.btn_remove_project_folder = QPushButton("×  Убрать папку")
        self.btn_refresh_project = QPushButton("↻  Обновить проект")
        self.btn_new_project_folder = QPushButton("+  Новая папка")
        self.btn_open_project_folder = QPushButton("▣  Открыть в проводнике")

        self.btn_project_run = QPushButton("▶  Run Project")
        self.btn_project_build = QPushButton("◆  Build Project")
        self.btn_project_test = QPushButton("✓  Test Project")
        self.btn_project_install = QPushButton("↓  Install Project")
        self.btn_project_commands = QPushButton("⚙  Команды проекта")
        self.btn_test_explorer = QPushButton("🧪  Test Explorer")
        self.btn_git_source_control = QPushButton("⑂  Git / Source Control")
        self.btn_project_search = QPushButton("⌕  Поиск по проекту")
        self.btn_project_doctor = QPushButton("✚  Project Doctor")
        self.btn_ai_context = QPushButton("✧  AI Context")

        for button in [
            self.btn_nav_editor,
            self.btn_nav_installer,
            self.btn_nav_settings,
            self.btn_nav_developer,
            self.btn_nav_python_libs,
            self.btn_nav_lsp,
            self.btn_run,
            self.btn_compile,
            self.btn_format,
            self.btn_lint,
            self.btn_build_exe,
            self.btn_stop,
            self.btn_new,
            self.btn_enter_typer,
            self.btn_open,
            self.btn_save,
            self.btn_save_as,
            self.btn_open_folder,
            self.btn_create_project,
            self.btn_open_project,
            self.btn_add_project_folder,
            self.btn_remove_project_folder,
            self.btn_refresh_project,
            self.btn_new_project_folder,
            self.btn_open_project_folder,
            self.btn_project_run,
            self.btn_project_build,
            self.btn_project_test,
            self.btn_project_install,
            self.btn_project_commands,
            self.btn_test_explorer,
            self.btn_git_source_control,
            self.btn_project_search,
            self.btn_project_doctor,
            self.btn_ai_context,
        ]:
            button.setMinimumHeight(34)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            button.setToolTip(button.text().replace("  ", " ").strip())

        side_layout.addWidget(self.language_card)
        side_layout.addSpacing(8)
        side_layout.addWidget(self.btn_run)
        side_layout.addWidget(self.btn_compile)
        side_layout.addWidget(self.btn_format)
        side_layout.addWidget(self.btn_lint)
        side_layout.addWidget(self.btn_build_exe)
        side_layout.addWidget(self.btn_stop)
        side_layout.addSpacing(10)
        side_layout.addWidget(self.btn_new)
        side_layout.addWidget(self.btn_enter_typer)
        side_layout.addWidget(self.btn_open)
        side_layout.addWidget(self.btn_save)
        side_layout.addWidget(self.btn_save_as)
        side_layout.addWidget(self.btn_open_folder)
        side_layout.addWidget(self.btn_create_project)
        side_layout.addWidget(self.btn_open_project)
        side_layout.addSpacing(10)
        side_layout.addWidget(self.btn_nav_editor)
        side_layout.addWidget(self.btn_nav_installer)
        side_layout.addWidget(self.btn_nav_settings)
        side_layout.addWidget(self.btn_nav_python_libs)
        side_layout.addWidget(self.btn_nav_lsp)
        side_layout.addWidget(self.btn_nav_developer)
        side_layout.addSpacing(12)

        self.theme_label = QLabel("Тема интерфейса")
        self.theme_label.setObjectName("MiniLabel")
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(THEMES.keys())
        self.theme_combo.setCurrentText(self.current_theme_name)

        self.accent_label = QLabel("Акцентный цвет")
        self.accent_label.setObjectName("MiniLabel")
        self.accent_combo = QComboBox()
        self.accent_combo.addItems(ACCENTS.keys())
        self.accent_combo.setCurrentText(self.current_accent_name)

        self.opacity_toggle = QCheckBox("Полупрозрачный режим")
        self.opacity_toggle.setObjectName("OpacityToggle")
        self.opacity_toggle.setChecked(self.transparency_enabled)
        self.opacity_label = QLabel()
        self.opacity_label.setObjectName("MiniLabel")
        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setObjectName("OpacitySlider")
        self.opacity_slider.setMinimum(35)
        self.opacity_slider.setMaximum(100)
        self.opacity_slider.setSingleStep(1)
        self.opacity_slider.setPageStep(5)
        self.opacity_slider.setValue(self.window_opacity_percent)
        self.update_opacity_label()

        self.topmost_toggle = QCheckBox("Закрепить поверх всех окон")
        self.topmost_toggle.setObjectName("OpacityToggle")
        self.topmost_toggle.setChecked(self.always_on_top_enabled)

        self.autocomplete_toggle = QCheckBox("Включить автодополнение по Tab")
        self.autocomplete_toggle.setObjectName("OpacityToggle")
        self.autocomplete_toggle.setChecked(self.autocomplete_enabled)
        self.show_snippets_toggle = QCheckBox("Показывать сниппеты")
        self.show_snippets_toggle.setObjectName("OpacityToggle")
        self.show_snippets_toggle.setChecked(self.show_snippets_enabled)
        self.accept_tab_toggle = QCheckBox("Принимать подсказку по Tab")
        self.accept_tab_toggle.setObjectName("OpacityToggle")
        self.accept_tab_toggle.setChecked(self.accept_tab_enabled)
        self.format_on_save_toggle = QCheckBox("Форматировать при сохранении")
        self.format_on_save_toggle.setObjectName("OpacityToggle")
        self.format_on_save_toggle.setChecked(self.format_on_save_enabled)

        self.auto_install_libs_toggle = QCheckBox("Включить автоустановку Python-библиотек")
        self.auto_install_libs_toggle.setObjectName("OpacityToggle")
        self.auto_install_libs_toggle.setChecked(self.python_auto_install_enabled)
        self.always_ask_install_toggle = QCheckBox("Всегда спрашивать перед установкой")
        self.always_ask_install_toggle.setObjectName("OpacityToggle")
        self.always_ask_install_toggle.setChecked(self.python_install_always_ask)
        self.unknown_auto_install_toggle = QCheckBox("Автоустановка неизвестных import по совпадающему имени PyPI")
        self.unknown_auto_install_toggle.setObjectName("OpacityToggle")
        self.unknown_auto_install_toggle.setChecked(self.python_unknown_auto_install_enabled)
        self.unknown_auto_install_toggle.setToolTip("Если import не найден во встроенном реестре, Astra попробует pip install <имя import>. Используй только для доверенных проектов.")
        self.open_install_log_toggle = QCheckBox("Открывать лог установки")
        self.open_install_log_toggle.setObjectName("OpacityToggle")
        self.open_install_log_toggle.setChecked(self.open_install_log_enabled)

        self.exe_mode_label = QLabel("Режим сборки Python EXE")
        self.exe_mode_label.setObjectName("MiniLabel")
        self.exe_mode_combo = QComboBox()
        self.exe_mode_combo.addItems(["Консольное приложение", "Оконное приложение"])
        self.exe_mode_combo.setCurrentText(self.exe_build_mode)
        self.cpp_using_std_toggle = QCheckBox("C++: добавлять using namespace std в стартовый шаблон")
        self.cpp_using_std_toggle.setObjectName("OpacityToggle")
        self.cpp_using_std_toggle.setChecked(self.cpp_using_namespace_std_enabled)
        self.tab_width_label = QLabel("Tab width = 4 · Indent width = 4 · 1 Tab визуально равен 4 пробелам")
        self.tab_width_label.setObjectName("Muted")
        self.tab_width_label.setWordWrap(True)

        self.wallpaper_label = QLabel()
        self.wallpaper_label.setObjectName("MiniLabel")
        self.wallpaper_label.setWordWrap(True)
        self.btn_choose_wallpaper = QPushButton("▧  Выбрать обои из файла")
        self.btn_clear_wallpaper = QPushButton("×  Убрать обои")
        self.preset_wallpaper_combo = QComboBox()
        self.preset_wallpaper_combo.addItems(ASTRA_WALLPAPERS.keys())
        self.preset_wallpaper_combo.setCurrentText(self.preset_wallpaper_name)
        self.btn_apply_astra_profile = QPushButton("✦  Применить профиль Astra")
        self.btn_apply_astra_profile.setObjectName("PrimaryButton")
        self.btn_apply_angel404_profile = QPushButton("✦  Применить профиль Angel 404")
        self.btn_apply_angel404_profile.setObjectName("PrimaryButton")
        self.wallpaper_all_toggle = QCheckBox("Использовать обои во всех окнах")
        self.wallpaper_all_toggle.setObjectName("OpacityToggle")
        self.wallpaper_all_toggle.setChecked(self.wallpaper_all_windows)
        self.disable_console_wallpaper_toggle = QCheckBox("Отключить обои в консоли")
        self.disable_console_wallpaper_toggle.setObjectName("OpacityToggle")
        self.disable_console_wallpaper_toggle.setChecked(self.disable_console_wallpaper)
        self.wallpaper_dim_label = QLabel()
        self.wallpaper_dim_label.setObjectName("MiniLabel")
        self.wallpaper_dim_slider = QSlider(Qt.Orientation.Horizontal)
        self.wallpaper_dim_slider.setObjectName("OpacitySlider")
        self.wallpaper_dim_slider.setRange(0, 85)
        self.wallpaper_dim_slider.setValue(self.wallpaper_dim_percent)
        self.wallpaper_blur_label = QLabel()
        self.wallpaper_blur_label.setObjectName("MiniLabel")
        self.wallpaper_blur_slider = QSlider(Qt.Orientation.Horizontal)
        self.wallpaper_blur_slider.setObjectName("OpacitySlider")
        self.wallpaper_blur_slider.setRange(0, 100)
        self.wallpaper_blur_slider.setValue(self.wallpaper_blur_px)
        simple_panel_transparency = int(round((self.editor_bg_transparency_percent + self.console_bg_transparency_percent + self.settings_bg_transparency_percent + self.project_bg_transparency_percent + self.aux_bg_transparency_percent) / 5))
        self.panel_transparency_label, self.panel_transparency_slider = self._make_percent_slider("Прозрачность панелей", simple_panel_transparency, 0, 100)
        self.logo_frame_blur_label, self.logo_frame_blur_slider = self._make_percent_slider("Размытие рамки логотипа", self.logo_frame_blur_percent, 0, 100)
        self.logo_frame_transparency_label, self.logo_frame_transparency_slider = self._make_percent_slider("Прозрачность рамки логотипа", self.logo_frame_transparency_percent, 0, 100)
        self.appearance_advanced_toggle = QCheckBox("Расширенные настройки оформления")
        self.appearance_advanced_toggle.setObjectName("OpacityToggle")
        self.appearance_advanced_toggle.setChecked(True)

        self.editor_tab_size_label = QLabel()
        self.editor_tab_size_label.setObjectName("MiniLabel")
        self.editor_tab_size_slider = QSlider(Qt.Orientation.Horizontal)
        self.editor_tab_size_slider.setObjectName("OpacitySlider")
        self.editor_tab_size_slider.setRange(1, 12)
        self.editor_tab_size_slider.setValue(self.editor_tab_size)
        self.editor_indent_size_label = QLabel()
        self.editor_indent_size_label.setObjectName("MiniLabel")
        self.editor_indent_size_slider = QSlider(Qt.Orientation.Horizontal)
        self.editor_indent_size_slider.setObjectName("OpacitySlider")
        self.editor_indent_size_slider.setRange(1, 12)
        self.editor_indent_size_slider.setValue(self.editor_indent_size)
        self.editor_insert_spaces_toggle = QCheckBox("Вставлять пробелы вместо Tab")
        self.editor_insert_spaces_toggle.setObjectName("OpacityToggle")
        self.editor_insert_spaces_toggle.setChecked(self.editor_insert_spaces)

        self.ui_font_size_label = QLabel()
        self.ui_font_size_label.setObjectName("MiniLabel")
        self.ui_font_size_slider = QSlider(Qt.Orientation.Horizontal)
        self.ui_font_size_slider.setObjectName("OpacitySlider")
        self.ui_font_size_slider.setRange(10, 22)
        self.ui_font_size_slider.setValue(self.ui_font_size)
        self.editor_font_size_label = QLabel()
        self.editor_font_size_label.setObjectName("MiniLabel")
        self.editor_font_size_slider = QSlider(Qt.Orientation.Horizontal)
        self.editor_font_size_slider.setObjectName("OpacitySlider")
        self.editor_font_size_slider.setRange(8, 32)
        self.editor_font_size_slider.setValue(self.editor_font_size)
        self.console_font_size_label = QLabel()
        self.console_font_size_label.setObjectName("MiniLabel")
        self.console_font_size_slider = QSlider(Qt.Orientation.Horizontal)
        self.console_font_size_slider.setRange(8, 28)
        self.console_font_size_slider.setValue(self.console_font_size)
        self.global_font_label = QLabel("Шрифт всего приложения")
        self.global_font_label.setObjectName("MiniLabel")
        self.global_font_combo = QComboBox()
        self.global_font_combo.addItems(GLOBAL_FONT_OPTIONS.keys())
        self.global_font_combo.setCurrentText(self.global_font_name)
        self.btn_reset_fonts = QPushButton("↺  Сбросить шрифт и размеры")
        self.btn_reset_fonts.setMinimumHeight(34)
        self.btn_reset_fonts.setCursor(Qt.CursorShape.PointingHandCursor)
        self.update_font_labels()

        self.btn_reset_indents = QPushButton("↺  Сбросить отступы")
        self.btn_reset_indents.setMinimumHeight(34)
        self.btn_reset_indents.setCursor(Qt.CursorShape.PointingHandCursor)
        self.update_indent_labels()

        self.editor_transparency_label, self.editor_transparency_slider = self._make_percent_slider("Прозрачность редактора кода", self.editor_bg_transparency_percent, 0, 100)
        self.console_transparency_label, self.console_transparency_slider = self._make_percent_slider("Прозрачность консоли", self.console_bg_transparency_percent, 0, 100)
        self.settings_transparency_label, self.settings_transparency_slider = self._make_percent_slider("Прозрачность настроек", self.settings_bg_transparency_percent, 0, 100)
        self.project_transparency_label, self.project_transparency_slider = self._make_percent_slider("Прозрачность окна проекта", self.project_bg_transparency_percent, 0, 100)
        self.aux_transparency_label, self.aux_transparency_slider = self._make_percent_slider("Прозрачность дополнительных окон", self.aux_bg_transparency_percent, 0, 100)
        self.editor_blur_label, self.editor_blur_slider = self._make_percent_slider("Размытие фона редактора", self.editor_blur_percent, 0, 100)
        self.console_blur_label, self.console_blur_slider = self._make_percent_slider("Размытие фона консоли", self.console_blur_percent, 0, 100)
        self.settings_blur_label, self.settings_blur_slider = self._make_percent_slider("Размытие фона настроек", self.settings_blur_percent, 0, 100)
        self.project_blur_label, self.project_blur_slider = self._make_percent_slider("Размытие фона проекта", self.project_blur_percent, 0, 100)
        self.save_window_sizes_toggle = QCheckBox("Сохранять размеры окон")
        self.save_window_sizes_toggle.setObjectName("OpacityToggle")
        self.save_window_sizes_toggle.setChecked(self.save_window_sizes_enabled)
        self.btn_reset_transparency = QPushButton("↺  Сбросить прозрачность")
        self.btn_reset_blur = QPushButton("↺  Сбросить размытие")
        self.btn_reset_window_sizes = QPushButton("↺  Восстановить размеры окон")
        self.btn_reset_appearance = QPushButton("↺  Оформление по умолчанию")
        for button in [self.btn_reset_transparency, self.btn_reset_blur, self.btn_reset_window_sizes, self.btn_reset_appearance]:
            button.setMinimumHeight(34)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.update_wallpaper_effect_labels()
        for button in [self.btn_choose_wallpaper, self.btn_clear_wallpaper, self.btn_apply_astra_profile, self.btn_apply_angel404_profile]:
            button.setMinimumHeight(34)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.update_wallpaper_label()

        # Настройки оформления теперь находятся в отдельной вкладке «Настройки».
        side_layout.addStretch(1)

        self.workspace_label = QLabel("Рабочая папка:\n" + str(self.workspace_dir))
        self.workspace_label.setObjectName("InfoText")
        self.workspace_label.setWordWrap(True)
        side_layout.addWidget(self.workspace_label)

        self.project_panel = QFrame()
        self.project_panel.setObjectName("ProjectPanel")
        self.project_panel.setMinimumWidth(245)
        project_layout = QVBoxLayout(self.project_panel)
        project_layout.setContentsMargins(12, 14, 12, 12)
        project_layout.setSpacing(8)

        project_title = QLabel("ПРОЕКТ")
        project_title.setObjectName("SectionTitle")
        self.project_hint = QLabel("Двойной клик откроет файл во вкладке")
        self.project_hint.setObjectName("Muted")
        self.project_hint.setWordWrap(True)

        self.project_tree = QTreeWidget()
        self.project_tree.setObjectName("ProjectTree")
        self.project_tree.setColumnCount(1)
        self.project_tree.setHeaderHidden(True)
        self.project_tree.setAnimated(True)
        self.project_tree.setUniformRowHeights(False)
        self.project_tree.setTextElideMode(Qt.TextElideMode.ElideNone)
        self.project_tree.setIndentation(20)
        self.project_tree.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.project_tree.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.project_tree.setToolTip("Проект: двойной клик открывает файл. Длинные пути доступны во всплывающей подсказке.")

        project_button_grid_1 = QHBoxLayout()
        project_button_grid_1.addWidget(self.btn_create_project)
        project_button_grid_1.addWidget(self.btn_open_project)
        project_button_grid_2 = QHBoxLayout()
        project_button_grid_2.addWidget(self.btn_add_project_folder)
        project_button_grid_2.addWidget(self.btn_refresh_project)
        project_button_grid_3 = QHBoxLayout()
        project_button_grid_3.addWidget(self.btn_new_project_folder)
        project_button_grid_3.addWidget(self.btn_open_project_folder)
        project_button_grid_4 = QHBoxLayout()
        project_button_grid_4.addWidget(self.btn_remove_project_folder)

        project_layout.addWidget(project_title)
        project_layout.addWidget(self.project_hint)
        project_command_grid_1 = QHBoxLayout()
        project_command_grid_1.addWidget(self.btn_project_run)
        project_command_grid_1.addWidget(self.btn_project_build)
        project_command_grid_2 = QHBoxLayout()
        project_command_grid_2.addWidget(self.btn_project_test)
        project_command_grid_2.addWidget(self.btn_project_install)
        project_layout.addLayout(project_command_grid_1)
        project_layout.addLayout(project_command_grid_2)
        project_layout.addWidget(self.btn_project_commands)
        project_layout.addWidget(self.btn_test_explorer)
        project_layout.addWidget(self.btn_git_source_control)
        project_tools_grid = QHBoxLayout()
        project_tools_grid.addWidget(self.btn_project_search)
        project_tools_grid.addWidget(self.btn_project_doctor)
        project_layout.addLayout(project_tools_grid)
        project_layout.addWidget(self.btn_ai_context)
        project_layout.addLayout(project_button_grid_1)
        project_layout.addLayout(project_button_grid_2)
        project_layout.addLayout(project_button_grid_3)
        project_layout.addLayout(project_button_grid_4)
        project_layout.addWidget(self.project_tree)

        self.tabs = QTabWidget()
        self.tabs.setObjectName("EditorTabs")
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.setDocumentMode(True)

        editor_card = QFrame()
        editor_card.setObjectName("Card")
        editor_layout = QVBoxLayout(editor_card)
        editor_layout.setContentsMargins(10, 10, 10, 10)
        editor_layout.setSpacing(8)

        top_bar = QHBoxLayout()
        self.file_label = QLabel("без имени.py")
        self.file_label.setObjectName("FileLabel")
        self.mini_hint = QLabel("Ctrl+S сохранить  ·  Ctrl+O открыть  ·  F5 запустить  ·  Ctrl+Shift+C проверить")
        self.mini_hint.setObjectName("Muted")
        top_bar.addWidget(self.file_label)
        top_bar.addStretch(1)
        top_bar.addWidget(self.mini_hint)

        editor_layout.addLayout(top_bar)
        editor_layout.addWidget(self.tabs)

        self.output_console = InteractiveConsole(prompt="› ")
        self.output_console.setObjectName("Console")
        self.output_console.setToolTip("Печатай stdin прямо в консоли и нажимай Enter. Старый вывод защищён от редактирования.")
        self.output_console.set_submit_callback(self.send_run_stdin_text)
        self._apply_console_font(self.output_console)

        run_console_card = QWidget()
        run_console_layout = QVBoxLayout(run_console_card)
        run_console_layout.setContentsMargins(0, 0, 0, 0)
        run_console_layout.setSpacing(8)
        run_console_layout.addWidget(self.output_console)

        self.terminal_console = InteractiveConsole(prompt="")
        self.terminal_console.setObjectName("Console")
        self.terminal_console.setToolTip("Печатай команды прямо здесь и нажимай Enter.")
        self.terminal_console.set_submit_callback(self.send_terminal_command_text)
        self._apply_console_font(self.terminal_console)

        terminal_buttons = QHBoxLayout()
        self.btn_terminal_restart = QPushButton("↻ Перезапустить терминал")
        self.btn_terminal_clear = QPushButton("Очистить")
        self.btn_terminal_restart.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_terminal_clear.setCursor(Qt.CursorShape.PointingHandCursor)
        terminal_buttons.addWidget(self.btn_terminal_restart)
        terminal_buttons.addWidget(self.btn_terminal_clear)
        terminal_buttons.addStretch(1)

        terminal_card = QWidget()
        terminal_layout = QVBoxLayout(terminal_card)
        terminal_layout.setContentsMargins(0, 0, 0, 0)
        terminal_layout.setSpacing(8)
        terminal_layout.addLayout(terminal_buttons)
        terminal_layout.addWidget(self.terminal_console)

        installer_card = QWidget()
        installer_card.setObjectName("PageCard")
        installer_layout = QVBoxLayout(installer_card)
        installer_layout.setContentsMargins(18, 18, 18, 18)
        installer_layout.setSpacing(8)

        self.installer_hint = QLabel(
            "Автоустановщик работает через WinGet: может поставить Python, C++ toolchain через MSYS2 и JDK для Java. "
            "После установки Astra сама подхватит стандартные пути без ручной настройки PATH."
        )
        self.installer_hint.setObjectName("Muted")
        self.installer_hint.setWordWrap(True)

        self.app_update_status = QLabel(f"Astra Studio: {APP_VERSION} · канал обновлений: stable")
        self.app_update_status.setObjectName("MiniLabel")
        self.app_update_status.setWordWrap(True)
        self.btn_check_app_update = QPushButton("Проверить обновление Astra Studio")
        self.btn_check_app_update.setObjectName("PrimaryButton")

        self.install_progress_label = QLabel("Загрузка/проверка: 0%")
        self.install_progress_label.setObjectName("MiniLabel")
        self.install_progress_bar = QProgressBar()
        self.install_progress_bar.setObjectName("ProgressBar")
        self.install_progress_bar.setRange(0, 100)
        self.install_progress_bar.setValue(0)
        self.install_progress_bar.setTextVisible(True)

        installer_buttons_1 = QVBoxLayout()
        self.btn_check_tools = QPushButton("Проверить версии и инструменты")
        self.btn_check_updates = QPushButton("Проверить обновления инструментов")
        self.btn_install_all = QPushButton("Установить всё")
        self.btn_install_all.setObjectName("PrimaryButton")
        self.btn_update_all = QPushButton("Обновить языки")
        self.btn_desktop_shortcut = QPushButton("Создать ярлык на рабочем столе")
        self.shortcut_icon_label = QLabel("Оформление ярлыка")
        self.shortcut_icon_label.setObjectName("MiniLabel")
        self.shortcut_icon_combo = QComboBox()
        for label, relative_path in SHORTCUT_ICON_OPTIONS.items():
            self.shortcut_icon_combo.addItem(label, relative_path)
        self.shortcut_icon_combo.setToolTip("Выбери значок и нажми «Создать ярлык на рабочем столе»")
        self.shortcut_icon_combo.setMinimumHeight(34)
        self.btn_install_python = QPushButton("Установить Python + uv")
        self.btn_install_cpp = QPushButton("Установить C++")
        self.btn_install_java = QPushButton("Установить Java")
        self.btn_install_node = QPushButton("Установить Node.js LTS + TypeScript")
        self.btn_install_git = QPushButton("Установить Git")
        self.btn_install_godot = QPushButton("Установить Godot")
        self.btn_install_php = QPushButton("Установить PHP 8.4")
        self.btn_install_powershell = QPushButton("Установить PowerShell 7")
        self.btn_install_all.setText("Установить основной набор StaffedUp")
        for button in [
            self.btn_check_tools, self.btn_check_updates, self.btn_install_all, self.btn_update_all,
            self.btn_desktop_shortcut, self.btn_install_python, self.btn_install_cpp, self.btn_install_java,
            self.btn_install_node, self.btn_install_git, self.btn_install_godot, self.btn_install_php,
            self.btn_install_powershell,
        ]:
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setMinimumHeight(34)
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            if button is self.btn_desktop_shortcut:
                installer_buttons_1.addWidget(self.shortcut_icon_label)
                installer_buttons_1.addWidget(self.shortcut_icon_combo)
            installer_buttons_1.addWidget(button)

        self.installer_console = QPlainTextEdit()
        self.installer_console.setObjectName("Console")
        self.installer_console.setReadOnly(True)
        self._apply_console_font(self.installer_console)

        installer_layout.addWidget(self.installer_hint)
        installer_layout.addWidget(self.app_update_status)
        installer_layout.addWidget(self.btn_check_app_update)
        installer_layout.addWidget(self.install_progress_label)
        installer_layout.addWidget(self.install_progress_bar)
        installer_layout.addLayout(installer_buttons_1)
        self.installer_console.setMinimumHeight(180)
        installer_layout.addWidget(self.installer_console)

        developer_card = QWidget()
        developer_card.setObjectName("PageCard")
        developer_layout = QVBoxLayout(developer_card)
        developer_layout.setContentsMargins(18, 18, 18, 18)
        developer_layout.setSpacing(10)
        developer_logo = QLabel()
        developer_logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        developer_logo_pixmap = QPixmap(str(resource_path("assets/astra.png")))
        if not developer_logo_pixmap.isNull():
            developer_logo.setPixmap(developer_logo_pixmap.scaledToHeight(118, Qt.TransformationMode.SmoothTransformation))
        developer_title = QLabel("Astra Studio")
        developer_title.setObjectName("DevTitle")
        developer_text = QLabel(
            "Разработчик: alaron\n\n"
            "Почта для предложений и обратной связи:\n"
            "astralstudio.help@gmail.com\n\n"
            "Главная цель Astra Studio — облегчить новичкам написание кода: убрать лишнюю возню с выбором среды, "
            "настройкой запуска и базовыми шаблонами, чтобы пользователь мог с кайфом писать код в собственной студии.\n\n"
            "Идея: лёгкая учебная среда для написания кода с тёмным виджетным интерфейсом, "
            "шаблонами, автодополнением по Tab и быстрым запуском.\n\n"
            f"Текущая версия: {APP_VERSION}.\n\n"
            "Astra Studio — среда для написания, запуска и сборки кода, ориентированная на удобную работу с Python, C++, JavaScript, TypeScript, Luau, GDScript, PHP, PowerShell, Java, C#, HTML, CSS, SQL и форматы конфигурации. "
            "Программа объединяет редактор кода, консоль, шаблоны, управление проектами, оформление интерфейса, сборку EXE и работу с Python-библиотеками в одном приложении.\n\n"
            "Функции: редактор кода, запуск Python и C++, шаблоны программ, автодополнение по Tab, автоустановка Python-библиотек, окно библиотек Python, сборка EXE с иконкой, пользовательские и предустановленные обои, тёмные окна сообщений, настройки прозрачности и размытия, работа с проектами и консоль вывода.\n\n"
            "Плюсы: проще и легче крупных IDE, не требует сложной настройки для базовой работы, помогает новичкам быстрее начать писать код и при этом остаётся практичной для небольших программ и экспериментов.\n\n"
            "Цель проекта — сделать программирование доступнее, удобнее и визуально приятнее, сохранив практичные функции для реальной работы с кодом."
        )
        developer_text.setObjectName("DevText")
        developer_text.setWordWrap(True)
        developer_layout.addWidget(developer_logo)
        developer_layout.addWidget(developer_title)
        developer_layout.addWidget(developer_text)
        developer_layout.addStretch(1)

        settings_card = QWidget()
        settings_card.setObjectName("PageCard")
        settings_layout = QVBoxLayout(settings_card)
        settings_layout.setContentsMargins(18, 18, 18, 18)
        settings_layout.setSpacing(10)
        settings_logo = QLabel()
        settings_logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        settings_logo_pixmap = QPixmap(str(resource_path("assets/astra.png")))
        if not settings_logo_pixmap.isNull():
            settings_logo.setPixmap(settings_logo_pixmap.scaledToHeight(74, Qt.TransformationMode.SmoothTransformation))
        settings_title = QLabel("НАСТРОЙКИ ОФОРМЛЕНИЯ")
        settings_title.setObjectName("SectionTitle")
        settings_text = QLabel("Здесь собраны темы, акцентные цвета, прозрачность окон, размытие и обои. Изменения сохраняются автоматически.")
        settings_text.setObjectName("Muted")
        settings_text.setWordWrap(True)
        settings_layout.addWidget(settings_logo)
        settings_layout.addWidget(settings_title)
        settings_layout.addWidget(settings_text)
        settings_layout.addWidget(self.theme_label)
        settings_layout.addWidget(self.theme_combo)
        settings_layout.addWidget(self.accent_label)
        settings_layout.addWidget(self.accent_combo)
        settings_layout.addSpacing(8)
        wallpaper_title = QLabel("ОБОИ ИНТЕРФЕЙСА")
        wallpaper_title.setObjectName("SectionTitle")
        wallpaper_hint = QLabel("Можно выбрать собственное изображение. Оно будет сохранено в настройках и использовано как фон приложения.")
        wallpaper_hint.setObjectName("Muted")
        wallpaper_hint.setWordWrap(True)
        settings_layout.addWidget(wallpaper_title)
        settings_layout.addWidget(wallpaper_hint)
        settings_layout.addWidget(self.wallpaper_label)
        preset_label = QLabel("Предустановленные обои Astra")
        preset_label.setObjectName("MiniLabel")
        preset_label.setWordWrap(True)
        settings_layout.addWidget(preset_label)
        settings_layout.addWidget(self.preset_wallpaper_combo)
        settings_layout.addWidget(self.btn_apply_astra_profile)
        settings_layout.addWidget(self.btn_apply_angel404_profile)
        settings_layout.addWidget(self.btn_choose_wallpaper)
        settings_layout.addWidget(self.btn_clear_wallpaper)
        settings_layout.addWidget(self.wallpaper_all_toggle)
        settings_layout.addWidget(self.disable_console_wallpaper_toggle)
        settings_layout.addWidget(self.wallpaper_dim_label)
        settings_layout.addWidget(self.wallpaper_dim_slider)
        settings_layout.addWidget(self.wallpaper_blur_label)
        settings_layout.addWidget(self.wallpaper_blur_slider)
        settings_layout.addWidget(self.panel_transparency_label)
        settings_layout.addWidget(self.panel_transparency_slider)
        settings_layout.addWidget(self.logo_frame_blur_label)
        settings_layout.addWidget(self.logo_frame_blur_slider)
        settings_layout.addWidget(self.appearance_advanced_toggle)
        settings_layout.addWidget(self.logo_frame_transparency_label)
        settings_layout.addWidget(self.logo_frame_transparency_slider)
        settings_layout.addWidget(self.editor_blur_label)
        settings_layout.addWidget(self.editor_blur_slider)
        settings_layout.addWidget(self.console_blur_label)
        settings_layout.addWidget(self.console_blur_slider)
        settings_layout.addWidget(self.settings_blur_label)
        settings_layout.addWidget(self.settings_blur_slider)
        settings_layout.addWidget(self.project_blur_label)
        settings_layout.addWidget(self.project_blur_slider)
        settings_layout.addWidget(self.btn_reset_blur)
        settings_layout.addSpacing(8)
        transparency_title = QLabel("ОФОРМЛЕНИЕ ПАНЕЛЕЙ")
        transparency_title.setObjectName("SectionTitle")
        settings_layout.addWidget(transparency_title)
        settings_layout.addWidget(self.editor_transparency_label)
        settings_layout.addWidget(self.editor_transparency_slider)
        settings_layout.addWidget(self.console_transparency_label)
        settings_layout.addWidget(self.console_transparency_slider)
        settings_layout.addWidget(self.settings_transparency_label)
        settings_layout.addWidget(self.settings_transparency_slider)
        settings_layout.addWidget(self.project_transparency_label)
        settings_layout.addWidget(self.project_transparency_slider)
        settings_layout.addWidget(self.aux_transparency_label)
        settings_layout.addWidget(self.aux_transparency_slider)
        settings_layout.addWidget(self.btn_reset_transparency)
        settings_layout.addSpacing(8)
        settings_layout.addWidget(self.opacity_toggle)
        settings_layout.addWidget(self.opacity_label)
        settings_layout.addWidget(self.opacity_slider)
        settings_layout.addSpacing(8)
        settings_layout.addWidget(self.topmost_toggle)
        settings_layout.addSpacing(8)
        settings_layout.addWidget(self.save_window_sizes_toggle)
        settings_layout.addWidget(self.btn_reset_window_sizes)
        settings_layout.addWidget(self.btn_reset_appearance)
        settings_layout.addSpacing(10)
        autocomplete_title = QLabel("АВТОДОПОЛНЕНИЕ")
        autocomplete_title.setObjectName("SectionTitle")
        autocomplete_hint = QLabel("Встроенные сниппеты показываются ненавязчиво в редакторе и принимаются клавишей Tab.")
        autocomplete_hint.setObjectName("Muted")
        autocomplete_hint.setWordWrap(True)
        settings_layout.addWidget(autocomplete_title)
        settings_layout.addWidget(autocomplete_hint)
        settings_layout.addWidget(self.tab_width_label)
        indents_title = QLabel("ОТСТУПЫ РЕДАКТОРА")
        indents_title.setObjectName("SectionTitle")
        settings_layout.addWidget(indents_title)
        settings_layout.addWidget(self.editor_tab_size_label)
        settings_layout.addWidget(self.editor_tab_size_slider)
        settings_layout.addWidget(self.editor_indent_size_label)
        settings_layout.addWidget(self.editor_indent_size_slider)
        settings_layout.addWidget(self.editor_insert_spaces_toggle)
        settings_layout.addWidget(self.btn_reset_indents)
        settings_layout.addSpacing(8)
        fonts_title = QLabel("ШРИФТЫ")
        fonts_title.setObjectName("SectionTitle")
        fonts_hint = QLabel("Выбранный шрифт применяется ко всему тексту Astra: интерфейсу, редактору, консолям, меню и диалогам. Размеры областей можно настроить отдельно.")
        fonts_hint.setObjectName("Muted")
        fonts_hint.setWordWrap(True)
        settings_layout.addWidget(fonts_title)
        settings_layout.addWidget(fonts_hint)
        settings_layout.addWidget(self.global_font_label)
        settings_layout.addWidget(self.global_font_combo)
        settings_layout.addWidget(self.ui_font_size_label)
        settings_layout.addWidget(self.ui_font_size_slider)
        settings_layout.addWidget(self.editor_font_size_label)
        settings_layout.addWidget(self.editor_font_size_slider)
        settings_layout.addWidget(self.console_font_size_label)
        settings_layout.addWidget(self.console_font_size_slider)
        settings_layout.addWidget(self.btn_reset_fonts)
        settings_layout.addSpacing(8)
        settings_layout.addWidget(self.autocomplete_toggle)
        settings_layout.addWidget(self.show_snippets_toggle)
        settings_layout.addWidget(self.accept_tab_toggle)
        settings_layout.addWidget(self.format_on_save_toggle)
        settings_layout.addSpacing(10)
        python_title = QLabel("PYTHON")
        python_title.setObjectName("SectionTitle")
        settings_layout.addWidget(python_title)
        settings_layout.addWidget(self.auto_install_libs_toggle)
        settings_layout.addWidget(self.always_ask_install_toggle)
        settings_layout.addWidget(self.unknown_auto_install_toggle)
        settings_layout.addWidget(self.open_install_log_toggle)
        settings_layout.addSpacing(10)
        build_title = QLabel("СБОРКА")
        build_title.setObjectName("SectionTitle")
        settings_layout.addWidget(build_title)
        settings_layout.addWidget(self.exe_mode_label)
        settings_layout.addWidget(self.exe_mode_combo)
        settings_layout.addWidget(self.cpp_using_std_toggle)
        settings_layout.addStretch(1)

        settings_card.setMinimumWidth(0)
        settings_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        for label in settings_card.findChildren(QLabel):
            label.setWordWrap(True)
            label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.settings_scroll = QScrollArea()
        self.settings_scroll.setObjectName("PageScroll")
        self.settings_scroll.setWidgetResizable(True)
        self.settings_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.settings_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.settings_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.settings_scroll.setWidget(settings_card)
        self.settings_scroll.setMinimumWidth(0)

        python_libs_card = QWidget()
        python_libs_card.setObjectName("PageCard")
        python_libs_layout = QVBoxLayout(python_libs_card)
        python_libs_layout.setContentsMargins(18, 18, 18, 18)
        python_libs_layout.setSpacing(8)
        libs_title = QLabel("БИБЛИОТЕКИ PYTHON")
        libs_title.setObjectName("SectionTitle")
        libs_hint = QLabel("Встроенный каталог хранит известные import→pip соответствия, но больше не ограничивает установку. Ниже можно установить любой пакет PyPI; неизвестный import Astra умеет попробовать установить по совпадающему имени.")
        libs_hint.setObjectName("Muted")
        libs_hint.setWordWrap(True)
        self.python_env_label = QLabel("Python environment: определение…")
        self.python_env_label.setObjectName("Muted")
        self.python_env_label.setWordWrap(True)
        self.btn_python_env_refresh = QPushButton("↻  Обновить окружение")
        self.btn_python_env_refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_python_env_refresh.setMinimumHeight(34)
        self.btn_python_env_create = QPushButton("+  Создать .venv")
        self.btn_python_env_select = QPushButton("⌁  Выбрать Python")
        self.btn_python_env_install_deps = QPushButton("↓  Установить зависимости проекта")
        self.btn_python_env_update_pip = QPushButton("↑  Обновить pip")
        self.btn_python_env_export = QPushButton("⇢  Экспорт requirements.txt")
        for button in [self.btn_python_env_create, self.btn_python_env_select, self.btn_python_env_install_deps, self.btn_python_env_update_pip, self.btn_python_env_export]:
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setMinimumHeight(34)
        self.libs_search = QLineEdit()
        self.libs_search.setObjectName("ConsoleInput")
        self.libs_search.setPlaceholderText("Поиск: requests, графики, GUI...")
        self.libs_category_combo = QComboBox()
        categories = ["Все"] + sorted({item["category"] for item in PYTHON_LIBRARY_REGISTRY})
        self.libs_category_combo.addItems(categories)
        self.custom_pip_edit = QLineEdit()
        self.custom_pip_edit.setObjectName("ConsoleInput")
        self.custom_pip_edit.setPlaceholderText("Любой пакет PyPI: httpx, fastapi, rich>=13, package[extra]")
        self.btn_custom_pip_install = QPushButton("Установить пакет PyPI")
        self.btn_custom_pip_update = QPushButton("Обновить пакет PyPI")
        for button in [self.btn_custom_pip_install, self.btn_custom_pip_update]:
            button.setCursor(Qt.CursorShape.PointingHandCursor)
        custom_pip_row = QHBoxLayout()
        custom_pip_row.addWidget(self.custom_pip_edit, 3)
        custom_pip_row.addWidget(self.btn_custom_pip_install, 1)
        custom_pip_row.addWidget(self.btn_custom_pip_update, 1)
        self.libs_bundle_combo = QComboBox()
        self.libs_bundle_combo.addItems(["Выбрать набор..."] + list(LIBRARY_BUNDLES.keys()))
        self.libs_bundle_combo.setToolTip("Наборы популярных библиотек для учёбы, ИИ, анализа данных, документов и автоматизации")
        self.libs_table = QTableWidget(0, 6)
        self.libs_table.setObjectName("LibrariesTable")
        self.libs_table.setHorizontalHeaderLabels(["import", "pip", "категория", "статус", "описание", "предупреждение"])
        self.libs_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.libs_table.verticalHeader().setVisible(False)
        self.libs_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.libs_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.btn_lib_install = QPushButton("Установить")
        self.btn_lib_update = QPushButton("Обновить")
        self.btn_lib_uninstall = QPushButton("Удалить")
        self.btn_lib_check = QPushButton("Проверить установленные")
        self.btn_lib_install_bundle = QPushButton("Установить выбранный набор")
        self.btn_lib_open_pypi = QPushButton("Открыть PyPI")
        self.btn_lib_copy_cmd = QPushButton("Скопировать команду")
        libs_buttons = QHBoxLayout()
        for button in [self.btn_lib_install, self.btn_lib_update, self.btn_lib_uninstall, self.btn_lib_check, self.btn_lib_open_pypi, self.btn_lib_copy_cmd]:
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            libs_buttons.addWidget(button)
        bundle_buttons = QHBoxLayout()
        bundle_buttons.addWidget(self.libs_bundle_combo, 2)
        bundle_buttons.addWidget(self.btn_lib_install_bundle, 1)
        python_libs_layout.addWidget(libs_title)
        python_libs_layout.addWidget(libs_hint)
        python_libs_layout.addWidget(self.python_env_label)
        env_buttons_1 = QHBoxLayout()
        env_buttons_1.addWidget(self.btn_python_env_refresh)
        env_buttons_1.addWidget(self.btn_python_env_create)
        env_buttons_1.addWidget(self.btn_python_env_select)
        env_buttons_2 = QHBoxLayout()
        env_buttons_2.addWidget(self.btn_python_env_install_deps)
        env_buttons_2.addWidget(self.btn_python_env_update_pip)
        env_buttons_2.addWidget(self.btn_python_env_export)
        python_libs_layout.addLayout(env_buttons_1)
        python_libs_layout.addLayout(env_buttons_2)
        python_libs_layout.addWidget(self.libs_search)
        python_libs_layout.addWidget(self.libs_category_combo)
        python_libs_layout.addLayout(custom_pip_row)
        python_libs_layout.addLayout(bundle_buttons)
        python_libs_layout.addWidget(self.libs_table)
        python_libs_layout.addLayout(libs_buttons)

        lsp_card = QWidget()
        lsp_card.setObjectName("PageCard")
        lsp_layout = QVBoxLayout(lsp_card)
        lsp_layout.setContentsMargins(18, 18, 18, 18)
        lsp_layout.setSpacing(8)
        lsp_title = QLabel("LSP / ИНТЕЛЛЕКТ РЕДАКТОРА")
        lsp_title.setObjectName("SectionTitle")
        lsp_hint = QLabel(
            "Language Server Protocol даёт диагностику, completion, hover, навигацию и rename. "
            "Astra использует локальные серверы проекта в приоритете и не устанавливает неизвестные серверы автоматически."
        )
        lsp_hint.setObjectName("Muted")
        lsp_hint.setWordWrap(True)
        self.lsp_server_table = QTableWidget(0, 5)
        self.lsp_server_table.setObjectName("LspServerTable")
        self.lsp_server_table.setHorizontalHeaderLabels(["Язык", "Статус", "Сервер", "Установка", "Примечание"])
        self.lsp_server_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.lsp_server_table.verticalHeader().setVisible(False)
        self.lsp_server_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.lsp_server_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.lsp_server_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.btn_lsp_refresh = QPushButton("↻  Обновить статус")
        self.btn_lsp_start = QPushButton("▶  Запустить / перезапустить")
        self.btn_lsp_stop = QPushButton("■  Остановить")
        self.btn_lsp_install = QPushButton("↓  Установить / обновить безопасный сервер")
        for button in [self.btn_lsp_refresh, self.btn_lsp_start, self.btn_lsp_stop, self.btn_lsp_install]:
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setMinimumHeight(34)
        lsp_buttons_1 = QHBoxLayout()
        lsp_buttons_1.addWidget(self.btn_lsp_refresh)
        lsp_buttons_1.addWidget(self.btn_lsp_start)
        lsp_buttons_1.addWidget(self.btn_lsp_stop)
        lsp_buttons_2 = QHBoxLayout()
        lsp_buttons_2.addWidget(self.btn_lsp_install)
        outline_title = QLabel("OUTLINE ТЕКУЩЕГО ФАЙЛА")
        outline_title.setObjectName("SectionTitle")
        outline_hint = QLabel("Ctrl+Shift+O обновляет symbols. Двойной клик переходит к объявлению.")
        outline_hint.setObjectName("Muted")
        outline_hint.setWordWrap(True)
        self.btn_lsp_outline_refresh = QPushButton("⌁  Обновить Outline")
        self.btn_lsp_outline_refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        self.lsp_outline_tree = QTreeWidget()
        self.lsp_outline_tree.setObjectName("LspOutlineTree")
        self.lsp_outline_tree.setColumnCount(3)
        self.lsp_outline_tree.setHeaderLabels(["Символ", "Тип", "Строка"])
        self.lsp_outline_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.lsp_outline_tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.lsp_outline_tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        lsp_layout.addWidget(lsp_title)
        lsp_layout.addWidget(lsp_hint)
        lsp_layout.addWidget(self.lsp_server_table, 2)
        lsp_layout.addLayout(lsp_buttons_1)
        lsp_layout.addLayout(lsp_buttons_2)
        lsp_layout.addSpacing(8)
        lsp_layout.addWidget(outline_title)
        lsp_layout.addWidget(outline_hint)
        lsp_layout.addWidget(self.btn_lsp_outline_refresh)
        lsp_layout.addWidget(self.lsp_outline_tree, 2)

        problems_card = QWidget()
        self.problems_page = problems_card
        problems_layout = QVBoxLayout(problems_card)
        problems_layout.setContentsMargins(0, 0, 0, 0)
        problems_layout.setSpacing(8)
        problems_toolbar = QHBoxLayout()
        self.problems_summary_label = QLabel("Проблемы: 0")
        self.problems_summary_label.setObjectName("MiniLabel")
        self.problems_errors_toggle = QCheckBox("Ошибки")
        self.problems_errors_toggle.setChecked(True)
        self.problems_warnings_toggle = QCheckBox("Предупреждения")
        self.problems_warnings_toggle.setChecked(True)
        self.problems_info_toggle = QCheckBox("Инфо / подсказки")
        self.problems_info_toggle.setChecked(True)
        self.problems_current_file_toggle = QCheckBox("Только текущий файл")
        problems_toolbar.addWidget(self.problems_summary_label)
        problems_toolbar.addStretch(1)
        problems_toolbar.addWidget(self.problems_errors_toggle)
        problems_toolbar.addWidget(self.problems_warnings_toggle)
        problems_toolbar.addWidget(self.problems_info_toggle)
        problems_toolbar.addWidget(self.problems_current_file_toggle)
        self.problems_tree = QTreeWidget()
        self.problems_tree.setObjectName("ProblemsTree")
        self.problems_tree.setColumnCount(4)
        self.problems_tree.setHeaderLabels(["Проблема", "Файл", "Строка", "Источник"])
        self.problems_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.problems_tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.problems_tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.problems_tree.header().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.problems_tree.setRootIsDecorated(True)
        self.problems_tree.setAlternatingRowColors(False)
        self.problems_tree.setToolTip("Нажмите на диагностику, чтобы открыть файл и перейти к строке")
        problems_layout.addLayout(problems_toolbar)
        problems_layout.addWidget(self.problems_tree, 1)

        tests_card = QWidget()
        self.tests_page = tests_card
        tests_layout = QVBoxLayout(tests_card)
        tests_layout.setContentsMargins(0, 0, 0, 0)
        tests_layout.setSpacing(8)
        tests_toolbar = QHBoxLayout()
        self.test_adapter_combo = QComboBox()
        self.test_adapter_combo.setMinimumWidth(180)
        self.test_adapter_combo.setToolTip("Обнаруженные тестовые фреймворки текущего проекта")
        self.btn_test_discover = QPushButton("↻  Обнаружить")
        self.btn_test_run_all = QPushButton("▶  Запустить все")
        self.btn_test_run_selected = QPushButton("▷  Запустить выбранный")
        self.btn_test_rerun = QPushButton("↻  Повторить последний")
        for button in [self.btn_test_discover, self.btn_test_run_all, self.btn_test_run_selected, self.btn_test_rerun]:
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setMinimumHeight(30)
        tests_toolbar.addWidget(self.test_adapter_combo)
        tests_toolbar.addWidget(self.btn_test_discover)
        tests_toolbar.addWidget(self.btn_test_run_all)
        tests_toolbar.addWidget(self.btn_test_run_selected)
        tests_toolbar.addWidget(self.btn_test_rerun)
        tests_toolbar.addStretch(1)
        self.test_summary_label = QLabel("Тесты: не обнаружены")
        self.test_summary_label.setObjectName("MiniLabel")
        self.test_tree = QTreeWidget()
        self.test_tree.setObjectName("TestExplorerTree")
        self.test_tree.setColumnCount(5)
        self.test_tree.setHeaderLabels(["Тест", "Статус", "Файл", "Строка", "Сообщение"])
        self.test_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.test_tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.test_tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.test_tree.header().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.test_tree.header().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.test_tree.setRootIsDecorated(True)
        self.test_tree.setToolTip("Двойной клик открывает исходный тест. Run Selected доступен для адаптеров с безопасным точечным запуском.")
        tests_layout.addLayout(tests_toolbar)
        tests_layout.addWidget(self.test_summary_label)
        tests_layout.addWidget(self.test_tree, 1)

        git_card = QWidget()
        self.git_page = git_card
        git_layout = QVBoxLayout(git_card)
        git_layout.setContentsMargins(0, 0, 0, 0)
        git_layout.setSpacing(8)

        git_top = QHBoxLayout()
        self.git_summary_label = QLabel("Git: статус не проверен")
        self.git_summary_label.setObjectName("MiniLabel")
        self.btn_git_refresh = QPushButton("↻  Обновить")
        self.btn_git_diff = QPushButton("Diff рабочий")
        self.btn_git_diff_staged = QPushButton("Diff staged")
        for button in [self.btn_git_refresh, self.btn_git_diff, self.btn_git_diff_staged]:
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setMinimumHeight(30)
        git_top.addWidget(self.git_summary_label)
        git_top.addStretch(1)
        git_top.addWidget(self.btn_git_refresh)
        git_top.addWidget(self.btn_git_diff)
        git_top.addWidget(self.btn_git_diff_staged)

        git_actions = QHBoxLayout()
        self.btn_git_stage = QPushButton("+ Stage")
        self.btn_git_unstage = QPushButton("− Unstage")
        self.btn_git_stage_all = QPushButton("Stage All")
        self.btn_git_unstage_all = QPushButton("Unstage All")
        self.btn_git_pull = QPushButton("↓ Pull --ff-only")
        self.btn_git_push = QPushButton("↑ Push")
        for button in [self.btn_git_stage, self.btn_git_unstage, self.btn_git_stage_all, self.btn_git_unstage_all, self.btn_git_pull, self.btn_git_push]:
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setMinimumHeight(30)
            git_actions.addWidget(button)
        git_actions.addStretch(1)

        commit_row = QHBoxLayout()
        self.git_commit_message = QLineEdit()
        self.git_commit_message.setObjectName("ConsoleInput")
        self.git_commit_message.setPlaceholderText("Сообщение коммита — commit выполняется только по кнопке")
        self.btn_git_commit = QPushButton("Commit staged")
        self.btn_git_commit.setObjectName("PrimaryButton")
        self.btn_git_commit.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_git_commit.setMinimumHeight(30)
        commit_row.addWidget(self.git_commit_message, 1)
        commit_row.addWidget(self.btn_git_commit)

        self.git_tree = QTreeWidget()
        self.git_tree.setObjectName("GitTree")
        self.git_tree.setColumnCount(4)
        self.git_tree.setHeaderLabels(["Файл", "Статус", "Index", "Working Tree"])
        self.git_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.git_tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.git_tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.git_tree.header().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.git_tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.git_tree.setToolTip("Выбери изменённый файл. Двойной клик открывает его, если файл существует в рабочем дереве.")

        self.git_diff_view = QPlainTextEdit()
        self.git_diff_view.setObjectName("GitDiff")
        self.git_diff_view.setReadOnly(True)
        self.git_diff_view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.git_diff_view.setPlaceholderText("Выбери файл и нажми «Diff рабочий» или «Diff staged».")
        self._apply_console_font(self.git_diff_view)

        git_split = QSplitter(Qt.Orientation.Vertical)
        git_split.addWidget(self.git_tree)
        git_split.addWidget(self.git_diff_view)
        git_split.setSizes([180, 180])

        git_layout.addLayout(git_top)
        git_layout.addLayout(git_actions)
        git_layout.addLayout(commit_row)
        git_layout.addWidget(git_split, 1)

        self.bottom_tabs = QTabWidget()
        self.bottom_tabs.setObjectName("BottomTabs")
        self.bottom_tabs.addTab(run_console_card, "Вывод программы")
        self.bottom_tabs.addTab(terminal_card, "Терминал")
        self.bottom_tabs.addTab(problems_card, "Проблемы (0)")
        self.bottom_tabs.addTab(tests_card, "Тесты")
        self.bottom_tabs.addTab(git_card, "Git")

        self.problems_tree.itemClicked.connect(self._open_problem_item)
        self.test_tree.itemDoubleClicked.connect(self._open_test_tree_item)
        self.test_adapter_combo.currentIndexChanged.connect(self._on_test_adapter_changed)
        self.btn_test_discover.clicked.connect(self.discover_project_tests)
        self.btn_test_run_all.clicked.connect(lambda: self.run_tests_from_explorer(False))
        self.btn_test_run_selected.clicked.connect(lambda: self.run_tests_from_explorer(True))
        self.btn_test_rerun.clicked.connect(self.rerun_last_tests)
        self.git_tree.itemDoubleClicked.connect(self._open_git_tree_item)
        self.git_tree.itemSelectionChanged.connect(self._update_git_controls)
        self.btn_git_refresh.clicked.connect(self.refresh_git_status)
        self.btn_git_diff.clicked.connect(lambda: self.show_selected_git_diff(False))
        self.btn_git_diff_staged.clicked.connect(lambda: self.show_selected_git_diff(True))
        self.btn_git_stage.clicked.connect(lambda: self.git_stage_selected(False))
        self.btn_git_unstage.clicked.connect(lambda: self.git_unstage_selected(False))
        self.btn_git_stage_all.clicked.connect(lambda: self.git_stage_selected(True))
        self.btn_git_unstage_all.clicked.connect(lambda: self.git_unstage_selected(True))
        self.btn_git_commit.clicked.connect(self.git_commit)
        self.btn_git_pull.clicked.connect(self.git_pull)
        self.btn_git_push.clicked.connect(self.git_push)
        self.problems_errors_toggle.toggled.connect(self._refresh_problems_panel)
        self.problems_warnings_toggle.toggled.connect(self._refresh_problems_panel)
        self.problems_info_toggle.toggled.connect(self._refresh_problems_panel)
        self.problems_current_file_toggle.toggled.connect(self._refresh_problems_panel)

        console_card = QFrame()
        console_card.setObjectName("ConsoleCard")
        console_layout = QVBoxLayout(console_card)
        console_layout.setContentsMargins(10, 10, 10, 10)
        console_layout.setSpacing(8)

        console_header = QHBoxLayout()
        console_title = QLabel("КОНСОЛЬ")
        console_title.setObjectName("SectionTitle")
        self.status_pill = QLabel("готово")
        self.status_pill.setObjectName("Pill")
        console_header.addWidget(console_title)
        console_header.addStretch(1)
        console_header.addWidget(self.status_pill)

        self.build_status_panel = QFrame()
        self.build_status_panel.setObjectName("BuildStatusPanel")
        build_status_layout = QHBoxLayout(self.build_status_panel)
        build_status_layout.setContentsMargins(10, 8, 10, 8)
        build_status_layout.setSpacing(8)
        self.build_status_label = QLabel("Идёт операция…")
        self.build_status_label.setObjectName("MiniLabel")
        self.build_status_label.setWordWrap(True)
        self.build_progress_bar = QProgressBar()
        self.build_progress_bar.setObjectName("ProgressBar")
        self.build_progress_bar.setRange(0, 0)
        self.build_progress_bar.setTextVisible(True)
        self.build_eta_label = QLabel("Расчёт времени…")
        self.build_eta_label.setObjectName("MiniLabel")
        self.build_eta_label.setWordWrap(True)
        self.btn_cancel_task = QPushButton("Отмена")
        self.btn_cancel_task.setObjectName("CloseButton")
        self.btn_cancel_task.setMinimumWidth(92)
        self.btn_cancel_task.setCursor(Qt.CursorShape.PointingHandCursor)
        build_status_layout.addWidget(self.build_status_label, 2)
        build_status_layout.addWidget(self.build_progress_bar, 3)
        build_status_layout.addWidget(self.build_eta_label, 2)
        build_status_layout.addWidget(self.btn_cancel_task)
        self.build_status_panel.setVisible(False)

        console_layout.addLayout(console_header)
        console_layout.addWidget(self.build_status_panel)
        console_layout.addWidget(self.bottom_tabs)

        self.vertical_splitter = QSplitter(Qt.Orientation.Vertical)
        self.vertical_splitter.addWidget(editor_card)
        self.vertical_splitter.addWidget(console_card)
        self.vertical_splitter.setSizes(self.saved_vertical_splitter_sizes if self.saved_vertical_splitter_sizes else [570, 250])
        self.vertical_splitter.setHandleWidth(3)

        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.main_splitter.addWidget(self.project_panel)
        self.main_splitter.addWidget(self.vertical_splitter)
        self.main_splitter.setCollapsible(0, False)
        main_sizes = list(self.saved_main_splitter_sizes) if self.saved_main_splitter_sizes and len(self.saved_main_splitter_sizes) >= 2 else [280, 940]
        main_sizes[0] = max(260, int(main_sizes[0] or 0))
        main_sizes[1] = max(520, int(main_sizes[1] or 0))
        self.main_splitter.setSizes(main_sizes[:2])
        self.main_splitter.setHandleWidth(3)

        editor_page = QWidget()
        editor_page_layout = QVBoxLayout(editor_page)
        editor_page_layout.setContentsMargins(0, 0, 0, 0)
        editor_page_layout.setSpacing(0)
        editor_page_layout.addWidget(self.main_splitter)

        self.tools_drawer = QFrame()
        self.tools_drawer.setObjectName("SideToolsPanel")
        self.tools_drawer.setMinimumWidth(330)
        self.tools_drawer.setMaximumWidth(760)
        self.tools_drawer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        drawer_layout = QVBoxLayout(self.tools_drawer)
        drawer_layout.setContentsMargins(10, 10, 10, 10)
        drawer_layout.setSpacing(8)

        drawer_header = QHBoxLayout()
        self.tools_drawer_title = QLabel("БОКОВАЯ ПАНЕЛЬ")
        self.tools_drawer_title.setObjectName("SectionTitle")
        self.btn_close_tools_drawer = QPushButton("×")
        self.btn_close_tools_drawer.setObjectName("CloseButton")
        self.btn_close_tools_drawer.setFixedSize(34, 30)
        self.btn_close_tools_drawer.setCursor(Qt.CursorShape.PointingHandCursor)
        drawer_header.addWidget(self.tools_drawer_title)
        drawer_header.addStretch(1)
        drawer_header.addWidget(self.btn_close_tools_drawer)

        self.tools_stack = QStackedWidget()
        self.tools_stack.setObjectName("ToolsStack")
        self.tools_stack.addWidget(installer_card)
        self.tools_stack.addWidget(self.settings_scroll)
        self.tools_stack.addWidget(python_libs_card)
        self.tools_stack.addWidget(lsp_card)
        self.tools_stack.addWidget(developer_card)

        drawer_layout.addLayout(drawer_header)
        drawer_layout.addWidget(self.tools_stack)
        self.btn_close_tools_drawer.raise_()
        self.tools_drawer.setVisible(False)

        self.root_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.root_splitter.setHandleWidth(3)
        self.root_splitter.addWidget(self.sidebar_shell)
        self.root_splitter.addWidget(self.tools_drawer)
        self.root_splitter.addWidget(editor_page)
        self.root_splitter.setSizes(self.saved_root_splitter_sizes if self.saved_root_splitter_sizes else [306, 0, 1040])
        self.btn_restore_sidebar = QPushButton("☰")
        self.btn_restore_sidebar.setObjectName("CloseButton")
        self.btn_restore_sidebar.setFixedWidth(36)
        self.btn_restore_sidebar.setMinimumHeight(44)
        self.btn_restore_sidebar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_restore_sidebar.setToolTip("Показать основную боковую панель")
        self.btn_restore_sidebar.setVisible(False)
        root_layout.addWidget(self.btn_restore_sidebar)
        root_layout.addWidget(self.root_splitter, 1)

        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Astra Studio готова")

        self.btn_nav_editor.clicked.connect(self.toggle_main_sidebar)
        self.btn_nav_installer.clicked.connect(self.open_installer_tab)
        self.btn_nav_settings.clicked.connect(self.open_settings_page)
        self.btn_nav_developer.clicked.connect(self.open_developer_page)
        self.btn_nav_python_libs.clicked.connect(self.open_python_libs_page)
        self.btn_nav_lsp.clicked.connect(self.open_lsp_page)
        self.btn_lsp_refresh.clicked.connect(self._refresh_lsp_server_table)
        self.btn_lsp_start.clicked.connect(self.start_selected_lsp_server)
        self.btn_lsp_stop.clicked.connect(self.stop_selected_lsp_server)
        self.btn_lsp_install.clicked.connect(self.install_or_update_selected_lsp_server)
        self.btn_lsp_outline_refresh.clicked.connect(self.request_lsp_outline)
        self.lsp_outline_tree.itemDoubleClicked.connect(self._open_lsp_outline_item)
        self.btn_close_tools_drawer.clicked.connect(self.close_tools_drawer)
        self.btn_restore_sidebar.clicked.connect(self.toggle_main_sidebar)
        self.btn_run.clicked.connect(self.run_code)
        self.btn_compile.clicked.connect(self.compile_code)
        self.btn_format.clicked.connect(self.format_current_file)
        self.btn_lint.clicked.connect(self.lint_current_file)
        self.btn_build_exe.clicked.connect(self.build_current_exe)
        self.btn_stop.clicked.connect(self.stop_run_process)
        self.btn_new.clicked.connect(self.create_new_file_dialog)
        self.btn_enter_typer.clicked.connect(self.open_enter_typer_template)
        self.btn_open.clicked.connect(self.open_file_dialog)
        self.btn_save.clicked.connect(self.save_current_file)
        self.btn_save_as.clicked.connect(self.save_current_file_as)
        self.btn_open_folder.clicked.connect(self.open_folder_dialog)
        self.btn_create_project.clicked.connect(self.create_project_dialog)
        self.btn_open_project.clicked.connect(self.open_project_dialog)
        self.btn_add_project_folder.clicked.connect(self.add_attached_folder_dialog)
        self.btn_remove_project_folder.clicked.connect(self.remove_selected_attached_folder)
        self.btn_refresh_project.clicked.connect(self.refresh_project_tree)
        self.btn_new_project_folder.clicked.connect(self.create_folder_in_project)
        self.btn_open_project_folder.clicked.connect(self.open_selected_project_path_in_explorer)
        self.btn_project_run.clicked.connect(lambda: self.run_project_command("run"))
        self.btn_project_build.clicked.connect(lambda: self.run_project_command("build"))
        self.btn_project_test.clicked.connect(lambda: self.run_project_command("test"))
        self.btn_project_install.clicked.connect(lambda: self.run_project_command("install"))
        self.btn_project_commands.clicked.connect(self.edit_project_commands)
        self.btn_test_explorer.clicked.connect(self.open_test_explorer)
        self.btn_git_source_control.clicked.connect(self.open_git_source_control)
        self.btn_project_search.clicked.connect(self.open_project_search)
        self.btn_project_doctor.clicked.connect(self.open_project_doctor)
        self.btn_ai_context.clicked.connect(self.open_ai_context_dialog)
        self.language_combo.currentTextChanged.connect(self.change_language)
        self.theme_combo.currentTextChanged.connect(self.change_theme)
        self.accent_combo.currentTextChanged.connect(self.change_accent)
        self.opacity_toggle.toggled.connect(self.toggle_transparency)
        self.opacity_slider.valueChanged.connect(self.change_window_opacity)
        self.topmost_toggle.toggled.connect(self.toggle_always_on_top)
        self.autocomplete_toggle.toggled.connect(self.toggle_autocomplete)
        self.show_snippets_toggle.toggled.connect(self.toggle_show_snippets)
        self.accept_tab_toggle.toggled.connect(self.toggle_accept_tab)
        self.format_on_save_toggle.toggled.connect(self.toggle_format_on_save)
        self.auto_install_libs_toggle.toggled.connect(self.toggle_python_auto_install)
        self.always_ask_install_toggle.toggled.connect(self.toggle_python_install_always_ask)
        self.unknown_auto_install_toggle.toggled.connect(self.toggle_python_unknown_auto_install)
        self.open_install_log_toggle.toggled.connect(self.toggle_open_install_log)
        self.exe_mode_combo.currentTextChanged.connect(self.change_exe_build_mode)
        self.cpp_using_std_toggle.toggled.connect(self.toggle_cpp_using_namespace_std)
        self.btn_choose_wallpaper.clicked.connect(self.choose_custom_wallpaper)
        self.btn_clear_wallpaper.clicked.connect(self.clear_custom_wallpaper)
        self.preset_wallpaper_combo.currentTextChanged.connect(self.change_preset_wallpaper)
        self.btn_apply_astra_profile.clicked.connect(self.apply_astra_profile)
        self.btn_apply_angel404_profile.clicked.connect(self.apply_angel404_profile)
        self.wallpaper_all_toggle.toggled.connect(self.toggle_wallpaper_all_windows)
        self.disable_console_wallpaper_toggle.toggled.connect(self.toggle_disable_console_wallpaper)
        self.wallpaper_dim_slider.valueChanged.connect(self.change_wallpaper_dim)
        self.wallpaper_blur_slider.valueChanged.connect(self.change_wallpaper_blur)
        self.panel_transparency_slider.valueChanged.connect(self.change_all_panel_transparency)
        self.logo_frame_blur_slider.valueChanged.connect(self.change_logo_frame_blur)
        self.logo_frame_transparency_slider.valueChanged.connect(self.change_logo_frame_transparency)
        self.appearance_advanced_toggle.toggled.connect(self.set_advanced_appearance_visible)
        self.editor_tab_size_slider.valueChanged.connect(self.change_editor_tab_size)
        self.editor_indent_size_slider.valueChanged.connect(self.change_editor_indent_size)
        self.editor_insert_spaces_toggle.toggled.connect(self.toggle_editor_insert_spaces)
        self.btn_reset_indents.clicked.connect(self.reset_indent_settings)
        self.ui_font_size_slider.valueChanged.connect(self.change_ui_font_size)
        self.editor_font_size_slider.valueChanged.connect(self.change_editor_font_size)
        self.console_font_size_slider.valueChanged.connect(self.change_console_font_size)
        self.global_font_combo.currentTextChanged.connect(self.change_global_font)
        self.btn_reset_fonts.clicked.connect(self.reset_font_settings)
        self.editor_transparency_slider.valueChanged.connect(lambda value: self.change_panel_transparency("editor", value))
        self.console_transparency_slider.valueChanged.connect(lambda value: self.change_panel_transparency("console", value))
        self.settings_transparency_slider.valueChanged.connect(lambda value: self.change_panel_transparency("settings", value))
        self.project_transparency_slider.valueChanged.connect(lambda value: self.change_panel_transparency("project", value))
        self.aux_transparency_slider.valueChanged.connect(lambda value: self.change_panel_transparency("aux", value))
        self.editor_blur_slider.valueChanged.connect(lambda value: self.change_secondary_blur("editor", value))
        self.console_blur_slider.valueChanged.connect(lambda value: self.change_secondary_blur("console", value))
        self.settings_blur_slider.valueChanged.connect(lambda value: self.change_secondary_blur("settings", value))
        self.project_blur_slider.valueChanged.connect(lambda value: self.change_secondary_blur("project", value))
        self.save_window_sizes_toggle.toggled.connect(self.toggle_save_window_sizes)
        self.btn_reset_transparency.clicked.connect(self.reset_transparency_settings)
        self.btn_reset_blur.clicked.connect(self.reset_blur_settings)
        self.btn_reset_window_sizes.clicked.connect(self.reset_window_sizes)
        self.btn_reset_appearance.clicked.connect(self.reset_appearance_defaults)
        self.btn_terminal_restart.clicked.connect(self.restart_terminal)
        self.btn_terminal_clear.clicked.connect(self.terminal_console.clear)
        self.btn_check_tools.clicked.connect(self.refresh_tool_status)
        self.btn_check_app_update.clicked.connect(self.check_app_update)
        self.btn_check_updates.clicked.connect(self.check_tool_updates)
        self.btn_update_all.clicked.connect(lambda: self.install_toolchain("update_all"))
        self.btn_install_python.clicked.connect(lambda: self.install_toolchain("python"))
        self.btn_install_cpp.clicked.connect(lambda: self.install_toolchain("cpp"))
        self.btn_install_java.clicked.connect(lambda: self.install_toolchain("java"))
        self.btn_install_node.clicked.connect(lambda: self.install_toolchain("node"))
        self.btn_install_git.clicked.connect(lambda: self.install_toolchain("git"))
        self.btn_install_godot.clicked.connect(lambda: self.install_toolchain("godot"))
        self.btn_install_php.clicked.connect(lambda: self.install_toolchain("php"))
        self.btn_install_powershell.clicked.connect(lambda: self.install_toolchain("powershell"))
        self.btn_install_all.clicked.connect(lambda: self.install_toolchain("all"))
        self.btn_desktop_shortcut.clicked.connect(lambda: self.install_toolchain("shortcut"))
        self.btn_cancel_task.clicked.connect(self.cancel_active_task)
        self.task_manager.taskStarted.connect(self._on_task_started)
        self.task_manager.taskOutput.connect(self._on_task_output)
        self.task_manager.taskProgress.connect(self._on_task_progress)
        self.task_manager.taskEta.connect(self._on_task_eta)
        self.task_manager.taskFinished.connect(self._on_task_finished)
        self.task_manager.taskFailed.connect(self._on_task_failed)
        self.project_tree.itemDoubleClicked.connect(self.open_project_tree_item)
        self.refresh_project_tree()
        self._refresh_python_environment_status()
        self.set_advanced_appearance_visible(True)
        self.tabs.currentChanged.connect(self.update_current_file_label)
        self.tabs.currentChanged.connect(lambda _index: self._refresh_problems_panel())
        self.tabs.currentChanged.connect(lambda _index: self._on_current_editor_changed_for_lsp())
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.btn_python_env_refresh.clicked.connect(self._refresh_python_environment_status)
        self.btn_python_env_create.clicked.connect(self.create_project_python_environment)
        self.btn_python_env_select.clicked.connect(self.select_project_python_interpreter)
        self.btn_python_env_install_deps.clicked.connect(self.install_project_python_dependencies)
        self.btn_python_env_update_pip.clicked.connect(self.update_project_pip)
        self.btn_python_env_export.clicked.connect(self.export_project_requirements)
        self.libs_search.textChanged.connect(self.populate_library_table)
        self.libs_category_combo.currentTextChanged.connect(self.populate_library_table)
        self.btn_lib_install.clicked.connect(lambda: self.library_action("install"))
        self.btn_lib_update.clicked.connect(lambda: self.library_action("update"))
        self.btn_lib_uninstall.clicked.connect(lambda: self.library_action("uninstall"))
        self.btn_lib_check.clicked.connect(self.check_visible_library_statuses)
        self.btn_lib_install_bundle.clicked.connect(self.install_selected_library_bundle)
        self.btn_lib_open_pypi.clicked.connect(lambda: self.library_action("pypi"))
        self.btn_lib_copy_cmd.clicked.connect(lambda: self.library_action("copy"))
        self.btn_custom_pip_install.clicked.connect(lambda: self.install_arbitrary_pypi_requirement(False))
        self.btn_custom_pip_update.clicked.connect(lambda: self.install_arbitrary_pypi_requirement(True))
        self.custom_pip_edit.returnPressed.connect(lambda: self.install_arbitrary_pypi_requirement(False))

    def _apply_console_font(self, widget):
        custom_family = self._selected_custom_font_family()
        console_font = QFont(custom_family or "Cascadia Code")
        if not custom_family:
            console_font.setStyleHint(QFont.StyleHint.Monospace)
        console_font.setPointSize(self.console_font_size)
        widget.setFont(console_font)
        if hasattr(widget, "setTabStopDistance"):
            widget.setTabStopDistance(widget.fontMetrics().horizontalAdvance(" ") * 4)

    def _setup_shortcuts(self):
        QShortcut(QKeySequence("F5"), self, self.run_code)
        QShortcut(QKeySequence("Ctrl+S"), self, self.save_current_file)
        QShortcut(QKeySequence("Ctrl+Shift+S"), self, self.save_current_file_as)
        QShortcut(QKeySequence("Ctrl+O"), self, self.open_file_dialog)
        QShortcut(QKeySequence("Ctrl+N"), self, self.create_new_file_dialog)
        QShortcut(QKeySequence("Ctrl+Shift+C"), self, self.compile_code)
        QShortcut(QKeySequence("Shift+Alt+F"), self, self.format_current_file)
        QShortcut(QKeySequence("Ctrl+Shift+B"), self, self.build_current_exe)
        QShortcut(QKeySequence("Ctrl+Shift+I"), self, self.open_installer_tab)
        QShortcut(QKeySequence("Ctrl+Shift+F"), self, self.open_project_search)
        QShortcut(QKeySequence("Ctrl+P"), self, self.open_quick_open)
        QShortcut(QKeySequence("Ctrl+Space"), self, self.request_lsp_completion)
        QShortcut(QKeySequence("Ctrl+Shift+H"), self, self.request_lsp_hover)
        QShortcut(QKeySequence("Ctrl+Shift+Space"), self, self.request_lsp_signature_help)
        QShortcut(QKeySequence("F12"), self, self.request_lsp_definition)
        QShortcut(QKeySequence("Shift+F12"), self, self.request_lsp_references)
        QShortcut(QKeySequence("F2"), self, self.request_lsp_rename)
        QShortcut(QKeySequence("Ctrl+Shift+O"), self, self.request_lsp_outline)


    def _hex_to_rgb(self, color: str) -> tuple[int, int, int]:
        color = color.strip().lstrip("#")
        if len(color) == 3:
            color = "".join(ch * 2 for ch in color)
        try:
            return int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)
        except Exception:
            return 8, 12, 18

    def _rgba(self, color: str, alpha_percent: int) -> str:
        r, g, b = self._hex_to_rgb(color)
        alpha = max(0, min(255, round(255 * max(0, min(100, alpha_percent)) / 100)))
        return f"rgba({r}, {g}, {b}, {alpha})"

    def _make_percent_slider(self, label_text: str, value: int, minimum: int = 0, maximum: int = 100):
        label = QLabel(f"{label_text}: {value}%")
        label.setObjectName("MiniLabel")
        label.setWordWrap(True)
        label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setObjectName("OpacitySlider")
        slider.setRange(minimum, maximum)
        slider.setValue(value)
        return label, slider


    def update_font_labels(self):
        if hasattr(self, "ui_font_size_label"):
            self.ui_font_size_label.setText(f"Размер шрифта интерфейса: {self.ui_font_size}px")
        if hasattr(self, "editor_font_size_label"):
            self.editor_font_size_label.setText(f"Размер шрифта редактора: {self.editor_font_size} pt")
        if hasattr(self, "console_font_size_label"):
            self.console_font_size_label.setText(f"Размер шрифта консоли: {self.console_font_size} pt")

    def apply_font_settings(self, reapply_theme: bool = True):
        self._load_global_font_family()
        self._apply_application_font()
        custom_family = self._selected_custom_font_family()
        for editor in self.all_editors():
            editor.set_editor_font_size(self.editor_font_size)
            editor.set_editor_font_family(custom_family)
            editor.refresh_tab_stop_distance()
        for widget_name in ["output_console", "terminal_console", "installer_console", "git_diff_view"]:
            widget = getattr(self, widget_name, None)
            if widget is not None:
                self._apply_console_font(widget)
        self.update_font_labels()
        if reapply_theme:
            self.apply_theme()

    def change_ui_font_size(self, value):
        self.ui_font_size = max(10, min(22, int(value)))
        self.apply_font_settings(reapply_theme=True)
        self._save_settings()

    def change_editor_font_size(self, value):
        self.editor_font_size = max(8, min(32, int(value)))
        self.apply_font_settings(reapply_theme=True)
        self._save_settings()

    def change_console_font_size(self, value):
        self.console_font_size = max(8, min(28, int(value)))
        self.apply_font_settings(reapply_theme=True)
        self._save_settings()

    def change_global_font(self, name):
        if name not in GLOBAL_FONT_OPTIONS:
            return
        self.global_font_name = name
        self.apply_font_settings(reapply_theme=True)
        self._save_settings()
        self.statusBar().showMessage(f"Шрифт всего приложения: {name}", 2500)

    def reset_font_settings(self):
        self.ui_font_size = 13
        self.editor_font_size = 12
        self.console_font_size = 10
        self.global_font_name = DEFAULT_GLOBAL_FONT
        self.global_font_combo.blockSignals(True)
        self.global_font_combo.setCurrentText(self.global_font_name)
        self.global_font_combo.blockSignals(False)
        for slider, value in [
            (self.ui_font_size_slider, self.ui_font_size),
            (self.editor_font_size_slider, self.editor_font_size),
            (self.console_font_size_slider, self.console_font_size),
        ]:
            slider.blockSignals(True)
            slider.setValue(value)
            slider.blockSignals(False)
        self.apply_font_settings(reapply_theme=True)
        self._save_settings()
        self.statusBar().showMessage("Размеры шрифтов сброшены", 2200)

    def update_indent_labels(self):
        if hasattr(self, "editor_tab_size_label"):
            self.editor_tab_size_label.setText(f"Размер табуляции: {self.editor_tab_size}")
        if hasattr(self, "editor_indent_size_label"):
            self.editor_indent_size_label.setText(f"Размер отступа: {self.editor_indent_size}")
        if hasattr(self, "tab_width_label"):
            self.tab_width_label.setText(
                f"Tab width = {self.editor_tab_size} · Indent width = {self.editor_indent_size} · "
                "редактор использует моноширинный шрифт; 1 Tab визуально равен 4 пробелам при размере 4"
            )

    def apply_indent_settings_to_editors(self):
        for editor in self.all_editors():
            insert_spaces = self.editor_insert_spaces or editor.language_name in {"Python", "GDScript", "YAML"}
            editor.set_indent_options(self.editor_tab_size, self.editor_indent_size, insert_spaces)

    def change_editor_tab_size(self, value):
        self.editor_tab_size = max(1, min(12, int(value)))
        self.update_indent_labels()
        self.apply_indent_settings_to_editors()
        self._save_settings()

    def change_editor_indent_size(self, value):
        self.editor_indent_size = max(1, min(12, int(value)))
        self.update_indent_labels()
        self.apply_indent_settings_to_editors()
        self._save_settings()

    def toggle_editor_insert_spaces(self, enabled):
        self.editor_insert_spaces = bool(enabled)
        self.apply_indent_settings_to_editors()
        self._save_settings()

    def reset_indent_settings(self):
        self.editor_tab_size = 4
        self.editor_indent_size = 4
        self.editor_insert_spaces = True
        for slider, value in [(self.editor_tab_size_slider, 4), (self.editor_indent_size_slider, 4)]:
            slider.blockSignals(True)
            slider.setValue(value)
            slider.blockSignals(False)
        self.editor_insert_spaces_toggle.blockSignals(True)
        self.editor_insert_spaces_toggle.setChecked(True)
        self.editor_insert_spaces_toggle.blockSignals(False)
        self.update_indent_labels()
        self.apply_indent_settings_to_editors()
        self._save_settings()
        self.statusBar().showMessage("Отступы сброшены: Tab = 4, Indent = 4", 2200)

    def set_advanced_appearance_visible(self, visible: bool):
        advanced_widgets = [
            self.logo_frame_transparency_label, self.logo_frame_transparency_slider,
            self.editor_transparency_label, self.editor_transparency_slider,
            self.console_transparency_label, self.console_transparency_slider,
            self.settings_transparency_label, self.settings_transparency_slider,
            self.project_transparency_label, self.project_transparency_slider,
            self.aux_transparency_label, self.aux_transparency_slider,
            self.editor_blur_label, self.editor_blur_slider,
            self.console_blur_label, self.console_blur_slider,
            self.settings_blur_label, self.settings_blur_slider,
            self.project_blur_label, self.project_blur_slider,
            self.btn_reset_transparency, self.btn_reset_blur,
        ]
        for widget in advanced_widgets:
            if widget is not None:
                widget.setVisible(bool(visible))

    def change_all_panel_transparency(self, value):
        value = int(value)
        self.editor_bg_transparency_percent = value
        self.console_bg_transparency_percent = value
        self.settings_bg_transparency_percent = value
        self.project_bg_transparency_percent = value
        self.aux_bg_transparency_percent = value
        for slider in [self.editor_transparency_slider, self.console_transparency_slider, self.settings_transparency_slider, self.project_transparency_slider, self.aux_transparency_slider]:
            slider.blockSignals(True)
            slider.setValue(value)
            slider.blockSignals(False)
        self.update_wallpaper_effect_labels()
        self.apply_theme()
        self._save_settings()

    def change_logo_frame_blur(self, value):
        self.logo_frame_blur_percent = max(0, min(100, int(value)))
        self.update_wallpaper_effect_labels()
        self.apply_theme()
        self._save_settings()

    def change_logo_frame_transparency(self, value):
        self.logo_frame_transparency_percent = max(0, min(100, int(value)))
        self.update_wallpaper_effect_labels()
        self.apply_theme()
        self._save_settings()

    def _panel_rgba(self, color: str, transparency_percent: int, min_alpha: int = 46) -> str:
        transparency_percent = max(0, min(100, int(transparency_percent)))
        alpha = max(0, min(100, 100 - transparency_percent))
        if transparency_percent < 100:
            alpha = max(min_alpha, alpha)
        return self._rgba(color, alpha)

    def current_wallpaper_path(self) -> Path | None:
        if not getattr(self, "wallpaper_enabled", True):
            return None
        if self.custom_wallpaper_path:
            path = Path(self.custom_wallpaper_path)
            if path.exists() and path.is_file():
                return path
            self.write_log(f"Обои недоступны: {path}. Используется серый fallback-фон.")
            return None
        preset = ASTRA_WALLPAPERS.get(self.preset_wallpaper_name)
        if preset:
            path = resource_path(preset)
            if path.exists() and path.is_file():
                return path
            self.write_log(f"Предустановленные обои недоступны: {path}. Используется серый fallback-фон.")
        return None

    def update_wallpaper_effect_labels(self):
        if hasattr(self, "wallpaper_dim_label"):
            self.wallpaper_dim_label.setText(f"Затемнение обоев: {self.wallpaper_dim_percent}%")
        if hasattr(self, "wallpaper_blur_label"):
            self.wallpaper_blur_label.setText(f"Размытие обоев во всех окнах: {self.wallpaper_blur_px}%")
        for attr, text, value in [
            ("editor_transparency_label", "Прозрачность редактора кода", self.editor_bg_transparency_percent),
            ("console_transparency_label", "Прозрачность консоли", self.console_bg_transparency_percent),
            ("settings_transparency_label", "Прозрачность настроек", self.settings_bg_transparency_percent),
            ("project_transparency_label", "Прозрачность окна проекта", self.project_bg_transparency_percent),
            ("aux_transparency_label", "Прозрачность дополнительных окон", self.aux_bg_transparency_percent),
            ("editor_blur_label", "Размытие фона редактора", self.editor_blur_percent),
            ("console_blur_label", "Размытие фона консоли", self.console_blur_percent),
            ("settings_blur_label", "Размытие фона настроек", self.settings_blur_percent),
            ("project_blur_label", "Размытие фона проекта", self.project_blur_percent),
        ]:
            if hasattr(self, attr):
                getattr(self, attr).setText(f"{text}: {value}%")

    def update_background_wallpaper(self):
        if not hasattr(self, "background_label"):
            return
        path = self.current_wallpaper_path()
        if not path:
            self.background_label.clear()
            self.background_label.hide()
            if hasattr(self, "wallpaper_dim_overlay"):
                self.wallpaper_dim_overlay.hide()
            return
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            self.background_label.hide()
            if hasattr(self, "wallpaper_dim_overlay"):
                self.wallpaper_dim_overlay.hide()
            return
        self.background_label.setPixmap(pixmap)
        self.background_label.setGeometry(self.root.rect())
        self.background_label.lower()
        self.background_label.show()
        if hasattr(self, "wallpaper_dim_overlay"):
            self.wallpaper_dim_overlay.setGeometry(self.root.rect())
            self.wallpaper_dim_overlay.setStyleSheet(f"background: rgba(0, 0, 0, {int(255 * self.wallpaper_dim_percent / 100)});")
            self.wallpaper_dim_overlay.show()
            self.wallpaper_dim_overlay.lower()
            self.background_label.lower()
        blur_value = max(int(self.wallpaper_blur_px), int(getattr(self, "editor_blur_percent", 0)), int(getattr(self, "console_blur_percent", 0)), int(getattr(self, "settings_blur_percent", 0)), int(getattr(self, "project_blur_percent", 0)))
        if blur_value > 0 and self.wallpaper_all_windows:
            effect = QGraphicsBlurEffect(self.background_label)
            effect.setBlurRadius(float(blur_value) * 0.48)
            self.background_label.setGraphicsEffect(effect)
        else:
            self.background_label.setGraphicsEffect(None)

    def apply_theme(self):
        self.theme = dict(THEMES[self.current_theme_name])
        self.theme["accent"] = ACCENTS[self.current_accent_name]

        wallpaper_path = self.current_wallpaper_path()
        root_bg = self.theme["bg"] if wallpaper_path is not None else FALLBACK_BACKGROUND
        if self.wallpaper_all_windows and wallpaper_path is not None:
            panel_bg = self._panel_rgba(self.theme["panel"], self.aux_bg_transparency_percent)
            panel2_bg = self._panel_rgba(self.theme["panel2"], self.aux_bg_transparency_percent)
            bg2_bg = self._panel_rgba(self.theme["bg2"], self.aux_bg_transparency_percent, 76)
            console_bg = self.theme["console"] if self.disable_console_wallpaper else self._panel_rgba(self.theme["console"], self.console_bg_transparency_percent, 8)
            project_bg = self._panel_rgba(self.theme["panel"], self.project_bg_transparency_percent)
            project_tree_bg = self._panel_rgba(self.theme["bg2"], self.project_bg_transparency_percent, 82)
            settings_bg = self._panel_rgba(self.theme["panel"], self.settings_bg_transparency_percent)
            aux_bg = self._panel_rgba(self.theme["panel"], self.aux_bg_transparency_percent)
            editor_bg = self._panel_rgba(self.theme["editor"], self.editor_bg_transparency_percent, 8)
        else:
            panel_bg = self._panel_rgba(self.theme["panel"], self.aux_bg_transparency_percent)
            panel2_bg = self._panel_rgba(self.theme["panel2"], self.aux_bg_transparency_percent)
            bg2_bg = self._panel_rgba(self.theme["bg2"], self.aux_bg_transparency_percent, 76)
            console_bg = self._panel_rgba(self.theme["console"], self.console_bg_transparency_percent, 8)
            project_bg = self._panel_rgba(FALLBACK_BACKGROUND, self.project_bg_transparency_percent, 86)
            project_tree_bg = self._panel_rgba(FALLBACK_BACKGROUND, self.project_bg_transparency_percent, 92)
            settings_bg = self._panel_rgba(self.theme["panel"], self.settings_bg_transparency_percent)
            aux_bg = self._panel_rgba(self.theme["panel"], self.aux_bg_transparency_percent)
            editor_bg = self._panel_rgba(self.theme["editor"], self.editor_bg_transparency_percent, 8)

        logo_frame_bg = self._panel_rgba(self.theme["panel"], self.logo_frame_transparency_percent, 0)
        logo_frame_border = self._rgba(self.theme["accent"], max(24, min(85, 42 + self.logo_frame_blur_percent // 3)))
        logo_frame_extra_border = self._rgba("#FFFFFF", max(6, min(24, self.logo_frame_blur_percent // 4)))

        ui_font = max(10, min(22, int(getattr(self, "ui_font_size", 13))))
        mini_font = max(9, ui_font - 2)
        file_font = ui_font + 1
        dev_title_font = ui_font + 11
        close_font = ui_font + 5
        logo_font = ui_font + 21
        editor_font = max(8, min(32, int(getattr(self, "editor_font_size", 12))))
        console_font = max(8, min(28, int(getattr(self, "console_font_size", 10))))
        ui_font_css = self._font_css_stack()
        code_font_css = self._font_css_stack(code=True)
        app = QApplication.instance()
        if app is not None:
            app_font = QFont(self.global_font_family)
            app_font.setPointSize(ui_font)
            app.setFont(app_font)

        for editor in self.all_editors():
            editor.set_theme(self.theme)

        self.update_background_wallpaper()

        qss = f"""
        QMainWindow {{
            background: {root_bg};
        }}
        QWidget#Root {{
            background: {root_bg};
            {self._wallpaper_qss()}
        }}
        QWidget {{
            color: {self.theme['text']};
            font-family: {ui_font_css};
            font-size: {ui_font}px;
        }}
        QScrollArea#SidebarScroll, QScrollArea#PageScroll {{
            background: transparent;
            border: none;
        }}
        QScrollArea#SidebarScroll > QWidget > QWidget, QScrollArea#PageScroll > QWidget > QWidget {{
            background: transparent;
        }}
        QScrollArea#PageScroll QWidget#qt_scrollarea_viewport, QAbstractScrollArea#PageScroll QWidget#qt_scrollarea_viewport {{
            background: transparent;
        }}
        QFrame#SidebarShell {{
            background: transparent;
            border: none;
        }}
        QFrame#LogoCard {{
            background: {logo_frame_bg};
            border: 1px solid {logo_frame_border};
            border-top-color: {logo_frame_extra_border};
            border-radius: 18px;
        }}
        QFrame#Sidebar, QFrame#Card, QFrame#ConsoleCard {{
            background: {panel_bg};
            border: 1px solid {self.theme['border']};
            border-radius: 18px;
        }}
        QFrame#BuildStatusPanel {{
            background: {bg2_bg};
            border: 1px solid {self.theme['border']};
            border-radius: 14px;
        }}
        QFrame#ProjectPanel {{
            background: {project_bg};
            border: 1px solid {self.theme['border']};
            border-radius: 18px;
        }}
        QWidget#PageCard {{
            background: {settings_bg};
            border: 1px solid {self.theme['border']};
            border-radius: 18px;
        }}
        QFrame#SideToolsPanel {{
            background: {aux_bg};
            border: 1px solid {self.theme['border']};
            border-radius: 18px;
        }}
        QFrame#Card {{
            background: {panel2_bg};
        }}
        QFrame#LanguageCard {{
            background: {bg2_bg};
            border: 1px solid {self.theme['border']};
            border-radius: 16px;
        }}
        QLabel#Logo {{
            color: {self.theme['text']};
            font-size: {logo_font}px;
            font-weight: 900;
            letter-spacing: 1px;
        }}
        QLabel#Subtitle {{
            color: {self.theme['muted']};
            font-size: {mini_font}px;
            letter-spacing: 2px;
        }}
        QLabel#SectionTitle {{
            color: {self.theme['accent']};
            font-size: {mini_font}px;
            font-weight: 800;
            letter-spacing: 2px;
        }}
        QLabel#MiniLabel {{
            color: {self.theme['muted']};
            font-size: {mini_font}px;
            font-weight: 700;
            margin-top: 8px;
        }}
        QLabel#Pill {{
            color: {self.theme['bg']};
            background: {self.theme['accent']};
            border-radius: 10px;
            padding: 3px 10px;
            font-weight: 800;
        }}
        QLabel#FileLabel {{
            color: {self.theme['text']};
            font-size: {file_font}px;
            font-weight: 800;
        }}
        QLabel#Muted, QLabel#InfoText, QLabel#MiniLabel {{
            color: {self.theme['muted']};
            line-height: 145%;
        }}
        QLabel#DevTitle {{
            color: {self.theme['accent']};
            font-size: {dev_title_font}px;
            font-weight: 900;
        }}
        QLabel#DevText {{
            color: {self.theme['text']};
            font-size: {file_font}px;
            line-height: 150%;
        }}
        QLabel#WallpaperPreview {{
            background: {self.theme['bg2']};
            border: 1px solid {self.theme['border']};
            border-radius: 14px;
            min-height: 110px;
        }}
        QPushButton {{
            background: transparent;
            color: {self.theme['text']};
            border: 1px solid {self.theme['border']};
            border-radius: 13px;
            padding: 8px 11px;
            text-align: left;
            font-weight: 650;
        }}
        QPushButton:hover {{
            border-color: {self.theme['accent']};
            background: {self.theme['bg2']};
        }}
        QPushButton:disabled {{
            color: {self.theme['muted']};
            border-color: {self.theme['border']};
            background: transparent;
            opacity: 0.7;
        }}
        QPushButton#PrimaryButton {{
            background: {self.theme['accent']};
            color: {self.theme['bg']};
            border: 0;
            font-weight: 900;
            text-align: center;
        }}
        QPushButton#PrimaryButton:hover {{
            background: {self.theme['accent']};
        }}
        QPushButton#CloseButton {{
            background: {self.theme['bg2']};
            color: {self.theme['text']};
            border: 1px solid {self.theme['border']};
            border-radius: 10px;
            padding: 0;
            text-align: center;
            font-weight: 900;
            font-size: {close_font}px;
        }}
        QPushButton#CloseButton:hover {{
            border-color: {self.theme['accent']};
            color: {self.theme['accent']};
        }}
        QCheckBox#OpacityToggle {{
            color: {self.theme['text']};
            font-weight: 650;
            spacing: 8px;
            margin-top: 8px;
        }}
        QCheckBox#OpacityToggle::indicator {{
            width: 16px;
            height: 16px;
            border-radius: 5px;
            border: 1px solid {self.theme['border']};
            background: {self.theme['bg2']};
        }}
        QCheckBox#OpacityToggle::indicator:checked {{
            background: {self.theme['accent']};
            border-color: {self.theme['accent']};
        }}
        QSlider#OpacitySlider::groove:horizontal {{
            height: 6px;
            border-radius: 3px;
            background: {self.theme['bg2']};
        }}
        QSlider#OpacitySlider::handle:horizontal {{
            width: 16px;
            height: 16px;
            margin: -5px 0;
            border-radius: 8px;
            background: {self.theme['accent']};
        }}
        QSlider#OpacitySlider::sub-page:horizontal {{
            background: {self.theme['accent']};
            border-radius: 3px;
        }}
        QComboBox {{
            background: {self.theme['bg2']};
            color: {self.theme['text']};
            border: 1px solid {self.theme['border']};
            border-radius: 11px;
            padding: 7px 10px;
        }}
        QComboBox:hover {{
            border-color: {self.theme['accent']};
        }}
        QComboBox QAbstractItemView {{
            background: {self.theme['panel']};
            color: {self.theme['text']};
            border: 1px solid {self.theme['border']};
            selection-background-color: {self.theme['selection']};
        }}
        QTabWidget::pane {{
            border: 1px solid {self.theme['border']};
            border-radius: 13px;
            background: {editor_bg};
            top: -1px;
        }}
        QTabBar::tab {{
            background: {self.theme['panel']};
            color: {self.theme['muted']};
            border: 1px solid {self.theme['border']};
            border-bottom: 0;
            border-top-left-radius: 10px;
            border-top-right-radius: 10px;
            padding: 8px 14px;
            margin-right: 3px;
        }}
        QTabBar::tab:selected {{
            background: {self.theme['editor']};
            color: {self.theme['text']};
            border-color: {self.theme['accent']};
        }}
        QTabBar::tab:hover {{
            color: {self.theme['text']};
            border-color: {self.theme['accent']};
        }}
        QPlainTextEdit#Editor {{
            background: {editor_bg};
            color: {self.theme['text']};
            font-family: {code_font_css};
            font-size: {editor_font}pt;
            letter-spacing: 0px;
            border: 0;
            border-radius: 12px;
            padding: 10px;
            selection-background-color: {self.theme['selection']};
        }}
        QProgressBar#ProgressBar {{
            min-height: 24px;
            border: 1px solid {self.theme['border']};
            border-radius: 12px;
            background: {self.theme['bg2']};
            color: {self.theme['text']};
            text-align: center;
            font-weight: 800;
        }}
        QProgressBar#ProgressBar::chunk {{
            border-radius: 11px;
            background: {self.theme['accent']};
        }}
        QPlainTextEdit#Console {{
            background: {console_bg};
            color: {self.theme['text']};
            font-family: {code_font_css};
            font-size: {console_font}pt;
            letter-spacing: 0px;
            border: 1px solid {self.theme['border']};
            border-radius: 14px;
            padding: 10px;
            selection-background-color: {self.theme['selection']};
        }}
        QLineEdit#ConsoleInput {{
            background: {self.theme['bg2']};
            color: {self.theme['text']};
            border: 1px solid {self.theme['border']};
            border-radius: 12px;
            padding: 9px 10px;
        }}
        QLineEdit#ConsoleInput:focus {{
            border-color: {self.theme['accent']};
        }}
        QTreeWidget#ProjectTree, QTreeView#ProjectTree, QTreeWidget#ProblemsTree, QTreeWidget#TestExplorerTree, QTreeWidget#GitTree {{
            background: {project_tree_bg};
            color: {self.theme['text']};
            border: 1px solid {self.theme['border']};
            border-radius: 13px;
            padding: 6px;
            selection-background-color: {self.theme['selection']};
            outline: 0;
        }}
        QTreeWidget#ProjectTree::item, QTreeView#ProjectTree::item, QTreeWidget#ProblemsTree::item, QTreeWidget#TestExplorerTree::item, QTreeWidget#GitTree::item {{
            min-height: 24px;
            border-radius: 7px;
            padding: 2px 4px;
        }}
        QTreeWidget#ProjectTree::item:hover, QTreeView#ProjectTree::item:hover, QTreeWidget#ProblemsTree::item:hover, QTreeWidget#TestExplorerTree::item:hover, QTreeWidget#GitTree::item:hover {{
            background: {self.theme['panel']};
        }}
        QTreeWidget#ProjectTree::item:selected, QTreeView#ProjectTree::item:selected, QTreeWidget#ProblemsTree::item:selected, QTreeWidget#TestExplorerTree::item:selected, QTreeWidget#GitTree::item:selected {{
            background: {self.theme['selection']};
            color: {self.theme['text']};
        }}
        QPlainTextEdit#Editor QWidget#qt_scrollarea_viewport {{
            background: transparent;
        }}
        QPlainTextEdit#Console QWidget#qt_scrollarea_viewport {{
            background: transparent;
        }}
        QSplitter::handle {{
            background: {self.theme['bg']};
        }}
        QStatusBar {{
            background: transparent;
            color: {self.theme['muted']};
        }}
        QScrollBar:vertical, QScrollBar:horizontal {{
            background: {self.theme['bg2']};
            border: 0;
            width: 12px;
            height: 12px;
        }}
        QScrollBar::handle:vertical, QScrollBar::handle:horizontal {{
            background: {self.theme['border']};
            border-radius: 6px;
            min-height: 24px;
            min-width: 24px;
        }}
        QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover {{
            background: {self.theme['accent']};
        }}
        QScrollBar::add-line, QScrollBar::sub-line {{
            width: 0px;
            height: 0px;
        }}
        """
        self.setStyleSheet(qss)

    def _wallpaper_qss(self) -> str:
        if hasattr(self, "background_label"):
            return ""
        path = self.current_wallpaper_path()
        if not path:
            return ""
        try:
            escaped = path.resolve().as_posix().replace('\"', '\\"')
            return f'border-image: url("{escaped}") 0 0 0 0 stretch stretch;'
        except Exception:
            return ""

    def update_wallpaper_label(self):
        if not hasattr(self, "wallpaper_label"):
            return
        if not self.wallpaper_enabled:
            self.wallpaper_label.setText("Обои отключены · используется серый фон")
        elif self.custom_wallpaper_path:
            self.wallpaper_label.setText("Текущие обои: пользовательские · " + Path(self.custom_wallpaper_path).name)
        else:
            self.wallpaper_label.setText("Текущие обои Astra: " + self.preset_wallpaper_name)

    def update_wallpaper_preview(self):
        # Release 2.1: крупный предпросмотр обоев удалён из настроек ради адаптивности.
        # Метод оставлен как безопасный legacy-hook для старых сигналов и профилей.
        return

    def choose_custom_wallpaper(self):
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Выбрать обои интерфейса",
            str(Path.home()),
            "Изображения (*.png *.jpg *.jpeg *.webp *.bmp);;Все файлы (*.*)",
        )
        if not file_name:
            return
        try:
            source = Path(file_name)
            wallpapers_dir = self.data_dir / "wallpapers"
            wallpapers_dir.mkdir(parents=True, exist_ok=True)
            target = wallpapers_dir / source.name
            if target.resolve() != source.resolve():
                shutil.copy2(source, target)
            self.custom_wallpaper_path = str(target)
            self.wallpaper_enabled = True
            self.update_wallpaper_label()
            self.apply_theme()
            self._save_settings()
            self.statusBar().showMessage("Обои интерфейса обновлены", 2500)
        except Exception as exc:
            self.write_exception_log("Ошибка выбора пользовательских обоев", exc)
            QMessageBox.warning(self, "Обои интерфейса", f"Не удалось применить изображение:\n{exc}")

    def clear_custom_wallpaper(self):
        self.custom_wallpaper_path = ""
        self.wallpaper_enabled = False
        self.update_wallpaper_label()
        self.apply_theme()
        self._save_settings()
        self.write_log("Обои отключены пользователем. Включён серый fallback-фон.")
        self.statusBar().showMessage("Обои отключены · включён серый фон", 2200)

    def update_opacity_label(self):
        if not hasattr(self, "opacity_label"):
            return
        if self.transparency_enabled:
            self.opacity_label.setText(f"Прозрачность окна: {self.window_opacity_percent}%")
        else:
            self.opacity_label.setText("Прозрачность окна: выключена")

    def apply_window_opacity(self):
        if self.transparency_enabled:
            self.setWindowOpacity(max(0.35, min(1.0, self.window_opacity_percent / 100)))
        else:
            self.setWindowOpacity(1.0)
        self.update_opacity_label()
        if hasattr(self, "opacity_slider"):
            self.opacity_slider.setEnabled(self.transparency_enabled)

    def toggle_transparency(self, enabled):
        self.transparency_enabled = bool(enabled)
        self.apply_window_opacity()
        self._save_settings()
        state = "включена" if enabled else "выключена"
        self.statusBar().showMessage(f"Полупрозрачность {state}", 2200)

    def change_window_opacity(self, value):
        self.window_opacity_percent = int(value)
        self.apply_window_opacity()
        self._save_settings()


    def _ensure_log_utf8_bom(self):
        """Keep the Windows diagnostic log readable in Windows PowerShell 5.x.

        Windows PowerShell's Get-Content does not reliably auto-detect UTF-8
        without a BOM. Release 3.9 migrates an existing UTF-8 log once and
        creates new logs with UTF-8 BOM while keeping normal UTF-8 appends.
        """
        try:
            ensure_utf8_bom_log(self.log_path)
        except OSError:
            pass

    def write_log(self, message: str):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            append_utf8_bom_log(self.log_path, f"[{timestamp}] {message}\n")
        except Exception:
            pass

    def write_exception_log(self, message: str, exc: BaseException):
        self.write_log(message + "\n" + "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)))

    def _sync_topmost_toggle(self):
        if hasattr(self, "topmost_toggle"):
            self.topmost_toggle.blockSignals(True)
            self.topmost_toggle.setChecked(self.always_on_top_enabled)
            self.topmost_toggle.blockSignals(False)

    def _apply_always_on_top_qt(self):
        """Toggle only WindowStaysOnTopHint without rebuilding unrelated flags.

        The older Windows SetWindowPos + setWindowFlags fallback could run while
        the native HWND was being created, producing ERROR_INVALID_WINDOW_HANDLE
        (1400). Reapplying the full window flags could then recreate the native
        top-level window and leave its caption buttons in a broken state.
        """
        apply_topmost_hint(self, self.always_on_top_enabled)

    def apply_always_on_top(self):
        self.write_log(f"Запрос закрепления поверх окон: {self.always_on_top_enabled}")
        try:
            self._apply_always_on_top_qt()
            self.write_log("Режим поверх окон применён успешно")
        except Exception as exc:
            self.write_exception_log("Ошибка применения режима поверх окон", exc)
            self.always_on_top_enabled = False
            try:
                # A failed native transition must not leave the checkbox lying.
                self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, False)
                if not self.isVisible():
                    self.show()
            except Exception as fallback_exc:
                self.write_exception_log("Не удалось восстановить обычный режим окна", fallback_exc)
        self._sync_topmost_toggle()

    def toggle_always_on_top(self, enabled):
        previous = self.always_on_top_enabled
        self.always_on_top_enabled = bool(enabled)
        self.write_log(f"Пользователь переключил режим поверх окон: {previous} -> {self.always_on_top_enabled}")
        self.apply_always_on_top()
        self._save_settings()
        state = "включено" if self.always_on_top_enabled else "выключено"
        self.statusBar().showMessage(f"Закрепление поверх окон: {state}", 2200)

    def apply_completion_settings_to_editors(self):
        for editor in self.all_editors():
            editor.set_completion_options(self.autocomplete_enabled, self.show_snippets_enabled, self.accept_tab_enabled)

    def toggle_autocomplete(self, enabled):
        self.autocomplete_enabled = bool(enabled)
        self.apply_completion_settings_to_editors()
        self._save_settings()
        state = "включено" if enabled else "выключено"
        self.statusBar().showMessage(f"Автодополнение по Tab: {state}", 2200)

    def toggle_show_snippets(self, enabled):
        self.show_snippets_enabled = bool(enabled)
        self.apply_completion_settings_to_editors()
        self._save_settings()
        state = "включены" if enabled else "выключены"
        self.statusBar().showMessage(f"Подсказки сниппетов: {state}", 2200)

    def toggle_accept_tab(self, enabled):
        self.accept_tab_enabled = bool(enabled)
        self.apply_completion_settings_to_editors()
        self._save_settings()
        state = "включено" if enabled else "выключено"
        self.statusBar().showMessage(f"Принятие подсказки по Tab: {state}", 2200)

    def toggle_format_on_save(self, enabled):
        self.format_on_save_enabled = bool(enabled)
        self._save_settings()
        state = "включено" if enabled else "выключено"
        self.statusBar().showMessage(f"Format on Save: {state}", 2200)

    def change_theme(self, name):
        self.current_theme_name = name
        self.apply_theme()
        self._save_settings()
        self.statusBar().showMessage(f"Тема изменена: {name}", 2500)

    def change_accent(self, name):
        self.current_accent_name = name
        self.apply_theme()
        self._save_settings()
        self.statusBar().showMessage(f"Акцент изменён: {name}", 2500)

    def change_language(self, name):
        if name not in LANGUAGES:
            return
        self.current_language_name = name
        editor = self.current_editor()
        if editor and editor.file_path is None:
            editor.set_language(name)
            base = re.sub(r"\.[A-Za-z0-9]+$", "", editor.untitled_name)
            editor.untitled_name = base + LANGUAGES[name]["extension"]
            self.update_tab_title(editor)
        self._save_settings()
        self.statusBar().showMessage(f"Выбран язык: {name}", 2500)

    def all_editors(self):
        for i in range(self.tabs.count()):
            widget = self.tabs.widget(i)
            if isinstance(widget, CodeEditor):
                yield widget

    def current_editor(self):
        widget = self.tabs.currentWidget()
        return widget if isinstance(widget, CodeEditor) else None

    def tab_title_for_editor(self, editor):
        base = editor.file_path.name if editor.file_path else editor.untitled_name
        return ("● " if editor.document().isModified() else "") + base

    def add_editor_tab(self, text, file_path=None, name=None, language_name=None, file_encoding="utf-8"):
        path = Path(file_path) if file_path else None
        language = language_name or infer_language_from_path(path, self.current_language_name)
        editor = CodeEditor(
            self.theme,
            language,
            font_point_size=self.editor_font_size,
            font_family=self._selected_custom_font_family(),
        )
        editor.setObjectName("Editor")
        insert_spaces = self.editor_insert_spaces or language in {"Python", "GDScript", "YAML"}
        editor.set_indent_options(self.editor_tab_size, self.editor_indent_size, insert_spaces)
        editor.setPlainText(text)
        editor.set_completion_options(self.autocomplete_enabled, self.show_snippets_enabled, self.accept_tab_enabled)
        editor.file_path = path
        editor.file_encoding = file_encoding or "utf-8"
        editor.untitled_name = name or f"без имени {self.untitled_counter}{LANGUAGES[language]['extension']}"
        editor.document().setModified(False)
        editor.document().modificationChanged.connect(lambda _changed, ed=editor: self.update_tab_title(ed))
        lsp_change_timer = QTimer(editor)
        lsp_change_timer.setSingleShot(True)
        lsp_change_timer.setInterval(180)
        lsp_change_timer.timeout.connect(lambda ed=editor: self._sync_editor_lsp_change(ed))
        editor._astra_lsp_change_timer = lsp_change_timer
        editor.textChanged.connect(lambda ed=editor: self._schedule_editor_lsp_change(ed))

        index = self.tabs.addTab(editor, self.tab_title_for_editor(editor))
        self.tabs.setCurrentIndex(index)
        self.update_current_file_label()
        if editor.file_path is not None:
            QTimer.singleShot(0, lambda ed=editor: self._ensure_editor_lsp_open(ed))
        return editor

    def update_tab_title(self, editor):
        index = self.tabs.indexOf(editor)
        if index >= 0:
            self.tabs.setTabText(index, self.tab_title_for_editor(editor))
        self.update_current_file_label()

    def update_current_file_label(self):
        editor = self.current_editor()
        if not editor:
            self.file_label.setText("нет открытого файла")
            return
        title = editor.file_path.name if editor.file_path else editor.untitled_name
        if editor.document().isModified():
            title = f"{title}  ·  изменён"
        self.file_label.setText(f"{title}  ·  {editor.language_name}")

        self.language_combo.blockSignals(True)
        self.language_combo.setCurrentText(editor.language_name)
        self.language_combo.blockSignals(False)
        self.current_language_name = editor.language_name

    def new_from_template(self):
        language = self.current_language_name
        name = f"без имени {self.untitled_counter}{LANGUAGES[language]['extension']}"
        self.untitled_counter += 1
        template_text = self._cpp_template_for_settings() if language == "C++" else LANGUAGES[language]["template"]
        self.add_editor_tab(template_text, name=name, language_name=language)
        self.output_console.setPlainText("Astra Studio готова.\nВыбери язык в отдельной плашке и нажми «Запустить» или F5.\n")
        self.statusBar().showMessage("Создан новый файл из шаблона", 2500)

    def open_file_dialog(self):
        all_filters = ";;".join([meta["filters"] for meta in LANGUAGES.values()])
        all_filters += ";;Text files (*.txt *.md *.json);;All files (*.*)"
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Открыть файл",
            str(self.workspace_dir),
            all_filters,
        )
        if file_name:
            self.open_file(Path(file_name))

    def open_file(self, path: Path):
        path = Path(path)
        if not path.exists() or not path.is_file():
            return

        for i in range(self.tabs.count()):
            editor = self.tabs.widget(i)
            if isinstance(editor, CodeEditor) and editor.file_path == path:
                self.tabs.setCurrentIndex(i)
                self._ensure_editor_lsp_open(editor)
                return

        encoding = "utf-8"
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            try:
                text = path.read_text(encoding="cp1251")
                encoding = "cp1251"
            except (UnicodeDecodeError, OSError) as exc:
                QMessageBox.critical(self, "Ошибка открытия", f"Не удалось прочитать файл в UTF-8 или CP1251:\n{exc}")
                return
        except OSError as exc:
            QMessageBox.critical(self, "Ошибка открытия", str(exc))
            return

        self.add_editor_tab(text, file_path=path, file_encoding=encoding)
        self._save_current_project_state()
        self.statusBar().showMessage(f"Открыт файл: {path}", 3000)

    def open_from_tree(self, index):
        # Legacy hook kept for compatibility with older project-panel code.
        return

    def save_current_file(self):
        editor = self.current_editor()
        if not editor:
            return False
        if editor.file_path is None:
            return self.save_current_file_as()

        if not can_write_to_directory(editor.file_path.parent):
            QMessageBox.warning(self, "Нет прав на сохранение", self._permission_help_text(editor.file_path.parent))
            return self.save_current_file_as()

        try:
            editor.file_path.write_text(editor.toPlainText(), encoding=editor.file_encoding or "utf-8")
        except UnicodeEncodeError:
            answer = QMessageBox.question(
                self,
                "Кодировка файла",
                f"Файл открыт в {editor.file_encoding}, но новые символы нельзя сохранить в этой кодировке. Перевести файл в UTF-8?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return False
            try:
                editor.file_path.write_text(editor.toPlainText(), encoding="utf-8")
                editor.file_encoding = "utf-8"
            except OSError as exc:
                QMessageBox.critical(self, "Ошибка сохранения", str(exc))
                return False
        except PermissionError as exc:
            self.write_exception_log("Нет прав на сохранение файла", exc)
            QMessageBox.warning(self, "Нет прав на сохранение", self._permission_help_text(editor.file_path.parent))
            return self.save_current_file_as()
        except OSError as exc:
            QMessageBox.critical(self, "Ошибка сохранения", str(exc))
            return False

        editor.set_language(infer_language_from_path(editor.file_path, editor.language_name))
        self._save_editor_to_lsp(editor)
        editor.document().setModified(False)
        self.update_tab_title(editor)
        self.statusBar().showMessage(f"Сохранено: {editor.file_path}", 3000)
        self.refresh_project_tree()
        self._save_current_project_state()
        if self.format_on_save_enabled and not getattr(self, "_quality_skip_format_on_save", False):
            self.format_current_file(save_after=True, silent_if_unavailable=True)
        return True

    def save_current_file_without_format(self):
        previous = bool(getattr(self, "_quality_skip_format_on_save", False))
        self._quality_skip_format_on_save = True
        try:
            return self.save_current_file()
        finally:
            self._quality_skip_format_on_save = previous

    def save_current_file_as(self):
        editor = self.current_editor()
        if not editor:
            return False

        default_ext = LANGUAGES[editor.language_name]["extension"]
        start_folder = self.workspace_dir if can_write_to_directory(self.workspace_dir) else default_projects_dir()
        start_name = str(start_folder / (editor.file_path.name if editor.file_path else editor.untitled_name))
        all_filters = f"{LANGUAGES[editor.language_name]['filters']};;All files (*.*)"
        file_name, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить файл",
            start_name,
            all_filters,
        )
        if not file_name:
            return False

        path = Path(file_name)
        if not path.suffix:
            path = path.with_suffix(default_ext)

        old_path = editor.file_path
        old_language = editor.language_name
        editor.file_path = path
        editor.set_language(infer_language_from_path(path, editor.language_name))
        if self.save_current_file():
            if old_path is not None and Path(old_path) != path:
                self.lsp_manager.close_document(old_language, old_path)
            return True
        # A cancelled/failed Save As must not leave the tab pointing at a path
        # that was never written successfully.
        editor.file_path = old_path
        editor.set_language(old_language)
        self.update_tab_title(editor)
        return False

    def _quality_path_for_editor(self, editor) -> Path:
        if editor.file_path is not None:
            return Path(editor.file_path)
        return Path(self.project_main_folder) / editor.untitled_name

    def _quality_python_executable(self, source_path: Path) -> str | None:
        program, prefix = self._active_python_command(source_path)
        # A project venv resolves to a direct python executable. The Windows py
        # launcher may include -3; it is still usable for explicit installation,
        # but it does not help locate a project-local Ruff executable.
        if program and not prefix:
            return str(program)
        return str(program) if program else None

    def _offer_quality_tool_install(self, tool_id: str, source_path: Path) -> bool:
        refresh_runtime_paths()
        root = self._project_root_for_source(source_path)
        python_executable = self._quality_python_executable(source_path)
        plan = install_plan_for_quality_tool(tool_id, root, python_executable)
        if plan is None:
            hints = {
                "ruff": "Создай/выбери Python-окружение проекта и установи Ruff.",
                "prettier": "Для безопасной установки Prettier нужен package.json; Astra ставит его локально в devDependencies.",
                "eslint": "Для безопасной установки ESLint нужен package.json; Astra ставит его локально в devDependencies.",
                "stylua": "Для автоматической установки StyLua через npm нужен package.json. Иначе установи StyLua вручную.",
                "clang-format": "Установи LLVM/clang-format и повтори операцию.",
            }
            QMessageBox.information(self, "Качество кода", f"Инструмент {tool_id} не найден.\n\n{hints.get(tool_id, 'Установи инструмент вручную и повтори операцию.')}")
            return False
        program, args = self._wrap_windows_command_script(plan.program, list(plan.arguments))
        answer = QMessageBox.question(
            self,
            "Установить инструмент качества",
            f"Инструмент {plan.display_name} не найден. Установить/обновить его?\n\nКоманда:\n{self._safe_command_preview(program, args)}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return False
        self.bottom_tabs.setCurrentIndex(0)
        self.output_console.appendPlainText(f"\n▶ Установка {plan.display_name}: {self._safe_command_preview(program, args)}\n")
        started = self._start_process_task(
            f"quality_install_{re.sub(r'[^a-z0-9]+', '_', tool_id.lower()).strip('_')}",
            f"Устанавливается {plan.display_name}…",
            program,
            args,
            plan.workdir,
            {
                "mode": "quality_install",
                "tool_id": tool_id,
                "display_name": plan.display_name,
                "target": "output",
                "indeterminate": True,
            },
            5,
            100,
            True,
        )
        return started is not None

    def format_current_file(self, _checked=False, save_after: bool = False, silent_if_unavailable: bool = False):
        editor = self.current_editor()
        if not isinstance(editor, CodeEditor):
            return False
        if self.task_manager.has_active_task():
            if not silent_if_unavailable:
                self.statusBar().showMessage("Форматирование недоступно: уже выполняется другая задача", 3000)
            return False
        source_path = self._quality_path_for_editor(editor)
        root = self._project_root_for_source(source_path)
        refresh_runtime_paths()
        python_executable = self._quality_python_executable(source_path)
        source_text = editor.toPlainText()
        command = formatter_command(editor.language_name, source_path, root, source_text, python_executable)
        if command is None:
            tool_id = formatter_tool_for_language(editor.language_name)
            if tool_id and not silent_if_unavailable:
                self._offer_quality_tool_install(tool_id, source_path)
            elif not tool_id and not silent_if_unavailable:
                QMessageBox.information(self, "Форматирование", f"Для {editor.language_name} в {APP_VERSION} пока не настроен безопасный formatter.")
            return False
        program, args = self._wrap_windows_command_script(command.program, list(command.arguments))
        context = {
            "mode": "quality_format",
            "tool_id": command.tool_id,
            "display_name": command.display_name,
            "editor": editor,
            "path": str(source_path),
            "original_text": source_text,
            "cursor_position": int(editor.textCursor().position()),
            "save_after": bool(save_after),
            "accepted_exit_codes": list(command.accepted_exit_codes),
            "stdout_chunks": [],
            "stderr_chunks": [],
            "target": "output",
            "indeterminate": True,
        }
        self.output_console.appendPlainText(f"\n▶ Format {editor.language_name}: {command.display_name}\n")
        started = self._start_process_task(
            f"quality_format_{re.sub(r'[^a-z0-9]+', '_', editor.language_name.lower()).strip('_')}",
            f"Форматирование {source_path.name} через {command.display_name}…",
            program,
            args,
            command.workdir,
            context,
            10,
            100,
            True,
            stdin_data=command.stdin_text,
        )
        return started is not None

    def lint_current_file(self, _checked=False):
        editor = self.current_editor()
        if not isinstance(editor, CodeEditor):
            return False
        if editor.file_path is None:
            QMessageBox.information(self, "Lint", "Сначала сохрани файл: Problems должны ссылаться на реальный путь проекта.")
            return False
        if self.task_manager.has_active_task():
            self.statusBar().showMessage("Lint недоступен: уже выполняется другая задача", 3000)
            return False
        source_path = Path(editor.file_path)
        root = self._project_root_for_source(source_path)
        refresh_runtime_paths()
        python_executable = self._quality_python_executable(source_path)
        command = linter_command(editor.language_name, source_path, root, editor.toPlainText(), python_executable)
        if command is None:
            tool_id = linter_tool_for_language(editor.language_name)
            if tool_id:
                self._offer_quality_tool_install(tool_id, source_path)
            else:
                QMessageBox.information(self, "Lint", f"Для {editor.language_name} в {APP_VERSION} пока не настроен отдельный linter.")
            return False
        program, args = self._wrap_windows_command_script(command.program, list(command.arguments))
        context = {
            "mode": "quality_lint",
            "tool_id": command.tool_id,
            "display_name": command.display_name,
            "path": str(source_path),
            "parser": command.parser,
            "accepted_exit_codes": list(command.accepted_exit_codes),
            "stdout_chunks": [],
            "stderr_chunks": [],
            "target": "output",
            "indeterminate": True,
        }
        self.output_console.appendPlainText(f"\n▶ Lint {editor.language_name}: {command.display_name}\n")
        started = self._start_process_task(
            f"quality_lint_{re.sub(r'[^a-z0-9]+', '_', editor.language_name.lower()).strip('_')}",
            f"Lint {source_path.name} через {command.display_name}…",
            program,
            args,
            command.workdir,
            context,
            10,
            100,
            True,
            stdin_data=command.stdin_text,
        )
        return started is not None

    def _apply_quality_format_result(self, context: dict, exit_code: int) -> bool:
        accepted = {int(value) for value in context.get("accepted_exit_codes", [0])}
        if int(exit_code) not in accepted:
            return False
        editor = context.get("editor")
        if not isinstance(editor, CodeEditor) or self.tabs.indexOf(editor) < 0:
            return False
        original_text = str(context.get("original_text") or "")
        if editor.toPlainText() != original_text:
            self.output_console.appendPlainText("⚠ Formatter завершился после новых правок. Результат отброшен, чтобы не затереть изменения.")
            return False
        formatted = "".join(context.get("stdout_chunks") or [])
        if not formatted and original_text:
            self.output_console.appendPlainText("✕ Formatter вернул пустой stdout; исходный текст оставлен без изменений.")
            return False
        changed = formatted != original_text
        if changed:
            cursor_position = min(max(0, int(context.get("cursor_position", 0))), len(formatted))
            cursor = QTextCursor(editor.document())
            cursor.beginEditBlock()
            cursor.select(QTextCursor.SelectionType.Document)
            cursor.insertText(formatted)
            cursor.endEditBlock()
            final_cursor = editor.textCursor()
            final_cursor.setPosition(cursor_position)
            editor.setTextCursor(final_cursor)
            editor.document().setModified(True)
            self.update_tab_title(editor)
        if context.get("save_after"):
            if editor.file_path is None:
                return changed
            try:
                editor.file_path.write_text(editor.toPlainText(), encoding=editor.file_encoding or "utf-8")
            except (OSError, UnicodeEncodeError) as exc:
                self.output_console.appendPlainText(f"✕ Formatter применён в редакторе, но повторное сохранение не удалось: {exc}")
                editor.document().setModified(True)
                self.update_tab_title(editor)
                return False
            editor.document().setModified(False)
            self.update_tab_title(editor)
            self._save_editor_to_lsp(editor)
            self._save_current_project_state()
        return True

    def _set_quality_diagnostics(self, path: Path, diagnostics) -> None:
        try:
            key = str(Path(path).resolve())
        except OSError:
            key = str(Path(path))
        self.quality_diagnostics[key] = list(diagnostics or [])
        self._refresh_problems_panel()

    def _write_current_code_for_execution(self):
        editor = self.current_editor()
        if not editor:
            return None

        if editor.file_path:
            if not self.save_current_file_without_format():
                return None
            return editor.file_path

        language = editor.language_name
        if language == "Java":
            class_name = self._detect_java_class_name(editor.toPlainText()) or "Main"
            temp_name = f"{class_name}.java"
        else:
            temp_name = editor.untitled_name.replace(" ", "_")
        path = self.temp_dir / temp_name
        path.write_text(editor.toPlainText(), encoding="utf-8")
        return path

    def _run_blocking(self, program, arguments, workdir, timeout_ms=30000, output_encoding=None):
        process = QProcess(self)
        process.setWorkingDirectory(str(workdir))
        process.setProgram(program)
        process.setArguments([str(arg) for arg in arguments])
        env = QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONIOENCODING", "utf-8")
        process.setProcessEnvironment(env)
        process.start()
        if not process.waitForStarted(3000):
            return False, -1, "", f"Не удалось запустить: {program}"
        if not process.waitForFinished(timeout_ms):
            process.kill()
            return False, -1, "", "Процесс проверки превысил лимит времени и был остановлен."
        stdout = _decode_process_output(process.readAllStandardOutput().data(), output_encoding)
        stderr = _decode_process_output(process.readAllStandardError().data(), output_encoding)
        return process.exitCode() == 0, process.exitCode(), stdout, stderr

    def _has_active_background_task(self) -> bool:
        if hasattr(self, "task_manager") and self.task_manager.has_active_task():
            return True
        if self.install_process and self.install_process.state() != QProcess.ProcessState.NotRunning:
            return True
        return False

    def _task_buttons(self):
        names = [
            "btn_run", "btn_compile", "btn_format", "btn_lint", "btn_build_exe", "btn_new", "btn_enter_typer", "btn_open",
            "btn_save_as", "btn_open_folder", "btn_create_project", "btn_open_project",
            "btn_add_project_folder", "btn_remove_project_folder", "btn_refresh_project",
            "btn_new_project_folder", "btn_open_project_folder", "btn_lib_install", "btn_lib_update",
            "btn_lib_uninstall", "btn_lib_check", "btn_lib_install_bundle", "btn_install_all", "btn_update_all", "btn_install_python",
            "btn_install_cpp", "btn_install_java", "btn_install_node", "btn_install_git", "btn_install_godot", "btn_install_php",
            "btn_install_powershell", "btn_desktop_shortcut", "btn_check_tools",
            "btn_check_updates", "btn_project_run", "btn_project_build", "btn_project_test", "btn_project_install", "btn_project_commands", "btn_test_explorer", "btn_git_source_control", "btn_project_search", "btn_project_doctor",
            "btn_test_discover", "btn_test_run_all", "btn_test_run_selected", "btn_test_rerun",
            "btn_git_refresh", "btn_git_diff", "btn_git_diff_staged", "btn_git_stage", "btn_git_unstage", "btn_git_stage_all", "btn_git_unstage_all", "btn_git_commit", "btn_git_pull", "btn_git_push",
            "btn_python_env_create", "btn_python_env_select",
            "btn_python_env_install_deps", "btn_python_env_update_pip", "btn_python_env_export",
            "btn_lsp_refresh", "btn_lsp_start", "btn_lsp_stop", "btn_lsp_install", "btn_lsp_outline_refresh",
        ]
        return [getattr(self, name) for name in names if hasattr(self, name)]

    def _set_long_task_ui(self, active: bool, title: str = "", indeterminate: bool = True):
        if not hasattr(self, "build_status_panel"):
            return
        self.build_status_panel.setVisible(active)
        self.btn_cancel_task.setEnabled(active)
        if active:
            self.build_status_label.setText(title or "Идёт операция…")
            self.build_eta_label.setText("Время зависит от размера проекта" if indeterminate else "Расчёт времени…")
            if indeterminate:
                self.build_progress_bar.setRange(0, 0)
            else:
                self.build_progress_bar.setRange(0, 100)
                self.build_progress_bar.setValue(0)
            self.status_pill.setText("выполняется")
        else:
            self.build_progress_bar.setRange(0, 100)
            self.build_progress_bar.setValue(0)
            self.build_status_label.setText("")
            self.build_eta_label.setText("")
        for button in self._task_buttons():
            # Сохранение текущего файла оставляем доступным: оно безопасно и не меняет процесс сборки.
            if getattr(self, "btn_save", None) is button:
                continue
            button.setEnabled(not active)

    def _start_process_task(
        self,
        task_id: str,
        title: str,
        program: str,
        arguments: list,
        workdir: Path | str,
        context: dict | None = None,
        progress_start: int = 0,
        progress_end: int = 100,
        indeterminate: bool = True,
        stdin_data: str | bytes | None = None,
        environment: dict[str, str] | None = None,
        output_encoding: str | None = None,
    ):
        if self.task_manager.has_active_task():
            self.output_console.appendPlainText("\n⚠ Другая долгая операция уже выполняется. Заверши её или нажми «Отмена».")
            self.status_pill.setText("занято")
            return None
        self.active_task_context = dict(context or {})
        self.active_task_context.setdefault("task_id", task_id)
        self.active_task_context.setdefault("title", title)
        self.active_task_context.setdefault("target", "output")
        spec = ProcessTaskSpec(
            task_id=task_id,
            title=title,
            program=str(program),
            arguments=[str(arg) for arg in arguments],
            workdir=str(workdir),
            progress_start=progress_start,
            progress_end=progress_end,
            indeterminate=indeterminate,
            stdin_data=stdin_data,
            environment=dict(environment or {}),
            output_encoding=output_encoding,
        )
        try:
            return self.task_manager.start_process(spec)
        except RuntimeError as exc:
            self.active_task_context = {}
            self.output_console.appendPlainText(f"\n⚠ {exc}")
            self.status_pill.setText("занято")
            return None

    def _safe_command_preview(self, program: str, arguments: list) -> str:
        items = [str(program), *[str(arg) for arg in arguments]]
        return " ".join(items)

    def _append_task_text(self, task_id: str, text: str, stream: str = "stdout"):
        context = self.active_task_context if self.active_task_context.get("task_id") == task_id else {}
        target = context.get("target", "output")
        if target == "installer":
            self._append_to_installer(text)
        else:
            if self.last_run_language == "Python" and stream == "stderr":
                self._detect_missing_python_module(text)
            self._append_to_output(text)

    def _on_task_started(self, task_id: str, title: str):
        context = self.active_task_context if self.active_task_context.get("task_id") == task_id else {}
        self._set_long_task_ui(True, title, bool(context.get("indeterminate", True)))
        self.statusBar().showMessage(title, 2000)

    def _on_task_output(self, task_id: str, text: str, stream: str):
        context = self.active_task_context if self.active_task_context.get("task_id") == task_id else {}
        if context.get("mode") == "compile" and context.get("language") == "Java":
            key = "stdout_chunks" if stream == "stdout" else "stderr_chunks"
            context.setdefault(key, []).append(text)
        if context.get("mode") in {"quality_format", "quality_lint"}:
            key = "stdout_chunks" if stream == "stdout" else "stderr_chunks"
            context.setdefault(key, []).append(text)
            # Formatter output and JSON linter output are machine data. Keep them
            # out of the user console; stderr remains useful for configuration errors.
            if stream == "stderr" and text.strip():
                self._append_task_text(task_id, text, stream)
            return
        if context.get("mode") == "test_explorer":
            key = "stdout_chunks" if stream == "stdout" else "stderr_chunks"
            context.setdefault(key, []).append(text)
            self._append_task_text(task_id, text, stream)
            return
        if context.get("mode") in {"git_probe", "git_status", "git_diff", "git_mutation"}:
            key = "stdout_chunks" if stream == "stdout" else "stderr_chunks"
            context.setdefault(key, []).append(text)
            if context.get("mode") == "git_mutation" or (stream == "stderr" and text.strip()):
                self._append_task_text(task_id, text, stream)
            return
        self._append_task_text(task_id, text, stream)

    def _on_task_progress(self, task_id: str, value: int, label: str):
        if not hasattr(self, "build_progress_bar"):
            return
        if value < 0:
            self.build_progress_bar.setRange(0, 0)
        else:
            self.build_progress_bar.setRange(0, 100)
            self.build_progress_bar.setValue(max(0, min(100, value)))
        if label:
            self.build_status_label.setText(label)
        if self.active_task_context.get("target") == "installer":
            self.set_progress(max(0, value) if value >= 0 else self.install_progress_bar.value(), label or "Выполнение…")

    def _on_task_eta(self, task_id: str, text: str):
        if hasattr(self, "build_eta_label") and text:
            self.build_eta_label.setText(text)

    def _on_task_failed(self, task_id: str, message: str):
        context = self.active_task_context if self.active_task_context.get("task_id") == task_id else {}
        if context.get("mode") == "compile" and context.get("language") == "Java":
            self._append_task_text(task_id, f"\n✕ javac найден, но процесс компилятора не запустился: {message}\n", "stderr")
            self.write_log(f"[Java] compile launch failed: {message}")
        else:
            self._append_task_text(task_id, f"\n✕ Ошибка запуска процесса: {message}\n", "stderr")
        if context.get("mode") in {"git_probe", "git_status"}:
            self.git_repo_root = None
            self._render_git_state(None, f"Git: не удалось запустить команду — {message}")
        elif context.get("mode") == "git_diff" and hasattr(self, "git_diff_view"):
            self.git_diff_view.setPlainText(f"Git diff не запущен: {message}")
        self.status_pill.setText("ошибка")
        # FailedToStart may not produce a finished signal. If TaskManager has
        # already released the task, restore the UI immediately.
        if not self.task_manager.has_active_task():
            self._finish_task_ui(False, False)
            self.active_task_context = {}

    def _finish_task_ui(self, success: bool, cancelled: bool):
        self._set_long_task_ui(False)
        if hasattr(self, "git_tree"):
            self._update_git_controls()
        if cancelled:
            self.status_pill.setText("отменено")
            self.statusBar().showMessage("Операция отменена", 3000)
        else:
            self.status_pill.setText("готово" if success else "сбой")
            self.statusBar().showMessage("Операция завершена" if success else "Операция завершилась с ошибкой", 3500)

    def _on_task_finished(self, task_id: str, exit_code: int, cancelled: bool):
        context = self.active_task_context if self.active_task_context.get("task_id") == task_id else {}
        mode = context.get("mode", "process")
        target = context.get("target", "output")
        success = exit_code == 0 and not cancelled

        if cancelled:
            self._append_task_text(task_id, "\n■ Операция отменена пользователем.\n", "stdout")
            if target == "installer":
                self.set_progress(max(1, self.install_progress_bar.value()), "Операция отменена")
            self._finish_task_ui(False, True)
            self.active_task_context = {}
            return

        if mode == "compile":
            language = context.get("language", self.last_run_language)
            if language == "Java":
                compiler_output = "".join(context.get("stdout_chunks", [])) + "\n" + "".join(context.get("stderr_chunks", []))
                source_path = Path(context.get("source_path") or self.last_run_source_path)
                diagnostics = parse_linter_output("javac", compiler_output, source_path)
                self._set_quality_diagnostics(source_path, diagnostics)
                self.write_log(
                    f"[Java] compile exit={exit_code}; diagnostics={len(diagnostics)}; "
                    f"javac={context.get('javac_path', '')}"
                )
            if success:
                if language == "Python":
                    self.output_console.appendPlainText("\n✓ Синтаксис Python корректный.")
                elif language == "C++":
                    self.output_console.appendPlainText(f"\n✓ C++ сборка успешна: {context.get('binary_path', '')}")
                elif language == "Java":
                    self.output_console.appendPlainText(f"\n✓ Java сборка успешна. Главный класс: {context.get('class_name', '')}")
                elif language == "JavaScript":
                    self.output_console.appendPlainText("\n✓ JavaScript синтаксис корректен.")
                elif language == "C#":
                    self.output_console.appendPlainText(f"\n✓ C# сборка успешна: {context.get('project_dir', '')}")
                elif language in {"TypeScript", "Luau", "GDScript", "PHP", "PowerShell", "Shell"}:
                    self.output_console.appendPlainText(f"\n✓ {language}: проверка завершена успешно.")
                if context.get("run_after"):
                    self._finish_task_ui(True, False)
                    self.active_task_context = {}
                    self._run_after_compile(context)
                    return
            else:
                self.output_console.appendPlainText(f"\n✕ {language} проверка/сборка завершилась с кодом {exit_code}")
                if language == "Java":
                    self.output_console.appendPlainText("Ошибки javac относятся к исходному коду; JDK найден, установщик не требуется.")
                elif language == "C++":
                    self._ask_install_now(language)
        elif mode == "build_python_exe":
            exe_path = context.get("exe_path")
            if success:
                self.output_console.appendPlainText(f"\n✓ EXE успешно собран: {exe_path}")
                self._finish_task_ui(True, False)
                self.active_task_context = {}
                self._ask_create_shortcut_for_exe(Path(exe_path))
                return
            self.output_console.appendPlainText(f"\n✕ Ошибка сборки EXE. Код: {exit_code}")
        elif mode == "build_cpp_resource":
            if success:
                self.output_console.appendPlainText("\n✓ Иконка проекта добавлена через resource-файл.")
                extra_objects = [context.get("res_path")] if context.get("res_path") else []
            else:
                self.output_console.appendPlainText("\n⚠ Не удалось собрать resource-файл иконки. EXE будет собран без встроенной иконки.")
                extra_objects = []
            self._finish_task_ui(success, False)
            next_context = dict(context)
            next_context["extra_objects"] = extra_objects
            self.active_task_context = {}
            self._start_build_cpp_compile(next_context)
            return
        elif mode == "build_cpp_exe":
            exe_path = context.get("exe_path")
            if success:
                self.output_console.appendPlainText(f"\n✓ EXE успешно собран: {exe_path}")
                self._finish_task_ui(True, False)
                self.active_task_context = {}
                self._ask_create_shortcut_for_exe(Path(exe_path))
                return
            self.output_console.appendPlainText(f"\n✕ Ошибка сборки C++ EXE. Код: {exit_code}")
        elif mode == "pip":
            package = context.get("package", "пакет")
            if success:
                self.output_console.appendPlainText(f"\n✓ Команда pip завершена успешно: {package}")
                self.populate_library_table()
                import_names = [name for name in (context.get("import_names") or ([context.get("import_name")] if context.get("import_name") else [])) if name]
                import_status = self._python_import_status_map(import_names) if import_names else {}
                failed_imports = [name for name in import_names if not import_status.get(name, False)]
                if failed_imports:
                    QMessageBox.warning(self, "Python-библиотеки", "Пакет установлен, но проверка import пока не прошла для: " + ", ".join(failed_imports) + ". Перезапусти Astra Studio или проверь окружение Python.")
                else:
                    self.output_console.appendPlainText("✓ Проверка import после установки прошла успешно.")
                if context.get("rerun_after") and not failed_imports:
                    answer = QMessageBox.question(self, "Python-библиотеки", "Библиотека установлена. Запустить программу снова?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.Yes)
                    if answer == QMessageBox.StandardButton.Yes:
                        self._finish_task_ui(True, False)
                        self.active_task_context = {}
                        self.run_code()
                        return
            else:
                self.output_console.appendPlainText(f"\n✕ pip завершился с кодом {exit_code}")
        elif mode == "project_command":
            kind = context.get("kind", "command")
            if success:
                self.output_console.appendPlainText(f"\n✓ Project {kind} завершён успешно.")
            else:
                self.output_console.appendPlainText(f"\n✕ Project {kind} завершился с кодом {exit_code}.")
        elif mode == "test_explorer":
            adapter_id = str(context.get("adapter_id") or "")
            stdout_text = "".join(context.get("stdout_chunks") or [])
            stderr_text = "".join(context.get("stderr_chunks") or [])
            selected_id = str(context.get("selected_id") or "")
            discovered = self.test_explorer_discovered
            if selected_id:
                selected_nodes = [node for node in discovered if str(getattr(node, "test_id", "")) == selected_id]
                discovered = selected_nodes or discovered
            result = parse_test_output(adapter_id, stdout_text, stderr_text, int(exit_code), discovered)
            self.test_explorer_last_run = result
            self.test_explorer_active_adapter = adapter_id
            self._render_test_result(result)
            self._save_current_project_state()
            if hasattr(self, "tests_page"):
                index = self.bottom_tabs.indexOf(self.tests_page)
                if index >= 0:
                    self.bottom_tabs.setCurrentIndex(index)
            success = bool(result.status == "passed") and not cancelled
            if success:
                self.output_console.appendPlainText(f"\n✓ Test Explorer: {result.summary}")
            else:
                self.output_console.appendPlainText(f"\n✕ Test Explorer: {result.summary}")
        elif mode == "git_probe":
            stdout_text = "".join(context.get("stdout_chunks") or [])
            if not success:
                self.git_repo_root = None
                self._render_git_state(None, "Git: текущая папка не находится внутри репозитория")
            else:
                repo_root = parse_repo_root(stdout_text)
                if repo_root is None or not repo_root.exists():
                    self.git_repo_root = None
                    self._render_git_state(None, "Git: не удалось определить корень репозитория")
                else:
                    self._finish_task_ui(True, False)
                    self.active_task_context = {}
                    self._start_git_status_task(repo_root)
                    return
        elif mode == "git_status":
            stdout_text = "".join(context.get("stdout_chunks") or [])
            repo_root = Path(str(context.get("repo_root") or self.git_repo_root or self.project_main_folder))
            if success:
                try:
                    state = parse_porcelain_v2_z(stdout_text, repo_root)
                except Exception as exc:
                    success = False
                    self.write_exception_log("Git status parse failed", exc)
                    self._render_git_state(None, "Git: не удалось разобрать status")
                else:
                    self.git_repo_root = repo_root
                    self._render_git_state(state)
                    if hasattr(self, "git_page"):
                        index = self.bottom_tabs.indexOf(self.git_page)
                        if index >= 0:
                            self.bottom_tabs.setCurrentIndex(index)
            else:
                self._render_git_state(None, "Git: status завершился с ошибкой")
        elif mode == "git_diff":
            stdout_text = "".join(context.get("stdout_chunks") or [])
            stderr_text = "".join(context.get("stderr_chunks") or []).strip()
            path = str(context.get("path") or "")
            staged = bool(context.get("staged"))
            if success:
                if stdout_text:
                    self.git_diff_view.setPlainText(stdout_text)
                else:
                    kind = "staged" if staged else "working-tree"
                    self.git_diff_view.setPlainText(f"Нет {kind} diff для {path}. Для untracked файла сначала выполни Stage, чтобы увидеть staged diff.")
                if hasattr(self, "git_page"):
                    index = self.bottom_tabs.indexOf(self.git_page)
                    if index >= 0:
                        self.bottom_tabs.setCurrentIndex(index)
            else:
                self.git_diff_view.setPlainText(stderr_text or f"Git diff завершился с кодом {exit_code}")
        elif mode == "git_mutation":
            action = str(context.get("action") or "git")
            if success:
                self.output_console.appendPlainText(f"\n✓ Git {action} завершён успешно.")
                if action == "commit" and hasattr(self, "git_commit_message"):
                    self.git_commit_message.clear()
                repo_root = Path(self.git_repo_root) if self.git_repo_root is not None else None
                if repo_root is not None:
                    self._finish_task_ui(True, False)
                    self.active_task_context = {}
                    self._start_git_status_task(repo_root)
                    return
            else:
                self.output_console.appendPlainText(f"\n✕ Git {action} завершился с кодом {exit_code}.")
        elif mode in {"python_env_create", "python_project_dependencies", "python_update_pip"}:
            if success:
                labels = {
                    "python_env_create": "Python-окружение создано",
                    "python_project_dependencies": "Зависимости проекта установлены",
                    "python_update_pip": "pip обновлён",
                }
                self.output_console.appendPlainText("\n✓ " + labels.get(mode, "Python-операция завершена"))
                if mode == "python_env_create":
                    # Creating a project .venv is an explicit request to use that
                    # environment. Drop a previous manual override so the new .venv
                    # becomes the active project interpreter immediately.
                    self.project_python_interpreter = ""
                    self._save_current_project_state()
            else:
                self.output_console.appendPlainText(f"\n✕ Python-операция завершилась с кодом {exit_code}")
            self._refresh_python_environment_status()
        elif mode == "quality_format":
            accepted = {int(value) for value in context.get("accepted_exit_codes", [0])}
            quality_success = int(exit_code) in accepted
            if quality_success:
                applied = self._apply_quality_format_result(context, exit_code)
                if applied:
                    self.output_console.appendPlainText(f"\n✓ Форматирование завершено: {context.get('display_name', 'formatter')}")
                else:
                    quality_success = False
            if not quality_success:
                stderr_text = "".join(context.get("stderr_chunks") or []).strip()
                self.output_console.appendPlainText(f"\n✕ Форматирование завершилось с кодом {exit_code}.")
                if stderr_text:
                    self.output_console.appendPlainText(stderr_text)
            success = quality_success
        elif mode == "quality_lint":
            accepted = {int(value) for value in context.get("accepted_exit_codes", [0, 1])}
            quality_success = int(exit_code) in accepted
            path = Path(str(context.get("path") or ""))
            stdout_text = "".join(context.get("stdout_chunks") or [])
            if quality_success:
                diagnostics = parse_linter_output(str(context.get("parser") or ""), stdout_text, path)
                # Ruff/ESLint emit valid JSON even for an empty result. If the
                # process says findings exist but stdout is malformed, keep the old
                # diagnostics instead of silently clearing them.
                if int(exit_code) == 1 and stdout_text.strip() and not diagnostics:
                    try:
                        json.loads(stdout_text)
                    except json.JSONDecodeError:
                        quality_success = False
                if quality_success:
                    self._set_quality_diagnostics(path, diagnostics)
                    count = len(diagnostics)
                    self.output_console.appendPlainText(f"\n✓ Lint завершён: {count} проблем(ы).")
                    if count and hasattr(self, "problems_page"):
                        index = self.bottom_tabs.indexOf(self.problems_page)
                        if index >= 0:
                            self.bottom_tabs.setCurrentIndex(index)
            if not quality_success:
                stderr_text = "".join(context.get("stderr_chunks") or []).strip()
                self.output_console.appendPlainText(f"\n✕ Lint не выполнен корректно. Код: {exit_code}")
                if stderr_text:
                    self.output_console.appendPlainText(stderr_text)
            success = quality_success
        elif mode == "quality_install":
            refresh_runtime_paths()
            if success:
                self.output_console.appendPlainText(f"\n✓ Инструмент качества установлен/обновлён: {context.get('display_name', context.get('tool_id', 'tool'))}.")
            else:
                self.output_console.appendPlainText(f"\n✕ Установка инструмента качества завершилась с кодом {exit_code}.")
        elif mode == "lsp_install":
            language = str(context.get("language") or "")
            refresh_runtime_paths()
            self.lsp_manager.registry.reload()
            if success:
                self.output_console.appendPlainText(f"\n✓ LSP для {language} установлен/обновлён.")
                editor = self.current_editor()
                if editor and editor.file_path and editor.language_name == language:
                    self._ensure_editor_lsp_open(editor)
            else:
                self.output_console.appendPlainText(f"\n✕ Установка LSP для {language} завершилась с кодом {exit_code}.")
            self._refresh_lsp_server_table()
        elif mode in {"tool_check", "update_check"}:
            refresh_runtime_paths()
            label = "Проверка инструментов" if mode == "tool_check" else "Проверка обновлений"
            self.installer_console.appendPlainText(f"\n■ {label} завершена с кодом {exit_code}")
            self.set_progress(100 if success else max(1, self.install_progress_bar.value()), "Проверка завершена" if success else "Проверка завершилась с ошибкой")
            if not success:
                self.installer_console.appendPlainText("✕ Не удалось завершить диагностику. Проверь сообщения PowerShell выше.")
        elif mode == "installer":
            refresh_runtime_paths()
            self.installer_console.appendPlainText(f"\n■ Установщик завершён с кодом {exit_code}")
            self.set_progress(100 if success else max(1, self.install_progress_bar.value()), "Выполнение завершено" if success else "Остановка из-за ошибки")
            if success:
                self.installer_console.appendPlainText("✓ Готово. Теперь можно снова нажать «Проверить инструменты» или запустить код.")
            else:
                self.installer_console.appendPlainText("✕ Установка завершилась с ошибкой. Проверь текст выше: чаще всего не найден WinGet, нет интернета или Windows требует подтверждение.")
        else:
            self._append_task_text(task_id, f"\n■ Процесс завершён с кодом {exit_code}\n", "stdout")

        self._finish_task_ui(success, False)
        self.active_task_context = {}

    def _run_after_compile(self, context: dict):
        language = context.get("language")
        source_path = Path(context.get("source_path")) if context.get("source_path") else self.last_run_source_path
        if language == "C++" and context.get("binary_path"):
            self.output_console.appendPlainText("\n▶ Запуск собранной программы:\n")
            self._start_process(str(context["binary_path"]), [], Path(context.get("workdir", source_path.parent)))
            return
        if language == "Java" and context.get("class_name"):
            java = str(context.get("java_path") or "")
            if not java or not Path(java).is_file():
                runtime = discover_java_runtime()
                java = str(runtime.java) if runtime is not None else ""
            if not java:
                self.output_console.appendPlainText("✕ Не найден java. Открой «Установщик» и нажми «Установить Java».")
                self.status_pill.setText("ошибка")
                self._ask_install_now("Java")
                return
            runtime_dir = Path(context.get("runtime_dir", source_path.parent))
            self.output_console.appendPlainText("\n▶ Запуск Java-программы:\n")
            args = java_arguments(runtime_dir, context["class_name"])
            self.write_log(f"[Java] launch command: {self._safe_command_preview(java, args)}")
            self._start_process(java, args, runtime_dir, output_encoding="utf-8")
            return
        if language == "C#" and context.get("project_dir"):
            dotnet = compiler_path("dotnet.exe", "dotnet")
            if not dotnet:
                self.output_console.appendPlainText("✕ .NET SDK пропал из PATH после сборки. Перезапусти Astra Studio и проверь dotnet.")
                self.status_pill.setText("нет .NET")
                return
            self.output_console.appendPlainText("\n▶ Запуск C#-программы:\n")
            self._start_process(dotnet, ["run", "--no-build", "--nologo"], Path(context["project_dir"]))

    def cancel_active_task(self):
        if self.task_manager.has_active_task():
            self.output_console.appendPlainText("\n■ Запрошена отмена долгой операции…")
            if self.active_task_context.get("target") == "installer":
                self.installer_console.appendPlainText("\n■ Запрошена отмена долгой операции…")
            self.task_manager.cancel_current_task()
            return
        if self.install_process and self.install_process.state() != QProcess.ProcessState.NotRunning:
            self.install_process.terminate()
            QTimer.singleShot(1600, lambda: self.install_process.kill() if self.install_process and self.install_process.state() != QProcess.ProcessState.NotRunning else None)
            return
        self.statusBar().showMessage("Нет активной долгой операции", 2500)

    def _compile_javascript(self, source_path: Path):
        node = compiler_path("node.exe", "node")
        if not node:
            self.output_console.appendPlainText("ℹ Node.js не найден. JS-файл сохранён, но синтаксис через node --check проверить нельзя.")
            self.status_pill.setText("нет Node.js")
            return False
        ok, exit_code, stdout, stderr = self._run_blocking(node, ["--check", str(source_path)], source_path.parent)
        if stdout:
            self.output_console.appendPlainText(stdout)
        if stderr:
            self.output_console.appendPlainText(stderr)
        if ok:
            self.output_console.appendPlainText("✓ JavaScript синтаксис корректен.")
            self.status_pill.setText("проверено")
            return True
        self.output_console.appendPlainText(f"✕ JavaScript проверка завершилась с кодом {exit_code}")
        self.status_pill.setText("ошибка")
        return False

    def _prepare_csharp_project(self, source_path: Path) -> Path:
        project_dir = self.build_dir / "csharp_runtime" / source_path.stem
        project_dir.mkdir(parents=True, exist_ok=True)
        csproj = project_dir / f"{source_path.stem}.csproj"
        program = project_dir / "Program.cs"
        csproj.write_text(
            '<Project Sdk="Microsoft.NET.Sdk">\n'
            '  <PropertyGroup>\n'
            '    <OutputType>Exe</OutputType>\n'
            '    <TargetFramework>net8.0</TargetFramework>\n'
            '    <ImplicitUsings>enable</ImplicitUsings>\n'
            '    <Nullable>enable</Nullable>\n'
            '  </PropertyGroup>\n'
            '</Project>\n',
            encoding="utf-8",
        )
        source_text, _source_encoding = _read_text_utf8_or_cp1251(source_path)
        program.write_text(source_text, encoding="utf-8")
        return project_dir

    def _compile_csharp(self, source_path: Path):
        dotnet = compiler_path("dotnet.exe", "dotnet")
        if not dotnet:
            self.output_console.appendPlainText("ℹ .NET SDK не найден. C#-файл сохранён, но сборка невозможна без dotnet.")
            self.status_pill.setText("нет .NET")
            return False, None
        project_dir = self._prepare_csharp_project(source_path)
        self.last_csharp_project_dir = project_dir
        ok, exit_code, stdout, stderr = self._run_blocking(dotnet, ["build", "--nologo"], project_dir, timeout_ms=60000)
        if stdout:
            self.output_console.appendPlainText(stdout)
        if stderr:
            self.output_console.appendPlainText(stderr)
        if ok:
            self.output_console.appendPlainText(f"✓ C# сборка успешна: {project_dir}")
            self.status_pill.setText("собрано")
            return True, project_dir
        self.output_console.appendPlainText(f"✕ C# сборка завершилась с кодом {exit_code}")
        self.status_pill.setText("ошибка")
        return False, None

    def _find_upwards(self, start: Path, filename: str) -> Path | None:
        """Find a project marker by walking from start to the filesystem root."""
        current = Path(start).resolve()
        if current.is_file():
            current = current.parent
        for folder in (current, *current.parents):
            candidate = folder / filename
            if candidate.exists():
                return candidate
        return None

    def _project_root_for_source(self, source_path: Path) -> Path:
        for marker in ("astral.project.json", "pyproject.toml", "package.json", "project.godot", ".git"):
            found = self._find_upwards(source_path.parent, marker)
            if found:
                # .git is normally a directory (and can also be a worktree file);
                # in both cases the project root is its parent, never .git itself.
                if marker == ".git":
                    return found.parent
                return found.parent if found.is_file() else found
        return source_path.parent

    def _compile_structured_text(self, language: str, source_path: Path) -> bool:
        """Fast local validation for data/config formats that do not need a compiler."""
        try:
            text, _source_encoding = _read_text_utf8_or_cp1251(source_path)
            if language == "JSON":
                if source_path.suffix.lower() == ".jsonc":
                    loads_jsonc(text)
                else:
                    json.loads(text)
            elif language == "TOML":
                import tomllib
                tomllib.loads(text)
            elif language == "XML":
                import xml.etree.ElementTree as ET
                ET.fromstring(text)
            elif language == "YAML":
                try:
                    import yaml
                except ImportError:
                    self.output_console.appendPlainText("ℹ Для полной проверки YAML установи PyYAML. Файл сохранён без проверки синтаксиса.")
                    self.status_pill.setText("нет PyYAML")
                    return False
                yaml.safe_load(text)
            else:
                return False
        except Exception as exc:
            self.output_console.appendPlainText(f"✕ {language}: ошибка синтаксиса/структуры:\n{exc}")
            self.status_pill.setText("ошибка")
            return False
        self.output_console.appendPlainText(f"✓ {language}: структура корректна.")
        self.status_pill.setText("проверено")
        return True

    def compile_code(self):
        editor = self.current_editor()
        if not editor:
            return False
        if self.task_manager.has_active_task():
            self.output_console.appendPlainText("\n⚠ Дождись завершения текущей операции или нажми «Отмена».")
            return False
        source_path = self._write_current_code_for_execution()
        if not source_path:
            return False

        language = editor.language_name
        self.last_run_language = language
        self.last_run_source_path = source_path
        self.last_missing_python_module = ""
        self.bottom_tabs.setCurrentIndex(0)
        self.output_console.clear()
        self.output_console.appendPlainText(f"◆ Проверка / сборка: {source_path}\n")
        self.output_console.appendPlainText(f"Язык: {language}\nПапка проекта: {source_path.parent}\n")

        if language == "Python":
            py_program, py_args = self._active_python_command(source_path)
            if not py_program:
                self.output_console.appendPlainText("✕ Не найден Python-интерпретатор. Открой «Установщик» и нажми «Установить Python».")
                self._ask_install_now("Python")
                return False
            args = [*py_args, "-m", "py_compile", str(source_path)]
            self.output_console.appendPlainText("Этапы: подготовка → проверка синтаксиса → завершение\n")
            self.output_console.appendPlainText(f"▶ Команда: {self._safe_command_preview(py_program, args)}\n")
            self._start_process_task("compile_python", "Идёт проверка Python…", py_program, args, source_path.parent, {"mode": "compile", "language": language, "source_path": str(source_path), "indeterminate": False}, 5, 100, False)
            return None
        if language == "C++":
            return self._start_compile_cpp_task(source_path, run_after=False)
        if language == "Java":
            return self._start_compile_java_task(source_path, run_after=False)
        if language == "JavaScript":
            node = compiler_path("node.exe", "node")
            if not node:
                self.output_console.appendPlainText("ℹ Node.js не найден. JS-файл сохранён, но синтаксис через node --check проверить нельзя.")
                self.status_pill.setText("нет Node.js")
                return False
            args = ["--check", str(source_path)]
            self.output_console.appendPlainText("Этапы: подготовка → node --check → завершение\n")
            self.output_console.appendPlainText(f"▶ Команда: {self._safe_command_preview(node, args)}\n")
            self._start_process_task("compile_js", "Идёт проверка JavaScript…", node, args, source_path.parent, {"mode": "compile", "language": language, "source_path": str(source_path), "indeterminate": False}, 5, 100, False)
            return None
        if language == "TypeScript":
            tsc = project_tool_path(source_path.parent, "tsc")
            if not tsc:
                self.output_console.appendPlainText("✕ Не найден TypeScript compiler (tsc). Установи Node.js и TypeScript в проекте или глобально.")
                self.status_pill.setText("нет tsc")
                return False
            tsconfig = self._find_upwards(source_path.parent, "tsconfig.json")
            if tsconfig:
                args = ["--pretty", "false", "--noEmit", "--project", str(tsconfig)]
                workdir = tsconfig.parent
                self.output_console.appendPlainText(f"ℹ Найден tsconfig.json: {tsconfig}")
            else:
                args = ["--pretty", "false", "--noEmit", str(source_path)]
                workdir = source_path.parent
            self.output_console.appendPlainText(f"▶ Команда: {self._safe_command_preview(tsc, args)}\n")
            self._start_process_task("compile_typescript", "Идёт проверка TypeScript…", tsc, args, workdir, {"mode": "compile", "language": language, "source_path": str(source_path), "indeterminate": True}, 10, 100, True)
            return None
        if language == "Luau":
            analyzer = compiler_path("luau-analyze.exe", "luau-analyze")
            if not analyzer:
                self.output_console.appendPlainText("ℹ luau-analyze не найден. Файл сохранён; диагностику можно получать через Luau LSP, если luau-lsp установлен и запущен Astra.")
                self.status_pill.setText("нет analyzer")
                return False
            args = [str(source_path)]
            self._start_process_task("compile_luau", "Идёт проверка Luau…", analyzer, args, source_path.parent, {"mode": "compile", "language": language, "source_path": str(source_path), "indeterminate": True}, 10, 100, True)
            return None
        if language == "GDScript":
            godot = compiler_path("godot4.exe", "godot.exe", "godot4", "godot")
            project_file = self._find_upwards(source_path.parent, "project.godot")
            if not godot or not project_file:
                self.output_console.appendPlainText("ℹ Для проверки GDScript нужен Godot 4 и project.godot. Файл сохранён.")
                self.status_pill.setText("нет Godot/project")
                return False
            args = ["--headless", "--path", str(project_file.parent), "--editor", "--quit-after", "1"]
            self._start_process_task("compile_gdscript", "Godot проверяет проект…", godot, args, project_file.parent, {"mode": "compile", "language": language, "source_path": str(source_path), "indeterminate": True}, 10, 100, True)
            return None
        if language == "PHP":
            php = compiler_path("php.exe", "php")
            if not php:
                self.output_console.appendPlainText("✕ PHP CLI не найден в PATH.")
                self.status_pill.setText("нет PHP")
                return False
            args = ["-l", str(source_path)]
            self._start_process_task("compile_php", "Идёт проверка PHP…", php, args, source_path.parent, {"mode": "compile", "language": language, "source_path": str(source_path), "indeterminate": False}, 10, 100, False)
            return None
        if language == "PowerShell":
            ps = compiler_path("pwsh.exe", "pwsh", "powershell.exe", "powershell")
            if not ps:
                self.output_console.appendPlainText("✕ PowerShell не найден.")
                self.status_pill.setText("нет PowerShell")
                return False
            command = "& { param([string]$p) $null = [scriptblock]::Create([IO.File]::ReadAllText($p)); Write-Output 'PowerShell syntax OK' }"
            args = ["-NoProfile", "-Command", command, str(source_path)]
            self._start_process_task("compile_powershell", "Идёт проверка PowerShell…", ps, args, source_path.parent, {"mode": "compile", "language": language, "source_path": str(source_path), "indeterminate": False}, 10, 100, False)
            return None
        if language == "Shell":
            if source_path.name.lower().startswith(".env"):
                self.output_console.appendPlainText("✓ .env-файл сохранён. Astra не применяет к dotenv-конфигам Bash-проверку, потому что это не shell-скрипт.")
                self.status_pill.setText("готово")
                return True
            bash = compiler_path("bash.exe", "bash")
            if not bash:
                self.output_console.appendPlainText("ℹ Bash не найден. На Windows его можно получить через Git Bash, MSYS2 или WSL.")
                self.status_pill.setText("нет bash")
                return False
            args = ["-n", str(source_path)]
            self._start_process_task("compile_shell", "Идёт проверка Shell…", bash, args, source_path.parent, {"mode": "compile", "language": language, "source_path": str(source_path), "indeterminate": False}, 10, 100, False)
            return None
        if language in {"JSON", "YAML", "TOML", "XML"}:
            return self._compile_structured_text(language, source_path)
        if language in {"Markdown", "Dockerfile"}:
            self.output_console.appendPlainText(f"✓ {language}: файл сохранён. Отдельная компиляция не требуется.")
            self.status_pill.setText("готово")
            return True
        if language == "C#":
            return self._start_compile_csharp_task(source_path, run_after=False)
        if language == "SQL":
            self.output_console.appendPlainText("✓ SQL-файл сохранён. Выполнение SQL требует подключённой базы данных или project command.")
            self.status_pill.setText("готово")
            return True
        if language == "HTML":
            self.output_console.appendPlainText("✓ HTML не требует компиляции. Файл сохранён и готов к открытию в браузере.")
            self.status_pill.setText("готово")
            return True
        if language == "CSS":
            self.output_console.appendPlainText("✓ CSS не требует компиляции. Файл сохранён и готов к подключению в HTML.")
            self.status_pill.setText("готово")
            return True

        self.output_console.appendPlainText("Этот язык пока не поддерживается.")
        self.status_pill.setText("сбой")
        return False

    def _start_compile_cpp_task(self, source_path: Path, run_after: bool = False):
        compiler = compiler_path("g++", "g++.exe", "clang++", "clang++.exe")
        if not compiler:
            self.output_console.appendPlainText("✕ Не найден C++ компилятор. Открой боковую панель «Установщик» и нажми «Установить C++».")
            self.status_pill.setText("нет компилятора")
            self._ask_install_now("C++")
            return False
        suffix = ".exe" if os.name == "nt" else ""
        binary_path = self.build_dir / f"{source_path.stem}{suffix}"
        compile_flags, linker_flags = self._cpp_extra_args(source_path)
        args = ["-std=c++17", "-Wall", "-Wextra", "-fdiagnostics-color=never", *compile_flags, str(source_path), "-o", str(binary_path), *linker_flags]
        if linker_flags:
            self.output_console.appendPlainText("ℹ Обнаружены Windows/GDI-вызовы — добавлены системные библиотеки: " + " ".join(linker_flags))
        self.output_console.appendPlainText("Этапы: подготовка → запуск компилятора → сборка → завершение\n")
        self.output_console.appendPlainText(f"▶ Команда: {self._safe_command_preview(compiler, args)}\n")
        self._start_process_task(
            "compile_cpp_run" if run_after else "compile_cpp",
            "Идёт компиляция C++…",
            compiler,
            args,
            source_path.parent,
            {"mode": "compile", "language": "C++", "source_path": str(source_path), "binary_path": str(binary_path), "run_after": run_after, "workdir": str(source_path.parent), "indeterminate": True},
            20,
            100,
            True,
        )
        return None

    def _start_compile_java_task(self, source_path: Path, run_after: bool = False):
        runtime = discover_java_runtime()
        if runtime is None:
            self.output_console.appendPlainText("✕ Не найдена согласованная пара javac/java из одного JDK. Открой «Установщик» и нажми «Установить Java».")
            self.status_pill.setText("нет JDK")
            self._ask_install_now("Java")
            return False
        javac = str(runtime.javac)
        java = str(runtime.java)
        version = java_version(runtime)
        self.output_console.appendPlainText(
            f"✓ JDK найден: {runtime.home}\n"
            f"  javac: {javac}\n  java: {java}\n  версия: {version}\n  источник: {runtime.source}"
        )
        self.write_log(
            f"[Java] runtime discovered: javac={javac}; java={java}; version={version}; source={runtime.source}"
        )
        text, source_encoding = _read_text_utf8_or_cp1251(source_path)
        class_name = self._detect_java_class_name(text) or source_path.stem
        compile_source = source_path
        runtime_dir = source_path.parent
        needs_temp_copy = bool(class_name and source_path.stem != class_name) or source_encoding != "utf-8"
        if needs_temp_copy:
            runtime_dir = self.build_dir / "java_runtime" / class_name
            runtime_dir.mkdir(parents=True, exist_ok=True)
            compile_source = runtime_dir / f"{class_name}.java"
            compile_source.write_text(text, encoding="utf-8")
            if source_encoding != "utf-8":
                self.output_console.appendPlainText(f"ℹ Java-файл открыт как {source_encoding}; для javac создана временная UTF-8 копия: {compile_source}")
            elif class_name and source_path.stem != class_name:
                self.output_console.appendPlainText(f"ℹ Java требует, чтобы public class совпадал с именем файла. Для сборки создана временная копия: {compile_source}")
        self.last_java_classpath = runtime_dir
        args = javac_arguments(compile_source)
        self.output_console.appendPlainText("Этапы: подготовка → javac → завершение\n")
        self.output_console.appendPlainText(f"▶ Команда: {self._safe_command_preview(javac, args)}\n")
        self.write_log(f"[Java] compile command: {self._safe_command_preview(javac, args)}")
        self._start_process_task(
            "compile_java_run" if run_after else "compile_java",
            "Идёт компиляция Java…",
            javac,
            args,
            compile_source.parent,
            {"mode": "compile", "language": "Java", "source_path": str(source_path), "compile_source": str(compile_source), "class_name": class_name, "runtime_dir": str(runtime_dir), "javac_path": javac, "java_path": java, "java_version": version, "runtime_source": runtime.source, "run_after": run_after, "indeterminate": True},
            20,
            100,
            True,
            output_encoding="utf-8",
        )
        return None

    def _start_compile_csharp_task(self, source_path: Path, run_after: bool = False):
        dotnet = compiler_path("dotnet.exe", "dotnet")
        if not dotnet:
            self.output_console.appendPlainText("ℹ .NET SDK не найден. C#-файл сохранён, но сборка невозможна без dotnet.")
            self.status_pill.setText("нет .NET")
            return False
        project_dir = self._prepare_csharp_project(source_path)
        self.last_csharp_project_dir = project_dir
        args = ["build", "--nologo"]
        self.output_console.appendPlainText("Этапы: подготовка → dotnet build → завершение\n")
        self.output_console.appendPlainText(f"▶ Команда: {self._safe_command_preview(dotnet, args)}\n")
        self._start_process_task(
            "compile_csharp_run" if run_after else "compile_csharp",
            "Идёт сборка C#…",
            dotnet,
            args,
            project_dir,
            {"mode": "compile", "language": "C#", "source_path": str(source_path), "project_dir": str(project_dir), "run_after": run_after, "indeterminate": True},
            20,
            100,
            True,
        )
        return None

    def _compile_python(self, source_path: Path):
        try:
            pyc_path = py_compile.compile(str(source_path), doraise=True)
        except py_compile.PyCompileError as exc:
            self.output_console.appendPlainText("✕ Ошибка компиляции Python:\n")
            self.output_console.appendPlainText(str(exc))
            self.status_pill.setText("ошибка")
            self.statusBar().showMessage("Проверка не пройдена", 3000)
            return False
        except Exception as exc:
            self.output_console.appendPlainText("✕ Ошибка:\n")
            self.output_console.appendPlainText(str(exc))
            self.status_pill.setText("ошибка")
            return False

        self.output_console.appendPlainText("✓ Синтаксис Python корректный.")
        self.output_console.appendPlainText(f"✓ Создан .pyc: {pyc_path}")
        self.status_pill.setText("проверено")
        self.statusBar().showMessage("Проверка завершена", 3000)
        return True

    def _cpp_extra_args(self, source_path: Path) -> tuple[list[str], list[str]]:
        """Возвращает дополнительные флаги компиляции и линковки для типовых Windows/C++ задач."""
        source_encoding = "utf-8"
        try:
            text, source_encoding = _read_text_utf8_or_cp1251(source_path)
        except OSError:
            text = ""

        input_charset = "CP1251" if source_encoding == "cp1251" else "UTF-8"
        compile_flags: list[str] = [f"-finput-charset={input_charset}", "-fexec-charset=UTF-8"]
        linker_flags: list[str] = []

        if os.name == "nt":
            win_triggers = (
                "windows.h", "windowsx.h", "wingdi.h", "winuser.h", "commctrl.h", "commdlg.h",
                "shellapi.h", "winsock2.h", "mmsystem.h", "dwmapi.h", "uxtheme.h", "shlwapi.h",
                "StretchDIBits", "SetBkMode", "SetTextColor", "CreateFont", "CreateFontW",
                "SelectObject", "DeleteObject", "BitBlt", "CreateCompatibleDC", "AlphaBlend",
                "TransparentBlt", "GradientFill", "MessageBox", "CreateWindow", "CreateWindowEx",
                "DefWindowProc", "WndProc", "DialogBox", "GetOpenFileName", "ShellExecute",
                "WinMain", "wWinMain", "HDC", "HWND", "HINSTANCE", "WNDCLASS", "WNDCLASSEX",
                "WSAStartup", "PlaySound", "DwmExtendFrameIntoClientArea", "SetWindowTheme",
                "GetFileVersionInfo", "ImmGetContext", "glBegin", "glClear", "OpenGL",
            )
            if any(trigger in text for trigger in win_triggers):
                # MinGW/MSYS2 не подключает графические библиотеки Windows автоматически.
                # Эти флаги закрывают типичные ошибки undefined reference для GDI/User32/WinAPI.
                linker_flags.extend([
                    "-lgdi32",
                    "-luser32",
                    "-lkernel32",
                    "-lcomdlg32",
                    "-lcomctl32",
                    "-lole32",
                    "-loleaut32",
                    "-luuid",
                    "-lwinmm",
                    "-lws2_32",
                    "-ladvapi32",
                    "-lshell32",
                    "-lmsimg32",
                    "-ldwmapi",
                    "-luxtheme",
                    "-lversion",
                    "-limm32",
                    "-lshlwapi",
                    "-lopengl32",
                    "-lglu32",
                ])
            if re.search(r"\b(wWinMain|WinMain)\b", text):
                compile_flags.append("-mwindows")
            if re.search(r"\bwWinMain\b", text):
                compile_flags.append("-municode")

        return compile_flags, linker_flags

    def _compile_cpp(self, source_path: Path):
        compiler = compiler_path("g++", "g++.exe", "clang++", "clang++.exe")
        if not compiler:
            self.output_console.appendPlainText(
                "✕ Не найден C++ компилятор.\n"
                "Открой боковую панель «Установщик» и нажми «Установить C++» — Astra поставит MSYS2/g++ и добавит путь автоматически."
            )
            self.status_pill.setText("нет компилятора")
            self._ask_install_now("C++")
            return False, None

        suffix = ".exe" if os.name == "nt" else ""
        binary_path = self.build_dir / f"{source_path.stem}{suffix}"
        compile_flags, linker_flags = self._cpp_extra_args(source_path)
        args = ["-std=c++17", "-Wall", "-Wextra", "-fdiagnostics-color=never", *compile_flags, str(source_path), "-o", str(binary_path), *linker_flags]
        if linker_flags:
            self.output_console.appendPlainText("ℹ Обнаружены Windows/GDI-вызовы — добавлены системные библиотеки: " + " ".join(linker_flags))
        ok, exit_code, stdout, stderr = self._run_blocking(compiler, args, source_path.parent)
        if stdout:
            self.output_console.appendPlainText(stdout)
        if stderr:
            self.output_console.appendPlainText(stderr)

        if ok:
            self.output_console.appendPlainText(f"✓ C++ сборка успешна: {binary_path}")
            self.status_pill.setText("собрано")
            return True, binary_path

        self.output_console.appendPlainText(f"✕ C++ сборка завершилась с кодом {exit_code}")
        self.status_pill.setText("ошибка")
        return False, None

    def _detect_java_class_name(self, text: str) -> str | None:
        match = re.search(r"public\s+class\s+([A-Za-z_][A-Za-z0-9_]*)", text)
        if match:
            return match.group(1)
        match = re.search(r"class\s+([A-Za-z_][A-Za-z0-9_]*)", text)
        return match.group(1) if match else None

    def _compile_java(self, source_path: Path):
        runtime = discover_java_runtime()
        if runtime is None:
            self.output_console.appendPlainText(
                "✕ Не найдена согласованная пара javac/java из одного JDK.\n"
                "Открой боковую панель «Установщик» и нажми «Установить Java» — Astra поставит JDK и добавит путь автоматически."
            )
            self.status_pill.setText("нет JDK")
            self._ask_install_now("Java")
            return False, None

        text, source_encoding = _read_text_utf8_or_cp1251(source_path)
        class_name = self._detect_java_class_name(text) or source_path.stem
        compile_source = source_path
        runtime_dir = source_path.parent
        if (class_name and source_path.stem != class_name) or source_encoding != "utf-8":
            runtime_dir = self.build_dir / "java_runtime" / class_name
            runtime_dir.mkdir(parents=True, exist_ok=True)
            compile_source = runtime_dir / f"{class_name}.java"
            compile_source.write_text(text, encoding="utf-8")
            self.output_console.appendPlainText(
                f"ℹ Java требует, чтобы public class совпадал с именем файла. "
                f"Для сборки создана временная копия: {compile_source}"
            )
        self.last_java_classpath = runtime_dir
        ok, exit_code, stdout, stderr = self._run_blocking(
            str(runtime.javac), javac_arguments(compile_source), compile_source.parent, output_encoding="utf-8"
        )
        if stdout:
            self.output_console.appendPlainText(stdout)
        if stderr:
            self.output_console.appendPlainText(stderr)

        if ok:
            self.output_console.appendPlainText(f"✓ Java сборка успешна. Главный класс: {class_name}")
            self.status_pill.setText("собрано")
            return True, class_name

        self.output_console.appendPlainText(f"✕ Java сборка завершилась с кодом {exit_code}")
        self.status_pill.setText("ошибка")
        return False, None

    def run_code(self):
        if self.run_process and self.run_process.state() != QProcess.ProcessState.NotRunning:
            self.output_console.appendPlainText("\nПроцесс уже запущен. Нажми «Остановить», если нужно завершить его.")
            return
        if self.task_manager.has_active_task():
            self.output_console.appendPlainText("\n⚠ Дождись завершения текущей операции или нажми «Отмена».")
            return

        editor = self.current_editor()
        if not editor:
            return
        source_path = self._write_current_code_for_execution()
        if not source_path:
            return

        language = editor.language_name
        self.last_run_language = language
        self.last_run_source_path = source_path
        self.last_missing_python_module = ""
        self.bottom_tabs.setCurrentIndex(0)
        self.output_console.clear()
        self.output_console.appendPlainText(f"▶ Запуск: {source_path}\n")
        self.output_console.appendPlainText(f"Язык: {language}\nПапка проекта: {source_path.parent}\n")
        self.status_pill.setText("запуск")

        if language == "Python":
            py_program, py_args = self._active_python_command(source_path)
            if not py_program:
                self.output_console.appendPlainText("✕ Не найден Python-интерпретатор. Открой боковую панель «Установщик» и нажми «Установить Python».")
                self.status_pill.setText("нет Python")
                self._ask_install_now("Python")
                return
            if ("# Astra Studio Template: Имитация ввода" in editor.toPlainText() or "# Astral Studio Template: Имитация ввода" in editor.toPlainText()):
                answer = QMessageBox.warning(
                    self,
                    "Имитация ввода",
                    "Этот скрипт имитирует нажатия клавиш. Используйте его только в своих окнах и с понятной целью.\n\nПродолжить запуск?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if answer != QMessageBox.StandardButton.Yes:
                    self.status_pill.setText("отменено")
                    return
                if not self.ensure_python_packages_for_enter_typer():
                    self.status_pill.setText("нет библиотек")
                    return
            if not self._ensure_python_imports_before_run(editor.toPlainText(), source_path):
                self.status_pill.setText("нет библиотек")
                return
            self._start_process(py_program, py_args + ["-u", str(source_path)], source_path.parent)
            return
        if language == "C++":
            self._start_compile_cpp_task(source_path, run_after=True)
            return
        if language == "Java":
            self._start_compile_java_task(source_path, run_after=True)
            return
        if language == "JavaScript":
            node = compiler_path("node.exe", "node")
            if not node:
                self.output_console.appendPlainText("✕ Не найден Node.js. Установи Node.js и проверь, что node доступен в PATH.")
                self.status_pill.setText("нет Node.js")
                return
            self._start_process(node, [str(source_path)], source_path.parent)
            return
        if language == "TypeScript":
            runner = project_tool_path(source_path.parent, "tsx", "ts-node")
            if not runner:
                self.output_console.appendPlainText("✕ Для прямого запуска TypeScript нужен tsx или ts-node. Проверку кода можно выполнить кнопкой «Проверить код» через tsc.")
                self.status_pill.setText("нет TS runner")
                return
            self._start_process(runner, [str(source_path)], source_path.parent)
            return
        if language == "Luau":
            luau = compiler_path("luau.exe", "luau")
            if not luau:
                self.output_console.appendPlainText("✕ Luau CLI не найден. Для Roblox-проектов запуск будет вынесен в проектную конфигурацию/Studio.")
                self.status_pill.setText("нет Luau CLI")
                return
            self._start_process(luau, [str(source_path)], source_path.parent)
            return
        if language == "GDScript":
            godot = compiler_path("godot4.exe", "godot.exe", "godot4", "godot")
            project_file = self._find_upwards(source_path.parent, "project.godot")
            if not godot or not project_file:
                self.output_console.appendPlainText("✕ Для запуска GDScript нужен Godot 4 и файл project.godot.")
                self.status_pill.setText("нет Godot/project")
                return
            self.output_console.appendPlainText(f"ℹ Запускается Godot-проект: {project_file.parent}")
            self._start_process(godot, ["--path", str(project_file.parent)], project_file.parent)
            return
        if language == "PHP":
            php = compiler_path("php.exe", "php")
            if not php:
                self.output_console.appendPlainText("✕ PHP CLI не найден в PATH.")
                self.status_pill.setText("нет PHP")
                return
            self._start_process(php, [str(source_path)], source_path.parent)
            return
        if language == "PowerShell":
            ps = compiler_path("pwsh.exe", "pwsh", "powershell.exe", "powershell")
            if not ps:
                self.output_console.appendPlainText("✕ PowerShell не найден.")
                self.status_pill.setText("нет PowerShell")
                return
            args = ["-NoProfile"]
            if Path(ps).name.lower().startswith("powershell"):
                args += ["-ExecutionPolicy", "Bypass"]
            args += ["-File", str(source_path)]
            self._start_process(ps, args, source_path.parent)
            return
        if language == "Shell":
            if source_path.name.lower().startswith(".env"):
                self.output_console.appendPlainText(".env — файл конфигурации окружения, Astra не выполняет его как Shell-скрипт. Используй «Проверить код» только для обычных .sh/.bash файлов.")
                self.status_pill.setText("готово")
                return
            bash = compiler_path("bash.exe", "bash")
            if not bash:
                self.output_console.appendPlainText("✕ Bash не найден. На Windows используй Git Bash, MSYS2 или WSL.")
                self.status_pill.setText("нет bash")
                return
            self._start_process(bash, [str(source_path)], source_path.parent)
            return
        if language in {"JSON", "YAML", "Markdown", "TOML", "XML", "Dockerfile"}:
            self.output_console.appendPlainText(f"{language} не является самостоятельной исполняемой программой. Используй «Проверить код» или проектную команду Run/Build/Test.")
            self.status_pill.setText("готово")
            return
        if language == "C#":
            self._start_compile_csharp_task(source_path, run_after=True)
            return
        if language == "SQL":
            self.output_console.appendPlainText("SQL-файл не запускается без подключения к конкретной базе данных. Сохрани запрос и выполни его в своей СУБД.")
            self.status_pill.setText("готово")
            return
        if language == "HTML":
            opened = QDesktopServices.openUrl(QUrl.fromLocalFile(str(source_path)))
            if opened:
                self.output_console.appendPlainText("✓ HTML-файл открыт в браузере по умолчанию.")
                self.status_pill.setText("открыто")
            else:
                self.output_console.appendPlainText("✕ Не удалось открыть HTML-файл в браузере.")
                self.status_pill.setText("ошибка")
            return
        if language == "CSS":
            self.output_console.appendPlainText("CSS-файл нельзя запустить отдельно. Подключи его в HTML через <link rel=\"stylesheet\" href=\"style.css\">.")
            self.status_pill.setText("готово")
            return

    def _start_process(self, program, arguments, workdir, output_encoding=None):
        self.run_process = QProcess(self)
        self.run_process.setWorkingDirectory(str(workdir))
        self.run_process.setProgram(str(program))
        self.run_process.setArguments([str(arg) for arg in arguments])
        env = QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONIOENCODING", "utf-8")
        self.run_process.setProcessEnvironment(env)
        self.run_output_encoding = output_encoding
        self.run_process.readyReadStandardOutput.connect(self._read_run_stdout)
        self.run_process.readyReadStandardError.connect(self._read_run_stderr)
        self.run_process.errorOccurred.connect(lambda _error: self._run_process_start_failed(program))
        self.run_process.finished.connect(self._run_process_finished)
        self.output_console.appendPlainText(f"▶ Команда: {self._safe_command_preview(str(program), arguments)}\n")
        self.run_process.start()

    def _run_process_start_failed(self, program):
        if self.last_run_language == "Java":
            self.output_console.appendPlainText(f"✕ Java runtime найден, но процесс запуска не стартовал: {program}")
            self.write_log(f"[Java] launch failed: {program}")
        else:
            self.output_console.appendPlainText(f"✕ Не удалось запустить процесс: {program}")
        self.status_pill.setText("ошибка")

    def _append_to_output(self, text):
        self.output_console.moveCursor(QTextCursor.MoveOperation.End)
        self.output_console.insertPlainText(text)
        self.output_console.ensureCursorVisible()

    def _read_run_stdout(self):
        data = _decode_process_output(
            self.run_process.readAllStandardOutput().data(), getattr(self, "run_output_encoding", None)
        )
        self._append_to_output(data)

    def _read_run_stderr(self):
        data = _decode_process_output(
            self.run_process.readAllStandardError().data(), getattr(self, "run_output_encoding", None)
        )
        if self.last_run_language == "Python":
            self._detect_missing_python_module(data)
        self._append_to_output(data)

    def _run_process_finished(self, exit_code, _exit_status):
        self.output_console.appendPlainText(f"\n\n■ Процесс завершён с кодом {exit_code}")
        if self.last_run_language == "Java":
            self.write_log(f"[Java] launch exit={exit_code}")
        self.status_pill.setText("готово" if exit_code == 0 else "сбой")
        self.statusBar().showMessage(f"Процесс завершён с кодом {exit_code}", 4000)
        if exit_code != 0 and self.last_run_language == "Python":
            QTimer.singleShot(0, self.handle_missing_python_module_after_run)

    def stop_run_process(self):
        if self.run_process and self.run_process.state() != QProcess.ProcessState.NotRunning:
            self.run_process.terminate()
            QTimer.singleShot(1200, lambda: self.run_process.kill() if self.run_process and self.run_process.state() != QProcess.ProcessState.NotRunning else None)
            self.output_console.appendPlainText("\n■ Процесс остановлен пользователем.")
            self.status_pill.setText("остановлено")
        elif self.task_manager.has_active_task():
            self.cancel_active_task()
        else:
            self.statusBar().showMessage("Нет запущенной программы", 2500)

    def send_run_stdin_text(self, text: str):
        text = str(text or "")
        if not text:
            return
        if self.run_process and self.run_process.state() != QProcess.ProcessState.NotRunning:
            self.run_process.write((text + "\n").encode("utf-8"))
        else:
            self.output_console.appendPlainText("Нет запущенной программы для ввода stdin.")

    def send_run_stdin(self):
        # Compatibility hook for older shortcuts/tests; inline console owns input.
        self.send_run_stdin_text(self.output_console.current_input())

    def start_terminal(self):
        if self.terminal_process and self.terminal_process.state() != QProcess.ProcessState.NotRunning:
            return

        self.terminal_process = QProcess(self)
        self.terminal_process.setWorkingDirectory(str(self.workspace_dir))
        if os.name == "nt":
            self.terminal_process.setProgram("cmd.exe")
            # cmd.exe uses an OEM code page by default on many Russian Windows
            # installations. Keep the persistent terminal in UTF-8 so its output
            # can be displayed without mojibake in the Qt console.
            self.terminal_process.setArguments(["/Q", "/K", "chcp 65001>nul"])
            shell_name = "cmd.exe"
        else:
            shell = os.environ.get("SHELL") or "/bin/bash"
            self.terminal_process.setProgram(shell)
            self.terminal_process.setArguments(["-i"])
            shell_name = shell
        env = QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONIOENCODING", "utf-8")
        self.terminal_process.setProcessEnvironment(env)
        self.terminal_process.readyReadStandardOutput.connect(self._read_terminal_stdout)
        self.terminal_process.readyReadStandardError.connect(self._read_terminal_stderr)
        self.terminal_process.finished.connect(self._terminal_finished)
        self.terminal_process.start()
        self.terminal_console.appendPlainText(f"Терминал {shell_name} запущен в папке:\n{self.workspace_dir}\n")

    def restart_terminal(self):
        if self.terminal_process and self.terminal_process.state() != QProcess.ProcessState.NotRunning:
            self.terminal_process.kill()
            self.terminal_process.waitForFinished(1000)
        self.terminal_console.clear()
        self.start_terminal()
        self.bottom_tabs.setCurrentIndex(1)

    def _append_to_terminal(self, text):
        self.terminal_console.moveCursor(QTextCursor.MoveOperation.End)
        self.terminal_console.insertPlainText(text)
        self.terminal_console.ensureCursorVisible()

    def _read_terminal_stdout(self):
        data = _decode_process_output(self.terminal_process.readAllStandardOutput().data())
        self._append_to_terminal(data)

    def _read_terminal_stderr(self):
        data = _decode_process_output(self.terminal_process.readAllStandardError().data())
        self._append_to_terminal(data)

    def _terminal_finished(self, exit_code, _exit_status):
        self.terminal_console.appendPlainText(f"\nТерминал завершён с кодом {exit_code}.")

    def send_terminal_command_text(self, command: str):
        command = str(command or "")
        if not command:
            return
        if not self.terminal_process or self.terminal_process.state() == QProcess.ProcessState.NotRunning:
            self.start_terminal()
        if self.terminal_process and self.terminal_process.state() != QProcess.ProcessState.NotRunning:
            self.terminal_process.write((command + "\n").encode("utf-8"))
        self.bottom_tabs.setCurrentIndex(1)

    def send_terminal_command(self):
        # Compatibility hook for older shortcuts/tests; inline console owns input.
        self.send_terminal_command_text(self.terminal_console.current_input())

    def _show_tools_drawer(self, index: int, title: str):
        if hasattr(self, "tools_stack"):
            self.tools_stack.setCurrentIndex(index)
        if hasattr(self, "tools_drawer"):
            self.tools_drawer.setVisible(True)
        if hasattr(self, "root_splitter"):
            sizes = self.root_splitter.sizes()
            if len(sizes) >= 3 and sizes[1] < 220:
                total = max(sum(sizes), 1260)
                self.root_splitter.setSizes([306, 420, max(520, total - 726)])
        if hasattr(self, "tools_drawer_title"):
            self.tools_drawer_title.setText(title)
        if hasattr(self, "btn_close_tools_drawer"):
            self.btn_close_tools_drawer.raise_()


    def open_enter_typer_template(self):
        self.current_language_name = "Python"
        if hasattr(self, "language_combo"):
            self.language_combo.blockSignals(True)
            self.language_combo.setCurrentText("Python")
            self.language_combo.blockSignals(False)
        editor = self.add_editor_tab(ENTER_TYPER_TEMPLATE, name="enter_typer_ru_en.py", language_name="Python")
        editor.document().setModified(True)
        QMessageBox.information(
            self,
            "Имитация ввода",
            "Шаблон открыт в новом Python-файле.\n\n"
            "Важно: скрипт имитирует нажатия клавиш. Используй его только в своих окнах и с понятной целью.\n"
            "Для запуска нажми F5 вручную.",
        )
        self.statusBar().showMessage("Открыт шаблон: Имитация ввода", 3000)

    def change_preset_wallpaper(self, name):
        if name not in ASTRA_WALLPAPERS:
            return
        self.preset_wallpaper_name = name
        self.custom_wallpaper_path = ""
        self.wallpaper_enabled = True
        self.update_wallpaper_label()
        self.apply_theme()
        self._save_settings()
        self.statusBar().showMessage(f"Выбраны обои Astra: {name}", 2500)

    def apply_astra_profile(self):
        self.current_theme_name = DEFAULT_THEME
        self.current_accent_name = DEFAULT_ACCENT
        self.global_font_name = DEFAULT_GLOBAL_FONT
        self.preset_wallpaper_name = DEFAULT_PRESET_WALLPAPER
        self.custom_wallpaper_path = ""
        self.wallpaper_all_windows = True
        self.disable_console_wallpaper = False
        self.wallpaper_dim_percent = 55
        self.wallpaper_blur_px = 18
        self.editor_bg_transparency_percent = 15
        self.console_bg_transparency_percent = 15
        self.settings_bg_transparency_percent = 15
        self.project_bg_transparency_percent = 15
        self.aux_bg_transparency_percent = 15
        self.editor_blur_percent = 18
        self.console_blur_percent = 18
        self.settings_blur_percent = 18
        self.project_blur_percent = 18
        self.logo_frame_blur_percent = 18
        self.logo_frame_transparency_percent = 42
        for combo, value in [(self.theme_combo, self.current_theme_name), (self.accent_combo, self.current_accent_name), (self.preset_wallpaper_combo, self.preset_wallpaper_name)]:
            combo.blockSignals(True)
            combo.setCurrentText(value)
            combo.blockSignals(False)
        self.global_font_combo.blockSignals(True)
        self.global_font_combo.setCurrentText(self.global_font_name)
        self.global_font_combo.blockSignals(False)
        self.wallpaper_all_toggle.blockSignals(True)
        self.wallpaper_all_toggle.setChecked(True)
        self.wallpaper_all_toggle.blockSignals(False)
        self.disable_console_wallpaper_toggle.blockSignals(True)
        self.disable_console_wallpaper_toggle.setChecked(False)
        self.disable_console_wallpaper_toggle.blockSignals(False)
        self.wallpaper_dim_slider.blockSignals(True)
        self.wallpaper_dim_slider.setValue(self.wallpaper_dim_percent)
        self.wallpaper_dim_slider.blockSignals(False)
        for slider, value in [
            (self.wallpaper_blur_slider, self.wallpaper_blur_px),
            (self.editor_blur_slider, self.editor_blur_percent),
            (self.console_blur_slider, self.console_blur_percent),
            (self.settings_blur_slider, self.settings_blur_percent),
            (self.project_blur_slider, self.project_blur_percent),
            (self.panel_transparency_slider, 15),
            (self.editor_transparency_slider, 15),
            (self.console_transparency_slider, 15),
            (self.settings_transparency_slider, 15),
            (self.project_transparency_slider, 15),
            (self.aux_transparency_slider, 15),
            (self.logo_frame_blur_slider, self.logo_frame_blur_percent),
            (self.logo_frame_transparency_slider, self.logo_frame_transparency_percent),
        ]:
            slider.blockSignals(True)
            slider.setValue(value)
            slider.blockSignals(False)
        self.update_wallpaper_effect_labels()
        self.update_wallpaper_label()
        self.apply_font_settings(reapply_theme=True)
        self._save_settings()
        self.statusBar().showMessage("Профиль Astra применён", 3000)

    def apply_angel404_profile(self):
        self.current_theme_name = ANGEL_404_THEME
        self.current_accent_name = ANGEL_404_ACCENT
        self.preset_wallpaper_name = ANGEL_404_WALLPAPER
        self.global_font_name = "Minecraft Rus"
        self.custom_wallpaper_path = ""
        self.wallpaper_enabled = True
        self.wallpaper_all_windows = True
        self.disable_console_wallpaper = False
        self.wallpaper_dim_percent = 28
        self.wallpaper_blur_px = 6
        self.editor_bg_transparency_percent = 24
        self.console_bg_transparency_percent = 24
        self.settings_bg_transparency_percent = 24
        self.project_bg_transparency_percent = 24
        self.aux_bg_transparency_percent = 24
        self.editor_blur_percent = 6
        self.console_blur_percent = 6
        self.settings_blur_percent = 6
        self.project_blur_percent = 6

        for combo, value in [
            (self.theme_combo, self.current_theme_name),
            (self.accent_combo, self.current_accent_name),
            (self.preset_wallpaper_combo, self.preset_wallpaper_name),
            (self.global_font_combo, self.global_font_name),
        ]:
            combo.blockSignals(True)
            combo.setCurrentText(value)
            combo.blockSignals(False)
        for toggle, checked in [
            (self.wallpaper_all_toggle, True),
            (self.disable_console_wallpaper_toggle, False),
        ]:
            toggle.blockSignals(True)
            toggle.setChecked(checked)
            toggle.blockSignals(False)
        for slider, value in [
            (self.wallpaper_dim_slider, self.wallpaper_dim_percent),
            (self.wallpaper_blur_slider, self.wallpaper_blur_px),
            (self.editor_blur_slider, self.editor_blur_percent),
            (self.console_blur_slider, self.console_blur_percent),
            (self.settings_blur_slider, self.settings_blur_percent),
            (self.project_blur_slider, self.project_blur_percent),
            (self.panel_transparency_slider, 24),
            (self.editor_transparency_slider, self.editor_bg_transparency_percent),
            (self.console_transparency_slider, self.console_bg_transparency_percent),
            (self.settings_transparency_slider, self.settings_bg_transparency_percent),
            (self.project_transparency_slider, self.project_bg_transparency_percent),
            (self.aux_transparency_slider, self.aux_bg_transparency_percent),
        ]:
            slider.blockSignals(True)
            slider.setValue(value)
            slider.blockSignals(False)
        self.update_wallpaper_effect_labels()
        self.update_wallpaper_label()
        self.apply_font_settings(reapply_theme=True)
        self._save_settings()
        self.statusBar().showMessage("Профиль Angel 404 применён", 3000)

    def toggle_wallpaper_all_windows(self, enabled):
        self.wallpaper_all_windows = bool(enabled)
        self.apply_theme()
        self._save_settings()

    def toggle_disable_console_wallpaper(self, enabled):
        self.disable_console_wallpaper = bool(enabled)
        self.apply_theme()
        self._save_settings()

    def change_wallpaper_dim(self, value):
        self.wallpaper_dim_percent = int(value)
        self.update_wallpaper_effect_labels()
        self.apply_theme()
        self._save_settings()

    def change_wallpaper_blur(self, value):
        self.wallpaper_blur_px = int(value)
        self.editor_blur_percent = int(value)
        self.console_blur_percent = int(value)
        self.settings_blur_percent = int(value)
        self.project_blur_percent = int(value)
        for slider in [self.editor_blur_slider, self.console_blur_slider, self.settings_blur_slider, self.project_blur_slider]:
            slider.blockSignals(True)
            slider.setValue(int(value))
            slider.blockSignals(False)
        self.update_wallpaper_effect_labels()
        self.apply_theme()
        self._save_settings()

    def change_panel_transparency(self, target: str, value: int):
        value = int(value)
        if target == "editor":
            self.editor_bg_transparency_percent = value
        elif target == "console":
            self.console_bg_transparency_percent = value
        elif target == "settings":
            self.settings_bg_transparency_percent = value
        elif target == "project":
            self.project_bg_transparency_percent = value
        elif target == "aux":
            self.aux_bg_transparency_percent = value
        self.update_wallpaper_effect_labels()
        self.apply_theme()
        self._save_settings()

    def change_secondary_blur(self, target: str, value: int):
        value = int(value)
        if target == "editor":
            self.editor_blur_percent = value
        elif target == "console":
            self.console_blur_percent = value
        elif target == "settings":
            self.settings_blur_percent = value
        elif target == "project":
            self.project_blur_percent = value
        self.update_wallpaper_effect_labels()
        self.apply_theme()
        self._save_settings()

    def toggle_save_window_sizes(self, enabled):
        self.save_window_sizes_enabled = bool(enabled)
        self._save_settings()

    def reset_transparency_settings(self):
        values = {
            "editor": 15,
            "console": 15,
            "settings": 15,
            "project": 15,
            "aux": 15,
        }
        self.editor_bg_transparency_percent = values["editor"]
        self.console_bg_transparency_percent = values["console"]
        self.settings_bg_transparency_percent = values["settings"]
        self.project_bg_transparency_percent = values["project"]
        self.aux_bg_transparency_percent = values["aux"]
        for slider, value in [
            (self.editor_transparency_slider, values["editor"]),
            (self.console_transparency_slider, values["console"]),
            (self.settings_transparency_slider, values["settings"]),
            (self.project_transparency_slider, values["project"]),
            (self.aux_transparency_slider, values["aux"]),
            (self.panel_transparency_slider, 15),
        ]:
            slider.blockSignals(True); slider.setValue(value); slider.blockSignals(False)
        self.update_wallpaper_effect_labels(); self.apply_theme(); self._save_settings()

    def reset_blur_settings(self):
        self.wallpaper_blur_px = 25
        self.editor_blur_percent = 25
        self.console_blur_percent = 25
        self.settings_blur_percent = 25
        self.project_blur_percent = 25
        self.logo_frame_blur_percent = 18
        for slider, value in [(self.wallpaper_blur_slider, 25), (self.editor_blur_slider, 25), (self.console_blur_slider, 25), (self.settings_blur_slider, 25), (self.project_blur_slider, 25), (self.logo_frame_blur_slider, 18)]:
            slider.blockSignals(True); slider.setValue(value); slider.blockSignals(False)
        self.update_wallpaper_effect_labels(); self.apply_theme(); self._save_settings()

    def reset_window_sizes(self):
        self.saved_root_splitter_sizes = []
        self.saved_main_splitter_sizes = []
        self.saved_vertical_splitter_sizes = []
        if hasattr(self, "root_splitter"):
            self.root_splitter.setSizes([306, 390 if self.tools_drawer.isVisible() else 0, 1040])
        if hasattr(self, "main_splitter"):
            self.main_splitter.setSizes([260, 940])
        if hasattr(self, "vertical_splitter"):
            self.vertical_splitter.setSizes([570, 250])
        self._save_settings()

    def reset_appearance_defaults(self):
        self.apply_astra_profile()

    def toggle_python_auto_install(self, enabled):
        self.python_auto_install_enabled = bool(enabled)
        self._save_settings()

    def toggle_python_install_always_ask(self, enabled):
        self.python_install_always_ask = bool(enabled)
        self._save_settings()

    def toggle_python_unknown_auto_install(self, enabled):
        self.python_unknown_auto_install_enabled = bool(enabled)
        self._save_settings()

    def toggle_open_install_log(self, enabled):
        self.open_install_log_enabled = bool(enabled)
        self._save_settings()

    def change_exe_build_mode(self, name):
        if name in ("Консольное приложение", "Оконное приложение"):
            self.exe_build_mode = name
            self._save_settings()

    def toggle_cpp_using_namespace_std(self, enabled):
        self.cpp_using_namespace_std_enabled = bool(enabled)
        self._save_settings()

    def _cpp_template_for_settings(self) -> str:
        text = CPP_TEMPLATE
        if self.cpp_using_namespace_std_enabled:
            return text
        text = text.replace("\nusing namespace std;\n", "\n")
        replacements = {
            "string name;": "std::string name;",
            "cout <<": "std::cout <<",
            "getline(cin, name);": "std::getline(std::cin, name);",
            " << endl": " << std::endl",
        }
        for old, new in replacements.items():
            text = text.replace(old, new)
        return text

    def _python_project_root(self, source_path: Path | None = None) -> Path:
        if source_path:
            return self._project_root_for_source(Path(source_path))
        try:
            return Path(self.project_main_folder).resolve()
        except OSError:
            return Path(self.project_main_folder)

    def _resolved_project_python_override(self, root: Path | None = None) -> Path | None:
        # A stored relative interpreter path is relative to the Astra project's main
        # folder (where astral.project.json lives), not to whichever nested source
        # folder happens to be active.
        override = (self.project_python_interpreter or "").strip()
        if not override:
            return None
        candidate = Path(override)
        if not candidate.is_absolute():
            candidate = Path(self.project_main_folder) / candidate
        return candidate if candidate.is_file() else None

    def _active_python_command(self, source_path: Path | None = None) -> tuple[str | None, list[str]]:
        """Resolve explicit/project Python before falling back to the global interpreter."""
        root = self._python_project_root(source_path)
        override = self._resolved_project_python_override(root)
        if override:
            return str(override), []
        info = detect_project_environment(root)
        if info.python_executable and info.python_executable.is_file():
            return str(info.python_executable), []
        return python_command()

    def _refresh_python_environment_status(self):
        if not hasattr(self, "python_env_label"):
            return
        root = self._python_project_root(self.current_editor().file_path if self.current_editor() else None)
        info = detect_project_environment(root)
        configured_override = (self.project_python_interpreter or "").strip()
        override_path = self._resolved_project_python_override(root)
        if override_path:
            env_text = f"Выбранный Python проекта: {override_path}"
        elif configured_override:
            env_text = f"⚠ Выбранный Python проекта недоступен: {configured_override}"
        elif info.python_executable:
            env_text = f"Проектное окружение: {info.source} — {info.python_executable}"
        else:
            global_python, global_args = python_command()
            if global_python:
                suffix = " " + " ".join(global_args) if global_args else ""
                env_text = f"Глобальный Python: {global_python}{suffix}"
            else:
                env_text = "Python не найден"
        deps = ", ".join(path.name for path in info.dependency_files) or "файлы зависимостей не найдены"
        uv_text = f"uv: {info.uv_executable}" if info.uv_executable else "uv: не найден (будет использоваться pip/venv)"
        self.python_env_label.setText(f"{env_text}\nПроект: {root}\nЗависимости: {deps}\n{uv_text}")

    def _project_interpreter_for_storage(self, path: Path) -> str:
        root = self._python_project_root()
        try:
            return str(path.resolve().relative_to(root.resolve()))
        except (OSError, ValueError):
            return str(path)

    def select_project_python_interpreter(self):
        root = self._python_project_root()
        start = str(root)
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Выбрать Python-интерпретатор проекта",
            start,
            "Python (python.exe python python3);;All files (*.*)",
        )
        if not file_name:
            return
        candidate = Path(file_name)
        ok, _code, stdout, stderr = self._run_blocking(str(candidate), ["-c", "import sys; print(sys.executable); print(sys.version.split()[0])"], root, timeout_ms=6000)
        if not ok:
            QMessageBox.warning(self, "Python environment", "Выбранный файл не удалось запустить как Python.\n" + (stderr or stdout))
            return
        self.project_python_interpreter = self._project_interpreter_for_storage(candidate)
        self._save_current_project_state()
        self._refresh_python_environment_status()
        self.statusBar().showMessage("Python-интерпретатор проекта сохранён", 3000)

    def create_project_python_environment(self):
        root = self._python_project_root()
        if not root.exists() or not root.is_dir():
            QMessageBox.warning(self, "Python environment", "Папка проекта недоступна.")
            return
        info = detect_project_environment(root)
        if info.python_executable:
            QMessageBox.information(self, "Python environment", f"Проектное окружение уже найдено:\n{info.python_executable}")
            self._refresh_python_environment_status()
            return
        if not can_write_to_directory(root):
            QMessageBox.warning(self, "Python environment", self._permission_help_text(root))
            return
        override = self._resolved_project_python_override(root)
        if override:
            base_python, base_args = str(override), []
        else:
            base_python, base_args = python_command()
        uv = info.uv_executable
        if not base_python and not uv:
            QMessageBox.warning(self, "Python environment", "Не найден ни Python, ни uv. Установи Python через вкладку «Установщик».")
            return
        env_dir = root / ".venv"
        if uv:
            args = ["venv", "--seed"]
            if base_python:
                # uv accepts an executable path as --python request.
                args += ["--python", str(base_python)]
            args += [str(env_dir)]
            program = uv
            description = "uv venv"
        else:
            program = base_python
            args = [*base_args, "-m", "venv", str(env_dir)]
            description = "python -m venv"
        self.bottom_tabs.setCurrentIndex(0)
        self.output_console.appendPlainText(f"\n▶ Создание окружения проекта через {description}:\n{self._safe_command_preview(program, args)}\n")
        self._start_process_task(
            "python_env_create",
            "Создаётся Python .venv…",
            program,
            args,
            root,
            {"mode": "python_env_create", "root": str(root), "env_dir": str(env_dir), "target": "output", "indeterminate": True},
            10,
            100,
            True,
        )

    def _project_dependency_install_command(self) -> tuple[str | None, list[str], str]:
        root = self._python_project_root()
        info = detect_project_environment(root)
        override = self._resolved_project_python_override(root)
        python_exe, python_args = self._active_python_command()
        files = {path.name.lower(): path for path in info.dependency_files}
        requirements = next((path for path in info.dependency_files if path.name.lower() == "requirements.txt"), None)
        pyproject = files.get("pyproject.toml")
        uv_lock = files.get("uv.lock")
        # uv sync intentionally owns the project's .venv. Respect a manually selected
        # interpreter by using uv's pip-compatible mode instead of silently switching envs.
        if info.uv_executable and pyproject and uv_lock and override is None:
            return info.uv_executable, ["sync", "--project", str(root)], "uv sync"
        if info.uv_executable and python_exe and requirements:
            return info.uv_executable, ["pip", "install", "--python", str(python_exe), "-r", str(requirements)], "uv pip install -r requirements.txt"
        if info.uv_executable and python_exe and pyproject:
            return info.uv_executable, ["pip", "install", "--python", str(python_exe), "-r", str(pyproject)], "uv pip install -r pyproject.toml"
        if python_exe and requirements:
            return python_exe, [*python_args, "-m", "pip", "install", "-r", str(requirements)], "pip install -r requirements.txt"
        if python_exe and pyproject:
            return python_exe, [*python_args, "-m", "pip", "install", "-e", str(root)], "pip install -e ."
        return None, [], ""

    def install_project_python_dependencies(self):
        root = self._python_project_root()
        info = detect_project_environment(root)
        configured_override = (self.project_python_interpreter or "").strip()
        valid_override = self._resolved_project_python_override(root)
        if configured_override and valid_override is None:
            QMessageBox.warning(
                self,
                "Python dependencies",
                "Сохранённый Python-интерпретатор проекта больше недоступен. Выбери новый интерпретатор или создай .venv, чтобы зависимости не попали в глобальный Python.",
            )
            return
        if not info.python_executable and valid_override is None:
            answer = QMessageBox.question(
                self,
                "Python dependencies",
                "У проекта ещё нет собственного Python-окружения. Создать .venv перед установкой зависимостей?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if answer == QMessageBox.StandardButton.Yes:
                self.create_project_python_environment()
            return
        program, args, label = self._project_dependency_install_command()
        if not program:
            QMessageBox.information(self, "Python dependencies", "Не найден поддерживаемый файл зависимостей. Добавь requirements.txt или pyproject.toml.")
            return
        answer = QMessageBox.question(
            self,
            "Python dependencies",
            f"Установить зависимости проекта?\n\nПапка: {root}\nМетод: {label}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.bottom_tabs.setCurrentIndex(0)
        self.output_console.appendPlainText(f"\n▶ Установка зависимостей проекта:\n{self._safe_command_preview(program, args)}\n")
        self._start_process_task(
            "python_project_dependencies",
            "Устанавливаются зависимости Python-проекта…",
            program,
            args,
            root,
            {"mode": "python_project_dependencies", "root": str(root), "target": "output", "indeterminate": True},
            10,
            100,
            True,
        )

    def update_project_pip(self):
        root = self._python_project_root()
        info = detect_project_environment(root)
        configured_override = (self.project_python_interpreter or "").strip()
        valid_override = self._resolved_project_python_override(root)
        if configured_override and valid_override is None:
            QMessageBox.warning(
                self,
                "Python environment",
                "Сохранённый Python-интерпретатор проекта недоступен. Обновление pip остановлено, чтобы не изменить глобальный Python.",
            )
            return
        if not info.python_executable and valid_override is None:
            answer = QMessageBox.question(
                self,
                "Python environment",
                "У проекта нет собственного Python-окружения. Создать .venv вместо обновления глобального pip?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if answer == QMessageBox.StandardButton.Yes:
                self.create_project_python_environment()
            return
        python_exe, python_args = self._active_python_command()
        if not python_exe:
            QMessageBox.warning(self, "Python environment", "Python не найден.")
            return
        args = [*python_args, "-m", "pip", "install", "--upgrade", "pip"]
        self.output_console.appendPlainText(f"\n▶ Обновление pip:\n{self._safe_command_preview(python_exe, args)}\n")
        self._start_process_task(
            "python_update_pip",
            "Обновляется pip…",
            python_exe,
            args,
            root,
            {"mode": "python_update_pip", "target": "output", "indeterminate": True},
            10,
            100,
            True,
        )

    def export_project_requirements(self):
        root = self._python_project_root()
        info = detect_project_environment(root)
        configured_override = (self.project_python_interpreter or "").strip()
        valid_override = self._resolved_project_python_override(root)
        if configured_override and valid_override is None:
            QMessageBox.warning(self, "Python environment", "Сохранённый Python-интерпретатор проекта недоступен. Экспорт остановлен, чтобы случайно не выгрузить глобальное окружение.")
            return
        if not info.python_executable and valid_override is None:
            QMessageBox.information(self, "Python environment", "Экспорт requirements.txt разрешён только из проектного .venv/venv или явно выбранного интерпретатора, чтобы случайно не выгрузить глобальное окружение.")
            return
        python_exe, python_args = self._active_python_command()
        if not python_exe:
            QMessageBox.warning(self, "Python environment", "Python не найден.")
            return
        if info.uv_executable:
            program = info.uv_executable
            args = ["pip", "freeze", "--python", str(python_exe)]
        else:
            program = python_exe
            args = [*python_args, "-m", "pip", "freeze"]
        ok, _code, stdout, stderr = self._run_blocking(program, args, root, timeout_ms=15000)
        if not ok:
            QMessageBox.warning(self, "Python environment", "Не удалось получить список пакетов.\n" + (stderr or stdout))
            return
        target = root / "requirements.txt"
        if target.exists():
            answer = QMessageBox.question(self, "requirements.txt", "requirements.txt уже существует. Перезаписать его текущим состоянием окружения?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
            if answer != QMessageBox.StandardButton.Yes:
                return
        try:
            target.write_text(stdout.strip() + ("\n" if stdout.strip() else ""), encoding="utf-8")
        except OSError as exc:
            QMessageBox.critical(self, "requirements.txt", f"Не удалось сохранить файл:\n{exc}")
            return
        self.refresh_project_tree()
        self._refresh_python_environment_status()
        self.statusBar().showMessage(f"requirements.txt сохранён: {target}", 3500)

    def _python_package_manager_command(self, pip_args: list[str], source_path: Path | None = None) -> tuple[str | None, list[str]]:
        """Prefer uv pip for a project environment; fall back to python -m pip."""
        root = self._python_project_root(source_path)
        info = detect_project_environment(root)
        python_exe, python_args = self._active_python_command(source_path)
        if info.uv_executable and python_exe and pip_args:
            action, *rest = pip_args
            if action in {"install", "uninstall", "freeze", "list", "show", "check"}:
                return info.uv_executable, ["pip", action, "--python", str(python_exe), *rest]
        if python_exe:
            return python_exe, [*python_args, "-m", "pip", *pip_args]
        return None, []

    def _python_package_record(self, module_or_package: str) -> dict | None:
        if is_standard_module(module_or_package):
            return None
        return package_record(module_or_package)

    def _python_package_version(self, package_name: str) -> str:
        py_program, py_args = self._active_python_command()
        if not py_program:
            return "нет Python"
        code = (
            "import importlib.metadata as m\n"
            "import sys\n"
            f"name = {package_name!r}\n"
            "try:\n"
            "    print(m.version(name))\n"
            "except Exception:\n"
            "    sys.exit(1)\n"
        )
        ok, _exit, stdout, _stderr = self._run_blocking(py_program, [*py_args, "-c", code], self.workspace_dir, timeout_ms=4500)
        return stdout.strip() if ok and stdout.strip() else "не установлена"

    def _python_import_available(self, import_name: str) -> bool:
        if is_standard_module(import_name):
            return True
        py_program, py_args = self._active_python_command()
        if not py_program:
            return False
        module = (import_name or "").split(".", 1)[0].strip()
        if not module:
            return False
        code = (
            "import importlib.util, sys\n"
            "module = sys.argv[1]\n"
            "sys.exit(0 if importlib.util.find_spec(module) is not None else 1)\n"
        )
        ok, _exit, _stdout, _stderr = self._run_blocking(py_program, [*py_args, "-c", code, module], self.workspace_dir, timeout_ms=4500)
        return ok

    def _python_import_status_map(self, import_names: list[str]) -> dict[str, bool]:
        modules = []
        seen = set()
        for name in import_names:
            module = (name or "").split(".", 1)[0].strip()
            if not module or module in seen:
                continue
            seen.add(module)
            modules.append(module)
        if not modules:
            return {}
        py_program, py_args = self._active_python_command()
        if not py_program:
            return {module: False for module in modules}
        code = (
            "import importlib.util, json, sys\n"
            "modules = json.loads(sys.argv[1])\n"
            "print(json.dumps({m: importlib.util.find_spec(m) is not None for m in modules}, ensure_ascii=False))\n"
        )
        ok, _exit, stdout, _stderr = self._run_blocking(
            py_program, [*py_args, "-c", code, json.dumps(modules, ensure_ascii=False)], self.workspace_dir, timeout_ms=6000
        )
        if not ok:
            return {module: False for module in modules}
        try:
            data = json.loads(stdout.strip() or "{}")
            return {module: bool(data.get(module)) for module in modules}
        except Exception:
            return {module: False for module in modules}

    def _local_python_module_exists(self, module: str, source_path: Path | None = None) -> bool:
        module = (module or "").split(".", 1)[0].strip()
        if not module:
            return False
        roots: list[Path] = []
        if source_path:
            roots.append(Path(source_path).parent)
        roots.append(Path(self.project_main_folder))
        for item in self.attached_project_folders:
            if isinstance(item, dict) and item.get("path"):
                roots.append(Path(item["path"]))
        seen = set()
        for root in roots:
            try:
                resolved = root.resolve()
            except OSError:
                resolved = root
            key = str(resolved).lower() if os.name == "nt" else str(resolved)
            if key in seen:
                continue
            seen.add(key)
            if (root / f"{module}.py").is_file() or (root / module).is_dir():
                return True
        return False

    def _missing_python_imports_from_code(self, source_code: str, source_path: Path | None = None) -> list[str]:
        modules = []
        for module in extract_python_imports(source_code):
            if not module or module.startswith("_"):
                continue
            if module in keyword.kwlist or is_standard_module(module):
                continue
            if self._local_python_module_exists(module, source_path):
                continue
            modules.append(module)
        status = self._python_import_status_map(modules)
        return [module for module in modules if not status.get(module, False)]

    def _ask_about_missing_python_module(self, module_name: str, rerun_after: bool = True) -> bool:
        module = (module_name or "").split(".", 1)[0].strip()
        if not module or is_standard_module(module):
            return True
        record = self._python_package_record(module)
        if not record:
            guessed = {"import": module, "package": module, "display_name": module, "description": "Автоматически подобран по имени import", "safe": True}
            if self.python_unknown_auto_install_enabled:
                self.output_console.appendPlainText(
                    f"⚠ Неизвестный import {module}: включён PyPI fallback, Astra попробует пакет с тем же именем."
                )
                self._run_pip_for_record(guessed, ["install", module], rerun_after=rerun_after)
                return False
            box = QMessageBox(self)
            box.setWindowTitle("Python-библиотеки")
            box.setText(f'Модуль "{module}" не найден во встроенном каталоге Astra.')
            box.setInformativeText(
                f'Astra может попробовать установить пакет PyPI с таким же именем: "{module}". '
                "Это не всегда верное соответствие import→distribution, поэтому для неизвестных пакетов требуется подтверждение, "
                "если автоматический fallback не включён в настройках."
            )
            install_btn = box.addButton(f"pip install {module}", QMessageBox.ButtonRole.AcceptRole)
            libs_btn = box.addButton("Открыть менеджер PyPI", QMessageBox.ButtonRole.ActionRole)
            box.addButton("Не устанавливать", QMessageBox.ButtonRole.RejectRole)
            box.exec()
            clicked = box.clickedButton()
            if clicked == install_btn:
                self._run_pip_for_record(guessed, ["install", module], rerun_after=rerun_after)
            elif clicked == libs_btn:
                self.open_python_libs_page()
                if hasattr(self, "custom_pip_edit"):
                    self.custom_pip_edit.setText(module)
                    self.custom_pip_edit.setFocus()
            return False

        if record.get("safe", True) and not self.python_install_always_ask:
            self._run_pip_for_record(record, ["install", record["package"]], rerun_after=rerun_after)
            return False

        box = QMessageBox(self)
        box.setWindowTitle("Python-библиотеки")
        box.setText(f'Модуль "{module}" не найден.\nДля него используется пакет pip: "{record["package"]}".')
        info_parts = [record.get("description", "")]
        if record.get("warning"):
            info_parts.append(record["warning"])
        if not record.get("safe", True):
            info_parts.append("Пакет отмечен как экспериментальный/тяжёлый и не устанавливается автоматически.")
        box.setInformativeText("\n\n".join(part for part in info_parts if part))
        install_btn = box.addButton("Установить", QMessageBox.ButtonRole.AcceptRole)
        details_btn = box.addButton("Подробнее", QMessageBox.ButtonRole.ActionRole)
        box.addButton("Не сейчас", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        clicked = box.clickedButton()
        if clicked == details_btn:
            self.open_python_libs_page()
            query = module
            if hasattr(self, "libs_search"):
                self.libs_search.setText(query)
            return False
        if clicked != install_btn:
            return False
        if not record.get("safe", True):
            QMessageBox.warning(self, "Python-библиотеки", "Этот пакет не входит в список автоматической установки. Установи его вручную, если он точно нужен.")
            return False
        self._run_pip_for_record(record, ["install", record["package"]], rerun_after=rerun_after)
        return False

    def _ensure_python_imports_before_run(self, source_code: str, source_path: Path | None = None) -> bool:
        if not self.python_auto_install_enabled:
            return True
        missing = self._missing_python_imports_from_code(source_code, source_path)
        missing = [m for m in missing if m.lower() not in self.ignored_missing_modules]
        if not missing:
            return True

        candidates: list[dict] = []
        blocked: list[str] = []
        for module in missing:
            record = self._python_package_record(module)
            if record is None:
                if self.python_unknown_auto_install_enabled or self.python_install_always_ask:
                    candidates.append({
                        "import": module,
                        "package": module,
                        "display_name": module,
                        "description": "PyPI fallback по имени import",
                        "safe": True,
                    })
                else:
                    blocked.append(module)
                continue
            if record.get("safe", True):
                candidates.append(record)
            else:
                blocked.append(module)

        if candidates:
            unique: list[dict] = []
            seen_packages: set[str] = set()
            for record in candidates:
                package = str(record.get("package") or "").strip()
                if package and package not in seen_packages:
                    seen_packages.add(package)
                    unique.append(record)
            candidates = unique

            if self.python_install_always_ask:
                mapping_lines = [f"{record.get('import')}  →  {record.get('package')}" for record in candidates]
                extra = ""
                if blocked:
                    extra = "\n\nОтдельного подтверждения всё ещё потребуют: " + ", ".join(blocked)
                answer = QMessageBox.question(
                    self,
                    "Python-библиотеки",
                    "Перед запуском не хватает библиотек:\n\n" + "\n".join(mapping_lines)
                    + extra
                    + "\n\nУстановить доступные пакеты одним действием через активное Python-окружение?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.Yes,
                )
                if answer != QMessageBox.StandardButton.Yes:
                    return False
            self.output_console.appendPlainText(
                "\n⚠ Перед запуском Astra установит отсутствующие Python-зависимости: "
                + ", ".join(str(record.get("package")) for record in candidates)
            )
            self._run_pip_for_records(candidates, rerun_after=True)
            return False

        module = missing[0]
        self.output_console.appendPlainText(
            f"\n⚠ Перед запуском найден отсутствующий модуль: {module}. Astra предложит способ установки.\n"
        )
        self._ask_about_missing_python_module(module, rerun_after=True)
        return False

    def populate_library_table(self):
        if not hasattr(self, "libs_table"):
            return
        query = self.libs_search.text().strip().lower() if hasattr(self, "libs_search") else ""
        category = self.libs_category_combo.currentText() if hasattr(self, "libs_category_combo") else "Все"
        if not hasattr(self, "library_status_cache"):
            self.library_status_cache = {}
        rows = []
        for item in PYTHON_LIBRARY_REGISTRY:
            haystack = " ".join([
                item.get("display_name", ""),
                item["import"],
                item["package"],
                item["category"],
                item["description"],
            ]).lower()
            if query and query not in haystack:
                continue
            if category != "Все" and item["category"] != category:
                continue
            rows.append(item)
        self.libs_table.setRowCount(len(rows))
        for row, item in enumerate(rows):
            cache_key = item["import"]
            status = self.library_status_cache.get(cache_key, "не проверено")
            warning = item.get("warning", "") or ("Тяжёлый пакет" if item.get("heavy") else "")
            values = [item["import"], item["package"], item["category"], status, item["description"], warning]
            for column, value in enumerate(values):
                cell = QTableWidgetItem(str(value))
                cell.setData(Qt.ItemDataRole.UserRole, item)
                self.libs_table.setItem(row, column, cell)

    def check_visible_library_statuses(self):
        if not hasattr(self, "libs_table"):
            return
        records = []
        for row in range(self.libs_table.rowCount()):
            item = self.libs_table.item(row, 0)
            record = item.data(Qt.ItemDataRole.UserRole) if item else None
            if record:
                records.append(record)
        status = self._python_import_status_map([record["import"] for record in records])
        for record in records:
            self.library_status_cache[record["import"]] = "установлена" if status.get(record["import"], False) else "не установлена"
        self.populate_library_table()
        self.statusBar().showMessage("Статусы библиотек обновлены", 2200)

    def selected_library_record(self) -> dict | None:
        if not hasattr(self, "libs_table"):
            return None
        row = self.libs_table.currentRow()
        if row < 0:
            return None
        item = self.libs_table.item(row, 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _confirm_package_install(self, record: dict, action: str = "install") -> bool:
        package = record["package"]
        warning = record.get("warning") or ""
        verb = {"install": "установить", "update": "обновить", "uninstall": "удалить"}.get(action, action)
        msg = f"Astra Studio собирается {verb} пакет:\n\n{package}\n\nКоманда будет выполнена через активный Python: python -m pip."
        if warning:
            msg += f"\n\nПредупреждение: {warning}"
        answer = QMessageBox.question(self, "Python-библиотеки", msg, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        return answer == QMessageBox.StandardButton.Yes

    def _run_pip_for_record(self, record: dict, args: list[str], rerun_after: bool = False):
        program, command_args = self._python_package_manager_command(args)
        if not program:
            QMessageBox.warning(self, "Python-библиотеки", "Python/менеджер пакетов не найден. Открой «Установщик» и проверь Python.")
            return False
        if self.task_manager.has_active_task():
            self.output_console.appendPlainText("\n⚠ Другая операция уже выполняется. Заверши её или нажми «Отмена».")
            return False
        command_preview = self._safe_command_preview(program, command_args)
        self.bottom_tabs.setCurrentIndex(0)
        self.output_console.appendPlainText(f"\n▶ Python libraries: {command_preview}\n")
        self.output_console.appendPlainText("Этапы: подготовка → менеджер пакетов → проверка import → завершение\n")
        self.write_log(f"Python package command: {command_preview}")
        if self.open_install_log_enabled:
            self.bottom_tabs.setCurrentIndex(0)
        self._start_process_task(
            "pip_" + record["package"].replace("-", "_").replace(".", "_"),
            "Идёт установка/обновление Python-библиотеки…",
            program,
            command_args,
            self._python_project_root(),
            {"mode": "pip", "package": record["package"], "import_name": record.get("import"), "rerun_after": rerun_after, "indeterminate": True},
            10,
            100,
            True,
        )
        return None

    def _run_pip_for_records(self, records: list[dict], rerun_after: bool = False):
        safe_records = [record for record in records if record and record.get("safe", True)]
        if not safe_records:
            QMessageBox.information(self, "Python-библиотеки", "В выбранном наборе нет библиотек, разрешённых для автоустановки.")
            return False
        if self.task_manager.has_active_task():
            self.output_console.appendPlainText("\n⚠ Другая операция уже выполняется. Заверши её или нажми «Отмена».")
            return False
        packages = []
        for record in safe_records:
            package = record["package"]
            if package not in packages:
                packages.append(package)
        program, command_args = self._python_package_manager_command(["install", *packages])
        if not program:
            QMessageBox.warning(self, "Python-библиотеки", "Python/менеджер пакетов не найден. Открой «Установщик» и проверь Python.")
            return False
        command_preview = self._safe_command_preview(program, command_args)
        self.bottom_tabs.setCurrentIndex(0)
        self.output_console.appendPlainText(f"\n▶ Python bundle install: {command_preview}\n")
        self.output_console.appendPlainText("Этапы: подготовка → менеджер пакетов → проверка import → завершение\n")
        self.write_log(f"Python bundle command: {command_preview}")
        self._start_process_task(
            "pip_bundle_" + str(abs(hash(tuple(packages))))[:8],
            "Идёт установка набора Python-библиотек…",
            program,
            command_args,
            self._python_project_root(),
            {
                "mode": "pip",
                "package": ", ".join(packages),
                "import_names": [record.get("import") for record in safe_records],
                "rerun_after": rerun_after,
                "indeterminate": True,
            },
            10,
            100,
            True,
        )
        return None

    def install_selected_library_bundle(self):
        if not hasattr(self, "libs_bundle_combo"):
            return
        bundle_name = self.libs_bundle_combo.currentText()
        if not bundle_name or bundle_name == "Выбрать набор...":
            QMessageBox.information(self, "Python-библиотеки", "Выбери набор библиотек.")
            return
        records = records_for_bundle(bundle_name)
        if not records:
            QMessageBox.information(self, "Python-библиотеки", "Набор пуст или не найден.")
            return
        packages = [record["package"] for record in records]
        large = [record["display_name"] for record in records if record.get("size") == "large" or record.get("heavy")]
        msg = "Astra Studio установит набор:\n\n" + bundle_name + "\n\nПакеты pip:\n" + "\n".join(packages)
        if large:
            msg += "\n\nПредупреждение: некоторые библиотеки крупные и могут устанавливаться несколько минут:\n" + "\n".join(large)
        answer = QMessageBox.question(self, "Python-библиотеки", msg, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._run_pip_for_records(records)

    def install_arbitrary_pypi_requirement(self, upgrade: bool = False):
        if not hasattr(self, "custom_pip_edit"):
            return
        requirement = self.custom_pip_edit.text().strip()
        if not requirement:
            QMessageBox.information(self, "PyPI", "Введите имя пакета, например: httpx или rich>=13.")
            return
        if len(requirement) > 180 or any(ch in requirement for ch in ("/", "\\", "@", ";", "\n", "\r", "\t", " ")):
            QMessageBox.warning(
                self,
                "PyPI",
                "Для безопасности здесь поддерживаются имена/версии PyPI без URL, путей и пробелов. "
                "Примеры: requests, rich>=13, fastapi[standard].",
            )
            return
        if not re.match(r"^[A-Za-z0-9][A-Za-z0-9_.-]*(?:\[[A-Za-z0-9_,.-]+\])?(?:[<>=!~].+)?$", requirement):
            QMessageBox.warning(self, "PyPI", "Не удалось распознать безопасную спецификацию пакета PyPI.")
            return
        action = "обновит" if upgrade else "установит"
        answer = QMessageBox.question(
            self,
            "PyPI",
            f"Astra {action} пакет через активное окружение проекта:\n\n{requirement}\n\nПродолжить?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        package_name = re.split(r"[<>=!~\[]", requirement, 1)[0]
        record = {"import": package_name, "package": requirement, "display_name": requirement, "safe": True}
        args = ["install"]
        if upgrade:
            args.append("--upgrade")
        args.append(requirement)
        self._run_pip_for_record(record, args, rerun_after=False)

    def library_action(self, action: str):
        record = self.selected_library_record()
        if not record:
            QMessageBox.information(self, "Библиотеки Python", "Выбери библиотеку в таблице.")
            return
        package = record["package"]
        if action == "copy":
            program, args = self._python_package_manager_command(["install", package])
            command = self._safe_command_preview(program, args) if program else f"python -m pip install {package}"
            QApplication.clipboard().setText(command)
            self.statusBar().showMessage("Команда установки скопирована", 2200)
            return
        if action == "pypi":
            QDesktopServices.openUrl(QUrl(f"https://pypi.org/project/{package}/"))
            return
        if action == "install":
            if self._confirm_package_install(record, "install"):
                self._run_pip_for_record(record, ["install", package])
            return
        if action == "update":
            if self._confirm_package_install(record, "update"):
                self._run_pip_for_record(record, ["install", "--upgrade", package])
            return
        if action == "uninstall":
            if self._confirm_package_install(record, "uninstall"):
                self._run_pip_for_record(record, ["uninstall", "-y", package])

    def install_missing_python_module(self, module_name: str) -> bool:
        return self._ask_about_missing_python_module(module_name, rerun_after=True)

    def ensure_python_packages_for_enter_typer(self) -> bool:
        required = ["pynput", "pyperclip"]
        missing = [name for name in required if not self._python_import_available(name)]
        if not missing:
            return True
        answer = QMessageBox.question(
            self,
            "Зависимости шаблона",
            "Для шаблона «Имитация ввода» нужны библиотеки:\n\n" + "\n".join(missing) + "\n\nУстановить их через активный Python? После установки нажми запуск ещё раз.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return False
        records = [self._python_package_record(name) for name in missing]
        records = [record for record in records if record]
        if records:
            self._run_pip_for_records(records)
        return False

    def _detect_missing_python_module(self, text: str):
        match = re.search(r"ModuleNotFoundError:\s+No module named ['\"]([^'\"]+)['\"]", text)
        if match:
            self.last_missing_python_module = match.group(1).split(".")[0]

    def handle_missing_python_module_after_run(self):
        module = (self.last_missing_python_module or "").strip()
        if not module or not self.python_auto_install_enabled:
            return
        if module.lower() in self.ignored_missing_modules or is_standard_module(module):
            return
        if self._local_python_module_exists(module, self.last_run_source_path):
            self.output_console.appendPlainText(
                f"\nℹ Модуль {module} найден среди файлов проекта. Astra не будет искать одноимённый пакет в PyPI. "
                "Проверь структуру пакета и пути импорта (PYTHONPATH/расположение запускаемого файла)."
            )
            return
        self._ask_about_missing_python_module(module, rerun_after=True)

    def build_current_exe(self):
        if self.task_manager.has_active_task():
            self.output_console.appendPlainText("\n⚠ Дождись завершения текущей операции или нажми «Отмена».")
            return
        editor = self.current_editor()
        if not editor:
            return
        source_path = self._write_current_code_for_execution()
        if not source_path:
            return
        self.bottom_tabs.setCurrentIndex(0)
        self.output_console.clear()
        self.output_console.appendPlainText(f"⧉ Сборка EXE: {source_path}\n")
        self.output_console.appendPlainText(f"Язык: {editor.language_name}\nПапка проекта: {source_path.parent}\n")
        self.write_log(f"Build EXE requested: {source_path}")
        if editor.language_name == "Python":
            self._build_python_exe(source_path)
            return
        if editor.language_name == "C++":
            self._build_cpp_exe(source_path)
            return
        QMessageBox.information(self, "Сборка EXE", f"В {APP_VERSION} сборка EXE поддерживается для Python и C++.")

    def _build_python_exe(self, source_path: Path):
        record = self._python_package_record("PyInstaller") or {"import": "PyInstaller", "package": "pyinstaller", "warning": "", "heavy": False}
        if not self._python_import_available("PyInstaller"):
            answer = QMessageBox.question(self, "Сборка EXE", "PyInstaller не установлен. Установить его сейчас?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.Yes)
            if answer != QMessageBox.StandardButton.Yes:
                return
            self._run_pip_for_record(record, ["install", "pyinstaller"])
            self.output_console.appendPlainText("\nПосле установки PyInstaller нажми «Собрать EXE» ещё раз.")
            return
        py_program, py_args = self._active_python_command(source_path)
        if not py_program:
            QMessageBox.warning(self, "Сборка EXE", "Python не найден.")
            return
        dist_dir = self._safe_output_dir(source_path.parent, "dist")
        work_dir = self.temp_dir / "pyinstaller_build"
        spec_dir = self.temp_dir / "pyinstaller_spec"
        icon_path = resource_path("assets/astra.ico")
        args = [*py_args, "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile", "--distpath", str(dist_dir), "--workpath", str(work_dir), "--specpath", str(spec_dir)]
        if self.exe_build_mode == "Оконное приложение":
            args.append("--windowed")
        if icon_path.exists():
            args.extend(["--icon", str(icon_path)])
        args.append(str(source_path))
        exe_name = source_path.with_suffix(".exe").name if os.name == "nt" else source_path.stem
        exe_path = dist_dir / exe_name
        command_preview = self._safe_command_preview(py_program, args)
        self.output_console.appendPlainText("Этапы: подготовка → запуск PyInstaller → сборка → копирование результата → завершение\n")
        self.output_console.appendPlainText(f"▶ Команда: {command_preview}\n")
        self._start_process_task(
            "build_python_exe",
            "Идёт сборка Python EXE…",
            py_program,
            args,
            source_path.parent,
            {"mode": "build_python_exe", "exe_path": str(exe_path), "source_path": str(source_path), "indeterminate": True},
            20,
            100,
            True,
        )

    def _build_cpp_exe(self, source_path: Path):
        compiler = compiler_path("g++", "g++.exe", "clang++", "clang++.exe")
        if not compiler:
            self.output_console.appendPlainText("✕ Не найден C++ компилятор.")
            self._ask_install_now("C++")
            return
        dist_dir = self._safe_output_dir(source_path.parent, "dist")
        dist_dir.mkdir(parents=True, exist_ok=True)
        binary_path = dist_dir / (source_path.stem + (".exe" if os.name == "nt" else ""))
        compile_flags, linker_flags = self._cpp_extra_args(source_path)
        context = {
            "mode": "build_cpp_exe",
            "compiler": compiler,
            "source_path": str(source_path),
            "exe_path": str(binary_path),
            "compile_flags": compile_flags,
            "linker_flags": linker_flags,
            "extra_objects": [],
            "indeterminate": True,
        }
        if os.name == "nt":
            windres = compiler_path("windres.exe", "windres")
            icon_path = resource_path("assets/astra.ico")
            if windres and icon_path.exists():
                rc_path = self.build_dir / f"{source_path.stem}_icon.rc"
                res_path = self.build_dir / f"{source_path.stem}_icon.o"
                icon_str = str(icon_path).replace("\\", "\\\\")
                rc_path.write_text(f'IDI_ICON1 ICON "{icon_str}"\n', encoding="utf-8")
                args = [str(rc_path), str(res_path)]
                self.output_console.appendPlainText("Этапы: подготовка resource-файла → windres → компиляция EXE → завершение\n")
                self.output_console.appendPlainText(f"▶ Команда resource: {self._safe_command_preview(windres, args)}\n")
                resource_context = dict(context)
                resource_context.update({"mode": "build_cpp_resource", "res_path": str(res_path)})
                self._start_process_task("build_cpp_resource", "Готовится иконка C++ EXE…", windres, args, source_path.parent, resource_context, 10, 30, True)
                return
        self._start_build_cpp_compile(context)

    def _start_build_cpp_compile(self, context: dict):
        compiler = context["compiler"]
        source_path = Path(context["source_path"])
        binary_path = Path(context["exe_path"])
        compile_flags = list(context.get("compile_flags", []))
        linker_flags = list(context.get("linker_flags", []))
        extra_objects = [str(obj) for obj in context.get("extra_objects", []) if obj]
        args = ["-std=c++17", "-Wall", "-Wextra", "-fdiagnostics-color=never", *compile_flags, str(source_path), *extra_objects, "-o", str(binary_path), *linker_flags]
        command_preview = self._safe_command_preview(compiler, args)
        self.output_console.appendPlainText("Этапы: подготовка → запуск компилятора → сборка EXE → завершение\n")
        self.output_console.appendPlainText(f"▶ Команда: {command_preview}\n")
        build_context = dict(context)
        build_context["mode"] = "build_cpp_exe"
        self._start_process_task(
            "build_cpp_exe",
            "Идёт сборка C++ EXE…",
            compiler,
            args,
            source_path.parent,
            build_context,
            30,
            100,
            True,
        )

    def _ask_create_shortcut_for_exe(self, exe_path: Path):
        if os.name != "nt" or not exe_path.exists():
            return
        answer = QMessageBox.question(self, "Сборка EXE", "Создать ярлык собранной программы на рабочем столе?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if answer != QMessageBox.StandardButton.Yes:
            return
        shortcut_name = self._ps_quote(exe_path.stem + ".lnk")
        target_path = self._ps_quote(str(exe_path))
        workdir_path = self._ps_quote(str(exe_path.parent))
        shortcut_icon = self._ps_quote(str(resource_path("assets/astra.ico")))
        ps_script = "\n".join([
            "$WshShell = New-Object -ComObject WScript.Shell",
            "$Desktop = [Environment]::GetFolderPath(\"Desktop\")",
            f"$Shortcut = $WshShell.CreateShortcut((Join-Path $Desktop {shortcut_name}))",
            f"$Shortcut.TargetPath = {target_path}",
            f"$Shortcut.WorkingDirectory = {workdir_path}",
            f"$Shortcut.IconLocation = {shortcut_icon}",
            "$Shortcut.Save()",
        ])
        script_path = self.temp_dir / "create_built_exe_shortcut.ps1"
        script_path.write_text(ps_script, encoding="utf-8-sig")
        powershell = compiler_path("powershell.exe", "pwsh.exe")
        if not powershell:
            QMessageBox.warning(self, "Ярлык", "PowerShell не найден, ярлык не создан.")
            return
        ok, _code, stdout, stderr = self._run_blocking(powershell, ["-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script_path)], exe_path.parent, timeout_ms=30000)
        if ok:
            QMessageBox.information(self, "Ярлык", "Ярлык создан на рабочем столе.")
        else:
            QMessageBox.warning(self, "Ярлык", "Не удалось создать ярлык.\n" + (stderr or stdout))


    def toggle_main_sidebar(self):
        """Скрывает/показывает только основную левую панель, не трогая панель настроек."""
        try:
            sidebar = getattr(self, "sidebar_shell", None) or getattr(self, "sidebar_scroll", None)
            if sidebar is None or not hasattr(self, "root_splitter"):
                return
            sizes = self.root_splitter.sizes()
            tools_width = sizes[1] if len(sizes) > 1 else (420 if self.tools_drawer.isVisible() else 0)
            editor_width = sizes[2] if len(sizes) > 2 else 1040
            if sidebar.isVisible():
                sidebar.setVisible(False)
                if hasattr(self, "btn_restore_sidebar"):
                    self.btn_restore_sidebar.setVisible(True)
                self.root_splitter.setSizes([0, tools_width, max(900, editor_width + max(sizes[0] if sizes else 306, 306))])
                self.statusBar().showMessage("Основная боковая панель скрыта", 1800)
                self.write_log("Основная боковая панель скрыта")
            else:
                sidebar.setVisible(True)
                if hasattr(self, "btn_restore_sidebar"):
                    self.btn_restore_sidebar.setVisible(False)
                self.root_splitter.setSizes([306, tools_width, max(700, editor_width)])
                self.statusBar().showMessage("Основная боковая панель показана", 1800)
                self.write_log("Основная боковая панель показана")
        except Exception as exc:
            self.write_exception_log("Ошибка переключения основной боковой панели", exc)


    def _safe_project_folder_name(self, name: str) -> str:
        clean = re.sub(r"[^A-Za-zА-Яа-яЁё0-9_. -]+", "_", name).strip(" ._")
        return clean or "AstraProject"

    def _project_config_path_for_folder(self, folder: Path) -> Path:
        return Path(folder) / "astral.project.json"

    def _permission_help_text(self, path: Path) -> str:
        return (
            "Windows не даёт Astra Studio изменить выбранную папку:\n"
            f"{path}\n\n"
            f"В {APP_VERSION} приложение не пытается писать изменяемые данные в папку программы или чужие защищённые каталоги. "
            "Выберите папку в Documents\\Astral Studio или сохраните файл через «Сохранить как»."
        )

    def _ensure_user_writable_folder(self, requested: Path, fallback: Path | None = None) -> Path | None:
        requested = Path(requested)
        if can_write_to_directory(requested):
            return requested
        fallback = fallback or default_projects_dir()
        if can_write_to_directory(fallback):
            answer = QMessageBox.question(
                self,
                "Нет прав на папку",
                self._permission_help_text(requested) + f"\n\nСоздать/сохранить в безопасной папке?\n{fallback}",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if answer == QMessageBox.StandardButton.Yes:
                return fallback
        QMessageBox.warning(self, "Нет прав на папку", self._permission_help_text(requested))
        return None

    def _safe_output_dir(self, source_folder: Path, child_name: str) -> Path:
        candidate = Path(source_folder) / child_name
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            if can_write_to_directory(candidate):
                return candidate
        except OSError:
            pass
        fallback = default_builds_dir() / child_name
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback

    def _normalize_attached_folders(self, attached_folders: list | None) -> list[dict]:
        normalized: list[dict] = []
        seen: set[str] = set()
        for item in attached_folders or []:
            if isinstance(item, dict):
                raw_path = str(item.get("path") or "").strip()
                alias = str(item.get("alias") or "").strip()
            else:
                raw_path = str(item or "").strip()
                alias = ""
            if not raw_path:
                continue
            path = Path(raw_path)
            try:
                key = str(path.resolve()).lower() if os.name == "nt" else str(path.resolve())
            except OSError:
                key = str(path).lower() if os.name == "nt" else str(path)
            if key in seen:
                continue
            seen.add(key)
            normalized.append({"alias": alias or path.name or "Подключённая папка", "path": str(path)})
        return normalized

    def _path_belongs_to_current_project(self, path: Path | str) -> bool:
        try:
            candidate = Path(path).resolve()
        except OSError:
            candidate = Path(path)
        roots = [Path(self.project_main_folder)]
        roots.extend(Path(item["path"]) for item in self.attached_project_folders if isinstance(item, dict) and item.get("path"))
        for root in roots:
            try:
                root_resolved = root.resolve()
                candidate.relative_to(root_resolved)
                return True
            except (OSError, ValueError):
                continue
        return False

    def _current_open_file_paths(self) -> list[str]:
        paths = []
        seen = set()
        for editor in self.all_editors():
            if not editor.file_path or not self._path_belongs_to_current_project(editor.file_path):
                continue
            text = str(editor.file_path)
            key = text.lower() if os.name == "nt" else text
            if key not in seen:
                seen.add(key)
                paths.append(text)
        return paths

    def _project_payload(self) -> dict:
        current_editor = self.current_editor()
        active_file = ""
        if current_editor and current_editor.file_path and self._path_belongs_to_current_project(current_editor.file_path):
            active_file = str(current_editor.file_path)
        config_path = self.current_project_config_path or self._project_config_path_for_folder(self.project_main_folder)
        return {
            "projectName": self.current_project_name,
            "version": APP_VERSION.replace("Release ", ""),
            "createdAt": datetime.datetime.now().isoformat(timespec="seconds"),
            "mainFolder": portable_project_path(self.project_main_folder, config_path),
            "attachedFolders": portable_attached_folders(self.attached_project_folders, config_path),
            "openFiles": [portable_project_path(path, config_path) for path in self._current_open_file_paths()],
            "activeFile": portable_project_path(active_file, config_path) if active_file else "",
            "defaultLanguage": self.current_language_name,
            "pythonInterpreter": self.project_python_interpreter,
            "commands": normalize_commands(self.project_commands),
            "testExplorerLastRun": self.test_explorer_last_run.to_dict() if self.test_explorer_last_run is not None else None,
            "staffedUp": dict(self.project_staffedup_meta) if self.project_staffedup_meta else None,
            "settings": {
                "tabSize": self.editor_tab_size,
                "indentSize": self.editor_indent_size,
                "insertSpaces": self.editor_insert_spaces,
                "uiFontSize": self.ui_font_size,
                "editorFontSize": self.editor_font_size,
                "consoleFontSize": self.console_font_size,
            },
            "astralStudioVersion": APP_VERSION,
        }

    def _save_current_project_state(self):
        if not self.current_project_config_path:
            return
        try:
            config_path = Path(self.current_project_config_path)
            if not config_path.parent.exists() or not config_path.parent.is_dir():
                self.write_exception_log("Не удалось сохранить состояние проекта", FileNotFoundError(str(config_path.parent)))
                return
            if not can_write_to_directory(config_path.parent):
                self.write_exception_log("Не удалось сохранить состояние проекта", PermissionError(str(config_path.parent)))
                return
            payload = self._project_payload()
            if config_path.exists():
                try:
                    old = json.loads(config_path.read_text(encoding="utf-8"))
                    payload["createdAt"] = old.get("createdAt", payload["createdAt"])
                except Exception:
                    pass
            config_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as exc:
            self.write_exception_log("Не удалось сохранить состояние проекта", exc)

    def _set_current_project(self, name: str, main_folder: Path, config_path: Path | None = None, attached_folders: list | None = None, python_interpreter: str = "", commands: dict | None = None, test_last_run: object = None, staffedup_meta: dict | None = None):
        new_main_folder = Path(main_folder)
        new_config_path = str(config_path or self._project_config_path_for_folder(new_main_folder))
        if self.current_project_config_path and self.current_project_config_path != new_config_path:
            self._save_current_project_state()
        self.current_project_name = name or new_main_folder.name
        self.project_main_folder = new_main_folder
        self.workspace_dir = self.project_main_folder
        if hasattr(self, "lsp_manager"):
            self._queued_lsp_requests.clear()
            self.lsp_manager.set_project_root(self.project_main_folder)
        self.quality_diagnostics.clear()
        if hasattr(self, "problems_tree"):
            self._refresh_problems_panel()
        self.current_project_config_path = new_config_path
        self.project_python_interpreter = str(python_interpreter or "")
        self.project_commands = normalize_commands(commands)
        self.project_staffedup_meta = dict(staffedup_meta) if isinstance(staffedup_meta, dict) else {}
        self.test_explorer_last_run = restore_test_run(test_last_run)
        self.test_explorer_discovered = []
        self.test_explorer_adapters = []
        self.test_explorer_active_adapter = str(getattr(self.test_explorer_last_run, "adapter_id", "") or "")
        self.git_repo_root = None
        self.git_state = None
        self.git_last_diff_path = ""
        self.git_last_diff_staged = False
        if hasattr(self, "git_tree"):
            self._render_git_state(None, "Git: статус не проверен для нового проекта")
        if hasattr(self, "test_tree"):
            if self.test_explorer_last_run is not None:
                self._render_test_result(self.test_explorer_last_run)
            else:
                self._render_test_nodes([], "Тесты: ещё не запускались")
        if not self.project_main_folder.exists() or not self.project_main_folder.is_dir():
            self.statusBar().showMessage("Папка проекта недоступна или не существует", 5000)
        elif not can_write_to_directory(self.project_main_folder):
            self.statusBar().showMessage("Проект открыт только для чтения: нет прав на изменение папки", 5000)
        self.attached_project_folders = self._normalize_attached_folders(attached_folders)
        QTimer.singleShot(0, self._resync_open_project_editors_lsp)
        if self.current_project_config_path:
            self.recent_projects = [self.current_project_config_path] + [p for p in self.recent_projects if p != self.current_project_config_path]
            self.recent_projects = self.recent_projects[:10]
        self.workspace_label.setText("Текущий проект:\n" + self.current_project_name + "\n" + str(self.project_main_folder))
        self.refresh_project_tree()
        self._save_settings()
        # The integrated terminal must follow the active project. Without this,
        # commands continue to run in the previously opened workspace.
        if self.terminal_process is not None:
            self.restart_terminal()
        self._refresh_python_environment_status()

    def _project_search_roots(self) -> list[Path]:
        roots = [Path(self.project_main_folder)]
        for item in self.attached_project_folders:
            if isinstance(item, dict) and item.get("path"):
                roots.append(Path(item["path"]))
        resolved_roots: list[tuple[Path, Path]] = []
        seen = set()
        for root in roots:
            if not root.exists() or not root.is_dir():
                continue
            try:
                resolved = root.resolve()
            except OSError:
                resolved = root
            key = str(resolved).lower() if os.name == "nt" else str(resolved)
            if key in seen:
                continue
            seen.add(key)
            resolved_roots.append((root, resolved))

        # If an attached folder is already inside the main/project search root,
        # walking both would duplicate Quick Open/search results and inflate replace counts.
        result: list[Path] = []
        covered: list[Path] = []
        for root, resolved in sorted(resolved_roots, key=lambda pair: len(pair[1].parts)):
            nested = False
            for parent in covered:
                try:
                    resolved.relative_to(parent)
                    nested = True
                    break
                except ValueError:
                    continue
            if nested:
                continue
            result.append(root)
            covered.append(resolved)
        return result

    def _iter_project_text_files(self, max_files: int | None = 6000):
        skipped_dirs = {
            ".git", "node_modules", ".venv", "venv", "__pycache__", "build", "dist",
            ".pytest_cache", ".mypy_cache", ".ruff_cache", ".next", ".cache", ".godot",
            "coverage", "vendor", "target", "bin", "obj", "out",
        }
        allowed_exts = set(EXTENSION_TO_LANGUAGE) | {".txt", ".ini", ".cfg", ".conf", ".env", ".gitignore"}
        count = 0
        for root in self._project_search_roots():
            for current, dirnames, filenames in os.walk(root):
                dirnames[:] = [name for name in dirnames if name not in skipped_dirs]
                current_path = Path(current)
                for filename in filenames:
                    path = current_path / filename
                    lower_name = filename.lower()
                    suffix = path.suffix.lower()
                    special = lower_name in SPECIAL_FILENAMES_TO_LANGUAGE or lower_name.startswith(("dockerfile", "containerfile")) or lower_name.startswith(".env")
                    if suffix not in allowed_exts and not special and filename not in {".gitignore"}:
                        continue
                    try:
                        if path.stat().st_size > 2 * 1024 * 1024:
                            continue
                    except OSError:
                        continue
                    yield path
                    count += 1
                    if max_files is not None and count >= max_files:
                        return

    def _path_belongs_to_active_project(self, path: Path | str) -> bool:
        try:
            candidate = Path(path).resolve()
        except OSError:
            candidate = Path(path)
        for root in self._project_search_roots():
            try:
                candidate.relative_to(root.resolve())
                return True
            except (OSError, ValueError):
                continue
        return False

    def _ensure_editor_lsp_open(self, editor):
        if not isinstance(editor, CodeEditor) or editor.file_path is None:
            return
        if self.tabs.indexOf(editor) < 0:
            return
        if not self._path_belongs_to_active_project(editor.file_path):
            return
        try:
            self.lsp_manager.open_document(editor.language_name, editor.file_path, editor.toPlainText())
        except Exception as exc:
            self.write_exception_log("Не удалось синхронизировать файл с LSP", exc)

    def _schedule_editor_lsp_change(self, editor):
        if not isinstance(editor, CodeEditor) or editor.file_path is None:
            return
        timer = getattr(editor, "_astra_lsp_change_timer", None)
        if timer is not None:
            timer.start()

    def _sync_editor_lsp_change(self, editor):
        if not isinstance(editor, CodeEditor) or editor.file_path is None:
            return
        if self.tabs.indexOf(editor) < 0 or not self._path_belongs_to_active_project(editor.file_path):
            return
        try:
            self.lsp_manager.change_document(editor.language_name, editor.file_path, editor.toPlainText())
        except Exception as exc:
            self.write_exception_log("Не удалось отправить изменение файла в LSP", exc)

    def _save_editor_to_lsp(self, editor):
        if not isinstance(editor, CodeEditor) or editor.file_path is None:
            return
        if not self._path_belongs_to_active_project(editor.file_path):
            return
        timer = getattr(editor, "_astra_lsp_change_timer", None)
        if timer is not None:
            timer.stop()
        try:
            self.lsp_manager.save_document(editor.language_name, editor.file_path, editor.toPlainText())
        except Exception as exc:
            self.write_exception_log("Не удалось отправить сохранение файла в LSP", exc)

    def _resync_open_project_editors_lsp(self):
        if not hasattr(self, "lsp_manager"):
            return
        for editor in self.all_editors():
            if editor.file_path is not None and self._path_belongs_to_active_project(editor.file_path):
                self._ensure_editor_lsp_open(editor)

    def _on_lsp_state_changed(self, language: str, state: str):
        if state in {"failed", "stopped"}:
            self._queued_lsp_requests.pop(language, None)
        if hasattr(self, "lsp_server_table"):
            self._refresh_lsp_server_table()
        if state == "ready":
            self.statusBar().showMessage(f"LSP {language}: готов", 1800)

    def _on_lsp_initialized(self, language: str, _capabilities):
        self._refresh_lsp_server_table()
        queued = self._queued_lsp_requests.pop(language, None)
        if queued:
            feature, path, line, character, token, extra = queued
            QTimer.singleShot(
                0,
                lambda: self._send_ready_lsp_feature(language, feature, path, line, character, token, extra),
            )

    def _refresh_lsp_server_table(self):
        table = getattr(self, "lsp_server_table", None)
        if table is None or not hasattr(self, "lsp_manager"):
            return
        registry = self.lsp_manager.registry
        registry.reload()
        languages = list(registry.supported_languages())
        table.setRowCount(len(languages))
        for row, language in enumerate(languages):
            config = registry.config_for_language(language)
            resolved = registry.resolve(language, self.project_main_folder)
            state = self.lsp_manager.server_state(language)
            if config is None:
                status = "нет конфигурации"
                server_text = "—"
                note = ""
            elif not config.enabled:
                status = "отключён"
                server_text = "—"
                note = config.notes
            elif state == "ready":
                status = "готов"
                server_text = (
                    f"{config.host}:{config.port}" if config.transport == "external_tcp"
                    else str(getattr(resolved, "executable", "") or "локальный сервер")
                )
                note = config.notes
            elif state in {"starting", "initializing", "restarting", "shutting_down"}:
                status = state
                server_text = (
                    f"{config.host}:{config.port}" if config.transport == "external_tcp"
                    else str(getattr(resolved, "executable", "") or (config.candidates[0].command if config.candidates else "—"))
                )
                note = config.notes
            elif resolved is not None:
                if resolved.transport == "external_tcp":
                    status = "ожидает внешний сервер"
                    server_text = f"{resolved.host}:{resolved.port}"
                else:
                    status = "доступен"
                    server_text = resolved.executable
                note = config.notes
            else:
                status = "не установлен"
                server_text = config.candidates[0].command if config.candidates else "—"
                note = config.notes
            plan = install_plan_for_language(language)
            if plan is None:
                install_text = "ручная настройка"
            elif plan.kind == "external":
                install_text = "встроен во внешний инструмент"
            elif plan.safe:
                install_text = plan.title
            else:
                install_text = "ручная настройка"
            for column, value in enumerate((language, status, server_text, install_text, note)):
                item = QTableWidgetItem(str(value))
                item.setToolTip(str(value))
                table.setItem(row, column, item)
        table.resizeRowsToContents()

    def _selected_lsp_language(self) -> str:
        table = getattr(self, "lsp_server_table", None)
        if table is None:
            return ""
        row = table.currentRow()
        if row < 0:
            editor = self.current_editor()
            return editor.language_name if editor else ""
        item = table.item(row, 0)
        return item.text().strip() if item is not None else ""

    def start_selected_lsp_server(self):
        language = self._selected_lsp_language()
        if not language:
            QMessageBox.information(self, "LSP", "Выбери язык в таблице LSP.")
            return
        config = self.lsp_manager.registry.config_for_language(language)
        if config is None or not config.enabled:
            QMessageBox.information(self, "LSP", f"Для {language} нет включённого LSP по умолчанию. Можно настроить lsp_servers.json вручную.")
            return
        if self.lsp_manager.registry.resolve(language, self.project_main_folder) is None:
            QMessageBox.information(self, "LSP", f"LSP-сервер для {language} не найден. Используй «Установить / обновить» или настрой lsp_servers.json.")
            return
        if not self.lsp_manager.restart_server(language):
            QMessageBox.warning(self, "LSP", f"Не удалось запустить LSP для {language}.")
            return
        self.statusBar().showMessage(f"LSP {language}: запуск…", 2500)
        self._refresh_lsp_server_table()

    def stop_selected_lsp_server(self):
        language = self._selected_lsp_language()
        if not language:
            return
        self.lsp_manager.stop_server(language, wait=False)
        self._refresh_lsp_server_table()
        self.statusBar().showMessage(f"LSP {language}: остановлен", 2200)

    def _wrap_windows_command_script(self, program: str, arguments: list[str]) -> tuple[str, list[str]]:
        suffix = Path(str(program)).suffix.lower()
        if os.name == "nt" and suffix in {".cmd", ".bat"}:
            command_line = subprocess.list2cmdline([str(program), *[str(item) for item in arguments]])
            return os.environ.get("COMSPEC", "cmd.exe"), ["/d", "/s", "/c", command_line]
        return str(program), [str(item) for item in arguments]

    def _node_version_tuple(self, node: str) -> tuple[int, int, int] | None:
        """Return Node.js semantic version for explicit LSP install preflight."""
        try:
            completed = subprocess.run(
                [str(node), "--version"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=3,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        if completed.returncode != 0:
            return None
        match = re.search(r"v?(\d+)(?:\.(\d+))?(?:\.(\d+))?", completed.stdout or "")
        if not match:
            return None
        return tuple(int(part or 0) for part in match.groups())

    def _dotnet_sdk_major(self, dotnet: str) -> int | None:
        """Return the active .NET SDK major version for an explicit install action.

        This preflight is intentionally short and is only run after the user opens
        the LSP installer flow; normal editor/LSP operation never blocks on it.
        """
        try:
            completed = subprocess.run(
                [str(dotnet), "--version"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=3,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        if completed.returncode != 0:
            return None
        match = re.match(r"\s*(\d+)", completed.stdout or "")
        return int(match.group(1)) if match else None

    def _lsp_install_command(self, language: str) -> tuple[str | None, list[str], str]:
        plan = install_plan_for_language(language)
        if plan is None or not plan.safe:
            return None, [], ""
        available = self.lsp_manager.registry.resolve(language, self.project_main_folder) is not None
        root = self._python_project_root()
        if plan.kind == "python_tool":
            info = detect_project_environment(root)
            override = self._resolved_project_python_override(root)
            if info.python_executable is None and override is None:
                return None, [], "needs_python_env"
            program, args = self._python_package_manager_command(["install", "--upgrade", *plan.packages])
            return program, args, plan.title if program else ""
        if plan.kind == "npm_global":
            npm = compiler_path("npm.cmd", "npm.exe", "npm")
            if not npm:
                return None, [], "needs_node"
            if language in {"JavaScript", "TypeScript"}:
                node = compiler_path("node.exe", "node")
                node_version = self._node_version_tuple(node) if node else None
                # typescript-language-server 5.3.0 (current during Release 3.1)
                # declares Node >=22.22.2. Refuse an install that is known to
                # produce a server incompatible with the active runtime.
                if node_version is not None and node_version < (22, 22, 2):
                    return None, [], "needs_node22"
            program, args = self._wrap_windows_command_script(npm, ["install", "--global", *plan.packages])
            return program, args, plan.title
        if plan.kind == "winget":
            winget = compiler_path("winget.exe", "winget")
            if not winget:
                return None, [], "needs_winget"
            verb = "upgrade" if available else "install"
            args = [verb, "--id", plan.package_id, "--exact", "--accept-source-agreements", "--accept-package-agreements"]
            return winget, args, plan.title
        if plan.kind == "dotnet_tool":
            dotnet = compiler_path("dotnet.exe", "dotnet")
            if not dotnet:
                return None, [], "needs_dotnet"
            sdk_major = self._dotnet_sdk_major(dotnet)
            if sdk_major is not None and sdk_major < 10:
                return None, [], "needs_dotnet10"
            verb = "update" if available else "install"
            return dotnet, ["tool", verb, "--global", *plan.packages], plan.title
        return None, [], ""

    def install_or_update_selected_lsp_server(self):
        language = self._selected_lsp_language()
        if not language:
            QMessageBox.information(self, "LSP", "Выбери язык в таблице LSP.")
            return
        plan = install_plan_for_language(language)
        if plan is None:
            QMessageBox.information(self, "LSP", f"Для {language} нет безопасного автоматического установщика. Настрой сервер вручную через lsp_servers.json.")
            return
        if plan.kind == "external":
            QMessageBox.information(self, "LSP", plan.notes or "Этот LSP предоставляется внешним приложением.")
            return
        if not plan.safe:
            QMessageBox.warning(self, "LSP", "Автоматическая установка этого сервера отключена из соображений безопасности.")
            return
        program, args, label = self._lsp_install_command(language)
        if label == "needs_python_env":
            answer = QMessageBox.question(
                self,
                "Python LSP",
                "Для BasedPyright Astra устанавливает сервер в Python-окружение проекта, чтобы не загрязнять глобальный Python. Создать .venv?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if answer == QMessageBox.StandardButton.Yes:
                self.create_project_python_environment()
            return
        missing_messages = {
            "needs_node": "Не найден Node.js/npm. Установи Node.js через вкладку «Установщик».",
            "needs_node22": "Текущий TypeScript Language Server требует Node.js 22.22.2 или новее. Обнови Node.js LTS через вкладку «Установщик».",
            "needs_winget": "WinGet недоступен — автоматическая установка clangd остановлена.",
            "needs_dotnet": "Не найден .NET SDK — автоматическая установка csharp-ls невозможна.",
            "needs_dotnet10": "csharp-ls требует .NET 10 SDK или новее. Обнови .NET SDK и повтори установку.",
        }
        if label in missing_messages:
            QMessageBox.warning(self, "LSP", missing_messages[label])
            return
        if not program:
            QMessageBox.warning(self, "LSP", f"Не удалось подготовить безопасную установку LSP для {language}.")
            return
        answer = QMessageBox.question(
            self,
            "Установка LSP",
            f"Установить или обновить {plan.title} для {language}?\n\nКоманда:\n{self._safe_command_preview(program, args)}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        # Updating an executable/package while its language server is still
        # running can fail on Windows because the tool files may be locked.
        # Stop the owned connection first; successful installation starts it
        # again for the current editor in _on_task_finished.
        if self.lsp_manager.server_state(language) != "stopped":
            self.lsp_manager.stop_server(language, wait=True)
        self.bottom_tabs.setCurrentIndex(0)
        self.output_console.appendPlainText(f"\n▶ LSP {language}: {self._safe_command_preview(program, args)}\n")
        self._start_process_task(
            f"lsp_install_{re.sub(r'[^a-z0-9]+', '_', language.lower()).strip('_')}",
            f"Устанавливается LSP для {language}…",
            program,
            args,
            self.project_main_folder,
            {"mode": "lsp_install", "language": language, "target": "output", "indeterminate": True},
            10,
            100,
            True,
        )

    def _on_current_editor_changed_for_lsp(self):
        if hasattr(self, "lsp_outline_tree"):
            self.lsp_outline_tree.clear()
        # Do not issue background symbol requests unless the LSP page is visible.
        if hasattr(self, "tools_drawer") and self.tools_drawer.isVisible() and hasattr(self, "tools_stack") and self.tools_stack.currentIndex() == 3:
            self.request_lsp_outline(silent=True)

    def _flush_editor_lsp_state(self, editor) -> bool:
        if not isinstance(editor, CodeEditor) or editor.file_path is None:
            return False
        if not self._path_belongs_to_active_project(editor.file_path):
            return False
        timer = getattr(editor, "_astra_lsp_change_timer", None)
        if timer is not None:
            timer.stop()
        self._ensure_editor_lsp_open(editor)
        document = self.lsp_manager.documents.get(editor.file_path)
        if document is not None and document.text != editor.toPlainText():
            self.lsp_manager.change_document(editor.language_name, editor.file_path, editor.toPlainText())
        return True

    def _lsp_request_token(self, editor) -> dict:
        self._lsp_request_serial += 1
        cursor = editor.textCursor()
        document = self.lsp_manager.documents.get(editor.file_path) if editor.file_path else None
        return {
            "serial": self._lsp_request_serial,
            "path": str(Path(editor.file_path).resolve()) if editor.file_path else "",
            "version": int(document.version) if document is not None else 0,
            "line": int(cursor.blockNumber()),
            "character": int(cursor.positionInBlock()),
        }

    def _send_ready_lsp_feature(self, language: str, feature: str, path: Path, line: int, character: int, token: dict, extra: dict | None):
        if self.lsp_manager.server_state(language) != "ready":
            return False
        if not self.lsp_manager.supports_feature(language, feature):
            self.statusBar().showMessage(f"LSP {language} не заявил поддержку: {feature}", 3200)
            return False
        request_id = self.lsp_manager.request_feature(
            language,
            feature,
            path,
            line,
            character,
            token=token,
            extra=extra,
        )
        return request_id is not None

    def _request_lsp_feature(self, feature: str, extra: dict | None = None, silent: bool = False) -> bool:
        editor = self.current_editor()
        if not isinstance(editor, CodeEditor) or editor.file_path is None:
            if not silent:
                self.statusBar().showMessage("LSP-функция доступна только для сохранённого файла проекта", 3000)
            return False
        if not self._flush_editor_lsp_state(editor):
            return False
        cursor = editor.textCursor()
        line = int(cursor.blockNumber())
        character = int(cursor.positionInBlock())
        token = self._lsp_request_token(editor)
        language = editor.language_name
        state = self.lsp_manager.server_state(language)
        if state != "ready":
            connection = self.lsp_manager.ensure_server(language)
            if connection is None:
                if not silent:
                    self.statusBar().showMessage(f"LSP для {language} не найден. Открой LSP / Outline для установки или настройки.", 4500)
                return False
            self._queued_lsp_requests[language] = (feature, Path(editor.file_path), line, character, token, dict(extra or {}))
            if not silent:
                self.statusBar().showMessage(f"LSP {language} запускается; запрос поставлен в очередь…", 3000)
            return True
        return self._send_ready_lsp_feature(language, feature, Path(editor.file_path), line, character, token, extra)

    def request_lsp_completion(self):
        self._request_lsp_feature("completion")

    def request_lsp_hover(self):
        self._request_lsp_feature("hover")

    def request_lsp_signature_help(self):
        self._request_lsp_feature("signature_help")

    def request_lsp_definition(self):
        self._request_lsp_feature("definition")

    def request_lsp_references(self):
        self._request_lsp_feature("references")

    def request_lsp_rename(self):
        editor = self.current_editor()
        if not isinstance(editor, CodeEditor) or editor.file_path is None:
            return
        cursor = editor.textCursor()
        cursor.select(QTextCursor.SelectionType.WordUnderCursor)
        current_name = cursor.selectedText().strip()
        new_name, ok = QInputDialog.getText(self, "Rename Symbol · F2", "Новое имя символа:", text=current_name)
        new_name = str(new_name or "").strip()
        if not ok or not new_name or new_name == current_name:
            return
        self._request_lsp_feature("rename", {"newName": new_name})

    def request_lsp_outline(self, silent: bool = False):
        return self._request_lsp_feature("document_symbols", silent=silent)

    def _token_matches_current_document(self, token: object, strict_version: bool = True) -> bool:
        if not isinstance(token, dict):
            return False
        editor = self.current_editor()
        if not isinstance(editor, CodeEditor) or editor.file_path is None:
            return False
        try:
            same_path = Path(editor.file_path).resolve() == Path(str(token.get("path") or "")).resolve()
        except OSError:
            same_path = str(editor.file_path) == str(token.get("path") or "")
        if not same_path:
            return False
        if strict_version:
            document = self.lsp_manager.documents.get(editor.file_path)
            if document is None or int(document.version) != int(token.get("version", -1)):
                return False
        return True

    def _on_lsp_interactive_result(self, language: str, feature: str, token: object, result: object, error: object):
        if error:
            message = error.get("message") if isinstance(error, dict) else str(error)
            self.statusBar().showMessage(f"LSP {language} · {feature}: {message}", 4500)
            return
        if feature == "completion":
            if not self._token_matches_current_document(token, strict_version=True):
                return
            self._show_lsp_completion(result)
        elif feature == "hover":
            if not self._token_matches_current_document(token, strict_version=True):
                return
            text = hover_text(result)
            if text:
                self._show_lsp_tooltip(text)
            else:
                self.statusBar().showMessage("LSP: hover-информация отсутствует", 1800)
        elif feature == "signature_help":
            if not self._token_matches_current_document(token, strict_version=True):
                return
            text = signature_help_text(result)
            if text:
                self._show_lsp_tooltip(text)
            else:
                self.statusBar().showMessage("LSP: signature help отсутствует", 1800)
        elif feature == "definition":
            if not self._token_matches_current_document(token, strict_version=True):
                return
            locations = normalize_locations(result)
            if len(locations) == 1:
                self._open_lsp_location(locations[0])
            elif locations:
                self._show_lsp_locations("Go to Definition", locations)
            else:
                self.statusBar().showMessage("LSP: определение не найдено", 2200)
        elif feature == "references":
            if not self._token_matches_current_document(token, strict_version=True):
                return
            locations = normalize_locations(result)
            if locations:
                self._show_lsp_locations("Find References", locations)
            else:
                self.statusBar().showMessage("LSP: ссылки на символ не найдены", 2200)
        elif feature == "rename":
            if not self._token_matches_current_document(token, strict_version=True):
                self.statusBar().showMessage("Rename отменён: документ изменился до ответа LSP", 3200)
                return
            if workspace_edit_has_resource_operations(result):
                QMessageBox.warning(self, "Rename Symbol", "LSP предложил создание/переименование/удаление файлов. B3 безопасно применяет только текстовые edits, поэтому rename отменён целиком.")
                return
            edits = normalize_workspace_edit(result)
            self._apply_lsp_workspace_rename(edits)
        elif feature == "document_symbols":
            if not self._token_matches_current_document(token, strict_version=True):
                return
            self._populate_lsp_outline(normalize_document_symbols(result), token)

    def _show_lsp_tooltip(self, text: str):
        editor = self.current_editor()
        if not isinstance(editor, CodeEditor):
            return
        clean = str(text or "").strip()
        if len(clean) > 5000:
            clean = clean[:5000] + "\n…"
        safe = html.escape(clean).replace("\n", "<br>")
        QToolTip.showText(editor.viewport().mapToGlobal(editor.cursorRect().bottomRight()), f"<div style='white-space:pre-wrap'>{safe}</div>", editor)

    def _show_lsp_completion(self, result: object):
        editor = self.current_editor()
        if not isinstance(editor, CodeEditor):
            return
        items = normalize_completion_items(result)
        if not items:
            self.statusBar().showMessage("LSP: вариантов completion нет", 1800)
            return
        menu = QMenu(editor)
        menu.setStyleSheet(self.styleSheet())
        action_map = {}
        for item in items[:100]:
            detail = item.get("detail") or ""
            label = item.get("label") or ""
            text = f"{label}    {detail}" if detail else label
            action = menu.addAction(text)
            if item.get("documentation"):
                action.setToolTip(str(item["documentation"])[:1200])
            action_map[action] = item
        chosen = menu.exec(editor.viewport().mapToGlobal(editor.cursorRect().bottomLeft()))
        item = action_map.get(chosen)
        if item:
            self._apply_lsp_completion_item(editor, item)

    def _lsp_cursor_position(self, editor: CodeEditor, line: int, character: int) -> int:
        block = editor.document().findBlockByNumber(max(0, int(line)))
        if not block.isValid():
            return max(0, editor.document().characterCount() - 1)
        max_character = max(0, block.length() - 1)
        return block.position() + min(max(0, int(character)), max_character)

    def _apply_lsp_completion_item(self, editor: CodeEditor, item: dict):
        cursor = editor.textCursor()
        text_edit = item.get("text_edit") if isinstance(item.get("text_edit"), dict) else None
        new_text = str((text_edit or {}).get("newText") or item.get("insert_text") or item.get("label") or "")
        if text_edit and isinstance(text_edit.get("range"), dict):
            raw_range = text_edit["range"]
            start = raw_range.get("start") if isinstance(raw_range.get("start"), dict) else {}
            end = raw_range.get("end") if isinstance(raw_range.get("end"), dict) else {}
            start_pos = self._lsp_cursor_position(editor, int(start.get("line", 0)), int(start.get("character", 0)))
            end_pos = self._lsp_cursor_position(editor, int(end.get("line", 0)), int(end.get("character", 0)))
            cursor.setPosition(start_pos)
            cursor.setPosition(max(start_pos, end_pos), QTextCursor.MoveMode.KeepAnchor)
        else:
            cursor.select(QTextCursor.SelectionType.WordUnderCursor)
        cursor.insertText(new_text)
        editor.setTextCursor(cursor)
        editor.setFocus()

    def _open_lsp_location(self, location):
        path = location.path
        if path is None or not path.exists() or not path.is_file():
            self.statusBar().showMessage("LSP location указывает на недоступный файл", 3000)
            return
        self.open_file_at_line(path, int(location.line) + 1, int(location.character))

    def _show_lsp_locations(self, title: str, locations):
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.resize(760, 460)
        layout = QVBoxLayout(dialog)
        hint = QLabel(f"Найдено: {len(locations)}. Двойной клик открывает место.")
        hint.setObjectName("Muted")
        tree = QTreeWidget()
        tree.setColumnCount(3)
        tree.setHeaderLabels(["Файл", "Строка", "Путь"])
        tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        for location in locations:
            path = location.path
            if path is None:
                continue
            item = QTreeWidgetItem([path.name, f"{location.line + 1}:{location.character + 1}", str(path)])
            item.setData(0, Qt.ItemDataRole.UserRole, json.dumps({"path": str(path), "line": location.line + 1, "column": location.character}))
            tree.addTopLevelItem(item)
        def open_item(item, _column=0):
            raw = item.data(0, Qt.ItemDataRole.UserRole)
            try:
                payload = json.loads(raw) if isinstance(raw, str) else {}
                path = Path(str(payload.get("path") or ""))
                self.open_file_at_line(path, int(payload.get("line", 1)), int(payload.get("column", 0)))
                dialog.accept()
            except Exception:
                return
        tree.itemDoubleClicked.connect(open_item)
        close_button = QPushButton("Закрыть")
        close_button.clicked.connect(dialog.accept)
        layout.addWidget(hint)
        layout.addWidget(tree, 1)
        layout.addWidget(close_button)
        dialog.setStyleSheet(self.styleSheet())
        dialog.exec()

    def _editor_for_path(self, path: Path):
        try:
            target = path.resolve()
        except OSError:
            target = path
        for editor in self.all_editors():
            if not editor.file_path:
                continue
            try:
                candidate = Path(editor.file_path).resolve()
            except OSError:
                candidate = Path(editor.file_path)
            if candidate == target:
                return editor
        return None

    def _apply_lsp_edits_to_editor(self, editor: CodeEditor, edits):
        cursor = editor.textCursor()
        cursor.beginEditBlock()
        try:
            ordered = sorted(edits, key=lambda edit: (edit.start_line, edit.start_character, edit.end_line, edit.end_character), reverse=True)
            for edit in ordered:
                start_pos = self._lsp_cursor_position(editor, edit.start_line, edit.start_character)
                end_pos = self._lsp_cursor_position(editor, edit.end_line, edit.end_character)
                edit_cursor = QTextCursor(editor.document())
                edit_cursor.setPosition(start_pos)
                edit_cursor.setPosition(max(start_pos, end_pos), QTextCursor.MoveMode.KeepAnchor)
                edit_cursor.insertText(edit.new_text)
        finally:
            cursor.endEditBlock()
        editor.document().setModified(True)

    def _apply_lsp_workspace_rename(self, edits):
        if not edits:
            self.statusBar().showMessage("LSP: rename не вернул изменений", 2200)
            return
        grouped = {}
        for edit in edits:
            grouped.setdefault(edit.uri, []).append(edit)
        prepared = []
        for uri, uri_edits in grouped.items():
            path = uri_to_path(uri)
            if path is None or not self._path_belongs_to_active_project(path):
                QMessageBox.warning(self, "Rename Symbol", "LSP попытался изменить файл вне активного проекта. Rename отменён целиком.")
                return
            editor = self._editor_for_path(path)
            if editor is not None:
                text = editor.toPlainText()
                encoding = editor.file_encoding or "utf-8"
            else:
                try:
                    raw_bytes = path.read_bytes()
                    try:
                        text = raw_bytes.decode("utf-8")
                        encoding = "utf-8"
                    except UnicodeDecodeError:
                        text = raw_bytes.decode("cp1251")
                        encoding = "cp1251"
                except (OSError, UnicodeDecodeError) as exc:
                    QMessageBox.warning(self, "Rename Symbol", f"Не удалось подготовить файл {path}:\n{exc}")
                    return
            try:
                new_text = apply_text_edits(text, uri_edits)
            except ValueError as exc:
                QMessageBox.warning(self, "Rename Symbol", f"LSP вернул конфликтующие edits для {path.name}:\n{exc}")
                return
            prepared.append((path, editor, encoding, text, new_text, uri_edits))
        answer = QMessageBox.question(
            self,
            "Rename Symbol",
            f"Применить rename?\n\nФайлов: {len(prepared)}\nИзменений: {len(edits)}\n\nОткрытые файлы останутся несохранёнными, чтобы rename можно было отменить через Undo.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        closed = [item for item in prepared if item[1] is None]
        staged = []
        try:
            for path, _editor, encoding, _old_text, new_text, _uri_edits in closed:
                backup = path.read_bytes()
                fd, temp_name = tempfile.mkstemp(
                    prefix=path.name + ".astra-rename-",
                    suffix=".tmp",
                    dir=str(path.parent),
                )
                temp = Path(temp_name)
                try:
                    os.close(fd)
                    temp.write_bytes(new_text.encode(encoding))
                    try:
                        shutil.copymode(path, temp)
                    except OSError:
                        pass
                except Exception:
                    try:
                        os.close(fd)
                    except OSError:
                        pass
                    temp.unlink(missing_ok=True)
                    raise
                staged.append((path, temp, backup))
            replaced = []
            try:
                for path, temp, backup in staged:
                    os.replace(temp, path)
                    replaced.append((path, backup))
            except OSError:
                for path, backup in reversed(replaced):
                    try:
                        path.write_bytes(backup)
                    except OSError:
                        pass
                raise
        except (OSError, UnicodeError) as exc:
            for _path, temp, _backup in staged:
                try:
                    temp.unlink(missing_ok=True)
                except OSError:
                    pass
            QMessageBox.critical(self, "Rename Symbol", f"Не удалось записать rename без риска частичного изменения проекта:\n{exc}")
            return
        for _path, editor, _encoding, _old_text, _new_text, uri_edits in prepared:
            if editor is not None:
                self._apply_lsp_edits_to_editor(editor, uri_edits)
        self.refresh_project_tree()
        self.statusBar().showMessage(f"Rename применён: {len(edits)} изменений в {len(prepared)} файлах", 3500)

    def _symbol_kind_name(self, kind: int) -> str:
        names = {
            1: "File", 2: "Module", 3: "Namespace", 4: "Package", 5: "Class", 6: "Method",
            7: "Property", 8: "Field", 9: "Constructor", 10: "Enum", 11: "Interface", 12: "Function",
            13: "Variable", 14: "Constant", 15: "String", 16: "Number", 17: "Boolean", 18: "Array",
            19: "Object", 20: "Key", 21: "Null", 22: "EnumMember", 23: "Struct", 24: "Event",
            25: "Operator", 26: "TypeParameter",
        }
        return names.get(int(kind), "Symbol")

    def _populate_lsp_outline(self, symbols, token):
        tree = getattr(self, "lsp_outline_tree", None)
        if tree is None:
            return
        tree.clear()
        path = str(token.get("path") or "") if isinstance(token, dict) else ""
        stack = []
        for symbol in symbols:
            item = QTreeWidgetItem([symbol.name, self._symbol_kind_name(symbol.kind), str(symbol.line + 1)])
            item.setToolTip(0, symbol.detail or symbol.name)
            item.setData(0, Qt.ItemDataRole.UserRole, json.dumps({
                "path": path,
                "line": int(symbol.line) + 1,
                "column": int(symbol.character),
            }, ensure_ascii=False))
            while len(stack) > symbol.depth:
                stack.pop()
            if symbol.depth > 0 and stack:
                stack[-1].addChild(item)
            else:
                tree.addTopLevelItem(item)
            if len(stack) == symbol.depth:
                stack.append(item)
            elif len(stack) > symbol.depth:
                stack[symbol.depth] = item
        tree.expandToDepth(1)
        if not symbols:
            tree.addTopLevelItem(QTreeWidgetItem(["Символы не найдены", "", ""]))

    def _open_lsp_outline_item(self, item, _column=0):
        if item is None:
            return
        raw = item.data(0, Qt.ItemDataRole.UserRole)
        if not isinstance(raw, str):
            return
        try:
            payload = json.loads(raw)
            path = Path(str(payload.get("path") or ""))
            line = int(payload.get("line", 1))
            column = int(payload.get("column", 0))
        except (ValueError, TypeError, json.JSONDecodeError):
            return
        if path.exists():
            self.open_file_at_line(path, line, column)

    def _on_lsp_diagnostics_published(self, language: str, uri: str, diagnostics):
        self.write_log(f"[LSP:{language}] diagnostics {len(diagnostics or [])}: {uri}")
        self._refresh_problems_panel()

    def _on_lsp_diagnostics_reset(self):
        self._refresh_problems_panel()

    def _problem_severity_visible(self, severity: int) -> bool:
        if severity == 1:
            return bool(getattr(self, "problems_errors_toggle", None) and self.problems_errors_toggle.isChecked())
        if severity == 2:
            return bool(getattr(self, "problems_warnings_toggle", None) and self.problems_warnings_toggle.isChecked())
        return bool(getattr(self, "problems_info_toggle", None) and self.problems_info_toggle.isChecked())

    def _refresh_problems_panel(self):
        if not hasattr(self, "problems_tree") or not hasattr(self, "lsp_manager"):
            return
        current_path = None
        editor = self.current_editor() if hasattr(self, "tabs") else None
        if editor and editor.file_path:
            try:
                current_path = Path(editor.file_path).resolve()
            except OSError:
                current_path = Path(editor.file_path)

        visible = []
        for diagnostic in self.lsp_manager.all_diagnostics():
            severity = int(getattr(diagnostic, "severity", 1))
            if not self._problem_severity_visible(severity):
                continue
            path = uri_to_path(getattr(diagnostic, "uri", ""))
            if path is None:
                continue
            try:
                resolved = path.resolve()
            except OSError:
                resolved = path
            if self.problems_current_file_toggle.isChecked() and current_path is not None and resolved != current_path:
                continue
            if self.problems_current_file_toggle.isChecked() and current_path is None:
                continue
            visible.append({
                "path": resolved,
                "line": int(getattr(diagnostic, "line", 0)),
                "character": int(getattr(diagnostic, "character", 0)),
                "severity": severity,
                "message": str(getattr(diagnostic, "message", "")),
                "source": str(getattr(diagnostic, "source", "") or "LSP"),
                "code": str(getattr(diagnostic, "code", "") or ""),
            })

        for diagnostics in self.quality_diagnostics.values():
            for diagnostic in diagnostics:
                severity = int(getattr(diagnostic, "severity", 2))
                if not self._problem_severity_visible(severity):
                    continue
                path = Path(getattr(diagnostic, "path", ""))
                try:
                    resolved = path.resolve()
                except OSError:
                    resolved = path
                if self.problems_current_file_toggle.isChecked() and current_path is not None and resolved != current_path:
                    continue
                if self.problems_current_file_toggle.isChecked() and current_path is None:
                    continue
                visible.append({
                    "path": resolved,
                    "line": int(getattr(diagnostic, "line", 0)),
                    "character": int(getattr(diagnostic, "character", 0)),
                    "severity": severity,
                    "message": str(getattr(diagnostic, "message", "")),
                    "source": str(getattr(diagnostic, "source", "") or "Linter"),
                    "code": str(getattr(diagnostic, "code", "") or ""),
                })

        visible.sort(key=lambda item: (
            str(item["path"]).lower(), item["line"], item["character"], item["severity"], item["message"]
        ))
        self.problems_tree.clear()
        groups: dict[str, QTreeWidgetItem] = {}
        severity_prefix = {1: "✕", 2: "⚠", 3: "•", 4: "·"}
        for diagnostic in visible:
            path = diagnostic["path"]
            key = str(path)
            group = groups.get(key)
            if group is None:
                group = QTreeWidgetItem([self._relative_project_label(path), "", "", ""])
                group.setToolTip(0, key)
                groups[key] = group
                self.problems_tree.addTopLevelItem(group)
            message = f"{severity_prefix.get(diagnostic['severity'], '•')} {diagnostic['message']}"
            source = diagnostic["source"]
            if diagnostic["code"]:
                source = f"{source} · {diagnostic['code']}"
            child = QTreeWidgetItem([
                message,
                path.name,
                f"{diagnostic['line'] + 1}:{diagnostic['character'] + 1}",
                source,
            ])
            payload = json.dumps({
                "path": key,
                "line": diagnostic["line"] + 1,
                "column": diagnostic["character"],
            }, ensure_ascii=False)
            child.setData(0, Qt.ItemDataRole.UserRole, payload)
            child.setToolTip(0, diagnostic["message"])
            group.addChild(child)

        for group in groups.values():
            group.setExpanded(True)
        count = len(visible)
        self.problems_summary_label.setText(f"Проблемы: {count}")
        page = getattr(self, "problems_page", None)
        if page is not None:
            index = self.bottom_tabs.indexOf(page)
            if index >= 0:
                self.bottom_tabs.setTabText(index, f"Проблемы ({count})")

    def _open_problem_item(self, item, _column=0):
        if item is None:
            return
        raw = item.data(0, Qt.ItemDataRole.UserRole)
        if not isinstance(raw, str) or not raw:
            return
        try:
            payload = json.loads(raw)
            path = Path(str(payload.get("path") or ""))
            line = max(1, int(payload.get("line", 1)))
            column = max(0, int(payload.get("column", 0)))
        except (ValueError, TypeError, json.JSONDecodeError):
            return
        if not path.exists() or not path.is_file():
            self.statusBar().showMessage(f"Файл диагностики больше недоступен: {path}", 4000)
            return
        self.open_file_at_line(path, line, column)
        self.statusBar().showMessage(f"Переход к диагностике: {path.name}:{line}:{column + 1}", 3000)

    def _relative_project_label(self, path: Path) -> str:
        for root in self._project_search_roots():
            try:
                return str(path.resolve().relative_to(root.resolve()))
            except (OSError, ValueError):
                continue
        return str(path)

    def open_file_at_line(self, path: Path, line_number: int = 1, column: int = 0):
        self.open_file(Path(path))
        editor = self.current_editor()
        if not editor:
            return
        block = editor.document().findBlockByNumber(max(0, int(line_number) - 1))
        if not block.isValid():
            return
        cursor = QTextCursor(block)
        cursor.setPosition(min(block.position() + max(0, int(column)), block.position() + max(0, block.length() - 1)))
        editor.setTextCursor(cursor)
        editor.centerCursor()
        editor.setFocus()

    def open_quick_open(self):
        files = list(self._iter_project_text_files(max_files=2500))
        dialog = QDialog(self)
        dialog.setWindowTitle("Quick Open · Ctrl+P")
        dialog.resize(760, 560)
        layout = QVBoxLayout(dialog)
        search = QLineEdit()
        search.setObjectName("ConsoleInput")
        search.setPlaceholderText("Введите часть имени или пути файла…")
        results = QTreeWidget()
        results.setHeaderHidden(True)
        layout.addWidget(search)
        layout.addWidget(results, 1)

        def refill(text=""):
            needle = (text or "").strip().lower()
            results.clear()
            shown = 0
            for path in files:
                label = self._relative_project_label(path)
                if needle and needle not in label.lower() and needle not in path.name.lower():
                    continue
                item = QTreeWidgetItem([label])
                item.setToolTip(0, str(path))
                item.setData(0, Qt.ItemDataRole.UserRole, str(path))
                results.addTopLevelItem(item)
                shown += 1
                if shown >= 250:
                    break
            if results.topLevelItemCount():
                results.setCurrentItem(results.topLevelItem(0))

        def open_selected(*_args):
            item = results.currentItem()
            if not item:
                return
            path = Path(str(item.data(0, Qt.ItemDataRole.UserRole)))
            dialog.accept()
            self.open_file(path)

        search.textChanged.connect(refill)
        search.returnPressed.connect(open_selected)
        results.itemDoubleClicked.connect(lambda _item, _column: open_selected())
        refill()
        dialog.setStyleSheet(self.styleSheet())
        search.setFocus()
        dialog.exec()

    def open_project_search(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Поиск по проекту · Ctrl+Shift+F")
        dialog.resize(980, 680)
        layout = QVBoxLayout(dialog)
        query = QLineEdit()
        query.setObjectName("ConsoleInput")
        query.setPlaceholderText("Что найти…")
        replace = QLineEdit()
        replace.setObjectName("ConsoleInput")
        replace.setPlaceholderText("Замена (необязательно)…")
        options = QHBoxLayout()
        case_box = QCheckBox("Учитывать регистр")
        regex_box = QCheckBox("Regex")
        search_btn = QPushButton("Найти")
        replace_btn = QPushButton("Заменить всё найденное")
        options.addWidget(case_box)
        options.addWidget(regex_box)
        options.addStretch(1)
        options.addWidget(search_btn)
        options.addWidget(replace_btn)
        results = QTreeWidget()
        results.setColumnCount(3)
        results.setHeaderLabels(["Файл", "Строка", "Совпадение"])
        results.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        results.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        results.header().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        status = QLabel("Готово")
        status.setObjectName("Muted")
        layout.addWidget(query)
        layout.addWidget(replace)
        layout.addLayout(options)
        layout.addWidget(results, 1)
        layout.addWidget(status)
        state = {"match_count": 0, "target_paths": [], "signature": None}

        def signature():
            return (query.text(), bool(case_box.isChecked()), bool(regex_box.isChecked()))

        def build_pattern():
            text = query.text()
            if not text:
                return None
            flags = 0 if case_box.isChecked() else re.IGNORECASE
            try:
                return re.compile(text if regex_box.isChecked() else re.escape(text), flags)
            except re.error as exc:
                QMessageBox.warning(dialog, "Regex", f"Некорректное регулярное выражение:\n{exc}")
                return None

        def read_text(path: Path):
            try:
                return path.read_text(encoding="utf-8"), "utf-8"
            except UnicodeDecodeError:
                try:
                    return path.read_text(encoding="cp1251"), "cp1251"
                except (OSError, UnicodeDecodeError):
                    return None, None
            except OSError:
                return None, None

        def run_search():
            pattern = build_pattern()
            if pattern is None:
                state.update({"match_count": 0, "target_paths": [], "signature": None})
                return False
            results.clear()
            status.setText("Поиск…")
            search_btn.setEnabled(False)
            replace_btn.setEnabled(False)
            QApplication.processEvents()
            match_count = 0
            file_count = 0
            shown = 0
            target_paths = []
            try:
                for file_index, path in enumerate(self._iter_project_text_files(max_files=None), start=1):
                    text, _encoding = read_text(path)
                    if text is None:
                        continue
                    local_found = False
                    # Search the same whole-file text that Replace All later edits.
                    # This keeps regex anchors/multiline expressions consistent
                    # between the result count and the actual replacement.
                    line_starts = [0]
                    line_starts.extend(index + 1 for index, char in enumerate(text) if char == "\n")
                    for match in pattern.finditer(text):
                        match_count += 1
                        local_found = True
                        if shown < 1500:
                            start = match.start()
                            line_index = max(0, bisect_right(line_starts, start) - 1)
                            line_no = line_index + 1
                            line_start = line_starts[line_index]
                            line_end = text.find("\n", line_start)
                            if line_end < 0:
                                line_end = len(text)
                            preview = text[line_start:line_end].rstrip("\r").strip()[:500]
                            column = max(0, start - line_start)
                            item = QTreeWidgetItem([self._relative_project_label(path), str(line_no), preview])
                            item.setToolTip(0, str(path))
                            item.setData(0, Qt.ItemDataRole.UserRole, {"path": str(path), "line": line_no, "column": column})
                            results.addTopLevelItem(item)
                            shown += 1
                    if local_found:
                        file_count += 1
                        target_paths.append(path)
                    if file_index % 50 == 0:
                        status.setText(f"Поиск… файлов: {file_index}, совпадений: {match_count}")
                        QApplication.processEvents()
            finally:
                search_btn.setEnabled(True)
                replace_btn.setEnabled(True)
            state.update({"match_count": match_count, "target_paths": target_paths, "signature": signature()})
            suffix = " · показаны первые 1500" if match_count > 1500 else ""
            status.setText(f"Найдено: {match_count} совпадений в {file_count} файлах{suffix}")
            return True

        def invalidate_search_state(*_args):
            if state.get("signature") is not None and state.get("signature") != signature():
                state.update({"match_count": 0, "target_paths": [], "signature": None})
                status.setText("Параметры поиска изменены — выполни поиск заново")

        def open_result(item, _column=0):
            data = item.data(0, Qt.ItemDataRole.UserRole) or {}
            if isinstance(data, dict) and data.get("path"):
                self.open_file_at_line(Path(data["path"]), int(data.get("line", 1)), int(data.get("column", 0)))

        def replace_all():
            # Always rescan with the current query/options so replacement can never
            # operate on stale result paths from a previous search.
            if not run_search():
                return
            match_count = int(state.get("match_count") or 0)
            target_paths = [Path(path) for path in state.get("target_paths") or []]
            if not match_count or not target_paths:
                QMessageBox.information(dialog, "Замена", "Совпадения для текущего поиска не найдены.")
                return
            target_resolved = set()
            for path in target_paths:
                try:
                    target_resolved.add(path.resolve())
                except OSError:
                    target_resolved.add(path)
            modified_open = []
            for editor in self.all_editors():
                if editor.file_path and editor.document().isModified():
                    try:
                        editor_path = Path(editor.file_path).resolve()
                    except OSError:
                        editor_path = Path(editor.file_path)
                    if editor_path in target_resolved:
                        modified_open.append(editor.file_path.name)
            if modified_open:
                QMessageBox.warning(dialog, "Замена", "Замена остановлена: среди целевых файлов есть несохранённые вкладки:\n" + "\n".join(modified_open[:10]))
                return
            answer = QMessageBox.question(
                dialog,
                "Заменить в проекте",
                f"Заменить {match_count} найденных совпадений в {len(target_paths)} файлах?\n\nЭто изменит файлы на диске.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
            pattern = build_pattern()
            if pattern is None:
                return
            replacement = replace.text()

            # Phase 1: calculate every edit before touching disk. This prevents a
            # bad regex replacement or a CP1251 encoding failure from leaving a
            # half-updated project.
            pending_changes = []
            convert_to_utf8 = []
            try:
                for path in target_paths:
                    original, encoding = read_text(path)
                    if original is None or encoding is None:
                        continue
                    if regex_box.isChecked():
                        updated, count = pattern.subn(replacement, original)
                    else:
                        # Lambda keeps literal replacement text literal (no backrefs).
                        updated, count = pattern.subn(lambda _m: replacement, original)
                    if not count or updated == original:
                        continue
                    target_encoding = encoding
                    try:
                        updated.encode(encoding)
                    except UnicodeEncodeError:
                        target_encoding = "utf-8"
                        convert_to_utf8.append(path)
                    pending_changes.append((path, updated, count, target_encoding))
            except re.error as exc:
                QMessageBox.warning(dialog, "Regex", f"Некорректная строка замены для регулярного выражения:\n{exc}")
                return

            if not pending_changes:
                QMessageBox.information(dialog, "Замена", "После пересчёта изменений для записи не найдено.")
                return

            if convert_to_utf8:
                names = "\n".join(self._relative_project_label(path) for path in convert_to_utf8[:8])
                extra = f"\n… и ещё {len(convert_to_utf8) - 8}" if len(convert_to_utf8) > 8 else ""
                answer = QMessageBox.question(
                    dialog,
                    "Кодировка файлов",
                    f"В {len(convert_to_utf8)} файлах CP1251 новая строка не помещается в исходную кодировку. "
                    f"Преобразовать эти файлы в UTF-8 и продолжить?\n\n{names}{extra}",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if answer != QMessageBox.StandardButton.Yes:
                    return

            # Phase 2: write only after validation/confirmation has completed.
            changed = 0
            replacements = 0
            failed = []
            changed_texts = {}
            for path, updated, count, target_encoding in pending_changes:
                try:
                    path.write_text(updated, encoding=target_encoding)
                except (OSError, UnicodeError) as exc:
                    failed.append(f"{self._relative_project_label(path)}: {exc}")
                    continue
                changed += 1
                replacements += count
                try:
                    key = path.resolve()
                except OSError:
                    key = path
                changed_texts[key] = (updated, target_encoding)

            for editor in self.all_editors():
                if not editor.file_path or editor.document().isModified():
                    continue
                try:
                    resolved = Path(editor.file_path).resolve()
                except OSError:
                    resolved = Path(editor.file_path)
                if resolved in changed_texts:
                    updated, target_encoding = changed_texts[resolved]
                    cursor_pos = editor.textCursor().position()
                    editor.setPlainText(updated)
                    editor.file_encoding = target_encoding
                    cursor = editor.textCursor()
                    cursor.setPosition(min(cursor_pos, len(updated)))
                    editor.setTextCursor(cursor)
                    editor.document().setModified(False)

            self.refresh_project_tree()
            if failed:
                QMessageBox.warning(
                    dialog,
                    "Замена завершена частично",
                    f"Изменено {changed} файлов, но {len(failed)} файлов записать не удалось:\n" + "\n".join(failed[:8]),
                )
            status.setText(f"Заменено: {replacements} совпадений в {changed} файлах" + (f" · ошибок записи: {len(failed)}" if failed else ""))
            run_search()

        search_btn.clicked.connect(run_search)
        query.returnPressed.connect(run_search)
        replace_btn.clicked.connect(replace_all)
        results.itemDoubleClicked.connect(open_result)
        query.textChanged.connect(invalidate_search_state)
        case_box.toggled.connect(invalidate_search_state)
        regex_box.toggled.connect(invalidate_search_state)
        dialog.setStyleSheet(self.styleSheet())
        query.setFocus()
        dialog.exec()

    def open_project_doctor(self):
        root = Path(self.project_main_folder)
        dialog = QDialog(self)
        dialog.setWindowTitle("Project Doctor · StaffedUp Health")
        dialog.resize(1040, 720)
        layout = QVBoxLayout(dialog)

        summary = QLabel()
        summary.setWordWrap(True)
        tree = QTreeWidget()
        tree.setObjectName("ProjectHealthTree")
        tree.setColumnCount(4)
        tree.setHeaderLabels(["Статус", "Проверка", "Детали", "Исправление"])
        tree.setAlternatingRowColors(True)
        tree.setRootIsDecorated(True)
        tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        header = tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)

        buttons = QHBoxLayout()
        refresh_btn = QPushButton("Обновить")
        fix_btn = QPushButton("Исправить безопасное")
        close_btn = QPushButton("Закрыть")
        buttons.addWidget(refresh_btn)
        buttons.addWidget(fix_btn)
        buttons.addStretch(1)
        buttons.addWidget(close_btn)

        state = {"health": None}
        icons = {"ok": "✓", "warn": "⚠", "error": "✕", "info": "•"}

        def add_section(title: str) -> QTreeWidgetItem:
            item = QTreeWidgetItem(tree, ["", title, "", ""])
            item.setExpanded(True)
            return item

        def add_check(parent: QTreeWidgetItem, check) -> None:
            QTreeWidgetItem(
                parent,
                [icons.get(check.status, "•"), str(check.label), str(check.detail), "safe fix" if getattr(check, "fixable", False) else ""],
            )

        def refresh_view():
            tree.clear()
            checks = inspect_project(root)
            general = add_section("Astra / Environment")
            for check in checks:
                add_check(general, check)

            explicit = normalize_commands(self.project_commands)
            effective = self._effective_project_commands()
            commands_section = add_section("Project commands")
            for key in COMMAND_KEYS:
                source = "explicit" if explicit.get(key) else ("detected" if effective.get(key) else "missing")
                QTreeWidgetItem(
                    commands_section,
                    ["✓" if effective.get(key) else "•", key, effective.get(key) or "—", source],
                )

            health = inspect_staffedup_project(
                root,
                self.current_project_name,
                self.project_staffedup_meta,
                Path(self.current_project_config_path) if self.current_project_config_path else None,
            )
            state["health"] = health
            if health is None:
                staffed = add_section("StaffedUp Project Health")
                QTreeWidgetItem(staffed, ["•", "Профиль", "Проект не создан из StaffedUp template; применяются только общие проверки.", ""])
                fix_btn.setEnabled(False)
                summary.setText("Project Doctor: общие проверки. StaffedUp health profile не назначен этому проекту.")
            else:
                staffed = add_section(f"StaffedUp Project Health · {health.profile}")
                for check in health.checks:
                    add_check(staffed, check)
                fix_btn.setEnabled(health.fixable_count > 0)
                summary.setText(
                    f"StaffedUp profile: {health.profile} · ошибок: {health.error_count} · "
                    f"предупреждений: {health.warning_count} · безопасных исправлений: {health.fixable_count}. "
                    "Safe fix никогда не перезаписывает пользовательский код и не запускает package manager/network actions."
                )
            tree.expandAll()

        def apply_fixes():
            health = state.get("health")
            if health is None or health.fixable_count <= 0:
                return
            result = apply_safe_staffedup_fixes(
                root,
                self.current_project_name,
                self.project_staffedup_meta,
                Path(self.current_project_config_path) if self.current_project_config_path else None,
            )
            if self.current_project_config_path:
                try:
                    data = json.loads(Path(self.current_project_config_path).read_text(encoding="utf-8"))
                    if isinstance(data.get("staffedUp"), dict):
                        self.project_staffedup_meta = dict(data["staffedUp"])
                    if isinstance(data.get("commands"), dict):
                        self.project_commands = normalize_commands(data["commands"])
                except Exception as exc:
                    self.write_exception_log("Не удалось перечитать StaffedUp health config после safe fix", exc)
            self.refresh_project_tree()
            refresh_view()
            details = "\n".join(f"• {item}" for item in result.actions) or "Безопасных изменений не потребовалось."
            if result.warnings:
                details += "\n\nПредупреждения:\n" + "\n".join(f"• {item}" for item in result.warnings)
                QMessageBox.warning(dialog, "StaffedUp Project Health", details)
            else:
                QMessageBox.information(dialog, "StaffedUp Project Health", details)

        refresh_btn.clicked.connect(refresh_view)
        fix_btn.clicked.connect(apply_fixes)
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(summary)
        layout.addWidget(tree, 1)
        layout.addLayout(buttons)
        dialog.setStyleSheet(self.styleSheet())
        refresh_view()
        dialog.exec()

    def _ai_project_roots(self) -> list[ProjectRoot]:
        raw_roots = [("Основная папка", Path(self.project_main_folder))]
        for item in self.attached_project_folders:
            if isinstance(item, dict) and item.get("path"):
                raw_roots.append((str(item.get("alias") or Path(item["path"]).name or "Attached"), Path(item["path"])))
        return normalize_roots(raw_roots)

    def _ai_copy_text(self, text: str, message: str):
        QApplication.clipboard().setText(str(text))
        self.statusBar().showMessage(message, 3000)

    def _ai_selected_project_path(self) -> Path | None:
        item = self.project_tree.currentItem() if hasattr(self, "project_tree") else None
        if item is not None:
            data = item.data(0, Qt.ItemDataRole.UserRole) or {}
            raw = data.get("path") if isinstance(data, dict) else None
            if raw:
                return Path(str(raw))
        editor = self.current_editor()
        if editor and editor.file_path:
            return Path(editor.file_path)
        return None

    def _ai_copy_relative_path(self):
        path = self._ai_selected_project_path()
        roots = self._ai_project_roots()
        if path is None or not roots:
            QMessageBox.information(self, "AI Context", "Выбери файл/папку проекта или открой файл проекта.")
            return
        try:
            label = project_path_label(path, roots)
        except ValueError:
            QMessageBox.warning(self, "AI Context", "Выбранный путь находится вне активного проекта.")
            return
        self._ai_copy_text(label, f"Скопирован относительный путь: {label}")

    def _ai_copy_selection_with_lines(self):
        editor = self.current_editor()
        if not isinstance(editor, CodeEditor):
            QMessageBox.information(self, "AI Context", "Сначала открой файл в редакторе.")
            return
        cursor = editor.textCursor()
        if not cursor.hasSelection():
            QMessageBox.information(self, "AI Context", "Сначала выдели фрагмент кода.")
            return
        if editor.file_path:
            try:
                label = project_path_label(Path(editor.file_path), self._ai_project_roots())
            except ValueError:
                label = Path(editor.file_path).name
        else:
            label = editor.untitled_name
        try:
            start_cursor = QTextCursor(editor.document())
            start_cursor.setPosition(cursor.selectionStart())
            formatted = format_selected_text_with_line_numbers(
                cursor.selectedText(), start_cursor.blockNumber() + 1, label, editor.language_name
            )
        except ValueError as exc:
            QMessageBox.information(self, "AI Context", str(exc))
            return
        self._ai_copy_text(formatted, "Выделение с номерами строк скопировано.")

    def _ai_copy_project_tree(self):
        roots = self._ai_project_roots()
        if not roots:
            QMessageBox.warning(self, "AI Context", "Нет доступного проекта для экспорта дерева.")
            return
        tree = build_project_tree(roots)
        self._ai_copy_text(f"```text\n{tree.rstrip()}\n```\n", "Дерево проекта скопировано.")

    def _ai_problem_records(self) -> list[dict]:
        roots = self._ai_project_roots()
        if not roots:
            return []
        records: list[dict] = []
        severity_names = {1: "error", 2: "warning", 3: "info", 4: "hint"}
        if hasattr(self, "lsp_manager"):
            for diagnostic in self.lsp_manager.all_diagnostics():
                path = uri_to_path(getattr(diagnostic, "uri", ""))
                if path is None:
                    continue
                try:
                    label = project_path_label(path, roots)
                except ValueError:
                    continue
                severity = int(getattr(diagnostic, "severity", 1))
                records.append({
                    "path": label,
                    "line": int(getattr(diagnostic, "line", 0)) + 1,
                    "column": int(getattr(diagnostic, "character", 0)) + 1,
                    "severity": severity_names.get(severity, "problem"),
                    "message": str(getattr(diagnostic, "message", "")),
                    "source": str(getattr(diagnostic, "source", "") or "LSP"),
                    "code": str(getattr(diagnostic, "code", "") or ""),
                })
        for diagnostics in getattr(self, "quality_diagnostics", {}).values():
            for diagnostic in diagnostics:
                path = Path(getattr(diagnostic, "path", ""))
                try:
                    label = project_path_label(path, roots)
                except ValueError:
                    continue
                severity = int(getattr(diagnostic, "severity", 2))
                records.append({
                    "path": label,
                    "line": int(getattr(diagnostic, "line", 0)) + 1,
                    "column": int(getattr(diagnostic, "character", 0)) + 1,
                    "severity": severity_names.get(severity, "problem"),
                    "message": str(getattr(diagnostic, "message", "")),
                    "source": str(getattr(diagnostic, "source", "") or "Linter"),
                    "code": str(getattr(diagnostic, "code", "") or ""),
                })
        records.sort(key=lambda item: (item["path"].casefold(), item["line"], item["column"], item["severity"], item["message"]))
        return records

    def _ai_copy_problems(self):
        text = format_problem_records(self._ai_problem_records())
        self._ai_copy_text(text + "\n", "Problems скопированы.")

    def _ai_confirm_output_export(self, kind: str) -> bool:
        answer = AstralMessageBox.question(
            self,
            "AI Context",
            f"{kind} может содержать токены, пароли, URL с ключами или другие секреты.\n\n"
            "Astra не умеет надёжно определить все секреты в произвольном выводе. Перед отправкой внешнему AI обязательно просмотри скопированный текст.\n\nПродолжить?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    def _ai_copy_terminal_output(self):
        text = self.terminal_console.toPlainText() if hasattr(self, "terminal_console") else ""
        if not text.strip():
            QMessageBox.information(self, "AI Context", "Терминал пока пуст.")
            return
        if not self._ai_confirm_output_export("Вывод терминала"):
            return
        self._ai_copy_text(truncate_output(text, 200_000), "Вывод терминала скопирован.")

    def _ai_copy_program_output(self):
        text = self.output_console.toPlainText() if hasattr(self, "output_console") else ""
        if not text.strip():
            QMessageBox.information(self, "AI Context", "Вывод программы пока пуст.")
            return
        if not self._ai_confirm_output_export("Вывод программы/задач"):
            return
        self._ai_copy_text(truncate_output(text, 200_000), "Вывод программы скопирован.")

    def _ai_context_candidate_paths(self) -> list[Path]:
        result: list[Path] = []
        seen: set[str] = set()
        for path in self._iter_project_text_files(max_files=3000):
            if path.name == CONTEXT_FILENAME or path.is_symlink():
                continue
            try:
                resolved = path.resolve()
            except OSError:
                continue
            key = str(resolved).casefold() if os.name == "nt" else str(resolved)
            if key in seen:
                continue
            seen.add(key)
            result.append(path)
        roots = self._ai_project_roots()
        return sorted(result, key=lambda path: project_path_label(path, roots).casefold())

    def open_ai_context_dialog(self):
        roots = self._ai_project_roots()
        if not roots:
            QMessageBox.warning(self, "AI Context", "Активная папка проекта недоступна.")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("AI Context · StaffedUp")
        dialog.resize(960, 760)
        layout = QVBoxLayout(dialog)

        title = QLabel("AI-adjacent workflow")
        title.setObjectName("SectionTitle")
        hint = QLabel(
            "Astra не отправляет данные в AI и не делает сетевых запросов. Здесь можно подготовить контекст для ChatGPT/Codex/Qwen и других инструментов. "
            "Файлы с типичными секретами, private keys и реальные .env блокируются. PROJECT_CONTEXT.md включает только файлы, которые ты явно отметил ниже."
        )
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(hint)

        quick = QHBoxLayout()
        copy_path_btn = QPushButton("Путь")
        copy_selection_btn = QPushButton("Выделение + строки")
        copy_tree_btn = QPushButton("Дерево")
        copy_problems_btn = QPushButton("Problems")
        copy_terminal_btn = QPushButton("Терминал")
        copy_output_btn = QPushButton("Вывод программы")
        for button in [copy_path_btn, copy_selection_btn, copy_tree_btn, copy_problems_btn, copy_terminal_btn, copy_output_btn]:
            quick.addWidget(button)
        layout.addLayout(quick)

        file_hint = QLabel(
            f"PROJECT_CONTEXT.md · отметь нужные файлы вручную (до 100 файлов, до {DEFAULT_MAX_FILE_BYTES // 1024} КБ на файл). "
            "Красные/секретные файлы недоступны для выбора."
        )
        file_hint.setObjectName("Muted")
        file_hint.setWordWrap(True)
        layout.addWidget(file_hint)

        files_tree = QTreeWidget()
        files_tree.setObjectName("AIContextFileTree")
        files_tree.setColumnCount(3)
        files_tree.setHeaderLabels(["Файл", "Размер", "Статус"])
        files_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        files_tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        files_tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        path_items: dict[str, QTreeWidgetItem] = {}
        for path in self._ai_context_candidate_paths():
            try:
                label = project_path_label(path, roots)
                size = path.stat().st_size
            except (OSError, ValueError):
                continue
            sensitive = is_sensitive_context_path(path)
            oversized = size > DEFAULT_MAX_FILE_BYTES
            status = "🔒 sensitive" if sensitive else ("слишком большой" if oversized else "")
            item = QTreeWidgetItem([label, f"{size / 1024:.1f} KB", status])
            item.setData(0, Qt.ItemDataRole.UserRole, str(path))
            if sensitive or oversized:
                item.setDisabled(True)
                item.setToolTip(0, "Этот файл не может быть встроен в PROJECT_CONTEXT.md.")
            else:
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(0, Qt.CheckState.Unchecked)
                path_items[str(path.resolve())] = item
            files_tree.addTopLevelItem(item)
        layout.addWidget(files_tree, 1)

        select_row = QHBoxLayout()
        select_open_btn = QPushButton("Отметить открытые файлы")
        clear_btn = QPushButton("Снять выбор")
        select_row.addWidget(select_open_btn)
        select_row.addWidget(clear_btn)
        select_row.addStretch(1)
        layout.addLayout(select_row)

        include_tree = QCheckBox("Добавить дерево проекта")
        include_tree.setChecked(True)
        include_problems = QCheckBox("Добавить текущие Problems")
        include_terminal = QCheckBox("Добавить вывод терминала (может содержать секреты)")
        include_output = QCheckBox("Добавить вывод программы/задач (может содержать секреты)")
        options = QHBoxLayout()
        options.addWidget(include_tree)
        options.addWidget(include_problems)
        options.addWidget(include_terminal)
        options.addWidget(include_output)
        layout.addLayout(options)

        status = QLabel("Ничего не отправляется автоматически. Перед передачей PROJECT_CONTEXT.md внешнему сервису просмотри файл.")
        status.setObjectName("Muted")
        status.setWordWrap(True)
        layout.addWidget(status)

        bottom = QHBoxLayout()
        generate_btn = QPushButton("Создать PROJECT_CONTEXT.md")
        generate_btn.setObjectName("PrimaryButton")
        close_btn = QPushButton("Закрыть")
        bottom.addWidget(generate_btn)
        bottom.addStretch(1)
        bottom.addWidget(close_btn)
        layout.addLayout(bottom)

        def checked_paths() -> list[Path]:
            paths: list[Path] = []
            for index in range(files_tree.topLevelItemCount()):
                item = files_tree.topLevelItem(index)
                if item.isDisabled() or item.checkState(0) != Qt.CheckState.Checked:
                    continue
                raw = item.data(0, Qt.ItemDataRole.UserRole)
                if raw:
                    paths.append(Path(str(raw)))
            return paths

        def select_open_files():
            open_paths = set()
            for editor in self.all_editors():
                if not editor.file_path:
                    continue
                try:
                    open_paths.add(str(Path(editor.file_path).resolve()))
                except OSError:
                    continue
            for key, item in path_items.items():
                item.setCheckState(0, Qt.CheckState.Checked if key in open_paths else Qt.CheckState.Unchecked)
            status.setText(f"Отмечено открытых файлов: {sum(1 for key in path_items if key in open_paths)}")

        def clear_selection():
            for item in path_items.values():
                item.setCheckState(0, Qt.CheckState.Unchecked)
            status.setText("Выбор файлов очищен.")

        def generate_context():
            selected = checked_paths()
            if not selected:
                QMessageBox.information(dialog, "AI Context", "Отметь хотя бы один файл проекта для PROJECT_CONTEXT.md.")
                return
            if (include_terminal.isChecked() or include_output.isChecked()) and not self._ai_confirm_output_export("Выбранный консольный вывод"):
                return
            target = Path(self.project_main_folder) / CONTEXT_FILENAME
            for editor in self.all_editors():
                if editor.file_path:
                    try:
                        same = Path(editor.file_path).resolve() == target.resolve()
                    except OSError:
                        same = False
                    if same:
                        QMessageBox.warning(dialog, "AI Context", "Закрой открытую вкладку PROJECT_CONTEXT.md перед повторной генерацией, чтобы не потерять несохранённый текст.")
                        return
            overwrite = False
            if target.exists():
                answer = AstralMessageBox.question(
                    dialog,
                    "AI Context",
                    "PROJECT_CONTEXT.md уже существует. Перезаписать его новой явно выбранной подборкой?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if answer != QMessageBox.StandardButton.Yes:
                    return
                overwrite = True
            try:
                content = build_project_context(
                    project_name=self.current_project_name,
                    roots=roots,
                    selected_paths=selected,
                    release_name=APP_VERSION,
                    include_tree=include_tree.isChecked(),
                    problem_records=self._ai_problem_records() if include_problems.isChecked() else None,
                    terminal_output=self.terminal_console.toPlainText() if include_terminal.isChecked() else None,
                    program_output=self.output_console.toPlainText() if include_output.isChecked() else None,
                )
                write_project_context(target, content, overwrite=overwrite)
            except (ValueError, OSError, FileExistsError) as exc:
                QMessageBox.warning(dialog, "AI Context", f"Не удалось создать PROJECT_CONTEXT.md:\n{exc}")
                return
            self.refresh_project_tree()
            self.open_file(target)
            status.setText(f"Создано: {target.name} · файлов: {len(selected)}")
            QMessageBox.information(
                dialog,
                "AI Context",
                "PROJECT_CONTEXT.md создан локально. Astra ничего не отправляла в сеть. Просмотри файл перед передачей внешнему AI/сервису.",
            )

        copy_path_btn.clicked.connect(self._ai_copy_relative_path)
        copy_selection_btn.clicked.connect(self._ai_copy_selection_with_lines)
        copy_tree_btn.clicked.connect(self._ai_copy_project_tree)
        copy_problems_btn.clicked.connect(self._ai_copy_problems)
        copy_terminal_btn.clicked.connect(self._ai_copy_terminal_output)
        copy_output_btn.clicked.connect(self._ai_copy_program_output)
        select_open_btn.clicked.connect(select_open_files)
        clear_btn.clicked.connect(clear_selection)
        generate_btn.clicked.connect(generate_context)
        close_btn.clicked.connect(dialog.accept)
        dialog.setStyleSheet(self.styleSheet())
        dialog.exec()

    def _detected_project_commands(self) -> dict[str, str]:
        return detect_project_commands(Path(self.project_main_folder))

    def _effective_project_commands(self) -> dict[str, str]:
        return merge_project_commands(self.project_commands, self._detected_project_commands())

    def _shell_quote(self, value: str) -> str:
        text = str(value)
        if os.name == "nt":
            return '"' + text.replace('"', '""') + '"'
        import shlex
        return shlex.quote(text)

    def _resolve_project_command(self, command: str) -> str | None:
        resolved = str(command or "").strip()
        if not resolved:
            return None
        if "{python-deps}" in resolved:
            return "{python-deps}"
        if "{python}" in resolved:
            python_exe, python_args = self._active_python_command()
            if not python_exe:
                QMessageBox.warning(self, "Project command", "Для команды проекта не найден Python.")
                return None
            python_token = self._shell_quote(python_exe)
            if python_args:
                python_token += " " + " ".join(self._shell_quote(arg) for arg in python_args)
            resolved = resolved.replace("{python}", python_token)
        if "{godot}" in resolved:
            godot = compiler_path("godot4.exe", "godot.exe", "godot4", "godot")
            if not godot:
                QMessageBox.warning(self, "Project command", "Godot 4 не найден в PATH. Project Doctor позже сможет предложить установку/настройку.")
                return None
            resolved = resolved.replace("{godot}", self._shell_quote(godot))
        if "{rojo}" in resolved:
            rojo = compiler_path("rojo.exe", "rojo")
            if not rojo:
                QMessageBox.warning(self, "Project command", "Rojo не найден в PATH.")
                return None
            resolved = resolved.replace("{rojo}", self._shell_quote(rojo))
        return resolved

    def _project_command_process(self, command: str) -> tuple[str, list[str]]:
        if os.name == "nt":
            return "cmd.exe", ["/d", "/s", "/c", command]
        shell = compiler_path("bash", "sh") or "/bin/sh"
        return shell, ["-lc", command]

    def _test_explorer_adapter_id(self) -> str:
        if not hasattr(self, "test_adapter_combo"):
            return ""
        index = self.test_adapter_combo.currentIndex()
        if index < 0:
            return ""
        value = self.test_adapter_combo.itemData(index, Qt.ItemDataRole.UserRole)
        return str(value or "")

    def _test_python_command(self) -> tuple[str | None, list[str]]:
        program, args = self._active_python_command()
        return program, list(args or [])

    def _refresh_test_adapters(self, preferred: str = ""):
        python_exe, _python_args = self._test_python_command()
        adapters = detect_test_adapters(Path(self.project_main_folder), python_exe)
        self.test_explorer_adapters = adapters
        if not hasattr(self, "test_adapter_combo"):
            return adapters
        current = preferred or self._test_explorer_adapter_id() or self.test_explorer_active_adapter
        self.test_adapter_combo.blockSignals(True)
        self.test_adapter_combo.clear()
        for adapter in adapters:
            label = adapter.display_name
            if not adapter.available:
                label += " · недоступен"
            self.test_adapter_combo.addItem(label, adapter.adapter_id)
            self.test_adapter_combo.setItemData(self.test_adapter_combo.count() - 1, adapter.reason, Qt.ItemDataRole.ToolTipRole)
        chosen = -1
        for index in range(self.test_adapter_combo.count()):
            if str(self.test_adapter_combo.itemData(index, Qt.ItemDataRole.UserRole) or "") == current:
                chosen = index
                break
        if chosen < 0 and self.test_adapter_combo.count():
            chosen = 0
        if chosen >= 0:
            self.test_adapter_combo.setCurrentIndex(chosen)
            self.test_explorer_active_adapter = str(self.test_adapter_combo.itemData(chosen, Qt.ItemDataRole.UserRole) or "")
        else:
            self.test_explorer_active_adapter = ""
        self.test_adapter_combo.blockSignals(False)
        self.btn_test_run_all.setEnabled(bool(chosen >= 0))
        self.btn_test_run_selected.setEnabled(False)
        if not adapters:
            self.test_summary_label.setText("Тестовые фреймворки не обнаружены. Можно использовать Test Project через команду проекта.")
        return adapters

    def open_test_explorer(self):
        if hasattr(self, "tests_page"):
            index = self.bottom_tabs.indexOf(self.tests_page)
            if index >= 0:
                self.bottom_tabs.setCurrentIndex(index)
        preferred = ""
        if self.test_explorer_last_run is not None:
            preferred = str(getattr(self.test_explorer_last_run, "adapter_id", "") or "")
        self._refresh_test_adapters(preferred)
        if self.test_explorer_last_run is not None and (not preferred or preferred == self._test_explorer_adapter_id()):
            self._render_test_result(self.test_explorer_last_run)
        else:
            self.discover_project_tests()

    def _on_test_adapter_changed(self, _index: int):
        self.test_explorer_active_adapter = self._test_explorer_adapter_id()
        self.discover_project_tests()

    def discover_project_tests(self):
        adapter_id = self._test_explorer_adapter_id()
        if not adapter_id:
            self.test_explorer_discovered = []
            self._render_test_nodes([], "Тесты: фреймворк не выбран")
            return
        try:
            nodes = discover_tests(Path(self.project_main_folder), adapter_id)
        except Exception as exc:
            self.write_exception_log("Test Explorer discovery failed", exc)
            self._render_test_nodes([], f"Ошибка обнаружения тестов: {exc}")
            return
        self.test_explorer_active_adapter = adapter_id
        self.test_explorer_discovered = nodes
        self._render_test_nodes(nodes, f"Обнаружено тестов: {len(nodes)}")
        adapter = next((item for item in self.test_explorer_adapters if item.adapter_id == adapter_id), None)
        self.btn_test_run_selected.setEnabled(bool(adapter and adapter.available and adapter.supports_selected and nodes))
        self.btn_test_run_all.setEnabled(bool(adapter and adapter.available))

    def _test_status_text(self, status: str) -> str:
        return {
            "passed": "✓ PASS",
            "failed": "✕ FAIL",
            "error": "! ERROR",
            "skipped": "– SKIP",
            "pending": "○ ожидает",
            "unknown": "?",
        }.get(str(status or ""), str(status or ""))

    def _render_test_nodes(self, nodes, summary: str = ""):
        if not hasattr(self, "test_tree"):
            return
        self.test_tree.clear()
        groups = {}
        for node in nodes or []:
            parent_key = str(getattr(node, "parent", "") or getattr(node, "path", "") or "Tests")
            parent_item = groups.get(parent_key)
            if parent_item is None:
                parent_label = parent_key
                try:
                    parent_path = Path(parent_key)
                    if parent_path.is_absolute():
                        try:
                            parent_label = parent_path.relative_to(Path(self.project_main_folder)).as_posix()
                        except ValueError:
                            parent_label = parent_path.name
                except Exception:
                    pass
                parent_item = QTreeWidgetItem([parent_label, "", "", "", ""])
                parent_item.setData(0, Qt.ItemDataRole.UserRole, "")
                self.test_tree.addTopLevelItem(parent_item)
                groups[parent_key] = parent_item
            path_text = str(getattr(node, "path", "") or "")
            file_text = ""
            if path_text:
                try:
                    file_text = Path(path_text).relative_to(Path(self.project_main_folder)).as_posix()
                except ValueError:
                    file_text = Path(path_text).name
            line = max(0, int(getattr(node, "line", 0) or 0))
            item = QTreeWidgetItem([
                str(getattr(node, "label", "test")),
                self._test_status_text(str(getattr(node, "status", "pending"))),
                file_text,
                str(line + 1) if path_text else "",
                str(getattr(node, "message", "") or getattr(node, "duration", "") or ""),
            ])
            item.setData(0, Qt.ItemDataRole.UserRole, str(getattr(node, "test_id", "") or ""))
            item.setData(1, Qt.ItemDataRole.UserRole, path_text)
            item.setData(2, Qt.ItemDataRole.UserRole, line)
            parent_item.addChild(item)
        for item in groups.values():
            item.setExpanded(True)
        self.test_summary_label.setText(summary or f"Тесты: {len(nodes or [])}")
        index = self.bottom_tabs.indexOf(self.tests_page) if hasattr(self, "tests_page") else -1
        if index >= 0:
            failed = sum(str(getattr(node, "status", "")) in {"failed", "error"} for node in (nodes or []))
            passed = sum(str(getattr(node, "status", "")) == "passed" for node in (nodes or []))
            suffix = f" ({passed}✓/{failed}✕)" if passed or failed else ""
            self.bottom_tabs.setTabText(index, "Тесты" + suffix)

    def _render_test_result(self, result):
        if result is None:
            self._render_test_nodes([], "Тесты: результатов пока нет")
            return
        stamp = str(getattr(result, "timestamp", "") or "")
        summary = str(getattr(result, "summary", "") or "")
        label = f"Последний запуск · {getattr(result, 'display_name', 'Tests')} · {summary}"
        if stamp:
            label += f" · {stamp}"
        self._render_test_nodes(getattr(result, "nodes", []) or [], label)

    def _open_test_tree_item(self, item: QTreeWidgetItem, _column: int):
        path_text = str(item.data(1, Qt.ItemDataRole.UserRole) or "")
        if not path_text:
            return
        path = Path(path_text)
        if not path.exists() or not path.is_file():
            self.statusBar().showMessage("Файл теста больше не существует", 3000)
            return
        line = max(0, int(item.data(2, Qt.ItemDataRole.UserRole) or 0))
        self.open_file(path)
        editor = self.current_editor()
        if not editor:
            return
        block = editor.document().findBlockByNumber(line)
        if block.isValid():
            cursor = QTextCursor(block)
            editor.setTextCursor(cursor)
            editor.centerCursor()
            editor.setFocus()

    def _unsaved_project_files(self) -> list[str]:
        result = []
        for editor in self.all_editors():
            if not isinstance(editor, CodeEditor) or not editor.document().isModified() or not editor.file_path:
                continue
            if self._path_belongs_to_current_project(editor.file_path):
                result.append(str(editor.file_path))
        return result

    def run_tests_from_explorer(self, selected: bool = False):
        if self.task_manager.has_active_task() or (self.run_process and self.run_process.state() != QProcess.ProcessState.NotRunning):
            QMessageBox.information(self, "Test Explorer", "Сначала дождись завершения текущей операции.")
            return
        adapter_id = self._test_explorer_adapter_id()
        if not adapter_id:
            QMessageBox.information(self, "Test Explorer", "Тестовый адаптер не выбран.")
            return
        adapter = next((item for item in self.test_explorer_adapters if item.adapter_id == adapter_id), None)
        if adapter is None or not adapter.available:
            QMessageBox.warning(self, "Test Explorer", (adapter.reason if adapter else "Тестовый адаптер недоступен.") or "Тестовый адаптер недоступен.")
            return
        dirty = self._unsaved_project_files()
        if dirty:
            QMessageBox.information(
                self,
                "Test Explorer",
                "Перед запуском тестов сохрани изменённые файлы проекта. Тестовый процесс выполняет версию с диска.\n\n" + "\n".join(dirty[:5]),
            )
            return
        selected_id = ""
        if selected:
            if not adapter.supports_selected:
                QMessageBox.information(self, "Test Explorer", "Этот адаптер безопасно поддерживает только запуск всего набора.")
                return
            current = self.test_tree.currentItem()
            selected_id = str(current.data(0, Qt.ItemDataRole.UserRole) or "") if current else ""
            if not selected_id:
                QMessageBox.information(self, "Test Explorer", "Выбери конкретный тест в дереве.")
                return
        python_exe, python_args = self._test_python_command()
        command = build_test_command(Path(self.project_main_folder), adapter_id, python_exe, selected_id)
        if command is None:
            QMessageBox.warning(self, "Test Explorer", "Не удалось построить безопасную команду запуска тестов.")
            return
        arguments = list(command.arguments)
        if adapter_id in {"pytest", "unittest"} and python_args:
            arguments = [*python_args, *arguments]
        if not self.test_explorer_discovered or self.test_explorer_active_adapter != adapter_id:
            self.test_explorer_discovered = discover_tests(Path(self.project_main_folder), adapter_id)
        self.test_explorer_active_adapter = adapter_id
        self.bottom_tabs.setCurrentIndex(0)
        self.output_console.clear()
        self.output_console.appendPlainText(
            f"▶ Test Explorer · {command.display_name}\nПроект: {self.project_main_folder}\nКоманда: {self._safe_command_preview(command.program, arguments)}\n"
        )
        self._start_process_task(
            f"test_explorer_{adapter_id}",
            f"Tests · {command.display_name}",
            command.program,
            arguments,
            command.workdir,
            {
                "mode": "test_explorer",
                "adapter_id": adapter_id,
                "display_name": command.display_name,
                "selected_id": selected_id,
                "stdout_chunks": [],
                "stderr_chunks": [],
                "target": "output",
                "indeterminate": True,
            },
            0,
            100,
            True,
        )

    def rerun_last_tests(self):
        if self.test_explorer_last_run is None:
            QMessageBox.information(self, "Test Explorer", "Предыдущего запуска тестов ещё нет.")
            return
        adapter_id = str(getattr(self.test_explorer_last_run, "adapter_id", "") or "")
        self._refresh_test_adapters(adapter_id)
        if self._test_explorer_adapter_id() != adapter_id:
            QMessageBox.warning(self, "Test Explorer", "Адаптер предыдущего запуска больше не доступен в этом проекте.")
            return
        self.run_tests_from_explorer(False)

    def open_git_source_control(self):
        if hasattr(self, "git_page"):
            index = self.bottom_tabs.indexOf(self.git_page)
            if index >= 0:
                self.bottom_tabs.setCurrentIndex(index)
        self.refresh_git_status()

    def _git_selected_path(self) -> str:
        if not hasattr(self, "git_tree"):
            return ""
        item = self.git_tree.currentItem()
        if item is None:
            return ""
        value = item.data(0, Qt.ItemDataRole.UserRole)
        return str(value or "")

    def _git_selected_original_path(self) -> str:
        if not hasattr(self, "git_tree"):
            return ""
        item = self.git_tree.currentItem()
        if item is None:
            return ""
        value = item.data(1, Qt.ItemDataRole.UserRole)
        return str(value or "")

    def _git_selected_entry(self):
        if self.git_state is None:
            return None
        path = self._git_selected_path()
        if not path:
            return None
        return next((entry for entry in self.git_state.entries if entry.path == path), None)

    def _update_git_controls(self):
        if not hasattr(self, "btn_git_refresh"):
            return
        busy = self.task_manager.has_active_task() if hasattr(self, "task_manager") else False
        state = self.git_state
        has_repo = state is not None and self.git_repo_root is not None
        entry = self._git_selected_entry() if has_repo else None
        self.btn_git_refresh.setEnabled(not busy)
        self.btn_git_diff.setEnabled(not busy and entry is not None)
        self.btn_git_diff_staged.setEnabled(not busy and entry is not None and entry.staged)
        self.btn_git_stage.setEnabled(not busy and entry is not None and (entry.unstaged or entry.untracked or entry.conflicted))
        self.btn_git_unstage.setEnabled(not busy and entry is not None and entry.staged)
        self.btn_git_stage_all.setEnabled(not busy and has_repo and any(item.unstaged or item.untracked or item.conflicted for item in state.entries))
        self.btn_git_unstage_all.setEnabled(not busy and has_repo and state.staged_count > 0)
        self.btn_git_commit.setEnabled(not busy and has_repo and state.staged_count > 0 and state.conflicted_count == 0)
        self.btn_git_pull.setEnabled(not busy and has_repo and bool(state.upstream) and not state.detached and not state.dirty)
        self.btn_git_push.setEnabled(not busy and has_repo and bool(state.upstream) and not state.detached)

    def _git_status_label(self, code: str) -> str:
        return {
            ".": "—",
            " ": "—",
            "M": "modified",
            "T": "type changed",
            "A": "added",
            "D": "deleted",
            "R": "renamed",
            "C": "copied",
            "U": "conflict",
            "?": "untracked",
        }.get(str(code or "."), str(code or "—"))

    def _render_git_state(self, state: GitRepositoryState | None, message: str = ""):
        if not hasattr(self, "git_tree"):
            return
        self.git_tree.clear()
        self.git_state = state
        if state is None:
            self.git_summary_label.setText(message or "Git: репозиторий не найден")
            self.git_summary_label.setToolTip("")
            self.git_diff_view.clear()
            self._update_git_controls()
            return

        self.git_summary_label.setToolTip(f"Корень Git-репозитория: {state.root}")
        branch = state.branch or ("detached" if state.detached else "unknown")
        tracking = ""
        if state.upstream:
            tracking = f" · {state.upstream} · ↑{state.ahead} ↓{state.behind}"
        conflict = f" · conflicts {state.conflicted_count}" if state.conflicted_count else ""
        repo_hint = ""
        try:
            if state.root.resolve() != Path(self.project_main_folder).resolve():
                repo_hint = f" · repo {state.root.name}"
        except OSError:
            pass
        self.git_summary_label.setText(
            f"Git: {branch}{tracking} · staged {state.staged_count} · working {state.unstaged_count}{conflict}{repo_hint}"
        )

        def sort_key(entry):
            return (
                0 if entry.conflicted else 1,
                0 if entry.staged else 1,
                0 if entry.unstaged else 1,
                entry.path.lower(),
            )

        for entry in sorted(state.entries, key=sort_key):
            labels = []
            if entry.conflicted:
                labels.append("CONFLICT")
            elif entry.untracked:
                labels.append("UNTRACKED")
            else:
                if entry.staged:
                    labels.append("STAGED")
                if entry.unstaged:
                    labels.append("MODIFIED")
            status_text = " + ".join(labels) or "CHANGED"
            display_path = entry.path
            if entry.original_path:
                display_path = f"{entry.original_path} → {entry.path}"
            item = QTreeWidgetItem([
                display_path,
                status_text,
                self._git_status_label(entry.index_status),
                self._git_status_label(entry.worktree_status),
            ])
            item.setData(0, Qt.ItemDataRole.UserRole, entry.path)
            item.setData(1, Qt.ItemDataRole.UserRole, entry.original_path)
            item.setToolTip(0, str(state.root / entry.path))
            self.git_tree.addTopLevelItem(item)
        if self.git_tree.topLevelItemCount():
            self.git_tree.setCurrentItem(self.git_tree.topLevelItem(0))
        elif not message:
            self.git_diff_view.setPlainText("Рабочее дерево чистое.")
        self._update_git_controls()

    def _open_git_tree_item(self, item: QTreeWidgetItem, _column: int = 0):
        if item is None or self.git_repo_root is None:
            return
        rel = str(item.data(0, Qt.ItemDataRole.UserRole) or "")
        if not rel:
            return
        path = self.git_repo_root / rel
        if path.exists() and path.is_file():
            self.open_file(path)
        else:
            self.statusBar().showMessage(f"Файл отсутствует в рабочем дереве: {rel}", 3500)

    def refresh_git_status(self):
        git = git_executable()
        self.git_available = bool(git)
        if not git:
            self.git_repo_root = None
            self._render_git_state(None, "Git: CLI не найден. Установи Git через установщик Astra.")
            return
        if self.task_manager.has_active_task():
            self.statusBar().showMessage("Git refresh подождёт: сейчас выполняется другая долгая операция.", 3500)
            return
        root = Path(self.project_main_folder)
        if not root.exists() or not root.is_dir():
            self._render_git_state(None, "Git: папка проекта недоступна")
            return
        try:
            command = probe_repository_command(root, git)
        except (RuntimeError, ValueError) as exc:
            self._render_git_state(None, f"Git: {exc}")
            return
        self._start_process_task(
            "git_probe",
            "Git · поиск репозитория",
            command.program,
            list(command.arguments),
            command.workdir,
            {"mode": "git_probe", "stdout_chunks": [], "stderr_chunks": [], "target": "output", "indeterminate": True},
            0,
            100,
            True,
        )

    def _start_git_status_task(self, repo_root: Path):
        try:
            command = status_command(repo_root)
        except RuntimeError as exc:
            self._render_git_state(None, f"Git: {exc}")
            return
        self.git_repo_root = Path(repo_root)
        self._start_process_task(
            "git_status",
            "Git · status",
            command.program,
            list(command.arguments),
            command.workdir,
            {"mode": "git_status", "repo_root": str(repo_root), "stdout_chunks": [], "stderr_chunks": [], "target": "output", "indeterminate": True},
            0,
            100,
            True,
        )

    def show_selected_git_diff(self, staged: bool = False):
        if self.git_repo_root is None or self.git_state is None:
            QMessageBox.information(self, "Git", "Сначала обнови статус Git.")
            return
        path = self._git_selected_path()
        if not path:
            QMessageBox.information(self, "Git", "Выбери изменённый файл.")
            return
        if self.task_manager.has_active_task():
            QMessageBox.information(self, "Git", "Сначала дождись завершения текущей операции.")
            return
        original_path = self._git_selected_original_path()
        try:
            command = diff_command(self.git_repo_root, path, staged, original_path=original_path)
        except RuntimeError as exc:
            QMessageBox.warning(self, "Git", str(exc))
            return
        self.git_last_diff_path = path
        self.git_last_diff_staged = bool(staged)
        self._start_process_task(
            "git_diff_staged" if staged else "git_diff_worktree",
            f"Git · {'staged ' if staged else ''}diff · {path}",
            command.program,
            list(command.arguments),
            command.workdir,
            {"mode": "git_diff", "path": path, "staged": bool(staged), "stdout_chunks": [], "stderr_chunks": [], "target": "output", "indeterminate": True},
            0,
            100,
            True,
        )

    def _start_git_mutation(self, action: str, command):
        if self.task_manager.has_active_task():
            QMessageBox.information(self, "Git", "Сначала дождись завершения текущей операции.")
            return False
        self.bottom_tabs.setCurrentIndex(0)
        self.output_console.appendPlainText(
            f"\n▶ Git · {action}\nРепозиторий: {self.git_repo_root}\nКоманда: {self._safe_command_preview(command.program, list(command.arguments))}\n"
        )
        return self._start_process_task(
            f"git_{action}",
            f"Git · {action}",
            command.program,
            list(command.arguments),
            command.workdir,
            {"mode": "git_mutation", "action": action, "stdout_chunks": [], "stderr_chunks": [], "target": "output", "indeterminate": True},
            0,
            100,
            True,
            environment={"GIT_TERMINAL_PROMPT": "0"},
        ) is not None

    def git_stage_selected(self, all_files: bool = False):
        if self.git_repo_root is None or self.git_state is None:
            QMessageBox.information(self, "Git", "Сначала обнови статус Git.")
            return
        if all_files:
            answer = QMessageBox.question(
                self,
                "Git Stage All",
                f"Добавить в index все изменения репозитория?\n\n{self.git_repo_root}\n\nЕсли проект открыт из вложенной папки монорепозитория, это включает изменения за пределами этой папки.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        path = None if all_files else self._git_selected_path()
        if not all_files and not path:
            QMessageBox.information(self, "Git", "Выбери файл для Stage.")
            return
        try:
            command = stage_command(self.git_repo_root, path, all_files=all_files)
        except (RuntimeError, ValueError) as exc:
            QMessageBox.warning(self, "Git", str(exc))
            return
        self._start_git_mutation("stage_all" if all_files else "stage", command)

    def git_unstage_selected(self, all_files: bool = False):
        if self.git_repo_root is None or self.git_state is None:
            QMessageBox.information(self, "Git", "Сначала обнови статус Git.")
            return
        if all_files:
            answer = QMessageBox.question(
                self,
                "Git Unstage All",
                "Убрать из index все staged-изменения? Файлы рабочего дерева останутся без изменений.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        path = None if all_files else self._git_selected_path()
        if not all_files and not path:
            QMessageBox.information(self, "Git", "Выбери файл для Unstage.")
            return
        original_path = "" if all_files else self._git_selected_original_path()
        try:
            command = unstage_command(self.git_repo_root, path, all_files=all_files, original_path=original_path)
        except (RuntimeError, ValueError) as exc:
            QMessageBox.warning(self, "Git", str(exc))
            return
        self._start_git_mutation("unstage_all" if all_files else "unstage", command)

    def git_commit(self):
        if self.git_repo_root is None or self.git_state is None:
            QMessageBox.information(self, "Git", "Сначала обнови статус Git.")
            return
        if self.git_state.conflicted_count:
            QMessageBox.warning(self, "Git", "Commit заблокирован: в репозитории есть нерешённые конфликты.")
            return
        if self.git_state.staged_count <= 0:
            QMessageBox.information(self, "Git", "Нет staged-изменений для commit.")
            return
        message = self.git_commit_message.text().strip()
        if not message:
            QMessageBox.information(self, "Git", "Введи сообщение commit.")
            return
        answer = QMessageBox.question(
            self,
            "Git commit",
            f"Создать commit из staged-изменений?\n\n{message}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            command = commit_command(self.git_repo_root, message)
        except (RuntimeError, ValueError) as exc:
            QMessageBox.warning(self, "Git", str(exc))
            return
        self._start_git_mutation("commit", command)

    def git_pull(self):
        if self.git_repo_root is None or self.git_state is None:
            QMessageBox.information(self, "Git", "Сначала обнови статус Git.")
            return
        if self.git_state.detached:
            QMessageBox.warning(self, "Git", "Pull заблокирован в detached HEAD.")
            return
        if not self.git_state.upstream:
            QMessageBox.warning(self, "Git", "Для текущей ветки не настроен upstream. Astra не назначает remote автоматически.")
            return
        if self.git_state.dirty:
            QMessageBox.warning(self, "Git", "Pull через GUI разрешён только при чистом рабочем дереве. Сначала commit/stash изменения.")
            return
        answer = QMessageBox.question(
            self,
            "Git pull",
            f"Получить изменения из {self.git_state.upstream}?\nAstra использует только pull --ff-only и не создаёт merge commit автоматически.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            command = pull_command(self.git_repo_root)
        except RuntimeError as exc:
            QMessageBox.warning(self, "Git", str(exc))
            return
        self._start_git_mutation("pull", command)

    def git_push(self):
        if self.git_repo_root is None or self.git_state is None:
            QMessageBox.information(self, "Git", "Сначала обнови статус Git.")
            return
        if self.git_state.detached:
            QMessageBox.warning(self, "Git", "Push заблокирован в detached HEAD.")
            return
        if not self.git_state.upstream:
            QMessageBox.warning(self, "Git", "Для текущей ветки не настроен upstream. Astra не выполняет push -u автоматически.")
            return
        answer = QMessageBox.question(
            self,
            "Git push",
            f"Отправить commits в {self.git_state.upstream}?\nForce push через Astra не используется.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            command = push_command(self.git_repo_root)
        except RuntimeError as exc:
            QMessageBox.warning(self, "Git", str(exc))
            return
        self._start_git_mutation("push", command)

    def edit_project_commands(self):
        detected = self._detected_project_commands()
        explicit = normalize_commands(self.project_commands)
        dialog = QDialog(self)
        dialog.setWindowTitle("Команды проекта")
        dialog.setModal(True)
        dialog.setMinimumWidth(620)
        layout = QVBoxLayout(dialog)
        hint = QLabel(
            "Явные команды сохраняются в astral.project.json. Пустое поле означает: использовать безопасно определённую команду Astra, если она есть."
        )
        hint.setWordWrap(True)
        hint.setObjectName("Muted")
        layout.addWidget(hint)
        edits = {}
        labels = {"run": "Run", "build": "Build", "test": "Test", "install": "Install"}
        for key in COMMAND_KEYS:
            label = QLabel(f"{labels[key]} · detected: {detected.get(key) or 'не определено'}")
            label.setObjectName("MiniLabel")
            edit = QLineEdit()
            edit.setObjectName("ConsoleInput")
            edit.setText(explicit.get(key, ""))
            edit.setPlaceholderText(detected.get(key) or "Команда не определена")
            layout.addWidget(label)
            layout.addWidget(edit)
            edits[key] = edit
        buttons = QHBoxLayout()
        save_btn = QPushButton("Сохранить")
        save_btn.setObjectName("PrimaryButton")
        cancel_btn = QPushButton("Отмена")
        buttons.addStretch(1)
        buttons.addWidget(cancel_btn)
        buttons.addWidget(save_btn)
        layout.addLayout(buttons)
        cancel_btn.clicked.connect(dialog.reject)
        save_btn.clicked.connect(dialog.accept)
        dialog.setStyleSheet(self.styleSheet())
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.project_commands = {key: edits[key].text().strip() for key in COMMAND_KEYS}
        self._save_current_project_state()
        self.statusBar().showMessage("Команды проекта сохранены", 2500)

    def run_project_command(self, kind: str):
        if kind not in COMMAND_KEYS:
            return
        if self.task_manager.has_active_task() or (self.run_process and self.run_process.state() != QProcess.ProcessState.NotRunning):
            self.output_console.appendPlainText("\n⚠ Уже выполняется другая операция. Дождись завершения или останови её.")
            return
        commands = self._effective_project_commands()
        command = commands.get(kind, "")
        if not command:
            QMessageBox.information(self, "Project command", f"Для действия {kind.upper()} команда не определена. Открой «Команды проекта» и задай её вручную.")
            return
        resolved = self._resolve_project_command(command)
        if resolved == "{python-deps}":
            self.install_project_python_dependencies()
            return
        if not resolved:
            return
        program, args = self._project_command_process(resolved)
        titles = {"run": "Run Project", "build": "Build Project", "test": "Test Project", "install": "Install Project"}
        self.bottom_tabs.setCurrentIndex(0)
        self.output_console.clear()
        self.output_console.appendPlainText(f"▶ {titles[kind]}\nПроект: {self.project_main_folder}\nКоманда: {resolved}\n")
        self._start_process_task(
            f"project_{kind}",
            titles[kind],
            program,
            args,
            self.project_main_folder,
            {"mode": "project_command", "kind": kind, "command": resolved, "target": "output", "indeterminate": True},
            10,
            100,
            True,
        )

    def _folder_entries_for_project(self) -> list[dict]:
        entries = [{"alias": "Основная папка", "path": str(self.project_main_folder), "kind": "main"}]
        for item in self.attached_project_folders:
            path = item.get("path", "") if isinstance(item, dict) else str(item)
            if not path:
                continue
            alias = item.get("alias") if isinstance(item, dict) else ""
            entries.append({"alias": alias or Path(path).name, "path": path, "kind": "attached"})
        return entries

    def _add_path_to_tree(self, parent_item: QTreeWidgetItem, path: Path, depth: int = 0, limit: list[int] | None = None):
        if limit is None:
            limit = [0]
        if limit[0] >= 5000:
            more = QTreeWidgetItem(["… показаны первые 5000 элементов; откройте папку в проводнике"])
            parent_item.addChild(more)
            return
        try:
            children = sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except OSError:
            warning = QTreeWidgetItem(["⚠ нет доступа"])
            parent_item.addChild(warning)
            return
        skipped_dirs = {
            "__pycache__", ".git", "build", "dist", "node_modules", ".venv", "venv",
            ".pytest_cache", ".mypy_cache", ".ruff_cache", ".next", ".cache", ".godot",
            "coverage", "vendor", "target", "bin", "obj", "out",
        }
        for child in children:
            if child.is_dir() and child.name in skipped_dirs:
                continue
            if child.is_file() and PROJECT_FILE_FILTERS:
                suffix = child.suffix.lower()
                # Derive the tree filter from the actual language registry so supported
                # extensions such as .cc, .cxx, .htm and .mjs cannot silently disappear.
                allowed = set(EXTENSION_TO_LANGUAGE) | {".txt", ".md", ".json", ".ini", ".cfg", ".conf"}
                lower_name = child.name.lower()
                special = (
                    lower_name in SPECIAL_FILENAMES_TO_LANGUAGE
                    or lower_name.startswith(("dockerfile", "containerfile", ".env"))
                    or lower_name in {"project.godot", ".gitignore"}
                )
                if suffix and suffix not in allowed and not special:
                    continue
            label = ("▾ " if child.is_dir() else "  ") + child.name
            item = QTreeWidgetItem([label])
            item.setToolTip(0, str(child))
            item.setData(0, Qt.ItemDataRole.UserRole, {"path": str(child), "kind": "folder" if child.is_dir() else "file"})
            parent_item.addChild(item)
            limit[0] += 1
            # The previous depth=4 cap produced folders that looked expandable
            # but had no children. Keep a defensive ceiling for pathological
            # trees while allowing normal Java/Gradle and web projects in full.
            if child.is_dir() and depth < 32:
                self._add_path_to_tree(item, child, depth + 1, limit)

    def refresh_project_tree(self):
        if not hasattr(self, "project_tree"):
            return
        self.project_tree.clear()
        title_item = QTreeWidgetItem([f"✦ {self.current_project_name}"])
        title_item.setToolTip(0, str(self.project_main_folder))
        title_item.setData(0, Qt.ItemDataRole.UserRole, {"kind": "project", "path": str(self.project_main_folder)})
        self.project_tree.addTopLevelItem(title_item)
        for entry in self._folder_entries_for_project():
            folder_path = Path(entry["path"])
            marker = "▣" if entry["kind"] == "main" else "⧉"
            root_item = QTreeWidgetItem([f"{marker} {entry['alias']}"])
            root_item.setToolTip(0, str(folder_path))
            root_item.setData(0, Qt.ItemDataRole.UserRole, {"path": str(folder_path), "kind": entry["kind"]})
            title_item.addChild(root_item)
            if folder_path.exists() and folder_path.is_dir():
                self._add_path_to_tree(root_item, folder_path)
            else:
                missing = QTreeWidgetItem(["⚠ папка недоступна"])
                missing.setToolTip(0, str(folder_path))
                root_item.addChild(missing)
        title_item.setExpanded(True)
        for i in range(title_item.childCount()):
            title_item.child(i).setExpanded(True)
        self.project_tree.doItemsLayout()
        self.project_tree.resizeColumnToContents(0)
        self.project_hint.setText("Двойной клик открывает файл · подключённые папки не удаляются с диска")

    def _selected_project_path(self) -> Path:
        item = self.project_tree.currentItem() if hasattr(self, "project_tree") else None
        if not item:
            return self.project_main_folder
        data = item.data(0, Qt.ItemDataRole.UserRole) or {}
        raw_path = data.get("path") if isinstance(data, dict) else None
        return Path(raw_path) if raw_path else self.project_main_folder

    def open_project_tree_item(self, item, _column=0):
        data = item.data(0, Qt.ItemDataRole.UserRole) or {}
        path_text = data.get("path") if isinstance(data, dict) else None
        if not path_text:
            return
        path = Path(path_text)
        if path.is_file():
            self.open_file(path)

    def create_project_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Создать проект · StaffedUp")
        dialog.setModal(True)
        dialog.setMinimumWidth(720)
        layout = QVBoxLayout(dialog)

        title = QLabel("Новый проект Astra Studio")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)

        hint = QLabel(
            "Выбери минимальный шаблон под задачу. Astra создаёт только файлы и конфигурацию проекта — "
            "зависимости и внешние инструменты не скачиваются без отдельного действия пользователя."
        )
        hint.setWordWrap(True)
        hint.setObjectName("Muted")
        layout.addWidget(hint)

        name_label = QLabel("Название проекта")
        name_edit = QLineEdit()
        name_edit.setObjectName("ConsoleInput")
        name_edit.setPlaceholderText("Например: StaffedUp Portfolio")
        layout.addWidget(name_label)
        layout.addWidget(name_edit)

        template_label = QLabel("Шаблон")
        template_combo = QComboBox()
        template_combo.setObjectName("LanguageCombo")
        for template_id, label in project_template_choices():
            template_combo.addItem(label, template_id)
        layout.addWidget(template_label)
        layout.addWidget(template_combo)

        location_label = QLabel("Родительская папка")
        location_row = QHBoxLayout()
        location_edit = QLineEdit(str(default_projects_dir()))
        location_edit.setObjectName("ConsoleInput")
        browse_btn = QPushButton("Обзор…")
        location_row.addWidget(location_edit, 1)
        location_row.addWidget(browse_btn)
        layout.addWidget(location_label)
        layout.addLayout(location_row)

        preview = QPlainTextEdit()
        preview.setReadOnly(True)
        preview.setMinimumHeight(250)
        preview.setObjectName("Console")
        self._apply_console_font(preview)
        layout.addWidget(preview, 1)

        button_row = QHBoxLayout()
        cancel_btn = QPushButton("Отмена")
        create_btn = QPushButton("Создать проект")
        create_btn.setObjectName("PrimaryButton")
        create_btn.setEnabled(False)
        button_row.addStretch(1)
        button_row.addWidget(cancel_btn)
        button_row.addWidget(create_btn)
        layout.addLayout(button_row)

        def selected_template_id() -> str:
            return str(template_combo.currentData(Qt.ItemDataRole.UserRole) or template_combo.currentData() or "empty")

        def update_preview():
            project_name = name_edit.text().strip() or "New Project"
            try:
                template = get_project_template(selected_template_id())
                files = rendered_template_files(template.template_id, project_name)
            except Exception as exc:
                preview.setPlainText(f"Не удалось подготовить шаблон: {exc}")
                create_btn.setEnabled(False)
                return
            required = ", ".join(template.required_tools) if template.required_tools else "нет обязательных внешних инструментов"
            recommended = ", ".join(template.recommended_tools) if template.recommended_tools else "—"
            command_lines = [f"  {key}: {value or '—'}" for key, value in template.commands.items()]
            file_lines = [f"  {path.as_posix()}" for path in files]
            preview.setPlainText(
                template.description
                + "\n\nОбязательные инструменты: " + required
                + "\nРекомендуемые: " + recommended
                + "\n\nProject commands:\n" + "\n".join(command_lines)
                + "\n\nБудут созданы файлы:\n" + "\n".join(file_lines)
            )
            create_btn.setEnabled(bool(name_edit.text().strip()) and bool(location_edit.text().strip()))

        def browse_location():
            chosen = QFileDialog.getExistingDirectory(
                dialog,
                "Где создавать проекты",
                location_edit.text().strip() or str(default_projects_dir()),
            )
            if chosen:
                location_edit.setText(chosen)
                update_preview()

        browse_btn.clicked.connect(browse_location)
        template_combo.currentIndexChanged.connect(lambda _index: update_preview())
        name_edit.textChanged.connect(lambda _text: update_preview())
        location_edit.textChanged.connect(lambda _text: update_preview())
        cancel_btn.clicked.connect(dialog.reject)
        create_btn.clicked.connect(dialog.accept)
        dialog.setStyleSheet(self.styleSheet())
        update_preview()

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        name = name_edit.text().strip()
        if not name:
            return
        requested_parent = Path(location_edit.text().strip()).expanduser()
        safe_start = default_projects_dir()
        parent = self._ensure_user_writable_folder(requested_parent, safe_start)
        if parent is None:
            return
        project_dir = Path(parent) / self._safe_project_folder_name(name)

        try:
            result = create_project_from_template(project_dir, name, selected_template_id(), APP_VERSION)
            config_data = json.loads(result.config_path.read_text(encoding="utf-8"))
            self.current_language_name = result.template.default_language
            if hasattr(self, "language_combo"):
                self.language_combo.blockSignals(True)
                self.language_combo.setCurrentText(self.current_language_name)
                self.language_combo.blockSignals(False)
            self._set_current_project(
                name,
                result.project_dir,
                result.config_path,
                [],
                "",
                config_data.get("commands") if isinstance(config_data.get("commands"), dict) else None,
                None,
                result.staffedup_metadata,
            )
            if result.entry_file is not None:
                self.open_file(result.entry_file)
            self._save_current_project_state()
            self.refresh_project_tree()
            required = ", ".join(result.template.required_tools) if result.template.required_tools else "нет"
            self.statusBar().showMessage(f"Создан StaffedUp-проект: {name}", 4000)
            QMessageBox.information(
                self,
                "Проект создан",
                f"Шаблон: {result.template.label}\nПапка: {result.project_dir}\nОбязательные внешние инструменты: {required}\n\n"
                "Astra не устанавливала зависимости автоматически. Используй Install Project / Project Doctor, когда будешь готов.",
            )
        except FileExistsError as exc:
            QMessageBox.warning(self, "Создать проект", f"Папка проекта уже содержит файлы и не будет перезаписана:\n{project_dir}\n\n{exc}")
        except PermissionError as exc:
            self.write_exception_log("Нет прав на создание проекта", exc)
            QMessageBox.warning(self, "Создать проект", self._permission_help_text(project_dir))
        except Exception as exc:
            self.write_exception_log("Ошибка создания проекта", exc)
            QMessageBox.critical(self, "Создать проект", f"Не удалось создать проект:\n{exc}")

    def open_project_dialog(self):
        start = str(Path(self.recent_projects[0]).parent if self.recent_projects else default_projects_dir())
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Открыть проект Astra Studio",
            start,
            "Astra project (astral.project.json *.project.json);;JSON (*.json);;All files (*.*)",
        )
        if not file_name:
            return
        self.open_project_config(Path(file_name))

    def _apply_project_preferences_from_payload(self, data: dict):
        """Restore project-scoped editor preferences saved in astral.project.json.

        Release 2.x already wrote these fields but did not restore them when a
        project was reopened. Treat them as optional migration data: malformed or
        unknown values are ignored and the current global settings stay intact.
        """
        language = data.get("defaultLanguage")
        if isinstance(language, str) and language in LANGUAGES:
            self.current_language_name = language
            if hasattr(self, "language_combo"):
                self.language_combo.blockSignals(True)
                self.language_combo.setCurrentText(language)
                self.language_combo.blockSignals(False)

        settings = data.get("settings")
        if not isinstance(settings, dict):
            return

        def int_value(key: str, current: int, minimum: int, maximum: int) -> int:
            raw = settings.get(key)
            if isinstance(raw, bool) or not isinstance(raw, int):
                return current
            return max(minimum, min(maximum, raw))

        self.editor_tab_size = int_value("tabSize", self.editor_tab_size, 1, 12)
        self.editor_indent_size = int_value("indentSize", self.editor_indent_size, 1, 12)
        if isinstance(settings.get("insertSpaces"), bool):
            self.editor_insert_spaces = settings["insertSpaces"]
        self.ui_font_size = int_value("uiFontSize", self.ui_font_size, 10, 22)
        self.editor_font_size = int_value("editorFontSize", self.editor_font_size, 8, 32)
        self.console_font_size = int_value("consoleFontSize", self.console_font_size, 8, 28)

        for attr, value in (
            ("editor_tab_size_slider", self.editor_tab_size),
            ("editor_indent_size_slider", self.editor_indent_size),
            ("ui_font_size_slider", self.ui_font_size),
            ("editor_font_size_slider", self.editor_font_size),
            ("console_font_size_slider", self.console_font_size),
        ):
            widget = getattr(self, attr, None)
            if widget is not None:
                widget.blockSignals(True)
                widget.setValue(value)
                widget.blockSignals(False)
        if hasattr(self, "editor_insert_spaces_toggle"):
            self.editor_insert_spaces_toggle.blockSignals(True)
            self.editor_insert_spaces_toggle.setChecked(self.editor_insert_spaces)
            self.editor_insert_spaces_toggle.blockSignals(False)

        self.update_indent_labels()
        self.apply_indent_settings_to_editors()
        self.update_font_labels()
        self.apply_font_settings(reapply_theme=True)

    def open_project_config(self, config_path: Path):
        try:
            config_path = Path(config_path)
            data = json.loads(config_path.read_text(encoding="utf-8"))
            raw_main_folder = Path(data.get("mainFolder") or config_path.parent)
            main_folder = raw_main_folder if raw_main_folder.is_absolute() else (config_path.parent / raw_main_folder)
            if not main_folder.exists() or not main_folder.is_dir():
                raise FileNotFoundError(f"Основная папка проекта не найдена: {main_folder}")
            name = data.get("projectName") or main_folder.name
            attached_raw = data.get("attachedFolders") if isinstance(data.get("attachedFolders"), list) else []
            attached = []
            for item in attached_raw:
                record = dict(item) if isinstance(item, dict) else {"path": str(item), "alias": ""}
                raw_path_text = str(record.get("path") or "").strip()
                if not raw_path_text:
                    continue
                raw_path = Path(raw_path_text)
                if not raw_path.is_absolute():
                    record["path"] = str(config_path.parent / raw_path)
                attached.append(record)
            self._set_current_project(
                name,
                main_folder,
                config_path,
                attached,
                str(data.get("pythonInterpreter") or ""),
                data.get("commands") if isinstance(data.get("commands"), dict) else None,
                data.get("testExplorerLastRun"),
                data.get("staffedUp") if isinstance(data.get("staffedUp"), dict) else None,
            )
            self._apply_project_preferences_from_payload(data)
            open_files = data.get("openFiles") if isinstance(data.get("openFiles"), list) else []
            missing = []
            for item in open_files[:12]:
                path = Path(str(item))
                if not path.is_absolute():
                    path = config_path.parent / path
                if path.exists() and path.is_file():
                    self.open_file(path)
                else:
                    missing.append(str(path))
            active_file = str(data.get("activeFile") or "")
            if active_file:
                active_raw = Path(active_file)
                if not active_raw.is_absolute():
                    active_raw = config_path.parent / active_raw
                try:
                    active_path = active_raw.resolve()
                except OSError:
                    active_path = active_raw
                for index in range(self.tabs.count()):
                    editor = self.tabs.widget(index)
                    if not isinstance(editor, CodeEditor) or not editor.file_path:
                        continue
                    try:
                        editor_path = Path(editor.file_path).resolve()
                    except OSError:
                        editor_path = Path(editor.file_path)
                    if editor_path == active_path:
                        self.tabs.setCurrentIndex(index)
                        break
            self.statusBar().showMessage(f"Открыт проект: {name}", 3000)
            if missing:
                QMessageBox.warning(self, "Проект открыт", "Некоторые файлы не найдены и не были открыты:\n" + "\n".join(missing[:5]))
        except Exception as exc:
            self.write_exception_log("Ошибка открытия проекта", exc)
            QMessageBox.critical(self, "Открыть проект", f"Не удалось открыть проект:\n{exc}")

    def add_attached_folder_dialog(self):
        folder = QFileDialog.getExistingDirectory(self, "Добавить подключённую папку", str(self.project_main_folder))
        if not folder:
            return
        folder_path = Path(folder)
        alias, ok = QInputDialog.getText(self, "Подключённая папка", "Название в проекте:", text=folder_path.name)
        if not ok:
            return
        record = {"alias": alias.strip() or folder_path.name, "path": str(folder_path)}
        if str(folder_path) not in [str(self.project_main_folder)] + [item.get("path", "") for item in self.attached_project_folders if isinstance(item, dict)]:
            self.attached_project_folders.append(record)
        self.refresh_project_tree()
        self._save_current_project_state()
        self._save_settings()
        self.statusBar().showMessage(f"Подключена папка: {record['alias']}", 2500)

    def remove_selected_attached_folder(self):
        item = self.project_tree.currentItem() if hasattr(self, "project_tree") else None
        if not item:
            return
        data = item.data(0, Qt.ItemDataRole.UserRole) or {}
        if not isinstance(data, dict) or data.get("kind") != "attached":
            QMessageBox.information(self, "Подключённые папки", "Выберите корневую подключённую папку. Основная папка проекта не удаляется.")
            return
        path_text = data.get("path", "")
        self.attached_project_folders = [item for item in self.attached_project_folders if item.get("path") != path_text]
        self.refresh_project_tree()
        self._save_current_project_state()
        self.statusBar().showMessage("Папка убрана из проекта, файлы на диске не удалялись", 3000)

    def open_selected_project_path_in_explorer(self):
        path = self._selected_project_path()
        if path.is_file():
            path = path.parent
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def create_folder_in_project(self):
        base = self._selected_project_path()
        if base.is_file():
            base = base.parent
        name, ok = QInputDialog.getText(self, "Новая папка", "Название папки:")
        if not ok or not name.strip():
            return
        try:
            base = self._ensure_user_writable_folder(base, default_projects_dir())
            if base is None:
                return
            target = base / self._safe_project_folder_name(name)
            target.mkdir(parents=True, exist_ok=True)
            self.refresh_project_tree()
            self._save_current_project_state()
            self.statusBar().showMessage(f"Создана папка: {target.name}", 2500)
        except Exception as exc:
            QMessageBox.critical(self, "Новая папка", f"Не удалось создать папку:\n{exc}")

    def _default_new_file_name(self, language: str) -> str:
        defaults = {
            "Python": "script.py",
            "C++": "example.cpp",
            "Java": "Main.java",
            "JavaScript": "script.js",
            "C#": "Program.cs",
            "HTML": "index.html",
            "CSS": "style.css",
            "SQL": "query.sql",
        }
        return defaults.get(language, "file" + LANGUAGES[language]["extension"])

    def create_new_file_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Создать файл")
        dialog.setModal(True)
        dialog.setMinimumWidth(560)
        dialog.setStyleSheet(self.styleSheet())

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)

        title = QLabel("НОВЫЙ ФАЙЛ")
        title.setObjectName("SectionTitle")
        hint = QLabel("Выберите язык и путь сохранения. После создания файл сразу откроется в редакторе.")
        hint.setObjectName("Muted")
        hint.setWordWrap(True)

        language_label = QLabel("Язык файла")
        language_label.setObjectName("MiniLabel")
        language_combo = QComboBox()
        language_combo.addItems(VISIBLE_LANGUAGES)
        language_combo.setCurrentText(
            self.current_language_name if self.current_language_name in VISIBLE_LANGUAGES else DEFAULT_LANGUAGE
        )

        folder_label = QLabel("Папка проекта")
        folder_label.setObjectName("MiniLabel")
        folder_combo = QComboBox()
        folder_entries = self._folder_entries_for_project()
        for entry in folder_entries:
            folder_combo.addItem(f"{entry['alias']} — {entry['path']}", entry['path'])

        path_label = QLabel("Место сохранения")
        path_label.setObjectName("MiniLabel")
        path_edit = QLineEdit()
        path_edit.setObjectName("ConsoleInput")
        path_edit.setText(str(self.workspace_dir / self._default_new_file_name(self.current_language_name)))

        browse_button = QPushButton("Выбрать путь")
        browse_button.setCursor(Qt.CursorShape.PointingHandCursor)
        create_button = QPushButton("Создать")
        create_button.setObjectName("PrimaryButton")
        create_button.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_button = QPushButton("Отмена")
        cancel_button.setCursor(Qt.CursorShape.PointingHandCursor)

        path_row = QHBoxLayout()
        path_row.addWidget(path_edit, 1)
        path_row.addWidget(browse_button)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(cancel_button)
        buttons.addWidget(create_button)

        def selected_base_folder():
            data = folder_combo.currentData()
            return Path(data) if data else self.project_main_folder

        def sync_default_path(new_language=None):
            language = new_language if isinstance(new_language, str) and new_language in LANGUAGES else language_combo.currentText()
            current_path = Path(path_edit.text()) if path_edit.text().strip() else selected_base_folder() / self._default_new_file_name(language)
            known_names = {self._default_new_file_name(lang) for lang in LANGUAGES}
            if current_path.name in known_names or not path_edit.text().strip():
                path_edit.setText(str(selected_base_folder() / self._default_new_file_name(language)))

        def browse_path():
            language = language_combo.currentText()
            meta = LANGUAGES[language]
            suggested = Path(path_edit.text()) if path_edit.text().strip() else selected_base_folder() / self._default_new_file_name(language)
            file_name, _ = QFileDialog.getSaveFileName(dialog, "Создать файл", str(suggested), f"{meta['filters']};;All files (*.*)")
            if file_name:
                path_edit.setText(file_name)

        language_combo.currentTextChanged.connect(sync_default_path)
        folder_combo.currentTextChanged.connect(sync_default_path)
        browse_button.clicked.connect(browse_path)
        cancel_button.clicked.connect(dialog.reject)
        create_button.clicked.connect(dialog.accept)

        layout.addWidget(title)
        layout.addWidget(hint)
        layout.addWidget(language_label)
        layout.addWidget(language_combo)
        layout.addWidget(folder_label)
        layout.addWidget(folder_combo)
        layout.addWidget(path_label)
        layout.addLayout(path_row)
        layout.addLayout(buttons)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        language = language_combo.currentText()
        path_text = path_edit.text().strip()
        if not path_text:
            QMessageBox.warning(self, "Создать файл", "Укажите место сохранения файла.")
            return
        path = Path(path_text)
        if not path.suffix:
            path = path.with_suffix(LANGUAGES[language]["extension"])
        try:
            writable_parent = self._ensure_user_writable_folder(path.parent, default_projects_dir())
            if writable_parent is None:
                return
            if writable_parent != path.parent:
                path = writable_parent / path.name
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists():
                answer = QMessageBox.question(
                    self,
                    "Файл уже существует",
                    f"Файл уже существует:\n{path}\n\nПерезаписать его?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if answer != QMessageBox.StandardButton.Yes:
                    return
            text = self._cpp_template_for_settings() if language == "C++" else LANGUAGES[language]["template"]
            path.write_text(text, encoding="utf-8")
            self.open_file(path)
            self.refresh_project_tree()
            self._save_current_project_state()
            self.statusBar().showMessage(f"Создан файл: {path.name}", 2500)
            self._save_settings()
        except Exception as exc:
            self.write_exception_log("Ошибка создания нового файла", exc)
            QMessageBox.critical(self, "Создать файл", f"Не удалось создать файл:\n{exc}")

    def open_editor_page(self):
        if hasattr(self, "tools_drawer"):
            self.tools_drawer.setVisible(False)
        self.statusBar().showMessage("Редактор открыт", 1800)

    def close_tools_drawer(self):
        try:
            if hasattr(self, "tools_drawer"):
                self.tools_drawer.setVisible(False)
            if hasattr(self, "root_splitter"):
                sizes = self.root_splitter.sizes()
                if len(sizes) >= 3:
                    self.root_splitter.setSizes([sizes[0] or 306, 0, max(700, sizes[2] + sizes[1])])
            self.write_log("Боковая панель закрыта через крестик")
            self.statusBar().showMessage("Боковая панель закрыта", 1600)
        except Exception as exc:
            self.write_exception_log("Ошибка закрытия боковой панели", exc)
            if hasattr(self, "tools_drawer"):
                self.tools_drawer.hide()

    def open_installer_tab(self):
        self._show_tools_drawer(0, "УСТАНОВЩИК")
        self.statusBar().showMessage("Установщик открыт в боковой панели", 1800)

    def open_settings_page(self):
        self._show_tools_drawer(1, "НАСТРОЙКИ")
        self.statusBar().showMessage("Настройки открыты внутри Astra Studio", 1800)

    def open_python_libs_page(self):
        self._show_tools_drawer(2, "БИБЛИОТЕКИ PYTHON")
        self.populate_library_table()
        self.statusBar().showMessage("Библиотеки Python открыты в боковой панели", 1800)

    def open_lsp_page(self):
        self._show_tools_drawer(3, "LSP / OUTLINE")
        self._refresh_lsp_server_table()
        self.request_lsp_outline(silent=True)
        self.statusBar().showMessage("LSP / Outline открыт в боковой панели", 1800)

    def open_developer_page(self):
        self._show_tools_drawer(4, "О ПРОЕКТЕ")
        self.statusBar().showMessage("О проекте открыто в боковой панели", 1800)

    def set_progress(self, value: int, label: str | None = None):
        value = max(0, min(100, int(value)))
        if hasattr(self, "install_progress_bar"):
            self.install_progress_bar.setValue(value)
        if hasattr(self, "install_progress_label"):
            self.install_progress_label.setText(label or f"Загрузка/проверка: {value}%")

    def _run_capture(self, program: str | None, args: list[str] | None = None, timeout: int = 8) -> tuple[bool, str]:
        if not program:
            return False, "команда не найдена"
        args = args or []
        try:
            completed = subprocess.run(
                [program, *args],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
            )
        except Exception as exc:
            return False, str(exc)
        output = (completed.stdout or "") + (completed.stderr or "")
        return completed.returncode == 0, output.strip()

    def _short_version(self, text: str) -> str:
        for line in text.splitlines():
            line = line.strip()
            if line:
                return line[:180]
        return "версия не определена"

    def _tool_line(self, label: str, path: str | None, version: str | None = None, valid: bool | None = None) -> str:
        if not path:
            return f"✕ {label}: не найден"
        status = "✓" if valid is not False else "⚠"
        tail = f" | {version}" if version else ""
        if valid is False:
            tail += " | найден, но тест корректности не пройден"
        elif valid is True:
            tail += " | тест корректности пройден"
        return f"{status} {label}: {path}{tail}"

    def _check_python_validity(self) -> tuple[str | None, str | None, bool]:
        program, args = python_command()
        label = (program + (" " + " ".join(args) if args else "")) if program else None
        ok_version, version_text = self._run_capture(program, [*args, "--version"] if program else [], timeout=6)
        ok_test, test_text = self._run_capture(program, [*args, "-c", "print(40 + 2)"] if program else [], timeout=6)
        version = self._short_version(version_text) if ok_version else self._short_version(version_text or test_text)
        valid = ok_test and "42" in test_text
        return label, version, valid

    def _check_cpp_validity(self) -> tuple[str | None, str | None, bool]:
        compiler = compiler_path("g++.exe", "g++") or compiler_path("clang++.exe", "clang++")
        if not compiler:
            return None, None, False
        ok_version, version_text = self._run_capture(compiler, ["--version"], timeout=8)
        test_dir = self.temp_dir / "toolcheck_cpp"
        test_dir.mkdir(parents=True, exist_ok=True)
        source = test_dir / "main.cpp"
        binary = test_dir / ("main.exe" if os.name == "nt" else "main")
        if os.name == "nt":
            source.write_text(
                '#include <windows.h>\n'
                'int main(){ HDC hdc = GetDC(NULL); if(hdc){ SetTextColor(hdc, RGB(255,0,0)); SetBkMode(hdc, TRANSPARENT); ReleaseDC(NULL, hdc); } return 0; }\n',
                encoding="utf-8",
            )
            compile_flags, linker_flags = self._cpp_extra_args(source)
            test_args = [compiler, "-std=c++17", *compile_flags, str(source), "-o", str(binary), *linker_flags]
        else:
            source.write_text('#include <iostream>\nint main(){std::cout << 42; return 0;}\n', encoding="utf-8")
            test_args = [compiler, str(source), "-std=c++17", "-o", str(binary)]
        try:
            compile_result = subprocess.run(test_args, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=18)
            run_result = subprocess.run([str(binary)], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=8) if compile_result.returncode == 0 else None
            valid = compile_result.returncode == 0 and run_result is not None and run_result.returncode == 0
        except Exception:
            valid = False
        version = self._short_version(version_text) if ok_version else "версия не определена"
        return compiler, version, valid

    def _check_java_validity(self) -> tuple[str | None, str | None, bool]:
        runtime = discover_java_runtime()
        if runtime is None:
            return None, None, False
        javac = str(runtime.javac)
        java = str(runtime.java)
        ok_version, version_text = self._run_capture(javac, ["-version"], timeout=8)
        test_dir = self.temp_dir / "toolcheck_java"
        test_dir.mkdir(parents=True, exist_ok=True)
        source = test_dir / "Main.java"
        source.write_text('public class Main { public static void main(String[] args) { System.out.print(42); } }\n', encoding="utf-8")
        try:
            compile_result = subprocess.run([javac, str(source)], cwd=str(test_dir), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=18)
            run_result = subprocess.run([java, "Main"], cwd=str(test_dir), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=8) if compile_result.returncode == 0 else None
            valid = compile_result.returncode == 0 and run_result is not None and "42" in (run_result.stdout or "")
        except Exception:
            valid = False
        version = self._short_version(version_text) if ok_version else "версия не определена"
        return f"javac: {javac} | java: {java} | source: {runtime.source}", version, valid

    def _start_installer_diagnostic_task(self, task_id: str, title: str, script_text: str, mode: str):
        if self.task_manager.has_active_task():
            self.installer_console.appendPlainText("\nДругая долгая операция уже выполняется. Дождись завершения или нажми «Отмена».")
            self.open_installer_tab()
            return
        if os.name != "nt":
            QMessageBox.information(self, "Установщик", f"Диагностика инструментов {APP_VERSION} рассчитана на Windows.")
            return
        self.open_installer_tab()
        self.installer_console.clear()
        self.installer_console.appendPlainText(f"▶ {title}\n")
        self.set_progress(0, "Подготовка: 0%")
        script_path = self.data_dir / f"{task_id}.ps1"
        try:
            script_path.write_text(script_text, encoding="utf-8-sig")
        except OSError as exc:
            QMessageBox.critical(self, "Установщик", f"Не удалось создать диагностический скрипт:\n{exc}")
            return
        args = ["-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script_path)]
        self._start_process_task(
            task_id,
            title,
            "powershell.exe",
            args,
            self.data_dir,
            {"mode": mode, "target": "installer", "indeterminate": False},
            0,
            100,
            False,
        )

    def refresh_tool_status(self):
        # Release 2.2 performed several subprocess.run calls in the GUI thread.
        # On slow machines this could freeze the window for tens of seconds.
        script = r'''
$ErrorActionPreference = "Continue"
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}
function P($value) { Write-Host "ASTRA_PROGRESS:$value" }
function First-Line($value) {
    $text = ($value | Out-String).Trim()
    if ([string]::IsNullOrWhiteSpace($text)) { return "версия не определена" }
    return ($text -split "`r?`n")[0]
}
Write-Host "Проверка версий и корректности инструментов Astra Studio:`n"
P 5

$winget = Get-Command winget -ErrorAction SilentlyContinue
if ($winget) {
    $v = & $winget.Source --version 2>&1
    if ($LASTEXITCODE -eq 0) { Write-Host "✓ WinGet: $($winget.Source) | $(First-Line $v)" }
    else { Write-Host "⚠ WinGet найден, но не запускается корректно: $($winget.Source)" }
} else { Write-Host "✕ WinGet: не найден" }
P 20

$python = Get-Command py -ErrorAction SilentlyContinue
$pythonArgs = @("-3")
$pythonOk = $false
if ($python) {
    $test = & $python.Source @pythonArgs -c "import sys; print(sys.version.split()[0]); print(40 + 2)" 2>&1
    $pythonOk = $LASTEXITCODE -eq 0 -and (($test | Out-String) -match "42")
}
if (-not $pythonOk) {
    $python = Get-Command python -ErrorAction SilentlyContinue
    $pythonArgs = @()
    if ($python) {
        $test = & $python.Source -c "import sys; print(sys.version.split()[0]); print(40 + 2)" 2>&1
        $pythonOk = $LASTEXITCODE -eq 0 -and (($test | Out-String) -match "42")
    }
}
if ($pythonOk) { Write-Host "✓ Python: $($python.Source) | $(First-Line $test) | тест корректности пройден" }
elseif ($python) { Write-Host "⚠ Python найден, но тест корректности не пройден: $($python.Source)" }
else { Write-Host "✕ Python: не найден" }
P 45

$gpp = Get-Command g++ -ErrorAction SilentlyContinue
if (-not $gpp -and (Test-Path "C:\msys64\ucrt64\bin\g++.exe")) { $gpp = Get-Item "C:\msys64\ucrt64\bin\g++.exe" }
$cppOk = $false
if ($gpp) {
    $gppPath = if ($gpp.Source) { $gpp.Source } else { $gpp.FullName }
    $cppDir = Join-Path $env:TEMP "AstralStudio\toolcheck_cpp"
    New-Item -ItemType Directory -Force -Path $cppDir | Out-Null
    $cppSource = Join-Path $cppDir "main.cpp"
    $cppExe = Join-Path $cppDir "main.exe"
    [IO.File]::WriteAllText($cppSource, "#include <windows.h>`nint main(){ HDC hdc = GetDC(NULL); if(hdc){ SetTextColor(hdc, RGB(255,0,0)); ReleaseDC(NULL, hdc); } return 0; }", (New-Object Text.UTF8Encoding($false)))
    $cppVersion = & $gppPath --version 2>&1
    & $gppPath -std=c++17 $cppSource -o $cppExe -lgdi32 -luser32 -lkernel32 2>&1 | ForEach-Object { Write-Host $_ }
    if ($LASTEXITCODE -eq 0 -and (Test-Path $cppExe)) {
        & $cppExe
        $cppOk = $LASTEXITCODE -eq 0
    }
    if ($cppOk) { Write-Host "✓ C++: $gppPath | $(First-Line $cppVersion) | тест GDI/User32 пройден" }
    else { Write-Host "⚠ C++ найден, но тест компиляции/линковки не пройден: $gppPath" }
} else { Write-Host "✕ C++: компилятор не найден" }
P 70

$javaHomes = @()
foreach ($value in @($env:JAVA_HOME, $env:JDK_HOME)) {
    if (-not [string]::IsNullOrWhiteSpace([string]$value)) { $javaHomes += [string]$value }
}
$pathJavac = Get-Command javac -ErrorAction SilentlyContinue
if ($pathJavac -and $pathJavac.Source) { $javaHomes += Split-Path -Parent (Split-Path -Parent $pathJavac.Source) }
foreach ($root in @($env:ProgramFiles, ${env:ProgramFiles(x86)}, (Join-Path $env:LOCALAPPDATA "Programs"))) {
    if ([string]::IsNullOrWhiteSpace([string]$root) -or -not (Test-Path $root)) { continue }
    foreach ($vendor in @("Eclipse Adoptium", "Java", "Microsoft", "Amazon Corretto", "BellSoft", "Azul Systems")) {
        $folder = Join-Path $root $vendor
        if (Test-Path $folder) { $javaHomes += Get-ChildItem $folder -Directory -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | ForEach-Object { $_.FullName } }
    }
}
$javacPath = $null
$javaPath = $null
foreach ($javaHomePath in ($javaHomes | Select-Object -Unique)) {
    $candidateJavac = Join-Path $javaHomePath "bin\javac.exe"
    $candidateJava = Join-Path $javaHomePath "bin\java.exe"
    if ((Test-Path $candidateJavac) -and (Test-Path $candidateJava)) { $javacPath = $candidateJavac; $javaPath = $candidateJava; break }
}
$javaOk = $false
if ($javacPath -and $javaPath) {
    $javaDir = Join-Path $env:TEMP "AstralStudio\toolcheck_java"
    New-Item -ItemType Directory -Force -Path $javaDir | Out-Null
    $javaSource = Join-Path $javaDir "Main.java"
    [IO.File]::WriteAllText($javaSource, 'public class Main { public static void main(String[] args) { System.out.print(42); } }', (New-Object Text.UTF8Encoding($false)))
    $javaVersion = & $javacPath -version 2>&1
    & $javacPath $javaSource 2>&1 | ForEach-Object { Write-Host $_ }
    if ($LASTEXITCODE -eq 0) {
        $result = & $javaPath -cp $javaDir Main 2>&1
        $javaOk = $LASTEXITCODE -eq 0 -and (($result | Out-String) -match "42")
    }
    if ($javaOk) { Write-Host "✓ Java: javac=$javacPath | java=$javaPath | $(First-Line $javaVersion) | тест пройден" }
    else { Write-Host "⚠ Java найдена, но тест компиляции/запуска не пройден" }
} else { Write-Host "✕ Java: согласованная пара javac/java из одного JDK не найдена" }
P 74

function Tool-Version($name, $args) {
    $tool = Get-Command $name -ErrorAction SilentlyContinue
    if (-not $tool) { return $null }
    $value = & $tool.Source @args 2>&1
    if ($LASTEXITCODE -ne 0) { return @{ Path = $tool.Source; Version = "ошибка запуска"; Ok = $false } }
    return @{ Path = $tool.Source; Version = (First-Line $value); Ok = $true }
}

$uv = Tool-Version "uv" @("--version")
if ($uv) { Write-Host "$($(if($uv.Ok){'✓'}else{'⚠'})) uv: $($uv.Path) | $($uv.Version)" } else { Write-Host "ℹ uv: не найден (pip/venv fallback доступен)" }
P 78
$node = Tool-Version "node" @("--version")
$npm = Tool-Version "npm" @("--version")
$tsc = Tool-Version "tsc" @("--version")
$tsx = Tool-Version "tsx" @("--version")
if ($node) { Write-Host "$($(if($node.Ok){'✓'}else{'⚠'})) Node.js: $($node.Path) | $($node.Version)" } else { Write-Host "✕ Node.js: не найден" }
if ($npm) { Write-Host "$($(if($npm.Ok){'✓'}else{'⚠'})) npm: $($npm.Path) | $($npm.Version)" } else { Write-Host "✕ npm: не найден" }
if ($tsc) { Write-Host "$($(if($tsc.Ok){'✓'}else{'⚠'})) TypeScript: $($tsc.Path) | $($tsc.Version)" } else { Write-Host "ℹ TypeScript compiler: не найден" }
if ($tsx) { Write-Host "$($(if($tsx.Ok){'✓'}else{'⚠'})) tsx: $($tsx.Path) | $($tsx.Version)" } else { Write-Host "ℹ tsx: не найден" }
P 84
$git = Tool-Version "git" @("--version")
if ($git) { Write-Host "$($(if($git.Ok){'✓'}else{'⚠'})) Git: $($git.Path) | $($git.Version)" } else { Write-Host "✕ Git: не найден" }
$pwsh = Tool-Version "pwsh" @("-NoProfile", "-Command", '$PSVersionTable.PSVersion.ToString()')
if ($pwsh) { Write-Host "$($(if($pwsh.Ok){'✓'}else{'⚠'})) PowerShell 7: $($pwsh.Path) | $($pwsh.Version)" } else { Write-Host "ℹ PowerShell 7: не найден; Windows PowerShell остаётся fallback" }
P 89
$godot = Tool-Version "godot" @("--version")
if ($godot) { Write-Host "$($(if($godot.Ok){'✓'}else{'⚠'})) Godot: $($godot.Path) | $($godot.Version)" } else { Write-Host "ℹ Godot: не найден" }
$php = Tool-Version "php" @("--version")
if ($php) { Write-Host "$($(if($php.Ok){'✓'}else{'⚠'})) PHP: $($php.Path) | $($php.Version)" } else { Write-Host "ℹ PHP: не найден" }
P 94
$bashTool = Tool-Version "bash" @("--version")
if ($bashTool) { Write-Host "$($(if($bashTool.Ok){'✓'}else{'⚠'})) Bash: $($bashTool.Path) | $($bashTool.Version)" } else { Write-Host "ℹ Bash: не найден" }
$luau = Tool-Version "luau" @("--version")
$luauAnalyze = Tool-Version "luau-analyze" @("--version")
$rojo = Tool-Version "rojo" @("--version")
if ($luau) { Write-Host "$($(if($luau.Ok){'✓'}else{'⚠'})) Luau CLI: $($luau.Path) | $($luau.Version)" } else { Write-Host "ℹ Luau CLI: не найден" }
if ($luauAnalyze) { Write-Host "$($(if($luauAnalyze.Ok){'✓'}else{'⚠'})) Luau analyzer: $($luauAnalyze.Path) | $($luauAnalyze.Version)" } else { Write-Host "ℹ luau-analyze: не найден" }
if ($rojo) { Write-Host "$($(if($rojo.Ok){'✓'}else{'⚠'})) Rojo: $($rojo.Path) | $($rojo.Version)" } else { Write-Host "ℹ Rojo: не найден" }
P 100
Write-Host "`nПроверка завершена. ✕ означает обязательный инструмент базового набора; ℹ — опциональный/проектный инструмент."
'''
        self._start_installer_diagnostic_task("tool_check", "Проверка инструментов", script, "tool_check")

    def check_app_update(self):
        try:
            manifest_url = configured_manifest_url(resource_path("update_channel.json"))
        except ValueError as exc:
            QMessageBox.warning(self, "Обновления Astra Studio", str(exc))
            return
        if not manifest_url:
            message = (
                "Канал обновлений ещё не опубликован. Сборка поддерживает HTTPS latest.json; "
                "издателю нужно записать его адрес в update_channel.json или переменную "
                "ASTRA_UPDATE_MANIFEST_URL."
            )
            self.app_update_status.setText(f"Astra Studio: {APP_VERSION} · канал не опубликован")
            self.installer_console.appendPlainText("\nℹ " + message + "\n")
            QMessageBox.information(self, "Обновления Astra Studio", message)
            return
        if (
            (self._app_update_reply is not None and not self._app_update_reply.isFinished())
            or (self._app_download_reply is not None and not self._app_download_reply.isFinished())
        ):
            self.statusBar().showMessage("Проверка или загрузка обновления уже выполняется", 2200)
            return

        self.btn_check_app_update.setEnabled(False)
        self.app_update_status.setText(f"Astra Studio: {APP_VERSION} · проверка обновления…")
        self.installer_console.appendPlainText(f"\n▶ Проверка обновления Astra Studio: {manifest_url}\n")
        request = QNetworkRequest(QUrl(manifest_url))
        request.setRawHeader(b"User-Agent", f"Astra-Studio/{APP_VERSION.replace(' ', '-')}".encode("ascii"))
        try:
            request.setAttribute(
                QNetworkRequest.Attribute.RedirectPolicyAttribute,
                QNetworkRequest.RedirectPolicy.NoLessSafeRedirectPolicy,
            )
        except (AttributeError, TypeError):
            pass
        reply = self.update_network.get(request)
        self._app_update_reply = reply
        reply.finished.connect(lambda current_reply=reply: self._finish_app_update(current_reply))

    def _finish_app_update(self, reply):
        try:
            if reply.error() != QNetworkReply.NetworkError.NoError:
                raise RuntimeError(reply.errorString())
            payload = bytes(reply.readAll())
            manifest = parse_update_manifest(payload)
            size_mb = manifest.size / (1024 * 1024)
            if is_newer_release(manifest.version, APP_VERSION):
                self.app_update_status.setText(
                    f"Доступно: {manifest.version} · {size_mb:.1f} МБ · SHA-256 {manifest.sha256[:12]}…"
                )
                self.installer_console.appendPlainText(
                    f"✓ Доступно обновление {manifest.version}\n"
                    f"  Размер: {manifest.size} байт\n"
                    f"  SHA-256: {manifest.sha256}\n"
                )
                answer = QMessageBox.question(
                    self,
                    "Обновление Astra Studio",
                    f"Доступно {manifest.version} ({size_mb:.1f} МБ).\n\n"
                    f"SHA-256: {manifest.sha256}\n\nСкачать, проверить и установить обновление?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.Yes,
                )
                if answer == QMessageBox.StandardButton.Yes:
                    self._start_app_update_download(manifest)
            else:
                self.app_update_status.setText(f"Astra Studio: {APP_VERSION} · обновлений нет")
                self.installer_console.appendPlainText("✓ Установлена актуальная версия Astra Studio.\n")
                QMessageBox.information(
                    self,
                    "Обновления Astra Studio",
                    f"Установлена актуальная версия: {APP_VERSION}.",
                )
        except Exception as exc:
            self.app_update_status.setText(f"Astra Studio: {APP_VERSION} · ошибка проверки")
            self.installer_console.appendPlainText(f"✕ Не удалось проверить обновление: {exc}\n")
            self.write_exception_log("Ошибка проверки обновления Astra Studio", exc)
            QMessageBox.warning(self, "Обновления Astra Studio", f"Не удалось проверить обновление:\n{exc}")
        finally:
            self.btn_check_app_update.setEnabled(self._app_download_reply is None)
            if self._app_update_reply is reply:
                self._app_update_reply = None
            reply.deleteLater()

    def _start_app_update_download(self, manifest):
        updates_dir = self.data_dir / "updates"
        updates_dir.mkdir(parents=True, exist_ok=True)
        safe_version = re.sub(r"[^0-9A-Za-z._-]+", "_", manifest.version).strip("_") or "update"
        archive_path = updates_dir / f"Astra_Studio_{safe_version}.zip"
        try:
            handle = archive_path.open("wb")
        except OSError as exc:
            QMessageBox.warning(self, "Обновление Astra Studio", f"Не удалось создать файл обновления:\n{exc}")
            return

        request = QNetworkRequest(QUrl(manifest.download_url))
        request.setRawHeader(b"User-Agent", f"Astra-Studio/{APP_VERSION.replace(' ', '-')}".encode("ascii"))
        try:
            request.setAttribute(
                QNetworkRequest.Attribute.RedirectPolicyAttribute,
                QNetworkRequest.RedirectPolicy.NoLessSafeRedirectPolicy,
            )
        except (AttributeError, TypeError):
            pass
        reply = self.update_network.get(request)
        self._app_download_reply = reply
        self._app_download_file = handle
        self._app_download_path = archive_path
        self._app_download_manifest = manifest
        self.btn_check_app_update.setEnabled(False)
        self.app_update_status.setText(f"Загрузка {manifest.version}: 0%")
        self.installer_console.appendPlainText(f"▶ Загрузка проверенного обновления: {manifest.download_url}\n")
        reply.readyRead.connect(lambda current_reply=reply: self._read_app_update_chunk(current_reply))
        reply.downloadProgress.connect(self._show_app_update_download_progress)
        reply.finished.connect(lambda current_reply=reply: self._finish_app_update_download(current_reply))

    def _read_app_update_chunk(self, reply):
        if reply is not self._app_download_reply or self._app_download_file is None:
            return
        chunk = bytes(reply.readAll())
        if chunk:
            self._app_download_file.write(chunk)

    def _show_app_update_download_progress(self, received, total):
        manifest = self._app_download_manifest
        version = manifest.version if manifest is not None else "обновления"
        expected = total if total and total > 0 else (manifest.size if manifest is not None else 0)
        if expected > 0:
            percent = max(0, min(100, int(received * 100 / expected)))
            self.app_update_status.setText(f"Загрузка {version}: {percent}%")
        else:
            self.app_update_status.setText(f"Загрузка {version}: {received / (1024 * 1024):.1f} МБ")

    def _finish_app_update_download(self, reply):
        archive_path = self._app_download_path
        manifest = self._app_download_manifest
        handle = self._app_download_file
        try:
            self._read_app_update_chunk(reply)
            if handle is not None:
                handle.flush()
                handle.close()
            self._app_download_file = None
            if reply.error() != QNetworkReply.NetworkError.NoError:
                raise RuntimeError(reply.errorString())
            if archive_path is None or manifest is None:
                raise RuntimeError("Внутреннее состояние загрузки потеряно")
            entry_count, unpacked_size = verify_update_archive(archive_path, manifest)
            self.installer_console.appendPlainText(
                f"✓ Архив проверен: {entry_count} файлов, {unpacked_size / (1024 * 1024):.1f} МБ после распаковки.\n"
            )
            self._queue_app_update_install(archive_path, manifest)
        except Exception as exc:
            if handle is not None and not handle.closed:
                handle.close()
            if archive_path is not None:
                try:
                    archive_path.unlink(missing_ok=True)
                except OSError:
                    pass
            self.app_update_status.setText(f"Astra Studio: {APP_VERSION} · ошибка загрузки")
            self.installer_console.appendPlainText(f"✕ Обновление не установлено: {exc}\n")
            self.write_exception_log("Ошибка загрузки обновления Astra Studio", exc)
            QMessageBox.warning(self, "Обновление Astra Studio", f"Обновление не установлено:\n{exc}")
        finally:
            if self._app_download_reply is reply:
                self._app_download_reply = None
            self._app_download_file = None
            self._app_download_path = None
            self._app_download_manifest = None
            self.btn_check_app_update.setEnabled(True)
            reply.deleteLater()

    def _queue_app_update_install(self, archive_path: Path, manifest):
        if os.name != "nt" or not getattr(sys, "frozen", False):
            self.app_update_status.setText(f"{manifest.version} загружено и проверено")
            QMessageBox.information(
                self,
                "Обновление Astra Studio",
                "Архив загружен и проверен. Автоматическая замена выполняется только в portable EXE.\n\n"
                f"Файл: {archive_path}",
            )
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(archive_path.parent)))
            return
        target_dir = Path(sys.executable).resolve().parent
        if target_dir.name.casefold() != "astra studio":
            raise RuntimeError(f"Небезопасная папка установки: {target_dir}")
        script_path = self.data_dir / "updates" / "install_verified_update.ps1"
        log_path = self.data_dir / "logs" / "update-install.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        script_path.write_text(windows_update_script(), encoding="utf-8-sig")
        args = [
            "-NoProfile", "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden",
            "-File", str(script_path), "-Archive", str(archive_path),
            "-TargetDirectory", str(target_dir), "-ParentPid", str(os.getpid()),
            "-LogPath", str(log_path),
        ]
        self._pending_update_command = ("powershell.exe", args)
        self.app_update_status.setText(f"{manifest.version} проверено · перезапуск для установки")
        QMessageBox.information(
            self,
            "Обновление Astra Studio",
            f"{manifest.version} скачано и проверено. Astra Studio сейчас закроется, установит обновление и запустится снова.",
        )
        self.close()

    def check_tool_updates(self):
        # Run potentially slow WinGet/pacman queries outside the GUI thread.
        script = r'''
$ErrorActionPreference = "Continue"
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}
function P($value) { Write-Host "ASTRA_PROGRESS:$value" }
Write-Host "Проверка доступных обновлений языков и инструментов...`n"
P 5
$winget = Get-Command winget -ErrorAction SilentlyContinue
if ($winget) {
    $checks = @(
        @{ Name = "Python 3.14"; Id = "Python.Python.3.14" },
        @{ Name = "uv"; Id = "astral-sh.uv" },
        @{ Name = "Node.js LTS"; Id = "OpenJS.NodeJS.LTS" },
        @{ Name = "Git"; Id = "Git.Git" },
        @{ Name = "MSYS2 / C++"; Id = "MSYS2.MSYS2" },
        @{ Name = "Java JDK"; Id = "EclipseAdoptium.Temurin.21.JDK" },
        @{ Name = "PowerShell 7"; Id = "Microsoft.PowerShell" },
        @{ Name = "Godot"; Id = "GodotEngine.GodotEngine" },
        @{ Name = "PHP 8.4"; Id = "PHP.PHP.8.4" }
    )
    $progress = 10
    $step = [Math]::Max(1, [int](70 / $checks.Count))
    foreach ($item in $checks) {
        Write-Host "`n▶ $($item.Name)"
        & $winget.Source upgrade --id $item.Id --accept-source-agreements 2>&1 | ForEach-Object { Write-Host $_ }
        $progress = [Math]::Min(82, $progress + $step)
        P $progress
    }
} else {
    Write-Host "✕ WinGet не найден. Автоматическая проверка обновлений Windows-пакетов невозможна."
    P 75
}
$bash = "C:\msys64\usr\bin\bash.exe"
if (Test-Path $bash) {
    Write-Host "`n▶ Пакеты MSYS2 / C++ toolchain"
    & $bash -lc "pacman -Qu" 2>&1 | ForEach-Object { Write-Host $_ }
} else {
    Write-Host "`nℹ MSYS2 не найден в C:\msys64 — проверка pacman пропущена."
}
P 100
Write-Host "`nПроверка обновлений завершена."
'''
        self._start_installer_diagnostic_task("update_check", "Проверка обновлений", script, "update_check")

    def _ps_quote(self, text: str) -> str:
        return "'" + text.replace("'", "''") + "'"

    def _installer_common_script(self) -> str:
        return r"""
$ErrorActionPreference = "Stop"
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}
function Write-Step($text) { Write-Host "`n=== $text ===" }
function Astra-Progress($value) { Write-Host "ASTRA_PROGRESS:$value" }
function Invoke-NativeVersionProbe([string]$FilePath, [string[]]$Arguments = @("--version")) {
    if ([string]::IsNullOrWhiteSpace($FilePath) -or -not (Test-Path $FilePath -ErrorAction SilentlyContinue)) { return $false }
    foreach ($argument in $Arguments) {
        if ([string]$argument -notmatch '^[A-Za-z0-9._:/=+\-]+$') { throw "Unsafe native version-probe argument: $argument" }
    }
    $startInfo = New-Object System.Diagnostics.ProcessStartInfo
    $startInfo.FileName = $FilePath
    $startInfo.Arguments = ($Arguments -join " ")
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $true
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true
    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $startInfo
    try {
        if (-not $process.Start()) { return $false }
        $stdout = $process.StandardOutput.ReadToEnd()
        $stderr = $process.StandardError.ReadToEnd()
        $process.WaitForExit()
        foreach ($text in @($stdout, $stderr)) {
            if (-not [string]::IsNullOrWhiteSpace($text)) { Write-Host $text.TrimEnd() }
        }
        return $process.ExitCode -eq 0
    } finally {
        $process.Dispose()
    }
}
function Find-JavaRuntime {
    $javaHomeCandidates = @()
    foreach ($value in @($env:JAVA_HOME, $env:JDK_HOME)) {
        if (-not [string]::IsNullOrWhiteSpace([string]$value)) { $javaHomeCandidates += [string]$value }
    }
    $javac = Get-Command javac -ErrorAction SilentlyContinue
    if ($javac -and $javac.Source) { $javaHomeCandidates += Split-Path -Parent (Split-Path -Parent $javac.Source) }
    foreach ($root in @($env:ProgramFiles, ${env:ProgramFiles(x86)}, (Join-Path $env:LOCALAPPDATA "Programs"))) {
        if ([string]::IsNullOrWhiteSpace([string]$root) -or -not (Test-Path $root)) { continue }
        foreach ($vendor in @("Eclipse Adoptium", "Java", "Microsoft", "Amazon Corretto", "BellSoft", "Azul Systems")) {
            $folder = Join-Path $root $vendor
            if (Test-Path $folder) {
                $javaHomeCandidates += Get-ChildItem $folder -Directory -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | ForEach-Object { $_.FullName }
            }
        }
    }
    foreach ($javaHomePath in ($javaHomeCandidates | Select-Object -Unique)) {
        $javacPath = Join-Path $javaHomePath "bin\javac.exe"
        $javaPath = Join-Path $javaHomePath "bin\java.exe"
        if ((Test-Path $javacPath) -and (Test-Path $javaPath)) { return @{ Home = $javaHomePath; Javac = $javacPath; Java = $javaPath } }
    }
    return $null
}
function Ensure-Winget {
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if (-not $winget) {
        throw "WinGet не найден. Обнови/установи App Installer из Microsoft Store и повтори запуск."
    }
    & $winget.Source --version | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "WinGet найден, но не запускается корректно." }
    return $winget.Source
}
function Test-WingetInstalled([string]$id) {
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if (-not $winget) { return $false }
    $text = & $winget.Source list -e --id $id --accept-source-agreements 2>&1 | Out-String
    return $text -match [regex]::Escape($id)
}
function Add-ProcessPath($dir) {
    if ([string]::IsNullOrWhiteSpace($dir) -or -not (Test-Path $dir)) { return }
    $resolved = (Resolve-Path $dir).Path
    if (($env:Path -split ';') -notcontains $resolved) { $env:Path = "$resolved;$env:Path" }
}
function Add-UserPath($dir) {
    if (-not (Test-Path $dir)) { return }
    $dir = (Resolve-Path $dir).Path
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    if ([string]::IsNullOrWhiteSpace($userPath)) { $userPath = "" }
    $parts = $userPath -split ';' | Where-Object { $_ -and $_.Trim() }
    if ($parts -notcontains $dir) {
        $newPath = (($parts + $dir) -join ';')
        [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
        Write-Host "Добавлено в пользовательский PATH: $dir"
    } else {
        Write-Host "PATH уже содержит: $dir"
    }
    Add-ProcessPath $dir
}
function WinGet-Link([string]$name) {
    $links = Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Links"
    $candidate = Join-Path $links $name
    if (Test-Path $candidate) { return $candidate }
    return $null
}
function Resolve-ToolPath($tool) {
    if ($null -eq $tool) { return $null }
    if ($tool -is [string]) { return [string]$tool }
    foreach ($property in @("Source", "FullName", "Path", "Definition")) {
        try {
            $value = $tool.$property
            if (-not [string]::IsNullOrWhiteSpace([string]$value)) { return [string]$value }
        } catch {}
    }
    return $null
}
function Refresh-KnownPaths {
    Add-ProcessPath (Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Links")
    Add-ProcessPath (Join-Path $env:APPDATA "npm")
    Add-ProcessPath "C:\Program Files\nodejs"
    Add-ProcessPath "C:\Program Files\Git\cmd"
    Add-ProcessPath "C:\Program Files\PowerShell\7"
    Add-ProcessPath "C:\msys64\ucrt64\bin"
    $javaRuntime = Find-JavaRuntime
    if ($javaRuntime) { Add-ProcessPath (Join-Path $javaRuntime.Home "bin") }
}
function Refresh-EnvHint {
    Write-Host "`nГотово. Astra обновляет известные runtime-пути сама; если Windows ещё не опубликовала новый alias, перезапусти Astra Studio."
}
Refresh-KnownPaths
"""

    def _installer_script(self, kind: str) -> str:
        common = self._installer_common_script()
        app_dir = str(project_root_dir())
        shortcut_icon_relative = "assets/astra.ico"
        shortcut_icon_label = "Astra 3.13 — красно-синий"
        if hasattr(self, "shortcut_icon_combo"):
            shortcut_icon_relative = str(self.shortcut_icon_combo.currentData() or shortcut_icon_relative)
            shortcut_icon_label = self.shortcut_icon_combo.currentText() or shortcut_icon_label
        shortcut_icon_path = str(resource_path(shortcut_icon_relative))
        shortcut_script = f"""
Write-Step "Создание ярлыка Astra Studio"
$appDir = {self._ps_quote(app_dir)}
$desktopCandidates = @([Environment]::GetFolderPath([Environment+SpecialFolder]::DesktopDirectory))
$registryDesktop = (Get-ItemProperty -LiteralPath "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\User Shell Folders" -Name Desktop -ErrorAction SilentlyContinue).Desktop
if (-not [string]::IsNullOrWhiteSpace($registryDesktop)) {{ $desktopCandidates += [Environment]::ExpandEnvironmentVariables($registryDesktop) }}
if (-not [string]::IsNullOrWhiteSpace($env:OneDrive)) {{
    $desktopCandidates += Join-Path $env:OneDrive "Рабочий стол"
    $desktopCandidates += Join-Path $env:OneDrive "Desktop"
}}
if (-not [string]::IsNullOrWhiteSpace($env:USERPROFILE)) {{
    $desktopCandidates += Join-Path $env:USERPROFILE "Рабочий стол"
    $desktopCandidates += Join-Path $env:USERPROFILE "Desktop"
}}
$desktop = $desktopCandidates | Where-Object {{ -not [string]::IsNullOrWhiteSpace($_) -and (Test-Path -LiteralPath $_) }} | Select-Object -First 1
if ([string]::IsNullOrWhiteSpace($desktop)) {{ throw "Не удалось определить папку рабочего стола." }}
$linkPath = Join-Path $desktop "Astra Studio.lnk"
$exeCandidate = Join-Path $appDir "Astra Studio.exe"
$distOneDirCandidate = Join-Path $appDir "dist\\Astra Studio\\Astra Studio.exe"
$distExeCandidate = Join-Path $appDir "dist\\Astra Studio.exe"
$vbsCandidate = Join-Path $appDir "run_astra.vbs"
$batCandidate = Join-Path $appDir "run_astra.bat"
if (Test-Path $exeCandidate) {{ $target = $exeCandidate }}
elseif (Test-Path $distOneDirCandidate) {{ $target = $distOneDirCandidate }}
elseif (Test-Path $distExeCandidate) {{ $target = $distExeCandidate }}
elseif (Test-Path $vbsCandidate) {{ $target = $vbsCandidate }}
elseif (Test-Path $batCandidate) {{ $target = $batCandidate }}
elseif (Test-Path (Join-Path $appDir "run.bat")) {{ $target = Join-Path $appDir "run.bat" }}
else {{ throw "Не найден исполняемый файл или launcher Astra Studio для ярлыка." }}
$wsh = New-Object -ComObject WScript.Shell
$shortcut = $wsh.CreateShortcut($linkPath)
$shortcut.TargetPath = $target
$shortcut.WorkingDirectory = Split-Path -Parent $target
$preferredIcon = {self._ps_quote(shortcut_icon_path)}
$stableIcon = Join-Path $appDir "assets\astra.ico"
if (Test-Path -LiteralPath $preferredIcon) {{ $shortcut.IconLocation = $preferredIcon }}
elseif (Test-Path -LiteralPath $stableIcon) {{ $shortcut.IconLocation = $stableIcon }}
else {{ $shortcut.IconLocation = $target }}
$shortcut.Description = "Astra Studio — среда для кода"
$shortcut.Save()
if (-not (Test-Path -LiteralPath $linkPath)) {{ throw "Windows не создала файл ярлыка: $linkPath" }}
Write-Host "Ярлык создан: $linkPath"
Write-Host "Оформление: {shortcut_icon_label}"
"""
        python_script = r"""
Astra-Progress 8
Write-Step "Установка Python"
Astra-Progress 15
function Test-PythonExecutable([string]$exe, [string[]]$prefixArgs = @()) {
    if ([string]::IsNullOrWhiteSpace($exe) -or -not (Test-Path $exe -ErrorAction SilentlyContinue)) { return $false }
    & $exe @prefixArgs -c "import sys; print(sys.executable); print(40 + 2)" 2>$null
    return $LASTEXITCODE -eq 0
}
function Find-WorkingPython {
    $launcher = Get-Command py -ErrorAction SilentlyContinue
    if ($launcher) {
        & $launcher.Source -3 -c "import sys; print(sys.executable); print(40 + 2)" 2>$null
        if ($LASTEXITCODE -eq 0) { return @{ Path = $launcher.Source; Args = @("-3"); RealExe = $null } }
    }
    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) {
        & $python.Source -c "import sys; print(sys.executable); print(40 + 2)" 2>$null
        if ($LASTEXITCODE -eq 0) { return @{ Path = $python.Source; Args = @(); RealExe = $python.Source } }
    }
    $candidates = @()
    $localPython = Join-Path $env:LOCALAPPDATA "Programs\Python"
    if (Test-Path $localPython) {
        $candidates += Get-ChildItem $localPython -Directory -Filter "Python*" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | ForEach-Object { Join-Path $_.FullName "python.exe" }
    }
    $candidates += Get-ChildItem "C:\Program Files" -Directory -Filter "Python*" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | ForEach-Object { Join-Path $_.FullName "python.exe" }
    foreach ($candidate in $candidates) {
        if (Test-PythonExecutable $candidate) { return @{ Path = $candidate; Args = @(); RealExe = $candidate } }
    }
    return $null
}
$working = Find-WorkingPython
if ($working) {
    Write-Host "Python уже найден: $($working.Path)"
    & $working.Path @($working.Args) --version
} else {
    Ensure-Winget
    $ids = @("Python.Python.3.14", "Python.Python.3.13", "Python.Python.3.12", "Python.Python.3.11")
    $installed = $false
    foreach ($id in $ids) {
        Write-Host "Пробую установить: $id"
        & winget install -e --id $id --accept-source-agreements --accept-package-agreements
        if ($LASTEXITCODE -eq 0) { $installed = $true; break }
    }
    if (-not $installed) { throw "Не удалось установить Python через WinGet." }
    $working = Find-WorkingPython
    if (-not $working) { throw "Python установлен, но рабочий интерпретатор не удалось проверить." }
    if ($working.RealExe) {
        Add-UserPath (Split-Path -Parent $working.RealExe)
        $scripts = Join-Path (Split-Path -Parent $working.RealExe) "Scripts"
        if (Test-Path $scripts) { Add-UserPath $scripts }
    }
    Write-Host "Python проверен: $($working.Path)"
    & $working.Path @($working.Args) --version
}
Astra-Progress 30
Refresh-EnvHint
"""
        cpp_script = r"""
Astra-Progress 35
Write-Step "Установка C++ toolchain"
$gpp = Get-Command g++ -ErrorAction SilentlyContinue
if ($gpp) {
    Write-Host "g++ уже найден: $($gpp.Source)"
    & $gpp.Source --version
    if ($LASTEXITCODE -ne 0) { $gpp = $null }
}
if (-not $gpp) {
    $bash = "C:\msys64\usr\bin\bash.exe"
    if (-not (Test-Path $bash)) {
        Ensure-Winget
        & winget install -e --id MSYS2.MSYS2 --accept-source-agreements --accept-package-agreements
        if ($LASTEXITCODE -ne 0 -and -not (Test-Path $bash)) { throw "Не удалось установить MSYS2 через WinGet." }
    }
    if (-not (Test-Path $bash)) { throw "MSYS2 не найден в C:\msys64 или установка не завершилась." }
    Astra-Progress 48
    Write-Step "Обновление MSYS2"
    & $bash -lc "pacman -Syuu --noconfirm"
    if ($LASTEXITCODE -ne 0) { throw "Обновление MSYS2 завершилось с ошибкой." }
    Astra-Progress 58
    Write-Step "Установка g++ UCRT64"
    & $bash -lc "pacman -S --needed --noconfirm mingw-w64-ucrt-x86_64-gcc"
    if ($LASTEXITCODE -ne 0) { throw "Установка g++ через pacman завершилась с ошибкой." }
}
$gppPath = "C:\msys64\ucrt64\bin\g++.exe"
if (Test-Path $gppPath) {
    Add-UserPath "C:\msys64\ucrt64\bin"
    & $gppPath --version
    if ($LASTEXITCODE -ne 0) { throw "g++ найден, но не запускается корректно." }
} elseif ($gpp) {
    & $gpp.Source --version
    if ($LASTEXITCODE -ne 0) { throw "Найденный g++ не прошёл проверку." }
} else {
    throw "Установка C++ завершилась, но g++ не удалось проверить."
}
Astra-Progress 68
Refresh-EnvHint
"""
        java_script = r"""
Astra-Progress 72
Write-Step "Установка Java JDK"
$pathJavac = Get-Command javac -ErrorAction SilentlyContinue
$runtime = Find-JavaRuntime
if ($pathJavac) { Write-Host "javac в PATH: $($pathJavac.Source)" }
if ($runtime) { Write-Host "JDK уже найден: $($runtime.Home)" }
$adoptium = "C:\Program Files\Eclipse Adoptium"
$jdk = $null
if (Test-Path $adoptium) {
    $jdk = Get-ChildItem $adoptium -Directory -Filter "jdk-*" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
}
if (-not $runtime -and -not $jdk) {
    Ensure-Winget
    & winget install -e --id EclipseAdoptium.Temurin.21.JDK --accept-source-agreements --accept-package-agreements
    if ($LASTEXITCODE -ne 0) {
        if (Test-Path $adoptium) {
            $jdk = Get-ChildItem $adoptium -Directory -Filter "jdk-*" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
        }
        if (-not $jdk) { throw "Не удалось установить Java JDK через WinGet." }
    }
}
if (-not $jdk -and (Test-Path $adoptium)) {
    $jdk = Get-ChildItem $adoptium -Directory -Filter "jdk-*" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
}
$verified = $false
if ($jdk) {
    [Environment]::SetEnvironmentVariable("JAVA_HOME", $jdk.FullName, "User")
    Add-UserPath (Join-Path $jdk.FullName "bin")
    $javacPath = Join-Path $jdk.FullName "bin\javac.exe"
    $javaPath = Join-Path $jdk.FullName "bin\java.exe"
    if ((Test-Path $javacPath) -and (Test-Path $javaPath)) {
        $javacOk = Invoke-NativeVersionProbe $javacPath @("-version")
        $javaOk = Invoke-NativeVersionProbe $javaPath @("-version")
        $verified = $javacOk -and $javaOk
    }
}
if (-not $verified) {
    $runtime = Find-JavaRuntime
    if ($runtime) {
        [Environment]::SetEnvironmentVariable("JAVA_HOME", $runtime.Home, "User")
        Add-UserPath (Join-Path $runtime.Home "bin")
        $verified = (Invoke-NativeVersionProbe $runtime.Javac @("-version")) -and (Invoke-NativeVersionProbe $runtime.Java @("-version"))
    }
}
if (-not $verified) { throw "Java установлена, но javac/java не удалось проверить." }
Astra-Progress 92
Refresh-EnvHint
"""
        node_script = r"""
Astra-Progress 18
Write-Step "Установка Node.js LTS и TypeScript tooling"
$node = Get-Command node -ErrorAction SilentlyContinue
$npm = Get-Command npm -ErrorAction SilentlyContinue
if (-not $node -or -not $npm) {
    Ensure-Winget
    & winget install -e --id OpenJS.NodeJS.LTS --accept-source-agreements --accept-package-agreements
    if ($LASTEXITCODE -ne 0) { throw "Не удалось установить Node.js LTS через WinGet." }
    Refresh-KnownPaths
    $node = Get-Command node -ErrorAction SilentlyContinue
    $npm = Get-Command npm -ErrorAction SilentlyContinue
    if (-not $node -and (Test-Path "C:\Program Files\nodejs\node.exe")) { $node = Get-Item "C:\Program Files\nodejs\node.exe" }
    if (-not $npm -and (Test-Path "C:\Program Files\nodejs\npm.cmd")) { $npm = Get-Item "C:\Program Files\nodejs\npm.cmd" }
}
if (-not $node -or -not $npm) { throw "Node.js установлен, но node/npm не удалось обнаружить или проверить." }
$nodePath = Resolve-ToolPath $node
$npmPath = Resolve-ToolPath $npm
if (-not $nodePath -or -not $npmPath) { throw "Не удалось получить путь к node/npm." }
& $nodePath --version
if ($LASTEXITCODE -ne 0) { throw "node найден, но не запускается корректно." }
& $npmPath --version
if ($LASTEXITCODE -ne 0) { throw "npm найден, но не запускается корректно." }
Write-Step "TypeScript + tsx"
& $npmPath install --global typescript tsx
if ($LASTEXITCODE -ne 0) { throw "Не удалось установить TypeScript/tsx через npm." }
$tsc = Get-Command tsc -ErrorAction SilentlyContinue
$tsx = Get-Command tsx -ErrorAction SilentlyContinue
if ($tsc) { & $tsc.Source --version }
if ($tsx) { & $tsx.Source --version }
Astra-Progress 36
Refresh-EnvHint
"""
        uv_script = r"""
Astra-Progress 34
Write-Step "Установка uv"
$uv = Get-Command uv -ErrorAction SilentlyContinue
if (-not $uv) {
    Ensure-Winget
    & winget install -e --id astral-sh.uv --accept-source-agreements --accept-package-agreements
    if ($LASTEXITCODE -ne 0) { throw "Не удалось установить uv через WinGet." }
    Refresh-KnownPaths
    $uv = Get-Command uv -ErrorAction SilentlyContinue
    if (-not $uv) { $uvPath = WinGet-Link "uv.exe"; if ($uvPath) { $uv = Get-Item $uvPath } }
}
if ($uv) {
    $uvPath = Resolve-ToolPath $uv
    if (-not $uvPath) { throw "Не удалось получить путь к uv." }
    & $uvPath --version
    if ($LASTEXITCODE -ne 0) { throw "uv найден, но не запускается корректно." }
} else {
    Write-Host "uv установлен, но ещё не появился в PATH текущего процесса. После перезапуска Astra он будет обнаружен автоматически."
}
Astra-Progress 40
Refresh-EnvHint
"""
        git_script = r"""
Astra-Progress 42
Write-Step "Установка Git"
$git = Get-Command git -ErrorAction SilentlyContinue
if (-not $git) {
    Ensure-Winget
    & winget install -e --id Git.Git --accept-source-agreements --accept-package-agreements
    if ($LASTEXITCODE -ne 0) { throw "Не удалось установить Git через WinGet." }
    Refresh-KnownPaths
    $git = Get-Command git -ErrorAction SilentlyContinue
    if (-not $git -and (Test-Path "C:\Program Files\Git\cmd\git.exe")) { $git = Get-Item "C:\Program Files\Git\cmd\git.exe" }
}
if ($git) {
    $gitPath = Resolve-ToolPath $git
    if (-not $gitPath) { throw "Не удалось получить путь к Git." }
    & $gitPath --version
    if ($LASTEXITCODE -ne 0) { throw "Git найден, но не запускается корректно." }
} else {
    Write-Host "Git установлен, но текущий процесс ещё не видит обновлённый PATH. Перезапусти Astra Studio."
}
Astra-Progress 50
Refresh-EnvHint
"""
        powershell_script = r"""
Astra-Progress 52
Write-Step "Установка PowerShell 7"
$pwsh = Get-Command pwsh -ErrorAction SilentlyContinue
if (-not $pwsh) {
    Ensure-Winget
    & winget install -e --id Microsoft.PowerShell --accept-source-agreements --accept-package-agreements
    if ($LASTEXITCODE -ne 0) { throw "Не удалось установить PowerShell 7 через WinGet." }
    Refresh-KnownPaths
    $pwsh = Get-Command pwsh -ErrorAction SilentlyContinue
    if (-not $pwsh -and (Test-Path "C:\Program Files\PowerShell\7\pwsh.exe")) { $pwsh = Get-Item "C:\Program Files\PowerShell\7\pwsh.exe" }
}
if ($pwsh) {
    $pwshPath = Resolve-ToolPath $pwsh
    if (-not $pwshPath) { throw "Не удалось получить путь к PowerShell 7." }
    & $pwshPath -NoProfile -Command '$PSVersionTable.PSVersion.ToString()'
    if ($LASTEXITCODE -ne 0) { throw "pwsh найден, но не запускается корректно." }
} else {
    Write-Host "PowerShell 7 установлен, но ещё не обнаружен в текущем PATH. Windows PowerShell остаётся fallback для Astra."
}
Astra-Progress 58
Refresh-EnvHint
"""
        godot_script = r"""
Astra-Progress 60
Write-Step "Установка Godot"
$godot = Get-Command godot -ErrorAction SilentlyContinue
if (-not $godot) {
    Ensure-Winget
    & winget install -e --id GodotEngine.GodotEngine --accept-source-agreements --accept-package-agreements
    if ($LASTEXITCODE -ne 0) { throw "Не удалось установить Godot через WinGet." }
    Refresh-KnownPaths
    $godot = Get-Command godot -ErrorAction SilentlyContinue
    if (-not $godot) { $godotPath = WinGet-Link "godot.exe"; if ($godotPath) { $godot = Get-Item $godotPath } }
}
if ($godot) {
    $godotPath = Resolve-ToolPath $godot
    if (-not $godotPath) { throw "Не удалось получить путь к Godot." }
    & $godotPath --version
    if ($LASTEXITCODE -ne 0) { throw "Godot найден, но не запускается корректно." }
} else {
    Write-Host "Godot установлен как portable alias, но текущий процесс ещё его не видит. Перезапусти Astra Studio."
}
Astra-Progress 68
Refresh-EnvHint
"""
        php_script = r"""
Astra-Progress 70
Write-Step "Установка PHP 8.4 CLI"
$php = Get-Command php -ErrorAction SilentlyContinue
if (-not $php) {
    Ensure-Winget
    & winget install -e --id PHP.PHP.8.4 --accept-source-agreements --accept-package-agreements
    if ($LASTEXITCODE -ne 0) { throw "Не удалось установить PHP 8.4 через WinGet." }
    Refresh-KnownPaths
    $php = Get-Command php -ErrorAction SilentlyContinue
    if (-not $php) { $phpPath = WinGet-Link "php.exe"; if ($phpPath) { $php = Get-Item $phpPath } }
}
if ($php) {
    $phpPath = Resolve-ToolPath $php
    if (-not $phpPath) { throw "Не удалось получить путь к PHP." }
    & $phpPath --version | Select-Object -First 1 | Write-Host
    if ($LASTEXITCODE -ne 0) { throw "PHP найден, но не запускается корректно." }
} else {
    Write-Host "PHP установлен, но ещё не обнаружен в текущем PATH. Перезапусти Astra Studio."
}
Astra-Progress 78
Refresh-EnvHint
"""
        update_script = r"""
Astra-Progress 5
Write-Step "Обновление установленных языков и инструментов"
Ensure-Winget | Out-Null
$ids = @(
    "Python.Python.3.14",
    "astral-sh.uv",
    "OpenJS.NodeJS.LTS",
    "Git.Git",
    "Microsoft.PowerShell",
    "MSYS2.MSYS2",
    "EclipseAdoptium.Temurin.21.JDK",
    "GodotEngine.GodotEngine",
    "PHP.PHP.8.4"
)
$progress = 8
foreach ($id in $ids) {
    if (-not (Test-WingetInstalled $id)) {
        Write-Host "Пропуск (не установлен): $id"
        continue
    }
    Write-Step "Обновление $id"
    & winget upgrade -e --id $id --accept-source-agreements --accept-package-agreements
    if ($LASTEXITCODE -ne 0) { Write-Warning "WinGet не обновил $id (возможно, пакет уже актуален)." }
    $progress = [Math]::Min(68, $progress + 7)
    Astra-Progress $progress
}
Refresh-KnownPaths
$npm = Get-Command npm -ErrorAction SilentlyContinue
if ($npm) {
    Write-Step "Обновление TypeScript tooling"
    $npmPath = Resolve-ToolPath $npm
    if (-not $npmPath) { throw "Не удалось получить путь к npm." }
    & $npmPath install --global typescript@latest tsx@latest
    if ($LASTEXITCODE -ne 0) { Write-Warning "npm не смог обновить TypeScript/tsx." }
}
Astra-Progress 78
$bash = "C:\msys64\usr\bin\bash.exe"
if (Test-Path $bash) {
    Write-Step "Обновление пакетов MSYS2 / C++"
    & $bash -lc "pacman -Syu --noconfirm"
    if ($LASTEXITCODE -ne 0) { Write-Warning "pacman -Syu завершился ненулевым кодом." }
    & $bash -lc "pacman -S --needed --noconfirm mingw-w64-ucrt-x86_64-gcc"
    if ($LASTEXITCODE -ne 0) { Write-Warning "Не удалось обновить/проверить пакет g++." }
    Add-UserPath "C:\msys64\ucrt64\bin"
}
Astra-Progress 92
Refresh-EnvHint
Astra-Progress 100
"""
        if kind == "python":
            return common + python_script + uv_script + "Astra-Progress 100\n"
        if kind == "node":
            return common + node_script + "Astra-Progress 100\n"
        if kind == "git":
            return common + git_script + "Astra-Progress 100\n"
        if kind == "godot":
            return common + godot_script + "Astra-Progress 100\n"
        if kind == "php":
            return common + php_script + "Astra-Progress 100\n"
        if kind == "powershell":
            return common + powershell_script + "Astra-Progress 100\n"
        if kind == "cpp":
            return common + cpp_script
        if kind == "java":
            return common + java_script
        if kind == "shortcut":
            return common + shortcut_script
        if kind == "update_all":
            return common + update_script
        if kind == "all":
            # Core StaffedUp workstation set. Godot/PHP stay explicit because they are role-specific.
            return common + python_script + uv_script + node_script + git_script + powershell_script + cpp_script + java_script + shortcut_script + "Astra-Progress 100\n"
        return common + "Write-Host 'Неизвестная задача установщика.'\n"

    def install_toolchain(self, kind: str):
        if self.task_manager.has_active_task():
            self.installer_console.appendPlainText("\nУстановка/долгая операция уже запущена. Дождись завершения или нажми «Отмена».")
            self.open_installer_tab()
            return

        if os.name != "nt":
            QMessageBox.information(
                self,
                "Установщик",
                f"Автоматический установщик {APP_VERSION} рассчитан на Windows через WinGet. "
                "На Linux/macOS используй системный пакетный менеджер.",
            )
            return

        titles = {
            "python": "Установка Python",
            "cpp": "Установка C++ toolchain",
            "java": "Установка Java JDK",
            "node": "Установка Node.js LTS + TypeScript",
            "git": "Установка Git",
            "godot": "Установка Godot",
            "php": "Установка PHP 8.4",
            "powershell": "Установка PowerShell 7",
            "all": "Установка основного набора StaffedUp",
            "update_all": "Обновление языков",
            "shortcut": "Создание ярлыка",
        }
        self.open_installer_tab()
        self.installer_console.clear()
        self.installer_console.appendPlainText(f"▶ {titles.get(kind, 'Установщик')}\n")
        self.installer_console.appendPlainText("Операция может занять несколько минут. Если Windows запросит подтверждение — разреши установку.\n")
        self.set_progress(0, "Выполнение: 0%")
        self.status_pill.setText("установка")

        script_path = self.data_dir / f"installer_{kind}.ps1"
        script_path.write_text(self._installer_script(kind), encoding="utf-8-sig")
        args = ["-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script_path)]
        self.installer_console.appendPlainText(f"▶ Команда: powershell.exe {' '.join(args)}\n")
        self._start_process_task(
            "installer_" + kind,
            titles.get(kind, "Установщик"),
            "powershell.exe",
            args,
            self.data_dir,
            {"mode": "installer", "target": "installer", "kind": kind, "indeterminate": False},
            0,
            100,
            False,
        )

    def _append_to_installer(self, text: str):
        self.installer_console.moveCursor(QTextCursor.MoveOperation.End)
        self.installer_console.insertPlainText(text)
        self.installer_console.ensureCursorVisible()

    def _read_install_stdout(self):
        data = self.install_process.readAllStandardOutput().data().decode("utf-8", errors="replace")
        visible_lines = []
        for line in data.splitlines(True):
            clean = line.strip()
            if clean.startswith("ASTRA_PROGRESS:"):
                try:
                    value = int(clean.split(":", 1)[1])
                    self.set_progress(value, f"Выполнение: {value}%")
                except ValueError:
                    pass
            else:
                visible_lines.append(line)
        if visible_lines:
            self._append_to_installer("".join(visible_lines))

    def _read_install_stderr(self):
        data = self.install_process.readAllStandardError().data().decode("utf-8", errors="replace")
        self._append_to_installer(data)

    def _install_finished(self, kind: str, exit_code: int, _exit_status):
        refresh_runtime_paths()
        self.installer_console.appendPlainText(f"\n■ Установщик завершён с кодом {exit_code}")
        self.set_progress(100 if exit_code == 0 else max(1, self.install_progress_bar.value()), "Выполнение завершено" if exit_code == 0 else "Остановка из-за ошибки")
        if exit_code == 0:
            self.status_pill.setText("готово")
            self.installer_console.appendPlainText("✓ Готово. Теперь можно снова нажать «Проверить инструменты» или запустить код.")
        else:
            self.status_pill.setText("сбой")
            self.installer_console.appendPlainText("✕ Установка завершилась с ошибкой. Проверь текст выше: чаще всего не найден WinGet, нет интернета или Windows требует подтверждение.")

    def _ask_install_now(self, language_name: str):
        mapping = {"Python": "python", "C++": "cpp", "Java": "java"}
        kind = mapping.get(language_name)
        if not kind:
            return
        answer = QMessageBox.question(
            self,
            "Не найден инструмент",
            f"Для языка {language_name} не найден нужный компилятор/интерпретатор. Запустить автоматический установщик сейчас?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.install_toolchain(kind)

    def open_folder_dialog(self):
        folder = QFileDialog.getExistingDirectory(self, "Выбрать рабочую папку", str(self.workspace_dir))
        if not folder:
            return
        self._save_current_project_state()
        self.current_project_name = "Рабочая папка"
        self.current_project_config_path = ""
        self.attached_project_folders = []
        self.project_python_interpreter = ""
        self.project_commands = {key: "" for key in COMMAND_KEYS}
        self.project_staffedup_meta = {}
        self.test_explorer_last_run = None
        self.test_explorer_discovered = []
        self.test_explorer_adapters = []
        self.test_explorer_active_adapter = ""
        self.git_repo_root = None
        self.git_state = None
        self.git_last_diff_path = ""
        self.git_last_diff_staged = False
        if hasattr(self, "git_tree"):
            self._render_git_state(None, "Git: статус не проверен для новой рабочей папки")
        if hasattr(self, "test_tree"):
            self._render_test_nodes([], "Тесты: ещё не запускались")
        self.project_main_folder = Path(folder)
        self.workspace_dir = self.project_main_folder
        if hasattr(self, "lsp_manager"):
            self._queued_lsp_requests.clear()
            self.lsp_manager.set_project_root(self.project_main_folder)
        QTimer.singleShot(0, self._resync_open_project_editors_lsp)
        self.workspace_label.setText("Рабочая папка:\n" + str(self.workspace_dir))
        self.refresh_project_tree()
        self._save_settings()
        self.restart_terminal()
        self._refresh_python_environment_status()
        self.statusBar().showMessage(f"Рабочая папка изменена: {self.workspace_dir}", 3000)

    def close_tab(self, index):
        editor = self.tabs.widget(index)
        if isinstance(editor, CodeEditor) and editor.document().isModified():
            answer = QMessageBox.question(
                self,
                "Закрыть вкладку",
                f"Файл «{self.tab_title_for_editor(editor).replace('● ', '')}» изменён. Сохранить перед закрытием?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
            )
            if answer == QMessageBox.StandardButton.Cancel:
                return
            if answer == QMessageBox.StandardButton.Yes:
                self.tabs.setCurrentIndex(index)
                if not self.save_current_file_without_format():
                    return
        if isinstance(editor, CodeEditor) and editor.file_path is not None:
            self.lsp_manager.close_document(editor.language_name, editor.file_path)
        self.tabs.removeTab(index)
        if self.tabs.count() == 0:
            self.new_from_template()
        self._save_current_project_state()

    def _stop_process_safely(self, process: QProcess | None, name: str):
        if not process:
            return
        try:
            if process.state() == QProcess.ProcessState.NotRunning:
                return
            process.terminate()
            if not process.waitForFinished(1200):
                process.kill()
                process.waitForFinished(1200)
            self.write_log(f"Процесс остановлен при закрытии: {name}")
        except Exception as exc:
            self.write_exception_log(f"Ошибка остановки процесса при закрытии: {name}", exc)

    def _confirm_unsaved_before_exit(self) -> bool:
        for i in range(self.tabs.count()):
            editor = self.tabs.widget(i)
            if not isinstance(editor, CodeEditor) or not editor.document().isModified():
                continue
            self.tabs.setCurrentIndex(i)
            name = self.tab_title_for_editor(editor).replace("● ", "")
            answer = QMessageBox.question(
                self,
                "Выход из Astra Studio",
                f"Файл «{name}» изменён. Сохранить перед выходом?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Yes,
            )
            if answer == QMessageBox.StandardButton.Cancel:
                return False
            if answer == QMessageBox.StandardButton.Yes and not self.save_current_file_without_format():
                return False
        return True

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "background_label") and hasattr(self, "root"):
            self.background_label.setGeometry(self.root.rect())
        if hasattr(self, "wallpaper_dim_overlay") and hasattr(self, "root"):
            self.wallpaper_dim_overlay.setGeometry(self.root.rect())

    def closeEvent(self, event):
        try:
            self.write_log("Запрошено закрытие окна Astra Studio")
            if self._has_active_background_task() or (self.run_process and self.run_process.state() != QProcess.ProcessState.NotRunning):
                answer = QMessageBox.question(
                    self,
                    "Выход из Astra Studio",
                    "Сейчас выполняется компиляция, запуск программы, установка или другая долгая операция. Отменить задачу и закрыть приложение?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if answer != QMessageBox.StandardButton.Yes:
                    event.ignore()
                    self.write_log("Закрытие отменено пользователем: активная задача")
                    return
                self.task_manager.cancel_and_wait(1800)
                self.active_task_context = {}
                self._stop_process_safely(self.run_process, "запуск программы")
            if not self._confirm_unsaved_before_exit():
                event.ignore()
                self.write_log("Закрытие отменено пользователем")
                return
            self._save_current_project_state()
            self._save_settings()
            # LSP servers are long-lived child processes; close them before the
            # terminal/install processes so Astra never leaves orphan servers.
            if hasattr(self, "lsp_manager"):
                self.lsp_manager.shutdown_all(wait=True)
            self._stop_process_safely(self.run_process, "запуск программы")
            self._stop_process_safely(self.terminal_process, "терминал")
            self._stop_process_safely(self.install_process, "установщик")
            if self._pending_update_command is not None:
                program, args = self._pending_update_command
                started = QProcess.startDetached(program, args)
                started_ok = started[0] if isinstance(started, tuple) else bool(started)
                if not started_ok:
                    self._pending_update_command = None
                    event.ignore()
                    QMessageBox.warning(
                        self,
                        "Обновление Astra Studio",
                        "Не удалось запустить проверенный установщик обновления. Приложение оставлено открытым.",
                    )
                    return
                self._pending_update_command = None
            event.accept()
            self.write_log("Astra Studio закрыта корректно")
        except Exception as exc:
            self.write_exception_log("Критическая ошибка при закрытии окна", exc)
            QMessageBox.warning(
                self,
                "Закрытие Astra Studio",
                "При закрытии возникла ошибка, но приложение не будет аварийно завершено. "
                f"Подробности записаны в лог:\n{self.log_path}",
            )
            event.accept()


def set_windows_app_user_model_id():
    if os.name != "nt":
        return
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(WINDOWS_APP_USER_MODEL_ID)
    except Exception:
        pass

def main():
    set_windows_app_user_model_id()
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName("Astra")
    icon = resource_path("assets/astra.ico")
    if icon.exists():
        app.setWindowIcon(QIcon(str(icon)))

    window = AstraStudio()
    if icon.exists():
        window.setWindowIcon(QIcon(str(icon)))
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
