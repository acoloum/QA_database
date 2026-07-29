import { useState } from 'react';
import { Offcanvas } from 'react-bootstrap';
import { Link } from 'react-router-dom';

import { useAuth } from '../../context/useAuth';
import {
  useDownloadMsaCertificate,
  useMsaEquipmentDetail,
  useMsaStatusEvent,
  useUpdateMsaEquipment,
} from '../../hooks/useMsaEquipment';
import type {
  CalibrationRecordStatus,
  CalibrationType,
  EquipmentCalibration,
  EquipmentCorrectionPoint,
  EquipmentLink,
  EquipmentStatus,
  EquipmentStatusEvent,
} from '../../types/msa';
import EquipmentStatusBadge from './EquipmentStatusBadge';

interface EquipmentDetailDrawerProps {
  equipmentId: number | null;
  show: boolean;
  onHide: () => void;
}

type Tab = 'master' | 'calibration' | 'events' | 'links' | 'studies';

const statusEventType = (
  sourceStatus: EquipmentStatus,
  targetStatus: EquipmentStatus,
) => {
  if (targetStatus === 'active') {
    return sourceStatus === 'pending_review'
      ? 'review_completed' as const
      : 'reactivated' as const;
  }
  if (targetStatus === 'maintenance') return 'maintenance' as const;
  if (targetStatus === 'inactive') return 'inactive' as const;
  if (targetStatus === 'scrapped') return 'scrapped' as const;
  return 'major_adjustment' as const;
};

const STATUS_OPTIONS: Array<{ value: EquipmentStatus; label: string }> = [
  { value: 'pending_review', label: '待確認' },
  { value: 'active', label: '使用中' },
  { value: 'maintenance', label: '維修' },
  { value: 'inactive', label: '停用' },
  { value: 'scrapped', label: '報廢' },
];

const EVENT_LABELS: Record<EquipmentStatusEvent['event_type'], string> = {
  calibration_overdue: '校驗逾期',
  calibration_failed: '校驗失敗',
  maintenance: '進入維修',
  major_adjustment: '重大調整',
  inactive: '停用',
  scrapped: '報廢',
  reactivated: '重新啟用',
  review_completed: '審查完成',
};

