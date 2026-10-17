import re
from app.config import MODEL_PATH, DEFAULT_THRESHOLD, MIN_TEXT_CHARS

FINANCIAL_CUE = re.compile(
    r"\b(?:bank|banking|account|checking|savings|credit|debit|card|loan|mortgage|debt|"
    r"collection|collector|transaction|transfer|payment|interest|overdraft|lender|payday|"
    r"deposit|withdrawal|wire|financial|finance|billing|bill|fee|charge|refund)\b",
    re.IGNORECASE,
)
OUT_OF_SCOPE_MESSAGE = (
    "This desk accepts consumer-finance complaints only, such as bank, card, loan, "
    "credit-reporting, debt, payment, or money-transfer issues. We cannot accept this complaint as written."
)

class RouterNotTrained(RuntimeError):
    pass

def load_model():
    import joblib
    if not MODEL_PATH.exists():
        raise RouterNotTrained(f"Model not found at {MODEL_PATH}. Run: python scripts/train.py")
    return joblib.load(MODEL_PATH)

def predict(text, bundle=None):
    text = (text or "").strip()
    if not text:
        raise ValueError("Enter complaint text or upload an image/PDF before submitting.")
    if not FINANCIAL_CUE.search(text):
        raise ValueError(OUT_OF_SCOPE_MESSAGE)
    bundle = bundle or load_model()
    model = bundle["model"]
    probs = model.predict_proba([text])[0]
    ranked = sorted([{"department": str(c), "confidence": float(p)}
                     for c, p in zip(model.classes_, probs)],
                    key=lambda x: x["confidence"], reverse=True)[:3]
    reasons = []
    if len(text) < MIN_TEXT_CHARS:
        reasons.append("text_too_short")
    if ranked[0]["confidence"] < float(bundle.get("threshold", DEFAULT_THRESHOLD)):
        reasons.append("low_classifier_confidence")
    return {"predicted_department": ranked[0]["department"], "top3": ranked,
            "confidence": ranked[0]["confidence"], "needs_review": bool(reasons),
            "review_reason": ",".join(reasons) or None}
