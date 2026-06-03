# Stock Ops — Android App (Capacitor)

App Android dibuat dengan **membungkus PWA Vue ini pakai Capacitor** (reuse semua fitur).
Mendukung **Android 11+**, tema **ERPNext (biru) + dark mode**, login via **API ERPNext**, dan
**bebas masalah CORS** (request lewat native via CapacitorHttp).

## Cara kerja login & CORS (penting)
- Native pakai **token auth**, bukan cookie. Alur: `POST /api/method/login` (user/password) →
  `GET /api/method/stock_ops.api.get_or_create_token` → simpan `api_key:api_secret` → semua request
  berikutnya pakai header `Authorization: token key:secret`.
- **CORS tidak jadi masalah** karena `capacitor.config.json` mengaktifkan **CapacitorHttp** — `fetch`
  di-patch agar request dijalankan oleh layer native (bukan WebView), jadi **tidak terkena CORS browser**.
- Tetap disarankan set di server ERPNext (untuk uji via web cross-origin / aman):
  ```bash
  bench --site <site> set-config allow_cors "*"
  bench --site <site> clear-cache
  ```
  (boleh diganti origin spesifik, mis. `"https://app.domainmu.com"`).

## Prasyarat build
- Node 18+, **Android Studio** (SDK Platform 30/Android 11 + Build-Tools), **JDK 17**.

## Langkah build APK
```bash
cd frontend
npm install

# 1) build web assets (service worker dimatikan untuk native)
npm run build:app

# 2) tambah platform android (sekali saja)
npx cap add android

# 3) sinkronkan web → native (ulangi tiap kali ganti kode web)
npm run cap:sync        # = build:app + cap sync android

# 4) buka di Android Studio lalu Run/Build APK
npm run cap:open        # atau: npx cap open android
```
Di Android Studio: **Build → Build Bundle(s)/APK(s) → Build APK(s)**. APK ada di
`android/app/build/outputs/apk/debug/app-debug.apk`. Untuk rilis: buat signing key, **Generate Signed Bundle/APK**.

> Folder `android/` di-generate oleh `npx cap add android` (tidak ikut di-commit; tambahkan ke .gitignore bila perlu).

## Konfigurasi
- `capacitor.config.json`: `appId=com.rmi.stockops`, `appName="Stock Ops"`, `webDir=dist`,
  plugin `CapacitorHttp.enabled=true`.
- Saat pertama buka app: isi **URL Server ERPNext** (mis. `https://erp.halosocia.my.id`) + email/username + password.
  Token disimpan di perangkat (localStorage WebView). Logout menghapus token.

## Izin Android yang relevan
- **Kamera** (scan barcode), **Lokasi** (tag geolokasi), **Internet**. Tambahkan di
  `android/app/src/main/AndroidManifest.xml` bila belum (CAMERA, ACCESS_FINE_LOCATION). Capacitor sudah
  menambah INTERNET default.

## Build via CLI tanpa Android Studio (mis. env: Android SDK + JBR JDK 21)
`npx cap add android` membuat project Gradle dengan AGP 8.2.1 + Gradle 8.2.1 (mendukung JDK ≤20) dan
build-tools default 34.0.0. Jika mesin pakai **JDK 21** dan/atau **belum ada build-tools 34.0.0**,
sesuaikan project `android/` (sekali, setelah `cap add android`):

1. `android/gradle/wrapper/gradle-wrapper.properties` → `gradle-8.7-all.zip` (dukung JDK 21).
2. `android/build.gradle` → `classpath 'com.android.tools.build:gradle:8.5.2'`.
3. `android/variables.gradle` → tambah `buildToolsVersion = '35.0.0'` (versi yang terpasang).
4. `android/build.gradle` → di blok `subprojects { afterEvaluate { ... } }` set
   `project.android.buildToolsVersion = rootProject.ext.buildToolsVersion` untuk semua modul.
5. `android/local.properties` → `sdk.dir=D:\\Android\\Sdk`.
6. Izin di `android/app/src/main/AndroidManifest.xml`: `CAMERA`, `ACCESS_FINE_LOCATION`, `ACCESS_COARSE_LOCATION`.

Build:
```powershell
$env:JAVA_HOME = "C:\Program Files\Android\Android Studio\jbr"   # JDK (JBR 21)
$env:ANDROID_HOME = "D:\Android\Sdk"
cd android
.\gradlew.bat :app:assembleDebug --no-daemon
```
APK: `android/app/build/outputs/apk/debug/app-debug.apk`.

> NB: folder `android/` di-gitignore (di-generate ulang via `cap add`). Bila ingin tweak di atas
> permanen lintas-mesin, commit folder `android/` atau buat patch.

## Catatan
- Scan kamera & geolokasi memakai API web (getUserMedia/Geolocation) di WebView; izin Android sudah
  dideklarasikan. Login & semua fitur data jalan via token. Uji kamera/lokasi di perangkat nyata.
- Service worker & Web Push tidak aktif di WebView native; push HP nanti via FCM (belum diimplementasi).
- HTTPS server wajib untuk produksi (kamera/lokasi & keamanan token).
