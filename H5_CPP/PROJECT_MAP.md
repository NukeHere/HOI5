# PROJECT_MAP — карта исходников HOI5 (C++)

> **Назначение:** быстрый поиск места в коде, а не описание каждой формулы. Составлено по **42 переданным файлам**. Обозначение `main.cpp:3303` — строка в загруженной версии (может сместиться после правок); имена символов надёжнее номеров строк. Все перечисленные пути — имена переданных файлов; в репозитории C++-часть, судя по `port_progress.py`, называется `H5_CPP/`.

## 1. Архитектура за 30 секунд

- **`main.cpp` — центральный узел** (≈11 тыс. строк): типы `Tile`, `Division`, `World`; генерация и состояние мира, связь подсистем, наземные/воздушные боевые расчёты, AI снабжения; SFML-отрисовка, интерфейс, управление, тестовые режимы и `main()`.
- **`World` (`main.cpp:276`) хранит** `tiles`, `divisions`, `armies`, `profiles`, `stockpiles`, `capacities`, `production`, `treasury`, `market`, `diplomacy`, `air`, `construction`, `battles`, `news`. **`World::advance()` (`main.cpp:3303`)** согласует все обновления.
- **`SimulationClock`** (`simulation_clock.hpp`) переводит кадры в игровые часы и инициирует недельные торговые циклы. Из игрового цикла `main.cpp:7382–7410` вызывается `world.advance(...)`.
- **`generateWorld()` (`main.cpp:3451`)** соединяет генератор рельефа, страны, стартовые здания/ресурсы, экономику, армии и авиацию. `WorldGenerator` в `world_generation.hpp` генерирует **местность**, а не весь игровой мир.
- **Механики преимущественно вынесены в `.hpp`**, но правила движения, фронтов, наземных боёв, выбора воздушных целей и пользовательские панели по-прежнему находятся в `main.cpp`.

```text
main() / SFML-цикл (main.cpp)
  ├─ SimulationClock::update() ──> World::advance(hours)
  │   ├─ Diplomacy + политика + News
  │   ├─ Market (раз в неделю) + Treasury + Production + Storage
  │   ├─ Construction + Population + Supply + пересчёт экономики
  │   ├─ Divisions/Fronts/Training + Ground battles
  │   ├─ AirLayer/Air missions/ПВО + полевые вертолётные площадки
  │   └─ Боты снабжения + уведомления
  └─ Обработка SFML-событий + карта + панели + музыка + профилировщик
```

## 2. Все файлы по подсистемам

### Карта, генерация и начальные условия

| Файл | Что искать |
| --- | --- |
| `world_generation.hpp` | `Terrain`, `WorldGenerator::generate()` — шумовая генерация высот, влажности, температуры, покровов, озёр. |
| `map_data.hpp` | `biome()`, `terrainMovementCost()`, `groundTerrainEffects()`, `generateDeposits()` — биомы, стоимость движения, эффекты рельефа в бою, месторождения. |
| `terrain_color.hpp` | `terrainColor()` — цвета типов поверхности. |
| `country_names.hpp` | `countryNames`, `rulerNames`, `countryIdentities(seed)` — названия/лидеры государств. |
| `starting_infrastructure.hpp` | `StartingProfile`, `placeStartingCities()`, `placeStartingBuildings()`, `distributeStartingPopulation()` — стартовые города, здания, расселение. |
| `starting_economy.hpp` | `Stockpile`, `startingStockpile()`, `compensateStartingResources()` — начальные запасы и их балансировка. |
| `reference-map.txt` | Исходный текстовый сценарий/контрольная карта: размеры, столица, статусы, гексы, дивизии. Читается конструктором `World(path)` (`main.cpp:329`); **не исходник C++**. |

### Экономика, население и строительство

