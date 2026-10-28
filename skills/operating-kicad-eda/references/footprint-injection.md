# Footprint Injection for kicad-cli

## The problem

When generating schematics programmatically (via kicad-sch-api or MCP), footprints are set as instance properties. But `kicad-cli` reads footprints from the **symbol library definition**, not from instance properties.

Result: `kicad-cli pcb new-from-schematic` fails to find footprints.

## The fix

Python script that injects `(property "Footprint" "Library:Footprint" ...)` into each symbol instance in the `.kicad_sch` file.

```python
import re

def inject_footprints(sch_path, footprint_map):
    """
    footprint_map: dict of { 'R1': 'Resistor_SMD:R_0402_1005Metric', ... }
    """
    with open(sch_path, 'r') as f:
        content = f.read()

    for ref, footprint in footprint_map.items():
        # Find symbol instance for this reference
        # Insert (property "Footprint" "...") if missing
        pattern = rf'(\(symbol\s*\(lib_id\s+"[^"]+"\)\s*\(at[^)]+\).*?'
        pattern += rf'\(property\s+"Reference"\s+"{ref}"[^)]*\))'
        
        fp_prop = f'(property "Footprint" "{footprint}" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))'
        
        # Insert after Reference property if Footprint not already present
        # Implementation depends on exact S-expression structure
        pass

    with open(sch_path, 'w') as f:
        f.write(content)
```

## Footprint map sources

Build the map from:
1. **BOM.csv** — primary source of truth
2. **DESIGN.md** — component selection section
3. **library(operation="search")** — verify footprint names exist

## Common footprint libraries

| Component type | Library prefix |
|---------------|----------------|
| Resistors | `Resistor_SMD:R_0402_*`, `R_0603_*`, `R_0805_*` |
| Capacitors | `Capacitor_SMD:C_0402_*`, `C_0603_*`, `C_0805_*` |
| Diodes | `Diode_SMD:D_SOD-123`, `D_SOD-323` |
| MOSFETs | `Package_TO_SOT_SMD:SOT-23` |
| ICs | Various, MUST search first |
| Connectors | `Connector_PinHeader_*`, `Connector_USB_*` |
| ESP32 | `espressif:ESP32-C3-MINI-1` (needs Espressif library) |

## Espressif library setup

```bash
git clone https://github.com/espressif/kicad-libraries.git hardware/kicad/libs/espressif
```

Register in `fp-lib-table`:
```
(fp_lib_table
  (lib (name "espressif")(type "KiCad")(uri "${KIPRJMOD}/libs/espressif/footprints/espressif.pretty")(options "")(descr ""))
)
```
