import { Outlet } from 'react-router';

const AuthLayout = () => {
    return (
        <div className="d-flex align-items-center justify-content-center min-vh-100">
            <Outlet />
        </div>
    );
};

export default AuthLayout;