const CALIBRATION_STATUS_LABELS: Record<CalibrationRecordStatus, string> = {
  draft: '草稿',
  in_progress: '輸入中',
  ready_for_submission: '待送審',
  submitted: '已送審',
  rejected: '已退回',
  approved: '已核准',
  superseded: '已被取代',
  voided: '已作廢',
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
  const updateEquipment = useUpdateMsaEquipment();
  const downloadCertificate = useDownloadMsaCertificate();
  const [activeTab, setActiveTab] = useState<Tab>('master');
  const [isEditing, setIsEditing] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);
  const [targetStatus, setTargetStatus] = useState<EquipmentStatus>('maintenance');
  const [statusReason, setStatusReason] = useState('');
  const [statusError, setStatusError] = useState<string | null>(null);
  const equipment = detail.data;
  const canManageEquipment = hasPermission('calibration.manage');
  const canCompleteCalibration = (
    hasPermission('calibration.execute')
    && hasPermission('calibration.manage')
  );
  const availableStatuses = STATUS_OPTIONS.filter(
    (option) => option.value !== equipment?.status,
  );
  const selectedTargetStatus = (
    targetStatus === equipment?.status
      ? availableStatuses[0]?.value
      : targetStatus
  ) ?? 'active';

  const selectTab = (tab: Tab) => {
    setActiveTab(tab);
    requestAnimationFrame(() => {
      document.getElementById(`equipment-tab-${tab}-tab`)?.focus();
    });
  };

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
                  id={`equipment-tab-${tab.id}-tab`}
                  aria-controls={`equipment-tab-${tab.id}`}
                  aria-selected={activeTab === tab.id}
                  tabIndex={activeTab === tab.id ? 0 : -1}
                  className={activeTab === tab.id ? 'is-active' : ''}
                  onClick={() => setActiveTab(tab.id)}
                  onKeyDown={(event) => {
                    const index = tabs.findIndex((item) => item.id === tab.id);
                    let nextIndex = index;
                    if (event.key === 'ArrowRight') nextIndex = (index + 1) % tabs.length;
                    else if (event.key === 'ArrowLeft') nextIndex = (index - 1 + tabs.length) % tabs.length;
                    else if (event.key === 'Home') nextIndex = 0;
                    else if (event.key === 'End') nextIndex = tabs.length - 1;
                    else return;
                    event.preventDefault();
                    selectTab(tabs[nextIndex].id);
                  }}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            {activeTab === 'master' && (
              <section
                className="msa-evidence-panel"
                role="tabpanel"
                id="equipment-tab-master"
                aria-labelledby="equipment-tab-master-tab"
              >
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
                {canManageEquipment && !isEditing && (
                  <button
                    type="button"
                    className="msa-button msa-button--quiet"
                    onClick={() => setIsEditing(true)}
                  >
                    編輯主檔
                  </button>
                )}
                {canManageEquipment && isEditing && (
                  <form
                    className="msa-edit-form"
                    onSubmit={(event) => {
                      event.preventDefault();
                      setEditError(null);
                      const data = new FormData(event.currentTarget);
                      void updateEquipment.mutateAsync({
                        equipmentId: equipment.id,
                        payload: {
                          name: String(data.get('name')),
                          equipment_type: String(data.get('equipment_type') || '') || null,
                          manufacturer: String(data.get('manufacturer') || '') || null,
                          model: String(data.get('model') || '') || null,
                          serial_no: String(data.get('serial_no') || '') || null,
                          range_min: String(data.get('range_min') || '') || null,
                          range_max: String(data.get('range_max') || '') || null,
                          resolution: String(data.get('resolution') || '') || null,
                          unit: String(data.get('unit') || '') || null,
                          department: String(data.get('department') || '') || null,
                          location: String(data.get('location') || '') || null,
                          custodian: String(data.get('custodian') || '') || null,
                          calibration_type: (String(data.get('calibration_type') || '') || null) as CalibrationType | null,
                          calibration_interval_months: data.get('calibration_interval_months')
                            ? Number(data.get('calibration_interval_months'))
                            : null,
                        },
                      }).then(() => {
                        setIsEditing(false);
                        void detail.refetch();
                      }).catch((error: unknown) => {
                        setEditError(
                          error instanceof Error
                            ? error.message
                            : '主檔未更新，請檢查輸入內容。',
                        );
                      });
                    }}
                  >
                    <h3>編輯主檔</h3>
                    <label>
                      設備名稱
                      <input name="name" defaultValue={equipment.name} required />
                    </label>
                    <label>
                      型式
                      <input name="equipment_type" defaultValue={equipment.equipment_type ?? ''} />
                    </label>
                    <label>
                      製造商
                      <input name="manufacturer" defaultValue={equipment.manufacturer ?? ''} />
                    </label>
                    <label>
                      型號
                      <input name="model" defaultValue={equipment.model ?? ''} />
                    </label>
                    <label>
                      序號
                      <input name="serial_no" defaultValue={equipment.serial_no ?? ''} />
                    </label>
                    <label>
                      量程下限
                      <input name="range_min" inputMode="decimal" defaultValue={equipment.range_min ?? ''} />
                    </label>
                    <label>
                      量程上限
                      <input name="range_max" inputMode="decimal" defaultValue={equipment.range_max ?? ''} />
                    </label>
                    <label>
                      解析度
                      <input name="resolution" inputMode="decimal" defaultValue={equipment.resolution ?? ''} />
                    </label>
                    <label>
                      單位
                      <input name="unit" defaultValue={equipment.unit ?? ''} />
                    </label>
                    <label>
                      部門
                      <input name="department" defaultValue={equipment.department ?? ''} />
                    </label>
                    <label>
                      位置
                      <input name="location" defaultValue={equipment.location ?? ''} />
                    </label>
                    <label>
                      保管人
                      <input name="custodian" defaultValue={equipment.custodian ?? ''} />
                    </label>
                    <label>
                      校驗類別
                      <select name="calibration_type" defaultValue={equipment.calibration_type ?? ''}>
                        <option value="">未設定</option>
                        <option value="external">外校</option>
                        <option value="internal">內校</option>
                        <option value="exempt">免校</option>
                      </select>
                    </label>
                    <label>
                      校驗週期（月）
                      <input name="calibration_interval_months" type="number" min="0" defaultValue={equipment.calibration_interval_months ?? ''} />
                    </label>
                    {editError && <p role="alert">{editError}</p>}
                    <div className="msa-edit-form__actions">
                      <button
                        type="button"
                        className="msa-button msa-button--quiet"
                        onClick={() => setIsEditing(false)}
                      >
                        取消
                      </button>
                      <button
                        className="msa-button msa-button--primary"
                        type="submit"
                        disabled={updateEquipment.isPending}
                      >
                        儲存主檔
                      </button>
                    </div>
                  </form>
                )}
                {canManageEquipment && (
                  <form
                    className="msa-status-form"
                    onSubmit={(event) => {
                      event.preventDefault();
                      setStatusError(null);
                      void statusEvent.mutateAsync({
                        equipmentId: equipment.id,
                        event_type: statusEventType(equipment.status, selectedTargetStatus),
                        expected_status: equipment.status,
                        target_status: selectedTargetStatus,
                        reason: statusReason.trim(),
                      }).catch((error: unknown) => {
                        setStatusError(
                          error instanceof Error
                            ? error.message
                            : '設備狀態未變更，請重新載入後再試。',
                        );
                      });
                    }}
                  >
                    <h3>變更設備狀態</h3>
                    <label>
                      目標狀態
                      <select
                        value={selectedTargetStatus}
                        onChange={(event) => setTargetStatus(event.target.value as EquipmentStatus)}
                      >
                        {availableStatuses.map((option) => (
                          <option key={option.value} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </select>
                    </label>
                    {statusError && <p role="alert">{statusError}</p>}
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
              <section
                className="msa-evidence-panel"
                role="tabpanel"
                id="equipment-tab-calibration"
                aria-labelledby="equipment-tab-calibration-tab"
              >
                <h2 id="equipment-calibration-title">校驗證據與補正點</h2>
                {equipment.calibrations.length === 0 && <p>尚無校驗紀錄。</p>}
                {equipment.calibrations.map((record: EquipmentCalibration) => (
                  <article className="msa-calibration-version" key={record.id}>
                    <header>
                      <strong>{record.certificate_no || `校驗 #${record.id}`}</strong>
                      <span>
                        {record.data_level === 'summary_legacy'
                          ? '舊版摘要資料'
                          : '詳細校正資料'}
                      </span>
                      <span>{CALIBRATION_STATUS_LABELS[record.status]}</span>
                    </header>
                    <p className="msa-mono">
                      {record.calibration_date} → {record.next_due_date || '未設定到期日'}
                    </p>
                    <p>{record.traceability_standard || '未填寫追溯標準'}</p>
                    {record.reference_standard_no && (
                      <p className="msa-mono">
                        參考標準器：{record.reference_standard_no}
                        {record.reference_standard_due_date && (
                          <small>（有效期至 {record.reference_standard_due_date}）</small>
                        )}
                      </p>
                    )}
                    <p>
                      證書附件：
                      {record.certificate_attachment_id
                        ? (
                          <button
                            type="button"
                            className="msa-button msa-button--quiet"
                            disabled={downloadCertificate.isPending}
                            aria-label={`下載證書 ${record.certificate_no || record.id}`}
                            onClick={() => void downloadCertificate.mutateAsync({
                              attachmentId: record.certificate_attachment_id!,
                              filename: `${record.certificate_no || `calibration-${record.id}`}.pdf`,
                            })}
                          >
                            下載附件 #{record.certificate_attachment_id}
                          </button>
                        )
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
                    {record.data_level === 'detailed' && (
                      <Link
                        className="msa-button msa-button--quiet"
                        to={`/calibrations/${record.id}`}
                      >
                        查看詳細證據
                      </Link>
                    )}
                  </article>
                ))}
                {canCompleteCalibration && (
                  <Link
                    className="msa-button msa-button--primary"
                    to={`/measurement-equipment/${equipment.id}/calibrations/new`}
                  >
                    建立詳細校正
                  </Link>
                )}
              </section>
            )}

            {activeTab === 'events' && (
              <section
                className="msa-evidence-panel"
                role="tabpanel"
                id="equipment-tab-events"
                aria-labelledby="equipment-tab-events-tab"
              >
                <h2 id="equipment-events-title">狀態事件</h2>
                {equipment.status_events.length === 0
                  ? <p>尚無狀態事件。</p>
                  : (
                    <ol className="msa-timeline">
                      {equipment.status_events.map((event: EquipmentStatusEvent) => (
                        <li key={event.id}>
                          <strong>{EVENT_LABELS[event.event_type]}</strong>
                          <time>{new Date(event.occurred_at).toLocaleString('zh-TW')}</time>
                          <p>{event.reason || '未填寫原因'}</p>
                        </li>
                      ))}
                    </ol>
                  )}
              </section>
            )}

            {activeTab === 'links' && (
              <section
                className="msa-evidence-panel"
                role="tabpanel"
                id="equipment-tab-links"
                aria-labelledby="equipment-tab-links-tab"
              >
                <h2 id="equipment-links-title">CQI-9 來源連結</h2>
                {equipment.links.length === 0
                  ? <p>此設備沒有 CQI-9 專用來源連結。</p>
                  : equipment.links.map((link: EquipmentLink) => (
                    <p key={link.id}>
                      <a href={
                        link.source_entity_type === 'Recorder'
                          ? '/pyrometry/recorders'
                          : '/pyrometry/thermocouples'
                      }>
                        <strong>{link.source_entity_type} #{link.source_entity_id}</strong>
                      </a>
                      {' · '}{link.is_current ? '目前正式連結' : '歷史連結'}
                      <small>
                        請在
                        {link.source_entity_type === 'Recorder' ? '記錄器' : '熱電偶'}
                        校正頁查詢 ID {link.source_entity_id}
                      </small>
                    </p>
                  ))}
              </section>
            )}

            {activeTab === 'studies' && (
              <section
                className="msa-evidence-panel"
                role="tabpanel"
                id="equipment-tab-studies"
                aria-labelledby="equipment-tab-studies-tab"
              >
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
