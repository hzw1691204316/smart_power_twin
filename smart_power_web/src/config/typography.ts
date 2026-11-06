/** Cesium标签画在Canvas内，读取相同的UI字体以免与页面文字不一致。 */
export function mapFont(size: number, weight = 500): string {
  const family =
    typeof document !== 'undefined'
      ? getComputedStyle(document.documentElement).getPropertyValue('--font-ui').trim()
      : ''
  return `${weight} ${size}px ${family || '"Microsoft YaHei UI", "Microsoft YaHei", sans-serif'}`
}
