# HOI5 — передача работы в другой чат

Снимок рабочего дерева от 6 ноября 2026. Репозиторий `C:\Ich\projects\HOI5`, Windows, PowerShell. Открой этот же workspace в новом чате и передай ему этот файл. Цель Codex привязана к чату. Если нужна отдельная цель в новом чате, её следует создать там явным запросом.

## Цель и границы

> Полностью перенеси HOI5 из Python в нативный C++ на SFML 3, исключая только логику ботов. Используй Python как эталон структуры, формул, порядка обновлений, команд, внешнего вида и поведения интерфейса. Заменяй упрощения прямыми переносами. Сравнивай результаты обеих версий на одинаковых сценариях и проверяй интерфейс в окне. Продолжай после промежуточных проверок. Заверши цель только после проверки всех игровых подсистем.

Пользователь позднее отдельно попросил начать перенос ИИ после коммита. Это отдельное направление, уже начатое с выбора и постановки приоритетного пункта снабжения. Основной процент исторически считается без ИИ. Полный перенос ещё не подтверждён. Пользователь просит писать код крупными блоками, реже делать промежуточные проверки, не останавливаться после мелких этапов и сообщать процент по реестру. Оконные проверки лучше группировать и закрывать тестовые экземпляры после прогона.

## Git и восстановление

- База `ac98c4d3d31cdc7a45de3e2993956a26dd20e8da`, ветка `main`. Последний запрошенный push выполнен, на момент передачи локальный HEAD и `origin/main` совпадали. Удалённый репозиторий `https://github.com/NukeHere/HOI5.git`.
- В `ac98c4d` вошли накопленные правки нативной игры, в том числе политическая карта и режимы «Страны», «Союзы», «Отношения к нам», исправления фронтов и карты снабжения, подписи строительства поверх значков, подсказки политических показателей и F3.
- После этого коммита локально добавлены начальный ИИ снабжения, общий бюджет вылетов по типам самолётов, журнал новостей и кэш запасов по гексам. Эти изменения уже лежат в данном workspace. Патч в конце предназначен для чистой копии на указанной базе. В текущем дереве повторно применять его не нужно.
- Тестовые логи и старые диагностические файлы из `H5_Python/.codex-work` оставлены в рабочем дереве. Они не входят в патч. Не добавляй их в будущий коммит вместе с игровым кодом.
- Если нужен чистый checkout, извлеки блок между маркерами `BEGIN_HOI5_PATCH` и `END_HOI5_PATCH` в отдельный UTF-8 файл без BOM. Сначала запусти `git apply --check handoff.patch`, затем `git apply handoff.patch`. Патч включает карту исходников `H5_CPP/PROJECT_MAP.md` и новый заголовок ИИ.

## Что уже работает и как проверено

- В последней локальной сборке прошли **19 из 19 CTest**, повторный прогон после сборки подтвердил результат. [Штатный HOI5.exe](C:/Ich/projects/HOI5/build/cpp/HOI5.exe).
- Наземные бои идут почасово и обходятся в порядке создания. На парных сценариях совпали организация, прочность, ширина фронта, приоритеты боевой линии и выбор целей при заданном состоянии генератора. Последовательности случайных событий в полном мире ещё различаются.
- У карт снабжения и строительства исправлены переключение кэша и отбор видимых рядов. Проценты стройки видны поверх иконок. Проверки `--smoke-warnings`, `--smoke-construction`, `--smoke-army` прошли на снимке до последующих изменений экономики. Снимок стройки доступен в `build/cpp/construction-percent.png`.
- Авиация запускает до пяти пакетов за цикл миссии, учитывает занятые машины по типам, резервирует часть общих самолётов под стратегический удар и проверяет отмену между пакетами. Парный сценарий на двух целях проверяет число вылетов и восьмичасовые интервалы. Прошёл `--smoke-wing-creation`. Состояния вылета и перехват требуют дальнейшей сверки.
- Журнал `logs/world-news.txt` находится рядом с EXE, начинается заново при создании партии и дописывает каждое событие в формате Python. Проверены UTF-8, даты, локальная/мировая видимость, более 300 событий, сброс и продолжение игры при ошибке записи.
- Последняя правка — складские остатки по гексам. В C++ есть ленивый кэш `World::stockpileAtTile`, распределение по эффективной вместимости, пропорциональное сокращение переполнения и резервные здания. Сценарий двух складов с разным состоянием, нехваткой топливной ёмкости и потерей гекса совпал с Python. Отдельный учёт списанных остатков как исторического переполнения и визуальная сверка обновлённой панели гекса ещё нужны.
- ИИ пока охватывает только ежедневный выбор пункта снабжения и постановку проекта в начало очереди с резервом казны. Численный выбор участка сверён с Python. Торговля под проект, полный цикл задач, тактика, авиация и политика ботов остаются отдельной работой.

## Как ориентироваться в коде

| Подсистема | Python | C++ |
| --- | --- | --- |
| Запуск, игровой цикл, карта, панели | `MainMenu.py`, `MainGame.py`, `simulation_core.py`, `ui_panels.py` | `H5_CPP/main.cpp` (`World::advance`, `generateWorld`, `main`), `simulation_clock.hpp` |
| Экономика, снабжение, стройка | `economy_system.py`, `construction_system.py`, `market_clearing.py` | `storage.hpp`, `supply.hpp`, `production.hpp`, `treasury.hpp`, `market.hpp`, `construction.hpp` |
| Дипломатия и новости | `politics_system.py`, `country_panel.py`, `country_dialog.py`, `news_system.py`, `news_panel.py` | `diplomacy.hpp`, `news.hpp`, `news_panel.hpp`, `world_news_data.hpp` |
| Дивизии, фронты, авиация | `MainGame.py`, `division_recruitment.py`, `air_system.py` | `main.cpp`, `combat.hpp`, `division_data.hpp`, `air_layer.hpp`, `air_missions.hpp` |
| Генерация | `world_generation.py`, `MapData.py`, `HexTile.py` | `world_generation.hpp`, `map_data.hpp`, `starting_infrastructure.hpp`, `main.cpp::generateWorld` |
| Отдельный перенос ИИ | `ai_system.py`, `ai_supply.py`, `ai_workers.py` | `ai_supply.hpp`, `World::startBots`, `World::planBotSupply`, `World::updateBots` |

Имена Python-файлов относятся к `H5_Python/`, заголовки C++ — к `H5_CPP/`. Ищи символы через `rg`, номера строк меняются. Дополнительная карта файлов — `H5_CPP/PROJECT_MAP.md`.

## Сборка и реестр

```powershell
$cm = 'C:/Program Files/JetBrains/CLion 2026.2.2/bin/cmake/win/x64/bin'
& "$cm/cmake.exe" --build build/cpp --target HOI5
& "$cm/ctest.exe" --test-dir build/cpp --output-on-failure --timeout 15
& H5_Python/.venv/Scripts/python.exe H5_CPP/port_progress.py
```

- Python из `H5_Python/.venv/Scripts/python.exe` рабочий. Системные `python` и `py` ранее не находили интерпретатор.
- После изменения объявлений Python запускай `port_progress.py --sync`. Статусы и основания меняй только для проверенных символов. Актуально **105 из 1422, 7,38%**. В игровом объёме 154 частичных, 1 явно отсутствующая строка и 1162 непроверенных. Непроверенные строки нельзя считать ни готовыми, ни отсутствующими.
- Сборка Release большого `main.cpp` с `-O3` занимает время и может использовать около 1,3 ГБ памяти компилятора. При `Permission denied` на линковке проверь, открыт ли штатный EXE. Не закрывай партию пользователя. Не прогоняй новый тест на старом EXE. При необходимости можно слинковать проверочный экземпляр из свежего объекта в том же каталоге и прогнать тесты на нём.
- Оконные режимы запускай из `build/cpp`, используя только подтверждённые флаги свежей сборки. Базовые сценарии: `--smoke-construction`, `--smoke-resources`, `--smoke-diplomacy`, `--smoke-army`, `--smoke-wing-creation`, `--smoke-warnings`. Для проверки журнала используй CTest `news_file_log`, поскольку создание новой партии сбрасывает настоящий игровой журнал.

## Следующие проверяемые расхождения

1. Открыть панель гекса в SFML, проверить её после покупки, повреждения склада и смены владельца. Сверить отдельный учёт переполнения из Python.
2. Перенести портреты командиров из `Game.draw_commander_portrait` и сверить карточки армий. Это единственный пробел со статусом `missing` в текущем реестре, который ещё содержит много непроверенных строк.
3. Сверить фазы авиамиссии, перехват, реакцию на отмену и восстановление авиакрыла в одинаковых сценариях.
4. Продолжить проверку стартового мира по общим сидам, цепочек экономики и сложных наступлений. Параллельный трек ИИ вести отдельно.

## Встроенный патч рабочего дерева


<!-- BEGIN_HOI5_PATCH -->
diff --git a/CMakeLists.txt b/CMakeLists.txt
index 4c5d587..f9d87a6 100644
--- a/CMakeLists.txt
+++ b/CMakeLists.txt
@@ -61,6 +61,7 @@ add_test(NAME withdrawal_after_revoked_transit COMMAND HOI5 --check-withdrawal)
 add_test(NAME division_path_python_parity COMMAND HOI5 --check-path-parity)
 add_test(NAME army_front_and_manual_orders COMMAND HOI5 --check-army-front)
 add_test(NAME news_popup_priority COMMAND HOI5 --check-news-popup)
+add_test(NAME news_file_log COMMAND HOI5 --check-news-log "${CMAKE_CURRENT_BINARY_DIR}/news-log-test.txt")
 add_test(NAME supply_python_parity COMMAND HOI5 --check-supply-parity)
 add_test(NAME airbase_capture COMMAND HOI5 --check-airbase-capture)
 add_test(NAME defense_reload COMMAND HOI5 --check-defense-reload)
