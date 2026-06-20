import { useState } from 'react';
import { Alert, Button, Form, Modal, Spinner } from 'react-bootstrap';

import type { RoleOption } from '../../context/useRoles';
import { useCreateAdminUser } from '../../hooks/useAdmin';

interface CreateUserModalProps {
  show: boolean;
  roleOptions: RoleOption[];
  onHide: () => void;
}

const CreateUserModal = ({ show, roleOptions, onHide }: CreateUserModalProps) => {
  const [newUsername, setNewUsername] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [newConfirm, setNewConfirm] = useState('');
  const [newRole, setNewRole] = useState<string>('inspector');
  const [formError, setFormError] = useState('');
  const createMutation = useCreateAdminUser({
    onSuccess: () => {
      resetForm();
      onHide();
    },
    onError: setFormError,
  });

  const resetForm = () => {
    setNewUsername('');
    setNewPassword('');
    setNewConfirm('');
    setNewRole('inspector');
    setFormError('');
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setFormError('');
    const trimmedUsername = newUsername.trim();
    if (!/^[A-Za-z0-9_\-.]{3,50}$/.test(trimmedUsername)) {
      setFormError('使用者名稱長度需 3–50 字元，僅允許英數字、底線、連字號、點號');
      return;
    }
    if (newPassword !== newConfirm) {
      setFormError('兩次密碼輸入不一致');
      return;
    }
    if (newPassword.length < 8) {
      setFormError('密碼長度至少需要 8 個字元');
      return;
    }
    createMutation.mutate({ username: trimmedUsername, password: newPassword, role: newRole });
  };

  const handleHide = () => {
    resetForm();
    onHide();
  };

  return (
    <Modal show={show} onHide={handleHide} centered>
      <Modal.Header closeButton>
        <Modal.Title>
          <i className="fa-solid fa-user-plus me-2"></i>新增使用者
        </Modal.Title>
      </Modal.Header>
      <Modal.Body>
        {formError && <Alert variant="danger">{formError}</Alert>}
        <Form onSubmit={handleSubmit} id="createUserForm">
          <Form.Group className="mb-3">
            <Form.Label>使用者名稱</Form.Label>
            <Form.Control
              type="text"
              placeholder="3–50 字元，英數字、底線、連字號、點號"
              value={newUsername}
              maxLength={50}
              onChange={e => setNewUsername(e.target.value)}
              required
            />
          </Form.Group>
          <Form.Group className="mb-3">
            <Form.Label>密碼</Form.Label>
            <Form.Control
              type="password"
              placeholder="至少 8 個字元"
              value={newPassword}
              onChange={e => setNewPassword(e.target.value)}
              required
              minLength={8}
            />
          </Form.Group>
          <Form.Group className="mb-3">
            <Form.Label>確認密碼</Form.Label>
            <Form.Control
              type="password"
              placeholder="再次輸入密碼"
              value={newConfirm}
              onChange={e => setNewConfirm(e.target.value)}
              required
            />
          </Form.Group>
          <Form.Group className="mb-1">
            <Form.Label>角色</Form.Label>
            <Form.Select value={newRole} onChange={e => setNewRole(e.target.value)}>
              {roleOptions.length > 0
                ? roleOptions.map(r => (
                    <option key={r.code} value={r.code}>{r.name}</option>
                  ))
                : (
                    <>
                      <option value="inspector">檢驗員</option>
                      <option value="admin">系統管理員</option>
                    </>
                  )
              }
            </Form.Select>
          </Form.Group>
        </Form>
      </Modal.Body>
      <Modal.Footer>
        <Button variant="secondary" onClick={handleHide}>取消</Button>
        <Button
          variant="primary"
          type="submit"
          form="createUserForm"
          disabled={createMutation.isPending}
        >
          {createMutation.isPending
            ? <><Spinner animation="border" size="sm" className="me-2" />建立中...</>
            : <><i className="fa-solid fa-check me-2"></i>建立使用者</>
          }
        </Button>
      </Modal.Footer>
    </Modal>
  );
};

export default CreateUserModal;
