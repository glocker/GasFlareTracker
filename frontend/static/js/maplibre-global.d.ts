// maplibre-gl is loaded as a UMD <script> in index.html (not an ES import), so it
// has no type info by default even with maplibre-gl installed as a
// devDependency. This declares the global the CDN script exposes.
declare const maplibregl: typeof import("maplibre-gl");
