#include "../land_path.hpp"
#include <array>
#include <chrono>
#include <iostream>
#include <queue>
#include <tuple>
#include <string>
#include <stdexcept>
namespace hoi5 { inline int airHexDistance(int a,int b,int size) {
    const int dq=a%size-b%size,dr=a/size-b/size;
    return std::max({std::abs(dq),std::abs(dr),std::abs(dq+dr)});
} }
struct Fixture {
    struct Tile { bool water{}; int owner{}; double movementCost=1.; };
    int size; std::vector<Tile> tiles;
    explicit Fixture(int n):size(n),tiles(n*n) {}
    bool contains(int q,int r) const { return q>=0 && r>=0 && q<size && r<size; }
    // Frozen baseline: World::landRoute at commit 297457c, for reproducible comparison.
    template<class CanEnter>
    std::deque<int> legacy(int origin,int destination,CanEnter canEnter,bool axialHeuristic = false) const {
        std::vector<int> parent(tiles.size(), -1);
        std::vector<double> distance(tiles.size(), std::numeric_limits<double>::infinity());
        using Node = std::tuple<double, int, int>;
        std::priority_queue<Node, std::vector<Node>, std::greater<>> frontier;
        int counter = 0, expansions = 0;
        frontier.emplace(0,counter,origin);
        distance[origin] = 0;
        const int dq = origin%size-destination%size, dr = origin/size-destination/size;
        const int limit = std::min(int(tiles.size()),std::max(2000,90*std::max({std::abs(dq),std::abs(dr),std::abs(dq+dr)})));
        while (!frontier.empty() && expansions < limit) {
            const int cell = std::get<2>(frontier.top());
            frontier.pop();
            ++expansions;
            if (cell == destination) break;
            const double cost = distance[cell];
            const int q = cell % size, r = cell / size;
            const int shift = r % 2;
            const std::array<std::pair<int, int>, 6> offsets{{
                {shift, 1}, {shift - 1, 1}, {-1, 0}, {shift - 1, -1}, {shift, -1}, {1, 0}
            }};
            for (const auto [dq, dr] : offsets) {
                if (!contains(q + dq, r + dr)) continue;
                const int next = (r + dr) * size + q + dq;
                if (!canEnter(next)) continue;
                const double nextCost = cost + std::max(1.,tiles[next].movementCost);
                if (nextCost >= distance[next]) continue;
                distance[next] = nextCost;
                parent[next] = cell;
                const int heuristic = axialHeuristic ? hoi5::airHexDistance(next,destination,size) :
                    std::max(std::abs(next%size-destination%size),std::abs(next/size-destination/size));
                frontier.emplace(nextCost+heuristic,++counter,next);
            }
        }
        if (destination != origin && parent[destination] < 0) return {};
        std::deque<int> route;
        for (int step = destination; step != origin; step = parent[step]) route.push_front(step);
        return route;
    }