| Файл | Что искать |
| --- | --- |
| `supply.hpp` | `Building`, `BuildingCoverage`, `recalculateSupply()` — типы сооружений и распространение снабжения по гексам. |
| `storage.hpp` | `storageBucket()`, `storageCapacity()`, `tileStorageCapacity()`, `enforceStorageCapacity()`, `freeStorage()` — вместимость и ограничения складов. |
| `production_data.hpp` | `ProductionStage`, `ProductionFlows`, `Recipe`, `recipes`, `sectors`, `lifeSupport` — рецепты и структура производства. |
| `production.hpp` | `industryAllocation()`, `assignStartingIndustry()`, `buildProduction()`, `runProduction()` — размещение отраслей, производство и расход сырья. |
| `market_data.hpp` | `TRADE_BASE_PRICES`, `MARKET_RESOURCE_RARITY`, коэффициенты цен, `linkedPrices` — справочники мирового рынка. |
| `market_clearing.hpp` | `MarketOrder`, `MarketFill`, `MarketPlan`, `clearMarket()` — алгоритм сведения заявок и исполнения сделок. |
| `market.hpp` | `Market`, `changeContract()`, `updatePrices()`, `monthlyCapacity()`, `execute()` — торговые контракты, цены, торговая пропускная способность, исполнение. |
| `treasury_data.hpp` | Ставки доходов населения/компаний и расходы на содержание инфраструктуры. |
| `treasury.hpp` | `TreasuryFlows`, `monthlyTreasury()` — доходы, расходы, бюджетный баланс. |
| `population.hpp` | `populationCapacity()`, `populationGrowthMultiplier()`, `runPopulationMonth()` — вместимость гексов и месячная демография. |
| `construction_data.hpp` | `ConstructionSpec`, `constructionSpecs` — стоимость/ресурсы/трудоёмкость построек. |
| `construction.hpp` | `ConstructionProject`, `ConstructionStatus`, `Construction::{enqueue,cancel,advance,placementBlock,damageBuilding}` — очередь, ограничения площадки, стройка и ремонт. |

### Политика, дипломатия, новости

| Файл | Что искать |
| --- | --- |
| `diplomacy.hpp` | `CountryPolitics`, `Relation`, `ForeignAction`, `Diplomacy::{act,resolve,advance,changeTax,changeProgram,serviceLoans}` — страны, договоры, войны, налоги, программы, займы, фракции. |
| `world_news_data.hpp` | `NewsPriority`, `WorldNewsTemplate`, `worldNewsTemplates` — справочник мировых новостных сюжетов. |
| `news.hpp` | `News`, `NewsItem`, `report()`, `alert()`, `advance()`, `recordTrade()`, `recordBattleLoss()`, `startLog()` — генерация событий, предупреждения, журнал. |
| `news_panel.hpp` | `NewsPanel::{update,click,scroll,draw,openItem}` — лента, архив, всплывающие окна новостей **в интерфейсе SFML**. |

### Армия, авиация и AI

| Файл | Что искать |
| --- | --- |
| `combat.hpp` | `CombatStats`, `Battle`, `combatDamage()` — параметры сухопутного боя и формула урона; **проведение боя — в `World`**. |
| `division_data.hpp` | `DivisionTemplate`, `divisionTemplates`, `DivisionComposition`, `composeDivision()`, `SavedDivisionDesign`, константы потерь снабжения — состав и шаблоны дивизий. |
| `air_data.hpp` | `AirRisk`, `AircraftType`, `aircraftTypes`, `FighterInterceptor`, `DefenseClass`, `defenseClasses` — типы самолётов, перехватчиков и ПВО. |
| `air_layer.hpp` | `Airbase`, `AirWing`, `AirDefense`, `AirLayer` — хранение авиакрыльев/баз/ПВО; `createWing()`, `rebaseWing()`, `transferAircraft()`, `replenishDefenseAmmo()`, `advanceDefenseReplacements()`. |
| `munition_data.hpp` | `Munition`, `munitions`, `aircraftMunitions`, твёрдость/ценность зданий, профили перехвата — параметры авиационного вооружения. |
| `air_missions.hpp` | `AirSalvo`, `AircraftInterceptorSalvo`, `missionWeapon()`, `airMissionLaunchDistance()`, `fighterSalvoInterceptChance()`, `buildingDamage()` — расчёты воздушных вылетов, попаданий и перехвата. |
| `ai_supply.hpp` | `BotSupplyPoint`, `BotSupplyCandidate`, `bestBotSupplySite()` — выбор гекса для улучшения снабжения ботом. Вызов/исполнение — `World::updateBots()`. |

### Инфраструктура приложения и портирование

