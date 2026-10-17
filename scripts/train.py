import argparse, json
import joblib, numpy as np, pandas as pd
from datasets import load_dataset
from tqdm import tqdm
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
from app.config import ARTIFACT_DIR, DATA_DIR, MODEL_PATH

DATASET_ID = "BEE-spoke-data/consumer-finance-complaints"
DATASET_CONFIG = "has-text"
RARE_LABEL = "Other / rare product"

def split_rows(df, seed, min_class_count):
    test_size = 0.2
    minimum_sample_count = int(np.ceil(min_class_count / (1 - test_size)))
    counts = df.label.value_counts()
    common_labels = set(counts[counts >= minimum_sample_count].index)
    df = df.copy()
    df["label"] = df.label.where(df.label.isin(common_labels), RARE_LABEL)
    if (df.label == RARE_LABEL).sum() == 1:
        df = df[df.label != RARE_LABEL].copy()
    if df.label.nunique() < 2:
        raise ValueError("Not enough complaint classes to make a stratified train/test split.")

    train, test = train_test_split(df, test_size=test_size, random_state=seed, stratify=df.label)
    train_counts = train.label.value_counts()
    keep = set(train_counts[train_counts >= min_class_count].index)
    train = train.copy()
    test = test.copy()
    train["label"] = train.label.where(train.label.isin(keep), RARE_LABEL)
    test["label"] = test.label.where(test.label.isin(keep), RARE_LABEL)
    return train.reset_index(drop=True), test.reset_index(drop=True)

def load_rows(size, seed):
    if size < 1:
        raise ValueError("Sample size must be positive.")
    dataset = load_dataset(DATASET_ID, name=DATASET_CONFIG, split="train")
    shuffled = dataset.shuffle(seed=seed)
    rows = []
    with tqdm(total=size, desc="Sampling CFPB complaints", unit="rows") as progress:
        for record in shuffled:
            narrative = record.get("Consumer complaint narrative")
            product = record.get("Product")
            if not isinstance(narrative, str) or not isinstance(product, str):
                continue
            text = narrative.strip()
            label = product.strip()
            if not text or not label:
                continue
            rows.append({"text": text, "label": label})
            progress.update(1)
            if len(rows) >= size:
                break
    if not rows:
        raise ValueError(f"Dataset {DATASET_ID}/{DATASET_CONFIG} contains no rows with both narrative and Product.")
    return pd.DataFrame(rows)

def select_threshold(y, probs, classes):
    pred = np.asarray(classes)[probs.argmax(axis=1)]; conf = probs.max(axis=1)
    best = None
    for t in np.arange(.20,.951,.025):
        mask = conf >= t
        coverage = float(mask.mean())
        acc = float((pred[mask] == y[mask]).mean()) if mask.any() else 0
        if acc >= .85 and coverage > 0 and (best is None or coverage > best["coverage"]):
            best = {"threshold": round(float(t),3), "coverage":coverage, "accuracy":acc}
    return best or {"threshold":.55,"coverage":0.0,"accuracy":0.0}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--sample-size",type=int,default=15000)
    ap.add_argument("--min-class-count",type=int,default=50)
    ap.add_argument("--seed",type=int,default=42)
    args=ap.parse_args()
    if not 10_000 <= args.sample_size <= 20_000:
        ap.error("--sample-size must be between 10000 and 20000")
    ARTIFACT_DIR.mkdir(parents=True,exist_ok=True); DATA_DIR.mkdir(parents=True,exist_ok=True)
    df=load_rows(args.sample_size,args.seed)
    train,test=split_rows(df,args.seed,args.min_class_count)
    (DATA_DIR/"ocr_test_20.json").write_text(json.dumps(test[["text","label"]].head(20).to_dict("records"),indent=2))
    xtr,xval,ytr,yval=train_test_split(train.text.to_list(),train.label.to_numpy(),test_size=.2,random_state=args.seed,stratify=train.label)
    model=Pipeline([("tfidf",TfidfVectorizer(ngram_range=(1,2),min_df=2,max_features=250000,strip_accents="unicode",sublinear_tf=True,stop_words="english")),
                    ("clf",LogisticRegression(max_iter=1200,class_weight="balanced",solver="liblinear",C=4.0,random_state=args.seed))])
    print(f"Training rows: {len(xtr)}; validation: {len(xval)}; held-out test: {len(test)}")
    model.fit(xtr,ytr); threshold=select_threshold(yval,model.predict_proba(xval),model.classes_)
    model.fit(train.text.to_list(),train.label.to_numpy())
    y=test.label.to_numpy(); probs=model.predict_proba(test.text.to_list()); pred=model.classes_[probs.argmax(axis=1)]
    mask=probs.max(axis=1)>=threshold["threshold"]
    labels=sorted(set(y)|set(pred))
    metrics={"sample_rows":len(df),"train_rows":len(train),"test_rows":len(test),"class_count":len(model.classes_),
      "min_class_count":args.min_class_count,"threshold":threshold["threshold"],
      "validation_auto_route_coverage":threshold["coverage"],"validation_auto_route_accuracy":threshold["accuracy"],
      "test_accuracy":float(accuracy_score(y,pred)),"test_macro_f1":float(f1_score(y,pred,average="macro")),
      "test_weighted_f1":float(f1_score(y,pred,average="weighted")),
      "test_auto_route_coverage":float(mask.mean()),"test_auto_route_accuracy":float((pred[mask]==y[mask]).mean()) if mask.any() else 0.0,
      "classification_report":classification_report(y,pred,output_dict=True,zero_division=0),
      "confusion_matrix_labels":labels,"confusion_matrix":confusion_matrix(y,pred,labels=labels).tolist(),"seed":args.seed}
    joblib.dump({"model":model,"threshold":threshold["threshold"],"metrics":metrics},MODEL_PATH)
    (ARTIFACT_DIR/"metrics.json").write_text(json.dumps(metrics,indent=2))
    print("Saved",MODEL_PATH); print("Test macro-F1:",round(metrics["test_macro_f1"],4))
    print("Test auto-route coverage:",round(metrics["test_auto_route_coverage"]*100,1),"%")
    print("Test auto-route accuracy:",round(metrics["test_auto_route_accuracy"]*100,1),"%")
if __name__=="__main__": main()
