/**
 * 前端共享工具函数
 */

/**
 * 格式化时间戳为可读日期
 * @param timestamp Unix 时间戳（秒）
 * @returns 格式化的日期字符串
 */
export function formatDate(timestamp: number): string {
  if (!timestamp) return '未知时间';
  
  const date = new Date(timestamp * 1000);
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  const hours = String(date.getHours()).padStart(2, '0');
  const minutes = String(date.getMinutes()).padStart(2, '0');
  
  return `${year}-${month}-${day} ${hours}:${minutes}`;
}

/**
 * 格式化哈希值，显示首尾部分
 * @param hash 完整的哈希字符串
 * @param startLen 开头显示长度
 * @param endLen 结尾显示长度
 * @returns 格式化后的哈希字符串
 */
export function formatHash(hash: string, startLen = 8, endLen = 8): string {
  if (!hash || hash.length <= startLen + endLen) return hash;
  return `${hash.slice(0, startLen)}...${hash.slice(-endLen)}`;
}

/**
 * 复制文本到剪贴板
 * @param text 要复制的文本
 * @returns 是否成功
 */
export async function copyToClipboard(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch (err) {
    console.error('复制失败:', err);
    return false;
  }
}

/**
 * 诊断状态标签颜色
 */
export function getStatusColor(status: string): string {
  switch (status?.toLowerCase()) {
    case 'confirmed':
      return 'bg-green-100 text-green-800';
    case 'pending':
      return 'bg-yellow-100 text-yellow-800';
    case 'failed':
      return 'bg-red-100 text-red-800';
    default:
      return 'bg-gray-100 text-gray-800';
  }
}
