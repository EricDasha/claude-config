# KiCad 9 S-Expression Quirks

Hard-won lessons from automated schematic/PCB generation.

## Parse errors that will bite you

| Symptom | Cause | Fix |
|---------|-------|-----|
| `unexpected token ;;` | Comments in .kicad_sch | KiCad 9 does NOT support `;;` comments. Remove all. |
| `missing angle` on symbol `(at x y)` | Missing rotation angle | Must be `(at x y 0)` — the third value is mandatory. `sed -i 's/(at \([0-9.]*\) \([0-9.]*\))/(at \1 \2 0)/g'` |
| `unexpected bold` | Bare `bold` keyword | KiCad 9 requires `(bold yes)`, not just `bold`. |
| `invalid effects` | `(color ...)` inside `(effects)` | Color is not valid in KiCad 9 text effects. Remove `(color ...)` from effects blocks. |
| Footprints not found by kicad-cli | Footprint set in instance but not in symbol lib | kicad-cli reads footprint from symbol library definition, NOT from instance properties. Must inject `(property "Footprint" "lib:fp")` into each symbol. |

## Footprint injection script

When programmatically generating schematics, footprints must be injected via Python:

```python
# Read .kicad_sch, find each symbol instance,
# insert (property "Footprint" "Library:Footprint" ...) if missing
# Use the BOM/design doc as the source of truth for footprint assignments
```

## PCB generation rules

1. **Board outline first** — set to product form factor before placing components
2. **Never hand-route** — LLM-placed traces violate clearances. Always use FreeRouter via autoroute.
3. **Serialize PCB operations** — kicad-mcp PCB tools do load/modify/save. Parallel calls corrupt the file.
4. **Search before placing** — never guess library/footprint names. `library(operation="search")` first.
5. **DRC after every major change** — catch problems early.
6. **Copper pour last** — GND zones on both layers, after routing is complete.

## Common DRC fixes

| Violation | Auto-fix approach |
|-----------|------------------|
| Courtyard overlap | Move component, reduce courtyard in footprint |
| Clearance violation | Increase trace spacing, move via |
| Unconnected net | Check schematic connectivity, re-route |
| Silk on pad | Hide silk layer for affected references |
| Via too small | Increase via drill/annular ring |
| Missing GND stitch | Add GND vias in copper pour areas |
