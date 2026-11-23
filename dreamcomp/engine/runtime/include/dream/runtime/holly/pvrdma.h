// PVR-DMA (0x005F7C00..0x005F7CFF): the Holly channel that moves blocks between system RAM and
// video memory through SH-4 DMAC channel 0. As in Flycast's pvr_sb_regs.cpp do_pvr_dma
// (GPL-2.0, ADR 1): writing 1 to SB_PDST copies SB_PDLEN bytes at once (SB_PDDIR 0: system RAM
// at SB_PDSTAR to VRAM at SB_PDSTAP, 1: the reverse), marks DMAC channel 0 done, clears SB_PDST
// and raises the PVR-DMA end interrupt.
#pragma once

#include <array>
#include <cstdint>

#include "dream/runtime/holly/intc.h"
#include "dream/runtime/mem/dc_memory.h"
#include "dream/runtime/sh4/dmac.h"

namespace dream::holly {

class PvrDma final : public mem::MmioHandler {
public:
    static constexpr std::uint32_t kBase = 0x005F7C00u, kEnd = 0x005F7D00u;
    static constexpr std::uint32_t kStap = 0x00, kStar = 0x04, kLen = 0x08, kDir = 0x0C,
                                   kTsel = 0x10, kEn = 0x14, kSt = 0x18;

    PvrDma(sh4::Dmac& dmac, Intc& holly, mem::DcMemory& memory)
        : dmac_(dmac), holly_(holly), memory_(memory) {}

    std::uint32_t read(std::uint32_t addr, unsigned size) override;
    void write(std::uint32_t addr, std::uint32_t value, unsigned size) override;

    std::uint64_t transfers = 0, bytes = 0, refused = 0;

private:
    void start();
    sh4::Dmac& dmac_;
    Intc& holly_;
    mem::DcMemory& memory_;
    std::array<std::uint32_t, (kEnd - kBase) / 4> regs_{};
};

}  // namespace dream::holly
