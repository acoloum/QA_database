import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button, Card, Form, Alert, Container } from 'react-bootstrap';
import api from '../../services/api';

const UserManagementPage = () => {
    const navigate = useNavigate();
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [confirmPassword, setConfirmPassword] = useState('');
    const [message, setMessage] = useState<{ type: 'success' | 'danger', text: string } | null>(null);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setMessage(null);

        if (password !== confirmPassword) {
            setMessage({ type: 'danger', text: '密碼不一致' });
            return;
        }

        try {
            const res = await api.post('/users', { username, password });
            if (res.status === 200 || res.status === 201) {
                setMessage({ type: 'success', text: '使用者建立成功！' });
                setUsername('');
                setPassword('');
                setConfirmPassword('');
            }
        } catch (error: any) {
            let errorMsg = error.response?.data?.error || '建立失敗';
            if (errorMsg.includes('UNIQUE') || errorMsg.includes('已存在')) {
                errorMsg = '使用者名稱已存在';
            }
            setMessage({ type: 'danger', text: errorMsg });
        }
    };

    return (
        <Container className="d-flex justify-content-center align-items-center" style={{ minHeight: '80vh' }}>
            <Card className="shadow-lg border-0" style={{ width: '100%', maxWidth: '500px', borderRadius: '1rem' }}>
                <Card.Header className="bg-primary text-white d-flex justify-content-between align-items-center py-4" style={{ borderTopLeftRadius: '1rem', borderTopRightRadius: '1rem', background: 'linear-gradient(135deg, #6a11cb 0%, #2575fc 100%)' }}>
                    <h3 className="mb-0"><i className="bi bi-person-plus-fill me-2"></i>建立新使用者</h3>
                    <Button variant="outline-light" size="sm" onClick={() => navigate('/')}>
                        <i className="bi bi-arrow-left"></i> 回首頁
                    </Button>
                </Card.Header>
                <Card.Body className="p-5">
                    {message && <Alert variant={message.type}>{message.text}</Alert>}
                    <Form onSubmit={handleSubmit}>
                        <Form.Group className="mb-3">
                            <Form.Label><i className="bi bi-person me-2"></i>使用者名稱</Form.Label>
                            <Form.Control
                                type="text"
                                placeholder="請輸入使用者名稱"
                                value={username}
                                onChange={e => setUsername(e.target.value)}
                                required
                            />
                        </Form.Group>
                        <Form.Group className="mb-3">
                            <Form.Label><i className="bi bi-lock me-2"></i>密碼</Form.Label>
                            <Form.Control
                                type="password"
                                placeholder="請輸入密碼"
                                value={password}
                                onChange={e => setPassword(e.target.value)}
                                required
                            />
                        </Form.Group>
                        <Form.Group className="mb-4">
                            <Form.Label><i className="bi bi-lock-fill me-2"></i>確認密碼</Form.Label>
                            <Form.Control
                                type="password"
                                placeholder="請確認密碼"
                                value={confirmPassword}
                                onChange={e => setConfirmPassword(e.target.value)}
                                required
                            />
                        </Form.Group>
                        <div className="d-grid">
                            <Button variant="primary" type="submit" size="lg" style={{ background: 'linear-gradient(135deg, #6a11cb 0%, #2575fc 100%)', border: 'none' }}>
                                建立使用者
                            </Button>
                        </div>
                    </Form>
                </Card.Body>
            </Card>
        </Container>
    );
};

export default UserManagementPage;
