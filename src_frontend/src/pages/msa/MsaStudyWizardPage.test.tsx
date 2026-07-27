import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import MsaStudyWizardPage from './MsaStudyWizardPage';

const equipmentMock = vi.hoisted(() => vi.fn());
const criteriaMock = vi.hoisted(() => vi.fn());
const createStudyMock = vi.hoisted(() => vi.fn());
const createPlanMock = vi.hoisted(() => vi.fn());
const freezeMock = vi.hoisted(() => vi.fn());
const navigateMock = vi.hoisted(() => vi.fn());

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>(
    'react-router-dom',
  );
  return { ...actual, useNavigate: () => navigateMock };
});
vi.mock('../../hooks/useMsaEquipment', () => ({
  useMsaEquipment: () => equipmentMock(),
  msaKeys: { all: ['msa'] },
}));
vi.mock('../../hooks/useMsaCriteria', () => ({
  useMsaCriteria: () => criteriaMock(),
}));
vi.mock('../../hooks/useMsaStudies', () => ({
  useCreateMsaStudy: () => ({
    mutateAsync: createStudyMock, isPending: false,
  }),
  useCreateMsaPlan: () => ({ mutateAsync: createPlanMock, isPending: false }),
  useFreezeMsaPlan: () => ({ mutateAsync: freezeMock, isPending: false }),
}));

const gauge = (overrides = {}) => ({
  id: 17, equipment_no: 'EQ-017', name: '分厘卡',
  calibration_status: 'valid', calibration_block_reason: null,
  resolution: '0.001', unit: 'mm', ...overrides,
});

const renderPage = () => render(
  <MemoryRouter><MsaStudyWizardPage /></MemoryRouter>,
);

const query = (items: unknown[]) => ({
  data: { items, page: 1, page_size: 100, total: items.length },
  isLoading: false, isError: false, refetch: vi.fn(),
});

beforeEach(() => {
  vi.clearAllMocks();
  equipmentMock.mockReturnValue(query([gauge()]));
  criteriaMock.mockReturnValue(query([{ id: 5, name: '一般計量型' }]));
});

const pickMethod = async (
  user: ReturnType<typeof userEvent.setup>, label: string,
) => {
  await user.click(screen.getByRole('radio', { name: label }));
  await user.click(screen.getByRole('button', { name: '下一步' }));
};

const fillCharacteristic = async (
  user: ReturnType<typeof userEvent.setup>,
) => {
  await user.type(screen.getByLabelText('品質特性'), '外徑');
  await user.type(screen.getByLabelText('單位'), 'mm');
  await user.type(screen.getByLabelText('規格下限'), '9.5');
  await user.type(screen.getByLabelText('規格上限'), '10.5');
  await user.click(screen.getByRole('button', { name: '下一步' }));
};

describe('MSA 研究精靈', () => {
  it('方法卡同時說明可以回答與不能回答什麼', () => {
    renderPage();

    const rangeCard = screen.getByRole('radio', { name: '極差法' })
      .closest('label') as HTMLElement;
    expect(
      within(rangeCard).getByText(/快速篩選用，不分解完整/),
    ).toBeInTheDocument();
    expect(within(rangeCard).getByText('可以回答')).toBeInTheDocument();
    expect(within(rangeCard).getByText('不能回答')).toBeInTheDocument();
  });

  it('未選方法就前進會顯示可點擊的錯誤摘要', async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(screen.getByRole('button', { name: '下一步' }));

    expect(screen.getByRole('alert')).toHaveTextContent('請選擇一種分析方法');
    expect(
      screen.getByRole('button', { name: '請選擇一種分析方法' }),
    ).toBeInTheDocument();
  });

  it('偏倚研究要求可追溯參考值後才能進入下一步', async () => {
    const user = userEvent.setup();
    renderPage();

    await pickMethod(user, '偏倚');
    await fillCharacteristic(user);
    await user.selectOptions(screen.getByLabelText('主量具'), '17');
    await user.click(screen.getByRole('button', { name: '下一步' }));

    expect(screen.getByRole('alert')).toHaveTextContent(
      '偏倚研究需要可追溯參考值或參考標準',
    );
  });

  it('勾選零件已具備參考值後偏倚研究可繼續', async () => {
    const user = userEvent.setup();
    renderPage();

    await pickMethod(user, '偏倚');
    await fillCharacteristic(user);
    await user.selectOptions(screen.getByLabelText('主量具'), '17');
    await user.click(screen.getByLabelText('零件已具備可追溯的參考值'));
    await user.click(screen.getByRole('button', { name: '下一步' }));

    expect(screen.getByLabelText('零件數')).toBeInTheDocument();
  });

  it('產品判定研究沒有規格時必須說明原因', async () => {
    const user = userEvent.setup();
    renderPage();

    await pickMethod(user, '交叉型 ANOVA');
    await user.type(screen.getByLabelText('品質特性'), '外徑');
    await user.type(screen.getByLabelText('單位'), 'mm');
    await user.click(screen.getByRole('button', { name: '下一步' }));

    expect(screen.getByRole('alert')).toHaveTextContent('無公差原因');
  });

  it('規格下限不小於上限時明確擋下', async () => {
    const user = userEvent.setup();
    renderPage();

    await pickMethod(user, '交叉型 ANOVA');
    await user.type(screen.getByLabelText('品質特性'), '外徑');
    await user.type(screen.getByLabelText('單位'), 'mm');
    await user.type(screen.getByLabelText('規格下限'), '10.5');
    await user.type(screen.getByLabelText('規格上限'), '9.5');
    await user.click(screen.getByRole('button', { name: '下一步' }));

    expect(screen.getByRole('alert')).toHaveTextContent(
      '規格下限必須小於規格上限',
    );
  });

  it('計數型研究顯示判定類別設定', async () => {
    const user = userEvent.setup();
    renderPage();

    await pickMethod(user, '計數型');
    await user.type(screen.getByLabelText('品質特性'), '外觀');
    await user.type(screen.getByLabelText('單位'), 'judgement');
    await user.type(
      screen.getByLabelText('無公差原因（沒有規格時必填）'), '計數型無數值公差',
    );
    await user.click(screen.getByRole('button', { name: '下一步' }));
    await user.selectOptions(screen.getByLabelText('主量具'), '17');
    await user.click(screen.getByRole('button', { name: '下一步' }));

    expect(screen.getByLabelText('判定類別（以逗號分隔）')).toBeInTheDocument();
  });

  it('不可重複研究必須確認全部物理假設', async () => {
    const user = userEvent.setup();
    renderPage();

    await pickMethod(user, '不可重複／破壞性');
    await fillCharacteristic(user);
    await user.selectOptions(screen.getByLabelText('主量具'), '17');
    await user.click(screen.getByRole('button', { name: '下一步' }));
    await user.click(screen.getByRole('button', { name: '下一步' }));

    expect(screen.getByRole('alert')).toHaveTextContent('必須確認全部物理假設');
  });

  it('往返步驟不會遺失已填內容', async () => {
    const user = userEvent.setup();
    renderPage();

    await pickMethod(user, '交叉型 ANOVA');
    await user.type(screen.getByLabelText('品質特性'), '外徑');
    await user.click(screen.getByRole('button', { name: '上一步' }));
    await user.click(screen.getByRole('button', { name: '下一步' }));

    expect(screen.getByLabelText('品質特性')).toHaveValue('外徑');
  });

  it('建議設計需求會依方法顯示但仍可調整', async () => {
    const user = userEvent.setup();
    renderPage();

    await pickMethod(user, '平均值－極差法');
    await fillCharacteristic(user);
    await user.selectOptions(screen.getByLabelText('主量具'), '17');
    await user.click(screen.getByRole('button', { name: '下一步' }));

    expect(
      screen.getByText(/建議：建議 10 零件 × 3 評價人 × 2–3 試驗/),
    ).toBeInTheDocument();
    await user.clear(screen.getByLabelText('零件數'));
    await user.type(screen.getByLabelText('零件數'), '5');
    expect(screen.getByLabelText('零件數')).toHaveValue('5');
  });
});

