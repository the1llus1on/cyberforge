# Phase 2 — залишкові фізичні перевірки власника

Статус REVIEW. Це лише ручні desktop-перевірки; стан CI наведено окремо в
[технічному аудиті](audits/phase-2-pre-acceptance.md). Виконати, коли з’явиться час.
Використовуйте синтетичні чернетки, не реальні паролі; не переініціалізовуйте demo.

- [ ] У цільовій Windows 11: звичайний запуск наявної БД, вхід/вихід для
  Administrator/Instructor/Learner; потрібні меню й Home, відсутність чужого
  контексту після зміни користувача. Перезапуск зберігає зміни.
- [ ] Мишею й клавіатурою: вибір рівно однієї ролі, лише indicator-click/Space
  змінює membership обох picker; text-click, фокус і пошук не змінюють чернетку.
  Save явний; create/edit/inactive/delete/cancel та single group save зрозумілі.
- [ ] Фізичні Ctrl+C/V/X/A у CyberForge під Standard Ukrainian та English,
  Shift+Insert, звичайний український текст; password copy/cut не копіює пароль.
  Probe є baseline без correction. Enhanced не вважати виправленим.
- [ ] Resize рамки у WSLg та native Windows 11, DPI 100/125/150/200%:
  старт у межах екрана, кнопки admin доступні, checkbox видно, текст читається,
  за малих розмірів вміст досяжний через scroll. Перевірити саме фізичний
  RDP/window-manager resize, який синтетичні тести повністю не доводять.
- [ ] У власному Windows-профілі перевірити приватність каталогу БД і demo-файлу
  за ACL. POSIX 0600/0700 та hosted Windows Server CI не доводять ці ACL.

Фізична Windows 11 перевірка не замінюється offscreen CI або QT_SCALE_FACTOR.
Прийняття Phase 2, merge і дозвіл Phase 3 — окреме рішення власника.
