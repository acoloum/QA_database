import { useQuery } from '@tanstack/react-query';
import { Card, Badge, Row, Col } from 'react-bootstrap';
import { useNavigate } from 'react-router-dom';
import api from '../../services/api';

interface DueInfo {
  最近測試日: string | null;
  下次應測日: string | null;
  狀態: '逾期' | '即將到期' | '正常' | '尚無紀錄';
}

interface BoardRow {
  爐子ID: number;
  爐號: string;
  名稱: string;
  製程類型: string;
  TUS: DueInfo;
  SAT: DueInfo;
  最近結果: { 測試類型: string; 測試日期: string; 是否合格: boolean } | null;
}

const STATUS_BADGE: Record<string, string> = {
  '逾期': 'danger',
  '即將到期': 'warning',
  '正常': 'success',
  '尚無紀錄': 'secondary',
};

const STATUS_ORDER: Record<string, number> = { '逾期': 0, '即將到期': 1, '尚無紀錄': 2, '正常': 3 };

const PyrometryDashboardPage = () => {
  const navigate = useNavigate();
  const { data: result, isLoading } = useQuery({
    queryKey: ['pyrometry-dashboard'],
    queryFn: () => api.get<{ data: BoardRow[] }>('/pyrometry/dashboard').then(r => r.data.data),
  });

  const rows = [...(result || [])].sort((a, b) => {
    const worstA = Math.min(STATUS_ORDER[a.TUS.狀態] ?? 3, STATUS_ORDER[a.SAT.狀態] ?? 3);
    const worstB = Math.min(STATUS_ORDER[b.TUS.狀態] ?? 3, STATUS_ORDER[b.SAT.狀態] ?? 3);
    return worstA - worstB;
  });

  if (isLoading) return <p>載入中…</p>;

  return (
    <div>
      <h4 className="mb-3">爐溫測試總覽</h4>
      <Row className="g-3">
        {rows.map(f => (
          <Col key={f.爐子ID} md={6} lg={4}>
            <Card className="h-100" style={{ cursor: 'pointer' }}
              onClick={() => navigate(`/pyrometry/tests?furnace_id=${f.爐子ID}`)}>
              <Card.Header className="d-flex justify-content-between align-items-center">
                <strong>{f.爐號}</strong>
                <span className="text-muted small">{f.製程類型}</span>
              </Card.Header>
              <Card.Body>
                <div className="fw-bold mb-2">{f.名稱}</div>

                {f.最近結果 && (
                  <div className="mb-2">
                    <span className="text-muted small">最近測試：</span>
                    <Badge bg={f.最近結果.是否合格 ? 'success' : 'danger'} className="ms-1">
                      {f.最近結果.是否合格 ? '合格' : '不合格'}
                    </Badge>
                    <span className="text-muted small ms-1">{f.最近結果.測試日期}</span>
                  </div>
                )}

                <div className="d-flex gap-3">
                  <div>
                    <div className="text-muted small">TUS</div>
                    <Badge bg={STATUS_BADGE[f.TUS.狀態]}>{f.TUS.狀態}</Badge>
                    {f.TUS.下次應測日 && (
                      <div className="text-muted" style={{ fontSize: '0.75rem' }}>下次：{f.TUS.下次應測日}</div>
                    )}
                  </div>
                  <div>
                    <div className="text-muted small">SAT</div>
                    <Badge bg={STATUS_BADGE[f.SAT.狀態]}>{f.SAT.狀態}</Badge>
                    {f.SAT.下次應測日 && (
                      <div className="text-muted" style={{ fontSize: '0.75rem' }}>下次：{f.SAT.下次應測日}</div>
                    )}
                  </div>
                </div>
              </Card.Body>
            </Card>
          </Col>
        ))}
      </Row>
    </div>
  );
};

export default PyrometryDashboardPage;
