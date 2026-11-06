/** 多编号共线路段逐项匹配，避免 G4 误命中 G40/G0421。 */
export function routeCodes(value = ''): string[] {
  return [
    ...new Set(
      value
        .toUpperCase()
        .split(/[;,，；\s]+/)
        .filter((code) => /^[GS]\d+$/.test(code)),
    ),
  ]
}

export function matchesHighway(value: string | undefined, selected: string): boolean {
  return !selected || routeCodes(value).includes(selected)
}

export function matchesQuery(query: string, ...values: (string | undefined)[]): boolean {
  const text = values.filter(Boolean).join(' ').toLowerCase()
  return query
    .trim()
    .toLowerCase()
    .split(/\s+/)
    .every((word) => text.includes(word))
}
