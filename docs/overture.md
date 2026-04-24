# the project resumed with overturemaps for a lot of reasons
mainly because of *LACKING OF DATA* from OSM for our cherry picked area

see:
https://explore.overturemaps.org/?mode=inspect&feature=base.land_use.8ba7fb60-9393-322c-ad08-4e81894fefd0#14.4/29.42887/32.40103


command to download that data:

```bash
overturemaps download --bbox=32.37,29.41,32.43,29.45 -f geojson --type=building -o galala_buildings.geojson
```
