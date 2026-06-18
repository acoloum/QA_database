import { useQuery } from '@tanstack/react-query';
import { Card, Badge, Row, Col } from 'react-bootstrap';
import { useNavigate } from 'react-router-dom';
import api from '../../services/api';

interface DueInfo {
  最近測試日: string | null;
  下次應測日: string | null;
  狀態: '逾期' | '即將到期' | '正常' | '尚無紀錄' | '不合格';
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
  '不合格': 'danger',
};

const STATUS_ORDER: Record<string, number> = { '逾期': 0, '不合格': 0, '即將到期': 1, '尚無紀錄': 2, '正常': 3 };

// 依狀態給定卡片配色（邊條 / 標題列 / 卡片底色）
interface CardTheme {
  accent: string;     // 左側邊條與標題文字
  headerBg: string;   // 標題列底色
  bodyBg: string;     // 卡片底色
}

const STATUS_THEME: Record<string, CardTheme> = {
  '逾期':     { accent: '#dc3545', headerBg: '#fdecea', bodyBg: '#fff8f8' },
  '不合格':   { accent: '#dc3545', headerBg: '#fdecea', bodyBg: '#fff8f8' },
  '即將到期': { accent: '#fd7e14', headerBg: '#fff4e8', bodyBg: '#fffcf7' },
  '正常':     { accent: '#198754', headerBg: '#e9f6ef', bodyBg: '#fafdfb' },
  '尚無紀錄': { accent: '#6c757d', headerBg: '#f1f3f5', bodyBg: '#fcfcfd' },
};

// 取 TUS / SAT 中最嚴重的狀態作為整張卡片的代表配色
const worstStatus = (f: BoardRow): string => {
  const t = STATUS_ORDER[f.TUS.狀態] ?? 3;
  const s = STATUS_ORDER[f.SAT.狀態] ?? 3;
  return (t <= s ? f.TUS.狀態 : f.SAT.狀態);
};

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
        {rows.map(f => {
          const theme = STATUS_THEME[worstStatus(f)] ?? STATUS_THEME['尚無紀錄'];
          return (
          <Col key={f.爐子ID} md={6} lg={4}>
            <Card
              className="h-100 pyrometry-card"
              style={{
                cursor: 'pointer',
                ['--pyro-accent' as string]: theme.accent,
                ['--pyro-header-bg' as string]: theme.headerBg,
                ['--pyro-body-bg' as string]: theme.bodyBg,
              }}
              onClick={() => navigate(`/pyrometry/tests?furnace_id=${f.爐子ID}`)}>
              <Card.Header className="d-flex justify-content-between align-items-center">
                <strong style={{ color: theme.accent }}>{f.爐號}</strong>
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
          );
        })}
      </Row>
    </div>
  );
};

export default PyrometryDashboardPage;
