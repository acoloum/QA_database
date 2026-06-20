import { Button, Modal } from 'react-bootstrap';
import type {
  ReworkApplication,
  ReworkCostDetail,
  ReworkExecutionDetail,
  ReworkInspectionDetail,
} from '../../types';
import type { ReworkDetailTab } from './useReworkDetail';

interface ReworkDetailModalProps {
  show: boolean;
  onHide: () => void;
  detail: ReworkApplication | null;
  activeTab: ReworkDetailTab;
  onTabChange: (tab: ReworkDetailTab) => void;
  executions: ReworkExecutionDetail[];
  inspections: ReworkInspectionDetail[];
  costs: ReworkCostDetail[];
  onEditBasic: () => void;
  onCloseRework: (reworkId: number) => void;
  onAddExecution: () => void;
  onEditExecution: (execution: ReworkExecutionDetail) => void;
  onDeleteExecution: (executionId: number) => void;
  onAddInspection: () => void;
  onEditInspection: (inspection: ReworkInspectionDetail) => void;
  onDeleteInspection: (inspectionId: number) => void;
  onAddCost: () => void;
  onEditCost: (cost: ReworkCostDetail) => void;
  onDeleteCost: (costId: number) => void;
}

const getStatusBadge = (status: string) => {
  switch (status) {
    case '已完成': return 'bg-info text-dark';
    case '已核准': return 'bg-success';
    case '已拒絕': return 'bg-danger';
    case '執行中': return 'bg-primary';
    default: return 'bg-warning text-dark';
  }
};

