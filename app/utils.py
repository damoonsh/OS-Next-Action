import requests, os
from openai import OpenAI
from datetime import datetime
import pandas as pd

FEATS = ['seconds_passed',
 'pa1_ss',
 'pa2_ss',
 'pa3_ss',
 'day',
 'month',
 'week',
 'year',
 'prev_action_1',
 'prev_action_2',
 'prev_action_3',
 'para1',
 'para2',
 'para3',
 'candidate_action']

CAT_COLS = ['prev_action_1',
 'prev_action_2',
 'prev_action_3',
 'para1',
 'para2',
 'para3',
 'candidate_action']

ALL_ACTIONS = ['DELETE /boards/{boardId}',
 'DELETE /events/{eventId}',
 'DELETE /sprints/{sprintId}',
 'DELETE /tickets/{ticketId}',
 'GET /boards',
 'GET /boards/{boardId}',
 'GET /events',
 'GET /events/{eventId}',
 'GET /sprints',
 'GET /sprints/{sprintId}',
 'GET /sprints/{sprintId}/tickets',
 'GET /tickets',
 'GET /tickets/{ticketId}',
 'GET /tickets/{ticketId}/transitions',
 'PATCH /boards/{boardId}',
 'PATCH /sprints/{sprintId}',
 'PATCH /tickets/{ticketId}',
 'POST /boards',
 'POST /events',
 'POST /sprints',
 'POST /sprints/{sprintId}/tickets',
 'POST /tickets',
 'POST /tickets/{ticketId}/transitions',
 'PUT /budgets/{budget_id}',
 'PUT /costs/{service_id}/{cost_id}',
 'PUT /invoices/{invoice_id}',
 'PUT /invoices/{invoice_id}/status',
 'PUT /revenue/{service_id}/{revenue_id}']

def predict_top_k_actions(model, context_features, k=5):
    candidates = []
    for action in ALL_ACTIONS:
        candidate = context_features.copy()
        candidate['candidate_action'] = action
        candidates.append(candidate)
    
    candidates_df = pd.DataFrame(candidates)
    for col in CAT_COLS:
        if col in candidates_df.columns:
            candidates_df[col] = candidates_df[col].astype('category')
    
    X_test = candidates_df[FEATS]
    scores = model.predict(X_test)
    action_scores = list(zip(ALL_ACTIONS, scores))
    ranked_actions = sorted(action_scores, key=lambda x: x[1], reverse=True)
    
    return ranked_actions[:k]


def generate_history(events):
    lines = ["Event Timeline (from earliest to latest):"]
    
    for event in events:
        endpoint = event['endpoint_abstract']
        params = event['params']
        
        param_str = " ".join([f'{k}:{v}' for k,v in params.items()])
        
        if param_str != " ":
            lines.append(f'{endpoint} with params: {param_str}\n')
        else:
            lines.append(f'{endpoint}\n')
            
    return "\n".join(lines)

def process_spec(client, m, url):
    file_name = url.split('/')[-1].split('.')[0]
    spec_path = f'./specs/{file_name}'
    if os.path.exists(spec_path):
        print('>> Spec already exists')
        with open(spec_path, 'r') as f:
            return f.read()
    else:
        if not os.path.exists('./specs'):
            print('>> Creating specs dir')
            os.makedirs('./specs')
        content = get_endpoint_descriptions(client, m, url)
        with open(spec_path, 'w') as f:
            f.write(content)
        
        print(f'>> Wrote {file_name}')
    return content

def build_endpoint_map(doc_str):
    endpoint_map = {}

    for line in doc_str.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith('-'):
            parts = line[2:].split(' ', 2)
            if len(parts) < 2:
                continue
            method, path = parts[0], parts[1]

            if method not in endpoint_map:
                endpoint_map[method] = []
            endpoint_map[method].append(path)

    return endpoint_map

