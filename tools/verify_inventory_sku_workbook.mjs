import fs from "node:fs/promises";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const workbookPath = "/Users/liyao/Documents/Doors and Windows Shopping wesite/output/inventory/2026年5月点数版本_SKU整理.xlsx";
const previewPath = "/Users/liyao/Documents/Doors and Windows Shopping wesite/output/inventory/sku_summary_preview.png";

const input = await FileBlob.load(workbookPath);
const workbook = await SpreadsheetFile.importXlsx(input);

const summary = await workbook.inspect({
  kind: "table",
  sheetId: "SKU汇总",
  range: "A1:O12",
  include: "values,formulas",
  tableMaxRows: 12,
  tableMaxCols: 15,
  maxChars: 6000,
});
console.log(summary.ndjson);

const errors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 100 },
  summary: "formula error scan",
  maxChars: 2000,
});
console.log(errors.ndjson);

const preview = await workbook.render({
  sheetName: "SKU汇总",
  range: "A1:O20",
  scale: 1,
  format: "png",
});
const bytes = new Uint8Array(await preview.arrayBuffer());
await fs.writeFile(previewPath, bytes);
console.log(previewPath);
