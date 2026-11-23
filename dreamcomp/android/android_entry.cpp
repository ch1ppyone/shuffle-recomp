// Android entry point for the dreamcomp port.
//
// SDLActivity loads libmain.so and calls this exported SDL_main. The desktop entry point is
// main() in boot_main.cpp; the build renames it to dream_main (see DreamAddGame.cmake), so the
// only work here is adapting Android's launch to the runtime's command line:
//
//   * run on a thread with a large stack, like SDL's own examples and the Vita/Android ports:
//     SDLActivity's thread is small and the recompiled guest reserves space for deep C++ frames;
//   * send stderr to a file, since a native stderr does not reach logcat and a crash would leave
//     no diagnostics;
//   * consume --android-base so relative paths a player or mod uses stay inside app storage.
#include <android/log.h>
#include <jni.h>
#include <pthread.h>
#include <unistd.h>

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>

#include "dream/render/input.h"

extern int dream_main(int argc, char** argv);

namespace {

#define SS_LOGI(...) __android_log_print(ANDROID_LOG_INFO, "SonicShuffle", __VA_ARGS__)

struct MainArgs {
    int argc;
    char** argv;
    int rc;
};

void* run_dream_main(void* opaque) {
    auto* args = static_cast<MainArgs*>(opaque);
    args->rc = dream_main(args->argc, args->argv);
    return nullptr;
}

}  // namespace

extern "C" __attribute__((visibility("default"))) int SDL_main(int argc, char** argv) {
    SS_LOGI("SDL_main argc=%d", argc);

    // --android-base DIR comes from MainActivity. It is not a runtime flag: strip it before the
    // launcher parses the rest, and use it for the working directory and the log.
    const char* base = nullptr;
    std::vector<char*> kept;
    kept.reserve(static_cast<std::size_t>(argc) + 1);
    kept.push_back(argv[0]);
    for (int i = 1; i < argc; ++i) {
        if (std::strcmp(argv[i], "--android-base") == 0 && i + 1 < argc) {
            base = argv[++i];
            continue;
        }
        kept.push_back(argv[i]);
    }
    kept.push_back(nullptr);

    if (base && *base) {
        if (chdir(base) != 0)
            SS_LOGI("chdir(%s) failed", base);
        char log_path[4096];
        std::snprintf(log_path, sizeof log_path, "%s/sonicshuffle.log", base);
        if (std::freopen(log_path, "w", stderr)) {
            std::setvbuf(stderr, nullptr, _IOLBF, 0);
            // The runtime writes its diagnostics (GPU name, renderer counters, report) to stdout.
            // Send that to the same file rather than dropping it into a console Android does not
            // have; sharing the descriptor keeps the two streams in order.
            dup2(fileno(stderr), fileno(stdout));
            std::setvbuf(stdout, nullptr, _IOLBF, 0);
        }
    }

    for (int i = 0; i < argc; ++i)
        SS_LOGI("argv[%d]=%s", i, argv[i]);

    MainArgs args{static_cast<int>(kept.size()) - 1, kept.data(), 1};
    pthread_attr_t attr;
    if (pthread_attr_init(&attr) == 0) {
        // 32 MiB: same figure as the Vita/Android dreamcomp ports; the guest itself uses its own
        // 16 MiB arena, this covers the host-side C++ frames of the recompiled code.
        pthread_attr_setstacksize(&attr, 32u << 20);
        pthread_t thread;
        if (pthread_create(&thread, &attr, run_dream_main, &args) == 0) {
            pthread_join(thread, nullptr);
            pthread_attr_destroy(&attr);
            SS_LOGI("dream_main returned %d", args.rc);
            return args.rc;
        }
        pthread_attr_destroy(&attr);
    }
    SS_LOGI("could not start the game thread; running on SDL's thread");
    return dream_main(args.argc, args.argv);
}

// TouchOverlay.nativeButton(button, down). The Java view decides the on-screen regions and draws
// them; the pad itself lives here, so it is visible to the next guest frame no matter which
// Android view has focus. The order is the overlay's, which is PadControl's own order:
// A, B, X, Y, START, UP, DOWN, LEFT, RIGHT, L, R.
extern "C" JNIEXPORT void JNICALL
Java_dev_ch1ppy_sonicshuffle_TouchOverlay_nativeButton(JNIEnv*, jclass, jint button,
                                                       jboolean down) {
    static constexpr dream::render::PadControl kMap[] = {
        dream::render::PadControl::A,          dream::render::PadControl::B,
        dream::render::PadControl::X,          dream::render::PadControl::Y,
        dream::render::PadControl::Start,      dream::render::PadControl::Up,
        dream::render::PadControl::Down,       dream::render::PadControl::Left,
        dream::render::PadControl::Right,      dream::render::PadControl::LeftTrigger,
        dream::render::PadControl::RightTrigger,
    };
    if (button < 0 || static_cast<std::size_t>(button) >= sizeof kMap / sizeof kMap[0])
        return;
    const bool pressed = down == JNI_TRUE;
    dream::render::set_touch_control(kMap[button], pressed);
    // The default keyboard bindings map the arrow keys to both the d-pad and the analog stick;
    // a touch D-pad must do the same or a game that steers with the stick (the board) ignores it.
    switch (kMap[button]) {
        case dream::render::PadControl::Up:
            dream::render::set_touch_control(dream::render::PadControl::StickUp, pressed);
            break;
        case dream::render::PadControl::Down:
            dream::render::set_touch_control(dream::render::PadControl::StickDown, pressed);
            break;
        case dream::render::PadControl::Left:
            dream::render::set_touch_control(dream::render::PadControl::StickLeft, pressed);
            break;
        case dream::render::PadControl::Right:
            dream::render::set_touch_control(dream::render::PadControl::StickRight, pressed);
            break;
        default:
            break;
    }
}
