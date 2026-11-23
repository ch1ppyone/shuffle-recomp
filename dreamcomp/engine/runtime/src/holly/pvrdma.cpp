#include "dream/runtime/holly/pvrdma.h"

#include <cstdio>
#include <cstdlib>

namespace dream::holly {

static const bool kTrace = std::getenv("DREAM_TRACE_PVRDMA") != nullptr;

std::uint32_t PvrDma::read(std::uint32_t addr, unsigned) {
    const std::uint32_t off = addr - kBase;
    return off < kEnd - kBase ? regs_[off >> 2] : 0;
}

void PvrDma::write(std::uint32_t addr, std::uint32_t v, unsigned) {
    const std::uint32_t off = addr - kBase;
    if (off >= kEnd - kBase)
        return;
    if (kTrace)
        std::fprintf(stderr, "pvrdma: write +%02x = %08x\n", off, v);
    if (off == kSt) {
        if (v & 1u)
            start();
        return;
    }
    regs_[off >> 2] = v;
}

void PvrDma::start() {
    if (!dmac_.ddt_ready()) {
        ++refused;
        if (kTrace)
            std::fprintf(stderr, "pvrdma: start refused, DMAOR %08x\n", dmac_.dmaor());
        return;
    }
    if (kTrace)
        std::fprintf(stderr, "pvrdma: start vram %08x ram %08x len %08x dir %u\n",
                     regs_[kStap >> 2], regs_[kStar >> 2], regs_[kLen >> 2],
                     regs_[kDir >> 2] & 1u);
    const std::uint32_t vram = regs_[kStap >> 2], ram = regs_[kStar >> 2],
                        len = regs_[kLen >> 2];
    const bool to_ram = regs_[kDir >> 2] & 1u;
    for (std::uint32_t k = 0; k + 4 <= len; k += 4) {
        if (to_ram)
            memory_.write32(ram + k, memory_.read32(vram + k));
        else
            memory_.write32(vram + k, memory_.read32(ram + k));
    }
    ++transfers;
    bytes += len;
    dmac_.complete(0);
    regs_[kSt >> 2] = 0;
    holly_.raise(Irq::PvrDma);
}

}  // namespace dream::holly
