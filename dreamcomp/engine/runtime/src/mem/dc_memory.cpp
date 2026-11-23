#include "dream/runtime/mem/dc_memory.h"

#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <type_traits>

namespace dream::mem {

// ---- FaultLog ----------------------------------------------------------------------------------

void FaultLog::record(std::uint32_t addr, unsigned size, bool write) {
    ++total_;
    const std::uint64_t key =
        (static_cast<std::uint64_t>(addr) << 8) | (size << 1) | (write ? 1u : 0u);
    auto it = map_.find(key);
    if (it != map_.end()) {
        ++it->second.count;
        return;
    }
    if (map_.size() >= kMaxUnique) {
        ++dropped_;
        return;
    }
    map_.emplace(key, FaultRecord{addr, size, write, 1});
}

std::vector<FaultRecord> FaultLog::records() const {
    std::vector<FaultRecord> out;
    out.reserve(map_.size());
    for (const auto& [k, r] : map_) out.push_back(r);
    std::sort(out.begin(), out.end(), [](const FaultRecord& a, const FaultRecord& b) {
        return a.addr != b.addr ? a.addr < b.addr : a.write < b.write;
    });
    return out;
}

std::string FaultLog::format() const {
    std::string s;
    char buf[96];
    for (const auto& r : records()) {
        std::snprintf(buf, sizeof buf, "0x%08x %s%u x%llu\n", r.addr, r.write ? "w" : "r", r.size,
                      static_cast<unsigned long long>(r.count));
        s += buf;
    }
    if (dropped_) {
        std::snprintf(buf, sizeof buf, "(%llu more unique faults not recorded)\n",
                      static_cast<unsigned long long>(dropped_));
        s += buf;
    }
    return s;
}

void FaultLog::clear() {
    map_.clear();
    total_ = dropped_ = 0;
}

// ---- DcMemory ----------------------------------------------------------------------------------

DcMemory::DcMemory()
    : ram_(new std::uint8_t[kRamSize]()),
      vram_(new std::uint8_t[kVramSize]()),
      aram_(new std::uint8_t[kAramSize]()),
      bios_(new std::uint8_t[kBiosSize]()),
      flash_(new std::uint8_t[kFlashSize]()),
      ocram_(new std::uint8_t[kOcramSize]()) {
    refresh_fast_path();
}

void DcMemory::map_mmio(std::uint32_t lo, std::uint32_t hi, MmioHandler* h) {
    phys_mmio_.push_back({lo, hi, h});
}

void DcMemory::map_p4(std::uint32_t lo, std::uint32_t hi, MmioHandler* h) {
    p4_mmio_.push_back({lo, hi, h});
}

MmioHandler* DcMemory::find(const std::vector<Range>& t, std::uint32_t a) const noexcept {
    for (const auto& r : t)
        if (a >= r.lo && a < r.hi)
            return r.h;
    return nullptr;
}

// Same interleave as the hardware's 64-bit bus and Flycast's pvr_map32 (GPL-2.0, ADR 1): bank 0
// words go to even 64-bit slots, bank 1 words to odd ones.
std::uint32_t DcMemory::vram_map32(std::uint32_t offset32) noexcept {
    constexpr std::uint32_t kBankBit = 0x400000u;
    constexpr std::uint32_t kStaticBits = (kVramSize - 1) - (kBankBit * 2 - 1) + 3;
    constexpr std::uint32_t kOffsetBits = (kBankBit - 1) & ~3u;
    const std::uint32_t bank = (offset32 & kBankBit) / kBankBit;
    std::uint32_t rv = offset32 & kStaticBits;
    rv |= (offset32 & kOffsetBits) * 2;
    rv |= bank * 4;
    return rv;
}

DcMemory::Target DcMemory::resolve(std::uint32_t a, unsigned size, bool write) {
    Target t;
    // P4: store queues, then the on-chip module registers.
    if ((a & 0xE0000000u) == 0xE0000000u) {
        if (a < 0xE4000000u) {
            t.kind = Target::kBytes;
            t.bytes = reinterpret_cast<std::uint8_t*>(&sq_[(a >> 5) & 1][0]) + (a & 0x1Cu);
            return t;
        }
        if (MmioHandler* h = find(p4_mmio_, a)) {
            t.kind = Target::kMmio;
            if (on_device_access)
                on_device_access();
            t.mmio = h;
            t.mmio_addr = a;
            return t;
        }
        if (on_unmapped)
            on_unmapped(a, size, write);
        faults_.record(a, size, write);
        return t;
    }
    // Operand cache as RAM (CCR.ORA): 8 KB in two 4 KB halves selected by bit 13, mirrored over
    // 0x7C000000-0x7FFFFFFF (SH7750 hardware manual, cache chapter).
    if ((a & 0xFC000000u) == 0x7C000000u) {
        t.kind = Target::kBytes;
        t.bytes = ocram_.get() + (((a >> 13) & 1u) << 12) + (a & 0xFFFu);
        return t;
    }
    const std::uint32_t phys = a & 0x1FFFFFFFu;
    switch (phys >> 26) {
        case 0: {  // area 0: ROM, flash, registers, sound RAM
            const std::uint32_t off = phys & 0x03FFFFFFu;
            if (off < 0x00200000u) {
                t.kind = Target::kBytes;
                t.bytes = bios_.get() + off;
                return t;
            }
            if (off < 0x00400000u) {
                t.kind = Target::kBytes;
                t.bytes = flash_.get() + (off & (kFlashSize - 1));
                return t;
            }
            if (off >= 0x00800000u && off < 0x01000000u) {
                t.kind = Target::kBytes;
                t.bytes = aram_.get() + (off & (kAramSize - 1));
                return t;
            }
            break;  // registers: table below
        }
        case 1: {  // area 1: VRAM, 64-bit view at +0x0000000, 32-bit view at +0x1000000, mirrors
            const std::uint32_t off = phys & 0x007FFFFFu;
            t.kind = Target::kBytes;
            t.bytes = vram_.get() + ((phys & 0x01000000u) ? vram_map32(off) : off);
            return t;
        }
        case 3: {  // area 3: main RAM and its three mirrors
            t.kind = Target::kBytes;
            t.bytes = ram_.get() + (phys & (kRamSize - 1));
            return t;
        }
        default:
            break;
    }
    if (MmioHandler* h = find(phys_mmio_, phys)) {
        t.kind = Target::kMmio;
        if (on_device_access)
            on_device_access();
        t.mmio = h;
        t.mmio_addr = phys;
        return t;
    }
    if (on_unmapped)
        on_unmapped(a, size, write);
    faults_.record(a, size, write);
    return t;
}

template <typename T>
T DcMemory::load(std::uint32_t a) {
    const Target t = resolve(a, sizeof(T), false);
    if (t.kind == Target::kBytes) {
        T v;
        std::memcpy(&v, t.bytes, sizeof(T));
        return v;
    }
    if (t.kind == Target::kMmio) {
        // Reading a device is not free either: a status register that clears on read, or a FIFO,
        // changes state, and a replay would read it a second time. Conservative, and the count of
        // skipped calls says how much it costs.
        if (journaling)
            journal_saw_device = true;
        return static_cast<T>(t.mmio->read(t.mmio_addr, sizeof(T)));
    }
    return T{};
}

template <typename T>
void DcMemory::store(std::uint32_t a, T v) {
    const Target t = resolve(a, sizeof(T), true);
    if (t.kind == Target::kBytes) {
        if (journaling) {
            std::uint64_t old = 0;
            std::memcpy(&old, t.bytes, sizeof(T));
            journal.push_back({a, old,
                               static_cast<std::uint64_t>(static_cast<std::make_unsigned_t<T>>(v)),
                               sizeof(T)});
        }
        std::memcpy(t.bytes, &v, sizeof(T));
        mark_vram(t.bytes, sizeof(T));
        note_ram_write(a, static_cast<std::uint64_t>(static_cast<std::make_unsigned_t<T>>(v)),
                       sizeof(T));
        return;
    }
    if (t.kind == Target::kMmio) {
        // A device write has effects outside memory: it cannot be put back, and repeating it would
        // tell the device twice. Note it and let the caller abandon the comparison.
        if (journaling)
            journal_saw_device = true;
        t.mmio->write(t.mmio_addr, static_cast<std::uint32_t>(v), sizeof(T));
    }
}

void DcMemory::undo_journal() {
    // Newest first, so a location written more than once ends up with what it held at the start.
    for (auto it = journal.rbegin(); it != journal.rend(); ++it) {
        const Target t = resolve(it->addr, it->size, true);
        if (t.kind == Target::kBytes)
            std::memcpy(t.bytes, &it->old_value, it->size);
    }
    journal.clear();
}

void DcMemory::redo_journal() {
    for (const WriteRecord& w : journal) {
        const Target t = resolve(w.addr, w.size, true);
        if (t.kind == Target::kBytes)
            std::memcpy(t.bytes, &w.new_value, w.size);
    }
}

std::uint8_t DcMemory::read8_slow(std::uint32_t a) {
    return load<std::uint8_t>(a);
}
std::uint16_t DcMemory::read16_slow(std::uint32_t a) {
    return load<std::uint16_t>(a);
}
std::uint32_t DcMemory::read32_slow(std::uint32_t a) {
    if ((a & 0xFFFFFFC0u) == 0xFF000000u) {  // CCN: MMU and cache control, exception registers
        switch (a & 0x3Cu) {
            case 0x20:
                return tra;
            case 0x24:
                return expevt;
            case 0x28:
                return intevt;
            case 0x38:
                return qacr_[0];
            case 0x3C:
                return qacr_[1];
            default:
                return ccn_[(a >> 2) & 15];
        }
    }
    if ((a >> 24) == 0xF6u || (a >> 24) == 0xF7u)
        return utlb_read(a);
    return load<std::uint32_t>(a);
}
std::uint64_t DcMemory::read64_slow(std::uint32_t a) {
    const Target t = resolve(a, 8, false);
    if (t.kind == Target::kBytes) {
        std::uint64_t v;
        std::memcpy(&v, t.bytes, 8);
        return v;
    }
    if (t.kind == Target::kMmio)
        return static_cast<std::uint64_t>(t.mmio->read(t.mmio_addr, 4)) |
               (static_cast<std::uint64_t>(t.mmio->read(t.mmio_addr + 4, 4)) << 32);
    return 0;
}
void DcMemory::write8_slow(std::uint32_t a, std::uint8_t v) {
    store<std::uint8_t>(a, v);
}
void DcMemory::write16_slow(std::uint32_t a, std::uint16_t v) {
    store<std::uint16_t>(a, v);
}
void DcMemory::write32_slow(std::uint32_t a, std::uint32_t v) {
    static const bool trace_ccn = std::getenv("DREAM_TRACE_SQ") != nullptr;
    if (trace_ccn && (a & 0xFF000000u) == 0xFF000000u && (a & 0x00FFFFC0u) == 0)
        std::fprintf(stderr, "ccn: write32 %08x = %08x\n", a, v);
    if ((a & 0xFFFFFFC0u) == 0xFF000000u) {
        switch (a & 0x3Cu) {
            case 0x20:
                tra = v & 0x3FCu;
                return;
            case 0x24:
                expevt = v & 0xFFFu;
                return;
            case 0x28:
                intevt = v & 0xFFFu;
                return;
            case 0x38:
                set_qacr(0, v);
                return;
            case 0x3C:
                set_qacr(1, v);
                return;
            default:
                ccn_[(a >> 2) & 15] = v;
                return;  // MMUCR, CCR, PTEH/PTEL/TTB/TEA/PTEA: stored, no effect
        }
    }
    if ((a >> 24) == 0xF6u || (a >> 24) == 0xF7u) {
        utlb_write(a, v);
        return;
    }
    store<std::uint32_t>(a, v);
}

// Flycast sh4_mmr.cpp WriteMem_P4 0xF6/0xF7 and mmu.cpp UTLB_Sync. PTEL keeps V in bit 8 and D
// in bit 2; the address array returns them at bits 8 and 9.
void DcMemory::utlb_write(std::uint32_t a, std::uint32_t v) noexcept {
    constexpr std::uint32_t kV = 1u << 8, kD = 1u << 2;
    const unsigned e = (a >> 8) & 63;
    const auto set_vd = [&](unsigned i) {
        utlb_data_[i] = (utlb_data_[i] & ~(kV | kD)) | (v & kV) | (((v >> 9) & 1u) << 2);
    };
    if ((a >> 24) == 0xF6u) {
        if (a & 0x80u) {  // associative write: every entry whose VPN matches
            for (unsigned i = 0; i < 64; ++i)
                if (((utlb_addr_[i] ^ v) & 0xFFFFFC00u) == 0) {
                    set_vd(i);
                    utlb_sync(i);
                }
            return;
        }
        utlb_addr_[e] = v & 0xFFFFFCFFu;
        set_vd(e);
    } else {
        if (a & 0x800000u)
            return;  // assistance array (PTEA): not needed for the queues
        utlb_data_[e] = v;
    }
    utlb_sync(e);
}

std::uint32_t DcMemory::utlb_read(std::uint32_t a) const noexcept {
    const unsigned e = (a >> 8) & 63;
    if ((a >> 24) == 0xF6u)
        return utlb_addr_[e] | (((utlb_data_[e] >> 2) & 1u) << 9) | (utlb_data_[e] & (1u << 8));
    return utlb_data_[e];
}

void DcMemory::utlb_sync(unsigned e) noexcept {
    if (!(utlb_data_[e] & (1u << 8)))
        return;
    if ((utlb_addr_[e] & 0xFC000000u) == 0xE0000000u)
        sq_remap_[(utlb_addr_[e] >> 20) & 0x3F] = utlb_data_[e] & 0x1FFFFC00u;
}
void DcMemory::write64_slow(std::uint32_t a, std::uint64_t v) {
    const Target t = resolve(a, 8, true);
    if (t.kind == Target::kBytes) {
        const std::uint32_t lo = static_cast<std::uint32_t>(v);
        const std::uint32_t hi = static_cast<std::uint32_t>(v >> 32);
        if (journaling) {
            std::uint32_t old_lo = 0, old_hi = 0;
            std::memcpy(&old_lo, t.bytes, 4);
            std::memcpy(&old_hi, t.bytes + 4, 4);
            journal.push_back({a, old_lo, lo, 4});
            journal.push_back({a + 4, old_hi, hi, 4});
        }
        std::memcpy(t.bytes, &v, 8);
        // Two 4-byte reports, the same split the device path below uses, so a pair written here
        // hashes identically to the same pair written as two stores.
        note_ram_write(a, lo, 4);
        note_ram_write(a + 4, hi, 4);
        return;
    }
    if (t.kind == Target::kMmio) {
        t.mmio->write(t.mmio_addr, static_cast<std::uint32_t>(v), 4);
        t.mmio->write(t.mmio_addr + 4, static_cast<std::uint32_t>(v >> 32), 4);
    }
}

void DcMemory::sq_write32(std::uint32_t a, std::uint32_t v) {
    sq_[(a >> 5) & 1][(a >> 2) & 7] = v;
}

// PREF @Rn with Rn in the store-queue area: the 32 bytes of SQ0 or SQ1 (address bit 5) land at
// physical (QACRn.AREA << 26) | (Rn & 0x03FFFFE0); SH7750 manual 4.6 and Flycast storeq.cpp.
void DcMemory::sq_flush(std::uint32_t a) {
    const unsigned n = (a >> 5) & 1;
    const std::uint32_t dest = (ccn_[0x10 >> 2] & 1u)  // MMUCR.AT: the UTLB maps the queues
                                   ? sq_remap_[(a >> 20) & 0x3F] | (a & 0xFFFE0u)
                                   : (qacr_[n] << 24) | (a & 0x03FFFFE0u);
    const std::uint32_t* words = sq_[n];
    static const bool trace_sq = std::getenv("DREAM_TRACE_SQ") != nullptr;
    if (trace_sq)
        std::fprintf(stderr, "sq: flush %08x -> %08x qacr %08x w0 %08x w1 %08x\n", a, dest,
                     qacr_[n], words[0], words[1]);
    const Target t = resolve(dest, 4, true);
    if (t.kind == Target::kBytes) {
        if (journaling)
            for (unsigned i = 0; i < 8; ++i) {
                std::uint32_t old = 0;
                std::memcpy(&old, t.bytes + 4 * i, 4);
                journal.push_back({dest + 4 * i, old, words[i], 4});
            }
        std::memcpy(t.bytes, words, 32);
        mark_vram(t.bytes, 32);
        // A burst into RAM is eight stores as far as anything watching memory is concerned. Until
        // this was here the hash and the watch saw none of them.
        if (tracing_writes())
            for (unsigned i = 0; i < 8; ++i) note_ram_write(dest + 4 * i, words[i], 4);
        return;
    }
    if (t.kind == Target::kMmio) {
        // A burst into a device is how a title hands the graphics hardware a display list. It
        // cannot be taken back and must not be sent twice, so a function that does one cannot be
        // replayed; without this the comparison sends every display list to the Tile Accelerator
        // twice and then blames the emitter for the difference.
        if (journaling)
            journal_saw_device = true;
        t.mmio->write_burst(t.mmio_addr, words);
    }
}

}  // namespace dream::mem
