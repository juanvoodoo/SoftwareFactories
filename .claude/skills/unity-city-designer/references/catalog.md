# Element catalog

Worked part-breakdowns for common city elements. Every recipe here has been
validated against the builder, so the numbers are known-good starting points —
adapt dimensions and colors freely, keep the structure.

Contents: [Standard palette](#standard-palette) · [corner-shop](#corner-shop) ·
[mid-rise](#mid-rise) · [office-tower](#office-tower) · [house](#house) ·
[streetlight](#streetlight) · [bench](#bench) · [bus-stop](#bus-stop) ·
[traffic-light](#traffic-light) · [tree](#tree) · [kiosk](#kiosk) ·
[billboard](#billboard) · [road-segment](#road-segment)

## Standard palette

Reuse these role names and hex values across every element. Consistency is what
makes separate props read as one city, and the builder shares materials by role
name, so reusing a role costs nothing and creates nothing new.

| Role | Hex | Role | Hex |
|---|---|---|---|
| `Concrete` | `#A8A49BFF` | `Asphalt` | `#35353AFF` |
| `ConcreteDark` | `#6E6A63FF` | `LineWhite` | `#E8E4DAFF` |
| `Plaster` | `#D6CDBEFF` | `Metal` | `#4A4D52FF` |
| `Brick` | `#9C5B45FF` | `MetalLight` | `#8A8F96FF` |
| `BrickDark` | `#7A4435FF` | `Wood` | `#8A6A45FF` |
| `Glass` | `#5B86A6FF` | `Foliage` | `#4F7A42FF` |
| `GlassDark` | `#3E5F77FF` | `LampWarm` | `#FFE9A8FF` |
| `RoofTile` | `#3A3A42FF` | `SignRed` | `#C0483CFF` |
| `RoofRed` | `#8C4A3AFF` | `SignGreen` | `#4E9A52FF` |

---

## corner-shop
Single storey retail, 6 × 4 × 5 m. Ground-level glazing is what makes it read
as a shop rather than a shed.

```json
{"name":"CornerShop","position":[0,0,0],
 "materials":{"Brick":"#9C5B45FF","Glass":"#5B86A6FF","RoofTile":"#3A3A42FF","SignRed":"#C0483CFF"},
 "parts":[
  {"name":"Walls","primitive":"cube","material":"Brick","size":[6,4,5],"at":[0,0,0]},
  {"name":"ShopFront","primitive":"cube","material":"Glass","size":[4.6,2.4,0.25],"at":[0,0.3,-2.55]},
  {"name":"Awning","primitive":"cube","material":"SignRed","size":[5,0.2,1],"at":[0,2.9,-3.0]},
  {"name":"RoofSlab","primitive":"cube","material":"RoofTile","size":[6.6,0.4,5.6],"at":[0,4,0]}
 ]}
```

## mid-rise
Four-to-five storey block, 12 × 16 × 10 m. Horizontal glazing bands read as
floors; a darker ground floor anchors it to the street.

```json
{"name":"MidRise","position":[0,0,0],
 "materials":{"Plaster":"#D6CDBEFF","ConcreteDark":"#6E6A63FF","Glass":"#5B86A6FF","RoofTile":"#3A3A42FF"},
 "parts":[
  {"name":"GroundFloor","primitive":"cube","material":"ConcreteDark","size":[12.2,3.5,10.2],"at":[0,0,0]},
  {"name":"Body","primitive":"cube","material":"Plaster","size":[12,12.5,10],"at":[0,3.5,0]},
  {"name":"Band_1","primitive":"cube","material":"Glass","size":[10.5,1.8,0.25],"at":[0,4.6,-5.05]},
  {"name":"Band_2","primitive":"cube","material":"Glass","size":[10.5,1.8,0.25],"at":[0,7.6,-5.05]},
  {"name":"Band_3","primitive":"cube","material":"Glass","size":[10.5,1.8,0.25],"at":[0,10.6,-5.05]},
  {"name":"Cornice","primitive":"cube","material":"ConcreteDark","size":[12.6,0.5,10.6],"at":[0,16,0]}
 ]}
```

## office-tower
30 m+ tower, 10 × 10 footprint. Full-height glazing proud of each face plus a
roof plant box and antenna; the silhouette does the work at distance.

```json
{"name":"OfficeTower","position":[0,0,0],
 "materials":{"Concrete":"#A8A49BFF","ConcreteDark":"#6E6A63FF","Glass":"#5B86A6FF","Metal":"#4A4D52FF","RoofTile":"#3A3A42FF"},
 "parts":[
  {"name":"GroundFloor","primitive":"cube","material":"ConcreteDark","size":[10.4,4,10.4],"at":[0,0,0]},
  {"name":"TowerBody","primitive":"cube","material":"Concrete","size":[10,24,10],"at":[0,4,0]},
  {"name":"Glass_North","primitive":"cube","material":"Glass","size":[8,22,0.3],"at":[0,5,-5.0]},
  {"name":"Glass_South","primitive":"cube","material":"Glass","size":[8,22,0.3],"at":[0,5,5.0]},
  {"name":"Glass_East","primitive":"cube","material":"Glass","size":[0.3,22,8],"at":[5.0,5,0]},
  {"name":"Glass_West","primitive":"cube","material":"Glass","size":[0.3,22,8],"at":[-5.0,5,0]},
  {"name":"RoofSlab","primitive":"cube","material":"RoofTile","size":[11,0.6,11],"at":[0,28,0]},
  {"name":"RoofUnit","primitive":"cube","material":"Metal","size":[3,2.2,3],"at":[0,28.6,0]},
  {"name":"Antenna","primitive":"cylinder","material":"Metal","size":[0.18,6,0.18],"at":[0,30.8,0]}
 ]}
```

## house
Detached house, 8 × 6 × 7 m with a gabled roof. The gable is two rotated slabs
positioned by `center`, because `at` assumes an upright part.

```json
{"name":"House","position":[0,0,0],
 "materials":{"Plaster":"#D6CDBEFF","RoofRed":"#8C4A3AFF","Wood":"#8A6A45FF","Glass":"#5B86A6FF"},
 "parts":[
  {"name":"Walls","primitive":"cube","material":"Plaster","size":[8,6,7],"at":[0,0,0]},
  {"name":"Door","primitive":"cube","material":"Wood","size":[1.1,2.2,0.2],"at":[0,0,-3.55]},
  {"name":"Window_L","primitive":"cube","material":"Glass","size":[1.4,1.2,0.2],"at":[-2.3,3,-3.55]},
  {"name":"Window_R","primitive":"cube","material":"Glass","size":[1.4,1.2,0.2],"at":[2.3,3,-3.55]},
  {"name":"RoofSlope_N","primitive":"cube","material":"RoofRed","size":[8.6,0.3,4.3],"center":[0,7.0,-1.75],"rotation":[-29.7,0,0]},
  {"name":"RoofSlope_S","primitive":"cube","material":"RoofRed","size":[8.6,0.3,4.3],"center":[0,7.0,1.75],"rotation":[29.7,0,0]}
 ]}
```

## streetlight
5.5 m pole with an arm and lamp head. Cylinders are the trap here — the builder
converts metres for you, so state the real height.

```json
{"name":"Streetlight","position":[0,0,0],
 "materials":{"Metal":"#4A4D52FF","LampWarm":"#FFE9A8FF"},
 "parts":[
  {"name":"Base","primitive":"cylinder","material":"Metal","size":[0.45,0.3,0.45],"at":[0,0,0]},
  {"name":"Pole","primitive":"cylinder","material":"Metal","size":[0.18,5.5,0.18],"at":[0,0.3,0]},
  {"name":"Arm","primitive":"cube","material":"Metal","size":[1.4,0.14,0.14],"at":[0.7,5.65,0]},
  {"name":"LampHead","primitive":"cube","material":"LampWarm","size":[0.7,0.22,0.35],"at":[1.3,5.42,0]}
 ]}
```

## bench
Public bench, 1.8 m long, 0.45 m seat height. Small props still need real
dimensions or they look like toys beside a building.

```json
{"name":"Bench","position":[0,0,0],
 "materials":{"Wood":"#8A6A45FF","Metal":"#4A4D52FF"},
 "parts":[
  {"name":"Leg_L","primitive":"cube","material":"Metal","size":[0.1,0.45,0.5],"at":[-0.75,0,0]},
  {"name":"Leg_R","primitive":"cube","material":"Metal","size":[0.1,0.45,0.5],"at":[0.75,0,0]},
  {"name":"Seat","primitive":"cube","material":"Wood","size":[1.8,0.08,0.5],"at":[0,0.45,0]},
  {"name":"Backrest","primitive":"cube","material":"Wood","size":[1.8,0.45,0.08],"at":[0,0.53,0.21]}
 ]}
```

## bus-stop
Shelter, 3.2 × 2.5 × 1.4 m. The roof overhangs the posts rather than enclosing
them — a primitive has no interior, so nothing can sit inside the posts.

```json
{"name":"BusStop","position":[0,0,0],
 "materials":{"Metal":"#4A4D52FF","Glass":"#5B86A6FF","SignGreen":"#4E9A52FF"},
 "parts":[
  {"name":"Post_L","primitive":"cylinder","material":"Metal","size":[0.12,2.5,0.12],"at":[-1.5,0,0.6]},
  {"name":"Post_R","primitive":"cylinder","material":"Metal","size":[0.12,2.5,0.12],"at":[1.5,0,0.6]},
  {"name":"BackPanel","primitive":"cube","material":"Glass","size":[3.2,2.0,0.08],"at":[0,0.3,0.68]},
  {"name":"Roof","primitive":"cube","material":"Metal","size":[3.6,0.12,1.6],"at":[0,2.5,0.2]},
  {"name":"Sign","primitive":"cube","material":"SignGreen","size":[0.5,0.7,0.06],"at":[1.5,1.6,0.44]}
 ]}
```

## traffic-light
4 m pole with a head carrying three lamps. Lamps sit proud of the head's face
so they stay visible.

```json
{"name":"TrafficLight","position":[0,0,0],
 "materials":{"Metal":"#4A4D52FF","SignRed":"#C0483CFF","LampWarm":"#FFE9A8FF","SignGreen":"#4E9A52FF"},
 "parts":[
  {"name":"Pole","primitive":"cylinder","material":"Metal","size":[0.16,4,0.16],"at":[0,0,0]},
  {"name":"Head","primitive":"cube","material":"Metal","size":[0.42,1.2,0.3],"at":[0,2.75,0]},
  {"name":"LampRed","primitive":"sphere","material":"SignRed","size":[0.26,0.26,0.26],"at":[0,3.65,-0.2]},
  {"name":"LampAmber","primitive":"sphere","material":"LampWarm","size":[0.26,0.26,0.26],"at":[0,3.27,-0.2]},
  {"name":"LampGreen","primitive":"sphere","material":"SignGreen","size":[0.26,0.26,0.26],"at":[0,2.89,-0.2]}
 ]}
```

## tree
Street tree, ~5 m. Two offset foliage spheres read far better than one, because
a single sphere looks like a lollipop.

```json
{"name":"Tree","position":[0,0,0],
 "materials":{"Wood":"#8A6A45FF","Foliage":"#4F7A42FF"},
 "parts":[
  {"name":"Trunk","primitive":"cylinder","material":"Wood","size":[0.3,2.6,0.3],"at":[0,0,0]},
  {"name":"CanopyLow","primitive":"sphere","material":"Foliage","size":[2.8,2.4,2.8],"at":[0,2.0,0]},
  {"name":"CanopyHigh","primitive":"sphere","material":"Foliage","size":[2.2,2.0,2.2],"at":[0.4,3.4,-0.2]}
 ]}
```

## kiosk
Newsstand, 2.4 × 2.6 × 1.8 m with a serving opening implied by a darker panel.

```json
{"name":"Kiosk","position":[0,0,0],
 "materials":{"MetalLight":"#8A8F96FF","GlassDark":"#3E5F77FF","SignRed":"#C0483CFF"},
 "parts":[
  {"name":"Body","primitive":"cube","material":"MetalLight","size":[2.4,2.4,1.8],"at":[0,0,0]},
  {"name":"Opening","primitive":"cube","material":"GlassDark","size":[1.8,1.1,0.12],"at":[0,1.0,-0.92]},
  {"name":"Canopy","primitive":"cube","material":"SignRed","size":[2.8,0.14,0.9],"at":[0,2.25,-1.2]},
  {"name":"RoofCap","primitive":"cube","material":"SignRed","size":[2.6,0.2,2.0],"at":[0,2.4,0]}
 ]}
```

## billboard
6 × 3 m display on two legs, face at 3 m. The face sits proud of the frame so
it doesn't z-fight.

```json
{"name":"Billboard","position":[0,0,0],
 "materials":{"Metal":"#4A4D52FF","SignRed":"#C0483CFF","LineWhite":"#E8E4DAFF"},
 "parts":[
  {"name":"Leg_L","primitive":"cylinder","material":"Metal","size":[0.2,3.2,0.2],"at":[-2,0,0]},
  {"name":"Leg_R","primitive":"cylinder","material":"Metal","size":[0.2,3.2,0.2],"at":[2,0,0]},
  {"name":"Frame","primitive":"cube","material":"Metal","size":[6.2,3.2,0.2],"at":[0,3.2,0]},
  {"name":"Face","primitive":"cube","material":"SignRed","size":[5.9,2.9,0.08],"at":[0,3.35,-0.16]},
  {"name":"Trim","primitive":"cube","material":"LineWhite","size":[5.6,0.18,0.06],"at":[0,3.35,-0.21]}
 ]}
```

## road-segment
20 m of two-lane road with kerbs and a dashed centre line. Markings sit just
above the asphalt, never flush with it.

```json
{"name":"RoadSegment","position":[0,0,0],
 "materials":{"Asphalt":"#35353AFF","Concrete":"#A8A49BFF","LineWhite":"#E8E4DAFF"},
 "parts":[
  {"name":"Asphalt","primitive":"cube","material":"Asphalt","size":[20,0.1,8],"at":[0,0,0]},
  {"name":"Kerb_N","primitive":"cube","material":"Concrete","size":[20,0.25,1.6],"at":[0,0,-4.8]},
  {"name":"Kerb_S","primitive":"cube","material":"Concrete","size":[20,0.25,1.6],"at":[0,0,4.8]},
  {"name":"Dash_1","primitive":"cube","material":"LineWhite","size":[2,0.02,0.2],"at":[-6,0.11,0]},
  {"name":"Dash_2","primitive":"cube","material":"LineWhite","size":[2,0.02,0.2],"at":[0,0.11,0]},
  {"name":"Dash_3","primitive":"cube","material":"LineWhite","size":[2,0.02,0.2],"at":[6,0.11,0]}
 ]}
```
