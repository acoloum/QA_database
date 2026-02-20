import { useState, useEffect } from 'react';
import { Modal, Button, Form, Row, Col } from 'react-bootstrap';
import api from '../../services/api';
import type { ReworkApplication } from '../../types';

interface EditBasicInfoModalProps {
  show: boolean;
  handleClose: () => void;
  onSuccess: () => void;
  application: ReworkApplication | null;
}

const EditBasicInfoModal = ({ show, handleClose, onSuccess, application }: EditBasicInfoModalProps) => {
  const [loading, setLoading] = useState(false);

  const [department, setDepartment] = useState('製造部');
  const [urgency, setUrgency] = useState('普通');
  const [vendor, setVendor] = useState('');
  const [material, setMaterial] = useState('');
  const [spec, setSpec] = useState('');
  const [batchNo, setBatchNo] = useState('');
  const [reworkQty, setReworkQty] = useState('');
  const [reason, setReason] = useState('');
  const [expectedDate, setExpectedDate] = useState('');

  useEffect(() => {
    if (show && application) {
      loadApplicationData();
    }
  }, [show, application]);

  const loadApplicationData = () => {
    if (!application) return;
    setDepartment(application.部門 || '製造部');
    setUrgency(application.緊急程度 || '普通');
    setVendor(application.廠商 || '');
    setMaterial(application.材質 || '');
    setSpec(application.產品資訊 || '');
    setBatchNo(application.批號 || '');
    setReworkQty(application.重工數量?.toString() || '');
    setReason(application.申請原因 || '');
    const dateStr = application.預計完成日期;
    if (dateStr) {
      setExpectedDate(dateStr.split(' ')[0]);
    } else {
      setExpectedDate('');
    }
  };

  const handleSubmit = async () => {
    if (!application) return;

    setLoading(true);
    try {
      const payload: any = {};

      if (department) payload.部門 = department;
      if (urgency) payload.緊急程度 = urgency;
      if (vendor !== undefined) payload.廠商 = vendor;
      if (material !== undefined) payload.材質 = material;
      if (spec !== undefined) payload.產品資訊 = spec;
      if (batchNo !== undefined) payload.批號 = batchNo;
      if (reworkQty) payload.重工數量 = parseFloat(reworkQty);
      if (reason) payload.申請原因 = reason;
      if (expectedDate !== undefined) payload.預計完成日期 = expectedDate;

      await api.put(`/rework/application/${application.識別碼}`, payload);
      alert('基本資訊已更新！');
      onSuccess();
      handleClose();
    } catch (error: any) {
      console.error(error);
      alert(error.response?.data?.error || '更新失敗');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal show={show} onHide={handleClose} size="lg" dialogClassName="modal-rework">
      <style type="text/css">{`
        .modal-rework {
          max-width: 800px !important;
        }
        .modal-rework .modal-body {
          max-height: 75vh;
          overflow-y: auto;
        }
      `}</style>
      <Modal.Header closeButton>
        <Modal.Title>編輯基本資訊 - {application?.申請單號}</Modal.Title>
      </Modal.Header>
      <Modal.Body>
        <Form>
          <Row>
            <Col md={6}>
              <Form.Group className="mb-3">
                <Form.Label>部門</Form.Label>
                <Form.Select value={department} onChange={(e) => setDepartment(e.target.value)}>
                  <option value="製造部">製造部</option>
                  <option value="品保部">品保部</option>
                  <option value="工程部">工程部</option>
                </Form.Select>
              </Form.Group>
            </Col>
            <Col md={6}>
              <Form.Group className="mb-3">
                <Form.Label>緊急程度</Form.Label>
                <Form.Select value={urgency} onChange={(e) => setUrgency(e.target.value)}>
                  <option value="普通">普通</option>
                  <option value="緊急">緊急</option>
                  <option value="特緊急">特緊急</option>
                </Form.Select>
              </Form.Group>
            </Col>
          </Row>

          <Row>
            <Col md={6}>
              <Form.Group className="mb-3">
                <Form.Label>廠商</Form.Label>
                <Form.Control
                  value={vendor}
                  onChange={(e) => setVendor(e.target.value)}
                  placeholder="廠商"
                />
              </Form.Group>
            </Col>
            <Col md={6}>
              <Form.Group className="mb-3">
                <Form.Label>材質</Form.Label>
                <Form.Control
                  value={material}
                  onChange={(e) => setMaterial(e.target.value)}
                  placeholder="材質"
                />
              </Form.Group>
            </Col>
          </Row>

          <Row>
            <Col md={6}>
              <Form.Group className="mb-3">
                <Form.Label>規格</Form.Label>
                <Form.Control
                  value={spec}
                  onChange={(e) => setSpec(e.target.value)}
                  placeholder="規格"
                />
              </Form.Group>
            </Col>
            <Col md={6}>
              <Form.Group className="mb-3">
                <Form.Label>批號</Form.Label>
                <Form.Control
                  value={batchNo}
                  onChange={(e) => setBatchNo(e.target.value)}
                  placeholder="批號"
                />
              </Form.Group>
            </Col>
          </Row>

          <Row>
            <Col md={6}>
              <Form.Group className="mb-3">
                <Form.Label>重工數量</Form.Label>
                <Form.Control
                  type="number"
                  value={reworkQty}
                  onChange={(e) => setReworkQty(e.target.value)}
                  placeholder="重工數量"
                />
              </Form.Group>
            </Col>
            <Col md={6}>
              <Form.Group className="mb-3">
                <Form.Label>預計完成日期</Form.Label>
                <Form.Control
                  type="date"
                  value={expectedDate}
                  onChange={(e) => setExpectedDate(e.target.value)}
                />
              </Form.Group>
            </Col>
          </Row>

          <Form.Group className="mb-3">
            <Form.Label>申請原因</Form.Label>
            <Form.Control
              as="textarea"
              rows={3}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="申請原因"
            />
          </Form.Group>
        </Form>
      </Modal.Body>
      <Modal.Footer>
        <Button variant="secondary" onClick={handleClose}>取消</Button>
        <Button variant="primary" onClick={handleSubmit} disabled={loading}>
          {loading ? '儲存中...' : '儲存'}
        </Button>
      </Modal.Footer>
    </Modal>
  );
};

export default EditBasicInfoModal;
