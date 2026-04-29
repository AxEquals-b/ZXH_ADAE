#pragma once

#include <cstddef>
#include <string>

namespace ZXHSim
{

void init(int *argc = nullptr, char ***argv = nullptr);
void finalize();
bool active();
size_t rank();
size_t nprocs();

void log(const char *msg);
void log(const std::string &msg);
[[noreturn]] void abort(const char *msg);
[[noreturn]] void abort(const std::string &msg);

} // namespace ZXHSim