def match_endpoint(request_str, endpoint_map):
    parts = request_str.strip().split(' ', 1)
    if len(parts) < 2:
        return None

    method, request_path = parts[0], parts[1]
    candidates = endpoint_map.get(method, [])
    request_segments = request_path.strip('/').split('/')

    for template in candidates:
        template_segments = template.strip('/').split('/')
        if len(request_segments) != len(template_segments):
            continue
        match = True
        for seg, temp_seg in zip(request_segments, template_segments):
            if temp_seg.startswith('{') and temp_seg.endswith('}'):
                continue
            if seg != temp_seg:
                match = False
                break
        if match:
            return template 

    return None

def clean_data(data, doc):
    endpoint_map = build_endpoint_map(doc)
    for idx in range(len(data['events'])):
        method = data['events'][idx]['endpoint'].split(" ")[0]
        data['events'][idx]['endpoint_abstract'] = f"{method} {match_endpoint(data['events'][idx]['endpoint'], endpoint_map)}"
    return data

def get_endpoint_descriptions(client, m, spec_url):
    response = requests.get(spec_url)
    response.raise_for_status()
    spec_content = response.text
    
    prompt = f"""
    Analyze this API specification and describe each endpoint in exactly one line.
    Group the endpoints by category using # headers.

    API Specification:
    ```
    {spec_content}
    ```

    Format your response like this:
    # Invoice Management
    - GET /invoices/ - Retrieve all invoices with optional filtering parameters
    - POST /invoices/ - Create a new invoice with customer and line item details
    
    # Payment Processing  
    - GET /payments/ - List all payment transactions with status filtering
    - POST /payments/ - Process a new payment for an existing invoice
    
    Provide concise, clear descriptions for each endpoint grouped by logical business categories.
    """
    
    response = client.chat.completions.create(
        model=m,
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )
    
    return response.choices[0].message.content


PROMPT = """
You are an intelligent API endpoint selector for a SaaS application. Your role is to analyze user interaction history, API specifications, and the ranking provided by XGBRanker — then return a refined, qualitatively justified ranking of next possible actions.

## Core Directive:
→ Use the XGBRanker’s ranking as your starting point.
→ ONLY override or reorder actions if qualitative analysis of the API specs, interaction history, business logic, parameter dependencies, or workflow state DEMONSTRABLY justifies it.
→ If you change the order, EXPLAIN CLEARLY in the reasoning why the XGBRanker ranking is insufficient or incorrect in this context.

## Instructions:

1. **Context Analysis**:
   - Examine interaction history to understand:
     - Endpoints previously called and their parameters (in {{}})
     - Sequence of actions and outcomes
     - User’s current workflow or goal
     - Application state inferred from past calls

2. **Parameter & Dependency Tracking**:
   - Extract and track IDs, filters, and values from prior calls
   - Identify required parameters for next actions
   - Enforce data dependencies (e.g., can’t PATCH invoice without knowing its ID from prior GET)

3. **Business Logic & Spec Compliance**:
   - Respect constraints in API specs (e.g., status transitions, validation rules)
   - Follow CRUD patterns where logical (POST → GET → PATCH → DELETE)
   - Avoid actions that violate state (e.g., deleting non-draft invoices)
   {exclude}

4. **XGBRanker Integration**:
   - Begin with the XGBRanker-provided ranking: {XGB_rankings}
   - Do NOT change the order unless SPECIFIC evidence from specs, history, or logic requires it.
   - If you reorder, your reasoning must explicitly state:
     - What part of the context/specs/logic invalidates the XGBRanker’s ranking
     - Why the new order is more appropriate

5. **Output Format**:
   → Return a JSON array of objects.
   → Each object MUST have ONLY two keys: `"action"` and `"reasoning"`.
   → `"reasoning"` must explain why XGBRanker order may have been changed for a specific item.
   → Change the ranking oder: only and only if the XGBRanker's rank does not make sense at all; otherwise just explain the possible reasoning for it.
   → Order the array by final adjusted likelihood (most probable first).
   → Never include confidence_level, suggested_parameters, or any other keys.
   → If no override is needed, return XGBRanker’s order with reasoning that affirms its validity.

## Interaction History:
{history}

## Available API Specifications:
{api_specs}

## XGBRanker Initial Ranking:
{XGB_rankings}

## Output Example:
[
  {{"action": "GET /invoices/123/", "reasoning": "User just created invoice 123; XGBRanker correctly prioritizes viewing details, and specs confirm this is valid next step"}},
  {{"action": "PATCH /invoices/123/status", "reasoning": "XGBRanker ranked this 3rd, but business logic requires status update before line-item edits — reordered to 2nd"}},
  {{"action": "GET /invoices/123/line-items/", "reasoning": "XGBRanker ranked this 2nd, but specs indicate line-items should only be fetched after status is confirmed — kept 3rd"}}
]

→ Return exactly {k} actions.

Analyze carefully. Only override XGBRanker if absolutely necessary — and justify every change.
"""

