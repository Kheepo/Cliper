#!/usr/bin/env python3
"""
Comprehensive API enhancements for production environments.
Handles pagination, filtering, sorting, validation, and error responses.
"""

import asyncio
import math
from typing import Dict, Any, Optional, List, Union, Type, Generic, TypeVar, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
from pydantic import BaseModel, Field, validator
from fastapi import Query, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy import and_, or_, desc, asc, func, text
from sqlalchemy.orm import Session, Query as SQLQuery
from sqlalchemy.ext.declarative import DeclarativeMeta
import re
from urllib.parse import urlencode

from .logging_config import get_logger
from .config import get_settings


T = TypeVar('T')


class SortDirection(Enum):
    """Sort direction enumeration."""
    ASC = "asc"
    DESC = "desc"


class FilterOperator(Enum):
    """Filter operator enumeration."""
    EQ = "eq"  # Equal
    NE = "ne"  # Not equal
    GT = "gt"  # Greater than
    GTE = "gte"  # Greater than or equal
    LT = "lt"  # Less than
    LTE = "lte"  # Less than or equal
    LIKE = "like"  # SQL LIKE
    ILIKE = "ilike"  # Case-insensitive LIKE
    IN = "in"  # IN clause
    NOT_IN = "not_in"  # NOT IN clause
    IS_NULL = "is_null"  # IS NULL
    IS_NOT_NULL = "is_not_null"  # IS NOT NULL
    BETWEEN = "between"  # BETWEEN
    CONTAINS = "contains"  # Array contains
    STARTS_WITH = "starts_with"  # String starts with
    ENDS_WITH = "ends_with"  # String ends with


@dataclass
class SortField:
    """Sort field configuration."""
    field: str
    direction: SortDirection = SortDirection.ASC
    nulls_last: bool = True


@dataclass
class FilterField:
    """Filter field configuration."""
    field: str
    operator: FilterOperator
    value: Any
    case_sensitive: bool = True


