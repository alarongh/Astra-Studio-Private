# Astra Studio — Release 3.13

## C++

- Плоский каталог заменён type-aware offline provider для C++20/23.
- Распознаются локальные `string`, STL containers, file streams, `optional`, smart pointers, threads и futures; completion работает после `.` и `->`.
- Предложения `std::vector`, algorithms, streams и других стандартных символов автоматически добавляют нужный `#include`, но не дублируют существующий.
- Добавлены современные keywords (`concept`, `requires`, coroutines, `consteval`, `constinit`) и новые snippets для range-for, функций, lambda, vector, smart pointers и namespace.
- Реальная C++23 программа с vector/map/algorithm/numeric/smart pointer проходит компиляцию `g++ -std=c++23` и запуск.

## Python libraries

- Реестр проверен по текущему PyPI JSON API и расширен с 41 до 67 тщательно сопоставленных import/package записей.
- Добавлены HTTPX, aiohttp, Pydantic, Django, Jinja2, WebSockets, aiofiles, pypdf, XlsxWriter, Markdown, PyMongo, Redis, DuckDB, Polars, NetworkX, Rich, Typer, tqdm, cryptography, OpenAI client, psutil, watchdog, Hypothesis и pytest-cov.
- Количество готовых наборов увеличено с 6 до 12: Web/API, async, CLI, документы, базы данных и тестирование.
- Selenium и Playwright видимы в каталоге, но помечены unsafe/experimental и никогда не ставятся автоматически.
- Добавлены детерминированная проверка качества registry и генератор `data/python_libraries.json`, исключающий рассинхронизацию Python/JSON.

## Сохранено из Release 3.12

## Интерфейс и дерево проекта

- Обои рисуются в исходном разрешении по центру: изменение размера окна больше не растягивает фон и не связывает его масштаб с панелями приложения.
- Дерево проекта больше не обрывается после четырёх уровней; безопасный предел увеличен до 32 уровней и 5000 элементов.
- Полные имена в дереве не заменяются многоточием, доступна горизонтальная прокрутка, а высота строк пересчитывается под выбранный глобальный шрифт.
- Поле номеров строк получило дополнительный запас для широких glyphs Minecraft-шрифта и высокого DPI.
- В выборе языка временно показаны Java, Python, C++, JavaScript, HTML и CSS. Остальные реализации, расширения, подсветка и runtime-код сохранены.

## Обновления

- Stable feed подключён к публичному GitHub `latest.json`.
- Кнопка обновления скачивает portable ZIP внутри приложения, проверяет точный размер, SHA-256, ZIP traversal, symlink entries, лимиты распаковки и обязательный EXE.
- После подтверждённой проверки отдельный Windows updater ждёт закрытия Astra, сохраняет предыдущую папку для отката, устанавливает новую и перезапускает приложение.
- При любой ошибке проверки текущая установка не изменяется; installer пишет отдельный журнал.

## Java autocomplete

- Добавлены расширенные методы String, List/ArrayList, Map/HashMap, Set, Stream, CompletableFuture, regex, BigDecimal, Thread, Objects и Executors.
- Добавлено распознавание массивов (`length`), локальных `var = new Type(...)` и методов текущего класса через `this.`.
- Каталог стандартных классов дополнен concurrent, IO и utility API с безопасным авто-import.

## Исправлено

- StaffedUp installer больше не считает успешный `java -version` ошибкой только потому, что Java штатно пишет версию в stderr.
- Native version probes запускаются через `System.Diagnostics.Process` с раздельными stdout/stderr и проверкой настоящего exit code.
- Исправление внесено и в standalone `scripts/install_java.ps1`, и во встроенный installer, который Astra разворачивает в `%LOCALAPPDATA%\AstralStudio\installer`.
- Fallback-проверка теперь требует работоспособности одновременно `javac` и `java`.
- Runtime resolver больше не смешивает `javac` из нового JDK и `java` из старого JRE в PATH: обе команды выбираются из одного JDK через `JAVA_HOME`/`JDK_HOME`, PATH или стандартные каталоги поставщиков.
- Ошибка исходного Java-кода больше не вызывает предложение установить JDK. Вывод `javac` остаётся в консоли и преобразуется в записи вкладки **Проблемы** со строкой, колонкой, severity и сообщением.
- Логи различают обнаружение runtime, команду/код завершения компиляции, отказ запуска компилятора и код завершения Java-программы.
- Устранены «кракозябры» кириллицы в Java-консоли: `javac`, stdout и stderr запускаемой JVM теперь явно работают в UTF-8; декодер фоновой задачи использует заданную для процесса кодировку.

## Автодополнение

- Добавлен общий registry встроенных completion providers без обязательной зависимости от language server.
- Offline-каталог расширен до 15 языков и форматов: Python, C++, Java, JavaScript, TypeScript, C#, PHP, PowerShell, SQL, HTML, CSS, GDScript, Luau, Shell и Dockerfile.
- Первый Tab в popup только выбирает нулевой вариант; следующие Tab циклически переключают строки. Space вставляет выбранное дополнение и пробел, Enter или мышь — только дополнение.
- Автоматический popup с debounce предлагает Java keywords, символы текущего документа, типовые классы стандартной библиотеки и методы известных локальных типов.
- Проверены `pub` → `public`, `cla` → `class`, локальный `cou` → `count`, `text.` → методы `String`, `ArrayL` → `ArrayList` с `import java.util.ArrayList;`.
- Suggestions не появляются внутри строк, `//` и `/* ... */`; exact snippets продолжают приниматься Tab, а неполный `cla` больше не разворачивает целый class-snippet.
- Полный semantic completion через `jdtls` остаётся доступен отдельно по `Ctrl+Space`, если сервер установлен или настроен.

## Оформление

- Включены профиль Angel 404, приложенные обои и глобальный `Minecraft Rus` из предыдущего кандидата.
- Выбранный шрифт применяется к Qt application, контролам, вкладкам, редактору, документу редактора и консолям.
- Добавлен новый Angel 404 icon и выбор из трёх оформлений ярлыка: Astra 3.13, Angel 404 и Astra Legacy.
- Создание ярлыка исправлено для обычного, русскоязычного и OneDrive Desktop; отдельная кнопка создаёт настоящий `.lnk` и проверяет результат.

## Проверка

- Реальный Temurin JDK 21.0.11 прошёл полный `install_java.ps1` в Windows PowerShell с кодом 0.
- Добавлены Release 3.13 regressions для C++ provider, настоящей C++23 сборки, Python registry и сохранённых 3.12 исправлений.
- Windows gate: `250 passed, 2 skipped`, плюс `88 subtests passed`; реальная компиляция/запуск русской строки, циклический completion и Windows `.lnk` выполнены на целевой системе.
- Публичный update feed подключён к GitHub Releases; отдельный домен можно добавить позже без пересборки логики updater.
