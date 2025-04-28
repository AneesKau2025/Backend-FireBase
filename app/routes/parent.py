from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from datetime import timedelta
from app.modules import parent as parent_module
from app.modules import child as child_module
from app.modules import message as message_module 
from fastapi import Request
from pydantic import BaseModel

class MinutesUpdate(BaseModel):
    minutes: int

router = APIRouter()


#-------------------------------  signup  --------------------------------------
@router.post("/parent/signup")
def add_parent(parent_data: parent_module.Parent):
    return parent_module.create_parent(parent_data)


#--------------------------------  login  ------------------------------------
@router.post("/parent/login", response_model=parent_module.Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = parent_module.authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=parent_module.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = parent_module.createAccessToken(
        data={"sub": form_data.username}, expiresDelta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}

#--------------------- add a child  ---------------------------
@router.post("/parent/children/add", status_code=status.HTTP_201_CREATED)
def add_child(
    child_data: child_module.ChildCreate,  # now uses ChildCreate
    current_user: dict = Depends(parent_module.getCurrentUser)
):
    parentUserName = current_user["parentUserName"]

    # Manually build full Child model from ChildCreate + parentUserName
    full_child_data = child_module.Child(
        **child_data.dict(),
        parentUserName=parentUserName
    )

    return parent_module.create_child(full_child_data)

#--------------------- get name ---------------------------
@router.get("/parent/name")
def get_parent_name(current_user: dict = Depends(parent_module.getCurrentUser)):
    parentUserName = current_user['parentUserName']
    parent_name = parent_module.get_parent_name(parentUserName)
    
    if not parent_name:
        return {
            "status": "error",
            "message": "Parent not found",
            "data": None
        }
    
    return parent_name

#--------------------- Get Parent Information ---------------------------
@router.get("/parent/info")
def get_parent_info(current_user: dict = Depends(parent_module.getCurrentUser)):
    parentUserName = current_user['parentUserName']
    parent_info = parent_module.get_parent_info(parentUserName)
    
    return parent_info
#----------------- get the children of the parent -----------------------
@router.get("/parent/children")
def get_all_children(current_user: dict = Depends(parent_module.getCurrentUser)):
    parentUserName = current_user['parentUserName']
    children = parent_module.get_children_of_parent(parentUserName)   
    return children

#---------------------- delete account --------------------------
@router.delete("/parent/delete")
def delete_parent_account(current_user: dict = Depends(parent_module.getCurrentUser)):
    parentUserName = current_user['parentUserName']
    result = parent_module.delete_parent_account(parentUserName)    
    return result
    

#--------------------- Get Parent Information ---------------------------
@router.get("/parent/info")
def get_parent_info(current_user: dict = Depends(parent_module.getCurrentUser)):
    parentUserName = current_user['parentUserName']
    parent_info = parent_module.get_parent_info(parentUserName)
    
    if not parent_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Parent not found",
        )   
    return parent_info
    
    
#----------------------- update settings -------------------------
@router.put("/parent/settings")
async def update_parent_settings(
    request: Request,
    current_user: dict = Depends(parent_module.getCurrentUser)
):
    settings = await request.json() 
    parentUserName = current_user['parentUserName']
    result = parent_module.update_parent_settings(parentUserName, settings)
    return result
    

#------------------ see how much child have time ----------------------
@router.get("/parent/children/{childUserName}/usage")
def get_child_usage(
    childUserName: str,
    current_user: dict = Depends(parent_module.getCurrentUser)
):
    parentUserName = current_user['parentUserName']
    return parent_module.get_child_usage_status(parentUserName, childUserName)


#------------- setting time limits for parent child  ------------------
@router.put("/parent/children/{childUserName}/usage/set")
def set_child_usage_time(
    childUserName: str,
    minutes_data: MinutesUpdate,
    current_user: dict = Depends(parent_module.getCurrentUser)
):
    parentUserName = current_user['parentUserName']
    return parent_module.set_child_usage_limit(parentUserName, childUserName, minutes_data.minutes)
#------------------ update child settings --------------------------
@router.put("/parent/children/{childUserName}/update")
def update_child_by_parent(
    childUserName: str,
    updates: dict,
    current_user: dict = Depends(parent_module.getCurrentUser)
):
    return child_module.update_child_by_parent(childUserName, updates)


#--------------- reset the time to zero for setting --------------------
@router.put("/parent/children/{childUserName}/usage/reset")
def reset_child_usage_time(
    childUserName: str,
    current_user: dict = Depends(parent_module.getCurrentUser)
):
    parentUserName = current_user['parentUserName']
    return parent_module.reset_child_usage(parentUserName, childUserName)


#-------------------- get the notifications --------------------------
@router.get("/parent/notifications")
def get_notifications(current_user: dict = Depends(parent_module.getCurrentUser)):
    parentUserName = current_user['parentUserName']
    notifications = message_module.get_notifications(parentUserName)
    return notifications
    

#-------------------- logging out --------------------------

    
@router.post("/parent/logout")
def parent_logout():
    return {
        "message": "Parent logged out successfully"
    }

@router.post("/parent/children/{childUserName}/login")
def get_child_token_from_parent(childUserName: str, current_user: dict = Depends(parent_module.getCurrentUser)):
    return child_module.parent_login_as_child(childUserName)
