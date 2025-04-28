from fastapi import APIRouter
from app.modules import message as message_module
from app.modules.message_filter import MessageFilter, FilteredMessage
from pydantic import BaseModel
from datetime import datetime

router = APIRouter()
message_filter = MessageFilter()

# Dummy input model 
class TestMessageInput(BaseModel):
    senderChildUserName: str
    receiverChildUserName: str
    content: str
    risk_level: int  # manually injected to simulate AI output

class MessageInput(BaseModel):
    senderChildUserName: str
    receiverChildUserName: str
    content: str

@router.post("/message/send")
async def send_message(data: MessageInput):
    # Filter the message content
    filtered_message = await message_filter.filter_message(data.content, data.receiverChildUserName)
    
    # Create message input with filtered content
    message = message_module.MessageInput(
        senderChildUserName=data.senderChildUserName,
        receiverChildUserName=data.receiverChildUserName,
        content=filtered_message.content,
        riskID=message_filter.risk_types.get(filtered_message.risk_type, 0) if filtered_message.is_filtered else 0
    )
    
    # Process the message
    result = message_module.process_message(message)
    
    # If the message was filtered and requires parent notification, create a notification
    if filtered_message.is_filtered and filtered_message.should_notify_parent:
        # Generate a unique ID for the Firebase message
        firebase_message_id = f"{data.senderChildUserName}_{data.receiverChildUserName}_{datetime.now().timestamp()}"
        
        message_module.create_notification(
            firebase_message_id=firebase_message_id,
            sender_child_username=data.senderChildUserName,
            receiver_child_username=data.receiverChildUserName,
            content=filtered_message.content,  # Masked content
            risk_type=filtered_message.risk_type,
            original_content=data.content  # Original unmasked content
        )
    
    return {
        "message": "Message processed successfully",
        "content": filtered_message.content,  # Return masked content to frontend
        "is_filtered": filtered_message.is_filtered,
        "risk_type": filtered_message.risk_type,
        "risk_level": filtered_message.risk_level,
        "parent_notified": filtered_message.should_notify_parent
    }

# Keep the test endpoint for backward compatibility
@router.post("/message/test")
def process_message(data: MessageInput):
    message = message_module.MessageInput(
        senderChildUserName=data.senderChildUserName,
        receiverChildUserName=data.receiverChildUserName,
        content=data.content,
        riskID=0  # Default to safe message
    )
    return message_module.process_message(message)

