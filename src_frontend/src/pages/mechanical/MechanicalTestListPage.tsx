import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Button, Card, Col, Form, Row, Table } from 'react-bootstrap';
import toast from 'react-hot-toast';

import { mechanicalApi } from '../../services/mechanicalApi';
import MechanicalTestForm from './MechanicalTestForm';

export default function MechanicalTestListPage() {
  const queryClient = useQueryClient();
  const [size, setSize] = useState('');
  const [material, setMaterial] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [onlyNg, setOnlyNg] = useState(false);
  const [editingId, setEditingId] = useState<number | null | 'new'>(null);

  const params = useMemo(
    () => ({
      product_size: size || undefined,
      material: material || undefined,
      date_from: dateFrom || undefined,
      date_to: dateTo || undefined,
      only_ng: onlyNg ? 'true' : undefined,
    }),
    [size, material, dateFrom, dateTo, onlyNg],
  );

  const { data, isLoading, isError } = useQuery({
    queryKey: ['mechanical-tests', params],
    queryFn: () => mechanicalApi.list(params),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => mechanicalApi.remove(id),
    onSuccess: () => {
      toast.success('已刪除');
      queryClient.invalidateQueries({ queryKey: ['mechanical-tests'] });
    },
    onError: () => {
      toast.error('刪除失敗，請稍後再試');
    },
  });

  const rows = data?.data ?? [];

  return (
    <div>
      <div className="d-flex justify-content-between align-items-center mb-3">
        <h4>機械性質檢驗</h4>
        <Button size="sm" onClick={() => setEditingId('new')}>
          + 新增檢驗
        </Button>
      </div>

      <Card className="mb-3">
        <Card.Body>
          <Row className="g-2">
            <Col md={2}>
              <Form.Label htmlFor="mechanical-product-size">產品尺寸</Form.Label>
              <Form.Control
                id="mechanical-product-size"
                size="sm"
                placeholder="產品尺寸"
                value={size}
                onChange={(event) => setSize(event.target.value)}
              />
            </Col>
            <Col md={2}>
              <Form.Label htmlFor="mechanical-material">材質</Form.Label>
              <Form.Control
                id="mechanical-material"
                size="sm"
                placeholder="材質"
                value={material}
                onChange={(event) => setMaterial(event.target.value)}
              />
            </Col>
            <Col md={2}>
              <Form.Label htmlFor="mechanical-date-from">起始日期</Form.Label>
              <Form.Control
                id="mechanical-date-from"
                type="date"
                size="sm"
                value={dateFrom}
                onChange={(event) => setDateFrom(event.target.value)}
              />
            </Col>
            <Col md={2}>
              <Form.Label htmlFor="mechanical-date-to">結束日期</Form.Label>
              <Form.Control
                id="mechanical-date-to"
                type="date"
                size="sm"
                value={dateTo}
                onChange={(event) => setDateTo(event.target.value)}
              />
            </Col>
            <Col md={2} className="d-flex align-items-end">
              <Form.Check
                id="mechanical-only-ng"
                label="僅顯示 NG"
                checked={onlyNg}
                onChange={(event) => setOnlyNg(event.target.checked)}
              />
            </Col>
          </Row>
        </Card.Body>
      </Card>

      <Card>
        <Card.Body>
          {isLoading ? (
            <p>載入中…</p>
          ) : isError ? (
            <p role="alert" className="text-danger mb-0">載入機械性質檢驗資料失敗，請稍後再試</p>
          ) : (
            <Table bordered hover size="sm">
              <thead className="table-secondary">
                <tr>
                  <th>產品尺寸</th>
                  <th>材質</th>
                  <th>測試日期</th>
                  <th>擠製編號</th>
                  <th>T4</th>
                  <th>T6</th>
                  <th>判定</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.識別碼}>
                    <td>{row.產品尺寸}</td>
                    <td>{row.材質}</td>
                    <td>{row.測試日期 ?? ''}</td>
                    <td>{row.擠製編號}</td>
                    <td>{row.T4溫度時間}</td>
                    <td>{row.T6溫度時間}</td>
                    <td>
                      {row.是否NG ? (
                        <span className="badge text-bg-danger">NG</span>
                      ) : (
                        <span className="badge text-bg-success">OK</span>
                      )}
                    </td>
                    <td>
                      <Button
                        size="sm"
                        variant="outline-primary"
                        className="me-1"
                        onClick={() => setEditingId(row.識別碼)}
                      >
                        編輯
                      </Button>
                      <Button
                        size="sm"
                        variant="outline-danger"
                        onClick={() => {
                          if (window.confirm('確定刪除這筆檢驗？')) {
                            deleteMutation.mutate(row.識別碼);
                          }
                        }}
                      >
                        刪除
                      </Button>
                    </td>
                  </tr>
                ))}
                {data && rows.length === 0 && (
                  <tr>
                    <td colSpan={8} className="text-center text-muted">查無資料</td>
                  </tr>
                )}
              </tbody>
            </Table>
          )}
        </Card.Body>
      </Card>

      {editingId !== null && (
        <MechanicalTestForm
          testId={editingId === 'new' ? null : editingId}
          onClose={() => setEditingId(null)}
          onSaved={() => {
            setEditingId(null);
            queryClient.invalidateQueries({ queryKey: ['mechanical-tests'] });
          }}
        />
      )}
    </div>
  );
}
