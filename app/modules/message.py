from pydantic import BaseModel
import sqlalchemy as sa
from sqlalchemy.sql import func
from datetime import datetime
from app.database import get_connection
from fastapi import HTTPException
from app.modules.message_filter import MessageFilter
from typing import Optional

class MessageInput(BaseModel):
    senderChildUserName: str
    receiverChildUserName: str
    content: str

class MessageResponse(BaseModel):
    content: str
    is_filtered: bool
    risk_type: Optional[str] = None
    risk_level: Optional[int] = None
    should_notify_parent: bool = False

async def process_message(msg: MessageInput) -> MessageResponse:
    """Process message content, analyze and mask if needed"""
    try:
        # Initialize message filter
        message_filter = MessageFilter()
        
        # Analyze and filter the message
        filtered_message = await message_filter.filter_message(
            content=msg.content,
            receiver_username=msg.receiverChildUserName
        )
        
        # If the message was filtered and requires parent notification, create a notification
        if filtered_message.is_filtered and filtered_message.should_notify_parent:
            # Generate a unique ID for the Firebase message
            firebase_message_id = f"{msg.senderChildUserName}_{msg.receiverChildUserName}_{datetime.now().timestamp()}"
            
            # Create notification in the database
            create_notification(
                firebase_message_id=firebase_message_id,
                sender_child_username=msg.senderChildUserName,
                receiver_child_username=msg.receiverChildUserName,
                content=filtered_message.content,
                risk_type=filtered_message.risk_type,
                original_content=msg.content
            )
        
        # Return the processed message for Firebase to display
        return MessageResponse(
            content=filtered_message.content,
            is_filtered=filtered_message.is_filtered,
            risk_type=filtered_message.risk_type,
            risk_level=filtered_message.risk_level,
            should_notify_parent=filtered_message.should_notify_parent
        )
        
    except Exception as e:
        print(f"Error processing message: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to process message")

RISK_TYPES = {
    1: "Inappropriate Language",
    2: "Sexual Assault",
    3: "Drugs"
}

def process_message_old(msg: MessageInput):
    if msg.riskID == 0:
        print("Message is safe.")
        return {"message": "Forward to Firebase."}

    risk_type = RISK_TYPES.get(msg.riskID)
    if not risk_type:
        raise HTTPException(status_code=400, detail="Invalid riskID")

    with get_connection() as conn:
        # Verify sender exists
        sender_exists = conn.execute(
            sa.text("SELECT 1 FROM Child WHERE childUserName = :sender"),
            {"sender": msg.senderChildUserName}
        ).scalar()
        if not sender_exists:
            raise HTTPException(status_code=404, detail="Sender child not found")

        # Verify receiver exists
        receiver_exists = conn.execute(
            sa.text("SELECT 1 FROM Child WHERE childUserName = :receiver"),
            {"receiver": msg.receiverChildUserName}
        ).scalar()
        if not receiver_exists:
            raise HTTPException(status_code=404, detail="Receiver child not found")

        insert_msg_query = sa.text("""
            INSERT INTO Notification (senderChildUserName, receiverChildUserName, content, RiskID, notificationFlag)
            VALUES (:sender, :receiver, :content, :riskID, 1)
        """)

        conn.execute(insert_msg_query, {
            "sender": msg.senderChildUserName,
            "receiver": msg.receiverChildUserName,
            "content": msg.content,
            "riskID": msg.riskID
        })
        conn.commit()

        message_id = conn.execute(sa.text("SELECT LAST_INSERT_ID() AS id")).scalar()

    create_notification(message_id, msg.receiverChildUserName, risk_type, msg.content)
    return {"message": f"Risky message stored. Notification for '{risk_type}' created."}

def create_notification(firebase_message_id: str, sender_child_username: str, receiver_child_username: str, content: str, risk_type: str, original_content: str):
    with get_connection() as conn:
        # Get parent username for the receiver child
        parent_query = sa.text("""
            SELECT parentUserName FROM Child WHERE childUserName = :receiver
        """)
        result = conn.execute(parent_query, {"receiver": receiver_child_username}).mappings().first()

        if not result:
            raise HTTPException(status_code=404, detail="Receiver child not found")

        parent_username = result["parentUserName"]
        
        # Insert notification into the database
        insert_notification_query = sa.text("""
            INSERT INTO Notification (
                firebaseMessageID, 
                senderChildUserName, 
                receiverChildUserName, 
                parentUserName, 
                content, 
                originalContent,
                riskType
            )
            VALUES (
                :firebase_message_id, 
                :sender_username, 
                :receiver_username, 
                :parent_username, 
                :content, 
                :original_content,
                :risk_type
            )
        """)
        
        conn.execute(insert_notification_query, {
            "firebase_message_id": firebase_message_id,
            "sender_username": sender_child_username,
            "receiver_username": receiver_child_username,
            "parent_username": parent_username,
            "content": content,
            "original_content": original_content,
            "risk_type": risk_type
        })
        conn.commit()
        
        print(f"🔔 Notification created for {parent_username} regarding message {firebase_message_id} with risk: {risk_type}")
        return {"status": "Notification created successfully"}

def get_notifications(parentUserName: str):
    with get_connection() as conn:
        query = sa.text("""
            SELECT 
                COALESCE(n.notificationID, n.messageID) AS notificationID,
                n.content,
                n.originalContent,
                n.timeStamp,
                n.senderChildUserName AS sender,
                n.receiverChildUserName AS receiver,
                c.firstName AS receiverFirstName,
                c.lastName AS receiverLastName,
                COALESCE(n.riskType, CASE 
                    WHEN n.riskID = 1 THEN 'Inappropriate Language'
                    WHEN n.riskID = 2 THEN 'Sexual Content'
                    WHEN n.riskID = 3 THEN 'Drugs'
                    ELSE NULL
                END) AS riskType
            FROM 
                Notification n
            JOIN 
                Child c ON n.receiverChildUserName = c.childUserName
            WHERE 
                c.parentUserName = :parentUserName
            ORDER BY n.timeStamp DESC
        """)
        results = conn.execute(query, {"parentUserName": parentUserName}).mappings().fetchall()

    return [dict(row) for row in results] if results else []
