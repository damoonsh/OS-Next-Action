from fastapi import FastAPI, Body
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Any, Optional
import uvicorn
from openai import OpenAI
import json, os
import pandas as pd
import xgboost as xgb
from utils import *
from json_repair import repair_json

app = FastAPI()

client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=os.getenv('AK'))
m = 'qwen/qwen3-30b-a3b:free'

df = pd.read_csv('./cleaned.csv')
raw = pd.read_csv('./mock.csv')

model = xgb.XGBRanker()
model.load_model('./ranker.json')

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all headers
)

@app.get("/")
async def read_root():
    return {"message": "Hello World"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.get("/next")
async def analyze_user_actions(payload: dict):
    global df, raw, m, client
    spec = process_spec(client, m, payload['spec_url'])
    payload = clean_data(payload, spec)
    history = generate_history(payload['events'])
    k = payload.get("k", 5)

    X_inference = process_events_and_query(payload, raw)
    predictions = predict_top_k_actions(model, X_inference, k)
    xgb_rank = ""
    for i, (action, score) in enumerate(predictions, 1):
        xgb_rank += f"{i}. {action}: {score:.4f}\n"

    user_prompt = payload.get("prompt", "")
    if user_prompt != "":
        user_prompt = f'## Additional Context:\n{user_prompt}\n'

    exclude = ""
    if payload.get("safe", False):
        exclude = "- Do not incluce endpoint methods of DELETE, PUT or PATCH from the rankings and replace with the next more likely endpoint.\n"
    
    prompt = PROMPT.format(
        history=history, api_specs=spec, user_prompt_addition=user_prompt,
        XGB_rankings=xgb_rank, exclude=exclude, k=k
    )
    print(prompt)

    response = client.chat.completions.create(
        model=m,
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )

    res = response.choices[0].message.content

    return {'response': repair_json(res)}


# Run the server
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",  # Listen on all available interfaces
        port=8000,
        reload=True  # Enable auto-reload during development
    )
