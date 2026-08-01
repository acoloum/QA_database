import { Button } from 'react-bootstrap';

import type { ReworkExecutionDetail } from '../../types';
import PermissionAction from '../../components/PermissionAction';

interface ReworkExecutionTabProps {
  executions: ReworkExecutionDetail[];
  onAddExecution: () => void;
  onEditExecution: (execution: ReworkExecutionDetail) => void;
  onDeleteExecution: (executionId: number) => void;
}

const ReworkExecutionTab = ({
  executions,
  onAddExecution,
  onEditExecution,
  onDeleteExecution,
}: ReworkExecutionTabProps) => (
  <div className="tab-pane fade show active">
    <div className="d-flex justify-content-between align-items-center mb-3">
      <h6 className="mb-0">執行記錄</h6>
      <PermissionAction permission="rework.create"><Button variant="primary" size="sm" onClick={onAddExecution}>
        <i className="bi bi-plus-lg"></i> 新增
      </Button></PermissionAction>
    </div>
    {executions.length > 0 ? (
      <table className="table table-sm table-bordered">
        <thead>
          <tr>
            <th>負責人員</th><th>執行部門</th><th>開始時間</th><th>完成數量</th><th>執行狀況</th><th style={{ width: '100px' }}>操作</th>
          </tr>
        </thead>
        <tbody>
          {executions.map((exec, index) => (
            <tr key={exec.識別碼 ?? index}>
              <td>{exec.負責人員姓名 || '-'}</td>
              <td>{exec.執行部門 || '-'}</td>
              <td>{exec.開始時間 ? new Date(exec.開始時間).toLocaleString('zh-TW') : '-'}</td>
              <td>{exec.完成數量 || '0'}</td>
              <td>{exec.執行狀況 || '-'}</td>
              <td>
                <div className="btn-group btn-group-sm">
                  <PermissionAction permission="rework.create"><button className="btn btn-outline-primary" onClick={() => onEditExecution(exec)}>編輯</button></PermissionAction>
                  <PermissionAction permission="rework.delete"><button className="btn btn-outline-danger" onClick={() => exec.識別碼 && onDeleteExecution(exec.識別碼)}>刪除</button></PermissionAction>
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
);

export default ReworkExecutionTab;
