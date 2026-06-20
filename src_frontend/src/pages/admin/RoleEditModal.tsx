import { useState } from 'react';
import { Button, Form, Modal, Spinner } from 'react-bootstrap';

import type { RoleOption } from '../../context/useRoles';
import { useUpdateRolePermissions } from '../../hooks/useAdmin';
import { PERMISSION_GROUPS } from './adminPermissions';

interface RoleEditModalProps {
  role: RoleOption | null;
  onHide: () => void;
}

const RoleEditModal = ({ role, onHide }: RoleEditModalProps) => {
  const [perms, setPerms] = useState<Record<string, boolean>>(role?.permissions ?? {});
  const mutation = useUpdateRolePermissions({ roleName: role?.name, onSuccess: onHide });

  if (!role) return null;

  const toggle = (key: string, checked: boolean) =>
    setPerms(prev => ({ ...prev, [key]: checked }));

  const handleSave = () => mutation.mutate({ code: role.code, permissions: perms });

  return (
    <Modal show onHide={onHide} centered size="lg">
      <Modal.Header closeButton>
        <Modal.Title>
          <i className="fa-solid fa-shield-halved me-2"></i>
          編輯角色權限 — {role.name}
        </Modal.Title>
      </Modal.Header>
      <Modal.Body style={{ maxHeight: '60vh', overflowY: 'auto' }}>
        {PERMISSION_GROUPS.map(group => (
          <div key={group.label} className="mb-4">
            <div className="fw-semibold text-primary mb-2 border-bottom pb-1">{group.label}</div>
            <div className="row row-cols-2 row-cols-md-3 g-2">
              {group.perms.map(({ key, label }) => (
                <div key={key} className="col">
                  <Form.Check
                    type="checkbox"
                    id={`perm-${key}`}
                    label={label}
                    checked={!!perms[key]}
                    onChange={e => toggle(key, e.target.checked)}
                  />
                  <div className="text-muted" style={{ fontSize: '0.7rem', marginLeft: '1.5rem' }}>
                    {key}
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </Modal.Body>
      <Modal.Footer>
        <Button variant="secondary" onClick={onHide}>取消</Button>
        <Button variant="primary" onClick={handleSave} disabled={mutation.isPending}>
          {mutation.isPending
            ? <><Spinner animation="border" size="sm" className="me-2" />儲存中...</>
            : <><i className="fa-solid fa-check me-2"></i>儲存權限</>
          }
        </Button>
      </Modal.Footer>
    </Modal>
  );
};

export default RoleEditModal;
