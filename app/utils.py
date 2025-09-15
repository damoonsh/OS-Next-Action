import requests
from openai import OpenAI

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


BASE_PROMPT = """
You are an intelligent API endpoint selector for a finance SaaS application. Your role is to analyze user interaction history and determine the most appropriate next endpoint to invoke based on the context, previous actions, and available API specifications.

## Instructions:

1. **Context Analysis**: Carefully examine the interaction history to understand:
   - What endpoints were previously called and with which parameters (shown in curly braces {{}})
   - The sequence of user actions and their outcomes
   - Any patterns or workflows the user is following
   - Current state of the application based on previous API calls

2. **Parameter Extraction**: Pay special attention to parameters passed in previous interactions:
   - Extract IDs, filters, and values from previous endpoint calls
   - Consider how these parameters influence the next logical step
   - Identify any missing parameters that might be needed

3. **Endpoint Selection Logic**: 
   - Choose endpoints that logically follow from the user's current workflow
   - Consider CRUD operation sequences (e.g., POST → GET → PATCH → DELETE)
   - Prioritize endpoints that complete user goals or provide necessary follow-up actions
   - Account for business logic constraints (e.g., can't delete invoices that aren't in 'draft' status)

4. **Response Format**: Provide your response as a JSON object with:
   - `selected_endpoint`: The HTTP method and path of the recommended endpoint
   - `reasoning`: Brief explanation of why this endpoint was chosen
   - `suggested_parameters`: Any parameters that should be included based on context
   - `confidence_level`: High/Medium/Low based on how certain you are about the selection

## Interaction History:

{history}

## Available API Specifications:

{api_specs}

## Additional Context:
{user_prompt_addition}
- Consider the current user's workflow state and business logic requirements
- If multiple endpoints seem equally valid, prioritize those that:
  1. Complete the current user task
  2. Provide essential follow-up information
  3. Enable the next logical step in the business process
- Account for any error conditions or validation requirements mentioned in the API specs
- Consider data dependencies between endpoints (e.g., needing invoice_id from previous GET /invoices/ call)

## Output Format:
Return a JSON array containing the most likely actions ordered by probability (most likely first). Each action should include the endpoint and reasoning:
{exclude_delete}
{{
  {{"action": "GET /invoices/123/", "reasoning": "User just created invoice 123 and likely wants to view the complete details"}},
  {{"action": "PATCH /invoices/123/status", "reasoning": "Natural next step would be to update the invoice status from draft to pending"}},
  {{"action": "GET /invoices/123/line-items/", "reasoning": "User might want to review or modify the line items of the newly created invoice"}}
}}

Analyze the interaction history and return your top 3 most likely next actions with their reasoning.
"""

from datetime import datetime
from typing import List, Dict, Any

def format_params(params: Dict[str, Any]) -> str:
    if not isinstance(params, dict) or not params:
        return ""
    
    param_pairs = []
    for key, value in params.items():
        param_pairs.append(f"{key}={value}")
    
    param_str = ', '.join(param_pairs)
    return f" ({param_str})" if param_str else ""

def generate_history(events: List[Dict[str, Any]]) -> str:
    if not events:
        return "No events recorded."
    
    lines = ["Event Timeline:"]
    
    for i, event in enumerate(events, 1):
        ts = event.get('ts', '')
        try:
            dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
            time_only = dt.strftime('%H:%M:%S')
        except:
            time_only = 'Unknown'
        
        endpoint = event.get('endpoint', 'Unknown')
        params = event.get('params', {})
        
        param_str = format_params(params)
        
        lines.append(f"{time_only} - {endpoint}{param_str}")
    
    return "\n".join(lines)