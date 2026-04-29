cmake_minimum_required(VERSION 3.18)

set(SKBUILD_PROJECT_NAME "zxhsim" CACHE STRING "Project name")
set(SKBUILD_PROJECT_VERSION "0.4.3" CACHE STRING "Project version")

# ----------------------feature options----------------------------------------
function(zxhsim_init_bool_cache name help_text default_value)
    if (DEFINED ${name})
        set(_zxhsim_option_value "${${name}}")
    elseif (DEFINED ENV{${name}} AND NOT "$ENV{${name}}" STREQUAL "")
        set(_zxhsim_option_value "$ENV{${name}}")
    else ()
        set(_zxhsim_option_value "${default_value}")
    endif ()

    set(${name} "${_zxhsim_option_value}" CACHE BOOL "${help_text}")
endfunction()

function(zxhsim_init_string_cache name help_text default_value)
    if (DEFINED ${name})
        set(_zxhsim_option_value "${${name}}")
    elseif (DEFINED ENV{${name}} AND NOT "$ENV{${name}}" STREQUAL "")
        set(_zxhsim_option_value "$ENV{${name}}")
    else ()
        set(_zxhsim_option_value "${default_value}")
    endif ()

    set(${name} "${_zxhsim_option_value}" CACHE STRING "${help_text}")
endfunction()

function(zxhsim_resolve_program out_var program_hint)
    if (NOT program_hint)
        set(${out_var} "" PARENT_SCOPE)
        return()
    endif ()

    if (IS_ABSOLUTE "${program_hint}")
        set(_zxhsim_program_resolved "${program_hint}")
    else ()
        find_program(_zxhsim_program_resolved NAMES "${program_hint}")
    endif ()

    set(${out_var} "${_zxhsim_program_resolved}" PARENT_SCOPE)
endfunction()

include("${CMAKE_CURRENT_SOURCE_DIR}/cmake/ZXHSimCuBridgeCompat.cmake")

function(zxhsim_parse_wrapper_tokens out_backend out_include_dirs out_link_dirs out_libs)
    set(_zxhsim_backend "")
    set(_zxhsim_include_dirs "")
    set(_zxhsim_link_dirs "")
    set(_zxhsim_libs "")
    set(_zxhsim_tokens ${ARGN})

    list(LENGTH _zxhsim_tokens _zxhsim_token_count)
    if (_zxhsim_token_count GREATER 0)
        list(GET _zxhsim_tokens 0 _zxhsim_backend)
    endif ()

    set(_zxhsim_expect_include OFF)
    set(_zxhsim_expect_link_dir OFF)
    set(_zxhsim_expect_lib OFF)
    foreach (_zxhsim_token IN LISTS _zxhsim_tokens)
        if (_zxhsim_token STREQUAL _zxhsim_backend)
            continue()
        endif ()

        if (_zxhsim_expect_include)
            list(APPEND _zxhsim_include_dirs "${_zxhsim_token}")
            set(_zxhsim_expect_include OFF)
            continue()
        endif ()
        if (_zxhsim_expect_link_dir)
            list(APPEND _zxhsim_link_dirs "${_zxhsim_token}")
            set(_zxhsim_expect_link_dir OFF)
            continue()
        endif ()
        if (_zxhsim_expect_lib)
            list(APPEND _zxhsim_libs "${_zxhsim_token}")
            set(_zxhsim_expect_lib OFF)
            continue()
        endif ()

        if (_zxhsim_token STREQUAL "-I" OR _zxhsim_token STREQUAL "-isystem")
            set(_zxhsim_expect_include ON)
        elseif (_zxhsim_token MATCHES "^-I(.+)$")
            list(APPEND _zxhsim_include_dirs "${CMAKE_MATCH_1}")
        elseif (_zxhsim_token STREQUAL "-L")
            set(_zxhsim_expect_link_dir ON)
        elseif (_zxhsim_token MATCHES "^-L(.+)$")
            list(APPEND _zxhsim_link_dirs "${CMAKE_MATCH_1}")
        elseif (_zxhsim_token STREQUAL "-l")
            set(_zxhsim_expect_lib ON)
        elseif (_zxhsim_token MATCHES "^-l(.+)$")
            list(APPEND _zxhsim_libs "${CMAKE_MATCH_1}")
        endif ()
    endforeach ()

    list(REMOVE_DUPLICATES _zxhsim_include_dirs)
    list(REMOVE_DUPLICATES _zxhsim_link_dirs)
    list(REMOVE_DUPLICATES _zxhsim_libs)

    set(${out_backend} "${_zxhsim_backend}" PARENT_SCOPE)
    set(${out_include_dirs} "${_zxhsim_include_dirs}" PARENT_SCOPE)
    set(${out_link_dirs} "${_zxhsim_link_dirs}" PARENT_SCOPE)
    set(${out_libs} "${_zxhsim_libs}" PARENT_SCOPE)
endfunction()

set(ZXHSIM_DEFAULT_USE_PYTHON OFF)
if (DEFINED SKBUILD OR DEFINED SKBUILD_STATE OR DEFINED ENV{SKBUILD})
    set(ZXHSIM_DEFAULT_USE_PYTHON ON)
endif ()

zxhsim_init_bool_cache(USE_PYTHON "Use Python frontend" "${ZXHSIM_DEFAULT_USE_PYTHON}")
zxhsim_init_string_cache(
    ZXHSIM_BACKEND
    "ZXH-Sim backend selector: single, omp, cuda, mpi, mpi_omp, mpi_cuda"
    "")
set_property(CACHE ZXHSIM_BACKEND PROPERTY STRINGS single omp cuda mpi mpi_omp mpi_cuda)
string(TOLOWER "${ZXHSIM_BACKEND}" ZXHSIM_BACKEND)

if (DEFINED CACHE{USE_MPI} OR DEFINED CACHE{USE_OMP} OR DEFINED CACHE{USE_CUDA}
    OR (DEFINED ENV{USE_MPI} AND NOT "$ENV{USE_MPI}" STREQUAL "")
    OR (DEFINED ENV{USE_OMP} AND NOT "$ENV{USE_OMP}" STREQUAL "")
    OR (DEFINED ENV{USE_CUDA} AND NOT "$ENV{USE_CUDA}" STREQUAL ""))
    message(FATAL_ERROR
            "Legacy top-level backend flags USE_MPI/USE_OMP/USE_CUDA are no longer accepted.\n"
            "Use ZXHSIM_BACKEND=<backend> instead.\n"
            "Examples:\n"
            "  cmake -S . -B build/mpi -DZXHSIM_BACKEND=mpi\n"
            "  ZXHSIM_BACKEND=mpi pip install .\n"
            "If this build directory was configured by an older version of the project, remove it and configure again.")
