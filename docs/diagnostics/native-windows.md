# Нативне тестове середовище Windows 11 — Phase 2

**Статус Phase 2: ACCEPTED власником 12.11.2026.** Власник підтвердив native
Windows 11 Enhanced input, keyboard shortcuts і physical minimum-size limits.
Докази прийняття — [окремий запис](../PHASE_2_ACCEPTANCE.md).

Під час підготовки власник повідомив про 9/10 фізичних WSLg перевірок:
ролі, CRUD, radio/checkbox interaction, Standard Ukrainian і English typing/
shortcuts, Shift+Insert, persistence, logout та обмеження доступу. Невирішена
WSLg перевірка — фізичне зменшення рамки нижче Qt minimum. Це відоме WSLg
обмеження зберігається після native acceptance. Phase 3 — NOT STARTED.

## Ізоляція та запуск

Дозволений workspace: `D:\Programs\Own\program\cyberforge-win-test`.
До підготовки він не існував. Джерела експортуються через `git archive HEAD`
у новий `source-<revision>`, без `.git`, WSL venv, `.local`, БД або credentials.
`SOURCE_REVISION.txt` і `environment.json` у test root указують точний snapshot.
Початковий snapshot — `04f01dbaccc2b32db8eb3f7d2b22c3fc6dcb38e3`.

Portable uv0.13.7 ZIP завантажено з офіційного GitHub release, SHA-256:
`0cdc5b38fe5a8168ed6a25814f5ba43c21d313dd3187314fccb37b7cec46e021`.
Native CPython3.12.16 x64 міститься в `.runtime\python`, Windows venv —
у snapshot `.venv`; cache/temp/tools також усередині workspace. Використано
`uv python install 3.12 --no-bin --no-registry`, явні local install/cache dirs
та `uv sync --locked --python <local-python> --no-python-downloads`.
PATH, registry, Python3.13, PyCharm, keyboard/WSL settings не змінювалися.

