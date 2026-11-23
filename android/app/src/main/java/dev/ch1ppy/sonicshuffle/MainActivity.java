package dev.ch1ppy.sonicshuffle;

import android.app.Activity;
import android.app.AlertDialog;
import android.app.ProgressDialog;
import android.content.Intent;
import android.content.SharedPreferences;
import android.database.Cursor;
import android.graphics.Color;
import android.graphics.Typeface;
import android.net.Uri;
import android.os.Bundle;
import android.provider.OpenableColumns;
import android.util.Log;
import android.view.Gravity;
import android.view.View;
import android.widget.ArrayAdapter;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.Spinner;
import android.widget.TextView;
import android.widget.Toast;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.util.Locale;

/**
 * Launcher and first-run setup.
 *
 * The APK carries the files the recompiled executable refers to beside its TOML (the boot binary
 * and the SUBPROG overlays, about 11 MB). They are extracted into the app's external files
 * directory once, so the desktop layout is preserved on the device:
 *
 *   .../files/data/game/sonicshuffle.toml
 *   .../files/data/game/extracted/fs/1ST_READ.BIN
 *   .../files/data/extracted/disc/fs/SUBPROG/*.BIN
 *
 * The disc image is not bundled: the player puts a CHD into .../files/iso/ with adb, or picks it
 * here and it is copied there. GameActivity then passes the absolute paths to the native runtime.
 *
 */
public class MainActivity extends Activity {
    private static final String TAG = "SonicShuffle";
    private static final int PICK_CHD = 100;
    private static final String PREFS = "sonicshuffle";

    static File sBase;
    static File sConfig;
    static File sDisc;
    static File sVmu;
    static File sData;
    static int sScale = 1;

    private File isoDir;
    private File savesDir;
    private SharedPreferences prefs;
    private TextView status;
    private Button play;
    private Spinner scaleChooser;
    private boolean extracting;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        prefs = getSharedPreferences(PREFS, MODE_PRIVATE);
        sScale = prefs.getInt("scale", 1) == 2 ? 2 : 1;

        sBase = getExternalFilesDir(null);
        if (sBase == null) sBase = getFilesDir();
        sData = new File(sBase, "data");
        isoDir = new File(sBase, "iso");
        savesDir = new File(sBase, "saves");
        //noinspection ResultOfMethodCallIgnored
        isoDir.mkdirs();
        //noinspection ResultOfMethodCallIgnored
        savesDir.mkdirs();

        sConfig = new File(sData, "game/sonicshuffle.toml");

