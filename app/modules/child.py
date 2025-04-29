from pydantic import BaseModel
import sqlalchemy as sa
from app.database import get_connection
from fastapi import HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer
from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from passlib.context import CryptContext 
from typing import Optional, List, Union

# --------------------- base models -----------------------
class Child(BaseModel):
    childUserName: str
    email: str
    passwordHash: str
    firstName: str
    lastName: str
    dateOfBirth: str
    timeControl: Optional[int] = None
    parentUserName: str
    profileIcon: Optional[str] = None
    
# moodel with no inserted parent username for parent to sign their kids
class ChildCreate(BaseModel):
    childUserName: str
    email: str
    passwordHash: str
    firstName: str
    lastName: str
    dateOfBirth: str  # datetime.date
    timeControl: Optional[int] = None
    profileIcon: Optional[str] = None

class Token(BaseModel):
    access_token: str
    token_type: str
    
class TokenData(BaseModel):
    username: Union[str, None] = None

class FriendRequest(BaseModel):
    receiverChildUserName: str

class FriendRequestOut(BaseModel):
    requestID: int
    requestStatus: str
    requestTimeStamp: datetime
    senderUserName: str
    senderFirstName: str
    senderLastName: str
    senderProfileIcon: Optional[str] = None

class FriendResponse(BaseModel):
    message: str
    data: Optional[Union[dict, list]] = None

# ------------------- constants --------------------
SECRET_KEY = "ca19e71bbdef859185ed9928a973d7af6095d2c6b9a6bed3684570f40439562f"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
revoked_tokens = set()  


# ---------------------- get child -----------------------------

def get_child(childUserName: str) -> Optional[dict]:
    with get_connection() as conn:
        result = conn.execute(
            sa.text("SELECT * FROM Child WHERE childUserName = :username"),
            {"username": childUserName}
        ).mappings().first()
    
    return dict(result) if result else None

# ---------------------- get the name ----------------------
def get_child_name(childUserName: str) -> Optional[dict]:
    """childs first and last name"""
    with get_connection() as conn:
        result = conn.execute(
            sa.text("SELECT firstName, lastName FROM Child WHERE childUserName = :childUserName"),
            {"childUserName": childUserName}
        ).mappings().first()
    
    return dict(result) if result else None

# ---------------------- update settings ----------------------
def update_settings(childUserName: str, settings: dict) -> FriendResponse:
    """Update child settings"""
    with get_connection() as conn:
        update_fields = []
        update_values = {"childUserName": childUserName}

        for field in ["firstName", "lastName", "profileIcon"]:
            if field in settings:
                update_fields.append(f"{field} = :{field}")
                update_values[field] = settings[field]

        if update_fields:
            conn.execute(
                sa.text(f"""
                    UPDATE Child
                    SET {", ".join(update_fields)}
                    WHERE childUserName = :childUserName
                """),
                update_values
            )
            conn.commit()
    
    return FriendResponse(
        message="Settings updated successfully!",
        data=settings
    )
    
  
# by parent 
def update_child_by_parent(childUserName: str, updates: dict):
    with get_connection() as conn:
        update_fields = []
        update_values = {"childUserName": childUserName} 

        if "firstName" in updates:
            update_fields.append("firstName = :firstName")
            update_values["firstName"] = updates["firstName"]

        if "lastName" in updates:
            update_fields.append("lastName = :lastName")
            update_values["lastName"] = updates["lastName"]

        if "email" in updates:
            update_fields.append("email = :email")
            update_values["email"] = updates["email"]

        if "passwordHash" in updates:
            update_fields.append("passwordHash = :passwordHash")
            update_values["passwordHash"] = updates["passwordHash"]

        if "timeControl" in updates:
            update_fields.append("timeControl = :timeControl")
            update_values["timeControl"] = updates["timeControl"]

        if "profileIcon" in updates:
            update_fields.append("profileIcon = :profileIcon")
            update_values["profileIcon"] = updates["profileIcon"]

        if not update_fields:
            raise HTTPException(status_code=400, detail="No valid fields to update.")

        update_query = sa.text(f"""
            UPDATE Child
            SET {", ".join(update_fields)}
            WHERE childUserName = :childUserName  
        """)

        conn.execute(update_query, update_values)
        conn.commit()

    return {"message": "Child updated successfully"}


#---------------------------------------------------------
# ---------------------- Friendship  ---------------------
#---------------------------------------------------------

