export interface CAPA {
    id: number;
    no?: string; // 8D單號
    ncmr_id: number;
    ncmr_no?: string;
    create_date: string;
    owner_name: string;
    status: string;
    // 動態 D1-D8 欄位
    [key: string]: unknown;
}

export interface CAPACreateInput {
    ncmr_id: number;
    業主姓名: string;
    判定結果?: string;
    [key: string]: unknown;
}

export interface CAPAUpdateInput extends CAPACreateInput {
    id: number;
}

export interface CAR {
    id: number;
    no: string; // 單號
    ncmr_id: number;
    ncmr_no?: string;
    create_date: string;
    owner_name: string;
    status: string;
    // 動態 D 欄位
    [key: string]: unknown;
}

export interface CARCreateInput {
    ncmr_id: number;
    業主姓名: string;
    [key: string]: unknown;
}

export interface CARUpdateInput extends CARCreateInput {
    id: number;
}

export interface CA_Detail<T> {
    ncmr: {
        發現日期: string;
        廠商: string;
        材質: string;
        產品資訊: string;
        來源: string;
        不良描述: string;
    };
    main: T; // CAPA 或 CAR 資料
}

