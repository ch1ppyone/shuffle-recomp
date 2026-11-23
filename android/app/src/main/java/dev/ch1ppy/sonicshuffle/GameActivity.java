package dev.ch1ppy.sonicshuffle;

import android.os.Build;
import android.os.Bundle;
import android.view.View;
import android.view.WindowInsets;
import android.view.WindowInsetsController;
import android.view.WindowManager;
import android.widget.RelativeLayout;

import org.libsdl.app.SDLActivity;

import java.util.ArrayList;
import java.util.List;

/** The SDL host for the game. MainActivity has already prepared the data and chosen a disc. */
public class GameActivity extends SDLActivity {
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        configureSurfaceScale();
        hideSystemBars();
        if (mLayout != null) {
            mLayout.addView(new TouchOverlay(this),
                    new RelativeLayout.LayoutParams(
                            RelativeLayout.LayoutParams.MATCH_PARENT,
                            RelativeLayout.LayoutParams.MATCH_PARENT));
        }
    }

    /**
     * The guest frame is 640x480. Presenting it at a phone's native 2856x1280 costs several times
     * the fill rate of the console for no visible detail, and on an emulator without a GPU
     * (SwiftShader) it is the difference between playable and a slideshow. Give the SDL surface a
     * fixed 960x720 buffer and a 4:3 on-screen rectangle; the compositor scales it, which is
     * essentially free compared with writing 3.6 megapixels every frame. The game's own
     * letterboxing then has a 4:3 target, so its pixels are not stretched.
     */
    private void configureSurfaceScale() {
        if (mSurface == null || mLayout == null) return;
        android.util.DisplayMetrics dm = getResources().getDisplayMetrics();
        int screenW = Math.max(dm.widthPixels, dm.heightPixels);
        int screenH = Math.min(dm.widthPixels, dm.heightPixels);
        int viewH = screenH;
        int viewW = Math.min(screenW, viewH * 4 / 3);
        RelativeLayout.LayoutParams lp = new RelativeLayout.LayoutParams(viewW, viewH);
        lp.addRule(RelativeLayout.CENTER_IN_PARENT);
        mSurface.setLayoutParams(lp);
        // An emulator still has no GPU in the guest (SwiftShader), so give it the guest's own
        // 640x480 instead of 960x720. A phone gets the sharper 960x720; both are scaled by the
        // compositor, never by the software renderer.
        boolean emulator = Build.FINGERPRINT.contains("generic")
                || Build.FINGERPRINT.contains("emulator")
                || Build.MODEL.contains("sdk_gphone")
                || Build.MODEL.contains("Emulator")
                || Build.HARDWARE.contains("ranchu");
        mSurface.getHolder().setFixedSize(emulator ? 640 : 960, emulator ? 480 : 720);
        // The opaque window behind the surface is what shows in the pillarboxes.
        getWindow().getDecorView().setBackgroundColor(android.graphics.Color.BLACK);
    }

    private void hideSystemBars() {
        if (Build.VERSION.SDK_INT >= 30) {
            WindowInsetsController c = getWindow().getInsetsController();
            if (c != null) {
                c.hide(WindowInsets.Type.systemBars());
                c.setSystemBarsBehavior(
                        WindowInsetsController.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE);
            }
        } else {
            getWindow().getDecorView().setSystemUiVisibility(
                    View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
                            | View.SYSTEM_UI_FLAG_FULLSCREEN
                            | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
                            | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
                            | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION
                            | View.SYSTEM_UI_FLAG_LAYOUT_STABLE);
        }
    }

    @Override
    public void setOrientationBis(int w, int h, boolean resizable, String hint) {
        // The manifest fixes the game to landscape.
    }

    @Override
    public void onWindowFocusChanged(boolean hasFocus) {
        super.onWindowFocusChanged(hasFocus);
        // SDLMain/immersive can lose the flags when the system bars appear; re-apply on focus.
        if (hasFocus) hideSystemBars();
    }

    @Override
    protected String[] getArguments() {
        List<String> args = new ArrayList<>();
        args.add("--config");
        args.add(MainActivity.sConfig.getAbsolutePath());
        if (MainActivity.sDisc != null) {
            args.add("--disc");
            args.add(MainActivity.sDisc.getAbsolutePath());
        }
        if (MainActivity.sVmu != null) {
            args.add("--vmu");
            args.add(MainActivity.sVmu.getAbsolutePath());
        }
        // The guest is 640x480. Scale 1 is the default; 2 is the optional supersampled image.
        args.add("--scale");
        args.add(MainActivity.sScale == 2 ? "2" : "1");
        args.add("--window");
        args.add("--android-base");
        args.add(MainActivity.sBase.getAbsolutePath());
        return args.toArray(new String[0]);
    }
}