| Файл | Что искать |
| --- | --- |
| `main.cpp` | **Главный файл приложения**: подробно разобран в §3. |
| `simulation_clock.hpp` | `SimulationClock::{update,setSpeed,togglePause}` — скорость, пауза, расчёт игровых часов и календарь рынка. |
| `settings.hpp` | `Settings`, `SettingsFiles`, `loadSettings()`, `saveSettings()` — пути и чтение/запись настроек. |
| `music.hpp` | `DynamicMusic::{newWorld,category,update,setVolume}` — фоновая музыка по игровым ситуациям через SFML Audio. |
| `debug_profiler.hpp` | `DebugProfiler`, `DebugMeasure`, `debugRows` — замеры FPS и стоимости подсистем. |
| `python_seed.hpp` | `PythonSeed`, `PythonRandom` — совместимое с Python воспроизведение последовательностей псевдослучайных чисел для отдельных алгоритмов/проверок. |
| `format_amount.hpp` | `formatAmount()` — компактная запись чисел (`K`, `M` и т. д.). |
| `resource_descriptions.hpp` | `resourceUsageDescription()` — текстовые описания применения ресурсов в интерфейсе. |
| `copy_resources.cmake` | Копирование каталогов `assets` и `music` к исполняемому файлу; **не основной конфигурационный `CMakeLists.txt`**. |
| `PORT_PROGRESS.md` | Правила аудита переноса Python → C++. |
| `port_progress.tsv` | Построчный реестр символов Python, статусов, C++-соответствий и доказательств. |
| `port_progress.py` | Проверка актуальности реестра и `--sync` по Python-коду из `H5_Python/`; нужны оригинальные исходники и git-окружение. |

## 3. Главные ориентиры внутри `main.cpp`

### Игровой мир и вычисления (строки 165–3430)

| Диапазон / символ | Назначение |
| --- | --- |
| `165–325`: `Tile`, `Division`, `World` | Данные гексов, дивизий, всех игровых подсистем. `Division::{consume,loseStrength,attackSupplies}`: снабжение и потери. |
| `329`: `World(path)` | Загрузка `reference-map.txt`. |
| `363–508`: `propagateWaterOwnership`, `landRoute`, `orderMove`, `orderAirDefenseMove`, `advanceAirDefense` | Владение морскими клетками, поиск пути по шестиугольникам, марши войск и ПВО. |
| `528–641`: `taxedTreasury`, `powerRanking`, `forecastMarketPlan`, `executeWeeklyMarket` | Налоги, рейтинг мощи, прогноз и проведение торговли. |
| `644–958`: `advanceWorldNews`, `performForeignAction`, `answerForeignOffer`, `advancePoliticsHours`, `changeTax`, `changeSupportProgram`, `reportCountryAlerts` | Дипломатические действия, политические решения, новостные предупреждения. |
| `961–1195`: `updateEconomyHistory`, `refreshLivingConditions`, `rebuildEconomy`, `supplyRatio`, `forecastResources` | История бюджета, благосостояние, пересборка экономики/складов, снабжение и прогноз ресурсов. |
| `1196–1375`: `replenish`, `train`, `cancelTraining`, `updateTraining` | Пополнение дивизий и обучение. |
| `1376–2006`: `rebalanceBattle`, `createArmy`, `setArmyFront`, `distributeArmyFront`, `executeArmyOffensive`, `updateArmyFronts` | Состав участников боя, армии, автоматические фронты, наступления. |
| `2007–2322`: `joinBattle`, `transferTile`, `battleCollateral`, `tickBattles`, `advanceBattles` | Наземные столкновения, захват гексов, побочный урон сооружениям. |
| `2323–2636`: `updateFieldHelipads`, `assignAirWingTarget`, `selectStrategicTarget`, `selectCasTarget`, `launchAirMission` | Полевые площадки, выбор целей авиации, запуск миссий. |
| `2637–3133`: `resolveAirImpact`, `interceptAircraft`, `groundAircraftHitChance`, `resolveGroundSalvoDefense`, `updateAir` | Поражение зданий/войск с воздуха, ПВО, перехваты, воздушная симуляция. |
| `3134–3302`: `updateDivisions`, `startBots`, `planBotSupply`, `updateBots` | Перемещение дивизий и бот по снабжению. |
| **`3303–3428`: `World::advance`, `updateVisualMotion`** | **Центральная последовательность обновления мира** + сглаживание перемещения. |

