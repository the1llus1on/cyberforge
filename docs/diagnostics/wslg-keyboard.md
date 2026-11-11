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
