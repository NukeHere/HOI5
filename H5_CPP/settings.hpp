#pragma once

#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iterator>
#include <locale>
#include <regex>
#include <sstream>

namespace hoi5 {

struct Settings {
    float soundVolume = 80, musicVolume = 60;
    bool fullscreen = false;
    int resolution = 1;
};

inline std::filesystem::path settingsFile(const std::filesystem::path& executableDirectory) {
#ifdef _WIN32
    if (const auto* local = _wgetenv(L"LOCALAPPDATA"); local && *local)
        return std::filesystem::path(local) / "HOI5" / "user_settings.json";
#endif
    return executableDirectory / "user_settings.json";
}

inline Settings loadSettings(const std::filesystem::path& path,int resolutionCount) {
    Settings result;
    std::ifstream input(path);
    const std::string json{std::istreambuf_iterator<char>(input),{}};
    const auto begin = json.find_first_not_of(" \t\r\n");
    const auto end = json.find_last_not_of(" \t\r\n");
    if (begin == std::string::npos || json[begin] != '{' || json[end] != '}') return result;
    const auto field = [&](const char* key) {
        const std::regex expression(std::string("\"")+key+"\"\\s*:\\s*([^,}\\s]+)\\s*[,}]");
        std::smatch match;
        return std::regex_search(json,match,expression) ? match[1].str() : std::string{};
    };
    const auto number = [&](const char* key,double fallback) {
        const auto value = field(key);
        std::istringstream stream(value);
        stream.imbue(std::locale::classic());
        double parsed;
        return stream >> parsed && stream.eof() && std::isfinite(parsed) ? parsed : fallback;
    };
    result.soundVolume = float(100*std::clamp(number("sound_volume",.8),0.,1.));
    result.musicVolume = float(100*std::clamp(number("music_volume",.6),0.,1.));
    result.fullscreen = field("fullscreen") == "true";
    result.resolution = int(std::clamp(number("resolution_index",1.),0.,double(resolutionCount-1)));
    return result;
}

inline bool saveSettings(const std::filesystem::path& path,const Settings& settings) {
    std::error_code error;
    if (path.has_parent_path()) {
        std::filesystem::create_directories(path.parent_path(),error);
        if (error) return false;
    }
    auto temporary = path;
    temporary += ".tmp";
    std::ofstream output(temporary,std::ios::trunc);
    output.imbue(std::locale::classic());
    output << "{\n  \"sound_volume\": " << settings.soundVolume/100.
           << ",\n  \"music_volume\": " << settings.musicVolume/100.
           << ",\n  \"fullscreen\": " << std::boolalpha << settings.fullscreen
           << ",\n  \"resolution_index\": " << settings.resolution << "\n}\n";
    output.close();
    if (output) {
        std::filesystem::rename(temporary,path,error);
        if (!error) return true;
    }
    std::filesystem::remove(temporary,error);
    return false;
}

}