# ---------------------- create a friendship request ------------------------
def create_friend_request(sender: str, receiver: str) -> FriendResponse:
    with get_connection() as conn:
        # Validate sender and receiver
        for user, role in [(sender, "Sender"), (receiver, "Receiver")]:
            if not conn.execute(
                sa.text("SELECT 1 FROM Child WHERE childUserName = :username"),
                {"username": user}
            ).scalar():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"{role} child does not exist"
                )

        # existing request
        if conn.execute(
            sa.text("""
                SELECT 1 FROM Request 
                WHERE requestChildUserName = :sender 
                AND ReceiverChildUserName = :receiver 
                AND requestStatus = 'Pending'
            """),
            {"sender": sender, "receiver": receiver}
        ).scalar():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Friend request already exists"
            )

        # new request
        conn.execute(
            sa.text("""
                INSERT INTO Request (requestChildUserName, ReceiverChildUserName, requestStatus)
                VALUES (:sender, :receiver, 'Pending')
            """),
            {"sender": sender, "receiver": receiver}
        )
        conn.commit()
    
    return FriendResponse(
        message="Friend request sent successfully!",
        data=None
    )

# ---------------------- return the requests avialable ----------------------
def get_friend_requests(child_username: str) -> List[dict]:
    with get_connection() as conn:
        results = conn.execute(
            sa.text("""
                SELECT 
                    r.requestID,
                    r.requestStatus,
                    r.requestTimeStamp,
                    sender.childUserName AS senderUserName,
                    sender.firstName AS senderFirstName,
                    sender.lastName AS senderLastName,
                    sender.profileIcon AS senderProfileIcon,
                    receiver.childUserName AS receiverUserName,
                    receiver.firstName AS receiverFirstName,
                    receiver.lastName AS receiverLastName,
                    receiver.profileIcon AS receiverProfileIcon
                FROM Request r
                JOIN Child sender ON r.requestChildUserName = sender.childUserName
                JOIN Child receiver ON r.ReceiverChildUserName = receiver.childUserName
                WHERE r.ReceiverChildUserName = :child_username
                AND r.requestStatus = 'Pending'
                ORDER BY r.requestTimeStamp DESC
            """),
            {"child_username": child_username}
        ).mappings().all()

    return [dict(row) for row in results]


# ---------------------- accept friendship ----------------------
def accept_friend_request(request_id: int, receiver: str) -> FriendResponse:
    """Accept a friend request and remove the request record"""
    with get_connection() as conn:
        request = conn.execute(
            sa.text("""
                SELECT requestChildUserName, ReceiverChildUserName 
                FROM Request 
                WHERE requestID = :request_id 
                AND ReceiverChildUserName = :receiver
                AND requestStatus = 'Pending'
            """),
            {"request_id": request_id, "receiver": receiver}
        ).fetchone()

        if not request:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Friend request not found or already processed"
            )

        sender, receiver_child_username = request

        # Insert into Friendship
        conn.execute(
            sa.text("""
                INSERT INTO Friendship (childUserName1, childUserName2, status)
                VALUES (:child1, :child2, 'Active')
            """),
            {
                "child1": sender,
                "child2": receiver_child_username
            }
        )

        # Delete the request from Request table
        conn.execute(
            sa.text("DELETE FROM Request WHERE requestID = :request_id"),
            {"request_id": request_id}
        )

        conn.commit()

    return FriendResponse(message="Friend request accepted and removed.", data=None)


# ---------------------- reject friendship request ----------------------
def reject_friend_request(request_id: int, receiver: str) -> FriendResponse:
    """Reject a friend request and delete it from the database"""
    with get_connection() as conn:
        request = conn.execute(
            sa.text("""
                SELECT 1 
                FROM Request 
                WHERE requestID = :request_id 
                AND ReceiverChildUserName = :receiver
                AND requestStatus = 'Pending'
            """),
            {"request_id": request_id, "receiver": receiver}
        ).fetchone()

        if not request:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Friend request not found or already processed"
            )

        # Delete the request
        conn.execute(
            sa.text("DELETE FROM Request WHERE requestID = :request_id"),
            {"request_id": request_id}
        )
        conn.commit()

    return FriendResponse(message="Friend request rejected and removed.", data=None)

