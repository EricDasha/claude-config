# Pipeline Phases — Execution Detail

## Phase 1: System Design

Input: product brief (MCU, sensors, features, form factor)
Output: `docs/DESIGN.md`

1. Define system block diagram (power, sensing, processing, communication, UI)
2. Select key components (MCU, regulators, sensors, connectors)
3. Design power topology (battery, charging IC, boost/buck if needed)
4. Define communication protocol (BLE GATT service/characteristics, UUIDs, wire formats)
5. Write BOM estimate

**Deliverables:** DESIGN.md, protocol/ble_protocol.md, initial BOM

## Phase 2: Firmware (ESP-IDF)

Input: DESIGN.md
Output: compilable firmware in `firmware/`

Structure:
```
firmware/
  main/src/main.c          — entry, FreeRTOS task creation
  components/
    <module>/
      <module>.c
      include/<module>.h
      CMakeLists.txt
  CMakeLists.txt
  sdkconfig.defaults
  partitions.csv
```

Task priority assignment:
- Highest: time-critical sensing (kill detection, ADC sampling)
- Medium: data processing (stats engine), communication (BLE)
- Low: UI (LED), power management

**Key patterns:**
- Shared ADC handle (extern global, create once in main)
- Mutex-protected shared state (stats, config)
- NVS storage: sharded if blob > 4KB page limit (max ~960B per shard)
- BLE: separate CCCD variables per notification characteristic
- Deep sleep: always configure wakeup source before entering

**Build:** `source esp-idf/export.sh && idf.py set-target esp32c3 && idf.py build`

## Phase 3: Hardware (KiCad)

Input: DESIGN.md, BOM
Output: Gerber zip, renders

**Sub-pipeline (fully automated):**
```
1. Create schematic (kicad-sch-api or mcp__kicad__schematic)
2. Inject footprints (Python script — kicad-cli reads from symbol library)
3. Build PCB from schematic (mcp__kicad__build_pcb_from_schematic)
4. Set board outline to product form factor
5. Place components (mcp__kicad__suggest_placement or manual)
6. Autoroute (mcp__kicad__autoroute → FreeRouter)
7. Run DRC + autofix (mcp__kicad__drc)
8. Add copper pour (GND zones both layers)
9. Export Gerbers (mcp__kicad__export)
10. Render 3D views
```

See [operating-kicad-eda](../../../operating-kicad-eda/SKILL.md) for tool details.

## Phase 4: Mobile App (UniApp)

Input: BLE protocol spec
Output: cross-platform app in `app/`

Template: `npx degit dcloudio/uni-preset-vue#vite-ts app`

Architecture:
```
app/src/
  utils/ble.js       — BLE communication (scan, connect, read/write, notify, OTA)
  utils/icons.js      — SVG icon library (data URI, cross-platform)
  utils/i18n.js       — Chinese/English auto-switch
  utils/mock.js       — Dev mode (simulated data without device)
  store/index.js      — Vuex state (connected, session, lifetime, config, env)
  components/MkIcon.vue — Global SVG icon component
  pages/              — 7 pages (index, connect, dashboard, stats, leaderboard, control, ota)
```

**Key patterns:**
- Register `<mk-icon>` globally in main.ts
- SVG icons as `data:image/svg+xml,` URIs (encodeURIComponent, no btoa needed)
- Dev mode: `enableDevMode()` → SET_DEV_MODE mutation → mock data + mock events
- TabBar icons: must be PNG (generate with Pillow from SVG designs)
- Dynamic tabBar text: `uni.setTabBarItem()` in App.vue onShow
- Number formatting: always `.toFixed(1)` for sensor values

**Build:** `npx uni build` (H5), `npx uni build -p mp-weixin` (WeChat)

## Phase 5: Verify + Package

1. `idf.py build` — firmware binary
2. `npx uni build` — app dist
3. KiCad DRC — zero violations
4. `zip -r release.zip` — source + binary + Gerber + BOM + renders + docs
   - Exclude: node_modules, .venv, __pycache__, dist, .git
