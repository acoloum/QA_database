/** 通道排序：TUS-1…TUS-12 在前，接著 SAT-1…SAT-6，其餘依字母；同群依數字遞增 */
export function sortChannels(keys: string[]): string[] {
  const rank = (name: string): [number, string, number] => {
    const m = name.match(/^([A-Za-z]+)[-_ ]?(\d+)?/);
    const prefix = (m?.[1] || name).toUpperCase();
    const num = m?.[2] ? parseInt(m[2], 10) : 0;
    const pri = prefix === 'TUS' ? 0 : prefix === 'SAT' ? 1 : 2;
    return [pri, prefix, num];
  };
  return [...keys].sort((a, b) => {
    const [pa, sa, na] = rank(a);
    const [pb, sb, nb] = rank(b);
    if (pa !== pb) return pa - pb;
    if (sa !== sb) return sa < sb ? -1 : 1;
    return na - nb;
  });
}
