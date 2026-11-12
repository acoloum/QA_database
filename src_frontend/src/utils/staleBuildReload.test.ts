import { describe, expect, it, vi } from 'vitest';
import { reloadOnceForStaleBuild } from './staleBuildReload';

const memoryStorage = () => {
    const map = new Map<string, string>();
    return {
        getItem: (k: string) => map.get(k) ?? null,
        setItem: (k: string, v: string) => { map.set(k, v); },
    };
};

describe('reloadOnceForStaleBuild', () => {
    it('首次 chunk 載入失敗時重新整理', () => {
        const reload = vi.fn();
        expect(reloadOnceForStaleBuild({ storage: memoryStorage(), now: () => 100_000, reload })).toBe(true);
        expect(reload).toHaveBeenCalledOnce();
    });

    it('冷卻時間內再次失敗不重整，避免伺服器停機時無限重新整理', () => {
        const storage = memoryStorage();
        const reload = vi.fn();
        reloadOnceForStaleBuild({ storage, now: () => 100_000, reload });
        expect(reloadOnceForStaleBuild({ storage, now: () => 105_000, reload })).toBe(false);
        expect(reload).toHaveBeenCalledOnce();
    });

    it('超過冷卻時間後可再次重整', () => {
        const storage = memoryStorage();
        const reload = vi.fn();
        reloadOnceForStaleBuild({ storage, now: () => 100_000, reload });
        expect(reloadOnceForStaleBuild({ storage, now: () => 111_000, reload })).toBe(true);
        expect(reload).toHaveBeenCalledTimes(2);
    });

    it('storage 無法使用時仍重整', () => {
        const reload = vi.fn();
        const storage = {
            getItem: () => { throw new Error('blocked'); },
            setItem: () => { throw new Error('blocked'); },
        };
        expect(reloadOnceForStaleBuild({ storage, now: () => 1, reload })).toBe(true);
        expect(reload).toHaveBeenCalledOnce();
    });
});