endif ()

if (ZXHSIM_BACKEND STREQUAL "")
    set(ZXHSIM_BACKEND "single")
endif ()

if (DEFINED CACHE{ZXHSIM_USE_NCCL}
    OR (DEFINED ENV{ZXHSIM_USE_NCCL} AND NOT "$ENV{ZXHSIM_USE_NCCL}" STREQUAL ""))
    message(FATAL_ERROR
            "ZXHSIM_USE_NCCL is no longer a user-facing option.\n"
            "NCCL support is derived automatically from backend=mpi_cuda.\n"
            "Use ZXHSIM_BACKEND=mpi_cuda, and provide NCCL path hints only when auto-detection is insufficient.")
endif ()

if (NOT ZXHSIM_BACKEND MATCHES "^(single|omp|cuda|mpi|mpi_omp|mpi_cuda)$")
    message(FATAL_ERROR
            "Invalid ZXHSIM_BACKEND: ${ZXHSIM_BACKEND}\n"
            "Valid values: single, omp, cuda, mpi, mpi_omp, mpi_cuda")
endif ()

set(ZXHSIM_BACKEND "${ZXHSIM_BACKEND}" CACHE STRING
    "ZXH-Sim backend selector: single, omp, cuda, mpi, mpi_omp, mpi_cuda" FORCE)

set(USE_MPI OFF)
set(USE_OMP OFF)
set(USE_CUDA OFF)
set(ZXHSIM_USE_NCCL OFF)
if (ZXHSIM_BACKEND STREQUAL "omp")
    set(USE_OMP ON)
elseif (ZXHSIM_BACKEND STREQUAL "cuda")
    set(USE_CUDA ON)
elseif (ZXHSIM_BACKEND STREQUAL "mpi")
    set(USE_MPI ON)
elseif (ZXHSIM_BACKEND STREQUAL "mpi_omp")
    set(USE_MPI ON)
    set(USE_OMP ON)
elseif (ZXHSIM_BACKEND STREQUAL "mpi_cuda")
    set(USE_MPI ON)
    set(USE_CUDA ON)
    set(ZXHSIM_USE_NCCL ON)
endif ()

set(ZXHSIM_NODE_EXECUTION_MODE "single")
if (USE_CUDA)
    set(ZXHSIM_NODE_EXECUTION_MODE "cuda")
elseif (USE_OMP)
    set(ZXHSIM_NODE_EXECUTION_MODE "omp")
endif ()
zxhsim_init_string_cache(
    ZXHSIM_CU_BRIDGE_RUNTIME_ROOT
    "Optional runtime prefix used when cu-bridge is installed outside the standard .../tools/cu-bridge layout"
    "")
zxhsim_init_string_cache(
    ZXHSIM_CU_BRIDGE_SYSTEM_INCLUDE_DIRS
    "Semicolon-separated system include directories required by cu-bridge"
    "")
zxhsim_init_string_cache(
    ZXHSIM_CU_BRIDGE_LINK_DIRECTORIES
    "Semicolon-separated link directories required by cu-bridge"
    "")
zxhsim_init_string_cache(
    ZXHSIM_CU_BRIDGE_LINK_LIBRARIES
    "Semicolon-separated cu-bridge runtime libraries used for CUDA compiler probing and final link"
    "")
zxhsim_init_string_cache(
    ZXHSIM_CUDA_EXTRA_INCLUDE_DIRS
    "Additional include directories appended to CUDA-enabled targets"
    "")
zxhsim_init_string_cache(
    ZXHSIM_CUDA_EXTRA_LIBRARIES
    "Additional libraries appended to CUDA-enabled final link targets"
    "")
zxhsim_init_string_cache(
    ZXHSIM_CUB_ROOT
    "Optional CUB package prefix containing include/ and lib/cmake/cub"
    "")
zxhsim_init_string_cache(
    ZXHSIM_NCCL_ROOT
    "Optional NCCL root prefix containing include/ and lib/ subdirectories"
    "")
zxhsim_init_string_cache(
    ZXHSIM_NCCL_INCLUDE_DIRS
    "Semicolon-separated NCCL include directories"
    "")
zxhsim_init_string_cache(
    ZXHSIM_NCCL_LIBRARIES
    "Semicolon-separated NCCL libraries or absolute library paths"
    "")

zxhsim_prepare_cuda_frontend()
set(ZXHSIM_EXTRA_RUNTIME_RPATHS "")

