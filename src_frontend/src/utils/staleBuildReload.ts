/**
 * 前端重建後，已開啟的舊分頁仍引用舊雜湊檔名；切換頁面時 lazy chunk 會載入失敗
 * （Vite 觸發 `vite:preloadError`）。此時自動重新整理一次以取得新版 index.html。
 *
 * 以 sessionStorage 記錄上次重整時間，短時間內不重複重整，
 * 避免伺服器真的掛掉時陷入無限重新整理。
 */
const STORAGE_KEY = 'qms:stale-build-reload-at';
const RELOAD_COOLDOWN_MS = 10_000;

interface ReloadDeps {
    storage: Pick<Storage, 'getItem' | 'setItem'> | null;
    now: () => number;
    reload: () => void;
}

/** 回傳 true 表示已觸發重新整理（呼叫端應 preventDefault 以免錯誤再往外拋） */
export const reloadOnceForStaleBuild = ({ storage, now, reload }: ReloadDeps): boolean => {
    try {
        const last = Number(storage?.getItem(STORAGE_KEY) ?? 0);
        if (now() - last < RELOAD_COOLDOWN_MS) return false;
        storage?.setItem(STORAGE_KEY, String(now()));
    } catch {
        // 無痕模式等 storage 無法使用時仍重整一次；最壞情況由瀏覽器自身處理
    }
    reload();
    return true;
};

const safeSessionStorage = (): Storage | null => {
    try {
        return window.sessionStorage;
    } catch {
        return null;
    }
};

export const installStaleBuildReload = () => {
    window.addEventListener('vite:preloadError', (event) => {
        const reloaded = reloadOnceForStaleBuild({
            storage: safeSessionStorage(),
            now: () => Date.now(),
            reload: () => window.location.reload(),
        });
        if (reloaded) event.preventDefault();
    });
};
