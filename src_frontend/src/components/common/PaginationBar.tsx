import { Pagination } from 'react-bootstrap';

interface PaginationBarProps {
    page: number;
    perPage: number;
    total: number;
    onPageChange: (page: number) => void;
}

const PaginationBar = ({ page, perPage, total, onPageChange }: PaginationBarProps) => {
    const totalPages = Math.ceil(total / perPage);
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
                共 {total} 筆，第 {page} / {totalPages} 頁
            </small>
            <Pagination size="sm" className="mb-0">
                <Pagination.Prev disabled={page === 1} onClick={() => onPageChange(page - 1)} />
                {getPageNumbers().map((p, idx) =>
                    p === 'ellipsis-start' || p === 'ellipsis-end'
                        ? <Pagination.Ellipsis key={p} disabled />
                        : <Pagination.Item key={idx} active={p === page} onClick={() => onPageChange(p as number)}>{p}</Pagination.Item>
                )}
                <Pagination.Next disabled={page === totalPages} onClick={() => onPageChange(page + 1)} />
            </Pagination>
        </div>
    );
};

export default PaginationBar;