if (USE_MPI)
    if (DEFINED MPI_CXX_COMPILER AND NOT MPI_CXX_COMPILER STREQUAL "")
        set(ZXHSIM_MPI_WRAPPER_CANDIDATE "${MPI_CXX_COMPILER}")
    elseif (DEFINED ENV{MPI_CXX_COMPILER} AND NOT "$ENV{MPI_CXX_COMPILER}" STREQUAL "")
        set(ZXHSIM_MPI_WRAPPER_CANDIDATE "$ENV{MPI_CXX_COMPILER}")
    elseif (DEFINED ENV{MPICXX} AND NOT "$ENV{MPICXX}" STREQUAL "")
        set(ZXHSIM_MPI_WRAPPER_CANDIDATE "$ENV{MPICXX}")
    else ()
        find_program(ZXHSIM_MPI_WRAPPER_CANDIDATE NAMES mpicxx mpic++ mpiicpc)
    endif ()

    if (NOT ZXHSIM_MPI_WRAPPER_CANDIDATE)
        message(FATAL_ERROR
                "Backend '${ZXHSIM_BACKEND}' requires an MPI C++ wrapper.
"
                "Provide mpicxx via -DMPI_CXX_COMPILER=<path>, MPICXX=<path>, or ensure mpicxx is on PATH.")
    endif ()

    set(ZXHSIM_MPI_WRAPPER_EXECUTABLE "")
    if (IS_ABSOLUTE "${ZXHSIM_MPI_WRAPPER_CANDIDATE}")
        set(ZXHSIM_MPI_WRAPPER_EXECUTABLE "${ZXHSIM_MPI_WRAPPER_CANDIDATE}")
    elseif ("${ZXHSIM_MPI_WRAPPER_CANDIDATE}" MATCHES "[/\\]")
        get_filename_component(
            ZXHSIM_MPI_WRAPPER_EXECUTABLE
            "${ZXHSIM_MPI_WRAPPER_CANDIDATE}"
            ABSOLUTE
            BASE_DIR "${CMAKE_CURRENT_SOURCE_DIR}")
    else ()
        find_program(ZXHSIM_MPI_WRAPPER_EXECUTABLE NAMES "${ZXHSIM_MPI_WRAPPER_CANDIDATE}")
    endif ()

    if (NOT ZXHSIM_MPI_WRAPPER_EXECUTABLE OR NOT EXISTS "${ZXHSIM_MPI_WRAPPER_EXECUTABLE}")
        message(FATAL_ERROR "MPI CXX wrapper does not exist: ${ZXHSIM_MPI_WRAPPER_CANDIDATE}")
    endif ()

    get_filename_component(ZXHSIM_MPI_WRAPPER_REALPATH "${ZXHSIM_MPI_WRAPPER_EXECUTABLE}" REALPATH)
    set(MPI_CXX_COMPILER "${ZXHSIM_MPI_WRAPPER_EXECUTABLE}" CACHE FILEPATH "MPI CXX wrapper" FORCE)

    if (DEFINED CMAKE_CXX_COMPILER AND NOT CMAKE_CXX_COMPILER STREQUAL "")
        get_filename_component(ZXHSIM_SELECTED_CXX_COMPILER "${CMAKE_CXX_COMPILER}" REALPATH)
        if (NOT ZXHSIM_SELECTED_CXX_COMPILER STREQUAL ZXHSIM_MPI_WRAPPER_REALPATH)
            message(FATAL_ERROR
                    "Backend '${ZXHSIM_BACKEND}' requires mpicxx to be the sole user-provided host C++ compiler entry.
"
                    "  MPI_CXX_COMPILER: ${MPI_CXX_COMPILER}
"
                    "  MPI_CXX_COMPILER (realpath): ${ZXHSIM_MPI_WRAPPER_REALPATH}
"
                    "  CMAKE_CXX_COMPILER (realpath): ${ZXHSIM_SELECTED_CXX_COMPILER}
"
                    "Use a fresh build directory, or remove the conflicting CMAKE_CXX_COMPILER/CXX setting.")
        endif ()
    else ()
        set(CMAKE_CXX_COMPILER "${ZXHSIM_MPI_WRAPPER_EXECUTABLE}" CACHE FILEPATH "C++ compiler" FORCE)
    endif ()

    if (USE_CUDA)
        set(ZXHSIM_MPI_BACKEND_CXX "")
        set(ZXHSIM_MPI_WRAPPER_INCLUDE_DIRS "")
        set(ZXHSIM_MPI_WRAPPER_LINK_DIRS "")
        set(ZXHSIM_MPI_WRAPPER_LIBS "")
        foreach (_zxhsim_show_arg IN ITEMS -show --showme:command --showme)
            execute_process(
                COMMAND "${MPI_CXX_COMPILER}" "${_zxhsim_show_arg}"
                OUTPUT_VARIABLE _zxhsim_wrapper_show
                ERROR_VARIABLE _zxhsim_wrapper_show_err
                RESULT_VARIABLE _zxhsim_wrapper_show_status
                OUTPUT_STRIP_TRAILING_WHITESPACE
                ERROR_STRIP_TRAILING_WHITESPACE)
            if (_zxhsim_wrapper_show_status EQUAL 0 AND NOT _zxhsim_wrapper_show STREQUAL "")
                separate_arguments(_zxhsim_wrapper_tokens NATIVE_COMMAND "${_zxhsim_wrapper_show}")
                list(LENGTH _zxhsim_wrapper_tokens _zxhsim_wrapper_token_count)
                if (_zxhsim_wrapper_token_count GREATER 0)
                    zxhsim_parse_wrapper_tokens(
                        ZXHSIM_MPI_BACKEND_CXX
                        ZXHSIM_MPI_WRAPPER_INCLUDE_DIRS
                        ZXHSIM_MPI_WRAPPER_LINK_DIRS
                        ZXHSIM_MPI_WRAPPER_LIBS
                        ${_zxhsim_wrapper_tokens})
                    break()
                endif ()
            endif ()
        endforeach ()

        if (NOT ZXHSIM_MPI_BACKEND_CXX)
            message(FATAL_ERROR
                    "Backend '${ZXHSIM_BACKEND}' requires deriving the CUDA host compiler from the MPI wrapper, but the wrapper did not report its backend compiler.
"
                    "  MPI_CXX_COMPILER: ${MPI_CXX_COMPILER}
"
                    "Supported wrappers should answer one of: -show, --showme:command, --showme.")
        endif ()

        if (IS_ABSOLUTE "${ZXHSIM_MPI_BACKEND_CXX}")
            get_filename_component(ZXHSIM_MPI_BACKEND_CXX "${ZXHSIM_MPI_BACKEND_CXX}" REALPATH)
        else ()
            find_program(ZXHSIM_MPI_BACKEND_CXX_PATH NAMES "${ZXHSIM_MPI_BACKEND_CXX}")
            if (NOT ZXHSIM_MPI_BACKEND_CXX_PATH)
                message(FATAL_ERROR
                        "Failed to resolve the backend host compiler reported by mpicxx.
"
                        "  MPI_CXX_COMPILER: ${MPI_CXX_COMPILER}
"
                        "  wrapper backend compiler: ${ZXHSIM_MPI_BACKEND_CXX}")
            endif ()
            get_filename_component(ZXHSIM_MPI_BACKEND_CXX "${ZXHSIM_MPI_BACKEND_CXX_PATH}" REALPATH)
        endif ()

        set(ZXHSIM_MPI_BACKEND_CXX "${ZXHSIM_MPI_BACKEND_CXX}" CACHE INTERNAL
            "Backend host compiler reported by the MPI wrapper" FORCE)

        if (DEFINED CMAKE_CUDA_HOST_COMPILER AND NOT CMAKE_CUDA_HOST_COMPILER STREQUAL "")
            get_filename_component(ZXHSIM_SELECTED_CUDA_HOST "${CMAKE_CUDA_HOST_COMPILER}" REALPATH)
            if (NOT ZXHSIM_SELECTED_CUDA_HOST STREQUAL ZXHSIM_MPI_BACKEND_CXX)
                message(FATAL_ERROR
                        "Backend '${ZXHSIM_BACKEND}' requires the CUDA host compiler to match the backend compiler reported by the MPI wrapper.
"
                        "  MPI_CXX_COMPILER: ${MPI_CXX_COMPILER}
"
                        "  MPI backend C++ compiler: ${ZXHSIM_MPI_BACKEND_CXX}
"
                        "  CMAKE_CUDA_HOST_COMPILER: ${ZXHSIM_SELECTED_CUDA_HOST}
"
                        "Do not set CUDAHOSTCXX/CMAKE_CUDA_HOST_COMPILER separately unless it matches the compiler used by mpicxx.")
            endif ()
        else ()
            set(CMAKE_CUDA_HOST_COMPILER "${ZXHSIM_MPI_BACKEND_CXX}" CACHE FILEPATH
                "CUDA host compiler derived from the MPI wrapper" FORCE)
        endif ()
    endif ()
