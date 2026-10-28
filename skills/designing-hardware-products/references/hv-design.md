# High Voltage Circuit Design

For products requiring HV output (mosquito swatters, ionizers, electrostatic sprayers).

## Topology: NE555 + MOSFET + Transformer + Cockcroft-Walton

```
Battery (3.7V) → NE555 oscillator (40kHz) → AO3400 N-MOSFET → EE13 transformer
→ Cockcroft-Walton voltage multiplier (3-stage) → ~2000V output on grid
```

### Key components

| Part | Role | Selection criteria |
|------|------|--------------------|
| NE555 | PWM oscillator | 40kHz, adjustable duty cycle |
| AO3400 | Primary switch | Vds > 30V, Rds(on) < 50mΩ, SOT-23 |
| EE13 transformer | Step-up | 10:200 turns ratio, ferrite core |
| UF4007 | Rectifier diodes | 1000V, fast recovery |
| Cockcroft-Walton | Voltage multiplier | 3-stage → 6x secondary peak |

### Transformer ratio calculation

```
V_secondary_peak = V_primary × (N_secondary / N_primary)
V_primary ≈ 3.3V (battery under load)
N_ratio = 200/10 = 20
V_secondary_peak = 3.3 × 20 = 66V

After 3-stage CW multiplier:
V_out ≈ 66 × 2 × 3 = ~396V (no load, theoretical)
With real losses: ~2000V achievable with optimized duty cycle
```

### Why 1:20 ratio fails

A 1:20 ratio only produces ~264V loaded — not enough for mosquito grid discharge. Minimum 1:200 (10:200 turns) needed.

## Safety circuits

1. **RC snubber** across transformer primary — absorbs flyback spikes
2. **TVS diode** on primary — clamps overshoot
3. **HV discharge resistor** on grid — bleeds charge when off (10MΩ)
4. **4mm clearance** between HV traces on PCB
5. **Watchdog timer** — max HV on-time 600s, then auto-off
6. **Charging interlock** — disable HV while USB charging

## Kill detection

```
Grid discharge → current pulse through 0.1Ω sense resistor
→ LMV358 op-amp (gain=20) → BAT43 Schottky peak detector
→ ESP32 ADC → state machine (IDLE → ARMED → CONFIRMING → COOLDOWN)
```

Classify by energy: `energy_accum = Σ(adc_value × dt)` → S/M/L/XL thresholds
