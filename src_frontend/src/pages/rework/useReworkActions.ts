import { useCallback } from 'react';
import toast from 'react-hot-toast';

import api from '../../services/api';
import type { ReworkApplication } from '../../types';
import { getReworkErrorMessage, resolveReworkFollowUp, type ReworkFollowUpState } from './reworkPageUtils';

interface UseReworkActionsOptions {
  applications: ReworkApplication[];
  selectedReworkDetail: ReworkApplication | null;
  reloadDetailData: () => Promise<void>;
  loadData: () => Promise<void>;
  setFollowUpModal: (state: ReworkFollowUpState | null) => void;
  hasPermission: (permission: string) => boolean;
}

export const useReworkActions = ({
  applications,
  selectedReworkDetail,
  reloadDetailData,
  loadData,
  setFollowUpModal,
  hasPermission,
}: UseReworkActionsOptions) => {
  // 各 action 用 useCallback 穩定引用：ReworkPage 傳給 memo 化表格/彈窗的 callback 才不會每次重繪都重建
  const deleteExecution = useCallback(async (executionId: number) => {
    if (!hasPermission('rework.delete')) {
      toast.error('需要 rework.delete 權限');
      return;
    }
    try {
      await api.delete(`/rework/execution/${executionId}`);
      toast.success('刪除成功');
      await reloadDetailData();
    } catch (error: unknown) {
      toast.error(getReworkErrorMessage(error, '刪除失敗'));
    }
  }, [hasPermission, reloadDetailData]);

  const deleteInspection = useCallback(async (inspectionId: number) => {
    if (!hasPermission('rework.delete')) {
      toast.error('需要 rework.delete 權限');
      return;
    }
    try {
      await api.delete(`/rework/inspection/${inspectionId}`);
      toast.success('刪除成功');
      await reloadDetailData();
    } catch (error: unknown) {
      toast.error(getReworkErrorMessage(error, '刪除失敗'));
    }
  }, [hasPermission, reloadDetailData]);

  const deleteCost = useCallback(async (costId: number) => {
    if (!hasPermission('rework.delete')) {
      toast.error('需要 rework.delete 權限');
      return;
    }
    try {
      await api.delete(`/rework/cost/${costId}`);
      toast.success('刪除成功');
      await reloadDetailData();
      await loadData();
    } catch (error: unknown) {
      toast.error(getReworkErrorMessage(error, '刪除失敗'));
    }
  }, [hasPermission, reloadDetailData, loadData]);

  const closeRework = useCallback(async (reworkId: number) => {
    if (!hasPermission('rework.approve')) {
      toast.error('需要 rework.approve 權限');
      return;
    }
    try {
      await api.post('/rework/close', { rework_id: reworkId });
      toast.success('結案成功');

      const rework = applications.find(a => a.識別碼 === reworkId)
        ?? (selectedReworkDetail?.識別碼 === reworkId ? selectedReworkDetail : null);
      const ncmrId = rework?.NCMR_ID;
      if (ncmrId) {
        try {
          const ncmrRes = await api.get(`/ncmr/detail/${ncmrId}`);
          const followUp = resolveReworkFollowUp(rework, ncmrRes.data);
          if (followUp) setFollowUpModal(followUp);
        } catch {
          // 取不到 NCMR 詳細資料也不影響結案流程
        }
      }

      await reloadDetailData();
    } catch (error: unknown) {
      toast.error(getReworkErrorMessage(error, '結案失敗'));
    }
  }, [hasPermission, applications, selectedReworkDetail, setFollowUpModal, reloadDetailData]);

  const deleteRework = useCallback(async (reworkId: number) => {
    if (!hasPermission('rework.delete')) {
      toast.error('需要 rework.delete 權限');
      return;
    }
    try {
      await api.post('/rework/delete', { rework_id: reworkId });
      toast.success('刪除成功');
      await loadData();
    } catch (error: unknown) {
      toast.error(getReworkErrorMessage(error, '刪除失敗'));
    }
  }, [hasPermission, loadData]);

  return {
    closeRework,
    deleteCost,
    deleteExecution,
    deleteInspection,
    deleteRework,
  };
};
