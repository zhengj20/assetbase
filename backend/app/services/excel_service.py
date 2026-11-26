"""Excel 流式导出（方案第十章）：write_only 模式，10 万行不 OOM。

rows 支持普通可迭代对象或**异步生成器**（分批查库流式导出）。
安全：字符串以 = + - @ 开头的值前置单引号，防止 Excel 公式注入。
"""
import io
from typing import Any, AsyncIterable, AsyncIterator, Iterable

from openpyxl import Workbook
from openpyxl.cell import WriteOnlyCell
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

HEADER_FILL = PatternFill("solid", fgColor="1F4E79")
HEADER_FONT = Font(bold=True, color="FFFFFF", size=11)
THIN = Side(style="thin", color="C0C0C0")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
CENTER = Alignment(horizontal="center", vertical="center")


def _safe(v: Any) -> Any:
    """Excel 公式注入防护：= + - @ 开头的字符串前置单引号。"""
    if isinstance(v, str) and v and v[0] in "=+-@":
        return "'" + v
    return v


async def _rows_iter(rows: Iterable[Any] | AsyncIterable[Any]) -> AsyncIterator[list[Any]]:
    if hasattr(rows, "__aiter__"):
        async for r in rows:
            yield r
    else:
        for r in rows:
            yield r


async def build_excel(
    headers: list[str],
    rows: Iterable[list[Any]] | AsyncIterable[list[Any]],
    sheet_name: str = "Sheet1",
    col_widths: list[int] | None = None,
    title_rows: list[list[Any]] | None = None,
) -> io.BytesIO:
    """构建 Excel 字节流。

    title_rows: 表头上方的信息区（如报表标题、统计口径、任务信息）。
    """
    wb = Workbook(write_only=True)
    ws = wb.create_sheet(sheet_name)

    if col_widths:
        for i, w in enumerate(col_widths, start=1):
            ws.column_dimensions[get_column_letter(i)].width = w

    for row in title_rows or []:
        ws.append(row)

    header_cells = []
    for h in headers:
        c = WriteOnlyCell(ws, value=_safe(h))
        c.fill = HEADER_FILL
        c.font = HEADER_FONT
        c.border = BORDER
        c.alignment = CENTER
        header_cells.append(c)
    ws.append(header_cells)

    async for row in _rows_iter(rows):
        cells = []
        for v in row:
            c = WriteOnlyCell(ws, value=_safe(v))
            c.border = BORDER
            cells.append(c)
        ws.append(cells)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf
