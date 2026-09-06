import sys
sys.path.insert(0, 'backend')
for mod in ['auth', 'cameras', 'vehicles', 'analytics', 'alerts', 'observations', 'admin', 'trajectory', 'gis']:
    try:
        __import__('app.api.v1.' + mod)
        print(mod, ': OK')
    except Exception as e:
        print(mod, ': ERROR', e)

from app.main import app
print('Total FastAPI routes registered:', len(app.routes))
