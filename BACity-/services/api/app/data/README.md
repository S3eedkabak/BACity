# Official Bratislava district boundaries

`bratislava-districts.geojson` is a WGS84 snapshot of all 17 polygons from the
City of Bratislava's public administrative-boundary FeatureServer, retrieved
2026-10-21. Geometry is unchanged; only the official numeric district code and
Slovak name are retained as properties. `label_coordinates` is a PostGIS
`ST_PointOnSurface` interior label anchor; containment always uses the original
polygon geometry. No geometry was drawn from the reference
image, simplified, or inferred from cluster positions.

Source: https://geoportal.bratislava.sk/hSite/rest/services/Hosted/Administrat%C3%ADvne_hranice_mestsk%C3%BDch_%C4%8Dast%C3%AD_Bratislavy/FeatureServer/0

Query: `/query?where=1%3D1&outFields=*&outSR=4326&f=geojson`.
Publisher response ETag: `W/"1721743375069"`.

Retain city attribution when displaying these administrative boundaries. Refresh
through a reviewed data/migration change; never substitute a sketch or centroid
bounding box for district membership. Shared boundaries belong to the lowest
covering official district code to make district totals disjoint.

Original author: **GKÚ Bratislava**. License: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
The public enterprise portal item explicitly identifies both, verified 2026-10-21:
https://geoportal.bratislava.sk/pfa/sharing/rest/content/items/a793c344be824577a6b0c69470fb723d?f=pjson
The service's `/rest/info` identifies `/pfa` as its owning portal. The public
item is titled “Územné hranice mestských častí Bratislavy”; its description
identifies 2022 administrative boundary data. Bratislava publishes this service;
GKÚ is the credited original author. Transformations: publisher's outSR=4326
export, retained official identifiers/names, added interior label anchors. The
polygon geometry itself is neither simplified nor redrawn.
