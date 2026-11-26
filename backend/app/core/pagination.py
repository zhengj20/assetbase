"""分页组件：统一分页参数与返回结构。"""
from math import ceil
from typing import Generic, TypeVar

from fastapi import Query
from pydantic import BaseModel

T = TypeVar("T")


class PageParams:
    def __init__(
        self,
        page: int = Query(1, ge=1, description="页码"),
        page_size: int = Query(20, ge=1, le=200, description="每页条数"),
    ):
        self.page = page
        self.page_size = page_size

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        return self.page_size


class PageData(BaseModel, Generic[T]):
    total: int
    pages: int
    page: int
    page_size: int
    records: list[T]

    @classmethod
    def build(cls, total: int, params: PageParams, records: list) -> "PageData":
        return cls(
            total=total,
            pages=ceil(total / params.page_size) if total else 0,
            page=params.page,
            page_size=params.page_size,
            records=records,
        )
