#pragma once

#include "market_clearing.hpp"
#include "format_amount.hpp"
#include "python_seed.hpp"
#include "world_news_data.hpp"
#include <chrono>
#include <deque>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <random>
#include <span>
#include <string>

namespace hoi5 {

struct NewsItem {
    int day, viewer;
    NewsPriority priority;
    std::string title, body;
    int id{};
    std::string key;
    int otherViewer = -1;

    bool important() const { return priority >= NewsPriority::important; }
    bool visibleTo(int country) const { return viewer < 0 || viewer == country || otherViewer == country; }
};

struct WorldNewsContext {
    double oilPressure = 1.;
    bool majorOilExporterRestricted = false;
};

class News {
    struct NoticeBatch {
        int day, country;
        std::string_view key;
        std::string title;
        bool important;
        int quantity{};
        std::vector<std::pair<std::string,int>> details;
        int count{};
    };
    Stockpile tradeRecords;
    std::map<std::string_view,int> lastTradeDay;
    struct BattleLoss { double accumulated{}; int lastDay = -1000; };
    std::map<std::pair<int,int>,BattleLoss> battleLosses;
    std::map<std::tuple<int,int,std::string_view>,int> lastLogisticsDay;
    std::map<std::pair<int,std::string>,bool> alerts;
    std::deque<NewsItem> items;
    int nextId = 1;
    int lastDailyDay = 0;
    std::map<std::string_view,int> lastTemplateDay;
    std::mt19937 rng;
    std::vector<NoticeBatch> pendingNotices;
    std::uint64_t worldSeed;
    std::filesystem::path logPath;
    bool logFailed{};

    static void writeLogDate(std::ostream& out,int day) {
        using namespace std::chrono;
        const year_month_day date{sys_days{year{2000}/1/1}+days{day}};
        out << int(date.year()) << '-' << std::setfill('0') << std::setw(2) << unsigned(date.month())
            << '-' << std::setw(2) << unsigned(date.day());
    }

    void reportLogError(std::string_view message) {
        logFailed = true;
        std::cerr << message << ": " << logPath << '\n';
    }

    void logItem(const NewsItem& item) {
        if (logPath.empty() || logFailed) return;
        std::ofstream stream(logPath,std::ios::app);
        constexpr std::array priorities{"flavor","regular","important","critical"};
        stream << '[';
        writeLogDate(stream,item.day);
        stream << "] #" << item.id << " [" << priorities[static_cast<int>(item.priority)] << "] [";
        if (item.viewer < 0) stream << "мир";
        else {
            stream << "страны " << item.viewer;
            if (item.otherViewer >= 0 && item.otherViewer != item.viewer) stream << ", " << item.otherViewer;
        }
        stream << "] " << item.key << '\n' << item.title << '\n' << item.body << "\n\n";
        stream.close();
        if (!stream) reportLogError("Не удалось записать новость");
    }

    void publish(NewsItem item) {
        item.id = nextId++;
        items.push_front(std::move(item));
        if (items.size() > 300) items.pop_back();
        logItem(items.front());
    }

public:
    explicit News(std::uint64_t seed = 0) : worldSeed(seed) {
        PythonSeed pythonSeed{seed};
        rng.seed(pythonSeed);
    }

    void startLog(const std::filesystem::path& path,std::span<const std::string_view> countries,
                  std::span<const std::string_view> rulers) {
        logPath = path;
        logFailed = false;
        std::error_code error;
        if (!path.parent_path().empty()) std::filesystem::create_directories(path.parent_path(),error);
        if (error) {
            reportLogError("Не удалось создать каталог журнала новостей");
            return;
        }
        std::ofstream stream(logPath);
        stream << "HOI5 — история новостей новой партии\nСид: " << worldSeed << "\nНачало: ";
        writeLogDate(stream,0);
        stream << '\n';
        for (std::size_t i = 0; i < countries.size(); ++i)
            stream << "Страна " << i << ": " << countries[i] << "; правитель: "
                   << (i < rulers.size() && !rulers[i].empty() ? rulers[i] : "не указан") << '\n';
        stream << '\n';
        stream.close();
        if (!stream) reportLogError("Не удалось создать журнал новостей");
    }

    int report(int day,std::string_view key,std::string title,std::string body,
                NewsPriority priority = NewsPriority::regular,int viewer = -1,int otherViewer = -1) {
        publish({day,viewer,priority,std::move(title),std::move(body),0,std::string(key),otherViewer});
        return items.front().id;
    }

    void updateBody(int id,std::string body) {
        const auto item = std::ranges::find(items,id,&NewsItem::id);
        if (item != items.end()) item->body = std::move(body);
    }

    void batchNotice(int day,int country,std::string_view key,std::string title,std::string body,
                     bool important = false,int quantity = 1) {
        auto batch = std::ranges::find_if(pendingNotices,[&](const auto& entry) {
            return entry.day == day && entry.country == country && entry.key == key;
        });
        if (batch == pendingNotices.end()) {
            pendingNotices.push_back({day,country,key,std::move(title),important});
            batch = std::prev(pendingNotices.end());
        }
        ++batch->count;
        batch->quantity += quantity;
        batch->important |= important;
        auto detail = std::ranges::find(batch->details,body,&std::pair<std::string,int>::first);
        if (detail == batch->details.end()) batch->details.emplace_back(std::move(body),1);
        else ++detail->second;
    }