const ReworkDetailModal = ({
  show,
  onHide,
  detail,
  activeTab,
  onTabChange,
  executions,
  inspections,
  costs,
  onEditBasic,
  onCloseRework,
  onAddExecution,
  onEditExecution,
  onDeleteExecution,
  onAddInspection,
  onEditInspection,
  onDeleteInspection,
  onAddCost,
  onEditCost,
  onDeleteCost,
}: ReworkDetailModalProps) => (
  <Modal show={show} onHide={onHide} dialogClassName="modal-rework-detail">
    <Modal.Header closeButton>
      <Modal.Title>重工申請詳情 - {detail?.申請單號}</Modal.Title>
    </Modal.Header>
    <Modal.Body>
      {detail && (
        <>
          <ul className="nav nav-tabs" role="tablist">
            <li className="nav-item">
              <button className={`nav-link ${activeTab === 'basic' ? 'active' : ''}`} onClick={() => onTabChange('basic')}>基本資訊</button>
            </li>
            <li className="nav-item">
              <button className={`nav-link ${activeTab === 'execution' ? 'active' : ''}`} onClick={() => onTabChange('execution')}>執行記錄</button>
            </li>
            <li className="nav-item">
              <button className={`nav-link ${activeTab === 'inspection' ? 'active' : ''}`} onClick={() => onTabChange('inspection')}>品檢記錄</button>
            </li>
            <li className="nav-item">
              <button className={`nav-link ${activeTab === 'cost' ? 'active' : ''}`} onClick={() => onTabChange('cost')}>成本分析</button>
            </li>
          </ul>
          <div className="tab-content mt-3">
            {activeTab === 'basic' && (
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
                  <div className="col-md-6 mb-3">
                    <label className="form-label fw-bold">申請單號</label>
                    <p>{detail.申請單號}</p>
                  </div>
                  <div className="col-md-6 mb-3">
                    <label className="form-label fw-bold">申請日期</label>
                    <p>{detail.申請日期}</p>
                  </div>
                  <div className="col-md-6 mb-3">
                    <label className="form-label fw-bold">{detail.客訴單號 && !detail.ncmr_number ? '客訴單號' : 'NCMR單號'}</label>
                    <p>{detail.ncmr_number || detail.客訴單號 || (detail.NCMR_ID ? `#${detail.NCMR_ID}` : '-')}</p>
                  </div>
                  <div className="col-md-6 mb-3">
                    <label className="form-label fw-bold">申請人員</label>
                    <p>{detail.申請人員姓名}</p>
                  </div>
                  <div className="col-md-6 mb-3">
                    <label className="form-label fw-bold">部門</label>
                    <p>{detail.部門}</p>
                  </div>
                  <div className="col-md-6 mb-3">
                    <label className="form-label fw-bold">緊急程度</label>
                    <p>{detail.緊急程度}</p>
                  </div>
                  <div className="col-md-6 mb-3">
                    <label className="form-label fw-bold">廠商</label>
                    <p>{detail.廠商 || '-'}</p>
                  </div>
                  <div className="col-md-6 mb-3">
                    <label className="form-label fw-bold">材質</label>
                    <p>{detail.材質 || '-'}</p>
                  </div>
                  <div className="col-md-6 mb-3">
                    <label className="form-label fw-bold">規格</label>
                    <p>{detail.產品資訊 || '-'}</p>
                  </div>
                  <div className="col-md-6 mb-3">
                    <label className="form-label fw-bold">批號</label>
                    <p>{detail.批號 || '-'}</p>
                  </div>
                  <div className="col-md-6 mb-3">
                    <label className="form-label fw-bold">重工數量</label>
                    <p>{detail.重工數量}</p>
                  </div>
                  <div className="col-md-6 mb-3">
                    <label className="form-label fw-bold">預計完成日期</label>
                    <p>{detail.預計完成日期 || '-'}</p>
                  </div>
                  <div className="col-md-6 mb-3">
                    <label className="form-label fw-bold">狀態</label>
                    <p><span className={`badge ${getStatusBadge(detail.狀態)}`}>{detail.狀態}</span></p>
                  </div>
                  <div className="col-12 mb-3">
                    <label className="form-label fw-bold">申請原因</label>
                    <p>{detail.申請原因 || '-'}</p>
                  </div>
                </div>
              </div>
            )}

            {activeTab === 'execution' && (
              <div className="tab-pane fade show active">
                <div className="d-flex justify-content-between align-items-center mb-3">
                  <h6 className="mb-0">執行記錄</h6>
                  <Button variant="primary" size="sm" onClick={onAddExecution}>
                    <i className="bi bi-plus-lg"></i> 新增
                  </Button>
                </div>
                {executions.length > 0 ? (
                  <table className="table table-sm table-bordered">
                    <thead>
                      <tr>
                        <th>負責人員</th>
                        <th>執行部門</th>
                        <th>開始時間</th>
                        <th>完成數量</th>
                        <th>執行狀況</th>
                        <th style={{ width: '100px' }}>操作</th>
                      </tr>
                    </thead>
                    <tbody>
                      {executions.map((exec: ReworkExecutionDetail, idx: number) => (
                        <tr key={idx}>
                          <td>{exec.負責人員姓名 || '-'}</td>
                          <td>{exec.執行部門 || '-'}</td>
                          <td>{exec.開始時間 ? new Date(exec.開始時間).toLocaleString('zh-TW') : '-'}</td>
                          <td>{exec.完成數量 || '0'}</td>
                          <td>{exec.執行狀況 || '-'}</td>
                          <td>
                            <div className="btn-group btn-group-sm">
                              <button className="btn btn-outline-primary" onClick={() => onEditExecution(exec)}>編輯</button>
                              <button className="btn btn-outline-danger" onClick={() => exec.識別碼 && onDeleteExecution(exec.識別碼)}>刪除</button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : (
                  <p className="text-muted">暫無執行記錄</p>
                )}
              </div>
            )}

            {activeTab === 'inspection' && (
              <div className="tab-pane fade show active">
                <div className="d-flex justify-content-between align-items-center mb-3">
                  <h6 className="mb-0">品檢記錄</h6>
                  <Button variant="primary" size="sm" onClick={onAddInspection}>
                    <i className="bi bi-plus-lg"></i> 新增
                  </Button>
                </div>
                {inspections.length > 0 ? (
                  <table className="table table-sm table-bordered">
                    <thead>
                      <tr>
                        <th>檢驗項目</th>
                        <th>檢驗結果</th>
                        <th>不良數量</th>
                        <th>檢驗人員</th>
                        <th>檢驗日期</th>
                        <th style={{ width: '100px' }}>操作</th>
                      </tr>
                    </thead>
                    <tbody>
                      {inspections.map((insp: ReworkInspectionDetail, idx: number) => (
                        <tr key={idx}>
                          <td>{insp.檢驗項目 || '-'}</td>
                          <td>{insp.檢驗結果 || '-'}</td>
                          <td>{insp.不良數量 || '0'}</td>
                          <td>{insp.檢驗人員姓名 || '-'}</td>
                          <td>{insp.檢驗日期 || '-'}</td>
                          <td>
                            <div className="btn-group btn-group-sm">
                              <button className="btn btn-outline-primary" onClick={() => onEditInspection(insp)}>編輯</button>
                              <button className="btn btn-outline-danger" onClick={() => insp.識別碼 && onDeleteInspection(insp.識別碼)}>刪除</button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : (
                  <p className="text-muted">暫無品檢記錄</p>
                )}
              </div>
            )}

            {activeTab === 'cost' && (
              <div className="tab-pane fade show active">
                <div className="d-flex justify-content-between align-items-center mb-3">
                  <h6 className="mb-0">成本分析</h6>
                  <Button variant="primary" size="sm" onClick={onAddCost}>
                    <i className="bi bi-plus-lg"></i> 新增
                  </Button>
                </div>
                {costs.length > 0 ? (
                  <table className="table table-sm table-bordered">
                    <thead>
                      <tr>
                        <th>成本類型</th>
                        <th>成本項目</th>
                        <th>單位成本</th>
                        <th>數量</th>
                        <th>總成本</th>
                        <th>記錄日期</th>
                        <th style={{ width: '100px' }}>操作</th>
                      </tr>
                    </thead>
                    <tbody>
                      {costs.map((cost: ReworkCostDetail, idx: number) => (
                        <tr key={idx}>
                          <td>{cost.成本類型 || '-'}</td>
                          <td>{cost.成本項目 || '-'}</td>
                          <td>${(Number(cost.單位成本) || 0).toFixed(2)}</td>
                          <td>{cost.數量 || '0'}</td>
                          <td>${(Number(cost.總成本) || 0).toFixed(2)}</td>
                          <td>{cost.記錄日期 || '-'}</td>
                          <td>
                            <div className="btn-group btn-group-sm">
                              <button className="btn btn-outline-primary" onClick={() => onEditCost(cost)}>編輯</button>
                              <button className="btn btn-outline-danger" onClick={() => cost.識別碼 && onDeleteCost(cost.識別碼)}>刪除</button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                    <tfoot>
                      <tr className="table-secondary">
                        <td colSpan={4}><strong>總成本</strong></td>
                        <td colSpan={3}>
                          <strong>${costs.reduce((sum: number, c: ReworkCostDetail) => sum + parseFloat(String(c.總成本 || 0)), 0).toFixed(2)}</strong>
                        </td>
                      </tr>
                    </tfoot>
                  </table>
                ) : (
                  <p className="text-muted">暫無成本記錄</p>
                )}
              </div>
            )}
          </div>
        </>
      )}
    </Modal.Body>
    <Modal.Footer>
      <Button variant="secondary" onClick={onHide}>關閉</Button>
    </Modal.Footer>
  </Modal>
);

export default ReworkDetailModal;