endif ()

set(ZXHSIM_PROJECT_LANGUAGES CXX)
if (USE_CUDA)
    if (NOT DEFINED CMAKE_CUDA_RUNTIME_LIBRARY OR CMAKE_CUDA_RUNTIME_LIBRARY STREQUAL "")
        set(CMAKE_CUDA_RUNTIME_LIBRARY "Shared" CACHE STRING "CUDA runtime library mode" FORCE)
    endif ()
    list(APPEND ZXHSIM_PROJECT_LANGUAGES CUDA)
endif ()

project(
  ${SKBUILD_PROJECT_NAME}
  VERSION ${SKBUILD_PROJECT_VERSION}
  LANGUAGES ${ZXHSIM_PROJECT_LANGUAGES})

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
if (NOT DEFINED CMAKE_EXPORT_COMPILE_COMMANDS)
    set(CMAKE_EXPORT_COMPILE_COMMANDS ON CACHE BOOL "Export compile_commands.json")
endif ()
string(ASCII 27 ESC)
set(MSG_PRFX "${ESC}[36m-- (ZXH-Sim)${ESC}[0m")
if (MSVC)
    add_compile_options("/source-charset:utf-8" "/execution-charset:utf-8")
endif ()

function(zxhsim_report_value label value)
    if (NOT "${value}" STREQUAL "")
        message("${MSG_PRFX} ${label}: ${value}")
    else ()
        message("${MSG_PRFX} ${label}: <unset>")
    endif ()
endfunction()

function(zxhsim_report_bool label value)
    if ("${value}" STREQUAL "ON" OR "${value}" STREQUAL "TRUE" OR "${value}" STREQUAL "1")
        message("${MSG_PRFX} ${label}: ON")
    else ()
        message("${MSG_PRFX} ${label}: OFF")
    endif ()
endfunction()

function(zxhsim_is_conda_toolchain out_var compiler_path)
    if (NOT compiler_path)
        set(${out_var} OFF PARENT_SCOPE)
        return()
    endif ()

    get_filename_component(_zxhsim_compiler_realpath "${compiler_path}" REALPATH)
    set(_zxhsim_is_conda OFF)

    if (_zxhsim_compiler_realpath MATCHES "(^|/)(mini|ana)conda[^/]*/"
        OR _zxhsim_compiler_realpath MATCHES "(^|/)x86_64-conda-linux-gnu-"
        OR _zxhsim_compiler_realpath MATCHES "/envs/")
        set(_zxhsim_is_conda ON)
    endif ()

    if (DEFINED ENV{CONDA_PREFIX} AND NOT "$ENV{CONDA_PREFIX}" STREQUAL "")
        get_filename_component(_zxhsim_conda_prefix "$ENV{CONDA_PREFIX}" REALPATH)
        string(FIND "${_zxhsim_compiler_realpath}" "${_zxhsim_conda_prefix}/" _zxhsim_prefix_pos)
        if (NOT _zxhsim_prefix_pos EQUAL -1)
            set(_zxhsim_is_conda ON)
        endif ()
    endif ()

    set(${out_var} ${_zxhsim_is_conda} PARENT_SCOPE)
endfunction()

function(zxhsim_toolchain_family out_var compiler_path)
    zxhsim_is_conda_toolchain(_zxhsim_is_conda "${compiler_path}")
    if (_zxhsim_is_conda)
        set(${out_var} "conda" PARENT_SCOPE)
    else ()
        set(${out_var} "system" PARENT_SCOPE)
    endif ()
endfunction()

zxhsim_report_value("CXX compiler" "${CMAKE_CXX_COMPILER}")
zxhsim_report_value("Backend" "${ZXHSIM_BACKEND}")
zxhsim_report_value("Node execution mode" "${ZXHSIM_NODE_EXECUTION_MODE}")
zxhsim_report_bool("MPI support" "${USE_MPI}")
zxhsim_report_bool("OpenMP support" "${USE_OMP}")
zxhsim_report_bool("CUDA support" "${USE_CUDA}")

# -----------------------target: core objects----------------------------------
set(COMMON_SOURCES
    src/core/bitvec.cpp
    src/core/addr.cpp
    src/core/selector.cpp
    src/core/bitmat.cpp
    src/sv/sv_common.cpp
    src/core/utils.cpp)
add_library(zxhsim_core OBJECT ${COMMON_SOURCES})
target_include_directories(zxhsim_core PUBLIC ${CMAKE_SOURCE_DIR}/include)
set_target_properties(zxhsim_core PROPERTIES POSITION_INDEPENDENT_CODE ON)

# -----------------------target: libzxhsim.a-----------------------------------
add_library(zxhsim STATIC $<TARGET_OBJECTS:zxhsim_core>)
target_include_directories(zxhsim PUBLIC ${CMAKE_SOURCE_DIR}/include)

# -----------------------target: zxhsim.py.so----------------------------------
if (USE_PYTHON)
    message("${MSG_PRFX} Python frontend: ON")

    set(PYBIND11_FINDPYTHON ON)
    find_package(Python3 COMPONENTS Interpreter Development.Module REQUIRED)
    find_package(pybind11 CONFIG QUIET)

    if (NOT pybind11_FOUND)
        execute_process(
            COMMAND ${Python3_EXECUTABLE} -m pybind11 --cmakedir
            OUTPUT_VARIABLE PYBIND11_CMAKE_DIR
            RESULT_VARIABLE PYBIND11_CMAKE_DIR_STATUS
            OUTPUT_STRIP_TRAILING_WHITESPACE
            ERROR_QUIET
        )
        if (PYBIND11_CMAKE_DIR_STATUS EQUAL 0 AND EXISTS "${PYBIND11_CMAKE_DIR}/pybind11Config.cmake")
            message("${MSG_PRFX} pybind11_DIR from python module: ${PYBIND11_CMAKE_DIR}")
            set(pybind11_DIR "${PYBIND11_CMAKE_DIR}" CACHE PATH "pybind11 CMake config directory" FORCE)
            find_package(pybind11 CONFIG REQUIRED)
        else ()
            message(FATAL_ERROR "pybind11 not found. Install pybind11 so `python3 -m pybind11 --cmakedir` is available.")
        endif ()
    endif ()

    pybind11_add_module(_core NO_EXTRAS "src/pybind/bindings.cpp" $<TARGET_OBJECTS:zxhsim_core>)
    # Keep Python extension link predictable across toolchains; CUDA builds are
    # especially sensitive to LTO plugin compatibility.
    set_property(TARGET _core PROPERTY INTERPROCEDURAL_OPTIMIZATION OFF)
    target_link_libraries(_core PRIVATE pybind11::headers)
    target_compile_definitions(_core PRIVATE VERSION_INFO=${PROJECT_VERSION})
    target_include_directories(_core PRIVATE ${CMAKE_SOURCE_DIR}/include)
    install(TARGETS _core DESTINATION ${SKBUILD_PROJECT_NAME})
