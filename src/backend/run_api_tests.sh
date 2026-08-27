#!/bin/bash
# 简单的 API 测试脚本

BASE_URL="http://localhost:8000"

echo "=== API 集成测试 ==="
echo

# Test 1: Create conversation
echo "Test 1: Create conversation"
RESPONSE=$(curl -s -X POST "$BASE_URL/api/conversations" \
  -H "Content-Type: application/json" \
  -d '{"patientId": "0xTest123", "title": "API 测试对话"}')
echo "Response: $RESPONSE"
CONVERSATION_ID=$(echo $RESPONSE | python3 -c "import sys, json; print(json.load(sys.stdin).get('conversationId', ''))")
echo "Conversation ID: $CONVERSATION_ID"
echo

# Test 2: Get conversations
echo "Test 2: Get conversations list"
RESPONSE=$(curl -s "$BASE_URL/api/conversations")
echo "Response: $RESPONSE"
echo

# Test 3: Get conversation by ID
echo "Test 3: Get conversation by ID"
if [ -n "$CONVERSATION_ID" ]; then
  RESPONSE=$(curl -s "$BASE_URL/api/conversations/$CONVERSATION_ID")
  echo "Response: $RESPONSE"
  echo
fi

# Test 4: Send message
echo "Test 4: Send message"
if [ -n "$CONVERSATION_ID" ]; then
  RESPONSE=$(curl -s -X POST "$BASE_URL/api/conversations/$CONVERSATION_ID/messages" \
    -H "Content-Type: application/json" \
    -d '{"content": "我头痛已经 3 天了", "contextWindow": 5}')
  echo "Response: $RESPONSE"
  echo
fi

# Test 5: Delete conversation
echo "Test 5: Delete conversation"
if [ -n "$CONVERSATION_ID" ]; then
  RESPONSE=$(curl -s -X DELETE "$BASE_URL/api/conversations/$CONVERSATION_ID")
  echo "Response: $RESPONSE"
  echo
fi

echo "=== 测试完成 ==="
