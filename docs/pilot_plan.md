# Pilot plan: re-slotting one dark store

The model's savings come from assumed walk speeds and pick times. A pilot checks them on
the floor before the layout is rolled out to other stores.

## 1. Baseline week (before any change)

- Time-and-motion study of 50+ orders per shift: walk time, search time, grab/scan time,
  and tote drop-off time. Use the results to calibrate `picking` in `config.yaml`.
- Pull a week of WMS pick logs to measure lines per hour, orders per hour, mispicks and
  pick-to-pack time per picker.
- Re-run the model with the calibrated parameters and the store's own SKU velocity.

## 2. Zone-by-zone rollout

Move one zone at a time, starting with the aisle nearest the pack station, so the store
never has more than one zone in flux.

| Phase | Scope | Duration |
|---|---|---|
| 1 | Aisle 1: re-slot A items, golden zone first | 1 week |
| 2 | Aisles 2-3: A and B items | 1 week |
| 3 | Remaining aisles, C items to the back | 1 week |

Re-slotting happens during the low-order window (about 02:00-06:00), with putaway labels
and the WMS bin master updated in the same shift.

## 3. Go / no-go KPIs per phase

| KPI | Go if | Source |
|---|---|---|
| Lines picked per hour | +10% or better vs baseline | WMS pick log |
| Mean walk distance per order | -15% or better | route model + spot checks |
| Mispick rate | no worse than baseline | packing QC |
| Peak aisle pick share | under the congestion cap | `zone_congestion_optimised.csv` |
| Picker feedback | no blocking issues | daily huddle |

A no-go on mispicks stops the rollout, whatever the speed gain.

## 4. Scale-up recommendation

At the end of phase 3, write a one-page summary with the measured gains, the cost in
re-slotting labour, and a recommendation: **scale**, **fix and re-pilot**, or **stop**.
Schedule re-slotting monthly, or whenever ABC classes shift by more than 10% of SKUs.
