# Діагностика українського введення WSLg

Перевірено під час рев’ю PR #3. Середовище: WSLg 1.0.73, Qt/PySide6 6.10.3,
Wayland; LANG=C.UTF-8; `/usr/share/X11/xkb/symbols/ua` наявний.
`setxkbmap`/`xkbcli` відсутні. У застосунку для імені, назви групи й опису
немає ASCII validator, input mask або обробника, що відкидає Unicode.
Логіни навмисно ASCII; це не обмеження решти полів.

У `/mnt/wslg/weston.log` зафіксовано послідовність:

```text
KeyboardLayout: 0x20422
matching model=pc105 layout=(null) variant=(null) options=(null)
Failed to switch to kbd_layout:0x20422
Resetting default keymap
```

Перемикання на `0x409` у тому самому журналі успішне (`layout=us`). Це
конкретна помилка перетворення Windows/RDP layout → XKB у Weston до Qt.
Введення в Windows Terminal не проходить цей шлях і не спростовує діагноз.

[Microsoft](https://learn.microsoft.com/en-gb/windows-hardware/manufacture/desktop/default-input-locales-for-windows-language-packs?view=windows-10)
визначає Ukrainian Enhanced як 00020422.
[FreeRDP keyboard identifiers](https://github.com/FreeRDP/FreeRDP/blob/master/include/freerdp/locale/keyboard.h)
визначають звичайну Ukrainian як 00000422;
[Weston upstream fix](https://github.com/microsoft/weston-mirror/pull/150/files)
стосується підтримки додаткових українських розкладок.

## Рекомендована перевірка власником

1. Windows Settings → Time & language → Language & region → Ukrainian →
   Language options → Keyboards: додати звичайну Ukrainian (00000422),
   зберігши поточну Enhanced. Перемкнутися на звичайну через Win+Space.
2. Запустити застосунок з `QT_QPA_PLATFORM=wayland` і набрати український
   текст у трьох полях. Перевірити, що нові записи weston.log містять
   `layout=ua`, без `Failed to switch`/`Resetting default keymap`.
3. Якщо проблема залишається, перевірити версію через `wsl --version` у
   PowerShell і розглянути `wsl --update`. `wsl --shutdown` закриває всі WSL
   процеси: виконувати лише після збереження роботи, потім повторити запуск.

Це цільова рекомендація за зафіксованим layout ID, а не твердження, що
перемикання вже виконано чи фізичне введення після нього успішне. Агент не
має доступу до фізичної клавіатури/Windows Settings власника. Системні
налаштування не змінювалися. Змінювати locale або викликати setxkbmap для
Wayland без доказів не пропонується.

## Автоматизовані докази та межі

У справжньому WSLg виконано GUI-тест: окремі QKeyEvent із українським text
і QInputMethodEvent commit проходять у display-name/group-name/description.
Також popup ролей вибирається одним лівим кліком і одразу оновлює currentData
без запису БД. Це перевіряє Qt/UI, але синтетичні події не є фізичним вводом
через RDP/XKB. Підтвердження фізичної клавіатури власником залишається потрібним.

## Повторна фізична перевірка власника — проблема не закрита

Свіжі записи Weston повторюють помилку 0x20422 (зокрема 21:08:00 за часом
журналу). Отже, попередня рекомендація не була підтвердженим виправленням.
Unicode key/input-method події доводять лише приймання символів Qt-полями.
Додаткову проблему на шляху фізичних подій Qt/Wayland ще не виключено.

Додано `tools/keyboard_probe.py`: чисті QLineEdit без доменних сервісів,
підключення БД, validators і запису клавіш. Порядок ручного порівняння:

1. У WSL: `QT_QPA_PLATFORM=wayland uv run python tools/keyboard_probe.py`.
   Поруч запустити CyberForge, вибрати ту саму Windows-розкладку й фізично
   набрати `Україна Київ ї є ґ` у всіх трьох полях обох вікон.
2. Перевірити свіжий фрагмент `/mnt/wslg/weston.log` на `KeyboardLayout`,
   `Failed to switch` і `Resetting default keymap`. Не збирати повні логи
   або введені паролі. Якщо обидва вікна не працюють і є mapping error,
   це підтверджує збій нижче бізнес-логіки CyberForge.
3. За бажанням власника перевірити звичайну Ukrainian 00000422 замість
   Enhanced, як описано вище. Успіх підтверджувати лише реально набраним
   текстом і відсутністю нового mapping error. Системні налаштування агент
   не змінює; наявну розкладку не видаляти.
4. Для native Windows скопіювати джерела в окремий робочий каталог Windows,
   установити Python 3.12/uv за звичайною процедурою README, виконати
   `uv sync --locked`, потім `uv run python tools/keyboard_probe.py` у PowerShell.
   Не задавати QT_QPA_PLATFORM=wayland. Вікно має показати backend `windows`.
   Наявну demo-БД або credentials не переносити й не ініціалізувати заново.
5. Якщо native probe працює, а WSLg probe — ні, наступна діагностична дія —
   звернення до WSLg з версіями та фрагментом mapping error або погоджене
   власником оновлення WSLg. Якщо probe працює, а CyberForge — ні, потрібен
   окремий захват фізичних подій у несекретних полях застосунку.

Windows interop перевірено лише read-only: `py -0p` знаходить Python 3.13;
`py -3.13 -m pip show PySide6` повідомляє, що пакет відсутній. Windows uv
не знайдено. Це не готове цільове Python 3.12/PySide6 середовище: native
Windows запуск і фізична клавіатура не перевірені. Нічого не встановлювалося.
Надійний фізичний workaround поки не підтверджено; дефект лишається відкритим.

Окреме обмеження GUI-автоматизації: QtTest mouse не дає Wayland compositor
input serial/warp, і Qt повідомляє `Failed to create grabbing popup`.
Три тести повної mouse-послідовності popup запускаються offscreen/CI, але
явно skip у Wayland. Keyboard popup acceptance/dismissal тестуються у WSLg.
Це обмеження тесту не є доказом ані успіху, ані збою фізичного кліку власника.

## Нові upstream-докази та фізичне підтвердження власника

Стан перевірено GitHub MCP 11.11.2026:

- [WSLg #1522](https://github.com/microsoft/wslg/issues/1522) — OPEN,
  popup QComboBox лишається видимим у Wayland; автор повідомляє, що xcb
  поводиться інакше. Це upstream observation, не перевірка xcb CyberForge.
- [Weston #172](https://github.com/microsoft/weston-mirror/pull/172) — OPEN,
  merged=false. Пропонує popup placement/RAIL synchronization/dismissal fix,
  а не виправлення української клавіатури. Посилання на PR не означає реліз.
- [Weston #150](https://github.com/microsoft/weston-mirror/pull/150) — OPEN,
  merged=false. Додає 0x20422 → ua/enhanced і 0xa0000422 → ua/unicode;
  автор прямо зазначив відсутність власного тестування.
- [WSL releases](https://github.com/microsoft/WSL/releases/tag/3.0.5): latest
  release 3.0.5 не оголошує цього keyboard fix. Переглянуті standalone WSLg
  releases (1.0.71 prerelease, 1.0.69 prerelease, 1.0.66 stable) також не
  підтверджують його доставку. Цей список не тотожний усім bundled-версіям
  WSLg; на підставі перевірених джерел офіційний реліз із цим fix не встановлено.
  Локально 1.0.73 містить Weston 2318feca й зафіксований mapping failure.

Власник фізично підтвердив: Enhanced не вводить український текст ані в
CyberForge, ані у чистому probe; Standard Ukrainian вводить його. Це
підтверджує environment проблему Enhanced і робочу стандартну конфігурацію
для typing, але НЕ для всіх shortcuts: Ctrl+V під Standard не працює, English
Ctrl+V працює. Не перебудовувати Weston і не переносити неперевірений patch
у системну WSLg. Standard Ukrainian — обраний власником безпечний шлях
введення тексту, не універсальне виправлення Enhanced.

## Ctrl+V: необхідне порівняння фізичних подій

`tools/keyboard_probe.py` тепер показує metadata лише Ctrl-комбінацій та
Shift+Insert: backend, числові Qt key/modifiers/native scan/native virtual key,
і збіг із Qt StandardKey Copy/Paste/Cut/SelectAll. Він не читає event.text(),
clipboard або credentials, не пише файлів/stdout, пропускає звичайні символи,
Alt/AltGr/GroupSwitch і password fields. Спостереження не споживає подій.
Журнал обмежено 24 рядками в самому вікні, поле Qt Paste показує platform
standard bindings. Не вводьте паролі; використовуйте тільки тестові дані.

1. Запустити `QT_QPA_PLATFORM=wayland uv run python tools/keyboard_probe.py`.
2. У полі Ім’я з English фізично натиснути Ctrl+V, Ctrl+C, Ctrl+X, Ctrl+A.
   Потім у Standard Ukrainian повторити ті самі комбінації. Надіслати лише
   metadata-рядки, без тексту полів або clipboard. Порівняти key/scan/modifiers
   і `standard=Paste` для обох Ctrl+V.
3. Під Standard Ukrainian натиснути Shift+Insert; перевірити фактичну вставку
   й відповідний рядок metadata. Це можливий workaround, поки не
   підтверджений власником. Праве меню «Вставити» також потребує фізичної
   перевірки через окреме upstream обмеження popup.
4. Якщо Ctrl+V під Ukrainian приходить як інша Qt key при тому самому scan
   та точному Ctrl без Alt/GroupSwitch, це підстава для вузької platform-
   scoped корекції. Не hardcode-ити scan code за припущенням. Якщо key та
   standard збігаються, потрібно досліджувати delivery/shortcut dispatch,
   а не мовну транслітерацію. Потрібні також C/X/A події для повної корекції.

На момент реалізації цих метаданих власника ще немає. Application-level
shortcut mapping не додано: непідтверджений mapping міг би зламати Unicode,
AltGr або password protections. Ctrl+V під Standard залишається відкритим
фізичним дефектом. Синтетичні StandardKey/Shift+Insert тести — лише baseline
Qt, не доказ правильності фізичного XKB path. Native Windows порівняння з
попереднього розділу залишається альтернативною діагностикою, ще не виконаною.

## Фізичні події отримано: причина Ctrl shortcuts підтверджена

Власник надав такі значення (hex):

| Дія | English Qt key | Standard Ukrainian Qt key | native scan |
|---|---|---|---|
| Copy | 43 | 421 | 36 |
| Paste | 56 | 41C | 37 |
| Cut | 58 | 427 | 35 |
| SelectAll | 41 | 424 | 26 |

У всіх випадках modifiers=04000000 (тільки Ctrl). English дає правильний
StandardKey, Ukrainian — `standard=-`. Під Standard фізичний Shift+Insert
працює: key=1000006, modifiers=22000000, scan=5A, standard=Paste. Текст
вводиться фізично під Standard. Enhanced і далі падає у Weston mapping.
Ці нові факти замінюють попередній статус «метаданих ще немає».

За цим доказом у CyberForge додано точну корекцію, описану в ADR-0002;
probe залишено без змін як baseline. Це не перепризначення глобальних клавіш
і не універсальна таблиця Linux/Windows scans. Нова фізична перевірка:

1. У CyberForge під Standard Ukrainian скопіювати/вирізати тестовий текст,
   вставити Ctrl+V, виділити Ctrl+A. Перевірити, що paste відбувається один раз.
2. Повторити English та Shift+Insert, звичайне українське введення й AltGr,
   якщо використовуєте його. Всі дії мають зберегти свою стандартну поведінку.
3. У password-полі перевірити paste/select-all на тестовому паролі; copy/cut
   не повинні переносити пароль у clipboard. Не надсилати паролі або clipboard.
4. У standalone probe Standard Ctrl+V може й далі не виконувати paste — це
   очікуваний baseline без app correction. Enhanced фізичне введення не
   оголошується виправленим. Native Windows залишається неперевіреним.

Автотести використовують точні owner key/scan/modifier дані, окремі негативні
сценарії, QLineEdit/QTextEdit/QPlainTextEdit native operations, signal count
та English/Shift+Insert. Фізичне виконання після зміни ще перевіряє власник.
