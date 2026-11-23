cmake_minimum_required(VERSION 3.24)
project(shuffle_recomp VERSION 0.1.0 LANGUAGES C CXX)

# The project has its own desktop launcher. The framework's pre-game frontend and in-game
# Escape overlay stay disabled, so Escape never opens a hidden framework menu.
set(DREAMCOMP_FRONTEND OFF CACHE BOOL "Use the project launcher instead of dreamcomp frontend" FORCE)

set(DREAMCOMP_DIR "${CMAKE_CURRENT_SOURCE_DIR}/dreamcomp" CACHE PATH "dreamcomp checkout")
if(NOT EXISTS "${DREAMCOMP_DIR}/cmake/DreamcompPort.cmake")
  message(FATAL_ERROR "dreamcomp not found at ${DREAMCOMP_DIR}")
endif()

if(ANDROID AND NOT Vulkan_LIBRARY)
  file(GLOB _ndk_prebuilt "${CMAKE_ANDROID_NDK}/toolchains/llvm/prebuilt/*")
  if(_ndk_prebuilt)
    list(GET _ndk_prebuilt 0 _ndk_prebuilt)
    set(Vulkan_INCLUDE_DIR "${_ndk_prebuilt}/sysroot/usr/include" CACHE PATH "Android Vulkan headers")
    file(GLOB _vulkan_lib "${_ndk_prebuilt}/sysroot/usr/lib/*-linux-android*/${CMAKE_ANDROID_API}/libvulkan.so")
    if(_vulkan_lib)
      list(GET _vulkan_lib 0 _vulkan_lib)
      set(Vulkan_LIBRARY "${_vulkan_lib}" CACHE FILEPATH "Android Vulkan stub")
    endif()
  endif()
endif()

add_subdirectory(${DREAMCOMP_DIR} dreamcomp)
add_subdirectory(game)
