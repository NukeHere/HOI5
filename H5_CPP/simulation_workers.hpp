#pragma once
#include <algorithm>
#include <atomic>
#include <condition_variable>
#include <cstdlib>
#include <exception>
#include <functional>
#include <mutex>
#include <thread>
#include <vector>

namespace hoi5 {
class SimulationWorkers {
    std::mutex dispatchMutex,mutex;
    std::condition_variable ready,finished;
    std::vector<std::thread> workers;
    std::function<void(std::size_t)> task;
    std::atomic<std::size_t> next{};
    std::size_t count{},generation{},remaining{};
    bool stopping{};
    std::exception_ptr error;
    std::atomic<unsigned> active{},peak{};
    inline static thread_local bool executing=false;
    void run() {
        const bool previous=executing;executing=true;
        for(;;) {
            const auto i=next.fetch_add(1,std::memory_order_relaxed);if(i>=count) break;
            const auto n=active.fetch_add(1)+1;auto old=peak.load();while(old<n && !peak.compare_exchange_weak(old,n)) {}
            try {task(i);} catch(...) {std::lock_guard lock(mutex);if(!error) error=std::current_exception();}
            --active;
        }
        executing=previous;
    }
public:
    explicit SimulationWorkers(unsigned background):workers(background) {
        for(auto& worker:workers) worker=std::thread([this] {
            std::size_t seen=0;
            for(;;) {
                {std::unique_lock lock(mutex);ready.wait(lock,[&]{return stopping || generation!=seen;});if(stopping) return;seen=generation;}
                run();
                {std::lock_guard lock(mutex);if(--remaining==0) finished.notify_one();}
            }
        });
    }
    ~SimulationWorkers() {
        {std::lock_guard lock(mutex);stopping=true;}ready.notify_all();
        for(auto& worker:workers) worker.join();
    }
    SimulationWorkers(const SimulationWorkers&)=delete;
    SimulationWorkers& operator=(const SimulationWorkers&)=delete;
    template<class Work> void forEach(std::size_t size,Work work) {
        if(workers.empty() || size<4 || executing) {for(std::size_t i=0;i<size;++i) work(i);return;}
        std::lock_guard dispatch(dispatchMutex);
        {std::lock_guard lock(mutex);task=std::move(work);count=size;next=0;remaining=workers.size();error={};++generation;}
        ready.notify_all();run();
        std::unique_lock lock(mutex);finished.wait(lock,[&]{return remaining==0;});task={};
        if(error) std::rethrow_exception(error);
    }
    unsigned backgroundCount() const {return unsigned(workers.size());}
    unsigned peakConcurrency() const {return peak.load();}
};
inline SimulationWorkers& simulationWorkers() {
    static SimulationWorkers pool([] {
        const unsigned available=std::thread::hardware_concurrency();
        unsigned count=available>2?std::min(4u,available-2):0;
        if(const char* setting=std::getenv("HOI5_WORKERS")) {
            char* end=nullptr;const long value=std::strtol(setting,&end,10);
            if(end!=setting && *end=='\0') count=unsigned(std::clamp(value,0l,8l));
        }
        return count;
    }());
    return pool;
}
}
