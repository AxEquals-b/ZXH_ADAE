function(zxhsim_append_unique_items out_var)
    set(_zxhsim_items ${${out_var}})
    foreach (_zxhsim_item IN LISTS ARGN)
        if (NOT "${_zxhsim_item}" STREQUAL "")
            list(APPEND _zxhsim_items "${_zxhsim_item}")
        endif ()
    endforeach ()
    list(REMOVE_DUPLICATES _zxhsim_items)
    set(${out_var} "${_zxhsim_items}" PARENT_SCOPE)
endfunction()

function(zxhsim_append_existing_paths out_var)
    set(_zxhsim_paths ${${out_var}})
    foreach (_zxhsim_path IN LISTS ARGN)
        if (NOT "${_zxhsim_path}" STREQUAL "" AND EXISTS "${_zxhsim_path}")
            list(APPEND _zxhsim_paths "${_zxhsim_path}")
        endif ()
    endforeach ()
    list(REMOVE_DUPLICATES _zxhsim_paths)
    set(${out_var} "${_zxhsim_paths}" PARENT_SCOPE)
endfunction()

function(zxhsim_prefix_flags out_var prefix)
    set(_zxhsim_flags "")
    foreach (_zxhsim_item IN LISTS ARGN)
        if (NOT "${_zxhsim_item}" STREQUAL "")
            list(APPEND _zxhsim_flags "${prefix}${_zxhsim_item}")
        endif ()
    endforeach ()
    string(JOIN " " _zxhsim_joined ${_zxhsim_flags})
    set(${out_var} "${_zxhsim_joined}" PARENT_SCOPE)
endfunction()

function(zxhsim_library_flags out_var)
    set(_zxhsim_flags "")
    foreach (_zxhsim_item IN LISTS ARGN)
        if ("${_zxhsim_item}" STREQUAL "")
            continue()
        endif ()

        if (IS_ABSOLUTE "${_zxhsim_item}" OR "${_zxhsim_item}" MATCHES "^-.*")
            list(APPEND _zxhsim_flags "${_zxhsim_item}")
        else ()
            list(APPEND _zxhsim_flags "-l${_zxhsim_item}")
        endif ()
    endforeach ()
    string(JOIN " " _zxhsim_joined ${_zxhsim_flags})
    set(${out_var} "${_zxhsim_joined}" PARENT_SCOPE)
endfunction()

