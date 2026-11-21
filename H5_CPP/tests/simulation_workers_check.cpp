#include "../simulation_workers.hpp"
#include <barrier>
#include <iostream>
#include <stdexcept>
int main() {
    hoi5::SimulationWorkers pool(3);
    std::barrier gate(4);
    std::vector<int> slots(128);
    pool.forEach(slots.size(),[&](std::size_t i) {
        if(i<4) gate.arrive_and_wait();
        pool.forEach(4,[&](std::size_t j){slots[i]+=int(i+j);});
    });
    for(int i=0;i<128;++i) if(slots[i]!=4*i+6) throw std::runtime_error("nested worker result");
    if(pool.peakConcurrency()!=4) throw std::runtime_error("workers did not overlap");
    bool caught=false;
    try {pool.forEach(128,[](auto i){if(i==17) throw std::runtime_error("expected");});} catch(const std::runtime_error&) {caught=true;}
    if(!caught) throw std::runtime_error("exception lost");
    pool.forEach(128,[&](auto i){slots[i]=int(i);});
    for(int i=0;i<128;++i) if(slots[i]!=i) throw std::runtime_error("recovery failed");
    std::cout<<"Four concurrent participants, nested calls, exceptions and recovery passed\n";
}
