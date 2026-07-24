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
    if (!material.trim()) {
      setError('請輸入材質');
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
          請先指定本次匯入資料要套用的材質；廠商為選填，指定後可套用對應公差判定 NG。
        </Alert>
        <Form.Group className="mb-3" controlId="mechanical-import-material">
          <Form.Label>材質（必填）</Form.Label>
          <Form.Control
            value={material}
            onChange={(event) => setMaterial(event.target.value)}
            placeholder="例如 6061-T651"
          />
        </Form.Group>
        <Form.Group className="mb-3" controlId="mechanical-import-vendor">
          <Form.Label>廠商</Form.Label>
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
            {result.errors.length > 0 && (
              <>
                <div className="mt-2 mb-1">以下 {result.errors.length} 筆資料匯入失敗，需人工檢查：</div>
                <ListGroup className="small" style={{ maxHeight: 200, overflowY: 'auto' }}>
                  {result.errors.map((e, idx) => (
                    <ListGroup.Item key={idx}>
                      工作表「{e.工作表}」第 {e.欄位} 欄：{e.錯誤}
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
