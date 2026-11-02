# Служебная папка (для разработчика)

Отсюда GitHub Actions (`.github/workflows/installer.yml`) собирает всё, что лежит в `downloads/`:
установщик и три архива (x64, x86, ARM64). Пользователям эта папка не нужна: скачивайте файлы из [релизов](https://github.com/VizitSpace/klira/releases/latest).

- `Klira_<версия>_binaries.zip` — готовые программы для трёх архитектур
- `VERSION` — номер версии, которую нужно собрать
- `Klira.iss` — скрипт установщика (Inno Setup)
- `on.ico` — значок установщика
