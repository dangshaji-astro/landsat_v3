import requests
r = requests.get('http://localhost:8000/api/predictions')
data = r.json()
preds = data['predictions']

probs = [p['probability'] for p in preds]
rains = [p['rain7'] for p in preds]
from collections import Counter
levels = Counter(p['risk_level'] for p in preds)

print("=== PREDICTION STATS ===")
print("Total:", len(preds))
print("Prob min:", min(probs), "max:", max(probs))
print("Rain min:", min(rains), "max:", max(rains))
print("Levels:", dict(levels))
print("")
top = sorted(preds, key=lambda p: p['probability'], reverse=True)[:5]
for p in top:
    print(f"{p['taluk_name']}: prob={p['probability']} risk={p['risk_level']} rain={p['rain7']}")
