#include "../ai_scheduler.hpp"
#include <array>
#include <iostream>
#include <stdexcept>
int main() {
    const auto require=[](bool ok){if(!ok) throw std::runtime_error("AI work budget/fairness regression");};
    std::size_t cursor=0;std::array<int,20> runs{};
    for(int tick=0;tick<10;++tick) {
        auto selected=hoi5::selectBotDailyWork(20,20,2.4,cursor,[&](auto i){return runs[i]==0;});
        int count=0;for(int i=0;i<20;++i) if(selected[i]) {++count;++runs[i];}
        require(count==2);
    }
    for(auto count:runs) require(count==1);
    // All bots being urgent cannot defeat the heavy-work budget.
    for(int tick=0;tick<100;++tick) {
        auto selected=hoi5::selectBotDailyWork(20,20,2.4,cursor,[](auto){return true;});
        require(std::count(selected.begin(),selected.end(),true)==2);
    }
    cursor=19;
    auto sparse=hoi5::selectBotDailyWork(20,2,6,cursor,[](auto i){return i==3 || i==12;});
    require(sparse[3] && std::count(sparse.begin(),sparse.end(),true)==1);
    sparse=hoi5::selectBotDailyWork(20,2,6,cursor,[](auto i){return i==3 || i==12;});require(sparse[12]);
    require(hoi5::selectBotDailyWork(0,0,6,cursor,[](auto){return true;}).empty());
    std::cout<<"Simulation-time AI budget, urgent bound, rotation, sparse countries and no starvation passed\n";
}
