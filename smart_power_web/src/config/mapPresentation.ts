/** 仅用于地图展示的夸张厚度，不表示真实海拔。道路、标记必须位于表面上方。 */
export function getMapElevation(
  scope: 'china' | 'henan' | 'province',
  city = false,
  spanDegrees?: number,
) {
  const surface =
    scope === 'china'
      ? 32000
      : city
        ? 450
        : scope === 'province' && spanDegrees
          ? Math.min(3500, Math.max(120, spanDegrees * 600))
          : 3500
  return {
    surface,
    road: surface + 350,
    marker: surface + 500,
    label: surface + (scope === 'china' ? 8000 : 800),
  }
}
