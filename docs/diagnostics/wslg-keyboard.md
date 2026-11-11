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
