import { Alert, Button } from 'react-bootstrap';

interface QueryErrorAlertProps {
    /** 通常直接傳 React Query 的 isError */
    show: boolean;
    /** 覆寫預設訊息（例如要指明是哪一份資料載入失敗） */
    message?: string;
    /** 有給就顯示「重新載入」按鈕，通常傳 React Query 的 refetch */
    onRetry?: () => void;
}

/**
 * 清單／統計載入失敗時的統一提示。
 *
 * 沒有這個提示時，查詢失敗的頁面會停在載入中或顯示空清單，
 * 使用者無法分辨「真的沒有資料」與「後端掛了」。
 */
const QueryErrorAlert = ({
    show,
    message = '資料載入失敗，請稍後再試或重新整理頁面',
    onRetry,
}: QueryErrorAlertProps) => {
    if (!show) return null;

    return (
        <Alert variant="danger" className="d-flex justify-content-between align-items-center mb-3">
            <span role="alert">
                <i className="bi bi-exclamation-triangle-fill me-2" />
                {message}
            </span>
            {onRetry && (
                <Button variant="outline-danger" size="sm" onClick={() => onRetry()}>
                    重新載入
                </Button>
            )}
        </Alert>
    );
};

export default QueryErrorAlert;
