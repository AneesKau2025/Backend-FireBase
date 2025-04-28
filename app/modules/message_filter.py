from openai import AsyncOpenAI
import os
from typing import Tuple, Optional, List
from pydantic import BaseModel
from datetime import datetime
import sqlalchemy as sa
from app.database import get_connection
import re
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class FilteredMessage(BaseModel):
    content: str
    is_filtered: bool
    risk_type: Optional[str] = None
    risk_level: Optional[int] = None
    should_notify_parent: bool = False

class MessageFilter:
    def __init__(self):
        self.client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.risk_types = {
            "inappropriate_content": 1,
            "sexual_content": 2,
            "drug_related": 3
        }

    def mask_content(self, content: str, inappropriate_words: List[str]) -> str:
        """Mask only inappropriate words in the content with asterisks"""
        if not inappropriate_words:
            return content
            
        masked_content = content
        for word in inappropriate_words:
            # Create a regex pattern that matches the word with word boundaries
            pattern = r'\b' + re.escape(word) + r'\b'
            # Replace the word with asterisks of the same length
            masked_content = re.sub(pattern, '*' * len(word), masked_content, flags=re.IGNORECASE)
        
        return masked_content

    def get_child_age(self, child_username: str) -> Optional[int]:
        """Get child's age from the database"""
        try:
            with get_connection() as conn:
                query = sa.text("""
                    SELECT dateOfBirth 
                    FROM Child 
                    WHERE childUserName = :username
                """)
                result = conn.execute(query, {"username": child_username}).scalar()
                
                if result:
                    birth_date = result
                    today = datetime.now()
                    age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
                    return age
                return None
        except Exception as e:
            print(f"Error getting child age: {str(e)}")
            return None

    def extract_classification_number(self, response_text: str) -> int:
        """Extract classification number from model response"""
        try:
            # First try to find a single digit in the response
            numbers = re.findall(r'\d', response_text)
            if numbers:
                num = int(numbers[0])
                # Ensure the number is within our valid range (0-3)
                if 0 <= num <= 3:
                    return num
            
            # If no valid number found, check for keywords in Arabic
            response_lower = response_text.lower()
            if any(word in response_lower for word in ["سليم", "آمن", "جيد", "مقبول"]):
                return 0
            elif any(word in response_lower for word in ["غير لائق", "شتائم", "إهانة"]):
                return 1
            elif any(word in response_lower for word in ["جنسي", "جنسية"]):
                return 2
            elif any(word in response_lower for word in ["مخدرات", "مخدر"]):
                return 3
            
            # Default to safe if no clear classification
            return 0
        except Exception as e:
            print(f"Error extracting classification number: {str(e)}")
            return 0  # Default to safe on error

    async def analyze_message(self, content: str, receiver_username: str) -> Tuple[bool, Optional[str], Optional[int], bool, Optional[List[str]]]:
        """Analyze message content using GPT-4o-mini and check if parent notification is needed"""
        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": """أنت مصنف محتوى للنصوص باللهجة السعودية. صنّف النص وفقًا للفئات التالية، مع إعطاء رقم التصنيف فقط (دون أي شرح إضافي):
0. نص سليم: إذا كان النص لا يحتوي على أي محتوى غير لائق.
1. ألفاظ غير لائقة: إذا كان النص يضم شتائم أو إهانات أو ألفاظ مسيئة.
2. نص جنسي: إذا كان النص يضم وصفًا جنسيًا صريحًا أو تلميحات جنسية واضحة. 
3. مخدرات: إذا كان النص يتحدث عن المخدرات بأي شكل (ترويج، تعاطٍ، اتجار، إلخ).
انتبه للألفاظ المحلية العامية، وحافظ على دقة التصنيف بإعطاء رقم واحد فقط (0 أو 1 أو 2 أو 3).

أجب برقم واحد فقط."""},
                    {"role": "user", "content": content}
                ],
                temperature=0.1
            )
            
            # Extract and validate the classification number
            response_text = response.choices[0].message.content.strip()
            classification = self.extract_classification_number(response_text)
            
            # Get inappropriate words if any
            inappropriate_words = []
            if classification > 0:
                word_response = await self.client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": """حدد الكلمات غير اللائقة في النص التالي فقط، دون أي شرح إضافي.
أجب بالكلمات فقط، كل كلمة في سطر جديد."""},
                        {"role": "user", "content": content}
                    ],
                    temperature=0.1
                )
                words = word_response.choices[0].message.content.strip().split('\n')
                inappropriate_words = [word.strip() for word in words if word.strip()]
            
            # Check if parent notification is needed based on message type and age
            should_notify = False
            child_age = self.get_child_age(receiver_username)
            
            if child_age:
                if classification == 1 and 6 <= child_age <= 9:  # Inappropriate content for ages 6-9
                    should_notify = True
                elif classification == 2 and 6 <= child_age <= 13:  # Sexual content for ages 6-13
                    should_notify = True
                elif classification == 3 and 6 <= child_age <= 17:  # Drug-related content for ages 6-17
                    should_notify = True
            
            if classification == 0:
                return False, None, 0, False, []
            elif classification == 1:
                return True, "inappropriate_content", 1, should_notify, inappropriate_words
            elif classification == 2:
                return True, "sexual_content", 2, should_notify, inappropriate_words
            elif classification == 3:
                return True, "drug_related", 3, should_notify, inappropriate_words
            else:
                return False, None, 0, False, []
            
        except Exception as e:
            print(f"Error analyzing message: {str(e)}")
            return False, None, 0, False, []

    async def filter_message(self, content: str, receiver_username: str) -> FilteredMessage:
        """Filter a message and return the processed result"""
        is_inappropriate, risk_type, risk_level, should_notify, inappropriate_words = await self.analyze_message(content, receiver_username)
        
        if is_inappropriate and risk_type:
            return FilteredMessage(
                content=self.mask_content(content, inappropriate_words),
                is_filtered=True,
                risk_type=risk_type,
                risk_level=risk_level,
                should_notify_parent=should_notify
            )
        
        return FilteredMessage(
            content=content,
            is_filtered=False,
            risk_type=None,
            risk_level=0,
            should_notify_parent=False
        ) 