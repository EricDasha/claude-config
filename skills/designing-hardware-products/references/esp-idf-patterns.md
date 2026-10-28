# ESP-IDF Firmware Patterns

Patterns extracted from MosKill project (ESP32-C3, ESP-IDF v5.4).

## Project structure

```
firmware/
  CMakeLists.txt              — top-level, registers EXTRA_COMPONENT_DIRS
  sdkconfig.defaults          — project defaults (BLE, NVS, partition table)
  partitions.csv              — custom partition layout (app + ota + nvs)
  main/
    src/main.c                — app_main(), task creation
    include/main.h
    CMakeLists.txt
  components/
    moskill_common/           — shared types, config defines
      include/moskill_types.h
      include/moskill_config.h
      CMakeLists.txt          — REQUIRES: [] (header-only)
    <component>/
      <component>.c
      include/<component>.h
      CMakeLists.txt          — REQUIRES: moskill_common, driver, ...
```

## FreeRTOS task priorities (descending)

| Priority | Task | Rationale |
|----------|------|-----------|
| 5 | Kill detection | Time-critical ADC sampling |
| 4 | Stats engine | Must process before next kill |
| 3 | BLE service | Responsive but not real-time |
| 2 | Env sensor / UI | Background polling |
| 1 | Power management | Lowest urgency |

## Common pitfalls

### ADC shared handle
ESP-IDF v5.x uses `adc_oneshot_new_unit()` — only one handle per ADC unit. Make it global:
```c
// main.c
adc_oneshot_unit_handle_t shared_adc_handle;
// other components: extern adc_oneshot_unit_handle_t shared_adc_handle;
```

### Header-only components and enums
Don't use `ADC_ATTEN_DB_12` (enum from driver) in a header-only component's config. Use integer constants:
```c
#define MOSKILL_ADC_ATTEN 3   // = ADC_ATTEN_DB_12
#define MOSKILL_ADC_WIDTH 4   // = ADC_BITWIDTH_12
```

### NVS blob size limit
NVS pages are 4KB. A blob can't span pages. If data > ~3.5KB, shard it:
```c
#define SHARD_SIZE 64
#define NUM_SHARDS 4
// key: "klog0", "klog1", "klog2", "klog3"
```

### BLE CCCD notifications
Each notification characteristic needs its own CCCD enable flag. Write handler must check `attr_handle` to set the correct flag.

### Deep sleep wakeup
Always configure a wakeup source before entering deep sleep:
```c
gpio_wakeup_enable(PIN_BUTTON, GPIO_INTR_LOW_LEVEL);
esp_sleep_enable_gpio_wakeup();
esp_deep_sleep_start();
```

## BLE GATT pattern

Use 128-bit custom UUIDs with a shared base:
```c
#define UUID_BASE "e3a1XXXX-f5e8-4c8a-9b3d-2c1f7b8a6d50"
// Replace XXXX with 2-byte service/char IDs
```

Wire format: packed structs with `__attribute__((packed))` for BLE transfer efficiency.
