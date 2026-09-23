# Публикация обновлений Astra Studio

Клиент обновлений читает ограниченный по размеру HTTPS JSON manifest и только после подтверждения пользователя скачивает ZIP. До установки он проверяет размер, SHA-256 и безопасную структуру архива; непроверенный архив никогда не заменяет приложение.

## 1. Подготовить portable ZIP

Соберите приложение командой `build_exe.bat`, затем упакуйте **всю** папку `dist\Astra Studio`, включая `_internal`.

## 2. Сгенерировать manifest

Из корня source release выполните:

```powershell
.\.venv\Scripts\python.exe scripts\make_update_feed.py `
  "<путь-к-portable.zip>" `
  --version "Release 3.17" `
  --download-url "https://github.com/alarongh/Astra-Studio-Releases/releases/download/v3.17/Astra_Studio_Release_3_17.zip" `
  --notes-url "https://github.com/alarongh/Astra-Studio-Releases/releases/tag/v3.17" `
  --output update/latest.json
```

Скрипт вычисляет SHA-256 и фактический размер архива. Не редактируйте эти поля вручную.

## 3. Опубликовать

Загрузите portable ZIP и `latest.json` на HTTPS-хостинг. URL из `download_url` должен указывать на опубликованный ZIP.

Пример структуры `latest.json`:

```json
{
  "schema_version": 1,
  "channel": "stable",
  "version": "Release 3.17",
  "download_url": "https://github.com/alarongh/Astra-Studio-Releases/releases/download/v3.17/Astra_Studio_Release_3_17.zip",
  "sha256": "64 lowercase hex symbols",
  "size": 123456789
}
```

## 4. Подключить приложение к feed

Перед финальной сборкой укажите HTTPS URL manifest в `update_channel.json`:

```json
{
  "schema_version": 1,
  "channel": "stable",
  "manifest_url": "https://raw.githubusercontent.com/alarongh/Astra-Studio-Releases/main/update/latest.json"
}
```

Для локальной проверки без пересборки можно временно задать `ASTRA_UPDATE_MANIFEST_URL`. HTTP, URL со встроенным логином/паролем, некорректные версии, размер или SHA-256 отклоняются.

## Порядок следующего релиза

Сначала загрузите новый ZIP, затем замените `latest.json` атомарно. Так клиент никогда не увидит manifest, который ссылается на ещё не загруженный файл. Удаление старого ZIP выполняйте только после проверки нового feed на чистом компьютере.
