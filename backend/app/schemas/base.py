"""Schema 公共基类：入参空串日期统一转 None（前端日期控件空值传 ""）。"""
from pydantic import BaseModel, model_validator

_EMPTY_DATE_KEYS = (
    "buy_date", "warranty_end", "apply_date", "in_date", "out_date",
    "transfer_date", "scrap_date", "plan_start", "plan_end",
)


class InSchema(BaseModel):
    @model_validator(mode="before")
    @classmethod
    def _empty_dates_to_none(cls, data):
        if isinstance(data, dict):
            for k in _EMPTY_DATE_KEYS:
                v = data.get(k)
                if isinstance(v, str) and not v.strip():
                    data[k] = None
        return data
