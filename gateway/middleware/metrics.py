"""
Prometheus Metrics Middleware - Auto-collect HTTP metrics
"""
import time
from typing import Callable
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from prometheus_client import Counter, Histogram, Gauge, REGISTRY


# HTTP Metrics - Use global registry
HTTP_REQUESTS_TOTAL = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'path', 'status'],
    registry=REGISTRY
)

HTTP_REQUEST_DURATION = Histogram(
    'http_request_duration_seconds',
    'HTTP request latency in seconds',
    ['method', 'path'],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0],
    registry=REGISTRY
)

HTTP_REQUESTS_IN_PROGRESS = Gauge(
    'http_requests_in_progress',
    'Number of HTTP requests currently being processed',
    ['method'],
    registry=REGISTRY
)

HTTP_RESPONSE_SIZE_BYTES = Histogram(
    'http_response_size_bytes',
    'HTTP response size in bytes',
    ['method', 'path'],
    buckets=[100, 1000, 10000, 100000, 1000000],
    registry=REGISTRY
)


class MetricsMiddleware(BaseHTTPMiddleware):
    """
    Middleware that automatically collects HTTP metrics for all requests.
    
    Collected metrics:
    - Request count (by method, path, status)
    - Request duration (histogram)
    - In-progress requests (gauge)
    - Response size (histogram)
    
    Note: /metrics endpoint is excluded to avoid self-monitoring
    """
    
    # Paths to exclude from metrics collection
    EXCLUDE_PATHS = ['/metrics', '/health', '/docs', '/openapi.json', '/redoc']
    
    async def dispatch(self, request: Request, call_next: Callable):
        """Process request and collect metrics"""
        
        # Skip excluded paths
        path = request.url.path
        if path in self.EXCLUDE_PATHS or path.startswith('/docs') or path.startswith('/openapi'):
            return await call_next(request)
        
        method = request.method
        
        # Increment in-progress gauge
        HTTP_REQUESTS_IN_PROGRESS.labels(method=method).inc()
        
        start_time = time.time()
        
        try:
            # Process request
            response = await call_next(request)
            
            # Record metrics
            status = response.status_code
            duration = time.time() - start_time
            
            HTTP_REQUESTS_TOTAL.labels(
                method=method,
                path=path,
                status=status
            ).inc()
            
            HTTP_REQUEST_DURATION.labels(
                method=method,
                path=path
            ).observe(duration)
            
            # Record response size if available
            if hasattr(response, 'body'):
                body_size = len(response.body) if response.body else 0
                HTTP_RESPONSE_SIZE_BYTES.labels(
                    method=method,
                    path=path
                ).observe(body_size)
            
            return response
            
        except Exception as e:
            # Record error as 500
            duration = time.time() - start_time
            HTTP_REQUESTS_TOTAL.labels(
                method=method,
                path=path,
                status=500
            ).inc()
            
            HTTP_REQUEST_DURATION.labels(
                method=method,
                path=path
            ).observe(duration)
            
            raise
            
        finally:
            # Decrement in-progress gauge
            HTTP_REQUESTS_IN_PROGRESS.labels(method=method).dec()


def get_http_metrics():
    """Return HTTP metrics for external access"""
    return {
        'requests_total': HTTP_REQUESTS_TOTAL,
        'request_duration': HTTP_REQUEST_DURATION,
        'requests_in_progress': HTTP_REQUESTS_IN_PROGRESS,
        'response_size': HTTP_RESPONSE_SIZE_BYTES,
    }