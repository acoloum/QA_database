import { Pagination } from 'react-bootstrap';

interface PaginationBarProps {
    page: number;
    perPage?: number;
    total?: number;
    totalPages?: number;
    onPageChange: (page: number) => void;
}

const PaginationBar = ({ page, perPage = 20, total, totalPages: totalPagesProp, onPageChange }: PaginationBarProps) => {
    const totalPages = totalPagesProp ?? Math.ceil((total ?? 0) / perPage);
    if (totalPages <= 1) return null;

    const getPageNumbers = () => {
        const pages: (number | 'ellipsis-start' | 'ellipsis-end')[] = [];
        if (totalPages <= 7) {
            for (let i = 1; i <= totalPages; i++) pages.push(i);
        } else {
            pages.push(1);
            if (page > 3) pages.push('ellipsis-start');
            for (let i = Math.max(2, page - 1); i <= Math.min(totalPages - 1, page + 1); i++) {
                pages.push(i);
            }
            if (page < totalPages - 2) pages.push('ellipsis-end');
            pages.push(totalPages);
        }
        return pages;
    };

    return (
        <div className="d-flex justify-content-between align-items-center mt-3">
            <small className="text-muted">
                {total != null ? `共 ${total} 筆，` : ''}第 {page} / {totalPages} 頁
            </small>
            <Pagination size="sm" className="mb-0">
                <Pagination.First disabled={page === 1} onClick={() => page > 1 && onPageChange(1)} aria-label="第一頁" />
                <Pagination.Prev disabled={page === 1} onClick={() => page > 1 && onPageChange(page - 1)} aria-label="上一頁" />
                {getPageNumbers().map((p) =>
                    p === 'ellipsis-start' || p === 'ellipsis-end'
                        ? <Pagination.Ellipsis key={p} disabled />
                        : <Pagination.Item key={p} active={p === page} onClick={() => onPageChange(p as number)}>{p}</Pagination.Item>
                )}
                <Pagination.Next disabled={page === totalPages} onClick={() => page < totalPages && onPageChange(page + 1)} aria-label="下一頁" />
                <Pagination.Last disabled={page === totalPages} onClick={() => page < totalPages && onPageChange(totalPages)} aria-label="最後一頁" />
            </Pagination>
        </div>
    );
};

export default PaginationBar;
