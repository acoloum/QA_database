import { useState } from 'react';
import { Offcanvas } from 'react-bootstrap';

import { useAuth } from '../../context/useAuth';
import {
  useMsaEquipmentDetail,
  useMsaStatusEvent,
} from '../../hooks/useMsaEquipment';
import type {
  EquipmentCalibration,
  EquipmentCorrectionPoint,
  EquipmentLink,
  EquipmentStatus,
  EquipmentStatusEvent,
} from '../../types/msa';
import EquipmentCalibrationForm from './EquipmentCalibrationForm';
import EquipmentStatusBadge from './EquipmentStatusBadge';

interface EquipmentDetailDrawerProps {
  equipmentId: number | null;
  show: boolean;
  onHide: () => void;
}

type Tab = 'master' | 'calibration' | 'events' | 'links' | 'studies';

const statusEventType = (targetStatus: EquipmentStatus) => {
  if (targetStatus === 'active') return 'reactivated' as const;
  if (targetStatus === 'maintenance') return 'maintenance' as const;
  if (targetStatus === 'inactive') return 'inactive' as const;
  if (targetStatus === 'scrapped') return 'scrapped' as const;
  return 'major_adjustment' as const;
};

const tabs: Array<{ id: Tab; label: string }> = [
  { id: 'master', label: '主檔與能力' },
  { id: 'calibration', label: '校驗與補正點' },
  { id: 'events', label: '狀態事件' },
  { id: 'links', label: 'CQI-9 來源' },
  { id: 'studies', label: 'MSA 研究引用' },
];

