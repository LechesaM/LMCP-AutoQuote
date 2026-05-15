from app.services.sbd_auto_detection_engine import SBDAutoDetectionEngine

pdf_path = "COM44-2026 SUPPLY AND FITMENT OF COMPACTOR TRUCK TYRES FOR CoM - Doc.pdf"

detections = SBDAutoDetectionEngine.detect_pdf(pdf_path)

print("DETECTIONS:")
for item in detections:
    print(
        {
            "form_code": item.form_code,
            "confidence": item.confidence,
            "buyer_family": item.buyer_family,
            "stamp_allowed": item.stamp_allowed,
            "witness_required": item.witness_required,
            "suggested_profile": item.suggested_profile,
            "page_index": item.page_index,
        }
    )

print("BEST PROFILE:", SBDAutoDetectionEngine.choose_best_profile(detections))
