import { useState, useRef, useEffect, useCallback } from 'react';
import { createPortal } from 'react-dom';

/**
 * 表格列的「操作」下拉選單。
 *
 * 採 portal 渲染至 document.body + position:fixed，開啟時依按鈕座標定位。
 * 如此可完全脫離表格的 overflow 裁切、祖先 transform（會困住 fixed 定位）、
 * 以及 React Query 背景重抓造成的重繪/動畫干擾——避免選單被遮擋、跑位或間歇消失。
 */
export interface ActionItem {
    label: string;
    onClick: () => void;
    danger?: boolean;
}

interface RowActionMenuProps {
    items: ActionItem[];
    label?: string;
}

const MENU_WIDTH = 160;
const ITEM_HEIGHT = 40;
const MENU_PADDING = 16;

const RowActionMenu = ({ items, label = '操作' }: RowActionMenuProps) => {
    const [open, setOpen] = useState(false);
    const [pos, setPos] = useState({ top: 0, left: 0 });
    const btnRef = useRef<HTMLButtonElement>(null);
    const menuRef = useRef<HTMLDivElement>(null);

    const place = useCallback(() => {
        const b = btnRef.current?.getBoundingClientRect();
        if (!b) return;
        const menuH = items.length * ITEM_HEIGHT + MENU_PADDING;
        let top = b.bottom + 2;
        // 接近視窗底部時往上翻
        if (top + menuH > window.innerHeight) {
            top = Math.max(4, b.top - menuH - 2);
        }
        // 靠右對齊；避免超出左右邊界
        let left = b.right - MENU_WIDTH;
        if (left < 4) left = 4;
        if (left + MENU_WIDTH > window.innerWidth - 4) left = window.innerWidth - MENU_WIDTH - 4;
        setPos({ top, left });
    }, [items.length]);

    const toggle = () => {
        if (!open) place();
        setOpen((o) => !o);
    };

    useEffect(() => {
        if (!open) return;
        const onDocMouseDown = (e: MouseEvent) => {
            const t = e.target as Node;
            if (menuRef.current?.contains(t) || btnRef.current?.contains(t)) return;
            setOpen(false);
        };
        const onDismiss = () => setOpen(false);
        // 捲動（含表格容器內捲動，用 capture）或縮放時關閉，避免選單停留在錯誤位置
        document.addEventListener('mousedown', onDocMouseDown);
        window.addEventListener('scroll', onDismiss, true);
        window.addEventListener('resize', onDismiss);
        const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false); };
        document.addEventListener('keydown', onKey);
        return () => {
            document.removeEventListener('mousedown', onDocMouseDown);
            window.removeEventListener('scroll', onDismiss, true);
            window.removeEventListener('resize', onDismiss);
            document.removeEventListener('keydown', onKey);
        };
    }, [open]);

    return (
        <>
            <button
                ref={btnRef}
                type="button"
                className="btn btn-outline-secondary btn-sm dropdown-toggle"
                onClick={toggle}
                aria-expanded={open}
            >
                {label}
            </button>
            {open &&
                createPortal(
                    <div
                        ref={menuRef}
                        className="dropdown-menu show"
                        style={{ position: 'fixed', top: pos.top, left: pos.left, minWidth: MENU_WIDTH, zIndex: 2000 }}
                    >
                        {items.map((it, i) => (
                            <button
                                key={i}
                                type="button"
                                className={'dropdown-item' + (it.danger ? ' text-danger' : '')}
                                onClick={() => { setOpen(false); it.onClick(); }}
                            >
                                {it.label}
                            </button>
                        ))}
                    </div>,
                    document.body,
                )}
        </>
    );
};

export default RowActionMenu;
