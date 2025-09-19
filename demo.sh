#!/bin/bash

URL="http://127.0.0.1:8000/next"

PAYLOAD='{
  "user_id": "user_1",
  "events": [
    {
      "ts": "2025-03-05 13:20:17+00:00",
      "endpoint": "GET /invoices",
      "sesson_id": "76dbd4b8-18f3-4e6b-bf1d-94b2412a4e33",
      "params": {"board_id": "123"}
    },
    {
      "ts": "2025-03-05 13:22:01+00:00",
      "endpoint": "PUT /invoices/123/status",
      "sesson_id": "76dbd4b8-18f3-4e6b-bf1d-94b2412a4e33",
      "params": {
        "status": "DRAFT"
      }
    }
  ],
  "spec_url": "https://raw.githubusercontent.com/damoonsh/OS-Next-Action/refs/heads/main/specs/ops.yaml",
  "k": 5
}'

echo "Making request to $URL"
echo "Status Code and Response:"

curl -X POST \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD" \
  -w "\nStatus Code: %{http_code}\n" \
  "$URL" | python3 -m json.tool 2>/dev/null || echo "Response is not valid JSON"

echo ""
echo "Request 1 completed."


PAYLOAD='{
  "user_id": "user_4",
  "events": [
    {
      "ts": "2025-03-12T11:48:17Z",
      "endpoint": "POST /tickets/odk0-2323k0-1212/transitions",
      "sesson_id": "8ca0ab1f-4294-4a00-86ef-2d750453c0fe",
      "params": {"board_id": "123"}
    },
    {
      "ts": "2025-03-12T12:02:17Z",
      "endpoint": "DELETE /events/123",
      "sesson_id": "8ca0ab1f-4294-4a00-86ef-2d750453c0fe",
      "params": {
        "status": "DRAFT"
      }
    },
    {
      "ts": "2025-03-12T12:12:17Z",
      "endpoint": "GET /sprints/hjgk-102",
      "sesson_id": "8ca0ab1f-4294-4a00-86ef-2d750453c0fe",
      "params": {"sprintID": "hjgk-102"}
    }
  ],
  "spec_url": "https://raw.githubusercontent.com/damoonsh/OS-Next-Action/refs/heads/main/specs/jira.yaml",
  "k": 3
}'

# Make the GET request with JSON payload (Note: Changed to POST since GET with body is unusual)
echo "Making request to $URL"
echo "Status Code and Response:"

curl -X POST \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD" \
  -w "\nStatus Code: %{http_code}\n" \
  "$URL" | python3 -m json.tool 2>/dev/null || echo "Response is not valid JSON"

echo ""
echo "Request 2 completed."