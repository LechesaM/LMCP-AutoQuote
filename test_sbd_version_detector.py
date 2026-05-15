import json

from app.services.sbd_version_detector import SBDVersionDetector


def main():
    detector = SBDVersionDetector()

    result = detector.detect_folder("runtime/test_tender_pack")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
