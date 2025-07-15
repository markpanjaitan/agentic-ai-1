import pymysql
import re
import google.generativeai as genai
from ..config import Config

genai.configure(api_key=Config.GEMINI_API_KEY)

class DatabaseAgent:
    def __init__(self):
        self.conn = pymysql.connect(
            host=Config.DB_HOST,
            port=Config.DB_PORT,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            database=Config.DB_NAME,
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor  # This returns dictionaries
        )
        self.cursor = self.conn.cursor()
        self.schema = self._get_db_schema()
    
    def _get_db_schema(self):
        """Get database schema - updated for DictCursor"""
        schema = ""
        self.cursor.execute("SHOW TABLES")
        tables = [row["Tables_in_" + Config.DB_NAME] for row in self.cursor.fetchall()]
        
        for table in tables:
            self.cursor.execute(f"SHOW COLUMNS FROM `{table}`")
            schema += f"Table: {table}\n"
            for col in self.cursor.fetchall():
                schema += f"- {col['Field']} ({col['Type']})\n"
            schema += "\n"
        return schema.strip()
    
    def _generate_sql(self, question):
        """Generate SQL using LLM"""
        model = genai.GenerativeModel(Config.GEMINI_MODEL)
        prompt = f"""Based on this schema:
{self.schema}

Generate a MySQL query to: {question}
Return ONLY the SQL query ending with semicolon."""
        
        response = model.generate_content(prompt)
        return self._extract_valid_sql(response.text)
    
    @staticmethod
    def _extract_valid_sql(text):
        """Extract valid SQL from LLM response"""
        match = re.search(r"(SELECT\s.+?;)", text, re.IGNORECASE | re.DOTALL)
        return match.group(1).strip() if match else None
    
    def execute_query(self, question):
        """Generate and execute SQL query using LLM"""
        try:
            sql = self._generate_sql(question)
            self.cursor.execute(sql)
            return self.cursor.fetchall()
        except Exception as e:
            print(f"Database query failed: {e}")
            return None
    
    def close(self):
        self.conn.close()