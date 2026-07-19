const COLORS = [
  '#e6194b', '#3cb44b', '#4363d8', '#f58231', '#911eb4',
  '#42d4f4', '#f032e6', '#bfef45', '#fabed4', '#469990',
  '#dcbeff', '#9a6324',
];

export const EXCLUDED_COLOR = '#adb5bd';

export const channelLineColor = (index: number, excluded: boolean): string =>
  excluded ? EXCLUDED_COLOR : COLORS[index % COLORS.length];
