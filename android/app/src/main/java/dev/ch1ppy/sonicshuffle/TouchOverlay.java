package dev.ch1ppy.sonicshuffle;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.Path;
import android.graphics.Typeface;
import android.view.MotionEvent;
import android.view.View;

/**
 * On-screen Dreamcast pad drawn over the SDL surface. It is the full pad, not just A/B:
 *
 *   left:  D-pad (also drives the analog stick, like the keyboard bindings), START above it
 *   right: Xbox-style diamond — Y top, X left, B right, A bottom — with L/R at the top corners
 *
 * A touch is written straight into the engine's pad (nativeButton -> set_touch_control), not
 * synthesised as a KeyEvent: those depended on Android focus and on the keyboard mapping and
 * were unreliable. Buttons light up while held; a release is delayed 110 ms so a quick tap spans
 * at least one guest VBlank poll.
 */
final class TouchOverlay extends View {
    private static final int BTN_A = 0;
    private static final int BTN_B = 1;
    private static final int BTN_X = 2;
    private static final int BTN_Y = 3;
    private static final int BTN_START = 4;
    private static final int BTN_UP = 5;
    private static final int BTN_DOWN = 6;
    private static final int BTN_LEFT = 7;
    private static final int BTN_RIGHT = 8;
    private static final int BTN_L = 9;
    private static final int BTN_R = 10;
    private static final int BTN_COUNT = 11;

    // Matches dream::render::PadControl order: A, B, X, Y, Start, Up, Down, Left, Right, L, R.
    private static native void nativeButton(int button, boolean down);

    private static final long RELEASE_DELAY_MS = 110;

    private final Paint fill = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint pressedFill = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint stroke = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint text = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Path triangle = new Path();
    private final int[] pointerButton = new int[20];
    private final int[] holdCount = new int[BTN_COUNT];
    private final boolean[] pressed = new boolean[BTN_COUNT];
    private final float density;

    private float padX, padY, padRadius;
    private float faceCx, faceCy, faceR, faceGap;
    private float startX, startY, startW, startH;
    private float lx, ly, rx, ry, lrR;

    TouchOverlay(Context context) {
        super(context);
        density = getResources().getDisplayMetrics().density;
        for (int i = 0; i < pointerButton.length; ++i) pointerButton[i] = -1;

        fill.setStyle(Paint.Style.FILL);
        fill.setColor(Color.argb(48, 255, 255, 255));
        pressedFill.setStyle(Paint.Style.FILL);
        pressedFill.setColor(Color.argb(150, 255, 196, 32));
        stroke.setStyle(Paint.Style.STROKE);
        stroke.setStrokeWidth(2f * density);
        stroke.setColor(Color.argb(150, 255, 255, 255));
        text.setColor(Color.argb(225, 255, 255, 255));
        text.setTextAlign(Paint.Align.CENTER);
        text.setTypeface(Typeface.create(Typeface.DEFAULT, Typeface.BOLD));
        text.setTextSize(15f * density);
        setWillNotDraw(false);
        setFocusable(false);
        setClickable(true);
    }

    @Override
    protected void onSizeChanged(int w, int h, int oldw, int oldh) {
        super.onSizeChanged(w, h, oldw, oldh);
        float unit = Math.min(w, h);
        padRadius = unit * 0.105f;
        padX = padRadius * 1.5f + 16f * density;
        padY = h - padRadius * 1.5f - 16f * density;

        faceR = unit * 0.050f;
        // Keep a visible gap between the face buttons. A gap below 2R makes the circles
        // overlap and the A/B/X/Y cluster reads as one blob on a phone screen.
        faceGap = faceR * 2.0f;
        // Anchor the whole diamond by its outer edges. The extra bottom margin lifts the
        // cluster above the gesture bar instead of spreading it across the lower corner.
        faceCx = w - faceGap - faceR - 24f * density;
        faceCy = h - faceGap - faceR - 48f * density;

        // START sits above the D-pad, not in the middle of the screen.
        startW = unit * 0.105f;
        startH = unit * 0.045f;
        startX = padX;
        startY = padY - padRadius * 1.45f - startH * 0.8f;

        // Shoulder buttons at the top corners.
        lrR = faceR * 0.72f;
        lx = lrR + 16f * density;
        ly = lrR + 16f * density;
        rx = w - lrR - 16f * density;
        ry = lrR + 16f * density;
    }

