import { Table, Card, Spinner } from 'react-bootstrap';
import { useRiskReleases } from '../../hooks/useNCMR';
import QueryErrorAlert from '../../components/common/QueryErrorAlert';

// 未授權放行風險清單頁面（IATF 16949 §8.7.1.1）
const RiskReleasePage = () => {
    const { data = [], isLoading, isError, refetch } = useRiskReleases();

    return (
        <Card className="m-3">
            <Card.Header>
                <h5 className="mb-0">未授權放行風險清單（IATF 16949 §8.7.1.1）</h5>
                <small className="text-muted">超出客戶規格但未取得客戶授權即放行的記錄</small>
            </Card.Header>
            <Card.Body>
                <QueryErrorAlert show={isError} onRetry={refetch} />
                {isLoading ? <Spinner animation="border" /> : (
                    <Table bordered hover responsive size="sm">
                        <thead>
                            <tr>
                                <th>NCMR單號</th><th>產品資訊</th><th>材質</th><th>廠商</th>
                                <th>處置數量</th><th>未授權放行理由</th><th>處置人</th><th>處置時間</th>
                            </tr>
                        </thead>
                        <tbody>
                            {data.map((r, i) => (
                                <tr key={i}>
                                    <td>{r.NCMR單號}</td>
                                    <td>{r.產品資訊}</td>
                                    <td>{r.材質}</td>
                                    <td>{r.廠商}</td>
                                    <td>{r.處置數量}</td>
                                    <td className="text-danger">{r.未授權放行理由}</td>
                                    <td>{r.處置人姓名}</td>
                                    <td>{r.處置時間}</td>
                                </tr>
                            ))}
                            {data.length === 0 && (
                                <tr><td colSpan={8} className="text-center text-muted">無風險放行記錄</td></tr>
                            )}
                        </tbody>
                    </Table>
                )}
            </Card.Body>
        </Card>
    );
};

export default RiskReleasePage;