else ()
    message("${MSG_PRFX} Python frontend: OFF")
endif ()

# ----------------------MPI----------------------------------------------------
if (USE_MPI)
    zxhsim_report_value("MPI CXX wrapper" "${MPI_CXX_COMPILER}")
    if (USE_CUDA)
        zxhsim_report_value("MPI backend host compiler" "${ZXHSIM_MPI_BACKEND_CXX}")
        zxhsim_report_value("MPI wrapper include dirs" "${ZXHSIM_MPI_WRAPPER_INCLUDE_DIRS}")
    endif ()

    unset(MPI_CXX_FOUND CACHE)
    unset(MPI_FOUND CACHE)
    find_package(MPI QUIET COMPONENTS CXX)

    if (NOT MPI_CXX_FOUND)
        message(FATAL_ERROR
                "Backend '${ZXHSIM_BACKEND}' selected the MPI wrapper below, but FindMPI could not resolve MPI headers/libraries from it.
"
                "  MPI_CXX_COMPILER: ${MPI_CXX_COMPILER}
"
                "Check that this wrapper is usable in the current environment, then reconfigure in a fresh build directory if needed.")
    endif ()

    get_filename_component(ZXHSIM_ACTIVE_CXX_COMPILER "${CMAKE_CXX_COMPILER}" REALPATH)
    get_filename_component(ZXHSIM_ACTIVE_MPI_WRAPPER "${MPI_CXX_COMPILER}" REALPATH)
    if (NOT ZXHSIM_ACTIVE_CXX_COMPILER STREQUAL ZXHSIM_ACTIVE_MPI_WRAPPER)
        message(FATAL_ERROR
                "Backend '${ZXHSIM_BACKEND}' requires CMAKE_CXX_COMPILER to resolve to the same MPI wrapper as MPI_CXX_COMPILER.
"
                "  CMAKE_CXX_COMPILER: ${ZXHSIM_ACTIVE_CXX_COMPILER}
"
                "  MPI_CXX_COMPILER: ${ZXHSIM_ACTIVE_MPI_WRAPPER}
"
                "Use a fresh build directory if this one was previously configured without MPI.")
    endif ()

    target_link_libraries(zxhsim_core PRIVATE MPI::MPI_CXX)
    target_link_libraries(zxhsim PUBLIC MPI::MPI_CXX)
    if (USE_CUDA AND NOT "${ZXHSIM_MPI_WRAPPER_INCLUDE_DIRS}" STREQUAL "")
        target_include_directories(zxhsim_core PRIVATE ${ZXHSIM_MPI_WRAPPER_INCLUDE_DIRS})
        target_include_directories(zxhsim PRIVATE ${ZXHSIM_MPI_WRAPPER_INCLUDE_DIRS})
    endif ()
    if (TARGET _core)
        target_link_libraries(_core PRIVATE MPI::MPI_CXX)
        if (USE_CUDA AND NOT "${ZXHSIM_MPI_WRAPPER_INCLUDE_DIRS}" STREQUAL "")
            target_include_directories(_core PRIVATE ${ZXHSIM_MPI_WRAPPER_INCLUDE_DIRS})
        endif ()
    endif ()
endif ()

# ----------------------Execution mode: OMP / CUDA------------------------------
if (USE_OMP AND USE_CUDA)
    message(FATAL_ERROR "Invalid backend configuration: OpenMP and CUDA execution modes are mutually exclusive.")
endif ()

# ----------------------backend source selection--------------------------------
set(BACKEND_COMMON_SOURCES
    src/core/zxh.cpp
    src/measure/measure_common.cpp)

set(BACKEND_KERNEL_SOURCE "src/kernel/kernel_general.cpp")
set(BACKEND_MEM_SOURCE "src/mem/mem_host.cpp")
set(BACKEND_SV_SOURCE "src/sv/sv_general.cpp")
set(BACKEND_RUNTIME_SOURCE "src/runtime/runtime_general.cpp")
set(BACKEND_COMM_SOURCE "src/comm/comm_general.cpp")
set(BACKEND_MEASURE_SOURCE "src/measure/measure_general.cpp")
if (USE_MPI)
    set(BACKEND_SV_SOURCE "src/sv/sv_mpi.cpp")
    set(BACKEND_RUNTIME_SOURCE "src/runtime/runtime_mpi.cpp")
    set(BACKEND_COMM_SOURCE "src/comm/comm_mpi.cpp")
    set(BACKEND_MEASURE_SOURCE "src/measure/measure_mpi.cpp")
endif ()
if (USE_CUDA)
    set(BACKEND_MEM_SOURCE "src/mem/mem_cuda.cu")
    if (USE_MPI)
        set(BACKEND_SV_SOURCE "src/sv/sv_mpi_cuda.cu")
        set(BACKEND_RUNTIME_SOURCE "src/runtime/runtime_mpi_cuda.cu")
        set(BACKEND_COMM_SOURCE
            src/comm/comm_mpi_cuda.cu
            src/comm/comm_mpi_cuda_transport_nccl.cu)
        set(BACKEND_MEASURE_SOURCE "src/measure/measure_mpi_cuda.cu")
    else ()
        set(BACKEND_MEASURE_SOURCE "src/measure/measure_cuda.cu")
    endif ()
else ()
    set(BACKEND_MEM_SOURCE "src/mem/mem_host.cpp")
endif ()
if (USE_CUDA)
    set(BACKEND_KERNEL_SOURCE "src/kernel/kernel_cuda.cu")
elseif (USE_OMP)
    set(BACKEND_KERNEL_SOURCE "src/kernel/kernel_omp.cpp")
else ()
    set(BACKEND_KERNEL_SOURCE "src/kernel/kernel_general.cpp")
endif ()

# ----------------------OpenMP--------------------------------------------------
if (USE_OMP)
    find_package(OpenMP REQUIRED COMPONENTS CXX)
    target_link_libraries(zxhsim_core PRIVATE OpenMP::OpenMP_CXX)
    target_link_libraries(zxhsim PUBLIC OpenMP::OpenMP_CXX)
    if (TARGET _core)
        target_link_libraries(_core PRIVATE OpenMP::OpenMP_CXX)
    endif ()
endif ()

