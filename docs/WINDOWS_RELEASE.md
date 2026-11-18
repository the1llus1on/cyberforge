# Підготовка випуску CyberForge для Windows 11 x64

## Збирання точного коміту

Потрібні нативні Windows 11 x64, CPython 3.12.16 x64, uv 0.13.7 і
Inno Setup 6.7.4. PyInstaller 6.22.3 і hooks 2026.10 встановлюються
із `uv.lock` у тимчасове середовище. Компілятор Inno Setup можна
розгорнути в новий тимчасовий каталог за допомогою
`release/windows/install_compiler.ps1`, який перевіряє Authenticode
офіційного пакета. Приготування на WSL допускається лише для архіву
коміту. Сам build виконується нативним Windows Python.
[PyInstaller Manual](https://www.pyinstaller.org/en/stable/),
[Inno Setup Downloads](https://jrsoftware.org/inno-setup/downloads).

У чистому checkout підготуйте архів поточного коміту:

```powershell
if (git status --porcelain) { throw "Потрібен чистий checkout." }
$sha = (git rev-parse HEAD).Trim()
$source = Join-Path $env:TEMP "cyberforge-source.tar"
git archive --format=tar "--output=$source" $sha
$uv = (Get-Command uv).Source
$inno = Join-Path $env:TEMP "cyberforge-inno"
./release/windows/install_compiler.ps1 -Destination $inno
uv run --no-project --python 3.12.16 python release/windows/build_release.py --archive $source --sha $sha --output "$env:TEMP/cyberforge-artifacts" --uv $uv --iscc "$inno/ISCC.exe"
```

Вихідний каталог має бути новим. Збирач перевіряє Git SHA в архіві,
створює повний onedir і перевіряє Qt platform plugin, WebEngine helper,
локалі/ресурси та Alembic revisions. Потім розпаковує готовий ZIP у
шлях із пробілами й кирилицею та запускає smoke з ізольованим Qt test
profile. Smoke запускає нативне вікно й внутрішній WebEngine документ.
Вхідні `.env`, локальні конфігурації та БД не включаються.
Windows Server 2022 CI має окремо маркований hosted manifest.
[Qt WebEngine deployment](https://doc.qt.io/qt-6/qtwebengine-deploying.html).

Manifest фіксує точний SHA, SHA-256 source archive і lockfile,
версії інструментів, Windows build, розміри та SHA-256 ZIP/інсталятора.
Опціональний підпис зовнішніх EXE використовує Windows SDK SignTool
з приватним ключем у certificate store. Передайте `--signtool`,
`--thumbprint` та HTTPS `--timestamp`. Збирач перевіряє цифрові
підписи доданих EXE, а хеші рахує після підписання. За замовчуванням
артефакти явно позначені як unsigned. [Сторонні ліцензії](../release/windows/THIRD_PARTY.md).

## Запуск і встановлення

Зіставте SHA-256 отриманих файлів із manifest з довіреного каналу.
У PowerShell використайте `Get-FileHash -Algorithm SHA256 <файл>`.
Для portable повністю розпакуйте ZIP і запустіть CyberForge.exe у
папці CyberForge. Для Inno Setup закрийте всі запущені копії CyberForge
і відкрийте інсталятор. Непідписана збірка може показати попередження
SmartScreen або бути заблокована чинною політикою. Дотримуйтеся
політики Windows та організації.
[Microsoft SmartScreen](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/smartscreen-reputation).

Installer працює для поточного користувача. Стала ідентичність setup
використовує `%LOCALAPPDATA%\Programs\CyberForge`; активний onedir
має підкаталог SHA збірки та актуальний ярлик у Start. Це відокремлює
оновлений payload від файлів старих версій. ZIP і встановлена копія
відкривають той самий захищений AppLocalDataLocation. Видалення
прибирає керовані файли програми та ярлики. База, резервні копії,
налаштування й Credential Manager зберігаються. Перевстановлення
використовує наявний профіль. Для запуску встановленої або portable
копії Python, uv, WSL та IDE не потрібні.
