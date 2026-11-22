#pragma once
#include "production_data.hpp"
#include <algorithm>
#include <functional>
#include <set>

namespace hoi5 {
// Immutable recipe structure, compiled once for this registry/technology policy.
class ProductionGraph {
public:
    struct Node {
        const Recipe* recipe;
        std::vector<std::pair<std::size_t,double>> inputs,outputs;
    };
    std::map<std::string_view,std::size_t> ids;
    std::vector<std::string_view> keys;
    std::vector<Node> nodes;
    std::vector<std::size_t> order; // producers before consumers
    bool acyclic=true;
    ProductionGraph() {
        for(const auto& r:recipes) {for(auto [k,a]:r.inputs) ids.try_emplace(k);for(auto [k,a]:r.outputs) ids.try_emplace(k);}
        for(const auto* stock:{&mineWeights,&lifeSupport,&cityUpkeep,&villageUpkeep}) for(auto [k,a]:*stock) ids.try_emplace(k);
        ids.try_emplace("rubber");
        for(auto& [key,id]:ids) {id=keys.size();keys.push_back(key);}
        for(const auto& r:recipes) if(r.building==industry && r.technology.empty() && !r.outputs.empty()) {
            Node node{&r,{},{}};
            for(auto [k,a]:r.inputs) node.inputs.emplace_back(ids.at(k),a);
            for(auto [k,a]:r.outputs) node.outputs.emplace_back(ids.at(k),a);
            nodes.push_back(std::move(node));
        }
        std::vector<int> producer(keys.size(),-1),state(nodes.size());
        for(std::size_t i=0;i<nodes.size();++i) for(auto [id,a]:nodes[i].outputs) if(a>0) {
            if(producer[id]>=0) acyclic=false;else producer[id]=int(i);
        }
        const std::function<void(std::size_t)> visit=[&](std::size_t i) {
            if(state[i]==2) return;
            if(state[i]==1) {acyclic=false;return;}
            state[i]=1;
            for(auto [id,a]:nodes[i].inputs) if(a>0 && producer[id]>=0) visit(std::size_t(producer[id]));
            state[i]=2;order.push_back(i);
        };
        for(std::size_t i=0;i<nodes.size();++i) visit(i);
    }
    std::vector<double> values(const Stockpile& stock) const {
        std::vector<double> result(keys.size());
        for(auto [key,a]:stock) if(auto it=ids.find(key);it!=ids.end()) result[it->second]=a;
        return result;
    }
    Stockpile close(const Stockpile& use,const Stockpile& base) const {
        const auto end=values(use),native=values(base);auto demand=end;
        std::vector<double> units(nodes.size());
        const auto count=[&](std::size_t i) {
            double n=0.;for(auto [id,a]:nodes[i].outputs) if(a>0) n=std::max(n,std::max(0.,demand[id]-native[id])/a);return n;
        };
        if(acyclic) {
            for(auto it=order.rbegin();it!=order.rend();++it) {
                const auto i=*it;units[i]=count(i);
                for(auto [id,a]:nodes[i].inputs) demand[id]+=a*units[i];
            }
        } else {
            // Bounded fallback for a future cyclic/alternative recipe registry.
            for(int pass=0;pass<12;++pass) {
                auto next=end;
                for(std::size_t i=0;i<nodes.size();++i) {units[i]=count(i);for(auto [id,a]:nodes[i].inputs) next[id]+=a*units[i];}
                demand=std::move(next);
            }
        }
        Stockpile powers;
        for(std::size_t i=0;i<nodes.size();++i) {
            const auto& r=*nodes[i].recipe;
            if(r.rate>0 && r.powerCost>0) powers[r.id]=units[i]*r.powerCost/r.rate;
        }
        return powers;
    }
};
inline const ProductionGraph& productionGraph() {static const ProductionGraph graph;return graph;}

// An inexpensive monthly flow balance for AI decisions, not an execution of
// production. Opening reserves support up to one third of their amount/month.
class CompiledProductionBalance {
    struct Flow {std::vector<std::pair<std::size_t,double>> inputs,outputs;};
    std::vector<ProductionFlows> signature;
    std::vector<Flow> flows;
    std::vector<double> inputDemand;
public:
    template<class Archive> void saveFields(Archive& archive) {archive(signature,flows,inputDemand,rebuilds);}
    unsigned rebuilds{};
    void update(const Production& model) {
        const auto& passive=model.nationalPlan?model.passive:static_cast<const std::array<ProductionFlows,productionStages>&>(model);
        bool same=signature.size()==std::size_t(productionStages-1)+(model.nationalPlan?model.lines.size():0);
        std::size_t index=0;
        if(same) {
            for(int stage=0;stage<productionStages;++stage) if(stage!=upkeep) {
                same&=signature[index].inputs==passive[stage].inputs && signature[index].outputs==passive[stage].outputs;++index;
            }
            if(model.nationalPlan) for(const auto& line:model.lines) {
                same&=signature[index].inputs==line.inputs && signature[index].outputs==line.outputs;++index;
            }
        }
        if(same) return;
        std::vector<const ProductionFlows*> current;
        for(int stage=0;stage<productionStages;++stage) if(stage!=upkeep) current.push_back(&passive[stage]);
        std::vector<ProductionFlows> lines;
        if(model.nationalPlan) for(const auto& line:model.lines) lines.push_back({line.inputs,line.outputs});
        for(const auto& line:lines) current.push_back(&line);
        ++rebuilds;signature.clear();flows.clear();
        const auto& graph=productionGraph();inputDemand.assign(graph.keys.size(),0.);
        for(const auto* source:current) {
            signature.push_back(*source);Flow flow;
            for(auto [key,a]:source->inputs) if(auto it=graph.ids.find(key);it!=graph.ids.end()) {
                flow.inputs.emplace_back(it->second,a);inputDemand[it->second]+=std::max(0.,a);
            }
            for(auto [key,a]:source->outputs) if(auto it=graph.ids.find(key);it!=graph.ids.end()) flow.outputs.emplace_back(it->second,a);
            flows.push_back(std::move(flow));
        }
    }
    Stockpile estimate(const Stockpile& stocks) const {
        const auto& graph=productionGraph();const auto reserve=graph.values(stocks);
        std::vector<double> output(graph.keys.size()),next(output.size());
        // Five bounded algebraic passes resolve short intermediate chains. There
        // are no simulated hours, market clearing, stock writes or report copies.
        for(int pass=0;pass<5;++pass) {
            std::fill(next.begin(),next.end(),0.);
            for(const auto& flow:flows) {
                double supported=1.;
                for(auto [id,a]:flow.inputs) if(a>0 && inputDemand[id]>0)
                    supported=std::min(supported,std::clamp((std::max(0.,reserve[id])/3.+output[id])/inputDemand[id],0.,1.));
                for(auto [id,a]:flow.outputs) next[id]+=std::max(0.,a)*supported;
            }
            output.swap(next);
        }
        Stockpile result;
        for(std::size_t i=0;i<output.size();++i) if(output[i]>0) result[graph.keys[i]]=output[i];
        return result;
    }
};
}
