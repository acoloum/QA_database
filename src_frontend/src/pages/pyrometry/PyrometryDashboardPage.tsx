import { Card, Badge, Row, Col } from 'react-bootstrap';
import { useNavigate } from 'react-router';
import { usePyrometryDashboard } from '../../hooks/usePyrometry';
import type { FurnaceStatus, PyrometryDashboardRow } from '../../types';

const STATUS_BADGE: Record<FurnaceStatus, string> = {
  '逾期': 'danger',
  '即將到期': 'warning',
  '正常': 'success',
  '尚無紀錄': 'secondary',
  '不合格': 'danger',
};

// 數字越小越嚴重，作為排序與「取較嚴重狀態」的依據
const STATUS_ORDER: Record<FurnaceStatus, number> = { '逾期': 0, '不合格': 0, '即將到期': 1, '尚無紀錄': 2, '正常': 3 };

// 依狀態給定卡片配色（邊條 / 標題列 / 卡片底色）
interface CardTheme {
  accent: string;     // 左側邊條與標題文字
  headerBg: string;   // 標題列底色
  bodyBg: string;     // 卡片底色
}

const STATUS_THEME: Record<FurnaceStatus, CardTheme> = {
  '逾期':     { accent: '#dc3545', headerBg: '#fdecea', bodyBg: '#fff8f8' },
  '不合格':   { accent: '#dc3545', headerBg: '#fdecea', bodyBg: '#fff8f8' },
  '即將到期': { accent: '#fd7e14', headerBg: '#fff4e8', bodyBg: '#fffcf7' },
  '正常':     { accent: '#198754', headerBg: '#e9f6ef', bodyBg: '#fafdfb' },
  '尚無紀錄': { accent: '#6c757d', headerBg: '#f1f3f5', bodyBg: '#fcfcfd' },
};

// 取 TUS / SAT 中較嚴重的狀態，作為整張卡片的代表配色與排序依據
const worstStatus = (f: PyrometryDashboardRow): FurnaceStatus =>
  STATUS_ORDER[f.TUS.狀態] <= STATUS_ORDER[f.SAT.狀態] ? f.TUS.狀態 : f.SAT.狀態;

const PyrometryDashboardPage = () => {
  const navigate = useNavigate();
  const { data: result, isLoading } = usePyrometryDashboard();

  // 依最嚴重狀態排序，讓需關注的爐子（逾期 / 不合格）排在前面
  const rows = [...(result || [])].sort(
    (a, b) => STATUS_ORDER[worstStatus(a)] - STATUS_ORDER[worstStatus(b)]
  );

  if (isLoading) return <p>載入中…</p>;

  return (
    <div>
      <h4 className="mb-3">爐溫測試總覽</h4>
      <Row className="g-3">
        {rows.map(f => {
          const theme = STATUS_THEME[worstStatus(f)];
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
                  {([['TUS', f.TUS], ['SAT', f.SAT]] as const).map(([label, info]) => (
                    <div key={label}>
                      <div className="text-muted small">{label}</div>
                      <Badge bg={STATUS_BADGE[info.狀態]}>{info.狀態}</Badge>
                      {info.下次應測日 && (
                        <div className="text-muted" style={{ fontSize: '0.75rem' }}>下次：{info.下次應測日}</div>
                      )}
                    </div>
                  ))}
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
