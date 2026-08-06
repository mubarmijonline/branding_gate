"""WSGI entry point for Gunicorn deployment."""
from branding_gate import (app, run_sales_request_migration,
                           initialize_default_templates, ensure_mongo_indexes)

# Run startup tasks (same as __main__ block)
run_sales_request_migration()

# Notifications and comments live in MongoDB; index them on the way up.
print("✓ Mongo indexes ready" if ensure_mongo_indexes()
      else "⚠ Warning: Mongo indexes could not be built")

template_init_result = initialize_default_templates()
if template_init_result.get('success'):
    print(f"✓ Templates ready: {template_init_result.get('templates_added', 0)} added, "
          f"{template_init_result.get('templates_skipped', 0)} existed")
else:
    print(f"⚠ Warning: Template initialization had issues: {template_init_result.get('error', 'Unknown error')}")

if __name__ == '__main__':
    app.run()
