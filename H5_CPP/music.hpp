#pragma once

#include <SFML/Audio/Music.hpp>
#include <algorithm>
#include <array>
#include <filesystem>
#include <iostream>
#include <random>
#include <set>
#include <tuple>
#include <vector>

namespace hoi5 {

enum MusicCategory { economyMusic, openingMusic, crisisMusic, warMusic };

class DynamicMusic {
    using Path = std::filesystem::path;
    using War = std::tuple<int,int,int>;
    std::array<std::vector<Path>,4> tracks, bags;
    std::set<Path> failed;
    std::set<War> seenWars, pendingWars;
    std::mt19937 random{std::random_device{}()};
    sf::Music music;
    Path current;
    float volume = 60;
    int peakTerritory{}, lastBattleCount{}, lastEscalation = -30, escalationUntil = -1;
    bool pendingEscalation{};

    static std::wstring foldedName(const Path& path) {
        auto name = path.filename().wstring();
        for (auto& c : name) if (c >= L'A' && c <= L'Z') c += L'a'-L'A';
        return name;
    }

public:
    explicit DynamicMusic(const Path& directory) {
        const std::array names{"economy","start_war","bad_times","war"};
        for (std::size_t i = 0; i < names.size(); ++i) {
            std::error_code error;
            for (const auto& file : std::filesystem::directory_iterator(directory/names[i],error)) {
                if (!file.is_regular_file(error)) continue;
                const auto ext = foldedName(file.path().extension());
                if (ext == L".ogg" || ext == L".mp3" || ext == L".wav" || ext == L".flac")
                    tracks[i].push_back(file.path());
            }
            std::sort(tracks[i].begin(),tracks[i].end());
            if (tracks[i].empty()) std::cerr << "[audio] No music tracks found in " << directory/names[i] << '\n';
        }
    }

    void setVolume(float value) { volume = value; music.setVolume(volume); }

    void newWorld() {
        seenWars.clear();
        pendingWars.clear();
        peakTerritory = lastBattleCount = 0;
        lastEscalation = -30;
        escalationUntil = -1;
        pendingEscalation = false;
    }

    template<class World>
    MusicCategory category(const World& world) {
        if (world.diplomacy.countries.empty()) return economyMusic;
        const auto& diplomacy = world.diplomacy;
        std::set<War> wars;
        for (const auto& [pair,relation] : diplomacy.relations)
            if (relation.war && (pair.first == 0 || pair.second == 0))
                wars.emplace(pair.first,pair.second,relation.warStarted);
        std::erase_if(pendingWars,[&](const auto& war) { return !wars.contains(war); });
        for (const auto& war : wars) if (!seenWars.contains(war)) pendingWars.insert(war);
        seenWars = wars;
        const bool incoming = std::any_of(diplomacy.goals.begin(),diplomacy.goals.end(),[](const auto& goal) {
            return goal.first.second == 0;
        });
        const bool opening = std::any_of(wars.begin(),wars.end(),[&](const auto& war) {
            const int days = diplomacy.day-std::get<2>(war);
            return days >= 0 && days < 30;
        });
        const int battleCount = int(std::count_if(world.battles.begin(),world.battles.end(),[](const auto& entry) {
            return entry.second.attacker == 0 || entry.second.defender == 0;
        }));
        if (wars.empty()) {
            pendingEscalation = false;
            escalationUntil = -1;
            lastEscalation = -30;
        } else if (battleCount >= std::max({3,lastBattleCount+3,lastBattleCount*2}) && diplomacy.day-lastEscalation >= 30) {
            pendingEscalation = true;
            lastEscalation = diplomacy.day;
            escalationUntil = diplomacy.day+30;
        }
        lastBattleCount = battleCount;
        const int territory = int(std::count_if(world.tiles.begin(),world.tiles.end(),[](const auto& tile) { return tile.owner == 0; }));
        peakTerritory = std::max(peakTerritory,territory);
        if (incoming || opening || !pendingWars.empty() || pendingEscalation || diplomacy.day < escalationUntil)
            return openingMusic;
        int divisions = 0, unsupplied = 0;
        for (const auto& unit : world.divisions) {
            if (unit.owner != 0 || unit.combat.strength <= 0) continue;
            ++divisions;
            unsupplied += world.supplyRatio(unit) < .3;
        }
        const bool crisis = diplomacy.countries[0].stability < .4 ||
            (world.profiles[0].budget <= 0 && world.treasury[0].balance() < 0) ||
            (divisions > 0 && unsupplied*2 >= divisions) || (!wars.empty() && territory < peakTerritory*.75);
        return crisis ? crisisMusic : wars.empty() ? economyMusic : warMusic;
    }

    void update(MusicCategory desired) {
        if (music.getStatus() != sf::SoundSource::Status::Stopped) return;
        const auto old = foldedName(current);
        for (auto category : {desired,desired == openingMusic ? warMusic : economyMusic,
                              economyMusic,openingMusic,crisisMusic,warMusic}) {
            auto& bag = bags[category];
            std::erase_if(bag,[&](const auto& path) { return failed.contains(path); });
            if (bag.empty()) {
                for (const auto& path : tracks[category])
                    if (!failed.contains(path)) bag.push_back(path);
                std::shuffle(bag.begin(),bag.end(),random);
            }
            while (!bag.empty()) {
                const auto different = std::find_if(bag.begin(),bag.end(),[&](const auto& path) { return foldedName(path) != old; });
                const auto chosen = different != bag.end() ? different : bag.begin();
                const Path path = *chosen;
                bag.erase(chosen);
                if (!music.openFromFile(path)) {
                    std::cerr << "[audio] Could not open music file: " << path << '\n';
                    failed.insert(path);
                    continue;
                }
                music.setVolume(volume);
                music.play();
                current = path;
                if (category == openingMusic) {
                    pendingWars.clear();
                    pendingEscalation = false;
                }
                return;
            }
        }
    }
};

}
