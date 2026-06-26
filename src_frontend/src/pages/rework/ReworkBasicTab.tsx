import { Button } from 'react-bootstrap';

import type { ReworkApplication } from '../../types';
import { getReworkStatusBadge } from './reworkDetailUtils';

interface ReworkBasicTabProps {
  detail: ReworkApplication;
  onEditBasic: () => void;
  onCloseRework: (reworkId: number) => void;
}

const ReworkBasicTab = ({ detail, onEditBasic, onCloseRework }: ReworkBasicTabProps) => (
  <div className="tab-pane fade show active">
    <div className="d-flex justify-content-between align-items-center mb-3">
      <h6 className="mb-0">基本資訊</h6>
      <div className="btn-group">
        <Button variant="primary" size="sm" onClick={onEditBasic}>
          <i className="bi bi-pencil"></i> 編輯
        </Button>
        {detail.狀態 !== '已完成' && (
          <Button variant="success" size="sm" onClick={() => onCloseRework(detail.識別碼)}>
            <i className="bi bi-check-circle"></i> 結案
          </Button>
        )}
      </div>
    </div>
    <div className="row">
      <div className="col-md-6 mb-3"><label className="form-label fw-bold">申請單號</label><p>{detail.申請單號}</p></div>
      <div className="col-md-6 mb-3"><label className="form-label fw-bold">申請日期</label><p>{detail.申請日期}</p></div>
      <div className="col-md-6 mb-3">
        <label className="form-label fw-bold">{detail.客訴單號 && !detail.ncmr_number ? '客訴單號' : 'NCMR單號'}</label>
        <p>{detail.ncmr_number || detail.客訴單號 || (detail.NCMR_ID ? `#${detail.NCMR_ID}` : '-')}</p>
      </div>
      <div className="col-md-6 mb-3"><label className="form-label fw-bold">申請人員</label><p>{detail.申請人員姓名}</p></div>
      <div className="col-md-6 mb-3"><label className="form-label fw-bold">部門</label><p>{detail.部門}</p></div>
      <div className="col-md-6 mb-3"><label className="form-label fw-bold">緊急程度</label><p>{detail.緊急程度}</p></div>
      <div className="col-md-6 mb-3"><label className="form-label fw-bold">廠商</label><p>{detail.廠商 || '-'}</p></div>
      <div className="col-md-6 mb-3"><label className="form-label fw-bold">材質</label><p>{detail.材質 || '-'}</p></div>
      <div className="col-md-6 mb-3"><label className="form-label fw-bold">規格</label><p>{detail.產品資訊 || '-'}</p></div>
      <div className="col-md-6 mb-3"><label className="form-label fw-bold">批號</label><p>{detail.批號 || '-'}</p></div>
      <div className="col-md-6 mb-3"><label className="form-label fw-bold">重工數量</label><p>{detail.重工數量}</p></div>
      <div className="col-md-6 mb-3"><label className="form-label fw-bold">預計完成日期</label><p>{detail.預計完成日期 || '-'}</p></div>
      <div className="col-md-6 mb-3">
        <label className="form-label fw-bold">狀態</label>
        <p><span className={`badge ${getReworkStatusBadge(detail.狀態)}`}>{detail.狀態}</span></p>
      </div>
      <div className="col-12 mb-3"><label className="form-label fw-bold">申請原因</label><p>{detail.申請原因 || '-'}</p></div>
    </div>
  </div>
);

export default ReworkBasicTab;
