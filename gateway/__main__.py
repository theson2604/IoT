import argparse
import logging
import uvicorn
from gateway.app.config import Settings

def main():
    parser = argparse.ArgumentParser(description='Local energy gateway (loopback HTTP only)')
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--version', action='version', version='energy-gateway 0.2.0')
    args = parser.parse_args()
    settings = Settings.from_env()
    logging.basicConfig(level=settings.log_level, format='%(asctime)s %(levelname)s %(name)s %(message)s')
    uvicorn.run('gateway.app.main:create_app', factory=True, host='127.0.0.1', port=args.port)

if __name__ == '__main__':
    main()