# ----------------------CUDA----------------------------------------------------
if (USE_CUDA)
    zxhsim_report_value("CUDA architectures" "${CMAKE_CUDA_ARCHITECTURES}")
    if (DEFINED ZXHSIM_USING_CU_BRIDGE AND ZXHSIM_USING_CU_BRIDGE)
        zxhsim_report_value("cu-bridge root" "${ZXHSIM_CU_BRIDGE_ROOT}")
        zxhsim_report_value("cu-bridge runtime root" "${ZXHSIM_CU_BRIDGE_RUNTIME_ROOT}")
        zxhsim_report_value("cu-bridge system include dirs" "${ZXHSIM_CU_BRIDGE_SYSTEM_INCLUDE_DIRS_RESOLVED}")
        zxhsim_report_value("cu-bridge link directories" "${ZXHSIM_CU_BRIDGE_LINK_DIRECTORIES_RESOLVED}")
        zxhsim_report_value("cu-bridge link libraries" "${ZXHSIM_CU_BRIDGE_LINK_LIBRARIES_RESOLVED}")
    endif ()
    set(_zxhsim_cub_hints "")
    if (NOT ZXHSIM_CUB_ROOT STREQUAL "")
        list(APPEND _zxhsim_cub_hints "${ZXHSIM_CUB_ROOT}")
    endif ()
    if (DEFINED ENV{CUB_ROOT} AND NOT "$ENV{CUB_ROOT}" STREQUAL "")
        list(APPEND _zxhsim_cub_hints "$ENV{CUB_ROOT}")
    endif ()
    list(REMOVE_DUPLICATES _zxhsim_cub_hints)
    if (NOT "${_zxhsim_cub_hints}" STREQUAL "")
        find_package(CUB CONFIG QUIET
            HINTS ${_zxhsim_cub_hints}
            PATH_SUFFIXES lib/cmake/cub cub/cmake
            NO_DEFAULT_PATH)
    else ()
        set(CUB_FOUND OFF)
    endif ()
    if (CUB_FOUND)
        get_target_property(ZXHSIM_CUB_INCLUDE_DIRS CUB::CUB INTERFACE_INCLUDE_DIRECTORIES)
        zxhsim_report_value("CUB version" "${CUB_VERSION}")
        zxhsim_report_value("CUB config" "${CUB_CONFIG}")
        zxhsim_report_value("CUB include dirs" "${ZXHSIM_CUB_INCLUDE_DIRS}")
    else ()
        set(ZXHSIM_CUB_INCLUDE_DIRS "")
        zxhsim_append_unique_items(ZXHSIM_CUB_INCLUDE_DIRS ${CMAKE_CUDA_TOOLKIT_INCLUDE_DIRECTORIES})
        zxhsim_append_unique_items(ZXHSIM_CUB_INCLUDE_DIRS ${CMAKE_CUDA_IMPLICIT_INCLUDE_DIRECTORIES})
        if ("${ZXHSIM_CUB_INCLUDE_DIRS}" STREQUAL "")
            message(FATAL_ERROR
                    "CUDA backend requires CUB headers, but neither an external CUB package nor bundled CUDA Toolkit headers were found.\n"
                    "Set CUB_ROOT (for example $HOME/tools/cub), or ensure the CUDA Toolkit include directories are discoverable.")
        endif ()
        add_library(zxhsim_cub INTERFACE)
        target_include_directories(zxhsim_cub INTERFACE ${ZXHSIM_CUB_INCLUDE_DIRS})
        add_library(CUB::CUB ALIAS zxhsim_cub)
        set(CUB_VERSION "bundled-with-cuda-toolkit")
        set(CUB_CONFIG "CUDA Toolkit include directories")
        zxhsim_report_value("CUB version" "${CUB_VERSION}")
        zxhsim_report_value("CUB config" "${CUB_CONFIG}")
        zxhsim_report_value("CUB include dirs" "${ZXHSIM_CUB_INCLUDE_DIRS}")
    endif ()
    set(ZXHSIM_CUDA_INCLUDE_DIRS "")
    if (DEFINED ZXHSIM_USING_CU_BRIDGE AND ZXHSIM_USING_CU_BRIDGE)
        zxhsim_append_unique_items(ZXHSIM_CUDA_INCLUDE_DIRS ${ZXHSIM_CU_BRIDGE_INCLUDE_DIRS})
    endif ()
    zxhsim_append_unique_items(ZXHSIM_CUDA_INCLUDE_DIRS ${ZXHSIM_CUDA_EXTRA_INCLUDE_DIRS})
    zxhsim_report_value("CUDA include dirs" "${ZXHSIM_CUDA_INCLUDE_DIRS}")
    zxhsim_report_value("CUDA extra libraries" "${ZXHSIM_CUDA_EXTRA_LIBRARIES}")

    set(ZXHSIM_NCCL_INCLUDE_DIRS_RESOLVED "")
    set(ZXHSIM_NCCL_LIBRARIES_RESOLVED "")
    set(ZXHSIM_NCCL_LIBRARY_DIRS_RESOLVED "")
    if (ZXHSIM_USE_NCCL)
        set(_zxhsim_nccl_roots "")
        if (NOT ZXHSIM_NCCL_ROOT STREQUAL "")
            list(APPEND _zxhsim_nccl_roots "${ZXHSIM_NCCL_ROOT}")
        endif ()
        if (DEFINED ENV{CONDA_PREFIX} AND NOT "$ENV{CONDA_PREFIX}" STREQUAL "")
            get_filename_component(_zxhsim_conda_env_dir "$ENV{CONDA_PREFIX}" DIRECTORY)
            get_filename_component(_zxhsim_conda_root "${_zxhsim_conda_env_dir}" DIRECTORY)
            if (EXISTS "${_zxhsim_conda_root}/pkgs")
                file(GLOB _zxhsim_conda_nccl_pkgs LIST_DIRECTORIES true
                     "${_zxhsim_conda_root}/pkgs/nccl-*")
                list(APPEND _zxhsim_nccl_roots ${_zxhsim_conda_nccl_pkgs})
            endif ()
        endif ()
        list(REMOVE_DUPLICATES _zxhsim_nccl_roots)

        if (NOT ZXHSIM_NCCL_INCLUDE_DIRS STREQUAL "")
            set(ZXHSIM_NCCL_INCLUDE_DIRS_RESOLVED ${ZXHSIM_NCCL_INCLUDE_DIRS})
        else ()
            find_path(
                ZXHSIM_NCCL_INCLUDE_DIR
                NAMES nccl.h
                HINTS ${_zxhsim_nccl_roots}
                PATH_SUFFIXES include)
            if (ZXHSIM_NCCL_INCLUDE_DIR)
                list(APPEND ZXHSIM_NCCL_INCLUDE_DIRS_RESOLVED "${ZXHSIM_NCCL_INCLUDE_DIR}")
            endif ()
        endif ()

        if (NOT ZXHSIM_NCCL_LIBRARIES STREQUAL "")
            set(ZXHSIM_NCCL_LIBRARIES_RESOLVED ${ZXHSIM_NCCL_LIBRARIES})
        else ()
            find_library(
                ZXHSIM_NCCL_LIBRARY
                NAMES nccl
                HINTS ${_zxhsim_nccl_roots}
                PATH_SUFFIXES lib lib64)
            if (ZXHSIM_NCCL_LIBRARY)
                list(APPEND ZXHSIM_NCCL_LIBRARIES_RESOLVED "${ZXHSIM_NCCL_LIBRARY}")
            endif ()
        endif ()

        if ("${ZXHSIM_NCCL_INCLUDE_DIRS_RESOLVED}" STREQUAL "")
            message(FATAL_ERROR
                    "Backend 'mpi_cuda' requires NCCL headers, but they were not found.\n"
                    "Provide ZXHSIM_NCCL_ROOT or ZXHSIM_NCCL_INCLUDE_DIRS.")
        endif ()
        if ("${ZXHSIM_NCCL_LIBRARIES_RESOLVED}" STREQUAL "")
            message(FATAL_ERROR
                    "Backend 'mpi_cuda' requires NCCL libraries, but they were not found.\n"
                    "Provide ZXHSIM_NCCL_ROOT or ZXHSIM_NCCL_LIBRARIES.")
        endif ()

        foreach (_zxhsim_nccl_lib IN LISTS ZXHSIM_NCCL_LIBRARIES_RESOLVED)
            if (IS_ABSOLUTE "${_zxhsim_nccl_lib}")
                get_filename_component(_zxhsim_nccl_lib_dir "${_zxhsim_nccl_lib}" DIRECTORY)
                list(APPEND ZXHSIM_NCCL_LIBRARY_DIRS_RESOLVED "${_zxhsim_nccl_lib_dir}")
            endif ()
        endforeach ()
        list(REMOVE_DUPLICATES ZXHSIM_NCCL_LIBRARY_DIRS_RESOLVED)

        zxhsim_report_value("NCCL support" "ON")
        zxhsim_report_value("NCCL include dirs" "${ZXHSIM_NCCL_INCLUDE_DIRS_RESOLVED}")
        zxhsim_report_value("NCCL libraries" "${ZXHSIM_NCCL_LIBRARIES_RESOLVED}")
        zxhsim_report_value("NCCL library dirs" "${ZXHSIM_NCCL_LIBRARY_DIRS_RESOLVED}")
        target_compile_definitions(zxhsim_core PRIVATE ZXHSIM_USE_NCCL)
        target_include_directories(zxhsim_core PRIVATE ${ZXHSIM_NCCL_INCLUDE_DIRS_RESOLVED})
        target_link_libraries(zxhsim PUBLIC ${ZXHSIM_NCCL_LIBRARIES_RESOLVED})
        if (TARGET _core)
            target_link_libraries(_core PRIVATE ${ZXHSIM_NCCL_LIBRARIES_RESOLVED})
        endif ()
        if (NOT "${ZXHSIM_NCCL_LIBRARY_DIRS_RESOLVED}" STREQUAL "")
            list(APPEND ZXHSIM_EXTRA_RUNTIME_RPATHS ${ZXHSIM_NCCL_LIBRARY_DIRS_RESOLVED})
            list(REMOVE_DUPLICATES ZXHSIM_EXTRA_RUNTIME_RPATHS)
        endif ()
    else ()
        zxhsim_report_value("NCCL support" "OFF")
    endif ()

    if (USE_MPI)
        get_filename_component(ZXHSIM_ACTIVE_MPI_BACKEND_CXX "${ZXHSIM_MPI_BACKEND_CXX}" REALPATH)
        get_filename_component(ZXHSIM_ACTIVE_CUDA_HOST "${CMAKE_CUDA_HOST_COMPILER}" REALPATH)
        if (NOT ZXHSIM_ACTIVE_CUDA_HOST STREQUAL ZXHSIM_ACTIVE_MPI_BACKEND_CXX)
            message(FATAL_ERROR
                    "Backend '${ZXHSIM_BACKEND}' requires the CUDA host compiler to resolve to the backend compiler reported by the MPI wrapper.
"
                    "  MPI backend C++ compiler: ${ZXHSIM_ACTIVE_MPI_BACKEND_CXX}
"
                    "  CMAKE_CUDA_HOST_COMPILER: ${ZXHSIM_ACTIVE_CUDA_HOST}
"
                    "Use a fresh build directory if this one was previously configured with a different CUDA host compiler.")
        endif ()
    else ()
        zxhsim_toolchain_family(ZXHSIM_CUDA_TOOLCHAIN_FAMILY "${CMAKE_CUDA_COMPILER}")
        zxhsim_toolchain_family(ZXHSIM_CXX_TOOLCHAIN_FAMILY "${CMAKE_CXX_COMPILER}")
        set(ZXHSIM_CUDA_HOST_TOOLCHAIN_FAMILY "")
        if (DEFINED CMAKE_CUDA_HOST_COMPILER AND NOT CMAKE_CUDA_HOST_COMPILER STREQUAL "")
            zxhsim_toolchain_family(ZXHSIM_CUDA_HOST_TOOLCHAIN_FAMILY "${CMAKE_CUDA_HOST_COMPILER}")
        endif ()

        set(ZXHSIM_TOOLCHAIN_MISMATCH OFF)
        if (NOT ZXHSIM_CUDA_TOOLCHAIN_FAMILY STREQUAL ZXHSIM_CXX_TOOLCHAIN_FAMILY)
            set(ZXHSIM_TOOLCHAIN_MISMATCH ON)
        endif ()
        if (NOT ZXHSIM_CUDA_HOST_TOOLCHAIN_FAMILY STREQUAL ""
            AND NOT ZXHSIM_CUDA_TOOLCHAIN_FAMILY STREQUAL ZXHSIM_CUDA_HOST_TOOLCHAIN_FAMILY)
            set(ZXHSIM_TOOLCHAIN_MISMATCH ON)
        endif ()

        if (ZXHSIM_TOOLCHAIN_MISMATCH)
            if (ZXHSIM_CUDA_HOST_TOOLCHAIN_FAMILY STREQUAL "")
                set(_zxhsim_host_line "  CMAKE_CUDA_HOST_COMPILER: <auto>")
            else ()
                set(_zxhsim_host_line
                    "  CMAKE_CUDA_HOST_COMPILER: ${CMAKE_CUDA_HOST_COMPILER} [${ZXHSIM_CUDA_HOST_TOOLCHAIN_FAMILY}]")
            endif ()

            message(FATAL_ERROR
                    "Mixed CUDA/C++ toolchains detected.
"
                    "  CMAKE_CUDA_COMPILER: ${CMAKE_CUDA_COMPILER} [${ZXHSIM_CUDA_TOOLCHAIN_FAMILY}]
"
                    "  CMAKE_CXX_COMPILER: ${CMAKE_CXX_COMPILER} [${ZXHSIM_CXX_TOOLCHAIN_FAMILY}]
"
                    "${_zxhsim_host_line}
"
                    "Use a consistent toolchain family for CUDA builds.
"
                    "Recommended env vars: CXX=<host-cxx> CUDACXX=<nvcc> CUDAHOSTCXX=<host-cxx>.
"
                    "Equivalent CMake options: -DCMAKE_CXX_COMPILER=<host-cxx> -DCMAKE_CUDA_COMPILER=<nvcc> "
                    "-DCMAKE_CUDA_HOST_COMPILER=<host-cxx>.")
        endif ()
    endif ()

    zxhsim_report_value("CUDA compiler" "${CMAKE_CUDA_COMPILER}")
    zxhsim_report_value("CUDA host compiler" "${CMAKE_CUDA_HOST_COMPILER}")

    target_link_libraries(zxhsim_core PRIVATE CUB::CUB)
    target_compile_options(zxhsim_core PRIVATE $<$<COMPILE_LANGUAGE:CUDA>:-fPIC>)
    if (NOT "${ZXHSIM_CUDA_INCLUDE_DIRS}" STREQUAL "")
        target_include_directories(zxhsim_core PRIVATE ${ZXHSIM_CUDA_INCLUDE_DIRS})
        target_include_directories(zxhsim PRIVATE ${ZXHSIM_CUDA_INCLUDE_DIRS})
        if (TARGET _core)
            target_include_directories(_core PRIVATE ${ZXHSIM_CUDA_INCLUDE_DIRS})
        endif ()
    endif ()
    if (NOT "${ZXHSIM_CUDA_EXTRA_LIBRARIES}" STREQUAL "")
        target_link_libraries(zxhsim PUBLIC ${ZXHSIM_CUDA_EXTRA_LIBRARIES})
        if (TARGET _core)
            target_link_libraries(_core PRIVATE ${ZXHSIM_CUDA_EXTRA_LIBRARIES})
        endif ()
    endif ()
    if (DEFINED ZXHSIM_USING_CU_BRIDGE AND ZXHSIM_USING_CU_BRIDGE)
        if (NOT "${ZXHSIM_CU_BRIDGE_LINK_DIRECTORIES_RESOLVED}" STREQUAL "")
            target_link_directories(zxhsim PUBLIC ${ZXHSIM_CU_BRIDGE_LINK_DIRECTORIES_RESOLVED})
            if (TARGET _core)
                target_link_directories(_core PRIVATE ${ZXHSIM_CU_BRIDGE_LINK_DIRECTORIES_RESOLVED})
            endif ()
        endif ()
        if (NOT "${ZXHSIM_CU_BRIDGE_LINK_LIBRARIES_RESOLVED}" STREQUAL "")
            target_link_libraries(zxhsim PUBLIC ${ZXHSIM_CU_BRIDGE_LINK_LIBRARIES_RESOLVED})
            if (TARGET _core)
                target_link_libraries(_core PRIVATE ${ZXHSIM_CU_BRIDGE_LINK_LIBRARIES_RESOLVED})
            endif ()
        endif ()
    endif ()
    if (TARGET _core)
        set_property(TARGET _core PROPERTY LINKER_LANGUAGE CUDA)
        if (NOT "${ZXHSIM_EXTRA_RUNTIME_RPATHS}" STREQUAL "")
            set_property(TARGET _core APPEND PROPERTY BUILD_RPATH "${ZXHSIM_EXTRA_RUNTIME_RPATHS}")
            set_property(TARGET _core APPEND PROPERTY INSTALL_RPATH "${ZXHSIM_EXTRA_RUNTIME_RPATHS}")
        endif ()
        # cu-bridge CUDA linker cannot consume GCC LTO objects reliably; this can
        # drop pybind's module init symbol (PyInit__core) and break Python import.
        target_compile_options(_core PRIVATE
            $<$<COMPILE_LANGUAGE:CXX>:-fno-lto>
            $<$<COMPILE_LANGUAGE:CUDA>:-Xcompiler=-fno-lto>)
        target_link_options(_core PRIVATE -fno-lto)
    endif ()