### Генерация, карта, отрисовка (строки 3432–4379)

| Диапазон / символ | Назначение |
| --- | --- |
| `3435–3450`: `center`, `tileAtWorldPosition` | Преобразование координат гекса ↔ пиксели; выбор гекса мышью. |
| **`3451–3588`: `generateWorld`** | **Создание новой партии:** рельеф → страны → инфраструктура → население → запасы/дивизии → экономика. |
| `3590–3775`: `drawDivisionRoute`, `divisionCounters` | Путь подразделений, счётчики и группировка значков на карте. |
| `3776–3919`: `wingAreaSummary`, `drawWingAreaOverlay`, `drawDefenseRanges`, `drawDefenseIcon` | Визуализация авиации и ПВО. |
| `3920–4077`: `MapLayer`, `mapLayerColor`, `makeMap`, `supplyColor` | Слои карты: рельеф, политика, высота, климат, ресурсы, снабжение. |
| `4078–4203`: `resourceCategoryKeys`, `resourceDurationLabel`, `mapResourceAmount`, `constructionOverlayColor` | Карта ресурсов, прогноз истощения, подсветка стройплощадок. |
| `4204–4379`: `makeBorders`, `box`, `label`, `battleLabel`, `drawBudgetSummary`, `drawPopulationSummary` | Границы карты и базовые SFML-компоненты интерфейса. |

### `main()` — запуск, тесты, ввод и панели (строки 4380–11083)

| Диапазон | Назначение |
| --- | --- |
| `4380–5720` | `main(argc, argv)`, загрузка эталонной карты; **встроенные CLI-проверки** `--check-*` (экономика, бой, маршруты, авиация, настройки и др.). |
| `5721–5782` | Флаги интеграционных/визуальных тестов `--smoke-*`, `--inspect-*` и подготовка мира. |
| `5783–5900` | Настройки, окно SFML, шрифты, загрузка `assets/ui_icons`, `assets/tile_visuals`, музыка. |
| `5900–6336` | Состояния UI, вспомогательные лямбды: выбор дивизий, авиации и фронтов, открытие дипломатии, работа с решениями; `startGame()` около `6295`. |
| **`6337–7379`** | **Главный цикл и обработка событий:** клавиатура/мышь, управление картой, фронтами, панелями, строительством, дипломатией. |
| **`7380–7410`** | **Такт симуляции:** `SimulationClock::update(...)` → `world.advance(...)` + обновление истории экономики. |
| `7411–~8700` | Карта, слои, отрисовка гексов/дивизий/авиации, контекстные и авиационные панели. |
| `~8700–8816` | Экономическая панель/бюджет. |
| `8817–9002` | Панель ресурсов. |
| `9003–9291` | Панель армии: обзор, конструктор дивизий, набор. |
| `9292–9408` | Панель строительства и очереди. |
| `9409–9783` | Список стран, политика, социальные показатели, дипломатические вкладки. |
| `9784–10111` | Панель торговых контрактов. |
| `10112–10717` | Вспомогательные панели, подробные карточки страны, налогов, программ, решений. |
| `10718–10881` | Верхняя полоса, подсказки, предупреждения, профилировщик, музыка, вывод кадра. |
| `10882–11083` | Сценарии автоматического нажатия кнопок для smoke-тестов интерфейса. |

## 4. Быстрая навигация: «хочу изменить X»