function(zxhsim_prepare_cuda_frontend)
    if (NOT USE_CUDA)
        return()
    endif ()

    set(_zxhsim_cuda_compiler_hint "")
    if (DEFINED CMAKE_CUDA_COMPILER AND NOT CMAKE_CUDA_COMPILER STREQUAL "")
        set(_zxhsim_cuda_compiler_hint "${CMAKE_CUDA_COMPILER}")
    elseif (DEFINED ENV{CUDACXX} AND NOT "$ENV{CUDACXX}" STREQUAL "")
        set(_zxhsim_cuda_compiler_hint "$ENV{CUDACXX}")
    endif ()

    if (_zxhsim_cuda_compiler_hint STREQUAL "")
        return()
    endif ()

    zxhsim_resolve_program(_zxhsim_cuda_compiler_path "${_zxhsim_cuda_compiler_hint}")
    if (NOT _zxhsim_cuda_compiler_path OR NOT EXISTS "${_zxhsim_cuda_compiler_path}")
        return()
    endif ()

    get_filename_component(_zxhsim_cuda_compiler_realpath "${_zxhsim_cuda_compiler_path}" REALPATH)
    get_filename_component(_zxhsim_cuda_compiler_name "${_zxhsim_cuda_compiler_realpath}" NAME)
    if (NOT _zxhsim_cuda_compiler_name STREQUAL "cucc")
        set(ZXHSIM_USING_CU_BRIDGE OFF CACHE INTERNAL "Whether the CUDA frontend is cu-bridge" FORCE)
        return()
    endif ()

    if (DEFINED ENV{CUDA_PATH} AND NOT "$ENV{CUDA_PATH}" STREQUAL "")
        set(_zxhsim_cu_bridge_root "$ENV{CUDA_PATH}")
    else ()
        get_filename_component(_zxhsim_cu_bridge_bin_dir "${_zxhsim_cuda_compiler_realpath}" DIRECTORY)
        get_filename_component(_zxhsim_cu_bridge_root "${_zxhsim_cu_bridge_bin_dir}" DIRECTORY)
    endif ()

    if (NOT EXISTS "${_zxhsim_cu_bridge_root}/include")
        message(FATAL_ERROR
                "USE_CUDA=ON with CUDACXX=cucc requires CUDA_PATH (or the compiler path) to resolve to a cu-bridge root with an include directory.\n"
                "  CUDACXX: ${_zxhsim_cuda_compiler_realpath}\n"
                "  CUDA_PATH root candidate: ${_zxhsim_cu_bridge_root}")
    endif ()

    set(_zxhsim_cu_bridge_runtime_root "")
    if (DEFINED ZXHSIM_CU_BRIDGE_RUNTIME_ROOT AND NOT ZXHSIM_CU_BRIDGE_RUNTIME_ROOT STREQUAL "")
        set(_zxhsim_cu_bridge_runtime_root "${ZXHSIM_CU_BRIDGE_RUNTIME_ROOT}")
    elseif (DEFINED ENV{ZXHSIM_CU_BRIDGE_RUNTIME_ROOT}
        AND NOT "$ENV{ZXHSIM_CU_BRIDGE_RUNTIME_ROOT}" STREQUAL "")
        set(_zxhsim_cu_bridge_runtime_root "$ENV{ZXHSIM_CU_BRIDGE_RUNTIME_ROOT}")
    elseif (_zxhsim_cu_bridge_root MATCHES "(.+)/tools/cu-bridge/?$")
        set(_zxhsim_cu_bridge_runtime_root "${CMAKE_MATCH_1}")
    endif ()

    if (_zxhsim_cu_bridge_runtime_root STREQUAL "" OR NOT EXISTS "${_zxhsim_cu_bridge_runtime_root}")
        message(FATAL_ERROR
                "USE_CUDA=ON with CUDACXX=cucc requires a runtime prefix.\n"
                "CMake tried to derive it from CUDA_PATH/CUDACXX using the standard '.../tools/cu-bridge' layout.\n"
                "If your installation uses a different layout, set ZXHSIM_CU_BRIDGE_RUNTIME_ROOT.\n"
                "  CUDA frontend root: ${_zxhsim_cu_bridge_root}\n"
                "  runtime root candidate: ${_zxhsim_cu_bridge_runtime_root}")
    endif ()

    set(_zxhsim_cuda_arch_list "")
    if (DEFINED CMAKE_CUDA_ARCHITECTURES AND NOT CMAKE_CUDA_ARCHITECTURES STREQUAL "")
        set(_zxhsim_cuda_arch_list "${CMAKE_CUDA_ARCHITECTURES}")
    elseif (DEFINED ENV{CUDAARCHS} AND NOT "$ENV{CUDAARCHS}" STREQUAL "")
        set(_zxhsim_cuda_arch_list "$ENV{CUDAARCHS}")
        set(CMAKE_CUDA_ARCHITECTURES "$ENV{CUDAARCHS}" CACHE STRING "CUDA architectures" FORCE)
    endif ()
    string(REPLACE "," ";" _zxhsim_cuda_arch_list "${_zxhsim_cuda_arch_list}")
    if ("${_zxhsim_cuda_arch_list}" STREQUAL "")
        message(FATAL_ERROR
                "USE_CUDA=ON with CUDACXX=cucc requires an explicit CUDA architecture list.\n"
                "Set CUDAARCHS or CMAKE_CUDA_ARCHITECTURES before configuring.")
    endif ()
    list(GET _zxhsim_cuda_arch_list 0 _zxhsim_primary_cuda_arch)

    set(_zxhsim_cu_bridge_system_include_dirs "")
    if (DEFINED ZXHSIM_CU_BRIDGE_SYSTEM_INCLUDE_DIRS AND NOT ZXHSIM_CU_BRIDGE_SYSTEM_INCLUDE_DIRS STREQUAL "")
        set(_zxhsim_cu_bridge_system_include_dirs ${ZXHSIM_CU_BRIDGE_SYSTEM_INCLUDE_DIRS})
    else ()
        zxhsim_append_existing_paths(
            _zxhsim_cu_bridge_system_include_dirs
            "${_zxhsim_cu_bridge_runtime_root}/include"
            "${_zxhsim_cu_bridge_runtime_root}/include/hcr")
    endif ()

    set(_zxhsim_cu_bridge_link_directories "")
    if (DEFINED ZXHSIM_CU_BRIDGE_LINK_DIRECTORIES AND NOT ZXHSIM_CU_BRIDGE_LINK_DIRECTORIES STREQUAL "")
        set(_zxhsim_cu_bridge_link_directories ${ZXHSIM_CU_BRIDGE_LINK_DIRECTORIES})
    else ()
        zxhsim_append_existing_paths(_zxhsim_cu_bridge_link_directories "${_zxhsim_cu_bridge_runtime_root}/lib")
    endif ()

    if (NOT DEFINED ZXHSIM_CU_BRIDGE_LINK_LIBRARIES OR ZXHSIM_CU_BRIDGE_LINK_LIBRARIES STREQUAL "")
        message(FATAL_ERROR
                "USE_CUDA=ON with CUDACXX=cucc requires ZXHSIM_CU_BRIDGE_LINK_LIBRARIES.\n"
                "Set it to a semicolon-separated list of cu-bridge runtime libraries, for example:\n"
                "  export ZXHSIM_CU_BRIDGE_LINK_LIBRARIES='runtime_cu;ToolsExt_cu;hccompiler;hcruntime'")
    endif ()

    set(_zxhsim_cu_bridge_include_dirs "${_zxhsim_cu_bridge_root}/include")
    zxhsim_append_unique_items(_zxhsim_cu_bridge_include_dirs ${_zxhsim_cu_bridge_system_include_dirs})

    zxhsim_prefix_flags(_zxhsim_cu_bridge_system_includes "-isystem " ${_zxhsim_cu_bridge_system_include_dirs})
    zxhsim_prefix_flags(_zxhsim_cu_bridge_link_dirs_flags "-L" ${_zxhsim_cu_bridge_link_directories})
    zxhsim_library_flags(_zxhsim_cu_bridge_link_lib_flags ${ZXHSIM_CU_BRIDGE_LINK_LIBRARIES})
    string(JOIN " " _zxhsim_cu_bridge_link_flags
        ${_zxhsim_cu_bridge_link_dirs_flags}
        ${_zxhsim_cu_bridge_link_lib_flags})

    set(_zxhsim_cu_bridge_compiler_output
        "#$ PATH=$ENV{PATH}\n"
        "#$ LIBRARIES=${_zxhsim_cu_bridge_link_flags}\n"
        "#$ INCLUDES=-I${_zxhsim_cu_bridge_root}/include\n"
        "#$ SYSTEM_INCLUDES=${_zxhsim_cu_bridge_system_includes}\n"
        "#$ cmdline -arch compute_${_zxhsim_primary_cuda_arch}\n"
        "${_zxhsim_cuda_compiler_realpath} CMakeCUDACompilerId.o -o a.out ${_zxhsim_cu_bridge_link_flags}\n")

    set(ZXHSIM_USING_CU_BRIDGE ON CACHE INTERNAL "Whether the CUDA frontend is cu-bridge" FORCE)
    set(ZXHSIM_CU_BRIDGE_ROOT "${_zxhsim_cu_bridge_root}" CACHE INTERNAL "Resolved cu-bridge root" FORCE)
    set(ZXHSIM_CU_BRIDGE_RUNTIME_ROOT "${_zxhsim_cu_bridge_runtime_root}" CACHE INTERNAL
        "Resolved cu-bridge runtime root" FORCE)
    set(ZXHSIM_CU_BRIDGE_INCLUDE_DIRS "${_zxhsim_cu_bridge_include_dirs}" CACHE INTERNAL
        "Implicit include directories required by cu-bridge" FORCE)
    set(ZXHSIM_CU_BRIDGE_SYSTEM_INCLUDE_DIRS_RESOLVED "${_zxhsim_cu_bridge_system_include_dirs}" CACHE INTERNAL
        "System include directories consumed by cu-bridge" FORCE)
    set(ZXHSIM_CU_BRIDGE_LINK_DIRECTORIES_RESOLVED "${_zxhsim_cu_bridge_link_directories}" CACHE INTERNAL
        "Link directories consumed by cu-bridge" FORCE)
    set(ZXHSIM_CU_BRIDGE_LINK_LIBRARIES_RESOLVED "${ZXHSIM_CU_BRIDGE_LINK_LIBRARIES}" CACHE INTERNAL
        "Link libraries consumed by cu-bridge" FORCE)

    set(CMAKE_CUDA_COMPILER "${_zxhsim_cuda_compiler_realpath}" CACHE FILEPATH "CUDA compiler" FORCE)
    set(CUDAToolkit_ROOT "${_zxhsim_cu_bridge_root}" CACHE PATH "CUDA toolkit root" FORCE)
    set(CMAKE_CUDA_COMPILER_FORCED TRUE CACHE BOOL "Use a preseeded CUDA compiler configuration" FORCE)
    set(CMAKE_CUDA_COMPILER_ID_RUN TRUE CACHE INTERNAL "" FORCE)
    set(CMAKE_CUDA_COMPILER_ID "NVIDIA" CACHE INTERNAL "" FORCE)
    set(CMAKE_CUDA_COMPILER_VERSION "12.0" CACHE STRING "Synthetic CUDA compiler version for cu-bridge" FORCE)
    set(CMAKE_CUDA_COMPILER_TOOLKIT_ROOT "${_zxhsim_cu_bridge_root}" CACHE PATH
        "CUDA toolkit root for cu-bridge" FORCE)
    set(CMAKE_CUDA_COMPILER_LIBRARY_ROOT "${_zxhsim_cu_bridge_root}" CACHE PATH
        "CUDA device library root for cu-bridge" FORCE)
    set(CMAKE_CUDA_COMPILER_TOOLKIT_LIBRARY_ROOT "${_zxhsim_cu_bridge_root}" CACHE PATH
        "CUDA toolkit library root for cu-bridge" FORCE)
    set(CMAKE_CUDA_COMPILER_PRODUCED_OUTPUT "${_zxhsim_cu_bridge_compiler_output}" PARENT_SCOPE)
endfunction()
