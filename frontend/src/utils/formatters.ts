/**
 * 金融数字格式化工具函数
 * 所有函数为纯函数，可安全用于 computed 和 template
 */

/**
 * 格式化百分比（保留指定小数位）
 * formatPercent(0.1234) => "+12.34%"
 * formatPercent(-0.05) => "-5.00%"
 * formatPercent(null) => "--"
 */
export function formatPercent(value: number | null | undefined, decimals = 2): string {
  if (value === null || value === undefined) return '--'
  const sign = value >= 0 ? '+' : ''
  return `${sign}${(value * 100).toFixed(decimals)}%`
}

/**
 * 格式化货币（千分位）
 * formatCurrency(1234567.89) => "1,234,567.89"
 * formatCurrency(1234567.89, 'USD') => "$1,234,567.89"
 */
export function formatCurrency(value: number, currency: 'CNY' | 'USD' = 'CNY'): string {
  const formatter = new Intl.NumberFormat('zh-CN', {
    style: currency === 'CNY' ? 'decimal' : 'currency',
    currency: currency === 'USD' ? 'USD' : undefined,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
  return formatter.format(value)
}

/**
 * 格式化数值（保留指定小数位，null 返回 '--'）
 */
export function formatNumber(value: number | null | undefined, decimals = 2): string {
  if (value === null || value === undefined) return '--'
  return value.toFixed(decimals)
}

/**
 * 格式化日期（ISO 字符串 -> 友好格式）
 * formatDate("2026-03-18T10:30:00Z") => "2026/03/18 10:30"
 */
export function formatDate(isoString: string | null | undefined, includeTime = true): string {
  if (!isoString) return '--'
  const date = new Date(isoString)
  const dateStr = date.toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit' })
  if (!includeTime) return dateStr
  const timeStr = date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  return `${dateStr} ${timeStr}`
}

/**
 * 格式化相对时间（"3 分钟前"/"2 小时前"）
 */
export function formatRelativeTime(isoString: string | null | undefined): string {
  if (!isoString) return '--'
  const diff = Date.now() - new Date(isoString).getTime()
  const minutes = Math.floor(diff / 60000)
  if (minutes < 1) return '刚刚'
  if (minutes < 60) return `${minutes} 分钟前`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours} 小时前`
  const days = Math.floor(hours / 24)
  return `${days} 天前`
}

/**
 * 格式化权重（0.35 -> "35.0%"，不带正负号）
 */
export function formatWeight(value: number | null | undefined, decimals = 1): string {
  if (value === null || value === undefined) return '--'
  return `${(value * 100).toFixed(decimals)}%`
}

/**
 * 获取收益率对应的 CSS 颜色类名
 */
export function getReturnColorClass(value: number | null | undefined): string {
  if (value === null || value === undefined || value === 0) return 'text-muted'
  return value > 0 ? 'text-success' : 'text-danger'
}
