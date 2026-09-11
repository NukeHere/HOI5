# HOI5 Optimization Review

Дата ревью: 2026-09-09.

Проверено статически: синтаксис Python, импорт основных модулей, горячие места draw-пути, lookup-доступ к авиации/ПВО/залпам. GUI/FPS-сценарии не прогонялись: производительность нужно подтвердить запуском игры и F3-профайлером.

## Уже сделано

- `MainGame.py` уменьшен примерно с 20k строк до 10.7k строк.
- Из `MainGame.py` вынесены крупные системы:
  - `game_models.py` - модели экономики, армии, боя, авиации и залпов.
  - `simulation_core.py` - локальный сервер/клиент симуляции и команды.
  - `performance.py` - профайлер и no-op таймер.
  - `ui_controls.py` - pause/HUD контролы.
  - `air_system.py` - авиация, ПВО, залпы, перехваты и авиационные индексы.
  - `economy_system.py` - ресурсы, склады, производство, снабжение, торговля, экономика и население.
  - `construction_system.py` - строительство, ремонт, очередь, размещение и строительные предупреждения.
  - `ui_panels.py` - верхняя панель, side panels, trade/resources/construction/army panels и hex-панель.
- `Game` теперь наследует mixin-системы и больше похож на координатор, а не на один общий склад логики.
- `PerformanceProfiler` теперь не собирает замеры, пока F3-оверлей скрыт. F3 включает и видимость, и сбор профиля.
- Добавлены lookup-индексы для авиации/ПВО/залпов:
  - `air_wing_lookup`, `air_wings_by_tile`.
  - `air_defense_unit_lookup`, `air_defense_units_by_tile`.
  - `air_salvo_lookup`, `air_attack_salvo_lookup`, кэш `air_salvo_tile_lookup`.
- Создание/удаление/перебазирование авиации и перемещение ПВО обновляют индексы через register/unregister helper-методы.
- `trade_panel_snapshot()` больше не вызывает mutating `normalize_trade_contracts()`: draw-путь читает нормализованную копию контрактов.
- Верхний warning по торговле тоже читает контракты без изменения состояния.
- `draw_economy_panel_content()` больше не вызывает `recalculate_monthly_balance()` каждый кадр; UI читает кэшированный economy snapshot.
- `draw_hex_info_panel()` получил `hex_panel_snapshot()` с кэшем по выбранным клеткам, ревизии визуала, ревизии авиации, ревизии залпов и dirty-флагам ресурсов/складов.

## Что не трогалось по договоренности

- `music/` не менялся.
- `Новый текстовый документ.txt` не менялся.
- Заглушки оставлены как есть: `save_game()`, `load_game()`, `draw_gui()`, multiplayer/continue в главном меню, upgrade аэродрома.

## Главные оставшиеся риски

1. `MainGame.py` все еще можно уменьшать дальше: там остаются генерация мира/стартовых стран, бой/армии, карта, рендер карты, input и главный игровой цикл.
2. Mixin-разбиение - безопасный первый шаг, но следующим этапом лучше выносить зависимости внутрь настоящих сервисов: `AirSystem`, `EconomySystem`, `ConstructionSystem`, `PanelSnapshots`.
3. `hex_panel_snapshot()` кэширует данные панели, но часть ключа пока опирается на существующие dirty-флаги и общие ревизии. Следующий шаг - явные revision-счетчики для ресурсов, складов, зданий и проектов строительства.
4. `estimate_monthly_trade_flows()` теперь read-only по контрактам, но часть resource-flow расчетов все еще может быть тяжелой для UI, если баланс помечен dirty и пересчитывается при открытой панели.
5. `field_helipad_projects_on_tile()` пока остается линейным проходом; если проектов станет много, нужен индекс по tile.
6. `draw_tile_visual_system()` кэширует sprite list, но rebuild все еще создает новые `arcade.Sprite` объекты для видимых тайлов.

## Рекомендуемый порядок следующей разбивки

1. Вынести генерацию мира и стартовых стран: `world_generation.py`, `starting_setup.py`.
2. Вынести бой и армии: `combat_system.py`, `army_plans.py`.
3. Вынести рендер карты и юнитов: `map_render.py`, `division_render.py`, `air_render.py`.
4. Заменить mixin-слой на композицию систем, когда станет ясно, какие данные должны принадлежать каждой системе.
5. Добавить явные revision-счетчики для ресурсов/складов/строений, чтобы panel snapshots были полностью предсказуемыми.

## Проверки

- `.venv\\Scripts\\python.exe -m compileall -q MainGame.py air_system.py economy_system.py construction_system.py ui_panels.py game_models.py performance.py simulation_core.py ui_controls.py MainMenu.py Settings.py HexTile.py MapData.py Constants.py` - прошло.
- `.venv\\Scripts\\python.exe -c "import air_system, economy_system, construction_system, ui_panels, MainGame; print('imports ok')"` - прошло.
- Smoke-тест `Game(difficulty="Normal", bot_count=3, map_size=50)` через временное окно Arcade - прошло: создано 2500 тайлов и 4 государства.

## Что проверить вручную в игре

- Запуск новой игры.
- Открытие экономики, ресурсов, торговли и hex-панели.
- Создание/перебазирование авиации.
- Создание/перемещение ПВО.
- Появление и движение залпов.
- F3: сравнить FPS и top-строки профайлера до/после на terrain/resources/trade/hex-panel.

