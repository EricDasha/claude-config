# DRC Fix Strategies

Automated approaches for common KiCad DRC violations.

## Priority order

Fix in this order (earlier fixes often resolve later ones):

1. **Courtyard overlaps** — move overlapping components apart
2. **Clearance violations** — increase spacing, move vias, reroute
3. **Unconnected nets** — check schematic, re-run autoroute
4. **Silk on pad** — hide silk reference for affected footprints
5. **Via size** — increase drill/annular ring to meet minimums
6. **Missing GND stitching** — add GND vias in pour areas

## Autofix capabilities

The `drc(operation="autofix")` tool can handle:
- Move components to resolve courtyard overlap (small adjustments)
- Hide silkscreen references conflicting with pads
- Adjust via sizes
- Shrink antenna keepout zones

It CANNOT:
- Reroute traces (use autoroute for that)
- Fix fundamental placement issues (manual intervention)
- Resolve inter-layer clearance on tight boards

## Manual intervention triggers

If autofix leaves > 3 violations:
1. Read the DRC report to understand remaining issues
2. Check if a component needs rotation or repositioning
3. If trace-related, delete affected traces and re-autoroute
4. Re-run DRC until 0 violations

## HV board special rules

For high-voltage designs:
- **4mm minimum clearance** between HV and LV nets
- **Slot isolation** between HV and LV zones where possible
- **No vias** under transformer or HV multiplier
- **Separate ground pour** for HV section if needed
