import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';

import api from '../services/api';
import type { UserRecord } from '../types';

export const adminKeys = {
  users: ['userList'] as const,
  roles: ['roles'] as const,
};

export interface CreateUserInput {
  username: string;
  password: string;
  role: string;
}

export interface UpdateUserRoleInput {
  id: number;
  role: string;
}

export interface UpdateUserActiveInput {
  id: number;
  is_active: boolean;
}

export interface UpdateRolePermissionsInput {
  code: string;
  permissions: Record<string, boolean>;
}

export interface ResetUserPasswordInput {
  id: number;
  password: string;
}

export const getAdminErrorMessage = (err: unknown): string => {
  if (err && typeof err === 'object' && 'response' in err) {
    const axiosErr = err as { response?: { data?: { error?: string; message?: string } } };
    return axiosErr.response?.data?.error ?? axiosErr.response?.data?.message ?? '操作失敗，請稍後再試';
  }
  return '操作失敗，請稍後再試';
};

export const useAdminUsers = () =>
  useQuery({
    queryKey: adminKeys.users,
    queryFn: async (): Promise<UserRecord[]> => {
      const res = await api.get<UserRecord[]>('/users');
      return res.data;
    },
  });

export const useCreateAdminUser = (options: { onSuccess?: () => void; onError?: (message: string) => void } = {}) => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: CreateUserInput) => {
      const res = await api.post('/users', data);
      return res.data;
    },
    onSuccess: () => {
      toast.success('使用者建立成功');
      queryClient.invalidateQueries({ queryKey: adminKeys.users });
      options.onSuccess?.();
    },
    onError: err => options.onError?.(getAdminErrorMessage(err)),
  });
};

export const useUpdateAdminUserRole = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, role }: UpdateUserRoleInput) => {
      const res = await api.put(`/users/${id}/role`, { role });
      return res.data;
    },
    onSuccess: () => {
      toast.success('角色已更新');
      queryClient.invalidateQueries({ queryKey: adminKeys.users });
    },
    onError: err => {
      toast.error(getAdminErrorMessage(err));
      queryClient.invalidateQueries({ queryKey: adminKeys.users });
    },
  });
};

export const useUpdateAdminUserActive = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, is_active }: UpdateUserActiveInput) => {
      const res = await api.put(`/users/${id}/active`, { is_active });
      return res.data;
    },
    onSuccess: (_data, variables) => {
      toast.success(variables.is_active ? '帳號已啟用' : '帳號已停用');
      queryClient.invalidateQueries({ queryKey: adminKeys.users });
    },
    onError: err => toast.error(getAdminErrorMessage(err)),
  });
};

export const useResetAdminUserPassword = (
  options: { onSuccess?: () => void } = {},
) => {
  return useMutation({
    mutationFn: async ({ id, password }: ResetUserPasswordInput) => {
      const res = await api.put(`/users/${id}/password`, { password });
      return res.data;
    },
    onSuccess: () => {
      toast.success('密碼已重設，舊登入憑證已撤銷');
      options.onSuccess?.();
    },
    onError: err => toast.error(getAdminErrorMessage(err)),
  });
};

export const useUpdateRolePermissions = (options: { roleName?: string; onSuccess?: () => void } = {}) => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ code, permissions }: UpdateRolePermissionsInput) => {
      const res = await api.patch(`/roles/${code}`, { permissions });
      return res.data;
    },
    onSuccess: () => {
      toast.success(`「${options.roleName ?? '角色'}」權限已更新`);
      queryClient.invalidateQueries({ queryKey: adminKeys.roles });
      options.onSuccess?.();
    },
    onError: err => toast.error(getAdminErrorMessage(err)),
  });
};