    // Xbox diamond: Y top, X left, B right, A bottom.
    private float ax() { return faceCx; }
    private float ay() { return faceCy + faceGap; }
    private float bx() { return faceCx + faceGap; }
    private float by() { return faceCy; }
    private float xx() { return faceCx - faceGap; }
    private float xy() { return faceCy; }
    private float yx() { return faceCx; }
    private float yy() { return faceCy - faceGap; }

    private int hitButton(float x, float y) {
        if (Math.hypot(x - ax(), y - ay()) <= faceR * 1.2f) return BTN_A;
        if (Math.hypot(x - bx(), y - by()) <= faceR * 1.2f) return BTN_B;
        if (Math.hypot(x - xx(), y - xy()) <= faceR * 1.2f) return BTN_X;
        if (Math.hypot(x - yx(), y - yy()) <= faceR * 1.2f) return BTN_Y;
        if (Math.hypot(x - lx, y - ly) <= lrR * 1.2f) return BTN_L;
        if (Math.hypot(x - rx, y - ry) <= lrR * 1.2f) return BTN_R;
        if (Math.abs(x - startX) <= startW * 0.6f
                && Math.abs(y - startY) <= startH * 1.1f) return BTN_START;

        float dx = x - padX, dy = y - padY;
        if (Math.hypot(dx, dy) <= padRadius * 1.55f) {
            if (Math.abs(dx) < padRadius * 0.28f && Math.abs(dy) < padRadius * 0.28f) return -1;
            if (Math.abs(dx) > Math.abs(dy)) return dx < 0 ? BTN_LEFT : BTN_RIGHT;
            return dy < 0 ? BTN_UP : BTN_DOWN;
        }
        return -1;
    }

    private void press(int button) {
        if (button < 0 || button >= BTN_COUNT) return;
        if (holdCount[button]++ == 0) {
            pressed[button] = true;
            nativeButton(button, true);
            invalidate();
        }
    }

    private void release(int button) {
        if (button < 0 || button >= BTN_COUNT) return;
        if (holdCount[button] > 0 && --holdCount[button] == 0) {
            pressed[button] = false;
            nativeButton(button, false);
            invalidate();
        }
    }

    private void releaseLater(int button) {
        if (button >= 0) postDelayed(() -> release(button), RELEASE_DELAY_MS);
    }

    private void updatePointer(int id, int button) {
        if (id < 0 || id >= pointerButton.length) return;
        int old = pointerButton[id];
        if (old == button) return;
        pointerButton[id] = button;
        if (button >= 0) press(button);
        if (old >= 0) releaseLater(old);
    }

    @Override
    public boolean onTouchEvent(MotionEvent event) {
        int w = getWidth(), h = getHeight();
        switch (event.getActionMasked()) {
            case MotionEvent.ACTION_DOWN:
            case MotionEvent.ACTION_POINTER_DOWN:
            case MotionEvent.ACTION_MOVE: {
                for (int i = 0; i < event.getPointerCount(); ++i) {
                    int id = event.getPointerId(i);
                    updatePointer(id, hitButton(event.getX(i), event.getY(i)));
                }
                return true;
            }
            case MotionEvent.ACTION_UP:
            case MotionEvent.ACTION_POINTER_UP: {
                int index = event.getActionIndex();
                updatePointer(event.getPointerId(index), -1);
                return true;
            }
            case MotionEvent.ACTION_CANCEL: {
                for (int i = 0; i < event.getPointerCount(); ++i)
                    updatePointer(event.getPointerId(i), -1);
                return true;
            }
            default:
                return true;
        }
    }

    @Override
    protected void onDetachedFromWindow() {
        removeCallbacks(null);
        for (int i = 0; i < pointerButton.length; ++i) pointerButton[i] = -1;
        for (int b = 0; b < BTN_COUNT; ++b) {
            if (holdCount[b] > 0) {
                holdCount[b] = 0;
                pressed[b] = false;
                nativeButton(b, false);
            }
        }
        super.onDetachedFromWindow();
    }

    // Xbox colours; L/R/START stay neutral so the face buttons read at a glance.
    private int buttonColor(int button) {
        switch (button) {
            case BTN_A: return Color.rgb(76, 175, 80);    // green
            case BTN_B: return Color.rgb(229, 57, 53);    // red
            case BTN_X: return Color.rgb(30, 136, 229);   // blue
            case BTN_Y: return Color.rgb(253, 216, 53);   // yellow
            case BTN_L:
            case BTN_R: return Color.rgb(210, 215, 225);
            default: return Color.rgb(245, 245, 245);      // START
        }
    }