@dataclass
class PaginationParams:
    """Pagination parameters."""
    page: int = Field(1, ge=1, description="Page number (1-based)")
    size: int = Field(20, ge=1, le=100, description="Items per page")
    
    @property
    def offset(self) -> int:
        """Calculate offset for database query."""
        return (self.page - 1) * self.size


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated response model."""
    items: List[T]
    total: int
    page: int
    size: int
    pages: int
    has_next: bool
    has_prev: bool
    next_page: Optional[int] = None
    prev_page: Optional[int] = None
    
    class Config:
        arbitrary_types_allowed = True


class ErrorDetail(BaseModel):
    """Error detail model."""
    field: Optional[str] = None
    message: str
    code: Optional[str] = None
    context: Optional[Dict[str, Any]] = None


class APIError(BaseModel):
    """Standardized API error response."""
    error: str
    message: str
    details: Optional[List[ErrorDetail]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    request_id: Optional[str] = None
    path: Optional[str] = None
    method: Optional[str] = None


class ValidationError(BaseModel):
    """Validation error response."""
    error: str = "validation_error"
    message: str = "Request validation failed"
    details: List[ErrorDetail]
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class QueryBuilder:
    """Advanced query builder for database operations."""
    
    def __init__(self, model: Type[DeclarativeMeta]):
        self.model = model
        self.logger = get_logger(__name__)
        
        # Get model column names for validation
        self.valid_fields = set()
        if hasattr(model, '__table__'):
            self.valid_fields = {col.name for col in model.__table__.columns}
        
        # Searchable text fields (can be configured per model)
        self.searchable_fields = self._get_searchable_fields()
        
        # Filterable fields with their types
        self.filterable_fields = self._get_filterable_fields()
    
    def _get_searchable_fields(self) -> List[str]:
        """Get searchable text fields for the model."""
        searchable = []
        if hasattr(self.model, '__table__'):
            for col in self.model.__table__.columns:
                if str(col.type).lower() in ['text', 'varchar', 'string']:
                    searchable.append(col.name)
        return searchable
    
    def _get_filterable_fields(self) -> Dict[str, str]:
        """Get filterable fields with their types."""
        filterable = {}
        if hasattr(self.model, '__table__'):
            for col in self.model.__table__.columns:
                filterable[col.name] = str(col.type).lower()
        return filterable
    
    def build_query(self, session: Session, 
                   filters: List[FilterField] = None,
                   sorts: List[SortField] = None,
                   search: str = None,
                   pagination: PaginationParams = None) -> SQLQuery:
        """Build SQLAlchemy query with filters, sorting, and search."""
        query = session.query(self.model)
        
        # Apply search
        if search and self.searchable_fields:
            search_conditions = []
            for field in self.searchable_fields:
                if hasattr(self.model, field):
                    column = getattr(self.model, field)
                    search_conditions.append(column.ilike(f"%{search}%"))
            
            if search_conditions:
                query = query.filter(or_(*search_conditions))
        
        # Apply filters
        if filters:
            for filter_field in filters:
                query = self._apply_filter(query, filter_field)
        
        # Apply sorting
        if sorts:
            for sort_field in sorts:
                query = self._apply_sort(query, sort_field)
        else:
            # Default sorting by ID if available
            if hasattr(self.model, 'id'):
                query = query.order_by(desc(self.model.id))
        
        return query
    
    def _apply_filter(self, query: SQLQuery, filter_field: FilterField) -> SQLQuery:
        """Apply a single filter to the query."""
        if filter_field.field not in self.valid_fields:
            raise ValueError(f"Invalid filter field: {filter_field.field}")
        
        column = getattr(self.model, filter_field.field)
        operator = filter_field.operator
        value = filter_field.value
        
        try:
            if operator == FilterOperator.EQ:
                return query.filter(column == value)
            elif operator == FilterOperator.NE:
                return query.filter(column != value)
            elif operator == FilterOperator.GT:
                return query.filter(column > value)
            elif operator == FilterOperator.GTE:
                return query.filter(column >= value)
            elif operator == FilterOperator.LT:
                return query.filter(column < value)
            elif operator == FilterOperator.LTE:
                return query.filter(column <= value)
            elif operator == FilterOperator.LIKE:
                if filter_field.case_sensitive:
                    return query.filter(column.like(f"%{value}%"))
                else:
                    return query.filter(column.ilike(f"%{value}%"))
            elif operator == FilterOperator.ILIKE:
                return query.filter(column.ilike(f"%{value}%"))
            elif operator == FilterOperator.IN:
                if isinstance(value, (list, tuple)):
                    return query.filter(column.in_(value))
                else:
                    return query.filter(column.in_([value]))
            elif operator == FilterOperator.NOT_IN:
                if isinstance(value, (list, tuple)):
                    return query.filter(~column.in_(value))
                else:
                    return query.filter(~column.in_([value]))
            elif operator == FilterOperator.IS_NULL:
                return query.filter(column.is_(None))
            elif operator == FilterOperator.IS_NOT_NULL:
                return query.filter(column.isnot(None))
            elif operator == FilterOperator.BETWEEN:
                if isinstance(value, (list, tuple)) and len(value) == 2:
                    return query.filter(column.between(value[0], value[1]))
                else:
                    raise ValueError("BETWEEN operator requires a list/tuple of 2 values")
            elif operator == FilterOperator.STARTS_WITH:
                if filter_field.case_sensitive:
                    return query.filter(column.like(f"{value}%"))
                else:
                    return query.filter(column.ilike(f"{value}%"))
            elif operator == FilterOperator.ENDS_WITH:
                if filter_field.case_sensitive:
                    return query.filter(column.like(f"%{value}"))
                else:
                    return query.filter(column.ilike(f"%{value}"))
            else:
                raise ValueError(f"Unsupported filter operator: {operator}")
                
        except Exception as e:
            self.logger.error(f"Error applying filter {filter_field.field} {operator.value}: {e}")
            raise ValueError(f"Invalid filter configuration: {e}")
    
    def _apply_sort(self, query: SQLQuery, sort_field: SortField) -> SQLQuery:
        """Apply sorting to the query."""
        if sort_field.field not in self.valid_fields:
            raise ValueError(f"Invalid sort field: {sort_field.field}")
        
        column = getattr(self.model, sort_field.field)
        
        if sort_field.direction == SortDirection.DESC:
            order_expr = desc(column)
        else:
            order_expr = asc(column)
        
        # Handle NULL values
        if sort_field.nulls_last:
            order_expr = order_expr.nullslast()
        else:
            order_expr = order_expr.nullsfirst()
        
        return query.order_by(order_expr)


class PaginationHelper:
    """Helper for pagination operations."""
    
    @staticmethod
    def paginate(query: SQLQuery, pagination: PaginationParams) -> PaginatedResponse:
        """Paginate a SQLAlchemy query."""
        # Get total count
        total = query.count()
        
        # Calculate pagination info
        pages = math.ceil(total / pagination.size) if total > 0 else 0
        has_next = pagination.page < pages
        has_prev = pagination.page > 1
        
        # Get items for current page
        items = query.offset(pagination.offset).limit(pagination.size).all()
        
        return PaginatedResponse(
            items=items,
            total=total,
            page=pagination.page,
            size=pagination.size,
            pages=pages,
            has_next=has_next,
            has_prev=has_prev,
            next_page=pagination.page + 1 if has_next else None,
            prev_page=pagination.page - 1 if has_prev else None
        )
    
    @staticmethod
    def create_pagination_links(request: Request, pagination: PaginatedResponse) -> Dict[str, str]:
        """Create pagination links for API responses."""
        base_url = str(request.url).split('?')[0]
        query_params = dict(request.query_params)
        
        links = {}
        
        # Self link
        query_params['page'] = pagination.page
        query_params['size'] = pagination.size
        links['self'] = f"{base_url}?{urlencode(query_params)}"
        
        # First page
        query_params['page'] = 1
        links['first'] = f"{base_url}?{urlencode(query_params)}"
        
        # Last page
        query_params['page'] = pagination.pages
        links['last'] = f"{base_url}?{urlencode(query_params)}"
        
        # Previous page
        if pagination.has_prev:
            query_params['page'] = pagination.prev_page
            links['prev'] = f"{base_url}?{urlencode(query_params)}"
        
        # Next page
        if pagination.has_next:
            query_params['page'] = pagination.next_page
            links['next'] = f"{base_url}?{urlencode(query_params)}"
        
        return links


class FilterParser:
    """Parse filter parameters from query strings."""
    
    @staticmethod
    def parse_filters(query_params: Dict[str, Any]) -> List[FilterField]:
        """Parse filter parameters from query string.
        
        Expected format: field__operator=value
        Examples:
        - name__eq=john
        - age__gte=18
        - status__in=active,pending
        - created_at__between=2023-01-01,2023-12-31
        """
        filters = []
        
        for param, value in query_params.items():
            if '__' in param:
                field, operator_str = param.rsplit('__', 1)
                
                try:
                    operator = FilterOperator(operator_str)
                except ValueError:
                    continue  # Skip invalid operators
                
                # Parse value based on operator
                parsed_value = FilterParser._parse_filter_value(value, operator)
                
                filters.append(FilterField(
                    field=field,
                    operator=operator,
                    value=parsed_value
                ))
        
        return filters
    
    @staticmethod
    def _parse_filter_value(value: str, operator: FilterOperator) -> Any:
        """Parse filter value based on operator type."""
        if operator in [FilterOperator.IN, FilterOperator.NOT_IN]:
            # Split comma-separated values
            return [v.strip() for v in value.split(',')]
        elif operator == FilterOperator.BETWEEN:
            # Split into two values
            parts = [v.strip() for v in value.split(',')]
            if len(parts) != 2:
                raise ValueError("BETWEEN operator requires exactly 2 values")
            return parts
        elif operator in [FilterOperator.IS_NULL, FilterOperator.IS_NOT_NULL]:
            # These operators don't need values
            return None
        else:
            # Return as-is for other operators
            return value


class SortParser:
    """Parse sort parameters from query strings."""
    
    @staticmethod
    def parse_sorts(sort_param: str) -> List[SortField]:
        """Parse sort parameters from query string.
        
        Expected format: field1,-field2,field3
        - field1: ascending
        - -field2: descending
        - field3: ascending
        """
        if not sort_param:
            return []
        
        sorts = []
        
        for field_str in sort_param.split(','):
            field_str = field_str.strip()
            if not field_str:
                continue
            
            if field_str.startswith('-'):
                field = field_str[1:]
                direction = SortDirection.DESC
            else:
                field = field_str
                direction = SortDirection.ASC
            
            sorts.append(SortField(field=field, direction=direction))
        
        return sorts


class ErrorHandler:
    """Centralized error handling for APIs."""
    
    def __init__(self):
        self.logger = get_logger(__name__)
    
    def create_error_response(self, 
                            error_type: str,
                            message: str,
                            status_code: int = 400,
                            details: List[ErrorDetail] = None,
                            request: Request = None) -> JSONResponse:
        """Create standardized error response."""
        error_data = APIError(
            error=error_type,
            message=message,
            details=details or [],
            request_id=getattr(request.state, 'request_id', None) if request else None,
            path=str(request.url.path) if request else None,
            method=request.method if request else None
        )
        
        # Log error
        self.logger.error(
            f"API Error: {error_type}",
            error_type=error_type,
            message=message,
            status_code=status_code,
            details=[d.dict() for d in (details or [])],
            path=error_data.path,
            method=error_data.method
        )
        
        return JSONResponse(
            status_code=status_code,
            content=error_data.dict()
        )
    
    def validation_error_response(self, 
                                errors: List[ErrorDetail],
                                request: Request = None) -> JSONResponse:
        """Create validation error response."""
        error_data = ValidationError(details=errors)
        
        self.logger.warning(
            "Validation Error",
            errors=[e.dict() for e in errors],
            path=str(request.url.path) if request else None,
            method=request.method if request else None
        )
        
        return JSONResponse(
            status_code=422,
            content=error_data.dict()
        )


class APIValidator:
    """Advanced API input validation."""
    
    @staticmethod
    def validate_pagination(page: int = Query(1, ge=1, description="Page number"),
                          size: int = Query(20, ge=1, le=100, description="Items per page")) -> PaginationParams:
        """Validate pagination parameters."""
        return PaginationParams(page=page, size=size)
    
    @staticmethod
    def validate_search(search: str = Query(None, max_length=100, description="Search term")) -> Optional[str]:
        """Validate search parameter."""
        if search:
            # Basic sanitization
            search = search.strip()
            if len(search) < 2:
                raise HTTPException(status_code=400, detail="Search term must be at least 2 characters")
            
            # Remove potentially dangerous characters
            search = re.sub(r'[<>"\';]', '', search)
        
        return search
    
    @staticmethod
    def validate_sort(sort: str = Query(None, description="Sort fields (comma-separated, prefix with - for desc)")) -> List[SortField]:
        """Validate sort parameter."""
        if not sort:
            return []
        
        try:
            return SortParser.parse_sorts(sort)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid sort parameter: {e}")
    
    @staticmethod
    def validate_date_range(start_date: Optional[datetime] = Query(None, description="Start date"),
                          end_date: Optional[datetime] = Query(None, description="End date")) -> tuple:
        """Validate date range parameters."""
        if start_date and end_date:
            if start_date > end_date:
                raise HTTPException(status_code=400, detail="Start date must be before end date")
            
            # Limit date range to prevent performance issues
            if (end_date - start_date).days > 365:
                raise HTTPException(status_code=400, detail="Date range cannot exceed 365 days")
        
        return start_date, end_date


# Dependency functions for FastAPI
def get_pagination_params(page: int = Query(1, ge=1, description="Page number"),
                         size: int = Query(20, ge=1, le=100, description="Items per page")) -> PaginationParams:
    """FastAPI dependency for pagination parameters."""
    return PaginationParams(page=page, size=size)


def get_search_param(search: str = Query(None, max_length=100, description="Search term")) -> Optional[str]:
    """FastAPI dependency for search parameter."""
    return APIValidator.validate_search(search)


def get_sort_params(sort: str = Query(None, description="Sort fields")) -> List[SortField]:
    """FastAPI dependency for sort parameters."""
    return APIValidator.validate_sort(sort)


def get_filter_params(request: Request) -> List[FilterField]:
    """FastAPI dependency for filter parameters."""
    try:
        return FilterParser.parse_filters(dict(request.query_params))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid filter parameters: {e}")


# Global instances
_error_handler = None


def get_error_handler() -> ErrorHandler:
    """Get global error handler instance."""
    global _error_handler
    if _error_handler is None:
        _error_handler = ErrorHandler()
    return _error_handler


# Response helpers
def success_response(data: Any, message: str = "Success", status_code: int = 200) -> JSONResponse:
    """Create standardized success response."""
    return JSONResponse(
        status_code=status_code,
        content={
            "success": True,
            "message": message,
            "data": data,
            "timestamp": datetime.utcnow().isoformat()
        }
    )


class FilterProcessor:
    """Advanced filter processing for database queries."""
    
    def __init__(self):
        self.logger = get_logger(__name__)
    
    def apply_filters(self, query, filters: List[FilterField], model_class):
        """Apply filters to a SQLAlchemy query."""
        for filter_field in filters:
            try:
                # Get the model attribute
                if not hasattr(model_class, filter_field.field):
                    self.logger.warning(f"Field {filter_field.field} not found in {model_class.__name__}")
                    continue
                
                attr = getattr(model_class, filter_field.field)
                
                # Apply filter based on operator
                if filter_field.operator == FilterOperator.EQ:
                    query = query.filter(attr == filter_field.value)
                elif filter_field.operator == FilterOperator.NE:
                    query = query.filter(attr != filter_field.value)
                elif filter_field.operator == FilterOperator.GT:
                    query = query.filter(attr > filter_field.value)
                elif filter_field.operator == FilterOperator.GTE:
                    query = query.filter(attr >= filter_field.value)
                elif filter_field.operator == FilterOperator.LT:
                    query = query.filter(attr < filter_field.value)
                elif filter_field.operator == FilterOperator.LTE:
                    query = query.filter(attr <= filter_field.value)
                elif filter_field.operator == FilterOperator.LIKE:
                    query = query.filter(attr.like(f"%{filter_field.value}%"))
                elif filter_field.operator == FilterOperator.ILIKE:
                    query = query.filter(attr.ilike(f"%{filter_field.value}%"))
                elif filter_field.operator == FilterOperator.IN:
                    if isinstance(filter_field.value, (list, tuple)):
                        query = query.filter(attr.in_(filter_field.value))
                    else:
                        # Try to parse as comma-separated values
                        values = str(filter_field.value).split(',')
                        query = query.filter(attr.in_(values))
                elif filter_field.operator == FilterOperator.NOT_IN:
                    if isinstance(filter_field.value, (list, tuple)):
                        query = query.filter(~attr.in_(filter_field.value))
                    else:
                        values = str(filter_field.value).split(',')
                        query = query.filter(~attr.in_(values))
                elif filter_field.operator == FilterOperator.IS_NULL:
                    query = query.filter(attr.is_(None))
                elif filter_field.operator == FilterOperator.IS_NOT_NULL:
                    query = query.filter(attr.isnot(None))
                
            except Exception as e:
                self.logger.error(f"Error applying filter {filter_field.field}: {e}")
                continue
        
        return query
    
    def validate_filters(self, filters: List[FilterField], allowed_fields: List[str]) -> List[FilterField]:
        """Validate and filter allowed fields."""
        valid_filters = []
        
        for filter_field in filters:
            if filter_field.field in allowed_fields:
                valid_filters.append(filter_field)
            else:
                self.logger.warning(f"Filter field {filter_field.field} not allowed")
        
        return valid_filters


class SortProcessor:
    """Advanced sorting processor for database queries."""
    
    @staticmethod
    def apply_sorting(query, sort_fields: List[SortField]) -> Any:
        """Apply sorting to a database query."""
        for sort_field in sort_fields:
            # Implementation would depend on the ORM being used
            pass
    
    @staticmethod
    def validate_sorting(sort_fields: List[SortField]) -> bool:
        """Validate sort fields."""
        return all(sort_field.field and sort_field.direction for sort_field in sort_fields)


class SearchProcessor:
    """Advanced search processor for database queries."""
    
    @staticmethod
    def apply_search(query, search_term: str, search_fields: List[str]) -> Any:
        """Apply search to a database query."""
        if not search_term or not search_fields:
            return query
        # Implementation would depend on the ORM being used
        return query
    
    @staticmethod
    def validate_search(search_term: str, search_fields: List[str]) -> bool:
        """Validate search parameters."""
        return bool(search_term and search_fields)


class CacheManager:
    """Cache management for API responses and data."""
    
    def __init__(self, redis_client=None):
        self.redis_client = redis_client
    
    async def get(self, key: str) -> Any:
        """Get value from cache."""
        if not self.redis_client:
            return None
        # Implementation would depend on the cache backend
        return None
    
    async def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        """Set value in cache with TTL."""
        if not self.redis_client:
            return False
        # Implementation would depend on the cache backend
        return True
    
    async def delete(self, key: str) -> bool:
        """Delete value from cache."""
        if not self.redis_client:
            return False
        # Implementation would depend on the cache backend
        return True


class ResponseFormatter:
    """Format API responses consistently."""
    
    @staticmethod
    def success(data: Any, message: str = "Success", status_code: int = 200) -> Dict[str, Any]:
        """Format successful response."""
        return {
            "success": True,
            "message": message,
            "data": data,
            "status_code": status_code
        }
    
    @staticmethod
    def error(message: str, error_code: str = None, status_code: int = 400) -> Dict[str, Any]:
        """Format error response."""
        response = {
            "success": False,
            "message": message,
            "status_code": status_code
        }
        if error_code:
            response["error_code"] = error_code
        return response
    
    @staticmethod
    def paginated(data: List[Any], pagination: PaginationParams, total: int) -> Dict[str, Any]:
        """Format paginated response."""
        return {
            "success": True,
            "data": data,
            "pagination": {
                "page": pagination.page,
                "per_page": pagination.per_page,
                "total": total,
                "total_pages": (total + pagination.per_page - 1) // pagination.per_page
            }
        }


class MetricsCollector:
    """Collect and manage API metrics and analytics."""
    
    def __init__(self):
        self.metrics = {}
        self.request_counts = {}
        self.response_times = []
        self.error_counts = {}
    
    def record_request(self, endpoint: str, method: str, response_time: float, status_code: int):
        """Record a request metric."""
        key = f"{method}:{endpoint}"
        
        # Count requests
        if key not in self.request_counts:
            self.request_counts[key] = 0
        self.request_counts[key] += 1
        
        # Record response time
        self.response_times.append(response_time)
        
        # Count errors
        if status_code >= 400:
            if key not in self.error_counts:
                self.error_counts[key] = 0
            self.error_counts[key] += 1
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get collected metrics."""
        avg_response_time = sum(self.response_times) / len(self.response_times) if self.response_times else 0
        
        return {
            "total_requests": sum(self.request_counts.values()),
            "average_response_time": avg_response_time,
            "total_errors": sum(self.error_counts.values()),
            "request_counts": self.request_counts,
            "error_counts": self.error_counts
        }
    
    def reset_metrics(self):
        """Reset all collected metrics."""
        self.metrics = {}
        self.request_counts = {}
        self.response_times = []
        self.error_counts = {}


def paginated_response(paginated_data: PaginatedResponse, 
                      request: Request,
                      message: str = "Success") -> JSONResponse:
    """Create standardized paginated response."""
    links = PaginationHelper.create_pagination_links(request, paginated_data)
    
    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "message": message,
            "data": {
                "items": [item.dict() if hasattr(item, 'dict') else item for item in paginated_data.items],
                "pagination": {
                    "total": paginated_data.total,
                    "page": paginated_data.page,
                    "size": paginated_data.size,
                    "pages": paginated_data.pages,
                    "has_next": paginated_data.has_next,
                    "has_prev": paginated_data.has_prev,
                    "next_page": paginated_data.next_page,
                    "prev_page": paginated_data.prev_page
                },
                "links": links
            },
            "timestamp": datetime.utcnow().isoformat()
        }
    )