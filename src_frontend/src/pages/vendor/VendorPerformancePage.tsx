import { useState } from 'react';
import { Container, Card, Table, Badge, Form, Row, Col, Spinner, Button } from 'react-bootstrap';
import { Line } from 'react-chartjs-2';
import { useAuth } from '../../context/useAuth';
import QueryErrorAlert from '../../components/common/QueryErrorAlert';
import '../../utils/chartSetup';
import {
  useVendorPerformanceList,
  useVendorPerformanceHistory,
  useRefreshVendorPerformance,
} from '../../hooks/useVendorPerformance';

// 根據分數回傳 Badge 顏色
const scoreVariant = (score: number) =>
  score >= 80 ? 'success' : score >= 60 ? 'warning' : 'danger';

const VendorPerformancePage = () => {
  const today = new Date();
  const [period, setPeriod] = useState(
    `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}`
  );
  const [selectedVendorId, setSelectedVendorId] = useState<number | null>(null);
  const { hasPermission } = useAuth();
  const refreshMutation = useRefreshVendorPerformance();

  const { data: list = [], isLoading, isError, refetch } = useVendorPerformanceList(period);
  const { data: history = [] } = useVendorPerformanceHistory(selectedVendorId ?? 0);
  const canRefresh = hasPermission('vendor.manage');

  return (
    <Container fluid className="py-4">
      <div className="d-flex justify-content-between align-items-center mb-4">
        <h4 className="mb-0">廠商績效評比</h4>
        <div className="d-flex gap-2 align-items-center">
          {canRefresh && (
            <Button
              variant="outline-primary"
              size="sm"
              disabled={refreshMutation.isPending}
              onClick={() => refreshMutation.mutate(period)}
            >
              {refreshMutation.isPending ? (
                <>
                  <Spinner animation="border" size="sm" className="me-1" />
                  計算中…
                </>
              ) : (
                '重新計算'
              )}
            </Button>
          )}
          <Form.Control
            type="month"
            value={period}
            onChange={e => setPeriod(e.target.value)}
            style={{ width: '160px' }}
          />
        </div>
      </div>

      <QueryErrorAlert show={isError} onRetry={refetch} />

      <Card className="shadow-sm mb-4">
        <Card.Body className="p-0">
          <Table hover responsive className="dense-list-table mb-0">
            <thead className="table-light">
              <tr>
                <th>廠商</th>
                <th>評分</th>
                <th>檢驗批次</th>
                <th>不良批次</th>
                <th>缺陷率</th>
                <th>CAPA件數</th>
                <th>客訴件數</th>
                <th>平均CAPA天數</th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr><td colSpan={8} className="text-center py-4">
                  <Spinner animation="border" size="sm" className="me-2" />載入中…
                </td></tr>
              ) : list.map(row => (
                <tr
                  key={row.vendor_id}
                  style={{ cursor: 'pointer' }}
                  className={selectedVendorId === row.vendor_id ? 'table-active' : ''}
                  onClick={() => setSelectedVendorId(
                    selectedVendorId === row.vendor_id ? null : row.vendor_id
                  )}
                >
                  <td className="fw-semibold">{row.vendor_name}</td>
                  <td>
                    <Badge bg={scoreVariant(row.score)} style={{ fontSize: '0.9rem' }}>
                      {row.score}
                    </Badge>
                  </td>
                  <td>{row.inspection_count}</td>
                  <td>{row.defect_count}</td>
                  <td className={row.defect_rate > 10 ? 'text-danger fw-semibold' : ''}>
                    {row.defect_rate.toFixed(1)}%
                  </td>
                  <td>{row.capa_count}</td>
                  <td>{row.complaint_count}</td>
                  <td>{row.avg_capa_days != null ? `${row.avg_capa_days} 天` : '—'}</td>
                </tr>
              ))}
            </tbody>
          </Table>
        </Card.Body>
      </Card>

      {selectedVendorId && history.length > 0 && (
        <Card className="shadow-sm">
          <Card.Header className="fw-semibold">
            {list.find(r => r.vendor_id === selectedVendorId)?.vendor_name} — 近期評分走勢
          </Card.Header>
          <Card.Body>
            <Row>
              <Col md={8}>
                <Line
                  data={{
                    labels: [...history].reverse().map(h => h.period),
                    datasets: [{
                      label: '績效評分',
                      data: [...history].reverse().map(h => h.score),
                      borderColor: '#0d6efd',
                      backgroundColor: 'rgba(13,110,253,0.1)',
                      tension: 0.3,
                      fill: true,
                    }],
                  }}
                  options={{
                    responsive: true,
                    scales: { y: { min: 0, max: 100 } },
                    plugins: { legend: { display: false } },
                  }}
                />
              </Col>
              <Col md={4}>
                <Table size="sm">
                  <thead><tr><th>期間</th><th>評分</th><th>缺陷率</th></tr></thead>
                  <tbody>
                    {history.map(h => (
                      <tr key={h.period}>
                        <td>{h.period}</td>
                        <td><Badge bg={scoreVariant(h.score)}>{h.score}</Badge></td>
                        <td>{h.defect_rate.toFixed(1)}%</td>
                      </tr>
                    ))}
                  </tbody>
                </Table>
              </Col>
            </Row>
          </Card.Body>
        </Card>
      )}
    </Container>
  );
};

export default VendorPerformancePage;