    void flushNotices() {
        for (auto& batch : pendingNotices) {
            if (batch.count > 1) {
                if (batch.key == "construction_complete") batch.title = "Завершены строительные и ремонтные работы";
                batch.title += " ("+std::to_string(batch.quantity)+")";
            }
            std::string body;
            for (const auto& [detail,count] : batch.details) {
                if (!body.empty()) body += '\n';
                body += detail;
                if (count > 1) body += " ×"+std::to_string(count);
            }
            report(batch.day,batch.key,std::move(batch.title),std::move(body),
                batch.important ? NewsPriority::important : NewsPriority::regular,batch.country);
        }
        pendingNotices.clear();
    }

    void advance(int day,WorldNewsContext context) {
        for (int current = lastDailyDay+1; current <= day; ++current) {
            for (const auto& event : worldNewsTemplates) {
                const auto last = lastTemplateDay.find(event.key);
                if (last != lastTemplateDay.end() && current-last->second < event.cooldown) continue;
                double chance = event.dailyChance;
                if (event.key == "oil_crisis") {
                    chance += std::min(.015,std::max(0.,context.oilPressure-1.)*.015);
                    if (context.majorOilExporterRestricted) chance += .025;
                }
                const auto high = rng() >> 5;
                const auto low = rng() >> 6;
                const double draw = (high*67108864. + low)/9007199254740992.;
                if (draw >= std::min(1.,chance)) continue;
                std::string body(event.body);
                if (event.key == "oil_crisis") {
                    if (context.majorOilExporterRestricted)
                        body += " Дополнительную тревогу вызвали ограничения поставок крупным экспортёром.";
                    else if (context.oilPressure > 1.25)
                        body += " Последний обзор рынка показал заметный перевес спроса над предложением.";
                }
                lastTemplateDay[event.key] = current;
                report(current,event.key,std::string(event.title),std::move(body),event.priority);
            }
        }
        lastDailyDay = std::max(lastDailyDay,day);
    }

    std::vector<const NewsItem*> visible(int viewer) const {
        std::vector<const NewsItem*> result;
        for (const auto& item : items)
            if (item.visibleTo(viewer)) result.push_back(&item);
        return result;
    }

    const NewsItem* latest(int viewer) const {
        for (const auto& item : items)
            if (item.visibleTo(viewer)) return &item;
        return nullptr;
    }

    const NewsItem* latestImportant(int viewer,std::string_view key,int minDay) const {
        for (const auto& item : items)
            if (item.key == key && item.day >= minDay && item.important() && item.visibleTo(viewer)) return &item;
        return nullptr;
    }

    template<class CountryName,class ResourceName>
    void recordTrade(int day,const MarketFill& fill,CountryName countryName,ResourceName resourceName) {
        if (!fill.buyer || !fill.seller || fill.buyer == fill.seller) return;
        const double value = std::max(0.,fill.amount*fill.price);
        auto& record = tradeRecords[fill.resource];
        const double previous = record;
        record = std::max(previous,value);
        if (value < 5000000. || (previous > 0 && value < previous*1.25)) return;
        const auto last = lastTradeDay.find(fill.resource);
        if (last != lastTradeDay.end() && day-last->second < 180) return;
        lastTradeDay[fill.resource] = day;
        publish({day,-1,NewsPriority::important,"Крупная сделка: "+std::string(resourceName(fill.resource)),
            std::string(countryName(*fill.seller))+" поставляет "+std::string(countryName(*fill.buyer))+
            " "+formatAmount(fill.amount)+" ед. товара. Стоимость сделки — $"+formatAmount(value)+".",0,"large_trade"});
    }

    void alert(int day,int country,std::string_view name,std::string_view key,bool active,
               std::string title,std::string body,std::string recovery) {
        auto& state = alerts[{country,std::string(key)}];
        if (active == state) return;
        state = active;
        if (active) report(day,key,std::move(title),std::move(body),NewsPriority::important,country);
        else report(day,key,recovery,std::string(name)+": "+recovery+".",NewsPriority::regular,country);
    }

    void reportIncompleteTrade(int day,int country,std::string_view name,std::string missing) {
        alert(day,country,name,"trade_incomplete",!missing.empty(),"Торговые заявки исполнены не полностью",
            "Последние недельные поставки ниже заявленных: "+missing+
            ". Проверьте доступ к рынку, лимиты, бюджет, склады и встречные заявки.",
            "Торговые заявки снова исполняются полностью");
    }

    void recordBattleLoss(int day,int battle,int side,int country,std::string_view name,
                          std::string_view opponent,double loss) {
        if (country < 0 || loss <= 0) return;
        auto& record = battleLosses[{battle,side}];
        record.accumulated += loss;
        if (record.accumulated < 12 || day-record.lastDay < 30) return;
        record = {0.,day};
        report(day,"battle_losses","Тяжёлые потери на фронте с "+std::string(opponent),
            "Военное командование "+std::string(name)+" сообщает о серьёзных потерях боеспособности соединений "
            "в боях против "+std::string(opponent)+". Оценка положения на фронте продолжается; "
            "точные людские потери пока не установлены.",NewsPriority::important,country);
    }

    void recordLogisticsDamage(int day,int country,std::string_view name,int q,int r,int tile,
                               std::string_view building,double before,double after) {
        if (country < 0 || building.empty() || before <= .5 || after > .5) return;
        const auto key = std::tuple{country,tile,building};
        const auto last = lastLogisticsDay.find(key);
        if (last != lastLogisticsDay.end() && day-last->second < 45) return;
        lastLogisticsDay[key] = day;
        report(day,"logistics_damage","Повреждён "+std::string(building),
            "В стране "+std::string(name)+" серьёзно повреждён "+std::string(building)+" на участке ("+
            std::to_string(q)+", "+std::to_string(r)+"). Объект работает с ограничениями; службы оценивают ущерб и готовят ремонт.",
            NewsPriority::important,country);
    }
};

}