endif ()

message("${MSG_PRFX} BACKEND_COMMON_SOURCES: ${BACKEND_COMMON_SOURCES}")
message("${MSG_PRFX} BACKEND_KERNEL_SOURCE: ${BACKEND_KERNEL_SOURCE}")
message("${MSG_PRFX} BACKEND_MEM_SOURCE: ${BACKEND_MEM_SOURCE}")
message("${MSG_PRFX} BACKEND_SV_SOURCE: ${BACKEND_SV_SOURCE}")
message("${MSG_PRFX} BACKEND_RUNTIME_SOURCE: ${BACKEND_RUNTIME_SOURCE}")
message("${MSG_PRFX} BACKEND_COMM_SOURCE: ${BACKEND_COMM_SOURCE}")
message("${MSG_PRFX} BACKEND_MEASURE_SOURCE: ${BACKEND_MEASURE_SOURCE}")
target_sources(
    zxhsim_core
    PRIVATE ${BACKEND_COMMON_SOURCES}
            ${BACKEND_KERNEL_SOURCE}
            ${BACKEND_MEM_SOURCE}
            ${BACKEND_SV_SOURCE}
            ${BACKEND_RUNTIME_SOURCE}
            ${BACKEND_COMM_SOURCE}
            ${BACKEND_MEASURE_SOURCE})

# ---------------------examples-------------------------------------------------
add_executable(driver_cat examples/cpp/driver_cat.cpp)
target_link_libraries(driver_cat zxhsim)
if (NOT "${ZXHSIM_EXTRA_RUNTIME_RPATHS}" STREQUAL "")
    set_property(TARGET driver_cat APPEND PROPERTY BUILD_RPATH "${ZXHSIM_EXTRA_RUNTIME_RPATHS}")
endif ()
if (USE_CUDA)
    # Force the final link through the CUDA driver so runtime libraries are injected
    # even when the top-level target itself only has host-language sources.
    set_property(TARGET driver_cat PROPERTY LINKER_LANGUAGE CUDA)
    target_compile_options(driver_cat PRIVATE -fno-lto)
    target_link_options(driver_cat PRIVATE -fno-lto)
endif ()
