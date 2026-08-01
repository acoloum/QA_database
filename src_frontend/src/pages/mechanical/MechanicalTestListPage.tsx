import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Button, Card, Col, Form, Row, Table } from 'react-bootstrap';
import toast from 'react-hot-toast';

import { mechanicalApi } from '../../services/mechanicalApi';
import { apiErrorMessage, apiErrorNeedsToast } from '../../services/apiError';
import type { MechanicalJudgementStatus } from '../../types';
import MechanicalTestForm from './MechanicalTestForm';
import MechanicalImportModal from '../../components/mechanical/MechanicalImportModal';
import MechanicalCharts from '../../components/mechanical/MechanicalCharts';
import PermissionAction from '../../components/PermissionAction';
import { useAuth } from '../../context/useAuth';

const judgementDisplay: Record<MechanicalJudgementStatus, { label: string; variant: string }> = {
  NG: { label: 'NG', variant: 'danger' },
  OK: { label: 'OK', variant: 'success' },
  NO_SPEC: { label: '無規格', variant: 'warning' },
  INCOMPLETE: { label: '未完成', variant: 'secondary' },
};

export default function MechanicalTestListPage() {
  const { hasPermission } = useAuth();
  const queryClient = useQueryClient();
  const [testId, setTestId] = useState('');
  const [size, setSize] = useState('');
  const [material, setMaterial] = useState('');
  const [vendorId, setVendorId] = useState('');
  const [judgementStatus, setJudgementStatus] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [editingId, setEditingId] = useState<number | null | 'new'>(null);
  const [showImport, setShowImport] = useState(false);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);

  const changeFilter = <T,>(setter: (value: T) => void, value: T) => {
    setPage(1);
    setter(value);
  };

  const clearFilters = () => {
    setTestId('');
    setSize('');
    setMaterial('');
    setVendorId('');
    setJudgementStatus('');
    setDateFrom('');
    setDateTo('');
    setPage(1);
  };
  const hasActiveFilter = Boolean(
    testId || size || material || vendorId || judgementStatus || dateFrom || dateTo,
  );

  const { data: vendors = [] } = useQuery({
    queryKey: ['vendors'],
    queryFn: mechanicalApi.getVendors,
  });

  const params = useMemo(
    () => ({
      id: testId || undefined,
      product_size: size || undefined,
      material: material || undefined,
      vendor_id: vendorId || undefined,
      judgement_status: judgementStatus || undefined,
      date_from: dateFrom || undefined,
      date_to: dateTo || undefined,
      page,
      page_size: pageSize,
    }),
    [testId, size, material, vendorId, judgementStatus, dateFrom, dateTo, page, pageSize],
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
    onError: (error) => {
      const message = apiErrorMessage(error, '刪除失敗，請稍後再試');
      if (apiErrorNeedsToast(error)) toast.error(message);
    },
  });

  const rows = data?.data ?? [];
  return (
    <div>
      <div className="d-flex justify-content-between align-items-center mb-3">
        <h4>機械性質檢驗</h4>
        <div className="d-flex gap-2">
          <PermissionAction permission="mechanical.create">
            <Button size="sm" variant="outline-secondary" onClick={() => setShowImport(true)}>
              匯入 Excel
            </Button>
          </PermissionAction>
          <PermissionAction permission="mechanical.create">
            <Button size="sm" onClick={() => setEditingId('new')}>+ 新增檢驗</Button>
          </PermissionAction>
        </div>
      </div>

      <Card className="mb-3">
        <Card.Body>
          <Row className="g-2">
            <Col md={1}>
              <Form.Label htmlFor="mechanical-id">ID</Form.Label>
              <Form.Control
                id="mechanical-id"
                size="sm"
                placeholder="ID"
                value={testId}
                onChange={(event) => changeFilter(setTestId, event.target.value)}
              />
            </Col>
            <Col md={2}>
              <Form.Label htmlFor="mechanical-product-size">產品尺寸</Form.Label>
              <Form.Control
                id="mechanical-product-size"
                size="sm"
                placeholder="產品尺寸"
                value={size}
                onChange={(event) => changeFilter(setSize, event.target.value)}
              />
            </Col>
            <Col md={2}>
              <Form.Label htmlFor="mechanical-material">材質</Form.Label>
              <Form.Control
                id="mechanical-material"
                size="sm"
                placeholder="材質"
                value={material}
                onChange={(event) => changeFilter(setMaterial, event.target.value)}
              />
            </Col>
            <Col md={2}>
              <Form.Label htmlFor="mechanical-date-from">起始日期</Form.Label>
              <Form.Control
                id="mechanical-date-from"
                type="date"
                size="sm"
                value={dateFrom}
                onChange={(event) => changeFilter(setDateFrom, event.target.value)}
              />
            </Col>
            <Col md={2}>
              <Form.Label htmlFor="mechanical-date-to">結束日期</Form.Label>
              <Form.Control
                id="mechanical-date-to"
                type="date"
                size="sm"
                value={dateTo}
                onChange={(event) => changeFilter(setDateTo, event.target.value)}
              />
            </Col>
            <Col md={2}>
              <Form.Label htmlFor="mechanical-vendor">廠商</Form.Label>
              <Form.Select
                id="mechanical-vendor"
                size="sm"
                value={vendorId}
                onChange={(event) => changeFilter(setVendorId, event.target.value)}
              >
                <option value="">全部</option>
                {vendors.map((vendor) => (
                  <option key={vendor.id} value={vendor.id}>{vendor.name}</option>
                ))}
              </Form.Select>
            </Col>
            <Col md={2}>
              <Form.Label htmlFor="mechanical-judgement-status">判定狀態</Form.Label>
              <Form.Select
                id="mechanical-judgement-status"
                size="sm"
                value={judgementStatus}
                onChange={(event) => changeFilter(setJudgementStatus, event.target.value)}
              >
                <option value="">全部</option>
                {(Object.keys(judgementDisplay) as MechanicalJudgementStatus[]).map((status) => (
                  <option key={status} value={status}>{judgementDisplay[status].label}</option>
                ))}
              </Form.Select>
            </Col>
            <Col md={2} className="d-flex align-items-end">
              <Button
                size="sm"
                variant="outline-secondary"
                className="w-100"
                disabled={!hasActiveFilter}
                onClick={clearFilters}
              >
                清除篩選
              </Button>
            </Col>
          </Row>
        </Card.Body>
      </Card>

      {(vendorId || material || size) && (
        <MechanicalCharts
          vendorId={vendorId}
          material={material}
          productSize={size}
          startDate={dateFrom}
          endDate={dateTo}
          onPointClick={hasPermission('mechanical.edit') ? (id) => setEditingId(id) : undefined}
        />
      )}

      <Card>
        <Card.Body>
          {isLoading ? (
            <p>載入中…</p>
          ) : isError ? (
            <p role="alert" className="text-danger mb-0">載入機械性質檢驗資料失敗，請稍後再試</p>
          ) : (
            <>
              <Table bordered hover size="sm">
              <thead className="table-secondary">
                <tr>
                  <th>ID</th>
                  <th>產品尺寸</th>
                  <th>材質</th>
                  <th>測試日期</th>
                  <th>擠製編號</th>
                  <th>T4爐號</th>
                  <th>T4溫度/時間</th>
                  <th>T6溫度/時間</th>
                  <th>判定</th>
                  <th>免測</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.識別碼}>
                    <td className="text-muted">{row.識別碼}</td>
                    <td>{row.產品尺寸}</td>
                    <td>{row.材質}</td>
                    <td>{row.測試日期 ?? ''}</td>
                    <td>{row.擠製編號}</td>
                    <td>{row.T4爐號 || '—'}</td>
                    <td>{row.T4溫度時間}</td>
                    <td>{row.T6溫度時間}</td>
                    <td>
                      <span className={`badge text-bg-${judgementDisplay[row.判定狀態].variant}`}>
                        {judgementDisplay[row.判定狀態].label}
                      </span>
                    </td>
                    <td>{row.免測 || '—'}</td>
                    <td>
                      <PermissionAction permission="mechanical.edit"><Button
                        size="sm"
                        variant="outline-primary"
                        className="me-1"
                        onClick={() => setEditingId(row.識別碼)}
                      >
                        編輯
                      </Button></PermissionAction>
                      <PermissionAction permission="mechanical.delete"><Button
                        size="sm"
                        variant="outline-danger"
                        onClick={() => {
                          if (window.confirm('確定刪除這筆檢驗？')) {
                            deleteMutation.mutate(row.識別碼);
                          }
                        }}
                      >
                        刪除
                      </Button></PermissionAction>
                    </td>
                  </tr>
                ))}
                {data && rows.length === 0 && (
                  <tr>
                    <td colSpan={11} className="text-center text-muted">查無資料</td>
                  </tr>
                )}
              </tbody>
              </Table>
              {data && (
              <div className="d-flex flex-wrap justify-content-between align-items-center gap-2">
                <span>共 {data.total} 筆</span>
                <div className="d-flex align-items-center gap-2">
                  <Form.Label htmlFor="mechanical-page-size" className="mb-0">每頁筆數</Form.Label>
                  <Form.Select
                    id="mechanical-page-size"
                    aria-label="每頁筆數"
                    size="sm"
                    value={pageSize}
                    onChange={(event) => {
                      setPage(1);
                      setPageSize(Number(event.target.value));
                    }}
                    style={{ width: 80 }}
                  >
                    {[20, 50, 100].map((value) => <option key={value} value={value}>{value}</option>)}
                  </Form.Select>
                  <Button
                    size="sm"
                    variant="outline-secondary"
                    disabled={page <= 1}
                    onClick={() => setPage((current) => current - 1)}
                  >
                    上一頁
                  </Button>
                  <span>第 {data.page} / {Math.max(data.total_pages, 1)} 頁</span>
                  <Button
                    size="sm"
                    variant="outline-secondary"
                    disabled={page >= data.total_pages}
                    onClick={() => setPage((current) => current + 1)}
                  >
                    下一頁
                  </Button>
                </div>
              </div>
              )}
            </>
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

      <MechanicalImportModal
        show={showImport}
        handleClose={() => setShowImport(false)}
        onSuccess={() => queryClient.invalidateQueries({ queryKey: ['mechanical-tests'] })}
      />
    </div>
  );
}