Для звичайного запуску двічі натисніть **Launch-CyberForge.cmd** у test root.
Це нативний PowerShell → `.venv\Scripts\python.exe`, без WSL/PyCharm/мережі.
Команда PowerShell:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File 'D:\Programs\Own\program\cyberforge-win-test\Launch-CyberForge.ps1' -TestRoot 'D:\Programs\Own\program\cyberforge-win-test'
```

ExecutionPolicy Bypass стосується тільки цього процесу; глобальна policy
не змінюється. Прапорці `-SmokeTest`, `-WindowProbe`, `-KeyboardProbe`
доступні окремо. Launcher задає backend `windows`, перевіряє local paths і
приватні demo ACL, не встановлює пакети й не ініціалізує дані при запуску.
Це acceptance workspace, не production installer.

## Незалежні demo-дані й ACL

Нова БД та нові випадкові credentials розміщені тільки в
`%LOCALAPPDATA%\CyberForge-Phase2-Native-<id>`. Точний шлях — `dataDirectory`
у `environment.json`. Новий каталог захищений до створення даних: inheritance
вимкнено, FullControl мають тільки поточний user SID, SYSTEM та Administrators;
файли БД/credentials успадковують ці правила. ACL перевірено через Get-Acl.
Це не захист від адміністратора ОС, який може змінити права.

Повторний explicit demo setup зберіг credentials; значення паролів та hashes
файлу не друкувалися. WSL demo та наявні owner credentials не копіювалися й
не змінювалися. Переглядайте новий JSON лише локально, не вставляйте його в
чат, скриншоти або журнал. Логіни: `Administrator_demo`, `teacher_demo_1`,
`learner_demo_2`; пароль кожного окремий, береться з нового приватного файлу.

## Початкові автоматизовані докази

Windows PowerShell5.1, sys.platform=win32, native CPython3.12.16 x64,
PySide6/Qt6.10.3, backend=windows. На snapshot04f01db: locked install,
Ruff, migrations/startup smoke — success; full pytest offscreen117 passed,
2 POSIX skips; native windows shell/geometry suite14 passed.

При наявному desktop scale125%: availableGeometry1536×816 logical,
DPR1.25, minimumSize1100×720, minimumSizeHint36×54. Preferred обмежився
1400×768. Programmatic resize(1,1) дав1100×720. WM_GETMINMAXINFO повернув
min tracking1393×947 physical pixels (з native decorations). Малий layout
minimumSizeHint не скасовує явний minimumSize.

Початковий frame(68,-6,1400,798) виходив на6 logical pixels вище available
screen. Внесено вузький showEvent clamp початкової рамки після визначення
decorations; він не фіксує розмір і не примушує resize під час роботи.
Регресія перевіряє frame containment і можливість подальшого resize; під
native backend також перевіряє WM_GETMINMAXINFO limits.

Додатковий native admin suite знайшов clipping sticky actions при1100×720:
1failed/30passed, хоча offscreen suite був успішний. При native font metrics
зовнішній QScrollArea використовував preferred heightForWidth730px, а його
viewport мав656px; нижній ряд кнопок опинявся за межами вікна. Стан незмінний
після30/300ms, це не asynchronous-resize test timing. AdminPage.heightForWidth
тепер делегує minimumHeightForWidth стандартного layout: внутрішні форми
прокручуються, header/message wrap зберігається, обидва ряди дій у viewport.
Candidate native measurement: page656px, кнопки закінчуються на685px при
вікні720px. Архітектура вкладок/scroll areas та explicit atomic Save збережена.
Регресія перевіряє повні rectangles кнопок і багаторядкове повідомлення.

## Перевірений результат після обох fixes

Code snapshot **1e11497c09c60ee4bd02b097d330f682d2ada420**:
- Native Windows11 Pro build26300, backendwindows: **47 GUI passed** (65.62s),
  включно з ролями, CRUD, membership, повними bounds кнопок і Win32 min limits.
- Windows full pytest offscreen: **119 passed,2 POSIX skips** (82.52s).
- Local full pytest: **121 passed** (96.99s); WSLg Wayland GUI: **75 passed**
  (75.01s). Ruff lint/format41files, locked sync, migrations/startup — success.
- Усі69tracked files Windows snapshot побайтово відповідають git archive;
  local DB/credentials/WSL venv не копіювалися.
- Root CMD launcher startup перевірено, конфліктні diagnostic flags відхилено.
  Native demo/credentials збережено при switch між snapshots. Наявний Python3.13.5
  read-only запуском підтверджено окремо, його установки не змінено.

Фінальний snapshot/revision записані в test-root SOURCE_REVISION.txt та
environment.json; documentation-only export після code snapshot не змінює
production Python/lockfile. Поточні hosted checks — у PR#3. Власник надав
остаточне прийняття 12.11.2026. Windows workspace зберігає tested snapshot
50d89e9; документаційна фіналізація не перевстановлює його й не змінює дані.

Widget captures на native backend при125%, logical1100×720 (physical1375×900),
тільки синтетичні temporary accounts, не owner demo/desktop:
[Users](../screenshots/phase-2-native-admin-users-min.png),
[Groups](../screenshots/phase-2-native-admin-groups-min.png).
Це не physical mouse/keyboard або compositor screenshot test.

WSLg Wayland: Qt6.10.3/DPR1, minimum1100×720, hint36×54, resize(1,1)
обмежується1100×720; раніше trace підтвердив xdg_toplevel.set_min_size.
Фізичний owner resize все одно порушує цей limit. Дані вказують на шлях
WSLg compositor/RDP, але точний компонент фізичного збою не встановлено.
Немає доказів зникнення application minimum. Native minimum-size enforcement
тепер підтверджено фізично власником. Попередні programmatic resize і native
metadata самі по собі не були фізичним dragging test.

Безпечний тимчасовий варіант — нативний запуск або ручне maximize WSLg.
Root scroll лишається fallback для зменшеного viewport, але не робить
майже нульову рамку придатною до роботи. Fixed-size, resize feedback loops,
Weston rebuild, global settings зміни не застосовуються.

## Ручні кроки для наступних регресій

Це інструкція для повторних перевірок, а не твердження, що кожен пункт
або вся DPI/multi-monitor матриця виконані. Фактичний обсяг owner evidence
наведено в acceptance record; native Enhanced/shortcuts/minimum уже підтверджено.

1. Запустіть launcher; по черзі ввійдіть трьома ролями, перевірте меню/logout.
2. Потягніть усі краї/кут Windows рамки до мінімуму; перевірте Users/Groups
   та доступність Save/Delete. Порівняйте з фізичним WSLg resize.
3. У полях Ім’я/Назва/Опис перевірте Standard Ukrainian та Enhanced,
   English, Ctrl+C/V/X/A й Shift+Insert. Username лишається ASCII-only.
   Використовуйте синтетичний текст; password copy/cut не має видавати пароль.
4. Перевірте читабельність і frame при доступних desktop DPI100/125/150/200%
   та переході між моніторами; це ручні дії власника, не автоматичні зміни.
5. Збережіть тестову групу, закрийте launcher і відкрийте знову: дані мають
   зберегтися. Не запускайте init-demo для скидання наявних даних.

Windows Enhanced не проходить через Weston; його фізичний успіх підтверджено
власником 12.11.2026. WSLg Enhanced залишається окремим upstream limitation.

Офіційні джерела:
[uv Python installs](https://docs.astral.sh/uv/concepts/python-versions/),
[WM_GETMINMAXINFO](https://learn.microsoft.com/en-us/windows/win32/winmsg/wm-getminmaxinfo),
[MINMAXINFO](https://learn.microsoft.com/en-us/windows/win32/api/winuser/ns-winuser-minmaxinfo),
[QWidget geometry](https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QWidget.html),
[Qt scroll-area layout behavior](https://github.com/qt/qtbase/blob/6.10/src/widgets/widgets/qscrollarea.cpp).
