# Copyright (c) 2023 - 2026 Chair for Design Automation, TUM
# Copyright (c) 2025 - 2026 Munich Quantum Software Company GmbH
# All rights reserved.
#
# SPDX-License-Identifier: MIT
#
# Licensed under the MIT License

# A CMake config file for the library, to be used by external projects


####### Expanded from @PACKAGE_INIT@ by configure_package_config_file() #######
####### Any changes to this file will be overwritten by the next CMake run ####
####### The input file was mqt-core-config.cmake.in                            ########

get_filename_component(PACKAGE_PREFIX_DIR "${CMAKE_CURRENT_LIST_DIR}/../../../" ABSOLUTE)

####################################################################################

list(APPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_LIST_DIR}")

include(CMakeFindDependencyMacro)
find_dependency(nlohmann_json)
find_dependency(spdlog)
find_dependency(qdmi)

option(MQT_CORE_WITH_GMP "Library is configured to use GMP" OFF)
if(MQT_CORE_WITH_GMP)
  find_dependency(GMP)
endif()

option(MQT_CORE_ZX_SYSTEM_BOOST
       "Library is configured to use system Boost instead of the bundled Boost::multiprecision"
       FALSE)
if(MQT_CORE_ZX_SYSTEM_BOOST)
  find_dependency(Boost 1.80.0)
endif()

if(TARGET MQT::Core)
  return()
endif()

include("${CMAKE_CURRENT_LIST_DIR}/AddMQTPythonBinding.cmake")
include("${CMAKE_CURRENT_LIST_DIR}/Cache.cmake")
include("${CMAKE_CURRENT_LIST_DIR}/PackageAddTest.cmake")
include("${CMAKE_CURRENT_LIST_DIR}/PreventInSourceBuilds.cmake")
include("${CMAKE_CURRENT_LIST_DIR}/StandardProjectSettings.cmake")
include("${CMAKE_CURRENT_LIST_DIR}/mqt-core-targets.cmake")

if(NOT mqt-core_FIND_QUIETLY)
  message(STATUS "Found mqt-core version ${mqt-core_VERSION}")
endif()
