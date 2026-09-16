# Astra Studio — Release 3.11

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
- Добавлен новый Angel 404 icon и выбор из трёх оформлений ярлыка: Astra 3.11, Angel 404 и Astra Legacy.
- Создание ярлыка исправлено для обычного, русскоязычного и OneDrive Desktop; отдельная кнопка создаёт настоящий `.lnk` и проверяет результат.

## Проверка

- Реальный Temurin JDK 21.0.11 прошёл полный `install_java.ps1` в Windows PowerShell с кодом 0.
- Добавлены Release 3.11 regressions для identity, installer wiring, stderr-only version command и полного Java workflow.
- Windows gate: `250 passed, 2 skipped`, плюс `88 subtests passed`; реальная компиляция/запуск русской строки, циклический completion и Windows `.lnk` выполнены на целевой системе.
- Публичный update feed остаётся выключенным до подключения домена издателя.
