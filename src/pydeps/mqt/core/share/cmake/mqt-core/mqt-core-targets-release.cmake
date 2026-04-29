#----------------------------------------------------------------
# Generated CMake target import file for configuration "Release".
#----------------------------------------------------------------

# Commands may need to know the format version.
set(CMAKE_IMPORT_FILE_VERSION 1)

# Import target "MQT::CoreIR" for configuration "Release"
set_property(TARGET MQT::CoreIR APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(MQT::CoreIR PROPERTIES
  IMPORTED_LOCATION_RELEASE "${_IMPORT_PREFIX}/lib64/libmqt-core-ir.so.3.4.1"
  IMPORTED_SONAME_RELEASE "libmqt-core-ir.so.3.4"
  )

list(APPEND _cmake_import_check_targets MQT::CoreIR )
list(APPEND _cmake_import_check_files_for_MQT::CoreIR "${_IMPORT_PREFIX}/lib64/libmqt-core-ir.so.3.4.1" )

# Import target "MQT::CoreQASM" for configuration "Release"
set_property(TARGET MQT::CoreQASM APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(MQT::CoreQASM PROPERTIES
  IMPORTED_LOCATION_RELEASE "${_IMPORT_PREFIX}/lib64/libmqt-core-qasm.so.3.4.1"
  IMPORTED_SONAME_RELEASE "libmqt-core-qasm.so.3.4"
  )

list(APPEND _cmake_import_check_targets MQT::CoreQASM )
list(APPEND _cmake_import_check_files_for_MQT::CoreQASM "${_IMPORT_PREFIX}/lib64/libmqt-core-qasm.so.3.4.1" )

# Import target "MQT::CoreAlgorithms" for configuration "Release"
set_property(TARGET MQT::CoreAlgorithms APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(MQT::CoreAlgorithms PROPERTIES
  IMPORTED_LINK_DEPENDENT_LIBRARIES_RELEASE "MQT::CoreCircuitOptimizer"
  IMPORTED_LOCATION_RELEASE "${_IMPORT_PREFIX}/lib64/libmqt-core-algorithms.so.3.4.1"
  IMPORTED_SONAME_RELEASE "libmqt-core-algorithms.so.3.4"
  )

list(APPEND _cmake_import_check_targets MQT::CoreAlgorithms )
list(APPEND _cmake_import_check_files_for_MQT::CoreAlgorithms "${_IMPORT_PREFIX}/lib64/libmqt-core-algorithms.so.3.4.1" )

# Import target "MQT::CoreCircuitOptimizer" for configuration "Release"
set_property(TARGET MQT::CoreCircuitOptimizer APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(MQT::CoreCircuitOptimizer PROPERTIES
  IMPORTED_LOCATION_RELEASE "${_IMPORT_PREFIX}/lib64/libmqt-core-circuit-optimizer.so.3.4.1"
  IMPORTED_SONAME_RELEASE "libmqt-core-circuit-optimizer.so.3.4"
  )

list(APPEND _cmake_import_check_targets MQT::CoreCircuitOptimizer )
list(APPEND _cmake_import_check_files_for_MQT::CoreCircuitOptimizer "${_IMPORT_PREFIX}/lib64/libmqt-core-circuit-optimizer.so.3.4.1" )

# Import target "MQT::CoreDS" for configuration "Release"
set_property(TARGET MQT::CoreDS APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(MQT::CoreDS PROPERTIES
  IMPORTED_LOCATION_RELEASE "${_IMPORT_PREFIX}/lib64/libmqt-core-ds.so.3.4.1"
  IMPORTED_SONAME_RELEASE "libmqt-core-ds.so.3.4"
  )

list(APPEND _cmake_import_check_targets MQT::CoreDS )
list(APPEND _cmake_import_check_files_for_MQT::CoreDS "${_IMPORT_PREFIX}/lib64/libmqt-core-ds.so.3.4.1" )

# Import target "MQT::CoreDD" for configuration "Release"
set_property(TARGET MQT::CoreDD APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(MQT::CoreDD PROPERTIES
  IMPORTED_LOCATION_RELEASE "${_IMPORT_PREFIX}/lib64/libmqt-core-dd.so.3.4.1"
  IMPORTED_SONAME_RELEASE "libmqt-core-dd.so.3.4"
  )

list(APPEND _cmake_import_check_targets MQT::CoreDD )
list(APPEND _cmake_import_check_files_for_MQT::CoreDD "${_IMPORT_PREFIX}/lib64/libmqt-core-dd.so.3.4.1" )

# Import target "MQT::CoreZX" for configuration "Release"
set_property(TARGET MQT::CoreZX APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(MQT::CoreZX PROPERTIES
  IMPORTED_LOCATION_RELEASE "${_IMPORT_PREFIX}/lib64/libmqt-core-zx.so.3.4.1"
  IMPORTED_SONAME_RELEASE "libmqt-core-zx.so.3.4"
  )

list(APPEND _cmake_import_check_targets MQT::CoreZX )
list(APPEND _cmake_import_check_files_for_MQT::CoreZX "${_IMPORT_PREFIX}/lib64/libmqt-core-zx.so.3.4.1" )

# Import target "MQT::CoreNAFoMaC" for configuration "Release"
set_property(TARGET MQT::CoreNAFoMaC APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(MQT::CoreNAFoMaC PROPERTIES
  IMPORTED_LINK_DEPENDENT_LIBRARIES_RELEASE "spdlog::spdlog;MQT::CoreQDMINaDeviceGen"
  IMPORTED_LOCATION_RELEASE "${_IMPORT_PREFIX}/lib64/libmqt-core-na-fomac.so.3.4.1"
  IMPORTED_SONAME_RELEASE "libmqt-core-na-fomac.so.3.4"
  )

list(APPEND _cmake_import_check_targets MQT::CoreNAFoMaC )
list(APPEND _cmake_import_check_files_for_MQT::CoreNAFoMaC "${_IMPORT_PREFIX}/lib64/libmqt-core-na-fomac.so.3.4.1" )

# Import target "MQT::CoreNA" for configuration "Release"
set_property(TARGET MQT::CoreNA APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(MQT::CoreNA PROPERTIES
  IMPORTED_LOCATION_RELEASE "${_IMPORT_PREFIX}/lib64/libmqt-core-na.so.3.4.1"
  IMPORTED_SONAME_RELEASE "libmqt-core-na.so.3.4"
  )

list(APPEND _cmake_import_check_targets MQT::CoreNA )
list(APPEND _cmake_import_check_files_for_MQT::CoreNA "${_IMPORT_PREFIX}/lib64/libmqt-core-na.so.3.4.1" )

# Import target "MQT::CoreQDMICommon" for configuration "Release"
set_property(TARGET MQT::CoreQDMICommon APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(MQT::CoreQDMICommon PROPERTIES
  IMPORTED_LOCATION_RELEASE "${_IMPORT_PREFIX}/lib64/libmqt-core-qdmi-common.so.3.4.1"
  IMPORTED_SONAME_RELEASE "libmqt-core-qdmi-common.so.3.4"
  )

list(APPEND _cmake_import_check_targets MQT::CoreQDMICommon )
list(APPEND _cmake_import_check_files_for_MQT::CoreQDMICommon "${_IMPORT_PREFIX}/lib64/libmqt-core-qdmi-common.so.3.4.1" )

# Import target "MQT::CoreQDMI_DDSIM_Device" for configuration "Release"
set_property(TARGET MQT::CoreQDMI_DDSIM_Device APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(MQT::CoreQDMI_DDSIM_Device PROPERTIES
  IMPORTED_LINK_DEPENDENT_LIBRARIES_RELEASE "MQT::CoreDD;MQT::CoreQASM;MQT::CoreCircuitOptimizer;MQT::CoreQDMICommon;spdlog::spdlog"
  IMPORTED_LOCATION_RELEASE "${_IMPORT_PREFIX}/lib64/libmqt-core-qdmi-ddsim-device.so.3.4.1"
  IMPORTED_SONAME_RELEASE "libmqt-core-qdmi-ddsim-device.so.3.4"
  )

list(APPEND _cmake_import_check_targets MQT::CoreQDMI_DDSIM_Device )
list(APPEND _cmake_import_check_files_for_MQT::CoreQDMI_DDSIM_Device "${_IMPORT_PREFIX}/lib64/libmqt-core-qdmi-ddsim-device.so.3.4.1" )

# Import target "MQT::CoreQDMIScDevice" for configuration "Release"
set_property(TARGET MQT::CoreQDMIScDevice APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(MQT::CoreQDMIScDevice PROPERTIES
  IMPORTED_LINK_DEPENDENT_LIBRARIES_RELEASE "MQT::CoreQDMICommon;spdlog::spdlog"
  IMPORTED_LOCATION_RELEASE "${_IMPORT_PREFIX}/lib64/libmqt-core-qdmi-sc-device.so.3.4.1"
  IMPORTED_SONAME_RELEASE "libmqt-core-qdmi-sc-device.so.3.4"
  )

list(APPEND _cmake_import_check_targets MQT::CoreQDMIScDevice )
list(APPEND _cmake_import_check_files_for_MQT::CoreQDMIScDevice "${_IMPORT_PREFIX}/lib64/libmqt-core-qdmi-sc-device.so.3.4.1" )

# Import target "MQT::CoreQDMIScDeviceDyn" for configuration "Release"
set_property(TARGET MQT::CoreQDMIScDeviceDyn APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(MQT::CoreQDMIScDeviceDyn PROPERTIES
  IMPORTED_LINK_DEPENDENT_LIBRARIES_RELEASE "MQT::CoreQDMIScDevice;MQT::CoreQDMICommon;spdlog::spdlog"
  IMPORTED_LOCATION_RELEASE "${_IMPORT_PREFIX}/lib64/libmqt-core-qdmi-sc-device-dyn.so.3.4.1"
  IMPORTED_SONAME_RELEASE "libmqt-core-qdmi-sc-device-dyn.so.3.4"
  )

list(APPEND _cmake_import_check_targets MQT::CoreQDMIScDeviceDyn )
list(APPEND _cmake_import_check_files_for_MQT::CoreQDMIScDeviceDyn "${_IMPORT_PREFIX}/lib64/libmqt-core-qdmi-sc-device-dyn.so.3.4.1" )

# Import target "MQT::CoreQDMINaDeviceGen" for configuration "Release"
set_property(TARGET MQT::CoreQDMINaDeviceGen APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(MQT::CoreQDMINaDeviceGen PROPERTIES
  IMPORTED_LINK_DEPENDENT_LIBRARIES_RELEASE "spdlog::spdlog"
  IMPORTED_LOCATION_RELEASE "${_IMPORT_PREFIX}/lib64/libmqt-core-qdmi-na-device-gen.so.3.4.1"
  IMPORTED_SONAME_RELEASE "libmqt-core-qdmi-na-device-gen.so.3.4"
  )

list(APPEND _cmake_import_check_targets MQT::CoreQDMINaDeviceGen )
list(APPEND _cmake_import_check_files_for_MQT::CoreQDMINaDeviceGen "${_IMPORT_PREFIX}/lib64/libmqt-core-qdmi-na-device-gen.so.3.4.1" )

# Import target "MQT::CoreQDMINaDevice" for configuration "Release"
set_property(TARGET MQT::CoreQDMINaDevice APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(MQT::CoreQDMINaDevice PROPERTIES
  IMPORTED_LINK_DEPENDENT_LIBRARIES_RELEASE "MQT::CoreQDMICommon;spdlog::spdlog"
  IMPORTED_LOCATION_RELEASE "${_IMPORT_PREFIX}/lib64/libmqt-core-qdmi-na-device.so.3.4.1"
  IMPORTED_SONAME_RELEASE "libmqt-core-qdmi-na-device.so.3.4"
  )

list(APPEND _cmake_import_check_targets MQT::CoreQDMINaDevice )
list(APPEND _cmake_import_check_files_for_MQT::CoreQDMINaDevice "${_IMPORT_PREFIX}/lib64/libmqt-core-qdmi-na-device.so.3.4.1" )

# Import target "MQT::CoreQDMINaDeviceDyn" for configuration "Release"
set_property(TARGET MQT::CoreQDMINaDeviceDyn APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(MQT::CoreQDMINaDeviceDyn PROPERTIES
  IMPORTED_LINK_DEPENDENT_LIBRARIES_RELEASE "MQT::CoreQDMINaDevice;MQT::CoreQDMICommon;spdlog::spdlog"
  IMPORTED_LOCATION_RELEASE "${_IMPORT_PREFIX}/lib64/libmqt-core-qdmi-na-device-dyn.so.3.4.1"
  IMPORTED_SONAME_RELEASE "libmqt-core-qdmi-na-device-dyn.so.3.4"
  )

list(APPEND _cmake_import_check_targets MQT::CoreQDMINaDeviceDyn )
list(APPEND _cmake_import_check_files_for_MQT::CoreQDMINaDeviceDyn "${_IMPORT_PREFIX}/lib64/libmqt-core-qdmi-na-device-dyn.so.3.4.1" )

# Import target "MQT::CoreQDMIDriver" for configuration "Release"
set_property(TARGET MQT::CoreQDMIDriver APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(MQT::CoreQDMIDriver PROPERTIES
  IMPORTED_LINK_DEPENDENT_LIBRARIES_RELEASE "MQT::CoreQDMINaDevice;MQT::CoreQDMIScDevice;MQT::CoreQDMI_DDSIM_Device;spdlog::spdlog"
  IMPORTED_LOCATION_RELEASE "${_IMPORT_PREFIX}/lib64/libmqt-core-qdmi-driver.so.3.4.1"
  IMPORTED_SONAME_RELEASE "libmqt-core-qdmi-driver.so.3.4"
  )

list(APPEND _cmake_import_check_targets MQT::CoreQDMIDriver )
list(APPEND _cmake_import_check_files_for_MQT::CoreQDMIDriver "${_IMPORT_PREFIX}/lib64/libmqt-core-qdmi-driver.so.3.4.1" )

# Import target "MQT::CoreFoMaC" for configuration "Release"
set_property(TARGET MQT::CoreFoMaC APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(MQT::CoreFoMaC PROPERTIES
  IMPORTED_LINK_DEPENDENT_LIBRARIES_RELEASE "spdlog::spdlog"
  IMPORTED_LOCATION_RELEASE "${_IMPORT_PREFIX}/lib64/libmqt-core-fomac.so.3.4.1"
  IMPORTED_SONAME_RELEASE "libmqt-core-fomac.so.3.4"
  )

list(APPEND _cmake_import_check_targets MQT::CoreFoMaC )
list(APPEND _cmake_import_check_files_for_MQT::CoreFoMaC "${_IMPORT_PREFIX}/lib64/libmqt-core-fomac.so.3.4.1" )

# Commands beyond this point should not need to know the version.
set(CMAKE_IMPORT_FILE_VERSION)
