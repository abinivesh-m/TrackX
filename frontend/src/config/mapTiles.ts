// frontend/src/config/mapTiles.ts
//
// Central tile-provider configuration for every Leaflet map in the app
// (CameraMap, CongestionMap, TrafficHeatmap, TrajectoryMap).
//
// Finding: all four map components had a hardcoded CARTO dark-tile URL
// (basemaps.cartocdn.com/dark_all/...). CARTO's anonymous/keyless raster
// endpoint has become unreliable in production - instead of map imagery it
// can return placeholder tiles whose text literally reads "API KEY
// REQUIRED", tiled across the whole map. That is exactly what appeared in
// the deployed app and must never ship.
//
// Default provider is now standard OpenStreetMap raster tiles
// (tile.openstreetmap.org) - the most widely used, genuinely free,
// no-registration, no-API-key tile source available, so the map always
// renders without any account or credential setup, in any environment.
//
// The provider stays environment-configurable for the future: set
// VITE_MAP_TILE_URL / VITE_MAP_TILE_ATTRIBUTION in frontend/.env (see
// frontend/.env.example - .env itself is gitignored) to point at a
// different provider. If that provider needs a key, bake the key into the
// URL you put in your own local/deployment .env - it is never hardcoded or
// committed here.

export const MAP_TILE_URL: string =
  (import.meta.env.VITE_MAP_TILE_URL as string | undefined) ||
  'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png'

export const MAP_TILE_ATTRIBUTION: string =
  (import.meta.env.VITE_MAP_TILE_ATTRIBUTION as string | undefined) ||
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'

export const MAP_TILE_MAX_ZOOM = 19
export const MAP_TILE_MIN_ZOOM = 3
