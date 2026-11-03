cmake_minimum_required(VERSION 3.24)
project(HOI5 LANGUAGES CXX)
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
target_compile_features(HOI5 PRIVATE cxx_std_20)
target_compile_definitions(HOI5 PRIVATE HOI5_PYTHON_DIR="${CMAKE_CURRENT_SOURCE_DIR}/H5_Python")
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
add_test(NAME reference_map COMMAND HOI5 --check-map)
add_test(NAME friendly_movement COMMAND HOI5 --check-movement)
add_test(NAME neutral_capture COMMAND HOI5 --check-capture)
add_test(NAME economy_tick_and_trade COMMAND HOI5 --check-economy)
add_test(NAME diplomacy_and_battle COMMAND HOI5 --check-battle)
add_test(NAME construction_and_training COMMAND HOI5 --check-construction-training)
add_test(NAME air_strike COMMAND HOI5 --check-air-strike)
