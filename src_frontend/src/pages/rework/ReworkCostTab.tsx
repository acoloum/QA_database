import { Button } from 'react-bootstrap';

import type { ReworkCostDetail } from '../../types';
import { calculateReworkCostTotal, formatReworkCurrency } from './reworkDetailUtils';
import PermissionAction from '../../components/PermissionAction';

interface ReworkCostTabProps {
  costs: ReworkCostDetail[];
  onAddCost: () => void;
  onEditCost: (cost: ReworkCostDetail) => void;
  onDeleteCost: (costId: number) => void;
}

const ReworkCostTab = ({ costs, onAddCost, onEditCost, onDeleteCost }: ReworkCostTabProps) => (
  <div className="tab-pane fade show active">
    <div className="d-flex justify-content-between align-items-center mb-3">
      <h6 className="mb-0">成本分析</h6>
      <PermissionAction permission="rework.create"><Button variant="primary" size="sm" onClick={onAddCost}>
        <i className="bi bi-plus-lg"></i> 新增
      </Button></PermissionAction>
    </div>
    {costs.length > 0 ? (
      <table className="table table-sm table-bordered">
        <thead>
          <tr>
            <th>成本類型</th><th>成本項目</th><th>單位成本</th><th>數量</th><th>總成本</th><th>記錄日期</th><th style={{ width: '100px' }}>操作</th>
          </tr>
        </thead>
        <tbody>
          {costs.map((cost, index) => (
            <tr key={cost.識別碼 ?? index}>
              <td>{cost.成本類型 || '-'}</td>
              <td>{cost.成本項目 || '-'}</td>
              <td>{formatReworkCurrency(cost.單位成本)}</td>
              <td>{cost.數量 || '0'}</td>
              <td>{formatReworkCurrency(cost.總成本)}</td>
              <td>{cost.記錄日期 || '-'}</td>
              <td>
                <div className="btn-group btn-group-sm">
                  <PermissionAction permission="rework.create" reasonDisplay="tooltip"><button className="btn btn-outline-primary" onClick={() => onEditCost(cost)}>編輯</button></PermissionAction>
                  <PermissionAction permission="rework.delete" reasonDisplay="tooltip"><button className="btn btn-outline-danger" onClick={() => cost.識別碼 && onDeleteCost(cost.識別碼)}>刪除</button></PermissionAction>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr className="table-secondary">
            <td colSpan={4}><strong>總成本</strong></td>
            <td colSpan={3}><strong>{formatReworkCurrency(calculateReworkCostTotal(costs))}</strong></td>
          </tr>
        </tfoot>
      </table>
    ) : (
      <p className="text-muted">暫無成本記錄</p>
    )}
  </div>
);

export default ReworkCostTab;
