import { useState } from 'react';
import { Button, Card, Table, Modal, Form, Row, Col, Badge } from 'react-bootstrap';
import type { Thermocouple, ThermocoupleCalPoint } from '../../types';
import ConfirmActionModal, { type ConfirmActionState } from '../../components/common/ConfirmActionModal';
import { useDeleteThermocouple, useSaveThermocouple, useThermocoupleDetail, useThermocouples } from '../../hooks/usePyrometry';
import {
  buildThermocouplePayload,
  validateThermocoupleRows,
  type CalibrationFieldErrors,
  type ThermocouplePointRow,
} from './pyrometryCalibrationPayload';
import PermissionAction from '../../components/PermissionAction';

const emptyMeta = () => ({
  編號: '', 型式: 'TYPE K', 校正日期: '', 到期日: '', 啟用狀態: true, 備註: '',
});

const ThermocoupleCalibrationPage = () => {
  const [showModal, setShowModal] = useState(false);
  const [editId, setEditId] = useState<number | null>(null);
  const [meta, setMeta] = useState(emptyMeta());
  const [points, setPoints] = useState<ThermocouplePointRow[]>([{ 標準溫度: '', 器差值: '' }]);
  const [fieldErrors, setFieldErrors] = useState<CalibrationFieldErrors>({});
  const [confirmAction, setConfirmAction] = useState<ConfirmActionState | null>(null);

  const { data, isLoading } = useThermocouples();
  const thermocoupleDetail = useThermocoupleDetail();
  const saveMutation = useSaveThermocouple(editId);
  const deleteMutation = useDeleteThermocouple();

  const openAdd = () => {
    setEditId(null);
    setMeta(emptyMeta());
    setPoints([{ 標準溫度: '', 器差值: '' }]);
    setFieldErrors({});
    setShowModal(true);
  };

  const openEdit = async (t: Thermocouple) => {
    setEditId(t.識別碼);
    const d = await thermocoupleDetail.mutateAsync(t.識別碼);
    setMeta({
      編號: d.編號 || '', 型式: d.型式 || '',
      校正日期: d.校正日期 || '', 到期日: d.到期日 || '',
      啟用狀態: d.啟用狀態, 備註: d.備註 || '',
    });
    const rows = (d.校正點 || []).map((cp: ThermocoupleCalPoint) => ({
      標準溫度: String(cp.標準溫度), 器差值: String(cp.器差值),
    }));
    setPoints(rows.length ? rows : [{ 標準溫度: '', 器差值: '' }]);
    setFieldErrors({});
    setShowModal(true);
  };

  const handleDelete = (t: Thermocouple) => setConfirmAction({
    title: '刪除熱電偶',
    message: `確定刪除熱電偶「${t.編號}」與其校正資料？`,
    confirmLabel: '刪除',
    confirmVariant: 'danger',
    onConfirm: async () => {
      await deleteMutation.mutateAsync(t.識別碼);
    },
  });

  const setRow = (i: number, k: keyof ThermocouplePointRow, v: string) => {
    setPoints(prev => prev.map((p, idx) => idx === i ? { ...p, [k]: v } : p));
    setFieldErrors(prev => {
      const next = { ...prev };
      delete next[`${i}:${k}`];
      return next;
    });
  };
  const addRow = () => setPoints(prev => [...prev, { 標準溫度: '', 器差值: '' }]);
  const delRow = (i: number) => setPoints(prev => prev.filter((_, idx) => idx !== i));

  const handleSave = () => {
    const errors = validateThermocoupleRows(points);
    setFieldErrors(errors);
    if (Object.keys(errors).length) return;
    saveMutation.mutate(
      { payload: buildThermocouplePayload(meta, points) },
      { onSuccess: () => setShowModal(false) },
    );
  };

  return (
    <div>
      <div className="d-flex justify-content-between align-items-center mb-3">
        <h4>熱電偶校正</h4>
        <PermissionAction permission="pyrometry.edit"><Button variant="primary" size="sm" onClick={openAdd}>+ 新增</Button></PermissionAction>
      </div>
      <Card>
        <Card.Body>
          {isLoading ? <p>載入中…</p> : (
            <Table bordered hover size="sm">
              <thead className="table-secondary">
                <tr>
                  <th>編號</th><th>型式</th><th>校正日期</th><th>到期日</th>
                  <th>校正點數</th><th>狀態</th><th>操作</th>
                </tr>
              </thead>
              <tbody>
                {(data || []).map(t => (
                  <tr key={t.識別碼}>
                    <td>{t.編號}</td>
                    <td>{t.型式}</td>
                    <td>{t.校正日期 || '—'}</td>
                    <td>{t.到期日 || '—'}</td>
                    <td>{t.校正點?.length ?? '—'}</td>
                    <td>
                      <Badge bg={t.啟用狀態 ? 'success' : 'secondary'}>
                        {t.啟用狀態 ? '啟用' : '停用'}
                      </Badge>
                    </td>
                    <td>
                      <PermissionAction permission="pyrometry.edit"><Button size="sm" variant="outline-primary" className="me-1" onClick={() => openEdit(t)}>編輯</Button></PermissionAction>
                      <PermissionAction permission="pyrometry.delete"><Button size="sm" variant="outline-danger" onClick={() => handleDelete(t)}>刪除</Button></PermissionAction>
                    </td>
                  </tr>
                ))}
              </tbody>
            </Table>
          )}
        </Card.Body>
      </Card>

      <Modal show={showModal} onHide={() => setShowModal(false)} size="lg">
        <Modal.Header closeButton>
          <Modal.Title>{editId ? '編輯熱電偶校正' : '新增熱電偶校正'}</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          <Form>
            <Row className="g-2 mb-3">
              <Col md={3}>
                <Form.Label>編號 *</Form.Label>
                <Form.Control size="sm" value={meta.編號} onChange={e => setMeta({ ...meta, 編號: e.target.value })} />
              </Col>
              <Col md={2}>
                <Form.Label>型式</Form.Label>
                <Form.Control size="sm" value={meta.型式} onChange={e => setMeta({ ...meta, 型式: e.target.value })} />
              </Col>
              <Col md={3}>
                <Form.Label>校正日期</Form.Label>
                <Form.Control size="sm" type="date" value={meta.校正日期} onChange={e => setMeta({ ...meta, 校正日期: e.target.value })} />
              </Col>
              <Col md={3}>
                <Form.Label>到期日</Form.Label>
                <Form.Control size="sm" type="date" value={meta.到期日} onChange={e => setMeta({ ...meta, 到期日: e.target.value })} />
              </Col>
              <Col md={1} className="d-flex align-items-end">
                <Form.Check type="checkbox" label="啟用" checked={meta.啟用狀態} onChange={e => setMeta({ ...meta, 啟用狀態: e.target.checked })} />
              </Col>
              <Col md={12}>
                <Form.Label>備註</Form.Label>
                <Form.Control as="textarea" rows={1} size="sm" value={meta.備註} onChange={e => setMeta({ ...meta, 備註: e.target.value })} />
              </Col>
            </Row>

            <div className="d-flex justify-content-between align-items-center">
              <h6 className="mb-0">校正曲線（標準溫度 → 器差值＝器示值−標準值）</h6>
              <PermissionAction permission="pyrometry.edit"><Button size="sm" variant="outline-secondary" onClick={addRow}>+ 新增一列</Button></PermissionAction>
            </div>
            <div className="text-muted mb-1" style={{ fontSize: 11 }}>
              補正值＝−器差值（依設定溫度於各點間線性內插）
            </div>
            <Table bordered size="sm" style={{ maxWidth: 420 }}>
              <thead className="table-secondary">
                <tr><th>標準溫度(°C)</th><th>器差值(°C)</th><th></th></tr>
              </thead>
              <tbody>
                {points.map((p, i) => (
                  <tr key={i}>
                    <td>
                      <Form.Control
                        size="sm"
                        value={p.標準溫度}
                        isInvalid={!!fieldErrors[`${i}:標準溫度`]}
                        onChange={e => setRow(i, '標準溫度', e.target.value)}
                      />
                      <Form.Control.Feedback type="invalid">{fieldErrors[`${i}:標準溫度`]}</Form.Control.Feedback>
                    </td>
                    <td>
                      <Form.Control
                        size="sm"
                        value={p.器差值}
                        isInvalid={!!fieldErrors[`${i}:器差值`]}
                        onChange={e => setRow(i, '器差值', e.target.value)}
                      />
                      <Form.Control.Feedback type="invalid">{fieldErrors[`${i}:器差值`]}</Form.Control.Feedback>
                    </td>
                    <td className="text-center">
                      <PermissionAction permission="pyrometry.edit"><Button size="sm" variant="outline-danger" onClick={() => delRow(i)} disabled={points.length <= 1}>✕</Button></PermissionAction>
                    </td>
                  </tr>
                ))}
              </tbody>
            </Table>
          </Form>
        </Modal.Body>
        <Modal.Footer>
          <Button variant="secondary" onClick={() => setShowModal(false)}>取消</Button>
          <PermissionAction permission="pyrometry.edit"><Button variant="primary" onClick={handleSave} disabled={saveMutation.isPending}>
            {saveMutation.isPending ? '儲存中…' : '儲存'}
          </Button></PermissionAction>
        </Modal.Footer>
      </Modal>
      <ConfirmActionModal action={confirmAction} onHide={() => setConfirmAction(null)} />
    </div>
  );
};

export default ThermocoupleCalibrationPage;
