import type { ReworkApplication } from '../../types';
import PermissionAction from '../../components/PermissionAction';

interface ReworkListTableProps {
  loading: boolean;
  applications: ReworkApplication[];
  onOpenDetail: (item: ReworkApplication) => void;
  onApprove: (id: number) => void;
  onDelete: (id: number) => void;
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

const getUrgencyBadge = (urgency: string) => {
  switch (urgency) {
    case '緊急': return 'bg-danger';
    case '重要': return 'bg-warning text-dark';
    default: return 'bg-secondary';
  }
};

const ReworkListTable = ({ loading, applications, onOpenDetail, onApprove, onDelete }: ReworkListTableProps) => (
  <div className="card shadow-sm">
    <div className="card-body">
      <div className="table-responsive">
        <table className="table table-hover align-middle">
          <thead className="table-light">
            <tr>
              <th>申請單號</th>
              <th>申請日期</th>
              <th>NCMR單號</th>
              <th>申請人</th>
              <th>規格</th>
              <th>重工數量</th>
              <th>緊急程度</th>
              <th>狀態</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={9} className="text-center py-5">
                  <div className="spinner-border text-primary" role="status">
                    <span className="visually-hidden">Loading...</span>
                  </div>
                </td>
              </tr>
            ) : applications.length === 0 ? (
              <tr>
                <td colSpan={9} className="text-center py-5 text-muted">查無資料</td>
              </tr>
            ) : (
              applications.map(item => (
                <tr key={item.識別碼}>
                  <td className="fw-bold">{item.申請單號}</td>
                  <td>{item.申請日期?.substring(0, 10)}</td>
                  <td>
                    <span className="badge bg-secondary">
                      {item.ncmr_number || item.客訴單號 || (item.NCMR_ID ? `#${item.NCMR_ID}` : '-')}
                    </span>
                  </td>
                  <td>{item.申請人員姓名}</td>
                  <td>{item.產品資訊 || '-'}</td>
                  <td>{item.重工數量}</td>
                  <td>
                    <span className={`badge ${getUrgencyBadge(item.緊急程度)}`}>{item.緊急程度}</span>
                  </td>
                  <td>
                    <span className={`badge ${getStatusBadge(item.狀態)}`}>{item.狀態}</span>
                  </td>
                  <td>
                    <div className="btn-group btn-group-sm">
                      <button className="btn btn-outline-info" onClick={() => onOpenDetail(item)}>詳情</button>
                      {item.狀態 === '申請中' && (
                        <PermissionAction permission="rework.approve">
                          <button className="btn btn-outline-success" onClick={() => onApprove(item.識別碼)}>審核</button>
                        </PermissionAction>
                      )}
                      <PermissionAction permission="rework.delete">
                        <button className="btn btn-outline-danger" onClick={() => onDelete(item.識別碼)}>刪除</button>
                      </PermissionAction>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  </div>
);

export default ReworkListTable;