diff --git a/H5_CPP/main.cpp b/H5_CPP/main.cpp
index a8b6975..84f507d 100644
--- a/H5_CPP/main.cpp
+++ b/H5_CPP/main.cpp
@@ -19,6 +19,7 @@
 #include "music.hpp"
 #include "population.hpp"
 #include "python_seed.hpp"
+#include "ai_supply.hpp"
 
 #include <algorithm>
 #include <array>
@@ -283,6 +284,9 @@ struct World {
     };
     static constexpr int armyCapacity = 20;
     std::vector<Army> armies;
+    struct BotSupplyState { int owner; double nextDaily; int target = -1; };
+    std::vector<BotSupplyState> supplyBots;
+    int botHours{};
     std::vector<int> frontOwnershipChanges;
     int size{};
     int capitalQ{}, capitalR{};
@@ -1015,7 +1019,60 @@ struct World {
             "Подд. войны: " + std::to_string(int(std::lround(diplomacy.countries[0].warSupport*100))) + "%"};
     }
 
+    struct TileStorageSnapshot {
+        hoi5::Stockpile national;
+        std::map<int,hoi5::Stockpile> tiles;
+    };
+    std::vector<std::optional<TileStorageSnapshot>> tileStorageSnapshots;
+
+    const hoi5::Stockpile& stockpileAtTile(int index) {
+        static const hoi5::Stockpile empty;
+        const int owner = tiles[index].owner;
+        if (owner < 0 || owner >= int(stockpiles.size())) return empty;
+        auto& snapshot = tileStorageSnapshots[owner];
+        auto& stocks = stockpiles[owner];
+        if (!snapshot || snapshot->national != stocks) {
+            hoi5::enforceStorageCapacity(stocks,capacities[owner]);
+            snapshot.emplace();
+            snapshot->national = stocks;
+        }
+        auto [stored,inserted] = snapshot->tiles.try_emplace(index);
+        if (inserted) stored->second = hoi5::distributeTileStockpile(stocks,capacities[owner],
+            hoi5::tileStorageCapacity(tiles[index]));
+        return stored->second;
+    }
+
     void rebuildEconomy() {
+        auto previousCapacities = std::move(capacities);
+        capacities.clear();
+        bool addedStorage = false;
+        for (int country = 0; country < int(profiles.size()); ++country) {
+            auto capacity = hoi5::storageCapacity(tiles,country);
+            const bool warehouseMissing = hoi5::value(capacity,"raw") <= 0. &&
+                hoi5::value(capacity,"semi_finished") <= 0. && hoi5::value(capacity,"finished") <= 0.;
+            const bool fuelMissing = hoi5::value(capacity,"fuel") <= 0.;
+            if (warehouseMissing || fuelMissing) {
+                int site = capitals[country];
+                if (!frontLand(country,site)) {
+                    const auto fallback = std::ranges::find_if(tiles,[&](const auto& tile) {
+                        return tile.owner == country && !tile.water;
+                    });
+                    site = fallback == tiles.end() ? -1 : int(fallback-tiles.begin());
+                }
+                if (site >= 0) {
+                    auto& buildings = tiles[site].buildings;
+                    if (warehouseMissing) buildings[hoi5::warehouse].area = std::min(.26,buildings[hoi5::warehouse].area+.12);
+                    if (fuelMissing) buildings[hoi5::fuelStorage].area = std::min(.34,buildings[hoi5::fuelStorage].area+.14);
+                    capacity = hoi5::storageCapacity(tiles,country);
+                    addedStorage = true;
+                }
+            }
+            if (country >= int(previousCapacities.size()) || capacity != previousCapacities[country])
+                hoi5::enforceStorageCapacity(stockpiles[country],capacity);
+            capacities.push_back(std::move(capacity));
+        }
+        tileStorageSnapshots.assign(profiles.size(),std::nullopt);
+        if (addedStorage) hoi5::recalculateSupply(std::span(tiles),size,capitals);
         humanSupply = {};
         double totalSupply = 0.;
         int suppliedLand = 0;
@@ -1030,11 +1087,9 @@ struct World {
         const auto tradeCapacity = hoi5::Market::monthlyCapacity(tiles,profiles);
         humanTradeCapacity = tradeCapacity.empty() ? 0. : tradeCapacity.front();
         production.clear();
-        capacities.clear();
         treasury.clear();
         for (int country = 0; country < static_cast<int>(profiles.size()); ++country) {
             production.push_back(hoi5::buildProduction(tiles, country, profiles[country].population, {}));
-            capacities.push_back(hoi5::storageCapacity(tiles, country));
             treasury.push_back(hoi5::monthlyTreasury(tiles,country,profiles[country].population));
         }
     }
@@ -2555,19 +2610,24 @@ struct World {
         return sorties;
     }
 
-    int launchAirMission(int wingIndex,bool strategic,int type,int reserved,bool& infrastructureChanged) {
+    using SortieCounts = std::array<int,std::size(hoi5::aircraftTypes)>;
+
+    int launchAirMission(int wingIndex,bool strategic,int type,SortieCounts& usedAircraft,bool& infrastructureChanged) {
         auto& wing = air.wings[wingIndex];
-        if (type < 0 || !wing.enabledMissions[strategic] || wing.missionCooldowns[strategic] > 0)
+        const auto unavailable = [&] { return wing.cooldown > 0. || wing.abortedHours > 0.; };
+        if (type < 0 || !wing.enabledMissions[strategic] || wing.missionCooldowns[strategic] > 0 || unavailable())
             return 0;
         int candidates = 0;
         int target = strategic ? selectStrategicTarget(wingIndex,&candidates) : selectCasTarget(wingIndex,&candidates);
         const int packages = std::clamp(candidates,1,5);
         int used = 0;
-        for (int i = 0; i < packages && used+reserved < wing.readyForType(type); ++i) {
+        for (int i = 0; i < packages && !unavailable(); ++i) {
+            const int available = wing.readyForType(type)-usedAircraft[type];
+            if (available <= 0) break;
             if (i > 0) target = strategic ? selectStrategicTarget(wingIndex) : selectCasTarget(wingIndex);
-            const int sorties = launchAirPackage(wingIndex,strategic,type,target,wing.readyForType(type)-used-reserved,
-                infrastructureChanged);
+            const int sorties = launchAirPackage(wingIndex,strategic,type,target,available,infrastructureChanged);
             if (!sorties) break;
+            usedAircraft[type] += sorties;
             used += sorties;
         }
         if (used > 0) wing.missionCooldowns[strategic] = std::max(2.,8./std::clamp(wing.sortieIntensity,.1,1.));
@@ -3040,8 +3100,11 @@ struct World {
                 if (shared && strikeReady >= 2 && wing.enabledMissions[0] && wing.enabledMissions[1] &&
                     wing.missionCooldowns[1] <= 0 && selectStrategicTarget(wingIndex) >= 0)
                     reservedStrike = std::max(1,int(strikeReady*.4));
-                const int used = launchAirMission(wingIndex,false,casType,reservedStrike,infrastructureChanged);
-                launchAirMission(wingIndex,true,strikeType,shared ? used : 0,infrastructureChanged);
+                SortieCounts usedAircraft{};
+                if (reservedStrike) usedAircraft[strikeType] = reservedStrike;
+                launchAirMission(wingIndex,false,casType,usedAircraft,infrastructureChanged);
+                if (reservedStrike) usedAircraft[strikeType] -= reservedStrike;
+                launchAirMission(wingIndex,true,strikeType,usedAircraft,infrastructureChanged);
             }
         }
         {
@@ -3153,6 +3216,90 @@ struct World {
         return ownershipChanged;
     }
 
+    void startBots(unsigned seed) {
+        for (int owner = 1; owner < int(profiles.size()); ++owner) {
+            hoi5::PythonRandom rng(seed^(owner*1000003u));
+            (void)rng.uniform(); // The first Python draw schedules the tactical review.
+            supplyBots.push_back({owner,6.+18.*rng.uniform()});
+        }
+    }
+
+    std::optional<hoi5::BotSupplyChoice> planBotSupply(const BotSupplyState& bot,int spec) const {
+        std::vector<int> occupied(tiles.size());
+        std::vector<int> critical;
+        for (const auto& unit : divisions) {
+            if (unit.owner != bot.owner || unit.combat.strength <= 0) continue;
+            const int index = unit.r*size+unit.q;
+            if (tiles[index].owner != bot.owner) continue;
+            ++occupied[index];
+            if (tiles[index].supply < .30) critical.push_back(index);
+        }
+        std::set<int> queued, sites;
+        for (const auto& project : construction.queues[bot.owner]) {
+            if (project.spec != spec) continue;
+            queued.insert(project.tile);
+            if (project.repair) continue;
+            sites.insert(project.tile);
+            if (!project.paused && std::ranges::any_of(critical,[&](int tile) {
+                return hoi5::supplyHexDistance(project.tile,tile,size) <= 3;
+            })) return std::nullopt;
+        }
+        if (sites.size() >= 2 || (!sites.empty() && critical.empty())) return std::nullopt;
+        std::vector<hoi5::BotSupplyPoint> points;
+        std::vector<hoi5::BotSupplyCandidate> candidates;
+        for (int index = 0; index < int(tiles.size()); ++index) {
+            const auto& tile = tiles[index];
+            if (tile.owner != bot.owner || tile.water) continue;
+            bool border = false, hostileBorder = false;
+            forFrontNeighbor(index,[&](int neighbor) {
+                const auto& other = tiles[neighbor];
+                if (other.water || other.owner < 0 || other.owner == bot.owner) return;
+                border = true;
+                hostileBorder |= diplomacy.hostile(bot.owner,other.owner);
+            });
+            const int weight = occupied[index]+(border ? 3 : 0);
+            if (weight && tile.supply < .55)
+                points.push_back({index,double(weight),1./std::max(1.,tile.movementCost),tile.supply});
+            const double coverage = tile.buildings[hoi5::supplyDepot].area;
+            if (coverage >= .7 || queued.contains(index)) continue;
+            double strength = capitals[bot.owner] == index ? .85 : 0.;
+            for (int b = 0; b < hoi5::buildingCount; ++b)
+                strength += tile.buildings[b].area*tile.buildings[b].health*hoi5::supplySourceWeights[b];
+            strength = std::min(1.,strength+hoi5::supplySourceWeights[hoi5::supplyDepot]*(.7-coverage));
+            double multiplier = hostileBorder ? .85 : 1.;
+            if (battles.contains(index)) multiplier *= .8;
+            if (index == bot.target) multiplier *= 1.2;
+            candidates.push_back({index,strength,multiplier});
+        }
+        return hoi5::bestBotSupplySite(size,points,candidates);
+    }
+
+    void updateBots(int hours,hoi5::DebugProfiler* debug) {
+        if (supplyBots.empty()) return;
+        hoi5::DebugMeasure total(debug,"ai_total");
+        botHours += hours;
+        const int spec = std::ranges::find(hoi5::constructionSpecs,hoi5::supplyDepot,
+            &hoi5::ConstructionSpec::building)-std::begin(hoi5::constructionSpecs);
+        std::vector<std::pair<int,int>> orders;
+        {
+            hoi5::DebugMeasure daily(debug,"ai_daily");
+            for (auto& bot : supplyBots) {
+                if (botHours < bot.nextDaily) continue;
+                bot.nextDaily = botHours+24;
+                const auto choice = planBotSupply(bot,spec);
+                bot.target = choice ? choice->tile : -1;
+                if (choice) orders.emplace_back(bot.owner,choice->tile);
+            }
+        }
+        hoi5::DebugMeasure tasks(debug,"ai_tasks");
+        for (const auto& [owner,tile] : orders) {
+            auto& queue = construction.queues[owner];
+            if (!construction.enqueue(tiles,size,owner,tile,spec,profiles[owner].buildEfficiency).empty()) continue;
+            if (queue.back().money > std::max(0.,profiles[owner].budget-5000000.)) queue.pop_back();
+            else std::rotate(queue.begin(),std::prev(queue.end()),queue.end());
+        }
+    }
+
     void advance(int hours,hoi5::DebugProfiler* debug = nullptr,std::optional<int> marketRotation = std::nullopt) {
         if (hours <= 0) return;
         using Clock = hoi5::DebugProfiler::Clock;
@@ -3267,6 +3414,7 @@ struct World {
                 if (tile.owner >= 0) profiles[tile.owner].population += tile.population;
         }
         if ((airDamage || battleDamage || helipadBuilt || ownershipChanged) && !capitals.empty()) refreshBuildings();
+        updateBots(hours,debug);
         news.flushNotices();
     }
 
@@ -4540,6 +4688,39 @@ int main(int argc, char** argv) try {
             test.air.defense[0].tile == 3 && test.air.freeCapacity(test.tiles,0,1,0) == 46 ? 0 : 1;
     }
     if (mode == "--check-air-strike") {
+        {
+            World packages;
+            packages.size = 8;
+            packages.tiles.resize(64);
+            packages.diplomacy.countries.resize(2);
+            packages.diplomacy.relation(0,1).war = true;
+            packages.air.wings.push_back({0,0,4,16,3,0,{true,true}});
+            auto& wing = packages.air.wings.front();
+            wing.composition = {{4,8},{2,8}};
+            wing.sortieIntensity = 1.;
+            wing.operationArea = {3,4};
+            for (int tile : wing.operationArea) {
+                packages.tiles[tile].owner = 1;
+                packages.tiles[tile].buildings[hoi5::industry].area = .3;
+                auto& defender = packages.divisions.emplace_back();
+                defender.q = tile;
+                defender.owner = 1;
+            }
+            World::SortieCounts used{};
+            bool changed = false;
+            if (packages.launchAirMission(0,false,wing.missionType(0),used,changed) != 4 ||
+                packages.launchAirMission(0,true,wing.missionType(1),used,changed) != 4 ||
+                used[4] != 4 || used[2] != 4 || packages.salvos.size() != 4 ||
+                wing.missionCooldowns != std::array{8.,8.}) return 1;
+            for (int i = 0; i < 4; i += 2)
+                if (packages.salvos[i].target == packages.salvos[i+1].target ||
+                    packages.salvos[i].sourceAircraft != (i == 0 ? 4 : 2) ||
+                    packages.salvos[i+1].sourceAircraft != packages.salvos[i].sourceAircraft) return 1;
+            wing.missionCooldowns = {};
+            wing.abortedHours = 2.;
+            if (packages.launchAirMission(0,true,wing.missionType(1),used,changed) ||
+                packages.salvos.size() != 4 || wing.missionCooldowns[1] != 0.) return 1;
+        }
         World priorities;
         priorities.size = 2;
         priorities.tiles.resize(4);
@@ -4727,6 +4908,28 @@ int main(int argc, char** argv) try {
             division.combat.strength < strength && city.health < health ? 0 : 1;
     }
     if (mode == "--check-supply-parity") {
+        constexpr std::array points{hoi5::BotSupplyPoint{2,3.,.5,.1},hoi5::BotSupplyPoint{6,2.,1.,.2}};
+        constexpr std::array candidates{hoi5::BotSupplyCandidate{1,.8,1.},hoi5::BotSupplyCandidate{6,.7,.85}};
+        const auto choice = hoi5::bestBotSupplySite(4,points,candidates);
+        if (!choice || choice->tile != 1 || std::abs(choice->gain-1.60256) > 1e-12) return 1;
+        {
+            World bot;
+            bot.size = 3;
+            bot.tiles.resize(9);
+            bot.profiles.resize(2,{1.,1000000.,20000000.});
+            bot.diplomacy.countries.resize(2);
+            bot.construction.queues.resize(2);
+            bot.capitals = {0,1};
+            bot.tiles[1].owner = 1;
+            auto& division = bot.divisions.emplace_back();
+            division.q = division.owner = 1;
+            bot.startBots(7);
+            bot.updateBots(24,nullptr);
+            if (!bot.construction.queues[0].empty() || bot.construction.queues[1].size() != 1 ||
+                bot.construction.queues[1].front().tile != 1) return 1;
+            bot.updateBots(24,nullptr);
+            if (bot.construction.queues[1].size() != 1) return 1;
+        }
         std::vector<Tile> tiles(4);
         tiles[0].owner = 1;
         tiles[1].owner = 0;
@@ -4740,6 +4943,35 @@ int main(int argc, char** argv) try {
         hoi5::recalculateSupply(std::span(tiles),2,capitals);
         return std::abs(tiles[1].supply-.071) < 1e-12 ? 0 : 1;
     }
+    if (mode == "--check-news-log" && argc == 3) {
+        const std::filesystem::path path(argv[2]);
+        constexpr std::array<std::string_view,2> countries{"Игрок","Сосед"}, rulers{"Правитель",""};
+        const auto read = [&] {
+            std::ifstream stream(path);
+            return std::string(std::istreambuf_iterator<char>(stream),{});
+        };
+        hoi5::News news(123);
+        news.startLog(path,countries,rulers);
+        for (int day = 0; day < 305; ++day)
+            news.report(day,"test","Заголовок "+std::to_string(day),"Описание "+std::to_string(day),
+                hoi5::NewsPriority::important,0,1);
+        news.report(305,"world","Мировая новость","Описание",hoi5::NewsPriority::flavor);
+        const auto journal = read();
+        if (!journal.starts_with("HOI5 — история новостей новой партии\nСид: 123\nНачало: 2000-01-01\n"
+                "Страна 0: Игрок; правитель: Правитель\nСтрана 1: Сосед; правитель: не указан\n\n") ||
+            journal.find("[2000-01-01] #1 [important] [страны 0, 1] test\nЗаголовок 0\nОписание 0\n\n") == std::string::npos ||
+            journal.find("[2000-10-31] #305 [important] [страны 0, 1] test\nЗаголовок 304\nОписание 304\n\n") == std::string::npos ||
+            !journal.ends_with("[2000-11-01] #306 [flavor] [мир] world\nМировая новость\nОписание\n\n") ||
+            news.visible(0).size() != 300) return 1;
+        hoi5::News restarted(456);
+        restarted.startLog(path,countries,rulers);
+        const auto reset = read();
+        if (reset.find("Сид: 456\n") == std::string::npos || reset.find("Заголовок") != std::string::npos) return 1;
+        restarted.startLog(path/"world-news.txt",countries,rulers);
+        restarted.report(0,"still_visible","Игра продолжается","Нет доступа к журналу");
+        const auto* item = restarted.latest(0);
+        return item && item->key == "still_visible" ? 0 : 1;
+    }
     if (mode == "--check-news-popup") {
         hoi5::Market steadyMarket;
         const std::vector<hoi5::MarketOrder> coalOrders{{0,"coal",true,10000.}};
@@ -5203,6 +5435,29 @@ int main(int argc, char** argv) try {
         return !retreat.retreating && retreat.combat.strength > 0 && retreat.r == 1 ? 0 : 1;
     }
     if (mode == "--check-economy") {
+        {
+            World storage;
+            storage.size = 2;
+            storage.tiles.resize(4);
+            storage.profiles.resize(1,{1.,1000000.,20000000.});
+            storage.capitals = {0};
+            storage.stockpiles = {{{"iron_ore",200000.},{"copper_ore",100000.},{"coal",500000.}}};
+            storage.tiles[0].buildings[hoi5::warehouse] = {.10,1.};
+            storage.tiles[1].buildings[hoi5::warehouse] = {.20,.25};
+            storage.rebuildEconomy();
+            const auto close = [](double a,double b) { return std::abs(a-b) < 1e-8; };
+            if (!close(hoi5::value(storage.stockpiles[0],"coal"),448000.) ||
+                !close(hoi5::value(storage.stockpileAtTile(0),"iron_ore"),70000.) ||
+                !close(hoi5::value(storage.stockpileAtTile(1),"iron_ore"),35000.) ||
+                !close(hoi5::value(storage.stockpileAtTile(0),"copper_ore"),35000.) ||
+                !storage.stockpileAtTile(2).empty()) return 1;
+            storage.stockpiles[0]["iron_ore"] = 15000.;
+            if (!close(hoi5::value(storage.stockpileAtTile(0),"iron_ore"),10000.)) return 1;
+            storage.tiles[0].owner = -1;
+            storage.rebuildEconomy();
+            if (!storage.stockpileAtTile(0).empty() ||
+                !close(hoi5::value(storage.stockpileAtTile(1),"iron_ore"),11666.666666666666)) return 1;
+        }
         if (exportSliderPercent(100) != 0 || exportSliderPercent(235) != 35 ||
             exportSliderPercent(500) != 100 || exportSliderPercent(137) != 0 ||
             exportSliderPercent(138) != 5) return 1;
@@ -6043,7 +6298,11 @@ int main(int argc, char** argv) try {
         dropdown = -1;
         const int size = sizes[sizeChoice];
         const unsigned seed = 1 + std::random_device{}() % 999999;
-        generator = std::async(std::launch::async, generateWorld, size, countries, seed, difficulty);
+        generator = std::async(std::launch::async,[=] {
+            auto generated = generateWorld(size,countries,seed,difficulty);
+            generated.startBots(seed);
+            return generated;
+        });
     };
     if (generationSmoke) startGame();
     sf::Clock clock;
@@ -7029,6 +7288,9 @@ int main(int argc, char** argv) try {
         if (generator.valid() && generator.wait_for(std::chrono::seconds(0)) == std::future_status::ready) {
             try {
                 world = generator.get();
+                world.news.startLog(directory/"logs"/"world-news.txt",
+                    std::span(world.countryNames).first(world.profiles.size()),
+                    std::span(world.rulers).first(world.profiles.size()));
                 if (music) music->newWorld();
                 (void)musicReview.restart();
                 tradePanel = diplomacyPanel = false;
@@ -7960,16 +8222,9 @@ int main(int argc, char** argv) try {
                 const auto hex_storage_lookupStart = DebugClock::now();
                 for (int cell : selectedTiles) {
                     const auto& selected = world.tiles[cell];
-                    if (selected.owner < 0 || selected.owner >= int(world.stockpiles.size())) continue;
                     const auto capacity = hoi5::tileStorageCapacity(selected);
                     for (const auto& [bucket,amount] : capacity) localCapacity[bucket] += amount;
-                    const auto& total = world.capacities[selected.owner];
-                    for (const auto& [key,amount] : world.stockpiles[selected.owner]) {
-                        const auto bucket = hoi5::storageBucket(key);
-                        const double whole = hoi5::value(total,bucket);
-                        const double part = hoi5::value(capacity,bucket);
-                        if (whole > 0 && part > 0 && amount > 0) localStock[key] += amount*part/whole;
-                    }
+                    for (const auto& [key,amount] : world.stockpileAtTile(cell)) localStock[key] += amount;
                 }
                 debug.record("hex_storage_lookup",hex_storage_lookupStart);
                 const auto hex_resources_lookupStart = DebugClock::now();
diff --git a/H5_CPP/market.hpp b/H5_CPP/market.hpp
index 4460da3..38225a1 100644
--- a/H5_CPP/market.hpp
+++ b/H5_CPP/market.hpp
@@ -5,11 +5,6 @@
 
 namespace hoi5 {
 
-inline double value(const Stockpile& values, std::string_view name, double fallback = 0) {
-    const auto it = values.find(name);
-    return it == values.end() ? fallback : it->second;
-}
-
 struct Market {
     static constexpr double weeklyFraction = 7./30.;
     static constexpr double buyMarkup = 1.08, sellMarkdown = .92;
diff --git a/H5_CPP/news.hpp b/H5_CPP/news.hpp
index b710717..9c23982 100644
--- a/H5_CPP/news.hpp
+++ b/H5_CPP/news.hpp
@@ -4,8 +4,14 @@
 #include "format_amount.hpp"
 #include "python_seed.hpp"
 #include "world_news_data.hpp"
+#include <chrono>
 #include <deque>
+#include <filesystem>
+#include <fstream>
+#include <iomanip>
+#include <iostream>
 #include <random>
+#include <span>
 #include <string>
 
 namespace hoi5 {
@@ -49,19 +55,74 @@ class News {
     std::map<std::string_view,int> lastTemplateDay;
     std::mt19937 rng;
     std::vector<NoticeBatch> pendingNotices;
+    std::uint64_t worldSeed;
+    std::filesystem::path logPath;
+    bool logFailed{};
+
+    static void writeLogDate(std::ostream& out,int day) {
+        using namespace std::chrono;
+        const year_month_day date{sys_days{year{2000}/1/1}+days{day}};
+        out << int(date.year()) << '-' << std::setfill('0') << std::setw(2) << unsigned(date.month())
+            << '-' << std::setw(2) << unsigned(date.day());
+    }
+
+    void reportLogError(std::string_view message) {
+        logFailed = true;
+        std::cerr << message << ": " << logPath << '\n';
+    }
+
+    void logItem(const NewsItem& item) {
+        if (logPath.empty() || logFailed) return;
+        std::ofstream stream(logPath,std::ios::app);
+        constexpr std::array priorities{"flavor","regular","important","critical"};
+        stream << '[';
+        writeLogDate(stream,item.day);
+        stream << "] #" << item.id << " [" << priorities[static_cast<int>(item.priority)] << "] [";
+        if (item.viewer < 0) stream << "мир";
+        else {
+            stream << "страны " << item.viewer;
+            if (item.otherViewer >= 0 && item.otherViewer != item.viewer) stream << ", " << item.otherViewer;
+        }
+        stream << "] " << item.key << '\n' << item.title << '\n' << item.body << "\n\n";
+        stream.close();
+        if (!stream) reportLogError("Не удалось записать новость");
+    }
 
     void publish(NewsItem item) {
         item.id = nextId++;
         items.push_front(std::move(item));
         if (items.size() > 300) items.pop_back();
+        logItem(items.front());
     }
 
 public:
-    explicit News(std::uint64_t seed = 0) {
+    explicit News(std::uint64_t seed = 0) : worldSeed(seed) {
         PythonSeed pythonSeed{seed};
         rng.seed(pythonSeed);
     }
 
+    void startLog(const std::filesystem::path& path,std::span<const std::string_view> countries,
+                  std::span<const std::string_view> rulers) {
+        logPath = path;
+        logFailed = false;
+        std::error_code error;
+        if (!path.parent_path().empty()) std::filesystem::create_directories(path.parent_path(),error);
+        if (error) {
+            reportLogError("Не удалось создать каталог журнала новостей");
+            return;
+        }
+        std::ofstream stream(logPath);
+        stream << "HOI5 — история новостей новой партии\nСид: " << worldSeed << "\nНачало: ";
+        writeLogDate(stream,0);
+        stream << '\n';
+        for (std::size_t i = 0; i < countries.size(); ++i)
+            stream << "Страна " << i << ": " << countries[i] << "; правитель: "
+                   << (i < rulers.size() && !rulers[i].empty() ? rulers[i] : "не указан") << '\n';
+        stream << '\n';
+        stream.close();
+        if (!stream) reportLogError("Не удалось создать журнал новостей");
+    }
+
     int report(int day,std::string_view key,std::string title,std::string body,
                 NewsPriority priority = NewsPriority::regular,int viewer = -1,int otherViewer = -1) {
         publish({day,viewer,priority,std::move(title),std::move(body),0,std::string(key),otherViewer});
diff --git a/H5_CPP/port_progress.tsv b/H5_CPP/port_progress.tsv
index b919769..839fb64 100644
--- a/H5_CPP/port_progress.tsv
+++ b/H5_CPP/port_progress.tsv
@@ -682,7 +682,7 @@
 "H5_Python/ai_regions.py"	"17"	"function"	"RegionMap.build"	"1"	"excluded_bot"	""	""
 "H5_Python/ai_regions.py"	"43"	"function"	"RegionMap.controlled"	"1"	"excluded_bot"	""	""
 "H5_Python/ai_regions.py"	"70"	"function"	"RegionMap.profile"	"1"	"excluded_bot"	""	""
-"H5_Python/ai_supply.py"	"7"	"function"	"supply_site"	"1"	"excluded_bot"	""	""
+"H5_Python/ai_supply.py"	"7"	"function"	"supply_site"	"1"	"excluded_bot"	"World::planBotSupply"	"AI track: border, occupied and existing depot scoring; mobilization weights and assignments pending"
 "H5_Python/ai_system.py"	"18"	"class"	"CountryAI"	"1"	"excluded_bot"	""	""
 "H5_Python/ai_system.py"	"19"	"function"	"CountryAI.__init__"	"1"	"excluded_bot"	""	""
 "H5_Python/ai_system.py"	"50"	"function"	"CountryAI.hour"	"1"	"excluded_bot"	""	""
@@ -706,7 +706,7 @@
 "H5_Python/ai_system.py"	"537"	"function"	"CountryAI.preparation_front"	"1"	"excluded_bot"	""	""
 "H5_Python/ai_system.py"	"542"	"function"	"CountryAI.war_preparation_blocker"	"1"	"excluded_bot"	""	""
 "H5_Python/ai_system.py"	"566"	"function"	"CountryAI.recruitment_tasks"	"1"	"excluded_bot"	""	""
-"H5_Python/ai_system.py"	"592"	"function"	"CountryAI.supply_tasks"	"1"	"excluded_bot"	""	""
+"H5_Python/ai_system.py"	"592"	"function"	"CountryAI.supply_tasks"	"1"	"excluded_bot"	"World::updateBots"	"AI track: daily supply project selection, fiscal reserve and construction priority; trade and task lifecycle pending"
 "H5_Python/ai_system.py"	"629"	"function"	"CountryAI.defense_infrastructure_tasks"	"1"	"excluded_bot"	""	""
 "H5_Python/ai_system.py"	"673"	"function"	"CountryAI.diplomatic_tasks"	"1"	"excluded_bot"	""	""
 "H5_Python/ai_system.py"	"714"	"function"	"CountryAI.offer_response"	"1"	"excluded_bot"	""	""
@@ -721,7 +721,7 @@
 "H5_Python/ai_system.py"	"1172"	"function"	"CountryAI.tactical"	"1"	"excluded_bot"	""	""
 "H5_Python/ai_system.py"	"1366"	"function"	"CountryAI.ownership_changed"	"1"	"excluded_bot"	""	""
 "H5_Python/ai_system.py"	"1371"	"function"	"CountryAI.snapshot"	"1"	"excluded_bot"	""	""
-"H5_Python/ai_workers.py"	"7"	"function"	"best_supply_site"	"1"	"excluded_bot"	""	""
+"H5_Python/ai_workers.py"	"7"	"function"	"best_supply_site"	"1"	"excluded_bot"	"hoi5::bestBotSupplySite"	"AI track: matched Python selected hex and gain 1.60256"
 "H5_Python/ai_workers.py"	"24"	"function"	"regional_profiles"	"1"	"excluded_bot"	""	""
 "H5_Python/ai_workers.py"	"64"	"class"	"AIPlanningWorkers"	"1"	"excluded_bot"	""	""
 "H5_Python/ai_workers.py"	"65"	"function"	"AIPlanningWorkers.__init__"	"1"	"excluded_bot"	""	""
@@ -748,7 +748,7 @@
 "H5_Python/air_system.py"	"123"	"function"	"AirSystemMixin.air_wing_extra_capacity_for_type"	"1"	"unreviewed"	""	""
 "H5_Python/air_system.py"	"133"	"function"	"AirSystemMixin.air_wing_type_counts_by_role"	"1"	"unreviewed"	""	""
 "H5_Python/air_system.py"	"143"	"function"	"AirSystemMixin.air_wing_primary_type_for_mission"	"1"	"unreviewed"	""	""
-"H5_Python/air_system.py"	"187"	"function"	"AirSystemMixin.air_wing_ready_count_for_type"	"1"	"unreviewed"	""	""
+"H5_Python/air_system.py"	"187"	"function"	"AirSystemMixin.air_wing_ready_count_for_type"	"1"	"ported"	"AirWing::readyForType"	"Proportional ready share and ties-to-even rounding; mixed-wing scenarios"
 "H5_Python/air_system.py"	"195"	"function"	"AirSystemMixin.air_wing_interceptor_loadout_data"	"1"	"unreviewed"	""	""
 "H5_Python/air_system.py"	"198"	"function"	"AirSystemMixin.air_wing_interceptor_capacity_for_type"	"1"	"unreviewed"	""	""
 "H5_Python/air_system.py"	"204"	"function"	"AirSystemMixin.air_wing_interceptor_capacity"	"1"	"unreviewed"	""	""
@@ -904,9 +904,9 @@
 "H5_Python/air_system.py"	"3463"	"function"	"AirSystemMixin.select_air_wing_cas_target"	"1"	"unreviewed"	""	""
 "H5_Python/air_system.py"	"3486"	"function"	"AirSystemMixin.air_wing_cas_candidate_tiles"	"1"	"unreviewed"	""	""
 "H5_Python/air_system.py"	"3503"	"function"	"AirSystemMixin.select_air_wing_active_mission"	"1"	"unreviewed"	""	""
-"H5_Python/air_system.py"	"3515"	"function"	"AirSystemMixin.execute_air_wing_active_mission"	"1"	"unreviewed"	""	""
-"H5_Python/air_system.py"	"3635"	"function"	"AirSystemMixin.launch_air_wing_mission_packages"	"1"	"missing"	""	"Native updateAir dispatches one launch per active mission instead of a target package loop"
-"H5_Python/air_system.py"	"3683"	"function"	"AirSystemMixin.update_air_missions"	"1"	"unreviewed"	""	""
+"H5_Python/air_system.py"	"3515"	"function"	"AirSystemMixin.execute_air_wing_active_mission"	"1"	"partial"	"World::launchAirPackage"	"Package size, loadout, ground defense and launch result; mission state and interception sequencing still differ"
+"H5_Python/air_system.py"	"3635"	"function"	"AirSystemMixin.launch_air_wing_mission_packages"	"1"	"partial"	"World::launchAirMission"	"Five-package cap, per-aircraft availability and abort/global cooldown guard; mixed-wing scenario compared"
+"H5_Python/air_system.py"	"3683"	"function"	"AirSystemMixin.update_air_missions"	"1"	"partial"	"World::updateAir"	"Shared per-type sortie budget, strategic reservation, independent cooldowns; mission state and full combat parity pending"
 "H5_Python/air_system.py"	"3726"	"function"	"AirSystemMixin.update_air_assets_after_tile_owner_change"	"1"	"unreviewed"	""	""
 "H5_Python/audio_process.py"	"8"	"function"	"audio_main"	"1"	"unreviewed"	""	""
 "H5_Python/audio_process.py"	"17"	"function"	"audio_main.report"	"1"	"unreviewed"	""	""
@@ -1092,19 +1092,19 @@
 "H5_Python/economy_system.py"	"151"	"function"	"EconomySystemMixin.mark_player_stockpiles_changed"	"1"	"unreviewed"	""	""
 "H5_Python/economy_system.py"	"156"	"function"	"EconomySystemMixin.cached_resource_balance_breakdown"	"1"	"unreviewed"	""	""
 "H5_Python/economy_system.py"	"169"	"function"	"EconomySystemMixin.ensure_player_storage"	"1"	"unreviewed"	""	""
-"H5_Python/economy_system.py"	"181"	"function"	"EconomySystemMixin.ensure_player_tile_stockpiles"	"1"	"unreviewed"	""	""
+"H5_Python/economy_system.py"	"181"	"function"	"EconomySystemMixin.ensure_player_tile_stockpiles"	"1"	"partial"	"World::stockpileAtTile"	"Native lazy snapshot invalidated by country stock changes and building/ownership refresh"
 "H5_Python/economy_system.py"	"186"	"function"	"EconomySystemMixin.empty_tile_stockpiles"	"1"	"unreviewed"	""	""
-"H5_Python/economy_system.py"	"194"	"function"	"EconomySystemMixin.storage_bucket_for_resource"	"1"	"unreviewed"	""	""
+"H5_Python/economy_system.py"	"194"	"function"	"EconomySystemMixin.storage_bucket_for_resource"	"1"	"ported"	"hoi5::storageBucket"	"Fuel keys take priority over economic categories; paired storage fixture"
 "H5_Python/economy_system.py"	"198"	"function"	"EconomySystemMixin.empty_storage_summary"	"1"	"unreviewed"	""	""
-"H5_Python/economy_system.py"	"201"	"function"	"EconomySystemMixin.tile_storage_capacity_by_category"	"1"	"unreviewed"	""	""
+"H5_Python/economy_system.py"	"201"	"function"	"EconomySystemMixin.tile_storage_capacity_by_category"	"1"	"ported"	"hoi5::tileStorageCapacity"	"Direct per-building capacity coefficients with effective coverage; paired damaged warehouse fixture"
 "H5_Python/economy_system.py"	"212"	"function"	"EconomySystemMixin.tile_storage_capacity"	"1"	"unreviewed"	""	""
 "H5_Python/economy_system.py"	"218"	"function"	"EconomySystemMixin.tile_fuel_storage_capacity"	"1"	"unreviewed"	""	""
 "H5_Python/economy_system.py"	"221"	"function"	"EconomySystemMixin.tile_storage_used_by_category"	"1"	"unreviewed"	""	""
 "H5_Python/economy_system.py"	"229"	"function"	"EconomySystemMixin.storage_summary_for_tiles"	"1"	"unreviewed"	""	""
 "H5_Python/economy_system.py"	"240"	"function"	"EconomySystemMixin.recalculate_player_storage"	"1"	"unreviewed"	""	""
 "H5_Python/economy_system.py"	"267"	"function"	"EconomySystemMixin.storage_free_capacity_for_resource"	"1"	"ported"	"storage.hpp::freeStorage"	"Capacity is shared across the matching resource bucket."
-"H5_Python/economy_system.py"	"272"	"function"	"EconomySystemMixin.enforce_player_storage_capacity"	"1"	"unreviewed"	""	""
-"H5_Python/economy_system.py"	"301"	"function"	"EconomySystemMixin.distribute_player_stockpiles_to_tiles"	"1"	"partial"	"Hex panel localStock calculation"	"Proportional estimate calculated for display; Python keeps distributed tile stock and storage state"
+"H5_Python/economy_system.py"	"272"	"function"	"EconomySystemMixin.enforce_player_storage_capacity"	"1"	"partial"	"hoi5::enforceStorageCapacity"	"Proportional per-bucket trimming matched; discarded amounts are not yet exposed as separate overflow history"
+"H5_Python/economy_system.py"	"301"	"function"	"EconomySystemMixin.distribute_player_stockpiles_to_tiles"	"1"	"partial"	"World::stockpileAtTile; hoi5::distributeTileStockpile"	"Native per-tile cached stock, capacity-based split and fallback depots; paired shortage and ownership fixture"
 "H5_Python/economy_system.py"	"352"	"function"	"EconomySystemMixin.add_resource_amount"	"1"	"unreviewed"	""	""
 "H5_Python/economy_system.py"	"356"	"function"	"EconomySystemMixin.raw_amount"	"1"	"unreviewed"	""	""
 "H5_Python/economy_system.py"	"359"	"function"	"EconomySystemMixin.recalculate_state_resources"	"1"	"unreviewed"	""	""
@@ -1251,10 +1251,10 @@
 "H5_Python/news_panel.py"	"258"	"function"	"NewsPanelMixin.handle_news_scroll"	"1"	"unreviewed"	""	""
 "H5_Python/news_system.py"	"17"	"class"	"NewsTemplate"	"1"	"unreviewed"	""	""
 "H5_Python/news_system.py"	"194"	"class"	"NewsItem"	"1"	"unreviewed"	""	""
-"H5_Python/news_system.py"	"206"	"class"	"NewsSystem"	"1"	"partial"	"news.hpp::News"	"Event feed present, contextual headlines and file journal pending."
+"H5_Python/news_system.py"	"206"	"class"	"NewsSystem"	"1"	"partial"	"news.hpp::News"	"Native feed, archive, contextual templates and file journal; event coverage still under audit"
 "H5_Python/news_system.py"	"207"	"function"	"NewsSystem.__init__"	"1"	"unreviewed"	""	""
-"H5_Python/news_system.py"	"227"	"function"	"NewsSystem.start_log"	"1"	"missing"	""	"Native News stores in-memory feed and archive without a file journal"
-"H5_Python/news_system.py"	"243"	"function"	"NewsSystem.log_item"	"1"	"missing"	""	"Native News has no persistent log writer"
+"H5_Python/news_system.py"	"227"	"function"	"NewsSystem.start_log"	"1"	"ported"	"News::startLog"	"New-world reset, seed and UTF-8 country header; fixed simulation epoch"
+"H5_Python/news_system.py"	"243"	"function"	"NewsSystem.log_item"	"1"	"ported"	"News::logItem"	"Immediate append, date, priority and audience; full history beyond the 300-item feed; write failure is nonfatal"
 "H5_Python/news_system.py"	"256"	"function"	"NewsSystem.begin_notice_batch"	"1"	"unreviewed"	""	""
 "H5_Python/news_system.py"	"259"	"function"	"NewsSystem.end_notice_batch"	"1"	"unreviewed"	""	""
 "H5_Python/news_system.py"	"275"	"function"	"NewsSystem.notice"	"1"	"unreviewed"	""	""
diff --git a/H5_CPP/starting_economy.hpp b/H5_CPP/starting_economy.hpp
index 54a8d89..4f44b47 100644
--- a/H5_CPP/starting_economy.hpp
+++ b/H5_CPP/starting_economy.hpp
@@ -6,6 +6,12 @@
 namespace hoi5 {
 
 using Stockpile = std::map<std::string_view, double>;
+
+inline double value(const Stockpile& values, std::string_view name, double fallback = 0) {
+    const auto it = values.find(name);
+    return it == values.end() ? fallback : it->second;
+}
+
 inline Stockpile startingStockpile(unsigned seed, double scale) {
     struct Entry { std::string_view name; int minimum, maximum; double multiplier; };
     constexpr Entry entries[] = {
diff --git a/H5_CPP/storage.hpp b/H5_CPP/storage.hpp
index 7174a09..fa57b6d 100644
--- a/H5_CPP/storage.hpp
+++ b/H5_CPP/storage.hpp
@@ -4,6 +4,8 @@
 
 namespace hoi5 {
 
+inline constexpr std::array<std::string_view,4> storageBuckets{"raw","semi_finished","finished","fuel"};
+
 inline std::string_view storageBucket(std::string_view resource) {
     constexpr std::array fuel{"coal","oil","natural_gas","peat","uranium","refined_fuel"};
     constexpr std::array semi{"steel","chemicals","food","fertilizer","copper_wire"};
@@ -19,7 +21,6 @@ inline std::string_view storageBucket(std::string_view resource) {
 
 template<class Tile>
 Stockpile tileStorageCapacity(const Tile& tile) {
-    constexpr std::array<std::string_view,4> buckets{"raw","semi_finished","finished","fuel"};
     constexpr int rates[][buildingCount] = {
         {520000,180000,1050000,240000,280000},
         {470000,140000,820000,210000,240000},
@@ -27,11 +28,35 @@ Stockpile tileStorageCapacity(const Tile& tile) {
         {180000,35000,0,120000,220000,3200000,850000,420000}
     };
     Stockpile result;
-    for (std::size_t bucket = 0; bucket < buckets.size(); ++bucket) {
+    for (std::size_t bucket = 0; bucket < storageBuckets.size(); ++bucket) {
         double capacity = 0;
         for (int b = 0; b < buildingCount; ++b)
             capacity += tile.buildings[b].area * tile.buildings[b].health * rates[bucket][b];
-        result[buckets[bucket]] = capacity;
+        result[storageBuckets[bucket]] = capacity;
+    }
+    return result;
+}
+
+inline void enforceStorageCapacity(Stockpile& stocks,const Stockpile& capacity) {
+    Stockpile used;
+    for (const auto& [resource,amount] : stocks) used[storageBucket(resource)] += std::max(0.,amount);
+    Stockpile retention;
+    for (auto bucket : storageBuckets) {
+        const double total = value(used,bucket);
+        retention[bucket] = total > 0. ? std::clamp(value(capacity,bucket)/total,0.,1.) : 1.;
+    }
+    for (auto& [resource,amount] : stocks)
+        if (amount > 0.) amount *= retention.at(storageBucket(resource));
+}
+
+inline Stockpile distributeTileStockpile(const Stockpile& stocks,const Stockpile& nationalCapacity,
+                                         const Stockpile& tileCapacity) {
+    Stockpile result;
+    for (const auto& [resource,amount] : stocks) {
+        if (amount <= 0.) continue;
+        const auto bucket = storageBucket(resource);
+        const double total = value(nationalCapacity,bucket), local = value(tileCapacity,bucket);
+        if (total > 0. && local > 0.) result[resource] = amount*(local/total);
     }
     return result;
 }
diff --git a/H5_CPP/supply.hpp b/H5_CPP/supply.hpp
index 44081e3..2289e11 100644
--- a/H5_CPP/supply.hpp
+++ b/H5_CPP/supply.hpp
@@ -15,9 +15,10 @@ struct BuildingCoverage {
     double health = 1;
 };
 
+inline constexpr std::array<double,buildingCount> supplySourceWeights{1.,.48,.50,.92,.46,.22,.30,.18,.18};
+
 template<class Tile>
 void recalculateSupply(std::span<Tile> tiles, int size, const std::vector<int>& capitals) {
-    constexpr std::array<double,buildingCount> sourceWeights{1., .48, .50, .92, .46, .22, .30, .18, .18, 0., 0., 0.};
     constexpr std::array<double,buildingCount> relayWeights{0., 0., .28, .72, .22, 0., 0., 0., 0., 0., 0., 0.};
     std::array<double, 8> decay{};
     for (int d = 0; d <= 7; ++d) decay[d] = std::pow(.78, d);
@@ -40,7 +41,7 @@ void recalculateSupply(std::span<Tile> tiles, int size, const std::vector<int>&
         const auto& source = tiles[index];
         if (source.water || source.owner < 0) continue;
         double strength = index == capitals[source.owner] ? .85 : 0.;
-        for (int b = 0; b < buildingCount; ++b) strength += effective(source.buildings[b]) * sourceWeights[b];
+        for (int b = 0; b < buildingCount; ++b) strength += effective(source.buildings[b]) * supplySourceWeights[b];
         if (strength <= 0) continue;
         hasSource[source.owner] = true;
         spread(index,source.owner,std::clamp(strength,0.,1.));
diff --git a/H5_CPP/ai_supply.hpp b/H5_CPP/ai_supply.hpp
new file mode 100644
index 0000000..65b2d4c
--- /dev/null
+++ b/H5_CPP/ai_supply.hpp
@@ -0,0 +1,36 @@
+#pragma once
+
+#include <algorithm>
+#include <cmath>
+#include <optional>
+#include <span>
+
+namespace hoi5 {
+
+struct BotSupplyPoint { int tile; double weight, passability, current; };
+struct BotSupplyCandidate { int tile; double strength, multiplier; };
+struct BotSupplyChoice { double gain; int tile; };
+
+inline int supplyHexDistance(int first,int second,int width) {
+    const int dq = first%width-second%width, dr = first/width-second/width;
+    return std::max({std::abs(dq),std::abs(dr),std::abs(dq+dr)});
+}
+
+inline std::optional<BotSupplyChoice> bestBotSupplySite(int width,std::span<const BotSupplyPoint> points,
+                                                     std::span<const BotSupplyCandidate> candidates) {
+    std::optional<BotSupplyChoice> best;
+    for (const auto& candidate : candidates) {
+        double gain = 0.;
+        for (const auto& point : points) {
+            const int distance = supplyHexDistance(candidate.tile,point.tile,width);
+            if (distance > 7) continue;
+            const double expected = candidate.strength*std::pow(.78,distance)*(.42+.58*point.passability);
+            gain += std::max(0.,std::min(.6,expected)-point.current)*point.weight;
+        }
+        gain *= candidate.multiplier;
+        if (gain > .05 && (!best || gain > best->gain)) best = BotSupplyChoice{gain,candidate.tile};
+    }
+    return best;
+}
+
+}
diff --git a/H5_CPP/PROJECT_MAP.md b/H5_CPP/PROJECT_MAP.md
new file mode 100644
index 0000000..e49a367
--- /dev/null
+++ b/H5_CPP/PROJECT_MAP.md
@@ -0,0 +1,182 @@
+# PROJECT_MAP — карта исходников HOI5 (C++)
+
+> **Назначение:** быстрый поиск места в коде, а не описание каждой формулы. Составлено по **42 переданным файлам**. Обозначение `main.cpp:3303` — строка в загруженной версии (может сместиться после правок); имена символов надёжнее номеров строк. Все перечисленные пути — имена переданных файлов; в репозитории C++-часть, судя по `port_progress.py`, называется `H5_CPP/`.
+
+## 1. Архитектура за 30 секунд
+
+- **`main.cpp` — центральный узел** (≈11 тыс. строк): типы `Tile`, `Division`, `World`; генерация и состояние мира, связь подсистем, наземные/воздушные боевые расчёты, AI снабжения; SFML-отрисовка, интерфейс, управление, тестовые режимы и `main()`.
+- **`World` (`main.cpp:276`) хранит** `tiles`, `divisions`, `armies`, `profiles`, `stockpiles`, `capacities`, `production`, `treasury`, `market`, `diplomacy`, `air`, `construction`, `battles`, `news`. **`World::advance()` (`main.cpp:3303`)** согласует все обновления.
+- **`SimulationClock`** (`simulation_clock.hpp`) переводит кадры в игровые часы и инициирует недельные торговые циклы. Из игрового цикла `main.cpp:7382–7410` вызывается `world.advance(...)`.
+- **`generateWorld()` (`main.cpp:3451`)** соединяет генератор рельефа, страны, стартовые здания/ресурсы, экономику, армии и авиацию. `WorldGenerator` в `world_generation.hpp` генерирует **местность**, а не весь игровой мир.
+- **Механики преимущественно вынесены в `.hpp`**, но правила движения, фронтов, наземных боёв, выбора воздушных целей и пользовательские панели по-прежнему находятся в `main.cpp`.
+
+```text
+main() / SFML-цикл (main.cpp)
+  ├─ SimulationClock::update() ──> World::advance(hours)
+  │   ├─ Diplomacy + политика + News
+  │   ├─ Market (раз в неделю) + Treasury + Production + Storage
+  │   ├─ Construction + Population + Supply + пересчёт экономики
+  │   ├─ Divisions/Fronts/Training + Ground battles
+  │   ├─ AirLayer/Air missions/ПВО + полевые вертолётные площадки
+  │   └─ Боты снабжения + уведомления
+  └─ Обработка SFML-событий + карта + панели + музыка + профилировщик
+```
+
+## 2. Все файлы по подсистемам
+
+### Карта, генерация и начальные условия
+
+| Файл | Что искать |
+| --- | --- |
+| `world_generation.hpp` | `Terrain`, `WorldGenerator::generate()` — шумовая генерация высот, влажности, температуры, покровов, озёр. |
+| `map_data.hpp` | `biome()`, `terrainMovementCost()`, `groundTerrainEffects()`, `generateDeposits()` — биомы, стоимость движения, эффекты рельефа в бою, месторождения. |
+| `terrain_color.hpp` | `terrainColor()` — цвета типов поверхности. |
+| `country_names.hpp` | `countryNames`, `rulerNames`, `countryIdentities(seed)` — названия/лидеры государств. |
+| `starting_infrastructure.hpp` | `StartingProfile`, `placeStartingCities()`, `placeStartingBuildings()`, `distributeStartingPopulation()` — стартовые города, здания, расселение. |
+| `starting_economy.hpp` | `Stockpile`, `startingStockpile()`, `compensateStartingResources()` — начальные запасы и их балансировка. |
+| `reference-map.txt` | Исходный текстовый сценарий/контрольная карта: размеры, столица, статусы, гексы, дивизии. Читается конструктором `World(path)` (`main.cpp:329`); **не исходник C++**. |
+
+### Экономика, население и строительство
+
+| Файл | Что искать |
+| --- | --- |
+| `supply.hpp` | `Building`, `BuildingCoverage`, `recalculateSupply()` — типы сооружений и распространение снабжения по гексам. |
+| `storage.hpp` | `storageBucket()`, `storageCapacity()`, `tileStorageCapacity()`, `enforceStorageCapacity()`, `freeStorage()` — вместимость и ограничения складов. |
+| `production_data.hpp` | `ProductionStage`, `ProductionFlows`, `Recipe`, `recipes`, `sectors`, `lifeSupport` — рецепты и структура производства. |
+| `production.hpp` | `industryAllocation()`, `assignStartingIndustry()`, `buildProduction()`, `runProduction()` — размещение отраслей, производство и расход сырья. |
+| `market_data.hpp` | `TRADE_BASE_PRICES`, `MARKET_RESOURCE_RARITY`, коэффициенты цен, `linkedPrices` — справочники мирового рынка. |
+| `market_clearing.hpp` | `MarketOrder`, `MarketFill`, `MarketPlan`, `clearMarket()` — алгоритм сведения заявок и исполнения сделок. |
+| `market.hpp` | `Market`, `changeContract()`, `updatePrices()`, `monthlyCapacity()`, `execute()` — торговые контракты, цены, торговая пропускная способность, исполнение. |
+| `treasury_data.hpp` | Ставки доходов населения/компаний и расходы на содержание инфраструктуры. |
+| `treasury.hpp` | `TreasuryFlows`, `monthlyTreasury()` — доходы, расходы, бюджетный баланс. |
+| `population.hpp` | `populationCapacity()`, `populationGrowthMultiplier()`, `runPopulationMonth()` — вместимость гексов и месячная демография. |
+| `construction_data.hpp` | `ConstructionSpec`, `constructionSpecs` — стоимость/ресурсы/трудоёмкость построек. |
+| `construction.hpp` | `ConstructionProject`, `ConstructionStatus`, `Construction::{enqueue,cancel,advance,placementBlock,damageBuilding}` — очередь, ограничения площадки, стройка и ремонт. |
+
+### Политика, дипломатия, новости
+
+| Файл | Что искать |
+| --- | --- |
+| `diplomacy.hpp` | `CountryPolitics`, `Relation`, `ForeignAction`, `Diplomacy::{act,resolve,advance,changeTax,changeProgram,serviceLoans}` — страны, договоры, войны, налоги, программы, займы, фракции. |
+| `world_news_data.hpp` | `NewsPriority`, `WorldNewsTemplate`, `worldNewsTemplates` — справочник мировых новостных сюжетов. |
+| `news.hpp` | `News`, `NewsItem`, `report()`, `alert()`, `advance()`, `recordTrade()`, `recordBattleLoss()`, `startLog()` — генерация событий, предупреждения, журнал. |
+| `news_panel.hpp` | `NewsPanel::{update,click,scroll,draw,openItem}` — лента, архив, всплывающие окна новостей **в интерфейсе SFML**. |
+
+### Армия, авиация и AI
+
+| Файл | Что искать |
+| --- | --- |
+| `combat.hpp` | `CombatStats`, `Battle`, `combatDamage()` — параметры сухопутного боя и формула урона; **проведение боя — в `World`**. |
+| `division_data.hpp` | `DivisionTemplate`, `divisionTemplates`, `DivisionComposition`, `composeDivision()`, `SavedDivisionDesign`, константы потерь снабжения — состав и шаблоны дивизий. |
+| `air_data.hpp` | `AirRisk`, `AircraftType`, `aircraftTypes`, `FighterInterceptor`, `DefenseClass`, `defenseClasses` — типы самолётов, перехватчиков и ПВО. |
+| `air_layer.hpp` | `Airbase`, `AirWing`, `AirDefense`, `AirLayer` — хранение авиакрыльев/баз/ПВО; `createWing()`, `rebaseWing()`, `transferAircraft()`, `replenishDefenseAmmo()`, `advanceDefenseReplacements()`. |
+| `munition_data.hpp` | `Munition`, `munitions`, `aircraftMunitions`, твёрдость/ценность зданий, профили перехвата — параметры авиационного вооружения. |
+| `air_missions.hpp` | `AirSalvo`, `AircraftInterceptorSalvo`, `missionWeapon()`, `airMissionLaunchDistance()`, `fighterSalvoInterceptChance()`, `buildingDamage()` — расчёты воздушных вылетов, попаданий и перехвата. |
+| `ai_supply.hpp` | `BotSupplyPoint`, `BotSupplyCandidate`, `bestBotSupplySite()` — выбор гекса для улучшения снабжения ботом. Вызов/исполнение — `World::updateBots()`. |
+
+### Инфраструктура приложения и портирование
+
+| Файл | Что искать |
+| --- | --- |
+| `main.cpp` | **Главный файл приложения**: подробно разобран в §3. |
+| `simulation_clock.hpp` | `SimulationClock::{update,setSpeed,togglePause}` — скорость, пауза, расчёт игровых часов и календарь рынка. |
+| `settings.hpp` | `Settings`, `SettingsFiles`, `loadSettings()`, `saveSettings()` — пути и чтение/запись настроек. |
+| `music.hpp` | `DynamicMusic::{newWorld,category,update,setVolume}` — фоновая музыка по игровым ситуациям через SFML Audio. |
+| `debug_profiler.hpp` | `DebugProfiler`, `DebugMeasure`, `debugRows` — замеры FPS и стоимости подсистем. |
+| `python_seed.hpp` | `PythonSeed`, `PythonRandom` — совместимое с Python воспроизведение последовательностей псевдослучайных чисел для отдельных алгоритмов/проверок. |
+| `format_amount.hpp` | `formatAmount()` — компактная запись чисел (`K`, `M` и т. д.). |
+| `resource_descriptions.hpp` | `resourceUsageDescription()` — текстовые описания применения ресурсов в интерфейсе. |
+| `copy_resources.cmake` | Копирование каталогов `assets` и `music` к исполняемому файлу; **не основной конфигурационный `CMakeLists.txt`**. |
+| `PORT_PROGRESS.md` | Правила аудита переноса Python → C++. |
+| `port_progress.tsv` | Построчный реестр символов Python, статусов, C++-соответствий и доказательств. |
+| `port_progress.py` | Проверка актуальности реестра и `--sync` по Python-коду из `H5_Python/`; нужны оригинальные исходники и git-окружение. |
+
+## 3. Главные ориентиры внутри `main.cpp`
+
+### Игровой мир и вычисления (строки 165–3430)
+
+| Диапазон / символ | Назначение |
+| --- | --- |
+| `165–325`: `Tile`, `Division`, `World` | Данные гексов, дивизий, всех игровых подсистем. `Division::{consume,loseStrength,attackSupplies}`: снабжение и потери. |
+| `329`: `World(path)` | Загрузка `reference-map.txt`. |
+| `363–508`: `propagateWaterOwnership`, `landRoute`, `orderMove`, `orderAirDefenseMove`, `advanceAirDefense` | Владение морскими клетками, поиск пути по шестиугольникам, марши войск и ПВО. |
+| `528–641`: `taxedTreasury`, `powerRanking`, `forecastMarketPlan`, `executeWeeklyMarket` | Налоги, рейтинг мощи, прогноз и проведение торговли. |
+| `644–958`: `advanceWorldNews`, `performForeignAction`, `answerForeignOffer`, `advancePoliticsHours`, `changeTax`, `changeSupportProgram`, `reportCountryAlerts` | Дипломатические действия, политические решения, новостные предупреждения. |
+| `961–1195`: `updateEconomyHistory`, `refreshLivingConditions`, `rebuildEconomy`, `supplyRatio`, `forecastResources` | История бюджета, благосостояние, пересборка экономики/складов, снабжение и прогноз ресурсов. |
+| `1196–1375`: `replenish`, `train`, `cancelTraining`, `updateTraining` | Пополнение дивизий и обучение. |
+| `1376–2006`: `rebalanceBattle`, `createArmy`, `setArmyFront`, `distributeArmyFront`, `executeArmyOffensive`, `updateArmyFronts` | Состав участников боя, армии, автоматические фронты, наступления. |
+| `2007–2322`: `joinBattle`, `transferTile`, `battleCollateral`, `tickBattles`, `advanceBattles` | Наземные столкновения, захват гексов, побочный урон сооружениям. |
+| `2323–2636`: `updateFieldHelipads`, `assignAirWingTarget`, `selectStrategicTarget`, `selectCasTarget`, `launchAirMission` | Полевые площадки, выбор целей авиации, запуск миссий. |
+| `2637–3133`: `resolveAirImpact`, `interceptAircraft`, `groundAircraftHitChance`, `resolveGroundSalvoDefense`, `updateAir` | Поражение зданий/войск с воздуха, ПВО, перехваты, воздушная симуляция. |
+| `3134–3302`: `updateDivisions`, `startBots`, `planBotSupply`, `updateBots` | Перемещение дивизий и бот по снабжению. |
+| **`3303–3428`: `World::advance`, `updateVisualMotion`** | **Центральная последовательность обновления мира** + сглаживание перемещения. |
+
+### Генерация, карта, отрисовка (строки 3432–4379)
+
+| Диапазон / символ | Назначение |
+| --- | --- |
+| `3435–3450`: `center`, `tileAtWorldPosition` | Преобразование координат гекса ↔ пиксели; выбор гекса мышью. |
+| **`3451–3588`: `generateWorld`** | **Создание новой партии:** рельеф → страны → инфраструктура → население → запасы/дивизии → экономика. |
+| `3590–3775`: `drawDivisionRoute`, `divisionCounters` | Путь подразделений, счётчики и группировка значков на карте. |
+| `3776–3919`: `wingAreaSummary`, `drawWingAreaOverlay`, `drawDefenseRanges`, `drawDefenseIcon` | Визуализация авиации и ПВО. |
+| `3920–4077`: `MapLayer`, `mapLayerColor`, `makeMap`, `supplyColor` | Слои карты: рельеф, политика, высота, климат, ресурсы, снабжение. |
+| `4078–4203`: `resourceCategoryKeys`, `resourceDurationLabel`, `mapResourceAmount`, `constructionOverlayColor` | Карта ресурсов, прогноз истощения, подсветка стройплощадок. |
+| `4204–4379`: `makeBorders`, `box`, `label`, `battleLabel`, `drawBudgetSummary`, `drawPopulationSummary` | Границы карты и базовые SFML-компоненты интерфейса. |
+
+### `main()` — запуск, тесты, ввод и панели (строки 4380–11083)
+
+| Диапазон | Назначение |
+| --- | --- |
+| `4380–5720` | `main(argc, argv)`, загрузка эталонной карты; **встроенные CLI-проверки** `--check-*` (экономика, бой, маршруты, авиация, настройки и др.). |
+| `5721–5782` | Флаги интеграционных/визуальных тестов `--smoke-*`, `--inspect-*` и подготовка мира. |
+| `5783–5900` | Настройки, окно SFML, шрифты, загрузка `assets/ui_icons`, `assets/tile_visuals`, музыка. |
+| `5900–6336` | Состояния UI, вспомогательные лямбды: выбор дивизий, авиации и фронтов, открытие дипломатии, работа с решениями; `startGame()` около `6295`. |
+| **`6337–7379`** | **Главный цикл и обработка событий:** клавиатура/мышь, управление картой, фронтами, панелями, строительством, дипломатией. |
+| **`7380–7410`** | **Такт симуляции:** `SimulationClock::update(...)` → `world.advance(...)` + обновление истории экономики. |
+| `7411–~8700` | Карта, слои, отрисовка гексов/дивизий/авиации, контекстные и авиационные панели. |
+| `~8700–8816` | Экономическая панель/бюджет. |
+| `8817–9002` | Панель ресурсов. |
+| `9003–9291` | Панель армии: обзор, конструктор дивизий, набор. |
+| `9292–9408` | Панель строительства и очереди. |
+| `9409–9783` | Список стран, политика, социальные показатели, дипломатические вкладки. |
+| `9784–10111` | Панель торговых контрактов. |
+| `10112–10717` | Вспомогательные панели, подробные карточки страны, налогов, программ, решений. |
+| `10718–10881` | Верхняя полоса, подсказки, предупреждения, профилировщик, музыка, вывод кадра. |
+| `10882–11083` | Сценарии автоматического нажатия кнопок для smoke-тестов интерфейса. |
+
+## 4. Быстрая навигация: «хочу изменить X»
+
+| Задача | Начать с |
+| --- | --- |
+| Частота тиков, скорость игры, пауза | `simulation_clock.hpp` → `SimulationClock::update`; вызов `main.cpp:7385`. |
+| Новый ресурс, его цена и текст | `market_data.hpp` → `TRADE_BASE_PRICES`; `production_data.hpp`/`resource_descriptions.hpp`; перевод имени — `main.cpp:106`. |
+| Логика производства/нехватки | `production.hpp` → `runProduction`; `main.cpp:3321`. |
+| Новые сделки, спрос/предложение, ценообразование | `market.hpp` → `execute`, `updatePrices`; `market_clearing.hpp` → `clearMarket`; `main.cpp:619`. |
+| Доходы, расходы, налоги, кредиты | `treasury.hpp`, `treasury_data.hpp`, `diplomacy.hpp`; интеграция `main.cpp:528,766`. |
+| Строить или ремонтировать здание | `construction_data.hpp`, `construction.hpp` → `enqueue/advance`; интеграция `main.cpp:3344`; UI `~9292`. |
+| Пересчитать снабжение и складские лимиты | `supply.hpp` → `recalculateSupply`; `storage.hpp`; `main.cpp:1045`. |
+| Прирост населения, продукты, потребтовары | `population.hpp`; `main.cpp:977,3360`. |
+| Генерация карты/месторождений/стартовых стран | `world_generation.hpp`, `map_data.hpp`, `starting_infrastructure.hpp`, `main.cpp:3451`. |
+| Цвета, отображение гексов, выбор мышью | `terrain_color.hpp`; `main.cpp:3435,3978,4032`. |
+| Поиск пути, скорость марша, маршруты | `main.cpp:419` (`landRoute`), `460` (`orderMove`), `3134` (`updateDivisions`); рельеф `map_data.hpp`. |
+| Новые шаблоны дивизий, набор, снабжение | `division_data.hpp`; `main.cpp:178,1196,1276,1321`. |
+| Боевой урон, ширина фронта, потери, захват | `combat.hpp` → `combatDamage`; `main.cpp:1392,2007,2136,2054`. |
+| Автоматические армии и линии фронта | `main.cpp:1473–2006`, прежде всего `distributeArmyFront`, `executeArmyOffensive`. |
+| Самолёты, создание крыла и перебазирование | `air_data.hpp`, `air_layer.hpp` → `createWing/rebaseWing`; UI `main.cpp:6978+,8532+`. |
+| Авиаудары, CAS, выбор цели, перехват/ПВО | `air_missions.hpp`, `munition_data.hpp`; `main.cpp:2444–3133`. |
+| Строительство/перемещение ПВО и пополнение БК | `air_layer.hpp`; `main.cpp:490–525,3378+`. |
+| Внешняя политика, договоры, войны, фракции | `diplomacy.hpp`; `main.cpp:659–857`; UI `~9409+`. |
+| События, предупреждения, лента новостей | `news.hpp`, `world_news_data.hpp`, `news_panel.hpp`; `main.cpp:644,913`. |
+| Музыка, громкость, настройки | `music.hpp`, `settings.hpp`; `main.cpp:5783+,10795+`. |
+| Найти узкое место по производительности | `debug_profiler.hpp`; именованные `DebugMeasure` и `debug.record` в `main.cpp`. |
+| Проверить соответствие версии Python | `PORT_PROGRESS.md` → `port_progress.tsv` → `port_progress.py`; локальные `--check-*` в `main.cpp:4380+`. |
+
+## 5. Важные зависимости и оговорки
+
+1. **Не путать данные и действие:** характеристики дивизии — `division_data.hpp`, вычисление урона — `combat.hpp`, **сам ход битвы** — `World::tickBattles`; характеристики самолёта — `air_data.hpp`, **выполнение вылета** — `World::updateAir`.
+2. **Изменение здания влияет сразу на несколько систем:** `supply.hpp`/`construction_data.hpp` → `construction.hpp` → `World::advance` → `recalculateSupply` + `World::rebuildEconomy`; также могут затрагиваться складские лимиты, выпуск продукции, бюджет, авиабазы.
+3. **`main.cpp` сильно связан с заголовками:** общие `Tile`, `Division`, `World` определены прямо там; часть `.hpp` опирается на типы игрового мира. При выносе кода нужно учитывать порядок объявлений/подключений.
+4. **Встроенные тесты не являются доказательством полной эквивалентности Python:** `port_progress.tsv` отмечает символы `ported`, `partial`, `missing`, `unreviewed`, а также исключённые инструменты/ботов. Реестр требует отдельного аудита.
+5. **Ограничение комплекта:** получены 42 файла, **не** загружены исходники `H5_Python/`, основные файлы сборки (`CMakeLists.txt`), каталоги `assets/` и `music/`. Поэтому карта покрывает **полученные файлы**, а не гарантированно весь репозиторий или работоспособность сборки.
+
+**Практика для Codex:** сначала найди строку в §4 → открой указанный символ → посмотри вызывающую функцию в `World::advance()` или обработчик `main()`; правя баланс, проверяй соответствующие `--check-*` и статусы портирования.
<!-- END_HOI5_PATCH -->
