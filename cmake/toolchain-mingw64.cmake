# Cross-compile the Windows x86_64 port from macOS with MinGW-w64.
#
#   cmake -S . -B build-win -G Ninja \
#     -DCMAKE_TOOLCHAIN_FILE=cmake/toolchain-mingw64.cmake \
#     -DDREAM_RENDERER=ON -DDREAMCOMP_FRONTEND=OFF \
#     -DSDL3_DIR="$PWD/.dreamcomp/win-deps/sdl3/lib/cmake/SDL3"
#
# The Windows build needs a Windows SDL3 (built with this same toolchain, see
# tools/build-windows-deps.sh) and a Vulkan import library. The host's macOS
# SDL3/Vulkan must not be picked up: that is why the search root is the staged
# dependency directory and not /opt/homebrew.
set(CMAKE_SYSTEM_NAME Windows)
set(CMAKE_SYSTEM_PROCESSOR x86_64)

set(_mingw x86_64-w64-mingw32)
set(CMAKE_C_COMPILER ${_mingw}-gcc)
set(CMAKE_CXX_COMPILER ${_mingw}-g++)
set(CMAKE_RC_COMPILER ${_mingw}-windres)
set(CMAKE_AR ${_mingw}-ar)
set(CMAKE_RANLIB ${_mingw}-ranlib)

# Self-contained executables: libstdc++, libgcc and winpthread go into the .exe, so the port is
# the exe plus SDL3.dll (already copied by the build) and nothing from the MinGW installation.
set(CMAKE_EXE_LINKER_FLAGS_INIT "-static")

# Where tools/build-windows-deps.sh stages SDL3 and the Vulkan import library.
set(DREAM_WINDOWS_DEPS "${CMAKE_CURRENT_LIST_DIR}/../.dreamcomp/win-deps" CACHE PATH
    "Staged Windows dependencies (SDL3, Vulkan import library)")

set(CMAKE_FIND_ROOT_PATH "${DREAM_WINDOWS_DEPS}" "${DREAM_WINDOWS_DEPS}/sdl3")
set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)
set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_PACKAGE ONLY)

# FindVulkan needs both halves explicitly in a cross build (the module searches for a Windows SDK,
# which does not exist on this host).
set(Vulkan_INCLUDE_DIR "${DREAM_WINDOWS_DEPS}/include" CACHE PATH "Windows Vulkan headers")
set(Vulkan_LIBRARY "${DREAM_WINDOWS_DEPS}/lib/libvulkan-1.a" CACHE FILEPATH
    "Windows Vulkan import library")