export default function EquipmentDetailDrawer({
  equipmentId,
  show,
  onHide,
}: EquipmentDetailDrawerProps) {
  const { hasPermission } = useAuth();
  const detail = useMsaEquipmentDetail(equipmentId);
  const statusEvent = useMsaStatusEvent();
  const [activeTab, setActiveTab] = useState<Tab>('master');
  const [targetStatus, setTargetStatus] = useState<EquipmentStatus>('maintenance');
  const [statusReason, setStatusReason] = useState('');
  const equipment = detail.data;

  return (
    <Offcanvas
      show={show}
      onHide={onHide}
      placement="end"
      className="msa-equipment-drawer"
      aria-labelledby="equipment-drawer-title"
    >
      <Offcanvas.Header closeButton>
        <div>
          <div className="msa-eyebrow">設備證據軌</div>
          <Offcanvas.Title id="equipment-drawer-title">
            {equipment ? `${equipment.equipment_no} · ${equipment.name}` : '設備明細'}
          </Offcanvas.Title>
        </div>
      </Offcanvas.Header>
      <Offcanvas.Body>
        {detail.isLoading && <p role="status">正在讀取設備明細…</p>}
        {detail.isError && (
          <div className="msa-state msa-state--error" role="alert">
            <p>無法載入設備明細。</p>
            <button type="button" onClick={() => void detail.refetch()}>重試</button>
          </div>
        )}
        {equipment && (
          <>
            <div className="msa-drawer-status">
              <EquipmentStatusBadge status={equipment.status} />
              <EquipmentStatusBadge status={equipment.calibration_status} />
              <span className="msa-mono">{equipment.next_calibration_date || '無下次校驗日'}</span>
            </div>
            <div className="msa-tabs" role="tablist" aria-label="設備明細分類">
              {tabs.map((tab) => (
                <button
                  key={tab.id}
                  type="button"
                  role="tab"
                  aria-selected={activeTab === tab.id}
                  className={activeTab === tab.id ? 'is-active' : ''}
                  onClick={() => setActiveTab(tab.id)}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            {activeTab === 'master' && (
              <section className="msa-evidence-panel" aria-labelledby="equipment-master-title">
                <h2 id="equipment-master-title">主檔與量測能力</h2>
                <dl className="msa-definition-grid">
                  <div><dt>設備編號</dt><dd className="msa-mono">{equipment.equipment_no}</dd></div>
                  <div><dt>型式</dt><dd>{equipment.equipment_type || '未填寫'}</dd></div>
                  <div><dt>製造商／型號</dt><dd>{[equipment.manufacturer, equipment.model].filter(Boolean).join(' / ') || '未填寫'}</dd></div>
                  <div><dt>序號</dt><dd className="msa-mono">{equipment.serial_no || '未填寫'}</dd></div>
                  <div><dt>量程</dt><dd className="msa-mono">{equipment.range_min ?? '—'} – {equipment.range_max ?? '—'} {equipment.unit}</dd></div>
                  <div><dt>解析度</dt><dd className="msa-mono">{equipment.resolution ?? '未填寫'} {equipment.unit}</dd></div>
                  <div><dt>位置</dt><dd>{equipment.location || '未填寫'}</dd></div>
                  <div><dt>保管人</dt><dd>{equipment.custodian || '未填寫'}</dd></div>
                </dl>
                {hasPermission('msa.manage') && (
                  <form
                    className="msa-status-form"
                    onSubmit={(event) => {
                      event.preventDefault();
                      void statusEvent.mutateAsync({
                        equipmentId: equipment.id,
                        event_type: statusEventType(targetStatus),
                        expected_status: equipment.status,
                        target_status: targetStatus,
                        reason: statusReason.trim(),
                      });
                    }}
                  >
                    <h3>變更設備狀態</h3>
                    <label>
                      目標狀態
                      <select
                        value={targetStatus}
                        onChange={(event) => setTargetStatus(event.target.value as EquipmentStatus)}
                      >
                        <option value="maintenance">維修</option>
                        <option value="inactive">停用</option>
                        <option value="scrapped">報廢</option>
                        <option value="active">重新啟用</option>
                      </select>
                    </label>
                    <label>
                      變更原因
                      <textarea
                        value={statusReason}
                        onChange={(event) => setStatusReason(event.target.value)}
                        required
                      />
                    </label>
                    <button
                      className="msa-button msa-button--primary"
                      type="submit"
                      disabled={!statusReason.trim() || statusEvent.isPending}
                    >
                      變更設備狀態
                    </button>
                  </form>
                )}
              </section>
            )}

            {activeTab === 'calibration' && (
              <section className="msa-evidence-panel" aria-labelledby="equipment-calibration-title">
                <h2 id="equipment-calibration-title">校驗證據與補正點</h2>
                {equipment.calibrations.length === 0 && <p>尚無校驗紀錄。</p>}
                {equipment.calibrations.map((record: EquipmentCalibration) => (
                  <article className="msa-calibration-version" key={record.id}>
                    <header>
                      <strong>{record.certificate_no || `校驗 #${record.id}`}</strong>
                      <span>{record.status === 'approved' ? '已核准' : '草稿'}</span>
                    </header>
                    <p className="msa-mono">
                      {record.calibration_date} → {record.next_due_date || '未設定到期日'}
                    </p>
                    <p>{record.traceability_standard || '未填寫追溯標準'}</p>
                    <p>
                      證書附件：
                      {record.certificate_attachment_id
                        ? <span className="msa-mono">#{record.certificate_attachment_id}</span>
                        : '未附檔'}
                    </p>
                    {record.correction_points.length > 0 && (
                      <table>
                        <caption>校驗 #{record.id} 補正點</caption>
                        <thead>
                          <tr><th>模式</th><th>名目值</th><th>器示值</th><th>補正值</th></tr>
                        </thead>
                        <tbody>
                          {record.correction_points.map((point: EquipmentCorrectionPoint) => (
                            <tr key={point.id}>
                              <td>{point.measurement_mode || '共用'}</td>
                              <td className="msa-mono">{point.nominal_value}</td>
                              <td className="msa-mono">{point.indicated_value}</td>
                              <td className="msa-mono">{point.correction_value ?? '—'}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    )}
                  </article>
                ))}
                <EquipmentCalibrationForm
                  equipmentId={equipment.id}
                  calibrations={equipment.calibrations}
                />
              </section>
            )}

            {activeTab === 'events' && (
              <section className="msa-evidence-panel" aria-labelledby="equipment-events-title">
                <h2 id="equipment-events-title">狀態事件</h2>
                {equipment.status_events.length === 0
                  ? <p>尚無狀態事件。</p>
                  : (
                    <ol className="msa-timeline">
                      {equipment.status_events.map((event: EquipmentStatusEvent) => (
                        <li key={event.id}>
                          <strong>{event.event_type}</strong>
                          <time>{new Date(event.occurred_at).toLocaleString('zh-TW')}</time>
                          <p>{event.reason || '未填寫原因'}</p>
                        </li>
                      ))}
                    </ol>
                  )}
              </section>
            )}

            {activeTab === 'links' && (
              <section className="msa-evidence-panel" aria-labelledby="equipment-links-title">
                <h2 id="equipment-links-title">CQI-9 來源連結</h2>
                {equipment.links.length === 0
                  ? <p>此設備沒有 CQI-9 專用來源連結。</p>
                  : equipment.links.map((link: EquipmentLink) => (
                    <p key={link.id}>
                      <strong>{link.source_entity_type} #{link.source_entity_id}</strong>
                      {' · '}{link.is_current ? '目前正式連結' : '歷史連結'}
                    </p>
                  ))}
              </section>
            )}

            {activeTab === 'studies' && (
              <section className="msa-evidence-panel" aria-labelledby="equipment-studies-title">
                <h2 id="equipment-studies-title">引用本設備的 MSA 研究</h2>
                <p>研究引用將於研究模組啟用後呈現</p>
              </section>
            )}
          </>
        )}
      </Offcanvas.Body>
    </Offcanvas>
  );
}