| Задача | Начать с |
| --- | --- |
| Частота тиков, скорость игры, пауза | `simulation_clock.hpp` → `SimulationClock::update`; вызов `main.cpp:7385`. |
| Новый ресурс, его цена и текст | `market_data.hpp` → `TRADE_BASE_PRICES`; `production_data.hpp`/`resource_descriptions.hpp`; перевод имени — `main.cpp:106`. |
| Логика производства/нехватки | `production.hpp` → `runProduction`; `main.cpp:3321`. |
| Новые сделки, спрос/предложение, ценообразование | `market.hpp` → `execute`, `updatePrices`; `market_clearing.hpp` → `clearMarket`; `main.cpp:619`. |
| Доходы, расходы, налоги, кредиты | `treasury.hpp`, `treasury_data.hpp`, `diplomacy.hpp`; интеграция `main.cpp:528,766`. |
| Строить или ремонтировать здание | `construction_data.hpp`, `construction.hpp` → `enqueue/advance`; интеграция `main.cpp:3344`; UI `~9292`. |
| Пересчитать снабжение и складские лимиты | `supply.hpp` → `recalculateSupply`; `storage.hpp`; `main.cpp:1045`. |
| Прирост населения, продукты, потребтовары | `population.hpp`; `main.cpp:977,3360`. |
| Генерация карты/месторождений/стартовых стран | `world_generation.hpp`, `map_data.hpp`, `starting_infrastructure.hpp`, `main.cpp:3451`. |
| Цвета, отображение гексов, выбор мышью | `terrain_color.hpp`; `main.cpp:3435,3978,4032`. |
| Поиск пути, скорость марша, маршруты | `main.cpp:419` (`landRoute`), `460` (`orderMove`), `3134` (`updateDivisions`); рельеф `map_data.hpp`. |
| Новые шаблоны дивизий, набор, снабжение | `division_data.hpp`; `main.cpp:178,1196,1276,1321`. |
| Боевой урон, ширина фронта, потери, захват | `combat.hpp` → `combatDamage`; `main.cpp:1392,2007,2136,2054`. |
| Автоматические армии и линии фронта | `main.cpp:1473–2006`, прежде всего `distributeArmyFront`, `executeArmyOffensive`. |
| Самолёты, создание крыла и перебазирование | `air_data.hpp`, `air_layer.hpp` → `createWing/rebaseWing`; UI `main.cpp:6978+,8532+`. |
| Авиаудары, CAS, выбор цели, перехват/ПВО | `air_missions.hpp`, `munition_data.hpp`; `main.cpp:2444–3133`. |
| Строительство/перемещение ПВО и пополнение БК | `air_layer.hpp`; `main.cpp:490–525,3378+`. |
| Внешняя политика, договоры, войны, фракции | `diplomacy.hpp`; `main.cpp:659–857`; UI `~9409+`. |
| События, предупреждения, лента новостей | `news.hpp`, `world_news_data.hpp`, `news_panel.hpp`; `main.cpp:644,913`. |
| Музыка, громкость, настройки | `music.hpp`, `settings.hpp`; `main.cpp:5783+,10795+`. |
| Найти узкое место по производительности | `debug_profiler.hpp`; именованные `DebugMeasure` и `debug.record` в `main.cpp`. |
| Проверить соответствие версии Python | `PORT_PROGRESS.md` → `port_progress.tsv` → `port_progress.py`; локальные `--check-*` в `main.cpp:4380+`. |

## 5. Важные зависимости и оговорки

1. **Не путать данные и действие:** характеристики дивизии — `division_data.hpp`, вычисление урона — `combat.hpp`, **сам ход битвы** — `World::tickBattles`; характеристики самолёта — `air_data.hpp`, **выполнение вылета** — `World::updateAir`.
2. **Изменение здания влияет сразу на несколько систем:** `supply.hpp`/`construction_data.hpp` → `construction.hpp` → `World::advance` → `recalculateSupply` + `World::rebuildEconomy`; также могут затрагиваться складские лимиты, выпуск продукции, бюджет, авиабазы.
3. **`main.cpp` сильно связан с заголовками:** общие `Tile`, `Division`, `World` определены прямо там; часть `.hpp` опирается на типы игрового мира. При выносе кода нужно учитывать порядок объявлений/подключений.
4. **Встроенные тесты не являются доказательством полной эквивалентности Python:** `port_progress.tsv` отмечает символы `ported`, `partial`, `missing`, `unreviewed`, а также исключённые инструменты/ботов. Реестр требует отдельного аудита.
5. **Ограничение комплекта:** получены 42 файла, **не** загружены исходники `H5_Python/`, основные файлы сборки (`CMakeLists.txt`), каталоги `assets/` и `music/`. Поэтому карта покрывает **полученные файлы**, а не гарантированно весь репозиторий или работоспособность сборки.

**Практика для Codex:** сначала найди строку в §4 → открой указанный символ → посмотри вызывающую функцию в `World::advance()` или обработчик `main()`; правя баланс, проверяй соответствующие `--check-*` и статусы портирования.
