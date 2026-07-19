cmake_minimum_required(VERSION 3.10)
project(VectorDB CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# Add include directory
include_directories(include)

# Find Threads for httplib
find_package(Threads REQUIRED)

add_executable(vectordb src/main.cpp)
target_link_libraries(vectordb Threads::Threads)

