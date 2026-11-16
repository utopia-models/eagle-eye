# Eagle Eye app icon

The Eye of Horus (the wedjat from `site/assets/mark.svg`) drawn in the gold sand of live.utopiamodels.ai, on ink `#0a0a09`. The sand is not a texture: it uses the live site's own grain shader (`live.js`), ported to numpy in `src/sand.py`. Grains run `#d4a94e` → `#f0d28a` → `#fff4d6`, with additive blending, one grain in five a pearl glint, a molten swirling sun-disk pupil and an amber bloom.

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
| `web/favicon-mark-transparent.png` | the flat-gold small-size mark with no tile |
| `splash/splash-icon-1024.png`, `splash/splash-mark-512.png` | the splash mark (transparent); use it on background `#0a0a09` |

At 16–48 px the favicon is a flat-gold simplified wedjat on an ink tile: eye, lid-cut pupil, teardrop and tail stub. Sand grain turns to mud at that size, and the ink tile keeps it readable on both light and dark tabs.

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
<link rel="icon" href="/favicon.ico?v=2" sizes="16x16 32x32 48x48">
<link rel="apple-touch-icon" href="/apple-touch-icon.png?v=2">
```

## Regenerate

```bash
python3 -m venv .venv && .venv/bin/pip install pillow numpy scipy
cd assets/icon/src && ../../../.venv/bin/python build.py ../   # rewrites every file above
```

`review/` holds the round-1 candidate sheet, the winner, every output under its platform mask, and the mock Pixel home screen at true size (1 px = 1 dp, 48 dp icons).