    bool enter(int t) const { return !tiles[t].water; }
    std::deque<int> route(int a,int b,hoi5::LandPathMetrics* m=nullptr) const {
        return hoi5::findLandPath(size,int(tiles.size()),a,b,[&](int t){return enter(t);},
            [&](int t){return tiles[t].movementCost;},m);
    }
    void validate(int a,int b,const std::deque<int>& path) const {
        if (path.empty() || path.back()!=b) throw std::runtime_error("missing path");
        for(int t:path) {
            if(!enter(t) || hoi5::landHexDistance(a,t,size)!=1) throw std::runtime_error("illegal edge");
            a=t;
        }
    }
};
void require(bool ok,const char* message) { if(!ok) throw std::runtime_error(message); }
double cost(const Fixture& f,const std::deque<int>& route) {
    double total=0; for(int t:route) total+=std::max(1.,f.tiles[t].movementCost); return total;
}
// Independent Dijkstra reference for optimal weighted cost on small fixtures.
double optimal(const Fixture& f,int a,int b) {
    std::vector<double> d(f.tiles.size(),1e100); d[a]=0;
    using N=std::pair<double,int>; std::priority_queue<N,std::vector<N>,std::greater<>> q; q.emplace(0,a);
    while(!q.empty()) {
        auto [g,t]=q.top(); q.pop(); if(g!=d[t]) continue; if(t==b) return g;
        const int x=t%f.size,y=t/f.size,s=y%2;
        for(auto [dx,dy]:std::array<std::pair<int,int>,6>{{{s,1},{s-1,1},{-1,0},{s-1,-1},{s,-1},{1,0}}}) {
            if(!f.contains(x+dx,y+dy)) continue; int n=(y+dy)*f.size+x+dx;
            if(!f.enter(n)) continue; double ng=g+std::max(1.,f.tiles[n].movementCost);
            if(ng<d[n]) {d[n]=ng;q.emplace(ng,n);}
        }
    } return 1e100;
}
int main() try {
    Fixture dry(256); dry.validate(0,65535,dry.route(0,65535));
    Fixture lake(160);
    for(int r=0;r<151;++r) lake.tiles[r*160+80].water=true;
    const int a=10*160+79,b=10*160+81;
    lake.validate(a,b,lake.route(a,b));
    require(lake.legacy(a,b,[&](int t){return lake.enter(t);}).empty(),"lake must reproduce old failure");
    Fixture narrow(240); for(auto& t:narrow.tiles)t.water=true;
    for(int r=0;r<240;r+=2) {
        for(int x=0;x<240;++x)narrow.tiles[r*240+x].water=false;
        if(r+1<240)narrow.tiles[(r+1)*240+((r/2)%2?0:239)].water=false;
    }
    const int end=238*240;
    narrow.validate(0,end,narrow.route(0,end));
    require(narrow.legacy(0,end,[&](int t){return narrow.enter(t);}).empty(),"corridor must reproduce old failure");
    Fixture blocked=lake; blocked.tiles[151*160+80].water=true;
    for(int r=152;r<160;++r)blocked.tiles[r*160+80].water=true;
    require(blocked.route(a,b).empty(),"disconnected goal accepted");
    require(hoi5::findLandPath(160,25600,-1,b,[](int){return true;},[](int){return 1.;}).empty(),"invalid origin");
    // Reuse the scratch across maps and changing terrain; there is no stale route cache.
    lake.tiles[80].water=false; auto direct=lake.route(79,81); require(direct.size()==2,"terrain update ignored");
    lake.tiles[80].water=true;
    for(int seed=0;seed<40;++seed) {
        Fixture weighted(24);
        for(int t=0;t<576;++t) {weighted.tiles[t].movementCost=1+(t*37+seed*13)%7;
            weighted.tiles[t].water=(t*17+seed*11)%19==0;}
        weighted.tiles[575].water=false;
        const auto path=weighted.route(0,575); const auto expected=optimal(weighted,0,575);
        require(path.empty()?expected==1e100:std::abs(cost(weighted,path)-expected)<1e-9,"weighted optimality");
    }
    std::cout<<"correctness: dry, lake, corridor, disconnected, terrain changes, weighted Dijkstra: PASS\n";
    const auto bench=[](const char* name,const Fixture& f,int a,int b,int orders,bool spread=false) {
        std::array<double,2> elapsed{}; std::array<int,2> found{}; std::size_t expanded=0;
        for(int mode=0;mode<2;++mode) {
            auto start=std::chrono::steady_clock::now();
            for(int i=0;i<orders;++i) {
                hoi5::LandPathMetrics m;
                const int from=spread ? (i%32)*f.size+i/32 : a;
                auto path=mode?f.route(from,b,&m):f.legacy(from,b,[&](int t){return f.enter(t);});
                found[mode]+=!path.empty(); if(mode)expanded+=m.expanded;
            }
            elapsed[mode]=std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-start).count();
        }
        std::cout<<name<<" orders="<<orders<<" old_ms="<<elapsed[0]<<" new_ms="<<elapsed[1]
            <<" old_found="<<found[0]<<" new_found="<<found[1]<<" new_expanded/order="<<expanded/orders<<'\n';
    };
    bench("dry256",dry,0,65535,100);
    bench("lake160",lake,a,b,100);
    bench("corridor240",narrow,0,end,30);
    bench("unreachable160",blocked,a,b,100);
    Fixture big(512); bench("dry512",big,0,262143,100);
    Fixture isolated(512); for(int r=0;r<512;++r)isolated.tiles[r*512+256].water=true;
    bench("unreachable512",isolated,100*512+255,100*512+257,100);
    bench("army512",big,0,262143,100,true);
    bench("short512",big,100*512+100,100*512+110,1000);
    return 0;
} catch(const std::exception& e) { std::cerr<<e.what()<<'\n'; return 1; }
