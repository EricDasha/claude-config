# UniApp Cross-Platform Patterns

Patterns for BLE hardware companion apps built with UniApp (Vue 3 + Vite).

## Setup

```bash
npx degit dcloudio/uni-preset-vue#vite-ts app
cd app && npm install vuex@4
```

Compiler update: `npm install @dcloudio/*@<version>` (avoid interactive `npx @dcloudio/uvm`).

## Architecture

```
src/
  main.ts           — createSSRApp, register global components, use Vuex
  App.vue           — global styles, dynamic tabBar text
  pages.json        — routes, tabBar config (PNG icons required)
  utils/
    ble.js          — BLE scan/connect/read/write/notify/OTA
    icons.js        — SVG icons as data URIs
    i18n.js         — Chinese/English auto-switch
    mock.js         — Dev mode simulated data
  store/index.js    — Vuex state management
  components/
    MkIcon.vue      — Global SVG icon component
  pages/            — Page components
  static/           — PNG/SVG assets
```

## SVG Icon System

UniApp cross-platform icon approach (works on H5, Android, iOS, WeChat MP):

```javascript
// icons.js — define SVG as functions returning markup
function sk(d) {
  return (c = '#e0e0e0') =>
    `<svg xmlns="..." viewBox="0 0 24 24" fill="none" stroke="${c}" ...>${d}</svg>`
}

export function iconUri(name, color) {
  const svg = ICONS[name](color)
  return 'data:image/svg+xml,' + encodeURIComponent(svg)
}
```

Component renders via CSS `background-image: url(data:image/svg+xml,...)`.

**TabBar icons must be PNG** — generate with Python Pillow at 81x81px.

## i18n Pattern

```javascript
const lang = ref(uni.getSystemInfoSync().language?.startsWith('zh') ? 'zh' : 'en')
export function t(key) { /* dot-path lookup in messages[lang.value] */ }
```

Dynamic tabBar text via `uni.setTabBarItem({ index, text })` in App.vue onShow.

## Dev Mode

Purpose: develop/debug app without physical BLE device.

```javascript
// mock.js — setInterval emitting 'kill' and 'env' events
// store SET_DEV_MODE mutation populates mock session/lifetime/config
// Dashboard subscribes to mock events via onMock() instead of BLE
// Control page skips isConnected() check in dev mode
```

Entry: button on splash page → `enableDevMode()` + `store.commit('SET_DEV_MODE', true)`

## BLE Communication

```javascript
// Scan → connect → discover services → read/write/subscribe
const UUID = { SVC: 'e3a11b00-...', KILL_COUNT: 'e3a11b01-...', ... }

export async function connect(deviceId) {
  await uni.createBLEConnection({ deviceId })
  await uni.getBLEDeviceServices({ deviceId })
  await uni.getBLEDeviceCharacteristics({ deviceId, serviceId: UUID.SVC })
}
```

OTA: chunked upload (236B per write) with CRC32 verification.

## Common Issues

| Issue | Fix |
|-------|-----|
| `uni: not found` | Need official template with `@dcloudio/vite-plugin-uni` |
| `@dcloudio/uvm` interactive prompt | Use direct `npm install @dcloudio/*@version` |
| Float precision in sensor display | Always `.toFixed(1)` for temp/humidity values |
| SVG in WeChat MP `<image>` | Use CSS background-image with data URI instead |
