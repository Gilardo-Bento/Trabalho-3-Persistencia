from typing import Generic, TypeVar, List
from pydantic import BaseModel, computed_field
from fastapi import Query

T = TypeVar('T') 

class PaginationParams(BaseModel):
    page: int = Query(1, ge=1, description="Number of the page")
    per_page: int = Query(10, ge=1, le=100, description="Number of items per page")

class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T] # List of items in the current page
    total: int # Total number of items across all pages
    page: int # Current page number
    per_page: int # Number of items per page

    @computed_field
    @property
    def total_pages(self) -> int:
        if self.per_page == 0:
            return 0
        return (self.total + self.per_page - 1) // self.per_page