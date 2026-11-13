cmake_minimum_required(VERSION 3.24)
project(HOI5 VERSION 0.0.9 LANGUAGES CXX)
include(CTest)
include(FetchContent)
set(CMAKE_POLICY_VERSION_MINIMUM 3.5)
set(SFML_BUILD_AUDIO ON CACHE BOOL "")
set(SFML_BUILD_NETWORK OFF CACHE BOOL "")
FetchContent_Declare(sfml GIT_REPOSITORY https://github.com/SFML/SFML.git
    GIT_TAG 3.0.2 GIT_SHALLOW TRUE GIT_SUBMODULES "")
# Declare the codecs before SFML so Git can skip unused submodule setup.
FetchContent_Declare(ogg GIT_REPOSITORY https://github.com/xiph/ogg.git
    GIT_TAG v1.3.5 GIT_SHALLOW TRUE GIT_SUBMODULES ""
    PATCH_COMMAND ${CMAKE_COMMAND} -DOGG_DIR=<SOURCE_DIR> -P ${FETCHCONTENT_BASE_DIR}/sfml-src/tools/ogg/PatchOgg.cmake)
FetchContent_Declare(flac GIT_REPOSITORY https://github.com/xiph/flac.git
    GIT_TAG 1.4.3 GIT_SHALLOW TRUE GIT_SUBMODULES ""
    PATCH_COMMAND ${CMAKE_COMMAND} -DFLAC_DIR=<SOURCE_DIR> -P ${FETCHCONTENT_BASE_DIR}/sfml-src/tools/flac/PatchFLAC.cmake)
FetchContent_Declare(vorbis GIT_REPOSITORY https://github.com/xiph/vorbis.git
    GIT_TAG v1.3.7 GIT_SHALLOW TRUE GIT_SUBMODULES ""
    PATCH_COMMAND ${CMAKE_COMMAND} -DVORBIS_DIR=<SOURCE_DIR> -P ${FETCHCONTENT_BASE_DIR}/sfml-src/tools/vorbis/PatchVorbis.cmake)
FetchContent_MakeAvailable(sfml)
add_executable(HOI5 H5_CPP/main.cpp)
execute_process(COMMAND git rev-parse --short=7 HEAD WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}"
    OUTPUT_VARIABLE HOI5_GIT_COMMIT OUTPUT_STRIP_TRAILING_WHITESPACE ERROR_QUIET)
if(NOT HOI5_GIT_COMMIT)
    set(HOI5_GIT_COMMIT "unknown")
endif()
set(HOI5_FULL_VERSION "${PROJECT_VERSION}.${HOI5_GIT_COMMIT}")
target_compile_definitions(HOI5 PRIVATE HOI5_VERSION="${HOI5_FULL_VERSION}")
file(WRITE "${CMAKE_CURRENT_BINARY_DIR}/version.txt" "${HOI5_FULL_VERSION}\n")
target_compile_features(HOI5 PRIVATE cxx_std_20)
if(MSVC)
    target_compile_options(HOI5 PRIVATE /utf-8)
endif()
target_link_libraries(HOI5 PRIVATE SFML::Graphics SFML::Audio)
if(MINGW)
    get_filename_component(compiler_bin "${CMAKE_CXX_COMPILER}" DIRECTORY)
    foreach(dll IN ITEMS libstdc++-6.dll libwinpthread-1.dll libgcc_s_seh-1.dll)
        set(runtime_dll "${compiler_bin}/${dll}")
        if(NOT EXISTS "${runtime_dll}")
            message(FATAL_ERROR "MinGW runtime not found: ${dll}")
        endif()
        add_custom_command(TARGET HOI5 POST_BUILD COMMAND ${CMAKE_COMMAND} -E copy_if_different
            "${runtime_dll}" "$<TARGET_FILE_DIR:HOI5>" VERBATIM)
    endforeach()
endif()
add_custom_command(TARGET HOI5 POST_BUILD COMMAND ${CMAKE_COMMAND} -E copy_if_different
    "${CMAKE_CURRENT_SOURCE_DIR}/H5_CPP/reference-map.txt"
    "$<TARGET_FILE_DIR:HOI5>/reference-map.txt")
