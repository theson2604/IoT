"""Phase 0 scaffold; no device writes, network connections, AI, cloud, or OTA."""
import argparse

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', action='version', version='energy-gateway 0.1.0-scaffold')
    parser.parse_args()
    print('Gateway scaffold only: transport and telemetry implementation deferred.')

if __name__ == '__main__':
    main()
