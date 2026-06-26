import { Badge, Button, Card, Col, Form, Row, Table } from 'react-bootstrap';
import {
  COMPLAINT_STATUS_VARIANT,
  COMPLAINT_TYPE_LABELS,
} from '../../hooks/useComplaint';
import type { ComplaintType, CustomerComplaint } from '../../types';

export interface ComplaintFilters {
  customer: string;
  material: string;
  spec: string;
  status: string;
  type: string;
  dateFrom: string;
  dateTo: string;
  repeat: '' | 'true' | 'false';
}

interface ComplaintFilterBarProps {
  filters: ComplaintFilters;
  onFilterChange: (key: keyof ComplaintFilters, value: string) => void;
  onReset: () => void;
}

export const ComplaintFilterBar = ({ filters, onFilterChange, onReset }: ComplaintFilterBarProps) => (
  <Card className="mb-3 shadow-sm">
    <Card.Body className="py-2">
      <Row className="g-2 align-items-end">
        <Col xs={6} md={2}>
          <Form.Label className="small mb-1">客戶</Form.Label>
          <Form.Control size="sm" placeholder="搜尋客戶…" value={filters.customer} onChange={e => onFilterChange('customer', e.target.value)} />
        </Col>
        <Col xs={6} md={2}>
          <Form.Label className="small mb-1">材質</Form.Label>
          <Form.Control size="sm" placeholder="搜尋材質…" value={filters.material} onChange={e => onFilterChange('material', e.target.value)} />
        </Col>
        <Col xs={6} md={2}>
          <Form.Label className="small mb-1">規格</Form.Label>
          <Form.Control size="sm" placeholder="搜尋規格…" value={filters.spec} onChange={e => onFilterChange('spec', e.target.value)} />
        </Col>
        <Col xs={6} md={2}>
          <Form.Label className="small mb-1">狀態</Form.Label>
          <Form.Select size="sm" value={filters.status} onChange={e => onFilterChange('status', e.target.value)}>
            <option value="">全部</option>
            {['待處理', '處理中', '已結案'].map(status => <option key={status} value={status}>{status}</option>)}
          </Form.Select>
        </Col>
        <Col xs={6} md={2}>
          <Form.Label className="small mb-1">類型</Form.Label>
          <Form.Select size="sm" value={filters.type} onChange={e => onFilterChange('type', e.target.value)}>
            <option value="">全部</option>
            {Object.entries(COMPLAINT_TYPE_LABELS).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
          </Form.Select>
        </Col>
        <Col xs={6} md={2}>
          <Button variant="outline-secondary" size="sm" className="w-100 mt-4" onClick={onReset}>清除</Button>
        </Col>
      </Row>
      <Row className="g-2 mt-1">
        <Col xs={6} md={3}>
          <Form.Label className="small mb-1">日期（起）</Form.Label>
          <Form.Control type="date" size="sm" value={filters.dateFrom} onChange={e => onFilterChange('dateFrom', e.target.value)} />
        </Col>
        <Col xs={6} md={3}>
          <Form.Label className="small mb-1">日期（迄）</Form.Label>
          <Form.Control type="date" size="sm" value={filters.dateTo} onChange={e => onFilterChange('dateTo', e.target.value)} />
        </Col>
        <Col xs={6} md={3}>
          <Form.Label className="small mb-1">重複客訴</Form.Label>
          <Form.Select size="sm" value={filters.repeat} onChange={e => onFilterChange('repeat', e.target.value)}>
            <option value="">全部</option>
            <option value="true">僅重複</option>
            <option value="false">非重複</option>
          </Form.Select>
        </Col>
      </Row>
    </Card.Body>
  </Card>
);

interface ComplaintTableProps {
  loading: boolean;
  complaints: CustomerComplaint[];
  capaPending: boolean;
  reworkPending: boolean;
  onEdit: (complaint: CustomerComplaint) => void;
  onDelete: (complaint: CustomerComplaint) => void;
  onOpenCapa: (complaint: CustomerComplaint) => void;
  onOpenRework: (complaint: CustomerComplaint) => void;
  onNavigateToCapa: (id: number) => void;
  onNavigateToRework: (id: number) => void;
}

export const ComplaintTable = ({
  loading,
  complaints,
  capaPending,
  reworkPending,
  onEdit,
  onDelete,
  onOpenCapa,
  onOpenRework,
  onNavigateToCapa,
  onNavigateToRework,
}: ComplaintTableProps) => (
  <div className="table-responsive">
    <Table hover className="mb-0">
      <thead className="table-light">
        <tr>
          <th>單號</th>
          <th>客戶</th>
          <th>材質 / 規格</th>
          <th>日期</th>
          <th>類型</th>
          <th>嚴重度</th>
          <th>初回期限</th>
          <th>狀態</th>
          <th>重複</th>
          <th style={{ minWidth: '200px' }}>關聯單據</th>
          <th style={{ width: '120px' }}>操作</th>
        </tr>
      </thead>
      <tbody>
        {loading ? (
          <tr><td colSpan={11} className="text-center py-4 text-muted">載入中…</td></tr>
        ) : complaints.length === 0 ? (
          <tr>
            <td colSpan={11} className="text-center py-4 text-muted">
              <i className="bi bi-inbox fs-3 d-block mb-2" />
              查無符合條件的客訴
            </td>
          </tr>
        ) : complaints.map(c => (
          <tr key={c.id} className={c.is_overdue ? 'table-warning' : ''}>
            <td className="small fw-semibold">{c.complaint_no}</td>
            <td className="small">{c.customer}</td>
            <td className="small">{[c.material, c.spec].filter(Boolean).join(' / ') || '—'}</td>
            <td className="small">{c.complaint_date}</td>
            <td className="small">
              <Badge bg="light" text="dark">{COMPLAINT_TYPE_LABELS[c.complaint_type as ComplaintType] ?? c.complaint_type}</Badge>
            </td>
            <td className="small">
              <Badge
                bg={c.severity === 'Critical' ? 'danger' : c.severity === 'Major' ? 'warning' : 'info'}
                text={c.severity === 'Minor' ? 'dark' : undefined}
              >
                {c.severity ?? '—'}
              </Badge>
            </td>
            <td className="small">
              {c.initial_reply_deadline ? (
                <span className={c.is_overdue ? 'text-danger fw-semibold' : ''}>
                  {c.initial_reply_deadline}
                  {c.is_overdue && <Badge bg="danger" className="ms-1" style={{ fontSize: '0.65rem' }}>+{c.overdue_days}天</Badge>}
                </span>
              ) : '—'}
            </td>
            <td><Badge bg={COMPLAINT_STATUS_VARIANT[c.status] ?? 'secondary'}>{c.status}</Badge></td>
            <td>{c.is_repeat && <Badge bg="danger" title="12 個月內重複客訴">重複</Badge>}</td>
            <td>
              <div className="d-flex flex-wrap gap-1">
                {c.related_capa_id ? (
                  <Badge bg="warning" text="dark" style={{ cursor: 'pointer' }} onClick={() => onNavigateToCapa(c.related_capa_id!)} title="點擊查看 CAPA">
                    CAPA #{c.related_capa_id}
                  </Badge>
                ) : (
                  <Button variant="outline-warning" size="sm" style={{ fontSize: '0.7rem' }} onClick={() => onOpenCapa(c)} disabled={capaPending}>
                    開立CAPA
                  </Button>
                )}
                {c.related_rework_id ? (
                  <Badge bg="secondary" style={{ cursor: 'pointer' }} onClick={() => onNavigateToRework(c.related_rework_id!)} title="點擊查看重工單">
                    重工 #{c.related_rework_id}
                  </Badge>
                ) : (
                  <Button variant="outline-secondary" size="sm" style={{ fontSize: '0.7rem' }} onClick={() => onOpenRework(c)} disabled={reworkPending}>
                    開立重工
                  </Button>
                )}
              </div>
            </td>
            <td>
              <Button variant="outline-primary" size="sm" className="me-1" onClick={() => onEdit(c)}>編輯</Button>
              <Button variant="outline-danger" size="sm" onClick={() => onDelete(c)}>刪除</Button>
            </td>
          </tr>
        ))}
      </tbody>
    </Table>
  </div>
);
