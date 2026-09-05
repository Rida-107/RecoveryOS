import subprocess, sys
from pathlib import Path
base=Path(__file__).resolve().parent
subprocess.check_call([sys.executable, str(base/'data/seed.py')])
subprocess.check_call([sys.executable, str(base/'backend/train_model.py')])
subprocess.call([sys.executable, '-m', 'uvicorn', 'backend.app:app', '--reload'], cwd=base)
