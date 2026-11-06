export interface ProvinceSelection {
  code: number
  name: string
}
export interface ProvinceRegion extends ProvinceSelection {
  bounds: { west: number; south: number; east: number; north: number }
  boundaryUrl: string
}
export interface PublicFacility {
  id: string
  name: string
  type: 'TOLL' | 'SERVICE'
  longitude: number
  latitude: number
  ref?: string
  cityCode?: number | null
  /** 仅指公开预览所用模型规模，不代表核验后的真实站点规模。 */
  modelScale?: 'S' | 'M' | 'L'
  boundSiteId?: string
}
export interface CityRegion {
  code: number
  name: string
  bounds: { west: number; south: number; east: number; north: number }
  roadCount: number
  serviceCount: number
  tollCount: number
}
export interface BoundaryFeature {
  type: 'Feature'
  properties: { adcode?: number | string; name?: string; center?: number[]; centroid?: number[] }
  geometry: { type: string; coordinates: unknown }
}
export interface BoundaryCollection {
  type: 'FeatureCollection'
  features: BoundaryFeature[]
}
export interface RoadCollection {
  type: 'FeatureCollection'
  features: {
    type: 'Feature'
    properties: { name?: string; ref?: string }
    geometry: { type: 'LineString'; coordinates: number[][] }
  }[]
}