describe('MSA 凍結前檢閱', () => {
  const reachReview = async (user: ReturnType<typeof userEvent.setup>) => {
    await pickMethod(user, '交叉型 ANOVA');
    await fillCharacteristic(user);
    await user.selectOptions(screen.getByLabelText('主量具'), '17');
    await user.click(screen.getByRole('button', { name: '下一步' }));
    await user.click(screen.getByRole('button', { name: '下一步' }));
    await user.selectOptions(screen.getByLabelText('判定準則設定'), '5');
    await user.click(screen.getByRole('button', { name: '下一步' }));
  };

  it('設備逾期時明確阻擋凍結且顯示設備編號', async () => {
    equipmentMock.mockReturnValue(query([gauge({
      calibration_status: 'expired',
      calibration_block_reason: '校驗已逾期',
    })]));
    const user = userEvent.setup();
    renderPage();

    await reachReview(user);

    expect(await screen.findByText('EQ-017 校驗已逾期')).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: '凍結研究計畫' }),
    ).toBeDisabled();
  });

  it('設備合格時可凍結並帶出設計摘要', async () => {
    const user = userEvent.setup();
    renderPage();

    await reachReview(user);

    expect(screen.getByText(/交叉型 ANOVA（MSA4_GRR_ANOVA_1_0）/)).toBeInTheDocument();
    expect(screen.getByText('一般計量型')).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: '凍結研究計畫' }),
    ).toBeEnabled();
  });

  it('凍結會依序建立研究與計畫後再凍結', async () => {
    createStudyMock.mockResolvedValue({ id: 31 });
    createPlanMock.mockResolvedValue({ id: 44, study_id: 31 });
    freezeMock.mockResolvedValue({ id: 44, study_id: 31 });
    const user = userEvent.setup();
    renderPage();

    await reachReview(user);
    await user.click(screen.getByRole('button', { name: '凍結研究計畫' }));
    await user.click(screen.getByRole('button', { name: '凍結研究計畫' }));

    expect(createStudyMock).toHaveBeenCalledTimes(1);
    expect(createPlanMock).toHaveBeenCalledWith(
      expect.objectContaining({
        studyId: 31,
        method_code: 'MSA4_GRR_ANOVA_1_0',
        percent_basis: 'tolerance',
      }),
    );
    expect(freezeMock).toHaveBeenCalledWith({ planId: 44 });
    expect(navigateMock).toHaveBeenCalledWith('/msa/studies/31');
  });

  it('建立失敗時顯示錯誤且不導向', async () => {
    createStudyMock.mockRejectedValue(new Error('研究編號連續碰撞'));
    const user = userEvent.setup();
    renderPage();

    await reachReview(user);
    await user.click(screen.getByRole('button', { name: '凍結研究計畫' }));

    expect(await screen.findByText('研究編號連續碰撞')).toBeInTheDocument();
    expect(navigateMock).not.toHaveBeenCalled();
  });
});
