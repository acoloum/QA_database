import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Button, Card, Form, Table, Badge, Modal, Alert, Spinner } from 'react-bootstrap';
import toast from 'react-hot-toast';
import api from '../../services/api';
import { useAuth } from '../../context/useAuth';
import type { UserRecord } from '../../types';

// ── API 函式 ──────────────────────────────────────────────
const fetchUsers = async (): Promise<UserRecord[]> => {
    const res = await api.get<UserRecord[]>('/users');
    return res.data;
};

const createUser = async (data: { username: string; password: string; role: string }) => {
    const res = await api.post('/users', data);
    return res.data;
};

const updateRole = async ({ id, role }: { id: number; role: string }) => {
    const res = await api.put(`/users/${id}/role`, { role });
    return res.data;
};

const updateActive = async ({ id, is_active }: { id: number; is_active: boolean }) => {
    const res = await api.put(`/users/${id}/active`, { is_active });
    return res.data;
};

// ── 工具函式 ──────────────────────────────────────────────
const formatCreatedAt = (iso: string | null): string => {
    if (!iso) return '—';
    const d = new Date(iso);
    return d.toLocaleDateString('zh-TW', { year: 'numeric', month: '2-digit', day: '2-digit' });
};

/** 從後端錯誤回應取得訊息 */
const getErrorMessage = (err: unknown): string => {
    if (err && typeof err === 'object' && 'response' in err) {
        const axiosErr = err as { response?: { data?: { error?: string } } };
        return axiosErr.response?.data?.error ?? '操作失敗，請稍後再試';
    }
    return '操作失敗，請稍後再試';
};

