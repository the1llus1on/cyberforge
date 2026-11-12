# Геометрія вікна та WSLg minimum hints

Перед зміною були preferred 1280×800 і minimum 860×620. Великий список,
форма й кнопки перебували в одному scrollable page, тож кнопки виходили
нижче viewport. Це підтверджений layout issue, а не доказ втрати Qt hints.

Нове правило: logical preferred 1400×900, minimum 1100×720, bounded
availableGeometry екрану із запасом 48 px; вікно центрується у цій області.
Старти на малих екранах і negative-coordinate моніторах перевірені окремо.
Не встановлюється фізичний pixel size без урахування DPI.

Діагностика у WSLg Wayland, екран 1920×1080, DPR=1:

```text
minimum (1100, 720) initial (1400, 900)
programmatic-shrink (1100, 720)
xdg_toplevel.set_min_size(1100, 720)
xdg_toplevel.set_min_size(1106, 753)
```

Другий protocol size включає window-decoration extents. Програмний resize
до 1×1 Qt обмежує мінімумом. Отже, Qt передає minimum-size hints на цьому
шляху; фізичний owner resize RDP-рамки нижче minimum не відтворено агентом.
Не оголошуємо його доведеним Qt-багом. На момент первинної діагностики native
Windows доказів не було; пізніші автоматизовані й owner докази наведено нижче.

Захист незалежний від compositor: root QScrollArea містить вміст не менше
860×620. Якщо compositor задає менший frame, root scroll відкриває доступ
до навігації/контенту. Тест явно знімає frame minimum для моделювання цього
випадку і перевіряє scrollbar та досяжність Profile. Forms прокручуються
всередині admin tabs; New/Save/Reset/Delete залишаються окремо під формою.
При екстремально малому екрані прокручування root теж потрібне.

Ручна перевірка власником: звичайний запуск; resize за краї/кут рамки;
перевірка minimum, вкладок Users/Groups і видимості кнопок; 150/200% scaling
на цільовій Windows 11. WSLg Qt scale-factor перевірка не дорівнює перевірці
Windows DPI або фізичного RDP resize. Не змінюйте глобальні WSL/Windows settings
автоматично. Для повторного тесту в окремому WSL-сеансі можна задати
QT_SCALE_FACTOR=1.5 або 2 тільки конкретній команді запуску.

## Оновлення 12.11.2026

Власник фізично підтвердив WSLg resize нижче minimum попри hints; це лишається
невирішеним WSLg обмеженням (compositor/RDP path під підозрою, точний компонент
не встановлено). Автоматизовано повторно перевірено
Qt minimum1100×720 та resize clamp під Wayland. Native Windows11/125%:
minimum1100×720, hint36×54; Win32 min tracking1393×947physical, Qt resizeclamp
1100×720. На момент автоматизації фізичний native dragging ще не був підтверджений.
Native probe знайшов initial frame clipping6logical px через decorations;
showEvent clamp коригує стартову позицію. Розмір лишається змінним.
[Native environment, докази й owner instructions](native-windows.md).

## Остаточне owner acceptance — 12.11.2026

Власник підтвердив правильне фізичне minimum-size enforcement у native
Windows11 і прийняв Phase2 (ACCEPTED). Це доповнює попередні Win32/Qt
metadata докази; агент не заявляє власного physical mouse test. WSLg tiny-frame
обмеження лишається невирішеним; точний compositor/RDP компонент не встановлено.
Повна фізична DPI/multi-monitor матриця не оголошується пройденою.
