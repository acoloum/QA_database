import { useState } from 'react';
import { Button, Card, Table, Form, Row, Col, Badge } from 'react-bootstrap';
import type { PyrometryTestRow } from '../../types';
import ConfirmActionModal, { type ConfirmActionState } from '../../components/common/ConfirmActionModal';
import PaginationBar from '../../components/common/PaginationBar';
import { useDeletePyrometryTest, useExportPyrometryTest, useFurnaces, usePyrometryTests } from '../../hooks/usePyrometry';
import PyrometryTestForm from './PyrometryTestForm';

const PyrometryTestListPage = () => {
  const [showForm, setShowForm] = useState(false);
  const [editId, setEditId] = useState<number | null>(null);
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState({
    furnace_id: '', test_type: '', quarter: '', is_pass: '', date_from: '', date_to: '',
  });
  const [confirmAction, setConfirmAction] = useState<ConfirmActionState | null>(null);

  const { data: furnaces } = useFurnaces({ activeOnly: true });
  const { data: result, isLoading } = usePyrometryTests({ page, filters });
  const deleteMutation = useDeletePyrometryTest();
  const exportMutation = useExportPyrometryTest();

  const setF = (k: string, v: string) => { setFilters(prev => ({ ...prev, [k]: v })); setPage(1); };
  const confirmDelete = (row: PyrometryTestRow) => setConfirmAction({
    title: '刪除爐溫測試',
    message: `確定刪除 ${row.爐號} ${row.測試類型} ${row.測試日期} 的測試紀錄？`,
    confirmLabel: '刪除',
    confirmVariant: 'danger',
    onConfirm: async () => {
      await deleteMutation.mutateAsync(row.識別碼);
    },
  });
  const rows: PyrometryTestRow[] = result?.data || [];
  const totalPages = result?.total_pages || 1;

  return (
    <div>
      <div className="d-flex justify-content-between align-items-center mb-3">
        <h4>爐溫測試紀錄</h4>
        <Button variant="primary" size="sm" onClick={() => { setEditId(null); setShowForm(true); }}>+ 新增</Button>
      </div>

      <Card className="mb-3">
        <Card.Body>
          <Row className="g-2 align-items-end">
            <Col md={2}>
              <Form.Label>爐子</Form.Label>
              <Form.Select size="sm" value={filters.furnace_id} onChange={e => setF('furnace_id', e.target.value)}>
                <option value="">全部</option>
                {(furnaces || []).map(f => <option key={f.識別碼} value={f.識別碼}>{f.爐號} {f.名稱}</option>)}
              </Form.Select>
            </Col>
            <Col md={2}>
              <Form.Label>類型</Form.Label>
              <Form.Select size="sm" value={filters.test_type} onChange={e => setF('test_type', e.target.value)}>
                <option value="">全部</option>
                <option value="TUS">TUS</option>
                <option value="SAT">SAT</option>
              </Form.Select>
            </Col>
            <Col md={2}>
              <Form.Label>季別</Form.Label>
              <Form.Control size="sm" value={filters.quarter} onChange={e => setF('quarter', e.target.value)} placeholder="如 2026Q2" />
            </Col>
            <Col md={2}>
              <Form.Label>合格狀態</Form.Label>
              <Form.Select size="sm" value={filters.is_pass} onChange={e => setF('is_pass', e.target.value)}>
                <option value="">全部</option>
                <option value="1">合格</option>
                <option value="0">不合格</option>
              </Form.Select>
            </Col>
            <Col md={2}>
              <Form.Label>起始日</Form.Label>
              <Form.Control size="sm" type="date" value={filters.date_from} onChange={e => setF('date_from', e.target.value)} />
            </Col>
            <Col md={2}>
              <Form.Label>結束日</Form.Label>
              <Form.Control size="sm" type="date" value={filters.date_to} onChange={e => setF('date_to', e.target.value)} />
            </Col>
          </Row>
        </Card.Body>
      </Card>

      <Card>
        <Card.Body>
          {isLoading ? <p>載入中…</p> : (
            <>
              <Table bordered hover size="sm">
                <thead className="table-secondary">
                  <tr>
                    <th>爐號</th><th>類型</th><th>季別</th><th>測試日期</th>
                    <th>判定</th><th>人員</th><th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map(r => (
                    <tr key={r.識別碼}>
                      <td>{r.爐號}</td>
                      <td>{r.測試類型}</td>
                      <td>{r.季別}</td>
                      <td>{r.測試日期}</td>
                      <td>
                        <Badge bg={r.是否合格 ? 'success' : 'danger'}>
                          {r.是否合格 ? '合格' : '不合格'}
                        </Badge>
                      </td>
                      <td>{r.測試人員姓名}</td>
                      <td>
                        <Button size="sm" variant="outline-primary" className="me-1"
                          onClick={() => { setEditId(r.識別碼); setShowForm(true); }}>編輯</Button>
                        <Button size="sm" variant="outline-danger"
                          onClick={() => confirmDelete(r)}>刪除</Button>
                        <Button size="sm" variant="outline-secondary" className="ms-1"
                          onClick={() => exportMutation.mutate(r.識別碼)}
                          disabled={exportMutation.isPending}
                        >匯出</Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </Table>
              <PaginationBar page={page} perPage={20} total={result?.total ?? 0} totalPages={totalPages} onPageChange={setPage} />
            </>
          )}
        </Card.Body>
      </Card>

      {showForm && (
        <PyrometryTestForm
          editId={editId}
          onClose={() => setShowForm(false)}
          onSaved={() => setShowForm(false)}
        />
      )}
      <ConfirmActionModal action={confirmAction} onHide={() => setConfirmAction(null)} />
    </div>
  );
};

export default PyrometryTestListPage;