    private void drawRoundButton(Canvas c, float x, float y, float radius, int button, String label) {
        int rgb = buttonColor(button);
        Paint body = new Paint(fill);
        body.setColor(Color.argb(pressed[button] ? 245 : 180,
                Color.red(rgb), Color.green(rgb), Color.blue(rgb)));
        c.drawCircle(x, y, radius, body);
        c.drawCircle(x, y, radius, stroke);
        Paint p = new Paint(text);
        p.setTextSize(label.length() > 1 ? 10f * density : 15f * density);
        p.setColor(button == BTN_Y ? Color.rgb(28, 28, 28) : Color.WHITE);
        c.drawText(label, x, y + (label.length() > 1 ? 3.5f : 5f) * density, p);
    }

    private void drawPad(Canvas c) {
        c.drawCircle(padX, padY, padRadius * 1.45f, fill);
        c.drawCircle(padX, padY, padRadius * 1.45f, stroke);
        float arm = padRadius * 0.55f, half = padRadius * 0.34f;
        float[] xs = {padX, padX, padX - arm, padX + arm};
        float[] ys = {padY - arm, padY + arm, padY, padY};
        int[] buttons = {BTN_UP, BTN_DOWN, BTN_LEFT, BTN_RIGHT};
        for (int i = 0; i < 4; ++i) {
            Paint p = pressed[buttons[i]] ? pressedFill : fill;
            c.drawRoundRect(xs[i] - half, ys[i] - half, xs[i] + half, ys[i] + half,
                    half * 0.5f, half * 0.5f, p);
            c.drawRoundRect(xs[i] - half, ys[i] - half, xs[i] + half, ys[i] + half,
                    half * 0.5f, half * 0.5f, stroke);
        }
        drawArrow(c, padX, padY - padRadius, padRadius * 0.20f, 0, pressed[BTN_UP]);
        drawArrow(c, padX, padY + padRadius, padRadius * 0.20f, 180, pressed[BTN_DOWN]);
        drawArrow(c, padX - padRadius, padY, padRadius * 0.20f, -90, pressed[BTN_LEFT]);
        drawArrow(c, padX + padRadius, padY, padRadius * 0.20f, 90, pressed[BTN_RIGHT]);
    }

    private void drawArrow(Canvas c, float x, float y, float size, float angleDeg, boolean on) {
        c.save();
        c.rotate(angleDeg, x, y);
        triangle.reset();
        triangle.moveTo(x, y - size);
        triangle.lineTo(x - size * 0.8f, y + size * 0.6f);
        triangle.lineTo(x + size * 0.8f, y + size * 0.6f);
        triangle.close();
        Paint p = new Paint(Paint.ANTI_ALIAS_FLAG);
        p.setColor(on ? Color.argb(235, 255, 196, 32) : Color.argb(170, 255, 255, 255));
        c.drawPath(triangle, p);
        c.restore();
    }

    @Override
    protected void onDraw(Canvas c) {
        super.onDraw(c);
        drawPad(c);
        drawRoundButton(c, ax(), ay(), faceR, BTN_A, "A");
        drawRoundButton(c, bx(), by(), faceR, BTN_B, "B");
        drawRoundButton(c, xx(), xy(), faceR, BTN_X, "X");
        drawRoundButton(c, yx(), yy(), faceR, BTN_Y, "Y");
        drawRoundButton(c, lx, ly, lrR, BTN_L, "L");
        drawRoundButton(c, rx, ry, lrR, BTN_R, "R");

        c.drawRoundRect(startX - startW * 0.5f, startY - startH * 0.5f,
                startX + startW * 0.5f, startY + startH * 0.5f,
                startH * 0.5f, startH * 0.5f, pressed[BTN_START] ? pressedFill : fill);
        c.drawRoundRect(startX - startW * 0.5f, startY - startH * 0.5f,
                startX + startW * 0.5f, startY + startH * 0.5f,
                startH * 0.5f, startH * 0.5f, stroke);
        Paint small = new Paint(text);
        small.setTextSize(11f * density);
        c.drawText("START", startX, startY + 4f * density, small);
    }
}
