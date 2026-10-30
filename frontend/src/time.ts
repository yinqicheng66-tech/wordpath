/** "10 分钟后", "3 小时后", "2 天后" */
export function untilText(iso: string, now: Date = new Date()): string {
  const minutes = Math.max(1, Math.round((new Date(iso).getTime() - now.getTime()) / 60000));
  if (minutes < 60) return `${minutes} 分钟后`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} 小时后`;
  return `${Math.round(hours / 24)} 天后`;
}
