from fastapi import APIRouter, Depends, Request
from app.modules.chatbot import Chatbot 
import asyncio

router = APIRouter()

chatbot = Chatbot()

@router.post("/chatbot/ask")
async def ask_chatbot(request: Request):
    body = await request.json()
    message = body.get("message")
    child_username = body.get("childUsername")

    if not message or not child_username:
        return {"error": "الرجاء إرسال الرسالة واسم المستخدم"}

    response = await chatbot.get_response(child_username, message)
    return {"response": response}
