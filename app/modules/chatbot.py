from openai import AsyncOpenAI
import os
from typing import Optional
from datetime import datetime
import sqlalchemy as sa
from app.database import get_connection
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Chatbot:
    def __init__(self):
        self.client = AsyncOpenAI(api_key=os.getenv("CHATBOT_OPENAI_API_KEY"))
        
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

    def get_age_group(self, age: int) -> str:
        """Determine the age group for response tailoring"""
        if age <= 6:
            return "preschool"
        elif 7 <= age <= 9:
            return "early_elementary"
        elif 10 <= age <= 12:
            return "late_elementary"
        elif 13 <= age <= 15:
            return "early_teen"
        else:
            return "teen"

    def get_system_prompt(self, age_group: str) -> str:
        """Get appropriate system prompt based on age group"""
        prompts = {
            "preschool": """أنت مساعد ودود للأطفال في مرحلة ما قبل المدرسة. استخدم لغة بسيطة وجمل قصيرة.
            كن مرحاً واستخدم أمثلة من عالمهم الصغير. تجنب الكلمات المعقدة.""",
            
            "early_elementary": """أنت مساعد صديق للأطفال في المرحلة الابتدائية المبكرة. استخدم لغة واضحة وبسيطة.
            قدم أمثلة من حياتهم اليومية. كن مشجعاً وداعماً.""",
            
            "late_elementary": """أنت مرشد للأطفال في المرحلة الابتدائية المتأخرة. استخدم لغة واضحة مع بعض المفاهيم المتقدمة.
            قدم أمثلة عملية وشجع التفكير النقدي.""",
            
            "early_teen": """أنت مرشد للأطفال في بداية مرحلة المراهقة. استخدم لغة مناسبة لعمرهم مع تقديم مفاهيم أكثر تعقيداً.
            شجع الاستقلالية والتفكير النقدي.""",
            
            "teen": """أنت مرشد للمراهقين. استخدم لغة ناضجة ومناسبة لعمرهم.
            شجع التفكير المستقل واتخاذ القرارات المسؤولة."""
        }
        return prompts.get(age_group, prompts["early_elementary"])

    async def get_response(self, child_username: str, message: str) -> str:
        """Get age-appropriate response for the child's message"""
        try:
            # Get child's age
            age = self.get_child_age(child_username)
            if not age:
                return "عذراً، حدث خطأ في تحديد عمرك. يرجى المحاولة مرة أخرى لاحقاً."

            # Determine age group
            age_group = self.get_age_group(age)
            
            # Create messages array with system prompt and current message only
            messages = [
                {"role": "system", "content": self.get_system_prompt(age_group)},
                {"role": "user", "content": message}
            ]

            # Get response from GPT
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                temperature=0.7,
                max_tokens=150
            )

            # Return response without storing history
            return response.choices[0].message.content.strip()

        except Exception as e:
            print(f"Error getting chatbot response: {str(e)}")
            return "عذراً، حدث خطأ في معالجة رسالتك. يرجى المحاولة مرة أخرى لاحقاً."