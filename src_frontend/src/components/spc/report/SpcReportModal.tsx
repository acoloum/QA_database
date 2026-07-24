import { Button, Modal } from 'react-bootstrap';

import SpcReportView from './SpcReportView';
import type { SpcReportModel } from './spcReportModel';
import './spcReport.css';

interface SpcReportModalProps {
  show: boolean;
  model: SpcReportModel | null;
  statsItem: string;
  onHide: () => void;
}

export default function SpcReportModal({ show, model, statsItem, onHide }: SpcReportModalProps) {
  return (
    <Modal show={show} onHide={onHide} size="xl" scrollable dialogClassName="spc-report-dialog">
      <Modal.Header closeButton className="spc-report-no-print">
        <Modal.Title>SPC 報告（AIAG-VDA §11.2）</Modal.Title>
      </Modal.Header>
      <Modal.Body>
        {model
          ? <SpcReportView model={model} statsItem={statsItem} />
          : <div className="text-muted">尚無可產生報告的分析結果。</div>}
      </Modal.Body>
      <Modal.Footer className="spc-report-no-print">
        <Button variant="secondary" onClick={onHide}>關閉</Button>
        <Button variant="primary" onClick={() => window.print()} disabled={!model}>
          列印 / 存成 PDF
        </Button>
      </Modal.Footer>
    </Modal>
  );
}
