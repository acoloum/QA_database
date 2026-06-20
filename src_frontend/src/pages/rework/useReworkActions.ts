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
}

export const useReworkActions = ({
  applications,
  selectedReworkDetail,
  reloadDetailData,
  loadData,
  setFollowUpModal,
}: UseReworkActionsOptions) => {
  const deleteExecution = async (executionId: number) => {
    try {
      await api.delete(`/rework/execution/${executionId}`);
      toast.success('刪除成功');
      await reloadDetailData();
    } catch (error: unknown) {
      toast.error(getReworkErrorMessage(error, '刪除失敗'));
    }
  };

  const deleteInspection = async (inspectionId: number) => {
    try {
      await api.delete(`/rework/inspection/${inspectionId}`);
      toast.success('刪除成功');
      await reloadDetailData();
    } catch (error: unknown) {
      toast.error(getReworkErrorMessage(error, '刪除失敗'));
    }
  };

  const deleteCost = async (costId: number) => {
    try {
      await api.delete(`/rework/cost/${costId}`);
      toast.success('刪除成功');
      await reloadDetailData();
      await loadData();
    } catch (error: unknown) {
      toast.error(getReworkErrorMessage(error, '刪除失敗'));
    }
  };

  const closeRework = async (reworkId: number) => {
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
  };

  const deleteRework = async (reworkId: number) => {
    try {
      await api.post('/rework/delete', { rework_id: reworkId });
      toast.success('刪除成功');
      await loadData();
    } catch (error: unknown) {
      toast.error(getReworkErrorMessage(error, '刪除失敗'));
    }
  };

  return {
    closeRework,
    deleteCost,
    deleteExecution,
    deleteInspection,
    deleteRework,
  };
};
