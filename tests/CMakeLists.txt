# If leaks are found, abort() during interpreter shutdown to catch this in the CI
add_definitions(-DNB_ABORT_ON_LEAK=1)

if (NB_TEST_STABLE_ABI)
  set(NB_EXTRA_ARGS ${NB_EXTRA_ARGS} STABLE_ABI)
endif()

if (NB_TEST_SHARED_BUILD)
  set(NB_EXTRA_ARGS ${NB_EXTRA_ARGS} NB_SHARED)
endif()

# Enable extra warning flags
if (MSVC)
  add_compile_options(/W4)
elseif (CMAKE_CXX_COMPILER_ID MATCHES "Clang" OR CMAKE_CXX_COMPILER_ID MATCHES "GNU")
  add_compile_options(-Wall -Wextra -Wno-unused-local-typedefs)
endif()

nanobind_add_module(test_functions_ext test_functions.cpp ${NB_EXTRA_ARGS})
nanobind_add_module(test_classes_ext test_classes.cpp ${NB_EXTRA_ARGS})
nanobind_add_module(test_holders_ext test_holders.cpp ${NB_EXTRA_ARGS})
nanobind_add_module(test_stl_ext test_stl.cpp ${NB_EXTRA_ARGS})
nanobind_add_module(test_bind_map_ext test_stl_bind_map.cpp ${NB_EXTRA_ARGS})
nanobind_add_module(test_bind_vector_ext test_stl_bind_vector.cpp ${NB_EXTRA_ARGS})
nanobind_add_module(test_chrono_ext test_chrono.cpp ${NB_EXTRA_ARGS})
nanobind_add_module(test_enum_ext test_enum.cpp ${NB_EXTRA_ARGS})
nanobind_add_module(test_ndarray_ext test_ndarray.cpp ${NB_EXTRA_ARGS})
nanobind_add_module(test_intrusive_ext test_intrusive.cpp object.cpp object.h ${NB_EXTRA_ARGS})
nanobind_add_module(test_exception_ext test_exception.cpp ${NB_EXTRA_ARGS})
nanobind_add_module(test_make_iterator_ext test_make_iterator.cpp ${NB_EXTRA_ARGS})

find_package (Eigen3 3.3.1 NO_MODULE)
if (TARGET Eigen3::Eigen)
  nanobind_add_module(test_eigen_ext test_eigen.cpp ${NB_EXTRA_ARGS})
  target_link_libraries(test_eigen_ext PRIVATE Eigen3::Eigen)
endif()

add_library(
  inter_module
  SHARED
  inter_module.h
  inter_module.cpp
)

target_compile_definitions(inter_module PRIVATE -DSHARED_BUILD)
target_compile_features(inter_module PRIVATE cxx_std_17)
target_include_directories(inter_module PRIVATE ${NB_DIR}/include)

nanobind_add_module(test_inter_module_1_ext NOTRIM test_inter_module_1.cpp ${NB_EXTRA_ARGS})
nanobind_add_module(test_inter_module_2_ext NOTRIM test_inter_module_2.cpp ${NB_EXTRA_ARGS})
target_link_libraries(test_inter_module_1_ext PRIVATE inter_module)
target_link_libraries(test_inter_module_2_ext PRIVATE inter_module)

set(TEST_FILES
  common.py
  test_classes.py
  test_eigen.py
  test_enum.py
  test_exception.py
  test_functions.py
  test_holders.py
  test_inter_module.py
  test_intrusive.py
  test_make_iterator.py
  test_stl.py
  test_stl_bind_map.py
  test_stl_bind_vector.py
  test_chrono.py
  test_ndarray.py
)

if (NOT (CMAKE_CURRENT_SOURCE_DIR STREQUAL CMAKE_CURRENT_BINARY_DIR) OR MSVC)
  if (MSVC)
    set(OUT_DIR ${CMAKE_CURRENT_BINARY_DIR}/$<CONFIG>)
  else()
    set(OUT_DIR ${CMAKE_CURRENT_BINARY_DIR})
  endif()

  foreach(TEST_FILE IN LISTS TEST_FILES)
    set(IN_FILE ${CMAKE_CURRENT_SOURCE_DIR}/${TEST_FILE})
    set(OUT_FILE ${OUT_DIR}/${TEST_FILE})
    set(TEST_FILES_OUT ${TEST_FILES_OUT} ${OUT_FILE})
    add_custom_command(
      DEPENDS ${IN_FILE} TARGET OUTPUT ${OUT_FILE}
      COMMAND ${CMAKE_COMMAND} -E copy_if_different ${IN_FILE} ${OUT_DIR})
  endforeach()

  add_custom_target(copy-tests ALL DEPENDS ${TEST_FILES_OUT})
endif()
