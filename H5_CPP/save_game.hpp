#pragma once
#ifdef _WIN32
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#endif
// Full world snapshots. Snapshots are little-endian IEEE754, with a checksum before deserialization.
namespace hoi5::save {
inline constexpr unsigned formatVersion=2;
struct Info {std::filesystem::path path;std::string version,country;unsigned format{},seed{};int hours{};std::uint64_t length{},checksum{};std::string error;};
inline std::uint64_t hash(std::string_view bytes) {std::uint64_t result=14695981039346656037ull;for(unsigned char c:bytes){result^=c;result*=1099511628211ull;}return result;}
inline Info header(std::istream& in,const std::filesystem::path& path) {
 Info info;info.path=path;std::string magic;std::getline(in,magic);
 if(magic!="HOI5_SAVE" || !(in>>info.format>>std::quoted(info.version)>>info.seed>>info.hours>>std::quoted(info.country)>>info.length>>info.checksum)) throw std::runtime_error("Invalid save header");
 in.ignore(std::numeric_limits<std::streamsize>::max(),'\n');if(info.length>512*1024*1024)throw std::runtime_error("Save exceeds size limit");return info;
}
inline void writeGame(const std::filesystem::path& path,World& world,SimulationClock& clock,bool overwrite=false) {
 std::stringstream payload(std::ios::in|std::ios::out|std::ios::binary);Archive archive(payload,false);archive(world,clock);auto bytes=payload.str();
 std::filesystem::create_directories(path.parent_path());auto temporary=path;temporary+=".tmp";
 try {
  std::ofstream out(temporary,std::ios::binary|std::ios::trunc);
  out<<"HOI5_SAVE\n"<<formatVersion<<' '<<std::quoted(std::string(gameVersion))<<' '<<world.campaignSeed<<' '<<clock.elapsedHours<<' '<<std::quoted(std::string(world.countryNames[world.controlledCountry]))<<' '<<bytes.size()<<' '<<hash(bytes)<<'\n';
  out.write(bytes.data(),bytes.size());out.close();if(!out)throw std::runtime_error("Could not write save");
  if(!overwrite && std::filesystem::exists(path))throw std::runtime_error("Save already exists");
#ifdef _WIN32
  if(!MoveFileExW(temporary.c_str(),path.c_str(),MOVEFILE_WRITE_THROUGH|(overwrite?MOVEFILE_REPLACE_EXISTING:0)))
      throw std::runtime_error("Could not replace save file");
#else
  std::filesystem::rename(temporary,path);
#endif
 }catch(...){std::error_code ec;std::filesystem::remove(temporary,ec);throw;}
}
inline World readGame(const std::filesystem::path& path,SimulationClock& clock) {
 std::ifstream input(path,std::ios::binary);auto info=header(input,path);
 if(info.format!=1 && info.format!=formatVersion)throw std::runtime_error("Unsupported save format");
 std::string bytes(info.length,'\0');input.read(bytes.data(),bytes.size());
 if(!input || input.peek()!=std::char_traits<char>::eof() || hash(bytes)!=info.checksum)throw std::runtime_error("Damaged save file");
 const auto decode=[&](bool legacy) {
 std::stringstream payload(bytes,std::ios::in|std::ios::out|std::ios::binary);Archive archive(payload,true);archive.legacyWorld=legacy;World candidate;SimulationClock candidateClock;archive(candidate,candidateClock);
 if(payload.peek()!=std::char_traits<char>::eof() || candidate.size<1 || candidate.size>150 || candidate.tiles.size()!=std::size_t(candidate.size*candidate.size) || candidate.profiles.empty() || candidate.profiles.size()>30 || candidate.controlledCountry<0 || candidate.controlledCountry>=int(candidate.profiles.size()) || candidateClock.speed<1 || candidateClock.speed>5)throw std::runtime_error("Invalid saved world");
 for(auto& d:candidate.divisions)if(!candidate.contains(d.q,d.r)||d.owner<0||d.owner>=int(candidate.profiles.size()))throw std::runtime_error("Invalid saved division");
 for(auto& d:candidate.divisions) {
  for(const auto& design:hoi5::divisionTemplates) if(d.design->key==design.key && !design.key.empty()) {d.design=&design;break;}
  if(d.design->key.empty()) for(const auto& design:candidate.playerDesigns) if(d.design->name==design->design.name && d.design->capacity==design->design.capacity){d.design=&design->design;break;}
 }
 if(legacy){candidate.tileStorageSnapshots.resize(candidate.profiles.size());candidate.refreshControlledSummary();if(candidate.campaignSeed==0)candidate.campaignSeed=candidate.news.seedValue();}
 candidate.saveBacking=archive.backing;clock=candidateClock;return candidate;
 };
 if(info.format==1){try{return decode(false);}catch(const std::exception&){return decode(true);}}
 return decode(false);
}
inline std::vector<Info> list(const std::filesystem::path& directory) {
 std::vector<Info> result;std::error_code ec;
 for(std::filesystem::directory_iterator it(directory,ec),end;!ec && it!=end;it.increment(ec)) {
  if(it->path().extension()!=".h5save")continue;
  try {std::ifstream input(it->path(),std::ios::binary);result.push_back(header(input,it->path()));}
  catch(const std::exception& e){Info info;info.path=it->path();info.error=e.what();result.push_back(info);}
 }
 std::ranges::sort(result,[](const Info& a,const Info& b){return a.path.filename()>b.path.filename();});return result;
}
}
