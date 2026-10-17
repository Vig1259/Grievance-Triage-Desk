import json, random
from pathlib import Path
import joblib, pandas as pd
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from app.config import ARTIFACT_DIR, DATA_DIR, MODEL_PATH
from app.ocr import extract_text

def distance(a,b):
    prev=list(range(len(b)+1))
    for i,ca in enumerate(a,1):
        cur=[i]
        for j,cb in enumerate(b,1): cur.append(min(cur[-1]+1,prev[j]+1,prev[j-1]+(ca!=cb)))
        prev=cur
    return prev[-1]
def cer(ref,hyp): return distance(ref or "",hyp or "")/max(1,len(ref or ""))
def render(text,path,noisy,seed):
    random.seed(seed); font=ImageFont.load_default()
    words=text.split(); lines=[]; line=""
    for w in words:
        if len(line)+len(w)>85: lines.append(line); line=w
        else: line=(line+" "+w).strip()
    if line: lines.append(line)
    img=Image.new("RGB",(900,max(120,50+18*len(lines))),"white"); draw=ImageDraw.Draw(img)
    for i,s in enumerate(lines): draw.text((25,25+18*i),s,fill="black",font=font)
    if noisy:
        img=img.resize((540,max(96,int(img.height*.6)))).filter(ImageFilter.GaussianBlur(.8))
        img=img.rotate(random.uniform(-2.5,2.5),expand=True,fillcolor="white")
    img.save(path)
def main():
    fixture=DATA_DIR/"ocr_test_20.json"
    if not MODEL_PATH.exists() or not fixture.exists(): raise SystemExit("Run python scripts/train.py first.")
    bundle=joblib.load(MODEL_PATH); out=DATA_DIR/"ocr_images"; out.mkdir(parents=True,exist_ok=True)
    rows=[]
    for i,item in enumerate(json.loads(fixture.read_text())):
        original=item["text"]; baseline=bundle["model"].predict([original])[0]
        for mode in ["clean","noisy"]:
            path=out/f"{i+1:02d}_{mode}.png"; render(original,path,mode=="noisy",i)
            extracted,conf=extract_text(path.name,path.read_bytes())
            prediction=bundle["model"].predict([extracted or " "])[0]
            rows.append({"example":i+1,"mode":mode,"true_label":item["label"],"original_prediction":str(baseline),
              "ocr_prediction":str(prediction),"ocr_confidence":round(conf,2),"cer":cer(original,extracted),
              "routing_agreement":bool(prediction==baseline),"routing_correct":bool(prediction==item["label"]),
              "ground_truth":original,"ocr_text":extracted})
    df=pd.DataFrame(rows); df.to_csv(DATA_DIR/"ocr_results.csv",index=False)
    summary={}
    for mode,g in df.groupby("mode"):
        summary[mode]={"mean_cer":float(g.cer.mean()),"routing_agreement_with_original_prediction":float(g.routing_agreement.mean()),
          "routing_accuracy_vs_true_label":float(g.routing_correct.mean()),"mean_ocr_confidence":float(g.ocr_confidence.mean())}
    (ARTIFACT_DIR/"ocr_metrics.json").write_text(json.dumps(summary,indent=2)); print(json.dumps(summary,indent=2))
if __name__=="__main__": main()
