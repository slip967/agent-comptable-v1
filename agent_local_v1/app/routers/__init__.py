from .analysis_router import odoo_router, router as analysis_router
from .human_validation_router import router as human_validation_router
from .invoices_router import router as invoices_router
from .motor_sync_router import router as motor_sync_router
from .workflow_router import router as workflow_router

__all__ = ["analysis_router", "odoo_router", "human_validation_router", "invoices_router", "motor_sync_router", "workflow_router"]

