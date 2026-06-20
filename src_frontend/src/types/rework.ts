export interface ReworkApplication {
  識別碼: number;
  申請單號: string;
  申請日期: string;
  NCMR_ID: number;
  ncmr_number?: string;
  客訴_ID?: number | null;
  客訴單號?: string;
  申請人員姓名: string;
  部門: string;
  產品資訊: string;
  重工數量: number;
  緊急程度: '普通' | '重要' | '緊急';
  狀態: '申請中' | '已核准' | '執行中' | '已完成' | '已拒絕';
  申請原因?: string;
  預計完成日期?: string;
  審核狀態?: string;
  審核意見?: string;
  廠商?: string;
  材質?: string;
  批號?: string;
}

export interface ReworkStatistics {
  application_stats: {
    total_applications: number;
    in_progress: number;
    completed: number;
    approved: number;
    rejected: number;
    total_rework_quantity: number;
  };
  department_stats: { department: string; count: number }[];
  cost_stats: {
    total_cost: number;
    labor_cost: number;
    material_cost: number;
    equipment_cost: number;
  };
}

export interface ReworkExecution {
  識別碼?: number;
  重工單號: number;
  負責人員姓名: string;
  執行部門: string;
  協同人員?: string;
  開始時間: string;
  預計完成時間?: string;
  實際完成時間?: string;
  使用設備?: string;
  SOP編號?: string;
  完成數量: number;
  不良數量: number;
  重工方式?: string;
  耗材記錄?: string;
  執行狀況?: string;
  異常狀況?: string;
  良率?: string;
}

export interface ReworkInspection {
  識別碼?: number;
  重工單號: number;
  檢驗日期: string;
  檢驗人員姓名: string;
  檢驗項目?: string;
  檢驗標準?: string;
  檢驗結果: string;
  不良數量: number;
  檢驗備註?: string;
}

export interface ReworkCost {
  識別碼?: number;
  重工單號: number;
  記錄日期?: string;
  記錄人員姓名?: string;
  成本類型: '人工' | '材料' | '設備' | '其他';
  成本項目: string;
  單位成本: number;
  數量: number;
  總成本?: number;
  備註?: string;
}

export interface ReworkExecutionDetail {
  id?: number;
  識別碼?: number;
  重工單號: number;
  負責人員姓名: string;
  執行部門: string;
  協同人員?: string;
  開始時間: string;
  預計完成時間?: string;
  實際完成時間?: string;
  使用設備?: string;
  SOP編號?: string;
  完成數量: number;
  不良數量: number;
  重工方式?: string;
  耗材記錄?: string;
  執行狀況?: string;
  異常狀況?: string;
  良率?: string;
}

export interface ReworkInspectionDetail {
  id?: number;
  識別碼?: number;
  重工單號: number;
  檢驗日期: string;
  檢驗人員?: string;
  檢驗人員姓名: string;
  檢驗項目?: string;
  檢驗標準?: string;
  檢驗結果: string;
  不良數量: number;
  檢驗備註?: string;
}

export interface ReworkCostDetail {
  id?: number;
  識別碼?: number;
  重工單號: number;
  記錄日期?: string;
  記錄人員姓名?: string;
  成本類型: string;
  成本幣別?: string;
  成本項目: string;
  單位成本: number;
  數量: number;
  總成本?: number;
  備註?: string;
}
