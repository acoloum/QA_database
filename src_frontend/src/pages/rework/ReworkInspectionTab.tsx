import { Button } from 'react-bootstrap';

import type { ReworkInspectionDetail } from '../../types';
import PermissionAction from '../../components/PermissionAction';

interface ReworkInspectionTabProps {
  inspections: ReworkInspectionDetail[];
  onAddInspection: () => void;
  onEditInspection: (inspection: ReworkInspectionDetail) => void;
  onDeleteInspection: (inspectionId: number) => void;
}

const ReworkInspectionTab = ({
  inspections,
  onAddInspection,
  onEditInspection,
  onDeleteInspection,
}: ReworkInspectionTabProps) => (
  <div className="tab-pane fade show active">
    <div className="d-flex justify-content-between align-items-center mb-3">
      <h6 className="mb-0">品檢記錄</h6>
      <PermissionAction permission="rework.create"><Button variant="primary" size="sm" onClick={onAddInspection}>
        <i className="bi bi-plus-lg"></i> 新增
      </Button></PermissionAction>
    </div>
    {inspections.length > 0 ? (
      <table className="table table-sm table-bordered">
        <thead>
          <tr>
            <th>檢驗項目</th><th>檢驗結果</th><th>不良數量</th><th>檢驗人員</th><th>檢驗日期</th><th style={{ width: '100px' }}>操作</th>
          </tr>
        </thead>
        <tbody>
          {inspections.map((inspection, index) => (
            <tr key={inspection.識別碼 ?? index}>
              <td>{inspection.檢驗項目 || '-'}</td>
              <td>{inspection.檢驗結果 || '-'}</td>
              <td>{inspection.不良數量 || '0'}</td>
              <td>{inspection.檢驗人員姓名 || '-'}</td>
              <td>{inspection.檢驗日期 || '-'}</td>
              <td>
                <div className="btn-group btn-group-sm">
                  <PermissionAction permission="rework.create" reasonDisplay="tooltip"><button className="btn btn-outline-primary" onClick={() => onEditInspection(inspection)}>編輯</button></PermissionAction>
                  <PermissionAction permission="rework.delete" reasonDisplay="tooltip"><button className="btn btn-outline-danger" onClick={() => inspection.識別碼 && onDeleteInspection(inspection.識別碼)}>刪除</button></PermissionAction>
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
);

export default ReworkInspectionTab;
