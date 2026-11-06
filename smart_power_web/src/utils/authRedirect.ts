/** 登录后只允许站内路径；拒绝外链、双斜线及反斜线，避免开放重定向。 */
export function safeRedirect(value: unknown): string {
  if (
    typeof value !== 'string' ||
    !value.startsWith('/') ||
    value.startsWith('//') ||
    /[\\\s]/.test(value) ||
    [...value].some((character) => character.charCodeAt(0) < 32) ||
    /^\/login(?:[/?#]|$)/i.test(value)
  )
    return '/overview'
  return value
}
