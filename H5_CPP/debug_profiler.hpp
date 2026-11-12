#pragma once

#include <array>
#include <chrono>
#include <map>
#include <string_view>

namespace hoi5 {

struct DebugRow { std::string_view label; std::array<std::string_view,3> keys; };
inline constexpr DebugRow debugRows[] = {
    {"Профайлер F3",{}},
    {"DRAW total",{"draw_total"}},
    {"  карта/тайлы",{"world_tiles"}},
    {"  тайловый визуал",{"world_tile_visuals"}},
    {"  границы",{"world_state_borders"}},
    {"  авиация визуал",{"world_air_assets"}},
    {"  планы армий",{"world_army_plans"}},
    {"  дивизии",{"world_divisions"}},
    {"  счётчики дивизий",{"ui_division_groups"}},
    {"  списки авиации/дивизий",{"ui_air_wing_list","ui_division_list"}},
    {"  верхний UI",{"ui_top_status","ui_top_navigation","ui_time_hud"}},
    {"  боковая/гекс панель",{"ui_side_panel","ui_hex_panel"}},
    {"    hex resources",{"hex_resources_lookup"}},
    {"    hex storage",{"hex_storage_lookup"}},
    {"    hex buildings",{"hex_buildings_lookup"}},
    {"    hex aviation",{"hex_aviation_lookup"}},
    {"    панель ресурсов",{"panel_resources"}},
    {"    панель торговли",{"panel_trade"}},
    {"      trade snapshot",{"trade_snapshot"}},
    {"      trade header",{"trade_header"}},
    {"      trade rows",{"trade_rows"}},
    {"      trade buttons",{"trade_buttons"}},
    {"    панель стройки",{"panel_construction"}},
    {"  текст UI",{"ui_text_batch"}},
    {"  сам профайлер",{"profiler_overlay"}},
    {"UPDATE total",{"update_total"}},
    {"  сервер: все шаги",{"server_steps"}},
    {"  политика",{"server_politics"}},
    {"  рынок",{"server_market"}},
    {"  экономика",{"server_economy"}},
    {"  производство",{"server_production"}},
    {"  строительство",{"server_construction"}},
    {"  пересчёт зданий",{"server_building_refresh"}},
    {"    стройка: auto repair",{"construction_auto_repairs"}},
    {"    стройка: проекты",{"construction_projects"}},
    {"    стройка: статус",{"construction_status_eval"}},
    {"    стройка: ресурсы",{"construction_consume_resources"}},
    {"  население",{"server_population"}},
    {"  дивизии логика",{"server_divisions"}},
    {"  подготовка дивизий",{"server_training"}},
    {"  наземные бои",{"server_ground_battles"}},
    {"    бой: атаки",{"battle_attack_phase"}},
    {"    бой: подкрепл./орг",{"battle_recover_reinforce"}},
    {"    бой: урон зданиям",{"battle_collateral"}},
    {"    бой: cleanup",{"battle_cleanup"}},
    {"    бой: rebalance",{"battle_rebalance"}},
    {"  полевые вертолётные площадки",{"server_field_helipads"}},
    {"  ПВО/воздушные атаки",{"server_air_defense","server_air_attack_salvos"}},
    {"  авиация логика",{"server_air_missions","server_air_salvos"}},
    {"  планы армий логика",{"server_army_plans"}},
    {"  история экономики",{"server_economy_history"}},
    {"  ИИ: всего",{"ai_total"}},
    {"    ИИ: обзоры",{"ai_reviews"}},
    {"    ИИ: суточный цикл всего",{"ai_daily"}},
    {"    ИИ: регионы/оценка сил",{"ai_regions"}},
    {"    ИИ: торговые зависимости",{"ai_dependencies"}},
    {"    ИИ: снабжение",{"ai_supply_planning"}},
    {"    ИИ: оборона/ПВО",{"ai_defense_planning"}},
    {"    ИИ: набор дивизий",{"ai_recruitment_planning"}},
    {"    ИИ: авиация",{"ai_air_planning"}},
    {"    ИИ: экономика/торговля",{"ai_economy_planning"}},
    {"    ИИ: мирная экспансия",{"ai_expansion_planning"}},
    {"    ИИ: дипломатия/политика",{"ai_diplomacy_planning"}},
    {"    ИИ: ответы на предложения",{"ai_offer_response"}},
    {"    ИИ: фронты/армии/атаки",{"ai_front_planning"}},
    {"    ИИ: микроцикл всего",{"ai_micro"}},
    {"    ИИ: выполнение задач",{"ai_tasks"}},
    {"  владение/камера/видимость",{"ownership_refresh","camera","visible_tiles_refresh"}},
    {"    владение",{"ownership_refresh"}},
    {"    камера",{"camera"}},
    {"    видимые тайлы",{"visible_tiles_refresh"}},
};

class DebugProfiler {
public:
    using Clock = std::chrono::steady_clock;
    bool visible = false;
    unsigned fps = 0;

    void frame(double seconds) {
        elapsed += seconds;
        ++frames;
        if (elapsed < .5) return;
        fps = static_cast<unsigned>(frames/elapsed+.5);
        averages.clear();
        for (const auto& [key,total] : samples) averages[key] = total/frames;
        samples.clear();
        elapsed = 0.;
        frames = 0;
    }

    void record(std::string_view key,Clock::time_point since) {
        samples[key] += std::chrono::duration<double,std::milli>(Clock::now()-since).count();
    }

    double average(const DebugRow& row) const {
        double total = 0.;
        for (auto key : row.keys) {
            const auto value = averages.find(key);
            if (value != averages.end()) total += value->second;
        }
        return total;
    }

    bool hasAverage(std::string_view key) const { return averages.contains(key); }

private:
    double elapsed{};
    unsigned frames{};
    std::map<std::string_view,double> samples, averages;
};

class DebugMeasure {
    DebugProfiler* profiler;
    std::string_view key;
    DebugProfiler::Clock::time_point start;

public:
    DebugMeasure(DebugProfiler* profiler,std::string_view key)
        : profiler(profiler),key(key),start(profiler ? DebugProfiler::Clock::now() : DebugProfiler::Clock::time_point{}) {}
    DebugMeasure(const DebugMeasure&) = delete;
    DebugMeasure& operator=(const DebugMeasure&) = delete;
    ~DebugMeasure() { if (profiler) profiler->record(key,start); }
};

}