def process_events_and_query(data, raw):
    
    user_id = data["user_id"] 
    events = data["events"]
    
    new_rows = []
    for event in events:
        new_row = {
            'session_id': event.get('sesson_id', event.get('session_id', '')), # Handle typo in sesson_id
            'user_id': user_id,
            'timestamp': event['ts'],
            'action': event.get('endpoint_abstract', event.get('endpoint', '')),
            'parameters': str(list(event.get('params', [])))
        }
        new_rows.append(new_row)
    
    print(f"\nAdding {len(new_rows)} new rows from events:")
    for i, row in enumerate(new_rows):
        print(f"{i+1}. {row}")
    
    # Add new rows to raw df
    print(new_rows)
    new_df = pd.DataFrame(new_rows)
    print(new_df)
    raw_updated = pd.concat([raw, new_df], ignore_index=True)
    print(raw_updated.iloc[-3:])
    
    # Apply the processing steps exactly as specified
    df = raw_updated.sort_values(['user_id', 'timestamp']).reset_index(drop=True)
    df['prev_action_1'] = df.groupby('user_id')['action'].shift(1)
    df['prev_action_2'] = df.groupby('user_id')['action'].shift(2)
    df['prev_action_3'] = df.groupby('user_id')['action'].shift(3)
    df['timestamp'] = pd.to_datetime(df['timestamp'], format='ISO8601')
    df['day'] = df['timestamp'].dt.day
    df['month'] = df['timestamp'].dt.month
    df['week'] = df['timestamp'].dt.isocalendar().week
    df['year'] = df['timestamp'].dt.year
    df['seconds_passed'] = (df['timestamp'].dt.hour * 3600 + 
                           df['timestamp'].dt.minute * 60 + 
                           df['timestamp'].dt.second)
    df['pa1_ss'] = df['session_id'] == df.groupby('user_id')['session_id'].shift(1)
    df['pa2_ss'] = df['session_id'] == df.groupby('user_id')['session_id'].shift(2)
    df['pa3_ss'] = df['session_id'] == df.groupby('user_id')['session_id'].shift(3)
    
    row = df.iloc[-1]
    
    # Convert to inference format
    X_inference = {
        'seconds_passed': int(row['seconds_passed']),
        'pa1_ss': float(row['pa1_ss']),
        'pa2_ss': float(row['pa2_ss']), 
        'pa3_ss': float(row['pa3_ss']),
        'day': int(row['day']),
        'month': int(row['month']),
        'week': int(row['week']),
        'year': int(row['year']),
        'prev_action_1': row['prev_action_1'] if pd.notna(row['prev_action_1']) else '',
        'prev_action_2': row['prev_action_2'] if pd.notna(row['prev_action_2']) else '',
        'prev_action_3': row['prev_action_3'] if pd.notna(row['prev_action_3']) else '',
        'para1': '',  # Will be filled from current action parameters
        'para2': '',
        'para3': ''
    }
    
    # Extract parameters from the current action (the row's action, not the latest event)
    current_action_params = row['parameters']
    if current_action_params and current_action_params != "[]":
        # Parse the parameters string (it's stored as a string representation of a list)
        import ast
        try:
            params_list = ast.literal_eval(current_action_params)
            X_inference['para1'] = params_list[0] if len(params_list) > 0 else ''
            X_inference['para2'] = params_list[1] if len(params_list) > 1 else ''
            X_inference['para3'] = params_list[2] if len(params_list) > 2 else ''
        except:
            # If parsing fails, leave empty
            pass
    
    return X_inference
