"""
Test resolve_invoice_pdf and debug_invoice_pdf against a known invoice
that has a core_profile with a PDF path.
"""
import sys, json
sys.path.insert(0, 'agent_local_v1/app')
sys.path.insert(0, 'agent_local_v1')
sys.path.insert(0, '.')

# Load env vars from .env
from dotenv import load_dotenv
load_dotenv('agent_local_v1/.env')

# Use the BOUCHERIE IFRI invoice we already identified
INVOICE_ID = 'fr_bd_892833831:00063ada-ba29-4717-b704-992d158ec6ca'

# Also test a core_profile doc we found that definitely has a PDF path
CORE_PROFILE_INVOICE = 'fr_bd_310496013:2024:02123680b46d4ff6517d3313'

from app.invoice_engine_service import debug_invoice_pdf, resolve_invoice_pdf

print("=" * 60)
print(f"DEBUG: {INVOICE_ID}")
print("=" * 60)
result = debug_invoice_pdf(INVOICE_ID)
print(json.dumps(result, ensure_ascii=False, indent=2, default=str))

print()
print("=" * 60)
print(f"DEBUG (core_profile doc): {CORE_PROFILE_INVOICE}")
print("=" * 60)
result2 = debug_invoice_pdf(CORE_PROFILE_INVOICE)
print(json.dumps({
    k: result2[k] for k in [
        'invoice_id', 'raw_pdf_path', 'field_used',
        'core_profile_id', 'core_profile_raw_path',
        'matched_prefix', 'resolved_pdf_path_preview', 'exists_on_disk',
        'path_mappings'
    ] if k in result2
}, ensure_ascii=False, indent=2, default=str))

print()
print("=" * 60)
print("RESOLVE (BOUCHERIE IFRI invoice):")
print("=" * 60)
try:
    kind, payload = resolve_invoice_pdf(INVOICE_ID)
    print(f"kind={kind}")
    if kind == "disk":
        print(f"path={payload}")
    else:
        print("couch_attachment returned")
except FileNotFoundError as e:
    print(f"FileNotFoundError: {e}")
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")