# ---------------------- get the friends of the child ----------------------
def get_friends(childUserName: str) -> FriendResponse:
    """Get all friends for a child"""
    with get_connection() as conn:
        results = conn.execute(
            sa.text("""
                SELECT c.childUserName, c.firstName, c.lastName, c.profileIcon
                FROM Friendship f
                JOIN Child c ON (
                    (f.childUserName1 = c.childUserName AND f.childUserName2 = :childUserName) OR
                    (f.childUserName2 = c.childUserName AND f.childUserName1 = :childUserName)
                )
                WHERE f.status = 'Active'
                AND c.childUserName != :childUserName
            """),
            {"childUserName": childUserName}
        ).mappings().all()
    
    return FriendResponse(
        message="Friends retrieved successfully",
        data=[dict(row) for row in results]
    )
#-------------------------- friend search --------------------
def search_users(query: str, current_child_username: str) -> FriendResponse:
    with get_connection() as conn:
        results = conn.execute(
            sa.text("""
                SELECT childUserName, firstName, lastName, profileIcon
                FROM Child
                WHERE childUserName LIKE :query
                AND childUserName != :current_user
                LIMIT 10
            """),
            {
                "query": f"%{query}%",
                "current_user": current_child_username
            }
        ).mappings().all()
    
    return FriendResponse(
        message="Search results retrieved successfully",
        data=[dict(row) for row in results]
    )


# ---------------------- block a friend ----------------------
def block_friend(childUserName: str, friendUserName: str) -> FriendResponse:
    """Block a friend"""
    with get_connection() as conn:
        if not conn.execute(
            sa.text("""
                UPDATE Friendship
                SET status = 'Blocked'
                WHERE (
                    (childUserName1 = :childUserName AND childUserName2 = :friendUserName) OR
                    (childUserName1 = :friendUserName AND childUserName2 = :childUserName)
                )
                AND status = 'Active'
            """),
            {"childUserName": childUserName, "friendUserName": friendUserName}
        ).rowcount:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Friendship not found"
            )
        conn.commit()
    
    return FriendResponse(
        message="Friend blocked successfully!",
        data=None
    )
    
#--------------------------- child Sessions ---------------------------------
def start_child_session(childUserName: str):
    with get_connection() as conn:
        now = datetime.utcnow()
        conn.execute(
            sa.text("""
                UPDATE Child
                SET sessionStartTime = :now, isLocked = 0
                WHERE childUserName = :username
            """),
            {"now": now, "username": childUserName}
        )
        conn.commit()
        

def check_usage_status(childUserName: str) -> dict:
    with get_connection() as conn:
        result = conn.execute(
            sa.text("""
                SELECT timeControl, sessionStartTime, isLocked
                FROM Child
                WHERE childUserName = :username
            """),
            {"username": childUserName}
        ).mappings().first()

        if not result:
            raise HTTPException(status_code=404, detail="الطفل غير موجود")

        if result['isLocked']:
            return {"remainingMinutes": 0, "isLocked": True}

        time_allowed = result['timeControl']
        start_time = result['sessionStartTime']

        if not time_allowed or not start_time:
            return {"remainingMinutes": time_allowed or 0, "isLocked": False}

        now = datetime.utcnow()
        elapsed_minutes = (now - start_time).total_seconds() / 60
        remaining = time_allowed - elapsed_minutes

        if remaining <= 0:
            conn.execute(
                sa.text("UPDATE Child SET isLocked = 1 WHERE childUserName = :username"),
                {"username": childUserName}
            )
            conn.commit()
            return {"remainingMinutes": 0, "isLocked": True}

        return {"remainingMinutes": int(remaining), "isLocked": False}

#-------------------------------------------------------------------------
#-------------            child log ins                ------------------
#-------------------------------------------------------------------------


def authenticate_user(childUserName: str, enteredPassword: str) -> Optional[dict]:
    """Authenticate child user with username and password"""
    with get_connection() as conn:
        result = conn.execute(
            sa.text("SELECT passwordHash, childUserName FROM Child WHERE childUserName = :childUserName"),
            {"childUserName": childUserName}
        ).mappings().first()

    if not result:
        return None

    if verify_password(enteredPassword, result['passwordHash']):
        return dict(result)
    return None

def createAccessToken(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token"""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=30))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


async def getCurrentUser(token: str = Depends(oauth2_scheme)) -> dict:
    """Get current authenticated user from JWT token"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"}
    )
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if not username:
            raise credentials_exception
            
        user = get_child(username)
        if not user:
            raise credentials_exception
            
        return user
    except JWTError:
        raise credentials_exception
    
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def parent_login_as_child(childUserName: str):
    child = get_child(childUserName)
    if not child:
        raise HTTPException(status_code=404, detail="Child not found")

    access_token = createAccessToken(
        data={"sub": childUserName},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return {"access_token": access_token, "token_type": "bearer"}
