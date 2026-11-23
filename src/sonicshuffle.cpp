#include "dreamcomp/port.h"

namespace {

const dreamcomp::PortInfo kInfo = [] {
    dreamcomp::PortInfo port;
    port.id = "sonicshuffle";
    port.title = "Sonic Shuffle";
    return port;
}();

dreamcomp::RegisterPort g_register(kInfo);

}  // namespace
