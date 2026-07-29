export class CalibrationMatrixPasteError extends Error {
  readonly rows: number;
  readonly columns: number;

  constructor(rows: number, columns: number, irregular = false) {
    super(irregular
      ? '貼上資料每列欄數不一致'
      : `貼上資料為 ${rows} 列 ${columns} 欄`);
    this.name = 'CalibrationMatrixPasteError';
    this.rows = rows;
    this.columns = columns;
  }
}

export const parseCalibrationMatrixPaste = (
  text: string,
  expectedRows: number,
  expectedColumns: number,
): string[][] => {
  const matrix = text
    .replace(/\r\n/g, '\n')
    .split('\n')
    .filter((row, index, rows) => !(index === rows.length - 1 && row === ''))
    .map((row) => row.split('\t').map((cell) => cell.trim()));
  const columns = matrix[0]?.length ?? 0;
  if (matrix.some((row) => row.length !== columns)) {
    throw new CalibrationMatrixPasteError(matrix.length, columns, true);
  }
  if (matrix.length !== expectedRows || columns !== expectedColumns) {
    throw new CalibrationMatrixPasteError(matrix.length, columns);
  }
  return matrix;
};
