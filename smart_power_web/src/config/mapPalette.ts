/** 地理底图与业务线路分层：行政边界低对比，高速线路高对比。 */
export const mapPalette = {
  surface: '#173f60',
  selectedSurface: '#215e83',
  sideWall: '#06192d',
  boundary: '#284b65',
  selectedBoundary: '#57829f',
  roadNational: '#78dcff',
  roadProvincial: '#a1c8ff',
  roadEdge: '#08253b',
} as const

/** 全国概览单独使用发光省界，不影响承载高速线路的省市底图。 */
export const nationalMapPalette = {
  surface: '#12385f',
  henanSurface: '#147eb2',
  selectedSurface: '#228cc1',
  boundary: '#48bce9',
  selectedBoundary: '#b5f5ff',
} as const
