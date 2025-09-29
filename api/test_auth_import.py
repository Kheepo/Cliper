#!/usr/bin/env python3
import sys
import os

# Change to parent directory and set up the path
os.chdir('..')
sys.path.insert(0, '.')

try:
    from api.routers.auth import router as auth_router
    print('SUCCESS: Auth router imported')
    print(f'Routes: {len(auth_router.routes)}')
    for route in auth_router.routes:
        print(f'  - {route.methods} {route.path}')
except Exception as e:
    print(f'ERROR: {e}')
    import traceback
    traceback.print_exc()

try:
    from api.routers.enhanced_auth import router as enhanced_auth_router
    print('SUCCESS: Enhanced auth router imported')
    print(f'Routes: {len(enhanced_auth_router.routes)}')
except Exception as e:
    print(f'ERROR importing enhanced auth: {e}')
    import traceback
    traceback.print_exc()