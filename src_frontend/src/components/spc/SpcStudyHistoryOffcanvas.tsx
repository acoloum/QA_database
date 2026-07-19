import { useState } from 'react';
import { Alert, Badge, Button, Offcanvas, Spinner, Table } from 'react-bootstrap';
import { useSpcStudyHistory } from '../../hooks/useSpcStudies';

interface SpcStudyHistoryOffcanvasProps {
  show: boolean;
  studyId: number;
  onHide: () => void;
}

const STATUS_LABELS: Record<string, string> = {
  draft: '候選', submitted: '已送審', active: '生效', retired: '停用',
  rejected: '退回', legacy_imported: '舊資料匯入',
};

const statusColor = (status: string) => ({
  active: 'success', submitted: 'primary', rejected: 'danger', retired: 'secondary',
}[status] ?? 'light');

const SpcStudyHistoryOffcanvas = ({ show, studyId, onHide }: SpcStudyHistoryOffcanvasProps) => {
  const [pagination, setPagination] = useState({ studyId, page: 1 });
  const page = pagination.studyId === studyId ? pagination.page : 1;
  const { data, isLoading } = useSpcStudyHistory(show ? studyId : null, page);
  const versions = data?.items ?? [];
  return (
    <Offcanvas show={show} onHide={onHide} placement="end" className="spc-history-canvas">
      <Offcanvas.Header closeButton>
        <div>
          <div className="spc-eyebrow">不可變稽核軌跡</div>
          <Offcanvas.Title>研究版本歷程</Offcanvas.Title>
        </div>
      </Offcanvas.Header>
      <Offcanvas.Body>
        {isLoading ? <div className="text-center py-5"><Spinner /></div> : (
          <>
            {versions.some(version => version.audit_incomplete) && (
              <Alert variant="warning">歷程包含稽核資料不完整的舊版本，不可直接核准為新基準。</Alert>
            )}
            <Table responsive hover size="sm" className="align-middle">
              <thead><tr><th>版本</th><th>狀態</th><th>模型</th><th>建立時間</th></tr></thead>
              <tbody>
                {versions.map(version => (
                  <tr key={version.id}>
                    <td>
                      <strong>v{version.version_no}</strong>
                      <div className="small text-muted">{version.method_version}</div>
                    </td>
                    <td><Badge bg={statusColor(version.status)} text={version.status === 'draft' ? 'dark' : undefined}>{STATUS_LABELS[version.status] ?? version.status}</Badge></td>
                    <td>{version.time_model.model ?? version.time_model.candidate ?? '—'}</td>
                    <td className="small">{new Date(version.created_at).toLocaleString('zh-TW')}</td>
                  </tr>
                ))}
              </tbody>
            </Table>
            {versions.length === 0 && <div className="text-center text-muted py-5">尚無保存版本。</div>}
            {(data?.pages ?? 0) > 1 && (
              <div className="d-flex justify-content-between align-items-center mt-3">
                <Button
                  size="sm"
                  variant="outline-secondary"
                  disabled={page <= 1}
                  onClick={() => setPagination({
                    studyId,
                    page: Math.max(1, page - 1),
                  })}
                >
                  上一頁
                </Button>
                <span className="small text-muted">
                  第 {data?.page ?? page} / {data?.pages ?? 1} 頁
                </span>
                <Button
                  size="sm"
                  variant="outline-secondary"
                  disabled={page >= (data?.pages ?? 1)}
                  onClick={() => setPagination({ studyId, page: page + 1 })}
                >
                  下一頁
                </Button>
              </div>
            )}
          </>
        )}
      </Offcanvas.Body>
    </Offcanvas>
  );
};

export default SpcStudyHistoryOffcanvas;