set_property(TARGET HOI5 APPEND PROPERTY LINK_DEPENDS "${CMAKE_CURRENT_SOURCE_DIR}/H5_CPP/reference-map.txt")
file(GLOB_RECURSE HOI5_ASSETS CONFIGURE_DEPENDS
    "${CMAKE_CURRENT_SOURCE_DIR}/H5_Python/assets/*" "${CMAKE_CURRENT_SOURCE_DIR}/H5_Python/data/*"
    "${CMAKE_CURRENT_SOURCE_DIR}/H5_Python/music/*" "${CMAKE_CURRENT_SOURCE_DIR}/H5_Python/sounds/*")
set_property(TARGET HOI5 APPEND PROPERTY LINK_DEPENDS "${HOI5_ASSETS}")
add_custom_command(TARGET HOI5 POST_BUILD
    COMMAND ${CMAKE_COMMAND}
        "-DRESOURCE_SOURCE=${CMAKE_CURRENT_SOURCE_DIR}/H5_Python"
        "-DRESOURCE_DESTINATION=$<TARGET_FILE_DIR:HOI5>"
        -P "${CMAKE_CURRENT_SOURCE_DIR}/H5_CPP/copy_resources.cmake"
    VERBATIM)
add_test(NAME reference_map COMMAND HOI5 --check-map)
add_test(NAME friendly_movement COMMAND HOI5 --check-movement)
add_test(NAME neutral_capture COMMAND HOI5 --check-capture)
add_test(NAME economy_tick_and_trade COMMAND HOI5 --check-economy)
add_test(NAME diplomacy_and_battle COMMAND HOI5 --check-battle)
add_test(NAME construction_and_training COMMAND HOI5 --check-construction-training)
add_test(NAME air_strike COMMAND HOI5 --check-air-strike)
add_test(NAME simulation_clock COMMAND HOI5 --check-clock)
add_test(NAME hex_picking COMMAND HOI5 --check-hex-picking)
add_test(NAME withdrawal_after_revoked_transit COMMAND HOI5 --check-withdrawal)
add_test(NAME division_path_python_parity COMMAND HOI5 --check-path-parity)
add_test(NAME army_front_and_manual_orders COMMAND HOI5 --check-army-front)
add_test(NAME news_popup_priority COMMAND HOI5 --check-news-popup)
add_test(NAME news_file_log COMMAND HOI5 --check-news-log "${CMAKE_CURRENT_BINARY_DIR}/news-log-test.txt")
add_test(NAME supply_python_parity COMMAND HOI5 --check-supply-parity)
add_test(NAME bot_regions_python_parity COMMAND HOI5 --check-bot-regions)
add_test(NAME bot_front_posts_python_parity COMMAND HOI5 --check-bot-front-posts)
add_test(NAME bot_border_campaign COMMAND HOI5 --check-border-campaign)
add_test(NAME bot_generated_campaign COMMAND HOI5 --check-campaign 146591 365)
set_tests_properties(bot_generated_campaign PROPERTIES
    FAIL_REGULAR_EXPRESSION "first bot battle hour: -1")
add_test(NAME bot_course_python_parity COMMAND HOI5 --check-bot-course)
add_test(NAME bot_recruitment_python_parity COMMAND HOI5 --check-bot-recruitment)
add_test(NAME bot_mobilization_stock COMMAND HOI5 --check-bot-mobilization)
add_test(NAME bot_air_planning_python_parity COMMAND HOI5 --check-bot-air)
add_test(NAME bot_economy_python_parity COMMAND HOI5 --check-bot-economy)
add_test(NAME ai_profiler_rows COMMAND HOI5 --check-ai-profiler)
add_test(NAME bot_diplomacy_python_parity COMMAND HOI5 --check-bot-diplomacy)
add_test(NAME bot_offer_response_python_parity COMMAND HOI5 --check-bot-offers)
add_test(NAME bot_dependencies_python_parity COMMAND HOI5 --check-bot-dependencies)
add_test(NAME bot_claim_python_parity COMMAND HOI5 --check-bot-claim)
add_test(NAME airbase_capture COMMAND HOI5 --check-airbase-capture)
add_test(NAME defense_reload COMMAND HOI5 --check-defense-reload)
add_test(NAME field_helipad COMMAND HOI5 --check-field-helipad)
add_test(NAME air_wing_rebase COMMAND HOI5 --check-air-rebase)