// ── 元件 ─────────────────────────────────────────────────
const UserManagementPage = () => {
    const queryClient = useQueryClient();
    const { user: currentUser } = useAuth();
    const currentUserId = currentUser ? Number(currentUser.user_id) : null;

    // 使用者列表
    const { data: users = [], isLoading, isError } = useQuery({
        queryKey: ['userList'],
        queryFn: fetchUsers,
    });

    // 修改角色（加入確認與錯誤處理）
    const roleMutation = useMutation({
        mutationFn: updateRole,
        onSuccess: () => {
            toast.success('角色已更新');
            queryClient.invalidateQueries({ queryKey: ['userList'] });
        },
        onError: (err) => {
            toast.error(getErrorMessage(err));
            // 重新載入以還原畫面上的選單狀態
            queryClient.invalidateQueries({ queryKey: ['userList'] });
        },
    });

    // 啟用／停用（加入錯誤處理）
    const activeMutation = useMutation({
        mutationFn: updateActive,
        onSuccess: (_data, variables) => {
            toast.success(variables.is_active ? '帳號已啟用' : '帳號已停用');
            queryClient.invalidateQueries({ queryKey: ['userList'] });
        },
        onError: (err) => {
            toast.error(getErrorMessage(err));
        },
    });

    // 角色變更確認（升級為 admin 需確認）
    const handleRoleChange = (u: UserRecord, newRole: string) => {
        if (newRole === 'admin' && u.role !== 'admin') {
            if (!window.confirm(`確定要將「${u.username}」升級為管理員？`)) return;
        }
        roleMutation.mutate({ id: u.id, role: newRole });
    };

    // 新增使用者 Modal
    const [showModal, setShowModal] = useState(false);
    const [newUsername, setNewUsername] = useState('');
    const [newPassword, setNewPassword] = useState('');
    const [newConfirm, setNewConfirm] = useState('');
    const [newRole, setNewRole] = useState<'user' | 'admin'>('user');
    const [formError, setFormError] = useState('');

    const createMutation = useMutation({
        mutationFn: createUser,
        onSuccess: () => {
            toast.success('使用者建立成功');
            queryClient.invalidateQueries({ queryKey: ['userList'] });
            setShowModal(false);
            resetForm();
        },
        onError: (err) => {
            setFormError(getErrorMessage(err));
        },
    });

    const resetForm = () => {
        setNewUsername('');
        setNewPassword('');
        setNewConfirm('');
        setNewRole('user');
        setFormError('');
    };

    const handleCreateSubmit = (e: React.FormEvent) => {
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

    // ── 渲染 ────────────────────────────────────────────
    return (
        <div className="container-fluid py-4">
            <div className="d-flex justify-content-between align-items-center mb-4">
                <h4 className="mb-0">
                    <i className="fa-solid fa-users-gear me-2 text-primary"></i>使用者管理
                </h4>
                <Button variant="primary" onClick={() => { resetForm(); setShowModal(true); }}>
                    <i className="fa-solid fa-user-plus me-2"></i>新增使用者
                </Button>
            </div>

            <Card className="shadow-sm border-0">
                <Card.Body className="p-0">
                    {isLoading && (
                        <div className="text-center py-5">
                            <Spinner animation="border" variant="primary" />
                        </div>
                    )}
                    {isError && (
                        <Alert variant="danger" className="m-3">載入使用者列表失敗，請重新整理頁面</Alert>
                    )}
                    {!isLoading && !isError && (
                        <Table hover responsive className="mb-0">
                            <thead className="table-light">
                                <tr>
                                    <th className="ps-4">#</th>
                                    <th>使用者名稱</th>
                                    <th>角色</th>
                                    <th>帳號狀態</th>
                                    <th>建立日期</th>
                                    <th className="text-end pe-4">操作</th>
                                </tr>
                            </thead>
                            <tbody>
                                {users.map(u => {
                                    const isSelf = u.id === currentUserId;
                                    return (
                                        <tr key={u.id}>
                                            <td className="ps-4 text-muted">{u.id}</td>
                                            <td>
                                                <i className="fa-solid fa-user me-2 text-secondary"></i>
                                                {u.username}
                                                {isSelf && (
                                                    <Badge bg="info" className="ms-2 fw-normal">我</Badge>
                                                )}
                                            </td>
                                            <td>
                                                <Form.Select
                                                    size="sm"
                                                    style={{ width: '110px' }}
                                                    value={u.role}
                                                    disabled={isSelf || roleMutation.isPending}
                                                    title={isSelf ? '無法修改自己的角色' : undefined}
                                                    onChange={e => handleRoleChange(u, e.target.value)}
                                                >
                                                    <option value="user">一般使用者</option>
                                                    <option value="admin">管理員</option>
                                                </Form.Select>
                                            </td>
                                            <td>
                                                <Badge bg={u.is_active ? 'success' : 'secondary'}>
                                                    {u.is_active ? '啟用中' : '已停用'}
                                                </Badge>
                                            </td>
                                            <td className="text-muted small">
                                                {formatCreatedAt(u.created_at)}
                                            </td>
                                            <td className="text-end pe-4">
                                                <Button
                                                    size="sm"
                                                    variant={u.is_active ? 'outline-danger' : 'outline-success'}
                                                    disabled={isSelf || activeMutation.isPending}
                                                    title={isSelf ? '無法停用自己的帳號' : undefined}
                                                    onClick={() => activeMutation.mutate({ id: u.id, is_active: !u.is_active })}
                                                >
                                                    {u.is_active ? (
                                                        <><i className="fa-solid fa-ban me-1"></i>停用</>
                                                    ) : (
                                                        <><i className="fa-solid fa-check me-1"></i>啟用</>
                                                    )}
                                                </Button>
                                            </td>
                                        </tr>
                                    );
                                })}
                                {users.length === 0 && (
                                    <tr>
                                        <td colSpan={6} className="text-center text-muted py-4">尚無使用者資料</td>
                                    </tr>
                                )}
                            </tbody>
                        </Table>
                    )}
                </Card.Body>
            </Card>

            {/* 新增使用者 Modal */}
            <Modal show={showModal} onHide={() => setShowModal(false)} centered>
                <Modal.Header closeButton>
                    <Modal.Title>
                        <i className="fa-solid fa-user-plus me-2"></i>新增使用者
                    </Modal.Title>
                </Modal.Header>
                <Modal.Body>
                    {formError && <Alert variant="danger">{formError}</Alert>}
                    <Form onSubmit={handleCreateSubmit} id="createUserForm">
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
                            <Form.Select
                                value={newRole}
                                onChange={e => setNewRole(e.target.value as 'user' | 'admin')}
                            >
                                <option value="user">一般使用者</option>
                                <option value="admin">管理員</option>
                            </Form.Select>
                        </Form.Group>
                    </Form>
                </Modal.Body>
                <Modal.Footer>
                    <Button variant="secondary" onClick={() => setShowModal(false)}>取消</Button>
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
        </div>
    );
};

export default UserManagementPage;
