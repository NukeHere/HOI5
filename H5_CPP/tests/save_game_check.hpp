#pragma once
inline int checkSaveGame(const std::filesystem::path& directory) {
 std::filesystem::create_directories(directory);
 auto original=generateWorld(20,3,918273,1);original.startBots(918273);
 hoi5::SimulationClock clock;
 for(int hour=1;hour<=72;++hour){original.advance(1,nullptr,hour==48?std::optional{1}:std::nullopt);clock.elapsedHours=hour;}
 clock.tickCount=72;clock.marketTickCount=1;clock.pendingMarketTicks=1;clock.speed=4;
 original.controlledCountry=1;
 original.countryNames[1]="Тестовая страна";
 original.playerDesigns.push_back(std::make_shared<hoi5::SavedDivisionDesign>("Особая дивизия",hoi5::DivisionComposition{7,3}));
 original.divisions.front().design=&original.playerDesigns.back()->design;
 original.divisions.front().postBattleRoute={original.capitals[0]};
 original.diplomacy.offers.push_back({1,0,100,hoi5::ForeignAction::alliance});
 original.training.push_back({1,original.capitals[1],0,17,123456.,original.nextTrainingId++});
 const auto snapshot=[](World& world,hoi5::SimulationClock& clock){std::stringstream stream(std::ios::in|std::ios::out|std::ios::binary);hoi5::save::Archive archive(stream,false);archive(world,clock);return stream.str();};
 const auto path=directory/"roundtrip.h5save";
 std::error_code ec;std::filesystem::remove(path,ec);
 hoi5::save::writeGame(path,original,clock);
 hoi5::SimulationClock restoredClock;auto restored=hoi5::save::readGame(path,restoredClock);
 if(snapshot(original,clock)!=snapshot(restored,restoredClock))throw std::runtime_error("Save roundtrip mismatch");
 if(restored.divisions.front().design!=&restored.playerDesigns.back()->design)throw std::runtime_error("Custom template identity lost");
 for(int hour=73;hour<=96;++hour){original.advance(1);restored.advance(1);}
 if(snapshot(original,clock)!=snapshot(restored,restoredClock))throw std::runtime_error("Loaded campaign diverged");
 std::ifstream input(path,std::ios::binary);std::string bytes{std::istreambuf_iterator<char>(input),{}};
 auto foreign=bytes;auto version=foreign.find(std::string(gameVersion));foreign.replace(version,gameVersion.size(),"older-build");
 auto write=[&](const char* name,const std::string& content){auto file=directory/name;std::ofstream out(file,std::ios::binary);out.write(content.data(),content.size());return file;};
 const auto foreignPath=write("foreign.h5save",foreign);auto compatible=hoi5::save::readGame(foreignPath,restoredClock);
 if(compatible.campaignSeed!=918273)throw std::runtime_error("Other game version should load");
 const auto expectFailure=[&](const char* name,std::string content){auto file=write(name,content);const int before=restoredClock.elapsedHours;bool failed=false;try{(void)hoi5::save::readGame(file,restoredClock);}catch(const std::exception&){failed=true;}if(!failed||restoredClock.elapsedHours!=before)throw std::runtime_error("Invalid save accepted or modified clock");};
 auto damaged=bytes;damaged.back()^=1;expectFailure("damaged.h5save",damaged);
 expectFailure("truncated.h5save",bytes.substr(0,bytes.size()/2));
 auto future=bytes;future.replace(future.find('\n')+1,1,"9");expectFailure("future.h5save",future);
 // The first public draft omitted the optional world suffix; retain its reader.
 std::stringstream legacyStream(std::ios::in|std::ios::out|std::ios::binary);hoi5::save::Archive legacyArchive(legacyStream,false);legacyArchive.legacyWorld=true;const auto originalSeed=original.campaignSeed;original.campaignSeed=0;legacyArchive(original,clock);original.campaignSeed=originalSeed;
 const auto legacyBytes=legacyStream.str();std::ostringstream legacyHeader;
 legacyHeader<<"HOI5_SAVE\n1 "<<std::quoted(std::string(gameVersion))<<' '<<original.campaignSeed<<' '<<clock.elapsedHours<<' '<<std::quoted(std::string(original.countryNames[original.controlledCountry]))<<' '<<legacyBytes.size()<<' '<<hoi5::save::hash(legacyBytes)<<'\n';
 auto legacyPath=write("legacy.h5save",legacyHeader.str()+legacyBytes);auto legacyWorld=hoi5::save::readGame(legacyPath,restoredClock);
 if(legacyWorld.campaignSeed!=originalSeed || legacyWorld.tiles.size()!=original.tiles.size() || legacyWorld.divisions.size()!=original.divisions.size() || legacyWorld.profiles[0].budget!=original.profiles[0].budget)throw std::runtime_error("Legacy save migration failed");
 const auto files=hoi5::save::list(directory);if(files.size()<5)throw std::runtime_error("Save browser did not list files");

 // Drive the same browser event handler as the game, including Unicode text entry.
 hoi5::save::Browser browser;using B=hoi5::save::Browser;
 const auto folder=directory/"browser"/std::to_string(std::chrono::system_clock::now().time_since_epoch().count());
 const sf::Vector2u size{1200,800};
 auto click=[&](int x,int y){return browser.event(sf::Event::MouseButtonPressed{sf::Mouse::Button::Left,{600+x,400+y}},size,original,clock);};
 auto type=[&](const sf::String& text){for(auto c:text)browser.event(sf::Event::TextEntered{c},size,original,clock);};
 auto check=[](bool ok,const char* message){if(!ok)throw std::runtime_error(message);};
 browser.open(B::Mode::save,folder);check(!std::filesystem::exists(folder),"Opening save browser wrote a file");
 click(30,290);type(U"Моя партия");click(100,90);
 check(browser.message=="Игра сохранена" && browser.files.size()==1,"Named save failed");
 auto named=browser.files[0].path;auto before=std::filesystem::file_size(named);
 const double savedBudget=original.profiles[0].budget;original.profiles[0].budget+=777;
 click(220,290);check(browser.dialog==B::Dialog::overwrite,"No overwrite confirmation");click(-200,90);
 auto cancelled=hoi5::save::readGame(named,restoredClock);check(cancelled.profiles[0].budget==savedBudget,"Cancelled overwrite wrote state");
 click(220,290);click(100,90);auto overwritten=hoi5::save::readGame(named,restoredClock);
 check(overwritten.profiles[0].budget==original.profiles[0].budget,"Confirmed overwrite did not replace snapshot");
 click(-150,290);check(browser.dialog==B::Dialog::rename,"No rename dialog");
 const auto chars=browser.name.getSize();for(std::size_t i=0;i<chars;++i)browser.event(sf::Event::TextEntered{8},size,original,clock);
 type(U"Новый сейв Ёж");click(100,90);
 check(browser.message=="Сохранение переименовано" && !std::filesystem::exists(named) && browser.files.size()==1,"Rename did not move save");
 auto renamed=browser.files[0].path;auto renamedWorld=hoi5::save::readGame(renamed,restoredClock);
 check(renamedWorld.profiles[0].budget==original.profiles[0].budget,"Rename changed snapshot");
 browser.open(B::Mode::load,folder);click(0,-170);const auto written=std::filesystem::last_write_time(renamed);
 original.profiles[0].budget+=999;
 check(click(220,290)==B::Action::load && std::filesystem::last_write_time(renamed)==written,"Load button wrote a save");
 bool invalid=false;try{hoi5::save::namedPath(folder,U"../outside");}catch(const std::exception&){invalid=true;}check(invalid,"Invalid filename accepted");
 std::cout<<"Browser named save, Cyrillic input, cancelled/confirmed overwrite, rename and load isolation passed.\n";
 std::cout<<"Save roundtrip, custom templates, 24-hour continuation, version mismatch, checksum, truncation and format checks passed. Size: "<<bytes.size()<<'\n';
 return 0;
}
