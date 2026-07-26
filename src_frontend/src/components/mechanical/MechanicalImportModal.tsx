import { useRef, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { Alert, Button, Form, ListGroup, Modal } from 'react-bootstrap';

import { mechanicalApi } from '../../services/mechanicalApi';
import type { MechanicalImportResult } from '../../services/mechanicalApi';
import { apiErrorMessage } from '../../services/apiError';

interface MechanicalImportModalProps {
  show: boolean;
  handleClose: () => void;
  onSuccess: () => void;
}

export default function MechanicalImportModal({ show, handleClose, onSuccess }: MechanicalImportModalProps) {
  const [file, setFile] = useState<File | null>(null);
  const [material, setMaterial] = useState('');
  const [vendorId, setVendorId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<MechanicalImportResult | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const { data: vendors = [] } = useQuery({
    queryKey: ['vendors'],
    queryFn: mechanicalApi.getVendors,
  });

  const importMutation = useMutation({
    mutationFn: () => mechanicalApi.importExcel(file as File, material.trim(), vendorId ?? undefined),
  });

  const reset = () => {
    setFile(null);
    setError(null);
    setResult(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handleUpload = async () => {
    if (!file) {
      setError('請選擇檔案');
      return;
    }
    // 未指定廠商時無法反查公差材質，此時預設材質才是必填
    if (vendorId === null && !material.trim()) {
      setError('未指定廠商時無法自動判定材質，請指定廠商或填寫預設材質');
      return;
    }
    setError(null);
    setResult(null);
    try {
      const data = await importMutation.mutateAsync();
      setResult(data);
      onSuccess();
    } catch (err) {
      setError(apiErrorMessage(err, '匯入失敗，請檢查檔案格式'));
    }
  };

  const handleModalClose = () => {
    reset();
    handleClose();
  };

  return (
    <Modal show={show} onHide={handleModalClose}>
      <Modal.Header closeButton>
        <Modal.Title>匯入機械性質 Excel</Modal.Title>
      </Modal.Header>
      <Modal.Body>
        <Alert variant="info">
          請上傳必榮供應商格式的機械性質 Excel 檔案 (.xlsx, .xls)。來源檔案沒有材質欄位，
          指定廠商後，系統會<strong>依各工作表的產品尺寸自動比對該廠商公差建檔的材質並填入</strong>，
          不再整批套用同一材質。
        </Alert>
        <Form.Group className="mb-3" controlId="mechanical-import-vendor">
          <Form.Label>廠商（自動判定材質所需）</Form.Label>
          <Form.Select
            value={vendorId ?? ''}
            onChange={(event) => setVendorId(event.target.value ? Number(event.target.value) : null)}
          >
            <option value="">未指定</option>
            {vendors.map((vendor) => (
              <option key={vendor.id} value={vendor.id}>{vendor.name}</option>
            ))}
          </Form.Select>
        </Form.Group>
        <Form.Group className="mb-3" controlId="mechanical-import-material">
          <Form.Label>
            預設材質{vendorId === null ? '（必填）' : '（選填，後援用）'}
          </Form.Label>
          <Form.Control
            value={material}
            onChange={(event) => setMaterial(event.target.value)}
            placeholder="例如 6061-T651"
          />
          <Form.Text className="text-muted">
            僅在公差檔查無該產品尺寸時套用。若某尺寸對應到多個材質，該工作表不會匯入，
            會列在下方錯誤清單供人工確認。
          </Form.Text>
        </Form.Group>
        <Form.Group className="mb-3" controlId="mechanical-import-file">
          <Form.Label>選擇檔案</Form.Label>
          <Form.Control
            type="file"
            accept=".xlsx, .xls"
            ref={fileInputRef}
            onChange={(event) => {
              const target = event.target as HTMLInputElement;
              setFile(target.files && target.files.length > 0 ? target.files[0] : null);
              setError(null);
              setResult(null);
            }}
          />
        </Form.Group>
        {error && <Alert variant="danger">{error}</Alert>}
        {result && (
          <Alert variant={result.errors.length > 0 ? 'warning' : 'success'}>
            <div>{result.message}</div>
            {result.skipped > 0 && (
              <div className="small text-muted mt-1">
                已略過 {result.skipped} 筆重複資料（產品尺寸/材質/測試日期/追溯編號皆相同，判定為已匯入過）。
              </div>
            )}
            {result.material_sources?.length > 0 && (
              <>
                <div className="mt-2 mb-1">各工作表套用的材質：</div>
                <ListGroup className="small" style={{ maxHeight: 200, overflowY: 'auto' }}>
                  {result.material_sources.map((source) => (
                    <ListGroup.Item key={source.工作表}>
                      {source.產品尺寸} → <strong>{source.材質}</strong>（{source.筆數} 筆）
                      {source.來源 === '預設值' && (
                        <span className="text-warning ms-1">
                          ⚠ 公差檔查無此尺寸，已套用預設材質
                        </span>
                      )}
                    </ListGroup.Item>
                  ))}
                </ListGroup>
              </>
            )}
            {result.errors.length > 0 && (
              <>
                <div className="mt-2 mb-1">以下 {result.errors.length} 項匯入失敗，需人工檢查：</div>
                <ListGroup className="small" style={{ maxHeight: 200, overflowY: 'auto' }}>
                  {result.errors.map((e, idx) => (
                    <ListGroup.Item key={idx}>
                      工作表「{e.工作表}」
                      {e.欄位 !== null && `第 ${e.欄位} 欄`}：{e.錯誤}
                    </ListGroup.Item>
                  ))}
                </ListGroup>
              </>
            )}
          </Alert>
        )}
      </Modal.Body>
      <Modal.Footer>
        <Button variant="secondary" onClick={handleModalClose} disabled={importMutation.isPending}>
          關閉
        </Button>
        <Button variant="success" onClick={handleUpload} disabled={!file || importMutation.isPending}>
          {importMutation.isPending ? '匯入中...' : '開始匯入'}
        </Button>
      </Modal.Footer>
    </Modal>
  );
}