        if (!new File(sData, "game/extracted/fs/1ST_READ.BIN").isFile()) {
            extractBundledData();
        } else {
            showLauncher();
        }
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (status != null) refreshStatus();
    }

    private void extractBundledData() {
        extracting = true;
        ProgressDialog dialog = new ProgressDialog(this);
        dialog.setMessage("Extracting game data…");
        dialog.setCancelable(false);
        dialog.show();
        new Thread(() -> {
            String error = null;
            try {
                copyAssetTree("data", sData);
            } catch (IOException e) {
                Log.e(TAG, "asset extraction failed", e);
                error = e.getMessage();
            }
            final String message = error;
            runOnUiThread(() -> {
                dialog.dismiss();
                extracting = false;
                if (message != null) {
                    new AlertDialog.Builder(this)
                            .setTitle("Error")
                            .setMessage("Could not extract game data: " + message)
                            .setPositiveButton("Close", (d, w) -> finish())
                            .show();
                } else {
                    showLauncher();
                }
            });
        }, "extract-assets").start();
    }

    private void copyAssetTree(String assetPath, File target) throws IOException {
        String[] children = getAssets().list(assetPath);
        if (children == null || children.length == 0) {
            File parent = target.getParentFile();
            if (parent != null) //noinspection ResultOfMethodCallIgnored
                parent.mkdirs();
            try (InputStream in = getAssets().open(assetPath);
                 FileOutputStream out = new FileOutputStream(target)) {
                byte[] buffer = new byte[1 << 16];
                int n;
                while ((n = in.read(buffer)) > 0) out.write(buffer, 0, n);
            }
            return;
        }
        //noinspection ResultOfMethodCallIgnored
        target.mkdirs();
        for (String child : children) {
            copyAssetTree(assetPath + "/" + child, new File(target, child));
        }
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }

    private void showLauncher() {
        ScrollView scroll = new ScrollView(this);
        scroll.setBackgroundColor(Color.rgb(6, 18, 46));
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(dp(28), dp(22), dp(28), dp(22));
        scroll.addView(root);

        TextView title = new TextView(this);
        title.setText("Sonic Shuffle Recompiled");
        title.setTextColor(Color.WHITE);
        title.setTextSize(26);
        title.setTypeface(Typeface.DEFAULT_BOLD);
        root.addView(title);

        TextView subtitle = new TextView(this);
        subtitle.setText("Android arm64 · SDL3 · Vulkan");
        subtitle.setTextColor(Color.rgb(150, 190, 255));
        subtitle.setTextSize(13);
        root.addView(subtitle);

        status = new TextView(this);
        status.setTextColor(Color.rgb(210, 220, 240));
        status.setTextSize(13);
        status.setPadding(0, dp(14), 0, dp(14));
        root.addView(status);

        play = new Button(this);
        play.setText("Launch Game");
        play.setTextSize(18);
        play.setOnClickListener(v -> startGame());
        root.addView(play);

        TextView scaleLabel = new TextView(this);
        scaleLabel.setText("Render Resolution");
        scaleLabel.setTextColor(Color.rgb(180, 200, 230));
        scaleLabel.setTextSize(13);
        scaleLabel.setPadding(0, dp(10), 0, 0);
        root.addView(scaleLabel);

        scaleChooser = new Spinner(this);
        ArrayAdapter<String> adapter = new ArrayAdapter<>(this,
                android.R.layout.simple_spinner_dropdown_item,
                new String[]{"Производительность — 640×480 (1x)",
                        "Качество — 1280×960 (2x, тяжелее)"});
        scaleChooser.setAdapter(adapter);
        scaleChooser.setSelection(sScale == 2 ? 1 : 0);
        root.addView(scaleChooser);

        Button pick = new Button(this);
        pick.setText("Select Disc Image (CHD)");
        pick.setOnClickListener(v -> pickChd());
        LinearLayout.LayoutParams pickParams = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        pickParams.topMargin = dp(14);
        root.addView(pick, pickParams);

        TextView hint = new TextView(this);
        hint.setText("You can also place a CHD here:\n" + isoDir.getAbsolutePath()
                + "\n\nSaves: " + new File(savesDir, "sonicshuffle.vmu").getAbsolutePath()
                + "\nLog: " + new File(sBase, "sonicshuffle.log").getAbsolutePath());
        hint.setTextColor(Color.rgb(130, 150, 180));
        hint.setTextSize(11);
        hint.setPadding(0, dp(18), 0, 0);
        hint.setTextIsSelectable(true);
        root.addView(hint);

        setContentView(scroll);
        refreshStatus();
    }

    private void refreshStatus() {
        if (status == null || play == null) return;
        File disc = findDisc();
        if (!new File(sData, "game/extracted/fs/1ST_READ.BIN").isFile()) {
            status.setText("Game data has not been extracted.");
            play.setEnabled(false);
            return;
        }
        if (disc == null) {
            status.setText("Disc image not found.\nPlace a CHD in: " + isoDir.getAbsolutePath()
                    + "\nor select a disc image.");
            play.setEnabled(false);
        } else {
            status.setText("Disc image: " + disc.getName() + "\n" + disc.getAbsolutePath());
            play.setEnabled(true);
        }
    }

    private void startGame() {
        File disc = findDisc();
        if (disc == null) {
            pickChd();
            return;
        }
        sDisc = disc;
        sVmu = new File(savesDir, "sonicshuffle.vmu");
        sScale = scaleChooser != null && scaleChooser.getSelectedItemPosition() == 1 ? 2 : 1;
        prefs.edit().putInt("scale", sScale).apply();
        startActivity(new Intent(this, GameActivity.class));
    }

    private File findDisc() {
        File[] files = isoDir.listFiles();
        if (files == null) return null;
        for (String[] exts : new String[][]{{".chd"}, {".gdi"}, {".cue"}}) {
            for (File f : files) {
                if (!f.isFile()) continue;
                String name = f.getName().toLowerCase(Locale.ROOT);
                for (String ext : exts) {
                    if (name.endsWith(ext)) return f;
                }
            }
        }
        return null;
    }

    private void pickChd() {
        Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
        intent.addCategory(Intent.CATEGORY_OPENABLE);
        intent.setType("*/*");
        startActivityForResult(intent, PICK_CHD);
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode != PICK_CHD || resultCode != RESULT_OK || data == null || data.getData() == null)
            return;
        Uri uri = data.getData();
        String name = displayName(uri);
        if (name == null || name.isEmpty()) name = "sonicshuffle.chd";
        String lower = name.toLowerCase(Locale.ROOT);
        if (!lower.endsWith(".chd") && !lower.endsWith(".gdi") && !lower.endsWith(".cue")) {
            name = name + ".chd";
        }
        File target = new File(isoDir, name);

        ProgressDialog dialog = new ProgressDialog(this);
        dialog.setMessage("Copying disc image…");
        dialog.setProgressStyle(ProgressDialog.STYLE_HORIZONTAL);
        dialog.setCancelable(false);
        dialog.show();
        final File finalTarget = target;
        new Thread(() -> {
            String error = null;
            try (InputStream in = getContentResolver().openInputStream(uri);
                 FileOutputStream out = new FileOutputStream(finalTarget)) {
                if (in == null) throw new IOException("cannot open " + uri);
                byte[] buffer = new byte[1 << 20];
                long total = 0;
                int n;
                while ((n = in.read(buffer)) > 0) {
                    out.write(buffer, 0, n);
                    total += n;
                    final long copied = total;
                    runOnUiThread(() -> dialog.setMessage(
                            "Copying disc image… " + (copied >> 20) + " MB"));
                }
            } catch (IOException e) {
                Log.e(TAG, "CHD copy failed", e);
                error = e.getMessage();
            }
            final String message = error;
            runOnUiThread(() -> {
                dialog.dismiss();
                if (message != null) {
                    Toast.makeText(this, "Could not copy: " + message, Toast.LENGTH_LONG).show();
                } else {
                    refreshStatus();
                }
            });
        }, "copy-chd").start();
    }

    private String displayName(Uri uri) {
        try (Cursor cursor = getContentResolver().query(uri, null, null, null, null)) {
            if (cursor != null && cursor.moveToFirst()) {
                int index = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME);
                if (index >= 0) return cursor.getString(index);
            }
        } catch (Exception ignored) {
        }
        String path = uri.getLastPathSegment();
        if (path == null) return null;
        int slash = path.lastIndexOf('/');
        return slash >= 0 ? path.substring(slash + 1) : path;
    }
}
