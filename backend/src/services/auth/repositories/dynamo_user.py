import time
import uuid
from typing import Optional, Dict, Any

from src.services.database import get_dynamo_resource, get_table_name, decimal_to_python
from src.services.auth.types import IUserReader, IUserWriter
from src.services.logger import get_logger

logger = get_logger("services.auth.dynamo")


class DynamoUserRepository(IUserReader, IUserWriter):

    def __init__(self, table_name: Optional[str] = None):
        self._table_name = table_name or get_table_name("users")
        self._table = None

    @property
    def table(self):
        if self._table is None:
            dynamo = get_dynamo_resource()
            self._table = dynamo.Table(self._table_name)
        return self._table

    def get_user_by_email(self, conn: Any, email: str) -> Optional[dict]:
        """Fetch user record by normalized email from DynamoDB."""
        try:
            norm_email = email.strip().lower()
            resp = self.table.get_item(Key={"email": norm_email})
            item = resp.get("Item")
            if not item:
                return None
            item = decimal_to_python(item)
            return {
                "id": item.get("id"),
                "email": item.get("email"),
                "password_hash": item.get("password_hash"),
                "salt": item.get("salt"),
                "gemini_api_key": item.get("gemini_api_key"),
                "created_at": item.get("created_at"),
            }
        except Exception as e:
            logger.error(f"Error fetching user by email from DynamoDB: {e}", email=email)
            return None

    def get_user_by_id(self, conn: Any, user_id: Any) -> Optional[dict]:
        """Fetch user record by ID from DynamoDB using GSI or scan."""
        try:
            str_id = str(user_id)
            resp = self.table.query(
                IndexName="UserIdIndex",
                KeyConditionExpression="id = :uid",
                ExpressionAttributeValues={":uid": str_id},
            )
            items = resp.get("Items", [])
            if items:
                item = decimal_to_python(items[0])
                return {
                    "id": item.get("id"),
                    "email": item.get("email"),
                    "password_hash": item.get("password_hash"),
                    "salt": item.get("salt"),
                    "gemini_api_key": item.get("gemini_api_key"),
                    "created_at": item.get("created_at"),
                }
            
            scan_resp = self.table.scan(
                FilterExpression="id = :uid",
                ExpressionAttributeValues={":uid": str_id},
            )
            scan_items = scan_resp.get("Items", [])
            if scan_items:
                item = decimal_to_python(scan_items[0])
                return {
                    "id": item.get("id"),
                    "email": item.get("email"),
                    "password_hash": item.get("password_hash"),
                    "salt": item.get("salt"),
                    "gemini_api_key": item.get("gemini_api_key"),
                    "created_at": item.get("created_at"),
                }
            return None
        except Exception as e:
            logger.error(f"Error fetching user by id from DynamoDB: {e}", user_id=str(user_id))
            return None

    def create_user(self, conn: Any, email: str, password_hash: str, salt: str) -> Any:
        """Insert a new user record into DynamoDB and return user ID."""
        norm_email = email.strip().lower()
        user_id = str(uuid.uuid4().hex[:12])
        created_at = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())

        item = {
            "email": norm_email,
            "id": user_id,
            "password_hash": password_hash,
            "salt": salt,
            "gemini_api_key": None,
            "created_at": created_at,
        }
        self.table.put_item(Item=item)
        logger.info("Created user in DynamoDB", email=norm_email, user_id=user_id)
        return user_id

    def update_user_api_key(self, conn: Any, user_id: Any, api_key: Optional[str]) -> bool:
        """Update or clear user's personal Google Gemini API key in DynamoDB."""
        try:
            user = self.get_user_by_id(conn, user_id)
            if not user:
                return False
            
            email = user["email"]
            clean_key = api_key.strip() if api_key else None

            if clean_key:
                self.table.update_item(
                    Key={"email": email},
                    UpdateExpression="SET gemini_api_key = :k",
                    ExpressionAttributeValues={":k": clean_key},
                )
            else:
                self.table.update_item(
                    Key={"email": email},
                    UpdateExpression="REMOVE gemini_api_key",
                )
            logger.info("Updated user API key in DynamoDB", user_id=str(user_id))
            return True
        except Exception as e:
            logger.error(f"Error updating API key in DynamoDB: {e}", user_id=str(user_id))
            return False
