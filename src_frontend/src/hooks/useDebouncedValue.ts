import { useEffect, useState } from 'react';

/**
 * 回傳 value 的防抖（debounce）版本：value 停止變動達 delay 毫秒後才更新。
 *
 * 用於篩選輸入框——輸入框本身維持即時顯示（受控於原始 state），但送進
 * 查詢鍵的值延遲更新，避免每個按鍵都觸發一次清單查詢與其下游的連鎖請求
 * （公差比對、SPC 圖表等）。
 */
export function useDebouncedValue<T>(value: T, delay = 300): T {
  const [debounced, setDebounced] = useState(value);

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);

  return debounced;
}
