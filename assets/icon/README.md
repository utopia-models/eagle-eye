# Eagle Eye app icon

Horus: a falcon head in the live.utopiamodels.ai gold sand on ink `#0a0a09`, with the Eye of Horus cut into it — brow, almond eye with a sealed gold pupil, kohl tail, the teardrop (the falcon's malar stripe, which is where the wedjat marking comes from) and the spiral. Chosen from six concepts (`review/concepts-a-f.png`); concept B, the Gold Amulet, is kept as an alternate mark in `assets/brand/alt-gold-amulet/`.

The sand is the live site's grain shader (`live.js`) ported to numpy in `src/sand.py`, over a beaten-gold plate so the head reads solid at 48 dp. Every concept lives in `src/concepts.py`; `src/build.py <out> <concept>` writes the whole set below, and `src/svgmask.py <concept> <out.svg>` writes the vector favicon from the same drawing calls.

At 16–32 px the favicon is flat gold: the whole head on an ink margin with only the eye and teardrop (no brow, tail or spiral), and the 16 px one is drawn on the pixel grid (`Horus.FAV16`).

| File | Use |
|---|---|
| `icon-1024.png` | the master (RGB, opaque) |
| `ios/AppIcon-1024.png` | iOS / App Store icon, RGB with no alpha. iOS applies its own squircle. |
| `android/adaptive-foreground.png` | adaptive icon foreground (transparent). The glyph sits inside the 66/108 dp safe circle. |
| `android/adaptive-background.png` | adaptive icon background, solid `#0a0a09` |
| `android/adaptive-monochrome.png` | Android 13+ themed icon (white silhouette on alpha) |
| `android/play-store-512.png` | Google Play listing icon |
| `pwa/icon-192.png`, `pwa/icon-512.png` | manifest icons, `purpose: "any"` |
| `pwa/icon-192-maskable.png`, `pwa/icon-512-maskable.png` | manifest icons, `purpose: "maskable"`. The glyph sits inside the 80% safe circle. |
| `web/favicon.ico` | 16 (drawn on the pixel grid) + 32 + 48 |
| `web/favicon-16.png`, `favicon-32.png`, `favicon-48.png` | the same favicons as PNG files |
| `web/apple-touch-icon.png` | 180×180, opaque |
| `web/favicon-1024.png` | the flat small-size mark on its tile, 1024 (the source of `site/favicon.svg`) |
| `splash/splash-icon-1024.png`, `splash/splash-mark-512.png` | the splash mark (transparent); use it on background `#0a0a09` |


## Expo (`app.json`)

```json
{
  "expo": {
    "icon": "./assets/icon/icon-1024.png",
    "ios": { "icon": "./assets/icon/ios/AppIcon-1024.png" },
    "android": {
      "adaptiveIcon": {
        "foregroundImage": "./assets/icon/android/adaptive-foreground.png",
        "backgroundImage": "./assets/icon/android/adaptive-background.png",
        "monochromeImage": "./assets/icon/android/adaptive-monochrome.png",
        "backgroundColor": "#0a0a09"
      }
    },
    "plugins": [["expo-splash-screen", {
      "image": "./assets/icon/splash/splash-icon-1024.png",
      "imageWidth": 200, "resizeMode": "contain", "backgroundColor": "#0a0a09"
    }]],
    "web": { "favicon": "./assets/icon/web/favicon-48.png" }
  }
}
```

## PWA (`manifest.webmanifest` + `<head>`)

```json
"icons": [
  { "src": "/icons/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any" },
  { "src": "/icons/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any" },
  { "src": "/icons/icon-192-maskable.png", "sizes": "192x192", "type": "image/png", "purpose": "maskable" },
  { "src": "/icons/icon-512-maskable.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable" }
],
"background_color": "#0a0a09", "theme_color": "#0a0a09"
```

```html
<link rel="icon" href="/favicon.ico?v=3" sizes="16x16 32x32 48x48">
<link rel="icon" href="/favicon.svg?v=3" type="image/svg+xml">
<link rel="apple-touch-icon" href="/apple-touch-icon.png?v=3">
```

## Regenerate

```bash
python3 -m venv .venv && .venv/bin/pip install pillow numpy scipy
cd assets/icon/src && ../../../.venv/bin/python build.py ../ horus   # rewrites every file above
../../../.venv/bin/python svgmask.py horus ../../../site/favicon.svg
```

`review/` holds the A-F concept sheet, the Horus review sheet (master, 48 dp circle and squircle, favicons on dark and light tabs) and the mock Pixel home screen at true size (1 px = 1 dp) and at device resolution.
